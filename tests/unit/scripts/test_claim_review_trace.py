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
    _CODE_SURFACES,
    changed_code_surfaces,
    commit_messages,
    find_seal_claims,
    main,
    missing_trace_fields,
)

# 🔴 패치는 string-path (`.claude/rules/testing.md` §이중 import 회피 — 신규 코드 규칙).
_MOD = "scripts.check_claim_review_trace"

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


# ── 축 5: 마크다운 인지 스트리핑 + 면제 annotation 개행 중성화 (Grok claim-review
#          `019fbe32-772f-7251-a232-384a556441d8` 재현 적발 F1·F2·F3) ─────────────────
# 🔴 TDD 선행 — 현행 `_strip_html_comments` 는 마크다운 비인지 정규식이고, 면제 `::notice`
#    사유는 `\n` 만 치환한다. 아래 비-대조군(F1·F2·F3)은 마크다운 인지 상태기계 +
#    개행류 전체 중성화 구현 전 RED 가 정상이다.
# 🔴 TDD-first: the current stripper is a markdown-unaware regex and the exemption reason only
#    replaces `\n` — non-control tests (F1/F2/F3) are expected RED until the markdown-aware
#    state machine and full newline-class neutralization land.


def test_seal_after_fenced_comment_marker_is_still_detected(monkeypatch):
    """🔴 F1 (fail-open) — 코드펜스 안의 미종결 `<!--` 는 이후 본문을 숨기지 못한다.

    GitHub 는 펜스 안 `<!--` 를 주석으로 렌더하지 않는다 — 펜스 내용은 리터럴 텍스트로
    **가시**다. 그런데 현행 `_UNTERMINATED_COMMENT` 정규식은 마크다운 비인지라 그 지점부터
    끝까지 지워, 펜스 **뒤**의 가시 seal 주장이 탐지를 벗어나 exit 0 이 된다(재현 적발 F1).
    "가드가 보는 텍스트 = 리뷰어가 보는 텍스트" 계약이 펜스 한 줄로 무너지는 방향 —
    가시 seal 주장을 숨기는 쪽이라 fail-open 이다.
    구현 계약: 펜스 라인(```/~~~, 선행 공백 0~3)은 in_comment 아닐 때 fence 를 토글하고,
    펜스 내부의 `<!--` 는 주석 시작으로 인정하지 않는다.
    GitHub renders `<!--` inside a code fence as visible literal text, so a visible seal
    claim after the fence must still be detected (today the regex strips it — fail-open).
    """
    body = "서문\n```html\n<!-- note\n```\n" + _REAL_SEAL_CLAIMS[1] + "\n\n흔적 없음"
    assert _run(monkeypatch, body=body) == 1


def test_trace_after_fenced_comment_marker_still_counts(monkeypatch):
    """🔴 F2 (false red) — 펜스 안 `<!--` 이후의 **가시** claim-review 흔적은 유효해야 한다.

    F1 과 같은 뿌리다: 펜스 안 `<!--` 는 GitHub 에서 가시 리터럴인데 현행 정규식이 그
    이후 전부를 지워, 정직하게 남긴 흔적이 사라지고 exit 1 이 된다(재현 적발 F2).
    false red 는 저자가 가드를 끄거나 면제로 도피하게 만든다(정책 17 — 오탐이 잦으면
    가드를 끄게 된다). 코드 예시가 흔한 PR 본문 표면에서 특히 치명적이다.
    Same root as F1 but the false-red direction: a visible trace after a fenced `<!--`
    is stripped today, failing an honest PR and pushing authors toward exemption abuse.
    """
    body = _REAL_SEAL_CLAIMS[1] + "\n```\n<!--\n```\n\n" + _GOOD_TRACE
    assert _run(monkeypatch, body=body) == 0


def test_inline_code_comment_marker_does_not_hide_the_rest(monkeypatch):
    """🔴 인라인 코드 스팬(`` `<!--` ``) 안의 마커는 주석 시작이 아니다 — 이후 본문은 가시다.

    마커 **설명** 문장은 백틱 코드 표기로 쓰는 것이 자연스럽다(이 가드 자신의 안내문이
    그렇다). 현행 정규식은 스팬을 몰라 그 지점부터 끝까지 지운다 — 서두 한 줄로 seal 도
    흔적도 함께 사라져, 본 케이스는 우연히 0 / 대조 케이스는 0(기대 1)이 된다.
    구현 계약: 단일 라인 백틱 스팬 안의 `<!--` 는 주석 시작 불인정(스팬 텍스트는 보존).
    대조 단언이 함께 있어야 "서두 이후가 통째로 지워져 얻은 우연한 0" 과
    "가시 텍스트가 실제로 판정된 0" 을 구별할 수 있다.
    A single-line backtick span must not start a comment: the seal AND the trace after the
    span stay visible. The contrast assertion distinguishes an accidental 0 (everything
    stripped) from a genuine 0 (visible text actually judged).
    """
    preamble = "본문에 `<!--` 마커 설명.\n"
    # 본 케이스 — 스팬 뒤의 가시 seal + 가시 흔적 = 정상 통과
    # Main case: visible seal + visible trace after the span must pass
    assert _run(monkeypatch, body=preamble + _REAL_SEAL_CLAIMS[1] + "\n\n" + _GOOD_TRACE) == 0
    # 대조 — 같은 서두에 seal 만 있고 흔적이 없으면 red 여야 한다 (현행은 서두 이후가
    # 지워져 seal 자체가 사라지고 0 — fail-open 방향의 RED 재현축)
    # Contrast: same preamble, seal only, no trace — must be red (today the stripper
    # erases the seal itself and returns 0, the fail-open direction)
    assert _run(monkeypatch, body=preamble + _REAL_SEAL_CLAIMS[1] + "\n\n흔적 없음") == 1


def test_fence_inside_real_comment_does_not_toggle(monkeypatch):
    """대조군 — 진짜 HTML 주석 **안**의 ``` 는 펜스가 아니다 (GitHub 동작 일치).

    HTML 주석 내부에서 GitHub 는 마크다운을 해석하지 않고 `-->` 만 찾는다. 상태기계가
    주석 내부에서 펜스를 토글하면 `-->` 를 놓쳐 주석이 닫히지 않은 것으로 오판하고,
    뒤따르는 **가시** seal+흔적 판정이 무너진다 — 이 테스트가 그 회귀를 잡는다.
    현 구현(종결 쌍 정규식)에서도 통과 — 상태기계 도입 후 회귀 방지축.
    Control: a ``` line inside a real HTML comment is not a fence. Inside a comment only
    `-->` matters (GitHub behavior); a state machine that toggles fences there mis-parses
    the close and breaks the visible seal+trace after it. Passes today — regression axis.
    """
    body = "<!--\n```\n-->\n" + _REAL_SEAL_CLAIMS[1] + "\n\n" + _GOOD_TRACE
    assert _run(monkeypatch, body=body) == 0


def test_exemption_notice_neutralizes_carriage_returns(monkeypatch, capsys):
    """🔴 F3 — 면제 `::notice` 사유의 `\\r` 로 워크플로 커맨드를 위조할 수 없어야 한다.

    현행은 사유에서 `\\n` 만 공백 치환한다. GitHub Actions 러너는 `\\r` 도 행 경계로
    처리하므로, 사유에 `\\r::error ...` 를 심으면 annotation 출력이 두 행으로 갈라져
    저자가 임의 워크플로 커맨드(`::error` 등)를 위조 주입할 수 있다(재현 적발 F3).
    구현 계약: 사유 출력 전 `\\r`·`\\n` 포함 **모든 개행류 제어문자**를 공백 치환 —
    면제 exit 0 과 `::notice` 가시화(R20-a)는 유지된다.
    Today only `\\n` is replaced: a `\\r` smuggled into the exemption reason splits the
    annotation line and forges arbitrary workflow commands. All newline-class control
    characters must be replaced with spaces before printing.
    """
    body = (
        "봉인했다.\n"
        "claim-review-not-required: 과거 회고 인용이라 검증 대상 아님\r::error title=forged::x"
    )
    # 면제 경로 자체는 유지 — exit 0 (advisory 계약 불변)
    # The exemption path itself stays exit 0 (advisory contract unchanged)
    assert _run(monkeypatch, body=body) == 0
    out = capsys.readouterr().out
    # splitlines() 는 \r 도 행 경계로 본다 — 러너가 행을 분해하는 방향과 같은 관측
    # splitlines() treats \r as a line boundary — same direction as the runner's splitting
    assert not any(line.startswith("::error") for line in out.splitlines()), (
        "면제 사유의 \\r 가 행을 갈라 ::error 워크플로 커맨드가 위조됐다"
    )
    # \n 기준으로만 갈라 보면 ::notice 행 내부의 잔존 \r 이 그대로 보인다
    # Splitting on \n only exposes any residual \r inside the ::notice line itself
    notice_lines = [line for line in out.split("\n") if line.startswith("::notice")]
    assert notice_lines, "면제 사용이 ::notice annotation 으로 가시화되지 않았다"
    assert all("\r" not in line for line in notice_lines), (
        "::notice 라인에 \\r 가 남아 있다 — 러너에서 행이 갈라져 커맨드 위조 표면이 된다"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 축 4 — 코드 표면 트리거 (backlog R57)
#
# 정책 19 는 *"실질 작업마다 CLAIM-REVIEW 기본 포함"* 인데 가드는 **seal 어휘가 있을 때만**
# 흔적을 요구했다. 그 간극을 `claim-review-not-required` 자기발급이 메웠다(최근 25 PR 중 6건).
# 이제 코드·가드 표면을 건드리면 어휘와 무관하게 흔적(또는 사유 있는 면제)을 요구한다.
#
# 실측 오탐(2026-08-06, 최근 30 머지 PR): 코드 표면 23 · 문서 전용 7 · 새로 red 3건(10%).
# ──────────────────────────────────────────────────────────────────────────────

_TRACE = (
    "## Grok claim-review\n"
    "- session: 019fd6e8-e995-7b82-9d28-1da13ae95ddd\n"
    "- claim: 이 변경이 기존 계약을 깨지 않는다는 주장을 검증했다\n"
    "- verdict: SURVIVES\n"
)
# 🔴 claim 은 16자 이상이어야 한다 — 초판 픽스처가 짧아 가드가 거부했고, 그것은
#    가드가 옳았던 것이다(한 줄짜리 형식적 claim 을 막는 것이 그 규칙의 목적).


def _run_with_surfaces(monkeypatch, surfaces, *, title="", body=""):
    """변경 표면을 주입해 main() 을 돌린다 (git 호출은 대체)."""
    monkeypatch.setenv("PR_TITLE", title)
    monkeypatch.setenv("PR_BODY", body)
    monkeypatch.setenv("PR_BASE_SHA", "aaaaaaa")
    monkeypatch.setenv("PR_HEAD_SHA", "bbbbbbb")
    monkeypatch.setattr(f"{_MOD}.changed_code_surfaces", lambda _b, _h: surfaces)
    monkeypatch.setattr(f"{_MOD}.commit_messages", lambda _b, _h: "")
    return main()


def test_code_surface_without_trace_is_blocked(monkeypatch):
    """🔴 이것이 R57 의 본체 — seal 어휘가 없어도 코드 변경이면 흔적을 요구한다.

    이전에는 어휘가 없으면 **아무것도 없이** exit 0 이었고, Claude 는 그 가드 트리거를
    정책 트리거로 오인해 면제를 자기발급했다.
    """
    rc = _run_with_surfaces(
        monkeypatch, ["src/services/foo.py"],
        title="fix(ui): 카드 정렬 수정", body="테스트 3건 추가.")
    assert rc == 1, "코드 표면을 바꾸는데 흔적 없이 통과했다"


def test_code_surface_with_trace_passes(monkeypatch):
    """대조군 — 흔적이 있으면 통과한다(가드가 무조건 red 면 곧 꺼진다)."""
    assert _run_with_surfaces(
        monkeypatch, ["src/services/foo.py"], body=_TRACE) == 0


def test_docs_only_change_is_not_triggered(monkeypatch):
    """🔴 문서 전용 PR 은 트리거하지 않는다 — 오탐이 진탐을 넘으면 가드 자살(정책 17).

    실측: 최근 30 PR 중 7건이 문서 전용이고, 그 전부가 이 축에서 자유롭다.
    """
    assert _run_with_surfaces(monkeypatch, [], body="수치 동기화만.") == 0


def test_no_pr_env_falls_back_to_seal_axis_only(monkeypatch):
    """🔴 PR env 가 없으면(로컬 `pre_push_gate`) 이 축은 쉰다.

    여기서 fail-closed 로 두면 **모든 로컬 push 가 영구 red** 가 된다 —
    `test_pre_push_gate.py` 가 CI 가드를 러너 목록에 강제 유입하기 때문이다.
    """
    for key in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PR_TITLE", "fix: 무언가")
    monkeypatch.setenv("PR_BODY", "본문")
    assert main() == 0


def test_exemption_still_works_but_is_recorded(monkeypatch, tmp_path):
    """면제는 계속 유효하되 **사람이 보는 자리**(job summary)에 누적된다.

    🔴 `::notice` 는 Actions 로그 안쪽이라 실질적으로 아무도 보지 않는다. 면제 남용은
    한 건씩 보면 정상이고 **추세로만** 드러난다.
    """
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    rc = _run_with_surfaces(
        monkeypatch, ["scripts/check_x.py"],
        body="claim-review-not-required: 순수 수치 동기화라 반증 대상 주장이 없습니다.")
    assert rc == 0
    text = summary.read_text(encoding="utf-8")
    assert "면제 사용" in text, f"면제가 job summary 에 기록되지 않았다: {text!r}"
    assert "반증 대상" in text, "사유가 기록되지 않으면 추세를 읽을 수 없다"


def test_summary_write_failure_never_changes_the_verdict(monkeypatch):
    """🔴 기록 실패가 판정을 바꾸면 안 된다 — 로깅이 게이트를 흔들면 그 자체가 결함이다."""
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent-dir/summary.md")
    assert _run_with_surfaces(
        monkeypatch, ["scripts/check_x.py"],
        body="claim-review-not-required: 사유가 충분히 긴 문장입니다.") == 0


# ── 표면 목록·경로 산출의 계약 ──────────────────────────────────────────


def test_surface_list_covers_the_machine_judgment_inputs():
    """🔴 기계 판정 입력이 '문서' 로 분류돼 무검증 통과하면 안 된다.

    `owed-verification.md` 는 R0-2 이후 판정 입력이고, `tests/unit/{scripts,hooks}` 는
    가드가 저술되는 표면이다. 리터럴로 못박는다 — 목록을 피검사 모듈에서 유도하면
    비우는 순간 초록이 된다.
    """
    for required in ("src/", "scripts/", ".github/workflows/", ".claude/hooks/",
                     "tests/unit/scripts/", "docs/runbooks/owed-verification.md"):
        assert required in _CODE_SURFACES, f"표면 목록에서 빠졌다: {required}"


def test_changed_surfaces_uses_three_dot_range(monkeypatch):
    """🔴 `base...head`(merge-base) 여야 한다 — two-dot 은 base 가 앞서간 만큼을 함께 세어
    **남의 변경을 이 PR 의 것으로** 오판한다."""
    seen = {}

    def fake_run(argv, **_kw):
        seen["argv"] = argv

        class R:
            returncode = 0
            stdout = "src/a.py\n"
        return R()

    monkeypatch.setattr(f"{_MOD}.subprocess.run", fake_run)
    changed_code_surfaces("aaa", "bbb")
    assert "aaa...bbb" in seen["argv"], f"three-dot 범위가 아니다: {seen['argv']}"


def test_changed_surfaces_returns_none_when_git_fails(monkeypatch):
    """🔴 판정 불가는 **빈 리스트와 구별**해야 한다 — 같게 두면 git 실패가 '변경 없음' 이 된다."""
    def fake_run(_argv, **_kw):
        class R:
            returncode = 128
            stdout = ""
        return R()

    monkeypatch.setattr(f"{_MOD}.subprocess.run", fake_run)
    assert changed_code_surfaces("aaa", "bbb") is None


def test_changed_surfaces_filters_out_unrelated_paths(monkeypatch):
    """대조군 — 표면 밖 경로는 걸러야 한다(전부 통과시키면 문서 PR 이 전부 red)."""
    def fake_run(_argv, **_kw):
        class R:
            returncode = 0
            stdout = "docs/STATE.md\nREADME.md\nsrc/main.py\n"
        return R()

    monkeypatch.setattr(f"{_MOD}.subprocess.run", fake_run)
    assert changed_code_surfaces("a", "b") == ["src/main.py"]


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 Grok claim-review `019fd786` (verdict: WEAKENED) 지적 이행
#
# 지적 요지: 위 축 4 테스트는 `changed_code_surfaces` 를 **통째로 대체**하므로
#   (a) CI 가 `PR_BASE_SHA`/`PR_HEAD_SHA` 를 실제로 넘기는지
#   (b) `main()` 이 그 env 를 (base, head) **순서대로** 넘기는지
# 를 하나도 검증하지 않는다. 둘 다 load-bearing 이고, 지우거나 뒤바꿔도 스위트는 초록이다.
# 즉 "보호를 삭제해도 참으로 보이는" 형태가 두 개 남아 있었다.
# ──────────────────────────────────────────────────────────────────────────────

_ENV_SURFACES = ("PR_BASE_SHA", "PR_HEAD_SHA")


@pytest.mark.parametrize("workflow", ["ci.yml", "claim-review-on-body-edit.yml"])
@pytest.mark.parametrize("var", _ENV_SURFACES)
def test_workflows_pass_the_sha_env_to_the_guard(workflow: str, var: str):
    """🔴 이 env 가 없으면 코드 표면 축이 **조용히 죽는다**.

    `main()` 은 base/head 가 둘 다 있을 때만 그 축을 켠다. 워크플로에서 두 줄을 지우면
    seal 어휘가 없는 모든 코드 PR 이 다시 무검증 통과하는데, 그 상태에서도 단위 테스트는
    전건 초록이다(Grok `019fd786` 1.1). 그래서 **배선을 따로 못박는다**.
    """
    text = (_REPO / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    assert var in text, (
        f"{workflow} 이 {var} 를 가드에 넘기지 않는다 — 코드 표면 축이 조용히 꺼진다"
    )


def test_main_passes_base_then_head_in_that_order(monkeypatch):
    """🔴 인자 순서가 뒤바뀌면 `head...base` 가 되어 **남의 변경**을 이 PR 것으로 본다.

    순수 함수 테스트는 three-dot 형태만 보고, 축 4 테스트는 함수를 대체하므로
    env→인자 사상은 어디서도 검증되지 않았다(Grok `019fd786` 1.2).
    """
    seen = {}

    def spy(base, head):
        seen["base"], seen["head"] = base, head
        return []

    monkeypatch.setenv("PR_TITLE", "")
    monkeypatch.setenv("PR_BODY", "")
    monkeypatch.setenv("PR_BASE_SHA", "BASE_SENTINEL")
    monkeypatch.setenv("PR_HEAD_SHA", "HEAD_SENTINEL")
    monkeypatch.setattr(f"{_MOD}.changed_code_surfaces", spy)
    monkeypatch.setattr(f"{_MOD}.commit_messages", lambda _b, _h: "")
    main()
    assert seen["base"] == "BASE_SENTINEL", f"base 자리에 {seen['base']!r} 가 왔다"
    assert seen["head"] == "HEAD_SENTINEL", f"head 자리에 {seen['head']!r} 가 왔다"


def test_undecidable_paths_do_not_claim_no_change(monkeypatch, capsys):
    """🔴 경로를 못 구했으면 '변경 없음' 이라고 **말하면 안 된다** — 모르는 것을 안다고 하는 것이다.

    `None`(판정 불가)과 `[]`(변경 없음)은 같은 분기로 오지만 같은 말을 하면 거짓 보고다
    (Grok `019fd786` 1.4).
    """
    monkeypatch.setenv("PR_TITLE", "")
    monkeypatch.setenv("PR_BODY", "")
    monkeypatch.setenv("PR_BASE_SHA", "aaa")
    monkeypatch.setenv("PR_HEAD_SHA", "bbb")
    monkeypatch.setattr(f"{_MOD}.changed_code_surfaces", lambda _b, _h: None)
    monkeypatch.setattr(f"{_MOD}.commit_messages", lambda _b, _h: "")
    assert main() == 0
    out = capsys.readouterr().out
    assert "판정 불가" in out, f"판정 불가를 알리지 않았다:\n{out}"
    assert "코드 표면 변경 없음" not in out, (
        f"모르는 상태에서 '변경 없음' 이라고 단언했다:\n{out}"
    )


def test_empty_surfaces_still_says_no_change(monkeypatch, capsys):
    """대조군 — 실제로 변경이 없으면 그렇게 말해야 한다(위 단언이 문구를 죽이지 않았는지)."""
    monkeypatch.setenv("PR_TITLE", "")
    monkeypatch.setenv("PR_BODY", "")
    monkeypatch.setenv("PR_BASE_SHA", "aaa")
    monkeypatch.setenv("PR_HEAD_SHA", "bbb")
    monkeypatch.setattr(f"{_MOD}.changed_code_surfaces", lambda _b, _h: [])
    monkeypatch.setattr(f"{_MOD}.commit_messages", lambda _b, _h: "")
    assert main() == 0
    assert "코드 표면 변경 없음" in capsys.readouterr().out


_LEGAL_VERDICTS = ("SURVIVES", "WEAKENED", "BROKEN", "CONFIRMED", "REFUTED", "HOLDS")


@pytest.mark.parametrize("verdict", _LEGAL_VERDICTS)
def test_every_legal_verdict_is_accepted(monkeypatch, verdict: str):
    """🔴 합법 판정 목록을 **리터럴로** 못박는다 — 모듈에서 유도하면 비워도 초록이다.

    `WEAKENED` 는 Grok 이 실제로 내는 판정인데 초판 목록에 없었다. `cycle-history.md:223`
    이 이미 그 판정을 서사로 기록하고 있는데 가드는 그것을 담은 본문을 **거부**했다 —
    '부분적으로 성립' 을 표현할 수단이 없으면 저자는 SURVIVES 로 반올림하게 되고,
    그러면 어휘 부족이 **판정을 낙관 쪽으로 왜곡**한다.
    """
    body = _GOOD_TRACE.replace(
        "- verdict: BROKEN — 설정 파싱이 손실 투영이라 우회 4종 통과",
        f"- verdict: {verdict} — 근거 요약",
    )
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=body) == 0


def test_unknown_verdict_is_rejected(monkeypatch):
    """대조군 — 아무 단어나 받으면 판정 어휘가 의미를 잃는다."""
    body = _GOOD_TRACE.replace(
        "- verdict: BROKEN — 설정 파싱이 손실 투영이라 우회 4종 통과",
        "- verdict: 아마도 괜찮음",
    )
    assert _run(monkeypatch, title=_REAL_SEAL_CLAIMS[0], body=body) == 1
