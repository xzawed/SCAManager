"""`check_test_count_sync.py` — ground-truth 축의 계약 (회고 P0-D · R25 · Grok 019fb930).

🔴 이 파일의 본체는 **fail-closed 부정 통제**다. "일치하면 통과"(양성)보다 **"도구가 죽거나
형식이 바뀌었을 때 조용히 초록이 되지 않는가"**(음성)가 이 축의 존재 이유다 — check_docs_sync
가 5지점 동시 오류에 GREEN 이던 것이 이 가드가 태어난 이유이므로, 이 가드 자신이 같은 방식으로
죽으면 안 된다.

Contract tests for the ground-truth axis. The negative controls are the point: the guard must not
go silently green when the tool dies or the format drifts — that failure shape is why it exists.
"""
import subprocess
from pathlib import Path

import pytest

import scripts.check_test_count_sync as mod
from scripts.check_docs_sync import _STATE_TOTAL as _DOCS_SYNC_STATE_TOTAL
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


# ── STATE 정규식 (PARITY + fail-closed) ──────────────────────────────────


def test_state_regex_parity_with_docs_sync():
    """🔴 PARITY GUARD — `check_docs_sync._STATE_TOTAL` 과 동일 패턴 의무.

    runtime import 결합 대신 사본 + 이 동등성 단언으로 drift 를 막는다(testing.md 패턴).
    한쪽만 바뀌면 두 가드가 서로 다른 STATE 형식을 요구하는 모순이 된다.
    """
    assert mod._STATE_TOTAL.pattern == _DOCS_SYNC_STATE_TOTAL.pattern


def test_state_counts_reads_the_live_file():
    """양성 통제 — 실제 STATE.md 에서 (전체, 단위)를 읽는다."""
    got = mod.state_counts((_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8"))
    assert got is not None
    total, unit = got
    assert total > unit > 0


def test_state_counts_none_on_format_drift():
    """🔴 형식이 바뀌면 None — 조용히 0 이나 옛값을 돌려주면 축이 소멸한 채 초록이 된다."""
    assert mod.state_counts("전체 6205 수집 (볼드 없음)") is None


# ── main — 모드별 판정 (fail-closed 는 모드 무관) ────────────────────────


@pytest.fixture(autouse=True)
def _no_ambient_pr_body(monkeypatch):
    """🔴 CI 는 `PR_BODY` 를 **실제로** 넘긴다 — 테스트를 그 환경에서 격리한다.

    본문 수치 축(R48)을 붙이자 기존 테스트 2건이 **CI 에서만** 깨졌다: 테스트는
    `collect_count` 를 90 같은 합성값으로 패치하는데, `deferral_carriers()` 는 패치되지
    않아 **진짜 PR 본문**(7000 passed / 9 skipped)을 읽어 왔다 → 불일치 → `main` 이 1.
    🔴 로컬은 `PR_BODY` 미설정이라 축이 '미실행' 이었고 **전건 초록이었다** — `pre_push_gate`
    가 매번 인쇄하는 로컬↔CI 이원(backlog R30)이 실제로 발현한 사례다.

    기본값을 비워 두고, 본문을 보는 테스트만 `_patch_body` 로 **명시 주입**한다.
    🔴 저자·SHA env 도 지운다 — CI PR job 은 `PR_HEAD_SHA` 를 실제로 심고, 남기면
    `main()` 이 PR 컨텍스트로 오판해 수치 부재 테스트가 CI 에서만 red 가 된다.
    CI really sets PR_BODY; default it empty so tests opt in explicitly.
    """
    monkeypatch.setattr(mod, "deferral_carriers", lambda: ("", ""))
    for key in (
        "PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA",
        "PR_AUTHOR_LOGIN", "PR_AUTHOR_TYPE",
    ):
        monkeypatch.delenv(key, raising=False)


def _patch_counts(monkeypatch, unit: int, integration: int):
    counts = {"tests/unit": unit, "tests/integration": integration}
    monkeypatch.setattr(mod, "collect_count", lambda p: counts[p])


def _patch_state(monkeypatch, tmp_path, total: int, unit: int):
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "STATE.md").write_text(
        f"**종합 수치**: 전체 **{total}** 수집 (단위 **{unit}** + 통합 x)\n", encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_ROOT", tmp_path)


def test_match_exits_zero(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path, 100, 90)
    _patch_counts(monkeypatch, 90, 10)
    assert mod.main([]) == 0


def test_drift_fails_in_enforce_mode(monkeypatch, tmp_path):
    """🔴 main push(기본 모드): drift = exit 1 — 이게 배치 이월의 종결 신호다."""
    _patch_state(monkeypatch, tmp_path, 100, 90)
    _patch_counts(monkeypatch, 95, 10)
    assert mod.main([]) == 1


def test_drift_passes_in_advisory_mode(monkeypatch, tmp_path, capsys):
    """PR: drift 는 loud 경고 + exit 0 — 병렬 PR 의 STATE 충돌을 강제하지 않는다."""
    _patch_state(monkeypatch, tmp_path, 100, 90)
    _patch_counts(monkeypatch, 95, 10)
    assert mod.main(["--advisory-drift"]) == 0
    assert "drift" in capsys.readouterr().out


def test_tool_failure_fails_even_in_advisory_mode(monkeypatch, tmp_path):
    """🔴 도구 실패는 advisory 에서도 exit 1 — 이것이 `|| true` 와의 경계다 (Grok 계약).

    여기가 뚫리면 "PR 에서는 collect 가 죽어도 초록" = 가드가 아무것도 안 보는데 통과.
    """
    _patch_state(monkeypatch, tmp_path, 100, 90)

    def _boom(_path):
        raise RuntimeError("pytest collect 실패 (exit 2)")
    monkeypatch.setattr(mod, "collect_count", _boom)
    assert mod.main(["--advisory-drift"]) == 1


def test_state_regex_miss_fails_even_in_advisory_mode(monkeypatch, tmp_path):
    """🔴 STATE 형식 drift 도 모드 무관 exit 1 — 축 소멸을 조용히 넘기지 않는다."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "STATE.md").write_text("형식이 완전히 바뀐 STATE\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    assert mod.main(["--advisory-drift"]) == 1


def test_missing_state_file_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    assert mod.main([]) == 1


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


# ── CI 배선 — PR advisory / main enforce 2스텝 (호출 형태 관측) ──────────


def _ci_steps():
    import yaml
    ci = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    return [s for job in ci["jobs"].values() for s in job.get("steps", [])]


def test_ci_wires_blocking_step_for_pull_requests():
    """🔴 PR 스텝은 **차단**이어야 한다 — `--advisory-drift` 금지 (2026-08-07 계약 변경).

    ## 왜 계약이 바뀌었나

    이 테스트의 초판은 정반대를 못박고 있었다 — *"PR 스텝은 `--advisory-drift` 를 쓴다"*.
    그 계약이 실제 사고를 냈다: 오판독한 정수 하나가 `check_docs_sync --fix` 로 **4지점에
    자동 전파**돼 문서 사본은 완벽히 일치했고(그 가드는 ✅), ground-truth 가드는 정확히
    잡았지만 **PR 에서 exit 0** 이라 통과·머지됐다. 그리고 막을 수 없는 곳(main push)에서만
    빨개져 **main CI 가 2연속 red** 였다.

    advisory 를 정당화하던 근거는 *"브랜치 보호 부재라 red 가 머지를 막지 못한다"* 는
    주석이었는데 그것은 이미 거짓이었다(required 10종 + `enforce_admins: true` 실측).

    배치-PR 이월은 사라지지 않았다 — `STATE-sync-deferred:` **명시 마커**로 승격했고
    그 사용은 job summary 에 계수된다. 조용한 통과 → 보이는 결정.
    """
    hits = [
        s for s in _ci_steps()
        if invokes(s.get("run", ""), "scripts/check_test_count_sync.py")
        and "pull_request" in str(s.get("if", ""))
    ]
    assert hits, "PR 스텝이 없다 — 이 축이 PR 에서 아예 돌지 않는다"
    for step in hits:
        assert "--advisory-drift" not in step.get("run", ""), (
            "PR 스텝이 `--advisory-drift` 를 쓴다 — 드리프트가 PR 을 통과해 "
            "**막을 수 없는 곳(main push)에서만** 빨개진다(2026-08-07 실사고)."
        )
    assert any("PR_BODY" in str(s.get("env", {})) for s in hits), (
        "PR 스텝이 `PR_BODY` 를 넘기지 않는다 — 이월 마커가 원리적으로 동작하지 않는다"
    )
    env_blob = " ".join(str(s.get("env", {})) for s in hits)
    assert "PR_AUTHOR_LOGIN" in env_blob, (
        "PR 스텝이 `PR_AUTHOR_LOGIN` 을 넘기지 않는다 — 봇 판정이 본문 자기인증이 된다"
    )
    assert "PR_AUTHOR_TYPE" in env_blob, (
        "PR 스텝이 `PR_AUTHOR_TYPE` 을 넘기지 않는다 — 봇 판정이 본문 자기인증이 된다"
    )


def test_ci_wires_enforce_step_for_main_push():
    """🔴 main push 스텝 — advisory 플래그 **없이** + `if: push` (drift 시 red)."""
    hits = [
        s for s in _ci_steps()
        if invokes(s.get("run", ""), "scripts/check_test_count_sync.py")
        and "--advisory-drift" not in s.get("run", "")
    ]
    assert hits, "enforce 스텝이 없다 — main 에서 drift 가 영영 초록이다"
    assert any("push" in str(s.get("if", "")) for s in hits), (
        "enforce 스텝에 push 조건이 없다"
    )


# ── 본문 수치 축 (R48 — "돌렸는가" 대신 "본문 숫자가 기계값에서 파생됐는가") ──────
#
# 🔴 왜 이 축인가 (2026-08-08 회고 권고 + 2026-08-10 실측):
#   *"전체 테스트를 돌렸는가"* 는 자기 신고라 기계가 진위를 못 잰다. *"본문에 적힌 수가
#   실측 수집값과 같은가"* 로 바꾸면 잴 수 있다. 실측으로 오라클이 판별함을 확인했다 —
#   #1305 본문 6800+9=6809 vs 실측 6819(−10) · #1310 6841+9=6850 vs 6851(−1) ·
#   #1312 6860+9=6869 vs 6885(−16). 🔴 **base drift 가설은 배제됐다**: 브랜치 tip 에서
#   재측정해도 수집값이 머지 커밋과 같았다(6819·6851·6885) — 저자 수치가 실제로 틀렸다.
#
# 🔴 2026-08-15: 비봇 PR 의 수치 라인 부재는 red. 봇 PR · `--advisory-drift` · CI push
#   는 기존 *"미실행"* 문구 + 0. 이 축은 여전히 *신선도* 만 잰다 (R76).

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


def _patch_body(monkeypatch, body: str):
    monkeypatch.setattr(mod, "deferral_carriers", lambda: ("", body))


def test_body_claim_mismatch_fails_even_when_state_matches(monkeypatch, tmp_path):
    """🔴 이 축의 존재 이유 — STATE 가 맞아도 본문 숫자가 틀리면 red.

    #1310 이 정확히 이 형태였다: STATE·사본은 전부 일치했고 본문만 −1 이었다.
    """
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, _REAL_MISMATCH)          # 6841 + 9 = 6850 != 6851
    assert mod.main([]) == 1


def test_body_claim_match_passes(monkeypatch, tmp_path):
    """대조군 — 같은 경로에서 본문이 맞으면 초록이어야 한다(과교정 방지)."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, "pytest tests/unit  →  6842 passed / 9 skipped / EXIT=0")
    assert mod.main([]) == 0


def test_body_claim_mismatch_fails_in_advisory_mode_too(monkeypatch, tmp_path):
    """`--advisory-drift` 가 완화하는 것은 **STATE 드리프트**뿐이다 — 본문 거짓 수치는 아니다.

    🔴 **초판은 공허했다** (적대 감사 `wf_9a4878aa-eab` 적발): STATE 를 *일치*시켜 놓아
    `main` 이 STATE-일치 분기에서 먼저 반환했고, advisory 분기에는 **도달조차 못 했다**.
    그래서 그 분기가 `claim_rc` 를 버리고 있는데도 이 테스트가 초록이었다.
    이제 STATE 를 **드리프트**시켜 advisory 분기를 실제로 통과시킨다.
    """
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6900, 171)          # STATE 와 어긋나야 advisory 분기로 간다
    _patch_body(monkeypatch, "pytest tests/unit  →  6800 passed / 9 skipped")
    assert mod.main(["--advisory-drift"]) == 1


def test_advisory_branch_is_actually_reached_by_that_test(monkeypatch, tmp_path, capsys):
    """대조군 — 위 테스트가 정말 advisory 분기를 지나는지 배너로 확인한다(도달 증명)."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6900, 171)
    _patch_body(monkeypatch, "pytest tests/unit  →  6900 passed / 0 skipped")
    assert mod.main(["--advisory-drift"]) == 0     # 본문은 맞고 STATE 만 드리프트
    assert "(advisory)" in capsys.readouterr().out, "advisory 분기에 도달하지 못했다 — 단언이 공허하다"


def test_absent_claim_is_reported_not_silently_green(monkeypatch, tmp_path, capsys):
    """PR 컨텍스트가 없으면(로컬·push) 미검출은 '안 쟀음' + 0 — 매번 red 가 되면 안 된다.

    비봇 PR 의 수치 부재 red 는 `test_non_bot_missing_claim_is_red` 가 잰다.
    """
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    assert mod.main([]) == 0
    out = capsys.readouterr().out
    assert "미실행" in out, "미검출이 조용히 통과하면 이 축은 관측되지 않는다"


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


def test_advisory_flag_does_not_fail_on_missing_claim(monkeypatch, capsys):
    """`--advisory-drift` / 로컬 pre-push — 수치 부재를 hard-fail 하지 않는다."""
    monkeypatch.setenv("PR_AUTHOR_LOGIN", "xzawed")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "User")
    assert mod.check_body_claim(
        "수치 라인이 없는 본문", 6851, advisory=True,
    ) == 0
    assert "미실행" in capsys.readouterr().out


def test_main_requires_claim_in_pr_context_when_author_missing(
    monkeypatch, tmp_path,
):
    """배선: PR SHA 가 있으면 저자 env 부재도 비봇 → 수치 부재 red."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    monkeypatch.setenv("PR_HEAD_SHA", "deadbeef")
    assert mod.main([]) == 1


def test_advisory_drift_via_main_does_not_fail_on_missing_claim(
    monkeypatch, tmp_path, capsys,
):
    """로컬 `pre_push_gate --advisory-drift` 는 PR SHA 가 있어도 수치 부재를 막지 않는다."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    monkeypatch.setenv("PR_HEAD_SHA", "deadbeef")
    monkeypatch.setenv("PR_AUTHOR_TYPE", "User")
    assert mod.main(["--advisory-drift"]) == 0
    assert "미실행" in capsys.readouterr().out


def test_body_claim_axis_reads_the_single_hardened_reader(monkeypatch, tmp_path):
    """배선(불변식 3) — 새 축이 별도 env 리더를 만들지 않고 기존 단일 리더를 탄다.

    `deferral_carriers()` 를 끊으면 축이 죽어야 한다. 죽지 않으면 어딘가에서 본문을
    따로 읽고 있다는 뜻이고, 그건 `test_pr_body_single_reader` 가 막는 결함이다.
    """
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    monkeypatch.setattr(mod, "deferral_carriers", lambda: ("", ""))
    assert mod.main([]) == 0          # PR 컨텍스트 없음 → 미실행
    _patch_body(monkeypatch, _REAL_MISMATCH)
    assert mod.main([]) == 1          # 같은 리더로 본문이 오면 red
