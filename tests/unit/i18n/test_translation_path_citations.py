"""번역 문자열이 인용한 **리포 경로가 실재한다** — 그리고 세 언어가 같은 곳을 가리킨다.

## 왜 — 사용자 화면에 죽은 문서 경로가 6건 렌더되고 있었다 (실측)

    admin.rls_audit.info_li5   docs/runbooks/saas-phase0-backfill-readiness.md   없음
    admin.operations.info_li5  docs/_archive/runbooks/sentry-activation.md       없음

둘 다 `src/templates/admin_rls_audit.html` · `admin_operations.html` 의 `<li>` 로
**운영자에게 그대로 보인다.** 두 키 × 3언어 = 6건.

🔴 어떤 가드도 이 표면을 보지 않았다. `check_doc_anchors.py` 는 `docs/**` 안의 앵커만 걷고,
i18n 시험은 키 존재·HTML 안전성만 본다. 문서 감사에서 「죽은 경로」를 셀 때도 `*.md` 소스만
훑어서 JSON 은 집계 밖이었다.

## 무엇을 강제하나

1. 번역이 인용한 경로가 디스크에 있다.
2. **같은 키는 세 언어가 같은 경로를 인용한다** — 한 언어만 고치는 표류가 이 결함을 2건이
   아니라 6건으로 만들었다. 개수를 세지 않고 언어 간 **집합**을 대조한다.

A dead path rendered to the operator is a lie with a UI; fixing one language leaves the drift.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_TRANSLATIONS = _ROOT / "src" / "i18n" / "translations"

# 백틱 안의 리포 경로 — 확장자가 있는 것만. 디렉토리·플레이스홀더는 대상이 아니다.
_CITATION = re.compile(
    r"`((?:docs|src|scripts|tests|e2e|alembic|\.github|\.claude)/[^`\s]+\.[A-Za-z0-9]+)`"
)


def _walk(obj, prefix: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, str):
        yield prefix, obj


def _citations() -> dict[str, dict[str, set[str]]]:
    """`{키: {언어: {인용 경로}}}` — 인용이 하나라도 있는 키만, 단 **빈 언어도 담는다**.

    🔴 인용이 있는 언어만 담으면 「ko 만 경로를 인용하고 en·ja 는 아무것도 안 함」이
    비교 대상 1개가 되어 표류로 안 잡힌다(실측 M1: 실재 red · 표류 green). 그게 바로
    한쪽만 고친 모양이다 — 빈 집합도 한 표로 센다.
    An absent citation is a citation set of its own; excluding it hides the one-sided fix.
    """
    per_key: dict[str, dict[str, set[str]]] = {}
    for path in sorted(_TRANSLATIONS.glob("*.json")):
        lang = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, text in _walk(data):
            per_key.setdefault(key, {})[lang] = set(_CITATION.findall(text))
    return {k: v for k, v in per_key.items() if any(v.values())}


def test_every_cited_repo_path_exists():
    """🔴 운영자 화면에 렌더되는 인용 경로가 실재한다."""
    cited = _citations()
    assert cited, (
        "번역에서 리포 경로 인용을 하나도 못 찾았다 — 정규식이 표기 변경에 늙었거나 "
        "번역 파일을 못 읽었다. 이 상태의 초록은 '없음'이지 '괜찮음'이 아니다."
    )
    dead = sorted(
        (key, lang, path)
        for key, per_lang in cited.items()
        for lang, paths in per_lang.items()
        for path in paths
        if not (_ROOT / path).exists()
    )
    assert not dead, (
        "번역이 없는 파일을 인용한다 — 사용자에게 그대로 보인다:\n"
        + "\n".join(f"  {lang}.json  {key}  ->  {path}" for key, lang, path in dead)
    )


def test_the_three_languages_cite_the_same_paths():
    """🔴 한 언어만 고치면 나머지가 늙는다 — 그 표류가 2건을 6건으로 만들었다.

    개수가 아니라 **집합**을 대조한다. 그 키를 가진 언어들끼리만 보므로 언어를 늘려도,
    세 언어에서 인용을 함께 지워도 부당하게 red 가 되지 않는다.
    """
    drift = {
        key: {lang: sorted(paths) for lang, paths in per_lang.items()}
        for key, per_lang in _citations().items()
        if len({frozenset(paths) for paths in per_lang.values()}) > 1
    }
    assert not drift, (
        "같은 키인데 언어마다 다른 경로를 인용한다 — 한쪽만 고친 흔적이다:\n"
        + json.dumps(drift, ensure_ascii=False, indent=2)
    )
