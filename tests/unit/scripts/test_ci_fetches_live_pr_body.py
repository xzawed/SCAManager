"""수치 축은 **살아 있는** PR 본문을 읽는다 — 고정 페이로드가 아니라 (2026-08-21 실측).

## 사고 — 이 세션 CI 실패 9건 중 6건이 본문이었다

`ci.yml` 은 `PR_BODY: ${{ github.event.pull_request.body }}` 로 넘겼다. 그 값은
**이벤트가 만들어진 순간에 고정**된다. 그래서:

- push 후 본문을 고쳐도 그 실행에는 반영되지 않는다.
- `gh run rerun` 은 **원래 이벤트를 재생**하므로 낡은 본문을 다시 읽는다.
- 복구 수단이 「새 SHA」 하나뿐이 된다.

실측(2026-08-18~20): CI 실패 9건 중 **4건이 이 수치 축**, 2건이 형제 trace 축.
같은 기간 `gh pr edit`(push 후 본문 편집) **19회**. 즉 가드가 **고칠 수 없는 것을
검사**하고 있었다 — 저자가 본문을 고쳐도 그 실행은 영원히 낡은 값을 본다.

## 왜 커밋 메시지로 옮기지 않았나 (Grok claim-review `01a02149` P4)

수치를 커밋 메시지에 적는 안(B)은 **실패 4건에 애초에 발동하지 않는다** —
그 4건은 본문에 수치 라인이 **이미 있었고**, 다만 고정본이라 낡았을 뿐이다.
「본문에 없을 때만 커밋을 본다」는 폴백은 이 사고를 하나도 막지 못한다.

## 이 파일이 강제하는 것

1. PR 단계 수치 스텝이 **API 로 본문을 조회**한다 (`gh api ... /pulls/`).
2. 그 스텝이 `github.event.pull_request.body` 를 **쓰지 않는다** (고정본 폴백 금지).
3. 조회 실패 시 **fail-closed** — 빈 본문으로 조용히 넘어가지 않는다.
4. `pull-requests: read` 권한이 선언돼 있다 (없으면 조회가 404/403).

🔴 `read_pr_body()` 단일 리더는 그대로다 — 스크립트는 여전히 `PR_BODY` 환경변수
하나만 읽고, **누가 그 값을 채우는지**만 바뀐다. `test_pr_body_single_reader` 가
계속 그 불변식을 지킨다.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_STEP = "테스트 수치 ↔ 실측 대조 (PR — 차단)"


def _ci_text() -> str:
    text = _CI.read_text(encoding="utf-8")
    assert text.strip(), "ci.yml 이 비었다 — 빈 텍스트 위의 ✅ 는 fail-open"
    return text


def _pr_count_step(text: str) -> str:
    """PR 단계 수치 스텝의 블록(다음 `- name:` 전까지)."""
    i = text.index(f"- name: {_STEP}")
    nxt = text.find("      - name:", i + 10)
    return text[i:nxt if nxt > 0 else len(text)]


_FETCH_STEP = "PR 본문 조회 (살아 있는 값 — 고정 페이로드 아님)"


def _fetch_step(text: str) -> str:
    """본문을 조회하는 **별도 스텝**의 블록.

    🔴 조회는 수치 스텝 **안**이 아니라 앞선 별도 스텝이다 — 계약은 두 스텝에
    걸쳐 있다: 조회 스텝이 값을 만들고, 수치 스텝이 그것을 `PR_BODY` 로 받는다.
    (초판 테스트는 수치 스텝 안에서 `gh api` 를 찾아 구현이 옳은데도 red 였다.)
    """
    i = text.index(f"- name: {_FETCH_STEP}")
    nxt = text.find("      - name:", i + 10)
    return text[i:nxt if nxt > 0 else len(text)]


def test_the_body_is_fetched_from_the_api_and_wired_into_the_count_step():
    """🔴 살아 있는 본문 — 편집 후 재실행이 실제로 의미를 갖는다.

    두 축을 함께 본다: 조회 스텝이 API 를 부르는가, 그리고 수치 스텝이 **그 결과를**
    받는가. 하나만 보면 조회해 놓고 안 쓰는 상태가 통과한다.
    """
    text = _ci_text()
    fetch = _fetch_step(text)
    count = _pr_count_step(text)

    assert "gh api" in fetch and "/pulls/" in fetch, (
        "조회 스텝이 본문을 API 로 가져오지 않는다 — 고정 페이로드를 읽으면 "
        "저자가 본문을 고쳐도 그 실행은 영원히 낡은 값을 본다."
    )
    assert "steps.prbody.outputs.body" in count, (
        "수치 스텝이 조회 결과를 받지 않는다 — 조회해 놓고 쓰지 않으면 아무것도 안 바뀐다."
    )


def test_the_pr_count_step_does_not_read_the_frozen_event_payload():
    """🔴 폴백 금지 — 고정본이 남아 있으면 사고가 그대로 살아난다."""
    step = _pr_count_step(_ci_text())

    assert "github.event.pull_request.body" not in step, (
        "PR 수치 스텝이 아직 `github.event.pull_request.body` 를 읽는다. "
        "그 값은 이벤트 생성 시점에 고정되고 `gh run rerun` 이 그것을 재생한다."
    )


def test_the_fetch_fails_closed():
    """🔴 조회 실패가 **빈 본문**으로 흘러가면 축이 조용히 미실행이 된다.

    `check_body_claim` 은 수치 라인이 없으면 「미실행」을 인쇄하고 0을 돌려준다
    (봇·advisory 배려). 조회가 조용히 실패하면 그 경로로 떨어져 **초록**이 된다 —
    이 리포가 반복해 온 fail-open 이다.
    """
    step = _fetch_step(_ci_text())

    assert "set -euo pipefail" in step, (
        "fetch 스텝에 `set -euo pipefail` 이 없다 — `gh api` 실패가 빈 문자열로 흘러간다."
    )
    assert not re.search(r"\|\|\s*(true|echo|:)", step), (
        "실패를 삼키는 관용구(`|| true` 류)가 있다 — 조회 실패는 red 여야 한다."
    )


def test_the_workflow_declares_pull_requests_read():
    """🔴 권한 — 없으면 `gh api /pulls/` 가 404/403 이고, 그때 fail-closed 가 발동한다.

    즉 권한 누락은 조용한 초록이 아니라 red 로 드러난다. 그래도 선언은 해 둔다 —
    매 PR 이 red 인 상태로 방치되면 가드가 곧 꺼진다.
    """
    text = _ci_text()
    head = text[: text.index("jobs:")]

    assert re.search(r"^\s*pull-requests:\s*read", head, re.M), (
        "워크플로 `permissions:` 에 `pull-requests: read` 가 없다 — 본문 조회가 실패한다."
    )


def test_the_single_reader_invariant_is_untouched():
    """대조군 — 스크립트 쪽은 바뀌지 않았다.

    바뀐 것은 **누가 `PR_BODY` 를 채우는가**뿐이고, 읽는 지점은 여전히
    `read_pr_body()` 하나다. 그 불변식은 `test_pr_body_single_reader.py` 가 지킨다.
    """
    step = _pr_count_step(_ci_text())

    assert "PR_BODY:" in step, "스텝이 `PR_BODY` 를 여전히 export 해야 한다"
    assert "check_test_count_sync.py" in step, "스텝이 수치 가드를 실행해야 한다"


# ── 하니스 상한 ↔ 서브프로세스 허용치 (2026-08-21 CI 실측) ────────────────
#
# 🔴 `pytest.ini` 의 `--timeout=30` 이 실바이너리 테스트의 `timeout=180` 보다 **작아서**
#    180초 허용이 처음부터 도달 불가였다. `golangci-lint` 가 콜드 캐시에서 30초를
#    넘기며 `Failed: Timeout (>30.0s)` 로 죽었다 — 그전까지는 우연히 안에 들어왔을 뿐이다.
#    두 값이 따로 늙으면 같은 사고가 조용히 돌아온다.


def test_real_binary_tests_raise_the_harness_timeout_above_the_subprocess_allowance():
    """🔴 실바이너리 파일이 하니스 상한을 서브프로세스 허용치까지 올려 두는가."""
    target = _ROOT / "tests" / "integration" / "test_contracted_analyzers_real_binary.py"
    text = target.read_text(encoding="utf-8")
    ini = (_ROOT / "pytest.ini").read_text(encoding="utf-8")

    m = re.search(r"--timeout=(\d+)", ini)
    assert m, "pytest.ini 에서 전역 timeout 을 못 읽었다"
    harness = int(m.group(1))

    assert "pytestmark = pytest.mark.timeout(" in text, (
        f"실바이너리 파일에 `pytestmark` 상한 상향이 없다 — 전역 {harness}s 가 그대로 적용돼 "
        "네트워크·컴파일을 포함하는 실행이 그 안에 못 들어온다."
    )
    n = re.search(r"_REAL_BINARY_TIMEOUT\s*=\s*(\d+)", text)
    assert n, "`_REAL_BINARY_TIMEOUT` 상수가 없다 — 두 값이 리터럴로 갈린다"
    assert int(n.group(1)) > harness, (
        f"서브프로세스 허용 {n.group(1)}s 가 하니스 상한 {harness}s 보다 크지 않다 — "
        "허용치가 도달 불가다."
    )
    assert "timeout=_REAL_BINARY_TIMEOUT" in text, (
        "`_run` 이 상수를 쓰지 않는다 — 리터럴이면 두 값이 따로 늙는다."
    )
