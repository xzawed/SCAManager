r"""브라우저가 «통째로 버리는» CSS 규칙을 만드는 주석 구조 깨짐을 막는다 — #1639 W15 2차.

🔴 무엇을 막는가

    /* 설명 */
       설명이 한 줄 더 샜다. */          ← 주석 «밖» 의 종결자
    .hook-alert.warn { ... }             ← 이 규칙이 통째로 사라진다

   CSS 파서는 주석 밖의 `*/` 부터 다음 `{` 까지를 셀렉터로 읽고, 그 셀렉터가 깨졌으므로
   **뒤따르는 블록까지 함께** 버린다. 화면에서 그 규칙만 조용히 없어진다.

🔴 왜 이 가드가 필요한가: 이 리포의 CSS 판정은 전부 정규식으로 **텍스트** 를 읽는다.
   실제 파서를 한 번도 통과시키지 않으므로, 브라우저가 버리는 규칙도 「선언이 거기 적혀
   있다」로 읽고 초록이 된다. 실측 — 이 결함이 든 작업트리에서 `tests/unit/ui` 546건이
   전건 초록이었고, Chromium CSSOM 은 규칙 수 168 → 167 · `.hook-alert.warn` 1 → 0 이었다.

🔴 계기를 뒤집어 봤다(`verify.md` 「판정식을 쓸 때」 4). 두 목록을 먼저 적었다.

   claimed(이 계기의 «이름» 이 포함한다고 적은 것)
     정적 CSS · 템플릿 `<style>` · 닫히지 않은 `/*` · 주석 밖 `*/` ·
     🔴 «중첩 시도» `/* a /* b */ c */` — 여는 표시 2 · 닫는 표시 2 라 **개수는 맞는데**
     뒤쪽이 주석 밖이다
   cheap(첫 출력만 보고 적은 «그 출력을 낼 가장 싼 과정» = `/*` 와 `*/` 의 개수 비교)
     개수가 어긋나는 모든 경우 · 🔴 문자열 리터럴 안의 `*/`(`content: "*/"`) — 개수 세기는
     이것도 위반으로 센다

   claimed\cheap = 중첩 시도 → **반드시 잡혀야** 한다  (`test_catches_the_nested_comment_attempt`)
   cheap\claimed = 문자열 안 종결자 → **반드시 무시돼야** 한다 (`test_ignores_a_terminator_inside_a_string`)

   두 번째로 싼 과정(`re.sub(r"/\*.*?\*/", "", src)` 뒤 `*/` 찾기)도 재봤다 — 중첩 시도는
   맞히지만 문자열 안 종결자를 **오탐** 한다. 문자열을 아는 것이 이 계기의 구분점이다.

Forbid comment nesting that makes a browser silently discard the following rule.
"""
from __future__ import annotations

import re

from ._contrast import ROOT

# 주석 밖 종결자 · 닫히지 않은 주석 — 둘 다 뒤따르는 규칙을 삼킨다.
# Stray terminator and unterminated comment both swallow the rule that follows.
STRAY_TERMINATOR = "주석 밖 `*/`"
UNTERMINATED = "닫히지 않은 `/*`"


def comment_defects(src: str) -> list[tuple[int, str]]:
    """주석 구조가 깨진 자리를 (줄번호, 종류) 로 돌려준다.

    문자열 리터럴과 따옴표 없는 `url(...)` 안은 주석 표시로 보지 않는다 —
    `content: "*/"` 도 `url(...x=*/y)` 도 적법한 CSS 다.
    Strings and unquoted url() tokens are opaque: comment markers inside them are not comments.
    """
    defects: list[tuple[int, str]] = []
    i, line, n = 0, 1, len(src)
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
        elif src.startswith("/*", i):
            end = src.find("*/", i + 2)
            if end < 0:
                defects.append((line, UNTERMINATED))
                break
            line += src.count("\n", i, end)
            i = end + 2
        elif src.startswith("*/", i):
            defects.append((line, STRAY_TERMINATOR))
            i += 2
        elif src[i:i + 4].lower() == "url(" and src[i + 4:i + 40].lstrip()[:1] not in "\"'":
            # 🔴 따옴표 없는 `url(...)` 토큰 안에서는 `*/` 도 `/*` 도 주석이 아니다.
            #    실측 — 이 갈래가 없으면 `url(data:image/svg+xml;x=*/y)` 를 위반으로 센다.
            # An unquoted url() token is opaque: comment markers inside it are not comments.
            close = src.find(")", i + 4)
            if close < 0:
                break
            line += src.count("\n", i, close)
            i = close + 1
        elif ch in "\"'":
            # 이스케이프를 건너뛰며 닫는 따옴표까지. 줄바꿈이 먼저 오면 거기서 끝난다.
            # Skip to the closing quote, honouring escapes; a raw newline ends it.
            j = i + 1
            while j < n and src[j] != ch and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            i = j + 1
        else:
            i += 1
    return defects


def _blocks() -> list[tuple[str, int, str]]:
    """검사 대상을 (경로, 그 조각이 시작하는 **파일 안의** 줄, 원문) 으로 연다.

    🔴 주석을 **지우지 않은** 원문이어야 한다 — 지운 뒤에 보면 이 결함이 정의상 사라진다.
    🔴 줄 시작점을 함께 들고 다닌다. `<style>` 블록만 떼어 세면 보고되는 줄이 파일의 줄과
       어긋나, 다음 사람이 엉뚱한 자리를 연다(실측: 보고 338 · 실제 341).
    Raw source with the file-relative line offset: stripping comments erases the defect,
    and counting inside the extracted block reports the wrong line.
    """
    out: list[tuple[str, int, str]] = []
    for f in sorted((ROOT / "src" / "static" / "css").glob("*.css")):
        out.append((str(f.relative_to(ROOT)), 1, f.read_text(encoding="utf-8")))
    for f in sorted((ROOT / "src" / "templates").rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S | re.I):
            out.append((str(f.relative_to(ROOT)),
                        text.count("\n", 0, m.start(1)) + 1, m.group(1)))
    return out


def test_catches_the_nested_comment_attempt():
    r"""claimed\cheap — 개수는 맞는데 뒤가 주석 밖이다. 개수 세기는 이것을 통과시킨다."""
    seeded = ".a { color: red; }\n/* 바깥 /* 안쪽 */ 남은 꼬리 */\n.b { color: blue; }"
    assert seeded.count("/*") == seeded.count("*/"), "이 심음은 «개수가 맞는» 것이어야 한다"
    assert [d for _, d in comment_defects(seeded)] == [STRAY_TERMINATOR]


def test_ignores_a_terminator_inside_a_string():
    r"""cheap\claimed — 적법한 CSS 다. 개수 세기는 이것을 위반으로 센다."""
    seeded = '.a::before { content: "*/"; }\n.b { color: red; }'
    assert seeded.count("*/") > seeded.count("/*"), "이 심음은 «개수가 어긋나는» 것이어야 한다"
    assert comment_defects(seeded) == []


def test_ignores_a_terminator_inside_an_unquoted_url():
    r"""🔴 적대 스윕에서 나온 진짜 오탐 — 계기가 먼저 거짓말했다.

    따옴표 없는 `url(...)` 은 통째로 한 토큰이라 그 안의 `*/` 는 주석 종결자가 아니다.
    이 갈래가 없을 때 아래 스니펫이 위반 1건으로 셌다(실측).
    """
    seeded = ".a { background: url(data:image/svg+xml;x=*/y); }\n.b { color: red; }"
    assert comment_defects(seeded) == []


def test_the_scan_actually_reaches_both_static_css_and_template_styles():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 안 읽었다」를 가른다."""
    blocks = _blocks()
    assert any(n.endswith(".css") for n, _, _ in blocks), "정적 CSS 를 하나도 안 읽었다"
    assert any(n.endswith(".html") for n, _, _ in blocks), "템플릿 `<style>` 을 하나도 안 읽었다"
    # 주석을 실제로 만났는가 — 원문을 읽지 않으면 이 수가 0 이 된다.
    assert sum(s.count("/*") for _, _, s in blocks) > 100
    # 줄 시작점이 실제로 파일 안쪽을 가리키는가 — 전부 1 이면 좌표가 죽은 것이다.
    assert any(start > 1 for _, start, _ in blocks)


def test_no_stylesheet_has_broken_comment_nesting():
    bad = [(name, start + line - 1, kind)
           for name, start, text in _blocks()
           for line, kind in comment_defects(text)]
    assert not bad, (
        "주석 구조가 깨졌다 — CSS 파서가 뒤따르는 규칙을 **통째로 버린다**:\n  "
        + "\n  ".join(f"{n}:{ln}  ({k})" for n, ln, k in bad))
