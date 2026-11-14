"""ESLint static analysis tool — JavaScript/TypeScript 코드 품질 분석.

_ESLintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
eslint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# 🔴 `..` 2개 필수 — 이 파일은 `src/analyzer/io/tools/` 에 있고 설정은 `src/analyzer/configs/` 에 있다.
#    `..` 1개는 존재하지 않는 `src/analyzer/io/configs/` 를 가리켰고, eslint 가 ENOENT 로 죽어도
#    분석기가 조용히 [] 를 반환해 **JS/TS 이슈가 항상 0** 이었다 (#1226 결함 1).
# 🔴 Two `..` are required — this file lives in `src/analyzer/io/tools/` while the configs live in
#    `src/analyzer/configs/`. A single `..` pointed at the nonexistent `src/analyzer/io/configs/`,
#    and since the analyzer silently returned [] on ENOENT, JS/TS issues were always zero (#1226).
_CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "configs", "eslint.config.mjs"
))

_REACT_CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "configs", "eslint_react.config.mjs"
))

# JSX/TSX 확장자 — React 전용 eslint 설정 사용 대상
# File extensions that use the React-specific eslint config
_REACT_EXTENSIONS: frozenset[str] = frozenset({".jsx", ".tsx"})

# 실패 사유 로그 발췌 길이 — eslint stderr 전문을 그대로 싣지 않는다
# Excerpt length for failure reasons — avoid dumping the whole eslint stderr into logs
_ERR_EXCERPT = 200

# 🔴 **지시문 · 설정 메타 메시지** — 분석 대상 코드의 결함이 아니다 (backlog R22 · 회고 원장 R-9 · R-10).
#   룰이 아니라 **린터 자신**이 분석 대상의 지시문 주석(`eslint-disable` · 인라인 룰 설정 · `global` · 옛 `eslint-env`)과
#   우리 10-룰 최소 설정(`--no-config-lookup`)의 어긋남을 메시지로 낸다. 남기면 `ruleId` 가 문자열이거나 fatal 인 것은
#   ERROR(−3)로 세고(`score-lie` — auto-merge 까지 전파), `ruleId` 없는 비치명은 아래 «미린트» 로 올라가 그 파일이
#   통째로 미분석이 됐다. 룰 보고는 늘 `messageId` 를 싣고(우리 10개는 모두 코어 룰) 이 메시지들은 싣지 않으므로
#   **`messageId` 없음 + 아래 문구 하나** 일 때만 드롭한다. 문구는 eslint 10.14.0 소스의 템플릿이고(운영 이미지 실측),
#   바뀌면 드롭이 조용히 풀리므로 출력 오라클 시료(`tests/fixtures/analyzer_oracle/javascript/` 의 `legacy_directive` ·
#   `inline_directives`)가 지킨다. 🔴 모르는 메타는 드롭하지 않는다 — 미린트 fail-closed(#1226)는 그대로다.
# The linter itself (not a rule) reports problems with the analyzed file's directive comments and with our
# minimal config. Kept, they deducted score (string ruleId / fatal) or marked the whole file unanalyzed
# (null ruleId, non-fatal). Rule reports always carry a messageId and these never do, so a message is dropped
# only when it has no messageId AND matches one of eslint 10.14.0's templates below. Oracle samples guard the
# wording; unknown meta still fails closed (#1226).
_DIRECTIVE_META_MESSAGES: tuple[re.Pattern[str], ...] = (
    # 우리 설정에 없는 룰 이름 — `eslint-disable` · 인라인 설정 (R22, Grok `019fbaa0` 실측). 이름은 사용자가 적으므로
    # 작은따옴표(Grok `f2d396e4` 반례)도, 인라인 설정 JSON 키로는 빈 글자 · 줄바꿈도 든다(실측) — 이름 자리는 무엇이든 받는다.
    # The user writes the name: it may hold a quote, and an inline-config JSON key may be empty or contain a newline.
    re.compile(r"^Definition for rule '.*' was not found\.?$", re.DOTALL),
    # 같은 경로에서 eslint 가 지운 옛 룰 이름이면 대체 안내가 나온다 (R-10, Grok `6459a817` 반례 · 실측)
    # The same path names the replacement when the rule is one eslint removed long ago.
    re.compile(r"^Rule '[^']+' was removed and replaced by:"),
    # 옛 eslintrc 지시문 — eslint 10 은 fatal 로 보고하고 린트는 계속한다 (R-9)
    # Legacy eslintrc directive; eslint 10 reports it as fatal yet keeps linting.
    re.compile(r"^/\* eslint-env \*/ comments are no longer supported\.?$"),
    # 인라인 룰 설정 값이 그 룰 스키마에 안 맞는다 — 그 주석만 무시되고 룰은 우리 설정대로 돈다 (R-10)
    # An inline rule config that fails the rule's schema; only that comment is ignored.
    re.compile(r'^Inline configuration for rule "[^"]+" is invalid:'),
    # 인라인 룰 설정 주석을 JSON 으로 못 읽었다(fatal 이지만 린트는 계속한다)
    # An inline rule config comment that is not valid JSON (fatal, linting continues).
    re.compile(r"^Failed to parse JSON from '"),
    # `global` 주석의 값이 readonly · writable · off 가 아니다(fatal 이지만 린트는 계속한다)
    # A `global` comment value other than readonly / writable / off (fatal, linting continues).
    re.compile(r"^'.*' is not a valid configuration for a global \(use 'readonly', 'writable', or 'off'\)$"),
    # 여러 줄에 걸친 `eslint-disable-line` 블록 주석 / A multi-line `eslint-disable-line` block comment.
    re.compile(r"^eslint-disable-line comment should not span multiple lines\.$"),
    # 같은 룰을 앞선 인라인 설정 주석이 이미 정했다 / An earlier inline config comment already set the rule.
    re.compile(r'^Rule "[^"]+" is already configured by another configuration comment in the preceding code\. '
               r"This configuration is ignored\.$"),
)

# 쓰이지 않는 `eslint-disable` · `eslint-enable` 주석을 보고하지 않는다 (R-10). 기본값 `warn` 의 메시지는 `ruleId` 없는
# 비치명이라 «미린트» 로 읽혀, 우리 10개 밖 코어 룰을 끄는 흔한 주석 하나로 그 파일이 미분석이 됐다(실측). 지울 수 있는
# 주석일 뿐 코드 결함이 아니다 — 문구 드롭이 아니라 보고 자체를 끈다. 오라클 시료 `inline_directives` 가 지킨다.
# Do not report unused disable/enable directives: the default `warn` message has a null ruleId, so a common
# directive for a core rule outside our ten marked the whole file unanalyzed. Guarded by the oracle sample.
_UNUSED_DIRECTIVES_OFF = "--report-unused-disable-directives-severity=off"


def _to_issues(data: list, ctx: AnalyzeContext) -> list[AnalysisIssue]:
    """eslint JSON 결과를 AnalysisIssue 목록으로 변환한다.

    🔴 ruleId 가 없고 fatal 도 아닌 메시지 = 파일이 **린트되지 않았다**는 eslint 메타 메시지
    ("File ignored because ..."). 이슈로 집계하면 없는 결함으로 점수를 깎고, 무시하면 미분석을
    clean 으로 오인한다 — 둘 다 틀리므로 fail-closed 로 올린다. fatal 파싱 오류는 ruleId 가
    없어도 분석 대상 코드의 **실제 결함**이므로 이슈로 보존한다 (대비 축).
    🔴 A message with no ruleId that is not fatal is an eslint meta message meaning the file was
    never linted ("File ignored because ..."). Counting it deducts points for a nonexistent defect;
    ignoring it reads "not analyzed" as clean — both are wrong, so fail closed. A fatal parse error
    has no ruleId either but IS a real defect in the analyzed code, so it is kept as an issue.

    🔴 세 번째 부류 — **지시문 · 설정 메타 메시지**(`_DIRECTIVE_META_MESSAGES`)는 린터가 분석 대상의 지시문
    주석과 우리 최소 설정의 어긋남을 알리는 것이라 이슈로도 실패로도 세지 않고 드롭한다(R22 · R-9 · R-10).
    🔴 Third kind: the linter's meta messages about directive comments and our config are dropped —
    neither raised nor counted.
    """
    issues = []
    for file_result in data:
        for msg in file_result.get("messages", []):
            # 🔴 지시문 · 설정 메타 드롭 — 미린트(ruleId=None) 판정과 «fatal = 실제 결함» 보다 **먼저** 본다.
            #   그중 몇은 ruleId 가 없거나 fatal 이라 순서가 바뀌면 미분석이나 ERROR 가 된다.
            # Drop directive/config meta before the not-linted check and the "fatal = real defect" rule —
            # some of them have a null ruleId or are fatal.
            text = msg.get("message", "") or ""
            if msg.get("messageId") is None and any(p.match(text) for p in _DIRECTIVE_META_MESSAGES):
                logger.debug("eslint directive-meta message dropped (not a code defect): %s", text[:_ERR_EXCERPT])
                continue
            if msg.get("ruleId") is None and not msg.get("fatal"):
                raise RuntimeError(
                    f"eslint did not lint {ctx.tmp_path}: {msg.get('message', '')[:_ERR_EXCERPT]}"
                )
            severity = Severity.ERROR if msg.get("severity", 1) == 2 else Severity.WARNING
            issues.append(AnalysisIssue(
                tool="eslint",
                severity=severity,
                message=msg.get("message", ""),
                line=msg.get("line", 0),
                category=Category.CODE_QUALITY,
                language=ctx.language,
            ))
    return issues


class _ESLintAnalyzer:
    name = "eslint"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"javascript", "typescript"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """JS/TS 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """eslint 바이너리 설치 여부 확인."""
        return shutil.which("eslint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """eslint JSON 출력을 파싱해 AnalysisIssue 목록 반환.

        🔴 실패를 조용히 삼키지 않는다 (#1226) — `RuntimeError` 를 올리면 `static.py` 의
        broad-except 가 이를 `StaticAnalysisResult.incomplete` 로 승격해 미분석 코드의
        auto-merge/auto-approve 를 차단한다(#805/#806 fail-closed 대칭). 이전 판은 설정 부재나
        무효 플래그로 eslint 가 죽어도 `[]` 를 반환해 **"이슈 0건" 과 구별 불가**했고, 그만큼
        점수가 인플레돼 게이트까지 전파됐다.
        🔴 Failures are never swallowed (#1226) — raising RuntimeError lets static.py's broad
        except promote it to StaticAnalysisResult.incomplete, blocking auto-merge/approve of
        unanalyzed code (fail-closed, symmetric with #805/#806). The previous version returned []
        when eslint died on a missing config or an invalid flag, making a dead analyzer
        indistinguishable from "zero issues" and inflating scores into the gate.

        예외: 타임아웃(`ctx.timed_out`)과 바이너리 부재(`FileNotFoundError`)는 **의도적 미수행**
        경로라 기존 계약대로 `[]` 를 반환한다 (`static.py` 의 opt-out 경계). 그 밖의 `OSError`
        (깨진 shebang · 권한)는 which() 를 통과한 뒤의 실행 실패라 미분석이고 올라간다.
        Exceptions: timeout and a missing binary (FileNotFoundError) are *intentional*
        non-execution paths and keep returning []; any other OSError is a spawn failure after
        the which() gate — unanalyzed, so it propagates.
        """
        # JSX/TSX 파일은 React 설정 사용, 그 외는 기본 설정 사용
        # Use React config for JSX/TSX files, base config otherwise
        _cfg = _REACT_CONFIG_PATH if pathlib.Path(ctx.filename).suffix in _REACT_EXTENSIONS else _CONFIG_PATH
        try:
            r = subprocess.run(  # nosec B603 B607
                ["eslint", "--format=json", "--no-config-lookup", _UNUSED_DIRECTIVES_OFF,
                 "-c", _cfg, ctx.tmp_path],
                # 🔴 cwd 필수 — eslint 는 base path(기본값 = cwd) 밖의 파일을 린트하지 않고
                # "File ignored because outside of base path" 로 넘긴다(9·10 공통). 분석 대상은
                # tempfile.TemporaryDirectory() 안에 있고 앱 cwd 는 리포 루트라, 지정하지 않으면
                # 모든 JS/TS 파일이 조용히 스킵된다 (#1226 결함 5).
                # 🔴 cwd is mandatory — eslint skips files outside its base path (defaults to cwd)
                # with "File ignored because outside of base path" (both 9 and 10). The target lives
                # in a TemporaryDirectory while the app cwd is the repo root, so omitting it makes
                # every JS/TS file silently skipped (#1226 defect 5).
                cwd=os.path.dirname(ctx.tmp_path),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("eslint timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("eslint unavailable for %s: %s", ctx.tmp_path, exc)
            return []

        if not r.stdout.strip().startswith("["):
            # stdout 이 JSON 이 아니다 = eslint 가 분석을 못 했다. stderr 를 실패 사유로 실어 보낸다.
            # Non-JSON stdout means eslint never analyzed the file; carry stderr as the reason.
            raise RuntimeError(
                f"eslint did not produce JSON for {ctx.tmp_path} "
                f"(exit={r.returncode}): {(r.stderr or r.stdout).strip()[:_ERR_EXCERPT]}"
            )
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"eslint produced unparseable JSON for {ctx.tmp_path}: {exc}") from exc

        return _to_issues(data, ctx)


def _register_eslint_analyzers() -> None:
    register(_ESLintAnalyzer())


_register_eslint_analyzers()
