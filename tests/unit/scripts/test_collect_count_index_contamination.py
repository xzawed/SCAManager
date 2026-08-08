"""테스트 수 계기가 **git 인덱스 상태에 오염되지 않는다** (회고 N-P0-3).

## 사고 — main CI 12시간 49분 red (2026-08-06~07)

`test_gate_claim_consistency.tracked_docs()` 는 수집 시점에 `git ls-files '*.md'` 를 부르고,
그 결과가 `parametrize` **2곳**에 쓰인다. `git ls-files` 는 **머지 충돌 중인 경로를
stage 1/2/3 로 3번** 출력하므로 충돌 `.md` 1건당 collected 가 **+4** 된다.

배치-PR 충돌 4건 상태에서 잰 값이 `6824 + 4×4 = 6840` 이었고, 그 숫자가
`check_docs_sync --fix` 로 STATE 4지점에 **파생 전파**됐다. 사본끼리는 서로 일치했으므로
`check_docs_sync` 는 ✅ 를 냈고, PR 이 통과했고, 머지 후 충돌 없는 CI 가 6824 를 재서
main 이 12시간 49분 red 였다.

🔴 **당시 이 사고는 "사람의 수치 오판독" 으로 기록됐다. 아니었다.**
계기가 거짓을 냈고 사람은 그 값을 정확히 읽었다. 원인 규명이 틀리면 처방도 틀린다 —
전파 차단(`check_test_count_sync` PR 차단)은 **두 번째 방어선**이지 원인 제거가 아니다.

## 이 파일이 고정하는 것

1. 🔴 **대조군 먼저** — 날 `git ls-files` 가 충돌 경로를 실제로 3번 낸다(이게 거짓이면
   아래 단언은 dedupe 가 없어도 통과한다 = 가드 자살).
2. `tracked_docs()` 는 같은 상태에서 **1건**만 돌려준다.
3. dedupe 가 **순서를 보존**한다 — `set()` 로 바꾸면 parametrize 순서가 비결정적이 되고
   `-p no:randomly` 환경에서도 test id 가 흔들린다.

합성 픽스처가 아니라 **실제 머지 충돌**을 만들어 검증한다(불변식 2).
Builds a real merge conflict — not a synthetic fixture — and proves the collector reports
the tree's truth rather than the index's.
"""
from __future__ import annotations

import subprocess  # nosec B404 — 격리된 임시 리포에만 쓴다
from pathlib import Path

import pytest

from tests.unit.scripts.test_gate_claim_consistency import tracked_docs


def _git(repo: Path, *args: str) -> str:
    """임시 리포 전용 git 실행. / Runs git inside the throwaway repo."""
    return subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    ).stdout


@pytest.fixture(name="conflicted_repo")
def _conflicted_repo(tmp_path: Path) -> Path:
    """`.md` 2건이 **실제로 충돌 중인** 리포를 만든다.

    2건인 이유: 1건이면 "충돌 수 × 배수" 관계를 확인할 수 없어, 상수를 잘못 세도 통과한다.
    Two files, so the guard sees a *ratio* rather than a single magic number.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "guard@test.local")
    _git(repo, "config", "user.name", "guard")
    _git(repo, "config", "commit.gpgsign", "false")

    for name in ("alpha.md", "beta.md"):
        (repo / name).write_text("base\n", encoding="utf-8")
    (repo / "untouched.md").write_text("stable\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    trunk = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()

    _git(repo, "checkout", "-qb", "side")
    for name in ("alpha.md", "beta.md"):
        (repo / name).write_text("side\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "side")

    _git(repo, "checkout", "-q", trunk)
    for name in ("alpha.md", "beta.md"):
        (repo / name).write_text("trunk\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "trunk")

    # 충돌을 **일으키는 것이 목적**이라 실패 종료 코드는 정상이다.
    # The merge is expected to fail — that is the state under test.
    subprocess.run(  # nosec B603 B607
        ["git", "merge", "side"], cwd=str(repo), capture_output=True, check=False,
    )
    return repo


def test_a_space_in_a_filename_does_not_split_into_two_entries(conflicted_repo: Path):
    """🔴 같은 부류의 계기 거짓말 — `split()` 은 공백 파일명을 두 조각으로 쪼갠다.

    Grok claim-review `019fe026` 지적. 현재 해당 파일은 0건이지만, 하나 생기는 순간
    parametrize 에 유령 항목 2개가 생겨 수집 수가 조용히 는다.
    """
    (conflicted_repo / "with space.md").write_text("x\n", encoding="utf-8")
    _git(conflicted_repo, "add", "with space.md")

    docs = tracked_docs(root=conflicted_repo)

    assert "with space.md" in docs, f"공백 경로가 온전히 안 들어왔다: {docs}"
    assert "with" not in docs, f"공백에서 쪼개진 유령 항목이 있다: {docs}"


def test_raw_git_ls_files_really_duplicates_conflicted_paths(conflicted_repo: Path):
    """🔴 대조군 — 이게 없으면 아래 단언은 dedupe 를 지워도 통과한다.

    git 이 언젠가 이 동작을 바꾸면 여기가 먼저 깨져서 **가드가 공허해졌음**을 알린다.
    """
    raw = _git(conflicted_repo, "ls-files", "*.md").split()

    assert raw.count("alpha.md") == 3, f"충돌 경로가 3-stage 로 안 나온다 — 대조군 붕괴: {raw}"
    assert raw.count("beta.md") == 3, f"충돌 경로가 3-stage 로 안 나온다 — 대조군 붕괴: {raw}"
    assert raw.count("untouched.md") == 1, "충돌하지 않은 경로까지 중복되면 전제가 다르다"
    # 충돌 2건이 만드는 초과분 = (3-1) × 2 = 4행. parametrize 2곳이면 collected +8.
    assert len(raw) == 7, f"기대 7행(3+3+1), 실측 {len(raw)}: {raw}"


def test_tracked_docs_reports_the_tree_not_the_index(conflicted_repo: Path):
    """🔴 봉인 — 충돌 중에도 파일당 1건. 이 단언이 6840 사고를 재발 불가로 만든다.

    dedupe 를 되돌리면 alpha/beta 가 3건씩 잡혀 즉시 red 다(실경로 뮤테이션 red 확인).
    """
    docs = tracked_docs(root=conflicted_repo)

    assert docs.count("alpha.md") == 1, f"인덱스 stage 가 새어 나왔다: {docs}"
    assert docs.count("beta.md") == 1, f"인덱스 stage 가 새어 나왔다: {docs}"
    assert len(docs) == len(set(docs)), f"중복이 남아 있다 — 수집 수가 부풀 수 있다: {docs}"
    assert sorted(docs) == ["alpha.md", "beta.md", "untouched.md"]


def test_dedupe_preserves_order(conflicted_repo: Path):
    """`set()` 로 바꾸면 parametrize 순서가 비결정적이 된다 — 그 회귀를 막는다."""
    raw = [f for f in _git(conflicted_repo, "ls-files", "*.md").split() if "_archive" not in f]
    expected_first_seen = list(dict.fromkeys(raw))

    assert tracked_docs(root=conflicted_repo) == expected_first_seen


def test_clean_repo_is_unaffected(conflicted_repo: Path):
    """🔴 대조군 — dedupe 가 **정상 상태에서 아무것도 바꾸지 않는지**.

    충돌을 풀면 목록이 그대로여야 한다. 이게 없으면 "dedupe 가 정당한 파일을 지운다" 는
    반대 방향 회귀를 못 잡는다.
    """
    before = tracked_docs(root=conflicted_repo)
    _git(conflicted_repo, "checkout", "--theirs", "alpha.md")
    _git(conflicted_repo, "checkout", "--theirs", "beta.md")
    _git(conflicted_repo, "add", "-A")

    assert tracked_docs(root=conflicted_repo) == before, "충돌 해소가 목록을 바꿨다"


def test_the_real_repo_has_no_duplicates():
    """정본 저장소 자신도 지금 깨끗한지 — 계기가 오염 상태로 커밋되지 않게."""
    docs = tracked_docs()

    assert docs, "추적 `.md` 가 0건 — 범위 붕괴(빈 목록 위의 ✅ 는 fail-open)"
    assert len(docs) == len(set(docs)), "정본 리포가 충돌 상태에서 측정되고 있다"
