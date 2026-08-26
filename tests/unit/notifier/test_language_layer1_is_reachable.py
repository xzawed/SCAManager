"""광고된 3층 언어 fallback 의 1층이 **도달 불가**다 (감사 A7, #1519).

🔴 실측. `src/notifier/_language.py` 의 모듈 docstring 과 notifier·gate 의 docstring
약 10곳이 이렇게 적는다:

    3-layer 우선순위:
    1. User.preferred_language  <- 가장 정확 (사용자 명시 선택)
    2. RepoConfig.notification_language
    3. settings.default_locale

그런데 1층은 `if db is not None and telegram_user_id:` 뒤에 있고,
**프로덕션 호출부 20곳 중 0곳이 `telegram_user_id` 를 넘기지 않는다**(AST 전수 실측).
전부 `resolve_notification_language(db, config=...)` 형태다. 즉:

- `db` 는 20곳에서 전달되지만 **읽히지 않는다** (1층 안에서만 쓰인다)
- 사용자가 설정한 언어가 6개 알림 채널·게이트·재시도·railway webhook **전부에서 무시**된다
- 실제로는 2층 resolver 다

그리고 그 값은 실제로 쓰이는 값이다:
- `src/api/users.py` 의 `PATCH .../preferred-language` 가 DB 에 쓴다
- `src/api/repos.py` 주석: 「NULL = 사용자 preferred_language fallback」

🔴 **형제가 이미 옳게 하고 있다.** `src/api/hook.py::_resolve_hook_locale` 은
`repo.full_name -> Repository.user_id -> User.preferred_language` 로 소유자 언어를
해소한다. 같은 배선이 `config.repo_full_name` 으로 여기서도 가능하다.

The advertised layer 1 is gated on an argument no production caller passes.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import ast  # noqa: E402
import io  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.config import settings  # noqa: E402
from src.config_manager.manager import RepoConfigData  # noqa: E402
from src.database import Base  # noqa: E402
from src.models.repository import Repository  # noqa: E402
from src.models.user import User  # noqa: E402
from src.notifier._language import resolve_notification_language  # noqa: E402

_FK_TARGET_MODELS = (Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")

_REPO = "owner/repo"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_owner(session, language: str) -> None:
    """소유자 1명 + 그 소유의 리포. `preferred_language` 는 NOT NULL(기본 'en')이다."""
    user = User(github_id="1", github_login="owner", email="o@example.test",
                display_name="Owner", preferred_language=language)
    session.add(user)
    session.flush()
    session.add(Repository(full_name=_REPO, user_id=user.id))
    session.commit()


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_no_production_caller_passes_telegram_user_id():
    """🔴 전제 — 프로덕션 호출부가 정말 `telegram_user_id` 를 안 넘기는가.

    넘기는 곳이 있다면 1층이 부분적으로는 살아 있는 것이고 서술을 고쳐야 한다.
    """
    passing = []
    for path in Path("src").rglob("*.py"):
        if "__pycache__" in path.as_posix():
            continue
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None))
            if name != "resolve_notification_language":
                continue
            kwargs = {k.arg for k in node.keywords}
            if "telegram_user_id" in kwargs or len(node.args) >= 2:
                passing.append(f"{path.as_posix()}:{node.lineno}")
    assert not passing, (
        f"telegram_user_id 를 넘기는 프로덕션 호출부가 생겼다: {passing} — "
        "이 파일의 전제를 다시 확인하라"
    )


def test_the_sibling_resolves_the_owner_language():
    """🔴 전제 — `api/hook.py` 가 소유자 언어를 해소하는 관용구를 이미 갖는가."""
    src = io.open("src/api/hook.py", encoding="utf-8").read()
    assert "preferred_language" in src and "Repository.full_name" in src, (
        "형제 관용구가 사라졌다 — 이 수정의 근거가 바뀌었다"
    )


# ─── 결함 ────────────────────────────────────────────────────────────────────


def test_owner_preferred_language_wins_over_default(db):
    """🔴 소유자가 설정한 언어가 실제로 쓰인다 — 1층이 도달 가능해야 한다.

    안 쓰이면 `PATCH /api/users/.../preferred-language` 가 DB 만 바꾸고
    알림에는 아무 영향이 없다.
    """
    _seed_owner(db, "ja")
    config = RepoConfigData(repo_full_name=_REPO)  # notification_language 미설정

    lang = resolve_notification_language(db, config=config)
    assert lang == "ja", (
        f"소유자 언어(ja)가 무시되고 {lang!r} 이 나왔다 — 1층이 도달 불가다"
    )


def test_repo_config_still_overrides_the_owner(db):
    """🔴 우선순위 유지 — repo 설정이 있으면 그것이 이긴다.

    docstring 이 적는 순서가 1층 > 2층이 아니라 **2층 override** 임을 고정한다.
    한국어 사용자가 글로벌 팀을 위해 영문 알림을 고르는 경우가 그 이유다.
    """
    _seed_owner(db, "ja")
    config = RepoConfigData(repo_full_name=_REPO, notification_language="en")

    lang = resolve_notification_language(db, config=config)
    assert lang == "en", (
        f"repo 설정(en)이 소유자 언어에 밀렸다 — {lang!r}. repo override 가 우선이다"
    )


def test_owner_at_the_schema_default_yields_that_default(db):
    """대조군 — `preferred_language` 는 NOT NULL(기본 'en')이라 «미설정» 이 없다.

    소유자가 한 번도 안 바꿨으면 값은 'en' 이고, 그것이 그대로 쓰인다.
    """
    _seed_owner(db, "en")
    lang = resolve_notification_language(db, config=RepoConfigData(repo_full_name=_REPO))
    assert lang == "en"


def test_no_owner_row_falls_back_to_default(db):
    """대조군 — 소유자가 없는 리포(user_id NULL)는 기본 로케일이다."""
    db.add(Repository(full_name=_REPO, user_id=None))
    db.commit()
    lang = resolve_notification_language(db, config=RepoConfigData(repo_full_name=_REPO))
    assert lang == settings.default_locale


def test_unsupported_owner_language_falls_back(db):
    """🔴 지원하지 않는 언어는 무시한다 — 형제(`hook.py`)와 같은 규율."""
    _seed_owner(db, "zz")
    lang = resolve_notification_language(db, config=RepoConfigData(repo_full_name=_REPO))
    assert lang == settings.default_locale, (
        f"미지원 언어 'zz' 가 그대로 쓰였다: {lang!r}"
    )


def test_no_db_still_works(db):
    """대조군 — `db=None` 이면 2·3층만으로 동작한다(기존 계약)."""
    assert resolve_notification_language(
        None, config=RepoConfigData(repo_full_name=_REPO, notification_language="ko")
    ) == "ko"
    assert resolve_notification_language(None) == settings.default_locale
