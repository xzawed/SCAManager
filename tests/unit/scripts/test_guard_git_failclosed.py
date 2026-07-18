"""CI 배선 가드 3종의 git 실패 fail-CLOSED 계약 (회고 2026-07-19 P1).

결함: `_git` 이 `returncode`/`stderr` 를 버리고 실패 시 `""` 를 반환했다. 이 가드들은
"결과 없음 = ✅ 위반 없음 + exit 0" 으로 보고하므로, **git 이 실패하면 무조건 통과**한다
(fail-OPEN). 잘못된 base SHA·shallow clone·detached 상태 등 CI 흔한 조건에서 가드가
조용히 무력화되고, 로그에는 성공 배너만 남는다 — #1094 형 '가드가 무력한데 green' 의 CI 판.
Defect: `_git` discarded returncode/stderr and returned "" on failure. Since these guards report
"no findings = pass", any git failure silently disabled them while printing a success banner.

🔴 **PARITY GUARD** — `_git` 은 세 스크립트에 의도적으로 중복 존재한다(`.claude/hooks/` 와 달리
동일 디렉토리지만, 공유 모듈 도입 시 `python scripts/X.py` 직접 실행과 `from scripts.X import`
테스트 임포트의 경로 해석이 갈라져 취약해진다 — 정책 16 최소 추상화). 대신 이 테스트가
**세 사본의 동작 동등성**을 강제한다. 한 곳을 고치면 나머지도 같이 고쳐야 통과한다.
The `_git` helper is intentionally duplicated across the three scripts; this test enforces
behavioral parity so a fix in one must be applied to all.
"""
import pytest

from scripts.check_dead_code import _git as dead_code_git
from scripts.check_dual_import import _git as dual_import_git
from scripts.check_noqa_sideeffect import _git as noqa_git

# (이름, 호출 래퍼) — check_dual_import 는 가변인자, 나머지는 리스트 인자.
# (name, caller) — check_dual_import 는 가변인자라 언패킹 lambda 가 필요하고,
# 나머지 둘은 리스트 인자를 그대로 받으므로 **함수 참조 그대로** 쓴다.
# 🔴 `lambda args: f(args)` 는 `f` 와 동일 — CodeQL py/unnecessary-lambda (alert #550·#551).
#    본 PR 의 신규 CodeQL 게이트가 머지 전에 적발했다(자초 CodeQL 4회차, 첫 pre-merge 차단).
# (name, caller) — dual_import takes varargs so it needs the unpacking lambda; the other two
# take the list directly, so pass the function reference (a wrapping lambda is redundant).
_GIT_HELPERS = [
    ("check_dead_code", dead_code_git),
    ("check_noqa_sideeffect", noqa_git),
    ("check_dual_import", lambda args: dual_import_git(*args)),
]

# 반드시 실패하는 git 호출 — 존재하지 않는 ref.
# A git invocation that must fail — a ref that cannot exist.
_FAILING_ARGS = ["diff", "--name-only", "refs/__no_such_ref_for_guard_test__", "HEAD"]
# 반드시 성공하는 git 호출 — 대조군(오탐 차단).
# A git invocation that must succeed — control against over-strictness.
_OK_ARGS = ["rev-parse", "HEAD"]


@pytest.mark.parametrize("name,call", _GIT_HELPERS, ids=[n for n, _ in _GIT_HELPERS])
def test_git_failure_is_fail_closed(name, call):
    """🔴 git 실패 시 조용한 빈 문자열 대신 **loud 종료** — fail-OPEN 봉인.

    긍정 통제: 이 단언이 죽으면 세 가드 전부가 git 실패에서 spurious-pass 로 돌아간다.
    """
    with pytest.raises(SystemExit) as exc:
        call(_FAILING_ARGS)
    assert exc.value.code == 2, (
        f"{name}._git 이 git 실패에 exit 2(가드 실행 불가)로 종료해야 한다 — "
        f"실제 {exc.value.code}. exit 1 은 '위반 발견' 과 혼동된다."
    )


@pytest.mark.parametrize("name,call", _GIT_HELPERS, ids=[n for n, _ in _GIT_HELPERS])
def test_git_success_still_returns_stdout(name, call):
    """🔴 부정 통제 — 정상 git 호출은 그대로 stdout 반환(과잉 엄격 차단)."""
    out = call(_OK_ARGS)
    assert out.strip(), f"{name}._git 이 정상 호출에서 빈 문자열 — 과잉 엄격"
    assert len(out.strip()) == 40, "rev-parse HEAD 는 40자 SHA 를 반환해야 한다"


def test_all_three_helpers_covered():
    """세 CI 배선 가드가 모두 이 parity 검사에 포함 — 신규 가드 추가 시 누락 방지."""
    assert len(_GIT_HELPERS) == 3
    assert {n for n, _ in _GIT_HELPERS} == {
        "check_dead_code", "check_noqa_sideeffect", "check_dual_import",
    }
