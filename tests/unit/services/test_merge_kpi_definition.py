"""🔴 «머지 성공» 판정이 SQL 과 파이썬에서 같은 답을 내는가.

🔴 Whether the "merged" predicate agrees between its SQL and Python forms.

## 왜 두 형태가 있나

머지율 KPI 는 두 곳에서 계산된다:

  · `operations_service._merge_kpi` — `COUNT(*) … WHERE <술어>` (SQL)
  · `dashboard_service._simple_success` / `_retry_aware_success` — ORM 객체 순회 (파이썬)

정의는 `_merge_attempt_states.is_merged` **하나**이고 SQL 쪽은 그 규칙을 옮긴 것이다.
둘이 어긋나면 **같은 제품의 두 머지율이 갈린다** — 사용자는 어느 쪽이 참인지 알 수 없고,
그 불일치는 숫자가 틀린 것보다 나쁘다(R46 이 정확히 그 사고였다).

## 무엇이 걸려 있나 (실측 2026-08-24, 운영 DB)

    state                 success  행수
    legacy                false    1,902
    legacy                true       675   ← 운영 머지 실적의 대부분
    direct_merged         true        58
    enabled_pending_merge  —           0   ← 코드 경로는 살아 있으나 성공 이력 0회
    actually_merged        —           0
    disabled_externally    —           0

`success=True` 만 세면 「켜기만 한」 행이 섞이고, `state` 화이트리스트만 쓰면 675행이
사라진다. 하이브리드가 두 시점 모두에서 옳다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.gate import _merge_attempt_states as _states
from src.models.merge_attempt import MergeAttempt
from src.repositories import merge_attempt_repo

# 판정에 등장할 수 있는 모든 (state, success) 조합 — 손으로 고르지 않고 상수에서 만든다.
_ALL_STATES = (
    _states.LEGACY,
    _states.ENABLED_PENDING_MERGE,
    _states.ACTUALLY_MERGED,
    _states.DISABLED_EXTERNALLY,
    _states.DIRECT_MERGED,
)
_COMBOS = [(s, ok) for s in _ALL_STATES for ok in (True, False)]


@pytest.fixture(name="db")
def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(timezone.utc)
    for i, (state, ok) in enumerate(_COMBOS, start=1):
        session.add(MergeAttempt(
            id=i, analysis_id=1, repo_name="o/r", pr_number=i,
            score=90, threshold=75, success=ok, state=state,
            attempted_at=now - timedelta(minutes=i),
        ))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_the_state_list_is_not_stale():
    """🔴 공허화 차단 — 새 state 가 생기면 이 표가 낡는다."""
    declared = {
        v for k, v in vars(_states).items()
        if k.isupper() and isinstance(v, str) and not k.startswith("_")
    }
    assert declared == set(_ALL_STATES), (
        f"state 상수가 바뀌었다: 선언 {sorted(declared)} vs 표본 {sorted(_ALL_STATES)}.\n"
        "→ 새 state 를 _ALL_STATES 에 추가하고, is_merged 가 그것을 어떻게 다룰지 정할 것."
    )


@pytest.mark.parametrize("state,success", _COMBOS, ids=[f"{s}-{ok}" for s, ok in _COMBOS])
def test_sql_and_python_predicates_agree(db, state, success):
    """🔴 모든 조합에서 두 형태가 같은 답을 낸다 — 갈리면 두 머지율이 갈린다."""
    row_id = _COMBOS.index((state, success)) + 1
    counted_by_sql = db.scalar(
        select(func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .where(MergeAttempt.id == row_id)
        .where(merge_attempt_repo.merged_sql_predicate())
    )
    by_python = _states.is_merged(state, success)
    assert bool(counted_by_sql) == by_python, (
        f"state={state!r} success={success}: SQL={bool(counted_by_sql)} 파이썬={by_python}"
    )


def test_the_corpus_exercises_both_verdicts(db):
    """공허화 차단 — 한쪽으로 쏠리면 위 단언이 아무것도 못 본다."""
    verdicts = {_states.is_merged(s, ok) for s, ok in _COMBOS}
    assert verdicts == {True, False}, f"판정이 한쪽뿐: {verdicts}"


def test_enabled_and_disabled_are_never_merged():
    """🔴 켜기만 한 것과 켠 뒤 꺼진 것은 **어떤 success 값에서도** 머지가 아니다.

    `mark_disabled_externally` 는 `state` 만 바꾸고 `success` 를 뒤집지 않는다(실측).
    그래서 「success=True 이고 state != pending」 같은 블랙리스트로는 disabled 가 샌다 —
    같은 결함이 한 전이 뒤에서 반복된다.
    """
    for ok in (True, False):
        assert _states.is_merged(_states.ENABLED_PENDING_MERGE, ok) is False
        assert _states.is_merged(_states.DISABLED_EXTERNALLY, ok) is False


def test_legacy_needs_success_but_merged_states_do_not():
    """`legacy` 는 신호가 `success` 뿐이라 그것을 믿고, 실제 머지 상태는 그 자체로 충분하다."""
    assert _states.is_merged(_states.LEGACY, True) is True
    assert _states.is_merged(_states.LEGACY, False) is False
    for state in (_states.ACTUALLY_MERGED, _states.DIRECT_MERGED):
        assert _states.is_merged(state, True) is True
        assert _states.is_merged(state, False) is True


def test_every_kpi_site_uses_the_shared_definition():
    """🔴 배선 축 — KPI 가 `success` 를 직접 보면 정의가 두 벌이 된다.

    세 곳(`operations._merge_kpi` · `dashboard._simple_success` · `_retry_aware_success`)이
    공유 판정을 쓰는지 AST 로 확인한다. 실패 분포(`success.is_(False)`)는 대상이 아니다 —
    그것은 「호출이 실패했다」를 세는 다른 축이다.
    """
    import ast  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    root = Path(__file__).resolve().parents[3] / "src" / "services"
    targets = {
        "operations_service.py": ["_merge_kpi"],
        "dashboard_service.py": ["_simple_success", "_retry_aware_success"],
    }
    problems = []
    for fname, fns in targets.items():
        tree = ast.parse((root / fname).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name in fns):
                continue
            dump = ast.dump(node)
            uses_shared = "is_merged" in dump or "merged_sql_predicate" in dump
            if not uses_shared:
                problems.append(f"{fname}:{node.lineno} {node.name}()")
    assert not problems, (
        "KPI 가 공유 판정을 쓰지 않는다 — 정의가 두 벌이 되면 두 머지율이 갈린다:\n  "
        + "\n  ".join(problems)
    )


def test_every_successful_write_labels_its_state():
    """🔴 `success=True` 를 기록하는 곳은 `state` 를 반드시 넘긴다.

    ## 이 가드가 왜 필요한가 (실측)

    `log_merge_attempt` 의 `state` 기본값은 `legacy` 다. 호출부 10곳 중 **2곳만** 그것을
    넘겼고, 넘기지 않은 곳에 **운영의 primary 머지 경로**(`merge_retry_service`)가 있었다.
    결과: 운영 `success=True` 733행 중 **675행이 `legacy`** — 라이프사이클 컬럼이 사실상
    장식이었고, KPI 를 `state` 기준으로 바꾸는 순간 머지 실적의 92% 가 증발할 상태였다.

    실패 기록(`success=False`)은 대상이 아니다. 실패에는 라이프사이클이 없고
    `is_terminal(legacy)` 가 True 라 webhook 전이도 걸리지 않는다.

    A default of `legacy` plus silent callers made the lifecycle column ornamental; only the
    success writers matter, and they must label themselves.
    """
    import ast  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    root = Path(__file__).resolve().parents[3] / "src"
    unlabelled, total_success = [], 0
    for path in sorted(root.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "log_merge_attempt(" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", None) == "log_merge_attempt"):
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            success = kw.get("success")
            # 리터럴 True 만 본다 — 변수(`success=ok`)는 분기라 정적으로 못 가른다.
            if not (isinstance(success, ast.Constant) and success.value is True):
                continue
            total_success += 1
            if "state" not in kw:
                rel = path.relative_to(root.parent).as_posix()
                unlabelled.append(f"{rel}:{node.lineno}")

    assert total_success, "`log_merge_attempt(success=True)` 호출을 못 찾았다 — 가드가 공허하다"
    assert not unlabelled, (
        "성공을 기록하면서 `state` 를 넘기지 않는다 — 기본값 `legacy` 로 저장돼 "
        f"머지 실적이 라벨 없이 쌓인다:\n  " + "\n  ".join(unlabelled)
        + "\n→ `state=_states.DIRECT_MERGED` (또는 해당 경로의 state) 를 함께 넘길 것."
    )
