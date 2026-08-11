"""pylint 진리값 가드 회귀 테스트 (문서감사 PR-4).

Regression tests for the pylint-score truth guard.

🔴 **왜 생겼나 (2026-08-12 실측)**: 배지·STATE 2지점·ci.yml 주석이 **10.00/10** 을 주장했는데
`pylint src/` 실측은 **9.99/10** 이었다(E1136 `config.py` · E1125 `ai_review.py` · C0302
`pipeline.py`). 5지점 중 어느 것도 집행자가 없었다 — `check_docs_sync.py` 는 Tests·FastAPI
배지만 보고, CI 는 `--fail-under=9.90` 리터럴만 강제하므로 9.99 도 10.00 주장도 전부 초록이었다.

🔴 **이 가드의 설계 핵심**: CI 의 `--fail-under` 를 **배지에서 파생**시킨다. 그러면 배지가
10.00 을 주장하는 순간 CI 가 10.00 을 강제하고, 못 지키면 **배지를 내리는 것이 유일한 통과
경로**가 된다. 산문이 게이트를 만족시킬 수 없다(AGENTS.md 불변식 1).
The CI floor is derived from the badge, so an inflated badge fails the build it claims to pass.
"""
import importlib.util
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SYNC_PATH = _REPO_ROOT / "scripts" / "check_docs_sync.py"

# 배지가 주장할 수 있는 하한 — 이 아래로 내리는 것은 '정정' 이 아니라 게이트 무력화다.
# 사이클 87 Tier B-1 이 정한 보수적 floor 를 그대로 계승한다.
_HISTORICAL_FLOOR = 9.90


def _load_sync():
    spec = importlib.util.spec_from_file_location("check_docs_sync", _SYNC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lint_badge_sites_agree():
    """🔴 본 회귀 가드 — 5지점이 같은 값을 말하는가."""
    sync = _load_sync()
    ok, msgs = sync.check_lint_badge(_REPO_ROOT)
    assert ok, "pylint 값 불일치:\n" + "\n".join(f"  {m}" for m in msgs)


def test_scan_is_not_vacuous():
    """anti-vacuity — 5지점을 실제로 뽑았는가. 정규식이 하나도 못 뽑으면 '초록' 이 아니다."""
    sync = _load_sync()
    sites = sync.lint_badge_sites(_REPO_ROOT)
    assert len(sites) == 5, f"지점 {len(sites)}개만 수집 — 5개여야 한다: {sites}"
    for name, value in sites:
        assert value is not None, f"{name} 에서 pylint 값을 못 읽었다"


def test_badge_value_is_not_below_the_historical_floor():
    """🔴 배지를 내려서 게이트를 통과하는 경로를 막는다.

    CI floor 가 배지에서 파생되므로, 배지를 9.00 으로 내리면 나쁜 코드도 통과한다.
    그 우회를 이 단언이 닫는다(정정은 허용, 무력화는 불허).
    """
    sync = _load_sync()
    sites = dict(sync.lint_badge_sites(_REPO_ROOT))
    assert sites["README.md"] >= _HISTORICAL_FLOOR, (
        f"배지 {sites['README.md']} < floor {_HISTORICAL_FLOOR} — 정정이 아니라 게이트 무력화다"
    )


def test_ci_derives_fail_under_from_the_badge():
    """🔴 **배선** — ci.yml 이 리터럴이 아니라 **배지에서 파싱한 값**을 쓰는가.

    리터럴 `--fail-under=9.90` 이 남아 있으면 배지는 장식일 뿐이다(산문이 게이트를 못 만든다).
    Wiring: the workflow must parse the badge, not hardcode the floor.
    """
    ci = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "badge/pylint-" in ci, (
        "ci.yml 이 배지를 파싱하지 않는다 — fail-under 가 리터럴이면 배지는 장식이다"
    )
    # 🔴 주석 줄은 제외한다 — 이 축을 설명하는 주석이 `--fail-under=9.99` 를 **인용**하는데,
    #    그것까지 위반으로 세면 정정 기록 자체가 막힌다(산문 가드가 양방향으로 틀리는 형태).
    #    실행되는 것은 `run:` 아래의 비-주석 줄뿐이다.
    # Skip comment lines: prose quoting the old literal is a record, not an invocation.
    executable = [ln for ln in ci.splitlines() if not ln.lstrip().startswith("#")]
    literals = [ln for ln in executable if re.search(r"--fail-under=\d", ln)]
    assert not literals, "리터럴 --fail-under 가 실행 줄에 남아 있다:\n" + "\n".join(literals)
    # 🔴 변수 경유 우회를 함께 막는다 — `score=9.90` 뒤 `--fail-under="$score"` 는 위 단언을
    #    통과하면서 배지를 다시 장식으로 만든다(Grok `019ff301` G.5 적발).
    # Block the variable detour: a literal assignment feeding the flag defeats the check above.
    assigned = [
        ln for ln in executable
        if re.search(r"^\s*(?:score|floor)\s*=\s*[\"']?\d", ln)
    ]
    assert not assigned, "floor 가 리터럴 대입으로 고정돼 있다:\n" + "\n".join(assigned)


def test_local_push_gate_derives_the_same_floor_as_ci():
    """🔴 **배선 파리티** — 로컬 `--full` 게이트가 CI 와 **같은 규칙**으로 floor 를 만드는가.

    한쪽만 리터럴이면 두 게이트가 서로 다른 것을 재고, 배지를 부풀려도 로컬은 초록이다
    (Grok `019ff301` P1). 여기서는 실제 함수를 호출해 값을 대조한다 — 산문 grep 이 아니다.
    """
    spec = importlib.util.spec_from_file_location(
        "pre_push_gate", _REPO_ROOT / "scripts" / "pre_push_gate.py"
    )
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    sync = _load_sync()
    badge = dict(sync.lint_badge_sites(_REPO_ROOT))["README.md"]
    assert float(gate.pylint_floor(_REPO_ROOT)) == pytest.approx(badge - 0.005), (
        "로컬 게이트의 floor 가 CI 규칙(배지 − 0.005)과 다르다"
    )


def test_ci_floor_allows_exactly_the_badge_rounding_width():
    """🔴 배지는 소수 2자리 **반올림** 표기 — 실점수가 최대 0.005 낮을 수 있다.

    실측(2026-08-12): 표기 9.99 · 배지 9.99 에서 `--fail-under=9.99` 는 **exit 18**,
    `9.90` 은 exit 0 이었다. 그래서 floor 는 배지 − 0.005 다.

    🔴 이 값을 **키우면** 게이트가 헐거워지고(10.00 배지가 9.99 코드를 통과시킨다),
    **지우면** 정직한 배지가 자기 빌드를 실패시킨다. 둘 다 이 축을 죽인다.
    실증: 배지 10.00 → floor 9.995 → pylint **exit 18**(부풀린 배지는 자기 빌드를 실패시킨다).
    """
    ci = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "0.005" in ci, (
        "반올림 허용폭(0.005)이 사라졌다 — 배지가 정직해도 CI 가 red 가 된다"
    )


@pytest.mark.parametrize("site", ["README.md", "README.ko.md"])
def test_mutating_a_badge_breaks_the_check(tmp_path, site):
    """뮤테이션 — 한 지점만 다른 값으로 바꾸면 red 여야 한다 (동치 검사가 실제로 동작)."""
    sync = _load_sync()
    # 실파일을 복제한 샌드박스에서 한 지점만 오염시킨다 (원본 불변).
    for rel in ("README.md", "README.ko.md", "docs/STATE.md", ".github/workflows/ci.yml"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((_REPO_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    target = tmp_path / site
    text = target.read_text(encoding="utf-8")
    mutated = text.replace("badge/pylint-9.99", "badge/pylint-9.55", 1)
    assert mutated != text, "뮤테이션이 파일을 바꾸지 못했다 — 앵커가 낡았다"
    target.write_text(mutated, encoding="utf-8")
    ok, msgs = sync.check_lint_badge(tmp_path)
    assert not ok, f"{site} 를 오염시켰는데 green 이다 — 동치 검사가 무동작"
    assert msgs, "불일치인데 사유가 비었다"
