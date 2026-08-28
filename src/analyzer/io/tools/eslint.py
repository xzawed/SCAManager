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

# 🔴 **우리 설정에 대한 메타 메시지** — 사용자 코드의 결함이 아니다 (backlog R22, 2026-08-01).
#   우리는 `--no-config-lookup` + 10-룰 최소 설정으로 돌린다. 그래서 대상 리포가 **자기 설정에**
#   있는 룰로 `eslint-disable` 을 달면, eslint 는 그 룰을 모르므로 다음을 보고한다:
#       ruleId="<그 룰 이름>" · severity=2 · fatal 없음
#       message="Definition for rule '<룰>' was not found."
#   `ruleId` 가 **문자열**이라 미린트 판정(ruleId=None) 분기에 걸리지 않고, severity 2 라
#   그대로 ERROR 이슈로 집계돼 **없는 결함으로 점수를 깎았다**(`score-lie` — auto-merge 까지 전파).
#   🔴 Grok claim-review `019fbaa0` 실측(eslint 9.39.5·10.8.0 동일): eslint 소스의
#   `createDisableDirectives` 가 미등록 룰명을 `report.addError(...)` 로 보내기 때문이며,
#   그 경로에서는 unused-disable 도 발화하지 않는다.
#   🔴 **드롭 대상은 이 메타 메시지뿐** — 미린트(ruleId=None) fail-closed(#1226)는 그대로 둔다.
# Meta messages about OUR minimal config, not defects in the reviewed code. Because we run with
# --no-config-lookup, a disable comment naming a rule from the repo's own config makes eslint emit
# "Definition for rule 'X' was not found." with a STRING ruleId and severity 2 — previously counted
# as a real ERROR and deducted score. Measured on eslint 9.39.5 / 10.8.0.
_CONFIG_META_MESSAGE = re.compile(r"^Definition for rule '[^']+' was not found\.?$")


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

    🔴 세 번째 부류 — **우리 설정에 대한 메타 메시지**(`Definition for rule 'X' was not found.`)는
    `ruleId` 가 문자열이라 위 두 축 어디에도 걸리지 않고 severity 2 로 ERROR 집계됐다.
    대상 리포가 자기 설정의 룰로 `eslint-disable` 을 달면 우리 10-룰 최소 설정에는 없으므로
    **정상 코드가 감점**됐다(backlog R22 · Grok `019fbaa0` 실측). 이슈로도 실패로도 세지 않고 드롭한다.
    🔴 Third kind: meta messages about OUR config carry a STRING ruleId at severity 2, so they
    escaped both axes and deducted score for correct code. Dropped — neither raised nor counted.
    """
    issues = []
    for file_result in data:
        for msg in file_result.get("messages", []):
            # 🔴 설정 메타 메시지 드롭 — 미린트(ruleId=None) 판정보다 **먼저** 본다.
            #   순서가 바뀌면 의미는 같지만(ruleId 가 문자열이라) 의도가 흐려진다.
            # Drop config-meta messages before the not-linted check; they are not code defects.
            if _CONFIG_META_MESSAGE.match(msg.get("message", "") or ""):
                logger.debug(
                    "eslint config-meta message dropped (not a code defect): %s",
                    msg.get("message", "")[:_ERR_EXCERPT],
                )
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

        예외: 타임아웃(`ctx.timed_out`)과 바이너리 부재(`OSError`)는 **의도적 미수행** 경로라
        기존 계약대로 `[]` 를 반환한다 (`static.py` 의 opt-out 경계).
        Exceptions: timeout and a missing binary are *intentional* non-execution paths and keep
        returning [] per the existing contract (static.py's opt-out boundary).
        """
        # JSX/TSX 파일은 React 설정 사용, 그 외는 기본 설정 사용
        # Use React config for JSX/TSX files, base config otherwise
        _cfg = _REACT_CONFIG_PATH if pathlib.Path(ctx.filename).suffix in _REACT_EXTENSIONS else _CONFIG_PATH
        try:
            r = subprocess.run(  # nosec B603 B607
                ["eslint", "--format=json", "--no-config-lookup",
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
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
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
