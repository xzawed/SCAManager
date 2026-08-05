"""CLAUDE.md 본문의 **행동 규칙 생존** 가드 — 슬림화가 규칙을 삼키는 것을 막는다.

## 왜 필요한가 (2026-08-06, Grok claim-review `8eccb444` 적발)

CLAUDE.md 를 424 → 196줄로 줄이면서 **행동 규칙 8건이 어디에도 남지 않았다**.
그런데 기존 가드 1096건은 **축소 전후 동일하게 전건 통과**했다 — 그것들이 보는 것은
`#### 정책 7` · `#### 정책 19` 같은 **헤딩 지문 2개**와 rules 매트릭스뿐이고,
정책 1~6·8~17 의 **본문 내용은 아무도 보지 않았기 때문**이다.

🔴 그래서 "가드가 전부 통과했다" 를 **보존의 근거로 쓴 것이 잘못**이었다. 그것은
앵커가 살아 있다는 증거이지 규칙이 살아 있다는 증거가 아니다(observer-lie).

이 파일이 그 사각을 닫는다: **각 규칙의 고유 어휘가 CLAUDE.md 본문에 실재하는지** 본다.

## 무엇을 고정하고 무엇을 고정하지 않는가

- **고정**: 실제 사고에서 나온 조건·예외·금지의 **판별 어휘**. 문장이 바뀌어도 이 어휘가
  사라지면 규칙이 사라진 것이다.
- **고정하지 않음**: 표현·순서·detail. detail 은 `.claude/policies/` 가 정본이고
  본문은 default rule 만 담는 것이 정책 17 원칙 2 다.

🔴 **어휘를 피검사 파일에서 유도하지 않는다** — 리터럴로 못박는다. CLAUDE.md 에서
읽어 오면 그 줄을 지우는 것이 곧 가드를 지우는 것이 된다(자기참조 공허화).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_CLAUDE_MD = Path(__file__).resolve().parents[3] / "CLAUDE.md"

# (규칙 이름, 본문에 반드시 있어야 하는 어휘, 사라지면 무엇을 잃는가)
# 🔴 리터럴 고정 — 피검사 파일에서 유도 금지.
_BEHAVIOR_RULES = [
    ("정책 1 — 일괄 결정 자가 보고", "검토 깊이 자가 보고", "빠른 일괄 결정 시 검토 깊이 보고 의무"),
    ("정책 1 — 빠른 진행 신호 임계", "≥10회", "다중 PR 빠른 진행이 일괄 결정과 동등 위험이라는 판정 기준"),
    ("정책 5 — Phase 종료 4정책 교차검토", "cross-reference 자가 검토", "한 정책만 적용하고 나머지 3 위반하는 사고"),
    ("정책 5 — NEW-P0-N 예외", "NEW-P0-N", "운영 사고 차단 영역에 보류 default 를 적용하는 사고"),
    ("정책 7 — main 직접 push 금지", "예외 0", "'사소하니 main 에 직접' 이라는 예외 자가부여"),
    ("정책 8 — 회고 카덴스 임계", "≥15 PR", "회고 진입 시점의 기계 판정 기준"),
    ("정책 8 — 회고 범위에 세션 산출물", "본 세션 산출물", "가장 검증 덜 된 코드가 회고를 피하는 사고"),
    ("정책 8 — 이월 승인 기록 의무", "retro-cadence-deferrals", "이월 결정의 관측 가능성"),
    ("정책 9 — 완화 미적용 3영역", "명시 회신 의무", "운영/destructive/architecture 결정을 자율 판단으로 넘기는 사고"),
    ("정책 10 — 본문 전달 방식", "--body-file", "PR 본문이 리터럴 `@-` 로 소실된 사고(8건)"),
    ("정책 11 — 시각 검증 비대칭", "8조합", "정적 통과를 시각 검증으로 오인"),
    ("정책 12 — MCP 쓰기 사전 승인", "사전 승인 의무", "운영 데이터 변경·secret 노출"),
    ("정책 13 — smoke 기대값 SSOT", "operational-smoke-checks.md", "리터럴 상태값 사본 drift(3 사본 사고)"),
    ("정책 14 — lint ≠ Security", "CodeQL", "lint 통과를 Security 0 alert 로 오인"),
    ("정책 15 — 3-tier 위임", "3-tier", "High tier 결정을 사전 확인 없이 진행"),
    ("정책 16 — 공유 로직 전수 grep", "grep -rn", "한 곳만 고치고 나머지 호출처를 놓치는 사고"),
    ("정책 16 — AI 품질 명시 제외", "build_review_prompt", "리뷰 품질에 닿는 축소를 자율 진행"),
    ("정책 17 — 외부 규격보다 안정성", "안정성과 충돌하면 거부", "권장 규격 숫자를 맞추려 행동 규칙을 자르는 사고(실제 발생)"),
    ("정책 17 — 본문 보존 영역", "본문 보존 default", "매 작업 의무 영역을 external 로 밀어내는 사고"),
    ("정책 19 — 2-phase 보고 게이트", "UNVERIFIED:", "미검증 배포/봉인 주장을 사용자에게 보고"),
    ("정책 19 — A2 뮤테이션 의무", "실경로 뮤테이션", "합성 픽스처로 seal 을 HOLDS 선언"),
    ("6-step — push 전 전체 테스트", "pytest tests/unit", "영역 서브셋만 돌려 CI 가 깨진 사고"),
    ("6-step — 로컬 게이트", "pre_push_gate", "make 없는 머신에서 게이트 미실행"),
    ("에이전트 격리", "isolation: worktree", "백그라운드 에이전트가 메인 작업트리를 오염"),
    ("측정 규율 진입점", "측정 규율", "1회용 측정 도구의 숫자를 검증 없이 발행"),
    ("정책 17 — 단계마다 5+1 회의", "5+1 회의", "문서 재구조화를 검증 없이 한 번에 밀어붙이는 사고(실제 발생)"),
    ("정책 17 — 누적 결함 정기 검증", "≥5 사이클", "≥18 PR 영역의 시간차 결함이 영영 미검증"),
    ("정책 6 — 실측 인용", "grep -n", "추정 line 번호가 자연 drift 로 거짓이 되는 사고"),
    ("메모리 grep 의무", "메모리 grep 의무", "같은 함정을 두 번 밟는다 — 교차 세션 학습 반송자 소실"),
    ("6-step ⑤ 배치 이월", "trailing sync", "병렬 PR 이 STATE 동일 라인을 연속 write 해 충돌 자초"),
]


# 🔴 이 가드가 **탐지하지 못하는 것** (정직 기준 — 2026-08-06 회고 실측)
#
# **규칙의 역전**: 어휘를 남긴 채 의미를 뒤집으면 통과한다. 실측 뮤테이션 —
# `🔴 **예외 0.**` 뒤에 "취소됨 — 사소한 변경은 main 직접 push 해도 된다" 를 덧붙여도 **GREEN**.
# 부분문자열 가드는 **삭제 탐지기**이지 의미 검증기가 아니다([[feedback-prose-guard-both-ways]]
# 가 기록한 "산문 가드는 양방향으로 틀린다" 의 이 파일 판).
#
# 이것을 정적으로 닫으려면 부정어 탐색이 필요한데, 그러면 **정정 기록**("이전엔 X 였다")까지
# 막혀 오탐 > 진탐이 된다(정책 17 = 가드 자살 회피). 남은 방어선은 review-time claim-review 다.
# 즉 이 가드가 보장하는 것은 **"규칙이 조용히 사라지지 않는다"** 이지 "규칙이 옳다" 가 아니다.


@pytest.mark.parametrize(("name", "needle", "loses"), _BEHAVIOR_RULES)
def test_behavior_rule_survives_in_claude_md(name: str, needle: str, loses: str):
    """각 행동 규칙의 판별 어휘가 CLAUDE.md 본문에 살아 있어야 한다."""
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert needle in text, (
        f"[{name}] 어휘 {needle!r} 가 CLAUDE.md 에서 사라졌다.\n"
        f"→ 잃는 것: {loses}\n"
        "→ 슬림화로 지웠다면 **본문에 되살릴 것**. detail 은 external 로 보내되 "
        "default rule 은 본문 보존이 정책 17 원칙 2 다."
    )


def test_the_rule_list_is_not_vacuous():
    """🔴 대조군 — 목록이 비거나 어휘가 지나치게 흔하면 이 가드는 아무것도 지키지 않는다."""
    assert len(_BEHAVIOR_RULES) >= 20, "규칙 목록이 축소됐다 — 커버리지 붕괴"
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    for name, needle, _ in _BEHAVIOR_RULES:
        assert len(needle) >= 3, f"[{name}] 어휘가 너무 짧아 우연히 매칭된다: {needle!r}"
        assert text.count(needle) <= 6, (
            f"[{name}] 어휘 {needle!r} 가 {text.count(needle)}회 출현 — 너무 흔해 판별력이 없다"
        )


def test_claude_md_stays_near_the_anthropic_line_target():
    """Anthropic 공식 권장(200줄 미만)에 대한 **관측**. 🔴 차단이 아니라 계량이다.

    정책 17 원칙 1: *"Anthropic 200줄 등 외부 권장 규격은 가이드라인 — 안정성과 충돌하면
    거부한다."* 그래서 초과를 red 로 만들지 않는다. 다만 **조용히 다시 424줄이 되는 것**은
    막아야 하므로, 크게 벗어나면 실패시켜 사람이 의식적으로 판단하게 한다.

    Observation, not a hard gate: the repo's own policy 17 outranks the external guideline.
    """
    n = len(_CLAUDE_MD.read_text(encoding="utf-8").splitlines())
    assert n <= 260, (
        f"CLAUDE.md 가 {n}줄이다 (Anthropic 권장 200 미만, 이 가드의 상한 260).\n"
        "→ 늘어난 것이 **행동 규칙**이면 정책 17 원칙 1 에 따라 정당하다. 그 경우 이 상한을 "
        "올리되 **왜 올리는지 커밋 본문에 적을 것**. detail 이 다시 흘러든 것이면 external 로 뺄 것."
    )
