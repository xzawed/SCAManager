"""src/templates/*.html <script> 블록에서 top-level const/let 선언 정적 스캔.
Static scanner for top-level const/let declarations in <script> blocks.

hx-boost body swap 시 <script> 블록은 동일 JS 컨텍스트에서 재실행됨.
top-level const/let 재선언 → SyntaxError → 핸들러 전체 무력화 (PR #604 회귀 학습).
On hx-boost body swap, <script> blocks re-execute in the same JS context.
Top-level const/let re-declaration → SyntaxError → all handlers silenced (PR #604).
"""

import re
from html.parser import HTMLParser
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "templates"


def _extract_inline_scripts(html: str) -> list[str]:
    """<script src=...> 외부 스크립트를 제외하고 인라인 <script> 블록 내용만 반환한다.
    Returns inline <script> block contents, excluding <script src=...> external scripts.
    """
    class _InlineScriptExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.blocks: list[str] = []
            self._in_script = False
            self._current: list[str] = []
            self._script_has_src = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() != "script":
                return
            self._in_script = True
            self._current = []
            self._script_has_src = any((name or "").lower() == "src" for name, _ in attrs)

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() != "script" or not self._in_script:
                return
            if not self._script_has_src:
                self.blocks.append("".join(self._current))
            self._in_script = False
            self._current = []
            self._script_has_src = False

        def handle_data(self, data: str) -> None:
            if self._in_script:
                self._current.append(data)

    parser = _InlineScriptExtractor()
    parser.feed(html)
    parser.close()
    return parser.blocks


def _find_toplevel_const_let(js: str) -> list[tuple[int, str]]:
    """JS 텍스트에서 brace depth 0 의 top-level const/let 선언 위치를 반환한다.
    Returns (line_number, keyword) for top-level const/let at brace depth 0.

    중괄호 깊이 추적 방식 — 주석·문자열 내부는 건너뜀.
    Tracks brace depth, skipping content inside comments and string literals.
    """
    violations: list[tuple[int, str]] = []
    depth = 0
    i = 0
    line = 1
    n = len(js)
    in_line_comment = False
    in_block_comment = False
    in_string = False
    string_char = ""

    while i < n:
        ch = js[i]

        # 개행: 줄번호 증가 + 라인 주석 종료
        # Newline: increment line counter and end line comment
        if ch == "\n":
            line += 1
            in_line_comment = False
            i += 1
            continue

        if in_line_comment:
            i += 1
            continue

        if in_block_comment:
            if js[i : i + 2] == "*/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if ch == "\\" and i + 1 < n:
                i += 2  # 이스케이프 문자 건너뜀 / skip escaped char
            elif ch == string_char:
                in_string = False
                i += 1
            else:
                i += 1
            continue

        # 주석 시작 감지 / detect comment start
        if js[i : i + 2] == "//":
            in_line_comment = True
            i += 2
            continue
        if js[i : i + 2] == "/*":
            in_block_comment = True
            i += 2
            continue

        # 문자열 시작 감지 (백틱 템플릿 리터럴 포함) / detect string start (incl. template literals)
        if ch in ('"', "'", "`"):
            in_string = True
            string_char = ch
            i += 1
            continue

        # 중괄호 깊이 추적 / track brace depth
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            continue

        # depth 0 에서만 top-level 선언 검사 / check only at depth 0
        if depth == 0:
            for kw in ("const ", "let "):
                if js[i : i + len(kw)] == kw:
                    # 직전 문자가 식별자 문자이면 키워드가 아님 (예: notconst)
                    # Skip if preceded by an identifier character (e.g. "notconst")
                    if i == 0 or not (js[i - 1].isalnum() or js[i - 1] == "_"):
                        violations.append((line, kw.strip()))
                    break

        i += 1

    return violations


def test_no_toplevel_const_let_in_templates():
    """모든 템플릿 <script> 블록에 top-level const/let 선언이 없어야 한다.
    No template <script> block should contain a top-level const/let declaration.

    위반 시 hx-boost 재방문에서 SyntaxError 발생 → 핸들러 전체 무력화.
    Violation causes SyntaxError on hx-boost re-visit → all handlers silenced.
    """
    all_violations: list[str] = []

    for html_file in sorted(_TEMPLATES_DIR.glob("*.html")):
        html = html_file.read_text(encoding="utf-8")
        scripts = _extract_inline_scripts(html)
        for block_idx, script in enumerate(scripts):
            hits = _find_toplevel_const_let(script)
            for line_in_block, kw in hits:
                all_violations.append(
                    f"{html_file.name} script#{block_idx + 1} line {line_in_block}: `{kw}`"
                )

    assert not all_violations, (
        "top-level const/let 선언 발견 — hx-boost SyntaxError 위험 (PR #604 회귀):\n"
        + "\n".join(f"  {v}" for v in all_violations)
    )
