"""Static code analysis — runs registered analyzers on source files via Registry."""
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field

import src.analyzer.io.tools.buf_lint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.clippy  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.cppcheck  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.dart_analyze  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.dotnet_format  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.eslint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.golangci_lint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.hadolint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.htmlhint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.ktlint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.phpstan  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.psscriptanalyzer  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.python  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.rubocop  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.semgrep  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.shellcheck  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.slither  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.sqlfluff  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.stylelint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.swiftlint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.tflint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.tsc  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.yamllint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
from src.analyzer.pure.language import detect_language, is_test_file
from src.analyzer.pure.registry import REGISTRY, AnalyzeContext, AnalysisIssue
from src.analyzer.io.tools.python import _BanditAnalyzer, _Flake8Analyzer, _PylintAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class StaticAnalysisResult:
    """Aggregated static analysis result for one source file."""

    filename: str
    issues: list[AnalysisIssue] = field(default_factory=list)
    # 도구 subprocess 타임아웃으로 일부 분석이 누락됐는지 — 파이프라인이 이를 모아
    # static_analysis_incomplete 마커로 승격해 auto-merge/auto-approve 를 차단(#7 fail-closed).
    # Whether a tool subprocess timed out (analysis partially missing) — the pipeline aggregates
    # this into the static_analysis_incomplete marker to block auto-merge/approve (#7 fail-closed).
    incomplete: bool = False
    # 이 파일 언어를 지원하지만 바이너리가 없어 실행되지 못한 도구 이름 — 커버리지 관측.
    # 이전엔 이 사실이 어디에도 기록되지 않아 "분석했는데 깨끗함" 과 구별 불가였다(감사 P0).
    # Analyzer names that support this file's language but could not run (binary absent).
    # Previously unrecorded, making "no analyzer ran" indistinguishable from "analyzed, clean".
    unavailable_tools: list[str] = field(default_factory=list)


def analyze_file(  # pylint: disable=too-many-locals
    filename: str, content: str, repo_config: object | None = None
) -> StaticAnalysisResult:
    """Run all applicable registered analyzers on a single file.

    repo_config: RepoConfig ORM 인스턴스 또는 disabled_tools 속성을 가진 객체 (선택).
    repo_config: RepoConfig ORM instance or any object with disabled_tools attribute (optional).
    repo_config.disabled_tools 에 포함된 analyzer는 스킵된다.
    Analyzers whose name appears in repo_config.disabled_tools are skipped.
    """
    if not content.strip():
        return StaticAnalysisResult(filename=filename)

    language = detect_language(filename, content)
    is_test = is_test_file(filename, language)

    result = StaticAnalysisResult(filename=filename)

    # Python 도구는 .py 확장자를 임시 파일에 써야 올바르게 작동
    # Python tools require the .py extension on the temp file to function correctly.
    # 확장자 정제: 최대 10자, 영숫자·점·하이픈만 허용 — 경로 탐색/확장자 인젝션 방지
    # Sanitise extension: max 10 chars, alphanumeric/dot/hyphen only — prevent path traversal.
    raw_ext = os.path.splitext(filename)[1]
    safe_ext = re.sub(r"[^a-zA-Z0-9._-]", "", raw_ext)[:10] or ".tmp"
    suffix = ".py" if language == "python" else safe_ext

    # TemporaryDirectory 사용 — delete=False + 수동 unlink 방식의 TOCTOU 경합 조건을 제거.
    # Use TemporaryDirectory to eliminate the TOCTOU race condition present with
    # NamedTemporaryFile(delete=False) + manual os.unlink().
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, f"analyze{suffix}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        ctx = AnalyzeContext(
            filename=filename,
            content=content,
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
            repo_config=repo_config,
        )
        # per-repo 비활성화 도구 목록 — 루프 외부에서 한 번만 조회
        # Fetch disabled tools list once before the loop
        _disabled = getattr(ctx.repo_config, 'disabled_tools', None) or []
        # 커버리지 관측 — 이 언어를 지원하는 도구 중 실제로 **실행된** 개수를 센다.
        # Coverage observation — count analyzers that actually RAN for this file's language.
        ran = 0
        opted_out = 0  # 운영자가 명시적으로 끈 도구 수 — 승격 판정에서 제외(의도된 미분석)
        for analyzer in REGISTRY:
            if not analyzer.supports(ctx):
                continue
            if not analyzer.is_enabled(ctx):
                # 바이너리 부재 = 배포 이미지에 조달되지 않음. 기록만 하고 계속 — 승격 판정은
                # 루프 종료 후 "실행 0개" 일 때만(semgrep 등이 커버하는 언어의 과차단 방지).
                # Binary absent. Record only; promotion is decided after the loop, and only when
                # ZERO analyzers ran — otherwise languages covered by semgrep would be over-blocked.
                result.unavailable_tools.append(analyzer.name)
                continue
            if analyzer.name in _disabled:
                # 운영자가 명시적으로 끈 것 — 의도된 opt-out. 미커버로 세지 않고, 이 파일에서
                # 승격 자체를 억제한다(아래 조건). "내가 껐다" 를 결함으로 되돌려주면 안 된다.
                opted_out += 1
                continue
            try:
                result.issues.extend(analyzer.run(ctx))
                ran += 1
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                # 🔴 감사 ④ (옵션 B): 도구가 내부에서 못 잡은 예상외 crash 는 이슈를 무음 폐기하므로
                # incomplete 로 승격 — 타임아웃(ctx.timed_out)과 동일하게 fail-closed 처리해 미분석
                # 코드의 auto-merge/auto-approve 를 차단한다(이전엔 로깅만 하고 삼켜 fail-open).
                # 의도적 미설치는 이 분기에 도달하지 않아 현행(opt-out) 유지 — 도구들이 내부에서 (1)
                # `shutil.which` 게이트(supports/is_enabled) 또는 (2) `except (json.JSONDecodeError, OSError)`
                # (FileNotFoundError 는 OSError 서브클래스)로 [] 를 반환하기 때문(옵션 B 경계).
                # Audit ④ (option B): an unexpected crash a tool failed to catch silently drops its issues,
                # so promote to incomplete — fail-closed like the timeout path (ctx.timed_out) to block
                # auto-merge/approve of unanalyzed code (previously logged-and-swallowed = fail-open).
                # Intentional absence never reaches here — tools return [] internally via either (1) a
                # shutil.which gate or (2) except (json.JSONDecodeError, OSError) (FileNotFoundError is an
                # OSError subclass) → missing tools keep current behaviour (opt-out, option B boundary).
                logger.warning("analyzer %s failed for %s: %s", analyzer.name, ctx.filename, exc)
                result.incomplete = True

    # 도구 subprocess 타임아웃 신호를 결과로 승격 — 타임아웃 도구는 이슈를 무음 폐기하므로
    # incomplete 로 표시해 파이프라인이 미분석 코드 auto-merge 를 차단하게 한다(#7 fail-closed).
    # Promote the tool subprocess-timeout signal — timed-out tools silently drop issues, so flag
    # incomplete to let the pipeline block auto-merge of unanalyzed code (#7 fail-closed).
    if ctx.timed_out:
        result.incomplete = True

    # 🔴 커버리지 승격 (2026-07-30 감사 P0) — 이 파일 언어를 지원하는 도구가 **하나도 실행되지
    # 않았고** 그 사유가 바이너리 부재면 incomplete. 실행 0개는 "이슈 0건"(=정적 만점 45/45)과
    # 구별 불가라, 배포 이미지에 없는 분석기 언어(Dart·PowerShell·Protobuf·CSS 등)가 결함 유무와
    # 무관하게 만점을 받고 auto-merge 까지 도달했다(실측 재현: 총점 89/B).
    # 🔴 `ran > 0` 이면 승격하지 않는다 — semgrep 이 커버하는 Rust·PHP·Swift 등에서 optional 도구
    # 하나가 없다고 영구 차단하면 과차단이다(경계는 "부분 미실행" 이 아니라 "전무").
    # 🔴 Promote only when ZERO analyzers ran AND the reason was an absent binary. Zero executions is
    # indistinguishable from "no issues" (= full 45/45 static marks) and reached auto-merge.
    # 🔴 `opted_out == 0` 조건 (Grok claim-review P1) — `is_enabled()` 는 "바이너리 부재" 와
    # "이 파일엔 해당 없음"(예: bandit 은 테스트 파일에서 False)을 **구별하지 않는다**. 운영자가
    # 나머지 도구를 disabled_tools 로 끈 상태면 `ran==0` 이 의도된 결과인데 이를 결함으로
    # 되돌려주게 된다(Grok 재현). 명시적 opt-out 이 하나라도 있으면 승격하지 않는다.
    # 🔴 is_enabled() conflates "binary absent" with "not applicable here"; skip promotion when the
    # operator explicitly disabled tools, otherwise their own opt-out is reported back as a defect.
    if ran == 0 and result.unavailable_tools and opted_out == 0:
        result.incomplete = True
        logger.warning(
            "no analyzer ran for %s (language=%s) — unavailable: %s",
            filename, language, ", ".join(sorted(result.unavailable_tools)),
        )

    return result


# ── 하위 호환 re-export (기존 코드가 static.py에서 직접 import 하는 경우 지원) ──

def _is_test_file(filename: str, language: str = "python") -> bool:
    """Deprecated: use is_test_file() from src.analyzer.pure.language. Kept for backward compatibility."""
    return is_test_file(filename, language)


def _run_pylint(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _PylintAnalyzer().run(ctx)


def _run_flake8(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _Flake8Analyzer().run(ctx)


def _run_bandit(path: str) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=False, tmp_path=path)
    return _BanditAnalyzer().run(ctx)
