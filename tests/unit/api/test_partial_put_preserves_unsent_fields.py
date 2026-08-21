"""부분 PUT 이 **보내지 않은 필드를 덮어쓰지 않는다** (2026-08-21 실측).

## 사고 — 실행으로 확증한 것

`PUT /api/repos/{repo}/config` 는 `RepoConfigUpdate` 를 받아 `**body.model_dump()` 로
통째로 upsert 했다. Pydantic 은 **보내지 않은 필드를 기본값으로 채우므로**,
필드 하나만 바꾸는 PUT 이 나머지 16개를 공장 기본값으로 되돌린다.

실행 확인(추론 아님):

    RepoConfigUpdate(approve_mode="auto")              -> ai_review_enabled = True
    RepoConfigUpdate(discord_webhook_url="https://x")  -> ai_review_enabled = True
    RepoConfigUpdate(ai_review_enabled=False, ...)     -> False   (대조군)

🔴 **가설이 아니라 공표된 사용 계약이다.** 이 엔드포인트의 테스트 호출 15건이 전부
부분 바디(17+ 필드 중 1~6개)이고, `ai_review_enabled` 를 포함한 것은 **0건**이다.

## 왜 비싼가

2026-08 실측: repo 하나가 켜진 채 남아 월 Anthropic 할당량의 **99.96%**
($27.31/$27.32 · 510/512 호출)를 쓰고 HTTP 400(할당량 소진)으로 멈췄다.
지금 6개 repo 가 전부 `false` 인데, 부분 PUT 한 번이면 조용히 되켜진다.

## 범위 — 한 필드가 아니라 모델 전체 (Grok claim-review `01a02424` G4)

`pr_review_comment: bool = True` · `auto_merge: bool = False` 등 **기본값이 있는 모든 필드**가
같은 모양이다. 「비싼 것 하나만 고치기」는 부분 수정이고, 다음 필드에서 같은 사고가 난다.

## 방식 — Optional 이 아니라 `exclude_unset` (Grok G3)

필드 선언을 바꾸지 않는다. `model_fields_set` 이 **보낸 필드만** 알려주므로
`model_dump(exclude_unset=True)` 로 그것만 뽑아 기존 설정 위에 얹는다.
선언을 유지하므로 `check_config_5way_sync.py` 의 3-way 필드 집합 대조가 그대로 초록이다.
422(불완전 바디 거부)는 위 15건이 공표한 부분 PUT 계약을 깨뜨리므로 택하지 않았다.
"""
from __future__ import annotations

import os
from dataclasses import fields as dc_fields

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402

from src.api.repos import RepoConfigUpdate  # noqa: E402
from src.config_manager.manager import RepoConfigData  # noqa: E402


# ── ① 계기: 보낸 필드를 식별할 수 있는가 ────────────────────────────────


def test_pydantic_reports_which_fields_were_actually_sent():
    """🔴 이 능력이 없으면 나머지 축이 전부 불가능하다 — 대조군 먼저."""
    m = RepoConfigUpdate(approve_mode="auto")

    assert m.model_fields_set == {"approve_mode"}, (
        f"보낸 필드를 식별하지 못한다: {m.model_fields_set}"
    )
    assert m.model_dump(exclude_unset=True) == {"approve_mode": "auto"}


# ── ② 사고 재현 — 부분 바디가 기본값을 강제한다 ─────────────────────────


@pytest.mark.parametrize("payload", [
    {"approve_mode": "auto"},
    {"discord_webhook_url": "https://example.invalid/x"},
    {"approve_threshold": 90, "reject_threshold": 40},
])
def test_full_dump_would_force_defaults_on_unsent_fields(payload):
    """🔴 사고의 기전을 고정한다 — `model_dump()`(전체)는 안 보낸 것을 채운다.

    이 테스트는 **고쳐도 계속 통과한다**. 고치는 것은 라우트가 무엇을 쓰느냐이지
    Pydantic 의 기본값 채움 자체가 아니다. 기전을 잊지 않기 위해 남긴다.
    """
    m = RepoConfigUpdate(**payload)

    assert m.model_dump()["ai_review_enabled"] is True, "기전 전제가 깨졌다"
    assert "ai_review_enabled" not in m.model_dump(exclude_unset=True), (
        "exclude_unset 이 보내지 않은 필드를 여전히 담는다 — 이 수정의 토대가 무너진다"
    )


# ── ③ 봉인 — 모델 전체가 대상이다 (한 필드 패치 금지) ────────────────────


def test_every_defaulted_field_is_omitted_when_unsent():
    """🔴 `ai_review_enabled` 만이 아니라 **기본값 있는 전 필드**가 같은 위험이다.

    한 필드만 고치면 다음 필드에서 같은 사고가 난다(Grok `01a02424` G4).
    """
    m = RepoConfigUpdate(approve_mode="auto")
    full = m.model_dump()
    partial = m.model_dump(exclude_unset=True)

    defaulted = set(full) - set(partial)
    assert len(defaulted) >= 10, (
        f"기본값으로 채워지는 필드가 {len(defaulted)}개뿐 — 모델 형태가 바뀌었는지 확인"
    )
    for name in ("ai_review_enabled", "pr_review_comment", "auto_merge", "commit_comment"):
        assert name in defaulted, f"`{name}` 이 부분 바디에서 강제 채움 대상이 아니다"


def test_explicit_false_is_preserved_not_treated_as_unsent():
    """🔴 대조군 — 명시적 `false` 는 「안 보냄」과 구별돼야 한다.

    이 둘을 섞으면 사용자가 **끄려고 보낸 false** 가 무시된다 — 반대 방향의 같은 사고다.
    """
    m = RepoConfigUpdate(ai_review_enabled=False, approve_mode="auto")

    assert "ai_review_enabled" in m.model_fields_set
    assert m.model_dump(exclude_unset=True)["ai_review_enabled"] is False


# ── ④ 3-way 싱크 가드를 깨지 않는다 ─────────────────────────────────────


def test_field_declarations_are_unchanged_so_the_parity_guard_stays_green():
    """🔴 `Optional` 로 바꾸지 않은 이유 — 필드 집합 대조가 깨지면 안 된다.

    `check_config_5way_sync.py` 는 ORM ↔ RepoConfigData ↔ RepoConfigUpdate 의
    **필드 이름 집합**을 대조한다. 선언을 유지하고 라우트만 고치면 그 축은 무사하다.
    """
    update_fields = set(RepoConfigUpdate.model_fields)
    data_fields = {f.name for f in dc_fields(RepoConfigData)} - {"repo_full_name"}

    missing = data_fields - update_fields
    assert not missing, f"RepoConfigUpdate 에 없는 RepoConfigData 필드: {sorted(missing)}"


# ── ⑤ 🔴 결정적 축 — 실 DB 라우트가 기존 값을 보존하는가 ─────────────────
#
# 🔴 기존 `test_repos.py` 는 `upsert_repo_config` 를 **통째로 mock** 한다. 그래서
#    「무엇이 실제로 저장되는가」를 원리적으로 볼 수 없고, 이 버그를 못 잡았다.
#    이 리포는 그 함정을 이미 실측했다(메모리: SessionLocal Mock 은 ORM 오류 미감지).
#    아래는 진짜 SQLite 세션으로 라우트를 태우고 **DB 를 다시 읽는다**.

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from unittest.mock import patch  # noqa: E402

from src.database import Base  # noqa: E402
from src.models.repo_config import RepoConfig  # noqa: E402


@pytest.fixture()
def real_db_client():
    """진짜 세션으로 라우트를 태운다 — mock 이 아니다."""
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    from src.main import app  # pylint: disable=import-outside-toplevel
    with patch("src.api.repos.SessionLocal", Session):
        yield TestClient(app), Session


def _seed(Session, **kw):
    with Session() as db:
        db.add(RepoConfig(repo_full_name="owner/repo", **kw))
        db.commit()


def _read(Session, field):
    with Session() as db:
        return getattr(db.query(RepoConfig).filter_by(repo_full_name="owner/repo").one(), field)


def test_partial_put_does_not_reenable_ai_review(real_db_client):
    """🔴 이 수정의 핵심 — 끈 것이 부분 PUT 으로 되켜지면 안 된다.

    2026-08 실측: repo 하나가 켜진 채 남아 월 할당량의 99.96%를 썼다.
    지금 6개가 전부 꺼져 있는데, 이 경로 하나가 조용히 되켠다.
    """
    client, Session = real_db_client
    _seed(Session, ai_review_enabled=False, approve_mode="disabled")

    r = client.put("/api/repos/owner%2Frepo/config", json={"approve_mode": "auto"})

    assert r.status_code == 200, r.text
    assert _read(Session, "approve_mode") == "auto", "보낸 필드가 반영되지 않았다"
    assert _read(Session, "ai_review_enabled") is False, (
        "🔴 보내지 않은 `ai_review_enabled` 가 True 로 덮였다 — 월 할당량이 다시 탄다"
    )


def test_partial_put_preserves_every_unsent_field(real_db_client):
    """🔴 한 필드가 아니라 **전 필드**다 (Grok `01a02424` G4)."""
    client, Session = real_db_client
    _seed(Session, ai_review_enabled=False, pr_review_comment=False,
          auto_merge=True, merge_threshold=95, approve_mode="disabled")

    r = client.put("/api/repos/owner%2Frepo/config", json={"approve_mode": "semi-auto"})

    assert r.status_code == 200, r.text
    for field, expected in [("ai_review_enabled", False), ("pr_review_comment", False),
                            ("auto_merge", True), ("merge_threshold", 95)]:
        assert _read(Session, field) == expected, (
            f"보내지 않은 `{field}` 가 {_read(Session, field)} 로 덮였다 (기대 {expected})"
        )


def test_explicit_value_still_wins(real_db_client):
    """🔴 대조군 — 명시적으로 보낸 값은 반드시 써져야 한다.

    이 축이 없으면 「아무것도 안 쓰는」 구현이 위 두 테스트를 통과한다.
    """
    client, Session = real_db_client
    _seed(Session, ai_review_enabled=False, approve_mode="disabled")

    r = client.put("/api/repos/owner%2Frepo/config",
                   json={"ai_review_enabled": True, "approve_mode": "auto"})

    assert r.status_code == 200, r.text
    assert _read(Session, "ai_review_enabled") is True, "명시적으로 보낸 값이 무시됐다"


def test_response_reports_what_was_stored_not_the_request_echo(real_db_client):
    """🔴 응답이 **요청 에코**면 호출자에게 거짓 상태를 보여준다.

    구판은 `**body.model_dump()` 를 그대로 돌려줬다 — 보내지 않은 필드까지 공장
    기본값으로 에코해, 저장된 값과 다른 것을 응답에 실었다. 호출자가 그 응답을
    믿고 「AI 리뷰가 켜졌구나」로 읽으면 실제 저장 상태와 어긋난다.

    🔴 이 축이 없으면 응답만 에코로 되돌리는 변경이 **살아남는다**(실측: 뮤테이션
    `echo_request` 가 다른 9건을 전부 통과했다).
    """
    client, Session = real_db_client
    _seed(Session, ai_review_enabled=False, auto_merge=True, approve_mode="disabled")

    r = client.put("/api/repos/owner%2Frepo/config", json={"approve_mode": "auto"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_review_enabled"] is False, (
        "응답이 저장값(False)이 아니라 요청 기본값(True)을 돌려준다"
    )
    assert body["auto_merge"] is True, "응답이 저장값(True)이 아니라 기본값(False)을 돌려준다"
    assert body["ai_review_enabled"] == _read(Session, "ai_review_enabled")
    assert body["auto_merge"] == _read(Session, "auto_merge")
