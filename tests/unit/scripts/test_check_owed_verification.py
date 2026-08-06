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
    _STALE_PR_THRESHOLD,
    SAFETY_TIER_MARKER,
    evaluate,
    main,
    merged_prs_since_ledger,
    parse_rows,
    pending_rows,
)

# 🔴 패치는 **string-path** 로 한다 (`.claude/rules/testing.md` §모듈 패치 시 이중 import 회피).
#    `import X as mod` + `from X import ...` 공존은 CodeQL `py/import-and-import-from` 를
#    자초하고 `check_dual_import.py` 가 신규 도입을 pre-merge 차단한다(실제로 차단당했다).
_MOD = "scripts.check_owed_verification"

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


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 완전성 축 (backlog R0-2) — "빈 원장이 green" 의 봉인
#
# 이 스크립트는 **원장에 적힌 것만** 셌다. 그래서 부채를 등재하지 않는 것이 가장 싼 통과
# 경로였다 — 파일이 없으면 아예 무음이었고, 비어 있으면 "미결 0건" 이라는 초록 문구가 나왔다.
# 실측된 기전: 창 42 PR 중 22건이 미체크 항목을 단 채 머지됐는데 세는 관측자가 0이었다.
#
# 두 축을 고정한다. 둘 다 advisory(exit 0)이지만 **판정 불가를 초록으로 흘리지 않는다**.
#   A. 원장 부재·읽기 실패·데이터 0행 → loud
#   B. 원장 갱신 이후 머지 PR 수가 임계 초과 → loud (git 전용, `gh`·네트워크 불요)
# ──────────────────────────────────────────────────────────────────────────────



def _run(monkeypatch, capsys, ledger: Path, *, since=0):
    """원장 경로와 intake 수를 주입해 main() 을 돌리고 출력을 돌려준다."""
    monkeypatch.setattr(f"{_MOD}._LEDGER", ledger)
    monkeypatch.setattr(f"{_MOD}.merged_prs_since_ledger", lambda: since)
    assert main() == 0, "advisory 계약 위반 — 항상 exit 0 이어야 한다(정책 17)"
    return capsys.readouterr().out


def test_missing_ledger_is_loud_not_silent(monkeypatch, capsys, tmp_path):
    """🔴 파일이 없으면 **판정 불가**라고 말해야 한다.

    이전 구현은 무음 `return 0` 이었다 — '부채 없음' 과 '원장이 사라짐' 이 구별되지 않았고,
    후자가 훨씬 나쁜 상태인데 더 조용했다.
    """
    out = _run(monkeypatch, capsys, tmp_path / "nope.md")
    assert "판정 불가" in out, "원장 부재를 조용히 통과시켰다"


def test_empty_ledger_is_loud(monkeypatch, capsys, tmp_path):
    """🔴 데이터 행이 0건이면 loud — 이것이 R0-2 가 지목한 바로 그 상태다.

    비어 있는 원장에 대해 "미결 0건" 이라고 답하면, **등재하지 않는 것**이 가장 싼
    통과 경로가 된다.
    """
    ledger = tmp_path / "owed.md"
    ledger.write_text("# 원장\n\n표 없음\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, ledger)
    assert "0건" in out and "등재" in out, f"빈 원장을 초록으로 보고했다:\n{out}"


def test_populated_ledger_still_reports_normally(monkeypatch, capsys, tmp_path):
    """대조군 — 항목이 있으면 기존 보고를 그대로 한다(무조건 빨강이면 신호가 죽는다)."""
    ledger = tmp_path / "owed.md"
    ledger.write_text(
        "## 운영 등급\n\n| PR | 항목 | 근거 | 정책 | 상태 |\n|---|---|---|---|---|\n"
        "| **#1** | x | y | 2 | \u23f3 |\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, ledger)
    assert "미결" in out
    assert "판정 불가" not in out


def test_stale_intake_is_loud(monkeypatch, capsys, tmp_path):
    """🔴 원장이 오래 손대지지 않았으면 촉구한다 — 실측 기전이 'intake 172 PR 동안 0건'.

    이 축은 **무엇이 빠졌는지 모른다**. 정체만 관측한다 — 산문으로 '등재 대상인가' 를
    판정하면 오탐이 진탐을 넘어 가드 자살이 된다(정책 17).
    """
    ledger = tmp_path / "owed.md"
    ledger.write_text(
        "## 운영 등급\n\n| PR | 항목 | 근거 | 정책 | 상태 |\n|---|---|---|---|---|\n"
        "| **#1** | x | y | 2 | \u2705 |\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, ledger, since=_STALE_PR_THRESHOLD)
    assert "PR** 동안" in out or "동안 손대지" in out, f"정체를 보고하지 않았다:\n{out}"


def test_fresh_intake_is_silent_about_staleness(monkeypatch, capsys, tmp_path):
    """대조군 — 최근에 갱신됐으면 그 축은 조용해야 한다(배너 피로 방지)."""
    ledger = tmp_path / "owed.md"
    ledger.write_text(
        "## 운영 등급\n\n| PR | 항목 | 근거 | 정책 | 상태 |\n|---|---|---|---|---|\n"
        "| **#1** | x | y | 2 | \u2705 |\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, ledger, since=_STALE_PR_THRESHOLD - 1)
    assert "동안 손대지" not in out


def test_unknown_intake_is_reported_as_undecidable(monkeypatch, capsys, tmp_path):
    """🔴 git 이 답을 못 주면 **판정 불가**로 인쇄한다 — 조용한 0 은 초록과 구별되지 않는다."""
    ledger = tmp_path / "owed.md"
    ledger.write_text(
        "## 운영 등급\n\n| PR | 항목 | 근거 | 정책 | 상태 |\n|---|---|---|---|---|\n"
        "| **#1** | x | y | 2 | \u2705 |\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, ledger, since=None)
    assert "판정 불가" in out


def test_intake_counter_uses_git_only(monkeypatch):
    """🔴 `gh`·네트워크에 의존하면 CI·오프라인에서 **항상 무음**이 되어 새 fail-open 이다."""
    calls = []

    def fake_run(argv, **_kw):
        calls.append(argv[0])

        class R:  # noqa: D401
            returncode = 1
            stdout = ""
        return R()

    monkeypatch.setattr(f"{_MOD}.subprocess.run", fake_run)
    merged_prs_since_ledger()
    assert calls and all(c == "git" for c in calls), f"git 외 도구를 호출했다: {calls}"


def test_intake_counter_counts_squash_titles(monkeypatch):
    """머지 제목 말미의 `(#NNNN)` 만 센다 — 이 저장소의 유일한 머지 형태다."""
    outputs = iter(["deadbeef\n", "feat: a (#1)\nwip: no pr\nfix: b (#22)\n"])

    def fake_run(_argv, **_kw):
        class R:
            returncode = 0
            stdout = next(outputs)
        return R()

    monkeypatch.setattr(f"{_MOD}.subprocess.run", fake_run)
    assert merged_prs_since_ledger() == 2
