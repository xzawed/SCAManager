"""`pytest tests/ --strict-skips` 게이트 — 판정 · 배선 · 허용 목록 정합 (원장 #1917 M06 P1-14 · P1-18).

#1857 뒤 CI 단위 잡에서 34건이 조용히 skip 이 됐고 시험 수 대조(합)는 초록이었다. 게이트는 skip **집합**을
커밋된 목록과 양방향으로 대조한다. 여기서는 (1) 판정 함수의 갈래 (2) CI 배선 (3) 목록 항목의 실재 ·
«어디서 도는가» 를 잰다 — 개수는 못박지 않는다(개수 스냅샷은 정당한 추가 · 삭제를 벌한다).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from tests._skip_gate import ALLOWLIST, base_nodeid, judge, read_allowlist

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
# «어디서도 돌지 않는다» 꼬리표는 두지 않는다 — 그렇게 적는 것이 가장 쉬운 오답이다(원장 #1917 P2-36).
_TAGS = ("pg 잡", "로컬 전용")


# ── (1) 판정 ─────────────────────────────────────────────────────────────────

def test_an_unlisted_skip_is_red_and_says_where_it_happened():
    msgs = judge({"tests/a.py::t": "tests/a.py:3: needs X"}, {"tests/a.py::t"}, set())
    assert len(msgs) == 1 and "tests/a.py::t" in msgs[0] and "tests/a.py:3: needs X" in msgs[0]


def test_a_listed_skip_that_no_longer_skips_is_red():
    msgs = judge({}, {"tests/a.py::t"}, {"tests/a.py::t"})
    assert len(msgs) == 1 and "낡았다" in msgs[0] and "tests/a.py::t" in msgs[0]


def test_a_listed_skip_outside_this_run_is_not_stale():
    """🔴 부분 실행(경로 · `-k`)에서 수집되지 않은 항목은 낡음으로 세지 않는다 — 거짓 red 방지."""
    assert judge({}, {"tests/b.py::u"}, {"tests/a.py::t"}) == []


def test_matching_sets_pass():
    assert judge({"tests/a.py::t": "x"}, {"tests/a.py::t", "tests/a.py::v"}, {"tests/a.py::t"}) == []


def test_an_unreadable_allowlist_is_red_not_green(tmp_path):
    """🔴 못 재면 red — 목록이 사라지면 게이트가 통째로 사라진다."""
    missing = tmp_path / "nope"
    assert read_allowlist(missing) is None
    msgs = judge({}, set(), None, missing)
    assert len(msgs) == 1 and "판정 불가" in msgs[0]


def test_allowlist_parsing_drops_comments_and_blank_lines(tmp_path):
    path = tmp_path / "SKIP_ALLOWLIST"
    path.write_text("# 머리 주석\n\ntests/a.py::t  # pg 잡\n   \ntests/b.py::u\n", encoding="utf-8")
    assert read_allowlist(path) == {"tests/a.py::t", "tests/b.py::u"}


def test_parametrized_ids_collapse_to_the_function():
    assert base_nodeid("tests\\a.py::t[x-1]") == "tests/a.py::t"
    assert base_nodeid("tests/a.py::C::t[p]") == "tests/a.py::C::t"


# ── (2) 배선 ─────────────────────────────────────────────────────────────────

def _unit_pytest_command() -> str:
    """CI 단위 잡의 `python -m pytest tests/` 명령 — 줄 이음(`\\`)으로 이어진 그 명령만."""
    lines = _CI.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*python -m pytest tests/ \\\s*$", line):
            cmd = [line.strip()]
            for nxt in lines[i + 1:]:
                cmd.append(nxt.strip())
                if not nxt.rstrip().endswith("\\"):
                    break
            return " ".join(cmd)
    raise AssertionError("ci.yml 에서 `python -m pytest tests/` 명령을 찾지 못했다 — 못 재면 초록이 아니라 red 다")


def test_strict_skips_is_wired_into_the_unit_job_as_a_boolean_flag():
    """🔴 불리언 플래그여야 한다 — 값을 받으면 `=0` 으로 끌 수 있다(e2e 가 한 번 밟았다)."""
    cmd = _unit_pytest_command()
    assert re.search(r"(?<!\S)--strict-skips(?!\S)", cmd), f"단위 잡에 skip 집합 게이트가 없다: {cmd}"
    assert not re.search(r"--strict-skips\s*=", cmd), f"플래그에 값을 붙였다: {cmd}"


def test_the_gate_option_and_hook_exist_in_conftest():
    conftest = (_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    names = {n.name for n in ast.walk(ast.parse(conftest)) if isinstance(n, ast.FunctionDef)}
    assert {"pytest_addoption", "pytest_sessionfinish"} <= names
    assert '"--strict-skips", action="store_true"' in conftest


# ── (3) 허용 목록 ─────────────────────────────────────────────────────────────

def _entries() -> list[tuple[str, str]]:
    out = []
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        entry, _, comment = line.partition("#")
        if entry.strip():
            out.append((entry.strip(), comment.strip()))
    return out


def test_every_entry_points_at_a_real_test():
    """🔴 낡은 예외는 게이트를 넓힌다 — 파일 · 함수가 실재해야 한다(사라진 시험은 훅의 낡음 축이 못 본다)."""
    entries = _entries()
    assert entries, "허용 목록이 비었다 — 지금 CI 단위 잡에는 정당한 skip 이 있다"
    for entry, _ in entries:
        rel, _, rest = entry.partition("::")
        assert rest, f"nodeid 형식이 아니다: {entry!r}"
        path = _ROOT / rel
        assert path.exists(), f"없는 파일을 가리킨다: {rel}"
        func = rest.split("::")[-1]
        assert re.search(rf"^\s*(async\s+)?def {re.escape(func)}\(", path.read_text(encoding="utf-8"), re.M), (
            f"허용 목록의 시험이 실재하지 않는다: {entry}")


def test_every_entry_says_where_it_runs():
    """🔴 «어디서 도는가» 가 없으면 영구 skip 과 다른 잡에서 도는 skip 을 가를 수 없다(#1857 의 34건)."""
    for entry, comment in _entries():
        assert comment.startswith(_TAGS), f"«어디서 도는가» 꼬리표가 없다({'/'.join(_TAGS)}): {entry}"
        if not comment.startswith("pg 잡"):
            assert "—" in comment, f"«로컬 전용» 은 사유를 적는다: {entry}"


def _job_block(ci: str, name: str) -> str:
    """잡 이름 줄부터 다음 잡 키(들여쓰기 2칸의 `key:`) 앞까지."""
    start = ci.index(f"name: {name}")
    nxt = re.compile(r"^  [A-Za-z0-9_-]+:\s*$", re.M).search(ci, start)
    return ci[start:nxt.start() if nxt else len(ci)]


def test_pg_entries_are_really_run_by_the_pg_job():
    """🔴 «pg 잡» 이라고 적은 항목은 CI «PG-only tests» 잡의 명령에 실제로 있어야 한다."""
    block = _job_block(_CI.read_text(encoding="utf-8"), "PG-only tests")
    assert "python -m pytest" in block, "PG 잡 블록을 잘못 잘랐다 — 못 재면 red"
    for entry, comment in _entries():
        if comment.startswith("pg 잡"):
            rel = entry.partition("::")[0]
            assert rel in block or entry in block, f"«pg 잡» 이라고 적었지만 그 잡이 돌리지 않는다: {entry}"
