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

# E2E 테스트용 고정 사용자 ID
# Fixed user ID for E2E tests.
_E2E_USER_ID = 1


def _get_alembic_head() -> str:
    """alembic/versions/ 디렉토리에서 head revision 자동 추출.

    모든 revision 중 down_revision 으로 참조되지 않는 것이 head. 선형 DAG 가정.
    분기 상태(head 가 여러 개)면 즉시 실패해 DAG 오류를 조기 포착한다.
    """
    import re
    versions_dir = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions"
    )
    revisions: set[str] = set()
    down_revisions: set[str] = set()
    rev_re = re.compile(r"^revision\s*(?::\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
    down_re = re.compile(r"^down_revision\s*(?::[^=]*)?=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
    for fname in os.listdir(versions_dir):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        with open(os.path.join(versions_dir, fname), encoding="utf-8") as f:
            text = f.read()
        m = rev_re.search(text)
        if m:
            revisions.add(m.group(1))
        m = down_re.search(text)
        if m:
            down_revisions.add(m.group(1))
    heads = revisions - down_revisions
    if len(heads) != 1:
        raise RuntimeError(
            f"Expected single alembic head, got {sorted(heads)}. Check migration DAG."
        )
    return heads.pop()


# Alembic head revision — E2E DB 스탬핑용 (DAG 파싱 자동 추출 → 신규 마이그레이션 자동 반영)
_ALEMBIC_HEAD = _get_alembic_head()


# ── E2E DB 스키마 직접 생성 (Alembic SQLite 호환 문제 우회) ──────────────


def _setup_e2e_db(db_path: str) -> None:
    """SQLite E2E DB에 ORM 스키마를 직접 생성하고 alembic_version을 head로 스탬핑한다.

    Alembic 0009/0010 마이그레이션이 SQLite에서 NotImplementedError를 발생시키므로
    Base.metadata.create_all()로 스키마를 생성한 뒤 버전만 수동 삽입한다.
    """
    from sqlalchemy import create_engine, text
    from src.database import Base
    import src.models.repository  # noqa: F401
    import src.models.analysis    # noqa: F401
    import src.models.repo_config  # noqa: F401
    import src.models.gate_decision  # noqa: F401
    import src.models.user  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": _ALEMBIC_HEAD})
        conn.commit()
    engine.dispose()


# ── 서버 시작/종료 ──────────────────────────────────────────────────────
# ── Server start/stop ──────────────────────────────────────────────────────


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
    os.environ["GITHUB_CLIENT_ID"] = "e2e-github-client-id"
    os.environ["GITHUB_CLIENT_SECRET"] = "e2e-github-client-secret"
    os.environ["SESSION_SECRET"] = "e2e-session-secret-32chars-long!!"

    # pydantic-settings 캐시 무효화
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]

    from src.main import app  # noqa: PLC0415
    from src.auth.session import require_login, CurrentUser  # noqa: PLC0415

    # E2E용 테스트 사용자 — require_login 의존성 우회 (CurrentUser dataclass 사용)
    _e2e_user = CurrentUser(
        id=_E2E_USER_ID,
        github_login="e2e-tester",
        email="e2e@test.com",
        display_name="E2E Test User",
        plaintext_token="gho_e2e_test_token",
    )
    app.dependency_overrides[require_login] = lambda: _e2e_user

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

    # Alembic SQLite 호환 문제 우회 — 스키마 직접 생성 후 버전 스탬핑
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["GITHUB_WEBHOOK_SECRET"] = "e2e-test-secret"
    os.environ["GITHUB_TOKEN"] = "e2e-test-token"
    os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:AAe2etest"
    os.environ["TELEGRAM_CHAT_ID"] = "-100000000"
    os.environ["API_KEY"] = "e2e-api-key"
    os.environ["GITHUB_CLIENT_ID"] = "e2e-github-client-id"
    os.environ["GITHUB_CLIENT_SECRET"] = "e2e-github-client-secret"
    os.environ["SESSION_SECRET"] = "e2e-session-secret-32chars-long!!"
    _setup_e2e_db(db_path)

    server, thread = _start_uvicorn(db_path)

    # 서버가 200을 반환할 때까지 대기 (최대 30초)
    # Wait until the server returns 200 (up to 30 seconds).
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

    # E2E 테스트용 User를 DB에 직접 삽입
    _seed_user(db_path)

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
# ── Test data seeding ────────────────────────────────────────────────────


def _build_sig(payload: str, secret: str) -> str:
    return "sha256=" + hmac.new(  # type: ignore[attr-defined]
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _seed_user(db_path: str) -> None:
    """E2E 테스트용 User를 DB에 직접 삽입한다."""
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT OR IGNORE INTO users
                (id, github_id, github_login, github_access_token, email, display_name, created_at)
            VALUES
                (:id, :gid, :login, :token, :email, :name, datetime('now'))
        """), {
            "id": _E2E_USER_ID,
            "gid": "e2e-test-user-12345",
            "login": "e2e-tester",
            "token": "gho_e2e_test_token",
            "email": "e2e@test.com",
            "name": "E2E Test User",
        })
        conn.commit()
    engine.dispose()


def _seed_repo(base_url: str, db_path: str) -> None:
    """Push Webhook을 시뮬레이션해 Repository를 DB에 등록하고, E2E 사용자에게 소유권을 부여한다."""
    payload = json.dumps({
        "ref": "refs/heads/main",
        "after": "abc1234567890abc1234567890abc1234567890ab",
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

    # Webhook으로 생성된 repo의 user_id를 E2E 테스트 사용자로 업데이트
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE repositories SET user_id=:uid WHERE full_name=:fn"
        ), {"uid": _E2E_USER_ID, "fn": "owner/testrepo"})
        conn.commit()
    engine.dispose()


@pytest.fixture
def seeded_page(browser_instance, live_server, tmp_path_factory):
    """테스트 레포(owner/testrepo)가 DB에 등록된 상태의 page fixture."""
    # db_path를 tmp_path_factory에서 재구성하는 대신, live_server fixture에서 전달받은 경로 활용
    # live_server가 세션 scope이므로 DB 경로를 세션 레벨에서 공유해야 함
    # 간단히: 같은 tmpdir 패턴으로 추정하는 대신, 환경변수에서 읽음
    # Simplified: read from the environment variable instead of guessing the tmpdir pattern.
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    context = browser_instance.new_context(base_url=live_server)
    pg = context.new_page()
    yield pg
    context.close()
