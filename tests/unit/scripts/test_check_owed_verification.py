"""owed 원장 미결 카운터 정합 (회고 2026-07-19 P0 — 원장이 write-only 였던 자기위반 봉인).

P0 실측: #1084 가 원장 파일만 만들고 **어떤 집행면에도 배선하지 않아**, 같은 세션 첫 기회에
안전등급 2건이 미회신인 채 종료됐다. 회고 P0 가 "문서-only 시정은 행동을 못 바꾼다"고 결론낸
직후 같은 형태로 신설된 것 — 문서-only 처방 3회차.
P0: #1084 created the ledger file but wired it to no enforcement surface, so its own safety-tier
rows went unanswered in the very first window — the third repetition of the doc-only remedy.

🔴 순수 함수만 테스트 — 현재 원장의 미결 여부는 시점 의존이라 단언 금지(flaky).
Pure functions only — the live ledger's pending state is time-dependent, so not asserted.
"""
from pathlib import Path

from scripts.check_owed_verification import (
    SAFETY_TIER_MARKER,
    evaluate,
    parse_rows,
    pending_rows,
)

_ROOT = Path(__file__).resolve().parents[3]

_LEDGER_SAMPLE = """# 미결 운영 검증 원장

## 🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1058** | SMTP 실발송 | 수신함 확인 | 5·13 | ⏳ |
| **#1062** | IDOR 과잉차단 | 7 라우트 200 | 15 | ✅ |

## 운영/외부 계약 등급 (Phase 종료 일괄 회신 — 정책 2 진화)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1071** | HSTS 헤더 | curl -I | 13 | ⏳ |
| **#1075** | retention DELETE | cron 로그 | 13 | ⏭️ |
"""


# ── 순수 함수: parse_rows ────────────────────────────────────────────────


def test_parse_rows_extracts_pr_status_and_tier():
    """PR 번호·상태·등급(안전/운영)을 행마다 추출."""
    rows = parse_rows(_LEDGER_SAMPLE)
    assert [r["pr"] for r in rows] == ["#1058", "#1062", "#1071", "#1075"]
    assert [r["status"] for r in rows] == ["⏳", "✅", "⏳", "⏭️"]
    assert [r["safety"] for r in rows] == [True, True, False, False]


def test_parse_rows_skips_header_and_separator():
    """표 헤더(`| PR | …`)와 구분선(`|----|`)은 데이터 행이 아니다."""
    rows = parse_rows(_LEDGER_SAMPLE)
    assert all(r["pr"].startswith("#") for r in rows)
    assert len(rows) == 4, "헤더/구분선이 행으로 새면 카운트가 부풀려진다"


def test_parse_rows_empty_on_no_tables():
    assert parse_rows("# 제목만 있고 표 없음\n\n본문.\n") == []


# ── 순수 함수: pending_rows ──────────────────────────────────────────────


def test_pending_rows_only_hourglass():
    """⏳ 만 미결 — ✅/❌/⏭️ 는 종결(회신 완료 또는 명시 보류)."""
    rows = parse_rows(_LEDGER_SAMPLE)
    assert [r["pr"] for r in pending_rows(rows)] == ["#1058", "#1071"]


def test_pending_rows_excludes_resolved_safety_row():
    """✅ 로 바뀐 안전등급 행은 미결에서 빠진다 (회신 반영 확인)."""
    rows = parse_rows(_LEDGER_SAMPLE)
    assert "#1062" not in [r["pr"] for r in pending_rows(rows)]


# ── 순수 함수: evaluate ──────────────────────────────────────────────────


def test_evaluate_breached_when_safety_tier_pending():
    """🔴 긍정 통제 — 안전등급 ⏳ 1건이면 breached (정책 5 NEW-P0-N 매 사이클 회신 의무).

    이 단언이 죽으면 카운터 전체가 공허해진다 — 회고가 지적한 '긍정 통제 부재' 재발 차단.
    """
    breached, msg = evaluate(parse_rows(_LEDGER_SAMPLE))
    assert breached is True
    assert "#1058" in msg, "미결 안전등급 PR 번호가 메시지에 노출돼야 조치 가능"


def test_evaluate_not_breached_when_only_operational_pending():
    """운영등급만 미결이면 breached 아님 — Phase 종료 일괄 회신 대상(정책 2 진화)."""
    text = _LEDGER_SAMPLE.replace("| **#1058** | SMTP 실발송 | 수신함 확인 | 5·13 | ⏳ |",
                                  "| **#1058** | SMTP 실발송 | 수신함 확인 | 5·13 | ✅ |")
    breached, msg = evaluate(parse_rows(text))
    assert breached is False
    assert "#1071" in msg, "운영등급 미결도 카운트는 보고돼야 한다"


def test_evaluate_clean_when_nothing_pending():
    text = _LEDGER_SAMPLE.replace("⏳", "✅")
    breached, msg = evaluate(parse_rows(text))
    assert breached is False
    assert "0" in msg


def test_evaluate_empty_ledger_is_clean():
    """행이 없으면 미결 0 — 파싱 실패가 breached 로 오탐되지 않게."""
    breached, _ = evaluate([])
    assert breached is False


# ── 실제 원장 파일 계약 ─────────────────────────────────────────────────


def test_live_ledger_parses_nonempty():
    """🔴 실제 원장이 파싱된다 — 형식이 바뀌어 0행이 되면 카운터가 무음으로 눈이 먼다.

    #1094 형('가드가 무력한데 green') 재발 차단: 파싱 결과 0행 = 카운터 무력화와 구분 불가.
    """
    ledger = _ROOT / "docs" / "runbooks" / "owed-verification.md"
    rows = parse_rows(ledger.read_text(encoding="utf-8"))
    assert len(rows) >= 4, f"원장 파싱 0~3행 — 표 형식 변경 의심 (실측 {len(rows)}행)"
    assert any(r["safety"] for r in rows), "안전등급 섹션 인식 실패 — 마커 변경 의심"


def test_safety_marker_present_in_live_ledger():
    """안전등급 섹션 마커가 원장에 실재 — 마커 drift 시 등급 분류가 조용히 무너진다."""
    ledger = _ROOT / "docs" / "runbooks" / "owed-verification.md"
    assert SAFETY_TIER_MARKER in ledger.read_text(encoding="utf-8")
