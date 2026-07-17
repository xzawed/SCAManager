import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.repo_config import RepoConfig
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData


@pytest.fixture
def db():
    """인메모리 SQLite 세션 — 각 테스트마다 독립 DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 기존 동작 유지 테스트
# Tests verifying that existing behaviour is preserved.
# ---------------------------------------------------------------------------

def test_get_repo_config_returns_default_when_not_found(db):
    """존재하지 않는 repo 조회 시 기본값 RepoConfigData가 반환된다."""
    config = get_repo_config(db, "owner/nonexistent")
    assert config.repo_full_name == "owner/nonexistent"
    # 기존 필드 — approve_mode로 rename 후에도 기본값은 "disabled"
    assert config.approve_mode == "disabled"
    assert config.approve_threshold == 75
    assert config.reject_threshold == 50
    assert config.notify_chat_id is None


def test_upsert_creates_new_config(db):
    """신규 RepoConfig가 DB에 생성되어야 한다."""
    data = RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        approve_threshold=80,
        reject_threshold=45,
    )
    record = upsert_repo_config(db, data)
    assert record.id is not None
    assert record.approve_mode == "auto"
    assert record.approve_threshold == 80


def test_upsert_updates_existing_config(db):
    """기존 RepoConfig가 업데이트되고 중복 생성되지 않아야 한다."""
    upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo", approve_mode="auto"))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="semi-auto",
        approve_threshold=90,
    ))
    assert record.approve_mode == "semi-auto"
    assert record.approve_threshold == 90
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo").count() == 1


def test_get_repo_config_returns_existing(db):
    """저장된 RepoConfig가 올바르게 조회된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        notify_chat_id="-100999",
    ))
    config = get_repo_config(db, "owner/repo")
    assert config.approve_mode == "auto"
    assert config.notify_chat_id == "-100999"


# ---------------------------------------------------------------------------
# 신규 필드 기본값 테스트 (Red: pr_review_comment, merge_threshold 미존재)
# ---------------------------------------------------------------------------

def test_repo_config_data_new_fields_defaults():
    """RepoConfigData에 신규 필드가 있고 기본값이 올바른지 검증한다."""
    # pr_review_comment 기본값은 True
    config = RepoConfigData(repo_full_name="owner/repo")
    assert config.pr_review_comment is True
    # merge_threshold 기본값은 75
    assert config.merge_threshold == 75
    # approve_mode 기본값은 "disabled" (gate_mode rename)
    assert config.approve_mode == "disabled"
    # approve_threshold 기본값은 75 (auto_approve_threshold rename)
    assert config.approve_threshold == 75
    # reject_threshold 기본값은 50 (auto_reject_threshold rename)
    assert config.reject_threshold == 50


def test_get_repo_config_default_pr_review_comment_is_true(db):
    """존재하지 않는 repo 조회 시 pr_review_comment 기본값이 True인지 검증한다."""
    config = get_repo_config(db, "owner/new-repo")
    assert config.pr_review_comment is True


def test_get_repo_config_default_merge_threshold_is_75(db):
    """존재하지 않는 repo 조회 시 merge_threshold 기본값이 75인지 검증한다."""
    config = get_repo_config(db, "owner/new-repo-2")
    assert config.merge_threshold == 75


def test_get_repo_config_default_auto_merge_is_false(db):
    """존재하지 않는 repo 조회 시 auto_merge 기본값이 False인지 검증한다."""
    config = get_repo_config(db, "owner/nonexistent-auto-merge")
    assert config.auto_merge is False


# ---------------------------------------------------------------------------
# 신규 필드 저장/조회 테스트 (Red: DB 컬럼 미존재)
# Tests for new field persistence (Red phase: DB column does not exist yet).
# ---------------------------------------------------------------------------

def test_get_repo_config_returns_new_fields(db):
    """get_repo_config()가 신규 필드(pr_review_comment, merge_threshold)를 포함한다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        pr_review_comment=False,
        merge_threshold=80,
    ))
    config = get_repo_config(db, "owner/repo")
    assert config.pr_review_comment is False
    assert config.merge_threshold == 80


def test_upsert_repo_config_with_pr_review_comment_false(db):
    """pr_review_comment=False로 upsert 시 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-noreview",
        approve_mode="auto",
        pr_review_comment=False,
    )
    record = upsert_repo_config(db, data)
    assert record.pr_review_comment is False


def test_upsert_repo_config_with_merge_threshold(db):
    """merge_threshold 값이 지정되면 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-mergethresh",
        approve_mode="auto",
        auto_merge=True,
        merge_threshold=85,
    )
    record = upsert_repo_config(db, data)
    assert record.merge_threshold == 85


def test_upsert_updates_pr_review_comment(db):
    """pr_review_comment를 True → False로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle",
        approve_mode="auto",
        pr_review_comment=True,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle",
        approve_mode="auto",
        pr_review_comment=False,
    ))
    assert record.pr_review_comment is False
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-toggle").count() == 1


def test_upsert_updates_merge_threshold(db):
    """merge_threshold를 75 → 90으로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-thresh",
        approve_mode="auto",
        merge_threshold=75,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-thresh",
        approve_mode="auto",
        merge_threshold=90,
    ))
    assert record.merge_threshold == 90
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-thresh").count() == 1


# ---------------------------------------------------------------------------
# auto_merge 기존 테스트 — approve_mode 필드명 기준으로 유지
# ---------------------------------------------------------------------------

def test_upsert_creates_config_with_auto_merge_true(db):
    """auto_merge=True로 RepoConfig 생성 시 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-merge",
        approve_mode="auto",
        auto_merge=True,
    )
    record = upsert_repo_config(db, data)
    assert record.auto_merge is True


def test_upsert_updates_auto_merge_flag(db):
    """auto_merge를 False → True로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-flag",
        approve_mode="auto",
        auto_merge=False,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-flag",
        approve_mode="auto",
        auto_merge=True,
    ))
    assert record.auto_merge is True
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-flag").count() == 1


# ---------------------------------------------------------------------------
# P1 — approve_threshold >= reject_threshold 검증
# ---------------------------------------------------------------------------

def test_upsert_raises_when_approve_threshold_less_than_reject(db):
    """approve_threshold < reject_threshold 이면 ValueError가 발생해야 한다."""
    with pytest.raises(ValueError, match="approve_threshold"):
        upsert_repo_config(db, RepoConfigData(
            repo_full_name="owner/invalid",
            approve_threshold=40,
            reject_threshold=60,
        ))


def test_upsert_allows_equal_thresholds(db):
    """approve_threshold == reject_threshold 이면 정상 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/equal",
        approve_threshold=60,
        reject_threshold=60,
    ))
    assert record.approve_threshold == 60
    assert record.reject_threshold == 60


def test_upsert_allows_approve_greater_than_reject(db):
    """approve_threshold > reject_threshold 이면 정상 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/normal",
        approve_threshold=75,
        reject_threshold=50,
    ))
    assert record.approve_threshold == 75
    assert record.reject_threshold == 50


# ---------------------------------------------------------------------------
# 🔴 threshold 범위(0~100) + merge >= reject 불변식 — UI 폼 경로의 검증 부재 봉인
#
# REST API(`RepoConfigUpdate`)는 이미 `Field(ge=0, le=100)` 로 검증하지만 **UI 폼 경로는
# `int(form.get(...))` 뿐**이라 -999 / 101 이 그대로 저장됐다 = 계층 비대칭.
# 두 경로 모두 `upsert_repo_config` 를 지나므로 여기서 막으면 양쪽이 동시에 닫힌다.
# (UI 는 기존 `except ValueError → ?save_error=1` 핸들러가 그대로 표면화한다.)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("approve_threshold", -1),
    ("approve_threshold", 101),
    ("reject_threshold", -1),
    ("reject_threshold", 101),
    ("merge_threshold", -1),
    ("merge_threshold", 101),
])
def test_upsert_raises_when_threshold_out_of_range(db, field, value):
    """threshold 가 0~100 밖이면 ValueError — 점수 범위(0~100)와 정합."""
    kwargs = {"repo_full_name": f"owner/range-{field}-{value}"}
    # approve >= reject 불변식에 먼저 걸리지 않도록 나머지 필드는 안전한 값으로 고정
    if field == "reject_threshold" and value == 101:
        kwargs["approve_threshold"] = 101  # approve >= reject 는 만족시키고 범위만 위반
    kwargs[field] = value
    with pytest.raises(ValueError, match="0~100|0-100"):
        upsert_repo_config(db, RepoConfigData(**kwargs))


@pytest.mark.parametrize("value", [0, 100])
def test_upsert_allows_threshold_boundary_values(db, value):
    """경계값 0/100 은 유효 — 배타가 아니라 포함 범위다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name=f"owner/boundary-{value}",
        approve_threshold=value,
        reject_threshold=value,
        merge_threshold=value,
    ))
    assert record.merge_threshold == value


def test_upsert_raises_when_merge_threshold_below_reject(db):
    """🔴 merge_threshold < reject_threshold = 자기모순 — 반려할 점수를 머지한다.

    이것이 이 가드의 **보안적 의미**다. 단순 범위 검증만으로는 공격을 못 막는다 —
    `merge_threshold=0` 은 0~100 범위 **안**이고 `score >= 0` 은 항상 참이라
    `-999` 와 효과가 동일하기 때문이다. reject 와의 관계로만 자기모순을 잡을 수 있다.
    """
    with pytest.raises(ValueError, match="merge_threshold"):
        upsert_repo_config(db, RepoConfigData(
            repo_full_name="owner/contradiction",
            approve_threshold=75,
            reject_threshold=50,
            merge_threshold=0,   # 50점 미만은 반려하면서 0점도 머지 = 모순
        ))


def test_upsert_allows_merge_threshold_equal_to_reject(db):
    """merge_threshold == reject_threshold 는 유효 — 경계는 모순이 아니다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/merge-eq-reject",
        approve_threshold=75,
        reject_threshold=50,
        merge_threshold=50,
    ))
    assert record.merge_threshold == 50


def test_upsert_allows_merge_zero_when_reject_zero(db):
    """🔴 reject_threshold=0 이면 merge_threshold=0 도 유효 — 의도적 '전부 머지'.

    아무것도 반려하지 않겠다고 선언한 사용자에게 "전부 머지"는 모순이 아니다.
    이 가드는 **모순**을 막는 것이지 관대한 설정 자체를 금지하는 게 아니다.
    """
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/permissive",
        approve_threshold=0,
        reject_threshold=0,
        merge_threshold=0,
    ))
    assert record.merge_threshold == 0


# ---------------------------------------------------------------------------
# 신규 필드 — commit_comment, create_issue
# ---------------------------------------------------------------------------

def test_repo_config_data_commit_comment_default_false():
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.commit_comment is False


def test_repo_config_data_create_issue_default_false():
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.create_issue is False


def test_upsert_persists_commit_comment(db):
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-cc",
        commit_comment=True,
    ))
    assert record.commit_comment is True

    got = get_repo_config(db, "owner/repo-cc")
    assert got.commit_comment is True


def test_upsert_persists_create_issue(db):
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-ci",
        create_issue=True,
    ))
    assert record.create_issue is True

    got = get_repo_config(db, "owner/repo-ci")
    assert got.create_issue is True


def test_upsert_updates_commit_comment_and_create_issue(db):
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-both",
        commit_comment=False,
        create_issue=False,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-both",
        commit_comment=True,
        create_issue=True,
    ))
    assert record.commit_comment is True
    assert record.create_issue is True
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-both").count() == 1
