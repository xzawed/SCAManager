"""hx-boost 리스너 누적 방지 정적 가드 (#35/#36).

hx-boost listener accumulation regression guard (#35/#36).

add_repo.html 의 pagehide 리스너와 tweaks.js 의 document keydown 리스너가
remove-before-add 패턴(named handler + 선행 removeEventListener)을 유지하는지
소스 정적 스캔으로 회귀 차단. hx-boost body swap 재실행 시 익명 리스너가
window/document 에 누적되던 사고(#35/#36)를 봉인한다.

Static source scan guard: ensures the pagehide (add_repo.html) and document keydown
(tweaks.js) listeners keep the remove-before-add pattern so they do not pile up on
hx-boost body-swap re-execution.
"""
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_add_repo_pagehide_uses_remove_before_add():
    """add_repo.html pagehide 리스너는 named handler + remove-before-add (#35)."""
    src = _read("src/templates/add_repo.html")
    # named handler 저장 + 선행 removeEventListener 존재
    # Named handler storage + preceding removeEventListener present
    assert "document._addRepoPagehide" in src
    assert "removeEventListener('pagehide', document._addRepoPagehide)" in src
    assert "addEventListener('pagehide', document._addRepoPagehide)" in src
    # 익명 화살표 리스너 회귀 차단 (제거 불가 → 누적)
    # Block regression to an anonymous arrow listener (unremovable → pile-up)
    assert "addEventListener('pagehide', () =>" not in src
    assert "addEventListener('pagehide', ()=>" not in src


def test_tweaks_keydown_uses_remove_before_add():
    """tweaks.js document keydown 리스너는 named handler + remove-before-add (#36)."""
    src = _read("src/static/js/tweaks.js")
    assert "document._tweaksKeydown" in src
    assert 'removeEventListener("keydown", document._tweaksKeydown)' in src
    assert 'addEventListener("keydown", document._tweaksKeydown)' in src
    # 익명 keydown 리스너 회귀 차단
    # Block regression to an anonymous keydown listener
    assert 'addEventListener("keydown", (e) =>' not in src


def test_effects_animations_reinit_on_hx_boost():
    """effects.js 애니메이션 init 이 hx-boost 재방문 시 재실행되도록 htmx:afterSettle/
    historyRestore 에 named handler + remove-before-add 로 등록돼야 한다 (U2).

    effects.js animation init must re-run after hx-boost navigation by registering on
    htmx:afterSettle/historyRestore via a named handler with the remove-before-add pattern (U2).

    수정 전: IIFE 가 DOMContentLoaded 에만 init() 을 바인딩 → hx-boost body swap 후
    score-bar / SVG draw / count-up 애니메이션이 재실행되지 않아 opacity:0 / 0% 고착.
    Before fix: the IIFE binds init() only to DOMContentLoaded → after an hx-boost body
    swap the score-bar / SVG draw / count-up animations never re-run (opacity:0 / 0% freeze).
    """
    src = _read("src/static/js/effects.js")
    # named handler 단일 슬롯 저장 + 선행 removeEventListener (누적 방지)
    # Single-slot named handler storage + preceding removeEventListener (no accumulation)
    assert "document._fxEffectsHandler" in src
    assert 'removeEventListener("htmx:afterSettle", document._fxEffectsHandler)' in src
    assert 'removeEventListener("htmx:historyRestore", document._fxEffectsHandler)' in src
    assert 'addEventListener("htmx:afterSettle", document._fxEffectsHandler)' in src
    assert 'addEventListener("htmx:historyRestore", document._fxEffectsHandler)' in src
    # 익명 리스너 회귀 차단 (제거 불가 → 누적)
    # Block regression to an anonymous listener (unremovable → pile-up)
    assert 'addEventListener("htmx:afterSettle", function' not in src
    assert 'addEventListener("htmx:afterSettle", () =>' not in src
