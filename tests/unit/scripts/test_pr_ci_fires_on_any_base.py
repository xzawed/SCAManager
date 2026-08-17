"""PR 워크플로가 base 브랜치와 무관하게 발화하는지 — 게이트 우회 차단 (#1432).

## 왜 (2026-08-17 실측)

`on.pull_request.branches: [main]` 이면 base 가 **다른 feature 브랜치**인 PR 에서
워크플로가 **아예 발화하지 않는다**. 그 PR 은 CI 0건 · claim-review 0건으로 머지된다.

이 리포에서 실제로 그렇게 머지된 PR (`gh pr list --state merged` 실측):

    #1402 base=docs/final-cleanup           checks=no checks reported
    #1399 base=docs/retire-owed-and-history checks=no checks reported
    #1398 base=docs/retire-owed-and-history checks=no checks reported
    #1389 base=docs/melt-state-ledger       checks=no checks reported

## 🔴 이 가드가 닫는 것과 **닫지 못하는 것** (정직 기준)

닫는다 — **관측**. 스택 PR 에서도 CI 가 돌아 저자와 리뷰어가 red 를 본다.

**닫지 못한다** — **집행**. 머지를 막는 것은 branch protection / ruleset 인데 둘 다
`refs/heads/main` 만 대상으로 한다(2026-08-17 실측):

    gh api .../branches/main/protection/required_status_checks  → main 전용 10종
    gh api .../rulesets/17144307 → conditions.ref_name.include = ["refs/heads/main"]

즉 feature 브랜치를 base 로 한 PR 은 **check 가 0건이라 통과한 게 아니라, 애초에 규칙이
적용되지 않는다.** 집행까지 원하면 ruleset 의 `ref_name.include` 를 넓혀야 하고 그것은
리포 설정 변경이라 이 리포의 가드가 볼 수 없다. 여기서는 그 사실을 **적어만 둔다** —
이 테스트가 초록이라고 「스택 PR 이 막힌다」로 읽히면 새 observer-lie 다.

## 🔴 왜 정규식이 아니라 YAML 파싱인가 (Grok claim-review `01a00f8c` 적발)

초판은 `on.pull_request` 아래 `branches:` 를 정규식으로 찾았고, Grok 이 구멍 3개를 실측했다:

    branches-ignore: [main]              → 미탐 (같은 효과인데 이름이 다르다)
    pull_request: {branches: [main]}     → 미탐 (flow 스타일)
    pull_request:\n    # 주석\n    branches: [main]  → 미탐 (주석이 끼면 앵커가 깨진다)

셋 다 **파일은 분모에 들어간 채 초록**이 된다 — 거짓 집행자다. 구조를 재는 도구로 바꾸면
세 구멍이 한 번에 닫힌다(가드 판정은 substring 이 아니라 술어로 — 리포 관용구).

Ensures PR-triggered workflows are not scoped to a set of base branches, so stacked PRs still
run CI. Note this buys visibility, not enforcement: branch protection targets main only.
"""
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# base 를 좁히는 두 키 — 효과가 같으므로 함께 막는다.
# Both keys narrow the base set; forbidding only one leaves the other as a bypass.
_BASE_FILTERS = ("branches", "branches-ignore")
_PR_EVENTS = ("pull_request", "pull_request_target")


def _on_block(path: Path):
    """워크플로의 `on:` 매핑. 🔴 YAML 1.1 은 `on` 을 **불리언 True** 로 읽는다."""
    import yaml  # pylint: disable=import-outside-toplevel  # (기존 테스트 관용구)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{path.name}: 워크플로가 매핑이 아니다"
    on = doc.get(True, doc.get("on"))
    assert on is not None, f"{path.name}: `on:` 블록을 찾지 못했다 — 파서가 눈을 잃었다"
    return on


def _pr_workflows() -> list[Path]:
    """`pull_request`(또는 `_target`)로 발화하는 워크플로.

    🔴 `*.yml` 과 `*.yaml` 을 모두 본다 — Grok 적발: 확장자 하나만 보면 파일을 `ci.yaml` 로
    바꾸는 것만으로 분모에서 조용히 빠진다.
    """
    found = []
    for p in sorted(list(_WORKFLOWS.glob("*.yml")) + list(_WORKFLOWS.glob("*.yaml"))):
        on = _on_block(p)
        keys = on if isinstance(on, (dict, list)) else [on]
        if any(e in keys for e in _PR_EVENTS):
            found.append(p)
    # 🔴 공허화 차단 — 분모가 비면 아래 단언이 전부 자동 통과다.
    # Vacuity guard: an empty denominator makes every assertion below trivially true.
    assert found, ".github/workflows 에 pull_request 워크플로가 0건 — 이 테스트가 공허하다"
    return found


def _base_filter(on, event) -> object | None:
    """해당 이벤트에 걸린 base 필터 값 — 없으면 None."""
    if not isinstance(on, dict):
        return None                       # `on: [pull_request]` 리스트형 = 필터 없음
    cfg = on.get(event)
    if not isinstance(cfg, dict):
        return None                       # `pull_request:` (null) 또는 스칼라 = 필터 없음
    for key in _BASE_FILTERS:
        if key in cfg:
            return {key: cfg[key]}
    return None


@pytest.mark.parametrize("wf", _pr_workflows(), ids=lambda p: p.name)
def test_pr_workflow_is_not_scoped_to_a_single_base_branch(wf: Path):
    """`on.pull_request` 에 base 필터를 걸면 스택 PR 이 CI 0건으로 머지된다 (#1432)."""
    on = _on_block(wf)
    offenders = {e: f for e in _PR_EVENTS if (f := _base_filter(on, e)) is not None}
    assert not offenders, (
        f"{wf.name}: `on.{'/'.join(offenders)}` 가 base 를 {offenders} 로 제한한다 — "
        "base 가 그 밖인 PR 은 워크플로가 발화하지 않아 CI 0건으로 머지된다.\n"
        "→ 그 필터를 지워 모든 base 에서 발화시킨다 (#1432 옵션 A).\n"
        "⚠️ 이것은 관측을 되살릴 뿐 머지를 막지는 않는다 — branch protection 은 main 전용이다."
    )


@pytest.mark.parametrize("shape", [
    # Grok `01a00f8c` 가 초판 정규식에서 실측한 미탐 3형 — 전부 red 여야 한다.
    "on:\n  pull_request:\n    branches: [main]\n",
    "on:\n  pull_request:\n    branches-ignore: [wip/**]\n",
    "on:\n  pull_request: {branches: [main]}\n",
    "on:\n  pull_request:\n    # 주석이 끼어도 잡아야 한다\n    branches:\n      - main\n",
    "on:\n  pull_request_target:\n    branches: [main]\n",
], ids=["list", "ignore", "flow", "comment+multiline", "pr_target"])
def test_guard_detects_every_forbidden_shape(shape: str, tmp_path: Path):
    """🔴 가드 자기검증 — 금지 형태를 실제로 잡는가.

    이 단언이 없으면 판정 함수가 무엇도 잡지 못하게 망가져도 위 테스트는 영원히 초록이다
    (가드가 자기 눈을 잃는 형태). 초판 정규식은 여기서 3/5 를 놓쳤다.
    Self-check: a predicate that detects nothing would keep the guard permanently green.
    """
    import yaml  # pylint: disable=import-outside-toplevel
    on = yaml.safe_load(shape)[True]
    assert any(_base_filter(on, e) is not None for e in _PR_EVENTS), \
        f"가드가 금지 형태를 놓친다: {shape!r}"


@pytest.mark.parametrize("shape", [
    "on:\n  push:\n    branches: [main]\n  pull_request:\n",          # 현재 ci.yml 형태
    "on:\n  pull_request:\n    types: [edited]\n",                    # body-edit 워크플로
    "on: [pull_request]\n",                                           # 리스트 축약형
], ids=["bare", "types-only", "list-form"])
def test_guard_does_not_flag_allowed_shapes(shape: str):
    """오탐 축 — `push` 의 `branches` 나 `types` 만 있는 형태를 금지로 읽으면 안 된다."""
    import yaml  # pylint: disable=import-outside-toplevel
    on = yaml.safe_load(shape)[True]
    assert all(_base_filter(on, e) is None for e in _PR_EVENTS), \
        f"가드가 허용 형태를 오탐한다: {shape!r}"
