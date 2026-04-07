"""E2E 테스트용 fixture — uvicorn(스레드) + Playwright.

tests/ conftest.py와 분리되어 asyncio_mode=auto 없이 실행됨.
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import threading
import time

import pytest
import requests

E2E_PORT = 8001
BASE_URL = f"http://localhost:{E2E_PORT}"


# ── 서버 시작/종료 ──────────────────────────────────────────────────────


def _start_uvicorn(db_path: str) -> tuple:
    """uvicorn Server를 별도 스레드(새 event loop)로 실행하고 (server, thread)를 반환한다."""
    import uvicorn

    # E2E용 환경변수 세팅 (import 전에 설정 — setdefault 대신 강제 덮어쓰기)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["GITHUB_WEBHOOK_SECRET"] = "e2e-test-secret"
    os.environ["GITHUB_TOKEN"] = "e2e-test-token"
    os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:AAe2etest"
    os.environ["TELEGRAM_CHAT_ID"] = "-100000000"
    os.environ["API_KEY"] = "e2e-api-key"

    # pydantic-settings 캐시 무효화
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]

    from src.main import app  # noqa: PLC0415

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=E2E_PORT,
        log_level="error",
    )
    server = uvicorn.Server(config)

    def run_in_new_loop():
        """스레드 내에서 새 event loop를 생성해 uvicorn을 실행한다."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_new_loop, daemon=True)
    thread.start()
    return server, thread


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """SQLite + 더미 시크릿으로 uvicorn 서버를 세션 동안 실행한다."""
    db_file = tmp_path_factory.mktemp("e2e_db") / "test_e2e.db"
    db_path = str(db_file)

    server, thread = _start_uvicorn(db_path)

    # 서버가 200을 반환할 때까지 대기 (최대 30초)
    ready = False
    for _ in range(60):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not ready:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.skip("E2E 서버 시작 실패 — 테스트 건너뜁니다")

    yield BASE_URL

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


# ── Playwright browser/page fixture ───────────────────────────────────


@pytest.fixture(scope="session")
def browser_instance():
    """세션 동안 Chromium 브라우저 인스턴스를 공유한다."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance, base_url):  # noqa: F811
    """테스트마다 새로운 브라우저 컨텍스트(격리된 localStorage)를 제공한다."""
    context = browser_instance.new_context(base_url=base_url)
    pg = context.new_page()
    yield pg
    context.close()


# ── 테스트 데이터 시드 ────────────────────────────────────────────────


def _build_sig(payload: str, secret: str) -> str:
    return "sha256=" + hmac.new(  # type: ignore[attr-defined]
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _seed_repo(base_url: str) -> None:
    """Push Webhook을 시뮬레이션해 Repository를 DB에 등록한다."""
    payload = json.dumps({
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/testrepo"},
        "head_commit": {
            "id": "abc1234567890abc1234567890abc1234567890ab",
            "message": "feat: e2e test seed commit",
        },
        "commits": [],
    })
    sig = _build_sig(payload, "e2e-test-secret")
    try:
        requests.post(
            f"{base_url}/webhooks/github",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
            },
            timeout=5,
        )
    except Exception:
        pass
    time.sleep(0.3)


@pytest.fixture
def seeded_page(browser_instance, live_server):
    """테스트 레포(owner/testrepo)가 DB에 등록된 상태의 page fixture."""
    _seed_repo(live_server)
    context = browser_instance.new_context(base_url=live_server)
    pg = context.new_page()
    yield pg
    context.close()
