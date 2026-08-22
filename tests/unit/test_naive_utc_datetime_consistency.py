"""naive/aware datetime 일관성 — DB 컬럼(naive)과 비교 경계·삽입값을 naive UTC 로 통일 (종합감사 P2).

Naive/aware datetime consistency (comprehensive audit P2).

🔴 이 결함은 SQLite 단위 테스트에서 **행동으로 재현 불가**하다: SQLAlchemy 의 SQLite DateTime 은
저장/조회 시 tzinfo 를 벗겨 naive/aware 를 구별하지 않기 때문이다. 결함은 PG(TIMESTAMP WITHOUT TIME
ZONE)에서 세션 타임존이 UTC 가 아닐 때만 드러난다. 따라서 이 파일은 DB 왕복 대신 **코드가 DB 계층에
넘기는 datetime 값이 naive 인지**를 직접 관측한다(뮤테이션 catch 가능).
The bug is not reproducible via SQLite behavior (SQLite strips tzinfo), so these tests observe the
code-level datetime values handed to the DB layer directly, which IS mutation-catchable.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")

# pylint: disable=wrong-import-position
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import src.repositories.claude_api_cost_repo as cost_repo
import src.services.analytics_service as analytics_service
import src.services.operations_service as operations_service
from src.models.analysis_attempt import AnalysisAttempt
from src.shared.time_utils import now_naive_utc, to_naive_utc


# ---------------------------------------------------------------------------
# to_naive_utc / now_naive_utc 헬퍼 (2026-07-23 회고 P1-B — grep 전수 단일 출처)
# ---------------------------------------------------------------------------


def test_to_naive_utc_converts_aware_to_naive_utc():
    """aware(+09:00) → naive UTC(tzinfo=None, 벽시계 UTC 로 변환)."""
    aware = datetime(2026, 7, 23, 21, 0, tzinfo=timezone(timedelta(hours=9)))  # 12:00 UTC
    out = to_naive_utc(aware)
    assert out.tzinfo is None
    assert out == datetime(2026, 7, 23, 12, 0)  # UTC 벽시계 / UTC wall-clock


def test_to_naive_utc_passes_naive_through():
    """이미 naive 면 그대로 통과 (idempotent)."""
    naive = datetime(2026, 7, 23, 12, 0)
    assert to_naive_utc(naive) is naive


def test_now_naive_utc_is_naive():
    """now_naive_utc() 는 tzinfo=None 을 반환."""
    assert now_naive_utc().tzinfo is None


def test_analysis_attempt_started_at_default_is_naive():
    """AnalysisAttempt.started_at 의 Python default 가 naive UTC 를 생성한다.
    orphan sweep 의 `_now_naive()` cutoff 와 동일 규약 — aware 삽입 시 PG 세션-tz 의존.
    The started_at default must yield a naive datetime to match the naive cutoff convention.
    """
    default_callable = AnalysisAttempt.__table__.c.started_at.default.arg
    value = default_callable(MagicMock())  # SQLAlchemy 는 실행 컨텍스트를 넘긴다 / passes a context
    assert isinstance(value, datetime)
    assert value.tzinfo is None, "started_at default 가 aware — naive UTC 여야 한다(PG 세션-tz 안전)"


def test_user_cost_summary_passes_naive_window_bounds(monkeypatch):
    """user_cost_summary 가 _window_cost_rows 에 naive UTC 경계를 넘긴다 (aware `now` 주입 시에도).
    Cost window bounds handed to the query layer must be naive UTC even when an aware `now` is injected.
    """
    captured = []

    def _fake_window(db, owner, since, until, *, until_inclusive):  # noqa: ARG001
        captured.append((since, until))
        return []

    monkeypatch.setattr(cost_repo, "_window_cost_rows", _fake_window)
    monkeypatch.setattr(cost_repo, "_owned_repo_ids_subquery", lambda uid: [])

    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    cost_repo.user_cost_summary(MagicMock(), user_id=1, days=30, now=aware_now)

    assert captured, "_window_cost_rows 미호출 — 경계 관측 불가"
    for since, until in captured:
        assert since.tzinfo is None, f"cur/prev since 가 aware: {since!r}"
        assert until.tzinfo is None, f"cur/prev until 이 aware: {until!r}"


def test_moving_average_uses_naive_query_bounds():
    """moving_average 의 WHERE 경계 바인드 값이 naive UTC 다 (aware `now` 주입 시에도).
    moving_average's WHERE-bound datetimes must be naive UTC even when an aware `now` is injected.
    """
    mock_db = MagicMock()
    # R46: score+result 를 execute().all() 로 읽음 (scalars 아님)
    mock_db.execute.return_value.all.return_value = []

    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    analytics_service.moving_average(mock_db, repo_id=1, window_days=7, now=aware_now)

    stmt = mock_db.execute.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "WHERE 절에 datetime 바인드가 없다 — 관측 불가"
    assert all(v.tzinfo is None for v in dt_params), (
        f"moving_average WHERE 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )


# ---------------------------------------------------------------------------
# grep-전수 스윕 대표 소비처 (2026-07-23 회고 P1-B) — #1197 이 3곳만 고친 것 확장
# ---------------------------------------------------------------------------


def test_weekly_summary_normalizes_aware_week_start_and_now():
    """weekly_summary 가 aware week_start + aware now 를 받아도 naive 경계로 쿼리한다.
    (min(week_end, _now) 가 naive/aware 혼합으로 TypeError 나지 않고, WHERE 경계는 naive).
    weekly_summary must accept aware inputs without TypeError and query with naive bounds.
    """
    mock_db = MagicMock()
    # R46: weekly_summary 는 execute().all() 로 score+result 행을 읽음
    mock_db.execute.return_value.all.return_value = []
    aware_start = datetime(2026, 7, 16, 0, 0, tzinfo=timezone.utc)
    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)

    analytics_service.weekly_summary(mock_db, repo_id=1, week_start=aware_start, now=aware_now)

    stmt = mock_db.execute.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "WHERE 경계 datetime 바인드 없음 — 관측 불가"
    assert all(v.tzinfo is None for v in dt_params), (
        f"weekly_summary WHERE 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )


def test_operations_merge_kpi_uses_naive_bound():
    """operations _merge_kpi 의 MergeAttempt.attempted_at >= since 경계가 naive UTC."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = 0
    operations_service._merge_kpi(mock_db, days=7)  # pylint: disable=protected-access

    stmt = mock_db.scalar.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "MergeAttempt WHERE 경계 datetime 바인드 없음"
    assert all(v.tzinfo is None for v in dt_params), (
        f"_merge_kpi since 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )


# ─── 🔴 전수 쓸이 — 헬퍼를 우회하는 생 tzinfo 벗기기 금지 ──────────────────────
#
# `to_naive_utc` 는 **먼저 UTC 로 변환하고** tzinfo 를 벗긴다. 생 `.replace(tzinfo=None)` 은
# 변환 없이 벗겨서, 값이 UTC 가 아니면 오프셋만큼 조용히 어긋난다.
#
# 이 저장소는 같은 클래스를 두 번 겪었다 — 이 파일이 존재하는 이유(#1197)이고,
# `src/shared/time_utils.py` 머리말이 "#1197 이 3곳만 고쳐(정책 16 grep 전수 위반)
# 회고 P1-B 로 재적발됨" 이라고 적어 두었다. **개별 지점을 고치는 것으로는 끝나지 않는다.**
# 실측(2026-08-22): 헬퍼 도입 후에도 11곳이 생 표기로 남아 있었고, 그중 8곳은 자기가
# 만들지 않은 값(호출자가 준 `now`, 계산된 `next_retry_at`)에서 tzinfo 를 벗기고 있었다.
#
# 🔴 다만 이것은 **표기 트립와이어**이지 클래스 봉인이 아니다 (Grok claim-review 01a02994).
#    `.replace(**{'tzinfo': None})` · `datetime(dt.year, …)` 같은 동치 표기는 문자열로 안 잡힌다.
#    실측상 그런 표기는 현재 `src/` 에 0건이고, 잡으려는 것은 #1197 이후 살아남은 **바로 그
#    복사-붙여넣기 형태**다. 「전수 검사했으니 이 클래스는 끝났다」로 읽지 말 것.
# A spelling tripwire for the exact copy-paste that survived #1197 — not proof the class is closed.

def test_no_raw_tzinfo_stripping_outside_the_helper():
    """`src/` 어디에도 생 `.replace(tzinfo=None)` 이 없어야 한다 — `time_utils.py` 제외.

    🔴 왜 지점별 테스트로 부족한가: `is_expired` 를 고쳐도 `merge_retry_service` 의 4곳,
    `insight_narrative_cache_repo` 의 1곳은 그대로였다. 각 지점마다 시간대 불변식 테스트를
    쓰는 것은 현실적이지 않고, 새로 추가되는 지점은 어차피 아무도 안 본다.

    🔴 **이 검사가 보증하지 않는 것**: 문자열 일치라서 동치 표기(`replace(**{...})`,
    `datetime(dt.year, …)`)는 통과한다. 초록은 "이 표기가 없다" 이지 "변환 없는 벗기기가
    없다" 가 아니다.
    """
    root = Path(__file__).resolve().parents[2]
    allowed = {"time_utils.py"}  # 헬퍼 본체 — 여기가 유일하게 정당한 사용처
    offenders = []

    for path in sorted((root / "src").rglob("*.py")):
        if path.name in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "replace(tzinfo=None)" in line:
                rel = path.relative_to(root).as_posix()
                offenders.append(f"{rel}:{lineno}  {line.strip()}")

    assert not offenders, (
        "생 tzinfo 벗기기가 헬퍼를 우회한다 — 값이 UTC 가 아니면 오프셋만큼 어긋난다:\n  "
        + "\n  ".join(offenders)
        + "\n\n→ `to_naive_utc(dt)` (변환 후 벗김) 또는 `now_naive_utc()` (현재 시각) 를 쓸 것."
    )


def test_the_sweep_actually_scans_files():
    """🔴 공허화 차단 — 스캔 범위가 비면 위 검사는 무조건 통과한다."""
    root = Path(__file__).resolve().parents[2]
    scanned = [p for p in (root / "src").rglob("*.py") if p.name != "time_utils.py"]
    assert len(scanned) > 100, f"src/ 스캔 대상이 {len(scanned)}개 — 범위 붕괴"


def test_the_helper_itself_converts_before_stripping():
    """대조축 — 위 쓸이는 *표기*를 강제한다. 헬퍼가 실제로 옳은지는 따로 단언한다.

    표기만 통일하고 헬퍼가 생 벗기기와 같은 동작이면 아무것도 고쳐지지 않는다.
    """
    kst = timezone(timedelta(hours=9))
    aware = datetime(2026, 4, 26, 21, 0, 0, tzinfo=kst)

    assert to_naive_utc(aware) == datetime(2026, 4, 26, 12, 0, 0), (
        "to_naive_utc 가 UTC 변환 없이 벗기고 있다 — 헬퍼 자신이 결함이면 쓸이는 무의미하다"
    )
    assert aware.replace(tzinfo=None) == datetime(2026, 4, 26, 21, 0, 0), (
        "대조 실패 — 생 벗기기가 다른 값을 준다는 전제가 깨졌다"
    )
