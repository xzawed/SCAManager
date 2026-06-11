"""base.html KPI count-up hx-boost 핸들러 정적 가드.

`_kpiCountupHandler` 가 htmx:afterSettle + htmx:historyRestore **양쪽**에 remove-before-add 로
등록되는지 검증 — 뒤로가기(historyRestore) 시에도 count-up 재초기화 (다른 핸들러 _initReveal 등 #766 대칭).
정적 소스 검사이므로 브라우저 불필요 (hx-boost SyntaxError 클래스는 기존 e2e #605 가 커버).
Static guard: the KPI count-up handler must register on BOTH htmx:afterSettle and htmx:historyRestore
with remove-before-add (back-nav re-init symmetry). Source-level check — no browser needed.
"""
from pathlib import Path

_BASE_HTML = (
    Path(__file__).resolve().parents[3] / "src" / "templates" / "base.html"
).read_text(encoding="utf-8")


def test_kpi_countup_registers_on_both_hx_boost_events():
    # afterSettle(전진 네비) + historyRestore(뒤로가기) 양쪽 등록 의무
    # Must register on both afterSettle (forward nav) and historyRestore (back nav)
    assert "addEventListener('htmx:afterSettle', document._kpiCountupHandler)" in _BASE_HTML
    assert "addEventListener('htmx:historyRestore', document._kpiCountupHandler)" in _BASE_HTML


def test_kpi_countup_uses_remove_before_add():
    # 등록 전 remove (양쪽) — hx-boost 재방문 시 핸들러 누적 차단 (ui.md remove-before-add 규칙)
    # remove before add (both events) — prevents handler accumulation across hx-boost re-visits
    assert "removeEventListener('htmx:afterSettle', document._kpiCountupHandler)" in _BASE_HTML
    assert "removeEventListener('htmx:historyRestore', document._kpiCountupHandler)" in _BASE_HTML
