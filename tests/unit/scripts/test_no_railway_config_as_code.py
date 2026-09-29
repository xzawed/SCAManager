"""Railway Config as Code 파일(`railway.toml`·`railway.json`)은 저장소 어디에도 추적되지 않는다.

No Railway Config-as-Code file is tracked anywhere in the repository.

## 왜 (Railway 문서, 2026-09-29 확인)

- Config as Code 는 폐기됐고 기존 파일도 **2026-12-01** 부터 읽히지 않는다.
- 파일이 있으면 그 배포에 한해 대시보드 값을 **덮는다**(대시보드 값은 바뀌지 않는다) —
  설정 주인이 둘이 되고, 컷오프 날 조용히 대시보드 값으로 돌아간다.
- 기본 탐색 이름은 `railway.toml`·`railway.json` 이고, 서비스 설정의 Config File Path 는
  저장소 안 **아무 경로**나 가리킬 수 있다(`/backend/railway.toml`, Root Directory 를 따르지 않음).
배포 설정의 정본은 Railway 대시보드다 — `docs/workflow/deploy.md` 표.
Config as Code is deprecated and overrides the dashboard per deployment; the dashboard is the source.

## 판정 — 추적된 경로의 basename 이 대소문자 무관 `railway.toml`/`railway.json` 인가

- 목록은 `git ls-files -z`(인덱스)에서 읽는다. Railway 는 커밋을 읽는다 — 작업트리의 미추적
  파일(다른 워크트리 `.claude/worktrees/*/railway.toml` 포함)은 배포되지 않는다.
- 깊이는 보지 않는다(커스텀 경로). 대소문자는 접는다 — 대소문자 무시 파일시스템에서 만든
  `Railway.toml` 도 커스텀 경로가 가리킬 수 있다.
- 안 잰다: 대시보드 Config File Path 가 **다른 이름**의 파일을 가리키는 경우 — 저장소 밖 설정이다.
  첫 배포 뒤 `railway status --json` 의 배포 meta 에 `configFile` 이 없는지로 확인한다.
The index is read (not the working tree); depth is ignored and case is folded.

## 판정식 뒤집기 (verify.md 「판정식을 쓸 때」 4)

- claimed = 루트 `railway.toml` · 루트 `railway.json` · 중첩 `backend/railway.toml` · `deploy/Railway.JSON`
- cheap(「초록 = 루트에 `railway.toml` 이 없다」를 낼 가장 싼 과정 — 루트 존재 검사 · 작업트리 rglob ·
  경로/본문 부분문자열) = 루트 `railway.toml` · 미추적 작업트리 파일 · `railway.toml.bak` ·
  `docs/railway.toml.md` · `src/railway_client/models.py` · 본문에 `railway.toml` 을 적은 문서
- claimed\\cheap(잡혀야) = 중첩 · 다른 대소문자 / cheap\\claimed(무시돼야) = 나머지
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

_ROOT = Path(__file__).resolve().parents[3]

# Railway 가 기본 탐색으로 읽는 Config as Code 파일 이름(문서: config-as-code).
# Names Railway's default discovery reads (docs: config-as-code).
_CAC_NAMES = frozenset({"railway.toml", "railway.json"})

# git 위치 변수는 cwd 를 이긴다 — 훅이 물려준 값이면 다른 저장소의 인덱스를 읽는다(Grok 반증).
# Git location variables beat cwd; inherited from a hook they point git at another index.
_GIT_LOCATION_VARS = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"})


def _git_env() -> dict[str, str]:
    """git 위치 변수를 뺀 환경 — git 이 cwd 의 저장소를 읽게 한다."""
    return {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION_VARS}


def config_as_code_files(paths: list[str]) -> list[str]:
    """경로 목록 중 Config as Code 파일 — basename 을 대소문자 무관으로 본다(깊이 무관).

    Paths whose basename is a Config-as-Code name, case-folded, at any depth.
    """
    return sorted({p for p in paths if PurePosixPath(p).name.lower() in _CAC_NAMES})


def tracked_files(root: Path) -> list[str]:
    """`git ls-files -z` 의 경로 — 인덱스를 읽는다(미추적 작업트리 파일 제외).

    `-z` = 비 ASCII 경로를 따옴표로 감싸지 않는다. git 이 없거나 실패하면 예외(=red)다.
    The index, not the working tree; `-z` keeps non-ASCII paths unquoted. No git = error (red).
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True, env=_git_env(),
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


# ── 판정식 자기검증 — 심은 입력으로 뒤집어 본다 ───────────────────────────


@pytest.mark.parametrize("path, caught", [
    # claimed — 기본 탐색 두 이름
    ("railway.toml", True),
    ("railway.json", True),
    # 🔴 claimed\cheap — 루트 존재 검사가 놓친다
    ("backend/railway.toml", True),
    ("deploy/Railway.JSON", True),
    # 🔴 cheap\claimed — 경로 부분문자열은 맞히지만 Config as Code 파일이 아니다
    ("railway.toml.bak", False),
    ("docs/railway.toml.md", False),
    ("src/railway_client/models.py", False),
    ("docs/runbooks/railway.md", False),
    ("railway.yaml", False),
])
def test_judgement_on_planted_paths(path, caught):
    assert (config_as_code_files([path]) == [path]) is caught


def _init_repo(repo: Path, files: dict[str, str]) -> None:
    """임시 git 저장소를 만들고 `files` 를 추적시킨다(커밋 없이 인덱스만)."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=_git_env())
    for name, body in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", *files], cwd=repo, check=True, env=_git_env())


def test_collector_reads_the_index_not_the_working_tree(tmp_path):
    """🔴 두 번째 싼 과정(작업트리 rglob · 본문 grep)이 맞히는 쌍을 실제 git 저장소에 심는다.

    추적된 중첩 파일은 잡히고, 미추적 루트 파일과 본문에만 이름을 적은 문서는 무시돼야 한다.
    A tracked nested file is caught; an untracked root file and a doc naming it in prose are not.
    """
    _init_repo(tmp_path, {
        "Dockerfile": "FROM scratch\n",
        "backend/railway.toml": "[deploy]\n",
        "notes.md": "`railway.toml` 은 폐기됐다\n",
    })
    (tmp_path / "railway.toml").write_text("[deploy]\n", encoding="utf-8")  # 미추적 / untracked

    tracked = tracked_files(tmp_path)
    assert sorted(tracked) == ["Dockerfile", "backend/railway.toml", "notes.md"], tracked
    assert config_as_code_files(tracked) == ["backend/railway.toml"]


def test_inherited_git_location_vars_do_not_redirect_the_listing(tmp_path, monkeypatch):
    """🔴 훅이 물려준 GIT_DIR·GIT_INDEX_FILE 이 다른 인덱스(Dockerfile 만)를 가리켜도 거짓 초록이 아니다.

    Inherited GIT_DIR/GIT_INDEX_FILE pointing at another index must not turn the verdict green.
    """
    repo, other = tmp_path / "repo", tmp_path / "other"
    _init_repo(repo, {"Dockerfile": "FROM scratch\n", "railway.toml": "[deploy]\n"})
    _init_repo(other, {"Dockerfile": "FROM scratch\n"})
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))
    assert config_as_code_files(tracked_files(repo)) == ["railway.toml"]


def test_planted_paths_in_the_real_index_flip_the_verdict():
    """실제 인덱스(손대지 않은 운영 목록)에 심어도 같은 뒤집힘 — 심은 CaC 만 잡힌다."""
    tracked = tracked_files(_ROOT)
    planted = config_as_code_files([*tracked, "backend/railway.toml", "railway.toml.bak"])
    assert planted == ["backend/railway.toml"], planted


# ── 저장소 상태 ─────────────────────────────────────────────────────────


def test_no_railway_config_as_code_file_is_tracked():
    """🔴 배포 설정은 대시보드 하나 — Config as Code 파일을 다시 만들지 않는다."""
    tracked = tracked_files(_ROOT)
    # 바닥 — 목록이 비면 「없음」이 아니라 「못 쟀음」이다. 빌드 정의는 반드시 추적된다.
    # Floor: an empty listing means "not measured", never "none found".
    assert "Dockerfile" in tracked, f"git ls-files 가 루트 Dockerfile 을 못 봤다 — 측정 실패 ({len(tracked)}건)"
    found = config_as_code_files(tracked)
    assert not found, (
        f"Railway Config as Code 파일이 추적된다: {found}\n"
        "→ 폐기된 형식이고(2026-12-01 컷오프) 대시보드 값을 덮는다. 설정은 대시보드에서 바꾸고 "
        "docs/workflow/deploy.md 표를 같은 PR 에서 고친다."
    )
