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


def _pg_gated_tests(path: Path) -> list[str]:
    """파일 안에서 **PG 가 없으면 skip 되는** 테스트 함수명을 뽑는다.

    Collect test functions that skip when PostgreSQL is absent.

    두 표기를 모두 인식한다 — 본문에서 직접 env 를 읽는 형태와, 모듈 상단의
    `_requires_postgres = pytest.mark.skipif(not _PG_URL, …)` 별칭 데코레이터.
    별칭은 연쇄한다(`_PG_URL` → `_requires_postgres`)므로 선언 순서대로 누적한다.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    aliases: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if _ENV in seg or any(a in seg for a in aliases):
            aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        body = ast.get_source_segment(src, node) or ""
        decorators = " ".join(
            ast.get_source_segment(src, d) or "" for d in node.decorator_list
        )
        if _ENV in body or any(a in decorators for a in aliases):
            found.append(node.name)
    return found


def _job_runs() -> str:
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    assert _JOB in ci["jobs"], f"ci.yml 에 {_JOB} job 이 없다 — PG 테스트가 어디서도 안 돈다"
    return " ".join(s.get("run", "") for s in ci["jobs"][_JOB]["steps"] if "run" in s)


def _pg_gated_files() -> list[Path]:
    return sorted(
        p for p in _ROOT.joinpath("tests").rglob("test_*.py")
        if _ENV in p.read_text(encoding="utf-8")
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
