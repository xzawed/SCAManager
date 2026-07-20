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
