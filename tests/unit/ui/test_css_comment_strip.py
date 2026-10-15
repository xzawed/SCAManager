r"""`_contrast.strip_css_comments` — 대비·토큰 가드가 «판정 전에» 쓰는 주석 제거기.

🔴 `re.sub(r"/\*.*?\*/", "", src)` 는 이 리포가 스스로 «두 번째로 싼, 틀린 과정» 이라 적은
   관용구다(`test_css_comment_nesting.py` 머리말). 문자열 리터럴·따옴표 없는 `url(...)` 안의
   `/*` 를 주석 시작으로 읽어, 다음 `*/` 까지 — **뒤따르는 규칙까지** — 지운다. 지워진 규칙은
   그 위에 선 가드에게 «없는 것» 이 된다. 지금 리포 안에 그 모양은 0건이라 잠복이다
   (2026-09-16 회고 P2-53).

🔴 계기를 뒤집어 봤다(`verify.md` 「판정식을 쓸 때」 4). 두 목록을 먼저 적었다.

   claimed(이름 = «CSS 주석을 지운다») — 주석 · 여러 줄 주석의 줄바꿈 보존 ·
     문자열 안 `/*` 는 주석이 아님 · 따옴표 없는 `url(...)` 안 `/*` 도 주석이 아님
   cheap(첫 출력 = «주석이 사라진 원문» 을 낼 가장 싼 과정 = 위 정규식)
     문자열·url 안의 `/*` 부터 다음 `*/` 까지를 지운다

   claimed\cheap = 문자열 안 `/*` → 뒤 규칙이 **살아 있어야** 한다
   cheap\claimed = (해당 없음 — 싼 과정이 «더» 지우는 쪽만 틀린다) → 대신 **두 번째 싼 과정**
     («문자열을 먼저 지우고 주석을 나중에») 이 틀리는 입력을 심는다: 주석 «안» 의 따옴표.

Strip CSS comments without eating the rule that follows a `/*` inside a string or url token.
"""
from __future__ import annotations

import ast

from ._contrast import ROOT, strip_css_comments

_NAIVE = r"/\*.*?\*/"


def test_a_comment_opener_inside_a_string_does_not_eat_the_next_rule():
    r"""claimed\cheap — 싼 정규식은 `"/*"` 부터 진짜 주석의 `*/` 까지 지워 `.b` 를 없앤다."""
    src = '.a::before { content: "/*"; }\n.b { color: red; }\n/* 진짜 주석 */\n.c { color: blue; }'
    out = strip_css_comments(src)
    assert ".b { color: red; }" in out, out
    assert '"/*"' in out, "문자열 리터럴은 그대로 남아야 한다"
    assert "진짜 주석" not in out, "진짜 주석은 지워져야 한다"


def test_a_comment_opener_inside_an_unquoted_url_does_not_eat_the_next_rule():
    """따옴표 없는 `url(...)` 은 통째로 한 토큰이다 — 그 안의 `/*` 는 주석이 아니다."""
    src = ".a { background: url(data:image/svg+xml;x=/*y); }\n.b { color: red; }\n/* c */"
    out = strip_css_comments(src)
    assert ".b { color: red; }" in out, out
    assert "url(data:image/svg+xml;x=/*y)" in out


def test_a_quote_inside_a_comment_does_not_open_a_string():
    """두 번째 싼 과정(문자열 먼저 · 주석 나중) 이 틀리는 입력 — 주석 «안» 의 따옴표.

    그 과정은 `it's` 의 `'` 부터 뒤 규칙의 `'` 까지를 문자열로 먹어 `.b` 를 지운다.
    """
    src = "/* it's a note */\n.b { color: red; }\n.c::before { content: 'x'; }"
    out = strip_css_comments(src)
    assert out == "\n.b { color: red; }\n.c::before { content: 'x'; }", repr(out)


def test_a_multiline_comment_keeps_its_newlines():
    """지운 자리에 줄바꿈만 남긴다 — 가드가 보고하는 줄이 파일의 줄과 맞도록."""
    src = ".a { color: red; }\n/* 한 줄\n   두 줄\n   세 줄 */\n.b { color: blue; }"
    out = strip_css_comments(src)
    assert out.count("\n") == src.count("\n")
    assert out.splitlines()[4] == ".b { color: blue; }"


def test_an_unterminated_comment_runs_to_the_end_of_the_source():
    """CSS 는 닫히지 않은 주석을 파일 끝까지 주석으로 본다 — 그 뒤는 규칙이 아니다."""
    out = strip_css_comments(".a { color: red; }\n/* 닫히지 않음\n.b { color: blue; }")
    assert ".b" not in out and ".a { color: red; }" in out


def _naive_pattern_sites() -> list[str]:
    """`tests/unit/ui/*.py` 안에서 싼 정규식을 «값» 으로 쓰는 자리.

    🔴 AST 의 문자열 상수가 그 패턴과 **정확히 같을 때만** 센다 — 머리말·주석이 그 관용구를
       «인용» 하는 것은 사용이 아니다(부분문자열로 세면 이 파일 머리말부터 걸린다).
    """
    sites = []
    for path in sorted((ROOT / "tests" / "unit" / "ui").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value == _NAIVE:
                sites.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    return sites


def test_no_ui_guard_strips_comments_with_the_known_wrong_regex():
    """🔴 형제 가드가 각자 그 정규식을 들고 있으면, 한 곳을 고쳐도 나머지가 같은 구멍이다.

    주석 제거는 `_contrast.strip_css_comments` 한 곳에서 한다.
    """
    sites = [s for s in _naive_pattern_sites() if not s.startswith(
        "tests/unit/ui/test_css_comment_strip.py")]
    assert not sites, ("싼 주석 정규식을 «값» 으로 쓰는 UI 가드가 있다 — "
                       "`_contrast.strip_css_comments` 를 쓴다:\n  " + "\n  ".join(sites))


def test_the_site_scan_sees_a_real_use_and_ignores_a_quotation():
    """🔴 대조군 — 위 스캔이 죽으면 「0건」으로 조용히 초록이다.

    잡혀야 할 것 = 이 파일의 `_NAIVE` 상수(실제 «값») · 무시돼야 할 것 = 머리말의 인용.
    """
    mine = [s for s in _naive_pattern_sites()
            if s.startswith("tests/unit/ui/test_css_comment_strip.py")]
    assert len(mine) == 1, f"이 파일의 상수 하나만 잡혀야 한다(머리말 인용은 무시): {mine}"
