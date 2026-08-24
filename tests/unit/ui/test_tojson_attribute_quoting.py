"""`tojson` 이 든 HTML 속성은 **홑따옴표**여야 한다 — 이중따옴표는 속성을 깨뜨린다.

🔴 왜: Jinja `tojson` 은 결과를 `Markup`(safe)으로 표시하므로 autoescape 가 `"` 를 바꾸지
않는다. 그래서 이중따옴표 속성 안에 넣으면 JSON 의 첫 `"` 에서 **속성이 종료**된다.

실측(브라우저, Chromium):
    onsubmit="return confirm({{ msg | tojson }});"
    -> onsubmitAttrRaw       = 'return confirm('
    -> onsubmitHandlerExists = False
    -> 제출 클릭 결과          = 'SUBMITTED confirmCalled=false'
즉 「저장소 삭제」가 **확인 대화상자 없이 실행**됐다 (#1493).

홑따옴표는 원천적으로 안전하다 — `tojson` 은 `'` 를 `\\u0027` 로 이스케이프한다(실측):
    "It's a test"  ->  "It\\u0027s a test"
반면 `"` 는 그대로 남는다.

`tojson` is Markup-safe, so autoescape leaves `"` intact; inside a double-quoted attribute the
value terminates at the first JSON quote. Single quotes are safe because tojson escapes `'`.
"""
from __future__ import annotations

import pathlib

import pytest

_DQ = '"'
_SQ = "'"
_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "templates"


def _attribute_context(line: str, pos: int) -> str:
    """`line[pos]` 가 속한 속성 컨텍스트 — ``double`` / ``single`` / ``bare``.

    `=` 바로 뒤의 따옴표만 여는 따옴표로 인정하고, 그 줄에서 닫히지 않은 채
    `{{` 에 도달한 것을 "열린 속성"으로 본다.
    """
    start = line.rfind("{{", 0, pos)
    if start < 0:
        return "bare"
    head = line[:start]

    open_kind: str | None = None
    i = 0
    while i < len(head):
        ch = head[i]
        if ch in (_DQ, _SQ) and i > 0 and head[i - 1] == "=":
            close = head.find(ch, i + 1)
            if close < 0:
                open_kind = ch
                break
            i = close + 1
            continue
        i += 1
    if open_kind is None:
        return "bare"
    return "double" if open_kind == _DQ else "single"


# ── 계기 자기검증 — 이 판정기가 틀리면 아래 전수 검사가 공허하다 ──────────────

@pytest.mark.parametrize(
    "line,expected",
    [
        ('  onsubmit="return confirm({{ x | tojson }});"', "double"),
        ("  data-x='{{ y | tojson }}'", "single"),
        # 표현식 안에 `}` 가 있어도(`or {}`) 판정이 끊기면 안 된다 — 실제로 겪은 오탐.
        ('  data-x="{{ (a or {}).get(' + _SQ + "b" + _SQ + ", []) | tojson }}\"", "double"),
        ("  var v = {{ y | tojson }};", "bare"),
        ('  <a href="/x" data-y="{{ z | tojson }}">', "double"),
        ('  <a href="/x">{{ z | tojson }}</a>', "bare"),
    ],
)
def test_attribute_context_detector(line, expected):
    assert _attribute_context(line, line.index("tojson")) == expected


# ── 전수 검사 ────────────────────────────────────────────────────────────

def _tojson_sites() -> list[tuple[str, int, str, str]]:
    out = []
    for f in sorted(_TEMPLATE_DIR.rglob("*.html")):
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            pos = 0
            while True:
                pos = line.find("tojson", pos)
                if pos < 0:
                    break
                out.append((f.name, lineno, _attribute_context(line, pos), line.strip()[:100]))
                pos += 6
    return out


def test_tojson_sites_are_found():
    """계기 자기검증 — 한 건도 못 찾으면 아래 단언이 공허하다."""
    sites = _tojson_sites()
    assert len(sites) >= 20, f"tojson 출현을 {len(sites)}건만 찾았다 — 스캐너 점검 필요"


def test_no_tojson_inside_double_quoted_attribute():
    """🔴 `tojson` 이 이중따옴표 속성 안에 있으면 그 속성은 렌더 시 깨진다."""
    broken = [
        f"{name}:{lineno}  {src}"
        for name, lineno, ctx, src in _tojson_sites()
        if ctx == "double"
    ]
    assert not broken, (
        "이중따옴표 속성 안 tojson — 속성이 JSON 첫 따옴표에서 종료된다. "
        "홑따옴표로 바꿔라(tojson 이 `'` 를 이스케이프하므로 안전):\n  "
        + "\n  ".join(broken)
    )
