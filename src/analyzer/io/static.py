"""Static code analysis — runs registered analyzers on source files via Registry."""
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

import src.analyzer.io.tools.buf_lint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.clippy  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.cppcheck  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.dart_analyze  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
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


# 분석기 이름 ≠ 실행 파일명인 경우의 예외 표. 현재는 비어 있다 —
# `PROVISIONED_ANALYZERS` 16종은 전부 이름과 바이너리명이 같다(실측).
# 새 분석기가 다른 바이너리를 쓰면 **여기 등재해야** 아래 판정이 참이 된다.
# Override table for analyzers whose binary name differs from the analyzer name.
_BINARY_OVERRIDES: dict[str, str] = {}


def _binary_is_absent(tool: str) -> bool:
    """`is_enabled()` 가 False 인 **두 원인**을 가른다 — 바이너리가 없는가, 있는데 못 도는가.

    ## 🔴 왜 필요한가

    `_run_analyzers` 는 `is_enabled()` 가 False 이면 무조건 `unavailable_tools` 에 넣는데,
    그 메서드는 두 가지를 **구별하지 않는다**(실측: 어댑터 24개 중 23개는 순수 `which`,
    나머지 하나가 아래 복합 판정이다):

    - `python.py::        return shutil.which("bandit") is not None` = **바이너리 부재** — 조달 회귀다
    - `slither.py::    def is_enabled(self, ctx: AnalyzeContext) -> bool:` = which 통과 뒤 **설치된 solc 아티팩트와 pragma** 까지 본다
      → 바이너리는 있고 **이 파일을 못 도는** 것이다. 조달은 멀쩡하다.

    둘을 합치면 후자가 조달 회귀로 승격돼 auto-merge 가 막힌다 — 고칠 것이 없는데.
    `PROVISIONED_ANALYZERS` 안 도구일수록 그 오판의 폭발 반경이 크다.

    🔴 「이 파일엔 정책상 해당 없음」은 여기가 아니라 `supports` 다(실측: `is_enabled` 가
    정책 술어를 읽는 어댑터는 **0개**). `python.py::        return ctx.language == "python" and not ctx.is_test` 가 그 자리를 보여준다 —
    `is_enabled` 에 두면 그 파일의 도구가 `unavailable_tools` 로 가서 같은 오판이 난다.

    `shutil.which` 는 「바이너리가 있는가」의 직접 관측이라 `is_enabled` 의 의도 모호성을
    타지 않는다.
    `is_enabled()` conflates "binary absent" with "not applicable here"; `shutil.which` observes
    the binary directly, which is the only one of the two that means a deployment regression.
    """
    return shutil.which(_BINARY_OVERRIDES.get(tool, tool)) is None


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
    # 🔴 범용은 돌았는데 **전담 관측면이 하나도 돌지 않은** 경우 그 언어명 —
    # `uncovered_language`(실행 0개)와 `incomplete`(미분석) 사이의 빈칸.
    #
    # 실측(2026-08-29 · `detect_language` 가 낼 수 있는 언어 × 프로덕션 `supports()` ×
    # `PROVISIONED_ANALYZERS`): 배포 이미지에서 **9개 언어**가 여기 걸린다 —
    #   clojure · csharp · elixir · html · java · php · rust · scala · swift
    # 그중 clojure·csharp·elixir·java·scala 는 전담 어댑터 자체가 없고(csharp 은 #1565 로
    # 지웠다), 나머지는 있으나 미조달이다.
    # 거기서는 범용 semgrep 하나만 도는데 규칙 밀도가 언어마다 크게 달라
    # (semgrep 자체 보고: elixir 0 · cpp 0 · swift 2 · rust 4) 취약 코드에도 이슈 0건이 나온다.
    # 실측: `analyze_file("vuln.ex", <System.cmd 주입>)` → issues=0 · incomplete=False.
    # 아래 `ran > 0` 주석이 「semgrep 이 커버한다」고 적은 것은 **선언상 참이고 실효로 거짓**이다.
    #
    # 🔴 차단하지 않는다(가시화만) — 차단하면 조달 실패가 다시 벽이 된다(#1568).
    # Supported and observed only by the generic fallback. 9 languages on the deployed image.
    no_dedicated_observer: str | None = None


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
    # 🔴 「전담 관측면이 하나라도 돌았는가」 — 범용(`is_generic`) 분석기는 세지 않는다.
    #    판정은 선언에서 파생한다(목록을 손으로 적지 않는다). 선언이 정확히 하나임은
    #    `tests/unit/analyzer/test_no_dedicated_observer.py` 가 강제한다.
    # Did any *dedicated* analyzer run? The generic fallback does not count.
    dedicated_ran = 0
    for analyzer in REGISTRY:
        if not analyzer.supports(ctx):
            continue
        supported += 1
        is_generic = getattr(analyzer, "is_generic", False)
        if not analyzer.is_enabled(ctx):
            # 바이너리 부재 = 배포 이미지에 조달되지 않음. 기록만 하고 계속 — 승격 판정은
            # 호출부가 한다. 🔴 조달 계약(`PROVISIONED_ANALYZERS`) 안 도구면 `ran` 과 무관하게
            # 승격하고, 계약 밖 도구는 «실행 0개» 일 때만 `uncovered_language` 로 가시화한다.
            # Binary absent. Record only; the caller decides — provisioned tools promote
            # regardless of `ran`, unprovisioned ones only surface when ZERO analyzers ran.
            result.unavailable_tools.append(analyzer.name)
            continue
        if analyzer.name in disabled:
            # 운영자가 명시적으로 끈 것 — 의도된 opt-out. "내가 껐다" 를 결함으로 되돌려주지 않는다.
            opted_out += 1
            continue
        try:
            result.issues.extend(analyzer.run(ctx))
            ran += 1
            if not is_generic:
                dedicated_ran += 1
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            # 🔴 감사 ④ (옵션 B): 도구가 내부에서 못 잡은 예상외 crash 는 이슈를 무음 폐기하므로
            # incomplete 로 승격 — 타임아웃(ctx.timed_out)과 동일하게 fail-closed 처리해 미분석
            # 코드의 auto-merge/auto-approve 를 차단한다(이전엔 로깅만 하고 삼켜 fail-open).
            # 의도적 미설치는 이 분기에 도달하지 않는다 — 도구가 (1) `shutil.which`
            # 게이트(supports/is_enabled)에서 걸러지거나 (2) 스폰이 `FileNotFoundError` 를
            # 내면 어댑터가 `[]` 를 돌려주기 때문이다(조달 축 = `unavailable_tools`).
            # 🔴 그 밖의 `OSError`(깨진 shebang · 권한 · which 통과 후 TOCTOU)는 **미분석**이므로
            # 여기로 올라와야 한다. 그것은 계약이지 아직 트리 전체의 사실이 아니다 —
            # `FileNotFoundError` 로 좁힌 어댑터만 이 구별을 갖고, 남은 7개(#1557 W2)는
            # 여전히 `except OSError` 로 삼켜 이 분기에 도달하지 않는다. 재고는
            # `tests/unit/analyzer/test_adapter_fail_open_inventory.py::KNOWN_FAIL_OPEN`.
            # Deliberate non-install never reaches here: the which() gate or a FileNotFoundError
            # returns []. Any other OSError *should* promote — that is the contract, not yet a
            # tree-wide fact: the W2 adapters still swallow OSError and never arrive here.
            # Audit ④ (option B): an unexpected crash a tool failed to catch silently drops its issues,
            # so promote to incomplete — fail-closed like the timeout path (ctx.timed_out).
            logger.warning("analyzer %s failed for %s: %s", analyzer.name, ctx.filename, exc)
            result.incomplete = True

    # 🔴 **범용은 돌았는데** 전담 관측면이 하나도 돌지 않았다 — 그 결과를 「완전」으로
    #    기록하지 않는다. 전담 어댑터가 아예 없는 언어(scala·elixir·java·clojure)도,
    #    있지만 조달 실패로 못 돈 경우(rust·swift·php·html)도 같은 축이다.
    #    (csharp 은 전자다 — dotnet_format 은 단일 `.cs` 를 분석할 수 없어 지웠다, #1565)
    #
    # 🔴 조건이 `supported > 0` 이 아니라 **`ran > 0`** 인 이유 — 첫 판은 전자였고 틀렸다.
    #    범용조차 돌지 않은 언어(css·dart·powershell·protobuf: semgrep 이 지원 안 함)까지
    #    잡아서 「범용 검사기만 봤다」는 경고가 **거짓**이 됐다. 그 자리는 이미
    #    `uncovered_language` 가 담당한다(실행 0개). 운영자가 전부 끈 경우(`ran == 0`)도
    #    같은 이유로 빠진다 — 「내가 껐다」를 결함으로 되돌려주지 않는 위 opt-out 규칙과 일치한다.
    #
    #    🔴 차단하지 않는다 — 이것은 가시화 축이고, 차단은 `incomplete` 가 한다.
    # Only when the generic fallback actually ran: otherwise the warning would be false and
    # `uncovered_language` already owns that case.
    if ran > 0 and dedicated_ran == 0:
        result.no_dedicated_observer = ctx.language
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

    # 🔴 **조달 회귀는 `ran` 과 무관하다** (2026-08-16 재검증 P0 — 이 리포의 운영 사고 축).
    #
    # 아래 `ran == 0` 게이트는 *"optional 도구 하나 없다고 과차단하지 말자"* 는 결정이었고
    # 그 자체는 옳다. 그런데 그 뒤에 들어온 `PROVISIONED_ANALYZERS` 갈라치기가 **그 게이트
    # 안쪽**에 놓이면서, 조달 대상 도구가 사라져도 semgrep 하나만 돌면 승격이 **도달 불가**가
    # 됐다. `PROVISIONED_ANALYZERS` docstring 은 스스로 "a listed tool going missing is a
    # deployment regression (block)" 이라 적는데 코드가 그 계약을 이행하지 않았다.
    #
    # 실측 연쇄: `railway.toml` 이 조달 실패를 `|| echo WARNING` 으로 삼킴 → rubocop·
    # golangci-lint·slither 부재 → 그러나 semgrep 은 `requirements.txt` 상시 설치이고
    # `SUPPORTED_LANGUAGES` 에 ruby·go·solidity 가 있어 `ran >= 1` → incomplete 미설정 →
    # `score_is_unreliable()` False → `auto_merge.py` 의 incomplete 차단 미발동.
    # 결과: 그 세 언어 PR 이 **전용 분석기 0회 실행**으로 정적 만점을 받고 auto-merge 에 도달.
    #
    # 🔴 `opted_out == 0` 은 유지한다 — 운영자가 명시적으로 끈 것을 결함으로 되돌려주면 안 된다.
    # A provisioned tool going missing is a deployment regression regardless of what else ran;
    # the `ran == 0` gate only ever protected *optional* tools.
    provisioned_missing = [
        t for t in result.unavailable_tools
        if t in PROVISIONED_ANALYZERS and _binary_is_absent(t)
    ]
    if provisioned_missing and opted_out == 0:
        result.incomplete = True
        logger.warning(
            "provisioned analyzer missing for %s (language=%s, ran=%d) — %s",
            filename, language, ran, ", ".join(sorted(provisioned_missing)),
        )

    if ran == 0 and result.unavailable_tools and opted_out == 0:
        # 🔴 **조달 계약으로 갈라친다** (backlog R21, 사용자 결정 2026-08-01 — 옵션 C).
        # `unavailable_tools`(바이너리 부재)를 무조건 incomplete 로 올리면, 배포 이미지가
        # **애초에 설치하지 않는** 도구의 언어는 auto-merge 가 **영구 불가**가 된다. 실측:
        # 등록 24 분석기 중 8종(buf_lint·clippy·dart_analyze·htmlhint·phpstan·psscriptanalyzer·
        # stylelint·swiftlint)이 railway.toml·nixpacks.toml·requirements.txt·package.json
        # 어디에도 조달 흔적이 없다 → rust·dart·php·powershell·css·swift·protobuf·html
        # 리포는 손댈 수 없는 이유로 영구 차단이었다. (C# 은 전담 어댑터가 아예 없다 — #1565) `#1245` 본문이 스스로
        # "차단 없이 가시화만" 이라 적은 것과 정면 모순이기도 하다.
        #
        # 갈라치는 기준은 **의도**다:
        #   · 조달 대상인데 없다 → 실제 배포 회귀 → incomplete (**위 블록이 처리한다**)
        #   · 애초에 조달 대상이 아니다 → 제품 미제공 → `uncovered_language` 와 동급, 가시화만
        # 🔴 조달 회귀 판정을 여기서 **다시 하지 않는다** — 같은 로직을 두 곳에 두면 한쪽만
        #    고쳐지고 다른 쪽이 조용히 낡는다(정책 16). 위 블록이 `ran` 과 무관하게 판정하므로
        #    여기 남는 것은 «조달 대상이 아닌 도구만 부재» 경우뿐이다.
        # Split by procurement intent; the regression axis is decided above (independent of `ran`),
        # so only the never-provisioned case remains here.
        if not provisioned_missing:
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
