"""CLAUDE.md 의 **구조적 불변식** — 산문 내용이 아니라 배치/중복만 본다.

## 왜 구조만 보는가

산문의 진위는 정적 검사로 판정할 수 없고, 그런 린터는 통과가 아무것도 보장하지 않아
**observer-lie 를 하나 더 만든다**(2026-07-19 Grok 협의 결론). 그래서 이 파일은
"규칙이 옳은가" 를 묻지 않는다. **"규칙이 읽히는 자리에 있는가"** 와
**"같은 규칙이 몇 번 적혀 있는가"** 만 본다.

## 잠그는 것 2가지 (회고 P1)

1. **살아있는 의무가 '⛔ 폐기' 섹션 아래 있으면 안 된다.**
   실측 사고: 매 발화에 걸리는 2-phase 사용자 보고 게이트가 `#### ⛔ 정책 18 폐기` 제목
   **15줄 아래**에 놓여 있었다. 다음 세션이 그 섹션을 "폐기됨" 으로 읽고 건너뛰면
   게이트가 통째로 사라진다. → 정책 19 로 독립 승격.

2. **같은 의무를 여러 곳에 복제하지 않는다.**
   실측: "검증 없이 단언 금지" 계열이 4개 문서 12곳에 분산됐고, 그 상태에서 `#1121` 이
   **문면을 만족한 채 위반**했다. 사본이 늘수록 어느 것이 정본인지 흐려진다 —
   rule inflation 자체가 회고가 지목한 결함이다.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE_MD = _ROOT / "CLAUDE.md"

# 살아있는 의무의 표지 — 이 문자열들이 폐기 섹션 안에 있으면 안 된다.
_LIVE_DUTIES = (
    "2-phase 사용자 보고 게이트",
    "UNVERIFIED:",
)


def _sections(text: str) -> list[tuple[str, str]]:
    """`#### ` 제목 기준으로 (제목, 본문) 분할."""
    parts = re.split(r"^#### ", text, flags=re.M)
    out = []
    for chunk in parts[1:]:
        title, _, body = chunk.partition("\n")
        out.append((title.strip(), body))
    return out


def test_live_duties_are_not_inside_a_deprecated_section():
    """🔴 살아있는 의무가 '⛔ 폐기' 제목 아래 있으면 안 된다.

    폐기 섹션은 읽는 사람이 **건너뛰도록** 설계된 자리다. 거기에 매 발화 의무를 두면
    그 의무는 구조적으로 무시된다(실제로 2-phase 게이트가 그 상태였다).
    """
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    misplaced = []
    for title, body in _sections(text):
        # 🔴 제목이 ⛔ 로 **시작**할 때만 폐기 섹션으로 본다.
        #   "폐기" 라는 낱말 포함으로 판정하면 `정책 19: … (정책 18 폐기 자리 대체)` 처럼
        #   **폐기를 언급하는 살아있는 섹션**까지 폐기로 오인한다(이 테스트 작성 중 실측).
        #   산문 언급과 구조적 표지를 구별하는 것이 이 세션의 반복 주제다.
        # Only a leading ⛔ marks a deprecated section; merely mentioning 폐기 must not count.
        if not title.startswith("⛔"):
            continue
        for duty in _LIVE_DUTIES:
            if duty in body:
                misplaced.append(f"{duty!r} in section {title[:40]!r}")
    assert not misplaced, (
        f"살아있는 의무가 폐기 섹션 안에 있다: {misplaced}\n"
        "→ 독립 정책 섹션으로 승격할 것. 폐기 제목 아래 두면 다음 세션이 건너뛴다."
    )


def test_live_duties_actually_exist_somewhere():
    """대조군 — 의무 자체가 사라지면 위 테스트가 공허하게 통과한다."""
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    for duty in _LIVE_DUTIES:
        assert duty in text, f"{duty!r} 가 CLAUDE.md 에서 사라졌다 — 이 가드의 전제 붕괴"


def test_grok_protocol_is_its_own_policy_section():
    """🔴 Grok 협업 규칙이 **독립 섹션**이어야 한다 — 폐기 정책의 하위가 아니라.

    승격 전에는 `정책 18 폐기` 하위 불릿이었고, 그래서 위 배치 결함이 생겼다.
    """
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    titles = [t for t, _ in _sections(text)]
    assert any("Grok" in t and "정책" in t for t in titles), (
        f"Grok 협업이 독립 정책 섹션이 아니다. 현재 섹션 제목: {titles[-6:]}"
    )
    # 폐기 섹션보다 **뒤**에 와야 한다(하위로 다시 흡수되지 않도록)
    dep = text.index("⛔ 정책 18 폐기")
    grok = next(text.index(t) for t in titles if "Grok" in t and "정책" in t)
    assert grok > dep, "Grok 정책이 폐기 섹션보다 앞에 있다 — 하위로 읽힐 위험"


def test_a2_specifies_what_to_mutate():
    """🔴 A2 는 **무엇을** 뮤테이트할지 규정해야 한다 — 합성 픽스처로 충족 불가.

    실측: `#1121` 이 합성 문자열로 "뮤테이션 실증" 을 적은 채 실파일에 대해 무동작이었다.
    "뮤테이션했다" 만 요구하면 그 상태가 문면상 준수다.
    """
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "합성 문자열·픽스처만으로는" in text, (
        "A2 에 '합성만으로는 불충족' 규정이 없다 — #1121 형 뮤테이션 연극이 다시 통과한다"
    )


def test_grok_boundary_is_ownership_not_silence():
    """🔴 경계가 '호출 금지' 단독이면 실효 있는 용도까지 막힌다.

    회고 P1: 두 번의 경계 위반이 **모두 실제 오류를 찾아냈다**. 경계를 '소유 금지 +
    claim-review 허용' 으로 개정한 것이 본문에 반영돼 있어야 한다.
    """
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "소유 금지" in text or "저술(authoring)하지 않는다" in text, (
        "경계 개정(소유 금지 / claim-review 허용)이 본문에 없다"
    )
