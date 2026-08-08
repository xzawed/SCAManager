"""이월 마커는 **머지 후에도 읽히는 곳**에서만 유효하다 (회고 N-P0-2).

## 사고 기전 — 마커가 자기가 없애려던 사고를 재생산한다

`check_test_count_sync` 는 두 이벤트에서 돈다.

| 이벤트 | `PR_BODY` | 초판 동작 |
|---|---|---|
| `pull_request` | 전달됨 | 마커 인식 → PR **통과** |
| `push` (머지 후 main) | **전달 안 됨** | 마커 소멸 → **main red** |

즉 `STATE-sync-deferred:` 를 **처음 쓰는 사람이 main 을 빨갛게 만든다**. 이 마커의 존재
이유가 *"오판독한 수치가 머지돼 main 이 12시간 49분 red 였던 사고"* 를 막는 것이었으므로,
초판은 자기 목적을 정확히 배반하는 구조였다. 사용 0건이라 아직 발현하지 않았을 뿐이다.

## 고친 방향

"push 에도 본문을 흘려보내기" 가 **아니라** "머지 후에도 남는 운반체에서만 마커를 인정하기".
이월은 *"지금 안 하고 나중에 한다"* 는 약속이고, 약속은 머지 뒤에도 읽혀야 한다.
커밋 메시지는 squash 후에도 남는다. CLAUDE.md 6-step ⑤ 이월 분기가 이미
*"commit body 에 카운트 delta 를 기록"* 하라고 적어 둔 것과도 일치한다.

🔴 **본문에만 적은 마커는 조용히 무시하지 않고 PR 단계에서 실패시킨다** — 무시하면 저자는
면제를 적었다고 믿고 떠나고, 사고는 머지 뒤에 터진다(고칠 수 있는 자리에서 알린다).

Only a carrier that survives the merge may defer; a body-only marker fails loudly on the PR.
"""
from __future__ import annotations

import importlib
import subprocess  # nosec B404 — 리포 자신의 로그만 읽는다
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]

_REASON = "병렬 PR 이 STATE 동일 라인을 건드려 trailing sync 로 이월합니다"
_MARKER = f"STATE-sync-deferred: {_REASON}"


@pytest.fixture(name="mod")
def _mod():
    return importlib.import_module("scripts.check_test_count_sync")


@pytest.fixture(name="drift")
def _drift(monkeypatch, mod):
    """드리프트가 **실재하는** 상태를 만든다 — 마커 분기까지 도달시키기 위해.

    수치 수집은 실제로 돌리면 분당 수십 초라 경계(collect)만 고정한다. 판정 로직은 그대로다.
    """
    monkeypatch.setattr(mod, "collect_count", lambda path: 1)
    monkeypatch.setattr(mod, "state_counts", lambda text: (9999, 9999))
    return mod


def _run(mod, monkeypatch, *, commits: str, body: str) -> int:
    monkeypatch.setattr(mod, "_git_text", lambda *a: commits)
    monkeypatch.setenv("PR_BODY", body)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return mod.main([])


# ── ① 운반체 선택 ─────────────────────────────────────────────────────────


def test_marker_in_a_commit_message_defers(drift, monkeypatch):
    """🔴 유효한 이월 — 커밋 메시지에 있으면 머지 후에도 읽힌다."""
    assert _run(drift, monkeypatch, commits=f"chore: 작업\n\n{_MARKER}\n", body="") == 0


def test_marker_only_in_the_pr_body_fails_on_the_pr(drift, monkeypatch):
    """🔴 봉인 본체 — 본문에만 있으면 **머지 전에** 실패한다.

    이전에는 여기서 0 을 돌려주고, 머지 후 push 이벤트가 같은 드리프트에 1 을 돌려줬다.
    """
    assert _run(drift, monkeypatch, commits="chore: 마커 없는 커밋\n", body=f"{_MARKER}\n") == 1


def test_no_marker_anywhere_still_blocks(drift, monkeypatch):
    """대조군 — 마커가 없으면 당연히 차단(가드가 통째로 꺼지지 않았는지)."""
    assert _run(drift, monkeypatch, commits="chore: 평범한 커밋\n", body="평범한 본문\n") == 1


def test_push_event_reads_the_same_carrier(drift, monkeypatch):
    """🔴 대칭 — push 이벤트(본문 없음)에서도 같은 마커가 통한다.

    이 단언이 이전 구현에서는 **실패**한다. 그게 이 파일의 존재 이유다.
    """
    monkeypatch.delenv("PR_BODY", raising=False)
    monkeypatch.delenv("PR_BASE_SHA", raising=False)
    monkeypatch.delenv("PR_HEAD_SHA", raising=False)
    monkeypatch.setattr(drift, "_git_text", lambda *a: f"chore: 머지\n\n{_MARKER}\n")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert drift.main([]) == 0


# ── ② 운반체 조회가 실제로 git 을 읽는가 (실경로) ────────────────────────


def test_carriers_read_real_git_history_on_a_pr_range(monkeypatch, mod):
    """🔴 실경로 — mock 없이, 이 저장소의 진짜 커밋 범위에서 메시지를 얻는지.

    `_git_text` 를 mock 한 위 테스트들만 있으면 git 인자가 틀려도 전부 초록이다.
    """
    head = subprocess.run(  # nosec B603 B607
        ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    expected = subprocess.run(  # nosec B603 B607
        ["git", "log", "-1", "--format=%s", head], cwd=str(_ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.strip()

    monkeypatch.setenv("PR_BASE_SHA", f"{head}~1")
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.setenv("PR_BODY", "")
    commits, body = mod.deferral_carriers()

    assert expected, "기준 커밋 제목이 비었다 — 이 테스트가 공허해졌다"
    assert expected in commits, (
        f"PR 범위의 커밋 제목({expected!r})이 운반체에 없다 — git 인자가 틀렸다"
    )
    assert body == "", "PR_BODY 가 비었는데 본문이 채워졌다"


def test_carriers_fall_back_to_the_last_commit_without_a_range(monkeypatch, mod):
    """push 이벤트 — SHA 범위가 없으면 직전 커밋을 본다."""
    for name in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PR_BODY", "")
    last = subprocess.run(  # nosec B603 B607
        ["git", "log", "-1", "--format=%s"], cwd=str(_ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.strip()

    assert last, "직전 커밋 제목이 비었다 — 이 테스트가 공허해졌다"
    assert last in mod.deferral_carriers()[0]


def test_git_failure_is_not_an_exemption(monkeypatch, mod):
    """🔴 fail-closed — git 이 실패해도 '마커 있음' 으로 읽히지 않는다."""
    monkeypatch.setenv("PR_BASE_SHA", "0000000000000000000000000000000000000000")
    monkeypatch.setenv("PR_HEAD_SHA", "0000000000000000000000000000000000000000")
    monkeypatch.setenv("PR_BODY", "")

    assert mod._DEFERRED.search(mod.deferral_carriers()[0]) is None


# ── ③ 🔴 실제 머지 토폴로지 (Grok claim-review 019fe026 이 BROKEN 판정한 축) ─────


@pytest.fixture(name="merged_repo")
def _merged_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """마커를 **feature 커밋 본문**에 담고 `--no-ff` 로 머지한 리포.

    이 토폴로지에서 tip(머지 커밋)의 메시지에는 마커가 **없다**. 그래서 초판처럼
    `git log -1` 을 보면 마커를 놓치고 main 이 빨개진다.

    Returns (repo, before_sha, after_sha) — push 이벤트가 주는 것과 같은 두 SHA.
    """
    repo = tmp_path / "merged"
    repo.mkdir()

    def g(*args: str) -> str:
        return subprocess.run(  # nosec B603 B607
            ["git", *args], cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        ).stdout

    g("init", "-q")
    g("config", "user.email", "guard@test.local")
    g("config", "user.name", "guard")
    g("config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("base\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-qm", "base")
    trunk = g("rev-parse", "--abbrev-ref", "HEAD").strip()
    before = g("rev-parse", "HEAD").strip()

    g("checkout", "-qb", "feature")
    (repo / "a.txt").write_text("feature\n", encoding="utf-8")
    # 🔴 마커는 feature 커밋의 **본문**에 있다 — 제목이 아니다.
    g("commit", "-qam", "chore: 작업", "-m", _MARKER)

    g("checkout", "-q", trunk)
    g("merge", "--no-ff", "-m", "Merge pull request #999 from feature", "feature")
    after = g("rev-parse", "HEAD").strip()
    return repo, before, after


def test_a_merge_commit_tip_really_hides_the_marker(merged_repo):
    """🔴 대조군 — `git log -1` 로는 마커가 **안 보인다**.

    이게 거짓이면 아래 봉인 단언은 범위 조회가 없어도 통과한다(가드 자살).
    Grok claim-review 019fe026 이 초판을 BROKEN 으로 판정한 근거가 정확히 이것이다.
    """
    repo, _, _ = merged_repo
    tip = subprocess.run(  # nosec B603 B607
        ["git", "log", "-1", "--format=%B"], cwd=str(repo), capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout

    assert "STATE-sync-deferred" not in tip, (
        "머지 커밋 tip 에 마커가 보인다 — 이 토폴로지가 위험을 재현하지 못한다"
    )


def test_push_range_finds_a_marker_the_tip_hides(merged_repo, monkeypatch, mod):
    """🔴 봉인 본체 — push 는 그 push 가 들여온 **커밋 전부**를 본다.

    실제 git 저장소에 실제 머지 커밋을 만들어 검증한다 — `_git_text` 를 mock 하지 않는다.
    """
    repo, before, after = merged_repo
    monkeypatch.setattr(mod, "_ROOT", repo)
    for name in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PUSH_BEFORE_SHA", before)
    monkeypatch.setenv("PUSH_AFTER_SHA", after)
    monkeypatch.setenv("PR_BODY", "")

    assert mod._DEFERRED.search(mod.deferral_carriers()[0]) is not None, (
        "머지 커밋으로 머지하면 마커가 사라진다 — PR 초록 → main red 가 그대로 재현된다"
    )


def test_new_branch_zero_sentinel_falls_back(merged_repo, monkeypatch, mod):
    """`github.event.before` 가 all-zero(새 브랜치)면 범위가 무효 — 물러나되 터지지 않는다."""
    repo, _, after = merged_repo
    monkeypatch.setattr(mod, "_ROOT", repo)
    for name in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PUSH_BEFORE_SHA", "0" * 40)
    monkeypatch.setenv("PUSH_AFTER_SHA", after)
    monkeypatch.setenv("PR_BODY", "")

    assert "Merge pull request #999" in mod.deferral_carriers()[0], (
        "all-zero sentinel 에서 직전 커밋으로 물러나지 않았다"
    )


def test_unreachable_range_does_not_exempt(merged_repo, monkeypatch, mod):
    """🔴 fail-closed — 범위가 조회 불가여도 '마커 있음' 이 되지 않는다."""
    repo, _, after = merged_repo
    monkeypatch.setattr(mod, "_ROOT", repo)
    for name in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PUSH_BEFORE_SHA", "1" * 40)
    monkeypatch.setenv("PUSH_AFTER_SHA", after)
    monkeypatch.setenv("PR_BODY", "")

    # 물러난 tip 에는 마커가 없다 → 면제 아님 → 드리프트가 차단된다.
    assert mod._DEFERRED.search(mod.deferral_carriers()[0]) is None


# ── ④ 자기문서화 면제 방지 (기존 관용구 유지) ────────────────────────────


def test_this_very_file_does_not_defer_itself(mod):
    """🔴 이 파일은 마커를 **설명**한다 — 그 설명이 이월로 인식되면 안 된다.

    정책 19 면제 마커가 자기를 문서화하는 PR 을 면제해 버린 실사고와 같은 클래스다.
    """
    prose = Path(__file__).read_text(encoding="utf-8")

    assert mod._DEFERRED.search(prose) is None, (
        "마커를 설명하는 산문이 이월로 인식됐다 — 문서화가 면제를 발급한다"
    )
