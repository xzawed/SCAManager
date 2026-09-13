"""E2E 테스트용 fixture — uvicorn(스레드) + Playwright.

tests/ conftest.py와 분리되어 asyncio_mode=auto 없이 실행됨.
"""
import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

E2E_PORT = 8001
# 서버 기동 대기 상한(초) — 초과 시 **실패**(skip 아님, R58)
# Server startup budget; exceeding it fails the suite rather than skipping it.
_STARTUP_TIMEOUT = 30
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
    import importlib
    import pkgutil

    from sqlalchemy import create_engine, text
    from src.database import Base
    import src.models as _models_pkg

    # 모든 ORM 모델을 자동 import — Base.metadata.tables 에 등록되어야 create_all 이 모든 테이블 생성
    # Auto-import every ORM model so Base.metadata.tables is fully populated before create_all
    # (Phase 1 PR — overview 페이지가 analysis_feedback_repo 사용, 신규 모델 추가 시 누락 방지)
    for _, _name, _ in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"src.models.{_name}")

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
    # 🔴 `/admin/*` 3화면은 `require_admin` 이 `SAAS_ADMIN_EMAILS` 를 보고 막는다.
    #    의존성을 override 하지 «않고» 설정으로 연다 — 실제 인가 경로를 그대로 탄다.
    #    이걸 안 하면 admin 화면은 e2e 로 도달 불가라 영영 검증되지 않는다.
    #    Opens /admin/* through the real authorization path instead of stubbing it.
    os.environ["SAAS_ADMIN_EMAILS"] = "e2e@test.com"
    # 🔴 **개발 PC 의 `.env` 가 e2e 로 새어 들어온다.** `build_settings()` 는 `.env` 를 읽고,
    #    위 목록에 없는 자격증명은 그대로 살아 있다 — 실측(2026-09-12): 이 PC 의 `.env` 에
    #    **진짜 `ANTHROPIC_API_KEY`** 가 있어 `?mode=insight`·`/repos/<repo>/insights` 가
    #    로컬 e2e 에서 **실제 API 를 호출**하고 있었다(CI 는 `.env` 가 없어 조용했다).
    #    자격증명은 «전부» CI 와 같은 값(기본값 `""`)으로 못박는다 — 목록을 손으로 지키지
    #    않도록 `tests/unit/scripts/test_e2e_harness_neutralises_credentials.py` 가
    #    `Settings` 에서 파생해 강제한다.
    # A developer .env leaks into e2e: pin every credential to its CI-equivalent value.
    for _cred in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TELEGRAM_WEBHOOK_SECRET",
                  "INTERNAL_CRON_API_KEY", "TOKEN_ENCRYPTION_KEY", "N8N_WEBHOOK_SECRET"):
        os.environ[_cred] = ""
    # 🔴 벨트+멜빵 — 키가 어떤 경로로든 살아나도 호출이 **기계 밖으로 나가지 않는다**.
    #    `anthropic` SDK 는 `base_url` 미지정 시 이 env 를 읽는다(1.3.0 실측, Grok `01a095b6`).
    os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:1"

    # pydantic-settings 캐시 무효화
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]

    from src.main import app  # noqa: PLC0415
    from src.auth.session import require_login, get_current_user, CurrentUser  # noqa: PLC0415

    # E2E용 테스트 사용자 — require_login + get_current_user 의존성 우회
    # require_login: 인증 필수 라우트 / get_current_user: overview 등 공개 라우트의 optional 인증
    # Override both: require_login (mandatory auth) + get_current_user (optional auth, public routes)
    # This ensures current_user is set in ALL templates including overview, so nav links render.
    _e2e_user = CurrentUser(
        id=_E2E_USER_ID,
        github_login="e2e-tester",
        email="e2e@test.com",
        display_name="E2E Test User",
        plaintext_token="gho_e2e_test_token",
    )
    app.dependency_overrides[require_login] = lambda: _e2e_user
    app.dependency_overrides[get_current_user] = lambda: _e2e_user

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
    # 🔴 `/admin/*` 3화면은 `require_admin` 이 `SAAS_ADMIN_EMAILS` 를 보고 막는다.
    #    의존성을 override 하지 «않고» 설정으로 연다 — 실제 인가 경로를 그대로 탄다.
    #    이걸 안 하면 admin 화면은 e2e 로 도달 불가라 영영 검증되지 않는다.
    #    Opens /admin/* through the real authorization path instead of stubbing it.
    os.environ["SAAS_ADMIN_EMAILS"] = "e2e@test.com"
    _setup_e2e_db(db_path)

    server, thread = _start_uvicorn(db_path)

    # 서버가 200을 반환할 때까지 대기 (최대 30초)
    # Wait until the server returns 200 (up to 30 seconds).
    ready = False
    # 🔴 마지막 실패 이유를 남긴다 — 없으면 "응답하지 않았다" 만 알고 **왜인지는 모른다**
    # (연결 거부인지 500 인지 타임아웃인지). R58 이 skip 을 실패로 바꾼 목적은 실패를
    # **읽을 수 있게** 하는 것이므로, 이유를 버리면 절반만 이행한 것이다.
    # Keep the last failure so the error can say *why* the server never came up.
    last_error: str = "(시도 기록 없음)"
    for _ in range(60):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                ready = True
                break
            last_error = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            # 아직 안 떴을 뿐이다 — 폴링 중 예외는 정상이라 재시도한다.
            # Not up yet; polling exceptions are expected, so retry.
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)

    if not ready:
        server.should_exit = True
        thread.join(timeout=5)
        # 🔴 **skip 이 아니라 실패다** (2026-08-06 회고 P1 · backlog R58).
        # `pytest.skip` 은 성공으로 집계돼 **121건 전건 skip 후 job exit 0** 이 된다 —
        # 앱이 부팅조차 못 해도 CI 가 초록이고 배지도 초록이다(뮤테이션 실측).
        # 검사 범위가 0 이 된 상태 위의 초록은 fail-open 이며, 이 리포는 같은 창에서
        # lint-js·의존성 핀·이력 절 3 표면에 이미 '범위 비면 fail' 을 적용해 두고
        # **자기가 방금 초록으로 만든 e2e 에만** 적용하지 않았다.
        # A skip counts as success: the whole suite would pass with the app dead.
        raise RuntimeError(
            f"E2E 서버가 {_STARTUP_TIMEOUT}초 안에 {BASE_URL}/health 에 응답하지 않았다 "
            f"(마지막 시도: {last_error}) — "
            "스위트를 skip 하지 않고 실패시킨다(전건 skip 후 exit 0 = 공허한 초록)."
        )

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
def anonymous_page(page, live_server):  # noqa: F811
    """비로그인 방문자 시점 — `get_current_user` override 를 이 테스트 동안만 해제한다.

    🔴 왜 필요한가: 이 conftest 는 `get_current_user` 를 전역 override 해서 **모든 요청이
    로그인 상태**다. 그래서 `/` 는 항상 대시보드를 렌더하고 **랜딩(비로그인) 페이지는
    e2e 로 도달 불가**였다 — 미로그인 UI 는 원리적으로 미검증 영역이었다(R52 완전성 비평).
    `require_login` override 는 그대로 두므로 인증 필수 라우트는 영향받지 않는다.

    Temporarily drops the global `get_current_user` override so `/` renders the landing
    (unauthenticated) page. Without this the landing UI is unreachable from e2e.

    ⚠️ 앱 전역 상태를 건드리므로 **테스트 병렬 실행과 양립하지 않는다**(현재 스위트는 순차).
    """
    from src.auth.session import get_current_user  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield page
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


@pytest.fixture
def page(browser_instance, base_url):  # noqa: F811
    """테스트마다 새로운 브라우저 컨텍스트(격리된 localStorage)를 제공한다.
    JS 런타임 에러(uncaught exception)를 테스트 실패로 자동 전환한다 (hx-boost SyntaxError 감지용).
    Each test gets a fresh browser context. Uncaught JS exceptions fail the test automatically.
    """
    context = browser_instance.new_context(base_url=base_url)
    pg = context.new_page()
    js_errors: list[str] = []
    pg.on("pageerror", lambda err: js_errors.append(str(err)))
    yield pg
    context.close()
    if js_errors:
        pytest.fail(
            f"JS 런타임 에러 감지 ({len(js_errors)}건) — hx-boost script 재실행 오류 의심:\n"
            + "\n".join(js_errors)
        )


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
    """테스트 레포(owner/testrepo)가 DB에 등록된 상태의 page fixture.
    JS 런타임 에러(uncaught exception)를 테스트 실패로 자동 전환한다.
    Page fixture with owner/testrepo seeded in DB. Uncaught JS exceptions fail the test.
    """
    # db_path를 tmp_path_factory에서 재구성하는 대신, live_server fixture에서 전달받은 경로 활용
    # live_server가 세션 scope이므로 DB 경로를 세션 레벨에서 공유해야 함
    # 간단히: 같은 tmpdir 패턴으로 추정하는 대신, 환경변수에서 읽음
    # Simplified: read from the environment variable instead of guessing the tmpdir pattern.
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    context = browser_instance.new_context(base_url=live_server)
    pg = context.new_page()
    js_errors: list[str] = []
    pg.on("pageerror", lambda err: js_errors.append(str(err)))
    yield pg
    context.close()
    if js_errors:
        pytest.fail(
            f"JS 런타임 에러 감지 ({len(js_errors)}건) — hx-boost script 재실행 오류 의심:\n"
            + "\n".join(js_errors)
        )


def _seed_analysis(db_path: str) -> int:
    """owner/testrepo Analysis 레코드를 DB에 삽입하고 ID를 반환한다.
    Insert an Analysis record for owner/testrepo and return its ID.
    """
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()
        if row is None:
            raise RuntimeError("_seed_repo must be called before _seed_analysis")
        repo_id = row[0]
        # 🔴 `score_unreliable` 을 판정 함수에서 낸다 (0046). 원시 SQL 은 ORM 을 거치지 않고
        #    컬럼 기본값이 **true(신뢰 불가·fail-closed)** 라, 빠뜨리면 이 행이 집계에서
        #    제외돼 대시보드·overview 가 빈 값을 그린다(실측: overview e2e 5건이 그렇게 깨졌다).
        from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415

        # 🔴 «빈» 결과를 시드하면 화면의 절반이 관측에서 사라진다. 정적 이슈 목록
        #    (`#tabStatic`)과 이슈 등록 모달의 «트리거» 는 `result["issues"]` 가 있어야
        #    존재한다 — 도달성이 아니라 데이터 문제였다(#1639 W12).
        #    `src/ui/routes/detail.py::annotate_issue_keys` 가 이 두 키를 읽어
        #    `issue_key` 를 얹고, 템플릿이 `panel.dataset.staticIssues` 로 넘긴다.
        # 🔴 이 시드는 «기준선을 옮긴다» — 알고 쓴다.
        #    `category="security"` + `severity="error"` 조합은
        #    `src/services/dashboard_service.py::_count_high_security` 에 걸려
        #    HIGH 보안 KPI 를 0 → 1 로 만들고, 그 값이
        #    `src/api/repo_report.py` 의 `warning` 플래그(`... or kpi["high_security_count"] > 0`)
        #    를 True 로 뒤집는다. `repo_category_breakdown` 도 0 이 아니게 된다.
        #    처음엔 「집계에 영향 없다」고 적었는데 그것은 **틀렸다** — `score_is_unreliable`
        #    만 보고 이슈를 «세는» 경로 열 곳을 놓쳤다(Grok `01a08f23` 이 BROKEN 판정).
        #
        #    그럼에도 남기는 이유: 그 플립이 여는 `warning` 분기에서 **진짜 결함**이 나왔다
        #    (`.repos-warning-link` 93x21, SC 2.5.8 미달 — 같은 PR 에서 고쳤다).
        #    감사의 목적은 더 많은 상태를 여는 것이고, 닫아 두면 그 면은 영영 관측 밖이다.
        #    🔴 따라서 e2e 에서 HIGH 보안 KPI 와 repos 경고 목록은 «시드가 만든 값» 이다 —
        #       그 숫자를 0 으로 고정하는 시험을 새로 쓰지 말 것.
        # This seed deliberately moves two aggregates (HIGH-security KPI, report warning flag);
        # that flip is what exposed the 21px warning link. Do not pin those numbers to zero.
        seed_result = {
            "summary": "e2e perf test",
            "issues": [
                {"tool": "bandit", "category": "security",
                 "message": "hardcoded password string", "file": "src/app.py",
                 "severity": "error", "line": 12},
                {"tool": "ruff", "category": "code_quality",
                 "message": "unused import os", "file": "src/util.py",
                 "severity": "warning", "line": 3},
            ],
            "ai_suggestions": [
                "입력값 검증을 추가하세요 / add input validation",
            ],
        }
        conn.execute(text("""
            INSERT OR IGNORE INTO analyses
                (repo_id, commit_sha, commit_message, score, grade, result, author_login,
                 score_unreliable, created_at)
            VALUES
                (:rid, 'perf-test-sha-001', 'perf: seed analysis for E2E',
                 85, 'B', :res, 'e2e-tester', :unrel, datetime('now'))
        """), {"rid": repo_id, "res": json.dumps(seed_result),
               "unrel": score_is_unreliable(seed_result)})
        conn.commit()
        analysis_row = conn.execute(text(
            "SELECT id FROM analyses WHERE repo_id=:rid AND commit_sha='perf-test-sha-001'"
        ), {"rid": repo_id}).fetchone()
        if analysis_row is None:
            raise RuntimeError("_seed_analysis: INSERT succeeded but row not found")
    engine.dispose()
    return analysis_row[0]


def _seed_graded_analyses(db_path: str) -> dict[str, int]:
    """등급 A~F 를 하나씩 만든다 → {등급: analysis_id}.

    🔴 `analysis_detail.html` 은 `score-bar--{{ grade | lower }}` 로 클래스 «이름» 을
       조립한다. 어떤 변종이 칠해지는지는 데이터가 정하므로, 등급 하나만 시드하면
       나머지 네 변종은 브라우저에서 **한 번도 렌더되지 않는다** — `{% if %}` 가 아니라서
       분기 커버리지도 못 보는 축이다(#1639 W12-b).
    Seed one analysis per grade: the score-bar variant class is interpolated from data,
    so a single-grade seed leaves four variants unrendered and unmeasurable.
    """
    from sqlalchemy import create_engine, text

    from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    ids: dict[str, int] = {}
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()
        if row is None:
            raise RuntimeError("_seed_repo must run before _seed_graded_analyses")
        repo_id = row[0]
        result = {"summary": "e2e grade seed"}
        unrel = score_is_unreliable(result)
        for grade, score in (("A", 95), ("B", 82), ("C", 68), ("D", 52), ("F", 30)):
            sha = f"grade-seed-{grade.lower()}"
            conn.execute(text("""
                INSERT OR IGNORE INTO analyses
                    (repo_id, commit_sha, commit_message, score, grade, result,
                     author_login, score_unreliable, created_at)
                VALUES
                    (:rid, :sha, 'feat: grade seed', :score, :grade, :res,
                     'e2e-tester', :unrel, datetime('now'))
            """), {"rid": repo_id, "sha": sha, "score": score, "grade": grade,
                   "res": json.dumps(result), "unrel": unrel})
        conn.commit()
        for grade in ("A", "B", "C", "D", "F"):
            got = conn.execute(text(
                "SELECT id FROM analyses WHERE repo_id=:rid AND commit_sha=:sha"
            ), {"rid": repo_id, "sha": f"grade-seed-{grade.lower()}"}).fetchone()
            if got is None:
                raise RuntimeError(f"_seed_graded_analyses: {grade} row not found")
            ids[grade] = got[0]
    engine.dispose()
    assert len(ids) == 5, f"등급 시드 {len(ids)}건 — 다섯이어야 한다"
    return ids


# 🔴 기본 설정에서 «숨는» 게이트 블록 — 네 곳이 `is-hidden` 으로 렌더된다
#    (`settings.html` 의 `{% if not config.auto_merge %}is-hidden{% endif %}` 등).
#    기본값이 `auto_merge=False`·`approve_mode="disabled"`(`src/models/repo_config.py`)라
#    그 안의 컨트롤(임계값 슬라이더·숫자 입력·토글)은 감사에 **한 번도 보인 적이 없다**.
#    공유 리포의 설정을 바꾸면 다른 시험의 전제가 흔들리므로 «두 번째 리포» 를 둔다.
# Gate blocks hidden under the default config; seed a second repo so both states are swept.
GATED_REPO = "owner/gatedrepo"

# 🔴 «소유자 미등록» 리포 — 웹훅이 만들었지만 아무도 `/repos/add` 로 청구하지 않은 상태.
#    `settings.py:243` 의 `repo_is_claimed = repo.user_id is not None` 이 False 가 되고
#    그 한 플래그가 설정 화면의 팔 셋을 동시에 뒤집는다(자격증명 가림 · 안내 힌트 ·
#    저장 버튼 숨김). e2e 의 두 리포는 전부 청구돼 있어 이 상태는 한 번도 렌더된 적이 없다.
# An unclaimed repo (webhook-created, never claimed): one flag flips three settings arms.
UNCLAIMED_REPO = "owner/unclaimedrepo"


def _seed_gated_repo(db_path: str) -> str:
    """게이트 블록이 «열린» 설정의 리포를 만든다 → full_name.

    🔴 원시 SQL 로 넣지 않는다. `RepoConfig` 의 기본값은 SQLAlchemy 의 **파이썬 측**
       `default=` 라 DB 에는 기본값이 없다 — `INSERT` 에서 빠뜨리면 NOT NULL 위반이고,
       `INSERT OR IGNORE` 는 그 실패를 **조용히 삼킨다**(실측: 행이 안 생겼는데 예외 0건).
       ORM 으로 넣어야 27개 컬럼의 기본값이 채워진다.
    Use the ORM: the column defaults are Python-side, and INSERT OR IGNORE swallows the
    resulting NOT NULL violation without raising.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.models.repo_config import RepoConfig  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        if not session.query(Repository).filter_by(full_name=GATED_REPO).first():
            session.add(Repository(full_name=GATED_REPO, user_id=_E2E_USER_ID))
        cfg = session.query(RepoConfig).filter_by(repo_full_name=GATED_REPO).first()
        if cfg is None:
            cfg = RepoConfig(repo_full_name=GATED_REPO)
            session.add(cfg)
        cfg.approve_mode = "semi-auto"
        cfg.auto_merge = True
        cfg.auto_merge_issue_on_failure = True
        session.commit()
        got = session.query(RepoConfig).filter_by(repo_full_name=GATED_REPO).first()
        assert got is not None, "_seed_gated_repo: repo_configs 행이 없다"
        assert got.approve_mode == "semi-auto" and got.auto_merge, (
            f"게이트 설정이 기대와 다르다: approve_mode={got.approve_mode!r} "
            f"auto_merge={got.auto_merge!r} — 이 값이 아니면 숨은 블록이 열리지 않아 "
            "«못 쟀음» 이 된다"
        )
    finally:
        session.close()
        engine.dispose()
    return GATED_REPO


def _seed_absence_analysis(db_path: str) -> int:
    """«없는 것» 을 가진 분석 — 점수 NULL · 줄번호/경로 없는 이슈 → analysis_id.

    🔴 `analysis_detail.html` 은 «있을 때» 와 «없을 때» 를 가른다:
       `{% if analysis.score is not none %}…{% else %}—{% endif %}`(:26·:33) ·
       `{% if iss.get('line') %}`(:378) · `{% if iss.get('path') or iss.get('file') %}`(:381).
       기존 시드는 점수도 줄번호도 «항상» 있어서 **거짓 팔이 한 번도 렌더되지 않았다**.
       그쪽이 사람이 «분석이 실패했을 때» 보는 화면이다(#1639 W12-b).
    🔴 점수 NULL 은 진짜 운영 상태다 — #960 이 「절단형이 아니라 genuine 실패만 NULL」로
       한정했다. 그래서 `ai_review_status='api_error'` 를 함께 준다.
    Seed the absence side: NULL score and an issue with neither line nor path.
    """
    from sqlalchemy import create_engine, text

    from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name=:fn"
        ), {"fn": GATED_REPO}).fetchone()
        if row is None:
            raise RuntimeError("_seed_absence_analysis: gated repo must exist first")
        repo_id = row[0]
        result = {
            "summary": "e2e absence seed",
            "ai_review_status": "api_error",
            "issues": [
                # 🔴 `line` 도 `file` 도 없다 — 그 «없음» 이 이 시드의 목적이다.
                {"tool": "ruff", "category": "code_quality",
                 "message": "issue without a location", "severity": "warning"},
            ],
        }
        conn.execute(text("""
            INSERT OR IGNORE INTO analyses
                (repo_id, commit_sha, commit_message, score, grade, result,
                 author_login, score_unreliable, created_at)
            VALUES
                (:rid, 'absence-seed-001', 'fix: absence seed', NULL, 'F', :res,
                 'e2e-tester', :unrel, datetime('now'))
        """), {"rid": repo_id, "res": json.dumps(result),
               "unrel": score_is_unreliable(result)})
        conn.commit()
        got = conn.execute(text(
            "SELECT id, score FROM analyses WHERE repo_id=:rid AND commit_sha='absence-seed-001'"
        ), {"rid": repo_id}).fetchone()
    engine.dispose()
    assert got is not None, "_seed_absence_analysis: 행이 없다"
    assert got[1] is None, f"점수가 NULL 이 아니다({got[1]!r}) — 부재 팔이 안 열린다"
    return got[0]


def _seed_security_alerts(db_path: str) -> int:
    """보안 알림 2건 — 대기 1 · 처리완료 1 → 시드한 행 수.

    🔴 `?mode=security` 는 세 갈래다(`dashboard.html`):
       kill-switch → `total_alerts == 0` 빈 상태 → **4카드 그리드**.
       e2e 는 알림이 0건이라 언제나 «빈 상태» 만 그렸다 — 카드·분류 수치·대기 목록은
       한 번도 관측되지 않았다(#1639 W12-b).
    🔴 «기존 리포를 재사용» 한다. 새 리포를 만들면 `active_repos.total` 이 또 움직인다
       (`dashboard_service.py::_kpi_active_repos` 의 `total` 은 Repository 수를 센다).
       보안 알림 자체는 `analyses` 를 거치지 않아 평균 점수·HIGH KPI 를 건드리지 않는다.
    🔴 ORM 으로 넣는다 — `processed_at` 은 파이썬 측 `default` 라 원시 SQL 에서는
       NOT NULL 위반이 되고 `INSERT OR IGNORE` 가 그것을 조용히 삼킨다(#1652 실측).
    Seed two alerts so the security mode renders its 4-card grid instead of the empty state.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.models.repository import Repository  # noqa: PLC0415
    from src.models.security_alert_log import SecurityAlertProcessLog  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        repo = session.query(Repository).filter_by(full_name="owner/testrepo").first()
        if repo is None:
            raise RuntimeError("_seed_security_alerts: owner/testrepo must exist first")
        rows = [
            # 대기 — `user_decision IS NULL` 이라야 `list_pending` 에 잡힌다.
            {"alert_number": 9001, "ai_classification": "actual_violation",
             "severity": "high", "rule_id": "py/sql-injection", "user_decision": None,
             "ai_confidence": 0.92, "ai_reason": "e2e: 사용자 입력이 쿼리에 직접 들어간다"},
            # 처리완료 — `processed_count > 0` 을 만든다.
            {"alert_number": 9002, "ai_classification": "false_positive",
             "severity": "medium", "rule_id": "py/clear-text-logging",
             "user_decision": "accept_ai", "ai_confidence": 0.71,
             "ai_reason": "e2e: 테스트 픽스처에서만 쓰인다"},
        ]
        made = 0
        for r in rows:
            exists = session.query(SecurityAlertProcessLog).filter_by(
                repo_id=repo.id, alert_type="code_scanning",
                alert_number=r["alert_number"]).first()
            if exists is None:
                session.add(SecurityAlertProcessLog(
                    repo_id=repo.id, alert_type="code_scanning", user_id=_E2E_USER_ID, **r))
                made += 1
        session.commit()
        total = session.query(SecurityAlertProcessLog).count()
    finally:
        session.close()
        engine.dispose()
    assert total >= 2, (
        f"보안 알림이 {total}건 — 2건 이상이어야 그리드가 열린다. "
        "0이면 «못 쟀음» 이지 통과가 아니다")
    return made


def _seed_merge_history(db_path: str, analysis_id: int) -> dict[str, int]:
    """auto-merge 시도 이력 — 현재 창 3건(머지 1·실패 2) · 직전 창 1건(머지) ·
    직전 창의 낮은 점수 분석 1건 → overview 의 «머지 이력이 있을 때» 화면을 연다.

    🔴 e2e 는 `merge_attempts` 행을 **한 번도** 만들지 않았다. 그래서
       `dashboard.html:1234` 의 실패 사유 목록(`.reason-list`)과 auto-merge KPI 의
       `distinct_prs`(`--text-3` PR 카운트)·`delta` 팔은 어떤 조합에서도
       렌더되지 않았다 — 「안 쟀음」이지 통과가 아니었다(#1639 W12-b).
    🔴 이 시드는 **기준선을 둘 옮긴다** — 알고 쓴다:
       ① auto-merge KPI 가 «—»(비교 없음)에서 33.3% + ▼ 로 바뀐다.
       ② 직전 창의 score=10 분석이 `kpi.avg_score.delta` 를 양수로 만든다. 그 행은
          현재 창(7일) 밖이라 평균 자체는 그대로지만, 같은 `days` 로 도는
          `repo_insight_cards` 의 **직전 창** 비교값(`score_trend`)은 움직인다.
       그 숫자를 «0» 이나 «—» 로 고정하는 시험을 새로 쓰지 말 것.
    🔴 ORM 으로 넣는다 — `score_unreliable` 의 기본값은 **server_default true**(신뢰 불가)
       라 빠뜨리면 그 분석이 집계에서 빠지고, 원시 SQL + `INSERT OR IGNORE` 는
       NOT NULL 위반을 조용히 삼킨다(#1652 실측).

    Seeds merge attempts (and one previous-window analysis) so the overview renders the
    failure-reason list and the auto-merge KPI arms. It deliberately moves two baselines.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.models.analysis import Analysis  # noqa: PLC0415
    from src.models.merge_attempt import MergeAttempt  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415
    from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415
    from src.services import dashboard_service  # noqa: PLC0415

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cur_at, prev_at = now - timedelta(days=1), now - timedelta(days=10)

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        repo = session.query(Repository).filter_by(full_name="owner/testrepo").first()
        if repo is None:
            raise RuntimeError("_seed_merge_history: owner/testrepo must exist first")
        # 🔴 실패 사유가 **서로 달라야** 목록이 두 줄이 된다 — 같은 사유면 한 줄로 접힌다.
        #    머지 판정은 `success` 가 아니라 `_merge_attempt_states.is_merged(state, success)`
        #    다(켜기만 한 auto-merge 도 success=True).
        rows = [
            {"pr_number": 9101, "success": False, "failure_reason": "unstable_ci",
             "state": "legacy", "score": 72, "attempted_at": cur_at},
            {"pr_number": 9102, "success": False, "failure_reason": "blocked_by_review",
             "state": "legacy", "score": 68, "attempted_at": cur_at},
            {"pr_number": 9103, "success": True, "failure_reason": None,
             "state": "direct_merged", "score": 91, "attempted_at": cur_at},
            # 직전 창은 전부 머지(100%) — 그래야 현재 33.3% 와의 delta 가 음수(▼)가 된다.
            {"pr_number": 9001, "success": True, "failure_reason": None,
             "state": "direct_merged", "score": 88, "attempted_at": prev_at},
        ]
        for r in rows:
            exists = session.query(MergeAttempt).filter_by(
                repo_name=repo.full_name, pr_number=r["pr_number"]).first()
            if exists is None:
                session.add(MergeAttempt(
                    analysis_id=analysis_id, repo_name=repo.full_name, threshold=80, **r))
        old_sha = "merge-history-prev-001"
        if session.query(Analysis).filter_by(commit_sha=old_sha).first() is None:
            old_result = {"summary": "e2e previous-window baseline"}
            session.add(Analysis(
                repo_id=repo.id, commit_sha=old_sha,
                commit_message="chore: previous-window baseline for delta",
                score=10, grade="F", result=old_result, author_login="e2e-tester",
                score_unreliable=score_is_unreliable(old_result), created_at=prev_at))
        session.commit()

        # 🔴 되읽기는 «템플릿이 읽는 바로 그 함수» 로 한다. 행 수만 세면 사용자 필터나
        #    시간 창이 어긋나도 초록이 된다 — 그때 화면에는 아무것도 안 열린다.
        dist = dashboard_service.merge_failure_distribution(
            session, days=7, user_id=_E2E_USER_ID)
        auto = dashboard_service.auto_merge_kpi(session, days=7, user_id=_E2E_USER_ID)
        kpi = dashboard_service.dashboard_kpi(session, days=7, user_id=_E2E_USER_ID)
    finally:
        session.close()
        engine.dispose()

    assert len(dist) >= 2, (
        f"실패 사유가 {len(dist)}종 — 2종 이상이라야 `.reason-list` 가 두 줄이 된다. "
        "0이면 «못 쟀음» 이지 통과가 아니다")
    assert auto["distinct_prs"] and auto["delta"] is not None and auto["delta"] < 0, (
        f"auto-merge KPI 가 열리지 않았다 (distinct_prs={auto['distinct_prs']!r} "
        f"delta={auto['delta']!r}) — `--text-3` PR 카운트와 ▼ delta 팔이 닫힌 채다")
    assert kpi["avg_score"]["delta"] is not None and kpi["avg_score"]["delta"] > 0, (
        f"평균 점수 delta 가 {kpi['avg_score']['delta']!r} — 직전 창 분석이 "
        "집계에 안 잡혔다(`score_unreliable` 또는 시간 창 확인). ▲ 팔이 닫힌 채다")
    return {"failure_reasons": len(dist), "distinct_prs": auto["distinct_prs"]}


@pytest.fixture(scope="session")
def security_alerts(live_server):
    """보안 알림이 있는 상태 — `?mode=security` 가 4카드 그리드를 그린다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    return _seed_security_alerts(db_path)


def _seed_unclaimed_repo(db_path: str) -> str:
    """소유자 미등록 리포 + railway webhook 토큰 → full_name.

    🔴 **토큰까지 넣어야 팔 넷이 다 열린다.** `user_id=None` 만으로는 셋만 열리고
       railway 블록은 «미설정(pending)» 팔로 간다 —
       `railway_webhook_unclaimed = bool(token) and not claimed`(`settings.py:258-264`).
       Grok `01a093db` 이 「NULL-owner 한 줄이면 넷이 열린다」는 내 주장을 이 대목에서 깎았다.
    🔴 이 시드는 **기준선을 여럿 옮긴다** — 알고 쓴다:
       ① `kpi.active_repos.total` 2→3 (`dashboard.html:1088`)
       ② `/` 에 «미청구» 배너가 생긴다(`overview.html:210-215`) + 리포 카드 1장 추가
       ③ repos 모드의 연결 리포 수·등급바 분모·선택 목록(`dashboard.html:509`·`:524`·`:581`)
       그 숫자를 고정하는 시험을 새로 쓰지 말 것.
    🔴 **전역 시드로 만들지 않는다.** `/` 의 리포 카드가 늘면
       `e2e/test_overview_score.py:125` 의 `click(".repo-card")` 가 strict 위반이 되고,
       정렬이 `created_at desc` 라 새 카드가 «첫 번째» 로 온다. 이 픽스처를 요청하는
       시험만 그 상태를 본다(알파벳 순으로 마지막 파일).
    Seed an unclaimed repo *with* a railway webhook token — the token is what opens the
    fourth arm. Deliberately not a global seed: `/` would gain a repo card.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.models.repo_config import RepoConfig  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        if not session.query(Repository).filter_by(full_name=UNCLAIMED_REPO).first():
            session.add(Repository(full_name=UNCLAIMED_REPO, user_id=None))
        cfg = session.query(RepoConfig).filter_by(repo_full_name=UNCLAIMED_REPO).first()
        if cfg is None:
            cfg = RepoConfig(repo_full_name=UNCLAIMED_REPO)
            session.add(cfg)
        # 자격증명이 «설정돼 있는데 가려지는» 상태라야 가림 로직이 관측된다
        # (`renderable_secrets(..., claimed=False)` 가 빈 문자열을 돌려준다).
        cfg.railway_webhook_token = "e2e-unclaimed-railway-token-0001"
        cfg.notify_chat_id = "1234567890"
        session.commit()
        got_repo = session.query(Repository).filter_by(full_name=UNCLAIMED_REPO).first()
        got_cfg = session.query(RepoConfig).filter_by(repo_full_name=UNCLAIMED_REPO).first()
        claimed = got_repo.user_id is not None if got_repo else None
        token = got_cfg.railway_webhook_token if got_cfg else None
    finally:
        session.close()
        engine.dispose()

    assert claimed is False, (
        f"미청구 상태가 아니다 (user_id 존재 여부={claimed!r}) — 팔이 열리지 않는다")
    assert token, "railway webhook 토큰이 비었다 — 네 번째 팔이 «미설정» 으로 간다"
    return UNCLAIMED_REPO


@pytest.fixture(scope="session")
def unclaimed_repo(live_server):
    """소유자 미등록 리포 — 설정 화면의 «청구 필요» 팔 넷이 열린다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_unclaimed_repo(db_path)


# ── analysis_detail 변종 시드의 «값» — 시험이 기대값으로 되읽는다 ────────────
#
# 🔴 DOM 만 보는 판정은 위조된다(Grok `01a0998d`): 더미 `.ad-feedback-item` 두 개나
#    가짜 막대 세 개를 템플릿에 박으면 「개수·클래스」 판정은 그대로 초록이다. 그래서
#    시험은 **여기 심은 값** 과 대조한다 — 화면이 그 값을 내려면 DB 를 거쳐야 한다.
# 🔴 세 값이 한 화면에서 high(≥75)·mid(50~74)·low(<50) 팔을 **동시에** 연다
#    (`pct = val / mx * 100`, 최대치는 템플릿 루프 상수: code_quality 25 · security 20).
VARIANT_BREAKDOWN = {"code_quality": 25, "security": 12, "commit_message": 1}
VARIANT_FEEDBACKS = {
    "commit_message_feedback": "e2e: 커밋 메시지가 규칙을 따릅니다 / follows the convention",
    "security_feedback": "e2e: 하드코딩된 비밀이 없습니다 / no hardcoded secrets",
}


def _seed_analysis_variants(db_path: str) -> dict[str, int]:
    """analysis_detail 의 «한 번도 안 그려진» 팔들을 여는 분석 8건 → {이름: id}.

    🔴 분기 프로브(전체 e2e 실측, 2026-09-13)가 지목한 좌표다 — `analysis_detail.html`
       237~241(AI 상태 사슬 전부) · 276(점수 막대 high/mid/low) · 333(카테고리 피드백) ·
       409(result 없는 레거시 행 — 점수 없는 쪽·있는 쪽 **양쪽**). 전부 **result JSON 만으로** 열린다
       (`{% set ai_status = r.get('ai_review_status', 'success') %}` 처럼 템플릿이 직접 읽는다).
    🔴 `owner/gatedrepo` 에 **점수 NULL** 로 심는다 — 평균 점수·등급 집계를 건드리지 않기
       위해서다(그 리포의 «분석 없음» 화면을 재는 시험이 있다). 분석 «건수» 는 움직인다.
    🔴 ORM 으로 넣는다 — `score_unreliable` 은 server_default true 라 빠뜨리면 집계에서
       빠지고, 원시 SQL + `INSERT OR IGNORE` 는 NOT NULL 위반을 조용히 삼킨다.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.models.analysis import Analysis  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    base_result = {
        "summary": "e2e: analysis_detail 변종 / variant page",
        "issues": [],
        "breakdown": VARIANT_BREAKDOWN,
        **VARIANT_FEEDBACKS,
    }
    # 🔴 `other` 는 **아는 이름이 아닌** 상태다 — 세 `elif` 를 전부 거짓으로 지나
    #    `{% else %}`(:242) 로 떨어뜨려 `:241` 의 «거짓» 팔을 연다. `no_api_key` 는
    #    `:237` 의 «참» 팔. 이 둘이 있어야 상태 사슬 다섯 노드가 양쪽 다 관측된다.
    variants = {
        "no_api_key": dict(base_result, ai_review_status="no_api_key"),
        "api_error": dict(base_result, ai_review_status="api_error"),
        "empty_diff": dict(base_result, ai_review_status="empty_diff"),
        "parse_error": dict(base_result, ai_review_status="parse_error"),
        "disabled": dict(base_result, ai_review_status="disabled"),
        "other": dict(base_result, ai_review_status="e2e-unknown-status"),
    }
    ids: dict[str, int] = {}
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        repo = session.query(Repository).filter_by(full_name=GATED_REPO).first()
        if repo is None:
            raise RuntimeError("_seed_analysis_variants: gated repo must exist first")
        for i, (name, result) in enumerate(variants.items()):
            sha = f"variant-{name}"
            row = session.query(Analysis).filter_by(commit_sha=sha).first()
            if row is None:
                row = Analysis(repo_id=repo.id, commit_sha=sha,
                               commit_message=f"e2e: {name} variant",
                               score=None, grade=None, result=result,
                               author_login="e2e-tester", score_unreliable=True,
                               created_at=now - timedelta(minutes=i + 1))
                session.add(row)
            ids[name] = 0
        # 🔴 레거시 행 — `result` 가 **없다**. `{% if analysis.score is none %}`(:409)는
        #    result 가 없는 갈래 «안» 에 있어서, 점수만 NULL 인 기존 시드로는 안 열린다.
        legacy_sha = "variant-legacy-no-result"
        if session.query(Analysis).filter_by(commit_sha=legacy_sha).first() is None:
            session.add(Analysis(repo_id=repo.id, commit_sha=legacy_sha,
                                 commit_message="e2e: legacy row without result",
                                 score=None, grade=None, result=None,
                                 author_login="e2e-tester", score_unreliable=True,
                                 created_at=now - timedelta(minutes=9)))
        # 🔴 `:409` 의 **거짓 팔**(`:418`) — result 는 없는데 점수는 있는 행. 두 팔을 한
        #    시험에서 **비교** 해야 「조건 없이 늘 레거시 문구를 찍는」 구현과 갈라진다
        #    (Grok `01a0998d` 가 앞선 판을 이 대목에서 깨다). `score_unreliable=True` 라
        #    집계에선 빠진다 — `src/ui/routes/overview.py` 의 `score_unreliable.isnot(True)`.
        scored_sha = "variant-legacy-scored"
        if session.query(Analysis).filter_by(commit_sha=scored_sha).first() is None:
            session.add(Analysis(repo_id=repo.id, commit_sha=scored_sha,
                                 commit_message="e2e: legacy row, no result but scored",
                                 score=77, grade="C", result=None,
                                 author_login="e2e-tester", score_unreliable=True,
                                 created_at=now - timedelta(minutes=10)))
        session.commit()
        shas = {name: f"variant-{name}" for name in variants}
        shas["legacy"] = legacy_sha
        shas["legacy_scored"] = scored_sha
        for name, sha in shas.items():
            row = session.query(Analysis).filter_by(commit_sha=sha).first()
            assert row is not None, f"시드한 {sha} 행을 되읽지 못했다"
            ids[name] = row.id
    finally:
        session.close()
        engine.dispose()
    return ids


@pytest.fixture(scope="session")
def analysis_variants(live_server, gated_settings_repo):
    """analysis_detail 의 AI 상태·점수 막대·피드백·레거시 팔을 여는 분석 id 들."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_analysis_variants(db_path)


@pytest.fixture(scope="session")
def merge_history(live_server, seeded_analysis):
    """머지 이력이 있는 상태 — overview 가 실패 사유 목록 + auto-merge KPI 를 그린다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_merge_history(db_path, seeded_analysis)


# ── insight 모드의 «성공» 그리드 ────────────────────────────────────────────
#
# 🔴 `?mode=insight` 는 e2e 에서 **한 번도 성공 화면을 그린 적이 없다.** 키가 없으면
#    `no_api_key` 상태 안내만 나온다. 4카드 그리드(`dashboard.html:941-973`)는
#    마지막 남은 «한 번도 안 열린» 대시보드 모드였다(#1639).
INSIGHT_LANGUAGE = "en"


def _seed_insight_success_cache(db_path: str, *, language: str = INSIGHT_LANGUAGE) -> dict:
    """insight 4카드 «성공» 응답을 캐시에 넣는다 → 넣은 응답 dict.

    🔴 **INSERT 가 아니라 upsert 다.** 같은 키
       `(user_id, days, language, repo_id IS NULL)` 에 유니크 인덱스
       (`uq_insight_cache_global`)가 있고, 앞선 `?mode=insight` 방문이 남긴 **오류 행**이
       이미 있을 수 있다(`_handle_insight_error` → `record_error`). 그 행은
       `expires_at=now` 라 stale 이라서 조회에는 안 잡히지만, INSERT 는 유니크 위반이다
       (Grok `01a095b6` 이 이 대목에서 내 계획을 깎았다).
    🔴 언어를 못박는다 — 라우트가 `language=locale_value` 로 넘기고 로케일은 브라우저
       `Accept-Language` 에서 온다. 시험은 `preferred_language` 쿠키로 같은 값을 고정한다.
       어긋나면 캐시가 빗나가 API 호출로 흘러간다.

    Upsert (never insert) a success payload; an earlier error row may already hold the key.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

    response = {
        "status": "success",
        "days": 7,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "positive_highlights": [
            "Average score held at 85 across the window.",
            "Auto-merge recovered on the second attempt for every blocked PR.",
        ],
        "focus_areas": [
            "Two PRs failed on unstable CI checks.",
            "One hardcoded credential finding is still open.",
        ],
        "key_metrics": [
            {"label": "Average score", "value": "85", "delta": "+45"},
            {"label": "Auto-merge success", "value": "33.3%", "delta": "-66.7"},
            {"label": "Analyses", "value": "1", "delta": None},
        ],
        "next_actions": [
            "Stabilise the flaky check before re-running auto-merge.",
            "Resolve the open security finding on src/app.py.",
        ],
    }
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        insight_narrative_cache_repo.upsert(
            session, user_id=_E2E_USER_ID, days=7, language=language, response=response)
        # 🔴 되읽기는 «서비스가 읽는 그 함수» 로 한다 — 행이 생겨도 시간 창·언어가
        #    어긋나면 화면은 안 열리고 API 호출로 흘러간다.
        got = insight_narrative_cache_repo.get_fresh(
            session, user_id=_E2E_USER_ID, days=7, language=language)
    finally:
        session.close()
        engine.dispose()
    assert got is not None and got.get("status") == "success", (
        f"insight 캐시가 신선하지 않다: {got!r} — 이 상태면 성공 그리드가 안 열린다")
    return response


@contextlib.contextmanager
def insight_key_window():
    """insight 경로가 «키가 있는» 상태로 도는 창 — 이 창 밖에서는 원래대로 돌려놓는다.

    🔴 키를 세션 전역 env 로 넣지 않는다. 키가 있으면 `/repos/<repo>/insights` 의
       리포 내러티브도 깨어나 매 방문마다 실패 호출 + `claude_api_calls` 행을 쓴다
       (Grok `01a095b6` 이 내 「부작용 없음」 주장을 BROKEN 으로 깎았다).
       e2e 서버는 **같은 프로세스의 스레드**라 `settings` 를 잠시 바꾸면 그 창만 열린다.
    🔴 그럼에도 `ANTHROPIC_BASE_URL` 을 도달 불가 주소로 고정한다 — 캐시가 빗나가도
       호출이 **기계 밖으로 나가지 않는다**(`anthropic` SDK 가 이 env 를 읽는다).
    """
    from src.config import settings  # noqa: PLC0415

    prev_key, prev_base = settings.anthropic_api_key, os.environ.get("ANTHROPIC_BASE_URL")
    settings.anthropic_api_key = "e2e-dummy-not-a-real-key"
    os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:1"
    try:
        yield
    finally:
        settings.anthropic_api_key = prev_key
        if prev_base is None:
            os.environ.pop("ANTHROPIC_BASE_URL", None)
        else:
            os.environ["ANTHROPIC_BASE_URL"] = prev_base


@contextlib.contextmanager
def acting_as(user_id: int, login: str = "e2e-other"):
    """이 창 동안 `/dashboard` 가 **다른 사용자**로 돈다.

    🔴 `require_login` 을 갈아야 한다 — `/dashboard` 가 무는 것이 그것이다
       (`src/ui/routes/dashboard.py`). `get_current_user` 만 갈면 아무것도 안 바뀐다:
       `require_login` 은 그것을 **평범한 함수로** 부르므로 FastAPI override 가 안 탄다
       (Grok `01a09a3b` 이 내 계획의 이 대목을 잡았다). 템플릿의 nav 를 위해 둘 다 간다.
    ⚠️ 앱 전역 상태다 — 순차 실행 전제(이 스위트가 그렇다).
    """
    from src.auth.session import CurrentUser, get_current_user, require_login  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415

    other = CurrentUser(id=user_id, github_login=login, email=f"{login}@test.com",
                        display_name=login, plaintext_token="gho_e2e_test_token")
    saved = {k: app.dependency_overrides.get(k) for k in (require_login, get_current_user)}
    app.dependency_overrides[require_login] = lambda: other
    app.dependency_overrides[get_current_user] = lambda: other
    try:
        yield other
    finally:
        for key, prev in saved.items():
            if prev is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = prev


# ── 리포를 하나도 안 가진 사용자 ────────────────────────────────────────────
#
# 🔴 `?mode=insight` 의 `no_data`(dashboard.html:979)는 **분석이 0건**일 때만 나온다.
#    그 상태를 «신선한 캐시 행» 으로 위조할 수는 없다 — `record_error` 는 error 를
#    `expires_at=now` 로 적어 **절대 신선하지 않다**(앱이 못 내는 상태를 심는 셈).
# 🔴 소유 필터는 `Repository.user_id == me OR user_id IS NULL` 이라, NULL 소유 리포에
#    분석이 생기면 이 사용자도 그것을 본다. 지금 NULL 소유는 `owner/unclaimedrepo`
#    하나이고 분석이 없다 — 시험이 그 전제를 직접 단언한다(Grok `01a09a3b`).
EMPTY_USER_ID = 9001


def _seed_empty_user(db_path: str) -> int:
    """리포도 분석도 없는 사용자 한 명 → user_id."""
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "INSERT OR IGNORE INTO users "
                "(id, github_id, github_login, github_access_token, email, display_name,"
                " created_at) VALUES (:id, :gid, :login, :token, :email, :name,"
                " datetime('now'))"
            ), {"id": EMPTY_USER_ID, "gid": EMPTY_USER_ID, "login": "e2e-empty",
                "token": "gho_e2e_empty", "email": "empty@test.com", "name": "E2E Empty"})
            conn.commit()
            owned = conn.execute(text(
                "SELECT COUNT(*) FROM repositories WHERE user_id = :uid"
            ), {"uid": EMPTY_USER_ID}).scalar()
            # 🔴 소유 필터가 `user_id == me OR user_id IS NULL` 이라, **NULL 소유 리포에
            #    분석이 하나라도 생기면** 이 사용자의 analysis_count 도 0 이 아니게 되고
            #    `?mode=insight` 는 `no_data` 가 아니라 `api_error` 로 간다. 그때 시험은
            #    red 가 되지만 이유가 멀다 — 여기서 바로 말한다.
            legacy = conn.execute(text(
                "SELECT COUNT(*) FROM analyses a JOIN repositories r ON r.id = a.repo_id"
                " WHERE r.user_id IS NULL"
            )).scalar()
        assert owned == 0, f"빈 사용자가 리포 {owned}개를 가졌다 — no_data 전제가 깨졌다"
        assert legacy == 0, (
            f"소유자 없는(user_id IS NULL) 리포에 분석이 {legacy}건 있다 — 모든 사용자가 "
            "그것을 보므로 «분석 0건» 사용자를 만들 수 없다. 그 분석을 소유자 있는 리포로 "
            "옮기거나, no_data 를 여는 다른 길을 찾아야 한다")
    finally:
        engine.dispose()
    return EMPTY_USER_ID


# ── delta 팔을 여는 전용 사용자 세 명 (#1639 · dashboard.html 564·1036·1153·1155) ──
#
# 🔴 그 다섯 노드는 전부 «부호» 를 묻는 elif 사슬이라, 팔을 다 열려면 **양수 · 음수 ·
#    정확히 0** 세 상태가 필요하다(뒤쪽 elif 의 «거짓» 팔은 앞 조건이 전부 거짓일 때만
#    도달한다 = delta == 0). 한 DB 에 세 상태를 동시에 두는 길은 **사용자를 나누는 것**뿐이다.
# 🔴 사용자 1 의 수치는 움직이지 않는다 — 소유 필터가 `user_id == me OR user_id IS NULL`
#    이라 새 사용자의 리포는 사용자 1 에게 안 보인다. 반대로 **NULL 소유 리포에는 아무것도
#    붙이지 않는다** — 그것은 모든 사용자에게 보인다(비용 서브쿼리도 마찬가지다,
#    `claude_api_cost_repo._owned_repo_ids_subquery`; Grok `01a09a3b` 이 이 대목을 정정했다).
# 🔴 창이 둘이다 — 점수는 `?days=N`, 비용은 **고정 30일**(`_kpi_cost`). 한 시각으로 둘을
#    채울 수 없어서 시험이 `?days=30` 으로 방문한다. 그러면 두 창이 겹친다:
#    현재 `[now-30d, now]` · 이전 `[now-60d, now-30d)`. 시드는 5일 전·45일 전에 둔다.
# 🔴 `score_unreliable` 은 server_default true 다 — 빠뜨리면 집계에서 통째로 빠진다.
DELTA_DAYS = 30
DELTA_USERS = {"mixed": 9101, "up": 9102, "down": 9103}
# {사용자: {리포 접미사: (이전 창 점수, 현재 창 점수)}} — 현재 점수가 등급을 정하고,
# 45 미만이면 F 라 «경고 리포» 가 된다(`dashboard.py:_REPORT_WARNING_GRADES`).
DELTA_REPO_SCORES = {
    "mixed": {"up": (20, 40), "down": (60, 30), "flat": (35, 35)},
    "up": {"even": (50, 50)},
    "down": {},
}
# {사용자: (이전 창 비용, 현재 창 비용)} — 셋 다 이전 창이 **비면 안 된다**(비면 delta 가
# None 이 되어 바깥 else 로 가고 elif 팔은 아예 평가되지 않는다).
DELTA_COSTS = {"mixed": (0.5, 0.5), "up": (0.5, 2.0), "down": (2.0, 0.5)}
# 🔴 `repo_insights.html:266`(`s.count > 1`)은 **같은 제안이 두 번 이상** 나와야 열린다.
#    `repo_ai_suggestions` 는 60자 prefix 로 묶고 `ai_review_status == "success"` 인
#    분석만 센다(`repo_insight_service.py`). 그래서 두 창의 분석에 **공통 제안 하나** 와
#    **각자 고유 제안 하나** 를 넣는다 — 전자가 «참» 팔(2회), 후자가 «거짓» 팔(1회)이다.
DELTA_SHARED_SUGGESTION = "e2e: 반복되는 제안 — 예외를 삼키지 말고 로그를 남기세요"
DELTA_UNIQUE_SUGGESTION = {"prev": "e2e: 이전 창에만 있는 제안 — 테스트를 추가하세요",
                           "cur": "e2e: 현재 창 A 의 제안 — 함수를 쪼개세요",
                           "cur2": "e2e: 현재 창 B 의 제안 — 상수를 이름으로 빼세요"}
# 30일 창 안에서 보이게 될 제안과 건수 — 시험이 이것과 대조한다.
DELTA_SUGGESTION_COUNTS = {
    DELTA_SHARED_SUGGESTION: 2,
    DELTA_UNIQUE_SUGGESTION["cur"]: 1,
    DELTA_UNIQUE_SUGGESTION["cur2"]: 1,
}


def delta_repo_name(kind: str, suffix: str) -> str:
    return f"owner/e2edelta-{kind}-{suffix}"


def expected_score_delta(kind: str, suffix: str) -> float:
    prev, cur = DELTA_REPO_SCORES[kind][suffix]
    return round(float(cur) - float(prev), 1)


def expected_avg_delta(kind: str) -> float | None:
    """그 사용자의 전역 평균 점수 delta — 분석 «건별» 평균이다(리포별 평균의 평균이 아니다)."""
    pairs = list(DELTA_REPO_SCORES[kind].values())
    if not pairs:
        return None
    cur = round(sum(c for _, c in pairs) / len(pairs), 1)
    prev = round(sum(p for p, _ in pairs) / len(pairs), 1)
    return round(cur - prev, 1)


def expected_cost_delta(kind: str) -> float:
    prev, cur = DELTA_COSTS[kind]
    return round(cur - prev, 6)


def _seed_delta_users(db_path: str) -> dict[str, int]:
    """세 사용자 + 각자의 리포·분석·비용 행 → {이름: user_id}."""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from sqlalchemy import create_engine, text  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from src.models.analysis import Analysis  # noqa: PLC0415
    from src.models.claude_api_call import ClaudeApiCall  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415
    from src.scorer.calculator import calculate_grade  # noqa: PLC0415

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # 🔴 현재 창에 분석이 **둘** 필요하다 — `repo_ai_suggestions` 는 30일 창만 보므로
    #    이전 창 분석은 제안 집계에 안 들어간다. 같은 점수로 넣어 평균·delta 는 그대로 둔다.
    cur_at, cur2_at = now - timedelta(days=5), now - timedelta(days=6)
    prev_at = now - timedelta(days=45)
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        for kind, uid in DELTA_USERS.items():
            session.execute(text(
                "INSERT OR IGNORE INTO users (id, github_id, github_login,"
                " github_access_token, email, display_name, created_at)"
                " VALUES (:id, :gid, :login, :tok, :mail, :name, datetime('now'))"
            ), {"id": uid, "gid": uid, "login": f"e2e-delta-{kind}",
                "tok": f"gho_e2e_delta_{kind}", "mail": f"delta-{kind}@test.com",
                "name": f"E2E delta {kind}"})
            for suffix, (prev_score, cur_score) in DELTA_REPO_SCORES[kind].items():
                name = delta_repo_name(kind, suffix)
                repo = session.query(Repository).filter_by(full_name=name).first()
                if repo is None:
                    repo = Repository(full_name=name, user_id=uid)
                    session.add(repo)
                    session.flush()
                for tag, score, at in (("prev", prev_score, prev_at),
                                       ("cur", cur_score, cur_at),
                                       ("cur2", cur_score, cur2_at)):
                    sha = f"delta-{kind}-{suffix}-{tag}"
                    if session.query(Analysis).filter_by(commit_sha=sha).first() is None:
                        session.add(Analysis(
                            repo_id=repo.id, commit_sha=sha,
                            commit_message=f"e2e delta {kind}/{suffix} {tag}",
                            score=score, grade=calculate_grade(score),
                            result={"summary": f"e2e delta {tag}", "issues": [],
                                    "ai_review_status": "success",
                                    "ai_suggestions": [DELTA_SHARED_SUGGESTION,
                                                       DELTA_UNIQUE_SUGGESTION[tag]]},
                            author_login="e2e-tester", score_unreliable=False,
                            created_at=at))
            prev_cost, cur_cost = DELTA_COSTS[kind]
            for tag, cost, at in (("prev", prev_cost, prev_at), ("cur", cur_cost, cur_at)):
                marker = f"e2e-delta-{kind}-{tag}"
                if session.query(ClaudeApiCall).filter_by(error_type=marker).first() is None:
                    # 🔴 `repo_id` 를 비운다 — NULL 소유 리포에 달면 모든 사용자에게 샌다.
                    session.add(ClaudeApiCall(
                        created_at=at, model="claude-haiku-4-5-20251001", status="success",
                        input_tokens=1, output_tokens=1, cost_usd=cost, duration_ms=1.0,
                        repo_id=None, user_id=uid, error_type=marker))
        session.commit()
        for kind, uid in DELTA_USERS.items():
            owned = session.query(Repository).filter_by(user_id=uid).count()
            assert owned == len(DELTA_REPO_SCORES[kind]), (
                f"{kind}: 리포 {owned}개 (기대 {len(DELTA_REPO_SCORES[kind])}) — "
                "시드가 어긋나면 부호가 바뀐다")
        # 🔴 제안 시드가 «두 팔» 을 열 수 있는지 못박는다 — 공통 제안이 없으면 `count > 1`
        #    팔이, 고유 제안이 없으면 그 «거짓» 팔이 안 열린다. 파생되지 않는 바닥이다.
        assert DELTA_SHARED_SUGGESTION not in DELTA_UNIQUE_SUGGESTION.values(), (
            "공통 제안과 고유 제안이 같다 — `:266` 의 두 팔이 갈라지지 않는다")
        assert len(set(DELTA_UNIQUE_SUGGESTION.values())) == 3, (
            "창마다 고유한 제안이 하나씩 있어야 «1회» 항목이 생긴다")
        assert len({s[:60] for s in
                    [DELTA_SHARED_SUGGESTION, *DELTA_UNIQUE_SUGGESTION.values()]}) == 4, (
            "60자 prefix 가 겹친다 — `repo_ai_suggestions` 가 그 단위로 묶으므로 "
            "겹치면 건수가 합쳐진다")
        assert set(DELTA_SUGGESTION_COUNTS.values()) == {1, 2}, (
            f"제안 건수가 {sorted(set(DELTA_SUGGESTION_COUNTS.values()))} — "
            "`repo_insights.html:266` 은 «2회 이상» 과 «1회» 가 **함께** 있어야 두 팔이 열린다")
        legacy = session.query(ClaudeApiCall).join(
            Repository, ClaudeApiCall.repo_id == Repository.id).filter(
            Repository.user_id.is_(None)).count()
        assert legacy == 0, (
            f"소유자 없는 리포에 비용 행이 {legacy}건 — 그 비용은 **모든** 사용자의 "
            "monthly_cost 에 들어가 이 시험의 부호를 무너뜨린다")
    finally:
        session.close()
        engine.dispose()
    return dict(DELTA_USERS)


@pytest.fixture(scope="session")
def delta_users(live_server):
    """delta 팔(+ · − · 정확히 0)을 여는 전용 사용자 세 명 → {이름: user_id}."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_delta_users(db_path)


@pytest.fixture(scope="session")
def empty_user(live_server):
    """리포가 없는 사용자 — `?mode=insight` 가 `no_data` 로 간다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_empty_user(db_path)


@pytest.fixture
def insight_success(live_server, seeded_analysis):
    """insight 성공 그리드가 열린 상태 — **이 시험 동안만** API 키를 켠다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    payload = _seed_insight_success_cache(db_path)
    with insight_key_window():
        yield payload


@pytest.fixture(scope="session")
def absence_analysis(live_server, gated_settings_repo):
    """점수 NULL · 위치 없는 이슈를 가진 분석 id."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_absence_analysis(db_path)


@pytest.fixture(scope="session")
def gated_settings_repo(live_server):
    """`auto_merge=True`·`approve_mode='semi-auto'` 인 리포 — 숨은 게이트 블록이 열린다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    return _seed_gated_repo(db_path)


@pytest.fixture(scope="session")
def graded_analyses(live_server):
    """등급 A~F 분석을 심고 {등급: id} 를 돌려준다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    return _seed_graded_analyses(db_path)


@pytest.fixture(scope="session")
def seeded_analysis(live_server):
    """owner/testrepo + Analysis 레코드를 삽입하고 analysis_id를 반환하는 session fixture.
    Seeds owner/testrepo repo and Analysis record; returns analysis_id (session-scoped).
    """
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_repo(live_server, db_path)
    return _seed_analysis(db_path)


# ── skip 집합 게이트 (backlog R58 → 회고 2026-09-07 D) ──────────────────────
#
# 🔴 **수집 건수 baseline 만으로는 전건 skip 을 못 막는다.** `scripts/check_e2e_scope.py`
# 가 수집 건수를 확인해도, 그것이 전부 skip 되면 pytest 는 **exit 0** 이다 —
# `pytest.mark.skip`·`skipif`·픽스처 skip 어느 경로든 결말이 같다. 실제로 이 스위트는
# `live_server` 가 전건 skip 을 유발해 **앱이 부팅 못 해도 CI 초록**이었다(뮤테이션 실측).
#
# 🔴 종전 처방(통과 건수 **하한**)은 그 자체가 같은 부류의 결함이었다. 하한은 손으로 적은
# 상수라 스위트가 자라도 따라가지 않는다 — 실측: 수집이 122→200 으로 는 동안 CI 는
# `--e2e-min-passed=100` 에 머물러 **절반이 조용히 skip 돼도 초록**인 상태였다(분해능
# 82%→50%). 여유 칸(budget)을 둔 파생값도 같은 결함을 다시 만든다.
#
# 그래서 숫자가 아니라 **집합**으로 판정한다: 관측된 skip 노드 집합이 커밋된
# `e2e/SKIP_ALLOWLIST` 와 **양방향으로** 일치해야 한다. 목록 밖 skip 이 생기면 red,
# 목록에 있는데 skip 되지 않아도 red(낡은 예외는 다음 사람에게 거짓을 가르친다).
# 이 관용구의 정본은 `scripts/check_lint_js_nonvacuous.py` 의 커밋된 justified 집합이다.
#
# opt-in(`--e2e-strict-skips`)이라 로컬 부분 실행(`-k`)에는 영향이 없고, CI 만 건다.
# 🔴 값을 받지 않는 **불리언 플래그**다 — `=N` 형태면 `=0` 으로 조용히 끌 수 있고,
# CI 배선을 부분문자열로 재던 가드가 그것을 통과시켰다.
#
# A collection baseline cannot stop mass-skip, and a hand-written pass floor rots as the
# suite grows. Gate on the skip *set* against a committed allowlist, both directions.

_SKIP_ALLOWLIST = Path(__file__).resolve().parent / "SKIP_ALLOWLIST"


def _allowed_skips() -> set[str] | None:
    """커밋된 정당 skip 집합 — 파일이 없거나 못 읽으면 None(판정 불가)."""
    try:
        raw = _SKIP_ALLOWLIST.read_text(encoding="utf-8")
    except OSError:
        return None
    out = set()
    for line in raw.splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            out.add(entry)
    return out


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-strict-skips", action="store_true",
        help="skip 집합이 e2e/SKIP_ALLOWLIST 와 다르면 세션을 실패시킨다(공허화 차단).",
    )


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if not session.config.getoption("--e2e-strict-skips"):
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return

    def fail(msg: str) -> None:
        reporter.write_line(msg, red=True)
        session.exitstatus = 1

    allowed = _allowed_skips()
    if allowed is None:
        # 🔴 못 재면 초록이 아니라 red 다 — 목록이 사라지면 게이트가 통째로 사라진다.
        fail(f"e2e skip allowlist 를 읽지 못했다 ({_SKIP_ALLOWLIST}) — 판정 불가라 red 다.")
        return

    observed = {r.nodeid.replace("\\", "/") for r in reporter.stats.get("skipped", [])}
    collected = {i.nodeid.replace("\\", "/") for i in getattr(session, "items", [])}
    unexpected = sorted(observed - allowed)
    # 🔴 stale 은 «이번에 수집된» 것만 본다 — `-k` 로 걸러진 항목까지 세면 부분 실행이
    #    거짓 red 가 된다. 목록에 있는데 **아예 사라진** 시험은 이 축이 아니라
    #    `test_skip_allowlist_is_committed_and_matches_the_measured_skip` 이 잡는다
    #    (파일·함수 실재를 정적으로 확인한다). 두 축이 겹치지 않게 나눈다.
    stale = sorted((allowed & collected) - observed)
    if unexpected:
        fail("e2e 에서 허용되지 않은 skip {}건 — 수집은 됐으나 검증되지 않았다:\n  {}".format(
            len(unexpected), "\n  ".join(unexpected)))
    if stale:
        fail("e2e/SKIP_ALLOWLIST 가 낡았다 — 이제 skip 되지 않는 항목 {}건, 지워라:\n  {}".format(
            len(stale), "\n  ".join(stale)))


# ── admin 도달 · 외부 이동 방지 (#1639 W10) ───────────────────────────────────
#
# 🔴 이 두 개는 «관용구» 다. 한 파일에만 있으면 다음 프로브가 같은 실수를 반복한다 —
#    실제로 admin 세션 쿠키 없이 `/admin/*` 을 연 프로브가 **github.com 을 72조합 측정**
#    하고, GitHub 로그인 페이지의 결함(이름 없는 아이콘 버튼 30·작은 타깃 37·중복 id 4)을
#    이 앱의 결함으로 집계했다. 남의 DOM 을 우리 것으로 적는 것이 가장 나쁜 오측이다.

def admin_session_cookie(user_id: int = 1) -> dict:
    """실제 서명 세션 쿠키 — `/admin/*` 을 여는 «유일한» 방법.

    🔴 의존성 override 로는 안 된다. `require_admin` 은 `require_login` 을 의존성이
    아니라 «평범한 함수» 로 부르기 때문에(`src/auth/session.py`), conftest 의
    `dependency_overrides[require_login]` 이 그 경로에는 적용되지 않는다.
    진짜 세션을 만들어 kill-switch → require_login → email allow-list 사슬을 그대로 태운다.

    🔴 비밀키를 여기 복제하지 않는다 — `live_server` 가 세운 값을 그대로 읽는다.
    복제하면 그 값을 바꾼 날 조용히 302 로 흘러간다.
    """
    import base64  # noqa: PLC0415
    import json as _json  # noqa: PLC0415

    import itsdangerous  # noqa: PLC0415
    secret = os.environ["SESSION_SECRET"]
    data = base64.b64encode(_json.dumps({"user_id": user_id}).encode())
    value = itsdangerous.TimestampSigner(secret).sign(data).decode()
    return {"name": "session", "value": value, "domain": "localhost", "path": "/"}


def _assert_still_on_our_app(page, path: str, resp=None) -> None:
    """🔴 «우리 앱을 재고 있는가» 를 먼저 확인한다 — 세 축을 다 본다.

    호스트만 보면 안 된다: 403/503 오류 페이지도 localhost 다(fail-open). 상태와
    «우리 마크업» 을 함께 봐야 「열렸다」가 「그 화면이다」가 된다.
    """
    assert "localhost" in page.url or "127.0.0.1" in page.url, (
        f"{path} 가 렌더되지 않고 {page.url[:70]} 로 이동했다 — "
        "인가 사슬이 막았다(세션 쿠키·SAAS_ADMIN_EMAILS 확인). 이 상태로 측정하면 "
        "«남의 페이지» 를 이 앱의 결함으로 적게 된다")
    if resp is not None:
        assert resp.status == 200, f"{path} status={resp.status} — 오류 페이지를 재고 있다"
    assert page.locator("nav").count() > 0, (
        f"{path} 에 우리 `nav` 가 없다 — localhost 이지만 우리 화면이 아니다")


def apply_theme(page, theme: str) -> None:
    """테마를 걸고 «실제로 걸렸는지» 확인한다 — 네 갈래가 같은 화면이 되지 않도록.

    🔴 `applyTheme` 은 모르는 이름을 **조용히 `dark` 로 되돌린다**(`base.html:770-771`).
       확인하지 않으면 `@parametrize("theme", [...4개...])` 가 같은 화면을 네 번 재고도
       초록이다 — 「안 쟀음」과 「통과」가 구별되지 않는다.
    🔴 실측(2026-09-12): 5개 경로 × 4테마가 **전부 서로 다른 팔레트**(4/4 고유)이고
       `data-theme` 도 일치했다. 즉 지금은 결함이 아니라 **그 상태를 유지시키는 장치**다.
       테마 목록이 바뀌는 날 이 단언이 유일한 관측자가 된다.

    🔴 **랜딩은 다른 길이다.** `landing.html` 은 `base.html` 을 상속하지 않아 `applyTheme`
       이 없고, 자기 스크립트가 **로드 시점에** `localStorage['sca-theme']` 를 읽어
       `<body data-theme>` 에 건다(`landing.html` 하단 초기화 스크립트). 그래서 저장하고
       다시 불러온 뒤 `body` 쪽을 확인한다. 두 길을 여기 한 곳에 둔다 — 시험이 각자
       테마를 거는 순간 「네 테마가 같은 화면」이 조용히 돌아온다.

    Applies the theme and verifies it stuck; an unknown name silently falls back to dark,
    which would make a four-theme parametrisation measure one screen four times.
    The landing page has no `applyTheme`: it reads localStorage at load and themes `<body>`.
    """
    if page.evaluate("() => typeof applyTheme === 'function'"):
        page.evaluate("(t) => applyTheme(t)", theme)
        applied = page.evaluate("() => document.documentElement.dataset.theme")
        where = "documentElement"
    else:
        page.evaluate("(t) => localStorage.setItem('sca-theme', t)", theme)
        page.reload()
        applied = page.evaluate("() => document.body.dataset.theme")
        where = "body(랜딩)"
    assert applied == theme, (
        f"테마가 {applied!r} 로 걸렸다({where}) — {theme!r} 을 재려 했는데 다른 화면을 "
        "잰다 (`applyTheme` 이 모르는 이름을 dark 로 되돌렸는지 볼 것)")


@pytest.fixture
def admin_page(seeded_page):
    """🔴 admin 화면을 여는 «유일한» 관용구 — 세션 쿠키가 붙은 페이지.

    이 픽스처를 쓰지 않고 `/admin/*` 을 열면 GitHub OAuth 로 나가고, 그 페이지를 재게 된다
    (실측: 프로브 72조합이 github.com 을 쟀다). 쿠키를 손으로 만들지 말 것.
    """
    seeded_page.context.add_cookies([admin_session_cookie()])
    return seeded_page


@pytest.fixture
def assert_still_on_our_app():
    """🔴 «우리 앱을 재고 있는가» 판정을 픽스처로 준다.

    conftest 의 함수는 시험 파일에서 직접 import 할 수 없다(pytest 는 conftest 를
    모듈로 노출하지 않는다). 픽스처로 주면 «쓰지 않으면 눈에 띈다» — 정의만 있고
    아무도 안 쓰는 헬퍼가 되는 것을 막는다(Grok `01a08b4a` 가 그 상태를 지적했다).
    """
    return _assert_still_on_our_app


# ── 점수 정합도 표를 «채우는» 피드백 (#1639 · overview.html:366) ──────────────
#
# 🔴 `{% for range_name, data in calibration.items() %}{% if data.count > 0 %}` 는
#    양쪽 팔 모두 미관측이었다 — e2e 에 피드백이 **0건**이라 다섯 구간이 전부 0 이었고,
#    그러면 «참» 팔은 물론 «거짓» 팔도… 는 아니다. 거짓 팔은 돌았어야 한다.
#    실제로는 로그인 사용자의 `/` 만 이 표를 그리는데 e2e 의 `/` 방문이 그 표까지
#    내려가 본 적이 없었다(첫 화면 아래).
# 🔴 등급 시드가 다섯 구간을 **전부** 덮는다(95·82·68·52·30). 그래서 둘에만 심는다 —
#    다섯 다 심으면 «거짓» 팔(count == 0)이 영영 안 열린다.
# 🔴 피드백은 (analysis_id, user_id) 유니크다. 한 분석에 둘을 달려면 사용자가 둘 있어야
#    한다 — `EMPTY_USER_ID` 를 빌린다(그 사용자는 리포가 없어야 하고, 피드백은 리포를
#    만들지 않는다).
CALIBRATION_SEED = {"A": ((1, +1), (EMPTY_USER_ID, -1)), "F": ((1, +1),)}


def _seed_calibration_feedback(db_path: str, graded: dict[str, int]) -> dict[str, dict]:
    """등급 A·F 분석에 피드백을 달고 → {구간 이름: {"count": n, "up_ratio": r}}.

    돌려주는 것은 **화면이 그려야 할 값**이다. 시험은 이것과 대조한다.
    """
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    ranges = (("0-44", 0, 44), ("45-59", 45, 59), ("60-74", 60, 74),
              ("75-89", 75, 89), ("90-100", 90, 100))
    expected: dict[str, dict] = {}
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            for grade, votes in CALIBRATION_SEED.items():
                analysis_id = graded[grade]
                score = conn.execute(text("SELECT score FROM analyses WHERE id=:i"),
                                     {"i": analysis_id}).scalar()
                assert score is not None, f"{grade} 분석에 점수가 없다 — 구간을 못 정한다"
                for user_id, thumbs in votes:
                    conn.execute(text(
                        "INSERT OR IGNORE INTO analysis_feedbacks"
                        " (analysis_id, user_id, thumbs, created_at, updated_at)"
                        " VALUES (:a, :u, :t, datetime('now'), datetime('now'))"
                    ), {"a": analysis_id, "u": user_id, "t": thumbs})
                name = next(n for n, lo, hi in ranges if lo <= score <= hi)
                ups = sum(1 for _, t in votes if t > 0)
                expected[name] = {"count": len(votes), "up_ratio": ups / len(votes)}
            conn.commit()
            got = conn.execute(text("SELECT COUNT(*) FROM analysis_feedbacks")).scalar()
        wanted = sum(len(v) for v in CALIBRATION_SEED.values())
        assert got == wanted, f"피드백 {got}건 (기대 {wanted}) — 유니크 충돌이 삼켰다"
    finally:
        engine.dispose()
    # 🔴 시드가 «양쪽 팔» 을 열 수 있는지 못박는다 — 다 채우면 count == 0 팔이,
    #    아무것도 안 채우면 count > 0 팔이 안 열린다. 파생되지 않는 바닥이다.
    assert 0 < len(expected) < len(ranges), (
        f"채운 구간이 {len(expected)}/{len(ranges)} — 하나 이상 채우고 하나 이상 비워야 "
        "`overview.html:366` 의 두 팔이 다 열린다")
    return expected


@pytest.fixture(scope="session")
def calibration_feedback(live_server, graded_analyses, empty_user):
    """점수 정합도 표의 «값이 있는 구간» 과 «빈 구간» 을 동시에 만든다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_calibration_feedback(db_path, graded_analyses)
