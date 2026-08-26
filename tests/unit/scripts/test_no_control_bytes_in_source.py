"""소스에 박힌 제어 바이트 — `\b` 가 백스페이스가 되어 정규식이 죽는다 (감사 B1·B2, #1519).

🔴 실측. 두 파일의 정규식이 `\b`(바이트 `5c 62`) 대신 **리터럴 백스페이스 0x08** 을
담고 있었다. raw string 안이라도 실제 0x08 바이트는 0x08 그대로 컴파일된다:

    scripts/check_e2e_scope.py:45
      re.compile(r"\x08errors?\x08", re.IGNORECASE)      -> 어떤 텍스트도 못 맞춘다
    tests/unit/scripts/test_claim_review_trace.py:852
      re.compile(r"\x08(?:live|test)_[A-Za-z0-9_]{35}\x08") -> 식별자를 못 맞춘다

무엇이 죽었나:

| 파일 | 죽은 것 |
|---|---|
| `check_e2e_scope.py` | collection error 를 fail-closed 로 잡는 **2층**. `parse_collected('2 tests collected, 1 error')` 가 `None` 이 아니라 `2` 를 돌려줬다(fail-open) |
| `test_claim_review_trace.py` | TruffleHog Lob 오탐(`test_` + 35자 식별자) **재발 방지 가드** |

원인은 셸/heredoc 이 `\b` 를 백스페이스 이스케이프로 해석해 파일에 쓴 것이다.
exit 0 이고 파이썬도 조용히 컴파일하므로 **어디에서도 발화하지 않는다.**

그래서 고치는 것만으로는 부족하다 — 같은 경로로 다시 들어온다. 이 파일은
**소스에 제어 바이트가 들어오는 것 자체**를 막는다.

A literal backspace where `\b` was intended compiles silently and never matches.
"""
from __future__ import annotations

import io
from pathlib import Path

# 탭(0x09) · LF(0x0a) · CR(0x0d) 는 정상 텍스트다. 나머지 C0 제어문자는 소스에 올 이유가 없다.
# Tab/LF/CR are legitimate; the rest of the C0 range is not.
_FORBIDDEN = bytes(b for b in range(0x00, 0x20) if b not in (0x09, 0x0A, 0x0D))

# 🔴 범위는 「정규식이 살 수 있는 모든 곳」이다. 첫 판은 src/tests/scripts/alembic/e2e/.claude
# 만 봤는데, Grok 이 사각 셋을 짚었다(실측):
#   · 리포 **루트** — `.pre-commit-config.yaml` 의 pygrep 훅이 정규식을 담는다
#   · `.github/` — `ci.yml` 의 `grep -E` 인자
#   · `docs/` — `secret-prevention.md` 의 `grep -oE`
#   · `.mjs` — `.claude/workflows/*.mjs` (디렉토리는 봤는데 확장자를 안 봤다)
# 좁은 범위는 초록이 아니라 '안 쟀음' 이다.
_SCAN_ROOTS = ("src", "tests", "scripts", "alembic", "e2e", ".claude", ".github", "docs")
_SCAN_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".html", ".js", ".mjs", ".cjs",
                  ".css", ".toml", ".cfg", ".ini", ".sh", ".txt"}
_ROOT_FILES = (".pre-commit-config.yaml", "Makefile", "pyproject.toml", "setup.cfg",
               "railway.toml", "nixpacks.toml", "alembic.ini", ".flake8", ".gitignore")
_SKIP_PARTS = ("__pycache__", "node_modules", ".git/", "worktrees", "/venv", "site-packages")


def _source_files() -> list[Path]:
    out: list[Path] = []
    for root in _SCAN_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in _SCAN_SUFFIXES:
                continue
            if any(s in p.as_posix() for s in _SKIP_PARTS):
                continue
            out.append(p)
    # 리포 루트의 설정 파일 — 디렉토리 순회로는 안 잡힌다
    out.extend(Path(name) for name in _ROOT_FILES if Path(name).is_file())
    for p in Path(".").glob("*.md"):
        out.append(p)
    return out


def _hits() -> list[tuple[str, int, int]]:
    """(파일, 줄번호, 바이트값) — 소스에 박힌 제어 바이트."""
    found: list[tuple[str, int, int]] = []
    for p in _source_files():
        try:
            raw = io.open(p, "rb").read()
        except OSError:
            continue
        if not any(bytes([b]) in raw for b in _FORBIDDEN):
            continue
        for lineno, line in enumerate(raw.split(b"\n"), start=1):
            for b in _FORBIDDEN:
                if bytes([b]) in line:
                    found.append((p.as_posix(), lineno, b))
    return found


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_scan_actually_reads_files():
    """🔴 스캔 범위가 비면 이 가드는 아무것도 검사하지 않는다."""
    files = _source_files()
    assert len(files) > 500, (
        f"소스 파일을 {len(files)}개만 찾았다 — 스캔 범위가 좁아졌다(초록이 아니라 '안 쟀음')"
    )


def test_the_scan_covers_the_places_regexes_actually_live():
    """🔴 정규식을 담는 알려진 지점이 범위 안인지 — 좁아지면 red.

    첫 판은 이 셋을 전부 놓쳤다(Grok 지적, 실측): 리포 루트의 pre-commit 설정,
    `.github/workflows`, `docs/runbooks`. 셋 다 정규식을 담는다.
    """
    scanned = {p.as_posix() for p in _source_files()}
    expected = [
        ".pre-commit-config.yaml",
        ".github/workflows/ci.yml",
        "docs/runbooks/secret-prevention.md",
    ]
    missing = [e for e in expected if Path(e).is_file() and e not in scanned]
    assert not missing, (
        f"정규식이 사는 지점이 스캔 범위 밖이다: {missing} — "
        "_SCAN_ROOTS / _SCAN_SUFFIXES / _ROOT_FILES 를 넓혀라"
    )


def test_the_detector_finds_a_planted_control_byte(tmp_path, monkeypatch):
    """🔴 탐지기가 실제로 0x08 을 잡는가 — 못 잡으면 위 단언이 공허하다."""
    planted = tmp_path / "planted.py"
    planted.write_bytes(b'pat = re.compile(r"\x08word\x08")\n')

    monkeypatch.setitem(globals(), "_source_files", lambda: [planted])
    hits = _hits()
    assert hits and hits[0][2] == 0x08, f"심어 둔 0x08 을 못 잡는다: {hits}"


# ─── 가드 ────────────────────────────────────────────────────────────────────


def test_no_control_bytes_in_source():
    """🔴 소스에 C0 제어 바이트가 없다 — `\b` 가 백스페이스로 저장되는 것을 막는다.

    발화하면 거의 항상 셸/heredoc 이 이스케이프를 먹은 것이다. 정규식이라면
    `\b`(단어 경계)를 쓰려던 자리다.
    """
    hits = _hits()
    formatted = [f"{f}:{ln} (0x{b:02x})" for f, ln, b in hits]
    assert not hits, (
        "소스에 제어 바이트가 박혔다 — 정규식의 `\b` 가 백스페이스(0x08)로 저장되면 "
        "패턴이 **어떤 텍스트도 못 맞추고** 조용히 통과한다. "
        f"해당 지점: {formatted}"
    )
