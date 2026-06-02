"""발신 모듈 한국어 하드코딩 자동 회귀 가드 (사이클 155 — 회고 메타학습).

Automated regression guard: no hardcoded Korean in user-facing send-module
string literals. AST-scans send modules and flags Korean string constants that
are NOT (a) docstrings or (b) logger.* call arguments.

배경 (Why this exists):
사이클 149/152/153 모두 "발신 경로 i18n 완결/0건 실측"을 선언한 직후 회고가
사용자 노출 한국어 P0 를 발견하는 패턴이 3연속 재발했다. 근본 원인은 검증 도구
(grep 패턴)를 **고정 함수명 enumeration** 으로 산문 규칙에 봉인한 것 — enumeration
에서 빠진 발신 함수가 새 회피 경로가 됐다 (사이클 154 회고 에이전트 5 식별).

이 테스트는 그 수동 검증을 **소스 스캔 자동화** 로 대체한다. "발신 경로 한국어 0건"
선언이 Claude 의 self-declaration 이 아니라 **CI green** 으로 객관화된다.
The "zero hardcoded Korean in send paths" claim becomes a CI-enforced invariant,
not a self-declaration.

판정 경계 (i18n.md "내부 로그 vs 사용자 발신 경계"):
- logger.* 인자 = 운영자용 내부 로그 → i18n 대상 외 (제외)
- docstring/주석 = 코드 문서 → i18n 대상 외 (주석은 AST 에 없음, docstring 만 제외)
- 그 외 모든 한국어 문자열 리터럴 = 사용자 발신 후보 → 위반 (get_text 키는 ASCII 이므로
  한국어가 코드에 남으면 i18n 미경유 = 위반)
"""
from __future__ import annotations

import ast
import glob
import os
import re

# 스캔 대상 — 사용자 발신 메시지를 조립하는 모듈 디렉토리/파일
# Scan targets — modules that compose user-facing outbound messages
_TARGET_DIRS = ["src/notifier", "src/gate", "src/webhook/providers"]
# upstream 데이터 출처 — notifier 로 흐르는 필드(AiReviewResult.summary 등)를 만드는 모듈.
# ai_review.py 의 AI 프롬프트는 review_prompt.py/review_guides 에 분리돼 있어 본 파일은
# summary 외 사용자 노출 한국어 없음 (사이클 155 회고 — Codex 검증이 발신 경로 누락 식별).
# Upstream data-origin modules: where notifier-bound fields originate. ai_review.py's
# AI prompts live in separate files, so it carries no user-facing Korean besides summary.
_TARGET_FILES = [
    "src/services/cron_service.py",
    "src/services/merge_retry_service.py",
    "src/analyzer/io/ai_review.py",
]

_KOREAN = re.compile(r"[가-힣]")
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}
_LOG_TARGETS = {"logger", "log", "logging", "_logger"}

# 정당한 예외 (file, lineno, 사유) — 현재 0건. 신규 추가 시 회고에서 사유 명시 의무.
# Legitimate exceptions (file, lineno, reason) — currently empty. New entries
# must be justified in a retrospective (e.g. a deliberately English-fixed search prefix).
_ALLOWLIST: set[tuple[str, int]] = set()


def _docstring_position(node: ast.AST) -> "tuple[int, int] | None":
    """node(module/func/class)가 docstring 을 가지면 그 Constant 위치, 아니면 None.
    Return the docstring Constant position if node has one, else None."""
    body = getattr(node, "body", None)
    if not body:
        return None
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return (first.value.lineno, first.value.col_offset)
    return None


def _is_logger_call(node: ast.AST) -> bool:
    """node 가 logger.<method>(...) 호출인지 판정한다.
    Whether node is a logger.<method>(...) call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _LOG_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in _LOG_TARGETS
    )


def _excluded_const_positions(tree: ast.AST) -> set[tuple[int, int]]:
    """docstring + logger.* 호출 서브트리의 문자열 상수 위치를 수집한다.
    Collect positions of string constants that are docstrings or logger.* call args."""
    excluded: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            pos = _docstring_position(node)
            if pos is not None:
                excluded.add(pos)
        elif _is_logger_call(node):
            # logger 호출 서브트리의 모든 문자열 상수 (f-string Constant 포함) 제외
            # Exclude all string constants in the logger-call subtree (incl. f-string parts)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    excluded.add((sub.lineno, sub.col_offset))
    return excluded


def _scan_korean_literals(source: str, filename: str = "<test>") -> list[tuple[str, int, str]]:
    """소스에서 한국어 문자열 리터럴 위반을 반환한다 (docstring/logger 제외).
    Return Korean string-literal violations in source (docstrings/logger excluded)."""
    tree = ast.parse(source)
    excluded = _excluded_const_positions(tree)
    violations: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _KOREAN.search(node.value)
            and (node.lineno, node.col_offset) not in excluded
            and (filename, node.lineno) not in _ALLOWLIST
        ):
            violations.append((filename, node.lineno, node.value[:50]))
    return violations


def _target_files() -> list[str]:
    files: list[str] = []
    for d in _TARGET_DIRS:
        files += glob.glob(os.path.join(d, "**", "*.py"), recursive=True)
    files += [f for f in _TARGET_FILES if os.path.exists(f)]
    return sorted(set(files))


def test_send_modules_have_no_hardcoded_korean():
    """발신 모듈 전체에 사용자 노출 한국어 하드코딩이 0건이어야 한다 (149~154 패턴 회귀 가드)."""
    files = _target_files()
    assert files, "스캔 대상 파일이 비어있음 — 경로 설정 오류 / no target files found"
    all_violations: list[tuple[str, int, str]] = []
    for f in files:
        with open(f, encoding="utf-8") as fp:
            all_violations += _scan_korean_literals(fp.read(), filename=f)
    assert not all_violations, (
        "발신 모듈에 사용자 노출 한국어 하드코딩 발견 (get_text 미경유) — "
        "i18n 키로 전환하거나, 정당한 예외면 _ALLOWLIST 등재 + 회고 사유 명시:\n"
        + "\n".join(f"  {f}:{ln}  {txt!r}" for f, ln, txt in all_violations)
    )


# ── 메타 테스트: 스캐너 자체가 진짜 가드인지 증명 (mutation) ──
# Meta tests: prove the scanner is a real guard, not a no-op.

def test_scanner_detects_hardcoded_korean_body():
    """합성 코드의 하드코딩 한국어 body 를 탐지해야 한다 (사이클 154 P0 동형 — telegram.py:120)."""
    src = (
        "def handler(decision, decided_by):\n"
        "    body = f\"{'✅ 승인' if decision == 'approve' else '❌ 반려'} by @{decided_by}\"\n"
        "    return body\n"
    )
    violations = _scan_korean_literals(src)
    assert violations, "스캐너가 하드코딩 한국어 body 를 놓침 — 가드 무효"
    assert any("승인" in v[2] or "반려" in v[2] for v in violations)


def test_scanner_excludes_logger_and_docstring_korean():
    """logger 인자 + docstring 한국어는 위반이 아니어야 한다 (false-positive 차단)."""
    src = (
        "\"\"\"모듈 docstring 한국어 — i18n 대상 외.\"\"\"\n"
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(exc):\n"
        "    \"\"\"함수 docstring 한국어.\"\"\"\n"
        "    logger.warning('로그 조회 실패: %s', exc)\n"
        "    logger.exception(f'재시도 중단: {exc}')\n"
    )
    violations = _scan_korean_literals(src)
    assert not violations, f"logger/docstring 한국어를 위반으로 오탐: {violations}"
