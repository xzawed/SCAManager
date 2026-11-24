"""`pytest tests/ --strict-skips` 의 판정 — 관측한 skip 집합 ↔ 커밋된 허용 목록, 양방향 (원장 #1917 M06 P1-14 · P1-18).

훅(`tests/conftest.py::pytest_sessionfinish`)은 관측만 모으고, 판정은 여기 순수 함수가 한다 — 그래야 훅 밖에서
미허용 · 낡음 · 판정 불가 갈래를 단위 시험으로 잰다(`tests/unit/scripts/test_unit_skip_gate.py`).
Pure judgment for the skip-set gate; the conftest hook only gathers observations.
"""
from __future__ import annotations

from pathlib import Path

# fail-open-reviewed: 허용 목록은 줄마다 nodeid 하나인 목록이다 — 부분문자열 판정이 아니라 줄을 항목으로 쪼개(`#` 뒤 버림) 집합으로 대조한다
ALLOWLIST = Path(__file__).resolve().parent / "SKIP_ALLOWLIST"


def base_nodeid(nodeid: str) -> str:
    """파라미터를 뗀 nodeid — 파라미터 값이 바뀌어도 목록이 따라 늙지 않게."""
    return nodeid.split("[", 1)[0].replace("\\", "/")


def read_allowlist(path: Path = ALLOWLIST) -> set[str] | None:
    """커밋된 정당 skip 집합 — 파일이 없거나 못 읽으면 None(판정 불가 → red)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return {entry for entry in (line.split("#", 1)[0].strip() for line in raw.splitlines()) if entry}


def judge(observed: dict[str, str], collected: set[str], allowed: set[str] | None, path: Path = ALLOWLIST) -> list[str]:
    """실패 메시지 목록 — 비면 통과다.

    observed = 기준 nodeid → skip 자리 · 사유, collected = 이번에 수집된 기준 nodeid.
    🔴 낡은 항목은 «이번에 수집된» 것만 본다 — 부분 실행(`-k` · 경로 지정)이 거짓 red 가 되지 않게.
       아예 사라진 시험은 `test_unit_skip_gate.py` 가 파일 · 함수 실재로 따로 잡는다.
    """
    if allowed is None:
        return [f"skip 허용 목록을 읽지 못했다 ({path}) — 판정 불가라 red 다."]
    out = []
    unexpected = sorted(set(observed) - allowed)
    stale = sorted((allowed & collected) - set(observed))
    if unexpected:
        out.append("허용되지 않은 skip {}건 — 수집은 됐으나 돌지 않았다(목록에 넣으려면 «어디서 도는가» 를 적는다):\n  {}".format(
            len(unexpected), "\n  ".join(f"{n}  # {observed[n]}" for n in unexpected)))
    if stale:
        out.append("tests/SKIP_ALLOWLIST 가 낡았다 — 이제 skip 되지 않는 항목 {}건, 지워라:\n  {}".format(
            len(stale), "\n  ".join(stale)))
    return out
