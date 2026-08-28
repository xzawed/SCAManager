"""가드 스크립트의 git 실패 fail-CLOSED 계약 (회고 2026-07-19 P1).

결함: `_git` 이 `returncode`/`stderr` 를 버리고 실패 시 `""` 를 반환했다. 이 가드들은
"결과 없음 = ✅ 위반 없음 + exit 0" 으로 보고하므로, **git 이 실패하면 무조건 통과**한다
(fail-OPEN). 잘못된 base SHA·shallow clone·detached 상태 등 CI 흔한 조건에서 가드가
조용히 무력화되고, 로그에는 성공 배너만 남는다 — #1094 형 '가드가 무력한데 green' 의 CI 판.
Defect: `_git` discarded returncode/stderr and returned "" on failure. Since these guards report
"no findings = pass", any git failure silently disabled them while printing a success banner.

🔴 **PARITY GUARD** — `_git` 은 여러 스크립트에 의도적으로 중복 존재한다(`.claude/hooks/` 와 달리
동일 디렉토리지만, 공유 모듈 도입 시 `python scripts/X.py` 직접 실행과 `from scripts.X import`
테스트 임포트의 경로 해석이 갈라져 취약해진다 — 정책 16 최소 추상화). 대신 이 테스트가
**사본들의 동작 동등성**을 강제한다. 한 곳을 고치면 나머지도 같이 고쳐야 통과한다.
The `_git` helper is intentionally duplicated across sibling guards; this test enforces
behavioral parity so a fix in one must be applied to all.

🔴 **분류 대상은 파생값이다 — 열거가 아니다.** 초판은 `len(_GIT_HELPERS) == 3` 과 이름 3개
집합으로 "신규 가드 추가 시 누락 방지" 를 주장했다. 하드코딩된 개수는 신규를 **원리적으로**
못 잡는다 — 그 주장이 거짓인 채 초록이었고, 실제로 4번째(`check_witness_set_predicates`)가
그 초록 밑에서 fail-OPEN 으로 들어와 살아남았다. 그래서 지금은 `scripts/check_*.py` 를 AST 로
훑어 `_git*` 헬퍼를 **발견**하고, 발견된 것이 아래 두 부류 중 하나로 분류되지 않으면 red 다.
The candidate set is derived from the filesystem, never enumerated: a frozen count cannot
detect the very thing it claims to prevent.
"""
import ast
import pathlib

import pytest

from scripts.check_dead_code import _git as dead_code_git
from scripts.check_dual_import import _git as dual_import_git
from scripts.check_noqa_sideeffect import _git as noqa_git
from scripts.check_test_count_sync import is_real_deferral
from scripts.check_witness_set_predicates import _git as witness_git

_ROOT = pathlib.Path(__file__).resolve().parents[3]

# 부류 ① — git 실패에 **loud 종료**(exit 2). (이름, 호출 래퍼)
# Class ①: must exit(2) on git failure. check_dual_import/witness take varargs.
_GIT_HELPERS = [
    # dead_code_git·noqa_git 는 리스트 인자 하나 — bare 함수 참조로 충분(불필요 lambda 제거,
    #   CodeQL py/unnecessary-lambda #550·#551 봉인). 나머지 둘만 *args 언팩이라 lambda 유지.
    # The first two take one list arg → bare refs suffice; the others need the *args unpack.
    ("check_dead_code", dead_code_git),
    ("check_noqa_sideeffect", noqa_git),
    ("check_dual_import", lambda args: dual_import_git(*args)),
    ("check_witness_set_predicates", lambda args: witness_git(*args)),
]


def _test_count_sync_enforces_on_empty() -> None:
    """`_git_text` 의 빈 문자열이 **면제가 되지 않음**을 정본 술어로 증명한다.

    이 헬퍼는 실패 시 `""` 를 돌려주는 것이 설계다(docstring: "호출자가 fail-closed 로
    처리한다"). 그 주장이 참인지는 호출자에게 물어야 한다 — 이월 마커 판정 정본
    `is_real_deferral` 에 빈 텍스트를 주면 **이월 아님**이어야 집행이 선다.
    """
    assert not is_real_deferral(""), (
        "빈 커밋 메시지가 이월로 인정되면 git 실패가 곧 STATE 동기화 면제가 된다"
    )


# 부류 ② — 빈 문자열 반환이 **설계**인 것. 면제가 아니다: 호출자가 집행함을 위 함수가 증명한다.
# Class ②: returning "" is by design — the caller's enforcement is proven, not assumed.
_EMPTY_IS_ENFORCED = {"check_test_count_sync": _test_count_sync_enforces_on_empty}


def _discovered_git_helpers() -> dict[str, list[str]]:
    """`scripts/check_*.py` 에서 module-level `_git*` 헬퍼를 **AST 로** 발견한다.

    문자열 검색은 주석·docstring 안의 `def _git` 에도 맞는다 — 부분문자열이 상태를
    대신하지 않게 구조를 읽는다.
    Discover module-level `_git*` helpers by AST, never by substring search.
    """
    found: dict[str, list[str]] = {}
    for path in sorted((_ROOT / "scripts").glob("check_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("_git")
        ]
        if names:
            found[path.stem] = names
    return found

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


@pytest.mark.parametrize("name", sorted(_EMPTY_IS_ENFORCED), ids=sorted(_EMPTY_IS_ENFORCED))
def test_empty_output_is_still_enforced(name):
    """부류 ② — 빈 문자열을 돌려주는 헬퍼는 **호출자가 집행함**을 증명해야 남을 수 있다."""
    _EMPTY_IS_ENFORCED[name]()


def test_every_discovered_git_helper_is_classified():
    """🔴 `scripts/check_*.py` 의 모든 `_git*` 헬퍼가 두 부류 중 하나로 분류돼야 한다.

    분류 대상은 파일시스템에서 **파생**한다 — 개수를 세지 않는다. 새 가드가 `_git` 을
    들고 들어오면 여기서 red 가 되고, 저자는 fail-closed 로 만들거나(부류 ①)
    호출자 집행을 증명해야(부류 ②) 한다.
    """
    discovered = _discovered_git_helpers()
    assert discovered, (
        "scripts/check_*.py 에서 `_git*` 헬퍼를 하나도 발견하지 못했다 — "
        "탐지기가 눈멀었거나 glob 이 깨졌다(공허화)"
    )

    classified = {n for n, _ in _GIT_HELPERS} | set(_EMPTY_IS_ENFORCED)
    unclassified = sorted(set(discovered) - classified)
    assert not unclassified, (
        f"`_git*` 헬퍼를 가진 가드가 분류되지 않았다: {unclassified}. "
        f"발견된 헬퍼 = { {k: discovered[k] for k in unclassified} }. "
        "git 실패에 exit 2 로 만들어 _GIT_HELPERS 에 넣거나, 빈 문자열이 설계라면 "
        "호출자 집행을 증명하는 함수를 _EMPTY_IS_ENFORCED 에 등록하라."
    )

    stale = sorted(classified - set(discovered))
    assert not stale, (
        f"분류표가 실재하지 않는 스크립트를 들고 있다: {stale} — 이름이 바뀌었거나 삭제됐다"
    )
