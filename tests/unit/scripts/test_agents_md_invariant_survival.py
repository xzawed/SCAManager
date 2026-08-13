"""AGENTS.md **가드 저술 규율의 어휘 생존** 가드.

## 왜 필요한가 (2026-08-13 — backlog R83 사용자 결정)

`AGENTS.md` 는 가드/관측자 저술 규율의 SSOT 다. 그런데 이 리포는 **문서를 줄이면서
규칙을 삼킨 전례**가 있다 — `#1296` 이 CLAUDE.md 를 424→196줄로 줄이며 행동 규칙 8건을
잃었고, 기존 가드 1096건은 **축소 전후 동일하게 전건 통과**했다. 그것들이 본 것은
헤딩 지문뿐이고 본문 내용은 아무도 안 봤기 때문이다(observer-lie).

`tests/unit/scripts/test_claude_md_behavior_rules.py` 가 CLAUDE.md 에 대해 그 사각을
닫았다. 이 파일은 **AGENTS.md 에 대해 같은 것**을 한다.

## 무엇을 고정하고 무엇을 고정하지 않는가

- **고정**: 실제 사고에서 나온 판별 어휘. 문장이 바뀌어도 이 어휘가 사라지면 규칙이 사라진 것이다.
- **고정하지 않음**: 표현·순서·분량.

🔴 **어휘를 피검사 파일에서 유도하지 않는다** — 리터럴로 못박는다. AGENTS.md 에서 읽어
오면 그 줄을 지우는 것이 곧 가드를 지우는 것이 된다(자기참조 공허화).

🔴 **이 가드가 하지 못하는 것 (정직 기준)**: 어휘가 살아 있다는 것은 **규칙이 문서에
남아 있다**는 증거이지 **지켜진다**는 증거가 아니다. 불변식 2-b 의 *"클래스 내 다른
인스턴스인가"* 는 정적으로 판정 불가라 기계 집행을 주장하지 않는다 — 방어선은
write-time 규율과 review-time claim-review 다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_AGENTS_MD = Path(__file__).resolve().parents[3] / "AGENTS.md"

# (규칙 이름, 반드시 있어야 하는 어휘, 사라지면 무엇을 잃는가)
# 🔴 리터럴 고정 — 피검사 파일에서 유도 금지.
_RULES = [
    ("불변식 1 — fail-closed", "fail-closed",
     "산문·echo 로 통과하는 가드를 금지하는 축"),
    ("불변식 2 — 실경로 뮤테이션", "실경로 뮤테이션",
     "합성 픽스처로 HOLDS 를 주장하는 것을 막는 축"),
    ("불변식 2 — 뮤테이션 적용 확인", "mutated != orig",
     "치환이 조용히 미적용인데 'N passed' 를 검증으로 오독하는 사고"),
    ("불변식 3 — 배선", "정의 ≠ 배선",
     "순수 함수는 옳은데 진입점이 도달하지 않는 dead code 사고"),
    # ── 2026-08-13 사용자 결정 (A+B 혼합) ──
    ("불변식 2-b — A 반례 일반화", "클래스를 명명",
     "받은 반례만 막고 클래스를 열어 둔 채 봉인을 선언하는 사고(R81)"),
    ("불변식 2-b — A 자가 인스턴스", "다른 인스턴스를 스스로 만들어",
     "외부가 준 반례 하나로 검증을 끝내는 사고"),
    ("불변식 2-b — B 보고 어휘", "이 뮤테이션을 막았다",
     "뮤테이션 red 를 fail-open 종결로 과대보고하는 사고"),
    ("불변식 2-b — B 승급 조건", "외부 적대 검증 1회를 더",
     "봉인 선언에 2차 검증을 요구하는 조건"),
    ("불변식 2-b — 집행 한계 정직 표기", "기계 집행을 주장하지 않는다",
     "못 재는 자리에 가드를 둔 것처럼 보이게 하는 거짓 집행자"),
]


@pytest.mark.parametrize("name,token,loses", _RULES, ids=[r[0] for r in _RULES])
def test_rule_vocabulary_survives(name: str, token: str, loses: str) -> None:
    body = _AGENTS_MD.read_text(encoding="utf-8")

    assert token in body, (
        f"{name} 의 판별 어휘 {token!r} 가 AGENTS.md 에서 사라졌다 — 잃는 것: {loses}"
    )


def test_the_three_invariant_name_is_still_the_umbrella() -> None:
    """🔴 총칭은 `3-불변식` 이다 — 리포 30여 곳이 그 이름을 참조한다.

    2-b 를 `불변식 4` 로 승격하면 그 참조가 전부 낡는다. 이 문서가 이미
    *"적용 술어가 다르면 번호를 붙이지 않는다"* 는 선례를 세웠으므로(§측정 규율),
    하위 축은 하위 축으로 둔다.
    """
    body = _AGENTS_MD.read_text(encoding="utf-8")

    assert "3-불변식" in body, "총칭이 사라졌다 — 리포 전역 참조가 낡는다"

    # 🔴 **헤딩만 본다** — 본문 산문은 `불변식 4` 를 *인용*할 수 있고(실제로 §2-b 의 설명이
    #    "왜 `불변식 4` 가 아닌가" 로 그 이름을 쓴다), 전문 검색이면 그 인용이 red 를 낸다.
    #    메모리 `feedback-prose-guard-both-ways` 가 규정한 클래스 — *"인용 면제 필수
    #    (정정 기록이 막힌다)"*. 실제로 이 가드의 초판이 자기 설명문에 걸렸다.
    #    Headings only: prose legitimately *quotes* the rejected name.
    headings = [ln for ln in body.splitlines() if ln.lstrip().startswith("#")]

    assert not [h for h in headings if "불변식 4" in h], (
        f"하위 축이 `불변식 4` 헤딩으로 승격됐다 — 리포 30여 곳의 `3-불변식` 참조가 낡는다. "
        f"승격하려면 그 참조들을 같은 PR 에서 함께 고칠 것. 발견: "
        f"{[h for h in headings if '불변식 4' in h]}"
    )


def test_the_decision_is_attributed_to_its_source() -> None:
    """🔴 이 규율은 **사용자 결정**이다 — 출처가 지워지면 다음 세션이 임의 규칙으로 읽는다.

    정책 17 원칙 2(default rule 은 본문 보존, detail 은 external)와 같은 이유다.
    """
    body = _AGENTS_MD.read_text(encoding="utf-8")

    assert "2026-08-13 사용자 결정" in body, "결정 출처가 사라졌다"
    assert "R83" in body, "backlog 원장 귀속이 사라졌다 — 결정 이력을 추적할 수 없다"
