"""웹 UI 저장이 폼에 없는 설정을 지운다 — 조용한 데이터 유실 (감사 A1, #1519).

🔴 실측. `src/ui/routes/settings.py` 의 POST 는 `RepoConfigData(...)` 를 폼에서
조립하는데 **21개 필드 중 19개만** 넘긴다. 빠지는 둘:

    notification_language
    disabled_tools

`upsert_repo_config` 는 `for name in field_names: setattr(record, name, ...)` 로
**전 필드를 무조건 덮어쓴다**(`config_manager/manager.py`). 그래서 UI 에서 아무 설정이나
저장하면 두 필드가 dataclass 기본값(`None`·`[]`)으로 날아가고, 라우트는 `?saved=1` 로
**성공을 표시한다.**

🔴 **형제는 이미 고쳐져 있다.** REST `PUT /api/repos/{repo}/config`
(`src/api/repos.py`)는 `model_dump(exclude_unset=True)` 로 보낸 것만 골라 현재 값 위에
덮는다. 그 docstring 은 「one-field PUT 이 나머지 열여섯을 리셋했다」고 적는다 —
같은 결함이 REST 에서만 고쳐지고 UI 경로는 남았다.

그래서 이 파일은 두 가지를 봉인한다:
1. 행동 — UI 저장이 폼에 없는 필드를 보존한다.
2. 구조 — `RepoConfigData` 에 필드를 새로 추가하면, UI 가 그것을 **폼에서 받든
   현재 값에서 보존하든** 둘 중 하나를 하게 강제한다. 안 하면 여기가 red 다.
   (1)만 있으면 다음에 추가되는 필드가 같은 방식으로 조용히 유실된다.

The REST path already merges via exclude_unset; the UI path still overwrites.
"""
from __future__ import annotations

import ast
import io
import os
from dataclasses import fields as dataclass_fields
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# 🔴 side-effect-only ORM import — `# noqa: F401` 단독은 CodeQL `py/unused-import` 를
# 부른다. 정본은 docs/workflow/verify.md 의 「side-effect-only ORM import」 **두 줄**이다.
# (`import src.models` 는 `__init__.py` 가 비어 있어 테이블을 0건 등록한다 —
#  가드: tests/unit/scripts/test_bare_src_models_import_is_a_noop.py)
from src.models.repo_config import RepoConfig  # noqa: E402
from src.config_manager.manager import (  # noqa: E402
    RepoConfigData,
    upsert_repo_config,
)
from src.database import Base  # noqa: E402

_SETTINGS_PY = Path("src/ui/routes/settings.py")

_FK_TARGET_MODELS = (RepoConfig,)
if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ui_supplied_field_names() -> set[str]:
    """settings.py POST 가 `RepoConfigData(...)` 에 실제로 넘기는 키워드 이름."""
    tree = ast.parse(io.open(_SETTINGS_PY, encoding="utf-8").read())
    best: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "RepoConfigData"
        ):
            names = {kw.arg for kw in node.keywords if kw.arg}
            if len(names) > len(best):
                best = names
    return best


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_upsert_really_overwrites_every_field():
    """🔴 전제 확인 — `upsert_repo_config` 가 정말 전 필드를 덮는가.

    덮지 않는다면 이 파일 전체가 공허하다.
    """
    db = _db()
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="o/r", notification_language="ja", disabled_tools=["semgrep"]))
    after = upsert_repo_config(db, RepoConfigData(repo_full_name="o/r"))
    assert after.notification_language is None, (
        "upsert 가 필드를 덮지 않는다 — 전제가 바뀌었다"
    )


# ─── 결함 ────────────────────────────────────────────────────────────────────


def test_ui_save_preserves_notification_language_and_disabled_tools():
    """🔴 UI 저장이 폼에 없는 두 설정을 보존한다.

    보존하지 않으면 사용자가 알림 언어를 `ja` 로 두고 다른 설정 하나만 바꿔도
    언어가 조용히 초기화되고, 화면에는 `?saved=1` 만 뜬다.
    """
    db = _db()
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="o/r",
        notification_language="ja",
        disabled_tools=["semgrep", "pylint"],
    ))

    from src.ui.routes.settings import build_repo_config_from_form  # noqa: PLC0415

    form = {"pr_review_comment": "on", "approve_mode": "disabled"}
    data = build_repo_config_from_form(db, "o/r", form)
    saved = upsert_repo_config(db, data)

    assert saved.notification_language == "ja", (
        f"UI 저장이 알림 언어를 지웠다: {saved.notification_language!r} "
        "— 사용자는 `?saved=1` 만 보고 유실을 모른다"
    )
    assert list(saved.disabled_tools or []) == ["semgrep", "pylint"], (
        f"UI 저장이 비활성 도구 목록을 지웠다: {saved.disabled_tools!r}"
    )


# ─── 재발 방지 (구조) ─────────────────────────────────────────────────────────


def test_every_config_field_is_either_posted_or_explicitly_preserved():
    """🔴 새 필드를 추가하면 UI 가 **받거나 보존하거나** 하도록 강제한다.

    행동 테스트만으로는 다음에 추가되는 필드가 같은 방식으로 유실된다 —
    그 필드는 이 파일의 어떤 단언에도 이름이 없기 때문이다.
    """
    from src.ui.routes.settings import PRESERVED_CONFIG_FIELDS  # noqa: PLC0415

    all_names = {f.name for f in dataclass_fields(RepoConfigData)} - {"repo_full_name"}
    posted = _ui_supplied_field_names() - {"repo_full_name"}
    unhandled = sorted(all_names - posted - set(PRESERVED_CONFIG_FIELDS))

    assert not unhandled, (
        f"RepoConfigData 필드 {unhandled} 를 UI 가 폼에서 받지도, "
        "PRESERVED_CONFIG_FIELDS 로 보존하지도 않는다 — 저장 시 기본값으로 유실된다. "
        "폼에 넣거나 PRESERVED_CONFIG_FIELDS 에 등재하라."
    )


def test_preserved_set_does_not_list_fields_the_form_already_posts():
    """보존 목록이 폼과 겹치면 사용자의 새 입력이 옛 값으로 되돌아간다."""
    from src.ui.routes.settings import PRESERVED_CONFIG_FIELDS  # noqa: PLC0415

    overlap = sorted(set(PRESERVED_CONFIG_FIELDS) & _ui_supplied_field_names())
    assert not overlap, (
        f"{overlap} 는 폼이 이미 보내는데 보존 목록에도 있다 — "
        "사용자가 방금 바꾼 값이 옛 값으로 덮인다"
    )


def test_preserved_fields_all_exist_on_the_dataclass():
    """보존 목록의 오타를 잡는다 — 없는 이름은 조용히 아무것도 보존하지 않는다."""
    from src.ui.routes.settings import PRESERVED_CONFIG_FIELDS  # noqa: PLC0415

    known = {f.name for f in dataclass_fields(RepoConfigData)}
    unknown = sorted(set(PRESERVED_CONFIG_FIELDS) - known)
    assert not unknown, f"RepoConfigData 에 없는 필드명: {unknown}"
