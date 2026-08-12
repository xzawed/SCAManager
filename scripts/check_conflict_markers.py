#!/usr/bin/env python3
"""커밋된 병합 충돌 마커 차단 — 추적 파일 전수 스캔.

Fail when a merge-conflict marker is committed into a tracked file.

🔴 **왜 필요한가 (2026-08-12 실측)**: `README.md:21-25` · `README.ko.md:21-25` 에
`<<<<<<< HEAD` / `>>>>>>> origin/main` 이 **커밋된 채** main 에 있었다(`#1328` 이래).
공개 README 가 깨진 채 렌더링됐고, 리포의 어떤 가드도 그것을 보지 않았다.

🔴 더 나쁜 것은 **자동 수정기가 그 상태를 유지시켰다**는 점이다 — `check_docs_sync.py --fix`
가 Tests 배지를 갱신할 때 **충돌 블록 안쪽의 줄**을 고쳐 썼다. 즉 파생 도구가 매번 마커를
살려 내면서 "정합 ✅" 를 인쇄했다. 값은 맞고 파일은 깨진, 전형적인 observer-lie 다.
The badge autofixer kept rewriting a line *inside* the conflict block and reported "in sync".

**판정 술어**: 여는 마커(`<`×7)와 닫는 마커(`>`×7)만 본다.
🔴 가운데 구분선(`=`×7)은 **일부러 제외**한다 — 마크다운 setext 제목 밑줄이 정확히 그 형태라
포함하면 정상 문서가 red 가 되고, 저자는 가드를 끄는 쪽을 택하게 된다(과차단이 가드를 죽인다).
Only the open/close markers are matched; a bare `=======` is a setext heading underline.

stdlib 전용. 마커 0건이면 exit 0.
"""
import io
import re
import subprocess  # nosec B404 — git ls-files 호출 전용(사용자 입력 없음)
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 🔴 마커 리터럴을 소스 **줄 맨 앞**에 두지 않는다 — 그러면 이 파일 자신이 스캔에 걸려
#    가드가 자기를 red 로 만든다. 수량자로 표현해 리터럴 자체를 만들지 않는다.
# Express markers as quantifiers so this source never contains a literal marker at line start.
# 🔴 **선행 공백을 허용한다** (Grok claim-review `019ff301` 적발). 컬럼 0 만 보면
#    들여쓴 코드 블록 안의 실충돌(Python·YAML·JS 에서 가장 흔한 형태)을 **전부 놓친다** —
#    README 사고와 같은 클래스인데 한 형태만 잡고 "봉인" 이라 부를 뻔했다.
#    `<<<<<<<HEAD`(공백 없음)도 손편집·일부 도구에서 나오므로 뒤 공백을 강제하지 않는다.
# Allow leading whitespace: indented conflicts inside code blocks are the common real case.
_MARKER = re.compile(r"^[ \t]*(?:<{7}(?!<)|>{7}(?!>))")

# 텍스트로 읽지 않는 확장자 — 이미지·폰트·아카이브 등.
_BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svgz",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pdf", ".zip", ".gz", ".tar", ".whl", ".pyc", ".db", ".sqlite", ".sqlite3",
})


def tracked_text_files(root: Path) -> list[Path]:
    """`git ls-files` 로 **추적 파일만** 수집한다 (텍스트로 읽을 수 있는 것만).

    🔴 rglob 이 아니라 git 추적 목록을 쓴다 — `.gitignore` 된 로컬 산출물이 섞이면
    가드가 **로컬에서만 red** 가 되고 CI 는 그 파일을 보지도 못한다(`#1328` 이 같은 함정을
    겪었다). Use git's index, not rglob: ignored local files would make this red locally only.
    """
    proc = subprocess.run(  # nosec B603 B607 — 고정 인자, 셸 미경유
        ["git", "ls-files", "-z"],
        cwd=root, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        return []
    out: list[Path] = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="replace")
        path = root / rel
        if path.suffix.lower() in _BINARY_SUFFIXES or not path.is_file():
            continue
        out.append(path)
    return out


def scan_paths(paths: list[Path], root: Path) -> list[tuple[str, int, str]]:
    """(상대경로, 1-기반 행번호, 줄) 목록. 마커가 없으면 빈 목록."""
    hits: list[tuple[str, int, str]] = []
    for path in paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data:  # 바이너리 — 확장자로 못 거른 것까지 방어
            continue
        text = data.decode("utf-8", errors="replace")
        for no, line in enumerate(text.splitlines(), 1):
            if _MARKER.match(line):
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    rel = path.as_posix()
                hits.append((rel, no, line))
    return hits


def scan_repo(root: Path) -> list[tuple[str, int, str]]:
    """추적 파일 전수 스캔."""
    return scan_paths(tracked_text_files(root), root)


def main() -> int:
    root = Path.cwd()
    files = tracked_text_files(root)
    hits = scan_repo(root)
    print("=== 병합 충돌 마커 점검 / Conflict Marker Check ===\n")
    if not files:
        # 🔴 스캔 대상이 0이면 '초록' 이 아니라 '안 쟀음' 이다 — fail-closed.
        print("❌ 추적 파일을 하나도 읽지 못했다 — git 저장소가 아니거나 범위가 비었다.")
        return 1
    if hits:
        print(f"❌ 커밋된 충돌 마커 {len(hits)}건:\n")
        for rel, no, line in hits:
            print(f"   {rel}:{no}  {line[:70]}")
        print("\n   해결: 해당 블록을 올바른 한쪽으로 정리하고 마커 3줄을 제거한다.")
        print("   🔴 파생 도구(`check_docs_sync.py --fix`)는 블록 **안쪽**을 고칠 수 있으므로,")
        print("      값이 맞아 보여도 파일은 깨진 상태일 수 있다.")
        return 1
    print(f"✅ 충돌 마커 0건 — 추적 파일 {len(files)}건 스캔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
