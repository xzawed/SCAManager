"""`check_test_count_sync.py` — 본문 수치 축의 계약 (회고 P0-D · R48 · #1442 · Grok 019fb930).

🔴 이 파일의 본체는 **fail-closed 부정 통제**다. "일치하면 통과"(양성)보다 **"도구가 죽거나
형식이 바뀌었을 때 조용히 초록이 되지 않는가"**(음성)가 이 축의 존재 이유다.

테스트 수는 문서(STATE · README)에 적지 않는다 — 이 가드가 대조하는 것은 PR 본문의 수치 줄과
그 PR 의 실행 결과(CI junit), junit 이 없는 로컬에서는 수집값이다.

Contract tests for the PR-body count axis. The negative controls are the point: the guard must not
go silently green when the tool dies or the format drifts.
"""
import subprocess
from pathlib import Path

import pytest

import scripts.check_test_count_sync as mod
from tests.unit.scripts._wiring_shape import invokes

_ROOT = Path(__file__).resolve().parents[3]


# ── 파싱 (Grok 계약: 마지막 매치 · 단수형 · 미검출 None) ─────────────────


def test_parse_uses_the_last_match():
    """🔴 `-q` 출력 앞부분은 nodeid 덤프 — 첫 매치를 쓰면 엉뚱한 수가 잡힌다."""
    out = "some::test[3 tests collected]\nnoise\n6099 tests collected in 5.15s\n"
    assert mod.parse_collected(out) == 6099


def test_parse_accepts_singular():
    assert mod.parse_collected("1 test collected in 0.01s") == 1


def test_parse_returns_none_when_absent():
    """미검출 = None — 호출자가 fail-closed 로 승격해야 한다 ('6 errors' 트랩)."""
    assert mod.parse_collected("!!! 6 errors !!!\nno trailing line") is None


def test_parse_no_tests_collected_is_not_a_number():
    """`no tests collected` 를 0 으로 발명하면 안 된다."""
    assert mod.parse_collected("no tests collected in 0.02s") is None


# ── main — 무엇을 언제 재는가 ──────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_ambient_pr_context(monkeypatch, tmp_path):
    """🔴 CI 는 `PR_BODY` · SHA · 저자 변수를 **실제로** 넘긴다 — 테스트를 그 환경에서 격리한다.

    본문 수치 축을 붙이자 기존 테스트 2건이 **CI 에서만** 깨졌다: 테스트는 `collect_count` 를
    합성값으로 패치하는데 본문 리더는 패치되지 않아 **진짜 PR 본문**을 읽어 왔다.
    🔴 SHA 변수를 남기면 `main()` 이 PR 맥락으로 오판해 수치 부재 테스트가 CI 에서만 red 가 된다.
    junit 산출물도 없는 경로로 돌린다 — 리포 루트에 남은 이전 실행 파일이 판정을 바꾸면 안 된다.
    CI really sets these; default them empty so tests opt in explicitly.
    """
    monkeypatch.setattr(mod, "read_pr_body", lambda: "")
    monkeypatch.setattr(mod, "_JUNIT", tmp_path / "absent-junit.xml")
    for key in (
        "PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA",
        "PR_AUTHOR_LOGIN", "PR_AUTHOR_TYPE",
    ):
        monkeypatch.delenv(key, raising=False)


def _patch_body(monkeypatch, body: str):
    monkeypatch.setattr(mod, "read_pr_body", lambda: body)


def _patch_collect(monkeypatch, unit: int) -> list[str]:
    calls: list[str] = []

    def _fake(path):
        calls.append(path)
        return unit
    monkeypatch.setattr(mod, "collect_count", _fake)
    return calls


def test_main_needs_no_documented_count(monkeypatch):
    """🔴 테스트 수는 문서에 없다 — 본문 수치가 실측과 맞으면 STATE 없이 통과한다.

    문서 사본(STATE 종합 수치)과 대조하던 판은 그 줄이 없으면 fail-closed 로 red 였다.
    """
    _patch_collect(monkeypatch, 6851)
    _patch_body(monkeypatch, "pytest tests/unit  →  6842 passed / 9 skipped / EXIT=0")
    assert mod.main() == 0


def test_main_body_mismatch_is_red(monkeypatch):
    """본문 숫자가 실측과 다르면 red — #1310 이 이 형태였다(본문만 −1)."""
    _patch_collect(monkeypatch, 6851)
    _patch_body(monkeypatch, _REAL_MISMATCH)          # 6841 + 9 = 6850 != 6851
    assert mod.main() == 1


def test_main_collection_failure_is_red(monkeypatch):
    """🔴 수집이 죽으면 red — 본문 수치를 아무것과도 대조하지 못했다 (`|| true` 와의 경계)."""
    def _boom(_path):
        raise RuntimeError("pytest collect 실패 (exit 2)")
    monkeypatch.setattr(mod, "collect_count", _boom)
    _patch_body(monkeypatch, "pytest tests/unit  →  6842 passed / 9 skipped")
    assert mod.main() == 1


def test_main_with_junit_compares_the_run_and_skips_collection(monkeypatch, tmp_path):
    """CI — junit 이 있으면 수집(≈11초)하지 않고 실행 결과와 대조한다."""
    calls = _patch_collect(monkeypatch, 999)
    monkeypatch.setattr(mod, "_JUNIT", _junit(tmp_path, [("tests.unit.a.test_x", "pass")] * 3))
    _patch_body(monkeypatch, _claim(3, 0))
    assert mod.main() == 0
    assert calls == [], "junit 이 있는데 수집을 돌렸다 — 쓰이지 않는 11초다"


def test_absent_claim_outside_a_pr_is_unmeasured_not_green(monkeypatch, capsys):
    """PR 맥락이 없으면(로컬 · push) 미검출은 '안 쟀음' + 0 — 수집도 돌리지 않는다.

    비봇 PR 의 수치 부재 red 는 `test_non_bot_missing_claim_is_red` 가 잰다.
    """
    calls = _patch_collect(monkeypatch, 6851)
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    assert mod.main() == 0
    assert "미실행" in capsys.readouterr().out, "미검출이 조용히 통과하면 이 축은 관측되지 않는다"
    assert calls == []


def test_main_requires_claim_in_pr_context_when_author_missing(monkeypatch):
    """배선: PR SHA 가 있으면 저자 변수 부재도 비봇 → 수치 부재 red."""
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    monkeypatch.setenv("PR_HEAD_SHA", "deadbeef")
    assert mod.main() == 1


def test_body_claim_axis_reads_the_single_hardened_reader(monkeypatch):
    """배선(불변식 3) — 본문은 단일 리더(`read_pr_body`)로만 온다. 끊으면 축이 죽어야 한다.

    죽지 않으면 어딘가에서 본문을 따로 읽고 있다는 뜻이고, 그건 `test_pr_body_single_reader` 가 막는 결함이다.
    """
    _patch_collect(monkeypatch, 6851)
    assert mod.main() == 0          # 본문 없음 → 미실행
    _patch_body(monkeypatch, _REAL_MISMATCH)
    assert mod.main() == 1          # 같은 리더로 본문이 오면 red


# ── collect_count — 실행 실패의 fail-closed (subprocess 경계) ────────────


def test_collect_count_raises_on_nonzero_exit(monkeypatch):
    """exit 2(수집 오류)·5(0건) 는 개수 신뢰 불가 — 예외 전파."""
    def _fake_run(*a, **k):
        return subprocess.CompletedProcess(a, returncode=2, stdout="!!! errors !!!", stderr="")
    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError):
        mod.collect_count("tests/unit")


def test_collect_count_raises_when_line_missing(monkeypatch):
    def _fake_run(*a, **k):
        return subprocess.CompletedProcess(a, returncode=0, stdout="깨끗하지만 라인 없음", stderr="")
    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError):
        mod.collect_count("tests/unit")


# ── CI 배선 (호출 형태 관측) ─────────────────────────────────────────────


def _ci_steps():
    import yaml
    ci = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    return [s for job in ci["jobs"].values() for s in job.get("steps", [])]


def test_ci_wires_the_claim_step_for_pull_requests():
    """🔴 PR 스텝이 본문 · SHA · 저자 변수를 넘긴다 — 저자 신원은 이벤트에서만(본문 마커는 자기인증).

    push 에는 PR 본문이 없어 이 축이 잴 것이 없다 — 스텝은 PR 에서만 돈다.
    """
    hits = [s for s in _ci_steps() if invokes(s.get("run", ""), "scripts/check_test_count_sync.py")]
    assert hits, "수치 스텝이 없다 — 이 축이 CI 에서 아예 돌지 않는다"
    assert all("pull_request" in str(s.get("if", "")) for s in hits), (
        "PR 밖에서 도는 수치 스텝이 있다 — 본문이 없는 이벤트에서는 «미실행» 만 찍는다"
    )
    passed = " ".join(str(s.get("env", {})) for s in hits)
    for key in ("PR_BODY", "PR_HEAD_SHA", "PR_AUTHOR_LOGIN", "PR_AUTHOR_TYPE"):
        assert key in passed, f"PR 스텝이 `{key}` 를 넘기지 않는다"


# ── 본문 수치 축 (R48 — "돌렸는가" 대신 "본문 숫자가 기계값에서 파생됐는가") ──────
#
# 🔴 왜 이 축인가 (2026-08-08 회고 권고 + 2026-08-10 실측):
#   *"전체 테스트를 돌렸는가"* 는 자기 신고라 기계가 진위를 못 잰다. *"본문에 적힌 수가
#   실측 수집값과 같은가"* 로 바꾸면 잴 수 있다. 실측으로 오라클이 판별함을 확인했다 —
#   #1305 본문 6800+9=6809 vs 실측 6819(−10) · #1310 6841+9=6850 vs 6851(−1) ·
#   #1312 6860+9=6869 vs 6885(−16). 🔴 **base drift 가설은 배제됐다**: 브랜치 tip 에서
#   재측정해도 수집값이 머지 커밋과 같았다(6819·6851·6885) — 저자 수치가 실제로 틀렸다.
#
# 🔴 2026-08-15: 비봇 PR 의 수치 라인 부재는 red. 봇 PR · PR 맥락이 없는 실행(로컬 · push)
#   은 *"미실행"* 문구 + 0. junit 이 있으면 실행 결과와, 없으면 수집값과 대조한다.

# 실제 PR 본문에서 그대로 가져온 형식 2종 (합성 문자열 아님 — 불변식 2)
_REAL_ARROW = "pytest tests/unit  →  6800 passed / 9 skipped / EXIT=0  (+16)"      # #1305
_REAL_TABLE = "| `pytest tests/unit` 전체 | **6985 passed / 9 skipped / 0 failed** |"  # #1320
_REAL_MISMATCH = "pytest tests/unit  →  6841 passed / 9 skipped / EXIT=0  (+16)"   # #1310


def test_body_claim_parses_the_arrow_format():
    assert mod.parse_body_claim(_REAL_ARROW) == (6800, 9)


def test_body_claim_parses_the_table_format():
    """🔴 표 형식이 최근 관행이다 — 화살표만 지원하면 이 축은 현행 PR 에서 영원히 미실행이다."""
    assert mod.parse_body_claim(_REAL_TABLE) == (6985, 9)


def test_body_claim_ignores_mutation_rows():
    """뮤테이션 표의 `**2 failed** / 3 passed` 는 전체 스위트 주장이 아니다."""
    body = "| dedupe 제거 | **3 failed** / 2 passed |\n| `read_pr_body()` 회귀 | **2 failed** / 13 passed |\n"
    assert mod.parse_body_claim(body) is None


def test_body_claim_absent_is_none():
    assert mod.parse_body_claim("본문에 수치가 없다") is None


def test_body_claim_uses_the_first_match_not_the_last():
    """🔴 첫 매치다 — 본문 순서는 **저자가 정한다**.

    마지막 매치를 쓰면 헤드라인에 틀린 수를 적고 접힌 `<details>` 부록에 맞는 수를 넣어
    리뷰어와 가드에게 다른 것을 보여줄 수 있다(적대 감사 `wf_9a4878aa-eab` 이 실행 실증).
    """
    assert mod.parse_body_claim(f"{_REAL_ARROW}\n{_REAL_TABLE}\n") == (6800, 9)


def test_details_appendix_cannot_override_the_headline():
    """실제 우회 시나리오 그대로 — 헤드라인은 거짓, 접힌 부록만 참인 본문."""
    body = (
        "### 요약\n"
        "pytest tests/unit  →  6841 passed / 9 skipped / EXIT=0\n"
        "<details><summary>부록</summary>\n"
        "pytest tests/unit  →  6842 passed / 9 skipped / EXIT=0\n"
        "</details>\n"
    )
    assert mod.parse_body_claim(body) == (6841, 9), "부록이 헤드라인을 덮으면 리뷰어와 가드가 다른 것을 본다"


def test_scoped_run_line_is_not_a_full_suite_claim():
    """🔴 `\\b` 는 `tests/unit/scripts` 에서도 성립한다 — 스코프 실행 증거를 전체 주장으로 읽으면 오탐."""
    assert mod.parse_body_claim("pytest tests/unit/scripts → 2 failed, 494 passed, 1 skipped") is None


def test_skipped_token_is_optional():
    """skip 0건이면 pytest 는 그 토큰을 아예 안 찍는다 — 필수로 두면 그 상태에서 축이 죽는다."""
    assert mod.parse_body_claim("pytest tests/unit  →  7004 passed / EXIT=0") == (7004, 0)


def test_thousands_separator_is_not_truncated():
    """`6,995 passed` 가 `995` 로 읽히면 정직한 저자가 red 가 된다."""
    assert mod.parse_body_claim("| `pytest tests/unit` | **6,995 passed / 9 skipped** |") == (6995, 9)


def test_non_bot_missing_claim_is_red(monkeypatch, capsys):
    """비봇 저자 + 수치 라인 없음 → red (R48 잔여 — 공허 통과 차단)."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "xzawed")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "User")
    assert mod.check_body_claim("수치 라인이 없는 본문", 6851) == 1
    captured = capsys.readouterr()
    assert "미실행" in captured.out


def test_bot_type_missing_claim_is_advisory(monkeypatch, capsys):
    """`user.type == Bot` + 수치 없음 → 0, 미실행 문구는 남긴다."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "dependabot[bot]")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "Bot")
    assert mod.check_body_claim("수치 라인이 없는 본문", 6851) == 0
    assert "미실행" in capsys.readouterr().out


def test_bot_login_suffix_missing_claim_is_advisory(monkeypatch, capsys):
    """로그인만 `[bot]` 이어도 봇 — type 단독에 의존하면 안 된다."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "renovate[bot]")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "User")
    assert mod.check_body_claim("수치 라인이 없는 본문", 6851) == 0
    assert "미실행" in capsys.readouterr().out


def test_missing_author_env_is_not_a_bot_exemption(monkeypatch):
    """저자 env 부재 = 비봇 = 수치 부재 red. 부재가 면제가 되면 fail-open."""
    monkeypatch.delenv("PR_AUTHOR_LOGIN", raising=False)
    monkeypatch.delenv("PR_AUTHOR_TYPE", raising=False)
    assert mod.check_body_claim("수치 라인이 없는 본문", 6851) == 1


def test_empty_author_env_is_not_a_bot_exemption(monkeypatch):
    """빈 문자열도 부재와 같다 — 공백을 봇으로 읽으면 안 된다."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "   ")
    assert mod.check_body_claim("수치 라인이 없는 본문", 6851) == 1


def test_matching_claim_still_passes_without_author_env(monkeypatch):
    """기존 동작 — 일치하는 수치 라인은 저자 env 없이도 0."""
    monkeypatch.delenv("PR_AUTHOR_LOGIN", raising=False)
    monkeypatch.delenv("PR_AUTHOR_TYPE", raising=False)
    assert mod.check_body_claim(
        "pytest tests/unit  →  6842 passed / 9 skipped / EXIT=0", 6851,
    ) == 0


def test_mismatched_claim_still_fails_without_author_env(monkeypatch):
    """기존 동작 — 불일치 수치는 저자 env 없이도 1."""
    monkeypatch.delenv("PR_AUTHOR_LOGIN", raising=False)
    monkeypatch.delenv("PR_AUTHOR_TYPE", raising=False)
    assert mod.check_body_claim(_REAL_MISMATCH, 6851) == 1


def test_advisory_does_not_fail_on_missing_claim(monkeypatch, capsys):
    """PR 맥락이 없는 실행(로컬 · push) — 수치 부재를 hard-fail 하지 않는다."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "xzawed")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "User")
    assert mod.check_body_claim(
        "수치 라인이 없는 본문", 6851, advisory=True,
    ) == 0
    assert "미실행" in capsys.readouterr().out


def test_body_mismatch_is_recorded_in_the_job_summary(monkeypatch, tmp_path):
    """🔴 불일치는 사람이 여는 자리(job summary)에 남는다 — 로그 안쪽만으로는 아무도 안 본다."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert mod.check_body_claim(_REAL_MISMATCH, 6851) == 1
    assert "본문 수치 불일치" in summary.read_text(encoding="utf-8")


def test_summary_write_failure_never_changes_the_verdict(monkeypatch):
    """기록 실패가 판정을 바꾸면 안 된다 — 로깅이 게이트를 흔들면 그 자체가 결함이다."""
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent-dir/summary.md")
    mod._append_step_summary("x")  # 예외가 나면 이 테스트가 실패한다


# ── 실행 증거 축: junit XML 대조 (#1442 b) ────────────────────────────────────
#
# 🔴 이 축이 왜 필요한가: `collect_count()` 는 `--collect-only`(약 11초)라 「수치가 신선한가」만
#    잰다. 실스위트는 250~340초다. 즉 저자는 19배 싼 경로로 같은 숫자를 만들 수 있고,
#    **테스트가 실패해도** 수집 수는 그대로다. CI 는 이미 `--junitxml=pytest-results.xml` 을
#    만든다 — 오라클이 이미 있는데 쓰지 않고 있었다.
#
# 🔴 CI 는 `pytest tests/`(단위+통합)를 돌리므로 junit 총계 != 본문의 단위 수치다.
#    `classname`(`tests.unit.…`)으로 단위만 골라낸다 — 실측으로 확인한 산출물 형태다.


def _junit(tmp_path, cases, suite_attrs=None):
    """junit XML 픽스처 — `cases` = [(classname, outcome), …]. outcome: pass|skip|fail."""
    attrs = suite_attrs or {}
    body = []
    for cn, outcome in cases:
        inner = {"pass": "", "skip": "<skipped/>", "fail": "<failure/>"}[outcome]
        body.append(f'<testcase classname="{cn}" name="t">{inner}</testcase>')
    xml = (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" '
        + " ".join(f'{k}="{v}"' for k, v in attrs.items())
        + ">" + "".join(body) + "</testsuite></testsuites>"
    )
    p = tmp_path / "pytest-results.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def test_junit_counts_only_unit_tests(tmp_path):
    """🔴 단위만 센다 — CI 는 `tests/` 전체를 돌리므로 통합이 섞이면 본문과 못 맞춘다."""
    p = _junit(tmp_path, [
        ("tests.unit.gate.test_engine", "pass"),
        ("tests.unit.gate.test_engine", "pass"),
        ("tests.unit.api.test_routes", "skip"),
        ("tests.integration.test_static_analyzer", "pass"),
        ("tests.integration.test_eslint_analyzer", "skip"),
    ])
    assert mod.junit_unit_counts(p) == (2, 1, 0)


def test_junit_counts_report_failures(tmp_path):
    """🔴 실패를 센다 — 이것이 `--collect-only` 가 원리적으로 못 보는 축이다."""
    p = _junit(tmp_path, [
        ("tests.unit.a.test_x", "pass"),
        ("tests.unit.a.test_y", "fail"),
    ])
    assert mod.junit_unit_counts(p) == (1, 0, 1)


def test_junit_absent_is_none_not_zero(tmp_path):
    """🔴 산출물이 없으면 `None` — `(0,0,0)` 을 돌려주면 「안 쟀음」이 「0건」이 된다."""
    assert mod.junit_unit_counts(tmp_path / "nope.xml") is None


def test_junit_unparsable_is_none_not_a_crash(tmp_path):
    """깨진 XML 은 예외가 아니라 None — 가드가 인프라 사고로 죽으면 안 된다."""
    p = tmp_path / "pytest-results.xml"
    p.write_text("<testsuites><broken", encoding="utf-8")
    assert mod.junit_unit_counts(p) is None


def _claim(passed, skipped):
    return f"pytest tests/unit → {passed} passed / {skipped} skipped"


def test_body_claim_is_checked_against_the_actual_run_when_junit_exists(tmp_path, monkeypatch, capsys):
    """🔴 junit 이 있으면 **실행 결과**와 대조한다 — 수집값이 아니라.

    수집 수가 맞아도 실제로 돌지 않았거나 실패했으면 그 본문은 거짓이다.
    """
    p = _junit(tmp_path, [("tests.unit.a.test_x", "pass")] * 5 + [("tests.unit.a.test_y", "skip")])
    monkeypatch.setattr(mod, "_JUNIT", p)
    # 실행 총계는 6 인데 본문이 8 을 주장한다 → 실행 결과와 어긋난다
    assert mod.check_body_claim(_claim(8, 0), unit=6) == 1
    assert "실행" in capsys.readouterr().err


def test_body_claim_matching_the_actual_run_passes(tmp_path, monkeypatch, capsys):
    p = _junit(tmp_path, [("tests.unit.a.test_x", "pass")] * 5 + [("tests.unit.a.test_y", "skip")])
    monkeypatch.setattr(mod, "_JUNIT", p)
    assert mod.check_body_claim(_claim(5, 1), unit=6) == 0
    assert "실행 증거" in capsys.readouterr().out


def test_skip_split_may_differ_between_local_and_ci(tmp_path, monkeypatch, capsys):
    """🔴 skip **분해**는 대조하지 않는다 — 총계만 본다.

    본문 수치는 저자가 로컬에서 잰다(6-step ②). 환경 조건부 skip 때문에 로컬과 CI 의
    skip 수가 정당하게 갈린다 — 실측(2026-08-18): 로컬 `9 skipped` ↔ CI `5 skipped`
    (openai SDK 가 CI 에만 설치돼 5건이 CI 에서는 실행된다).

    초판은 `(passed, skipped)` 튜플을 그대로 비교해 **원리적으로 만족 불가**였고 CI 가 잡았다.
    Totals only: environment-conditional skips legitimately differ between local and CI.
    """
    p = _junit(tmp_path, [("tests.unit.a.test_x", "pass")] * 6 + [("tests.unit.a.test_y", "skip")])
    monkeypatch.setattr(mod, "_JUNIT", p)
    # 본문(로컬) 5 passed / 2 skipped · 실행(CI) 6 passed / 1 skipped — 총계 7 로 같다
    assert mod.check_body_claim(_claim(5, 2), unit=7) == 0
    assert "실행 증거" in capsys.readouterr().out


def test_failed_tests_make_the_claim_red_even_when_counts_add_up(tmp_path, monkeypatch, capsys):
    """🔴 `--collect-only` 가 원리적으로 못 보는 축 — 실패가 있으면 red.

    수집 6건 · 본문 「5 passed / 1 skipped」 로 합이 맞아도, 실제로는 1건이 **실패**했다.
    """
    p = _junit(tmp_path, [("tests.unit.a.test_x", "pass")] * 5 + [("tests.unit.a.test_y", "fail")])
    monkeypatch.setattr(mod, "_JUNIT", p)
    assert mod.check_body_claim(_claim(5, 1), unit=6) == 1
    assert "실패" in capsys.readouterr().err


def test_without_junit_it_falls_back_to_collection_and_says_so(tmp_path, monkeypatch, capsys):
    """산출물이 없으면 기존 수집 대조로 — 다만 **무엇을 못 쟀는지** 인쇄한다."""
    monkeypatch.setattr(mod, "_JUNIT", tmp_path / "absent.xml")
    assert mod.check_body_claim(_claim(6, 0), unit=6) == 0
    out = capsys.readouterr().out
    assert "수집" in out and "실행 증거 아님" in out


def test_fallback_without_a_collected_count_is_red(capsys):
    """🔴 junit 도 수집값도 없으면 대조할 실측이 없다 — 초록이 아니라 red."""
    assert mod.check_body_claim(_claim(6, 0), unit=None) == 1
    assert "실측" in capsys.readouterr().err
