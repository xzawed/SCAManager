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

from src.logging_config import _MARKER, configure_logging


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
