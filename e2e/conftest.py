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


@pytest.fixture(scope="session")
def merge_history(live_server, seeded_analysis):
    """머지 이력이 있는 상태 — overview 가 실패 사유 목록 + auto-merge KPI 를 그린다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    return _seed_merge_history(db_path, seeded_analysis)


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
