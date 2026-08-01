"""`docs/backlog.md` 의 **구조 정합**만 검사한다 — 산문은 보지 않는다.

## 사고 (2026-07-19 회고 P1, 한 파일에 12건)

원장이 자기 자신과 모순된 채 방치됐다:

  · 요약표 `🔴 결정 대기 | 1` 인데 본문 §🔴 는 `_현재 없음._` (정면 모순)
  · 요약표 `🟡 5` 인데 본문 미완 행은 6
  · 완료된 B3·B4 가 **착수 순서 1·2위**로 남아 다음 세션을 오도
  · 결정 항목 B6-b 가 🟡 표에 들어가 있어 "결정 요청 의무" 흐름이 트리거되지 않음

`#1128` 이 헤더 산술을 한 번 고쳤으나 **같은 세션 두 PR 뒤에 재파손**됐다 — 사람이 두 곳을
동시에 갱신하는 규율에 의존했기 때문이다.

## 🔴 왜 '카운트 대응' 만 보는가

산문의 진위는 정적 검사로 판정할 수 없고, 그런 린터는 통과가 아무것도 보장하지 않아
**observer-lie 를 하나 더 만든다**. Grok 협의 결론도 같다 —
*"count bijection 은 하되 산문 NLP 는 하지 말 것."*

이 파일은 **"요약표의 수 == 본문 행 수"** 라는 산술 하나만 강제한다. 그 산술은 사람이
한쪽만 고치는 순간 즉시 깨지고, CI 가 그것을 잡는다.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_BACKLOG = _ROOT / "docs" / "backlog.md"

# 요약표 행: `| 🔴 결정 대기 | **2** (…) | … |`
_SUMMARY_RE = re.compile(r"^\|\s*(🔴|🟡|⏸️)[^|]*\|\s*\*\*(\d+)\*\*[^|]*\|", re.M)
# 본문 항목 행: `| **B6-b** | … |`
_ITEM_RE = re.compile(r"^\|\s*\*\*([\w-]+)\*\*\s*\|", re.M)


def _text() -> str:
    return _BACKLOG.read_text(encoding="utf-8")


def summary_counts(text: str) -> dict:
    """요약표에서 상태별 선언 수 — `{"🔴": 2, "🟡": 2, "⏸️": 1}`."""
    return {m.group(1): int(m.group(2)) for m in _SUMMARY_RE.finditer(text)}


def body_rows(text: str) -> dict:
    """본문 섹션별 항목 ID — `{"🔴": ["B5","B6-b"], ...}`.

    🔴 섹션 판정은 `## ` 제목의 **선행 이모지**로만 한다(산문 언급과 구별).
    """
    out = {}
    for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
        title = chunk.split("\n", 1)[0]
        marker = next((m for m in ("🔴", "🟡", "⏸️") if title.startswith(m)), None)
        if not marker:
            continue
        out[marker] = [m.group(1) for m in _ITEM_RE.finditer(chunk)]
    return out


# ── 핵심 불변식 / the invariant ──────────────────────────────────────────


def test_summary_counts_match_body_rows():
    """🔴 요약표의 수 == 본문 섹션의 행 수 — 한쪽만 고치면 즉시 깨진다.

    이 단언 하나가 회고 P1 12건 중 산술 모순 전부를 덮는다.
    """
    text = _text()
    summary, body = summary_counts(text), body_rows(text)
    assert summary, "요약표를 못 찾았다 — 표 형식이 바뀌었는지 확인할 것"
    mismatched = {
        marker: (count, len(body.get(marker, [])), body.get(marker, []))
        for marker, count in summary.items()
        if count != len(body.get(marker, []))
    }
    assert not mismatched, (
        "요약표 수와 본문 행 수가 어긋난다 (마커: (요약, 본문, 본문항목)):\n"
        f"  {mismatched}\n"
        "→ 항목을 옮기거나 완료 처리했으면 **요약표도 같은 커밋에서** 갱신할 것."
    )


def test_no_section_claims_empty_while_summary_counts_rows():
    """🔴 본문이 `_현재 없음._` 인데 요약표가 0 이 아니면 정면 모순이다.

    실측 사고의 정확한 형태 — 요약표 "🔴 1건" · 본문 "_현재 없음._".
    """
    text = _text()
    summary = summary_counts(text)
    for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
        title = chunk.split("\n", 1)[0]
        marker = next((m for m in ("🔴", "🟡", "⏸️") if title.startswith(m)), None)
        if marker and "_현재 없음._" in chunk:
            assert summary.get(marker, 0) == 0, (
                f"본문 §{marker} 는 '_현재 없음._' 인데 요약표는 {summary.get(marker)}건이다"
            )


def test_priority_order_only_references_open_items():
    """🔴 착수 순서가 **열린 항목**만 가리켜야 한다 — 완료분을 1순위로 두면 오도한다.

    실측: 완료된 B3·B4 가 착수 순서 선두 2건으로 남아 있었다.
    """
    text = _text()
    body = body_rows(text)
    open_ids = {i for ids in body.values() for i in ids}
    m = re.search(r"\*\*권장 착수 순서\*\*:(.+?)(?:\n\n|\n🔴)", text, re.DOTALL)
    assert m, "권장 착수 순서 문구를 못 찾았다"
    referenced = set(re.findall(r"\*\*(B[\w-]*)\*\*", m.group(1)))
    stale = sorted(referenced - open_ids)
    assert not stale, (
        f"착수 순서가 본문에 없는(완료·이동된) 항목을 가리킨다: {stale}\n"
        f"현재 열린 항목: {sorted(open_ids)}"
    )


def test_open_sections_contain_no_completed_items():
    """🔴 열린 섹션(🔴·🟡)에 **완료 표지가 붙은 행**이 있으면 안 된다.

    ## Grok 적대 검토가 반증한 지점 (C2)

    카운트 전단사만으로는 이 편집을 막지 못한다:

        본문 §🟡 에  `| **B3** | ✅ 완료 (#1131) | … |`  를 남기고
        요약표를  `| 🟡 착수 가능 | **3** |`  로 함께 올린다

    → 수는 완전히 맞고 5개 테스트가 전부 green 인데 **원장은 거짓말한다**. 그리고 이건
    가정이 아니라 **이 PR 이 고친 원래 결함과 정확히 같은 형태**다(완료된 B3·B4 가
    착수 순서 1·2위에 남아 다음 세션을 오도했다).

    🔴 교훈: 카운트 대응은 필요조건이지 충분조건이 아니다. "몇 개인가" 가 맞아도
    "그것이 열린 일인가" 가 틀리면 원장은 여전히 오도한다.
    Count bijection is necessary, not sufficient — matching counts of the WRONG rows still lies.

    산문이 아니라 **표지(marker)** 를 본다 — `✅` 나 `완료` 는 사람이 붙이는 구조적 표시다.
    """
    text = _text()
    offenders = []
    for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
        title = chunk.split("\n", 1)[0]
        if not any(title.startswith(m) for m in ("🔴", "🟡")):
            continue
        for line in chunk.splitlines():
            m = _ITEM_RE.match(line)
            if m and ("✅" in line or "완료" in line):
                offenders.append(f"§{title[:12]} → {m.group(1)}")
    assert not offenders, (
        f"열린 섹션에 완료 표지가 붙은 행이 있다: {offenders}\n"
        "→ 완료분은 헤더의 '완료분' 줄로 옮기고 요약표 수를 함께 내릴 것.\n"
        "   (수만 맞추고 완료 항목을 남기면 원장은 green 인 채로 오도한다 — Grok C2)"
    )


def test_decision_items_are_not_parked_in_the_actionable_section():
    """🔴 결정 대기 항목이 🟡(착수 가능)에 섞이면 **결정 요청 의무가 트리거되지 않는다**.

    실측 사고: B6-b(AI 자기 머지 거버넌스 — 사용자 영역)가 🟡 표에 들어가 있어
    "다음 사이클 진입 시 회신 요청" 흐름을 타지 못했다. 수는 맞았다.
    """
    body = body_rows(_text())
    text = _text()
    misplaced = []
    for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
        if not chunk.split("\n", 1)[0].startswith("🟡"):
            continue
        for line in chunk.splitlines():
            m = _ITEM_RE.match(line)
            if m and ("사용자 결정" in line or "결정 대기" in line):
                misplaced.append(m.group(1))
    assert not misplaced, (
        f"🟡(착수 가능)에 사용자 결정 항목이 있다: {misplaced} → 🔴 섹션으로 옮길 것"
    )
    assert body.get("🟡") is not None, "🟡 섹션이 사라졌다 — 이 가드의 전제 붕괴"


# ── 탐지력 자가 검증 / self-verification ─────────────────────────────────


def test_detector_flags_a_synthetic_count_mismatch():
    """합성 불일치를 실제로 잡는가 — 통과만 하는 가드 차단."""
    synthetic = (
        "| 🔴 결정 대기 | **3** (x) | y |\n"
        "\n## 🔴 사용자 결정 대기\n\n| **B1** | a |\n"
    )
    assert summary_counts(synthetic) == {"🔴": 3}
    assert body_rows(synthetic) == {"🔴": ["B1"]}


def test_section_detection_ignores_prose_mentions():
    """🔴 제목 **선행 이모지**로만 섹션을 판정한다 — 산문 언급은 세지 않는다.

    "🔴 결정 대기 항목은 …" 같은 본문 문장이 섹션으로 오인되면 카운트가 흔들린다.
    """
    prose = "## 갱신 규칙\n\n🔴 결정 대기 항목은 회신 요청 의무.\n\n| **B9** | x |\n"
    assert body_rows(prose) == {}, "산문 섹션이 상태 섹션으로 오인됐다"


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 위 불변식이 보는 범위 = **파일 맨 아래 `## 🔴/🟡/⏸️` 섹션 5행뿐**이다.
#
# 실측(2026-08-01): 원장의 실제 항목은 **33행**이고 그중 28행은 두 개의 인수인계 표
#   (`▶️ 다음 세션 시작점` · `▶️ (역사) …`)에 있는데, 위 파서는 `## ` 제목의 선행 이모지로
#   섹션을 찾으므로 **그 28행을 한 번도 읽지 않는다**. 회고가 적발한
#   "회귀 가드가 원장 23행 중 5행만 본다" 가 바로 이것이다.
#
# 가드가 **있는데 안 보는** 형태라 가장 조용하다 — 테스트는 계속 초록이고,
# 원장은 계속 틀린다. 아래가 현재 창 표를 실제로 본다.
# ──────────────────────────────────────────────────────────────────────────────

# 현재 창 표의 항목 행: `| **R29** | 🟡 착수 가능 | … |`
_TABLE_ROW_RE = re.compile(r"^\|\s*\*\*(R[\w-]+)\*\*\s*\|\s*([^|]+?)\s*\|", re.M)
# 선언 요약: `> **상태 요약 — 이 표(현재 창) 16행 기준**: 🔴 결정 대기 **1** · 🟡 … **9** · …`
_DECLARED_TOTAL_RE = re.compile(r"상태 요약[^:]*?(\d+)행 기준")
_DECLARED_PART_RE = re.compile(r"(🔴|🟡|⏸️|✅)[^*·]*\*\*(\d+)\*\*")

_MARKERS = ("🔴", "🟡", "⏸️", "✅")


def current_window(text: str) -> str:
    """현재 창 섹션만 잘라낸다 — 역사 섹션의 행이 카운트에 섞이면 안 된다."""
    head, sep, _ = text.partition("## ▶️ (역사)")
    assert sep, "역사 섹션 구분자를 못 찾았다 — 파일 구조가 바뀌었다(fail-closed)"
    return head


def table_status_counts(text: str) -> dict:
    """현재 창 표의 상태 열을 마커별로 센다."""
    counts = {}
    for match in _TABLE_ROW_RE.finditer(text):
        status = match.group(2)
        marker = next((m for m in _MARKERS if status.startswith(m)), None)
        assert marker, f"상태 열이 범례 마커로 시작하지 않는다: {status!r}"
        counts[marker] = counts.get(marker, 0) + 1
    return counts


def test_status_summary_matches_the_table():
    """🔴 선언된 상태 요약이 **현재 창 표의 실제 행**과 일치해야 한다.

    손유지 카운트는 반드시 drift 한다 — 이 요약을 쓰는 그 자리에서 필자(Claude)가
    🔴 를 2로 잘못 세었고, 실제는 1이었다(R0-2 는 역사 섹션 소속). 사람이 세는 한
    같은 실수가 반복되므로 산술만 기계로 고정한다(산문은 보지 않는다 — 위 §설계 원칙).
    """
    window = current_window(_text())
    actual = table_status_counts(window)
    assert sum(actual.values()) >= 10, f"표를 못 읽었다 — 파서 고장: {actual}"

    declared_total = _DECLARED_TOTAL_RE.search(window)
    assert declared_total, "상태 요약 줄을 못 찾았다 — 요약 삭제도 실패로 본다(fail-closed)"

    summary_line = window[declared_total.start():].split("\n", 1)[0]
    declared = {m: int(n) for m, n in _DECLARED_PART_RE.findall(summary_line)}
    assert declared, f"요약 줄에서 마커별 수를 못 읽었다: {summary_line!r}"

    assert int(declared_total.group(1)) == sum(actual.values()), (
        f"선언 총행 {declared_total.group(1)} != 실제 {sum(actual.values())}행"
    )
    assert declared == actual, (
        f"상태 요약이 표와 어긋난다:\n  선언 {declared}\n  실제 {actual}\n"
        "→ 항목 상태를 바꿨으면 **같은 커밋에서** 요약 줄도 갱신할 것."
    )


# ── R24 — 전장(whole-file) 상태 legality / whole-file status legality ────────
#
# 위 카운트 불변식은 **현재 창 표만** 본다(`current_window` 가 역사 섹션을 잘라낸다).
# 역사 2026-07-26 창 표는 현재 창과 같은 `| **Rn** | 상태 |` 형태라 같은 파서로
# 커버 가능한데도 **한 번도 읽히지 않았다**. 아래는 파일 전체를 훑는 legality 백스톱이다.
# The count invariants above only see the current-window table; the history handover
# tables share the same row shape yet were never read. This is the whole-file backstop.


def whole_file_status_rows(text: str) -> list:
    """파일 **전체**의 `| **Rn** | 상태 |` 행 — (ID, 상태 셀) 쌍. 창 절단 없음.
    Every R-row in the whole file as (id, status-cell) pairs — no window slicing."""
    return [(m.group(1), m.group(2)) for m in _TABLE_ROW_RE.finditer(text)]


def illegal_status_rows(rows: list) -> list:
    """상태 셀이 범례 마커(🔴/🟡/⏸️/✅)로 시작하지 않는 행만 추린다.
    Rows whose status cell does not start with a legal legend marker."""
    return [(rid, status) for rid, status in rows
            if not any(status.startswith(m) for m in _MARKERS)]


def test_every_r_row_status_is_a_legal_marker_whole_file():
    """🔴 R24: 기존 가드는 원장 R행 중 **현재 창만** 관측 — 역사 창 첫 셀 drift 행이
    조용히 버려지는 클래스(R10)의 **전장 legality 백스톱**.

    파일 전체를 `_TABLE_ROW_RE` 로 전수 스캔해 모든 상태 셀이 범례 마커
    (🔴/🟡/⏸️/✅) 중 하나로 **시작**함을 강제한다. 행 수 하한(≥30)은 파서가
    고장 나 0행을 읽고도 초록이 되는 공허화를 막는다 — 실측 35행
    (현재 창 18 + 역사 창 17, 2026-08-02).
    Whole-file scan: every status cell must start with a legal marker, and the
    row-count floor (>=30) keeps a broken parser from passing vacuously on 0 rows.
    """
    rows = whole_file_status_rows(_text())
    assert len(rows) >= 30, (
        f"전장 스캔이 {len(rows)}행만 읽었다(실측 35행) — 파서 공허화 또는 표 구조 변경"
    )
    offenders = illegal_status_rows(rows)
    assert not offenders, (
        f"상태 셀이 범례 마커로 시작하지 않는 행: {offenders}\n"
        "→ 역사 창 포함 **파일 전체**의 R행 상태는 🔴/🟡/⏸️/✅ 로 시작해야 한다."
    )


def test_whole_file_scan_flags_a_malformed_status():
    """합성 비마커 상태(`진행중?`)를 같은 검사가 실제로 잡는가 — 통과만 하는 가드 차단.
    Self-verification: the same scan must flag a synthetic non-marker status cell."""
    synthetic = (
        "| **R99** | 진행중? | x |\n"
        "| **R100** | 🟡 착수 가능 | y |\n"
    )
    rows = whole_file_status_rows(synthetic)
    assert rows, "합성 표를 파서가 못 읽었다 — 자가 검증의 전제 붕괴"
    assert illegal_status_rows(rows) == [("R99", "진행중?")], (
        "비마커 상태 행을 탐지하지 못했다 — 전장 legality 검사가 공허하다"
    )
