"""HTML 을 담은 번역문이 **글자가 아니라 마크업으로** 렌더된다.

## 왜 — 운영자 화면에 `<strong>` 이 글자로 보이고 있었다 (실측)

프로덕션 Jinja 환경(`src.ui._helpers.templates.env`, `autoescape=True`)으로 실제 템플릿 줄을
렌더한 결과:

    <li>&lt;strong&gt;RLS 적용&lt;/strong&gt; = PostgreSQL 만 (SQLite 단위 테스트 자동 skip)</li>

세 언어 합집합으로 HTML 태그를 담은 번역 키 49개 중 **5개**가 `| safe` 없이 렌더돼
태그가 그대로 글자였다(`admin.rls_audit.info_li1`, `admin.operations.info_li1`~`li4`).
나머지는 `| safe` 로 정상 렌더되거나 Telegram 등 다른 sink 로 간다.

🔴 이 축을 보는 가드가 없었다. `test_i18n_args_safe_contract.py` 는 **반대 방향**만 본다 —
`| safe` 에 kwargs 가 붙는 것을 막을 뿐, `| safe` 가 **빠진** 것은 보지 않는다.

## 이 파일이 강제하는 것

번역값에 HTML 태그가 있으면, 그 키를 렌더하는 템플릿 줄의 **출력에 태그가 살아 있어야** 한다.
정적으로 `| safe` 문자열을 세지 않고 **프로덕션 env 로 그 줄을 렌더해서** 본다 —
「선언」이 아니라 「도달」을 재기 위해서다.

예외는 **속성 위치** 하나뿐이다. `data-i18n-*="{{ ... }}"` 처럼 따옴표 안에서는 이스케이프가
정답이고(JS 가 읽어 다시 삽입한다), 그 자리는 사용자에게 마크업으로 보이지 않는다.

A translation carrying markup must reach the browser as markup; the only exception is an
attribute position, where escaping is correct.
"""
from __future__ import annotations

import json
import os
import re
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
# en/ja 에만 태그가 있는 키를 통째로 놓쳤다(이 세션이 이미 두 번 당한 「한쪽만 본다」).
_TAG = re.compile(r"<(strong|b|em|i|code|br|span|a|p|ul|li|div)\b[^>]*>", re.IGNORECASE)


def _walk(obj, prefix: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, str):
        yield prefix, obj


def _html_bearing_keys() -> set[str]:
    """세 언어 중 **어느 하나라도** HTML 태그를 담은 번역 키."""
    keys: set[str] = set()
    for path in sorted(_TRANSLATIONS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        keys.update(key for key, text in _walk(data) if _TAG.search(text))
    return keys


def _is_attribute_position(line: str) -> bool:
    """`{{` 가 따옴표로 열린 속성값 안에 있는가 — 그 자리는 이스케이프가 정답이다.

    앞선 큰따옴표 개수가 홀수면 속성 안이다. 줄바꿈으로 쪼갠 속성은 이 판정을 벗어나므로,
    그때는 red 가 나고 메시지가 무엇을 볼지 말한다 — 조용히 통과시키지 않는다.
    """
    head = line[: line.index("{{")]
    return head.count('"') % 2 == 1


def _render_env():
    """프로덕션이 쓰는 Jinja 환경 — 시험 전용 환경을 새로 만들지 않는다.

    🔴 `undefined` 를 느슨한 것으로 바꾸지 않는다. 그러면 이스케이프 동작이 다른 환경을 재게 된다.
    대신 그 줄이 참조하는 이름을 파싱해서 **채워 넣는다**(아래 `_context_for`).
    """
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    return importlib.import_module("src.ui._helpers").templates.env


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


def _context_for(env, source: str) -> dict:
    """그 줄이 참조하는 이름을 파싱해 자리표로 채운다 — `locale` 만 실제 값."""
    from jinja2 import meta  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    names = meta.find_undeclared_variables(env.parse(source))
    context = {name: _Anything() for name in names}
    context["locale"] = "ko"
    return context


def test_html_bearing_translations_reach_the_browser_as_markup():
    """🔴 태그를 담은 번역이 글자로 보이면 red — `| safe` 유무가 아니라 **출력**을 본다."""
    keys = _html_bearing_keys()
    assert keys, "HTML 을 담은 번역 키를 하나도 못 찾았다 — 이 시험이 공허하다"

    env = _render_env()
    examined = 0
    escaped: list[str] = []
    unrenderable: list[str] = []
    for path in sorted(_TEMPLATES.rglob("*.html")):
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if "{{" not in line:
                continue
            key = next((k for k in keys if f"'{k}'" in line or f'"{k}"' in line), None)
            if key is None:
                continue
            examined += 1
            if _is_attribute_position(line):
                continue
            source = line.strip()
            try:
                out = env.from_string(source).render(_context_for(env, source))
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                unrenderable.append(f"{path.name}:{number} {key} — {type(exc).__name__}: {exc}")
                continue
            if "&lt;" in out:
                escaped.append(f"{path.name}:{number} {key}")

    assert examined, "HTML 번역을 렌더하는 템플릿 줄을 하나도 못 찾았다 — 이 시험이 공허하다"
    assert not unrenderable, (
        "그 줄을 단독으로 렌더하지 못했다 — 못 쟀으면 초록이 아니라 red 다:\n"
        + "\n".join(f"  {u}" for u in unrenderable)
    )
    assert not escaped, (
        "HTML 을 담은 번역이 **글자로** 렌더된다 — 운영자 화면에 `<strong>` 이 그대로 보인다.\n"
        "  텍스트 위치면 `| safe` 를 붙이고, 속성값이면 그 `{{` 를 같은 줄의 따옴표 안에 두어라:\n"
        + "\n".join(f"  {e}" for e in escaped)
    )


def test_the_attribute_exception_is_real_and_not_a_blanket_pass():
    """🔴 부정 통제 — 속성 예외가 **모든 줄**을 통과시키는 문이 아님을 잰다.

    `_is_attribute_position` 이 항상 True 를 주면 위 시험은 공허해진다. 텍스트 위치의 대표
    형태(`<li>{{ ... }}</li>`)가 예외로 새지 않는지 직접 본다.
    """
    assert not _is_attribute_position("      <li>{{ 'a.b' | i18n_args(locale) }}</li>")
    assert _is_attribute_position('  <div data-x="{{ \'a.b\' | i18n_args(locale) }}">')
    # 닫힌 속성 뒤의 텍스트 위치도 텍스트다 (따옴표 2개 = 짝수)
    assert not _is_attribute_position('  <div class="c">{{ \'a.b\' | i18n_args(locale) }}')
