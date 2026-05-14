"""HTMX vendor 파일 존재 및 base.html 통합 테스트 (RED phase — 구현 전).

RED phase tests for HTMX vendoring and base.html integration.
이 테스트 파일의 3개 테스트는 구현 완료 전까지 모두 실패(RED) 상태여야 한다.
All three tests must fail (RED) until the implementation is in place.
"""
import pathlib

# src 모듈 import 전 환경변수 주입
# Inject env vars before importing src modules
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# 프로젝트 루트 기준 절대 경로 — CI / 로컬 모두 동일하게 동작
# Absolute path anchored at project root — works on CI and local alike
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_VENDOR_DIR = _PROJECT_ROOT / "src" / "static" / "vendor"
_HTMX_FILE = _VENDOR_DIR / "htmx.min.js"
_BASE_HTML = _PROJECT_ROOT / "src" / "templates" / "base.html"


def test_htmx_vendor_file_exists():
    """src/static/vendor/htmx.min.js 파일이 존재해야 한다 (HTMX 1.9.12 vendored).

    The vendored htmx.min.js must exist so the app can serve HTMX without
    depending on an external CDN (matches the pattern used for chart.umd.min.js).
    """
    assert _HTMX_FILE.exists(), (
        f"htmx.min.js 파일이 없습니다: {_HTMX_FILE}\n"
        f"HTMX 1.9.12 배포본을 src/static/vendor/htmx.min.js 로 추가해야 합니다.\n"
        f"htmx.min.js not found at {_HTMX_FILE}. "
        f"Add the HTMX 1.9.12 dist file to src/static/vendor/htmx.min.js."
    )


def test_base_template_loads_htmx():
    """base.html 에 /static/vendor/htmx.min.js 를 로드하는 <script> 태그가 있어야 한다.

    base.html must contain a <script> tag that loads htmx.min.js from the
    vendored path so every page inheriting the base layout gets HTMX.
    """
    content = _BASE_HTML.read_text(encoding="utf-8")
    # 스크립트 src 에 vendor/htmx.min.js 경로가 포함되어야 함
    # The script src attribute must reference the vendored htmx path
    assert "vendor/htmx.min.js" in content, (
        "base.html 에 htmx.min.js 를 로드하는 <script> 태그가 없습니다.\n"
        "base.html does not contain a <script> tag loading vendor/htmx.min.js."
    )


def test_base_template_body_has_hx_boost():
    """base.html 의 <body> 태그에 hx-boost=\"true\" 속성이 있어야 한다.

    The <body> opening tag must carry hx-boost=\"true\" so that HTMX upgrades
    all same-origin anchor and form navigations to fetch-based requests,
    enabling SPA-like transitions without a full page reload.
    """
    content = _BASE_HTML.read_text(encoding="utf-8")
    # hx-boost="true" 가 body 태그 어딘가에 존재하는지 확인
    # Check that hx-boost="true" appears somewhere in the body opening tag region
    assert 'hx-boost="true"' in content, (
        'base.html 의 <body> 태그에 hx-boost="true" 속성이 없습니다.\n'
        'The <body> tag in base.html is missing the hx-boost="true" attribute.'
    )
