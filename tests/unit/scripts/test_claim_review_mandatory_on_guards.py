"""가드 표면 PR 은 claim-review 를 **자기 면제할 수 없다** (사용자 결정 2026-08-08).

## 왜 승격했나 — 이 세션이 낸 증거

2026-08-08 창은 *"반복되는 실수가 문서 규모의 문제인가"* 라는 질문에서 시작해, 지배 원인을
**"고친 당사자가 관측자를 같은 PR 에서 만들고, 그 관측자가 그 PR 이 고친 결함에만 맹목"**
으로 진단하고 게이트 4개(P1~P4)를 만들었다.

🔴 **그 게이트 4개 중 3개가 같은 형태로 결함이었다.** 면제 마커 관용구는 복제됐는데
그 관용구가 이미 치른 하드닝(HTML 주석 스트리핑 — backlog R20 결함 1)은 복제되지 않아,
세 게이트 전부 *"리뷰어 비가시 + 게이트 통과"* 를 허용했다.

그리고 그것을 찾은 것은 **11 에이전트 5+1 회고가 아니었다**:

| 검증자 | 물은 질문 | 결과 |
|---|---|---|
| 5+1 회고 (11 에이전트) | *"게이트가 작동하는가"* | 통과 확인 — **결함 미발견** |
| Grok claim-review `019fe026` | *"이 봉인을 어떻게 깨는가"* | **BROKEN** (merge commit 으로 우회) |

저자는 AGENTS.md 불변식 2(실경로 뮤테이션 red)를 **지켰는데도** 틀렸다 — 자기가 상상한
실패 모드만 뮤테이션했기 때문이다. 뮤테이션 red 는 필요조건이지 충분조건이 아니다.

## 계약

| 상황 | `claim-review-not-required:` |
|---|---|
| **가드 표면** 변경 (관측자를 저술) | 🔴 **무효 — exit 1** |
| seal 주장 + 코드 표면 변경 | 🔴 **무효 — exit 1** |
| 문서 전용 PR 이 과거 사고를 **인용** | ✅ 유효 (인용은 주장이 아니다) |
| 코드 표면 변경이지만 seal 주장 없음 | ✅ 유효 (일상 리팩터까지 막으면 가드 자살) |

🔴 **흔적은 벤더 중립**이다 — 요구하는 것은 (session · claim · verdict) 세 필드이지 특정
도구가 아니다. 그래야 외부 서비스 장애가 가드 작업을 **영구 차단하지 않는다**(정책 17).

Guard-authoring PRs cannot self-exempt from adversarial review; documentation that merely
quotes past incidents still can.
"""
from __future__ import annotations

import importlib
import subprocess  # nosec B404 — 리포 자신의 히스토리만 읽는다
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]

_EXEMPT_LINE = "claim-review-not-required: 넘어가려고 적는 사유입니다 충분히 길게 적었습니다"
_TRACE = (
    "## Grok claim-review\n"
    "- session: 019fe026-3e81-74c0-a948-ed30b05132fc\n"
    "- claim: 이 변경이 주장하는 봉인이 실제로 버티는가\n"
    "- verdict: SURVIVES (반증 시도 4종 전부 실패)\n"
)


@pytest.fixture(name="mod")
def _mod():
    return importlib.import_module("scripts.check_claim_review_trace")


def _run(mod, monkeypatch, *, body: str, base: str, head: str, title: str = "") -> int:
    monkeypatch.setenv("PR_TITLE", title)
    monkeypatch.setenv("PR_BODY", body)
    monkeypatch.setenv("PR_BASE_SHA", base)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return mod.main()


def _rev(ref: str) -> str:
    return subprocess.run(  # nosec B603 B607
        ["git", "rev-parse", ref], cwd=str(_ROOT), capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout.strip()


# ── ① 순수 판정 — 가드 표면 분류 ────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "scripts/check_reverse_mutation.py",
        ".claude/hooks/doc_review_gate.py",
        ".claude/workflows/retrospective.mjs",
        ".claude/settings.json",
        ".github/workflows/ci.yml",
        ".pre-commit-config.yaml",
        "tests/unit/hooks/test_doc_review_gate.py",
    ],
)
def test_guard_surface_is_recognised(mod, path: str):
    """관측자를 저술하는 표면은 전부 잡혀야 한다."""
    assert mod.guard_surfaces([path]) == [path]


@pytest.mark.parametrize(
    "path",
    [
        "src/gate/engine.py",
        "src/templates/dashboard.html",
        "docs/STATE.md",
        "README.md",
        "tests/unit/ui/test_router.py",
        "alembic/versions/0001_init.py",
    ],
)
def test_non_guard_surface_is_not_recognised(mod, path: str):
    """🔴 과교정 대조군 — 여기까지 막으면 일상 작업이 외부 검증을 기다린다(정책 17).

    이게 없으면 `_GUARD_SURFACES` 에 `""` 를 넣어 전부 막아도 초록이다.
    """
    assert mod.guard_surfaces([path]) == []


@pytest.mark.parametrize(
    "path",
    [
        "tools/check_new_guard.py",          # 목록 밖 디렉토리에 만든 가드
        "tests/unit/gate/test_wiring_guard.py",  # test-as-guard (최다 observer-lie 표면)
        "anywhere/deep/check_thing.py",
    ],
)
def test_a_guard_authored_outside_the_directory_list_is_still_caught(mod, path: str):
    """🔴 Grok claim-review `019fe089` 반례 — 디렉토리 열거만으로는 못 잡는다.

    실측 반례: `tools/check_new_guard.py` 를 만들고 면제를 적으면 **exit 0** 이었다.
    AGENTS.md 가 기록하듯 이 리포의 최다 observer-lie 표면은 **test-as-guard** 이고
    그것은 어느 디렉토리에나 생긴다. 그래서 이름 규칙을 함께 본다.
    """
    assert mod.guard_surfaces([path]) == [path]


def test_guard_classification_runs_before_the_code_surface_filter(mod):
    """🔴 더 깊은 결함 — 판정 순서. 이름 규칙이 있어도 **도달 못 하면** 무의미하다.

    초판은 `guard_surfaces(changed_code_surfaces(...))` 였다. `_CODE_SURFACES` 는
    `tools/` 를 포함하지 않으므로 그 경로는 걸러진 뒤 사라져, 이름 규칙이 볼 기회조차 없었다.
    이 단언은 **필터 전 전체 경로**를 돌려주는 함수가 존재하고 그것이 쓰이는지 고정한다.
    """
    assert hasattr(mod, "changed_paths"), "필터 전 경로 조회가 사라졌다 — 목록 밖 가드가 다시 비가시"
    head = _rev("b1eb7110")
    every = mod.changed_paths(f"{head}~1", head)
    filtered = mod.changed_code_surfaces(f"{head}~1", head)

    assert every is not None and filtered is not None
    assert len(every) >= len(filtered), "필터 전 목록이 필터 후보다 작다 — 관계가 뒤집혔다"
    assert any(p not in filtered for p in every), (
        "이 범위에 `_CODE_SURFACES` 밖 경로가 하나도 없다 — 대조군으로 쓸 수 없다"
    )


def test_undecidable_paths_do_not_block(mod):
    """🔴 판정 불가(None)에서 fail-closed 로 두면 **모든 로컬 실행이 영구 red** 가 된다."""
    assert mod.guard_surfaces(None) == []


# ── ② 실경로 — 진짜 커밋 범위로 main() 을 관통시킨다 ────────────────────


def test_real_guard_pr_cannot_self_exempt(mod, monkeypatch):
    """🔴 봉인 본체 — `#1315`(가드 표면 10파일) 범위에서 면제가 **거부**된다.

    합성 픽스처가 아니라 이 저장소의 실제 머지 커밋 범위를 쓴다(불변식 2).
    """
    head = _rev("b1eb7110")

    assert _run(mod, monkeypatch, body=_EXEMPT_LINE, base=f"{head}~1", head=head) == 1


def test_real_guard_pr_passes_with_a_trace(mod, monkeypatch):
    """🔴 대조군 — 흔적을 남기면 통과한다. 이게 없으면 위 단언은 "항상 red" 로도 만족된다."""
    head = _rev("b1eb7110")

    assert _run(mod, monkeypatch, body=_TRACE, base=f"{head}~1", head=head) == 0


def test_docs_only_pr_quoting_a_seal_still_exempts(mod, monkeypatch):
    """🔴 인용은 주장이 아니다 — 회고·원장 기록이 막히면 이 리포의 학습이 멈춘다.

    🔴 **초판은 공허했다** (Grok claim-review `019fe089` 적발). `base == head` 를 써서
    변경 경로가 **0건**이었고, 그건 *"문서 전용 PR 이 면제된다"* 가 아니라 *"빈 diff 가
    면제된다"* 만 증명한다 — 승격을 통째로 지워도 통과하는 단언이었다.

    이제 **실제 docs-only 머지 범위**(`e76f2d43` — 비-docs 파일 0건 실측)를 쓴다.

    ⚠️ 함께 정정: 초판 docstring 은 `#1316` 을 예로 들었는데 **틀렸다**. `#1316` 은
    `tests/unit/scripts/` 가드 2개를 건드렸으므로 docs-only 가 아니고,
    새 규칙에서 **차단되는 것이 옳다**(그 가드들은 적대 검증을 받은 적이 없었다).
    """
    body = f"과거에 **봉인**했다고 적혀 있다(인용).\n\n{_EXEMPT_LINE}\n"
    head = _rev("e76f2d43")

    assert _run(mod, monkeypatch, body=body, base=f"{head}~1", head=head) == 0


def test_the_docs_only_fixture_really_has_no_code_surface(mod):
    """🔴 대조군 — 위 테스트의 픽스처가 정말 docs-only 인지.

    이게 없으면 그 범위에 코드가 섞여도 (다른 이유로) 통과하는 것을 못 본다.
    """
    head = _rev("e76f2d43")

    assert mod.changed_code_surfaces(f"{head}~1", head) == []


def test_a_pr_that_authors_a_guard_is_blocked_even_amid_docs(mod, monkeypatch):
    """🔴 반대 축 — 문서가 대부분이어도 **가드를 저술했으면** 면제되지 않는다.

    `#1316` 이 정확히 그런 PR 이었다(문서 9 + 가드 테스트 2).
    """
    head = _rev("4d0a8dda")
    body = f"회고 기록. 과거에 **봉인**했다고 적혀 있다.\n\n{_EXEMPT_LINE}\n"

    assert _run(mod, monkeypatch, body=body, base=f"{head}~1", head=head) == 1


# ── ③ 두 번째 트리거 — seal 주장 + 코드 표면 ────────────────────────────


def test_seal_claim_over_code_blocks_the_exemption(mod, monkeypatch):
    """코드가 걸린 '봉인' 주장은 가드 표면이 아니어도 검증이 필요하다."""
    src_only = ["src/gate/retry_policy.py"]

    assert mod.guard_surfaces(src_only) == [], "전제: src/ 는 가드 표면이 아니다"
    # 그럼에도 seal 주장 + 코드 표면이면 면제가 막힌다 — main() 의 분기를 직접 확인.
    monkeypatch.setattr(mod, "changed_code_surfaces", lambda b, h: src_only)
    assert _run(
        mod, monkeypatch, title="fix(gate): 봉인", body=_EXEMPT_LINE,
        base="0" * 40, head="1" * 40,
    ) == 1


def test_code_change_without_a_seal_claim_may_still_exempt(mod, monkeypatch):
    """🔴 과교정 대조군 — 일상 코드 변경까지 막으면 오탐이 진탐을 넘는다(정책 17).

    이게 없으면 `exemption_blocked = bool(surfaces)` 라는 과도한 구현으로도 초록이다.
    """
    monkeypatch.setattr(mod, "changed_code_surfaces", lambda b, h: ["src/ui/router.py"])

    assert _run(
        mod, monkeypatch, title="refactor(ui): 라우터 정리", body=_EXEMPT_LINE,
        base="0" * 40, head="1" * 40,
    ) == 0


# ── ④ 흔적은 벤더 중립이다 (가용성 축) ──────────────────────────────────


def test_a_workflow_run_id_is_an_acceptable_session(mod):
    """🔴 외부 서비스 장애가 가드 작업을 영구 차단하면 안 된다 (정책 17).

    면제를 닫는 순간 이 필드가 **단일 벤더 형식만** 받으면 그건 봉인이 아니라 가용성 사고다.
    워크플로 run id 는 transcript 가 디스크에 남아 사후에 열 수 있다 — 흔적의 요건을 만족한다.
    """
    by_workflow = (
        "## claim-review\n"
        "- session: wf_a3ad73e1-eca\n"
        "- claim: 이 가드가 공허하지 않은지 실경로 뮤테이션으로 확인했다\n"
        "- verdict: WEAKENED (우회 1건 발견, 같은 PR 에서 보강)\n"
    )

    assert mod.missing_trace_fields(by_workflow) == []


def test_a_grok_session_is_still_accepted(mod):
    """대조군 — 기존 형식을 깨뜨리지 않았는지."""
    assert mod.missing_trace_fields(_TRACE) == []


@pytest.mark.parametrize(
    "session",
    ["없음", "TODO", "local-pass", "reviewed", "n/a", "12345", "wf_ab"],
)
def test_a_free_form_session_is_rejected(mod, session: str):
    """🔴 과교정의 반대편 — 아무 문자열이나 받으면 그건 **자기 인증**이다.

    이게 없으면 벤더 중립화가 "session: 아무거나" 로 통과하는 fail-open 이 된다.
    """
    body = (
        "## claim-review\n"
        f"- session: {session}\n"
        "- claim: 이 가드가 공허하지 않은지 실경로 뮤테이션으로 확인했다\n"
        "- verdict: SURVIVES (근거)\n"
    )

    assert any("session" in m for m in mod.missing_trace_fields(body)), (
        f"되짚을 수 없는 식별자({session!r})가 흔적으로 인정됐다"
    )
