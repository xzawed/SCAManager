r"""표의 행(`tr`)에 `::before`/`::after` 를 달지 않는다 — Chromium 은 그것을 «열 하나» 로 센다.

🔴 무엇을 막는가

    .x tbody tr::before { content: ""; position: absolute; left: 0; width: 3px; }

   headless Chromium 153 실측 — `position: absolute` 여도 행의 가상 요소가 첫 열 자리를
   차지해, 본문 행의 `td` 가 머리글 `th` 보다 **한 칸씩 오른쪽** 에 그려진다
   (가상 요소 없음 → th x == td x · `tr::before` absolute/static → 어긋남 ·
   `td:first-child::before` + `td:first-child { position: relative }` → 일치).
   행 강조선은 첫 칸에 단다 — `tr:hover td:first-child::before`.

🔴 계기를 뒤집어 봤다(`docs/workflow/verify.md` 「판정식을 쓸 때」 4).

   claimed(이 계기의 «이름» 이 포함한다고 적은 것)
     `tr` 복합 셀렉터 + `::before`/`::after`/`:before`/`:after` — `tr:hover::before` ·
     `tr.row::after` · `tr:nth-child(2n)::before` · 대소문자 무시(`TR::Before`) ·
     정적 CSS 와 템플릿 `<style>` 양쪽 · 주석 안의 언급은 **제외**
   cheap(첫 출력 「admin.css · repo_insights.css 두 파일이 red」 를 낼 가장 싼 과정
     = 부분문자열 `tr::before`)
     주석 `/* tbody tr::before */` · `.tr::before` · `.str::before` 를 잡고,
     `tr:hover::before` · `tr:before` · `tr.row::after` · `TR::Before` 를 놓친다

   claimed\cheap → **반드시 잡혀야** 한다  (`test_catches_every_row_pseudo_form`)
   cheap\claimed → **반드시 무시돼야** 한다 (`test_ignores_cells_classes_and_comments`)

   두 번째로 싼 과정(`\btr\b[^{]*::?(before|after)`)은 위 두 목록을 다 맞히지만
   `.tr-x::before` 와 **이 수정 자체** `tr:hover td:first-child::before` 를 위반으로 센다 —
   둘 다 무시 목록에 넣었다. 같은 심음 쌍을 손대지 않은 운영 파일(`components.css`)에
   끼워 넣고도 같은 뒤집힘을 요구한다(`test_plants_flip_inside_an_untouched_stylesheet`).

🔴 이 계기가 **못 보는** 것 — 여기 걸리지 않아도 안전하다는 뜻이 아니다.
   · CSS 중첩 `tr { &::before {} }` — 셀렉터 머리만 한 줄씩 읽으므로 `&` 를 부모로 풀지
     않는다. 이 리포 CSS 는 중첩 셀렉터를 쓰지 않는다(`&` 는 `main.css` 의
     `@custom-variant` 에만 있다 — 실측).
   · `:is(tr)::before` 처럼 함수 안에 든 `tr`, JS 가 주입하는 스타일,
     gitignore 된 `dist/tailwind.css`.

Table rows must not carry ::before/::after: Chromium lays the row pseudo-element out as an
extra first column, shifting every body cell one column right of its header. Put a row
accent on `td:first-child::before` instead. CSS nesting (`tr { &::before {} }`) and
`:is(tr)::before` are NOT covered — this scanner reads flat selector preludes only.
"""
from __future__ import annotations

import re
import subprocess  # nosec B404

import pytest

from ._contrast import ROOT

# `tr` 타입 셀렉터로 시작하는 복합 셀렉터가 `::before`/`::after`(구식 한 콜론 포함) 로 끝난다.
#   앞 글자가 경계·결합자여야 `.tr-x` · `.str` · `[data-tr]` 가 빠진다.
#   복합 셀렉터 조각(.클래스 · #아이디 · [속성] · :의사클래스(인자)) 은 몇 개든 허용한다.
# A compound starting with the `tr` type selector and ending in a before/after pseudo-element.
_TR_COMPOUND_PSEUDO = re.compile(
    r"(?:(?<=[\s>+~,(])|^)"
    r"tr"
    r"(?:\.[\w-]+|#[\w-]+|\[[^\]]*\]|::?(?!(?:before|after)\b)[\w-]+(?:\([^)]*\))?)*"
    r"::?(?:before|after)\b",
    re.I,
)

# 공허화 방어용 — 가상 요소 없이 `tr` 타입 셀렉터가 셀렉터 머리에 실제로 나오는가.
# Anti-vacuous: does a `tr` type selector appear in the preludes at all?
_TR_TYPE = re.compile(r"(?:(?<=[\s>+~,(])|^)tr(?![\w-])", re.I)

# `{` 앞의 셀렉터 머리 — 직전 `{` · `}` · `;` 뒤부터 `{` 까지.
# A rule prelude: the text between the previous `{`/`}`/`;` and the next `{`.
_PRELUDE = re.compile(r"([^{};]*)\{")

_STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)


def _strip_comments(src: str) -> str:
    r"""주석을 지우되 줄바꿈 수는 남긴다 — 보고하는 줄이 파일의 줄과 맞도록.

    `re.sub(r"/\*.*?\*/", "", src, flags=re.S)` 관용구 그대로, 지운 자리에 그 주석이 품었던
    줄바꿈만 되돌려 둔다. 주석 안에서 규칙을 인용해도(`/* tbody tr::before */`) 걸리지 않는다.
    Strip comments (repo idiom) but keep their newlines so reported lines match the file.
    """
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)


def row_pseudo_selectors(css: str) -> list[tuple[int, str]]:
    """`tr` 에 가상 요소를 다는 셀렉터를 (조각 안 줄번호, 셀렉터) 로 돌려준다.
    Return (line within the snippet, offending selector) for each row pseudo-element."""
    text = _strip_comments(css)
    found: list[tuple[int, str]] = []
    for pm in _PRELUDE.finditer(text):
        prelude = pm.group(1)
        for sm in _TR_COMPOUND_PSEUDO.finditer(prelude):
            line = text.count("\n", 0, pm.start(1) + sm.start()) + 1
            found.append((line, sm.group(0)))
    return found


def style_blocks(html: str) -> list[tuple[int, str]]:
    """템플릿의 `<style>` 내용을 (파일 안 시작 줄, 원문) 으로.
    The template's `<style>` contents with their file-relative start line."""
    return [(html.count("\n", 0, m.start(1)) + 1, m.group(1)) for m in _STYLE.finditer(html)]


def _tracked(under: str, suffix: str) -> list[str]:
    """git 추적 파일만, 한 번씩. `git ls-files` 는 충돌 중인 경로를 stage 마다 되풀이한다.
    Git-tracked files only, deduped (a conflicted path is listed once per stage)."""
    out = subprocess.run(  # nosec B603 B607
        ["git", "ls-files", "-z", "--", under], cwd=str(ROOT),
        capture_output=True, check=True,
    ).stdout.decode("utf-8").split("\0")
    return list(dict.fromkeys(
        p for p in out if p.endswith(suffix) and (ROOT / p).is_file()))


def _sources() -> list[tuple[str, int, str]]:
    """검사 대상을 (경로, 그 조각이 시작하는 파일 안의 줄, 원문) 으로 연다."""
    out: list[tuple[str, int, str]] = []
    for rel in _tracked("src/static/css", ".css"):
        out.append((rel, 1, (ROOT / rel).read_text(encoding="utf-8")))
    for rel in _tracked("src/templates", ".html"):
        for start, block in style_blocks((ROOT / rel).read_text(encoding="utf-8")):
            out.append((rel, start, block))
    return out


@pytest.mark.parametrize("css", [
    ".x tbody tr::before { content: ''; }",
    ".x tbody tr:hover::before { transform: scaleY(1); }",
    ".x tr.row::after { content: ''; }",
    ".x tbody tr:nth-child(2n)::before { content: ''; }",
    "tr:before { content: ''; }",
    ".x TBODY TR::Before { content: ''; }",
    ".a,\n.x tbody > tr::after { content: ''; }",
    "@media (prefers-reduced-motion: reduce) {\n  .x tbody tr::before { transition: none; }\n}",
])
def test_catches_every_row_pseudo_form(css):
    r"""claimed\cheap 포함 — 부분문자열 `tr::before` 는 이 중 절반을 놓친다."""
    assert len(row_pseudo_selectors(css)) == 1, css


@pytest.mark.parametrize("css", [
    ".x th::before { content: ''; }",
    ".x td::before { content: ''; }",
    ".x tbody tr:hover td:first-child::before { transform: scaleY(1); }",
    ".tr-x::before { content: ''; }",
    ".tr::before { content: ''; }",
    ".str::before { content: ''; }",
    "[data-tr]::before { content: ''; }",
    "/* tbody tr::before */\n.x td { color: red; }",
    ".x tbody tr { position: relative; }",
])
def test_ignores_cells_classes_and_comments(css):
    r"""cheap\claimed 포함 — 둘째로 싼 과정은 `.tr-x` 와 이 수정의 셀렉터를 위반으로 센다."""
    assert row_pseudo_selectors(css) == [], css


def test_style_blocks_read_only_the_style_element():
    """템플릿에서는 `<style>` 안만 CSS 다 — 본문 텍스트의 같은 글자는 셀렉터가 아니다."""
    html = ("<p>tbody tr::before {</p>\n<style>\n  .a { color: red; }\n"
            "  .x tbody tr::after { content: ''; }\n</style>")
    blocks = style_blocks(html)
    assert [start for start, _ in blocks] == [2]
    assert [(start + ln - 1, sel) for start, b in blocks
            for ln, sel in row_pseudo_selectors(b)] == [(4, "tr::after")]


def test_plants_flip_inside_an_untouched_stylesheet():
    """🔴 같은 심음 쌍을 이 수정이 건드리지 않은 운영 파일에 끼운다 — 합성 조각에서만
    맞는 계기가 아닌지 본다. 위반 심음은 정확히 1건을 더하고, 적법 심음은 0건을 더한다."""
    rel = "src/static/css/components.css"
    src = (ROOT / rel).read_text(encoding="utf-8")
    cut = src.index("}\n", len(src) // 2) + 2
    base = row_pseudo_selectors(src)
    bad = src[:cut] + ".plant tbody tr:hover::before { content: ''; }\n" + src[cut:]
    ok = (src[:cut] + "/* .plant tbody tr::before */\n"
          ".plant tbody tr:hover td:first-child::before { content: ''; }\n" + src[cut:])
    got = [s for _, s in row_pseudo_selectors(bad)]
    assert len(got) == len(base) + 1
    assert got.count("tr:hover::before") == [s for _, s in base].count("tr:hover::before") + 1
    assert row_pseudo_selectors(ok) == base


def test_the_scan_actually_reaches_both_stylesheets_and_template_styles():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 안 읽었다」를 가른다."""
    sources = _sources()
    names = {n for n, _, _ in sources}
    assert "src/static/css/repo_insights.css" in names
    assert "src/static/css/admin.css" in names
    assert any(n.endswith(".html") for n in names), "템플릿 `<style>` 을 하나도 안 읽었다"
    # 판정 대상인 `tr` 타입 셀렉터를 실제로 만났는가 — 머리를 못 읽으면 이 수가 0 이다.
    preludes = [pm.group(1) for _, _, s in sources
                for pm in _PRELUDE.finditer(_strip_comments(s))]
    assert any(_TR_TYPE.search(p) for p in preludes), "셀렉터 머리에서 `tr` 을 하나도 못 봤다"


def test_no_table_row_gets_a_pseudo_element():
    bad = [(name, start + line - 1, sel)
           for name, start, text in _sources()
           for line, sel in row_pseudo_selectors(text)]
    assert not bad, (
        "표의 행에 ::before/::after 가 달렸다 — Chromium 이 그것을 열 하나로 세어 본문 행이 "
        "머리글보다 한 칸 밀린다. `td:first-child::before` 로 옮긴다:\n  "
        + "\n  ".join(f"{n}:{ln}  {s}" for n, ln, s in bad))
