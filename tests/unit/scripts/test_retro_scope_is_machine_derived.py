"""회고 범위는 **기계에서 파생**된다 — 손 조립 금지 (회고 N-P0-5).

## 사고 (2026-08-08 — 이 회고 자신이 밟았다)

정책 8(`CLAUDE.md`)은 회고 범위를 *"기계 산출 `scripts/retro_scope.py`"* 로 못박는다.
그 도구는 존재하고 `--json` 까지 제공하며, 자기 출력에 이렇게 적어 둔다:

> 🔴 회고 착수 **직전에** 다시 실행할 것 — 그 사이 머지분이 빠지는 것이 P0 의 기전이었다.

그런데 진입점인 `.claude/skills/retrospective.md` 의 실행 절차 1단계는
*"`git log --oneline <baseline>..HEAD` + 머지 PR 목록 → `context` 문자열"* 이라 적혀 있었다.
**손 조립을 지시한 것이다.** 그래서 2026-08-08 회고는 세션 시작 훅
세션 초에 인쇄한 **17건**을 브리프에 굳혀 5 관점에 배포했고,
디스패치 시점의 실제 범위는 **18건**(`#1297`~`#1314`)이었다.

🔴 두 도구가 서로 어긋난 게 아니다 — **읽은 시점이 달랐다.** 그리고 그 시점 차를 없애라고
만들어 둔 도구를 진입점이 부르지 않았다. 회고가 자기 범위를 잘못 알고 돌았다.

## 🔴 워크플로가 직접 부를 수는 없다 (설계 제약)

`.claude/workflows/*.mjs` 는 **파일시스템·child_process 접근이 없다**(Workflow 런타임 제약 —
resume 결정성을 위해 `Date.now()` 마저 막혀 있다). 그러므로 *"워크플로가 `retro_scope.py` 를
호출하게 하라"* 는 처방은 **실행 불가능**하다. 유일하게 가능한 배선 지점은 **스킬(진입점)** 이고,
그래서 이 가드는 스킬 문서가 그 명령을 **실행 가능한 형태로** 담고 있는지를 본다.

## 이 파일이 강제하는 것

1. 스킬이 `scripts/retro_scope.py` 를 **인터프리터로 실행**한다 (`surface_invokes` —
   경로 문자열 언급이 아니라 실행 형태. 산문 substring 판정은 이 리포에서 금지다).
2. 스킬이 손 조립(`git log … → context`)을 지시하지 **않는다**.
3. `retro_scope.py --json` 이 실제로 돌고, 스킬이 넘기라고 한 키를 담는다 (계약 대조).

Scope must come from the machine oracle at dispatch time, not from prose or a stale counter.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404 — 리포 자신의 스크립트만 실행한다
import sys
from pathlib import Path

from tests.unit.scripts._wiring_shape import surface_invokes

_ROOT = Path(__file__).resolve().parents[3]
_SKILL = _ROOT / ".claude" / "skills" / "retrospective.md"
_ORACLE = "scripts/retro_scope.py"


def _skill_text() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    assert text.strip(), "스킬 파일이 비었다 — 범위 붕괴(빈 텍스트 위의 ✅ 는 fail-open)"
    return text


# ── ① 진입점이 기계 오라클을 실행한다 ────────────────────────────────────


def test_skill_invokes_the_scope_oracle():
    """🔴 봉인 — 경로 **언급**이 아니라 **실행**을 요구한다.

    `surface_invokes` 는 `echo 'scripts/retro_scope.py'` 같은 형태를 배선으로 세지 않는다
    (guards.md: substring 배선 판정 11건이 fail-open 이었던 실측 이후 도입된 술어).
    """
    assert surface_invokes(_skill_text(), _ORACLE), (
        f"스킬이 {_ORACLE} 을 실행하지 않는다 — 회고 범위가 다시 손 조립된다.\n"
        "→ 실행 절차 1단계에 `py -3 scripts/retro_scope.py --json` 을 둘 것(정책 8)."
    )


def test_skill_no_longer_instructs_hand_assembly():
    """🔴 손 조립 지시가 남아 있으면 오라클이 있어도 우회된다.

    구 절차: "`git log --oneline <baseline>..HEAD` + 머지 PR 목록 → `context` 문자열".
    이 문장이 정확히 2026-08-08 의 17 vs 18 을 허용했다.
    """
    text = _skill_text()
    offending = [
        line.strip()
        for line in text.splitlines()
        if "git log" in line and "context" in line
    ]

    assert not offending, (
        f"스킬이 아직 범위 손 조립을 지시한다: {offending}\n"
        "→ 범위는 `retro_scope.py --json` 에서만 온다."
    )


# ── ② 오라클이 실제로 돌고 계약을 지킨다 ─────────────────────────────────


def _oracle_payload() -> dict:
    """스킬이 가리키는 명령을 **정말 실행**해 JSON 을 얻는다 (mock 없음)."""
    proc = subprocess.run(  # nosec B603
        [sys.executable, str(_ROOT / "scripts" / "retro_scope.py"), "--json"],
        cwd=str(_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120, check=False,
    )
    # 🔴 exit 1 은 고장이 아니다 — 경계 커밋을 못 찾았을 때의 **fail-closed 응답**이고,
    #    그 경우에도 stdout 에는 사유를 담은 JSON 이 온다(아래 계약 테스트가 그것을 단언한다).
    #    exit 1 = deliberate refusal, still with parseable JSON on stdout.
    assert proc.returncode in (0, 1), (
        f"retro_scope.py --json 예상 밖 종료(exit {proc.returncode}): {proc.stderr[-400:]}"
    )
    assert proc.stdout.strip(), (
        f"stdout 이 비었다 — 스킬이 넘길 값이 없다(exit {proc.returncode}): {proc.stderr[-400:]}"
    )
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict), f"JSON 객체가 아니다: {type(payload).__name__}"
    assert payload, "빈 객체 — 스킬이 이 출력을 args 로 넘길 수 없다"
    return payload


def test_the_oracle_actually_runs_and_emits_the_documented_shape():
    """🔴 실경로 — 문서만 고치고 도구가 깨져 있으면 스킬은 실행 불가한 절차를 지시하게 된다."""
    _oracle_payload()


def test_the_oracle_either_reports_a_window_or_refuses_explicitly():
    """🔴 계약 — **범위를 주거나, 못 주는 이유를 준다.** 조용한 빈 답은 없다.

    🔴 이 테스트의 초판은 *"항상 PR 창이 있다"* 고 단언했고 **전체 스위트에서 깨졌다**
    (부분 실행에서는 통과 — 6-step ② 가 잡았다). 원인은 도구가 아니라 내 단언이었다:
    회고 보고서를 **막 작성했지만 아직 커밋 전**이면 경계 커밋이 없어
    `{"ok": false, "reason": …}` 를 돌려준다. 그건 고장이 아니라 **fail-closed 응답**이고,
    회고를 쓰는 중에는 정상 상태다.

    두 분기 **모두** 단언한다 — 어느 쪽도 무조건 통과가 아니다.
    """
    payload = _oracle_payload()

    if payload.get("ok") is False:
        reason = payload.get("reason", "")
        assert isinstance(reason, str) and reason.strip(), (
            f"거부인데 사유가 없다 — 조용한 실패다: {payload}"
        )
        return

    assert any("pr" in key.lower() for key in payload), (
        f"PR 창을 담은 키가 없다 — 회고 범위로 쓸 수 없다: {sorted(payload)}"
    )


# ── ③ 왜 워크플로가 아니라 스킬인가 (설계 근거 고정) ─────────────────────


def test_the_workflow_cannot_and_does_not_shell_out():
    """🔴 워크플로는 child_process 를 못 쓴다 — 그래서 배선 지점이 스킬이다.

    이 단언은 *"왜 워크플로에 안 넣었나"* 를 코드로 남긴다. 누군가 워크플로에
    `child_process` 를 넣으려 하면 런타임이 거부하므로, 그 시도가 여기서 먼저 보인다.
    """
    workflow = (_ROOT / ".claude" / "workflows" / "retrospective.mjs").read_text(encoding="utf-8")

    assert "child_process" not in workflow, (
        "워크플로가 child_process 를 쓴다 — Workflow 런타임은 이를 제공하지 않는다.\n"
        "→ 범위 산출은 스킬(진입점)에서 하고 `args` 로 주입할 것."
    )


# ── ④ 실행 중 머지는 진입 시점 신탁이 원리적으로 못 본다 (2026-08-14 P0-B) ──


def _workflow_src() -> str:
    return (_ROOT / ".claude" / "workflows" / "retrospective.mjs").read_text(encoding="utf-8")


def test_scope_is_remeasured_at_the_end_not_only_at_dispatch():
    """🔴 회고가 **도는 동안** 머지된 분을 산출물이 드러내야 한다.

    ## 왜 이 축이 따로 필요한가

    2026-08-14 회고 P0-B 의 실제 기전은 *"범위를 손으로 적었다"* 가 **아니었다**.
    오라클(`scripts/retro_scope.py`)은 디스패치 직전에 실행됐고 그 값이 맞았다 —
    그 뒤 회고가 3시간 도는 동안 세션이 `#1347` 을 새로 머지했다. **진입 시점의 어떤
    검사도 미래의 머지를 볼 수 없다.** 위 ①~③ 축(스킬이 오라클을 부르는가)은
    2026-08-08 의 다른 기전(손 조립)을 닫은 것이고, 이 축은 그것과 별개다.

    닫는 것이 아니라 **드러내는** 축이다 — 실행 중 늘어난 분을 반환값에 실어
    다음 회고의 하한으로 이월한다.

    Dispatch-time oracles cannot see merges that happen during the run; the workflow must
    re-measure at the end and surface the delta.
    """
    src = _workflow_src()

    assert "scope:closing" in src, (
        "종료 시 범위 재확인 에이전트가 없다 — 실행 중 머지분을 아무도 보지 않는다."
    )
    assert "scope_drift_during_run" in src, (
        "재확인 결과가 반환값에 노출되지 않는다 — 로그만으로는 다음 회고가 못 읽는다."
    )


def test_the_closing_check_actually_runs_the_oracle():
    """🔴 배선 단언 — 종료 검사가 **그 스크립트를 실제로 실행**하라고 지시하는가.

    `"scope:closing" in src` 만 보면 라벨만 남기고 프롬프트를 비워도 통과한다
    (A1 = 산문이 가드를 통과시킨다). 종료 에이전트 프롬프트가 오라클 실행 명령을
    담고 있는지 확인한다.
    """
    src = _workflow_src()
    closing = src[src.index("scope:closing") - 1200:src.index("scope:closing")]
    assert "retro_scope.py" in closing, (
        "종료 검사가 오라클을 부르지 않는다 — 라벨만 있고 실행이 없다."
    )
    assert "추정값을 만들지 마세요" in closing, (
        "추정 금지 지시가 없다 — 에이전트가 값을 지어내면 이 축은 거짓을 발행한다."
    )


def test_drift_is_computed_against_the_dispatch_time_scope():
    """대조군 — 종료값만 보고하면 '늘었는지' 를 판정할 수 없다.

    진입 시점 산출(`machineScope`)과 대조해야 delta 가 나온다. 종료값 단독 보고는
    *"지금 범위는 8건"* 이라고만 말하고 **그중 무엇이 회고 밖인지**는 말하지 않는다.
    """
    src = _workflow_src()
    assert "machineScope?.prs" in src or "machineScope.prs" in src, (
        "종료 검사가 진입 시점 범위와 대조하지 않는다 — delta 가 산출되지 않는다."
    )
