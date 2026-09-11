"""선언만 되고 아무도 읽지 않는 디자인 토큰 — «죽은 토큰» 은 0이어야 한다.

죽은 토큰은 조용히 거짓말을 한다. `--chart-1`~`--chart-5`·`--chart-axis` 는 네 테마 ×
signature 변주까지 색이 정의돼 있어서 「차트 팔레트가 테마별로 있다」로 읽혔지만,
실제로 차트를 그리는 코드는 그 이름을 **한 번도 읽지 않았다**(#1639 W19).
같은 이유로 `--aurora-*`·`--container-*` 등도 값만 남아 있었다.

Dead tokens lie: a themed palette that nothing reads still reads as "we have one".

🔴 판정은 **양방향 등식**이다 — `선언 - 소비 == ∅`. 「6개가 없다」 같은 손 목록이 아니라
   집합이 비었는지를 본다. 손 목록은 새 죽은 토큰이 생겨도 조용하다.

🔴 소비 축이 둘이다. `var(--x)` 만 보면 안 된다 — 이 리포는 `readVar('--text-subtle', …)`·
   `getPropertyValue('--chart-grid')` 처럼 **문자열로** 읽는 축이 있어서, `var()` 만 세면
   살아 있는 토큰이 죽은 것으로 나온다(실측: 그 방식이 `--text-subtle` 을 죽은 것으로 오판).

🔴 소비는 `src/` 안의 «읽는 형태» 만 센다. 이름이 «등장» 하는 것으로 세면 **가드가 자기
   문서에 속는다** — 이 파일의 산문이 `--chart-1` 을 언급하자 그 토큰이 살아 있는 것으로
   집계돼 죽은 토큰 15개가 12개로 줄었다(실측). 문서·테스트가 이름을 적는 것은 제품이
   그 토큰을 읽는다는 뜻이 아니다.

🔴 경계를 본다. `--chart-1` 은 `--chart-10` 의 부분문자열이다. 부분문자열 일치로 세면
   존재하지 않는 소비를 세어 거짓 초록이 된다.
"""
import pathlib
import re

from ._contrast import ROOT, strip_css_comments

# 토큰을 «선언» 하는 곳 — 소스 CSS 전부. `dist/` 는 추적되지 않는 빌드 산출물이라 제외한다
# (tailwind 가 main.css 에서 생성하며, 독립적인 소비자가 아니다).
_CSS_DIR = ROOT / "src" / "static" / "css"

# 토큰을 «읽는» 곳 — 제품 코드(`src/`)만이다. 확장자로 파생하고 손으로 파일을 적지 않는다.
# 테스트·문서를 넣으면 그것들이 이름을 «언급» 하는 것만으로 죽은 토큰이 살아난다.
_CONSUMER_GLOB = "src/**/*"
_CONSUMER_SUFFIXES = {".css", ".html", ".js", ".mjs", ".ts", ".py"}
_EXCLUDED_PARTS = ("__pycache__", "vendor", "node_modules")
_EXCLUDED_DIRS = (_CSS_DIR / "dist",)

# 커스텀 프로퍼티 «선언» 은 블록 시작(`{`)·직전 선언의 끝(`;`)·줄머리 뒤에서만 시작한다.
#
# 🔴 줄 단위로 보면 안 된다. 첫 판은 「`{` 가 있는 줄은 셀렉터」로 걸렀는데, 그러면
#    `:root { --zz: red; }` 한 줄짜리 블록의 선언이 통째로 안 보인다 — 역-뮤테이션을
#    심었더니 가드가 **초록으로 통과했다**(실측). 부재보다 나쁜 거짓 집행자였다.
# 🔴 `.btn--primary:hover` 를 선언으로 세면 안 된다. 이 경계 조건이 그것도 막는다 —
#    `--primary` 앞에 `.btn` 이 있어 `{`/`;`/줄머리 어느 것도 아니다(실측: 그렇게 7건 오판).
_DECL_RE = re.compile(r"(?:^|[{;])\s*(--[\w-]+)\s*:", re.MULTILINE)


def _css_sources() -> dict[pathlib.Path, str]:
    files = sorted(p for p in _CSS_DIR.glob("*.css") if p.is_file())
    assert files, f"CSS 원문을 못 찾았다 — 경로가 바뀌었다: {_CSS_DIR}"
    return {p: p.read_text(encoding="utf-8") for p in files}


def declared_tokens() -> dict[str, set[str]]:
    """`--x: value;` 형태의 «선언» 만 모은다 → {토큰: {파일명}}."""
    out: dict[str, set[str]] = {}
    for path, src in _css_sources().items():
        for m in _DECL_RE.finditer(strip_css_comments(src)):
            out.setdefault(m.group(1), set()).add(path.name)
    assert len(out) > 50, f"선언이 {len(out)}개뿐 — 파서가 늙었다(공허한 초록 방지)"
    return out


def _consumer_files() -> list[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    for path in ROOT.glob(_CONSUMER_GLOB):
        if not path.is_file() or path.suffix not in _CONSUMER_SUFFIXES:
            continue
        if any(part in str(path) for part in _EXCLUDED_PARTS):
            continue
        if any(d in path.parents for d in _EXCLUDED_DIRS):
            continue
        seen.add(path)
    assert len(seen) > 20, f"소비자 후보 파일이 {len(seen)}개 — 글롭이 늙었다"
    return sorted(seen)


def _read_probe(name: str) -> re.Pattern[str]:
    """그 토큰을 «읽는» 두 형태만 인정한다 — `var(--x)` 와 따옴표 문자열 `'--x'`.

    경계를 강제한다: 뒤에 `[\\w-]` 가 오면 다른 토큰이다(`--chart-1` vs `--chart-10`).
    """
    tok = re.escape(name)
    return re.compile(rf"""var\(\s*{tok}(?![\w-])|['"]{tok}(?![\w-])""")


def unread_tokens() -> dict[str, set[str]]:
    """선언됐으나 제품 코드가 «읽지» 않는 토큰."""
    declared = declared_tokens()
    probes = {name: _read_probe(name) for name in declared}
    unread = dict(declared)
    for path in _consumer_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in list(unread):
            if probes[name].search(text):
                del unread[name]
    return unread


def test_no_declared_token_is_left_unread():
    """🔴 양방향 등식 — 선언 집합에서 소비 집합을 빼면 비어야 한다.

    red 로 만드는 뮤테이션: `tokens.css` 에 `--zz-dead: red;` 한 줄을 넣으면 red.
    반대 방향: 살아 있는 토큰의 소비를 전부 지워도 red(그 토큰이 죽은 것이 되므로).
    """
    unread = unread_tokens()
    assert not unread, (
        f"아무도 읽지 않는 토큰 {len(unread)}개 — 지우거나 배선한다: "
        + ", ".join(f"{k}({','.join(sorted(v))})" for k, v in sorted(unread.items()))
    )


def test_guard_can_actually_see_a_dead_token():
    """가드가 «잴 수 있는지» 를 잰다 — 죽은 토큰을 심으면 탐지되는가.

    이 시험이 없으면 파서가 조용히 망가져 「죽은 토큰 0」이 영원한 초록이 된다.
    """
    declared = declared_tokens()
    planted = "--test-only-dead-token-probe"
    assert planted not in declared, "심을 이름이 이미 쓰이고 있다 — 다른 이름을 고를 것"
    probe = _read_probe(planted)
    assert probe.search(f"color: var({planted});"), "탐지기가 `var()` 소비를 못 본다"
    assert probe.search(f"readVar('{planted}', '#000')"), "탐지기가 문자열 소비를 못 본다"
    # 산문은 소비가 아니다 — 이 가드가 자기 문서에 속았던 축
    assert not probe.search(f"주석에서 {planted} 를 언급한다"), (
        "산문 언급이 소비로 세어진다 — 문서가 죽은 토큰을 살려낸다(실측 15→12)"
    )
    # 경계 검사가 실제로 동작하는가 — 부분문자열은 소비가 아니다
    assert not _read_probe("--chart-1").search("color: var(--chart-10);"), (
        "경계 검사 소실 — `--chart-1` 이 `--chart-10` 에 걸린다(거짓 초록)"
    )


def test_declaration_parser_sees_every_css_shape():
    """🔴 선언 파서의 «축» 을 전부 건다 — 한 축만 걸면 거짓 집행자가 된다.

    실측: 첫 판은 「`{` 가 있는 줄은 셀렉터」로 걸렀고, `:root { --zz: red; }` 를
    tokens.css 에 심는 역-뮤테이션이 **초록으로 통과했다**. 가드가 있는데 못 잡았다.
    """
    shapes = {
        "여러 줄 블록": ":root {\n  --a-tok: red;\n}",
        "한 줄 블록": ":root { --b-tok: red; }",
        "한 줄에 둘": ":root { --c-tok: red; --d-tok: blue; }",
        "테마 블록": '[data-theme="light"] { --e-tok: red; }',
    }
    for label, css in shapes.items():
        found = {m.group(1) for m in _DECL_RE.finditer(css)}
        assert found, f"{label} 형태의 선언을 파서가 못 본다 — 그 축이 통째로 열려 있다"
    assert {m.group(1) for m in _DECL_RE.finditer(shapes["한 줄에 둘"])} == {
        "--c-tok",
        "--d-tok",
    }, "한 줄에 둘 있으면 하나만 본다 — `;` 경계 소실"
    # 셀렉터는 선언이 아니다
    assert not {m.group(1) for m in _DECL_RE.finditer(".btn--primary:hover { color: red; }")}, (
        "`.btn--primary:hover` 를 선언으로 센다 — 있지도 않은 토큰이 죽은 것으로 나온다"
    )
