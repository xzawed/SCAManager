"""HTML 을 담은 번역문이 **글자가 아니라 마크업으로** 렌더되고, 그 마크업이 성립한다.

## 왜 — 운영자 화면에 `<strong>` 이 글자로 보이고 있었다 (실측)

프로덕션 Jinja 환경(`src.ui._helpers.templates.env`, `autoescape=True`)으로 실제 템플릿 줄을
렌더한 결과:

    <li>&lt;strong&gt;RLS 적용&lt;/strong&gt; = PostgreSQL 만 (SQLite 단위 테스트 자동 skip)</li>

세 언어 합집합으로 HTML 태그를 담은 번역 키 50개 중 **5개**가 `| safe` 없이 렌더돼
태그가 그대로 글자였다(`admin.rls_audit.info_li1`, `admin.operations.info_li1`~`li4`).

🔴 이 축을 보는 가드가 없었다. `test_i18n_args_safe_contract.py` 는 **반대 방향**만 본다 —
`| safe` 에 kwargs 가 붙는 것을 막을 뿐, `| safe` 가 **빠진** 것은 보지 않는다.

## 이 파일이 강제하는 것 — 두 축

1. **도달** — 태그를 담은 번역은 브라우저에 마크업으로 닿는다. `| safe` 문자열을 세지 않고
   **프로덕션 env 로 그 줄을 렌더해서** 본다. 예외는 속성 위치 하나뿐이다
   (`data-i18n-*="{{ ... }}"` 안에서는 이스케이프가 정답이고, JS 가 읽어 다시 삽입한다).
2. **성립** — `| safe` 는 **키**에 붙지 값에 붙지 않는다. 값에 `<strong>` 을 안 닫으면
   굵게가 페이지 뒤쪽으로 번지고 `</ul><script>` 는 레이아웃을 깬다. 이스케이프였을 때는
   못생긴 글자로 끝났다 — `| safe` 가 그 실패를 «보기 싫음»에서 «페이지 깨짐»으로 바꾼다
   (적대 검증이 실증). 그래서 어휘와 균형을 잰다.

A translation carrying markup must reach the browser as markup — and that markup must actually
close, because `| safe` upgrades a typo from ugly text into a broken page.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("SESSION_SECRET", "0123456789abcdef0123456789abcdef")

_ROOT = Path(__file__).resolve().parents[3]
_TRANSLATIONS = _ROOT / "src" / "i18n" / "translations"
_TEMPLATES = _ROOT / "src" / "templates"

# 번역값 안의 HTML 태그. 🔴 세 언어를 **합집합**으로 본다 — 초판 계기는 ko.json 만 봐서
# en/ja 에만 태그가 있는 키를 통째로 놓쳤다.
_TAG = re.compile(r"<(strong|b|em|i|code|br|span|a|p|ul|li|div|sub|sup)\b[^>]*>", re.IGNORECASE)
_KEY_IN_CALL = re.compile(r"'([^']+)'\s*\|\s*i18n_args")

# 번역문이 쓸 수 있는 태그 — **의도적으로 좁다**. 넓히는 것은 의식적인 편집이어야 한다.
# 현재 어휘를 실측해서 정했다(strong 63 · code 9 · br 3 · a 3, 불균형 0건).
_ALLOWED_TAGS = {"strong", "code", "br", "a"}
_VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "wbr"}


def _walk(obj, prefix: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, str):
        yield prefix, obj


def _tables() -> dict[str, dict[str, str]]:
    """`{언어: {키: 값}}`."""
    return {
        path.stem: dict(_walk(json.loads(path.read_text(encoding="utf-8"))))
        for path in sorted(_TRANSLATIONS.glob("*.json"))
    }


def _locales_with_markup(tables: dict[str, dict[str, str]]) -> dict[str, set[str]]:
    """`{키: 그 키에 태그가 있는 언어들}` — 한 언어라도 있으면 담는다."""
    found: dict[str, set[str]] = {}
    for lang, table in tables.items():
        for key, text in table.items():
            if _TAG.search(text):
                found.setdefault(key, set()).add(lang)
    return found


_JINJA_BLOCK = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.DOTALL)
_SENTINEL = re.compile("\x02J(\\d+)\x03")


class _Where(HTMLParser):
    """치환된 Jinja 자리표가 **속성값**에서 나오는지 **본문 텍스트**에서 나오는지 기록한다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.position: dict[int, str] = {}

    def _mark(self, blob: str, where: str) -> None:
        for match in _SENTINEL.finditer(blob or ""):
            self.position.setdefault(int(match.group(1)), where)

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            self._mark(name, "attribute")
            self._mark(value or "", "attribute")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self._mark(data, "text")

    def handle_comment(self, data):
        self._mark(data, "comment")


def _positions(text: str) -> tuple[list[tuple[int, str]], dict[int, str]]:
    """`([(원본 오프셋, 블록 본문)], {블록 번호: 위치})`.

    🔴 블록 본문을 **치환 시점에** 들고 온다. 초판은 `{{` 위치에서 다음 `}}` 까지를 블록이라
    불렀는데, `{% if x %}` 에는 `}}` 가 없어 **뒤쪽 `{{ ... }}` 를 통째로 삼켰다** —
    자리 3개가 남의 키를 자기 것으로 보고했다(자리 목록 덤프에서 발견).

    🔴 손으로 쓴 상태기계로는 못 푼다. 초판은 따옴표 개수를, 두 번째 판은 `<`…`>` 상태를
    셌는데, `settings.html` 의 `<script>` 안 `<`·화살표 함수·주석에 걸려 **12자리를 속성으로
    건너뛰었다** — 즉 조용한 fail-open 이었다(자리 목록을 덤프해서 발견).
    그래서 Jinja 블록을 자리표로 바꾸고 **진짜 HTML 파서**에게 묻는다.

    분류 못 한 자리는 `"text"` 로 둔다 — 그래야 「못 쟀음」이 통과가 아니라 검사로 간다.
    Ask a real HTML parser; an unclassified site defaults to text so it is checked, not skipped.
    """
    offsets: list[tuple[int, str]] = []

    def _replace(match: re.Match) -> str:
        offsets.append((match.start(), match.group(0)))
        return f"\x02J{len(offsets) - 1}\x03"

    parser = _Where()
    parser.feed(_JINJA_BLOCK.sub(_replace, text))
    parser.close()
    return offsets, parser.position


class _Balance(HTMLParser):
    """열린 태그가 닫히는가 + 어떤 태그를 썼는가."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.tags: Counter = Counter()
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags[tag] += 1

    def handle_endtag(self, tag):
        if tag in _VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"여는 태그 없이 </{tag}>")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> 인데 열린 것은 <{self.stack[-1]}>")
            self.stack.pop()
        else:
            self.stack.pop()


class _Anything:
    """무엇을 물어도 답하는 자리표 — 렌더가 이름 부재로 죽지 않게 한다.

    🔴 `__html__` 을 두지 않는다. 두면 autoescape 가 이 값을 안전하다고 믿어
    **이 시험이 재려는 바로 그 축**(이스케이프 여부)이 오염된다.
    """

    def __getattr__(self, _name: str) -> "_Anything":
        return self

    def __getitem__(self, _key) -> "_Anything":
        return self

    def __iter__(self):
        return iter(())

    def __str__(self) -> str:
        return ""


def _render_env():
    """프로덕션이 쓰는 Jinja 환경 — 시험 전용 환경을 새로 만들지 않는다.

    🔴 `undefined` 를 느슨한 것으로 바꾸지 않는다. 그러면 이스케이프 동작이 다른 환경을 잰다.
    대신 그 줄이 참조하는 이름을 파싱해서 채워 넣는다.
    """
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    return importlib.import_module("src.ui._helpers").templates.env


def _render(env, source: str, locale: str) -> str:
    from jinja2 import meta  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    names = meta.find_undeclared_variables(env.parse(source))
    context = {name: _Anything() for name in names}
    context["locale"] = locale
    return env.from_string(source).render(context)


def _markup_call_sites():
    """`(파일, 줄번호, 줄, 키, 위치)` — 태그를 담은 키를 렌더하는 템플릿 자리 전부.

    한 줄에 같은 키가 두 번(속성 + 텍스트) 나오는 실제 형태가 있으므로 **자리마다** 낸다.
    """
    marked = _locales_with_markup(_tables())
    for path in sorted(_TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        offsets, position = _positions(text)
        for number, (start, block) in enumerate(offsets):
            if not block.startswith("{{"):
                continue  # `{% %}` 문·`{# #}` 주석은 값을 출력하지 않는다
            key_match = _KEY_IN_CALL.search(block)
            if key_match is None or key_match.group(1) not in marked:
                continue
            key = key_match.group(1)
            line_no = text.count("\n", 0, start) + 1
            # 렌더는 그 `{{` 가 들어 있는 **한 줄**로 한다(위치 판정만 파일 전체를 본다).
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", start)
            line = text[line_start: len(text) if line_end == -1 else line_end]
            yield path, line_no, line, key, position.get(number, "text"), marked[key]


def test_html_bearing_translations_reach_the_browser_as_markup():
    """🔴 태그를 담은 번역이 글자로 보이면 red — `| safe` 유무가 아니라 **출력**을 본다.

    🔴 **태그가 있는 언어를 전부 렌더한다.** ko 만 렌더하면 en/ja 에만 태그가 있는 키가
    조용히 통과한다 — 키는 합집합으로 모아 놓고 렌더는 한 언어만 하는, 스스로 만든 구멍이다
    (Grok claim-review `01a05a36`).
    """
    env = _render_env()
    sites = list(_markup_call_sites())
    assert sites, "태그를 담은 번역을 렌더하는 템플릿 자리를 하나도 못 찾았다 — 이 시험이 공허하다"

    rendered = 0
    escaped: list[str] = []
    unrenderable: list[str] = []
    for path, number, line, key, position, locales in sites:
        if position == "attribute":
            continue
        for locale in sorted(locales):
            try:
                out = _render(env, line.strip(), locale)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                unrenderable.append(
                    f"{path.name}:{number} {key} [{locale}] — {type(exc).__name__}: {exc}"
                )
                continue
            rendered += 1
            if "&lt;" in out:
                escaped.append(f"{path.name}:{number} {key} [{locale}]")

    assert rendered, "텍스트 위치에서 렌더된 자리가 0이다 — 이 시험이 공허하다"
    assert not unrenderable, (
        "그 줄을 단독으로 렌더하지 못했다 — 못 쟀으면 초록이 아니라 red 다:\n"
        + "\n".join(f"  {u}" for u in unrenderable)
    )
    assert not escaped, (
        "HTML 을 담은 번역이 **글자로** 렌더된다 — 운영자 화면에 `<strong>` 이 그대로 보인다.\n"
        "  텍스트 위치면 `| safe` 를 붙이고, 속성값이면 그 `{{` 를 여는 태그 안에 두어라:\n"
        + "\n".join(f"  {e}" for e in escaped)
    )


def test_markup_rendered_as_safe_is_well_formed_and_in_vocabulary():
    """🔴 `| safe` 는 **키**에 붙지 값에 붙지 않는다 — 값이 성립하는지는 따로 잰다.

    실증(적대 검증): `<strong>` 을 안 닫은 값은 `| safe` 에서 굵게가 페이지 뒤쪽으로 번지고,
    `</ul><script>` 는 리스트를 끊고 script 노드를 만든다. 이스케이프였을 때는 둘 다
    못생긴 글자로 끝났다. 이 시험이 그 승격을 CI red 로 되돌린다.
    """
    tables = _tables()
    safe_keys = {
        key
        for _path, _number, line, key, position, _locales in _markup_call_sites()
        if position == "text" and "| safe" in line
    }
    assert safe_keys, "`| safe` 로 렌더되는 마크업 키가 0개다 — 이 시험이 공허하다"

    offences: list[str] = []
    checked = 0
    for key in sorted(safe_keys):
        for lang, table in tables.items():
            value = table.get(key)
            if value is None:
                continue
            checked += 1
            balance = _Balance()
            balance.feed(value)
            balance.close()
            outside = set(balance.tags) - _ALLOWED_TAGS
            if outside:
                offences.append(f"{lang}/{key} — 허용 밖 태그 {sorted(outside)}")
            if balance.errors:
                offences.append(f"{lang}/{key} — {'; '.join(balance.errors)}")
            if balance.stack:
                offences.append(f"{lang}/{key} — 안 닫은 태그 {balance.stack}")

    assert checked, "값을 하나도 못 읽었다 — 이 시험이 공허하다"
    assert not offences, (
        "`| safe` 로 나가는 번역값이 성립하지 않는다 — 페이지가 깨진다:\n"
        f"  허용 어휘 = {sorted(_ALLOWED_TAGS)} (넓히려면 이 목록을 의식적으로 고쳐라)\n"
        + "\n".join(f"  {o}" for o in offences)
    )


def _classify(fragment: str) -> list[str]:
    """조각 안의 `{{ }}` 자리들을 순서대로 분류한다 — 정본 함수를 그대로 쓴다."""
    offsets, position = _positions(fragment)
    return [
        position.get(number, "text")
        for number, (_start, block) in enumerate(offsets)
        if block.startswith("{{")
    ]


def test_the_attribute_exception_is_real_and_not_a_blanket_pass():
    """🔴 부정 통제 — 속성 예외가 **모든 자리**를 통과시키는 문이 아님을 잰다.

    여기 있는 반례는 전부 **내 초판 판정식이 실제로 틀렸던 입력**이다:

    - 따옴표 개수 세기 판: 한 줄에 `{{` 가 둘이면 첫 번째만 봤고, 텍스트 안의 짝 없는
      따옴표에 속았다(Grok `01a05a36`).
    - `<`…`>` 상태기계 판: `<script>` 안의 `<` 에 걸려 그 뒤 **12자리를 속성으로 건너뛰었다**.
    - 블록 끝을 `}}` 로 찾던 판: `{% if %}` 가 뒤쪽 `{{ }}` 를 통째로 삼켰다.
    """
    assert _classify("<li>{{ 'a.b' | i18n_args(locale) }}</li>") == ["text"]
    assert _classify("<div data-x=\"{{ 'a.b' | i18n_args(locale) }}\"></div>") == ["attribute"]

    # 🔴 한 자리에 속성과 텍스트가 함께 — 두 번째는 텍스트다
    assert _classify(
        "<div data-x=\"{{ 'p.k' | i18n_args(locale) }}\">{{ 'a.b' | i18n_args(locale) }}</div>"
    ) == ["attribute", "text"]

    # 🔴 텍스트 안의 짝 없는 따옴표는 속성이 아니다
    assert _classify("<li>Note: \"RLS {{ 'a.b' | i18n_args(locale) }}</li>") == ["text"]

    # 🔴 앞선 `<script>` 안의 `<` 가 뒤 자리를 오염시키지 않는다
    assert _classify(
        "<script>if (a < b) { x() }</script>\n<li>{{ 'a.b' | i18n_args(locale) }}</li>"
    ) == ["text"]

    # 🔴 `{% if %}` 가 뒤따르는 `{{ }}` 를 삼키지 않는다 — 자리는 둘로 세어지고 값은 텍스트다
    assert _classify(
        "{% if flag %}<li>{{ 'a.b' | i18n_args(locale) }}</li>{% endif %}"
    ) == ["text"]
