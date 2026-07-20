"""민감 경로 자동 머지 가드 (B6-a) — 분류·fail-closed·배선.

## 사고 (2026-07-20 실측)

운영 6개 리포 **전부** `auto_merge=true`·`approve_mode=auto`·`merge_threshold=60` 이고
**6/6 기본 브랜치가 무보호**였다. 점수 60 이상이면 인증·마이그레이션·CI 워크플로를 바꾸는
PR 도 **사람 개입 0으로** 머지된다. 실증: `#1102`~`#1107` 6건 전부 `reviews=0` · 4분37초~
5분27초 만에 자동 머지, 그중 `#1104` 는 **토큰 평문 유출 P0 보안 변경**이었다.

🔴 **점수 게이트는 경로 민감도를 모른다** — 이 가드가 그 축을 담당한다.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.gate.merge_reasons import SENSITIVE_PATH_HOLD, is_retriable_tag
from src.gate.sensitive_paths import sensitive_paths_block_merge, sensitive_paths_in

_ARGS = {"github_token": "t", "repo_name": "o/r", "pr_number": 7}


# ── 분류 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [
    "src/auth/oauth.py", "app/auth/session.py",
    "alembic/versions/0050_add_col.py", "db/migrations/003_x.sql", "alembic.ini",
    ".github/workflows/ci.yml", ".github/workflows/deploy.yaml",
    "src/crypto.py", "lib/secrets.py", "config/credentials.json",
    "Dockerfile", "docker/Dockerfile",
])
def test_sensitive_paths_are_detected(path):
    assert sensitive_paths_in([path]) == [path], f"{path} 가 민감 경로로 잡히지 않는다"


@pytest.mark.parametrize("path", [
    "README.md", "docs/STATE.md", "src/ui/routes/home.py",
    "tests/unit/gate/test_engine.py", "src/notifier/telegram.py",
    "src/templates/base.html", "package.json",
])
def test_ordinary_paths_are_not_flagged(path):
    """🔴 과탐은 가드의 자살이다 — 정상 PR 이 막히면 사용자가 가드를 끈다."""
    assert sensitive_paths_in([path]) == [], f"{path} 가 잘못 민감 경로로 잡힌다"


def test_mixed_changeset_reports_only_the_sensitive_subset():
    files = ["README.md", "src/auth/oauth.py", "src/ui/x.py", "alembic/versions/1.py"]
    assert sensitive_paths_in(files) == ["alembic/versions/1.py", "src/auth/oauth.py"]


def test_empty_input_yields_empty_but_callers_must_not_read_it_as_safe():
    """빈 입력은 '판정 불가' 지 '안전' 이 아니다 — 구별은 호출부 책임(아래 fail-closed)."""
    assert sensitive_paths_in([]) == []
    assert sensitive_paths_in(None) == []


# ── 가드 동작 ───────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.asyncio
async def test_guard_blocks_when_sensitive_file_present():
    with patch("src.github_client.diff.get_pr_filenames", return_value=["src/auth/x.py"]), \
         patch("src.notifier.github_comment.post_plain_pr_comment", new=AsyncMock()) as c:
        assert await sensitive_paths_block_merge(**_ARGS) is True
    c.assert_awaited_once()


@pytest.mark.asyncio
async def test_guard_allows_when_no_sensitive_file():
    with patch("src.github_client.diff.get_pr_filenames", return_value=["README.md"]), \
         patch("src.notifier.github_comment.post_plain_pr_comment", new=AsyncMock()) as c:
        assert await sensitive_paths_block_merge(**_ARGS) is False
    c.assert_not_awaited()


@pytest.mark.asyncio
async def test_guard_is_fail_closed_when_file_listing_fails():
    """🔴 무엇이 바뀌었는지 모르면 **보류**한다.

    "판정 불가" 를 "안전" 으로 접으면 GitHub API 장애 한 번이 곧 인증 코드 무검토 머지가
    된다. 검증자 가드가 오류를 차단으로 취급하는 것과 같은 규칙이다.
    """
    with patch("src.github_client.diff.get_pr_filenames", side_effect=RuntimeError("api down")):
        assert await sensitive_paths_block_merge(**_ARGS) is True


@pytest.mark.asyncio
async def test_comment_failure_does_not_flip_the_decision():
    """알림 실패가 **차단 결정을 뒤집으면 안 된다** — 알림은 부수효과다."""
    with patch("src.github_client.diff.get_pr_filenames", return_value=["alembic/versions/1.py"]), \
         patch("src.notifier.github_comment.post_plain_pr_comment",
               new=AsyncMock(side_effect=RuntimeError("comment down"))):
        assert await sensitive_paths_block_merge(**_ARGS) is True


@pytest.mark.asyncio
async def test_kill_switch_disables_the_guard(monkeypatch):
    """운영자가 즉시 끌 수 있어야 한다 — 끄면 조회조차 하지 않는다."""
    monkeypatch.setenv("SENSITIVE_PATH_GUARD_DISABLED", "1")
    with patch("src.github_client.diff.get_pr_filenames") as g:
        assert await sensitive_paths_block_merge(**_ARGS) is False
    g.assert_not_called()


# ── 배선 (dead code 차단) ───────────────────────────────────────────────


def test_guard_is_wired_into_the_single_source_auto_merge_path():
    """🔴 `_run_auto_merge` 가 실제로 **호출**해야 한다 — 정의만 하면 dead code 다.

    AST 로 호출을 확인한다. 문자열 검색이면 "가드를 붙일 것" 이라는 주석이 통과시킨다.
    `_run_auto_merge` 는 자동(`AutoMergeAction`)·반자동(telegram) **양 경로의 단일 출처**라
    여기 걸어야 반자동이 우회하지 못한다(#859 P1-1 이 남긴 교훈).
    """
    import ast
    import inspect

    import src.gate.engine as engine

    src = inspect.getsource(engine._run_auto_merge)  # pylint: disable=protected-access
    tree = ast.parse(src.lstrip())
    called = {
        getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert "sensitive_paths_block_merge" in called, (
        "민감 경로 가드가 _run_auto_merge 에서 호출되지 않는다 — 배선 없는 dead code"
    )


def test_guard_runs_before_the_merge_actually_happens():
    """🔴 가드가 머지 **뒤**에 있으면 아무 의미가 없다 — 순서를 AST 로 고정한다.

    🔴 문자열 검색으로 쓰면 안 된다: 이 함수의 **docstring** 에 이미
    *"P0-H: 독립 `SessionLocal()` 사용"* 이라는 문장이 있어, `src.index("SessionLocal()")`
    는 실제 `with` 문이 아니라 **산문**을 가리킨다(작성 중 실측 — 순서가 옳은데 FAIL 났다).
    산문과 코드를 구별하지 못하는 검사는 이 저장소가 반복해 만든 결함이다.
    Text search would match the docstring, not the statement — assert on the AST.
    """
    import ast
    import inspect
    import textwrap

    import src.gate.engine as engine

    src = textwrap.dedent(inspect.getsource(engine._run_auto_merge))  # pylint: disable=protected-access
    tree = ast.parse(src)

    guard_line = min(
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) or getattr(n.func, "attr", None))
        == "sensitive_paths_block_merge"
    )
    session_line = min(
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) or getattr(n.func, "attr", None)) == "SessionLocal"
    )
    assert guard_line < session_line, (
        f"가드(line {guard_line})가 머지 실행 경로(SessionLocal, line {session_line})보다 뒤에 있다"
    )


def test_hold_tag_is_terminal_not_retriable():
    """🔴 보류는 **종결**이다 — 기다린다고 사람이 검토하지는 않는다.

    재시도 가능 태그로 두면 큐가 영원히 재시도하며 같은 이유로 계속 실패한다.
    """
    assert is_retriable_tag(SENSITIVE_PATH_HOLD) is False
