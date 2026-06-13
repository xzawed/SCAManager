"""telegram_commands 단위 테스트 — TDD Red → Green.
Unit tests for telegram_commands — TDD Red → Green.

In-memory SQLite 자체 fixture 사용, now 의존성 주입으로 시간 고정.
Uses self-contained in-memory SQLite fixture; injects fixed `now` for time control.
"""
# pylint: disable=redefined-outer-name
import os

# src 모듈 임포트 전 환경변수 주입 필수
# Inject env vars before any src.* import that triggers Settings() loading
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.notifier.telegram_commands import (
    CmdCallback,
    _NOT_CONNECTED_MSG,
    handle_message_command,
    parse_cmd_callback,
)


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite DB
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션을 제공한다.
    Provide an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _make_user(
    db: Session,
    *,
    github_id: str = "gh-1",
    github_login: str = "tester",
    email: str = "t@example.com",
    display_name: str = "Tester",
    telegram_user_id: str | None = None,
    telegram_otp: str | None = None,
    telegram_otp_expires_at: datetime | None = None,
) -> User:
    """테스트용 User 레코드를 DB에 저장하고 반환한다.
    Create and persist a test User record.
    """
    user = User(
        github_id=github_id,
        github_login=github_login,
        email=email,
        display_name=display_name,
        telegram_user_id=telegram_user_id,
        telegram_otp=telegram_otp,
        telegram_otp_expires_at=telegram_otp_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_repo(db: Session, user_id: int, full_name: str = "owner/repo") -> Repository:
    """테스트용 Repository 레코드를 DB에 저장하고 반환한다.
    Create and persist a test Repository record.
    """
    repo = Repository(full_name=full_name, user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int = 80,
    offset_hours: int = 0,
) -> Analysis:
    """테스트용 Analysis 레코드를 생성하는 헬퍼.
    Helper to create a test Analysis record.
    """
    created = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    analysis = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{score}-{offset_hours}-{id(object())}",
        score=score,
        grade="B",
        created_at=created,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# ---------------------------------------------------------------------------
# Test: parse_cmd_callback
# ---------------------------------------------------------------------------


def test_parse_cmd_callback_returns_none_for_gate_prefix():
    """gate: 접두사 데이터는 None을 반환해야 한다.
    gate: prefix data must return None.
    """
    result = parse_cmd_callback("gate:approve:1:abc")
    assert result is None


def test_parse_cmd_callback_returns_none_for_unknown_prefix():
    """알 수 없는 접두사는 None을 반환해야 한다.
    Unknown prefix must return None.
    """
    result = parse_cmd_callback("unknown:verb:1:token")
    assert result is None


def test_parse_cmd_callback_parses_cmd_with_id():
    """cmd:<verb>:<id>:<token> 형식을 올바르게 파싱해야 한다.
    Must correctly parse cmd:<verb>:<id>:<token> format.
    """
    result = parse_cmd_callback("cmd:stats:42:abc")
    assert result is not None
    assert isinstance(result, CmdCallback)
    assert result.verb == "stats"
    assert result.payload_id == 42
    assert result.token == "abc"


def test_parse_cmd_callback_parses_connect_without_id():
    """cmd:connect:<token> 형식(id 없음)을 올바르게 파싱해야 한다.
    Must correctly parse cmd:connect:<token> format (no id).
    """
    result = parse_cmd_callback("cmd:connect:abc")
    assert result is not None
    assert result.verb == "connect"
    assert result.payload_id is None
    assert result.token == "abc"


def test_parse_cmd_callback_returns_none_for_non_integer_id():
    """id 필드가 정수로 변환되지 않으면 None을 반환해야 한다.
    Must return None if the id field cannot be converted to int.
    """
    result = parse_cmd_callback("cmd:stats:notanint:token")
    assert result is None


def test_parse_cmd_callback_returns_none_for_malformed_data():
    """파트 수가 맞지 않는 잘못된 형식은 None을 반환해야 한다.
    Malformed data with wrong number of parts must return None.
    """
    result = parse_cmd_callback("cmd:only_two")
    assert result is None


# ---------------------------------------------------------------------------
# Test: handle_message_command — /connect
# ---------------------------------------------------------------------------


def test_handle_connect_accepts_valid_otp(db):
    """유효한 OTP로 /connect 시 연결 성공 메시지를 반환해야 한다.
    /connect with a valid OTP must return a success message.
    """
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    _make_user(
        db,
        github_id="gh-otp",
        email="otp@example.com",
        display_name="OtpUser",
        telegram_otp="123456",
        telegram_otp_expires_at=future,
    )

    result = handle_message_command(db, "tg-999", "/connect 123456")

    assert "OtpUser" in result
    assert "연결" in result or "linked" in result.lower()


def test_handle_connect_escapes_html_in_display_name(db):
    """🔴 C27: 봇 응답(parse_mode=HTML)의 사용자 제어 display_name HTML 이스케이프.

    display_name 에 <,>,& 가 있으면 raw 노출 시 (a) 자기 채팅 서식 주입 (b) malformed HTML →
    Telegram API 400 → 봇 silent 실패(가용성). 분석-알림 경로(escape)와 대칭.
    """
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    _make_user(
        db, github_id="gh-xss", email="xss@example.com",
        display_name="Evil<b>Name</b>", telegram_otp="654321",
        telegram_otp_expires_at=future,
    )
    result = handle_message_command(db, "tg-xss", "/connect 654321")
    assert "Evil&lt;b&gt;Name&lt;/b&gt;" in result   # 이스케이프됨
    assert "<b>" not in result                       # raw 태그 미노출


def test_handle_connect_rejects_expired_otp(db):
    """만료된 OTP는 오류 메시지를 반환해야 한다 (find_by_otp가 None).
    Expired OTP must return an error message (find_by_otp returns None).
    """
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    _make_user(
        db,
        github_id="gh-expired",
        email="expired@example.com",
        display_name="Expired",
        telegram_otp="expired1",
        telegram_otp_expires_at=past,
    )

    result = handle_message_command(db, "tg-expired", "/connect expired1")

    assert "OTP" in result
    assert "잘못" in result or "Invalid" in result or "expired" in result.lower()


def test_handle_connect_rejects_double_mapping(db):
    """이미 연결된 Telegram ID로 재연결 시도 시 에러 메시지를 반환해야 한다.
    Re-linking with an already-mapped Telegram ID must return an error message.
    """
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    # 먼저 tg-already를 다른 사용자에게 연결
    # Link tg-already to another user first
    _make_user(
        db,
        github_id="gh-existing",
        email="existing@example.com",
        display_name="Existing",
        telegram_user_id="tg-already",
    )
    # OTP를 가진 새 사용자
    # New user with OTP
    _make_user(
        db,
        github_id="gh-new",
        email="new@example.com",
        display_name="NewUser",
        telegram_otp="newcode1",
        telegram_otp_expires_at=future,
    )

    # set_telegram_user_id가 IntegrityError → ValueError를 발생시키는 상황을 모사
    # Simulate set_telegram_user_id raising ValueError due to IntegrityError
    with patch(
        "src.notifier.telegram_commands.user_repo.set_telegram_user_id",
        side_effect=ValueError("already mapped"),
    ):
        result = handle_message_command(db, "tg-already", "/connect newcode1")

    assert "이미" in result or "already" in result.lower()


def test_handle_connect_requires_otp_argument(db):
    """/connect 명령에 OTP 인수가 없으면 사용법 안내를 반환해야 한다.
    /connect without OTP argument must return usage instructions.
    """
    result = handle_message_command(db, "tg-noarg", "/connect")
    assert "사용법" in result or "Usage" in result


# ---------------------------------------------------------------------------
# Test: handle_message_command — /connect OTP brute-force rate-limit (C12)
# ---------------------------------------------------------------------------


def test_handle_connect_blocks_after_repeated_wrong_otp(db):
    """동일 telegram_user_id 의 반복된 잘못된 OTP 시도는 한도 초과 시 차단된다.
    Repeated wrong-OTP guesses from the same telegram_user_id are blocked past the cap.
    """
    from src.constants import OTP_MAX_FAILED_ATTEMPTS

    # 한도까지는 "잘못된 OTP" 응답 (find_by_otp None → 실패 기록)
    # Up to the cap: each returns the invalid-OTP message and records a failure
    for _ in range(OTP_MAX_FAILED_ATTEMPTS):
        result = handle_message_command(db, "tg-brute", "/connect 000000")
        assert "OTP" in result

    # 한도 초과 — rate-limit 메시지 (DB 조회조차 하지 않음)
    # Past the cap — rate-limit message (no DB lookup performed)
    blocked = handle_message_command(db, "tg-brute", "/connect 000000")
    assert "OTP" not in blocked  # invalid_otp 가 아닌 별도 메시지
    assert "많" in blocked or "many" in blocked.lower() or "시도" in blocked


def test_handle_connect_block_is_per_telegram_user(db):
    """한 사용자가 차단돼도 다른 telegram_user_id 는 정상 시도 가능하다.
    Blocking one user does not affect a different telegram_user_id.
    """
    from src.constants import OTP_MAX_FAILED_ATTEMPTS

    for _ in range(OTP_MAX_FAILED_ATTEMPTS + 1):
        handle_message_command(db, "tg-attacker", "/connect 999999")

    # 차단된 공격자
    blocked = handle_message_command(db, "tg-attacker", "/connect 999999")
    assert "many" in blocked.lower() or "많" in blocked or "시도" in blocked

    # 다른 사용자는 정상적으로 invalid_otp 응답을 받는다
    # A different user still gets the normal invalid-OTP response
    other = handle_message_command(db, "tg-innocent", "/connect 111111")
    assert "OTP" in other


def test_handle_connect_success_resets_failure_counter(db):
    """잘못된 시도 후 유효 OTP 로 성공하면 실패 카운터가 초기화된다.
    A successful connect after some wrong tries resets the failure counter.
    """
    from src.constants import OTP_MAX_FAILED_ATTEMPTS

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    _make_user(
        db,
        github_id="gh-reset",
        email="reset@example.com",
        display_name="ResetUser",
        telegram_otp="555555",
        telegram_otp_expires_at=future,
    )

    # 한도 미만의 실패 (한도-1)
    # Fewer failures than the cap (cap - 1)
    for _ in range(OTP_MAX_FAILED_ATTEMPTS - 1):
        handle_message_command(db, "tg-reset", "/connect 000000")

    # 유효 OTP 성공 → 카운터 초기화
    # Valid OTP succeeds → counter cleared
    ok = handle_message_command(db, "tg-reset", "/connect 555555")
    assert "ResetUser" in ok

    # 초기화되었으므로 다시 한도-1 회 실패해도 차단되지 않는다
    # Counter cleared → another (cap - 1) failures still not blocked
    for _ in range(OTP_MAX_FAILED_ATTEMPTS - 1):
        result = handle_message_command(db, "tg-reset", "/connect 000000")
        assert "OTP" in result  # 여전히 invalid_otp (차단 아님)


def test_handle_connect_already_linked_preserves_failure_counter(db):
    """🔴 C12 NG fix (Codex mutual): 유효 OTP 를 맞췄으나 set 이 already_linked
    (ValueError)로 실패하면 연결 실패이므로 실패 카운터를 초기화하지 않는다.
    A valid OTP that fails at set (already linked) must NOT reset the counter —
    clear() runs only after set_telegram_user_id succeeds.
    """
    from src.constants import OTP_MAX_FAILED_ATTEMPTS
    from src.notifier.telegram_commands import _otp_limiter

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    _make_user(
        db,
        github_id="gh-linked",
        email="linked@example.com",
        display_name="LinkedUser",
        telegram_otp="777777",
        telegram_otp_expires_at=future,
    )

    # 한도-1 회 실패 누적
    # Accumulate (cap - 1) failures
    for _ in range(OTP_MAX_FAILED_ATTEMPTS - 1):
        handle_message_command(db, "tg-linked", "/connect 000000")
    assert len(_otp_limiter._failures.get("tg-linked", [])) == OTP_MAX_FAILED_ATTEMPTS - 1

    # 유효 OTP 이지만 set 이 ValueError → already_linked 응답 (연결 실패)
    # Valid OTP but set raises ValueError → already_linked response (connect failed)
    with patch(
        "src.notifier.telegram_commands.user_repo.set_telegram_user_id",
        side_effect=ValueError("already mapped"),
    ):
        result = handle_message_command(db, "tg-linked", "/connect 777777")
    assert "이미" in result or "already" in result.lower()

    # 카운터 미초기화 — 여전히 한도-1 (clear 가 set 성공 후에만 실행되므로)
    # Counter preserved — still (cap - 1), because clear runs only after set succeeds
    assert len(_otp_limiter._failures.get("tg-linked", [])) == OTP_MAX_FAILED_ATTEMPTS - 1


# ---------------------------------------------------------------------------
# Test: handle_message_command — /stats
# ---------------------------------------------------------------------------


def test_handle_message_not_connected_prompts_connect(db):
    """미연결 사용자의 /stats 요청은 연결 안내 메시지를 반환해야 한다.
    /stats from a disconnected user must return the connect prompt.
    """
    result = handle_message_command(db, "tg-unknown", "/stats owner/repo")
    assert result == _NOT_CONNECTED_MSG


def test_handle_stats_requires_repo_argument(db):
    """/stats에 리포 인수가 없으면 사용법 안내를 반환해야 한다.
    /stats without repo argument must return usage instructions.
    """
    _make_user(db, telegram_user_id="tg-norepo")
    result = handle_message_command(db, "tg-norepo", "/stats")
    assert "사용법" in result or "Usage" in result


def test_handle_stats_returns_not_found_for_unknown_repo(db):
    """등록되지 않은 리포 요청 시 에러 메시지를 반환해야 한다.
    Unknown repo request must return an error message.
    """
    _make_user(db, telegram_user_id="tg-stat1")
    result = handle_message_command(db, "tg-stat1", "/stats nonexistent/repo")
    assert "없습니다" in result or "not found" in result.lower()


def test_handle_stats_returns_no_data_when_no_analyses(db):
    """분석 데이터가 없는 리포는 데이터 없음 메시지를 반환해야 한다.
    Repo with no analyses must return a no-data message.
    """
    user = _make_user(db, telegram_user_id="tg-empty")
    _make_repo(db, user.id, "owner/empty")

    result = handle_message_command(db, "tg-empty", "/stats owner/empty")
    assert "없습니다" in result or "No analysis" in result


def test_handle_stats_returns_summary_for_valid_repo(db):
    """분석 있는 리포 /stats 요청 시 통계 메시지를 반환해야 한다.
    /stats for a repo with analyses must return a statistics message.
    """
    user = _make_user(db, telegram_user_id="tg-stat2")
    repo = _make_repo(db, user.id, "owner/statrepo")

    # 최근 7일 이내 분석 5건 생성 (moving_average는 min_samples=5 기본값)
    # Create 5 analyses within the last 7 days (moving_average defaults min_samples=5)
    for i in range(5):
        _make_analysis(db, repo.id, score=80 + i, offset_hours=i * 10)

    result = handle_message_command(db, "tg-stat2", "/stats owner/statrepo")

    assert "owner/statrepo" in result
    assert "5" in result  # 분석 건수 / analysis count


# ---------------------------------------------------------------------------
# Test: handle_message_command — /settings
# ---------------------------------------------------------------------------


def test_handle_settings_lists_repos(db):
    """/settings 요청 시 등록된 리포지토리 목록을 반환해야 한다.
    /settings must return the list of registered repositories.
    """
    user = _make_user(db, telegram_user_id="tg-settings1")
    _make_repo(db, user.id, "owner/repo-alpha")
    _make_repo(db, user.id, "owner/repo-beta")

    result = handle_message_command(db, "tg-settings1", "/settings")

    assert "owner/repo-alpha" in result
    assert "owner/repo-beta" in result


def test_handle_settings_returns_empty_message_when_no_repos(db):
    """/settings 요청 시 등록된 리포가 없으면 안내 메시지를 반환해야 한다.
    /settings with no repos must return a guidance message.
    """
    _make_user(db, telegram_user_id="tg-settings-empty")
    result = handle_message_command(db, "tg-settings-empty", "/settings")
    assert "없습니다" in result or "No repositories" in result


def test_handle_settings_not_connected_prompts_connect(db):
    """미연결 사용자의 /settings 요청은 연결 안내 메시지를 반환해야 한다.
    /settings from disconnected user must return the connect prompt.
    """
    result = handle_message_command(db, "tg-nosettings", "/settings")
    assert result == _NOT_CONNECTED_MSG


# ---------------------------------------------------------------------------
# Test: handle_message_command — unknown commands
# ---------------------------------------------------------------------------


def test_unknown_command_returns_help(db):
    """알 수 없는 명령은 도움말 메시지를 반환해야 한다.
    Unknown command must return a help message.
    """
    _make_user(db, telegram_user_id="tg-unknown-cmd")
    result = handle_message_command(db, "tg-unknown-cmd", "/unknown")
    assert "/stats" in result
    assert "/settings" in result
    assert "/connect" in result


def test_unknown_command_not_connected_prompts_connect(db):
    """미연결 사용자의 알 수 없는 명령은 연결 안내 메시지를 반환해야 한다.
    Unknown command from disconnected user must return the connect prompt.
    """
    result = handle_message_command(db, "tg-disconnected", "/unknown")
    assert result == _NOT_CONNECTED_MSG


def test_dispatcher_returns_not_connected_constant_directly():
    """회귀 가드(#888 / CodeQL #516): 디스패처가 `_NOT_CONNECTED_MSG` 상수를 직접 반환해야 한다.
    Regression guard (#888 / CodeQL #516): the dispatcher must return the
    `_NOT_CONNECTED_MSG` constant directly.

    위 3개 테스트는 반환'값' 동등(== _NOT_CONNECTED_MSG)만 검증하므로, 디스패처를 inline
    `get_text(...)` 로 되돌려도(값이 글자 그대로 동일) 통과한다 → 모듈 상수가 src 에서 고아화돼
    `py/unused-global-variable`(#516) 가 재발해도 pytest 는 green. CodeQL 은 비동기 Code
    Scanning(머지 후 alert)이라 PR-CI 에서 못 잡는다. 따라서 상수 '심볼' 사용을 ast 로 직접 단언.
    The three tests above only assert value-equality, so reverting the dispatcher to an inline
    `get_text(...)` (byte-identical value) would still pass while the module global re-orphans
    and CodeQL #516 resurfaces — and async Code Scanning can't gate it at PR-CI. So assert the
    symbol usage via ast.
    """
    import ast
    from pathlib import Path

    import src.notifier.telegram_commands as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    returns_constant = any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Name)
        and node.value.id == "_NOT_CONNECTED_MSG"
        for node in ast.walk(ast.parse(source))
    )
    assert returns_constant, (
        "디스패처가 _NOT_CONNECTED_MSG 를 inline get_text 로 되돌리면 상수가 고아화돼 "
        "CodeQL py/unused-global-variable(#516) 가 재발한다 — 상수 직접 반환 유지 의무 / "
        "dispatcher must keep returning the _NOT_CONNECTED_MSG constant"
    )
