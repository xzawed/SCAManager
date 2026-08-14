"""🔴 결정 대기 카운터의 계약 (backlog R92 — 2026-08-14 사용자 결정 (a)).

## 사고

`docs/backlog.md` 의 상태 셋 중 **🔴 만 Claude 가 닫을 수 없다**. 그런데 그것을 사용자
앞에 다시 올리는 장치가 하나도 없었다 — SessionStart 훅 2종은 회고 카덴스와 owed 원장만
본다. 실측: `R81`·`R82` 가 P0 로 등재된 뒤 **6 PR 동안 한 번도 회신 요청에 재등장하지
않았다.** 🟡 는 Claude 가 자율 착수해 자연 소멸하므로, 구조적으로 정체하는 것은 🔴 뿐이다.

## 초판이 틀린 곳 (2026-08-14 Grok `019fffde` — CLAIM 1 BROKEN)

적대 검증이 실경로 뮤테이션으로 셋을 실증했다. 전부 **위음성**이었고, 이 카운터에서
위음성은 거짓 양성보다 나쁘다 — 안 보이는 결정은 영원히 정체한다.

| 반례 | 초판 동작 |
|---|---|
| (a) `open_decisions() → []` | ✅ 0건 배너 — **건강한 상태와 구별 불가** |
| (e) `B6-b`·`R0-2`·`H2` · 볼드 상태셀 | ID 를 `R\\d+` 로 좁혀 **한 번도 안 셌다** |
| (e) `## 🔴 사용자 결정 대기` 섹션 행 | 상태 셀에 마커가 없어 **표 전체가 위음성** |
| (f) 역사 구역 | 세긴 하는데 요약의 '현재 창' 계약과 **범위가 갈라짐** |

## 고정하는 계약

| 상황 | 기대 |
|---|---|
| 상태 셀 🔴 · 볼드 🔴 · `## 🔴` 섹션 소속 | **셋 다** 센다 |
| 현재 창 / 역사 구역 | **나눠서** 인쇄(요약 계약과 갈라지지 않게) |
| 진짜 0건 | *"결정 대기 없음 — 원장 N행을 읽었고"* |
| 파서 파손 | *"파서 확인"* — 진짜 0건과 **문구가 달라야** 한다 |
| 원장 부재·읽기 실패 | **판정 불가** |
| 어느 경우든 | **exit 0** (advisory) |

🔴 **본문 산문의 🔴 을 상태로 오인하면 안 된다** — 이 리포는 본문에 🔴 이 흔하다.
상태 셀 **선두**로만 판정하는 것이 과교정 방지축이다(traps B5 · 가드 자살).
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


# ── ① 판정 정밀도 — 위음성 축 (Grok 반례 (e)(f)) ─────────────────────────


def test_only_the_status_cell_counts():
    assert gate.open_decisions(_TABLE) == [("R1", "현재")]


def test_non_numeric_ids_are_not_invisible():
    """🔴 초판은 ID 를 `R\\d+` 로 좁혀 실원장의 `B6-b`·`R0-2`·`H2` 를 한 번도 안 셌다."""
    rows = (
        "| **B6-b** | 🔴 결정 대기 | 형태 1 |\n"
        "| **R0-2** | 🔴 결정 대기 | 형태 2 |\n"
        "| **H2** | 🔴 결정 대기 | 형태 3 |\n"
    )
    assert [rid for rid, _ in gate.open_decisions(rows)] == ["B6-b", "R0-2", "H2"]


def test_bold_status_cell_is_still_a_status():
    """`| **R96** | **🔴 결정 대기** |` — 볼드로 감싸면 안 보이던 위음성."""
    assert gate.open_decisions("| **R96** | **🔴 결정 대기** | x |\n") == [("R96", "현재")]


def test_section_membership_counts_even_without_a_cell_marker():
    """🔴 `## 🔴 사용자 결정 대기` 섹션의 행은 **상태 셀에 마커가 없다**.

    실원장의 `B6-b`·`B7` 이 그 형태다. 상태 셀만 보면 그 표 전체가 위음성이었다.
    """
    doc = "## 🔴 사용자 결정 대기\n\n| **B9** | 넓은 범위 | 본문 |\n"
    assert gate.open_decisions(doc) == [("B9", "현재")]


def test_history_zone_is_reported_separately():
    """🔴 요약이 '역사 섹션은 카운트 제외' 라 적으므로 카운터도 구분한다(반례 (f)).

    한 숫자로 뭉개면 `test_backlog_shape.current_window()` 와 갈라진다. 세되 **나눠서**
    센다 — 역사 구역의 결정도 열려 있는 것은 사실이기 때문이다.
    """
    doc = (
        "| **R1** | 🔴 결정 대기 | 현재 |\n"
        "## ▶️ (역사) 옛 인수인계\n\n"
        "| **R2** | 🔴 결정 대기 | 옛것 |\n"
    )
    assert gate.open_decisions(doc) == [("R1", "현재"), ("R2", "역사")]


def test_prose_red_markers_are_not_statuses():
    """🔴 과교정 방지 — 본문에 🔴 이 있는 행을 세면 거의 전 행이 잡힌다(가드 자살).

    이 리포의 backlog 는 기전 설명에 🔴 을 상시 쓴다. 상태 셀 선두로만 판정하지 않으면
    카운터가 *"결정 대기 55건"* 을 인쇄하고 아무도 안 읽게 된다.
    """
    noisy = "| **R9** | 🟡 착수 가능 | 🔴 **중요**: 이 기전은 🔴 로 표시된다 |\n"
    assert gate.open_decisions(noisy) == []


def test_real_backlog_is_parsed_and_finds_open_decisions():
    """🔴 대조군 — 실파일에서 **실제로 결정 대기를 찾아야** 한다.

    초판은 `isinstance(..., list)` 만 봤다. 그래서 `open_decisions()` 를 `return []` 로
    죽여도 **green 이었다**(반례 (a)) — 계수를 주장하는 이름의 테스트가 계수를 안 쟀다.
    """
    text = (_ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    rows = gate._ROW.findall(text)  # pylint: disable=protected-access
    assert len(rows) >= 30, f"실 backlog 에서 {len(rows)}행만 파싱했다 — 정규식 확인"

    found = gate.open_decisions(text)
    assert found, "실 backlog 에서 결정 대기를 0건 찾았다 — 계수가 죽었거나 원장이 비었다"
    assert all(zone in ("현재", "역사") for _, zone in found)


# ── ② 실행 관측 — '판정 불가'·'파손' 을 '0건' 으로 흘리지 않는다 ──────────


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
    assert "파서 확인" in capsys.readouterr().out


def test_pending_rows_are_named(tmp_path, monkeypatch, capsys):
    """이름을 인쇄해야 사용자가 무엇을 결정할지 안다 — 개수만으로는 행동이 안 나온다."""
    f = tmp_path / "backlog.md"
    f.write_text(_TABLE, encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", f)
    monkeypatch.setattr(f"{_MOD}.merged_prs_since_backlog_touch", lambda: 0)
    assert gate.main() == 0
    out = capsys.readouterr().out
    assert "결정 대기 1건" in out and "R1" in out


def test_zero_pending_is_distinguishable_from_a_broken_parser(tmp_path, monkeypatch, capsys):
    """🔴 **'진짜 0건' 과 '파서 파손' 이 사람 눈에 구별돼야 한다** (반례 (a)(b)).

    초판은 둘 다 «0건» 을 인쇄했고 테스트는 `"0건" in out` 이라 **양쪽 다 green** 이었다.
    계수 함수를 죽여도 건강한 배너와 같아 보이는 상태 — observer-lie 그 자체다.
    지금은 정상 0건이 **읽은 행 수**를 함께 말하고, 파손은 *"파서 확인"* 을 말한다.
    """
    healthy_file = tmp_path / "backlog.md"
    healthy_file.write_text(_TABLE.replace("🔴 결정 대기", "✅ 완료"), encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", healthy_file)
    assert gate.main() == 0
    healthy = capsys.readouterr().out
    assert "결정 대기 **없음**" in healthy
    assert "행을 읽었고" in healthy, "정상 0건이 '몇 행을 읽었는지' 를 말하지 않는다"

    # 파손 배너와 문구가 실제로 다른지 대조 — 같으면 위 단언이 공허하다.
    broken_file = tmp_path / "broken.md"
    broken_file.write_text("표가 없는 문서\n", encoding="utf-8")
    monkeypatch.setattr(f"{_MOD}._BACKLOG", broken_file)
    gate.main()
    broken = capsys.readouterr().out
    assert "파서 확인" in broken
    assert "결정 대기 **없음**" not in broken, "파손이 정상 0건과 같은 문구를 쓴다"


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
