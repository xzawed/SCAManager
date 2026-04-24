"""observability._before_send — PII/secret 스크러빙 단위 테스트.

Phase E.2a 의 Sentry before_send 훅은 순수 Python 함수 (sentry_sdk 의존 없음)
이므로 devcontainer DNS 제약 환경에서도 테스트 가능. test_observability.py 는
sentry_sdk 를 importorskip 하므로 이 파일을 별도로 분리.
"""
# pylint: disable=protected-access
from src.shared.observability import _before_send


class TestUrlScrubbing:
    """URL query string 제거 — ?token=xxx 등 누출 방어."""

    def test_strips_query_string(self):
        event = {"request": {"url": "https://example.com/api?token=secret123&foo=bar"}}
        result = _before_send(event, {})
        assert result["request"]["url"] == "https://example.com/api"

    def test_preserves_url_without_query(self):
        event = {"request": {"url": "https://example.com/api"}}
        result = _before_send(event, {})
        assert result["request"]["url"] == "https://example.com/api"

    def test_handles_missing_url(self):
        event = {"request": {}}
        result = _before_send(event, {})
        # request 자체는 유지되어야 함
        assert "request" in result

    def test_handles_missing_request(self):
        event = {}
        result = _before_send(event, {})
        # request 가 없으면 빈 dict 추가되고 에러 없이 반환
        assert isinstance(result, dict)


class TestCookieScrubbing:
    """Cookies 전체 제거 — 세션 쿠키 유출 방어."""

    def test_clears_cookies(self):
        event = {"request": {"cookies": {"session": "abc123", "csrf": "xyz"}}}
        result = _before_send(event, {})
        assert result["request"]["cookies"] == {}

    def test_no_cookies_field_preserved(self):
        event = {"request": {"url": "https://example.com"}}
        result = _before_send(event, {})
        assert "cookies" not in result["request"]  # 없으면 추가하지 않음


class TestHeaderScrubbing:
    """민감 헤더 값 [Filtered] 로 교체."""

    def test_filters_authorization_header(self):
        event = {"request": {"headers": {"Authorization": "Bearer sk-ant-xxxx"}}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["Authorization"] == "[Filtered]"

    def test_filters_x_api_key(self):
        event = {"request": {"headers": {"X-API-Key": "my-secret"}}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["X-API-Key"] == "[Filtered]"

    def test_filters_x_hub_signature_256(self):
        event = {"request": {"headers": {"X-Hub-Signature-256": "sha256=abc"}}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["X-Hub-Signature-256"] == "[Filtered]"

    def test_filters_cookie_header(self):
        event = {"request": {"headers": {"Cookie": "session=abc"}}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["Cookie"] == "[Filtered]"

    def test_case_insensitive_filtering(self):
        event = {"request": {"headers": {"authorization": "Bearer xxx"}}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["authorization"] == "[Filtered]"

    def test_preserves_safe_headers(self):
        event = {"request": {"headers": {
            "Content-Type": "application/json",
            "User-Agent": "test",
            "Authorization": "Bearer secret",
        }}}
        result = _before_send(event, {})
        assert result["request"]["headers"]["Content-Type"] == "application/json"
        assert result["request"]["headers"]["User-Agent"] == "test"
        assert result["request"]["headers"]["Authorization"] == "[Filtered]"

    def test_handles_non_dict_headers(self):
        # Sentry 는 가끔 list 형태로 headers 를 보낼 수 있음 — 에러 없이 반환
        event = {"request": {"headers": [("Authorization", "Bearer x")]}}
        result = _before_send(event, {})
        # list 형식은 필터링하지 않되 크래시하지 않음
        assert isinstance(result, dict)


class TestRequestBodyScrubbing:
    """request.data (body) 명시적 필터링."""

    def test_filters_request_data(self):
        event = {"request": {"data": {"password": "secret"}}}
        result = _before_send(event, {})
        assert result["request"]["data"] == "[Filtered]"

    def test_no_data_field_preserved(self):
        event = {"request": {"url": "https://example.com"}}
        result = _before_send(event, {})
        assert "data" not in result["request"]  # 없으면 추가하지 않음


class TestCompleteScrubbing:
    """복합 시나리오 — 실제 GitHub webhook 예외 이벤트 모사."""

    def test_full_github_webhook_event_scrubbed(self):
        event = {
            "request": {
                "url": "https://scamanager.app/webhooks/github?installation_id=12345",
                "method": "POST",
                "cookies": {"session": "user-session-cookie"},
                "headers": {
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=leaked-hmac",
                    "Authorization": "token ghp_leaked",
                    "User-Agent": "GitHub-Hookshot/abc",
                },
                "data": {"repository": {"full_name": "test/repo"}},
            },
            "exception": {"values": [{"type": "ValueError"}]},
        }
        result = _before_send(event, {})
        req = result["request"]
        # URL query 제거
        assert "?" not in req["url"]
        # Cookies 클리어
        assert req["cookies"] == {}
        # 민감 헤더 필터
        assert req["headers"]["X-Hub-Signature-256"] == "[Filtered]"
        assert req["headers"]["Authorization"] == "[Filtered]"
        # 안전 헤더 보존
        assert req["headers"]["Content-Type"] == "application/json"
        assert req["headers"]["User-Agent"] == "GitHub-Hookshot/abc"
        # body 필터
        assert req["data"] == "[Filtered]"
        # 예외 정보는 보존
        assert result["exception"]["values"][0]["type"] == "ValueError"

    def test_returns_same_event_object(self):
        # 성능: 새 dict 생성하지 않고 event 자체를 수정 후 반환
        event = {"request": {"url": "https://example.com"}}
        result = _before_send(event, {})
        assert result is event
