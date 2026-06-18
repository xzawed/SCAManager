"""Phase 4 PR-T1 — ai_review.py 에러 경로 + cache_control 동작 단위 테스트.

기존 test_ai_review.py 는 happy path 위주 — 에러 경로를 별도 파일로 분리해
가독성 + 14-에이전트 감사 R1-B 의 "AI review 에러 케이스 부족" 갭 해소.

검증 대상:
  - anthropic API 예외 (timeout / rate-limit / auth / connection) → graceful
  - log_claude_api_call 호출 검증 (status="error" + error_type)
  - prompt cache 토큰 추출 (Phase 1 PR-B caching 후속)
  - response 파싱 fallback (preamble + JSON, malformed)
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# pylint: disable=wrong-import-position
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.analyzer.io.ai_review import (
    _coerce_score,
    _default_result,
    _extract_json_payload,
    _parse_response,
    review_code,
)


# ──────────────────────────────────────────────────────────────────────────
# 점수 키 누락 → parse_error (C2 — hook keys_present 와 parity, 인플레 fail-open 봉인)
# ──────────────────────────────────────────────────────────────────────────


def test_parse_response_missing_commit_score_key_is_parse_error():
    """🔴 commit_message_score 키 누락 → parse_error (인플레 default 17 로 success 위장 차단).

    data.get(key, DEFAULT) 가 키 부재 시 17(인플레)을 ok=True 로 반환 → 이전엔 success →
    #804 ai_review_failed 게이트 미작동(auto-merge/approve fail-open). 키 누락은 채점 안 된
    응답이므로 parse_error 로 표시해 NULL-persist + 게이트 차단을 유지한다.
    """
    result = _parse_response('{"direction_score": 18, "test_score": 9, "summary": "ok"}')
    assert result.status == "parse_error"


def test_parse_response_missing_direction_score_key_is_parse_error():
    """direction_score 키 누락 → parse_error (commit 과 동일 인플레 봉인)."""
    result = _parse_response('{"commit_message_score": 15, "test_score": 9, "summary": "ok"}')
    assert result.status == "parse_error"


def test_parse_response_all_score_keys_present_is_success():
    """commit/direction/test 키 모두 존재 + 숫자 → success 보존 (회귀 가드)."""
    result = _parse_response(
        '{"commit_message_score": 15, "direction_score": 18, "test_score": 9, "summary": "ok"}'
    )
    assert result.status == "success"


def test_parse_response_missing_test_score_key_stays_success():
    """test_score 키 부재 → has_tests 폴백(부재=0, 인플레 X)이라 success 보존 (정당 처리).

    test_score 는 commit/direction 과 달리 _coerce_test_score 의 has_tests 레거시 폴백으로
    부재 시 0(보수적, 인플레 아님)을 정당하게 처리하므로 keys_present 검사에서 제외한다.
    """
    result = _parse_response(
        '{"commit_message_score": 15, "direction_score": 18, "summary": "ok"}'
    )
    assert result.status == "success"


# ──────────────────────────────────────────────────────────────────────────
# anthropic API 예외 경로 — 모든 케이스 graceful "api_error" fallback
# ──────────────────────────────────────────────────────────────────────────


async def test_review_code_handles_httpx_connect_error():
    """httpx.ConnectError 발생 시 _default_result("api_error") 반환."""
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.ConnectError("DNS lookup failed"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"
    assert result.commit_score == 17
    assert result.ai_score == 17
    assert result.test_score == 7


async def test_review_code_handles_httpx_timeout_error():
    """httpx.TimeoutException → api_error fallback."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.TimeoutException("read timeout"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"


async def test_review_code_handles_runtime_error():
    """RuntimeError (예: anthropic 내부 정책 거부) → api_error fallback.

    실제 anthropic 예외 클래스(APIError 등)는 SDK 의존성 — 광역 Exception catch
    가 의도적이므로 RuntimeError 로 동작 검증.
    """
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=RuntimeError("policy denied"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"


async def test_review_code_logs_claude_api_call_with_error_status():
    """예외 발생 시 log_claude_api_call(status='error', error_type=...) 호출 검증."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=httpx.ConnectError("net"))
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["status"] == "error"
    assert kwargs["error_type"] == "ConnectError"
    assert kwargs["input_tokens"] == 0
    assert kwargs["output_tokens"] == 0


async def test_review_code_logs_claude_api_call_with_success_status():
    """정상 응답 시 log_claude_api_call(status='success' + cache token) 호출 검증."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=json.dumps({
        "commit_message_score": 18, "direction_score": 17, "test_score": 8,
        "summary": "ok", "suggestions": [],
        "commit_message_feedback": "", "code_quality_feedback": "",
        "security_feedback": "", "direction_feedback": "", "test_feedback": "",
        "file_feedbacks": [],
    }))]
    response_obj.usage = MagicMock(
        input_tokens=120, output_tokens=300,
        cache_read_input_tokens=80, cache_creation_input_tokens=0,
    )
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        result = await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    assert result.status == "success"
    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 300
    # Phase 1 PR-B caching 후속 — cache 토큰 전달 검증
    assert kwargs["cache_read_tokens"] == 80
    assert kwargs["cache_creation_tokens"] == 0


async def test_review_code_uses_cache_control_in_system_prompt():
    """Phase 1 PR-B: messages.create 호출에 system=[{cache_control: ephemeral}] 포함 검증."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert "system" in call_kwargs
    system_blocks = call_kwargs["system"]
    assert isinstance(system_blocks, list)
    assert system_blocks[0]["type"] == "text"
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert system_blocks[0]["text"]  # 비어있지 않음


async def test_review_code_propagates_detected_languages():
    """build_review_prompt 가 detected_languages 반환 → result.detected_languages 전달."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch(
             "src.analyzer.io.ai_review.build_review_prompt",
             return_value=("user prompt", ["python", "go"]),
         ):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.detected_languages == ["python", "go"]


async def test_review_code_returns_empty_diff_status_for_empty_patches():
    """patches list 가 비어있을 때 status=empty_diff (build_review_prompt → empty)."""
    result = await review_code("sk-test", "feat: x", [])
    assert result.status == "empty_diff"


async def test_review_code_returns_no_api_key_for_missing_key():
    """api_key 가 빈 문자열일 때 status=no_api_key (empty_diff 보다 우선)."""
    result = await review_code("", "feat: x", [("a.py", "+ x = 1")])
    assert result.status == "no_api_key"


# ──────────────────────────────────────────────────────────────────────────
# _extract_json_payload 응답 파싱 fallback
# ──────────────────────────────────────────────────────────────────────────


def test_extract_json_payload_codeblock_lowercase():
    """```json {...} ``` → JSON 본문만 추출."""
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_codeblock_uppercase():
    """대문자 ```JSON 도 case-insensitive 매칭."""
    text = '```JSON\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_codeblock_no_lang_tag():
    """언어 태그 없는 ``` ``` → 동일 매칭."""
    text = '```\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_with_preamble_and_trailing_text():
    """JSON 앞뒤 설명 텍스트 → 첫 { ~ 마지막 } 구간 추출."""
    text = (
        "Here is the analysis:\n"
        '{"commit_message_score": 18, "summary": "ok"}\n'
        "End of response."
    )
    extracted = _extract_json_payload(text)
    assert extracted.startswith("{")
    assert extracted.endswith("}")
    assert "commit_message_score" in extracted


def test_extract_json_payload_returns_cleaned_when_no_braces():
    """{ } 없으면 cleaned text 그대로 반환."""
    text = "no JSON here at all"
    assert _extract_json_payload(text) == "no JSON here at all"


# ──────────────────────────────────────────────────────────────────────────
# _parse_response — JSON decode/value/key 에러 모두 parse_error fallback
# ──────────────────────────────────────────────────────────────────────────


def test_parse_response_value_error_returns_default():
    """int(non-numeric) ValueError → status=parse_error."""
    text = '{"commit_message_score": "not-a-number"}'
    result = _parse_response(text)
    assert result.status == "parse_error"
    assert result.commit_score == 17


def test_parse_response_invalid_json_returns_default():
    """완전 깨진 JSON → status=parse_error."""
    result = _parse_response("totally broken {][")
    assert result.status == "parse_error"


def test_parse_response_clamps_out_of_range_scores():
    """commit_message_score=99 → max(0, min(20, 99)) = 20."""
    text = json.dumps({
        "commit_message_score": 99, "direction_score": -5, "test_score": 50,
        "summary": "x",
    })
    result = _parse_response(text)
    assert result.commit_score == 20  # clamped to max
    assert result.ai_score == 0       # clamped to min
    assert result.test_score == 10    # clamped to test max


# ──────────────────────────────────────────────────────────────────────────
# #24 — 점수 필드 per-field 안전 변환 (단일 비숫자/Infinity 가 리뷰 전체를 붕괴시키지 않음)
# ──────────────────────────────────────────────────────────────────────────


def test_coerce_score_parity_with_hook_coerce_raw_score():
    """🔴 PARITY GUARD: ai_review._coerce_score 가 hook._coerce_raw_score 와 행동 동등 (#24/#784).

    의도적 중복(인라인, 정책16 사용처 2곳) 두 구현이 drift 하지 않도록 입력 배터리로 (int, ok)
    동등성을 봉인한다. 한쪽 변경 시 본 테스트가 fail → 양쪽 동시 수정 강제.
    """
    from src.api.hook import _coerce_raw_score  # pylint: disable=import-outside-toplevel
    battery = [
        ("88.0", 20, 17),        # float-string → ValueError → default
        (float("inf"), 20, 17),  # Infinity → OverflowError → default
        (float("nan"), 20, 17),  # NaN → ValueError → default
        ("abc", 20, 17),         # 비숫자 문자열 → ValueError → default
        (None, 20, 17),          # None → TypeError → default
        (18, 20, 17),            # 정상 → 18
        (99, 20, 17),            # 범위 초과 → clamp 20
        (-5, 20, 17),            # 음수 → clamp 0
        (3.9, 20, 17),           # float → int 절단 3
        (10, 10, 7),             # test 범위
    ]
    for raw, mx, default in battery:
        assert _coerce_score(raw, mx, default) == _coerce_raw_score(raw, mx, default), \
            f"parity drift for raw={raw!r}"


def test_coerce_score_truncates_valid_float_toward_zero():
    """유효한 float 은 int() 0방향 절삭(반올림 X) — docstring 정수 의미 가드 (사이클166 follow-up).

    문서화한 '정수 변환 의미'(8.9 → 8, 반올림이면 9)를 값으로 명시 봉인. int()→round() 같은
    무심코 변경 시 본 가드가 fail. PARITY 대상이라 양쪽 동일 단언.
    Valid floats are truncated toward zero (no rounding) — guards the documented int() semantics.
    """
    from src.api.hook import _coerce_raw_score  # pylint: disable=import-outside-toplevel
    # 8.9 → 8 (절삭; 반올림이면 9), 유효 숫자라 ok=True
    assert _coerce_score(8.9, 20, 17) == (8, True)
    assert _coerce_raw_score(8.9, 20, 17) == (8, True)
    # 음수 float 은 0 방향 절삭(-2.9 → -2) 후 [0,max] clamp → 0
    assert _coerce_score(-2.9, 20, 17) == (0, True)
    assert _coerce_raw_score(-2.9, 20, 17) == (0, True)


def test_parse_response_preserves_feedback_on_nonnumeric_score():
    """#24: 단일 점수 필드 float-string 이어도 리뷰 전체를 폐기하지 않고 feedback·정상 점수 보존.

    상태는 parse_error 로 표시(#804 게이트 fail-closed 유지)하되, 이전처럼 _default_result 로
    feedback 까지 폐기하지 않는다.
    """
    text = json.dumps({
        "commit_message_score": "88.0",  # float-string → ValueError → default + parse_error
        "direction_score": 18,
        "test_score": 9,
        "summary": "great review",
        "security_feedback": "no issues",
        "suggestions": ["add tests"],
    })
    result = _parse_response(text)
    assert result.status == "parse_error"          # 비숫자 필드 → 게이트 fail-closed 유지
    assert result.commit_score == 17               # 복구 불가 필드는 default
    assert result.ai_score == 18                   # 정상 필드 보존 (전량 폐기 아님)
    assert result.test_score == 9                  # 정상 필드 보존
    assert result.summary == "great review"        # 🔴 feedback 보존 (이전엔 _default_result 로 폐기)
    assert result.security_feedback == "no issues"
    assert "add tests" in result.suggestions


def test_parse_response_infinity_marked_parse_error_preserves():
    """#24: direction_score=Infinity(int(inf) OverflowError) → 전량 폐기/api_error 아닌 parse_error + 보존."""
    text = '{"commit_message_score": 18, "direction_score": Infinity, "test_score": 9, "summary": "ok"}'
    result = _parse_response(text)
    assert result.status == "parse_error"
    assert result.commit_score == 18    # 보존
    assert result.ai_score == 17        # Infinity → default
    assert result.test_score == 9       # 보존
    assert result.summary == "ok"       # feedback 보존


def test_parse_response_non_dict_payload_returns_parse_error():
    """#24: JSON 이 유효해도 비-dict(array/scalar) 페이로드는 parse_error (data.get AttributeError 방어)."""
    # _extract_json_payload 는 {} 구간을 찾지만, 중괄호 없는 순수 배열/스칼라는 그대로 통과 가능
    assert _parse_response("[1, 2, 3]").status == "parse_error"
    assert _parse_response("42").status == "parse_error"


# ──────────────────────────────────────────────────────────────────────────
# _default_result — status enum 정확성
# ──────────────────────────────────────────────────────────────────────────


def test_default_result_carries_status_field():
    """_default_result(reason) 의 status 필드가 reason 그대로."""
    assert _default_result("api_error").status == "api_error"
    assert _default_result("no_api_key").status == "no_api_key"
    assert _default_result("empty_diff").status == "empty_diff"
    assert _default_result("parse_error").status == "parse_error"


def test_default_result_default_reason_is_no_api_key():
    """기본값 호출 시 status='no_api_key'."""
    assert _default_result().status == "no_api_key"


def test_default_result_neutral_scores():
    """모든 default 결과가 동일한 중립 점수 (commit=17, ai=17, test=7)."""
    for reason in ("no_api_key", "empty_diff", "api_error", "parse_error"):
        result = _default_result(reason)
        assert result.commit_score == 17
        assert result.ai_score == 17
        assert result.test_score == 7
        # summary 는 빈 문자열 — 발신 시 status 기반 현지화 (사이클 155). status 가 사유 추적.
        # summary is empty; notifiers localize via status (Cycle 155). status carries the reason.
        assert result.summary == ""
        assert result.status == reason


# ──────────────────────────────────────────────────────────────────────────
# 회귀 방지 — Phase H PR-1A: anthropic.AsyncAnthropic timeout 명시 전달
# Regression guard — Phase H PR-1A: AsyncAnthropic timeout kwarg passed
# ──────────────────────────────────────────────────────────────────────────


async def test_review_code_passes_explicit_timeout_to_anthropic_client():
    """Anthropic SDK hang 방어 — AsyncAnthropic 인스턴스화 시 timeout 명시.

    SDK 기본 timeout=600초 — Claude API hang 시 BackgroundTask 슬롯 10분
    점유 → 다른 webhook 분석 큐잉 정체. 명시적 timeout 으로 차단.
    """
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)

    captured_kwargs = {}

    def _capture_init(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return fake_client

    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", side_effect=_capture_init):
        await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])

    assert "timeout" in captured_kwargs, "AsyncAnthropic 인스턴스화에 timeout 인자 필수"
    timeout_val = captured_kwargs["timeout"]
    assert isinstance(timeout_val, (int, float))
    assert 0 < timeout_val <= 120  # SDK 600초 default 보다 훨씬 짧아야 함


async def test_review_code_passes_explicit_max_retries_to_anthropic_client():
    """Anthropic SDK 5xx/timeout 재시도 정책 명시 — Phase H PR-1B-1 회귀 가드.

    SDK 기본 max_retries=2 (현재 동작 중이지만 명시되지 않음). SDK 업그레이드
    시 default 변경되면 운영 영향 — 명시적 인자로 면역 + 미래 검증 가능.
    """
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)

    captured_kwargs = {}

    def _capture_init(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return fake_client

    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", side_effect=_capture_init):
        await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])

    assert "max_retries" in captured_kwargs, "AsyncAnthropic 인스턴스화에 max_retries 명시 필수"
    retries = captured_kwargs["max_retries"]
    assert isinstance(retries, int)
    assert 1 <= retries <= 5  # 합리적 범위 (무한 재시도 차단)


# ── Phase 2 a-B (사이클 74) — Multi-block 인프라 회귀 가드 ──
def test_build_review_blocks_returns_three_tuple():
    """신규 helper = (lang_guides_block, user_prompt, languages) 3-튜플 반환."""
    from src.analyzer.pure.review_prompt import build_review_blocks
    result = build_review_blocks(
        "fix bug", [("src/foo.py", "+def f():\n+    pass")],
    )
    assert len(result) == 3
    lang_block, user_prompt, langs = result
    assert isinstance(lang_block, str)
    assert isinstance(user_prompt, str)
    assert "python" in langs


def test_build_review_blocks_separates_lang_guides_from_user():
    """lang_guides 가 system block 으로 분리 — user_prompt 안 inline X.

    Phase 4 PR-12 (사이클 84) — lang_guides header 영문 통일 ("## Per-language review criteria").
    Phase 4 PR-12 (Cycle 84) — lang_guides header unified to English.
    """
    from src.analyzer.pure.review_prompt import build_review_blocks
    lang_block, user_prompt, _ = build_review_blocks(
        "fix bug", [("src/foo.py", "+def f():\n+    pass")],
    )
    if lang_block:  # 언어 감지 시
        assert "## Per-language review criteria" in lang_block
        assert "## Per-language review criteria" not in user_prompt


def test_build_review_prompt_backwards_compat_unchanged():
    """기존 build_review_prompt 시그니처 + 반환 형식 100% 보존 (호출자 영향 0).

    Phase 4 PR-12 (사이클 84) — lang_guides header 영문 통일.
    """
    from src.analyzer.pure.review_prompt import build_review_prompt
    user_prompt, langs = build_review_prompt(
        "fix bug", [("src/foo.py", "+def f():\n+    pass")],
    )
    assert isinstance(user_prompt, str)
    assert isinstance(langs, list)
    # lang_guides 가 user_prompt 안 inline 보존 (multi-block 미적용)
    if "python" in langs:
        # 단일 언어 시 ## Per-language review criteria inline
        assert "## Per-language review criteria" in user_prompt or "(none)" not in user_prompt


async def test_review_code_closes_anthropic_client():
    """review_code 가 호출 후 AsyncAnthropic httpx 풀을 닫는지 검증 — FD 누수 차단 회귀 가드 (WBS P1).

    finally 가 성공/에러 양 경로에서 aclose_anthropic_client 호출 → 풀 해제. 에러 경로로 검증.
    """
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=httpx.ConnectError("boom"))
    fake_client.aclose = AsyncMock()
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        await review_code("sk-test", "feat: x", [("app.py", "+ x = 1")])
    fake_client.aclose.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────
# 🔴 출력 토큰 절단 봉인 — max_tokens 상향 + stop_reason="max_tokens" 감지
# 🔴 Output-token truncation seal — raise max_tokens + detect stop_reason="max_tokens"
#
# 근본 사고: max_tokens=1500 이 한국어 리뷰 JSON(점수 + 5 feedback + file_feedbacks,
# 실측 ~2660 토큰)을 잘라 stop_reason=max_tokens → 불완전 JSON → parse_error 로 출시
# 이래 ~80% AI 리뷰 실패. 운영 DB + 실제 API 재현으로 확정 (2026-06-18).
# Root incident: max_tokens=1500 truncated Korean review JSON (~2660 tokens measured),
# yielding stop_reason=max_tokens → broken JSON → parse_error ~80% since launch.
# ──────────────────────────────────────────────────────────────────────────

_FULL_REVIEW_JSON = json.dumps({
    "commit_message_score": 15, "direction_score": 18, "test_score": 9,
    "summary": "ok", "suggestions": [],
    "commit_message_feedback": "", "code_quality_feedback": "",
    "security_feedback": "", "direction_feedback": "", "test_feedback": "",
    "file_feedbacks": [],
})


async def test_review_code_passes_sufficient_max_tokens_to_create():
    """🔴 회귀 가드 — messages.create 의 max_tokens 가 충분히 커야 함 (1500 절단 사고 재발 방지).

    max_tokens=1500 은 한국어 리뷰 JSON(~2660 토큰)을 잘라 stop_reason=max_tokens →
    불완전 JSON → parse_error 로 출시 이래 ~80% 실패. 작은 값으로 복귀하면 본 테스트 fail.
    Regression guard: max_tokens must stay large enough to avoid the 1500-token truncation.
    """
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=_FULL_REVIEW_JSON)]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    response_obj.stop_reason = "end_turn"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])
    create_kwargs = fake_client.messages.create.call_args.kwargs
    assert "max_tokens" in create_kwargs
    assert create_kwargs["max_tokens"] >= 4096, (
        "max_tokens 가 작으면 리뷰 응답 절단 → parse_error 재발 (실측 필요량 ~2660)"
    )


async def test_review_code_marks_truncated_on_max_tokens_stop_reason():
    """🔴 stop_reason='max_tokens'(출력 절단) → result.truncated=True (부분 응답 점수 신뢰 불가).

    출력이 잘리면 대부분 parse_error 지만, 운좋게 유효 JSON(success)이어도 부분 응답이라
    점수 인플레 위험 → truncated 마커로 auto-merge/approve 차단(C22 입력 절단과 대칭).
    Output truncation: even a parsable partial response is unreliable → mark truncated.
    """
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=_FULL_REVIEW_JSON)]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    response_obj.stop_reason = "max_tokens"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])
    assert result.status == "success"
    assert result.truncated is True


async def test_review_code_no_truncation_marker_on_normal_stop():
    """stop_reason='end_turn' + 작은 diff → result.truncated=False (정상 회귀 가드).

    정상 완료 응답에 truncated 마커가 잘못 붙으면 모든 리뷰가 auto-merge 차단됨 → 보존 가드.
    """
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=_FULL_REVIEW_JSON)]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    response_obj.stop_reason = "end_turn"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])
    assert result.status == "success"
    assert result.truncated is False
