"""Local git diff collection for CLI usage — reads diffs from the working repo."""
import logging
import re
import subprocess  # nosec B404

from src.github_client.models import ChangedFile

logger = logging.getLogger(__name__)

_TIMEOUT = 30
_BINARY_PATTERN = re.compile(r"^Binary files", re.MULTILINE)


class GitError(Exception):
    """Raised when a git operation fails."""


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(  # nosec B603 B607
            ["git", *args],
            capture_output=True,
            text=True,
            # 🔴 로케일에 맡기지 않는다 — 이 리포의 diff 는 한국어를 담는다. cp949 머신에서
            # `text=True` 만 주면 리더가 UnicodeDecodeError 로 죽어 `stdout` 이 None 이 되고,
            # CLI 는 그것을 「변경 없음」으로 읽는다 (#1586).
            # git output here is Korean; locale decoding would silently yield stdout=None.
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            check=check,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not in PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git command timeout after {_TIMEOUT}s") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git command failed: {exc.stderr or exc}") from exc


def _collect_file(
    line: str, base: str, staged: bool
) -> ChangedFile | None:
    """`--name-status` 한 줄을 ChangedFile 로 변환. 바이너리·스킵 케이스는 None."""
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    status = parts[0]
    # 리네임(R###)·복사(C###) 라인은 `status\told\tnew` (탭 2개) → 대상(new) 파일명 사용.
    # 일반 라인은 `status\tfile` → parts[-1] 이 곧 파일명 (양쪽 모두 정확).
    # Rename(R###)/copy(C###) lines are `status<TAB>old<TAB>new`; use the destination (new)
    # filename. Normal lines are `status<TAB>file`, so parts[-1] is correct in both cases.
    filename = parts[-1]

    patch_args = ("diff", "--cached", "--", filename) if staged else ("diff", base, "--", filename)
    patch = _git(*patch_args, check=False).stdout
    if _BINARY_PATTERN.search(patch):
        return None

    content = ""
    if status != "D":
        # 🔴 분석 대상은 **patch 와 같은 판** 이어야 한다.
        # `--staged` 면 patch 가 index 에서 오므로 content 도 index 에서 읽는다.
        # HEAD 에서 읽으면 방금 스테이징한 변경이 통째로 분석을 빠져나가고, 신규 파일은
        # `HEAD:` 조회가 실패해 빈 문자열이 된다 — 커밋 전 검사의 존재 이유가 사라진다
        # (감사 A3, #1519 실측).
        #
        # 🔴 `:0:<path>` 를 쓴다 — 맨 `:<path>` 는 오파싱된다(실측). git 은 `:` 뒤의
        # `[0-3]:` 를 **스테이지 번호**로 먹으므로, 경로가 `0:weird/f.py` 면
        # `:0:weird/f.py` 로 해석돼 실제로는 `weird/f.py` 를 찾는다. `:/text` 도
        # 커밋 메시지 검색이다. `:0:` 접두사 뒤는 전부 경로다.
        # Use the explicit stage form; a bare `:<path>` misparses `[0-3]:` and `/`.
        revision = ":0:" + filename if staged else "HEAD:" + filename
        content_result = _git("show", revision, check=False)
        if content_result.returncode == 0:
            content = content_result.stdout

    return ChangedFile(filename=filename, content=content, patch=patch)


def get_diff_files(
    base: str = "HEAD~1", staged: bool = False
) -> list[ChangedFile]:
    """로컬 git diff로 변경 파일 목록과 패치를 수집한다."""
    name_status_args = ("diff", "--cached", "--name-status") if staged else ("diff", "--name-status", base)
    result = _git(*name_status_args, check=False)
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]

    files: list[ChangedFile] = []
    for line in lines:
        changed = _collect_file(line, base, staged)
        if changed is not None:
            files.append(changed)
    return files


def get_commit_message(base: str = "HEAD~1") -> str:
    """base부터 HEAD까지 커밋 메시지를 반환한다."""
    result = _git("log", "--format=%B", f"{base}..HEAD", check=False)
    return result.stdout.strip()


def get_repo_name() -> str:
    """git remote origin URL에서 owner/repo 형태의 리포 이름을 추출한다."""
    try:
        result = _git("remote", "get-url", "origin")
    except GitError:
        return ""

    url = result.stdout.strip()
    # SSH: git@github.com:owner/repo.git
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else ""
