"""`--staged` 가 **변경 전** 내용을 분석한다 — 방금 스테이징한 코드가 안 보인다 (감사 A3, #1519).

🔴 실측. `src/cli/git_diff.py::_collect_file` 는 patch 를 `staged` 에 맞춰 고르면서
content 는 **언제나 `git show HEAD:<file>`** 에서 읽는다:

    patch_args = ("diff", "--cached", ...) if staged else ("diff", base, ...)   # staged 반영
    content_result = _git("show", "HEAD:" + filename, ...)                       # 언제나 HEAD

그 결과 `python -m src.cli review --staged` 는:

| 파일 상태 | patch | 분석되는 content |
|---|---|---|
| 수정(M) | 스테이징된 변경 | **변경 전 HEAD 판** |
| 신규(A) | 스테이징된 추가 | **빈 문자열** (`HEAD:new.py` 조회 실패) |

실 git 으로 재현했다 — 방금 스테이징한 `eval("2")` 가 분석 대상에서 사라진다:

    git show HEAD:a.py   ->  x = 1                    (옛 판)
    git show :a.py       ->  x = 1 / import os / y = eval("2")   (스테이징된 판)
    git show HEAD:new.py ->  fatal: path 'new.py' exists on disk, but not in 'HEAD'
    git show :new.py     ->  z = 3

즉 CLI 로 커밋 전 검사를 하면 **바로 그 변경만** 안 보인다. 정적분석의 목적이
「이 변경이 안전한가」인데 그 축이 통째로 빠진다.

index 판은 `git show :<file>` 로 읽는다(콜론 뒤 경로 = 스테이지 0).

Under --staged the patch comes from the index but the content came from HEAD.
"""
from __future__ import annotations

import subprocess  # nosec B404
from pathlib import Path

import pytest

from src.cli.git_diff import get_diff_files


def _run(*args: str, cwd: Path) -> str:
    return subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """커밋 1개 + 수정 1건 + 신규 1건이 스테이징된 실제 저장소."""
    _run("init", "-q", ".", cwd=tmp_path)
    _run("config", "user.email", "t@t", cwd=tmp_path)
    _run("config", "user.name", "t", cwd=tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _run("add", "a.py", cwd=tmp_path)
    _run("commit", "-qm", "init", cwd=tmp_path)

    # 커밋 뒤 스테이징 — 이것이 --staged 가 봐야 할 것이다
    (tmp_path / "a.py").write_text('x = 1\nimport os\ny = eval("2")\n', encoding="utf-8")
    (tmp_path / "new.py").write_text("z = 3\n", encoding="utf-8")
    _run("add", "a.py", "new.py", cwd=tmp_path)

    monkeypatch.chdir(tmp_path)
    return tmp_path


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_fixture_really_stages_both_changes(repo: Path):
    """🔴 전제 — 저장소가 정말 수정 1건 + 신규 1건을 스테이징했는가."""
    status = _run("diff", "--cached", "--name-status", cwd=repo)
    assert "M\ta.py" in status and "A\tnew.py" in status, (
        f"픽스처가 기대한 상태가 아니다:\n{status}"
    )


def test_head_and_index_really_differ(repo: Path):
    """🔴 전제 — HEAD 와 index 가 실제로 다른가. 같다면 이 파일 전체가 공허하다."""
    head = _run("show", "HEAD:a.py", cwd=repo)
    index = _run("show", ":a.py", cwd=repo)
    assert head != index, "HEAD 와 index 가 같다 — 픽스처가 변경을 스테이징하지 않았다"
    assert 'eval("2")' in index and 'eval("2")' not in head


# ─── 결함 ────────────────────────────────────────────────────────────────────


def test_staged_analyses_the_staged_content_not_head(repo: Path):
    """🔴 수정 파일의 분석 대상이 **스테이징된 내용**이다.

    HEAD 판을 분석하면 방금 추가한 코드가 정적분석을 통째로 빠져나간다 —
    커밋 전 검사의 존재 이유가 사라진다.
    """
    files = {f.filename: f for f in get_diff_files(staged=True)}
    assert "a.py" in files, f"수정 파일을 못 찾았다: {sorted(files)}"

    content = files["a.py"].content
    assert 'eval("2")' in content, (
        "스테이징한 코드가 분석 대상에 없다 — HEAD(변경 전) 내용을 읽고 있다. "
        f"실제 content={content!r}"
    )


def test_staged_new_file_is_not_analysed_as_empty(repo: Path):
    """🔴 신규 파일이 빈 문자열로 분석되지 않는다.

    `git show HEAD:new.py` 는 실패하므로 content 가 `""` 가 되고, 새 파일 전체가
    «검사했는데 아무것도 없었다» 로 기록된다.
    """
    files = {f.filename: f for f in get_diff_files(staged=True)}
    assert "new.py" in files, f"신규 파일을 못 찾았다: {sorted(files)}"

    content = files["new.py"].content
    assert content.strip(), (
        "신규 파일의 content 가 비었다 — `HEAD:` 조회 실패를 «내용 없음» 으로 기록한다"
    )
    assert "z = 3" in content


# ─── 대조군 — staged 가 아닌 경로는 그대로 ────────────────────────────────────


def test_non_staged_path_reads_head_not_the_index(repo: Path):
    """대조군 — `--staged` 가 **아니면** HEAD 를 읽는다. 이 축까지 index 로 바꾸면 안 된다.

    🔴 이 대조군의 첫 판은 커밋 직후를 봤는데, 그 상태에서는 HEAD 와 index 가
    **같아서** 「항상 index」 뮤테이션을 못 잡았다(실측: 35건 전부 초록).
    둘이 갈리는 상태 — 커밋한 뒤 **다시 다른 것을 스테이징** — 를 만들어야 유효하다.
    """
    # ① 스테이징된 것을 커밋한다 (HEAD == index)
    _run("commit", "-qm", "second", cwd=repo)
    # ② 커밋 뒤 **다른** 내용을 스테이징한다 -> HEAD != index
    (repo / "a.py").write_text("x = 1" + chr(10) + "STAGED_ONLY = 1" + chr(10),
                                encoding="utf-8")
    _run("add", "a.py", cwd=repo)

    head = _run("show", "HEAD:a.py", cwd=repo)
    index = _run("show", ":a.py", cwd=repo)
    assert head != index, "픽스처가 HEAD 와 index 를 갈라놓지 못했다 — 대조군이 공허하다"

    files = {f.filename: f for f in get_diff_files(base="HEAD~1", staged=False)}
    assert "a.py" in files
    content = files["a.py"].content
    assert "STAGED_ONLY" not in content, (
        "비-staged 경로가 index 를 읽는다 — `--base` 비교가 망가진다. "
        f"content={content!r}"
    )
    assert 'eval("2")' in content, (
        f"비-staged 경로가 HEAD 내용을 못 읽는다: {content!r}"
    )


# ─── 리비전 표기 — `:<path>` 는 오파싱된다 ────────────────────────────────────


def test_staged_uses_the_explicit_stage_form():
    """🔴 index 조회는 `:0:<path>` 여야 한다 — 맨 `:<path>` 는 오파싱된다.

    git 은 `:` 뒤의 `[0-3]:` 를 **스테이지 번호**로 먹는다. 그래서 경로가
    `0:weird/f.py` 면 `:0:weird/f.py` 로 읽혀 실제로는 `weird/f.py` 를 찾는다(실측):

        git show ":0:weird/f.py"    -> fatal: path 'weird/f.py' does not exist
        git show ":0:0:weird/f.py"  -> fatal: path '0:weird/f.py' does not exist

    앞은 경로를 **잃었고** 뒤는 보존했다. `:/text` 도 커밋 메시지 검색이라 같은 부류다.
    Windows 는 `:` 파일명을 못 만들지만 CI·배포는 Linux 다.

    동작 테스트로는 이 성질을 잡을 수 없다(정상 경로는 둘 다 통과한다) — 그래서
    호출 인자를 직접 본다.
    """
    import inspect  # noqa: PLC0415

    from src.cli import git_diff  # noqa: PLC0415

    src = inspect.getsource(git_diff._collect_file)
    assert '":0:"' in src, (
        "index 조회가 명시 스테이지 형태(`:0:`)가 아니다 — 콜론이 든 경로가 오파싱된다"
    )


def test_the_stage_prefix_really_preserves_a_colon_path(tmp_path: Path):
    """🔴 계기 자기검증 — `:0:` 가 정말 경로를 보존하는가.

    보존하지 않는다면 위 단언이 허구를 지키는 것이 된다. 파일을 만들 필요는 없다 —
    git 의 **에러 메시지가 어느 경로를 찾았는지** 말해 준다.
    """
    _run("init", "-q", ".", cwd=tmp_path)
    tricky = "0:weird/f.py"

    bare = subprocess.run(  # nosec B603 B607
        ["git", "show", ":" + tricky], cwd=tmp_path, capture_output=True, text=True, check=False,
    ).stderr
    staged = subprocess.run(  # nosec B603 B607
        ["git", "show", ":0:" + tricky], cwd=tmp_path, capture_output=True, text=True, check=False,
    ).stderr

    assert "weird/f.py" in bare and tricky not in bare, (
        f"맨 `:` 형태가 경로를 잃지 않는다 — 전제가 바뀌었다: {bare!r}"
    )
    assert tricky in staged, (
        f"`:0:` 형태가 경로를 보존하지 않는다: {staged!r}"
    )
