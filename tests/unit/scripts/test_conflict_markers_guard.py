"""병합 충돌 마커 가드 회귀 테스트.

Regression tests for the committed-conflict-marker guard.

🔴 **왜 생겼나 (2026-08-12 실사고)**: `README.md:21-25` 과 `README.ko.md:21-25` 에
`<<<<<<< HEAD` / `>>>>>>> origin/main` 이 **커밋된 채** main 에 있었다(`#1328` 이래).
공개 README 가 깨진 상태로 렌더링됐는데 어떤 가드도 잡지 않았고, 더 나쁘게는
`check_docs_sync.py --fix` 가 **충돌 블록 안의 줄을 갱신**하며 마커를 매번 살려 냈다.
Committed conflict markers survived on main because no guard looked for them, and the
badge autofixer kept rewriting a line *inside* the conflict block.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GUARD_PATH = _REPO_ROOT / "scripts" / "check_conflict_markers.py"

# 🔴 마커 리터럴을 이 파일 **줄 맨 앞**에 두지 않는다 — 그러면 이 테스트 파일 자신이
#    스캔에 걸려 가드가 영구 red 가 된다(가드가 자기 테스트를 죽이는 형태).
# Build markers at runtime; a literal at line start would make this file trip the guard.
_OPEN = "<" * 7
_MID = "=" * 7
_CLOSE = ">" * 7


def _load_guard():
    spec = importlib.util.spec_from_file_location("check_conflict_markers", _GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_guard_script_exists():
    """가드 파일이 실재해야 한다 — dangling 이름은 집행자가 아니다."""
    assert _GUARD_PATH.is_file(), f"가드 스크립트 없음: {_GUARD_PATH}"


def test_repo_has_no_committed_conflict_markers():
    """🔴 본 회귀 가드 — 추적 파일 어디에도 충돌 마커가 없어야 한다."""
    guard = _load_guard()
    hits = guard.scan_repo(_REPO_ROOT)
    assert hits == [], "커밋된 충돌 마커 발견:\n" + "\n".join(
        f"  {rel}:{no}: {line[:60]}" for rel, no, line in hits
    )


def test_scan_is_not_vacuous():
    """anti-vacuity — 스캔 대상이 조용히 비면 '초록' 이 아니라 '안 쟀음' 이다.

    실측 2026-08-12: 추적 파일 1089건. 하한은 보수적으로 500.
    """
    guard = _load_guard()
    files = guard.tracked_text_files(_REPO_ROOT)
    assert len(files) >= 500, f"스캔 대상이 {len(files)}건 — 범위가 조용히 좁아졌다"


@pytest.mark.parametrize(
    "marker",
    [
        f"{_OPEN} HEAD",
        f"{_CLOSE} origin/main",
        # 🔴 들여쓴 실충돌 — Python·YAML·JS 코드 블록 안에서 가장 흔한 형태인데
        #    컬럼 0 만 보던 초판이 **전부 놓쳤다**(Grok `019ff301`).
        f"    {_OPEN} HEAD",
        f"\t{_CLOSE} feature",
        # 공백 없는 형태(손편집·일부 머지 도구).
        f"{_OPEN}HEAD",
    ],
)
def test_detects_open_and_close_markers(tmp_path, marker):
    """여는·닫는 마커를 **들여쓰기·공백 유무와 무관하게** 잡는다."""
    guard = _load_guard()
    target = tmp_path / "doc.md"
    target.write_text(f"before\n{marker}\nafter\n", encoding="utf-8")
    hits = guard.scan_paths([target], tmp_path)
    assert len(hits) == 1, f"마커 {marker!r} 미탐지"
    assert hits[0][1] == 2, "행 번호는 1-기반 실측값이어야 한다"


def test_detects_a_real_indented_python_conflict(tmp_path):
    """실제 형태 — 들여쓴 파이썬 충돌 블록 전체(여는 2 + 닫는 1 축)."""
    guard = _load_guard()
    target = tmp_path / "mod.py"
    target.write_text(
        "def f():\n"
        f"    {_OPEN} HEAD\n"
        "    return 1\n"
        f"    {_MID}\n"
        "    return 2\n"
        f"    {_CLOSE} feature\n",
        encoding="utf-8",
    )
    hits = guard.scan_paths([target], tmp_path)
    assert [no for _, no, _ in hits] == [2, 6], f"들여쓴 충돌 미탐지: {hits}"


def test_bare_separator_line_is_not_a_marker(tmp_path):
    """🔴 `=======` 단독은 마커가 아니다 — 마크다운 setext 제목 밑줄이 그 형태다.

    부호를 넓히면 정상 문서가 red 가 되고, 저자는 가드를 끄게 된다(과차단이 가드를 죽인다).
    A bare `=======` is a setext heading underline; flagging it would red normal docs.
    """
    guard = _load_guard()
    target = tmp_path / "doc.md"
    target.write_text(f"제목\n{_MID}\n본문\n", encoding="utf-8")
    assert guard.scan_paths([target], tmp_path) == []


def test_clean_file_has_no_hits(tmp_path):
    """대조군 — 정상 파일은 0건 (탐지기가 무엇이든 잡는 것이 아님을 고정)."""
    guard = _load_guard()
    target = tmp_path / "clean.md"
    target.write_text("# 제목\n\n본문\n", encoding="utf-8")
    assert guard.scan_paths([target], tmp_path) == []


def test_guard_exits_nonzero_on_dirty_tree(tmp_path):
    """🔴 **배선** — 순수 함수가 옳은 것과 CLI 가 red 를 내는 것은 다른 문제다.

    실제 git 저장소를 만들어 마커를 커밋하고, 가드를 **subprocess 로 호출**해 종료코드를 본다.
    Wiring: a correct pure function proves nothing about the entry point's exit code.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    dirty = tmp_path / "broken.md"
    dirty.write_text(f"a\n{_OPEN} HEAD\nb\n", encoding="utf-8")
    subprocess.run(["git", "add", "broken.md"], cwd=tmp_path, check=True)
    proc = subprocess.run(
        [sys.executable, str(_GUARD_PATH)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode != 0, f"더러운 트리인데 exit 0 이다:\n{proc.stdout}{proc.stderr}"


def test_guard_is_wired_into_push_gate():
    """🔴 **배선** — `pre_push_gate` 의 실제 튜플에 등재됐는가 (산문 grep 아님)."""
    spec = importlib.util.spec_from_file_location(
        "pre_push_gate", _REPO_ROOT / "scripts" / "pre_push_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "check_conflict_markers.py" in mod._INTEGRITY, (  # pylint: disable=protected-access
        "pre_push_gate._INTEGRITY 에 미등재 — 로컬 게이트가 이 축을 돌리지 않는다"
    )
