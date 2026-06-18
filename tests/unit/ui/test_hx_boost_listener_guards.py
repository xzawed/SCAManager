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


def test_oncein_view_has_io_miss_safety_net():
    """effects.js onceInView 는 IntersectionObserver 콜백 미발동 시 화면 내 요소를 강제
    실행하는 rAF 안전망을 가져야 한다 — count-up "0" pre-fill 고착 봉인 (2026-06-18 운영 사고).

    🔴 운영 사고: setupCountUp 이 `.repo-card__score` 를 "0" pre-fill 후 onceInView
    (IntersectionObserver)로 0→점수 count-up. hx-boost swap race 로 IO 콜백이 미발동하면
    점수가 "0" 에 고착(등급은 별도 요소라 정상)된다. 안전망(rAF 2회 후 getBoundingClientRect
    로 화면 내 미발동 요소 강제 fire)으로 봉인. 런타임 검증 = e2e/test_overview_score.py
    (IntersectionObserver no-op 주입 → 안전망이 점수를 서버값으로 강제).

    effects.js onceInView must keep a rAF safety net that force-runs in-viewport elements
    when the IntersectionObserver callback never fires (count-up "0"-prefill freeze).
    e2e is not run in fast CI, so this static guard seals the regression there.
    """
    src = _read("src/static/js/effects.js")
    idx = src.find("function onceInView")
    assert idx >= 0, "onceInView 함수 부재 — 테스트 stale"
    # onceInView 함수 전체 범위 (다음 함수 선언 전까지) — scroll 안전망 포함
    # Whole onceInView function (up to the next function declaration) — includes scroll safety net
    nxt = src.find("function ", idx + 1)
    body = src[idx:nxt] if nxt > idx else src[idx:]
    # IO 콜백 ↔ 안전망 중복 실행 방지 fired 가드
    # fired guard prevents double-run between the IO callback and the safety net
    assert "fired" in body and "WeakSet" in body, "onceInView fired 중복 가드 누락"
    # rAF 안전망 + viewport 체크 (미발동 시 화면 내 강제) — getBoundingClientRect 누락 시 0 고착 회귀
    # rAF safety net + viewport check; missing getBoundingClientRect → count-up "0" freeze regression
    assert "requestAnimationFrame" in body, "onceInView rAF 안전망 누락"
    assert "getBoundingClientRect" in body, (
        "onceInView viewport 강제 안전망 누락 → IO 미발동 시 count-up '0' 고착 회귀 (2026-06-18 사고)"
    )
    # 🔴 one-shot 금지 — scroll/resize 지속 sweep 으로 below-fold 요소도 복구 (Codex P2).
    # IO 영구 미발동 + 처음 화면 밖이던 아래쪽 카드가 스크롤로 보일 때도 강제 실행해야 한다.
    # Not one-shot — keep sweeping on scroll/resize so below-fold elements recover when scrolled in.
    assert "pending" in body, "onceInView pending(미실행 요소) 추적 누락 → 지속 sweep 불가"
    assert 'addEventListener("scroll"' in body, (
        "onceInView scroll 지속 안전망 누락 → below-fold 요소 IO 영구 미발동 시 '0' 고착 (Codex P2)"
    )
    # 🔴 detached(hx-boost swap 분리) 요소 제거 — scroll/resize 리스너 자가 정리(누수 차단).
    # init() 일괄 dispose 를 제거한 뒤(Codex P1 수정) 이 isConnected 검사가 누수 방지의 단일 수단.
    # Drop detached elements so scroll/resize listeners self-clean; after removing the init() blanket
    # dispose (Codex P1 fix) this isConnected check is the sole leak-prevention mechanism.
    assert "isConnected" in body, (
        "sweep detached 제거 누락 → hx-boost swap 후 scroll/resize 리스너 누적·메모리 누수"
    )
    # 🔴 Codex P1 회귀 가드: init() 일괄 dispose 재유입 금지. effects.js 는 <body> 외부 스크립트라
    # hx-boost swap 마다 IIFE 재실행(즉시 init) + htmx:afterSettle 로 init 이 nav 당 2~3회 호출된다.
    # 직전 안전망을 dispose 하면 같은 closure 의 freshOnly(seen) 이 EMPTY 를 반환해 재등록을 막아
    # count-up 이 "0" pre-fill 에 영구 고착(below-fold). 런타임 검증 = e2e/test_overview_score.py::
    # test_overview_score_survives_double_init.
    # Codex P1 regression guard: no blanket dispose may return to init() (it tears down the prior
    # init's safety net while freshOnly(seen) blocks re-registration → count-up "0" freeze).
    assert (
        "_disposers.pop" not in src
        and "_disposers.push" not in src
        and "while (_disposers" not in src
    ), "init() 일괄 dispose 재유입 → Codex P1 count-up '0' 고착 회귀 (이중 init + freshOnly 재등록 차단)"
