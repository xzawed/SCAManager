"""Git Bash(Git for Windows) 가 여는 경로를 Windows 경로로 바꾼다 — 막는 훅 둘(credential · 게시 전 검사)이 함께 쓴다.
Translate paths the way Git Bash opens them into Windows paths; shared by both blocking hooks (ledger #1940 M06 P1-24).

Windows 의 Python 은 `/c/x` 를 «지금 드라이브의 \\c\\x» 로, `/tmp/x` 를 «지금 드라이브의 \\tmp\\x» 로 연다(3.13 부터는 상대
경로로 보고 작업 폴더의 드라이브에 붙인다). Git Bash 는 같은 글자를 `C:\\x` · 마운트된 임시 폴더로 연다 — 그래서 훅이 정직한
명령을 막거나(없는 폴더), 다른 파일을 재고 통과시켰다(작업 드라이브에 `\\tmp` 가 따로 있을 때). Windows 밖에서는 그대로다.
On Windows Python opens `/c/x` and `/tmp/x` under the current drive; Git Bash opens `C:\\x` and its mounted temp folder.
"""
from __future__ import annotations

import functools
import os
import posixpath
import re
import subprocess  # nosec B404 — `cygpath -m /<맨 위 폴더>` 만 / fixed-argument cygpath calls only

_ON_WINDOWS = os.name == "nt"
_DRIVE = re.compile(r"/([A-Za-z])(?=/|$)")


@functools.lru_cache(maxsize=32)
def _mount(top: str) -> str | None:
    """Git Bash 의 `/<top>` 이 가리키는 폴더(`cygpath -m /<top>` — fstab 을 따른다 · `top` 이 비면 `/`). 못 물으면 None.
    The folder Git Bash calls `/<top>` (honours fstab), or None when cygpath cannot be asked."""
    try:
        done = subprocess.run(["cygpath", "-m", "/" + top], capture_output=True, text=True, timeout=5,  # nosec B603 B607
                              check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    folder = done.stdout.strip().rstrip("/")
    return folder if done.returncode == 0 and folder else None


def git_bash_to_windows(path: str) -> str | None:
    """Bash 가 여는 경로를 Windows 경로로 — 바꿀 것이 없으면 그대로, 어디를 여는지 모르면 None(호출자가 막는 쪽으로).

    `/c/x` → `C:/x` · `/dev/null` → `NUL` · 그 밖의 `/dev/…` · `/proc/…` → None(장치 · 가상 파일) · 그 밖의 `/<맨 위>/…` →
    그 마운트(`cygpath -m /<맨 위>` — `/tmp` 는 사용자 임시 폴더, 나머지는 Git 설치 뿌리 아래 · 못 물으면 None). 바꾸기 전에
    Cygwin 처럼 `\\` 를 구분자로 보고, 빗금 셋 이상을 하나로, `..` 를 글자로 접는다 — `..` 는 마운트 경계를 넘는다(Grok 반례).
    UNC(빗금 둘 `//server/…`) · 드라이브 경로 · 상대 경로 · Windows 밖은 그대로다.
    Bash path → Windows path; unchanged when nothing applies, None when the target is unknown (callers fail closed).
    """
    if not _ON_WINDOWS or not path.startswith("/"):
        return path
    path = path.replace("\\", "/")
    if path.startswith("//") and not path.startswith("///"):
        return path
    path = posixpath.normpath("/" + path.lstrip("/"))
    drive = _DRIVE.match(path)
    if drive:
        return f"{drive.group(1).upper()}:{path[2:] or '/'}"
    if path == "/dev/null":
        return "NUL"
    if path in ("/dev", "/proc") or path.startswith(("/dev/", "/proc/")):
        return None
    top, _, rest = path[1:].partition("/")
    folder = _mount(top)
    if folder is None:
        return None
    return folder + ("/" + rest if rest else "")
