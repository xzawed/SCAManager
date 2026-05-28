# Per-Repository Code Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-repository code insights — a dashboard repo card section linking to `/repos/{name}/insights` pages showing recurring issues, problem files, AI suggestions, category breakdown, and an optional AI narrative per repo.

**Architecture:** Python-side JSON aggregation over the last 30 `Analysis.result` rows per repo (same pattern as `frequent_issues_v2` in `dashboard_service.py`). Extend `insight_narrative_cache` with a nullable `repo_id` FK for repo-scoped AI narrative caching (NULL=global dashboard, N=repo-specific). New route + template + CSS file (`.ri-*` prefix) following the `admin.css` separation pattern established in PR #399.

**Tech Stack:** FastAPI, SQLAlchemy (Session), Jinja2, Chart.js (vendored at `/static/vendor/chart.umd.min.js`), Alembic migration 0031, CSS custom properties (`--accent`, `--danger`, `--warning`).

---

## File Map

| Change | File | Why |
|--------|------|-----|
| Create | `src/services/repo_insight_service.py` | 5 aggregation functions + AI narrative |
| Create | `src/ui/routes/repo_insights.py` | `GET /repos/{name}/insights` route |
| Create | `src/templates/repo_insights.html` | Insights page Jinja2 template |
| Create | `src/static/css/repo_insights.css` | `.ri-*` scoped CSS (CPD 방지) |
| Create | `alembic/versions/0031_repo_insights_cache.py` | Add `repo_id` FK to narrative cache |
| Create | `tests/unit/services/test_repo_insight_service.py` | Service unit tests |
| Create | `tests/unit/services/test_repo_insight_cards.py` | `repo_insight_cards()` unit tests |
| Create | `tests/unit/api/test_repo_insights_route.py` | Route unit tests |
| Create | `tests/integration/test_repo_insights_css.py` | CSS class existence + 44px checks |
| Modify | `src/models/insight_narrative_cache.py` | Add `repo_id` Column |
| Modify | `src/repositories/insight_narrative_cache_repo.py` | Add repo-scoped get/upsert/invalidate |
| Modify | `src/services/dashboard_service.py` | Add `repo_insight_cards()` function |
| Modify | `src/ui/routes/dashboard.py` | Call `repo_insight_cards()` in overview |
| Modify | `src/templates/dashboard.html` | Add repo card section |
| Modify | `src/ui/router.py` | Include `repo_insights` router |
| Modify | `docs/architecture.md` | Sync new files |

---

### Task 1: DB Foundation — `insight_narrative_cache.repo_id` column + cache repo helpers

**Files:**
- Modify: `src/models/insight_narrative_cache.py`
- Modify: `src/repositories/insight_narrative_cache_repo.py`
- Create: `alembic/versions/0031_repo_insights_cache.py`
- Create: `tests/unit/migrations/test_0031_repo_insights_cache.py`

- [ ] **Step 1: Update the ORM model — add `repo_id` column, remove old UniqueConstraint**

Replace the `__table_args__` block and add the `repo_id` column in `src/models/insight_narrative_cache.py`:

```python
"""InsightNarrativeCache ORM — Insight 모드 Claude AI narrative 1h TTL 캐시.

(previous docstring preserved, add below)

0031 — `repo_id` nullable FK 추가 (repo_id=NULL: 전체 대시보드 캐시, repo_id=N: 리포별 캐시).
0031 — Add nullable `repo_id` FK (NULL=global dashboard cache, N=repo-specific cache).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class InsightNarrativeCache(Base):
    """Claude AI Insight narrative 응답 1h TTL 캐시.

    Claude AI Insight narrative response cache (1h TTL).
    """

    __tablename__ = "insight_narrative_cache"
    __table_args__ = (
        # 0031: old (user_id, days) UniqueConstraint removed — repo_id 추가로 다중 행 허용.
        # 0031: old (user_id, days) UniqueConstraint removed — multiple rows allowed with repo_id.
        # Partial uniqueness enforced by migration 0031 partial indexes (PG only).
        Index(
            "ix_insight_cache_user_days_language",
            "user_id", "days", "language",
        ),
        Index("ix_insight_cache_repo_id", "repo_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    days = Column(Integer, nullable=False)
    language = Column(String(5), nullable=False, default="en", server_default="en")
    # 0031 — repo-specific cache key (NULL = global dashboard narrative)
    # 0031 — 리포별 캐시 키 (NULL = 전체 대시보드 내러티브)
    repo_id = Column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    response_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    expires_at = Column(DateTime, nullable=False, index=True)
```

- [ ] **Step 2: Add repo-scoped helpers to `src/repositories/insight_narrative_cache_repo.py`**

Append after the existing `invalidate` function:

```python
# ─── 0031: repo-scoped cache helpers ─────────────────────────────────────────


def get_fresh_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str = "en",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """리포별 캐시 조회 — 만료 미경과 시 response_json 반환, 없거나 만료면 None.

    Get repo-specific cache — return response_json if not expired, else None.
    """
    now = now or datetime.now(timezone.utc)
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.language == language,
        )
        .first()
    )
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return None
    return dict(row.response_json or {})


def upsert_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str = "en",
    response: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> InsightNarrativeCache:
    """리포별 캐시 upsert — (user_id, repo_id, days, language) 키 기준.

    Upsert repo-specific cache by (user_id, repo_id, days, language).
    """
    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.language == language,
        )
        .first()
    )
    if existing is not None:
        existing.response_json = response
        existing.created_at = now
        existing.expires_at = expires_at
        db.commit()
        db.refresh(existing)
        return existing
    row = InsightNarrativeCache(
        user_id=user_id, repo_id=repo_id, days=days, language=language,
        response_json=response, created_at=now, expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def invalidate_repo(db: Session, *, user_id: int, repo_id: int, days: int) -> bool:
    """리포별 캐시 강제 무효화 (DELETE).

    Force invalidate repo-specific cache (DELETE).
    Returns True if deleted, False if not found.
    """
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
```

Also update the existing `get_fresh`, `upsert`, `invalidate` functions to explicitly filter `repo_id IS NULL` so global and repo-scoped rows don't interfere. In `get_fresh` and `invalidate`, add `.filter(InsightNarrativeCache.repo_id.is_(None))`. In `upsert`, add `repo_id=None` to the filter and to the new row construction.

- [ ] **Step 3: Write the migration test first**

Create `tests/unit/migrations/test_0031_repo_insights_cache.py`:

```python
"""0031 마이그레이션 회귀 가드 — insight_narrative_cache.repo_id 컬럼 + 인덱스."""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

import src.models  # noqa: F401  # side-effect: populate Base.metadata
from src.database import Base


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_repo_id_column_exists(engine):
    """insight_narrative_cache 테이블에 repo_id 컬럼이 존재한다."""
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("insight_narrative_cache")}
    assert "repo_id" in cols


def test_repo_id_is_nullable(engine):
    """repo_id 컬럼은 nullable 이다 (기존 전체 대시보드 캐시 하위 호환)."""
    insp = inspect(engine)
    col = next(c for c in insp.get_columns("insight_narrative_cache") if c["name"] == "repo_id")
    assert col["nullable"] is True


def test_global_and_repo_rows_coexist(engine):
    """같은 (user_id, days) 에 repo_id=NULL 과 repo_id=N 행이 공존 가능하다."""
    from src.models.insight_narrative_cache import InsightNarrativeCache
    from datetime import datetime, timedelta, timezone

    _now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=None,
            response_json={"status": "global"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.add(InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=5,
            response_json={"status": "repo"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.commit()
        count = db.query(InsightNarrativeCache).filter(
            InsightNarrativeCache.user_id == 1,
            InsightNarrativeCache.days == 30,
        ).count()
        assert count == 2
```

- [ ] **Step 4: Run the test — expect failure (column missing)**

```bash
pytest tests/unit/migrations/test_0031_repo_insights_cache.py -v
```
Expected: FAIL — `repo_id` column not found (the model change drives ORM schema).

After applying the ORM model change from Step 1, run again — expect PASS for all 3 tests.

- [ ] **Step 5: Create the Alembic migration file**

Create `alembic/versions/0031_repo_insights_cache.py`:

```python
"""insight_narrative_cache에 repo_id FK 추가 — 리포별 AI 내러티브 캐시 지원.

Revision ID: 0031repoinsights
Revises: 0030i18ncolumns
Create Date: 2026-05-12

0031 변경 사항:
1. insight_narrative_cache.repo_id (Integer, nullable, FK → repositories.id CASCADE)
2. 기존 uq_insight_cache_user_days 제약 삭제 (PG only) — repo_id 추가로 다중 행 필요
3. 부분 유니크 인덱스 2종 생성 (PG only):
   - uq_insight_cache_global: (user_id, days, language) WHERE repo_id IS NULL
   - uq_insight_cache_repo:   (user_id, days, language, repo_id) WHERE repo_id IS NOT NULL
4. ix_insight_cache_repo_id 인덱스 추가 (전체 환경)

repo_id = NULL → 기존 전체 대시보드 캐시 (하위 호환 유지)
repo_id = N    → 리포별 AI 내러티브 캐시 (1h TTL)

회귀 가드: tests/unit/migrations/test_0031_repo_insights_cache.py
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0031repoinsights"
down_revision = "0030i18ncolumns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """repo_id 컬럼 추가 + PG 부분 유니크 인덱스 교체.

    Add repo_id column + replace PG unique constraints with partial indexes.
    """
    # 1. repo_id 컬럼 추가 (nullable FK, CASCADE)
    # 1. Add nullable repo_id column (FK with CASCADE delete)
    op.add_column(
        "insight_narrative_cache",
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # 2. 기존 체인 인덱스 + 제약 교체 (PG only)
    # 2. Replace old constraint + add partial indexes (PG only)
    if is_postgresql(op.get_bind()):
        # 기존 (user_id, days) 유니크 제약 삭제 — repo_id 추가로 전역+리포 다중 행 필요
        # Drop old (user_id, days) unique constraint — needed for global+repo coexistence
        op.drop_constraint("uq_insight_cache_user_days", "insight_narrative_cache")

        # 전역 캐시 부분 유니크 인덱스 (repo_id IS NULL)
        # Partial unique index for global cache rows (repo_id IS NULL)
        op.execute(
            "CREATE UNIQUE INDEX uq_insight_cache_global "
            "ON insight_narrative_cache (user_id, days, language) "
            "WHERE repo_id IS NULL"
        )

        # 리포별 캐시 부분 유니크 인덱스 (repo_id IS NOT NULL)
        # Partial unique index for repo-specific cache rows
        op.execute(
            "CREATE UNIQUE INDEX uq_insight_cache_repo "
            "ON insight_narrative_cache (user_id, days, language, repo_id) "
            "WHERE repo_id IS NOT NULL"
        )

    # 3. repo_id 검색 인덱스 (전체 환경)
    # 3. repo_id lookup index (all environments)
    op.create_index("ix_insight_cache_repo_id", "insight_narrative_cache", ["repo_id"])


def downgrade() -> None:
    """역순 복구 — 인덱스 삭제 → 컬럼 삭제 → 구 제약 복구.

    Reverse: drop indexes → drop column → restore old constraint.
    """
    op.drop_index("ix_insight_cache_repo_id", table_name="insight_narrative_cache")

    if is_postgresql(op.get_bind()):
        op.execute("DROP INDEX IF EXISTS uq_insight_cache_repo")
        op.execute("DROP INDEX IF EXISTS uq_insight_cache_global")
        op.create_unique_constraint(
            "uq_insight_cache_user_days", "insight_narrative_cache", ["user_id", "days"]
        )

    op.drop_column("insight_narrative_cache", "repo_id")
```

- [ ] **Step 6: Run migration tests + full unit suite**

```bash
pytest tests/unit/migrations/test_0031_repo_insights_cache.py -v
pytest tests/unit/ -x -q
```
Expected: all pass. The migration test passes because the ORM model now includes `repo_id`.

- [ ] **Step 7: Commit**

```bash
git add src/models/insight_narrative_cache.py \
        src/repositories/insight_narrative_cache_repo.py \
        alembic/versions/0031_repo_insights_cache.py \
        tests/unit/migrations/test_0031_repo_insights_cache.py
git commit -m "feat(db): add repo_id FK to insight_narrative_cache + repo-scoped cache helpers"
```

---

### Task 2: `repo_insight_service.py` — 5 aggregation functions + AI narrative

**Files:**
- Create: `tests/unit/services/test_repo_insight_service.py`
- Create: `src/services/repo_insight_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/services/test_repo_insight_service.py`:

```python
"""repo_insight_service 단위 테스트 — 5 집계 함수 + AI narrative stub.

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401  side-effect: populate Base.metadata
from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=99, github_login="tester", email="t@x.com", display_name="T")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    r = Repository(full_name="owner/myrepo", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _add_analysis(
    db: Session,
    repo_id: int,
    *,
    offset_hours: int = 0,
    result: dict[str, Any] | None = None,
    score: int = 70,
) -> Analysis:
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="C",
        result=result or {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ─── repo_kpi ────────────────────────────────────────────────────────────


class TestRepoKpi:
    def test_returns_required_keys(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, score=80)
        result = repo_kpi(db, repo.id)

        assert set(result.keys()) >= {
            "avg_score", "grade", "analysis_count",
            "top_recurring_issue", "top_recurring_count",
            "high_security_count", "score_delta",
        }

    def test_empty_repo_returns_none_avg(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        result = repo_kpi(db, repo.id)
        assert result["avg_score"] is None
        assert result["analysis_count"] == 0

    def test_days_filter_excludes_old_analysis(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, offset_hours=24 * 40, score=50)  # 40 days ago
        result = repo_kpi(db, repo.id, days=30)
        assert result["analysis_count"] == 0

    def test_counts_high_security_issues(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, result={
            "issues": [
                {"category": "security", "severity": "HIGH", "message": "sql inj"},
                {"category": "code_quality", "severity": "error", "message": "line too long"},
            ]
        })
        result = repo_kpi(db, repo.id)
        assert result["high_security_count"] == 1

    def test_identifies_top_recurring_issue(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        issue = {"category": "code_quality", "severity": "warning", "message": "line too long"}
        for _ in range(3):
            _add_analysis(db, repo.id, result={"issues": [issue]})
        result = repo_kpi(db, repo.id)
        assert result["top_recurring_issue"] == "line too long"
        assert result["top_recurring_count"] == 3


# ─── repo_recurring_issues ───────────────────────────────────────────────


class TestRepoRecurringIssues:
    def test_returns_sorted_by_count(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues

        for _ in range(3):
            _add_analysis(db, repo.id, result={"issues": [
                {"message": "A", "category": "code_quality", "severity": "warning", "tool": "pylint", "language": "python"},
            ]})
        _add_analysis(db, repo.id, result={"issues": [
            {"message": "B", "category": "security", "severity": "error", "tool": "bandit", "language": "python"},
        ]})

        result = repo_recurring_issues(db, repo.id)
        assert result[0]["message"] == "A"
        assert result[0]["count"] == 3
        assert result[1]["message"] == "B"

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues
        assert repo_recurring_issues(db, repo.id) == []

    def test_result_dict_has_required_keys(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues

        _add_analysis(db, repo.id, result={"issues": [
            {"message": "x", "category": "security", "severity": "error", "tool": "bandit", "language": "python"},
        ]})
        item = repo_recurring_issues(db, repo.id)[0]
        assert set(item.keys()) >= {"message", "count", "category", "severity", "tool", "language"}


# ─── repo_problem_files ──────────────────────────────────────────────────


class TestRepoProblemFiles:
    def test_returns_sorted_by_count(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files

        for _ in range(4):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "src/main.py", "text": "x"}]})
        _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "src/other.py", "text": "y"}]})

        result = repo_problem_files(db, repo.id)
        assert result[0]["file"] == "src/main.py"
        assert result[0]["count"] == 4
        assert result[0]["pct"] == 100

    def test_pct_calculated_relative_to_max(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files

        for _ in range(4):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "a.py", "text": "x"}]})
        for _ in range(2):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "b.py", "text": "y"}]})

        result = repo_problem_files(db, repo.id)
        assert result[0]["pct"] == 100
        assert result[1]["pct"] == 50

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files
        assert repo_problem_files(db, repo.id) == []


# ─── repo_ai_suggestions ─────────────────────────────────────────────────


class TestRepoAiSuggestions:
    def test_groups_by_60char_prefix(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions

        suggestion = "A" * 70  # longer than 60 chars — two identical prefixes
        for _ in range(2):
            _add_analysis(db, repo.id, result={
                "ai_review_status": "success",
                "ai_suggestions": [suggestion],
            })
        result = repo_ai_suggestions(db, repo.id)
        assert len(result) == 1
        assert result[0]["count"] == 2

    def test_excludes_non_success_analyses(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions

        _add_analysis(db, repo.id, result={
            "ai_review_status": "error",
            "ai_suggestions": ["fix this"],
        })
        assert repo_ai_suggestions(db, repo.id) == []

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions
        assert repo_ai_suggestions(db, repo.id) == []


# ─── repo_category_breakdown ─────────────────────────────────────────────


class TestRepoCategoryBreakdown:
    def test_returns_5_keys(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown

        result = repo_category_breakdown(db, repo.id)
        assert set(result.keys()) == {
            "security_error", "security_warning",
            "code_quality_error", "code_quality_warning", "total",
        }

    def test_counts_by_category_and_severity(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown

        _add_analysis(db, repo.id, result={"issues": [
            {"category": "security", "severity": "error"},
            {"category": "security", "severity": "warning"},
            {"category": "code_quality", "severity": "error"},
            {"category": "code_quality", "severity": "warning"},
        ]})
        bd = repo_category_breakdown(db, repo.id)
        assert bd["security_error"] == 1
        assert bd["security_warning"] == 1
        assert bd["code_quality_error"] == 1
        assert bd["code_quality_warning"] == 1
        assert bd["total"] == 4

    def test_empty_all_zeros(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown
        bd = repo_category_breakdown(db, repo.id)
        assert bd["total"] == 0
```

- [ ] **Step 2: Run tests — expect all failures**

```bash
pytest tests/unit/services/test_repo_insight_service.py -v
```
Expected: all FAIL with `ModuleNotFoundError: No module named 'src.services.repo_insight_service'`.

- [ ] **Step 3: Implement `src/services/repo_insight_service.py`**

Create the file:

```python
"""리포별 코드 인사이트 서비스 — 5 집계 함수 + AI narrative.

Repository-level code insight service — 5 aggregation functions + AI narrative.

모든 집계 함수는 Analysis.result JSON을 Python-side 루프로 처리 (최근 30건 상한).
All aggregation functions process Analysis.result JSON Python-side (max 30 rows).

함수 목록:
- repo_kpi          — KPI 4종 카드 + 점수 delta
- repo_recurring_issues — 빈도 내림차순 이슈 리스트
- repo_problem_files    — 문제 파일 TOP N (프로그레스 바용 pct 포함)
- repo_ai_suggestions   — AI 제안 60자 prefix 그룹화
- repo_category_breakdown — 카테고리×심각도 4-way 분포
- repo_insight_narrative  — Claude AI 리포 진단 내러티브 (async, 캐시 1h TTL)
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.analysis import Analysis
from src.scorer.calculator import calculate_grade
from src.shared.claude_metrics import extract_anthropic_usage, log_claude_api_call

logger = logging.getLogger(__name__)

# 집계 최대 분석 건수 — Python 루프 O(N×이슈수) 상한
# Max analyses per aggregation — caps Python loop O(N×issues)
_MAX_ANALYSES = 30


def _fetch_analyses(
    db: Session, repo_id: int, days: int, now: datetime
) -> list[Analysis]:
    """최근 days 내 분석 최대 _MAX_ANALYSES 건 조회 (created_at 내림차순).

    Fetch up to _MAX_ANALYSES analyses within `days` window, newest first.
    """
    since = now - timedelta(days=days)
    return list(
        db.scalars(
            select(Analysis)
            .where(Analysis.repo_id == repo_id)
            .where(Analysis.created_at >= since)
            .where(Analysis.created_at <= now)
            .where(Analysis.result.isnot(None))
            .order_by(Analysis.created_at.desc())
            .limit(_MAX_ANALYSES)
        ).all()
    )


def repo_kpi(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, Any]:
    """KPI 4종 — 평균 점수/등급/분석수/최다 반복 이슈/보안 HIGH/점수 delta.

    Returns:
        {
          "avg_score": float | None,
          "grade": str,
          "analysis_count": int,
          "top_recurring_issue": str | None,
          "top_recurring_count": int,
          "high_security_count": int,
          "score_delta": float | None,
        }
    """
    _now = now or datetime.now(timezone.utc)
    cur = _fetch_analyses(db, repo_id, days, _now)

    # 직전 동일 기간 (delta 비교용)
    # Previous identical window for delta comparison
    prev_since = _now - timedelta(days=days * 2)
    prev_until = _now - timedelta(days=days)
    prev = list(
        db.scalars(
            select(Analysis)
            .where(Analysis.repo_id == repo_id)
            .where(Analysis.created_at >= prev_since)
            .where(Analysis.created_at < prev_until)
            .where(Analysis.result.isnot(None))
            .limit(_MAX_ANALYSES)
        ).all()
    )

    cur_scores = [a.score for a in cur if a.score is not None]
    prev_scores = [a.score for a in prev if a.score is not None]
    avg_score = round(sum(cur_scores) / len(cur_scores), 1) if cur_scores else None
    prev_avg = round(sum(prev_scores) / len(prev_scores), 1) if prev_scores else None
    score_delta = (
        round(avg_score - prev_avg, 1)
        if (avg_score is not None and prev_avg is not None)
        else None
    )
    grade = calculate_grade(int(avg_score)) if avg_score is not None else "?"

    # 이슈 빈도 카운트 (message 키)
    # Issue frequency count (message key)
    issue_counter: dict[str, int] = {}
    high_security = 0
    for a in cur:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            key = issue.get("message") or issue.get("code")
            if key:
                issue_counter[key] = issue_counter.get(key, 0) + 1
            if (
                issue.get("category") == "security"
                and issue.get("severity", "").upper() in ("HIGH", "ERROR")
            ):
                high_security += 1

    top_issue, top_count = None, 0
    if issue_counter:
        top_issue, top_count = max(issue_counter.items(), key=lambda x: x[1])

    return {
        "avg_score": avg_score,
        "grade": grade,
        "analysis_count": len(cur),
        "top_recurring_issue": top_issue,
        "top_recurring_count": top_count,
        "high_security_count": high_security,
        "score_delta": score_delta,
    }


def repo_recurring_issues(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict[str, Any]]:
    """이슈 빈도 Top N — category/severity/tool/language 포함, 빈도 내림차순.

    Top N issues by frequency — includes category/severity/tool/language, sorted descending.

    Returns:
        [{"message": str, "count": int, "category": str, "severity": str, "tool": str, "language": str}, ...]
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    meta: dict[str, dict[str, str]] = {}
    for a in analyses:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            key = issue.get("message") or issue.get("code")
            if not key:
                continue
            counter[key] = counter.get(key, 0) + 1
            if key not in meta:
                meta[key] = {
                    "category": issue.get("category", ""),
                    "severity": issue.get("severity", ""),
                    "tool": issue.get("tool", ""),
                    "language": issue.get("language", ""),
                }

    return [
        {
            "message": msg,
            "count": cnt,
            "category": meta[msg]["category"],
            "severity": meta[msg]["severity"],
            "tool": meta[msg]["tool"],
            "language": meta[msg]["language"],
        }
        for msg, cnt in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    ]


def repo_problem_files(
    db: Session, repo_id: int, days: int = 30, n: int = 5, now: datetime | None = None
) -> list[dict[str, Any]]:
    """문제 파일 Top N — file_feedbacks[].file 빈도 집계 + 프로그레스 바용 pct.

    Top N problem files — frequency of file_feedbacks[].file + pct for progress bars.

    Returns:
        [{"file": str, "count": int, "pct": float}, ...]  count 내림차순
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    for a in analyses:
        for fb in (a.result or {}).get("file_feedbacks", []):
            if not isinstance(fb, dict):
                continue
            fname = fb.get("file")
            if fname:
                counter[fname] = counter.get(fname, 0) + 1

    if not counter:
        return []

    sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    max_count = sorted_items[0][1]
    return [
        {"file": fname, "count": cnt, "pct": round(cnt / max_count * 100)}
        for fname, cnt in sorted_items
    ]


def repo_ai_suggestions(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict[str, Any]]:
    """AI 제안 Top N — 60자 prefix 그룹화, ai_review_status=success 분석만 포함.

    Top N AI suggestions — grouped by 60-char prefix, success analyses only.

    Returns:
        [{"suggestion": str, "count": int}, ...]  count 내림차순
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    for a in analyses:
        if (a.result or {}).get("ai_review_status") != "success":
            continue
        for suggestion in (a.result or {}).get("ai_suggestions", []):
            if not isinstance(suggestion, str) or not suggestion.strip():
                continue
            prefix = suggestion[:60]
            counter[prefix] = counter.get(prefix, 0) + 1

    return [
        {"suggestion": prefix, "count": cnt}
        for prefix, cnt in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    ]


def repo_category_breakdown(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, int]:
    """이슈 카테고리×심각도 4-way 분포 — Chart.js 도넛용.

    4-way issue distribution by category×severity — for Chart.js donut.

    Returns:
        {
          "security_error": int,
          "security_warning": int,
          "code_quality_error": int,
          "code_quality_warning": int,
          "total": int,
        }
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counts: dict[str, int] = {
        "security_error": 0,
        "security_warning": 0,
        "code_quality_error": 0,
        "code_quality_warning": 0,
    }
    for a in analyses:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            category = issue.get("category", "")
            severity = issue.get("severity", "").lower()
            is_error = severity in ("error", "high")
            if category == "security":
                counts["security_error" if is_error else "security_warning"] += 1
            elif category == "code_quality":
                counts["code_quality_error" if is_error else "code_quality_warning"] += 1

    counts["total"] = sum(counts.values())
    return counts


# ─── AI 내러티브 ──────────────────────────────────────────────────────────


def _extract_narrative_json(text: str) -> str:
    """Claude 응답에서 JSON 추출 — 코드 블록 우선, {~} fallback.

    Extract JSON from Claude response — prefer fenced block, fallback to first/last brace.
    """
    cleaned = text.strip()
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if block:
        return block.group(1)
    first, last = cleaned.find("{"), cleaned.rfind("}")
    if first != -1 and last > first:
        return cleaned[first : last + 1]
    return cleaned


async def repo_insight_narrative(
    db: Session,
    repo_id: int,
    days: int = 30,
    *,
    repo_full_name: str = "",
    kpi: dict[str, Any],
    recurring: list[dict[str, Any]],
    now: datetime | None = None,
    refresh: bool = False,
    user_id: int | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """리포별 Claude AI 진단 내러티브 — 1h TTL 캐시 + refresh 지원.

    Repo-level Claude AI narrative — 1h TTL cache + refresh support.

    Returns:
        {"text": str, "status": "success"|"no_api_key"|"no_data"|"api_error"}
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        return {"text": "", "status": "no_api_key"}

    _now = now or datetime.now(timezone.utc)

    if user_id is not None:
        from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

        if refresh:
            insight_narrative_cache_repo.invalidate_repo(
                db, user_id=user_id, repo_id=repo_id, days=days
            )
        else:
            cached = insight_narrative_cache_repo.get_fresh_repo(
                db, user_id=user_id, repo_id=repo_id, days=days, language=language, now=_now,
            )
            if cached:
                return cached

    if not kpi.get("analysis_count"):
        return {"text": "", "status": "no_data"}

    user_prompt = (
        f"Repository: {repo_full_name}\n"
        f"Period: last {days} days\n"
        f"Avg score: {kpi.get('avg_score')} ({kpi.get('grade')}), "
        f"delta: {kpi.get('score_delta')}\n"
        f"Analyses: {kpi.get('analysis_count')}\n"
        f"Security HIGH: {kpi.get('high_security_count')}\n"
        f"Top recurring issue: {kpi.get('top_recurring_issue')} "
        f"({kpi.get('top_recurring_count')} times)\n"
        f"Top 5 issues: {json.dumps(recurring[:5], ensure_ascii=False)}\n\n"
        "Please provide a 2-3 paragraph diagnostic narrative in Korean summarizing "
        "this repository's code quality status, key recurring problems, and concrete "
        "next steps. Respond with strict JSON only: {\"text\": \"...narrative...\"}"
    )

    start = time.perf_counter()
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0, max_retries=2)
    try:
        response = await client.messages.create(
            model=settings.claude_insight_model,
            max_tokens=600,
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="success",
        )
        raw = response.content[0].text
        data = json.loads(_extract_narrative_json(raw))
        result: dict[str, Any] = {"text": str(data.get("text", raw)), "status": "success"}
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        duration_ms = (time.perf_counter() - start) * 1000
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            status="error",
        )
        logger.exception("repo_insight_narrative API call failed")
        return {"text": "", "status": "api_error"}

    if user_id is not None:
        from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user_id, repo_id=repo_id, days=days,
            language=language, response=result, now=_now,
        )

    return result
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
pytest tests/unit/services/test_repo_insight_service.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/repo_insight_service.py \
        tests/unit/services/test_repo_insight_service.py
git commit -m "feat(service): add repo_insight_service with 5 aggregation functions + AI narrative"
```

---

### Task 3: `repo_insight_cards()` in `dashboard_service.py`

**Files:**
- Create: `tests/unit/services/test_repo_insight_cards.py`
- Modify: `src/services/dashboard_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/services/test_repo_insight_cards.py`:

```python
"""repo_insight_cards 단위 테스트 — 대시보드 리포별 인사이트 카드 섹션."""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=77, github_login="owner", email="o@x.com", display_name="O")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_repo(db, name, user_id):
    r = Repository(full_name=name, user_id=user_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_analysis(db, repo_id, score, offset_hours=0, result=None):
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        result=result or {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestRepoInsightCards:
    def test_returns_list_of_cards(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/api", user.id)
        _make_analysis(db, r.id, 80)

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_card_has_required_keys(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/web", user.id)
        _make_analysis(db, r.id, 75)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert set(card.keys()) >= {
            "repo_id", "full_name", "avg_score", "grade",
            "recurring_issue_count", "score_trend", "insights_url",
        }

    def test_insights_url_format(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/my-repo", user.id)
        _make_analysis(db, r.id, 80)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert card["insights_url"] == "/repos/owner/my-repo/insights"

    def test_empty_repos_returns_empty_list(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert result == []

    def test_score_trend_up_when_improved(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/cli", user.id)
        # Previous window: score 50 (40 days ago), current window: score 80
        _make_analysis(db, r.id, 50, offset_hours=24 * 35)
        _make_analysis(db, r.id, 80, offset_hours=5)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert card["score_trend"] == "up"

    def test_max_10_repos(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        for i in range(12):
            r = _make_repo(db, f"owner/repo-{i}", user.id)
            _make_analysis(db, r.id, 70)

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert len(result) <= 10
```

- [ ] **Step 2: Run tests — expect all failures**

```bash
pytest tests/unit/services/test_repo_insight_cards.py -v
```
Expected: FAIL with `AttributeError: module 'src.services.dashboard_service' has no attribute 'repo_insight_cards'`.

- [ ] **Step 3: Add `repo_insight_cards()` to `src/services/dashboard_service.py`**

Append before the `# ─── Phase 3 PR 2` section (around line 437). Add after the `feedback_status` function:

```python
# ─── 0031: 리포별 인사이트 카드 (대시보드 섹션용) ───────────────────────────


def repo_insight_cards(
    db: Session,
    days: int = 30,
    *,
    user_id: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """사용자 소유 리포별 인사이트 카드 요약 — 대시보드 카드 섹션용 (최대 10개).

    Per-repo insight card summary for the dashboard section (max 10 repos).

    Returns:
        [
          {
            "repo_id": int,
            "full_name": str,
            "avg_score": float | None,
            "grade": str,
            "recurring_issue_count": int,   # 반복 이슈 종류 수
            "score_trend": "up" | "down" | "flat",
            "insights_url": str,            # "/repos/{name}/insights"
          }, ...
        ]
    """
    from src.services.repo_insight_service import (  # noqa: PLC0415
        repo_kpi,
        repo_recurring_issues,
    )

    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    # 사용자 소유 리포 조회 (legacy NULL 포함)
    # Fetch user-owned repos (legacy NULL user_id included)
    repo_q = select(Repository)
    if user_id is not None:
        repo_q = repo_q.where(
            (Repository.user_id == user_id) | (Repository.user_id.is_(None))
        )
    # 최근 분석이 있는 리포만 (활성 리포 우선)
    # Only repos with recent analyses (active repos first)
    repos = list(db.scalars(repo_q.limit(50)).all())
    if not repos:
        return []

    # 각 리포별 요약 집계
    # Aggregate summary per repo
    cards = []
    for repo in repos:
        kpi = repo_kpi(db, repo.id, days, now=_now)
        if kpi["analysis_count"] == 0:
            continue  # 해당 기간 내 분석 없는 리포 제외 / Skip repos with no analyses in window

        recurring = repo_recurring_issues(db, repo.id, days, n=20, now=_now)
        recurring_count = len(recurring)

        trend = _score_trend(kpi["score_delta"])

        cards.append({
            "repo_id": repo.id,
            "full_name": repo.full_name,
            "avg_score": kpi["avg_score"],
            "grade": kpi["grade"],
            "recurring_issue_count": recurring_count,
            "score_trend": trend,
            "insights_url": f"/repos/{repo.full_name}/insights",
        })

    # avg_score 내림차순 정렬 후 최대 10개 반환
    # Sort by avg_score descending, return max 10
    cards.sort(key=lambda c: c["avg_score"] or 0, reverse=True)
    return cards[:10]


def _score_trend(score_delta: float | None) -> str:
    """점수 delta → 추세 문자열 변환.

    Convert score delta to trend string.
    """
    if score_delta is None:
        return "flat"
    if score_delta > 1.0:
        return "up"
    if score_delta < -1.0:
        return "down"
    return "flat"
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
pytest tests/unit/services/test_repo_insight_cards.py -v
```
Expected: all PASS.

- [ ] **Step 5: Run full unit suite to catch regressions**

```bash
pytest tests/unit/ -x -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/services/dashboard_service.py \
        tests/unit/services/test_repo_insight_cards.py
git commit -m "feat(service): add repo_insight_cards() to dashboard_service"
```

---

### Task 4: Route `repo_insights.py` + router wiring + route tests

**Files:**
- Create: `tests/unit/api/test_repo_insights_route.py`
- Create: `src/ui/routes/repo_insights.py`
- Modify: `src/ui/router.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/unit/api/test_repo_insights_route.py`:

```python
"""repo_insights 라우트 단위 테스트 — 200/404/권한 격리."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401
from src.auth.session import CurrentUser, require_login
from src.database import Base
from src.main import app
from src.models.repository import Repository
from src.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sess = Session(engine)
    yield sess
    sess.close()
    engine.dispose()


@pytest.fixture()
def test_user(db_session):
    u = User(github_id=1, github_login="owner", email="owner@x.com", display_name="O")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def other_user(db_session):
    u = User(github_id=2, github_login="other", email="other@x.com", display_name="X")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def repo(db_session, test_user):
    r = Repository(full_name="owner/myrepo", user_id=test_user.id)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


def _make_client(db_session, user):
    current = CurrentUser(
        id=user.id,
        github_login=user.github_login,
        email=user.email or "",
        display_name=user.display_name or "",
        plaintext_token="ghp_test",
    )
    from src.ui.routes.repo_insights import _get_db

    app.dependency_overrides[require_login] = lambda: current
    app.dependency_overrides[_get_db] = lambda: db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(require_login, None)
    app.dependency_overrides.pop(_get_db, None)


@pytest.fixture()
def client(db_session, test_user):
    yield from _make_client(db_session, test_user)


@pytest.fixture()
def other_client(db_session, other_user):
    yield from _make_client(db_session, other_user)


def test_insights_page_returns_200(client, repo):
    """GET /repos/owner/myrepo/insights → 200."""
    response = client.get("/repos/owner/myrepo/insights")
    assert response.status_code == 200


def test_insights_page_contains_repo_name(client, repo):
    """인사이트 페이지 HTML에 리포명이 포함된다."""
    response = client.get("/repos/owner/myrepo/insights")
    assert "owner/myrepo" in response.text


def test_unknown_repo_returns_404(client):
    """존재하지 않는 리포 → 404."""
    response = client.get("/repos/nobody/unknown/insights")
    assert response.status_code == 404


def test_other_user_cannot_access_repo(other_client, repo):
    """다른 사용자의 리포 → 404 (권한 격리)."""
    response = other_client.get("/repos/owner/myrepo/insights")
    assert response.status_code == 404


def test_days_parameter_accepted(client, repo):
    """?days=7, ?days=90 모두 200 반환."""
    for days in (7, 90):
        response = client.get(f"/repos/owner/myrepo/insights?days={days}")
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests — expect ImportError / 404 for route not found**

```bash
pytest tests/unit/api/test_repo_insights_route.py -v
```
Expected: FAIL (route doesn't exist yet).

- [ ] **Step 3: Create `src/ui/routes/repo_insights.py`**

```python
"""리포별 코드 인사이트 라우트 — GET /repos/{name}/insights.

Repository code insights route — GET /repos/{name}/insights.
"""
from __future__ import annotations

import logging
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.services.repo_insight_service import (
    repo_ai_suggestions,
    repo_category_breakdown,
    repo_insight_narrative,
    repo_kpi,
    repo_problem_files,
    repo_recurring_issues,
)
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import get_locale, templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db() -> Generator[Session, None, None]:
    """DB 세션 의존성 — 테스트에서 override 가능.

    DB session dependency — overrideable in tests.
    """
    with SessionLocal() as db:
        yield db


def _find_repo(db: Session, repo_name: str, user_id: int):
    """사용자 접근 가능한 리포 조회 — 없거나 권한 없으면 None.

    Find user-accessible repo — returns None if not found or unauthorized.
    """
    from src.models.repository import Repository  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    repo = db.scalar(
        select(Repository).where(Repository.full_name == repo_name)
    )
    if repo is None:
        return None
    if repo.user_id is not None and repo.user_id != user_id:
        return None
    return repo


@router.get("/repos/{repo_name:path}/insights", response_class=HTMLResponse)
async def repo_insights(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = 30,
    refresh: int = 0,
    db: Session = Depends(_get_db),
) -> HTMLResponse:
    """리포별 코드 인사이트 페이지.

    Per-repository code insights page.

    반복 이슈 / 문제 파일 / AI 제안 / 카테고리 비율 / AI 내러티브 (API 키 있을 때).
    Recurring issues / problem files / AI suggestions / category breakdown / AI narrative (when API key set).
    """
    logger.info(
        "repo_insights user_id=%d repo=%s days=%s",
        current_user.id,
        sanitize_for_log(repo_name),
        sanitize_for_log(str(days), max_len=5),
    )

    repo = _find_repo(db, repo_name, current_user.id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    kpi = repo_kpi(db, repo.id, days)
    recurring = repo_recurring_issues(db, repo.id, days)
    problem_files = repo_problem_files(db, repo.id, days)
    ai_suggestions = repo_ai_suggestions(db, repo.id, days)
    breakdown = repo_category_breakdown(db, repo.id, days)

    # AI 내러티브 — API 키 있을 때만 / AI narrative — only when API key is configured
    narrative: dict | None = None
    if settings.anthropic_api_key:
        narrative = await repo_insight_narrative(
            db,
            repo.id,
            days,
            repo_full_name=repo.full_name,
            kpi=kpi,
            recurring=recurring,
            refresh=bool(refresh),
            user_id=current_user.id,
            language=get_locale(request),
        )
        if narrative and narrative.get("status") != "success":
            narrative = None

    return templates.TemplateResponse(
        request,
        "repo_insights.html",
        {
            "current_user": current_user,
            "repo": repo,
            "days": days,
            "kpi": kpi,
            "recurring_issues": recurring,
            "problem_files": problem_files,
            "ai_suggestions": ai_suggestions,
            "breakdown": breakdown,
            "narrative": narrative,
            "locale": get_locale(request),
        },
    )
```

- [ ] **Step 4: Add `repo_insights` router to `src/ui/router.py`**

```python
from src.ui.routes import (
    actions,
    add_repo,
    dashboard,
    detail,
    overview,
    repo_insights,  # ← add this import
    settings,
)

router = APIRouter()

# 구체 경로 → 일반 경로 순
router.include_router(overview.router)
router.include_router(dashboard.router)
router.include_router(add_repo.router)
router.include_router(settings.router)
router.include_router(actions.router)
router.include_router(repo_insights.router)  # ← add before detail (catch-all)
router.include_router(detail.router)
```

> **Note:** `repo_insights` must come before `detail.router` because `/repos/{name}` is a catch-all. Placing `repo_insights` before it ensures `/repos/{name}/insights` is matched first.

- [ ] **Step 5: Create a minimal `src/templates/repo_insights.html` stub** (just enough for the route test to pass — full template comes in Task 5)

```html
{% extends "base.html" %}
{% block title %}{{ repo.full_name }} — Insights{% endblock %}
{% block content %}
<div>{{ repo.full_name }}</div>
{% endblock %}
```

- [ ] **Step 6: Run route tests — expect all pass**

```bash
pytest tests/unit/api/test_repo_insights_route.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ui/routes/repo_insights.py \
        src/ui/router.py \
        src/templates/repo_insights.html \
        tests/unit/api/test_repo_insights_route.py
git commit -m "feat(route): add /repos/{name}/insights route + router wiring"
```

---

### Task 5: CSS + Full Template + CSS integration test

**Files:**
- Create: `src/static/css/repo_insights.css`
- Modify: `src/templates/repo_insights.html` (replace stub with full template)
- Create: `tests/integration/test_repo_insights_css.py`

- [ ] **Step 1: Create `src/static/css/repo_insights.css`**

```css
/* ──────────────────────────────────────────────────────────
   Repo Insights page — scoped .ri-* classes
   CPD 방지: admin.css 분리와 동일 패턴. 독립 파일 분리.
   CPD prevention: same pattern as admin.css separation.
   CSS variables only, no hardcoded hex.
   ────────────────────────────────────────────────────────── */

/* ── 페이지 레이아웃 / Page layout ─────────────────────── */
.ri-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px 64px;
}

/* ── 헤더 / Header ──────────────────────────────────────── */
.ri-header {
  margin-bottom: 28px;
}

.ri-back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-2);
  text-decoration: none;
  margin-bottom: 12px;
  transition: color 0.15s;
}

.ri-back-link:hover {
  color: var(--accent);
}

.ri-repo-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
  background: linear-gradient(135deg, var(--text-1), var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.ri-header-meta {
  font-size: 13px;
  color: var(--text-2);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ri-grade-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 700;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
}

/* ── 기간 선택 버튼 / Period selector ───────────────────── */
.ri-day-selector {
  display: flex;
  gap: 6px;
}

.ri-day-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  color: var(--text-2);
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  transition: background 0.15s, color 0.15s;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}

.ri-day-btn:hover,
.ri-day-btn.active {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
}

/* ── KPI 카드 그리드 / KPI card grid ───────────────────── */
.ri-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.ri-kpi-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px) saturate(150%);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 18px 20px 16px;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
  min-height: 100px;
}

.ri-kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.ri-kpi-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
  margin-bottom: 8px;
}

.ri-kpi-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1;
  margin-bottom: 4px;
}

.ri-kpi-sub {
  font-size: 12px;
  color: var(--text-2);
}

.ri-delta-up   { color: var(--success); }
.ri-delta-down { color: var(--danger); }

/* ── 2열 그리드 (반복 이슈 + 도넛) / 2-col grid ─────────── */
.ri-two-col {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 20px;
  margin-bottom: 24px;
}

/* ── 공통 카드 / Common card ────────────────────────────── */
.ri-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px) saturate(150%);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
}

.ri-card-header {
  padding: 14px 18px 0;
}

.ri-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
  margin: 0 0 14px;
}

/* ── 반복 이슈 테이블 / Recurring issues table ───────────── */
.ri-issues-table {
  width: 100%;
  border-collapse: collapse;
}

.ri-issues-table th {
  text-align: left;
  padding: 8px 18px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-2);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
}

.ri-issues-table tbody tr {
  position: relative;
  border-bottom: 1px solid var(--border-subtle);
  transition: background 0.15s;
}

.ri-issues-table tbody tr:last-child {
  border-bottom: none;
}

.ri-issues-table tbody tr::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.15s;
}

.ri-issues-table tbody tr:hover::before {
  transform: scaleY(1);
}

.ri-issues-table tbody tr:hover {
  background: color-mix(in srgb, var(--accent) 5%, transparent);
}

.ri-issues-table td {
  padding: 10px 18px;
  font-size: 13px;
  color: var(--text-1);
  vertical-align: middle;
}

.ri-issues-table td.ri-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--text-2);
}

/* ── 심각도 배지 / Severity badge ───────────────────────── */
.ri-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.ri-badge-error {
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  color: var(--danger);
  border: 1px solid color-mix(in srgb, var(--danger) 25%, transparent);
}

.ri-badge-warning {
  background: color-mix(in srgb, var(--warning) 15%, transparent);
  color: var(--warning);
  border: 1px solid color-mix(in srgb, var(--warning) 25%, transparent);
}

.ri-badge-tool {
  background: color-mix(in srgb, var(--text-2) 12%, transparent);
  color: var(--text-2);
  border: 1px solid color-mix(in srgb, var(--text-2) 20%, transparent);
}

/* ── 도넛 차트 컨테이너 / Donut chart container ──────────── */
.ri-donut-wrap {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.ri-donut-wrap canvas {
  max-width: 200px;
  max-height: 200px;
}

/* ── 문제 파일 / Problem files ──────────────────────────── */
.ri-file-list {
  padding: 0 18px 16px;
  list-style: none;
  margin: 0;
}

.ri-file-row {
  margin-bottom: 12px;
}

.ri-file-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ri-file-name {
  font-size: 12px;
  font-family: monospace;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 70%;
}

.ri-file-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
}

.ri-file-bar-bg {
  height: 6px;
  background: var(--border-subtle);
  border-radius: 3px;
  overflow: hidden;
}

.ri-file-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-2, var(--accent)));
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* ── AI 제안 / AI suggestions ───────────────────────────── */
.ri-suggestions {
  padding: 0 18px 16px;
  counter-reset: suggestion;
  list-style: none;
  margin: 0;
}

.ri-suggestion-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: flex-start;
  gap: 12px;
  counter-increment: suggestion;
}

.ri-suggestion-item:last-child {
  border-bottom: none;
}

.ri-suggestion-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-2);
  min-width: 20px;
}

.ri-suggestion-text {
  font-size: 13px;
  color: var(--text-1);
  flex: 1;
  line-height: 1.5;
}

.ri-suggestion-count {
  font-size: 11px;
  color: var(--text-2);
  white-space: nowrap;
}

/* ── AI 내러티브 카드 / AI narrative card ───────────────── */
.ri-narrative-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px) saturate(150%);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 20px 22px 22px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}

.ri-narrative-card::after {
  content: "";
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2, var(--accent)));
  border-radius: 0 0 12px 12px;
}

.ri-narrative-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
  margin: 0 0 12px;
}

.ri-narrative-text {
  font-size: 14px;
  color: var(--text-2);
  line-height: 1.75;
  white-space: pre-wrap;
}

/* ── 빈 상태 / Empty state ──────────────────────────────── */
.ri-empty {
  text-align: center;
  padding: 40px 24px;
  color: var(--text-2);
  font-size: 14px;
}

/* ── 반응형 / Responsive ────────────────────────────────── */
@media (max-width: 1024px) {
  .ri-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .ri-page {
    padding: 16px 12px 48px;
  }

  .ri-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .ri-two-col {
    grid-template-columns: 1fr;
  }

  .ri-repo-title {
    font-size: 20px;
  }

  /* WCAG 2.5.5 — 모바일 인터랙티브 요소 최소 44px */
  /* WCAG 2.5.5 — min 44px for mobile interactive elements */
  .ri-day-btn {
    min-height: 44px;
    padding: 0 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ri-kpi-card,
  .ri-issues-table tbody tr::before,
  .ri-file-bar {
    transition: none;
  }
}
```

- [ ] **Step 2: Write the CSS integration test**

Create `tests/integration/test_repo_insights_css.py`:

```python
"""repo_insights.css 통합 테스트 — 필수 클래스 + WCAG 2.5.5 44px 검증.

repo_insights.css integration test — required classes + WCAG 2.5.5 44px check.
"""
from pathlib import Path

import pytest

CSS_PATH = Path("src/static/css/repo_insights.css")


@pytest.fixture(scope="module")
def css_content():
    assert CSS_PATH.exists(), f"{CSS_PATH} not found"
    return CSS_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("cls", [
    ".ri-page",
    ".ri-header",
    ".ri-repo-title",
    ".ri-grade-badge",
    ".ri-kpi-grid",
    ".ri-kpi-card",
    ".ri-kpi-label",
    ".ri-kpi-value",
    ".ri-two-col",
    ".ri-card",
    ".ri-issues-table",
    ".ri-badge-error",
    ".ri-badge-warning",
    ".ri-donut-wrap",
    ".ri-file-bar",
    ".ri-suggestions",
    ".ri-narrative-card",
    ".ri-empty",
    ".ri-day-btn",
])
def test_ri_class_exists(css_content, cls):
    """각 .ri-* 클래스가 CSS 파일에 정의되어 있다."""
    assert cls in css_content, f"Missing CSS class: {cls}"


def test_mobile_44px_applied_to_day_btn(css_content):
    """모바일 @media 분기에 .ri-day-btn min-height: 44px가 있다."""
    # Check that min-height: 44px appears in the media query for .ri-day-btn
    assert "min-height: 44px" in css_content
    # Verify it appears in or near the media query context
    media_idx = css_content.rfind("@media (max-width: 768px)")
    assert media_idx != -1
    mobile_section = css_content[media_idx:]
    assert "44px" in mobile_section


def test_prefers_reduced_motion_present(css_content):
    """prefers-reduced-motion 미디어 쿼리가 포함되어 있다."""
    assert "prefers-reduced-motion" in css_content


def test_no_hardcoded_hex_colors(css_content):
    """CSS 파일에 직접 hex 색상 코드가 없다 (CSS variable 사용 의무)."""
    import re
    # Allow #nnn short hex only if it's inside a class name or CSS selector token (like #id), not a color
    # Match # followed by exactly 3 or 6 hex digits that look like color values
    hex_colors = re.findall(r"(?<![a-zA-Z0-9_-])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])", css_content)
    assert hex_colors == [], f"Found hardcoded hex colors: {hex_colors}"
```

- [ ] **Step 3: Run CSS tests — expect failures (file doesn't exist yet)**

```bash
pytest tests/integration/test_repo_insights_css.py -v
```
Expected: FAIL on `assert CSS_PATH.exists()`.

After creating the CSS file in Step 1, run again — expect all PASS.

- [ ] **Step 4: Replace stub template with full `src/templates/repo_insights.html`**

```html
{% extends "base.html" %}
{% block title %}{{ repo.full_name }} — Insights · SCAManager{% endblock %}

{% block content %}
<link rel="stylesheet" href="/static/css/repo_insights.css">

<div class="ri-page">

  {# ── 헤더 ──────────────────────────────────────────────── #}
  <div class="ri-header">
    <a href="/dashboard" class="ri-back-link">← {{ 'nav.dashboard' | i18n_args(locale | default('ko')) }}</a>
    <div style="display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:12px;">
      <div>
        <h1 class="ri-repo-title">📦 {{ repo.full_name }}</h1>
        <div class="ri-header-meta">
          <span class="ri-grade-badge">{{ kpi.grade }}</span>
          <span>최근 {{ days }}일 · 분석 {{ kpi.analysis_count }}건 기준</span>
          {% if kpi.score_delta is not none %}
            {% if kpi.score_delta > 0 %}
              <span class="ri-delta-up">↑ +{{ kpi.score_delta }}</span>
            {% elif kpi.score_delta < 0 %}
              <span class="ri-delta-down">↓ {{ kpi.score_delta }}</span>
            {% endif %}
          {% endif %}
        </div>
      </div>
      <div class="ri-day-selector">
        {% for d in [7, 30, 90] %}
        <a href="/repos/{{ repo.full_name }}/insights?days={{ d }}"
           class="ri-day-btn {% if days == d %}active{% endif %}">{{ d }}일</a>
        {% endfor %}
      </div>
    </div>
  </div>

  {# ── KPI 4 카드 ─────────────────────────────────────────── #}
  <div class="ri-kpi-grid">
    {# 평균 점수 #}
    <div class="ri-kpi-card reveal">
      <div class="ri-kpi-label">평균 점수</div>
      <div class="ri-kpi-value">
        {% if kpi.avg_score is not none %}{{ kpi.avg_score }}{% else %}—{% endif %}
      </div>
      <div class="ri-kpi-sub">{{ kpi.grade }}등급</div>
    </div>
    {# 총 분석수 #}
    <div class="ri-kpi-card reveal">
      <div class="ri-kpi-label">총 분석수</div>
      <div class="ri-kpi-value">{{ kpi.analysis_count }}</div>
      <div class="ri-kpi-sub">최근 {{ days }}일</div>
    </div>
    {# 최다 반복 이슈 #}
    <div class="ri-kpi-card reveal">
      <div class="ri-kpi-label">최다 반복 이슈</div>
      <div class="ri-kpi-value" style="font-size:16px; word-break:break-word;">
        {% if kpi.top_recurring_issue %}{{ kpi.top_recurring_issue[:40] }}{% else %}—{% endif %}
      </div>
      {% if kpi.top_recurring_count %}
      <div class="ri-kpi-sub">{{ kpi.top_recurring_count }}회 반복</div>
      {% endif %}
    </div>
    {# 보안 HIGH #}
    <div class="ri-kpi-card reveal">
      <div class="ri-kpi-label">보안 HIGH</div>
      <div class="ri-kpi-value {% if kpi.high_security_count > 0 %}ri-delta-down{% endif %}">
        {{ kpi.high_security_count }}건
      </div>
      <div class="ri-kpi-sub">severity: error / HIGH</div>
    </div>
  </div>

  {# ── AI 내러티브 카드 (API 키 있을 때만) ────────────────── #}
  {% if narrative and narrative.text %}
  <div class="ri-narrative-card reveal">
    <div class="ri-narrative-title">🤖 AI 종합 진단</div>
    <p class="ri-narrative-text">{{ narrative.text }}</p>
    <div style="text-align:right; margin-top:8px;">
      <a href="/repos/{{ repo.full_name }}/insights?days={{ days }}&refresh=1"
         style="font-size:11px; color:var(--text-2); text-decoration:none;">↺ 갱신</a>
    </div>
  </div>
  {% endif %}

  {# ── 2열: 반복 이슈 테이블 + 카테고리 도넛 ──────────────── #}
  {% if recurring_issues or breakdown.total > 0 %}
  <div class="ri-two-col">
    {# 반복 이슈 테이블 (좌) #}
    <div class="ri-card">
      <div class="ri-card-header">
        <h2 class="ri-card-title">🔄 반복 이슈 랭킹</h2>
      </div>
      {% if recurring_issues %}
      <table class="ri-issues-table" aria-label="반복 이슈 목록">
        <thead>
          <tr>
            <th>#</th>
            <th>이슈 메시지</th>
            <th>도구</th>
            <th class="ri-num">횟수</th>
          </tr>
        </thead>
        <tbody>
          {% for issue in recurring_issues %}
          <tr class="reveal">
            <td style="color:var(--text-2); font-size:12px;">{{ loop.index }}</td>
            <td>
              <div style="font-size:13px; word-break:break-word;">{{ issue.message }}</div>
              <div style="margin-top:3px; display:flex; gap:4px; flex-wrap:wrap;">
                {% if issue.severity %}
                <span class="ri-badge {% if issue.severity|lower in ('error','high') %}ri-badge-error{% else %}ri-badge-warning{% endif %}">
                  {{ issue.severity }}
                </span>
                {% endif %}
                {% if issue.tool %}
                <span class="ri-badge ri-badge-tool">{{ issue.tool }}</span>
                {% endif %}
              </div>
            </td>
            <td style="font-size:12px; color:var(--text-2);">{{ issue.tool or '—' }}</td>
            <td class="ri-num">{{ issue.count }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <div class="ri-empty">반복 이슈 없음</div>
      {% endif %}
    </div>

    {# 카테고리 비율 도넛 (우) #}
    <div class="ri-card">
      <div class="ri-card-header">
        <h2 class="ri-card-title">📊 카테고리 비율</h2>
      </div>
      <div class="ri-donut-wrap">
        {% if breakdown.total > 0 %}
        <canvas id="riDonutChart" width="200" height="200"
                aria-label="이슈 카테고리 비율 차트"></canvas>
        <div style="margin-top:12px; font-size:12px; color:var(--text-2); text-align:center;">
          전체 {{ breakdown.total }}건
        </div>
        {% else %}
        <div class="ri-empty">집계 데이터 없음</div>
        {% endif %}
      </div>
    </div>
  </div>
  {% endif %}

  {# ── 문제 파일 TOP 5 ─────────────────────────────────────── #}
  {% if problem_files %}
  <div class="ri-card">
    <div class="ri-card-header">
      <h2 class="ri-card-title">📁 문제 파일 TOP {{ problem_files|length }}</h2>
    </div>
    <ul class="ri-file-list">
      {% for f in problem_files %}
      <li class="ri-file-row reveal">
        <div class="ri-file-info">
          <span class="ri-file-name" title="{{ f.file }}">{{ f.file }}</span>
          <span class="ri-file-count">{{ f.count }}회</span>
        </div>
        <div class="ri-file-bar-bg">
          <div class="ri-file-bar" style="width: {{ f.pct }}%;"></div>
        </div>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  {# ── AI 제안 모음 TOP 10 ─────────────────────────────────── #}
  {% if ai_suggestions %}
  <div class="ri-card">
    <div class="ri-card-header">
      <h2 class="ri-card-title">💡 AI 제안 모음</h2>
    </div>
    <ol class="ri-suggestions">
      {% for s in ai_suggestions %}
      <li class="ri-suggestion-item reveal">
        <span class="ri-suggestion-num">{{ loop.index }}</span>
        <span class="ri-suggestion-text">{{ s.suggestion }}</span>
        {% if s.count > 1 %}
        <span class="ri-suggestion-count">{{ s.count }}회 언급</span>
        {% endif %}
      </li>
      {% endfor %}
    </ol>
  </div>
  {% endif %}

  {# 분석 데이터 없을 때 empty state #}
  {% if kpi.analysis_count == 0 %}
  <div class="ri-card">
    <div class="ri-empty">
      <p>최근 {{ days }}일 내 분석 데이터가 없습니다.</p>
      <small>GitHub Push 또는 PR 이벤트 발생 후 다시 확인하세요.</small>
    </div>
  </div>
  {% endif %}

</div>
{% endblock %}

{% block scripts %}
{% if breakdown.total > 0 %}
<script src="/static/vendor/chart.umd.min.js"></script>
<script>
(function() {
  const breakdown = {{ breakdown | tojson }};

  function readVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  let riChart = null;
  function buildRiChart() {
    const ctx = document.getElementById('riDonutChart');
    if (!ctx) return;
    if (riChart) riChart.destroy();
    riChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['보안 오류', '보안 경고', '코드품질 오류', '코드품질 경고'],
        datasets: [{
          data: [
            breakdown.security_error,
            breakdown.security_warning,
            breakdown.code_quality_error,
            breakdown.code_quality_warning,
          ],
          backgroundColor: [
            readVar('--danger',  '#ef4444'),
            readVar('--warning', '#f59e0b'),
            readVar('--accent',  '#6366f1'),
            readVar('--text-2',  '#9ca3af'),
          ],
          borderWidth: 0,
        }],
      },
      options: {
        cutout: '62%',
        plugins: { legend: { display: false } },
        animation: { duration: 500 },
      },
    });
  }

  buildRiChart();
  document.addEventListener('themechange', buildRiChart);
})();
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/unit/api/test_repo_insights_route.py tests/integration/test_repo_insights_css.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/static/css/repo_insights.css \
        src/templates/repo_insights.html \
        tests/integration/test_repo_insights_css.py
git commit -m "feat(ui): add repo_insights.css + full repo_insights.html template"
```

---

### Task 6: Dashboard integration — repo card section

**Files:**
- Modify: `src/ui/routes/dashboard.py`
- Modify: `src/templates/dashboard.html`

- [ ] **Step 1: Add `repo_insight_cards()` call to `src/ui/routes/dashboard.py`**

In the `dashboard()` route, add `repo_insight_cards` to the overview mode context. Find the existing `merge_failures` line and add after it:

```python
        merge_failures = dashboard_service.merge_failure_distribution(db, days=days, n=5, user_id=_uid)
        # 0031 — 리포별 인사이트 카드 섹션 (overview 모드 전용)
        # 0031 — Per-repo insight card section (overview mode only)
        repo_cards = dashboard_service.repo_insight_cards(db, days=days, user_id=_uid)
        feedback = dashboard_service.feedback_status(db)
```

Add `"repo_cards": repo_cards` to the `TemplateResponse` context dict for overview mode:

```python
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": current_user,
            "mode": "overview",
            "initial_mode": effective_mode,
            "kpi": kpi,
            "trend": trend,
            "frequent_issues": frequent_issues,
            "auto_merge": auto_merge,
            "merge_failures": merge_failures,
            "repo_cards": repo_cards,     # ← add this
            "feedback": feedback,
            "days": days,
            "locale": locale_value,
        },
    )
```

- [ ] **Step 2: Add repo card section to `src/templates/dashboard.html`**

Insert the following block inside the `{% if mode == 'overview' %}` section, after the `merge_failures` block (after line 841 — the closing `{% endif %}` of the merge_failures section, before the final `{% endif %}`):

```html
  {# 0031 — 리포별 인사이트 카드 섹션 / Per-repo insight card section #}
  {% if repo_cards %}
  <div style="margin-top: 24px;">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:8px;">
      <h2 class="dash-section-title">🗂 리포별 인사이트</h2>
      <span style="font-size:12px; color:var(--text-2);">최근 {{ days }}일</span>
    </div>
    <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:16px;">
      {% for card in repo_cards %}
      <a href="{{ card.insights_url }}" style="text-decoration:none;"
         class="reveal">
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle);
                    border-radius:12px; padding:16px 18px; transition:transform 0.2s, box-shadow 0.2s;"
             onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='var(--shadow-md)'"
             onmouseleave="this.style.transform=''; this.style.boxShadow=''">
          <div style="font-size:13px; font-weight:600; color:var(--text-1); margin-bottom:8px;
                      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
               title="{{ card.full_name }}">{{ card.full_name }}</div>
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="display:inline-flex; align-items:center; padding:2px 10px;
                         border-radius:20px; font-size:13px; font-weight:700;
                         background:color-mix(in srgb, var(--accent) 15%, transparent);
                         color:var(--accent); border:1px solid color-mix(in srgb, var(--accent) 30%, transparent);">
              {{ card.grade }}
            </span>
            {% if card.avg_score is not none %}
            <span style="font-size:20px; font-weight:700; color:var(--text-1);">{{ card.avg_score }}</span>
            {% endif %}
          </div>
          <div style="font-size:12px; color:var(--text-2); margin-bottom:4px;">
            반복이슈 {{ card.recurring_issue_count }}종
          </div>
          <div style="font-size:12px; color:var(--text-2);">
            추세
            {% if card.score_trend == 'up' %}
              <span style="color:var(--success);">↑ 개선</span>
            {% elif card.score_trend == 'down' %}
              <span style="color:var(--danger);">↓ 하락</span>
            {% else %}
              <span>→ 유지</span>
            {% endif %}
          </div>
          <div style="margin-top:10px; font-size:12px; color:var(--accent); font-weight:600;">
            인사이트 보기 →
          </div>
        </div>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}
```

> **Where to insert:** Open `src/templates/dashboard.html`, search for `{% endif %}{# end of mode == 'overview'`. The block goes immediately before that final `{% endif %}`.

- [ ] **Step 3: Run route tests to confirm no regressions**

```bash
pytest tests/unit/api/test_repo_insights_route.py tests/unit/services/ -v
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/ui/routes/dashboard.py \
        src/templates/dashboard.html
git commit -m "feat(dashboard): add repo insight cards section to overview mode"
```

---

### Task 7: Architecture docs sync + final validation

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update `docs/architecture.md` — `src/` tree section**

Add the following entries in the appropriate sections:

In `services/` block, after `dashboard_service.py` line:
```
│   ├── repo_insight_service.py  # 리포별 집계 6 함수 (repo_kpi/recurring_issues/problem_files/ai_suggestions/category_breakdown/insight_narrative)
```

In `static/css/` block, after `admin.css` line:
```
│   ├── css/repo_insights.css    # 리포별 인사이트 페이지 전용 스타일 — .ri-* 클래스 (CPD 분리)
```

In the `ui/routes/` line description, update to include `repo_insights`:
```
│   └── routes/                  # overview / dashboard (mode 4종) / add_repo / settings / actions / detail / admin / repo_insights
```

In `templates/` line, add `repo_insights`:
```
├── templates/                   # base, login, overview, repo_detail, analysis_detail, settings, dashboard, admin_*, repo_insights
```

In `models/` line, update `insight_narrative_cache` mention to note `repo_id` FK:
```
├── models/                      # 10 ORM 모델 — repository, analysis, analysis_feedback, repo_config, gate_decision, merge_attempt, merge_retry, security_alert_log, insight_narrative_cache (0031: repo_id FK), user
```

Also update `dashboard_service.py` description:
```
│   ├── dashboard_service.py     # /dashboard 10 공개 함수 (KPI 4 + trend + frequent_issues + auto_merge_kpi + feedback_status + insight_narrative + dashboard_security + dashboard_usage + repo_insight_cards) + RLS 격리 헬퍼 2건
```

- [ ] **Step 2: Run the complete test suite**

```bash
pytest tests/unit/ tests/integration/ -x -q
```
Expected: all pass (no regressions introduced).

- [ ] **Step 3: Run lint**

```bash
make lint
```
Expected: pass (no new pylint/flake8/bandit issues).

- [ ] **Step 4: Commit docs + final check**

```bash
git add docs/architecture.md
git commit -m "docs(arch): sync architecture.md for repo insights feature (0031)"
```

- [ ] **Step 5: Push branch + create PR**

```bash
git push -u origin feat/repo-insights-page
```

Then open PR with:
- Title: `feat: per-repository code insights page (/repos/{name}/insights)`
- Body should include:
  - Summary of new files + modified files
  - `🔍 사용자 검증 필요` section with 8-combination visual checklist (dark/light/glass/claude-dark × desktop/mobile)
  - Note: `Claude 시각 검증 불가 — 4-테마 × 모바일/데스크탑 8 조합 사용자 검증 의무`
  - `code-scanning open alerts: 0` (check GitHub Security tab before merge)

---

## Quick Reference: Key Invariants

| Rule | Source |
|------|--------|
| `_MAX_ANALYSES = 30` — all service functions cap at 30 rows | spec §8 |
| `repo_id=NULL` rows in `insight_narrative_cache` = global cache (not broken by 0031) | spec §4.3 |
| `.ri-*` prefix for all CSS classes in `repo_insights.css` | spec §7 |
| `repo_insights` router must be included before `detail` router in `router.py` | FastAPI path matching order |
| `ai_review_status != "success"` → excluded from `repo_ai_suggestions` | spec §6.2 |
| `pct = count / max_count * 100` (not total) for progress bars | spec §4.1 |
| AI narrative shown only when `settings.anthropic_api_key` is set AND `status == "success"` | spec §6.2 |
| Route uses `_find_repo()` with `user_id` check — not `get_accessible_repo()` because we need the Depends injectable `_get_db` to be overrideable in tests | Task 4 design |
