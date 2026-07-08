"""tests/unit/test_worker_session_routing.py

TDD Red Phase: RLS Phase 2 — background 전용 DB 세션 분리 (옵션 A) 테스트.
TDD Red Phase: RLS Phase 2 — dedicated background DB session split (Option A) tests.

검증 대상 / Targets:
  - src/config.py: database_url_worker 필드 + postgres:// → postgresql:// validator
  - src/database.py: _build_worker_session_factory pure 함수 + WorkerSessionLocal 모듈 심볼
  - RLS listener (_set_rls_user_id_per_query) — 분리 worker engine 미등록 가드
  - background 모듈 18개 (scripts/backfill 포함) import alias 전환
    + 웹 모듈 WorkerSessionLocal 미사용 정적 가드
    + hybrid 모듈 1개 (src/auth/github.py — OAuth 콜백 upsert 만 worker 세션, RLS #2 Phase 4)

구현 전이므로 신규 기능 테스트는 실패(Red)해야 정상이다.
Most tests must fail (Red) until the implementation lands.
conftest.py 가 환경변수를 주입하므로 파일 레벨 os.environ 설정은 불필요.
conftest.py already injects env vars — no file-level os.environ setup needed.
"""
import ast
import importlib
from pathlib import Path

import pytest

# 리포 루트 파생 — 절대경로 하드코딩 금지 (test_doc_review_gate #767 학습)
# Derive repo root — never hardcode absolute paths (lesson from test_doc_review_gate #767)
_REPO_ROOT = Path(__file__).resolve().parents[2]

# background 전용 모듈 18개 (scripts/backfill 포함) — WorkerSessionLocal alias 전환 의무 대상
# 18 background-only modules (incl. scripts/backfill) — must use the WorkerSessionLocal alias
_BACKGROUND_MODULES = [
    "src/worker/pipeline.py",
    "src/webhook/providers/github.py",
    "src/webhook/providers/telegram.py",
    "src/webhook/providers/railway.py",
    "src/webhook/_helpers.py",
    "src/api/internal_cron.py",
    "src/api/hook.py",
    "src/gate/engine.py",
    "src/gate/actions/review_comment.py",
    "src/gate/actions/approve.py",
    "src/notifier/telegram.py",
    "src/notifier/slack.py",
    "src/notifier/discord.py",
    "src/notifier/email.py",
    "src/notifier/github_issue.py",
    "src/notifier/github_commit_comment.py",
    # RLS Phase 3 — Phase 4 role 전환 후 app role 의 users self-RLS 가
    # backfill 스크립트를 silent skip 시키는 것 방어 (worker 세션 경유 의무)
    # RLS Phase 3 — after the Phase 4 role switch, the app role's users self-RLS
    # would silently skip the backfill; the script must go through the worker session
    "scripts/backfill_repository_user_id.py",
    # C1 Phase 3 T3.1 — _persist_cost(claude_api_calls 비용 영속화)는 웹/백그라운드 어느 호출
    # 컨텍스트든 세션 컨텍스트 무관하게 성공해야 함(0043 RLS 정책, repo_id/user_id 설정 시
    # app.user_id 일치 요구) → worker 세션 일관 사용.
    # C1 Phase 3 T3.1 — _persist_cost (claude_api_calls cost persistence) must succeed
    # regardless of caller context (web or background), since the 0043 RLS policy requires
    # app.user_id to match once repo_id/user_id is set → always uses the worker session.
    "src/shared/claude_metrics.py",
]

# 웹 경로 명시 파일 — WorkerSessionLocal 사용 금지 대상 (api 3 파일, 전부 세션 기반).
# users(require_login)·issue_registration(get_current_user+user_id 필터)·admin(require_saas_admin):
# 모두 로그인 사용자 세션 컨텍스트가 있어 app.user_id 가 설정됨 → RLS 가 본인 행을 허용한다.
# Explicit web-path files — must NOT use WorkerSessionLocal (3 api files, all session-based).
# users / issue_registration / admin all run within a logged-in user session (app.user_id set),
# so RLS permits their own rows.
_WEB_API_MODULES = [
    "src/api/users.py",
    "src/api/issue_registration.py",
    "src/api/admin.py",
]

# 시스템 컨텍스트 API 모듈 — `require_api_key`(글로벌 키) 인증, 사용자 세션 없음.
# repos/stats/repo_report 는 cross-tenant 전체 데이터를 반환하는 시스템/관리 엔드포인트라
# Phase 4 비-BYPASSRLS app role 전환 시 `app.user_id=''` 로 RLS 가 owned 행을 은닉/차단한다.
# 따라서 background 모듈과 동일하게 `WorkerSessionLocal as SessionLocal`(BYPASSRLS) 경유 의무 —
# 현 BYPASSRLS postgres 의 cross-tenant 동작을 Phase 4 후에도 보존 (Codex mutual #2 Phase 4 갭).
# System-context API modules — authenticated by the global `require_api_key`, no user session.
# repos/stats/repo_report are system/admin endpoints returning cross-tenant data; after the Phase 4
# non-BYPASSRLS app-role switch (`app.user_id=''`) RLS would hide/block owned rows. They must route
# through `WorkerSessionLocal as SessionLocal` (BYPASSRLS) like background modules, preserving the
# current cross-tenant behavior through Phase 4 (Codex mutual #2 Phase 4 gap).
_SYSTEM_API_MODULES = [
    "src/api/repos.py",
    "src/api/stats.py",
    "src/api/repo_report.py",
]

# bare SessionLocal import 허용 웹 모듈 전수 allowlist (16 파일 — Codex R1 강화 가드).
# 신규 src 모듈이 SessionLocal 계열을 import 하면 BACKGROUND/WEB 중 한쪽에 분류 의무 —
# 미등재 시 inventory 테스트가 자동 fail (db.md WorkerSessionLocal 라우팅 규칙 페어).
# Exhaustive allowlist of web modules permitted to import bare SessionLocal (16 files).
# Any new src module importing the SessionLocal family must be classified into BACKGROUND
# or WEB — unlisted imports automatically fail the inventory test (pairs with db.md rule).
_WEB_DB_MODULES = _WEB_API_MODULES + [
    "src/auth/session.py",
    "src/auth/github.py",
    "src/ui/routes/dashboard.py",
    "src/ui/routes/actions.py",
    "src/ui/routes/settings.py",
    "src/ui/routes/admin.py",
    "src/ui/routes/repo_insights.py",
    "src/ui/routes/add_repo.py",
    "src/ui/routes/detail.py",
    "src/ui/routes/overview.py",
]

# hybrid 모듈 — bare SessionLocal(웹 RLS 경로) + WorkerSessionLocal(시스템 컨텍스트) 둘 다 import 허용.
# 같은 모듈 안에서 일부 경로는 사용자 세션(웹 RLS), 일부는 세션 없는 cross-tenant(시스템 컨텍스트)이다.
#  - src/auth/github.py: auth_callback(콜백 시점 session 부재 → users self-RLS 차단)만 worker,
#    logout(세션 존재 → 본인 행)은 bare.
#  - src/api/admin.py · src/ui/routes/admin.py: tenants(tenant_inventory)·operations(operations_kpi)는
#    cross-tenant 집계(User/Repository/Analysis/MergeAttempt) → worker(BYPASSRLS) 의무 (Phase 4 admin
#    세션 RLS under-report 방어). rls-audit(rls_coverage_summary)는 **현재 connection 의 BYPASSRLS 여부
#    진단**이라 반드시 웹 app role 세션으로 실행돼야 정확 → bare 유지(worker 로 돌리면 항상 우회=오진단).
# Hybrid modules — permitted to import BOTH bare SessionLocal (web RLS path) and WorkerSessionLocal
# (system context). Within one module some routes run under a user session (web RLS), others are
# sessionless cross-tenant (system context):
#  - src/auth/github.py: only auth_callback (no session at callback → users self-RLS blocks) uses
#    worker; logout (session present → own row) stays bare.
#  - src/api/admin.py · src/ui/routes/admin.py: tenants/operations are cross-tenant aggregates → worker
#    (BYPASSRLS) to avoid Phase 4 admin-session-RLS under-report; rls-audit diagnoses the CURRENT
#    connection's BYPASSRLS status, so it must run as the web app role (worker would always report
#    bypass = misdiagnosis) → stays bare.
# 절차: docs/runbooks/rls-role-separation.md §Phase 4.
_HYBRID_DB_MODULES = [
    "src/auth/github.py",
    "src/api/admin.py",
    "src/ui/routes/admin.py",
]

# WorkerSessionLocal alias(`as SessionLocal`) 경유 의무 모듈 전체 = background + 시스템 컨텍스트 API.
# 양쪽 모두 사용자 세션이 없어 RLS 우회(BYPASSRLS)가 필요하며 라우팅 메커니즘이 동일하다.
# All modules required to import via the WorkerSessionLocal alias = background + system-context API.
# Both lack a user session and need RLS bypass (BYPASSRLS); the routing mechanism is identical.
_WORKER_ALIAS_MODULES = _BACKGROUND_MODULES + _SYSTEM_API_MODULES

# 세션 팩토리 계열 심볼 — inventory/재바인딩 가드 대상
# Session-factory family symbols — targets of the inventory/rebinding guards
_SESSION_SYMBOLS = {"SessionLocal", "WorkerSessionLocal"}


def _read_source(rel_path: str) -> str:
    """리포 루트 기준 상대 경로의 소스 텍스트를 읽는다.
    Reads source text by repo-root-relative path."""
    return (_REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _db_import_bindings(source: str) -> list[tuple[str, str | None]]:
    """`from src.database import ...` 의 (원본 이름, alias) 쌍 전체를 수집한다.
    Collects all (original name, alias) pairs imported from src.database.

    ast 기반 — 주석/괄호/함수 내부 lazy import 모두 정확히 처리 (정규식보다 견고).
    ast-based — robust against comments, parentheses, and function-level lazy imports.
    """
    bindings: list[tuple[str, str | None]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "src.database":
            for alias in node.names:
                bindings.append((alias.name, alias.asname))
    return bindings


def _make_settings(**overrides):
    """필수 필드만 채운 Settings 직접 인스턴스화 헬퍼 — 싱글톤 우회.
    Helper to instantiate Settings directly with required fields — bypasses the singleton.

    testing.md 규칙: settings 싱글톤은 import 시점 인스턴스화라 monkeypatch.setenv 무효.
    testing.md rule: the settings singleton is built at import time, so setenv is ineffective.
    """
    from src.config import Settings
    base = {
        "database_url": "sqlite:///:memory:",
        "telegram_bot_token": "123:ABC",
        "telegram_chat_id": "-100123",
    }
    base.update(overrides)
    return Settings(**base)


# ---------------------------------------------------------------------------
# 테스트 1: config — database_url_worker 필드 + 스킴 변환 validator
# Test 1: config — database_url_worker field + scheme-conversion validator
# ---------------------------------------------------------------------------

class TestDatabaseUrlWorkerConfig:
    """database_url_worker 필드의 default + postgres:// → postgresql:// 변환 검증.
    Validates the database_url_worker default and postgres:// → postgresql:// conversion."""

    def test_worker_url_postgres_scheme_converted(self):
        # postgres:// 스킴이 postgresql:// 로 변환되어야 한다 (fix_optional_pg_url 멀티필드 validator)
        # The postgres:// scheme must be converted to postgresql:// (fix_optional_pg_url multi-field validator)
        s = _make_settings(database_url_worker="postgres://u:p@h:5432/db")
        assert s.database_url_worker == "postgresql://u:p@h:5432/db"

    def test_worker_url_unset_defaults_to_empty(self, monkeypatch):
        # 미설정 시 빈 문자열 default 이어야 한다 (현행 동작 보존 가드)
        # When unset, the default must be an empty string (preserves current behavior)
        monkeypatch.delenv("DATABASE_URL_WORKER", raising=False)
        s = _make_settings()
        assert s.database_url_worker == ""

    def test_worker_url_empty_string_passthrough(self):
        # 빈 문자열 명시 설정 시 변환 없이 그대로 반환되어야 한다 (validator 빈값 가드)
        # An explicitly empty string must pass through unchanged (validator empty guard)
        s = _make_settings(database_url_worker="")
        assert s.database_url_worker == ""

    def test_worker_url_postgresql_scheme_unchanged(self):
        # 이미 postgresql:// 스킴이면 변경 없이 유지되어야 한다 (멱등성 경계)
        # An existing postgresql:// scheme must remain unchanged (idempotency boundary)
        s = _make_settings(database_url_worker="postgresql://u:p@h:5432/db")
        assert s.database_url_worker == "postgresql://u:p@h:5432/db"

    def test_worker_url_supabase_gets_sslmode_require(self):
        # Supabase URL 이면 sslmode=require 자동 추가 — _normalize_pg_url 미러 정합
        # Supabase URLs must get sslmode=require appended — mirrors _normalize_pg_url
        s = _make_settings(
            database_url_worker="postgres://u:p@db.abc.supabase.co:5432/postgres"
        )
        assert s.database_url_worker.startswith("postgresql://")
        assert "sslmode=require" in s.database_url_worker

    def test_worker_url_reads_from_env(self, monkeypatch):
        # DATABASE_URL_WORKER 환경변수가 필드에 매핑 + 변환되어야 한다 (reload 패턴)
        # The DATABASE_URL_WORKER env var must map to the field and be converted (reload pattern)
        import src.config as cfg
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
        monkeypatch.setenv("DATABASE_URL_WORKER", "postgres://u:p@h:5432/db")
        importlib.reload(cfg)
        try:
            assert cfg.settings.database_url_worker == "postgresql://u:p@h:5432/db"
        finally:
            # 싱글톤 오염 방지 — env 원복 후 재로드 (다른 테스트 격리 보장)
            # Prevent singleton pollution — restore env and reload (isolates other tests)
            monkeypatch.delenv("DATABASE_URL_WORKER")
            importlib.reload(cfg)


# ---------------------------------------------------------------------------
# 테스트 2: _build_worker_session_factory — pure 함수 분기
# Test 2: _build_worker_session_factory — pure function branching
# ---------------------------------------------------------------------------

class TestBuildWorkerSessionFactory:
    """worker_url 유무에 따른 동일 객체 반환 / 독립 인스턴스 생성 분기 검증.
    Validates identity-return vs. independent-instance branching by worker_url."""

    def test_empty_url_returns_same_web_factory(self):
        # 빈 문자열이면 web_factory 동일 객체를 반환해야 한다 (현행 동작 보존 핵심 가드)
        # Empty string must return the exact same web_factory object (core behavior-preservation guard)
        from src.database import _build_worker_session_factory
        sentinel = object()
        assert _build_worker_session_factory("", sentinel) is sentinel

    def test_none_url_returns_same_web_factory(self):
        # None (falsy) 이어도 web_factory 동일 객체를 반환해야 한다 (방어적 경계)
        # None (falsy) must also return the same web_factory object (defensive boundary)
        from src.database import _build_worker_session_factory
        sentinel = object()
        assert _build_worker_session_factory(None, sentinel) is sentinel

    def test_nonempty_url_returns_independent_failover_factory(self):
        # non-empty URL 이면 FailoverSessionFactory 신규 인스턴스를 반환해야 한다
        # A non-empty URL must return a brand-new FailoverSessionFactory instance
        from src.database import FailoverSessionFactory, _build_worker_session_factory
        sentinel = object()
        factory = _build_worker_session_factory("sqlite:///:memory:", sentinel)
        assert isinstance(factory, FailoverSessionFactory)
        assert factory is not sentinel

    def test_nonempty_url_factory_is_single_engine_mode(self):
        # 분리 factory 는 fallback 없는 단일 엔진 모드여야 한다 (active_db == "primary")
        # The split factory must run in single-engine mode without fallback (active_db == "primary")
        from src.database import _build_worker_session_factory
        factory = _build_worker_session_factory("sqlite:///:memory:", object())
        assert factory.active_db == "primary"
        assert factory._fallback_maker is None  # pylint: disable=protected-access
        # 단일 엔진 모드 — probe 스레드 미생성 (FailoverSessionFactory 기존 계약)
        # Single-engine mode — no probe thread (existing FailoverSessionFactory contract)
        assert factory._probe_thread is None  # pylint: disable=protected-access

    def test_nonempty_url_factory_returns_usable_session(self):
        # 분리 factory() 호출은 사용 가능한 세션을 반환해야 한다 (SessionLocal() 호환)
        # Calling the split factory must return a usable session (SessionLocal() compatible)
        from src.database import _build_worker_session_factory
        factory = _build_worker_session_factory("sqlite:///:memory:", object())
        session = factory()
        try:
            assert session is not None
        finally:
            session.close()


# ---------------------------------------------------------------------------
# 테스트 3: 모듈 레벨 WorkerSessionLocal — 테스트 env 미설정 = SessionLocal 동일 객체
# Test 3: module-level WorkerSessionLocal — unset test env = identical to SessionLocal
# ---------------------------------------------------------------------------

class TestModuleLevelWorkerSessionLocal:
    """테스트 env 는 DATABASE_URL_WORKER 미설정 — 현행 동작 보존 identity 검증.
    Test env leaves DATABASE_URL_WORKER unset — verifies behavior-preserving identity."""

    def test_worker_session_local_is_session_local_when_unset(self):
        # 미설정 환경에서 WorkerSessionLocal 은 SessionLocal 동일 객체여야 한다
        # With the env unset, WorkerSessionLocal must be the exact same object as SessionLocal
        from src.database import SessionLocal, WorkerSessionLocal
        assert WorkerSessionLocal is SessionLocal


# ---------------------------------------------------------------------------
# 테스트 4: RLS listener 등록 범위 — web engine 등록 ○ / 분리 worker engine 등록 ×
# Test 4: RLS listener scope — registered on web engine, NOT on the split worker engine
# ---------------------------------------------------------------------------

class TestRlsListenerScope:
    """_set_rls_user_id_per_query listener 의 engine 별 등록 여부 검증.
    Validates per-engine registration of the _set_rls_user_id_per_query listener."""

    def test_rls_listener_registered_on_web_engine(self):
        # 모듈 레벨 web engine 에는 RLS listener 가 등록되어 있어야 한다 (현행 보존 가드)
        # The module-level web engine must keep the RLS listener registered (preservation guard)
        from sqlalchemy import event
        from src.database import engine, _set_rls_user_id_per_query
        assert event.contains(
            engine, "before_cursor_execute", _set_rls_user_id_per_query
        )

    def test_rls_listener_absent_on_separate_worker_engine(self):
        # 분리 생성된 worker engine 에는 RLS listener 가 등록되지 않아야 한다
        # (BYPASSRLS worker role 은 RLS 미평가 — SET LOCAL 불필요)
        # The separately-built worker engine must NOT have the RLS listener
        # (a BYPASSRLS worker role never evaluates RLS — SET LOCAL is unnecessary)
        from sqlalchemy import event
        from src.database import _build_worker_session_factory, _set_rls_user_id_per_query
        factory = _build_worker_session_factory("sqlite:///:memory:", object())
        worker_engine = factory._primary_engine  # pylint: disable=protected-access
        assert not event.contains(
            worker_engine, "before_cursor_execute", _set_rls_user_id_per_query
        )


# ---------------------------------------------------------------------------
# 테스트 5: 정적 라우팅 가드 — background 18 모듈 (scripts/backfill 포함) alias 전환 (회귀 차단 핵심)
# Test 5: static routing guard — 18 background modules (incl. scripts/backfill) use the alias
#         (core regression guard)
# ---------------------------------------------------------------------------

class TestBackgroundModulesUseWorkerAlias:
    """worker alias 의무 모듈(_WORKER_ALIAS_MODULES = background 18 + 시스템 API 3)이
    `WorkerSessionLocal as SessionLocal` 로 import 하는지 정적 검증.
    Statically verifies every worker-alias module (_WORKER_ALIAS_MODULES = 18 background +
    3 system API) imports via the `WorkerSessionLocal as SessionLocal` alias."""

    @pytest.mark.parametrize("rel_path", _WORKER_ALIAS_MODULES)
    def test_background_module_imports_worker_alias(self, rel_path):
        # 각 background 모듈은 `WorkerSessionLocal as SessionLocal` import 를 포함해야 한다
        # (모듈 심볼명 유지 — 기존 patch 대상 `src.worker.pipeline.SessionLocal` 등 불변)
        # Each background module must contain a `WorkerSessionLocal as SessionLocal` import
        # (module symbol name preserved — existing patch targets remain valid)
        bindings = _db_import_bindings(_read_source(rel_path))
        assert ("WorkerSessionLocal", "SessionLocal") in bindings, (
            f"{rel_path}: `from src.database import WorkerSessionLocal as SessionLocal` "
            "import 가 없습니다 / import is missing"
        )

    @pytest.mark.parametrize("rel_path", _WORKER_ALIAS_MODULES)
    def test_background_module_has_no_bare_sessionlocal_import(self, rel_path):
        # 각 background 모듈은 bare `from src.database import SessionLocal` 을 가지면 안 된다
        # (Worker 미경유 web 세션 직접 import = RLS Phase 2 라우팅 우회 회귀)
        # Each background module must NOT have a bare `from src.database import SessionLocal`
        # (importing the web session directly bypasses the RLS Phase 2 routing)
        bindings = _db_import_bindings(_read_source(rel_path))
        bare = [(name, asname) for name, asname in bindings if name == "SessionLocal"]
        assert not bare, (
            f"{rel_path}: web SessionLocal 직접 import 발견 {bare} — "
            "WorkerSessionLocal alias 경유 의무 / must go through the WorkerSessionLocal alias"
        )


# ---------------------------------------------------------------------------
# 테스트 6: 정적 라우팅 가드 — 웹 모듈 WorkerSessionLocal 사용 금지
# Test 6: static routing guard — web modules must not use WorkerSessionLocal
# ---------------------------------------------------------------------------

class TestWebModulesDoNotUseWorkerSession:
    """웹 경로 모듈 (api 6 + ui/routes glob + auth glob) 의 WorkerSessionLocal 부재 검증.
    Verifies web-path modules (6 api files + ui/routes glob + auth glob) never mention
    WorkerSessionLocal."""

    def _web_module_paths(self) -> list[Path]:
        """웹 모듈 경로 목록을 수집한다 (명시 api 6 + glob 2종).
        Collects web module paths (6 explicit api files + 2 globs)."""
        paths = [_REPO_ROOT / rel for rel in _WEB_API_MODULES]
        paths += sorted((_REPO_ROOT / "src" / "ui" / "routes").glob("*.py"))
        paths += sorted((_REPO_ROOT / "src" / "auth").glob("*.py"))
        return paths

    def test_web_module_glob_found_files(self):
        # glob 이 빈 결과면 가드 자체가 무력화되므로 최소 파일 수를 단언한다 (silent pass 방지)
        # An empty glob would neuter the guard — assert a minimum file count (prevents silent pass)
        paths = self._web_module_paths()
        # api 3(세션 기반) + ui/routes(다수) + auth(다수) — 실측 ~18, 하한 8 로 silent pass 방지
        # 3 session-based api + many ui/routes + many auth — actual ~18, floor 8 prevents silent pass
        assert len(paths) >= 8, f"웹 모듈 수집 실패 / web module collection failed: {paths}"

    def test_web_modules_do_not_mention_worker_session_local(self):
        # 웹 모듈 소스에 WorkerSessionLocal 문자열이 존재하면 안 된다 (RLS 적용 경로 보존)
        # — 단 hybrid 모듈(_HYBRID_DB_MODULES, src/auth/github.py)은 명시 예외:
        #   OAuth 콜백 upsert 의 시스템 컨텍스트 worker 세션 사용이 의도된 설계다.
        # Web module sources must not contain the WorkerSessionLocal string (keeps RLS path intact)
        # — except hybrid modules (_HYBRID_DB_MODULES, src/auth/github.py) where the OAuth callback's
        #   system-context worker session is intentional.
        violations = []
        for path in self._web_module_paths():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if rel in _HYBRID_DB_MODULES:
                continue
            if "WorkerSessionLocal" in path.read_text(encoding="utf-8"):
                violations.append(rel)
        assert not violations, (
            f"웹 모듈에서 WorkerSessionLocal 사용 발견 / found in web modules: {violations}"
        )


# ---------------------------------------------------------------------------
# 테스트 7: 전수 inventory 가드 — src 전체 SessionLocal 계열 import 분류 강제
# Test 7: exhaustive inventory guard — every src import of the SessionLocal family
#         must be classified (Codex R1 강화 — 신규 모듈 누락 자동 fail)
# ---------------------------------------------------------------------------

def _iter_src_py() -> list:
    """src/ 하위 전체 .py 파일 경로를 수집한다 (database.py 자신 포함).
    Collects every .py file under src/ (including database.py itself)."""
    return sorted((_REPO_ROOT / "src").rglob("*.py"))


def _iter_guarded_py() -> list:
    """src 전체 + _BACKGROUND_MODULES 의 non-src(scripts) 파일 — 재바인딩/모듈객체 가드 공통 대상.
    Every src .py plus the non-src (scripts) entries of _BACKGROUND_MODULES — shared
    scan set for the rebinding and module-object-import guards.

    inventory(테스트 7)는 src 전용 bijection 을 유지하지만, 정책 도메인에 편입된 scripts
    파일은 재바인딩/모듈객체 우회 가드도 동일하게 받아야 한다 (가드 커버리지 비대칭 차단).
    The inventory (test 7) keeps its src-only bijection, but scripts files adopted into
    the policy domain must receive the rebinding/module-object guards too.
    """
    extra = [
        _REPO_ROOT / rel for rel in _BACKGROUND_MODULES if not rel.startswith("src/")
    ]
    return _iter_src_py() + sorted(extra)


class TestSessionFactoryInventory:
    """src 전체에서 SessionLocal 계열 import 를 전수 수집해 분류 누락을 차단한다.
    Sweeps every src module for SessionLocal-family imports and blocks unclassified ones.

    수동 목록(_BACKGROUND_MODULES/_WEB_DB_MODULES) 밖의 신규 모듈이 SessionLocal 계열을
    import 하면 본 테스트가 fail — BACKGROUND(worker alias) / WEB(bare) 분류를 강제한다.
    A new module outside the manual lists importing the family fails this test,
    forcing an explicit BACKGROUND (worker alias) vs WEB (bare) classification.
    """

    def _inventory(self) -> dict:
        """파일별 (원본 이름, alias) import 목록 — SessionLocal 계열만.
        Per-file (name, alias) import list — SessionLocal family only."""
        result = {}
        for path in _iter_src_py():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            bindings = [
                (name, asname)
                for name, asname in _db_import_bindings(path.read_text(encoding="utf-8"))
                if name in _SESSION_SYMBOLS
            ]
            if bindings:
                result[rel] = bindings
        return result

    def test_every_worker_alias_importer_is_listed_background(self):
        # WorkerSessionLocal 을 import 하는 src 파일 집합 == _BACKGROUND_MODULES 의 src 부분집합 (양방향)
        # scripts/ 항목은 src 전수 스캔(_iter_src_py) 범위 밖 — parametrize 정적 가드
        # (test_background_module_imports_worker_alias) 가 직접 검증한다 (RLS Phase 3)
        # The set of src files importing WorkerSessionLocal == the src/ subset of
        # _BACKGROUND_MODULES (bijection). scripts/ entries live outside the src sweep
        # (_iter_src_py) — the parametrized static guard covers them directly (RLS Phase 3)
        importers = {
            rel for rel, bindings in self._inventory().items()
            if any(name == "WorkerSessionLocal" for name, _ in bindings)
        }
        # hybrid 모듈(_HYBRID_DB_MODULES, src/auth/github.py)도 WorkerSessionLocal 을 import 한다 —
        # 단 alias(`as SessionLocal`) 없이 자체 이름으로 (콜백 upsert 전용). expected 에 포함.
        # Hybrid modules also import WorkerSessionLocal (under its own name, callback-upsert only) —
        # include them in the expected set.
        expected = {m for m in _WORKER_ALIAS_MODULES if m.startswith("src/")} | set(_HYBRID_DB_MODULES)
        assert importers == expected, (
            "WorkerSessionLocal import 파일 집합이 _WORKER_ALIAS_MODULES(src 부분집합) + _HYBRID 와 불일치 — "
            f"누락/잉여: {importers ^ expected} / "
            "신규 background/시스템 API 모듈은 _BACKGROUND_MODULES/_SYSTEM_API_MODULES, "
            "hybrid 는 _HYBRID_DB_MODULES 등재 의무 (db.md 규칙)"
        )

    def test_every_bare_sessionlocal_importer_is_listed_web(self):
        # bare SessionLocal 을 import 하는 src 파일 집합 == _WEB_DB_MODULES 집합 (양방향)
        # The set of src files importing bare SessionLocal == _WEB_DB_MODULES (bijection)
        importers = {
            rel for rel, bindings in self._inventory().items()
            if any(name == "SessionLocal" for name, _ in bindings)
        }
        assert importers == set(_WEB_DB_MODULES), (
            "bare SessionLocal import 파일 집합이 _WEB_DB_MODULES 와 불일치 — "
            f"누락/잉여: {importers ^ set(_WEB_DB_MODULES)} / "
            "신규 모듈은 BACKGROUND(worker alias)/WEB(bare) 분류 의무 (db.md 규칙)"
        )


# ---------------------------------------------------------------------------
# 테스트 8: 재바인딩 금지 가드 — alias 우회 차단 (Codex R1 강화)
# Test 8: rebinding ban guard — blocks alias bypass via reassignment (Codex R1)
# ---------------------------------------------------------------------------

class TestNoSessionFactoryRebinding:
    """src 전체에서 SessionLocal/WorkerSessionLocal 재할당을 금지한다 (database.py 제외).
    Bans any reassignment of SessionLocal/WorkerSessionLocal across src (except database.py).

    올바른 alias import 후 `SessionLocal = src.database.SessionLocal` 재바인딩으로
    worker 라우팅을 우회하는 형태를 ast Assign/AnnAssign/AugAssign 대상 검사로 차단.
    Blocks bypassing the worker routing via post-import rebinding by inspecting
    Assign/AnnAssign/AugAssign targets in the AST.
    """

    @staticmethod
    def _assigned_names(node) -> set:
        """할당 노드의 대상 이름 집합을 수집한다 (Name id + Attribute attr).
        Collects assigned target names from an assignment node (Name ids + Attribute attrs)."""
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        names = set()
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr)
        return names

    def test_no_rebinding_of_session_factories_in_src(self):
        # database.py(정의부) 외 어떤 가드 대상 파일도 SessionLocal 계열을 재할당하면 안 된다
        # (src 전체 + scripts background 모듈 — _iter_guarded_py)
        # No guarded file other than database.py (the definition site) may reassign the
        # family (all of src plus scripts background modules — _iter_guarded_py)
        violations = []
        for path in _iter_guarded_py():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if rel == "src/database.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                hit = self._assigned_names(node) & _SESSION_SYMBOLS
                if hit:
                    violations.append(f"{rel}:{node.lineno} {sorted(hit)}")
        assert not violations, (
            "SessionLocal 계열 재바인딩 발견 — worker 라우팅 우회 금지 / "
            f"rebinding bypasses worker routing: {violations}"
        )


# ---------------------------------------------------------------------------
# 테스트 9: 모듈 객체 import 금지 가드 — `import src.database` 우회 차단 (Codex R2)
# Test 9: module-object import ban — blocks the `import src.database` bypass (Codex R2)
# ---------------------------------------------------------------------------

class TestNoDatabaseModuleObjectImport:
    """src 전체에서 database 모듈 객체 import 를 금지한다 (attribute 우회 차단).
    Bans importing the database module object anywhere in src (blocks attribute bypass).

    `import src.database as db; db.SessionLocal()` 형태는 ImportFrom inventory 가
    못 잡는다 — 모듈 객체 import 자체를 금지해 attribute 경유 우회를 원천 차단.
    src 실측 기존 사용처 0건 (정합 비용 없음) — DB 접근은 항상
    `from src.database import <symbol>` 형식만 허용 (inventory/재바인딩 가드 페어).
    `import src.database as db; db.SessionLocal()` escapes the ImportFrom inventory —
    banning the module-object import closes the attribute-access bypass at the source.
    """

    def test_no_module_object_import_of_database(self):
        # plain `import src.database[.* as X]` + `from src import database` 전면 금지
        # (src 전체 + scripts background 모듈 — _iter_guarded_py)
        # Bans both plain `import src.database[.* as X]` and `from src import database`
        # (all of src plus scripts background modules — _iter_guarded_py)
        violations = []
        for path in _iter_guarded_py():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "src.database" or alias.name.startswith("src.database."):
                            violations.append(f"{rel}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module == "src":
                    for alias in node.names:
                        if alias.name == "database":
                            violations.append(f"{rel}:{node.lineno} from src import database")
        assert not violations, (
            "database 모듈 객체 import 금지 — attribute 경유 세션 우회 차단 / "
            f"module-object import enables an attribute bypass: {violations}"
        )


# ---------------------------------------------------------------------------
# 테스트 10: hybrid 모듈 계약 가드 — auth/github.py 는 두 세션 팩토리를 모두 import
# Test 10: hybrid module contract guard — auth/github.py imports both session factories
#          (RLS #2 Phase 4 P1 blocker — OAuth 콜백 upsert 만 worker 세션 경유)
# ---------------------------------------------------------------------------

class TestHybridAuthModuleContract:
    """hybrid 모듈(src/auth/github.py)이 bare SessionLocal + WorkerSessionLocal 을 모두 import 하고
    WorkerSessionLocal 을 alias 없이 자체 이름으로 가져오는지 검증한다.
    Verifies the hybrid module (src/auth/github.py) imports both bare SessionLocal and
    WorkerSessionLocal, with WorkerSessionLocal under its own (non-aliased) name.

    logout(웹 RLS 경로) 은 bare SessionLocal, OAuth 콜백 upsert(시스템 컨텍스트) 는
    WorkerSessionLocal 를 써야 한다 — 한쪽 import 가 사라지면 둘 중 한 경로가 깨진다.
    logout (web RLS path) needs bare SessionLocal; the OAuth callback upsert (system context)
    needs WorkerSessionLocal — dropping either import breaks one of the two paths.
    """

    @pytest.mark.parametrize("rel_path", _HYBRID_DB_MODULES)
    def test_hybrid_module_imports_both_factories(self, rel_path):
        # hybrid 모듈은 bare SessionLocal + WorkerSessionLocal(alias 없음) 둘 다 import 해야 한다
        # The hybrid module must import both bare SessionLocal and non-aliased WorkerSessionLocal
        bindings = _db_import_bindings(_read_source(rel_path))
        assert ("SessionLocal", None) in bindings, (
            f"{rel_path}: bare `from src.database import SessionLocal` 가 없습니다 (logout 웹 RLS 경로) / "
            "missing bare SessionLocal import (logout web RLS path)"
        )
        assert ("WorkerSessionLocal", None) in bindings, (
            f"{rel_path}: `from src.database import WorkerSessionLocal` (alias 없음) 가 없습니다 "
            "(OAuth 콜백 upsert worker 세션) / missing non-aliased WorkerSessionLocal import "
            "(OAuth callback upsert worker session)"
        )

    @pytest.mark.parametrize("rel_path", _HYBRID_DB_MODULES)
    def test_hybrid_module_does_not_alias_worker_as_session(self, rel_path):
        # WorkerSessionLocal 을 `as SessionLocal` 로 alias 하면 logout 의 웹 RLS 경로가 worker 로
        # 잘못 라우팅된다 — alias 금지 (background 모듈과 달리 hybrid 는 두 심볼 구분 유지 의무)
        # Aliasing WorkerSessionLocal as SessionLocal would misroute logout's web RLS path to the
        # worker — banned (unlike background modules, the hybrid must keep the two symbols distinct)
        bindings = _db_import_bindings(_read_source(rel_path))
        assert ("WorkerSessionLocal", "SessionLocal") not in bindings, (
            f"{rel_path}: WorkerSessionLocal 을 `as SessionLocal` 로 alias 금지 (logout 오라우팅 위험) / "
            "must not alias WorkerSessionLocal as SessionLocal (would misroute logout)"
        )
