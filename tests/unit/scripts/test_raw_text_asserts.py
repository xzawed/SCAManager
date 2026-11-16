"""PR 이 새로 쓴 «원문 글자 포함» 단언을 막는다 — 바뀐 줄 래칫 (회고 원장 L12 P2-52 · 사용자 11-16 결정).

## 사고

B8 floor(`check_guard_fail_open.py`)는 파일 단위다 — 파일 어디서든 구조 도구를 한 번 부르면 그 파일의 맨
`assert "글자" in text` 가 전부 지나간다. 회고가 잰 바로는 파일을 읽는 시험 206개가 모두 통과했고, 그중 원문 위에서
글자를 찾는 단언이 약 50파일 120건이었다. 그런 단언은 주석 · docstring · 산문이 통과시킨다(#1136 클래스).

## 이 파일이 잠그는 것

1. 막는다 — 단언의 `"글자" in X` 에서 X 가 파일 원문(읽기 호출 · 원문을 그대로 두는 변형 · 대입 · 함수 · 픽스처)일 때.
2. 막지 않는다 — 구조를 읽은 값(주석 제거 · 파서), 원문이 아닌 값(목록 · HTTP 응답), 바뀌지 않은 줄, 면제 주석이 붙은 줄.
3. 문서화한 한계 — 이 가드가 따라가지 않는 원문 보존 변형은 정말 못 본다(목록이 거짓이 되지 않게).
4. 배선 — CI 의 lint-changed-tests 잡과 로컬 게이트가 이 가드를 부른다.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 — 격리된 임시 리포와 이 리포의 가드만
import sys
from pathlib import Path

import pytest
import yaml

import scripts.check_raw_text_asserts as mod
from tests.unit.scripts._wiring_shape import invokes

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_raw_text_asserts.py"


def _flagged(src: str, added: set[int] | None = None) -> list[int]:
    """그 소스에서 막힌 단언의 줄 — `added` 가 없으면 모든 줄을 이 PR 이 쓴 것으로 본다."""
    lines = set(range(1, src.count("\n") + 2)) if added is None else added
    return [line for line, _text in mod.violations_in(src, lines)]


# ── 1. 막는다 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name, src", [
    ("모듈 최상위 원문", 'TEXT = open("x").read()\ndef test_a():\n    assert "alpha" in TEXT\n'),
    ("함수 안 read_text", 'def test_a(p):\n    text = p.read_text(encoding="utf-8")\n    assert "alpha" in text\n'),
    ("바로 읽은 원문", 'def test_a(p):\n    assert "alpha" in p.read_text()\n'),
    ("read_bytes 를 decode", 'def test_a(p):\n    raw = p.read_bytes().decode("utf-8")\n    assert "alpha" in raw\n'),
    ("lower 를 거친 원문", 'def test_a(p):\n    text = p.read_text().lower()\n    assert "alpha" in text\n'),
    ("자른 조각", 'def test_a(p):\n    text = p.read_text()\n    part = text[3:90]\n    assert "alpha" in part\n'),
    ("partition 의 조각", 'def test_a(p):\n    head, _, tail = p.read_text().partition("x")\n    assert "alpha" in tail\n'),
    ("split 의 한 조각", 'def test_a(p):\n    block = p.read_text().split("- id: x", 1)[1]\n    assert "alpha" in block\n'),
    ("with open 의 read", 'def test_a(p):\n    with open(p) as fh:\n        text = fh.read()\n    assert "alpha" in text\n'),
    ("원문을 돌려주는 함수", 'def _src():\n    return open("x").read()\ndef test_a():\n    assert "alpha" in _src()\n'),
    ("원문 픽스처", 'import pytest\n@pytest.fixture\ndef css():\n    return open("x").read()\ndef test_a(css):\n    assert "alpha" in css\n'),
    ("f-문자열 글자", 'TEXT = open("x").read()\ndef test_a(k):\n    assert f"{k}-alpha" in TEXT\n'),
    ("not in", 'TEXT = open("x").read()\ndef test_a():\n    assert "alpha" not in TEXT\n'),
    ("and 로 묶은 단언", 'TEXT = open("x").read()\ndef test_a():\n    assert "a" in TEXT and "b" in TEXT\n'),
])
def test_a_raw_text_substring_assert_is_flagged(name, src):
    assert _flagged(src), f"{name}: 막지 못했다"


# ── 2. 막지 않는다 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("name, src", [
    ("주석을 지운 본문", 'def test_a(p):\n    css = strip_css_comments(p.read_text())\n    assert "alpha" in css\n'),
    ("파서를 거친 값", 'import json\ndef test_a(p):\n    doc = json.loads(p.read_text())\n    assert "alpha" in doc\n'),
    ("목록 소속", 'NAMES = ["alpha", "beta"]\ndef test_a():\n    assert "alpha" in NAMES\n'),
    ("HTTP 응답", 'def test_a(client):\n    body = client.get("/").text\n    assert "alpha" in body\n'),
    ("왼쪽이 리터럴이 아님", 'TEXT = open("x").read()\ndef test_a(k):\n    assert k in TEXT\n'),
    ("단언이 아닌 판정", 'TEXT = open("x").read()\ndef test_a():\n    found = "alpha" in TEXT\n    assert found\n'),
    ("지역 이름이 원문 전역을 가림", 'TEXT = open("x").read()\ndef test_a():\n    TEXT = "alpha beta"\n    assert "alpha" in TEXT\n'),
])
def test_structured_or_non_text_values_are_not_flagged(name, src):
    assert _flagged(src) == [], f"{name}: 막지 말아야 할 것을 막았다"


def test_only_lines_this_pr_wrote_are_judged():
    """🔴 래칫 — 이미 있던 단언은 그 줄을 고칠 때만 본다(기존 건수를 한 번에 고치게 만들지 않는다)."""
    src = 'TEXT = open("x").read()\ndef test_a():\n    assert "alpha" in TEXT\n    assert "beta" in TEXT\n'
    assert _flagged(src, added={4}) == [4]
    assert _flagged(src, added={1, 2}) == []


def test_a_reviewed_line_is_exempt_but_only_that_line():
    src = ('TEXT = open("x").read()\ndef test_a():\n'
           '    assert "alpha" in TEXT  # fail-open-reviewed: 원문 글자 그 자체가 계약이다\n'
           '    assert "beta" in TEXT\n')
    assert _flagged(src) == [4]


def test_the_exemption_must_be_a_real_comment():
    """문자열 안에 표지를 적은 것은 면제가 아니다 — 주석 토큰만 인정한다."""
    src = ('TEXT = open("x").read()\ndef test_a():\n'
           '    assert "alpha # fail-open-reviewed: x" in TEXT\n')
    assert _flagged(src) == [3]


# ── 3. 문서화한 한계 — 따라가지 않는 원문 보존 변형 ─────────────────────────

# witness-corpus: 원문을 그대로 두는데 이 가드가 따라가지 않는 변형 — 리포 시험에 쓰인 꼴(ui · gate 시험)
_KNOWN_GAPS = {
    "join": 'TEXT = open("x").read()\nNORM = " ".join(TEXT.split())\ndef test_a():\n    assert "a b" in NORM\n',
    "dedent": 'import textwrap\nTEXT = textwrap.dedent(open("x").read())\ndef test_a():\n    assert "a" in TEXT\n',
    "removeprefix": 'TEXT = open("x").read().removeprefix("#")\ndef test_a():\n    assert "a" in TEXT\n',
}


@pytest.mark.parametrize("shape", sorted(_KNOWN_GAPS))
def test_the_documented_gaps_are_really_gaps(shape):
    """docstring 이 «못 본다» 고 적은 꼴은 정말 못 본다 — 고쳐서 보게 되면 이 목록과 docstring 을 함께 고친다."""
    assert _flagged(_KNOWN_GAPS[shape]) == [], f"{shape}: 이제 보인다 — 한계 목록을 고칠 것"
    assert shape in (mod.__doc__ or ""), f"{shape}: 모듈 docstring 의 한계 목록에 없다"


# ── 통합 — 임시 리포의 실제 diff ──────────────────────────────────────────


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        _git(root, "add", rel)
    _git(root, "commit", "-q", "--allow-empty", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _run(root: Path, base: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(_SCRIPT), base, "HEAD"], cwd=str(root), env={**os.environ},
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


_OLD = 'TEXT = open("x").read()\ndef test_old():\n    assert "alpha" in TEXT\n'


@pytest.fixture()
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, {"tests/unit/test_old.py": _OLD, "README.md": "x\n"}, "base")
    return tmp_path, base


def test_a_new_violation_blocks_and_names_its_line(repo):
    root, base = repo
    _commit(root, {"tests/unit/test_new.py": _OLD.replace("test_old", "test_new")}, "new")
    proc = _run(root, base)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    listed = [line.split()[1] for line in proc.stdout.splitlines() if line.startswith("   - ")]
    assert listed == ["tests/unit/test_new.py:3"], proc.stdout


def test_an_untouched_old_violation_does_not_block(repo):
    root, base = repo
    _commit(root, {"tests/unit/test_old.py": _OLD + "def test_more():\n    assert 1\n"}, "more")
    proc = _run(root, base)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_editing_an_old_violation_line_makes_it_new(repo):
    """«기존 건은 손댈 때» — 그 줄을 고치면 새로 쓴 것이다."""
    root, base = repo
    _commit(root, {"tests/unit/test_old.py": _OLD.replace('"alpha"', '"alpha2"')}, "edit")
    assert _run(root, base).returncode == 1


def test_an_unparseable_changed_test_is_red_not_skipped(repo):
    """🔴 못 재면 red — 구문이 깨진 시험은 «위반 없음» 이 아니다."""
    root, base = repo
    _commit(root, {"tests/unit/test_broken.py": "def test_x(:\n"}, "broken")
    assert _run(root, base).returncode == 1


# ── 4. 배선 ───────────────────────────────────────────────────────────────


def test_ci_runs_the_guard_on_the_pr_range():
    ci = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = ci["jobs"]["lint-changed-tests"]["steps"]
    runs = [step.get("run", "") for step in steps]
    hits = [run for run in runs if invokes(run, "scripts/check_raw_text_asserts.py")]
    assert len(hits) == 1, runs
    assert "pull_request.base.sha" in hits[0], hits[0]


def test_the_local_gate_runs_it_as_a_diff_scoped_guard():
    sys.path.insert(0, str(_ROOT / "scripts"))
    import pre_push_gate  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    assert "check_raw_text_asserts.py" in pre_push_gate._DIFF_SCOPED  # pylint: disable=protected-access
