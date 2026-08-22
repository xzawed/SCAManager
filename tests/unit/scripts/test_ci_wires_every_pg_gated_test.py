"""PostgreSQL 전용 테스트는 **전부** pg-concurrency job 에 배선돼 있어야 한다.

Every PostgreSQL-gated test must be wired into the pg-concurrency CI job.

## 왜 이 가드인가

PG 전용 테스트는 `DATABASE_URL_TEST_POSTGRES` 가 없으면 skip 된다. 즉 로컬에서도, 메인
`pytest tests/` job(SQLite)에서도 **초록으로 지나간다**. 실제로 실행되는 곳은
`ci.yml` 의 `pg-concurrency` job 하나뿐이고, 그 job 은 파일·`::node-id` 를 **손으로 열거**한다.
열거에서 빠진 테스트는 어디서도 실행되지 않으면서 아무도 빨갛지 않다.

`tests/integration/test_retention_sweep_postgres.py` 는 자기 파일 1개에 대해 이 검사를
갖고 있었다. 반면 `tests/unit/migrations/test_0020_round_trip.py` 는 같은 요구를
**docstring 산문**으로만 적어 두었다(`:167-168`, `:264-265` — "핀 미등재 시 자동 미수집").
산문은 아무것도 집행하지 않는다. 이 파일은 그 요구를 파일 단위가 아니라 **클래스 단위**로
집행한다 — 새 PG 테스트가 어느 파일에 생기든 배선 누락이 여기서 빨개진다.

Prose in a docstring enforces nothing. This guard closes the class, not one instance:
any newly added PG-gated test, in any file, fails here until it is wired.

이 가드 자신은 PG 를 요구하지 않는다 — 그래야 로컬·메인 job 에서도 돌아 배선을 잠근다.
This guard itself needs no PostgreSQL, so it runs everywhere and keeps the wiring locked.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_ENV = "DATABASE_URL_TEST_POSTGRES"
_JOB = "pg-concurrency"


def _pg_alias_names(src: str, tree: ast.Module) -> set[str]:
    """PG 부재 시 skip 을 유발하는 **모듈 수준 이름**을 모은다.

    Collect module-level names that carry the PG skip.

    두 종류를 받는다 — 마크 별칭(`_requires_postgres = pytest.mark.skipif(not _PG_URL, …)`)과
    그 별칭이 파생된 값(`_PG_URL = os.environ.get(ENV, "")`). 별칭은 연쇄하므로
    더 이상 늘지 않을 때까지 반복한다(선언 순서에 의존하지 않는다).
    또 **본문에서 env 를 읽는 모듈 수준 헬퍼 함수**(`def _skip_without_pg(): …`)도 이름으로 받는다 —
    테스트가 그 헬퍼를 호출하는 형태면 본문에 env 문자열이 나타나지 않기 때문이다.
    Includes helper functions whose body reads the env var, since a test calling such a helper
    never mentions the env string itself.
    """
    names: set[str] = set()
    for _ in range(8):  # 연쇄 별칭 수렴 — 실측상 2단계면 충분하나 여유를 둔다
        grew = False
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                targets = [node.name]
            if not targets:
                continue
            seg = ast.get_source_segment(src, node) or ""
            if _ENV in seg or any(a in seg for a in names):
                new = set(targets) - names
                if new:
                    names.update(new)
                    grew = True
        if not grew:
            break
    return names


def _module_is_wholly_pg_gated(src: str, tree: ast.Module, aliases: set[str]) -> bool:
    """모듈 전체를 skip 시키는 `pytestmark` 가 PG 게이트인가.

    Whether a module-level `pytestmark` gates the entire file on PostgreSQL.
    """
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        if "pytestmark" not in targets:
            continue
        seg = ast.get_source_segment(src, node) or ""
        if _ENV in seg or any(a in seg for a in aliases):
            return True
    return False


def _pg_gated_tests(path: Path) -> list[str]:
    """파일 안에서 **PG 가 없으면 skip 되는** 테스트 함수명을 뽑는다.

    Collect test functions that skip when PostgreSQL is absent.

    인식하는 표기 — 본문에서 직접 env 를 읽는 형태, 모듈 수준 별칭 데코레이터,
    **클래스 레벨** 데코레이터(그 클래스의 모든 테스트에 상속), 모듈 `pytestmark`,
    그리고 env 를 읽는 모듈 수준 헬퍼 호출.
    `test_unrecognised_skip_styles_do_not_slip_through` 가 이 목록의 공백을 감시한다.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    aliases = _pg_alias_names(src, tree)

    def _gated_by_decorators(node) -> bool:
        text = " ".join(
            ast.get_source_segment(src, d) or "" for d in node.decorator_list
        )
        return _ENV in text or any(a in text for a in aliases)

    if _module_is_wholly_pg_gated(src, tree, aliases):
        return _all_tests(path)

    found: list[str] = []

    def _visit(container, inherited: bool) -> None:
        for node in container.body:
            if isinstance(node, ast.ClassDef):
                _visit(node, inherited or _gated_by_decorators(node))
                continue
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            body = ast.get_source_segment(src, node) or ""
            if (
                inherited
                or _gated_by_decorators(node)
                or _ENV in body
                or any(a in body for a in aliases)
            ):
                found.append(node.name)

    _visit(tree, False)
    return found


def _job_runs() -> str:
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    assert _JOB in ci["jobs"], f"ci.yml 에 {_JOB} job 이 없다 — PG 테스트가 어디서도 안 돈다"
    return " ".join(s.get("run", "") for s in ci["jobs"][_JOB]["steps"] if "run" in s)


def _pg_gated_files() -> list[Path]:
    """`DATABASE_URL_TEST_POSTGRES` 를 참조하는 테스트 파일들.

    🔴 **이 파일 자신은 제외한다** — 여기는 env 이름을 *언급*할 뿐 그것으로 skip 되지 않는다.
    넓힌 분류기는 모듈 수준 `_ENV = "..."` 를 별칭으로 잡으므로, 제외하지 않으면 이 가드가
    자기 자신을 "PG 전용인데 미배선" 으로 신고한다(자기참조). 메타 가드는 PG 없이 돌아야 한다.
    Excludes itself: this module only *names* the env var; it is not gated by it.
    """
    here = Path(__file__).resolve()
    return sorted(
        p for p in _ROOT.joinpath("tests").rglob("test_*.py")
        if p.resolve() != here and _ENV in p.read_text(encoding="utf-8")
    )


def test_pg_gated_tests_exist_at_all():
    """🔴 공허화 차단 — 대상 집합이 비면 아래 검사는 무엇도 단언하지 않는다.

    Emptiness guard: with no PG-gated tests, the assertions below are vacuously true.
    """
    files = _pg_gated_files()
    assert files, f"{_ENV} 를 쓰는 테스트 파일이 0개 — 이 가드가 공허하다"
    assert any(_pg_gated_tests(p) for p in files), (
        "PG-게이트 테스트 함수가 0개 — 파일은 있는데 함수를 못 찾았다(파서 회귀 의심)"
    )


def test_every_pg_gated_test_is_wired_into_the_pg_job():
    """PG 전용 테스트 하나하나가 pg-concurrency 실행 목록에서 도달 가능한가.

    도달 경로는 둘 — 파일 통째 지정, 또는 `파일::함수명` node-id 핀.
    """
    runs = _job_runs()
    unwired: list[str] = []

    for path in _pg_gated_files():
        rel = path.relative_to(_ROOT).as_posix()
        whole_file = any(
            token == rel for token in runs.split()
        )  # 통째 지정 — `::` 없는 정확한 토큰
        for name in _pg_gated_tests(path):
            if whole_file or f"{rel}::{name}" in runs:
                continue
            unwired.append(f"{rel}::{name}")

    assert not unwired, (
        "PG 전용인데 pg-concurrency job 에 미배선 — **어디서도 실행되지 않는다**:\n  "
        + "\n  ".join(unwired)
        + f"\n\n→ {_CI.relative_to(_ROOT).as_posix()} 의 {_JOB} job 실행 목록에 "
        "파일 또는 `파일::함수명` 을 추가할 것."
    )


def test_the_pin_list_has_no_stale_entries():
    """대조축 — 핀 목록이 **사라진 테스트**를 가리키면 그 줄은 조용히 아무것도 안 돌린다.

    Control axis: a node-id pin naming a deleted test silently runs nothing. pytest 는
    미존재 node-id 에 에러를 내지만, 파일이 통째로 사라지면 job 전체가 실패해 원인이
    배선이라는 사실이 묻힌다. 여기서 먼저 이름으로 잡는다.
    """
    runs = _job_runs()
    stale: list[str] = []

    for token in runs.split():
        if "::" not in token or not token.startswith("tests/"):
            continue
        rel, _, name = token.partition("::")
        path = _ROOT / rel
        if not path.is_file():
            stale.append(f"{token} (파일 없음)")
        elif name not in _pg_gated_tests(path) and name not in _all_tests(path):
            stale.append(f"{token} (함수 없음)")

    assert not stale, "pg-concurrency 핀이 존재하지 않는 대상을 가리킨다:\n  " + "\n  ".join(stale)


def _all_tests(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    ]


# ── 분류기 자신의 회귀 가드 ──────────────────────────────────────────────────
#
# 🔴 초판 분류기는 두 표기만 봤다 — 본문의 env 문자열, 모듈 수준 `ast.Assign` 별칭 데코레이터.
#    Grok claim-review `01a0296e` 가 적발: 클래스 레벨 skipif · 모듈 `pytestmark` ·
#    env 를 읽는 헬퍼 호출로 쓴 PG 테스트는 **분류되지 않아** 배선 검사를 통째로 지나갔다.
#    분류에서 빠지면 위 검사는 그 테스트에 대해 아무 말도 하지 않는다 — 못 재는 자리에
#    초록을 내는 거짓 집행자다. 아래가 그 표기들을 고정한다.
#
# The first classifier recognized only two styles; three others slipped through silently,
# which made the wiring check a false enforcer for anything written that way.

_STYLES = {
    "본문에서 직접 env 를 읽는다": '''
import os
import pytest


def test_body_reads_env():
    if not os.environ.get("DATABASE_URL_TEST_POSTGRES"):
        pytest.skip("pg")
''',
    "모듈 수준 별칭 데코레이터": '''
import os
import pytest

_PG = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_pg = pytest.mark.skipif(not _PG, reason="pg")


@_requires_pg
def test_body_reads_env():
    pass
''',
    "클래스 레벨 데코레이터 (상속)": '''
import os
import pytest

_PG = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_pg = pytest.mark.skipif(not _PG, reason="pg")


@_requires_pg
class TestGrouped:
    def test_body_reads_env(self):
        pass
''',
    "모듈 pytestmark (파일 전체)": '''
import os
import pytest

_PG = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
pytestmark = pytest.mark.skipif(not _PG, reason="pg")


def test_body_reads_env():
    pass
''',
    "env 를 읽는 헬퍼 호출": '''
import os
import pytest


def _skip_without_pg():
    if not os.environ.get("DATABASE_URL_TEST_POSTGRES"):
        pytest.skip("pg")


def test_body_reads_env():
    _skip_without_pg()
''',
    "타입 주석 별칭 (AnnAssign)": '''
import os
import pytest

_PG: str = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_pg = pytest.mark.skipif(not _PG, reason="pg")


@_requires_pg
def test_body_reads_env():
    pass
''',
}


@pytest.mark.parametrize("style", sorted(_STYLES))
def test_unrecognised_skip_styles_do_not_slip_through(tmp_path, style):
    """PG skip 을 거는 **모든 표기**가 분류돼야 한다 — 하나라도 놓치면 그 축은 무집행이다."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(_STYLES[style], encoding="utf-8")

    assert _pg_gated_tests(probe) == ["test_body_reads_env"], (
        f"표기 「{style}」 를 PG 게이트로 분류하지 못했다 — 이 표기로 쓴 테스트는 "
        "배선 검사를 그냥 지나간다(어디서도 실행되지 않으면서 초록)."
    )


def test_a_test_without_any_pg_gate_is_not_classified():
    """대조축 — 전부 PG 로 보면 순수 테스트까지 배선을 요구해 가드가 거짓 red 를 낸다.

    Control axis: classifying everything as PG-gated would demand wiring for pure tests.
    """
    probe = _ROOT / "tests" / "unit" / "migrations" / "test_orm_alembic_parity.py"
    gated = _pg_gated_tests(probe)

    assert "test_orm_metadata_matches_migrations" in gated, "실제 PG 테스트를 놓쳤다"
    assert "test_structural_diffs_filter_logic" not in gated, (
        f"순수 로직 테스트를 PG 로 오분류했다 — 불필요한 배선을 강요한다: {gated}"
    )
