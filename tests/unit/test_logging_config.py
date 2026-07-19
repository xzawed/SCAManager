"""애플리케이션 로깅 설정 정합 (2026-07-19 — INFO 로그가 출시 이래 전부 소실된 문제).

🔴 사고: 앱이 `logging.basicConfig`/`dictConfig` 를 **한 번도 호출하지 않아** 모든
`logging.getLogger(__name__).info(...)` 가 핸들러 없는 root 로 갔다. Python 의 last-resort
핸들러는 **WARNING 이상만** stderr 로 내보내므로 앱의 INFO 로그는 전부 소실됐다
(Railway 로그에 uvicorn·alembic 만 보이던 이유 — 그 둘은 각자 핸들러를 설정한다).

실측 영향 / Measured impact:
- `retention sweep — purged expired_cache=N` 같은 운영 관측 라인이 한 번도 보이지 않았다
- owed 원장의 검증 절차("Railway cron 로그에서 sweep 실행 확인")가 **물리적으로 불가능**했다
- 신규 인앱 스케줄러(#1099)의 `scheduler started — 5 jobs` 도 보이지 않아 배포 검증이 막혔다
The app never configured logging, so every INFO log was dropped; only uvicorn/alembic were visible.
"""
import copy
import io
import logging
import logging.config

from uvicorn.config import LOGGING_CONFIG as UVICORN_LOGGING_CONFIG

from src.logging_config import _MARKER, _RedactSecretsFilter, configure_logging


def test_configure_logging_attaches_root_handler():
    """🔴 root 에 핸들러가 붙는다 — 없으면 last-resort 가 WARNING 이상만 내보낸다."""
    root = logging.getLogger()
    original = list(root.handlers)
    try:
        root.handlers.clear()
        configure_logging()
        assert root.handlers, "root 핸들러 미부착 — INFO 로그가 계속 소실된다"
    finally:
        root.handlers[:] = original


def test_app_logger_emits_info_after_configuration():
    """🔴 긍정 통제 — 앱 모듈 logger 가 INFO 를 실제로 통과시킨다.

    이 단언이 죽으면 운영 관측(스케줄러·retention sweep 등)이 다시 조용히 사라진다.
    """
    root = logging.getLogger()
    original, original_level = list(root.handlers), root.level
    try:
        root.handlers.clear()
        configure_logging()
        assert logging.getLogger("src.scheduler").isEnabledFor(logging.INFO)
        assert logging.getLogger("src.services.cron_service").isEnabledFor(logging.INFO)
    finally:
        root.handlers[:] = original
        root.setLevel(original_level)


def test_configure_logging_is_idempotent():
    """중복 호출해도 핸들러가 누적되지 않는다 — 매 호출마다 로그가 배로 늘면 안 된다."""
    root = logging.getLogger()
    original = list(root.handlers)
    try:
        root.handlers.clear()
        configure_logging()
        count = len(root.handlers)
        configure_logging()
        assert len(root.handlers) == count, "중복 호출 시 핸들러 누적 — 로그 중복 출력"
    finally:
        root.handlers[:] = original


def test_debug_is_not_enabled_by_default():
    """🔴 부정 통제 — 기본은 INFO. DEBUG 가 켜지면 운영 로그에 비밀이 섞일 위험이 커진다."""
    root = logging.getLogger()
    original, original_level = list(root.handlers), root.level
    try:
        root.handlers.clear()
        configure_logging()
        assert not logging.getLogger("src.scheduler").isEnabledFor(logging.DEBUG)
    finally:
        root.handlers[:] = original
        root.setLevel(original_level)


def test_is_configured_false_before_and_true_after(logging_isolation):
    """🔴 `is_configured()` 계약 — 설정 전 False, 설정 후 True.

    이 술어가 alembic/env.py 의 fileConfig 가드 판정 기준이다. 뒤집히면 (a) 항상 True →
    `make migrate` 로그 소실, (b) 항상 False → 인프로세스 마이그레이션이 앱 로깅 파괴.
    This predicate drives the fileConfig guard in alembic/env.py; inverting it either silences the
    alembic CLI or lets in-process migrations wipe application logging.
    """
    # 지연 import — 미구현(TDD Red) 단계에서 이 파일의 나머지 테스트까지 collection error 로
    # 죽이지 않기 위함. 구현 후에도 동작은 동일하다.
    # Local import so the TDD-Red phase does not turn the whole file into a collection error.
    from src.logging_config import is_configured  # pylint: disable=import-outside-toplevel

    root = logging.getLogger()
    # 앱 미설정 상태 재현 — conftest 의 `src.main` import 가 이미 configure_logging() 을 돌렸다.
    # Reproduce the unconfigured state: conftest's src.main import already ran configure_logging().
    root.handlers[:] = [h for h in root.handlers if not getattr(h, _MARKER, False)]
    assert is_configured() is False, (
        "marker 핸들러가 없는데 is_configured() 가 True — 가드가 항상 skip 으로 판정해 "
        "alembic CLI(`make migrate`) 로그가 사라진다."
    )

    configure_logging()

    assert is_configured() is True, (
        "configure_logging() 후에도 is_configured() 가 False — 가드가 항상 fileConfig 를 "
        "호출해 인프로세스 마이그레이션이 앱 로깅을 파괴한다."
    )


def test_is_configured_detects_marker_handler_only(logging_isolation):
    """🔴 부정 통제 — 무관한 핸들러(예: pytest·uvicorn)만 있으면 False 여야 한다.

    "root 에 핸들러가 하나라도 있으면 True" 로 구현하면, alembic CLI 단독 실행 시에도 사실상
    항상 True 가 되어(파이썬 런타임/서드파티가 핸들러를 붙이는 경우) fileConfig 가 영영 skip 된다.
    Implementing this as "any handler at all" would make the CLI path skip fileConfig forever.
    """
    from src.logging_config import is_configured  # pylint: disable=import-outside-toplevel

    root = logging.getLogger()
    root.handlers[:] = [logging.NullHandler()]

    assert is_configured() is False, (
        "marker 없는 제3자 핸들러를 앱 설정으로 오판 — is_configured() 는 _MARKER 속성만 봐야 한다."
    )


def test_main_configures_logging_at_import():
    """🔴 배선 단언 — main 이 실제로 호출해야 운영에 적용된다(모듈만 있으면 dead code)."""
    import src.main

    # 🔴 `# noqa: F401` 은닉 금지 (testing.md) — 실제 참조로 'used' 를 만든다.
    # import 는 부수효과(configure_logging 호출)가 목적이지만, 참조가 있어야 flake8·CodeQL
    # 양쪽에서 used 로 인식되고 import 가 사라지면 loud-fail 한다.
    # No noqa-hidden import: an actual reference keeps it 'used' for both flake8 and CodeQL.
    assert hasattr(src.main, "app"), "src.main 로드 실패 — 배선 검증 불가"

    root = logging.getLogger()
    assert root.handlers, "src.main import 후에도 root 핸들러 없음 — configure_logging 미배선"


# ---------------------------------------------------------------------------
# 시크릿 리댁션 회귀 가드 (2026-07-19 P0 — Telegram 봇 토큰이 운영 로그에 평문 유출)
# Secret redaction regression guards
#
# 🔴 사고: #1102 가 앱 로깅을 복구하자마자 Railway 운영 로그에 아래 형태가 5건 나타났다.
#     INFO [httpx] HTTP Request: POST https://api.telegram.org/bot<토큰>/sendMessage "..."
# Telegram API 는 **토큰을 URL 경로에** 넣는 설계이고 `httpx` 는 INFO 레벨에서 요청 URL 전문을
# 로깅한다. 로그가 죽어 있던 동안 잠복해 있다가 로깅 복구와 함께 활성화된 유출 경로다.
# `src/shared/log_safety.py::sanitize_for_log` 는 로그 인젝션(CR/LF) 전용이라 시크릿
# 리댁션 기능이 **없다** — 즉 이 사고 시점의 방어 수단은 0이었다.
# Telegram puts the bot token in the URL path and httpx logs full request URLs at INFO, so
# restoring application logging immediately started leaking the token in production logs.
#
# 방어는 2계층이며 아래 테스트가 각각을 독립적으로 잠근다 / two independent layers:
#   계층 1 = 서드파티 URL 로깅 차단 (`httpx` 로거 WARNING)  → test_httpx_logger_*
#   계층 2 = 리댁션 필터 (심층 방어, 우리 코드 실수도 포함) → test_*_redacted / _preserved
# ---------------------------------------------------------------------------

# 🔴 명백한 더미만 사용 — 실제 토큰 형태는 gitleaks pre-commit 훅이 차단한다.
# Obvious dummy only: a realistic token shape would be blocked by the gitleaks pre-commit hook.
_FAKE_BOT_TOKEN = "123456:FAKE_TOKEN_FOR_TEST"
_FAKE_TELEGRAM_URL = f"https://api.telegram.org/bot{_FAKE_BOT_TOKEN}/sendMessage"


class _RecordCapture(logging.Filter):
    """핸들러를 통과한 LogRecord 를 그대로 보관하는 프로브 필터.
    A probe filter that keeps every LogRecord which reached the handler.

    리댁션 필터 **뒤에** 부착하므로 record 의 사후 상태(msg·args)를 관찰할 수 있다.
    Attached after the redaction filter, so it observes the post-redaction record state.
    """

    def __init__(self):
        super().__init__()
        self.records = []

    def filter(self, record):
        self.records.append(record)
        return True


def _fresh_configured_handler():
    """앱 미설정 상태를 재현한 뒤 configure_logging() 이 만든 핸들러를 StringIO 로 돌린다.
    Reset to the unconfigured state, then point the freshly configured handler at a StringIO.

    🔴 **포맷된 최종 출력**을 검사하기 위한 장치다. `record.msg` 만 보면 필터가 핸들러에
    실제로 부착됐는지(= 운영에서 동작하는지) 검증되지 않는다 — 예컨대 필터를 root **로거**에
    붙이면 하위 로거에서 전파된 레코드는 걸러지지 않는데, msg 만 보는 테스트는 이를 놓친다.
    🔴 We assert on formatted handler output, not record.msg: only the former proves the filter is
    actually wired into the handler (a filter on the root *logger* would miss propagated records).
    """
    root = logging.getLogger()
    # conftest 의 `src.main` import 가 이미 configure_logging() 을 돌렸다 — 그 핸들러를 걷어내
    # 새 핸들러를 만들게 한다(기존 핸들러의 stream 을 건드려 테스트 밖으로 새는 것을 방지).
    # conftest already configured logging; drop that handler so a fresh, disposable one is built.
    root.handlers[:] = [h for h in root.handlers if not getattr(h, _MARKER, False)]
    configure_logging()

    handler = next((h for h in root.handlers if getattr(h, _MARKER, False)), None)
    assert handler is not None, "configure_logging() 후 marker 핸들러 없음 — 출력 검증 불가"

    stream = io.StringIO()
    handler.setStream(stream)
    capture = _RecordCapture()
    handler.addFilter(capture)
    return stream, capture


def test_telegram_bot_token_is_redacted_from_handler_output(logging_isolation):
    """🔴 핵심 — 봇 토큰이 포함된 URL 을 로깅해도 **최종 출력에 토큰이 없다**.

    이 단언이 죽으면 운영 로그(Railway·수집기·백업)에 Telegram 봇 토큰이 평문으로 남는다.
    토큰 보유자는 봇을 완전히 탈취(메시지 발신·수신·게이트 콜백 위조)할 수 있다.
    If this dies, the bot token lands in production logs in plain text and anyone with log
    access can fully take over the bot.
    """
    stream, _ = _fresh_configured_handler()

    # 운영에서 실제로 나온 httpx 라인 형태를 그대로 재현. 여기서는 **완성된 메시지**(args 없음)
    # 경로를 덮는다 — args 경로는 test_redaction_applies_to_lazy_percent_format_args 담당.
    # Replays the real production line shape via the pre-formatted path (no args); the lazy-args
    # path is covered separately so the two tests fail for different implementation defects.
    logging.getLogger("tests.redaction_probe").info(
        f'HTTP Request: POST {_FAKE_TELEGRAM_URL} "HTTP/1.1 200 OK"'
    )
    out = stream.getvalue()

    assert out, "핸들러 출력이 비었다 — 로깅 자체가 동작하지 않아 리댁션 검증 불가"
    assert _FAKE_BOT_TOKEN not in out, (
        f"봇 토큰이 로그 출력에 평문으로 남았다 — 운영 로그 유출 재발.\n출력: {out!r}"
    )
    assert "FAKE_TOKEN_FOR_TEST" not in out, (
        f"토큰 시크릿 부분이 로그 출력에 남았다 — 부분 마스킹은 유출 차단이 아니다.\n출력: {out!r}"
    )


def test_redaction_preserves_url_structure_for_operability(logging_isolation):
    """🔴 마스킹 형태 — 도메인/경로 구조는 남고 토큰만 사라진다 (운영 판독성 보존).

    라인 전체를 지우거나 `***` 로 통째 치환하면 유출은 막히지만 "어느 API 가 몇 번 호출됐나"
    라는 운영 관측이 함께 죽는다. 유출 차단과 판독성은 양립해야 한다.
    Blanket-wiping the line would stop the leak but also destroy operational observability;
    the domain and path must survive so operators can still read the call.
    """
    stream, _ = _fresh_configured_handler()

    logging.getLogger("tests.redaction_probe").info(
        f'HTTP Request: POST {_FAKE_TELEGRAM_URL} "HTTP/1.1 200 OK"'
    )
    out = stream.getvalue()

    assert "api.telegram.org/bot***" in out, (
        f"마스킹 형태 불일치 — `api.telegram.org/bot***` 가 없다. 도메인/경로가 통째로 "
        f"사라지면 운영에서 호출 대상을 판독할 수 없다.\n출력: {out!r}"
    )
    assert "/sendMessage" in out, (
        f"경로 꼬리(`/sendMessage`)가 소실 — 어떤 API 를 호출했는지 판독 불가.\n출력: {out!r}"
    )


def test_redaction_applies_to_lazy_percent_format_args(logging_isolation):
    """🔴 `%s` lazy 포맷 경로 방어 — args 로 넘어온 토큰도 마스킹된다.

    `record.msg` 만 검사하는 리댁션은 이 경로를 통째로 놓친다: `logger.info("sent to %s", url)`
    에서 msg 는 `"sent to %s"` 라 패턴에 걸리지 않고, 토큰은 `record.args` 안에 있다가
    포맷 시점에 출력으로 새어나간다. httpx 를 포함한 대부분의 라이브러리가 이 형태를 쓴다.
    A redaction that inspects record.msg alone misses this entirely — the token lives in
    record.args and only surfaces at format time. Most libraries (httpx included) log this way.
    """
    stream, _ = _fresh_configured_handler()

    logging.getLogger("tests.redaction_probe").info("sent to %s", _FAKE_TELEGRAM_URL)
    out = stream.getvalue()

    assert _FAKE_BOT_TOKEN not in out, (
        f"lazy `%s` 포맷 경로에서 토큰이 유출됐다 — 필터가 record.getMessage() 가 아니라 "
        f"record.msg 만 검사하고 있다.\n출력: {out!r}"
    )
    assert "api.telegram.org/bot***" in out, (
        f"lazy 포맷 경로에서 마스킹 형태 불일치.\n출력: {out!r}"
    )


def test_non_secret_record_passes_through_untouched(logging_isolation):
    """🔴 부정 통제 — 토큰이 없는 일반 로그는 원문 그대로, `record.args` 도 보존된다.

    필터가 무해함을 단언한다. 매 레코드를 무조건 `record.msg = getMessage()` 로 평탄화하면
    (a) lazy % 포맷 이점이 사라지고 (b) `%` 를 포함한 메시지가 재포맷 시 깨지며
    (c) args 에 의존하는 구조화 로깅 소비자가 조용히 망가진다. 변경이 있을 때만 손대야 한다.
    Asserts the filter is inert on clean records: unconditionally flattening every record would
    kill lazy formatting, corrupt messages containing '%', and break structured-log consumers.
    """
    stream, capture = _fresh_configured_handler()

    logging.getLogger("tests.redaction_probe").info(
        "analysis complete repo=%s score=%s", "owner/repo", 87
    )
    out = stream.getvalue()

    assert "analysis complete repo=owner/repo score=87" in out, (
        f"비-시크릿 로그가 변형됐다 — 필터가 무해하지 않다.\n출력: {out!r}"
    )
    assert capture.records, "레코드가 핸들러에 도달하지 않았다 — 검증 불가"
    record = capture.records[-1]
    assert record.msg == "analysis complete repo=%s score=%s", (
        f"변경이 없는데 record.msg 를 평탄화했다 — lazy % 포맷 계약 위반.\n실제: {record.msg!r}"
    )
    assert record.args == ("owner/repo", 87), (
        f"변경이 없는데 record.args 를 비웠다 — args 의존 소비자가 조용히 깨진다.\n"
        f"실제: {record.args!r}"
    )


def test_httpx_logger_is_silenced_at_info(logging_isolation):
    """🔴 계층 1 — `configure_logging()` 이 httpx 로거를 WARNING 으로 올려 URL 로깅을 끈다.

    유출의 근원은 httpx 가 INFO 레벨에서 요청 URL **전문**을 찍는 것이다. 리댁션 필터(계층 2)는
    심층 방어일 뿐 — 신규 시크릿 URL 패턴은 정규식에 등재되기 전까지 그대로 새므로, 서드파티의
    URL 로깅 자체를 끄는 계층 1 이 1차 통제다. 앱 자체 관측은
    `src.shared.stage_metrics`·`merge_metrics` 가 이미 담당하므로 손실이 없다.
    Layer 1 is the primary control: the redaction filter only masks patterns already known to the
    regex, so third-party URL logging must be off at the source. App-side observability is
    unaffected (stage_metrics / merge_metrics already cover it).
    """
    # 이전 테스트/`src.main` import 의 잔여 설정을 지우고 configure_logging() 이 직접 설정하는지
    # 검증한다 — 미리 WARNING 인 상태에서 통과하면 뮤테이션(설정 제거)을 탐지하지 못한다.
    # Reset first so the test proves configure_logging() sets it, rather than passing on leftovers.
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.NOTSET)

    stream, _ = _fresh_configured_handler()

    assert httpx_logger.level == logging.WARNING, (
        f"httpx 로거 레벨이 WARNING 이 아니다(실제: {httpx_logger.level}) — httpx 가 INFO 로 "
        f"요청 URL 전문을 계속 찍는다."
    )

    httpx_logger.info('HTTP Request: POST %s "HTTP/1.1 200 OK"', _FAKE_TELEGRAM_URL)

    assert stream.getvalue() == "", (
        f"httpx INFO 레코드가 출력됐다 — 계층 1 차단 실패.\n출력: {stream.getvalue()!r}"
    )


def test_httpx_warning_still_redacted_by_filter(logging_isolation):
    """🔴 계층 1+2 결합 — 계층 1 을 통과하는 httpx WARNING/ERROR 도 토큰이 마스킹된다.

    계층 1 은 INFO 만 막는다. httpx 는 재시도·타임아웃·4xx 상황에서 WARNING 이상으로도
    **같은 URL** 을 찍으므로, 실패 시나리오(=사고 조사 시 로그를 가장 많이 뒤지는 순간)에는
    계층 2 만이 유일한 방어선이다. 두 계층 중 하나만 있으면 이 경로가 뚫린다.
    Layer 1 only silences INFO; httpx still logs the same URL at WARNING+ on retries/timeouts,
    which is precisely when logs get scrutinized — layer 2 is the only defense on that path.
    """
    stream, _ = _fresh_configured_handler()

    logging.getLogger("httpx").warning("retrying %s after timeout", _FAKE_TELEGRAM_URL)
    out = stream.getvalue()

    assert out, "httpx WARNING 이 출력되지 않았다 — 오류 관측까지 죽었다(계층 1 과잉 차단)"
    assert _FAKE_BOT_TOKEN not in out, (
        f"httpx WARNING 경로로 토큰이 유출됐다 — 계층 2 필터가 이 경로를 덮지 못한다.\n"
        f"출력: {out!r}"
    )


# ---------------------------------------------------------------------------
# 후속 P0 — #1104 리댁션이 **불완전**했던 3 결함의 회귀 가드 (2026-07-19)
# Follow-up P0: regression guards for the three defects #1104 left open.
#
# #1104 는 `_RedactSecretsFilter` 를 넣고 "2계층 봉인"을 선언했으나 5+1 회고(168 에이전트)가
# P0 로 반박했고 실측 재현으로 확정됐다:
#     --- msg 경로 토큰 유출: False   (마스킹 성공)
#     --- exc_info 경로 토큰 유출: True (트레이스백 원문 노출)
#     RuntimeError: Client error '401 Unauthorized' for url
#                   'https://api.telegram.org/bot<토큰>/sendMessage'
#
# 결함 3종 / three measured defects:
#   D1. `filter()` 가 `record.getMessage()` 만 치환 → `exc_info` 트레이스백·`stack_info` 미커버.
#       예외 **문자열**에 URL 이 박히는 httpx `raise_for_status()` 가 정확히 이 경로다.
#   D2. 필터가 **root 핸들러**에만 붙었는데 uvicorn 로거는 자체 핸들러 + `propagate=False` →
#       uvicorn 레코드는 **구조적으로 root 에 도달하지 않는다**. 가드된 적 없는 백그라운드
#       태스크 예외를 uvicorn 이 `exc_info` 로 로깅하므로 **이 축이 실제 운영 유출 경로**다.
#   D3. `_SECRET_URL_PATTERNS` 가 telegram 1개뿐 → Slack/Discord webhook URL 전문(=credential
#       그 자체)이 평문으로 남는다.
#
# 🔴 이 블록의 테스트는 서로 **다른 결함에서 실패**하도록 축을 분리했다 (한 테스트가 세 결함을
# 동시에 덮으면 어느 것이 회귀했는지 진단 불가).
# Each test below fails for a distinct defect so a regression is diagnosable.
# ---------------------------------------------------------------------------

# 🔴 명백한 더미만 — 실제 시크릿 형태는 gitleaks pre-commit 훅이 차단한다.
# Obvious dummies only; realistic secret shapes are blocked by the gitleaks pre-commit hook.
_FAKE_SLACK_SECRET = "XXXXSLACKSECRET"
_FAKE_SLACK_URL = f"https://hooks.slack.com/services/T00FAKE/B00FAKE/{_FAKE_SLACK_SECRET}"
_FAKE_DISCORD_SECRET = "XXXXDISCORDSECRET"
_FAKE_DISCORD_URL = f"https://discord.com/api/webhooks/123456789/{_FAKE_DISCORD_SECRET}"


def _marker_handler():
    """`configure_logging()` 이 root 에 붙인 핸들러를 돌려준다.
    Return the handler configure_logging() attached to root.
    """
    handler = next(
        (h for h in logging.getLogger().handlers if getattr(h, _MARKER, False)), None
    )
    assert handler is not None, "marker 핸들러 없음 — 출력 검증 불가"
    return handler


def _configured_uvicorn_handler():
    """운영과 **동일한 순서**로 uvicorn 로깅 + 앱 로깅을 세우고 uvicorn 핸들러를 StringIO 로 돌린다.
    Reproduce production ordering (uvicorn dictConfig, then app configure_logging).

    🔴 순서가 계약의 일부다: uvicorn 은 `Config.__init__` 에서 `configure_logging()`(dictConfig)
    를 돌리고, 앱 모듈(`src.main`)은 그 **뒤에** `config.load()` 로 import 된다. 즉 운영에서는
    dictConfig 가 먼저다 — 따라서 우리 `configure_logging()` 이 **이미 존재하는** uvicorn
    핸들러를 찾아 필터를 부착해야 한다.
    Ordering is part of the contract: uvicorn's dictConfig runs first (Config.__init__), and the
    app module is imported afterwards (config.load) — so configure_logging() must attach its filter
    to uvicorn handlers that already exist.

    🔴 `logging_isolation` 없이 호출 금지 — `dictConfig` 는 `_clearExistingHandlers()` 로
    전역 핸들러 레지스트리를 비우고 기존 핸들러를 close 한다(pytest caplog 포함).
    Never call without the logging_isolation fixture: dictConfig wipes the global handler registry.
    """
    # deepcopy — dictConfig 는 전달된 dict 를 in-place 로 변형한다(`()` 팩토리 해석 등).
    # uvicorn 의 모듈 전역 상수를 오염시키면 이후 테스트/운영 import 가 깨진다.
    # deepcopy: dictConfig mutates the mapping in place; never let it corrupt uvicorn's global.
    logging.config.dictConfig(copy.deepcopy(UVICORN_LOGGING_CONFIG))

    # 앱 미설정 상태 재현 — conftest 의 `src.main` import 가 이미 configure_logging() 을 돌렸다.
    # Reproduce the pre-app state; conftest's src.main import already configured logging.
    root = logging.getLogger()
    root.handlers[:] = [h for h in root.handlers if not getattr(h, _MARKER, False)]
    configure_logging()

    uv = logging.getLogger("uvicorn")
    assert uv.handlers, "uvicorn 로거에 핸들러 없음 — dictConfig 재현 실패(테스트 전제 붕괴)"
    handler = uv.handlers[0]
    stream = io.StringIO()
    handler.setStream(stream)
    return stream, handler


def test_exception_traceback_is_redacted_from_handler_output(logging_isolation):
    """🔴 D1 핵심 — `logger.exception()` 트레이스백 **안**의 토큰이 최종 출력에서 마스킹된다.

    이것이 실측으로 확인된 유출 경로다. httpx `raise_for_status()` 는 요청 URL 을 **예외 메시지
    문자열**에 박아 넣으므로(`Client error '401 Unauthorized' for url '<토큰 URL>'`), 로그 라인의
    msg 가 아무리 깨끗해도 트레이스백이 토큰을 통째로 노출한다. `record.getMessage()` 만 치환하는
    필터는 이 축을 **전혀 건드리지 않는다**.
    This is the measured leak: httpx bakes the request URL into the exception *message*, so a
    filter that only rewrites record.getMessage() leaves the token fully exposed in the traceback.
    """
    stream, _ = _fresh_configured_handler()

    try:
        # httpx 의 raise_for_status() 가 만드는 메시지 형태를 그대로 재현.
        # Replays the exact message shape produced by httpx's raise_for_status().
        raise RuntimeError(f"Client error '401 Unauthorized' for url '{_FAKE_TELEGRAM_URL}'")
    except RuntimeError:
        logging.getLogger("tests.redaction_probe").exception("telegram send failed")

    out = stream.getvalue()

    assert "Traceback (most recent call last)" in out, (
        f"트레이스백이 출력되지 않았다 — exc_info 축을 검증할 수 없다(테스트 전제 붕괴).\n"
        f"출력: {out!r}"
    )
    assert _FAKE_BOT_TOKEN not in out, (
        f"🔴 exc_info 트레이스백으로 봇 토큰이 평문 유출됐다 — 필터가 record.getMessage() 만 "
        f"치환하고 exc_info/exc_text 를 덮지 않는다.\n출력: {out!r}"
    )
    assert "FAKE_TOKEN_FOR_TEST" not in out, (
        f"토큰 시크릿 부분이 트레이스백에 남았다 — 부분 마스킹은 유출 차단이 아니다.\n출력: {out!r}"
    )
    assert "api.telegram.org/bot***" in out, (
        f"트레이스백에서 마스킹 형태 불일치 — 라인을 통째로 지우면 사고 조사가 불가능해진다.\n"
        f"출력: {out!r}"
    )


def test_stack_info_is_redacted_from_handler_output(logging_isolation):
    """🔴 D1 형제 축 — `record.stack_info` 안의 토큰도 마스킹된다.

    `Formatter.format()` 은 msg·exc_text 와 **독립적으로** `record.stack_info` 를 출력에 덧붙인다
    (`logger.x(..., stack_info=True)` 경로). exc_text 만 처리하고 stack_info 를 빠뜨리면 이 축이
    그대로 뚫린다.
    Formatter.format() appends record.stack_info independently of msg/exc_text, so handling only
    exc_text leaves this axis open.

    🔴 합성 LogRecord 를 쓰는 이유: 실제 `stack_info=True` 스택에 토큰이 들어가려면 **이 파일의
    소스 라인**에 토큰 리터럴이 있어야 해 테스트가 소스 레이아웃에 종속되고, gitleaks 훅과도
    충돌한다. `stack_info` 라는 축 자체를 결정론적으로 단언한다.
    A synthetic record keeps this deterministic: a real stack would need a token literal in this
    file's source lines, coupling the test to source layout.
    """
    stream, _ = _fresh_configured_handler()
    handler = _marker_handler()

    record = logging.LogRecord(
        name="tests.redaction_probe",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="background task crashed",
        args=(),
        exc_info=None,
        sinfo=(
            "Stack (most recent call last):\n"
            '  File "src/notifier/telegram.py", line 52, in telegram_post_message\n'
            f'    r = await client.post("{_FAKE_TELEGRAM_URL}")\n'
        ),
    )
    # 핸들러에 직접 넘긴다 — `Handler.handle()` 이 핸들러 필터를 적용한 뒤 emit 하므로
    # 필터 부착 여부와 포맷 최종 출력을 동시에 검증한다.
    # handle() applies handler filters before emit, exercising both wiring and formatting.
    handler.handle(record)

    out = stream.getvalue()

    assert out, "레코드가 출력되지 않았다 — stack_info 축 검증 불가"
    assert _FAKE_BOT_TOKEN not in out, (
        f"🔴 stack_info 경로로 봇 토큰이 평문 유출됐다 — 필터가 record.stack_info 를 덮지 않는다.\n"
        f"출력: {out!r}"
    )
    assert "api.telegram.org/bot***" in out, (
        f"stack_info 에서 마스킹 형태 불일치.\n출력: {out!r}"
    )


def test_uvicorn_error_logger_redacts_exception_traceback(logging_isolation):
    """🔴 D2 — **실제 운영 유출 경로**. uvicorn 로거의 exc_info 로깅도 마스킹된다.

    uvicorn 은 `uvicorn` 로거에 자체 핸들러를 붙이고 `propagate=False` 로 둔다. 따라서
    `uvicorn.error` 레코드는 **구조적으로 root 핸들러에 도달하지 않는다** — root 에만 필터를
    붙인 #1104 의 방어는 이 축에 대해 존재하지 않는 것과 같다. 가드되지 않은 백그라운드 태스크
    예외(`BackgroundTasks`)를 ASGI 밖으로 흘리면 uvicorn 이 `Exception in ASGI application` 을
    exc_info 와 함께 찍고, 그 트레이스백에 토큰 URL 이 통째로 들어간다.
    uvicorn's loggers carry their own handlers with propagate=False, so their records never reach
    the root handler — a root-only filter simply does not exist for this axis, which is exactly the
    path an unguarded background-task exception takes.
    """
    stream, _ = _configured_uvicorn_handler()

    # 🔴 구조적 사실의 명시 단언 — 이것이 참인 한 root 전용 필터로는 이 축을 절대 막지 못한다.
    # Pin the structural fact: while this holds, a root-only filter can never cover this axis.
    assert logging.getLogger("uvicorn").propagate is False, (
        "uvicorn 로거가 propagate=True — dictConfig 재현 실패(테스트 전제 붕괴)"
    )

    try:
        raise RuntimeError(f"Client error '401 Unauthorized' for url '{_FAKE_TELEGRAM_URL}'")
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")

    out = stream.getvalue()

    assert "Traceback (most recent call last)" in out, (
        f"uvicorn 핸들러에 트레이스백이 출력되지 않았다 — 축 검증 불가(테스트 전제 붕괴).\n"
        f"출력: {out!r}"
    )
    assert _FAKE_BOT_TOKEN not in out, (
        f"🔴 uvicorn 축으로 봇 토큰이 평문 유출됐다 — configure_logging() 이 uvicorn 계열 로거의 "
        f"핸들러에 리댁션 필터를 부착하지 않는다. 이것이 운영에서 실제로 새는 경로다.\n"
        f"출력: {out!r}"
    )
    assert "api.telegram.org/bot***" in out, (
        f"uvicorn 축에서 마스킹 형태 불일치.\n출력: {out!r}"
    )


def test_uvicorn_access_logger_handler_also_carries_filter(logging_isolation):
    """🔴 D2 형제 축 — `uvicorn.access` 핸들러에도 필터가 붙는다.

    `uvicorn.access` 는 `uvicorn` 과 **다른 핸들러**(`access`, stdout)를 쓰고 역시
    `propagate=False` 다. `uvicorn` 하나만 처리하면 access 축이 남는다 — 액세스 로그는 요청
    URL 을 찍는 로거라 시크릿이 쿼리/경로에 실린 요청에서 특히 위험하다.
    uvicorn.access uses a *different* handler and is also non-propagating, so covering only the
    `uvicorn` logger leaves this axis open — and it is the logger that prints request URLs.
    """
    _configured_uvicorn_handler()

    access_handlers = logging.getLogger("uvicorn.access").handlers
    assert access_handlers, "uvicorn.access 핸들러 없음 — dictConfig 재현 실패(테스트 전제 붕괴)"
    assert any(
        any(isinstance(f, _RedactSecretsFilter) for f in h.filters) for h in access_handlers
    ), (
        "uvicorn.access 핸들러에 리댁션 필터가 없다 — `uvicorn` 로거만 처리하고 access 축을 "
        "빠뜨렸다. access 로거는 요청 URL 을 찍으므로 시크릿 노출 표면이 가장 넓다."
    )


def test_configure_logging_does_not_duplicate_uvicorn_filter(logging_isolation):
    """🔴 멱등성 — `configure_logging()` 재호출이 uvicorn 핸들러에 필터를 중복 부착하지 않는다.

    필터가 쌓이면 (a) 매 레코드마다 정규식이 N회 반복돼 hot path 비용이 선형 증가하고
    (b) 필터가 record 를 변형하는 설계라 중복 적용 시 마스킹된 문자열을 재차 치환하는
    부작용 위험이 생긴다. 부착 자체(개수 ≥ 1)도 같은 단언으로 함께 잠근다.
    Stacking filters costs one regex pass per copy and risks re-masking an already-masked string;
    the exact-count assertion also pins that attachment happened at all.
    """
    _, handler = _configured_uvicorn_handler()

    configure_logging()
    configure_logging()

    count = sum(1 for f in handler.filters if isinstance(f, _RedactSecretsFilter))
    assert count == 1, (
        f"uvicorn 핸들러의 리댁션 필터 개수가 1이 아니다(실제: {count}). "
        f"0 이면 미부착(유출 방치), 2 이상이면 재호출마다 누적(중복 적용)."
    )


def test_slack_webhook_url_is_redacted_from_handler_output(logging_isolation):
    """🔴 D3 — Slack Incoming Webhook URL 이 마스킹되고 호스트 구조는 남는다.

    Slack webhook URL 은 `/services/` 뒤 경로 **전체가 credential 그 자체**다 — 이 URL 하나면
    누구든 해당 워크스페이스 채널에 임의 메시지를 게시할 수 있다(별도 인증 없음).
    A Slack webhook URL *is* the credential: anyone holding it can post to the channel.
    """
    stream, _ = _fresh_configured_handler()

    logging.getLogger("tests.redaction_probe").warning("posting to %s", _FAKE_SLACK_URL)
    out = stream.getvalue()

    assert out, "핸들러 출력이 비었다 — 검증 불가"
    assert _FAKE_SLACK_SECRET not in out, (
        f"🔴 Slack webhook 시크릿이 로그에 평문으로 남았다 — `_SECRET_URL_PATTERNS` 에 Slack "
        f"패턴이 없다.\n출력: {out!r}"
    )
    assert "hooks.slack.com/services/***" in out, (
        f"Slack 마스킹 형태 불일치 — `hooks.slack.com/services/***` 가 없다. 호스트/경로 구조가 "
        f"통째로 사라지면 어느 채널로 보내려 했는지 운영에서 판독할 수 없다.\n출력: {out!r}"
    )


def test_discord_webhook_url_is_redacted_from_handler_output(logging_isolation):
    """🔴 D3 형제 축 — Discord Webhook URL 도 마스킹되고 호스트 구조는 남는다.

    Discord 도 동일하게 `/api/webhooks/` 뒤 경로(id + token)가 credential 이다.
    Same shape as Slack: the path after /api/webhooks/ is the credential.
    """
    stream, _ = _fresh_configured_handler()

    logging.getLogger("tests.redaction_probe").warning("posting to %s", _FAKE_DISCORD_URL)
    out = stream.getvalue()

    assert out, "핸들러 출력이 비었다 — 검증 불가"
    assert _FAKE_DISCORD_SECRET not in out, (
        f"🔴 Discord webhook 시크릿이 로그에 평문으로 남았다 — `_SECRET_URL_PATTERNS` 에 "
        f"Discord 패턴이 없다.\n출력: {out!r}"
    )
    assert "discord.com/api/webhooks/***" in out, (
        f"Discord 마스킹 형태 불일치 — `discord.com/api/webhooks/***` 가 없다.\n출력: {out!r}"
    )


def test_clean_exception_record_passes_through_untouched(logging_isolation):
    """🔴 무해성 — 시크릿 없는 트레이스백은 원문 그대로, `record.args`·`exc_text` 도 보존된다.

    exc_info 축을 덮기 위해 **모든** 레코드의 `exc_text` 를 무조건 계산·대입하면
    (a) 예외 포맷을 커스터마이즈한 다운스트림 핸들러(uvicorn 의 `DefaultFormatter` 등)가
        캐시된 `exc_text` 를 재사용하게 되어 포맷이 강제로 덮어써지고
    (b) 시크릿이 없는 절대다수의 레코드에 트레이스백 포맷 비용이 항상 부과된다.
    따라서 **마스킹이 실제로 발생한 경우에만** 대입해야 한다.
    Unconditionally computing/assigning exc_text would hijack downstream exception formatting
    (Formatter.format reuses a set exc_text) and tax every clean record; assign only on change.
    """
    stream, capture = _fresh_configured_handler()

    try:
        raise ValueError("nothing secret here")
    except ValueError:
        logging.getLogger("tests.redaction_probe").exception(
            "pipeline failed repo=%s pr=%s", "owner/repo", 7
        )

    out = stream.getvalue()

    assert "pipeline failed repo=owner/repo pr=7" in out, (
        f"시크릿 없는 메시지가 변형됐다 — 필터가 무해하지 않다.\n출력: {out!r}"
    )
    assert "ValueError: nothing secret here" in out, (
        f"시크릿 없는 트레이스백이 손상됐다 — 사고 조사 정보가 소실된다.\n출력: {out!r}"
    )

    assert capture.records, "레코드가 핸들러에 도달하지 않았다 — 검증 불가"
    record = capture.records[-1]
    assert record.msg == "pipeline failed repo=%s pr=%s", (
        f"변경이 없는데 record.msg 를 평탄화했다 — lazy % 포맷 계약 위반.\n실제: {record.msg!r}"
    )
    assert record.args == ("owner/repo", 7), (
        f"변경이 없는데 record.args 를 비웠다 — args 의존 소비자가 조용히 깨진다.\n"
        f"실제: {record.args!r}"
    )


def test_filter_does_not_synthesize_exc_text_on_plain_record(logging_isolation):
    """🔴 무해성(2) — 예외가 없는 레코드에 `exc_text` 를 만들어 붙이지 않는다.

    `Formatter.format()` 은 `record.exc_text` 가 설정돼 있으면 **그것을 그대로 재사용**한다
    (재포맷하지 않는다). 따라서 필터가 exc_info 없는 레코드에까지 `exc_text` 를 합성해 넣으면,
    뒤따르는 핸들러(uvicorn 의 `DefaultFormatter` 등)의 예외 포맷이 무력화되고 평범한 로그
    라인에 정체불명의 트레이스백 꼬리가 붙는다.
    Formatter.format reuses a pre-set exc_text verbatim, so synthesizing one on an exception-free
    record would hijack downstream exception formatting and tack a stray traceback onto plain lines.

    🔴 합성 record + `handler.handle()` 를 쓰는 이유: 실제 로깅 경로에서는 pytest 의 caplog
    핸들러가 **우리 핸들러보다 먼저** 포맷을 돌려 `record.exc_text` 를 이미 캐시해 버린다
    (stdlib 의 캐시 동작). 그러면 "필터가 넣었는지"를 관측할 수 없다.
    A synthetic record isolates the filter: in a real logging call pytest's caplog handler formats
    first and already caches exc_text, making the filter's own behaviour unobservable.
    """
    _fresh_configured_handler()
    handler = _marker_handler()

    record = logging.LogRecord(
        name="tests.redaction_probe",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="analysis complete repo=%s score=%s",
        args=("owner/repo", 87),
        exc_info=None,
    )
    handler.handle(record)

    assert record.exc_text is None, (
        f"예외가 없는 레코드에 exc_text 를 합성했다 — 이후 핸들러의 예외 포맷터가 무력화되고 "
        f"평범한 로그에 트레이스백 꼬리가 붙는다.\n실제: {record.exc_text!r}"
    )
    assert record.stack_info is None, (
        f"예외가 없는 레코드에 stack_info 를 합성했다.\n실제: {record.stack_info!r}"
    )
    assert record.args == ("owner/repo", 87), (
        f"변경이 없는데 record.args 를 비웠다.\n실제: {record.args!r}"
    )
