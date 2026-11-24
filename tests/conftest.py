import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 사이클 65 fix — pre-existing 5 fail (사이클 62~64 누적 보류) 정밀 조사 결과:
# `.env` 가 셸 환경에 export 된 환경 (예: direnv, 또는 사용자 셸 config) 에서는
# `os.environ.setdefault` 가 무시되어 운영 토큰 (TELEGRAM_BOT_TOKEN 등) 이 settings 로 들어감.
# 단위 테스트의 하드코딩 HMAC 토큰 ("123:ABC" 기반) 과 mismatch → 5 fail.
# 직접 set 으로 변경 — 모든 환경에서 일관 (CI 도 동일 값 명시 — `.github/workflows/ci.yml` L51).
# Fix for cycle 65: replaced setdefault with direct assignment so test env vars always win
# over .env exports — prevents 5 pre-existing flaky fails caused by HMAC token mismatch.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test_secret"
os.environ["GITHUB_TOKEN"] = "ghp_test"
os.environ["TELEGRAM_BOT_TOKEN"] = "123:ABC"
os.environ["TELEGRAM_CHAT_ID"] = "-100123"
os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"
os.environ["GITHUB_CLIENT_ID"] = "test-github-client-id"
os.environ["GITHUB_CLIENT_SECRET"] = "test-github-client-secret"
os.environ["SESSION_SECRET"] = "test-session-secret-32-chars-long!"
# Claude 모델 기본값 명시 — .env.example 이 빈값으로 설정되어 Python default 를 override 하는 버그 방지
# Explicitly set Claude model defaults — .env.example sets empty values that would override Python defaults
os.environ["CLAUDE_REVIEW_MODEL"] = "claude-sonnet-5"
os.environ["CLAUDE_INSIGHT_MODEL"] = "claude-haiku-4-5"
# 테스트 환경 = 개발 모드 명시 opt-out — API_KEY 미설정 시 REST API fail-closed(503) 기본값을
# 우회해 기존 endpoint 테스트(repos/stats 등 키 없이 200 의존)를 보존한다.
# 🔴 음성검증 마스킹 완화 (GAP-5, 2026-06-23 회고 P2): 이 전역 opt-out 은 모든 endpoint 테스트를
#   무인증으로 돌려 fail-closed 회귀를 가릴 수 있다. 마스킹은 tests/unit/api/test_auth.py 의 전용
#   가드가 완화한다 — api_auth_disabled=False 로 명시 override 후 503 단언:
#   test_api_key_empty_default_fail_closed_503 / test_api_key_empty_fail_closed_regardless_of_base_url
#   / test_api_key_empty_default_ignores_provided_key_503. 이 가드 삭제 시 마스킹 재노출 주의.
# Test env = explicit dev opt-out — bypass the fail-closed(503) default for unset API_KEY so existing
# endpoint tests (repos/stats relying on keyless 200) keep passing.
# 🔴 Negative-verification masking mitigation (GAP-5): this global opt-out runs every endpoint test
#   keyless, which could hide a fail-closed regression. The masking is mitigated by the dedicated guards
#   in tests/unit/api/test_auth.py — they override api_auth_disabled=False and assert 503
#   (test_api_key_empty_default_fail_closed_503 / ..._regardless_of_base_url / ..._ignores_provided_key_503).
#   Removing those guards re-exposes the masking.
os.environ["API_AUTH_DISABLED"] = "1"
# 🔴 개발 PC 의 `.env` 가 단위 테스트로 새어 들어온다(회고 2026-09-16 K12). `build_settings()` 는 `.env` 를
#    읽어, 위 목록에 없는 자격증명·연결 대상(`OPENAI_API_KEY`·`TOKEN_ENCRYPTION_KEY`·DB 보조 URL 등)은
#    이 PC 의 값으로 돌았다 — CI 는 `.env` 가 없어 기본값 `""` 로 돈다. 그래서 로컬만 다르게 동작하고,
#    벤더 키면 실제 호출이다. 운영 모드 스위치(`APP_BASE_URL`·`ENVIRONMENT`)까지 «전부» CI 와 같은 `""`
#    로 못박는다. 목록은 `tests/unit/scripts/test_e2e_harness_neutralises_credentials.py` 가 `Settings`
#    에서 파생해 강제한다(e2e 하네스와 같은 가드).
# A developer .env leaks into unit tests: pin every credential, routing target and production switch.
for _name in ("OPENAI_API_KEY", "TELEGRAM_WEBHOOK_SECRET", "API_KEY", "INTERNAL_CRON_API_KEY",
              "TOKEN_ENCRYPTION_KEY", "N8N_WEBHOOK_SECRET", "SMTP_HOST", "SMTP_USER", "SMTP_PASS",
              "VERIFIER_BASE_URL", "DATABASE_URL_FALLBACK", "DATABASE_URL_WORKER",
              "MIGRATION_DATABASE_URL", "APP_BASE_URL", "ENVIRONMENT"):
    os.environ[_name] = ""
# 벨트+멜빵 — 키가 어떤 경로로든 살아나도 Anthropic 호출이 기계 밖으로 나가지 않는다.
# Belt and braces: even if a key survives, Anthropic calls cannot leave the machine.
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:1"

from src.main import app
from src.ui.routes import add_repo as _add_repo_module
from src.webhook import router as webhook_router


@pytest.fixture(autouse=True)
def _clear_webhook_secret_cache():
    webhook_router._webhook_secret_cache.clear()
    yield
    webhook_router._webhook_secret_cache.clear()


@pytest.fixture(autouse=True)
def _clear_user_repos_cache():
    # GitHub 리포 TTL 캐시 — 테스트 간 격리 보장
    # Clear GitHub repos TTL cache to ensure test isolation.
    _add_repo_module._user_repos_cache.clear()
    yield
    _add_repo_module._user_repos_cache.clear()


@pytest.fixture(autouse=True)
def _clear_otp_attempt_limiter():
    # Telegram OTP brute-force 슬라이딩 윈도우 (C12) — 모듈 레벨 싱글톤, 테스트 간 격리
    # Telegram OTP brute-force sliding window (C12) — module-level singleton, isolate per test
    from src.notifier.telegram_commands import _otp_limiter  # pylint: disable=import-outside-toplevel
    _otp_limiter._failures.clear()
    yield
    _otp_limiter._failures.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate limiter 인메모리 카운터를 테스트마다 초기화한다 — 테스트 간 rate limit 누적 방지.
    Reset in-memory rate limiter counters between tests to prevent cross-test leakage.
    """
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel
    yield
    try:
        limiter._storage.reset()  # limits.MemoryStorage.reset() — 모든 카운터 초기화
    except Exception:  # pylint: disable=broad-except
        pass


@pytest.fixture
def client():
    return TestClient(app)


# ── skip 집합 게이트 — `pytest tests/` 의 skip 은 커밋된 목록과 양방향으로 같아야 한다 (원장 #1917 M06) ──
#
# #1857 뒤 CI 의 이 잡에서 slither pragma 판정 시험 34건이 «semantic_version 부재» 로 skip 이 됐는데
# 어떤 게이트도 잡지 않았다 — 시험 수 대조는 «본문 + skip == junit» 합만 보았다. e2e 와 같은 관용구
# (`e2e/conftest.py` 의 `--e2e-strict-skips` · `e2e/SKIP_ALLOWLIST`)로, 숫자가 아니라 **집합**을 본다.
# 목록 밖 skip 이 생기면 red, 목록에 있는데 skip 되지 않아도 red 다(낡은 예외는 게이트를 넓힌다).
# 항목은 파라미터를 뗀 nodeid 이고, 줄 주석에 «어디서 도는가» 를 적는다. 판정은 `tests/_skip_gate.py` 의 순수 함수다.
# opt-in 불리언 플래그(`--strict-skips`)라 로컬 부분 실행에는 영향이 없고 CI 만 건다.
# Gate the skip *set* of `pytest tests/` against a committed allowlist, both directions (as e2e does).


def pytest_addoption(parser):
    parser.addoption(
        "--strict-skips", action="store_true",
        help="skip 집합이 tests/SKIP_ALLOWLIST 와 다르면 세션을 실패시킨다(CI 전용 · 공허화 차단).",
    )


def _where(report, root: Path) -> str:
    """skip 이 난 자리와 사유(`-rs` 와 같은 줄 번호 · 리포 상대 경로) — 실패 메시지에서 목록 줄로 옮길 수 있게."""
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        path, lineno, reason = longrepr
        try:
            path = Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            path = str(path).replace("\\", "/")
        return f"{path}:{lineno}: {reason}"
    return ""


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001  # pylint: disable=unused-argument
    if not session.config.getoption("--strict-skips"):
        return
    from tests._skip_gate import base_nodeid, judge, read_allowlist  # pylint: disable=import-outside-toplevel

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    observed: dict[str, str] = {}
    root = Path(str(session.config.rootpath)).resolve()
    for report in reporter.stats.get("skipped", []):
        observed.setdefault(base_nodeid(report.nodeid), _where(report, root))
    collected = {base_nodeid(item.nodeid) for item in getattr(session, "items", [])}
    for msg in judge(observed, collected, read_allowlist()):
        reporter.write_line(msg, red=True)
        session.exitstatus = 1
