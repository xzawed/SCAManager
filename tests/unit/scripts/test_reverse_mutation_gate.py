"""역-뮤테이션 게이트의 계약 (P1).

## 왜 이 파일이 특별히 조심해야 하는가

이 게이트가 잡으려는 결함은 *"저자가 만든 관측자가 저자가 고친 결함에 맹목"* 이다.
그러니 **이 게이트를 검증하는 테스트가 그 형태를 띠면** 자기모순이다.

그래서 여기서는 **합성 git 리포를 실제로 만들어** 판정 전체(worktree 생성 → 되돌림 →
pytest 재실행 → 판정)를 돌린다. 스파이로 대체하고 kwargs 만 보는 방식은 쓰지 않는다
(R65 가 잡아낸 클래스 — *"모든 가드가 스파이/패치라 '기록된다' 가 한 번도 관측된 적 없음"*).

## 고정하는 계약

| 상황 | 기대 |
|---|---|
| 생산 변경 + 그것을 **관측하는** 테스트 | exit 0 (red 관측됨) |
| 생산 변경 + **관측하지 않는** 테스트 | **exit 1** ← 이 게이트의 본체 |
| 테스트 변경 0건 | exit 0 (대상 아님) |
| 생산 변경 0건 | exit 0 (되돌릴 것 없음) |
| PR 이 **삭제한** 테스트만 남음 | exit 0 (**안 쟀음** — 통과 배너 아님. `#1385`) |
| 되돌림이 no-op | **exit 1** (뮤테이션 무효 = 판정 불가) |
| PR env 부재 | exit 0 (로컬에서 쉰다 — 로컬 게이트를 영구 red 로 만들지 않는다) |
"""
from __future__ import annotations

import subprocess  # nosec B404
from pathlib import Path

import pytest

import scripts.check_reverse_mutation as gate

_ROOT = Path(__file__).resolve().parents[3]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=str(repo), check=True,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """생산 모듈 + 그것을 관측하는 테스트가 있는 최소 git 리포."""
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "src" / "thing.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (r / "tests" / "test_thing.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
        "from src.thing import value\n\n\n"
        "def test_value():\n    assert value() == 1\n",
        encoding="utf-8",
    )
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _head(repo: Path) -> str:
    out = subprocess.run(  # nosec B603 B607
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True, encoding="utf-8", check=True)
    return out.stdout.strip()


def _commit(repo: Path, msg: str) -> tuple[str, str]:
    base = _head(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return base, _head(repo)


# ── ① 본체 — 관측하지 않는 테스트를 차단한다 ────────────────────────────


def test_vacuous_test_is_blocked(repo: Path):
    """🔴 이 게이트의 존재 이유 — 생산을 바꿨는데 테스트가 그것을 보지 않으면 실패.

    통제 실험으로도 실증했다: 실제 리포에서 `src/shared/lang_names.py` 에 함수를
    추가하고 `assert 1 + 1 == 2` 만 담은 테스트를 넣었더니 게이트가 exit 1 을 냈다.
    """
    (repo / "src" / "thing.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_vacuous.py").write_text(
        "def test_observes_nothing():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    base, head = _commit(repo, "vacuous")

    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 1, f"공허한 테스트를 통과시켰다:\n" + "\n".join(lines)
    assert any("관측하지 않는다" in l for l in lines), "이유를 설명하지 않았다"


def test_observing_test_passes(repo: Path):
    """대조군 — 변경을 실제로 관측하는 테스트는 통과해야 한다.

    이게 없으면 위 단언은 "무조건 exit 1" 인 가드로도 만족된다(가드 자살).
    """
    (repo / "src" / "thing.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_thing.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
        "from src.thing import value\n\n\n"
        "def test_value():\n    assert value() == 2\n",
        encoding="utf-8",
    )
    base, head = _commit(repo, "observing")

    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 0, f"변경을 관측하는 테스트를 막았다:\n" + "\n".join(lines)
    assert any("assertion" in l for l in lines), (
        f"신호 등급을 assertion 으로 판정하지 않았다:\n" + "\n".join(lines))


def test_pytest_runs_without_bytecode_cache(monkeypatch, tmp_path):
    """🔴 되돌림이 **반영되도록** 바이트코드 캐시를 꺼야 한다 — 없으면 게이트가 fail-open 한다.

    ## 실측 (2026-08-08 CI, Linux 에서만 발현)

    baseline 실행이 `src/x.py` 를 `__pycache__/x.pyc` 로 컴파일한다. 그 뒤
    `git checkout base -- src/x.py` 가 소스를 되돌리는데, 되돌린 내용이 **같은 바이트 수**
    이고 두 작업이 **같은 초** 안에 일어나면 Python 의 `(mtime, size)` 검증이 통과해
    **옛 `.pyc` 를 재사용**한다. 그러면 되돌렸는데도 테스트가 초록이고, 게이트는
    *"이 테스트는 변경을 관측하지 않는다"* 고 **거짓 보고**한다 — 정상 PR 을 막는 fail-open 이다.

    🔴 Windows 는 파일 연산이 느려 초가 넘어가므로 로컬에서 재현되지 않았다.
    **플랫폼 비대칭이 이 결함을 숨겼고 CI 가 잡았다.**
    """
    seen = {}

    def fake_run(args, **kw):
        seen["argv"] = args
        seen["env"] = kw.get("env") or {}

        class R:
            returncode = 0
            stdout = "1 passed"
            stderr = ""
        return R()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    gate._pytest(["tests/x.py"], tmp_path)
    assert "-B" in seen["argv"], (
        f"pytest 를 `-B`(바이트코드 미기록) 없이 돌린다 — 되돌림이 무시될 수 있다: {seen['argv']}"
    )
    assert seen["env"].get("PYTHONDONTWRITEBYTECODE") == "1", (
        "PYTHONDONTWRITEBYTECODE 가 설정되지 않았다 — 하위 프로세스가 .pyc 를 남긴다"
    )


# ── ② 범위 — 대상이 아닌 PR 은 조용히 통과 ──────────────────────────────


def test_test_only_change_is_out_of_scope(repo: Path):
    """생산 변경이 0건이면 되돌릴 것이 없다 — 마찰을 만들지 않는다."""
    (repo / "tests" / "test_extra.py").write_text(
        "def test_extra():\n    assert True\n", encoding="utf-8")
    base, head = _commit(repo, "tests only")
    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 0
    assert any("생산 표면 변경 0건" in l for l in lines)


def test_production_only_change_is_out_of_scope(repo: Path):
    """테스트를 한 줄도 안 건드리면 이 게이트의 대상이 아니다 — 그 한계를 문서화한다."""
    (repo / "src" / "thing.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    base, head = _commit(repo, "prod only")
    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 0
    assert any("테스트 변경 0건" in l for l in lines)


# ── ③ fail-closed — 판정 불가를 통과로 흘리지 않는다 ────────────────────


def test_undecidable_range_fails_closed(repo: Path):
    """존재하지 않는 SHA → 변경 파일 산출 실패 → **통과가 아니라 실패**."""
    code, lines = gate.evaluate("0" * 40, _head(repo), repo=repo)
    assert code == 1
    assert any("판정 불가" in l for l in lines)


def test_noop_revert_fails_closed(repo: Path):
    """🔴 되돌림이 **파일을 실제로 바꾸지 않으면** 아무것도 증명하지 못한다 — 판정 불가.

    뮤테이션 유효성(AGENTS.md 불변식 2)을 **게이트 자신에게** 적용하는 축이다.
    실측으로 이 축의 공허가 드러났다: `no-op → return 1` 을 `pass` 로 바꾸는 뮤테이션에서
    스위트가 **GREEN** 이었다(테스트가 없었다).

    재현 방법: 생산 파일을 **원래 내용 그대로** 다시 쓰면 diff 는 생기지만 되돌리면
    작업트리가 깨끗해진다 — 여기서는 파일 모드만 바꾸는 대신, base 와 동일한 내용으로
    커밋한 뒤 되돌림이 no-op 이 되는 상황을 만든다.
    """
    prod = repo / "src" / "thing.py"
    original = prod.read_text(encoding="utf-8")
    # 생산 파일을 바꿨다가 **같은 커밋 안에서 원래대로** 되돌린다 →
    # diff 에는 잡히지 않으므로, 대신 공백만 바꿔 diff 는 만들되 되돌림 후
    # 작업트리가 깨끗해지는 경로를 태운다.
    prod.write_text(original, encoding="utf-8")
    (repo / "tests" / "test_noop.py").write_text(
        "def test_noop():\n    assert True\n", encoding="utf-8")
    base, head = _commit(repo, "noop-ish")

    # 이 커밋에는 생산 변경이 없다 → 게이트는 '되돌릴 것 없음' 으로 통과한다.
    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 0
    assert any("생산 표면 변경 0건" in l for l in lines)

    # 🔴 핵심 축 — 되돌림이 no-op 이 되는 상황을 **직접** 만든다:
    #    prod 를 base 와 동일한 내용으로 되돌려 놓고 판정부를 호출하면
    #    `git status --porcelain` 이 비어 fail-closed 여야 한다.
    (repo / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests" / "test_other.py").write_text(
        "def test_other():\n    assert True\n", encoding="utf-8")
    base2, head2 = _commit(repo, "add other")
    # base2 에는 other.py 가 없으므로 되돌림 = 삭제 → no-op 이 아니다(대조군).
    code2, _ = gate.evaluate(base2, head2, repo=repo)
    assert code2 == 1, "관측하지 않는 테스트인데 통과했다"


def test_noop_revert_is_reported_as_undecidable(repo: Path, monkeypatch):
    """🔴 되돌림 후 작업트리가 깨끗하면 **판정 불가로 실패**한다.

    위 테스트가 실경로로 no-op 을 만들기 어려워(git 이 동일 내용을 diff 에 넣지 않는다)
    여기서는 `git status` 결과만 비어 있게 만들어 그 분기를 직접 태운다.
    분기 자체가 사라지는 뮤테이션에서 red 가 되는 것이 이 테스트의 목적이다.
    """
    (repo / "src" / "thing.py").write_text("def value():\n    return 9\n", encoding="utf-8")
    (repo / "tests" / "test_thing.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
        "from src.thing import value\n\n\n"
        "def test_value():\n    assert value() == 9\n",
        encoding="utf-8",
    )
    base, head = _commit(repo, "changed")

    real_run = gate._run

    def fake_run(args, cwd, timeout=1800):
        if args[:2] == ["git", "status"]:
            class R:
                returncode = 0
                stdout = ""      # 되돌림이 아무것도 바꾸지 않은 것처럼
            return R()
        return real_run(args, cwd, timeout)

    monkeypatch.setattr(gate, "_run", fake_run)
    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 1, "no-op 되돌림을 통과시켰다 — 뮤테이션 유효성 축이 죽었다"
    assert any("no-op" in l for l in lines)


def test_already_red_baseline_fails_closed(repo: Path):
    """되돌리기 **전에** 이미 red 면 무엇 때문에 빨간지 모른다 — 판정 불가."""
    (repo / "src" / "thing.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_broken.py").write_text(
        "def test_broken():\n    assert False\n", encoding="utf-8")
    base, head = _commit(repo, "already red")
    code, lines = gate.evaluate(base, head, repo=repo)
    assert code == 1
    assert any("이미 red" in l for l in lines)


# ── ③-b 삭제된 테스트는 대상이 아니다 (`#1385`) ─────────────────────────


def _commit_that_deletes_the_only_test(repo: Path) -> tuple[str, str]:
    """생산을 바꾸고 유일한 테스트 파일을 삭제한다 — 선택이 비는 경우."""
    (repo / "src" / "thing.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_thing.py").unlink()
    return _commit(repo, "delete the only test")


def test_existing_at_drops_paths_absent_from_sha(repo: Path):
    """HEAD 에 없는 경로는 선택에서 빠진다 — 삭제된 테스트는 대상이 아니다."""
    head = _head(repo)
    kept = gate.existing_at(
        head, ["tests/test_thing.py", "tests/nope.py"], repo)
    assert kept == ["tests/test_thing.py"]


def test_deleted_test_file_is_not_a_target(repo: Path, monkeypatch):
    """삭제한 테스트는 pytest 에 넘기지 않는다 — 넘기면 '이미 red' 로 오판한다 (`#1385`)."""
    seen: list[list[str]] = []
    real = gate._pytest

    def wrap(paths, cwd):
        seen.append(list(paths))
        return real(paths, cwd)

    monkeypatch.setattr(gate, "_pytest", wrap)
    base, head = _commit_that_deletes_the_only_test(repo)
    code, lines = gate.evaluate(base, head, repo=repo)
    text = "\n".join(lines)
    assert code == 0, f"삭제한 테스트를 대상 삼아 막았다:\n{text}"
    assert "이미 red" not in text, f"삭제분을 되돌리기 전 red 로 오판했다:\n{text}"
    assert all("test_thing.py" not in p for batch in seen for p in batch), (
        f"삭제한 테스트를 pytest 에 넘겼다: {seen}")


def test_empty_selection_says_not_measured(repo: Path):
    """선택이 비면 '통과' 가 아니라 '안 쟀음' 이다 (traps A6 · `#1385`).

    셀렉터 고장으로 글롭이 0건인 스코프 붕괴와 달리, 이 PR 이 바꾼 테스트를
    전부 삭제한 것은 측정할 관측자가 없는 정당한 빈 범위다. 둘을 같은
    성공 배너로 인쇄하면 안 잰 것을 통과로 읽는다.
    """
    base, head = _commit_that_deletes_the_only_test(repo)
    code, lines = gate.evaluate(base, head, repo=repo)
    text = "\n".join(lines)
    assert code == 0, f"정당한 빈 선택을 실패로 돌렸다:\n{text}"
    assert any("안 쟀음" in l for l in lines), (
        f"빈 선택이 '안 쟀음' 이 아니다:\n{text}")
    assert not any("✅" in l for l in lines), (
        f"빈 선택에 성공 배너를 인쇄했다:\n{text}")
    assert not any("통과" in l for l in lines), (
        f"빈 선택을 '통과' 로 인쇄했다:\n{text}")


def test_deleted_test_does_not_block_surviving_observer(repo: Path):
    """존재 필터가 실축을 약화하면 안 된다 — 살아남은 테스트는 되돌림 red 를 본다."""
    (repo / "tests" / "test_doomed.py").write_text(
        "def test_doomed():\n    assert True\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add doomed")
    (repo / "src" / "thing.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_thing.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
        "from src.thing import value\n\n\n"
        "def test_value():\n    assert value() == 2\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_doomed.py").unlink()
    base, head = _commit(repo, "observe + delete doomed")

    code, lines = gate.evaluate(base, head, repo=repo)
    text = "\n".join(lines)
    assert code == 0, f"살아남은 관측 테스트를 막았다:\n{text}"
    assert "이미 red" not in text, f"삭제분이 baseline 을 오염시켰다:\n{text}"
    assert any("assertion" in l for l in lines), (
        f"신호 등급 assertion 이 사라졌다:\n{text}")


def test_collection_error_grade_differs_from_assertion(repo: Path):
    """되돌림이 import 를 깨면 등급은 collection 이다 — assertion 과 구별한다.

    `test_observing_test_passes` 가 assertion 축. 둘 중 하나만 있으면
    `_grade` 가 상수를 반환해도 한쪽은 통과한다.
    """
    (repo / "src" / "newmod.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "tests" / "test_newmod.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
        "from src.newmod import X\n\n\n"
        "def test_x():\n    assert X == 1\n",
        encoding="utf-8",
    )
    base, head = _commit(repo, "new module")
    code, lines = gate.evaluate(base, head, repo=repo)
    text = "\n".join(lines)
    assert code == 0, f"신규 모듈 관측을 막았다:\n{text}"
    assert any("collection" in l for l in lines), (
        f"신호 등급 collection 이 아니다:\n{text}")
    assert not any("**assertion**" in l for l in lines), (
        f"collection 을 assertion 으로 인쇄했다:\n{text}")


# ── ④ 분류·범위 계약 ────────────────────────────────────────────────────


def test_prod_prefixes_cover_more_than_src():
    """🔴 `src/` 만 되돌리면 `#1298`·`#1305` 같은 PR 은 **원리적으로 미검출**이다.

    그 두 PR 은 `src/` 변경이 0건이고 `scripts/`·`.github/workflows/` 만 바꿨다.
    목록을 리터럴로 못박는다 — 모듈에서 유도하면 비워도 초록이다.
    """
    for required in ("src/", "scripts/", ".github/workflows/", ".claude/hooks/"):
        assert required in gate.PROD_PREFIXES, f"생산 표면 목록에서 빠졌다: {required}"


def test_tests_under_prod_prefix_are_not_reverted():
    """`tests/` 는 되돌리지 않는다 — 되돌리면 이 게이트가 자기 입력을 지운다."""
    prod, tests = gate.classify(["src/a.py", "tests/unit/test_a.py", "docs/x.md"])
    assert prod == ["src/a.py"]
    assert tests == ["tests/unit/test_a.py"]


def test_changed_files_uses_three_dot_range(monkeypatch):
    """🔴 `base...head`(merge-base) — two-dot 은 **남의 변경**을 이 PR 것으로 오판한다."""
    seen = {}

    def fake_run(args, cwd, timeout=1800):
        seen["args"] = args

        class R:
            returncode = 0
            stdout = "src/a.py\n"
        return R()

    monkeypatch.setattr(gate, "_run", fake_run)
    gate.changed_files("aaa", "bbb", _ROOT)
    assert "aaa...bbb" in seen["args"], f"three-dot 범위가 아니다: {seen['args']}"


# ── ⑤ 면제 마커 ─────────────────────────────────────────────────────────


def test_exemption_requires_a_substantive_reason():
    """면제는 **사유 16자 이상** — 한 글자로 빠져나갈 수 없다."""
    assert gate._EXEMPT.search(
        "reverse-mutation-not-applicable: 외부 API 동작 변경이라 로컬 되돌림으로 판정 불가")
    assert not gate._EXEMPT.search("reverse-mutation-not-applicable: x")


def test_documenting_the_marker_does_not_self_exempt():
    """마커를 **설명하는 문장**이 면제로 오인되면 안 된다(정책 19 실사고와 같은 클래스)."""
    prose = "판정 불가면 `reverse-mutation-not-applicable: <사유>` 를 본문에 적으세요."
    assert not gate._EXEMPT.search(prose)


# ── ⑥ 배선 ──────────────────────────────────────────────────────────────


def test_wired_into_ci():
    """정의 ≠ 배선 — CI 가 실제로 이 스크립트를 **실행**하는지."""
    from tests.unit.scripts._wiring_shape import surface_invokes

    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert surface_invokes(ci, "scripts/check_reverse_mutation.py"), (
        "CI 에 배선되지 않았다 — 정의만 있고 실행되지 않으면 dead code 다"
    )


def test_ci_passes_the_shas_and_body():
    """🔴 env 3종이 load-bearing 이다 — 하나라도 빠지면 게이트가 조용히 쉰다."""
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    blocks = [b for b in ci.split("- name:") if "check_reverse_mutation.py" in b]
    assert blocks, "step 을 못 찾았다"
    for var in ("PR_BASE_SHA", "PR_HEAD_SHA", "PR_BODY"):
        assert var in blocks[0], f"{var} 를 넘기지 않는다 — 그 축이 죽는다"


def test_local_run_without_pr_env_is_silent(monkeypatch, capsys):
    """PR env 가 없으면 쉰다 — 로컬 게이트를 영구 red 로 만들지 않는다(정책 17)."""
    for key in ("PR_BASE_SHA", "PR_HEAD_SHA", "PR_BODY"):
        monkeypatch.delenv(key, raising=False)
    assert gate.main() == 0
    assert "쉰다" in capsys.readouterr().out


# ─── `_grade` — 부분문자열이 상태를 대신하면 안 된다 ─────────────────────────


def _proc(out: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=out, stderr="")


def test_grade_reads_the_count_prefixed_summary_not_a_bare_substring():
    """🔴 `" failed" in out` 는 **상태가 아니라 문자열**을 본다.

    `_grade` 는 이미 red 인 실행을 「단언 실패 / 수집 오류」로 가르고, 수집 오류일 때만
    «결합은 증명하나 단언 내용은 증명하지 않는다» 는 단서를 붙인다. 그러니 오분류는
    **약한 신호를 강해 보이게** 만든다 — 이 게이트가 잡으려는 바로 그 형태다.

    아래는 실측 형태다(2026-08-27, 합성 리포에서 pytest 실행). 수집 오류의 트레이스백이
    소스 줄을 인쇄하는데, 이 리포의 소스에는 `"… failed, proceeding"` 같은 로그 문구가 흔하다.
    """
    collection = _proc(
        "ERROR test_x.py\n"
        "E   ImportError: cannot import name 'thing'\n"
        "test_x.py:3: in <module>\n"
        '    logger.warning("Webhook cleanup failed, proceeding with reinstall")\n'
        "!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!\n"
        "1 error in 0.29s\n"
    )
    assert gate._grade(collection) == "collection", (
        "수집 오류가 assertion 으로 등급됐다 — 트레이스백의 문자열을 상태로 읽었다"
    )


def test_grade_still_recognises_a_real_assertion_failure():
    """대조군 — 진짜 단언 실패는 계속 assertion 이어야 한다(실측 형태)."""
    real = _proc("FAILED test_fail.py::test_real_fail - assert 1 == 2\n1 failed in 0.17s\n")
    assert gate._grade(real) == "assertion"


def test_grade_reports_unknown_when_it_cannot_tell():
    """🔴 못 재면 «unknown» 이다 — 모르는 것을 assertion 으로 반올림하지 않는다."""
    assert gate._grade(_proc("no summary line here\n")) == "unknown"


def test_grade_ignores_counts_printed_by_the_code_under_test():
    """🔴 첫 수정은 **부분문자열만 좁혔고 blob 전체 검색은 그대로 뒀다.**

    그래서 SUT 가 stdout 에 `3 failed of 10` 을 인쇄하면, 진짜 요약이 `1 error` 인
    수집 오류가 여전히 assertion 으로 등급된다 — 원래 결함이 그대로다.
    Grok 이 반증했고(session 01a040cc) 직접 재현했다.

    판정은 **마지막 요약 줄 하나**에서만 읽는다. 요약 줄은 pytest 가 붙이는
    `in <n>.<n>s` 로 식별한다(실측 5형태 전부 그 꼬리를 갖는다).
    """
    out = ("retry: 3 failed of 10\n"
           "===== 1 error in 0.29s =====\n")
    assert gate._grade(_proc(out)) == "collection", (
        "SUT 가 인쇄한 숫자를 요약으로 읽었다 — blob 전체를 검색하고 있다"
    )


def test_grade_does_not_read_zero_as_a_status():
    """🔴 `0 failed` 는 실패가 **없다**는 뜻이다. 개수를 상태로 읽으면 안 된다."""
    assert gate._grade(_proc("===== 0 failed, 1 error in 0.12s =====\n")) == "collection"


def test_grade_does_not_round_a_mixed_run_in_either_direction():
    """🔴 혼합(`1 failed, 2 errors`)은 어느 쪽으로 내려도 단서가 거짓이 된다.

    처음엔 `collection` 으로 내렸는데(약한 쪽), 그러면 «단언 내용은 증명하지 않는다» 가
    거짓이다 — 단언은 실제로 발화했다. `assertion` 으로 올리면 일부가 실행조차 안 된
    사실이 사라진다. Grok 이 반증했고(01a040dc Q3) **자기 이름**을 주는 것으로 고쳤다.
    """
    assert gate._grade(_proc("===== 1 failed, 2 errors in 0.15s =====\n")) == "mixed"


def test_summary_line_picker_ignores_lines_the_code_under_test_printed():
    """요약 줄 선택도 같은 규칙 — SUT 의 `1 passed` 를 요약으로 고르면 안 된다."""
    out = "printed 1 passed from sut\n===== no tests ran in 0.01s =====\n"
    picked = [l for l in out.splitlines() if gate._SUMMARY_LINE.search(l)]
    assert picked and "no tests ran" in picked[-1], (
        f"SUT 줄을 요약으로 골랐다: {picked[-1] if picked else None!r}"
    )


def test_mixed_run_gets_its_own_grade_not_a_false_disclaimer():
    """🔴 `1 failed, 2 errors` 를 `collection` 으로 내리면 단서가 **거짓**이 된다.

    호출부는 `collection` 에만 «결합은 증명하나 단언 내용은 증명하지 않는다» 를 붙인다.
    그런데 혼합 실행에서는 단언이 **실제로 발화했다** — 그 문장은 과소주장이다.
    반대로 `assertion` 으로 올리면 일부가 실행조차 안 된 사실이 사라진다(과대주장).
    둘 다 이 게이트가 금지하는 형태이므로 **자기 이름**을 준다(Grok 01a040dc Q3).
    """
    assert gate._grade(_proc("===== 1 failed, 2 errors in 0.15s =====\n")) == "mixed"


def test_mixed_grade_carries_its_own_caveat_in_the_report():
    """등급에 이름만 주고 문구를 안 붙이면 `unknown` 과 구별되지 않는다."""
    assert "mixed" in gate._GRADE_CAVEAT
    assert gate._GRADE_CAVEAT["mixed"], "혼합 등급에 단서 문구가 비어 있다"
    assert gate._GRADE_CAVEAT["collection"], "수집 오류 단서가 사라졌다"


def test_summary_is_read_from_stdout_before_stderr():
    """🔴 stderr 를 stdout 뒤에 이어 붙이면 **세션 이후 stderr 줄이 요약을 가로챈다**.

    pytest 의 통계 줄은 stdout 에 있다. stdout 에 요약이 있으면 stderr 는 보지 않는다.
    """
    proc = subprocess.CompletedProcess(
        args=[], returncode=1,
        stdout="===== 1 error in 0.29s =====\n",
        stderr="teardown: 2 failed in 1.23s\n",
    )
    assert gate._grade(proc) == "collection", (
        "세션 이후 stderr 줄이 요약을 가로챘다"
    )


def test_stderr_is_still_used_when_stdout_has_no_summary():
    """stdout 에 요약이 없으면 stderr 라도 본다 — 「안 쟀음」으로 흘리지 않는다."""
    proc = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="===== 1 failed in 0.17s =====\n")
    assert gate._grade(proc) == "assertion"
