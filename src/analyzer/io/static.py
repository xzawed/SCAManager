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

# 🔴 **조달 계약** — 배포 이미지가 설치를 약속한 분석기 (backlog R21, 사용자 결정 2026-08-01).
#
# 이 목록의 도구가 런타임에 없으면 = **실제 배포 회귀** → `incomplete` 로 auto-merge 차단.
# 목록 밖 도구가 없으면 = **제품이 그 언어를 제공하지 않음** → 차단하지 않고 가시화만
# (`uncovered_language` 와 동급). 이 구분이 없으면 조달 계획이 없는 언어의 리포는
# auto-merge 가 **영구 불가**가 된다 — 손댈 수 없는 이유로 차단되는 것이라 게이트가 아니라 벽이다.
#
# 🔴 이 목록은 산문이 아니라 **계약**이다. `railway.toml`·`nixpacks.toml`·`requirements.txt`·
# `package.json` 의 실제 조달과 대조하는 회귀 가드가 있다
# (`tests/unit/analyzer/test_procurement_contract.py`) — 조달을 추가/제거하면 여기도 바꿔야 한다.
# 목록이 실제 조달과 갈라지면 (a) 조달했는데 미등재 = 회귀를 못 잡음 (b) 미조달인데 등재 =
# 영구 차단 재발. 둘 다 이 파일이 막으려는 것이다.
#
# PROVISIONED_ANALYZERS is a contract, not prose: a listed tool going missing is a deployment
# regression (block); an unlisted tool's absence means the product never covered that language
# (surface only). A guard cross-checks this against the real provisioning files.
PROVISIONED_ANALYZERS: frozenset[str] = frozenset({
    # nixpacks.toml aptPkgs
    "shellcheck", "cppcheck", "rubocop",
    # railway.toml buildCommand (직접 설치 / installed explicitly)
    "golangci-lint", "hadolint", "ktlint", "tflint",
    # Python 의존성 (requirements.txt)
    "pylint", "flake8", "bandit", "semgrep", "sqlfluff", "yamllint", "slither",
    # npm (package.json)
    "eslint", "tsc",
})


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
    # 이 파일의 언어를 **지원하는 분석기 자체가 등록돼 있지 않은** 경우 그 언어명.
    # `unavailable_tools`(바이너리 부재 → incomplete 로 차단)와 구별된다 — 이쪽은 제품이 애초에
    # 그 언어의 정적분석을 제공하지 않는다는 뜻이라 **차단하지 않고 가시화만** 한다(사용자 결정).
    # Language name when NO registered analyzer supports it at all. Distinct from unavailable_tools
    # (absent binary → blocks): this means the product never covered the language — surface, don't block.
    uncovered_language: str | None = None


def _run_analyzers(ctx: AnalyzeContext, result: StaticAnalysisResult) -> tuple[int, int, int]:
    """이 파일에 등록 분석기를 돌리고 `(실행 수, opt-out 수, 지원 분석기 수)` 를 반환한다.

    Run the registered analyzers for this file; return (ran, opted_out, supported).

    커버리지 판정 3 축을 분리해 센다 — 셋이 섞이면 "안 돌았다" 의 사유를 구별할 수 없다:
      - `supported` : 이 언어를 지원한다고 선언한 분석기 수 (0 = 제품이 이 언어를 커버 안 함)
      - `ran`       : 실제로 실행된 수
      - `opted_out` : 운영자가 `disabled_tools` 로 끈 수 (의도된 미분석)
    """
    disabled = getattr(ctx.repo_config, 'disabled_tools', None) or []
    ran = opted_out = supported = 0
    for analyzer in REGISTRY:
        if not analyzer.supports(ctx):
            continue
        supported += 1
        if not analyzer.is_enabled(ctx):
            # 바이너리 부재 = 배포 이미지에 조달되지 않음. 기록만 하고 계속 — 승격 판정은
            # 호출부에서 "실행 0개" 일 때만(semgrep 등이 커버하는 언어의 과차단 방지).
            # Binary absent. Record only; the caller promotes solely when ZERO analyzers ran.
            result.unavailable_tools.append(analyzer.name)
            continue
        if analyzer.name in disabled:
            # 운영자가 명시적으로 끈 것 — 의도된 opt-out. "내가 껐다" 를 결함으로 되돌려주지 않는다.
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
            # so promote to incomplete — fail-closed like the timeout path (ctx.timed_out).
            logger.warning("analyzer %s failed for %s: %s", analyzer.name, ctx.filename, exc)
            result.incomplete = True
    return ran, opted_out, supported


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
        ran, opted_out, supported = _run_analyzers(ctx, result)

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
    # 🔴 미커버 언어 기록 — **차단하지 않는다** (사용자 결정: 가시화만).
    # 인식 언어 47개 중 21개(lua·perl·haskell·r·julia·elm·erlang·zig·ocaml·graphql·toml·xml 등)는
    # 지원 분석기가 **애초에 등록돼 있지 않다**. 그 PR 은 정적 45/45 만점을 받는데, 이는 "분석했더니
    # 깨끗함" 이 아니라 "제품이 이 언어를 분석하지 않음" 이다. 바이너리 부재(위 incomplete)와 달리
    # 고칠 수 있는 조달 문제가 아니므로 차단하면 해당 언어 리포의 auto-merge 가 영구 불가가 된다
    # → 점수·게이트는 그대로 두고 사람이 오독하지 않도록 **표면화만** 한다.
    # 🔴 Record uncovered languages WITHOUT blocking (user decision). 21 of 47 recognised languages
    # have no registered analyzer at all; blocking would permanently disable auto-merge for those
    # repos, so surface it instead of gating on it.
    # `unknown` = 확장자 맵에 없는 파일(.txt·.md 등) — 코드가 아니므로 제외한다.
    if supported == 0 and language and language != "unknown":
        result.uncovered_language = language

    if ran == 0 and result.unavailable_tools and opted_out == 0:
        # 🔴 **조달 계약으로 갈라친다** (backlog R21, 사용자 결정 2026-08-01 — 옵션 C).
        # `unavailable_tools`(바이너리 부재)를 무조건 incomplete 로 올리면, 배포 이미지가
        # **애초에 설치하지 않는** 도구의 언어는 auto-merge 가 **영구 불가**가 된다. 실측:
        # 등록 25 분석기 중 10종(clippy·dart_analyze·dotnet_format·phpstan·psscriptanalyzer·
        # stylelint·swiftlint·buf_lint·htmlhint …)이 railway.toml·nixpacks.toml·requirements.txt·
        # package.json 어디에도 조달 흔적이 없다 → rust·dart·C#·php·powershell·css/scss·swift·
        # protobuf·html 리포는 손댈 수 없는 이유로 영구 차단이었다. `#1245` 본문이 스스로
        # "차단 없이 가시화만" 이라 적은 것과 정면 모순이기도 하다.
        #
        # 갈라치는 기준은 **의도**다:
        #   · 조달 대상인데 없다 → 실제 배포 회귀 → incomplete (fail-closed 보존)
        #   · 애초에 조달 대상이 아니다 → 제품 미제공 → `uncovered_language` 와 동급, 가시화만
        # Split by procurement intent: a PROVISIONED tool going missing is a real deployment
        # regression (keep blocking); a never-provisioned tool is product scope (surface only).
        blocking = [t for t in result.unavailable_tools if t in PROVISIONED_ANALYZERS]
        if blocking:
            result.incomplete = True
            logger.warning(
                "no analyzer ran for %s (language=%s) — provisioned but missing: %s",
                filename, language, ", ".join(sorted(blocking)),
            )
        else:
            # 조달 대상이 아닌 도구만 부재 — 차단하지 않고 미커버로 표면화한다.
            # Only never-provisioned tools are absent: surface as uncovered, do not block.
            result.uncovered_language = result.uncovered_language or language
            logger.info(
                "no analyzer ran for %s (language=%s) — not provisioned: %s",
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
