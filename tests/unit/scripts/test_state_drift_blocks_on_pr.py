"""STATE 수치 drift 가 **PR 시점에** 차단되는가 (P2 · 2026-08-07 사고 대응).

## 사고 (2026-08-06~07)

테스트 수를 `6840` 으로 오판독했다. 그 값 하나가 `check_docs_sync --fix` 로
**4지점(STATE 종합·추적셀·README 배지 2개)에 자동 전파**됐다.

그래서 두 관측자가 정반대를 말했다:

| 관측자 | 판정 | 무엇을 재는가 |
|---|---|---|
| `check_docs_sync` | **exit 0 ✅** | 문서 **사본끼리** 대조 — 전부 함께 틀리면 초록 |
| `check_test_count_sync` | **exit 1 🔴** | `--collect-only` **실측**과 대조 |

후자가 정확히 잡았지만 CI 가 PR 에서 `--advisory-drift`(exit 0)로 돌려 **막지 않았고**,
main push 에서만 enforce 돼 **막을 수 없는 곳에서** 빨개졌다 — main CI 2연속 red.

🔴 그 advisory 를 유지하던 근거는 *"브랜치 보호 부재라 red 는 머지를 막지 못한다"* 는
주석이었는데, 그 서술은 이미 거짓이었다(required 10종 + `enforce_admins: true` 실측).
**stale 한 정직 고지가 fail-open 의 알리바이가 된 형태**다.

## 이 파일이 고정하는 것

1. CI 의 PR step 이 `--advisory-drift` 를 **쓰지 않는다**
2. 이월은 사라지지 않고 **명시 마커**(`STATE-sync-deferred:`)로만 가능하다 — 사유 16자 이상
3. 마커 사용이 **job summary 에 계수**된다(로그 안쪽 `::notice` 만으로는 아무도 안 본다)
4. stale 한 "브랜치 보호 부재" 서술이 되살아나지 않는다
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_SCRIPT = _ROOT / "scripts" / "check_test_count_sync.py"


# ── ① CI 배선 — PR 에서 advisory 를 쓰지 않는다 ─────────────────────────


def _pr_step_block() -> str:
    """PR 조건이 걸린 테스트-수치 step 블록."""
    ci = _CI.read_text(encoding="utf-8")
    blocks = [b for b in ci.split("- name:") if "check_test_count_sync.py" in b]
    assert blocks, "테스트 수치 step 을 못 찾았다 — 이 가드가 공허해졌다"
    pr_blocks = [b for b in blocks if "pull_request" in b]
    assert pr_blocks, "PR 조건이 걸린 테스트 수치 step 이 없다"
    return pr_blocks[0]


def test_pr_step_does_not_use_advisory_drift():
    """🔴 PR 에서 advisory 면 드리프트가 **막을 수 없는 곳**(main push)에서만 빨개진다.

    실사고: 오판독한 정수가 4지점에 전파돼 PR 을 통과하고 머지된 뒤 main CI 2연속 red.
    """
    block = _pr_step_block()
    assert "--advisory-drift" not in block, (
        "PR step 이 아직 `--advisory-drift` 를 쓴다 — 드리프트가 PR 을 통과한다.\n"
        "→ 이월이 필요하면 `STATE-sync-deferred:` 마커로(명시·계수), advisory 로가 아니라."
    )


def test_pr_step_passes_the_body_so_the_marker_can_work():
    """대조군 — 마커를 볼 수 없으면 이월 경로가 죽고 가드가 곧 꺼진다(정책 17)."""
    assert "PR_BODY" in _pr_step_block(), (
        "PR step 이 `PR_BODY` 를 넘기지 않는다 — 이월 마커가 원리적으로 동작하지 않는다"
    )


def test_main_push_step_still_enforces():
    """main push 축은 그대로 남아야 한다 — PR 을 막는다고 main 관측을 버리지 않는다."""
    ci = _CI.read_text(encoding="utf-8")
    blocks = [b for b in ci.split("- name:") if "check_test_count_sync.py" in b]
    assert any("push" in b and "--advisory-drift" not in b for b in blocks), (
        "main push enforce step 이 사라졌다"
    )


# ── ② stale 알리바이 재발 차단 ──────────────────────────────────────────


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", "scripts/check_test_count_sync.py"])
def test_no_stale_claim_that_branch_protection_is_absent(path: str):
    """🔴 *"브랜치 보호 부재"* 서술이 **fail-open 의 알리바이**로 쓰였다.

    그 서술은 거짓이다 — required 10종 + `enforce_admins: true` 가 살아 있다.
    거짓 고지가 되살아나면 같은 완화 논리가 다시 정당화된다.

    🔴 **판정은 '인용됐는가' 라는 구조로 한다 — 키워드 근접이 아니라.**

    초판은 같은 줄만 봐서 *정정 기록 자체*를 막았고(`ci.yml` 이 구 서술을 인용한 뒤 다음
    줄에서 반박한다), 그것을 ±2줄 창으로 완화했더니 **정정 문구 옆에 stale 주장을 끼워
    넣으면 면제**되는 공허가 생겼다(뮤테이션 M3 이 GREEN 이었다).

    정직한 신호는 근접이 아니라 **인용 부호**다: 구 서술을 기록으로 남길 때는 반드시
    따옴표/백틱 안에 넣는다. **따옴표 밖의 맨 주장**만 위반으로 본다.
    메모리 `feedback-prose-guard-both-ways` — 산문 가드는 양방향으로 틀리므로
    열거/구조 문맥을 쓴다.
    """
    lines = (_ROOT / path).read_text(encoding="utf-8").splitlines()
    # 구 서술이 따옴표·백틱 **안**에 있으면 인용(기록)으로 본다.
    quoted = re.compile(r"""["'`][^"'`]*(브랜치 보호 부재|no branch protection)[^"'`]*["'`]""")
    offenders = [
        line.strip() for line in lines
        if ("브랜치 보호 부재" in line or "no branch protection" in line)
        and not quoted.search(line)
    ]
    assert not offenders, (
        f"{path} 에 '브랜치 보호 부재' 서술이 정정 표시 없이 남아 있다 — "
        "그 서술이 advisory 유지의 근거로 쓰였다:\n  " + "\n  ".join(offenders)
    )


# ── ③ 이월 마커의 행동 계약 (실행 관측) ─────────────────────────────────


def test_deferral_marker_requires_a_substantive_reason():
    """마커는 **사유 16자 이상**을 요구한다 — 한 글자로 빠져나갈 수 없다."""
    import scripts.check_test_count_sync as mod  # noqa: PLC0415

    assert mod._DEFERRED.search("STATE-sync-deferred: 병렬 PR 이 STATE 를 건드려 이월합니다")
    assert not mod._DEFERRED.search("STATE-sync-deferred: x")
    assert not mod._DEFERRED.search("STATE-sync-deferred:")


def test_documenting_the_marker_does_not_self_defer():
    """🔴 마커를 **설명하는 문장**이 이월로 오인되면 안 된다.

    정책 19 면제 마커가 **자기를 문서화하는 PR** 을 면제해 버린 실사고와 같은 클래스다.
    """
    import scripts.check_test_count_sync as mod  # noqa: PLC0415

    prose = "이월하려면 `STATE-sync-deferred: <사유>` 를 본문에 적으세요 — 16자 이상."
    assert not mod._DEFERRED.search(prose), "마커 설명문이 이월로 인식됐다"


def test_deferral_is_recorded_in_the_job_summary(tmp_path, monkeypatch):
    """🔴 `::notice` 만으로는 **아무도 안 본다** — 사람이 여는 자리에 누적돼야 한다.

    이월 남용은 한 건씩 보면 정상이고 추세로만 드러난다.
    """
    import scripts.check_test_count_sync as mod  # noqa: PLC0415

    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    mod._append_step_summary("- ⏭️ **STATE 수치 동기화 이월**\n  - 사유: 테스트 사유입니다\n")
    text = summary.read_text(encoding="utf-8")
    assert "이월" in text, f"이월 사실이 summary 에 없다: {text!r}"
    assert "사유" in text, f"사유가 없으면 추세를 읽을 수 없다: {text!r}"


def test_the_deferral_branch_actually_calls_the_summary_writer():
    """🔴 위 테스트는 헬퍼를 **직접 호출**한다 — `main()` 의 호출부를 지워도 초록이다.

    실측: 호출부를 `_noop_summary(` 로 바꾸는 뮤테이션에서 스위트가 **GREEN** 이었다.
    이 저장소가 R65 에서 잡아낸 결함 클래스(*"모든 가드가 스파이/패치라 기록된다가
    한 번도 관측된 적 없음"*)를 이 파일이 그대로 재생산한 것이다.

    그래서 **배선**을 따로 단언한다 — 이월 분기 안에서 실제로 호출되는지 AST 로 본다.
    """
    import ast  # noqa: PLC0415

    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_append_step_summary"]
    assert calls, (
        "`main()` 이 `_append_step_summary` 를 호출하지 않는다 — 이월이 job summary 에 "
        "누적되지 않아 추세가 관측 불가해진다(헬퍼만 존재하는 dead code)."
    )


def test_summary_write_failure_never_changes_the_verdict(monkeypatch):
    """기록 실패가 판정을 바꾸면 안 된다 — 로깅이 게이트를 흔들면 그 자체가 결함이다."""
    import scripts.check_test_count_sync as mod  # noqa: PLC0415

    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent-dir/summary.md")
    mod._append_step_summary("x")  # 예외가 나면 이 테스트가 실패한다
