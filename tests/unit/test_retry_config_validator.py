"""tests/unit/test_retry_config_validator.py

TDD Red Phase: merge_retry_* 백오프 config 검증자 회귀 테스트.
TDD Red Phase: regression tests for the merge_retry_* backoff config validators.

검증 대상 / Validation target:
  - src/config.py Settings 클래스 (pydantic v2 BaseSettings)
  - merge_retry_max_attempts / merge_retry_max_age_hours /
    merge_retry_initial_backoff_seconds / merge_retry_max_backoff_seconds /
    merge_retry_worker_batch_size 에 대한 검증자 (정합성 감사 area=gate P2 — config.py:81)

검증 규칙 / Validation rules:
  1. 양수 제약 — 위 5개 필드는 >= 1 이어야 한다. 0·음수 시
     gate/retry_policy.py::compute_next_retry_at 의 min(initial*2^n, max_backoff)
     백오프가 소멸/단조성 깨짐, max_attempts=0 시 재시도 즉시 terminal 등.
     Positive constraint — the 5 fields must be >= 1, otherwise the exponential
     backoff in compute_next_retry_at degenerates / monotonicity breaks.
  2. 백오프 경계 — merge_retry_max_backoff_seconds >= merge_retry_initial_backoff_seconds.
     max < initial 이면 base 가 항상 max 로 capped → 단조 증가 소멸.
     Backoff boundary — max must be >= initial, otherwise base is always capped to max.

위반 시 pydantic 이 ValidationError 를 던져야 한다 (구현 예정).
On violation pydantic must raise ValidationError (implementation pending).

구현 전이므로 invalid 입력도 현재 통과(에러 없음)해 테스트가 실패해야 정상이다 (Red).
Implementation is absent, so invalid inputs currently pass (no error) and the
invalid-input tests must FAIL (Red) until the validators are added.

conftest.py 가 환경변수를 주입하므로 추가 os.environ 설정 불필요 — test_failover.py 미러.
conftest.py injects env vars, so no extra os.environ setup is needed (mirrors test_failover.py).
"""
import pytest
from pydantic import ValidationError

from src.config import Settings

# Settings(...) 직접 구성에 필요한 필수 6개 kwargs (test_failover.py:232~270 미러).
# The six required kwargs to construct Settings directly (mirrors test_failover.py:232~270).
_REQUIRED_KWARGS = dict(
    database_url="sqlite:///:memory:",
    github_webhook_secret="x",
    github_token="x",
    telegram_bot_token="123:ABC",
    telegram_chat_id="-100",
)


def test_valid_defaults_construct_ok():
    # 회귀 가드 — merge_retry_* 미지정(기본값 30/24/60/600/50) 시 검증자가 정상 기본값을 거부하면 안 된다
    # Regression guard — when merge_retry_* is unspecified (defaults), the validators must NOT reject valid defaults
    s = Settings(**_REQUIRED_KWARGS)
    assert s.merge_retry_max_attempts == 30
    assert s.merge_retry_max_age_hours == 24
    assert s.merge_retry_initial_backoff_seconds == 60
    assert s.merge_retry_max_backoff_seconds == 600
    assert s.merge_retry_worker_batch_size == 50


def test_max_backoff_less_than_initial_raises():
    # max_backoff(10) < initial_backoff(60) → 경계 위반 → ValidationError (단조 증가 소멸 방지)
    # max_backoff(10) < initial_backoff(60) → boundary violation → ValidationError (prevents monotonicity loss)
    with pytest.raises(ValidationError):
        Settings(
            **_REQUIRED_KWARGS,
            merge_retry_max_backoff_seconds=10,
            merge_retry_initial_backoff_seconds=60,
        )


def test_zero_initial_backoff_raises():
    # initial_backoff=0 → 양수 제약 위반 → ValidationError (백오프 0 으로 소멸)
    # initial_backoff=0 → positive-constraint violation → ValidationError (backoff degenerates to 0)
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, merge_retry_initial_backoff_seconds=0)


def test_negative_max_attempts_raises():
    # max_attempts=-1 → 양수 제약 위반 → ValidationError (음수 시 재시도 로직 비정상)
    # max_attempts=-1 → positive-constraint violation → ValidationError (negative breaks retry logic)
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, merge_retry_max_attempts=-1)


def test_zero_worker_batch_size_raises():
    # worker_batch_size=0 → 양수 제약 위반 → ValidationError (cron sweep 0행 처리로 무한 정체)
    # worker_batch_size=0 → positive-constraint violation → ValidationError (cron sweep processes 0 rows, stalls forever)
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, merge_retry_worker_batch_size=0)


def test_max_backoff_equal_initial_ok():
    # 경계 포함 — max_backoff == initial_backoff(60==60) 동일값은 허용(>= 경계) → 예외 없음
    # Boundary inclusive — equal values (60==60) are allowed (>= boundary) → no exception
    s = Settings(
        **_REQUIRED_KWARGS,
        merge_retry_max_backoff_seconds=60,
        merge_retry_initial_backoff_seconds=60,
    )
    assert s.merge_retry_max_backoff_seconds == 60
    assert s.merge_retry_initial_backoff_seconds == 60
