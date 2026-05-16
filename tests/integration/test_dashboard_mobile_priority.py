"""dashboard 모바일 KPI 우선순위 재배치 회귀 가드 (Cycle 81 PR-B).

5+1 cross-verify (관점 🅑) PR-B 의무:
- 모바일 480px↓ first-fold 우선순위 = 보안 HIGH + 자동 머지 (사용자 가치 ↑)
- 데스크탑 HTML 순서 보존 (CSS order 만 모바일 분기)
- 운영 위험 신호 (보안 HIGH) + PR 결과 (자동 머지) 우선 인지

Cycle 81 PR-A fix-up 학습 (TestClient lifespan 비활성):
- `c = TestClient(app)` 직접 (lifespan 진입 X — 후속 unit test 영향 차단)
- `/login` route 응답 검증 (DB/lifespan 무관)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


def test_dashboard_html_includes_mobile_order_css():
    """dashboard.html 응답에 모바일 KPI order CSS 포함.

    /login 페이지 = base.html 상속 but dashboard CSS 미포함 — dashboard 페이지 직접 검증
    필요. 단 require_login 의무 = 비로그인 시 302 → CSS 직접 검증 불가.
    대신 dashboard.html 정적 파일 본문 직접 검증 (templates 영역).
    """
    # dashboard.html 본문 직접 read (templates 정적 자원)
    from pathlib import Path
    dashboard_html = Path(__file__).resolve().parents[2] / "src" / "templates" / "dashboard.html"
    content = dashboard_html.read_text(encoding='utf-8')

    # 모바일 480px↓ 분기 안 order CSS 포함 검증
    assert "@media (max-width: 480px)" in content
    # CSS order 5건 (1~5) 모두 포함
    for order_n in range(1, 6):
        assert f"order: {order_n};" in content, f"CSS order: {order_n} 누락"


def test_dashboard_html_security_kpi_first_in_mobile_order():
    """모바일 first-fold = 보안 HIGH (3rd HTML child) → order: 1 의무."""
    from pathlib import Path
    dashboard_html = Path(__file__).resolve().parents[2] / "src" / "templates" / "dashboard.html"
    content = dashboard_html.read_text(encoding='utf-8')
    # nth-child(3) = 보안 HIGH (HTML 순서) — order: 1 (모바일 first)
    assert ".dash-kpi:nth-child(3) { order: 1;" in content, \
        "모바일 보안 HIGH first-fold 우선순위 누락"


def test_dashboard_html_auto_merge_kpi_second_in_mobile_order():
    """모바일 second = 자동 머지 (5th HTML child) → order: 2 의무."""
    from pathlib import Path
    dashboard_html = Path(__file__).resolve().parents[2] / "src" / "templates" / "dashboard.html"
    content = dashboard_html.read_text(encoding='utf-8')
    # nth-child(5) = 자동 머지 (HTML 순서) — order: 2 (모바일 second)
    assert ".dash-kpi:nth-child(5) { order: 2;" in content, \
        "모바일 자동 머지 second-fold 우선순위 누락"


def test_dashboard_html_desktop_order_preserved():
    """데스크탑 = HTML 순서 보존 (CSS order 비활성).

    데스크탑 = 5 컬럼 grid + nth-child order 무관 (HTML 순서 표시).
    모바일 480px↓ 분기 안에만 order 적용 = 데스크탑 영향 0.
    """
    from pathlib import Path
    dashboard_html = Path(__file__).resolve().parents[2] / "src" / "templates" / "dashboard.html"
    content = dashboard_html.read_text(encoding='utf-8')
    # order CSS 가 모바일 분기 안에만 위치 검증 (전역 X)
    # 단순 검증 = order CSS 직전 line 에 480px media query 포함
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if ".dash-kpi:nth-child" in line and "order:" in line:
            # 전 5 line 안 480px media query 포함 의무
            preceding = "\n".join(lines[max(0, i-15):i])
            assert "max-width: 480px" in preceding, \
                f"order CSS 가 모바일 분기 외부에 있음 — line {i}: {line.strip()}"


def test_dashboard_html_login_response_includes_pwa_headers():
    """기존 PR-A 회귀 가드 — /login = base.html PWA 헤더 보존."""
    c = TestClient(app)
    response = c.get("/login")
    assert response.status_code == 200
    # PR-A PWA 헤더 = PR-B 무관 = 회귀 0 검증
    assert '<link rel="manifest" href="/static/manifest.json">' in response.text
    assert 'theme-color' in response.text
