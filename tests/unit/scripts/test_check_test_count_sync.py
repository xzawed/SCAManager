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
# 🔴 이 축이 증명하지 않는 것 (정직 기준): 수치를 **아예 안 적으면** 축이 돌지 않는다.
#   그래서 미검출은 조용한 통과가 아니라 *"안 쟀음"* 을 명시 출력한다 — 빈 범위 위의 ✅ 를
#   만들지 않기 위해서다. 우회로를 닫는 것(수치 라인 의무화)은 dependabot 등 봇 PR 을
#   깨뜨리므로 별도 결정 영역이다.

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


def test_body_claim_uses_the_last_match():
    assert mod.parse_body_claim(f"{_REAL_ARROW}\n{_REAL_TABLE}\n") == (6985, 9)


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
    """`--advisory-drift` 가 완화하는 것은 **STATE 드리프트**뿐이다 — 본문 거짓 수치는 아니다."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, _REAL_MISMATCH)
    assert mod.main(["--advisory-drift"]) == 1


def test_absent_claim_is_reported_not_silently_green(monkeypatch, tmp_path, capsys):
    """🔴 빈 범위 위의 ✅ 는 fail-open 이다 — 미검출은 '안 쟀음' 으로 발화해야 한다."""
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    _patch_body(monkeypatch, "수치 라인이 없는 본문")
    assert mod.main([]) == 0
    out = capsys.readouterr().out
    assert "미실행" in out, "미검출이 조용히 통과하면 이 축은 관측되지 않는다"


def test_body_claim_axis_reads_the_single_hardened_reader(monkeypatch, tmp_path):
    """배선(불변식 3) — 새 축이 별도 env 리더를 만들지 않고 기존 단일 리더를 탄다.

    `deferral_carriers()` 를 끊으면 축이 죽어야 한다. 죽지 않으면 어딘가에서 본문을
    따로 읽고 있다는 뜻이고, 그건 `test_pr_body_single_reader` 가 막는 결함이다.
    """
    _patch_state(monkeypatch, tmp_path, 7022, 6851)
    _patch_counts(monkeypatch, 6851, 171)
    monkeypatch.setattr(mod, "deferral_carriers", lambda: ("", ""))
    assert mod.main([]) == 0          # 본문이 없으면 미실행
    _patch_body(monkeypatch, _REAL_MISMATCH)
    assert mod.main([]) == 1          # 같은 리더로 본문이 오면 red
