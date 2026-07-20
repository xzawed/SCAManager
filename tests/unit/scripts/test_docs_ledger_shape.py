"""회고 색인 · STATE 헤더의 **구조 불변식** — 산문이 아니라 대응 관계만 본다.

## 사고 3종 (2026-07-19 회고 클러스터 A)

1. **색인이 최신 산출물을 모른다.** `docs/_archive/reports/` 에 2026-07-19 회고 보고서가
   **2건** 놓였는데 `INDEX.md` 의 최신 행은 2026-07-18 이었다. 색인만 읽는 다음 세션은
   그 두 건이 **존재하지 않는 것과 같다** — 특히 2차 회고는 "회고 범위에 세션 자신의
   산출물 포함"(정책 8 진화 5) 의 근거였다.

2. **STATE 의 '최신' 블록이 체인으로 누적됐다.** 파일 자신의 갱신 규칙 (2) 가
   *"직전 작업 서사는 cycle-history 로 이관, 헤더에 체인 누적 금지"* 라고 적고 있는데
   세션3·세션4 블록이 **동시에** 헤더에 있었다. SSOT 가 자기 규칙을 어긴 상태.

3. **같은 섹션의 제목과 본문이 서로 다른 수를 말했다.** `cycle-history.md` 의 세션3 섹션은
   제목이 `13 PR`, 본문이 `총 9 PR #1102~#1110` 이었다(본문에 #1112~#1114 서술이 있는데도).

## 🔴 왜 대응 관계만 보는가

세 사고 모두 "글이 틀렸다" 가 아니라 **"두 곳의 수/목록이 어긋났다"** 이다. 전자는 정적
검사로 판정 불가고 그런 린터는 observer-lie 를 하나 더 만든다. 후자는 **산술**이라
기계가 판정할 수 있고, 사람이 한쪽만 고치는 순간 즉시 깨진다.
Only correspondences are checked — prose truth is undecidable, and a linter that pretends
otherwise is itself an observer-lie.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_REPORTS = _ROOT / "docs" / "_archive" / "reports"
_INDEX = _REPORTS / "INDEX.md"
_STATE = _ROOT / "docs" / "STATE.md"
_CYCLE = _ROOT / "docs" / "cycle-history.md"

# 색인 행의 링크 대상: `| 2026-07-19 | [retrospective](2026-07-19-retrospective.md) | …`
_LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")


def _inside_reports(link: str):
    """링크를 INDEX.md 기준으로 해석해 **reports/ 안쪽이면** 상대 경로를 돌려준다.

    🔴 파일명(basename)만 비교하면 두 방향으로 틀린다:
      · `../../CLAUDE.md` 같은 정당한 교차 링크가 '없는 보고서' 로 오신고된다(실측 3건)
      · `pending/x.md` 와 `x.md` 가 같은 것으로 뭉개진다(하위 디렉토리 탈출로)
    경로를 해석하고 **디렉토리 포함 여부**로 판정하면 둘 다 사라진다.
    """
    try:
        resolved = (_INDEX.parent / link).resolve()
        return resolved.relative_to(_REPORTS.resolve()).as_posix()
    except (ValueError, OSError):
        return None  # reports/ 바깥 — 교차 링크이므로 대상 아님


def indexed_filenames() -> set:
    """INDEX.md 가 링크하는 **reports/ 내부** 보고서의 상대 경로 집합."""
    links = _LINK_RE.findall(_INDEX.read_text(encoding="utf-8"))
    return {rel for rel in (_inside_reports(m) for m in links) if rel}


def report_filenames() -> set:
    """디스크에 실제로 있는 보고서 파일명 집합 — **재귀 · 이름 무관**.

    🔴 이전 판은 `glob("*retrospective*.md")` 였고 Grok 적대 검토가 두 탈출로를 실증했다:
      (a) **비재귀** — `reports/pending/2026-07-21-retrospective.md` 는 집합에 안 들어온다
      (b) **이름 의존** — `2026-07-21-5plus1.md` 처럼 부분문자열이 없으면 빠진다
    실측으로도 디스크 53건 중 **31건만** 보고 있었다(감사·품질 리포트 22건이 사각).

    "무엇이 색인 대상인가" 를 파일명으로 추측하는 순간 그 추측이 사각이 된다. 대상은
    **`reports/` 아래 모든 `.md`**(색인 자신 제외)로 정의한다 — 추측이 없으면 사각도 없다.
    Guessing which files "count" is what created the blind spot; the rule is now: all of them.
    """
    return {
        p.relative_to(_REPORTS).as_posix()
        for p in _REPORTS.rglob("*.md")
        if p.name != "INDEX.md"
    }


# ── 1. 색인 전단사 / index bijection ─────────────────────────────────────


def test_every_retrospective_report_is_indexed():
    """🔴 디스크의 회고 보고서는 **전부** 색인에 있어야 한다.

    색인만 읽는 세션에게 미등재 보고서는 존재하지 않는 것과 같다.
    실측: 2026-07-19 회고 2건이 디스크에만 있고 색인 최신은 2026-07-18 이었다.
    """
    missing = sorted(report_filenames() - indexed_filenames())
    assert not missing, (
        f"색인에 없는 회고 보고서: {missing}\n"
        "→ `docs/_archive/reports/INDEX.md` 에 행을 추가할 것 "
        "(보고서를 쓴 **같은 커밋**에서)."
    )


def test_index_does_not_link_missing_reports():
    """역방향 — 색인이 없는 파일을 가리키면 죽은 링크다.

    한 방향만 잠그면 rename 이 조용히 통과한다("정의⇒호출" 과 "호출⇒정의" 가 다른 것과 동형).
    """
    # 🔴 이전 판은 이름에 "retrospective" 가 든 링크만 검사했다 — 정방향과 같은 추측이라
    #   감사·품질 리포트의 죽은 링크를 통째로 놓쳤다. 이제 보고서 디렉토리 링크 전부를 본다.
    dangling = sorted(indexed_filenames() - report_filenames())
    assert not dangling, f"색인이 존재하지 않는 보고서를 가리킨다: {dangling}"


# ── 2. STATE '최신' 블록 단일성 / at most one live block ─────────────────


def test_state_has_exactly_one_latest_block():
    """🔴 STATE 헤더의 `**최신 (…)**` 블록은 **정확히 1개**다.

    파일 자신의 갱신 규칙 (2): 직전 서사는 cycle-history 로 이관, 헤더 체인 누적 금지.
    실측 위반: 세션3·세션4 블록이 동시에 헤더에 있었다.
    """
    blocks = re.findall(r"^\*\*최신 \(", _STATE.read_text(encoding="utf-8"), re.M)
    assert len(blocks) == 1, (
        f"STATE 의 '최신' 블록이 {len(blocks)}개다(1이어야 함).\n"
        "→ 직전 블록은 `docs/cycle-history.md` 최신순 맨 앞으로 이관할 것."
    )


def _state_current_region(text: str) -> str:
    """'현재 값' 영역만 — 지표 표(append-only 추적 이력) 앞까지.

    🔴 표 안의 `단위 **5206**` 류는 **과거 시점 기록**이라 현재 값과 다른 게 정상이다.
    파일 전체를 비교하면 이 테스트는 정상적인 이력을 위반으로 신고한다(작성 중 실측 —
    9개 값이 나왔고 8개가 과거 기록이었다). 관측 범위를 틀리면 가드가 거짓말을 한다.
    """
    head, _, _ = text.partition("\n| 지표 |")
    return head


def test_state_current_counts_agree_across_the_header():
    """🔴 헤더 영역(현재 값)의 테스트 수는 한 값이어야 한다.

    '최신' 블록과 '종합 수치' 줄이 서로 다른 수를 말하면 어느 쪽을 믿을지 알 수 없다
    (실측: 헤더를 5731 로 갱신한 뒤 추적 셀의 '현재' 값만 5684 로 남아 있었다).
    과거 이력 셀은 append-only 라 비교 대상이 아니다 — `_state_current_region` 참조.
    """
    region = _state_current_region(_STATE.read_text(encoding="utf-8"))
    totals = re.findall(r"전체 \*\*(\d+)\*\* 수집", region)
    units = re.findall(r"단위 \*\*(\d+)\*\*", region)
    assert totals, "'전체 N 수집' 표현을 헤더에서 못 찾았다 — 형식이 바뀌었는지 확인할 것"
    assert len(set(totals)) == 1, f"헤더의 '전체 수집' 수가 어긋난다: {sorted(set(totals))}"
    assert len(set(units)) == 1, f"헤더의 '단위' 수가 어긋난다: {sorted(set(units))}"


def test_current_region_excludes_the_append_only_ledger():
    """🔴 관측 범위 자체를 고정한다 — 표까지 삼키면 이력이 위반으로 신고된다.

    이 단언이 없으면 누가 `_state_current_region` 을 '전체 반환' 으로 되돌려도 조용하다.
    """
    text = _STATE.read_text(encoding="utf-8")
    region = _state_current_region(text)
    assert len(region) < len(text), "추적 표를 잘라내지 못했다 — 표 머리글 형식 확인"
    assert "추적 이력" in text, "추적 이력 표가 사라졌다 — 이 가드의 전제 붕괴"
    assert "추적 이력" not in region, "추적 이력이 현재-값 영역에 포함됐다"


# ── 3. 섹션 제목 ↔ 본문 PR 수 / heading vs body ──────────────────────────


def _pr_range_count(text: str):
    """`#1102~#1114` → 13. 범위 표기가 없으면 None."""
    m = re.search(r"#(\d{3,5})\s*~\s*#(\d{3,5})", text)
    return abs(int(m.group(2)) - int(m.group(1))) + 1 if m else None


def test_cycle_history_headline_pr_count_matches_its_range():
    """🔴 `총 N PR #A~#B` 의 N 이 범위 폭과 일치해야 한다.

    실측: 제목 `13 PR` · 본문 `총 9 PR #1102~#1110` 이 같은 섹션에 공존했고,
    본문에는 #1112~#1114 서술이 실제로 들어 있었다(본문이 자기 서술과도 불일치).
    """
    text = _CYCLE.read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r"총 (\d+) PR (#\d{3,5}\s*~\s*#\d{3,5})", text):
        claimed, span = int(m.group(1)), _pr_range_count(m.group(2))
        if span is not None and claimed != span:
            bad.append(f"'총 {claimed} PR {m.group(2)}' → 범위 폭 {span}")
    assert not bad, "선언 PR 수와 PR 범위 폭이 어긋난다:\n  " + "\n  ".join(bad)


# ── 탐지력 자가 검증 / self-verification ─────────────────────────────────


def test_pr_range_arithmetic_is_inclusive():
    """경계 산술 고정 — off-by-one 이면 위 단언이 조용히 무의미해진다."""
    assert _pr_range_count("#1102~#1114") == 13
    assert _pr_range_count("#1102 ~ #1102") == 1
    assert _pr_range_count("범위 표기 없음") is None


def test_index_link_extraction_finds_real_rows():
    """대조군 — 링크 추출이 0건이면 전단사 단언이 공허하게 통과한다."""
    assert len(indexed_filenames()) > 10, "색인 링크 추출이 사실상 비었다 — 정규식 확인 필요"
    assert len(report_filenames()) > 5, "회고 보고서 탐색이 사실상 비었다"
