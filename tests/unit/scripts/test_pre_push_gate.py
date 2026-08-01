"""`scripts/pre_push_gate.py` — 로컬 게이트 러너가 **CI 와 같은 것을 부르는가**.

## 왜 이 파일이 있나 (2026-08-01)

두 가지가 겹쳐 CI 왕복이 반복됐다.

1. 🔴 `make` 이 이 머신에 없다 — CLAUDE.md 가 처방하는 `make gate` 는 **실행 불가**다.
2. 🔴 `make gate` 는 있었어도 부족하다 — 그 타깃은 pytest·pylint·bandit 뿐이라
   CI 의 repo-integrity 7종 · PR-diff 한정 4종을 **하나도** 돌리지 않는다.

실제로 한 세션에서 `Block new dual-import` 에 **두 번** 걸렸고 두 번 다 로컬은 초록이었다.

## 🔴 이 파일이 강제하는 것

러너의 목록이 **CI 워크플로에서 유도된 실제 명령과 일치**하는지 본다. 목록을 손으로
적고 그것만 검사하면 CI 가 가드를 추가해도 러너는 영영 모른다 — 그게 이 저장소가
반복해 온 observer-lie 다. 그래서 기대값을 `.github/workflows/ci.yml` **실파일에서 파싱**한다.
Asserts the runner's guard list matches what CI actually runs, parsed from ci.yml itself.
"""
import re
import subprocess  # nosec B404 — 리포 자신의 스크립트만 실행
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import pre_push_gate as gate  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"

# ci.yml 의 `run: python scripts/check_x.py ...` 에서 스크립트 파일명만 뽑는다.
# Extract script filenames from `run: python scripts/check_x.py` lines in ci.yml.
_CI_SCRIPT = re.compile(r"run:\s*python\s+scripts/(check_\w+\.py)")


def ci_guard_scripts() -> set[str]:
    return set(_CI_SCRIPT.findall(_CI.read_text(encoding="utf-8")))


# ── 목록 정합 — 손유지 목록이 CI 와 갈라지지 않게 ──────────────────────────


def test_ci_parsing_is_not_vacuous():
    """🔴 대조군 — 파서가 고장 나면 아래 단언이 전부 공허해진다."""
    found = ci_guard_scripts()
    assert len(found) >= 8, f"ci.yml 에서 가드 스크립트를 {len(found)}개만 찾았다 — 파서 확인"


def test_runner_covers_every_ci_guard_script():
    """🔴 CI 가 부르는 `scripts/check_*.py` 를 러너도 전부 부른다.

    CI 에 가드가 추가됐는데 러너가 모르면, 로컬 초록이 CI 초록을 의미하지 않게 된다 —
    이 러너 자체가 새 observer-lie 가 되는 경로다.
    """
    covered = (set(gate._INTEGRITY) | set(gate._DIFF_SCOPED)
               | {name for name, _args in gate._INTEGRITY_WITH_ARGS})
    missing = ci_guard_scripts() - covered
    assert not missing, (
        f"CI 는 부르는데 러너가 안 부르는 가드: {sorted(missing)}\n"
        "→ scripts/pre_push_gate.py 의 _INTEGRITY / _DIFF_SCOPED 에 추가할 것."
    )


def test_runner_does_not_list_scripts_that_do_not_exist():
    """목록에 죽은 경로가 있으면 그 항목은 영원히 FAIL 이거나 무의미하다."""
    listed = (*gate._INTEGRITY, *gate._DIFF_SCOPED,
              *(name for name, _args in gate._INTEGRITY_WITH_ARGS))
    for name in listed:
        assert (_ROOT / "scripts" / name).exists(), f"러너 목록에 없는 파일: {name}"


# ── 실패 전파 — 통과가 공허하지 않은지 ─────────────────────────────────────


def test_failed_guard_is_reported_and_propagates(monkeypatch, capsys):
    """🔴 가드 하나가 실패하면 exit 1 + 이름이 인쇄돼야 한다.

    러너가 실패를 삼키면 "로컬 게이트를 돌렸다" 는 말이 아무것도 보장하지 않는다.
    """
    calls = []

    # 🔴 `**_kw` 필수 — `_run` 이 kwarg(`show_always`)를 얻으면 좁은 더블이 TypeError 를 내고,
    #    그 증상이 "가드 실패" 로 위장된다(이 세션 `services.md` 에 등재한 함정과 동형).
    # The double must absorb kwargs, else a signature change surfaces as a fake guard failure.
    def _fake_run(label, argv, **_kw):
        calls.append(label)
        return label != gate._INTEGRITY[0]     # 첫 가드만 실패시킨다

    monkeypatch.setattr(gate, "_run", _fake_run)
    monkeypatch.setattr(gate, "_changed_test_files", lambda base: [])
    monkeypatch.setattr(gate, "_base_sha", lambda explicit: "deadbeefdeadbeef")
    monkeypatch.setattr(sys, "argv", ["pre_push_gate.py"])

    assert gate.main() == 1
    out = capsys.readouterr().out
    assert gate._INTEGRITY[0] in out, "실패한 가드 이름이 인쇄되지 않았다"
    assert "실패 1건" in out


def test_all_pass_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(gate, "_run", lambda label, argv, **_kw: True)
    monkeypatch.setattr(gate, "_changed_test_files", lambda base: [])
    monkeypatch.setattr(gate, "_base_sha", lambda explicit: "deadbeefdeadbeef")
    monkeypatch.setattr(sys, "argv", ["pre_push_gate.py"])
    assert gate.main() == 0


def test_blind_spots_are_always_printed(capsys):
    """🔴 "여기 초록 = CI 초록" 오독 차단이 이 러너의 안전장치다 — 조용해지면 안 된다."""
    gate.print_blind_spots(full=False)
    out = capsys.readouterr().out
    assert "보지 못하는" in out
    for needle in ("CodeQL", "TruffleHog", "lint-js", "PG-only"):
        assert needle in out, f"미포함 축 고지에서 {needle} 가 빠졌다"


@pytest.mark.parametrize("full", [True, False])
def test_slow_axes_are_declared_when_not_run(full, capsys):
    """`--full` 없이 돌렸으면 pylint·bandit·pytest 가 **안 돌았다**고 말해야 한다."""
    gate.print_blind_spots(full=full)
    out = capsys.readouterr().out
    assert ("--full" in out and "pylint" in out) is not full


# ── 실행 스모크 — 스크립트가 실제로 돌아간다 ───────────────────────────────


def test_script_runs_standalone():
    """🔴 배선(불변식 3) — `py -3 scripts/pre_push_gate.py --help` 가 실제로 실행된다.

    import 가능함과 standalone 실행 가능함은 다르다(`scripts/` 는 패키지가 아니다).
    """
    proc = subprocess.run(  # nosec B603
        [sys.executable, "scripts/pre_push_gate.py", "--help"],
        cwd=str(_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, check=False,
    )
    assert proc.returncode == 0, f"standalone 실행 실패: {proc.stderr[:300]}"
    assert "--full" in proc.stdout
