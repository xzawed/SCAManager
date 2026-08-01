"""정책 19 집행 가드 검증 — seal 주장 ↔ claim-review 흔적 (`check_claim_review_trace.py`).

AGENTS.md 3-불변식 대응:

  1. **fail-closed** — 통과 조건이 "Grok 이라는 단어가 어딘가 있으면" 이 아니라 **구조**
     (헤딩 + session/claim/verdict 필드)여야 한다. 산문 한 줄로 충족되면 안 된다.
  2. **실경로 뮤테이션** — 이 저장소가 실제로 낸 seal 주장 문장으로 red 를 확인한다(합성 문자열 X).
  3. **배선** — `ci.yml` 이 실제로 이 스크립트를 실행하는지 YAML 구조로 확인한다.

추가 축: **셸 인젝션 방지** — PR 본문은 임의 사용자 입력이라 `run:` 에 보간하면 안 되고
env 로 전달돼야 한다. 이건 가드 자신의 보안 결함이 될 수 있어 별도로 고정한다.
"""
import pathlib

import pytest
import yaml

from tests.unit.scripts._wiring_shape import any_invokes
from scripts.check_claim_review_trace import (
    commit_messages,
    find_seal_claims,
    main,
    missing_trace_fields,
)

_REPO = pathlib.Path(__file__).resolve().parents[3]
_CI_YAML = _REPO / ".github" / "workflows" / "ci.yml"
_SCRIPT_REF = "scripts/check_claim_review_trace.py"

# 🔴 합성 문자열이 아니라 **이 저장소가 실제로 낸 seal 주장**(2026-07-29 PR #1229 본문·커밋).
# 그 주장들은 뒤늦은 claim-review 에서 BROKEN 판정을 받았다 — 이 가드가 잡았어야 할 바로 그 텍스트.
_REAL_SEAL_CLAIMS = [
    "fix(analyzer): 런타임 eslint 무동작 5-결함 봉인 — JS/TS 이슈 항상 0 = 점수 인플레",
    "## 실경로 뮤테이션 8/8 red (AGENTS.md 불변식 2)",
    "🔴 **fail-open → fail-closed**: 비-JSON stdout 은 RuntimeError 로 승격",
]

_GOOD_TRACE = """## Grok claim-review

- session: 019fadda-3609-7ab3-8d94-ebe23699008e
- claim: 무시 목록은 임의 집합이 될 수 없다
- verdict: BROKEN — 설정 파싱이 손실 투영이라 우회 4종 통과
"""


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """PR_* env 를 매 테스트마다 초기화 — 누수 시 결과가 서로 오염된다."""
    for key in ("PR_TITLE", "PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(key, raising=False)


def _run(monkeypatch, *, title="", body=""):
    monkeypatch.setenv("PR_TITLE", title)
    monkeypatch.setenv("PR_BODY", body)
    return main()


# ── 축 1: 탐지 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", _REAL_SEAL_CLAIMS)
def test_detects_real_seal_claims_from_this_repo(text):
    """이 저장소가 실제로 낸 seal 주장 문장을 탐지해야 한다 (합성 픽스처 아님)."""
    assert find_seal_claims(text), f"seal 주장을 놓쳤다: {text!r}"


def test_ordinary_text_is_not_flagged():
    """평범한 변경 설명은 트리거하지 않는다 — 오탐이 잦으면 가드를 끄게 된다(정책 17)."""
    body = "fix(ui): 대시보드 카드 정렬 수정\n\n테스트 3건 추가. 회귀 없음."
    assert not find_seal_claims(body)


# ── 축 2: fail-closed (산문으로 충족 불가) ────────────────────────────────────

def test_seal_claim_without_trace_fails(monkeypatch):
    """seal 주장 + 흔적 0 = exit 1. 이번 사고(#1229)가 정확히 이 상태였다."""
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body="테스트 통과. 회귀 없음.") == 1


def test_mentioning_grok_in_prose_is_not_enough(monkeypatch):
    """🔴 산문 한 줄로는 통과 못 한다 — `X in text` 형 가드였다면 여기서 fail-open 이 된다.

    통과 조건이 "Grok 이라는 단어의 존재" 면 저자가 한 문장 적고 초록을 받는다(불변식 1 위반).
    """
    body = "봉인 완료. Grok 으로 검토했습니다. 문제 없습니다."
    assert _run(monkeypatch, body=body) == 1


def test_heading_without_fields_fails(monkeypatch):
    """헤딩만 있고 session/claim/verdict 가 없으면 exit 1 (형식만 흉내낸 경우)."""
    body = "봉인했다.\n\n## Grok claim-review\n\n검토함.\n"
    assert _run(monkeypatch, body=body) == 1


@pytest.mark.parametrize("drop", ["session", "claim", "verdict"])
def test_each_required_field_is_load_bearing(monkeypatch, drop):
    """필수 필드 3종 각각이 독립적으로 필요하다 — 하나라도 빠지면 red."""
    body = "봉인했다.\n\n" + "\n".join(
        line for line in _GOOD_TRACE.splitlines() if not line.strip().startswith(f"- {drop}:")
    )
    assert _run(monkeypatch, body=body) == 1


def test_complete_trace_passes(monkeypatch):
    """seal 주장 + 구조화된 흔적 = exit 0."""
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=_GOOD_TRACE) == 0


@pytest.mark.parametrize("wrapped", [
    "- session: `019fadda-3609-7ab3-8d94-ebe23699008e`",
    "- session: '019fadda-3609-7ab3-8d94-ebe23699008e'",
    '- session: "019fadda-3609-7ab3-8d94-ebe23699008e"',
])
def test_session_id_may_be_code_quoted(monkeypatch, wrapped):
    """🔴 백틱/따옴표로 감싼 sessionId 도 인정 — 가드가 **자기 안내대로 적은 본문**을 막았다.

    실패 메시지의 예시가 `` `019fadf6-523e-...` `` 백틱 형태인데 정규식은 백틱을 거부해,
    안내를 그대로 따른 PR 본문이 exit 1 로 차단됐다(이 가드를 고치는 PR 자신이 그 사례).
    마크다운에서 ID 를 코드 표기하는 것은 자연스러우므로 허용한다.
    The failure message demonstrated a backticked example the regex rejected.
    """
    body = _GOOD_TRACE.replace(
        "- session: 019fadda-3609-7ab3-8d94-ebe23699008e", wrapped,
    )
    assert wrapped in body, "치환 미적용 — 픽스처 drift"
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=body) == 0


def test_empty_session_still_fails_when_quoted(monkeypatch):
    """대조군 — 따옴표 허용이 **빈 값 통과**로 새지 않는다(초판 결함 재발 방지)."""
    body = _GOOD_TRACE.replace(
        "- session: 019fadda-3609-7ab3-8d94-ebe23699008e", "- session: ``",
    )
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=body) == 1


def test_no_seal_claim_passes_without_trace(monkeypatch):
    """seal 주장이 없으면 흔적을 요구하지 않는다 — 모든 PR 에 마찰을 주지 않는다."""
    assert _run(monkeypatch, title="docs: 오타 수정", body="오타 1건.") == 0


def test_exemption_marker_requires_a_substantive_reason(monkeypatch):
    """면제 마커는 **실질적 사유**(16자 이상)를 요구한다 — 한 글자로 빠져나갈 수 없다.

    🔴 Grok 적발: 초판은 `\\S+` 라 `claim-review-not-required: x` 로 자기면제가 됐다.
    """
    good = "봉인했다.\nclaim-review-not-required: 2026-07-19 회고 보고서의 과거 주장 인용문이라 검증 대상 아님"
    assert _run(monkeypatch, body=good) == 0
    assert _run(monkeypatch, body="봉인했다.\nclaim-review-not-required: x") == 1
    assert _run(monkeypatch, body="봉인했다.\nclaim-review-not-required:") == 1


def test_documenting_the_marker_does_not_self_exempt(monkeypatch):
    """🔴 마커를 **설명하는 문장**이 면제로 오인되면 안 된다 — 실제로 일어났다(자기 적용 실측).

    이 가드를 신설한 PR 본문에 사용법 안내가 들어 있었고, 그 한 줄 때문에 seal 주장 13건이
    통과했다. 즉 **가드를 문서화하는 PR 이 스스로 면제**되는 구조였다.
    🔴 Prose explaining the marker must not count as the marker: the PR introducing this guard
    exempted itself this way (13 seal claims passed).
    """
    body = (
        "봉인했다.\n"
        "인용·회고 서술이면 `claim-review-not-required: <사유 16자 이상>` 를 적으세요.\n"
        "문장 중간에 claim-review-not-required: 이런 식으로 언급해도 마커가 아니다.\n"
    )
    assert _run(monkeypatch, body=body) == 1


def test_exemption_is_not_accepted_from_title_or_commits(monkeypatch):
    """🔴 면제는 **본문에서만** 유효 — 제목/커밋 메시지로 자기면제할 수 없다(Grok 적발)."""
    reason = "claim-review-not-required: 과거 회고 인용이라 검증 대상이 아님"
    assert _run(monkeypatch, title=f"fix: 봉인 완료 {reason}", body="테스트 통과") == 1


def test_empty_fields_do_not_satisfy_the_trace(monkeypatch):
    """🔴 값 없는 3줄로는 통과 못 한다 — "구조는 있는데 내용이 없는" 초록 차단(Grok 적발).

    초판은 키만 봐서 `session:` `claim:` `verdict:` **빈 3줄**이면 green 이었다.
    """
    body = "봉인했다.\n\n## claim-review\n- session:\n- claim:\n- verdict:\n"
    assert _run(monkeypatch, body=body) == 1


@pytest.mark.parametrize("field,blanked", [
    ("session", "- session:"),
    ("claim", "- claim: 짧음"),
    ("verdict", "- verdict:"),
])
def test_each_field_value_is_independently_required(monkeypatch, field, blanked):
    """🔴 필드마다 **값** 요구가 독립적으로 살아 있어야 한다.

    뮤테이션으로 발견: session 의 값 요구(`[0-9a-f]{8}-…`)를 지워도 claim/verdict 가 대신 red 를
    만들어 스위트가 green 이었다 — 그 분기가 load-bearing 이 아니었다는 뜻.
    🔴 Found by mutation: dropping session's value requirement left the suite green because other
    fields happened to fail — that branch was not load-bearing.
    """
    body = "봉인했다.\n\n" + "\n".join(
        blanked if line.strip().startswith(f"- {field}:") else line
        for line in _GOOD_TRACE.splitlines()
    )
    assert _run(monkeypatch, body=body) == 1


def test_bogus_verdict_value_is_rejected(monkeypatch):
    """verdict 는 닫힌 집합이어야 한다 — 임의 문자열(`I LIE`)은 거부."""
    body = _GOOD_TRACE.replace("verdict: BROKEN — 설정 파싱이 손실 투영이라 우회 4종 통과",
                               "verdict: I LIE")
    assert _run(monkeypatch, body="봉인했다.\n" + body) == 1


@pytest.mark.parametrize("reworded", [
    "fail closed 로 전환했다",           # 공백 변형
    "mutation 7 of 7 red 확인",           # N of N 변형
    "뮤테이션 전부 red",                   # 서술 변형
    "유출 없음을 확인했다",                # 부정 표현
])
def test_reworded_seal_claims_are_still_detected(reworded):
    """🔴 어휘 우회 변형도 탐지한다 — Grok 이 실측 제시한 우회 4종.

    (완전한 목록은 원리적으로 불가능하다. 여기 있는 것은 **실제로 제시된** 우회만 닫은 것이다.)
    """
    assert find_seal_claims(reworded), f"우회 변형을 놓쳤다: {reworded!r}"


def test_missing_trace_fields_reports_every_gap():
    """빠진 요소를 전부 열거해야 한다 — 하나씩 알려주면 왕복이 늘어난다."""
    gaps = missing_trace_fields("아무 흔적 없음")
    assert len(gaps) == 4, gaps          # 헤딩 + 필드 3


# ── 축 3: 배선 + 보안 ────────────────────────────────────────────────────────

def _ci_steps():
    workflow = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_ci_actually_runs_the_guard():
    """`ci.yml` 의 어떤 step 이 **실제로** 이 스크립트를 실행하는지 YAML 구조로 확인한다.

    주석에만 언급되고 실행되지 않는 상태(#1145 형 배선 누락)를 통과시키지 않기 위해
    산문 grep 이 아니라 `jobs.*.steps[].run` 을 파싱한다.
    """
    assert any_invokes([s.get("run", "") for s in _ci_steps()], _SCRIPT_REF), (
        f"{_SCRIPT_REF} 를 실행하는 CI step 이 없다 — 가드가 배선되지 않았다"
    )


def test_pr_body_is_passed_via_env_not_interpolated():
    """🔴 PR 본문을 `run:` 에 보간하면 **명령 인젝션**이다 — env 로만 전달돼야 한다.

    `run: python x.py "${{ github.event.pull_request.body }}"` 형태면 본문에
    `"; rm -rf / #` 를 적은 PR 이 CI 러너에서 임의 명령을 실행한다. 가드를 만들면서
    새 취약점을 여는 것을 막는 축.
    """
    steps = [s for s in _ci_steps() if _SCRIPT_REF in s.get("run", "")]
    assert steps, "가드 step 을 찾지 못했다"
    for step in steps:
        assert "github.event.pull_request.body" not in step.get("run", ""), (
            "PR 본문이 run: 에 보간됐다 — 명령 인젝션 위험"
        )
        assert "github.event.pull_request.title" not in step.get("run", "")
        env = step.get("env", {})
        assert "PR_BODY" in env and "PR_TITLE" in env, "PR 본문/제목이 env 로 전달되지 않았다"


def test_repo_integrity_job_checks_out_full_history():
    """🔴 가드가 속한 job 은 `fetch-depth: 0` 이어야 한다 — 얕은 clone 이면 커밋 축이 죽는다.

    `git log base..head` 가 base 부재로 실패하면 `commit_messages()` 가 빈 문자열을 돌려주고,
    **커밋 메시지에만 있는 seal 주장**을 영영 못 본다(Grok 적발 — 이 축은 테스트도 0건이었다).
    """
    workflow = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    job = next(j for j in workflow["jobs"].values()
               if any(_SCRIPT_REF in s.get("run", "") for s in j.get("steps", [])))
    checkout = next(s for s in job["steps"] if "actions/checkout" in str(s.get("uses", "")))
    assert checkout.get("with", {}).get("fetch-depth") == 0, (
        "가드 job 이 얕은 clone 이다 — PR 범위 커밋을 읽을 수 없어 커밋 축이 조용히 죽는다"
    )


def test_commit_axis_degrades_quietly_when_history_is_unavailable():
    """커밋 축은 이력이 없으면 **빈 문자열로 degrade** 한다 — 그래서 위 fetch-depth 가 필요하다.

    이 동작 자체는 의도된 것이지만(가드가 크래시하면 안 됨), **관측되지 않으면 조용한 무력화**가
    되므로 계약으로 고정한다.
    """
    assert commit_messages("0000000000000000000000000000000000000000", "HEAD") == ""


def test_guard_runs_on_pull_request_events():
    """PR 이벤트에서 실행돼야 한다 — push 전용이면 PR 본문을 볼 수 없다."""
    steps = [s for s in _ci_steps() if _SCRIPT_REF in s.get("run", "")]
    assert any("pull_request" in str(s.get("if", "")) for s in steps), (
        "가드 step 에 pull_request 조건이 없다"
    )


# ── 축 4: HTML 주석 비가시 영역 + 단수형 관용구 + 면제 가시화 (backlog R20) ────────
# 🔴 TDD 선행 — 본문 `_strip_html_comments` 스트리핑·단수형 seal 패턴·`::notice` annotation 은
#    아직 미구현이라 이 축의 비-대조군 테스트는 RED 가 정상이다.
# 🔴 TDD-first: body comment stripping, singular seal idioms, and the ::notice annotation are
#    not implemented yet — non-control tests in this axis are expected RED.


def test_trace_hidden_in_html_comment_does_not_satisfy(monkeypatch):
    """🔴 HTML 주석 안의 흔적은 흔적이 아니다 — GitHub 렌더링에서 리뷰어에게 보이지 않는다.

    현재는 exit 0 — 리뷰어에게 안 보이는 흔적이 가드를 통과시킨다(R20 실측 결함).
    seal 주장은 가시로 두고 흔적만 `<!-- -->` 에 숨기면 "가드 통과 + 리뷰어 비가시" 조합이
    성립한다 — 정책 19 가 끝내려던 "주장 + 흔적 0 + CI 초록" 무임승차가 형태만 바꿔 되살아난다.
    구현 계약: `main()` 은 **body 에만** `_strip_html_comments` 를 적용한 뒤 흔적을 찾는다
    (제목·커밋 메시지는 plain text 로 렌더되므로 스트리핑 없음).
    A trace hidden inside an HTML comment is invisible to reviewers on GitHub and must not
    satisfy the guard (today it does — the R20 measured defect).
    """
    body = _REAL_SEAL_CLAIMS[1] + "\n\n<!--\n" + _GOOD_TRACE + "\n-->"
    assert _run(monkeypatch, body=body) == 1


def test_exemption_hidden_in_html_comment_does_not_exempt(monkeypatch):
    """🔴 HTML 주석 안의 면제 마커는 면제가 아니다 — 보이지 않는 자기면제 차단.

    면제가 본문 한정인 이유("리뷰어가 보는 자리에 있어야 한다")와 같은 근거다 — 주석에
    숨긴 `claim-review-not-required:` 는 렌더링에서 사라지므로, 인정하면 리뷰어 모르게
    seal 주장이 통과하는 조용한 자기면제 경로가 된다.
    An exemption marker hidden in an HTML comment must not exempt: reviewers never see it,
    so honoring it reopens the silent self-exemption path.
    """
    body = "봉인했다.\n<!--\nclaim-review-not-required: 과거 회고 인용이라 검증 대상이 아님\n-->"
    assert _run(monkeypatch, body=body) == 1


def test_unterminated_html_comment_hides_the_rest(monkeypatch):
    """🔴 미종결 `<!--` 이후는 전부 비가시다 — GitHub 는 닫히지 않은 주석 뒤를 렌더하지 않는다.

    종결 쌍(`<!-- -->`)만 지우면 닫는 `-->` 를 빼는 것만으로 스트리핑을 우회할 수 있다.
    구현 계약: 미종결 `<!--` 이후 끝까지 제거 — GitHub 실제 렌더 동작과 일치시켜야
    "가드가 보는 텍스트 = 리뷰어가 보는 텍스트" 가 성립한다.
    GitHub hides everything after an unterminated `<!--`; stripping must drop to EOF, or
    omitting the closing marker becomes the trivial bypass.
    """
    body = _REAL_SEAL_CLAIMS[1] + "\n<!--\n" + _GOOD_TRACE
    assert _run(monkeypatch, body=body) == 1


def test_visible_trace_passes_even_with_comment_blocks_nearby(monkeypatch):
    """대조군 — 스트리핑이 **가시** 흔적까지 지우면 안 된다 (오탐이 잦으면 가드를 끄게 된다, 정책 17).

    PR 템플릿 표면은 안내 주석과 실작성 본문이 섞이므로, 주석 블록 **밖**의 가시 흔적이
    여전히 통과하는지를 계약으로 고정한다 (현 구현에서도 통과 — 스트리핑 도입 후 회귀 방지축).
    Control: a visible trace next to comment blocks must keep passing after stripping lands.
    """
    body = "<!-- 안내 주석 -->\n" + _REAL_SEAL_CLAIMS[1] + "\n\n" + _GOOD_TRACE
    assert _run(monkeypatch, body=body) == 0


def test_actual_pr_template_slot_does_not_satisfy_the_trace(monkeypatch):
    """🔴 실경로 — `.github/PULL_REQUEST_TEMPLATE.md` 의 주석 처리된 예시 슬롯은 흔적이 아니다.

    템플릿에는 `## Grok claim-review` 슬롯 전체가 **HTML 주석 안에** 실려 있다. 이 슬롯이
    흔적으로 인정되면 템플릿을 그대로 둔 **모든 PR** 이 무임승차한다 — 합성 픽스처가 아니라
    실파일을 body 로 써서 검증한다(불변식 2). 지금은 슬롯의 placeholder 값(`<Grok sessionId>`)
    이 필드 값 정규식을 우연히 못 채워 막히지만, 그 방어는 우연이다 — 템플릿에 예시 값이
    채워지는 순간 무너지므로 주석 스트리핑이 구조적 방어가 돼야 한다.
    Real-path: the commented-out example slot in the PR template must never satisfy the
    trace; today it fails only by accident of placeholder values, not by structure.
    """
    template = (_REPO / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    # 템플릿 drift 가드 — 슬롯 자체가 사라지면 이 테스트는 아무것도 검증하지 않는다
    # Template-drift guard: if the slot vanishes, this test would verify nothing
    assert "claim-review" in template, "템플릿 drift — claim-review 슬롯이 사라졌다"
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=template) == 1


def test_singular_count_mutation_idiom_is_detected():
    """🔴 단수형 카운트 관용구도 seal 주장이다 — 이 리포 실관용구 — STATE.md 세션13 서사가 실제로 쓴 형태.

    기존 `_SEAL_PATTERNS` 는 `N/N` · `N of N` · `전부/모두` 형만 잡아 `뮤테이션 6건 red` ·
    `뮤테이션 5종 red` 같은 단수형이 통과했다(R20 결함 2). 우회 어휘(§한계 3)가 아니라
    **이 저장소가 실제로 쓰는 자기 관용구**를 놓친 것이라 합성 문자열이 아닌 실관용구로 고정한다.
    Singular-count idioms (`뮤테이션 N건/N종 red`) are seal claims this repo actually writes
    (STATE.md session-13 narrative) and must be detected.
    """
    for idiom in ("뮤테이션 6건 red", "mutation 3건 red", "뮤테이션 5종 red"):
        assert find_seal_claims(idiom), f"단수형 seal 관용구를 놓쳤다: {idiom!r}"


def test_singular_idiom_without_red_is_not_flagged():
    """대조군 — red 없는 단순 개수 서술(`뮤테이션 6건 추가`)은 seal 주장이 아니다.

    단수형을 넓히며 `N건` 만으로 트리거하면 평범한 작업 보고("테스트 6건 추가")가 전부
    걸린다 — 오탐이 잦으면 가드를 끄게 된다(정책 17). red 동반이 판정선이어야 한다.
    Control: a plain count without `red` is not a seal claim — widening must not over-trigger.
    """
    assert not find_seal_claims("뮤테이션 6건 추가")


def test_exemption_use_emits_a_visible_annotation(monkeypatch, capsys):
    """🔴 면제 사용은 계량돼야 한다 — `::notice` GitHub annotation 으로 가시화(R20-a).

    면제 경로는 조용한 exit 0 이라 남용 추세가 관측되지 않는다("보이지 않는 우회 경로").
    구현 계약: exit 0 은 유지하되(면제 자체는 정당한 경로 — advisory) stdout 에
    `::notice` annotation(제목에 claim-review exemption 포함)을 추가 출력해 Actions UI
    에서 면제 사용이 보이게 한다.
    The exemption path stays exit 0 but must emit a `::notice` annotation so each use is
    observable in the Actions UI instead of silently green.
    """
    body = (
        "봉인했다.\n"
        "claim-review-not-required: 2026-07-19 회고 보고서의 과거 주장 인용문이라 검증 대상 아님"
    )
    assert _run(monkeypatch, body=body) == 0
    out = capsys.readouterr().out
    notice_lines = [line for line in out.splitlines() if line.startswith("::notice")]
    assert notice_lines, "면제 사용이 ::notice annotation 으로 가시화되지 않았다"
    assert any("claim-review" in line for line in notice_lines), (
        "::notice 라인에 claim-review 식별자가 없다 — 어떤 가드의 면제인지 구분 불가"
    )
