"""🔴 결정 대기 카운터의 계약 (backlog R92 — 2026-08-14 사용자 결정 (a)).

## 사고

`docs/backlog.md` 의 상태 셋 중 **🔴 만 Claude 가 닫을 수 없다**. 그런데 그것을 사용자
앞에 다시 올리는 장치가 하나도 없었다 — SessionStart 훅 2종은 회고 카덴스와 owed 원장만
본다. 실측: `R81`·`R82` 가 P0 로 등재된 뒤 **6 PR 동안 한 번도 회신 요청에 재등장하지
않았다.** 🟡 는 Claude 가 자율 착수해 자연 소멸하므로, 구조적으로 정체하는 것은 🔴 뿐이다.

## 고정하는 계약

| 상황 | 기대 |
|---|---|
| 🔴 행 존재 | 개수 + ID 목록을 인쇄 |
| 🔴 0건 | 명시적 ✅ (무음 아님) |
| 원장 부재·읽기 실패 | **판정 불가**를 인쇄 — "0건" 과 구별한다 |
| 표 파싱 0행 | **판정 불가** (빈 범위 위의 초록은 fail-open) |
| 어느 경우든 | **exit 0** (advisory — 세션을 막지 않는다) |

🔴 **본문 산문의 🔴 을 상태로 오인하면 안 된다** — 이 리포는 본문에 🔴 이 흔하다.
상태 셀 **선두 문자**로만 판정하는 것이 과교정 방지축이다(traps B5).
"""
from __future__ import annotations

from pathlib import Path

import scripts.check_open_decisions as gate

_ROOT = Path(__file__).resolve().parents[3]
_MOD = "scripts.check_open_decisions"

_TABLE = (
    "| ID | 상태 | 제목 |\n"
    "|---|---|---|\n"
    "| **R1** | 🔴 결정 대기 | 무언가 |\n"
    "| **R2** | 🟡 착수 가능 | 다른 것 |\n"
    "| **R3** | ✅ 완료 | 끝난 것 |\n"
)


# ── ① 판정 정밀도 ────────────────────────────────────────────────────────


def test_only_the_status_cell_counts():
    assert gate.open_decisions(_TABLE) == ["R1"]


def test_prose_red_markers_are_not_statuses():
    """🔴 과교정 방지 — 본문에 🔴 이 있는 행을 결정 대기로 세면 거의 전 행이 잡힌다.

    이 리포의 backlog 는 기전 설명에 🔴 을 상시 쓴다. 상태 셀 선두로만 판정하지 않으면
    카운터가 *"결정 대기 55건"* 을 인쇄하고 아무도 안 읽게 된다(가드 자살).
    """
    noisy = "| **R9** | 🟡 착수 가능 | 🔴 **중요**: 이 기전은 🔴 로 표시된다 |\n"
    assert gate.open_decisions(noisy) == []


def test_real_backlog_is_parsed_and_nonempty():
    """대조군 — 합성 표만 통과하고 실파일에서 0행이면 이 가드는 공허하다."""
    text = (_ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    rows = gate._ROW.findall(text)  # pylint: disable=protected-access
    assert len(rows) >= 30, f"실 backlog 에서 {len(rows)}행만 파싱했다 — 정규식 확인"
    assert isinstance(gate.open_decisions(text), list)


# ── ② 실행 관측 — '판정 불가' 를 '0건' 으로 흘리지 않는다 ────────────────


def test_missing_ledger_is_undecidable_not_zero(tmp_path, monkeypatch, capsys):
    """🔴 원장이 없으면 **판정 불가**다 — 무음 통과는 owed 카운터가 밟은 클래스(R0-2)."""
    monkeypatch.setattr(f"{_MOD}._BACKLOG", tmp_path / "gone.md")
    assert gate.main() == 0
    out = capsys.readouterr().out
    assert "판정 불가" in out
    assert "0건이라는 뜻이 아니다" in out


def test_empty_table_is_undecidable(tmp_path, monkeypatch, capsys):
    f = tmp_path / "backlog.md"
    f.write_text("표가 없는 문서\n", encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    assert gate.main() == 0
    assert "0건** 찾았다" in capsys.readouterr().out


def test_pending_rows_are_named(tmp_path, monkeypatch, capsys):
    """이름을 인쇄해야 사용자가 무엇을 결정할지 안다 — 개수만으로는 행동이 안 나온다."""
    f = tmp_path / "backlog.md"
    f.write_text(_TABLE, encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    monkeypatch.setattr(f"{_MOD}.merged_prs_since_backlog_touch", lambda: 0)
    assert gate.main() == 0
    out = capsys.readouterr().out
    assert "결정 대기 1건" in out and "R1" in out


def test_zero_pending_is_explicit(tmp_path, monkeypatch, capsys):
    """대조군 — 0건일 때 조용하면 '안 돌았다' 와 구별되지 않는다."""
    f = tmp_path / "backlog.md"
    f.write_text(_TABLE.replace("🔴 결정 대기", "✅ 완료"), encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    assert gate.main() == 0
    assert "0건" in capsys.readouterr().out


def test_always_advisory(tmp_path, monkeypatch):
    """🔴 어느 경로로도 exit 0 — 세션을 막지 않는다(정책 17 안정성)."""
    f = tmp_path / "backlog.md"
    f.write_text(_TABLE, encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    monkeypatch.setattr(f"{_MOD}.merged_prs_since_backlog_touch", lambda: 999)
    assert gate.main() == 0


# ── ③ 한계를 숨기지 않는다 ──────────────────────────────────────────────


def test_it_says_what_it_cannot_judge(tmp_path, monkeypatch, capsys):
    """🔴 **중요도·의도적 보류를 판정하지 않는다**는 고지가 출력에 있어야 한다.

    없으면 다음 세션이 이 배너를 *"이 6건은 방치된 결함"* 으로 읽는다. 사용자가
    의도적으로 보류한 항목도 같은 모양으로 잡히므로, 촉구임을 매번 밝힌다.
    """
    f = tmp_path / "backlog.md"
    f.write_text(_TABLE, encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    monkeypatch.setattr(f"{_MOD}.merged_prs_since_backlog_touch", lambda: 0)
    gate.main()
    assert "판정하지 않는다" in capsys.readouterr().out


def test_stale_threshold_matches_the_sibling_ledger():
    """두 원장의 정체 기준이 갈라지면 어느 쪽을 믿을지 알 수 없다."""
    import scripts.check_owed_verification as owed  # pylint: disable=import-outside-toplevel

    assert gate._STALE_PR_THRESHOLD == owed._STALE_PR_THRESHOLD  # pylint: disable=protected-access
