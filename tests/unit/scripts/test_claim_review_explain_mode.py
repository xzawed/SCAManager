"""`check_claim_review_trace.py --explain <base> <head>` 자기진단 모드 (#1433).

## 왜 (2026-08-17 회고 P0)

세 사고(`#1409` · `#1411` · `#1414`)가 같은 형태였다 — 저자가 **상상한 실패 모드**만
뮤테이션으로 죽이고 red 를 확보한 뒤 「봉인」을 발행했고, 실제 회귀는 **테스트에 한 번도
준 적 없는 입력 클래스**에서 났다. `#1409` 는 실제 PR SHA 로 태우자 `EXIT 1` 이었고
**면제가 발화조차 못 했다** — 그런데 저자는 그 사실을 볼 방법이 없었다.

이 모드는 그 한 가지를 준다: *어떤 입력이 어떤 분류를 거쳐 어떤 분기로 갔는가*.

## 🔴 이 테스트가 지키는 가장 중요한 계약

`--explain` 은 **`main()` 과 같은 exit code** 를 돌려준다.

진단 모드가 항상 0 을 돌려주면, 누군가 그것을 CI 에 배선하는 순간 **게이트가 조용히
사라진다**(fail-open). 그래서 `--explain` 은 「정상 실행 + 설명」의 진부분집합이 아니라
**진상위집합**이어야 한다 — 판정은 그대로, 출력만 는다.
`--explain` must return main()'s exit code; a diagnostic that always exits 0 becomes a
fail-open gate the moment someone wires it.
"""
import subprocess

import pytest

from scripts.check_claim_review_trace import cli, main

_MOD = "scripts.check_claim_review_trace"

_GOOD_TRACE = """## Grok claim-review

- session: 019fadda-3609-7ab3-8d94-ebe23699008e
- claim: 무시 목록은 임의 집합이 될 수 없다
- verdict: SURVIVES
"""


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in (
        "PR_TITLE", "PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA",
        "PR_AUTHOR_TYPE", "PR_AUTHOR_LOGIN",
    ):
        monkeypatch.delenv(key, raising=False)


def _repo_with(tmp_path, files_before: dict, files_after: dict):
    """실제 git 저장소 — `(root, base, head)`. 합성 diff 문자열은 프로덕션과 어긋난다."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    for rel, content in files_before.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    for rel, content in files_after.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "head")
    return root, base, git("rev-parse", "HEAD")


# ── 축 1: 판정은 바뀌지 않는다 (fail-open 차단) ───────────────────────────────


def test_explain_returns_the_same_exit_code_as_a_normal_run_when_blocking(
    tmp_path, monkeypatch, capsys,
):
    """🔴 가드 표면을 흔적 없이 바꾼 PR — 정상 실행이 1 이면 `--explain` 도 1 이다."""
    root, base, head = _repo_with(
        tmp_path,
        {"scripts/check_foo.py": "print(1)\n"},
        {"scripts/check_foo.py": "print(2)\n"},
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_TITLE", "chore: 가드 손질")
    monkeypatch.setenv("PR_BODY", "흔적 없음.")

    monkeypatch.setenv("PR_BASE_SHA", base)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    plain = main()
    capsys.readouterr()

    explained = cli(["--explain", base, head])
    out = capsys.readouterr().out

    assert plain == 1, "전제가 깨졌다 — 이 픽스처는 차단되어야 한다"
    assert explained == plain, (
        "🔴 --explain 이 판정을 바꿨다 — 진단 모드가 게이트를 무력화한다(fail-open)"
    )
    assert "EXIT" in out


def test_explain_returns_the_same_exit_code_when_passing(tmp_path, monkeypatch, capsys):
    """흔적이 있으면 정상 실행도 `--explain` 도 0 이다 — 오탐 축."""
    root, base, head = _repo_with(
        tmp_path,
        {"scripts/check_foo.py": "print(1)\n"},
        {"scripts/check_foo.py": "print(2)\n"},
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_TITLE", "chore: 가드 손질")
    monkeypatch.setenv("PR_BODY", _GOOD_TRACE)

    monkeypatch.setenv("PR_BASE_SHA", base)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    plain = main()
    capsys.readouterr()

    assert plain == 0, "전제가 깨졌다 — 이 픽스처는 통과해야 한다"
    assert cli(["--explain", base, head]) == plain


# ── 축 2: 무엇을 인쇄하는가 ──────────────────────────────────────────────────


def test_explain_prints_the_surface_classification(tmp_path, monkeypatch, capsys):
    """분류 각 단계를 인쇄한다 — 「어떤 표면으로 읽혔는가」가 눈에 보여야 한다."""
    root, base, head = _repo_with(
        tmp_path,
        {"scripts/check_foo.py": "1\n", "docs/x.md": "a\n"},
        {"scripts/check_foo.py": "2\n", "docs/x.md": "b\n"},
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_BODY", _GOOD_TRACE)

    cli(["--explain", base, head])
    out = capsys.readouterr().out

    assert "scripts/check_foo.py" in out, "변경 경로를 인쇄하지 않는다"
    assert "가드 표면" in out, "가드 표면 분류를 인쇄하지 않는다"
    assert "코드 표면" in out, "코드 표면 분류를 인쇄하지 않는다"
    # 🔴 docs/x.md 는 코드 표면이 아니다 — 분류가 실제로 갈렸는지 본다(전량 나열이 아니라).
    assert "docs/x.md" in out, "변경 경로 전체를 보여주지 않으면 분류를 대조할 수 없다"


def test_explain_reports_exemption_state(tmp_path, monkeypatch, capsys):
    """🔴 이 모드의 존재 이유 — 「면제가 발화했는가」를 눈으로 확인할 수 있어야 한다."""
    root, base, head = _repo_with(
        tmp_path,
        {"scripts/check_foo.py": "1\n"},
        {"scripts/check_foo.py": "2\n"},
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_BODY", "claim-review-not-required: 이 변경은 인용 서술이라 판정 대상이 아니다")

    code = cli(["--explain", base, head])
    out = capsys.readouterr().out

    assert "면제" in out, "면제 상태를 인쇄하지 않는다"
    # 가드 표면이므로 면제는 **거부**되어야 하고, 그 사실이 보여야 한다.
    assert code == 1, "가드 표면에서 면제가 통과했다 — 전제가 깨졌다"
    assert "거부" in out or "차단" in out or "무효" in out, (
        "면제가 거부됐는데 그 사실이 진단 출력에 없다 — 저자는 여전히 이유를 모른다"
    )


def test_explain_says_undecidable_not_zero(tmp_path, monkeypatch, capsys):
    """🔴 「모른다」를 「없다」로 인쇄하면 안 된다 — 이 리포가 반복해 실패한 형태."""
    root, _base, _head = _repo_with(tmp_path, {"a.txt": "1\n"}, {"a.txt": "2\n"})
    monkeypatch.chdir(root)

    # 존재하지 않는 SHA → git 이 실패 → changed_paths 가 None
    cli(["--explain", "0" * 40, "1" * 40])
    out = capsys.readouterr().out

    assert "판정 불가" in out or "모른다" in out, (
        "경로 산출 실패를 '변경 없음' 으로 인쇄한다 — 모르는 것을 안다고 말하는 형태"
    )
    assert "0건" not in out.split("판정 불가")[0], "판정 불가 앞에서 이미 0건이라 단언한다"


# ── 축 3: 인자 계약 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("argv", [
    ["--explain"],
    ["--explain", "onlybase"],
    ["--explain", "a", "b", "c"],
], ids=["none", "one", "three"])
def test_explain_requires_exactly_two_shas(argv, capsys):
    """인자가 정확히 2개가 아니면 usage + exit 2 — 조용히 env 로 흘러가면 안 된다."""
    assert cli(argv) == 2
    err = capsys.readouterr().err
    assert "--explain" in err


def test_argv_shas_win_over_env(tmp_path, monkeypatch, capsys):
    """진단 대상은 **인자**가 정한다 — env 가 남아 있어도 인자 범위를 본다."""
    root, base, head = _repo_with(
        tmp_path,
        {"scripts/check_foo.py": "1\n"},
        {"scripts/check_foo.py": "2\n"},
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_BASE_SHA", "0" * 40)     # 판정 불가를 만드는 값
    monkeypatch.setenv("PR_HEAD_SHA", "1" * 40)
    monkeypatch.setenv("PR_BODY", _GOOD_TRACE)

    cli(["--explain", base, head])
    out = capsys.readouterr().out
    assert "scripts/check_foo.py" in out, "env 의 SHA 를 보고 있다 — 인자가 무시됐다"


def test_explain_does_not_leak_pr_env_into_the_process(tmp_path, monkeypatch, capsys):
    """🔴 `--explain` 은 `os.environ` 을 **영구 오염시키면 안 된다**.

    `main()` 이 env 를 읽으므로 진단 모드는 인자를 env 로 옮겨 넣는다. 그것을 되돌리지 않으면
    같은 프로세스의 뒤 코드가 **남의 SHA** 를 본다. 실측: 이 가드가 없던 초판에서
    `test_deferral_marker_survives_merge.py` 가 깨졌고 — **격리 실행에서는 통과**하고
    전체 실행에서만 났다. 새로 도달 가능해진 입력 클래스 그 자체다 (#1433).
    The diagnostic must restore PR_* env; otherwise later code in the same process reads
    another range's SHAs — a failure only visible in full-suite ordering.
    """
    root, base, head = _repo_with(tmp_path, {"a.txt": "1\n"}, {"a.txt": "2\n"})
    monkeypatch.chdir(root)
    import os  # pylint: disable=import-outside-toplevel

    assert "PR_BASE_SHA" not in os.environ, "전제가 깨졌다 — 시작 시 env 가 비어 있어야 한다"
    cli(["--explain", base, head])
    capsys.readouterr()

    assert "PR_BASE_SHA" not in os.environ, "--explain 이 PR_BASE_SHA 를 남겼다"
    assert "PR_HEAD_SHA" not in os.environ, "--explain 이 PR_HEAD_SHA 를 남겼다"


def test_explain_restores_a_preexisting_env_value(tmp_path, monkeypatch, capsys):
    """원래 값이 있었으면 **그 값으로** 되돌린다 — 삭제해 버리는 것도 오염이다."""
    root, base, head = _repo_with(tmp_path, {"a.txt": "1\n"}, {"a.txt": "2\n"})
    monkeypatch.chdir(root)
    monkeypatch.setenv("PR_BASE_SHA", "PRESET-BASE")
    monkeypatch.setenv("PR_HEAD_SHA", "PRESET-HEAD")
    import os  # pylint: disable=import-outside-toplevel

    cli(["--explain", base, head])
    capsys.readouterr()

    assert os.environ["PR_BASE_SHA"] == "PRESET-BASE"
    assert os.environ["PR_HEAD_SHA"] == "PRESET-HEAD"


def test_no_flag_behaves_exactly_like_main(monkeypatch):
    """플래그 없이 부르면 기존 동작 그대로 — 진입점 교체가 회귀를 만들지 않는다."""
    monkeypatch.setenv("PR_TITLE", "docs: 오타 수정")
    monkeypatch.setenv("PR_BODY", "오타 1건.")
    assert cli([]) == main() == 0
