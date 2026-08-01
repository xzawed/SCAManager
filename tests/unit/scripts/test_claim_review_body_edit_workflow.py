"""`claim-review-on-body-edit.yml` ↔ `ci.yml` repo-integrity 동치 강제.

## 왜 (2026-08-01 실측 + Grok claim-review `019fbc8e`)

정책 19 가드는 `github.event.pull_request.body` 를 읽는데, `ci.yml` 의 `on.pull_request` 에
`types:` 가 없어 **본문만 고쳐서는 CI 가 다시 돌지 않는다**. `gh run rerun` 도 원래 이벤트
payload(= 옛 본문)를 재생하므로 소용없다 — PR #1260 이 이 이유로 두 번 막혔고 결국
**의미 없는 force-push** 로 `synchronize` 를 억지로 발화시켜야 했다.

## 🔴 이 파일이 막는 두 가지 (둘 다 Grok 검증자가 지목한 fail-open)

1. **job 이름 drift** — required status check 는 **(SHA, check 이름)** 으로 식별된다. 이 워크플로의
   job 이름이 `ci.yml` 과 갈라지면, 초록이 돼도 이전 실행의 빨간 check 는 **그대로 남아**
   머지가 계속 막힌다(그리고 새 check 만 하나 더 생긴다). 그래서 기대값을 손으로 적지 않고
   **`ci.yml` 실파일에서 파싱**한다.
2. **step 목록 축소** — 같은 이름의 check 를 갱신하므로, 여기서 일부 step 만 돌리면 그 check 가
   **자기 의미보다 적은 것을 검증하고도 초록**이 된다. 두 워크플로의 가드 스크립트 집합이
   같아야 한다.

부수로 `ci.yml` 이 전체 매트릭스에 `edited` 를 달지 않았는지도 본다 — 달면 본문 오타 한 번에
8 job 이 전부 도는 비용이고, 이 얇은 워크플로의 존재 이유가 사라진다.

Enforces that the thin body-edit workflow keeps ci.yml's repo-integrity job NAME and the same
guard-script set; expectations are parsed from ci.yml itself, never hand-copied.
"""
import re
from pathlib import Path

import pytest

# 배선 판정은 substring 이 아니라 술어로 (guards.md 의무).
# Wiring is decided by the shared predicate, not substring matching.
from tests.unit.scripts._wiring_shape import surface_invokes

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_THIN = _ROOT / ".github" / "workflows" / "claim-review-on-body-edit.yml"

# `run: python scripts/check_x.py` 에서 스크립트 경로만 뽑는다.
_GUARD_RUN = re.compile(r"run:\s*python\s+(scripts/check_\w+\.py)")


def _text(path: Path) -> str:
    assert path.exists(), f"워크플로가 사라졌다 — 이 테스트가 공허해진다: {path.name}"
    return path.read_text(encoding="utf-8")


def _repo_integrity_block(ci_text: str) -> str:
    """`ci.yml` 의 repo-integrity job 본문만 잘라낸다 (다음 top-level job 직전까지)."""
    start = ci_text.index("\n  repo-integrity:")
    rest = ci_text[start + 1:]
    nxt = re.search(r"^  [a-z][\w-]*:$", rest[1:], re.MULTILINE)
    return rest[: nxt.start() + 1] if nxt else rest


def ci_job_display_name(ci_text: str) -> str:
    block = _repo_integrity_block(ci_text)
    match = re.search(r"^\s*name:\s*(.+)$", block, re.MULTILINE)
    assert match, "ci.yml repo-integrity 의 `name:` 을 못 찾았다 — 파서 확인"
    return match.group(1).strip()


def ci_guard_scripts(ci_text: str) -> set:
    return set(_GUARD_RUN.findall(_repo_integrity_block(ci_text)))


# ── 파서가 공허하지 않은지 ────────────────────────────────────────────────


def test_ci_parsing_is_not_vacuous():
    """🔴 대조군 — 파서가 고장 나면 아래 단언이 전부 통과해 버린다."""
    ci = _text(_CI)
    assert ci_job_display_name(ci), "job 표시 이름을 못 읽었다"
    assert len(ci_guard_scripts(ci)) >= 5, (
        f"ci.yml repo-integrity 에서 가드를 {len(ci_guard_scripts(ci))}개만 찾았다 — 파서 확인"
    )


# ── 핵심 불변식 ───────────────────────────────────────────────────────────


def test_thin_workflow_shares_the_required_check_name():
    """🔴 이름이 갈라지면 required check 를 **갱신하지 못한다**(머지가 계속 막힌다).

    기대값을 `ci.yml` 에서 유도한다 — 손으로 적으면 ci.yml 이 바뀌어도 영원히 초록이다.
    """
    expected = ci_job_display_name(_text(_CI))
    thin = _text(_THIN)
    assert f"name: {expected}" in thin, (
        f"얇은 워크플로의 job 이름이 ci.yml 과 다르다.\n"
        f"  ci.yml: {expected!r}\n"
        "→ 다르면 새 check 만 하나 더 생기고, 이전 빨간 check 는 그대로 남는다."
    )


def test_thin_workflow_runs_the_same_guard_set():
    """🔴 step 이 부족하면 **같은 이름의 check 가 더 적은 것을 검증하고 초록**이 된다."""
    ci_guards = ci_guard_scripts(_text(_CI))
    thin_guards = set(_GUARD_RUN.findall(_text(_THIN)))
    missing = ci_guards - thin_guards
    assert not missing, (
        f"ci.yml 은 돌리는데 얇은 워크플로가 빠뜨린 가드: {sorted(missing)}\n"
        "→ 같은 check 이름을 쓰므로 의미가 달라지면 안 된다."
    )


def test_thin_workflow_actually_invokes_the_claim_review_guard():
    """🔴 배선 술어로 확인 — `echo scripts/check_claim_review_trace.py` 는 배선이 아니다."""
    assert surface_invokes(_text(_THIN), "scripts/check_claim_review_trace.py")


def _without_comments(text: str) -> str:
    """`#` 주석 줄 제거 — 🔴 주석의 **설명 문구**가 단언을 충족하는 것을 막는다.

    실측: `fetch-depth: 0` 을 substring 으로 보던 초판은, 설정을 `1` 로 바꿔도
    바로 위 주석("🔴 fetch-depth: 0 필수 —…")이 그 문자열을 포함해 **GREEN 이었다**.
    산문이 검사를 통과시키는 전형이라 설정 줄만 남기고 본다.
    Strip comment lines: a comment explaining the setting satisfied the substring check.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


@pytest.mark.parametrize(("needle", "why"), [
    ("types: [edited]", "본문 편집 이벤트로만 발화해야 한다"),
    ("github.event.changes.body", "제목/base 편집으로는 돌지 않아야 한다(비용)"),
    ("fetch-depth: 0", "정책 19 가드가 PR 범위 커밋을 읽는다 — 얕은 clone 이면 축이 degrade"),
    ("PR_BODY: ${{ github.event.pull_request.body }}", "본문을 env 로 전달(명령 인젝션 차단)"),
])
def test_thin_workflow_keeps_its_contract(needle, why):
    assert needle in _without_comments(_text(_THIN)), f"{needle!r} 누락 — {why}"


def test_thin_workflow_does_not_set_a_permission_decision_on_siblings():
    """🔴 형제 job 을 skip 시키지 않는다 — skip 은 성공으로 취급돼 **빨간 required check 를 세탁**한다.

    이 워크플로는 job 이 하나뿐이어야 한다. 여러 개가 되면 위 세탁 경로가 열린다
    (Grok `019fbc8e` 검증자 적발).
    """
    # 🔴 `jobs:` 이후로 한정 — 그러지 않으면 `on:` 블록의 `pull_request:` 도 job 으로 잡힌다
    #    (실측: 초판이 `['pull_request', 'repo-integrity']` 를 냈다).
    # Scope to the jobs: block; otherwise `on: pull_request:` is misread as a job.
    body = _text(_THIN).split("\njobs:", 1)[1]
    jobs = re.findall(r"^  ([a-z][\w-]*):$", body, re.MULTILINE)
    assert jobs == ["repo-integrity"], (
        f"job 이 {jobs} — 하나여야 한다. 형제 job 을 두면 skip-세탁 경로가 열린다."
    )


def test_ci_full_matrix_still_uses_default_pull_request_types():
    """🔴 `ci.yml` 이 전체 매트릭스에 `edited` 를 달면 이 워크플로의 존재 이유가 사라지고,
    본문 오타 한 번에 8 job 이 전부 돈다."""
    ci = _text(_CI)
    head = ci[: ci.index("jobs:")]
    assert "edited" not in head, (
        "ci.yml 이 전체 매트릭스에 `edited` 를 달았다 — 얇은 워크플로와 중복이고 비용이 크다."
    )
