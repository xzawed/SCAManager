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


# ── R30 — 인터프리터 이원 관측면 / interpreter drift observability ──────────
#
# 로컬 인터프리터(3.14)와 CI(3.12, 7지점 전부)가 갈라져 있다 — 6-step ② 의
# "push 전 전체 통과 실측" 이 **다른 런타임에서의 통과**라 버전 의존 회귀를 못 잡는데,
# 그 이원을 인쇄하는 관측면이 없었다. 아래는 그 관측면의 계약이다.
# Local (3.14) and CI (3.12) interpreters diverge; the local green never meant a CI green
# for version-dependent regressions, and nothing printed that split. These pin the contract.
#
# 🔴 신규 심볼은 모듈 attribute 로만 접근한다(top-level from-import 금지) —
#    구현 전에는 AttributeError 로 RED 가 되고 collection 은 깨지지 않는다.
# New symbols are reached as module attributes only, so pre-implementation runs
# fail RED at call time (AttributeError) without breaking collection.


def test_ci_python_versions_parsed_nonempty_and_wellformed():
    """🔴 `_ci_python_versions()` — ci.yml **실파일**에서 파싱, 비공허 + `3.N` 형태.

    {"3.12"} 하드코딩 단언 금지 — CI 가 버전을 범프하는 순간 이 가드가 drift 가 아니라
    **자기 자신** 때문에 red 가 되어(가드 자살) 사람이 가드를 끄게 된다. 그래서
    형태(`^3\\.\\d+$`)와 비공허성만 고정하고, 값은 ci.yml 이 말하게 둔다.
    No hardcoded {"3.12"}: pinning the value would make a legitimate CI bump kill the
    guard itself, so only shape and non-emptiness are asserted.
    """
    versions = gate._ci_python_versions()
    assert versions, "ci.yml 에서 python-version 을 하나도 못 찾았다 — 파서/워크플로 확인"
    for version in versions:
        assert re.fullmatch(r"3\.\d+", version), f"python-version 형식이 아니다: {version!r}"


def test_drift_line_warns_on_mismatch():
    """🔴 로컬 ∉ CI 집합 → 경고 마커 + **양쪽 버전 문자열**이 한 줄에 다 보여야 한다.
    A mismatch must carry the warning marker plus both version strings in one line."""
    line = gate.interpreter_drift_line("3.14", {"3.12"})
    assert "⚠️" in line, "버전 불일치인데 경고 마커가 없다"
    assert "3.14" in line, f"로컬 버전이 라인에 없다: {line!r}"
    assert "3.12" in line, f"CI 버전이 라인에 없다: {line!r}"


def test_drift_line_informational_when_matching():
    """로컬 ∈ CI 집합 → 경고 없이 정보만 — 항상 경고하면 아무도 안 읽는다(경고 피로).
    Matching interpreters yield an informational line; constant warnings breed fatigue."""
    line = gate.interpreter_drift_line("3.12", {"3.12"})
    assert "⚠️" not in line, f"일치하는데 경고가 붙었다: {line!r}"
    assert "3.12" in line, "정보 라인에도 버전은 보여야 한다"


def test_drift_line_fails_loud_on_empty_ci_set():
    """🔴 CI 집합이 비었다(파싱 실패) → "⚠️" + 파싱 실패 명시 — 조용한 생략 금지.

    "CI 버전을 못 읽었으니 이 축은 건너뛴다" 는 **가드가 있는데 안 보는** 가장 조용한
    fail-open 형태다 — 파싱이 깨진 날부터 drift 가 무관측으로 돌아간다. fail-closed.
    An empty CI set must warn loudly; silently dropping the axis is the quiet fail-open.
    """
    line = gate.interpreter_drift_line("3.14", set())
    assert "⚠️" in line, "파싱 실패가 조용히 지나갔다 — fail-closed 위반"
    # 🔴 "⚠️ 존재" 만 단언하면 이 분기를 죽여도 mismatch fallthrough 가 우연히 ⚠️ 를 내
    #    green 이 된다(뮤테이션 M2 실측 — 이 단언이 없던 초판에서 생존). 분기 고유 문구
    #    (파싱 실패 명시)를 고정해야 분기가 load-bearing 이 된다.
    # Asserting only the marker let the dead branch survive via the mismatch fallthrough
    # (mutation M2, measured). Pin the branch-specific wording to make it load-bearing.
    assert "파싱 실패" in line, f"파싱 실패가 원인으로 명시되지 않았다: {line!r}"


def test_blind_spots_always_prints_interpreter_axis(capsys):
    """🔴 배선(3-불변식 ③) — `print_blind_spots` 가 --full 무관하게 이 축을 항상 인쇄.

    순수 함수(`interpreter_drift_line`)가 옳아도 진입점에 배선되지 않으면 관측면은 0 이다.
    뮤테이션: 인쇄 호출을 제거하면 이 테스트만 red — R30 관측면의 **유일한 배선 단언**.
    Wiring assertion: correct pure functions reach nobody unless the entry point prints
    them; removing that print turns exactly this test red.
    """
    gate.print_blind_spots(False)
    out = capsys.readouterr().out
    local = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert "CI" in out, "인터프리터 축에 CI 언급이 없다"
    assert local in out, f"로컬 인터프리터 {local} 가 blind-spot 출력에 없다"
    # 🔴 --full=True 축도 고정 (Grok `019fbe61` F1) — False 만 단언하면 인쇄를
    #    `if not full:` 블록 안으로 옮기는 리팩터가 초록인 채 --full 경로의 관측면을 지운다.
    # Pin the full=True path too: asserting only False lets a refactor nest the print
    # under `if not full:` and silently drop the axis on --full runs.
    gate.print_blind_spots(True)
    out_full = capsys.readouterr().out
    assert local in out_full, f"--full 경로에서 인터프리터 축이 사라졌다: {out_full!r}"
