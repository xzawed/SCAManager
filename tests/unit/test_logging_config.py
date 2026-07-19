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
import logging

from src.logging_config import configure_logging


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


def test_main_configures_logging_at_import():
    """🔴 배선 단언 — main 이 실제로 호출해야 운영에 적용된다(모듈만 있으면 dead code)."""
    import src.main  # noqa: F401  (import 자체가 배선 검증)

    root = logging.getLogger()
    assert root.handlers, "src.main import 후에도 root 핸들러 없음 — configure_logging 미배선"
