"""LocaleMiddleware — ASGI middleware for i18n locale detection (Phase 1 PR-1b).

Request 시작 시 locale 감지 후 scope["state"]["locale"] 주입.
LocaleMiddleware injects scope["state"]["locale"] from request signals.

감지 우선순위 (Detection priority):
1. Cookie `preferred_language` (사용자 명시 선택 / explicit user choice)
2. Accept-Language 헤더 (RFC 7231 q-weight 파싱 / RFC 7231 q-weight parsing)
3. settings.default_locale (Q1 default = "en")
4. settings.locale_fallback (모든 감지 실패 시 극한 fallback)

Note: Session 기반 감지는 본 미들웨어 시점에 미존재 (SessionMiddleware 가 outer 라
LocaleMiddleware 호출 시점에 scope["session"] 미설정). 사용자 로그인 후
preferred_language 갱신 시 = Cookie 동기화 의무 (Phase 2 PR-4 영역 — 헤더 dropdown).

Note: Session-based detection unavailable here (SessionMiddleware is outer in LIFO,
so scope["session"] not yet populated). User login → preferred_language sync via
Cookie (Phase 2 PR-4 — header dropdown).

🔴 ASGI middleware 패턴 의무 (BaseHTTPMiddleware 우회) — 메모리
RLSSessionMiddleware 패턴 차용 (근거 메모리는 소실 — 교훈은 본문에 보존).

ASGI middleware required (not BaseHTTPMiddleware) — pairs with memory
Pattern from RLSSessionMiddleware; the source memo is gone, the lesson stays here.

Kill-switch: `is_disabled("I18N")` 시 skip + scope["state"]["locale"] = "en"
강제 (운영 사고 시 응급 비활성 — 사이클 78 NEW-P0-2 패턴 페어).

Kill-switch: When `is_disabled("I18N")`, skip detection + force scope locale = "en"
(emergency disable — pairs with Cycle 78 NEW-P0-2 pattern).
"""
import logging
from src.config import settings
from src.shared.feature_kill_switch import is_disabled

logger = logging.getLogger(__name__)


class LocaleMiddleware:  # pylint: disable=too-few-public-methods
    """ASGI middleware — locale detection + scope.state.locale injection.

    ASGI 표준 = `__call__` 단일 method (pylint R0903 inline disable — 의도된 표준 패턴).
    ASGI standard = single `__call__` method (pylint R0903 inline disable — intended).
    """

    def __init__(self, app):
        self.app = app
        # 지원 locale 집합 (settings.supported_locales 정규화 후 캐싱)
        # Cached set of supported locales (normalized from settings.supported_locales)
        self._supported = frozenset(
            lang.strip() for lang in settings.supported_locales.split(",") if lang.strip()
        )

    async def __call__(self, scope, receive, send):
        # HTTP scope 만 처리 (websocket / lifespan 무관)
        # Only handle HTTP scope (websocket / lifespan unaffected)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Kill-switch: i18n 비활성 → 영문 강제
        # Kill-switch: i18n disabled → force English
        if is_disabled("I18N"):
            scope.setdefault("state", {})
            scope["state"]["locale"] = settings.locale_fallback
            await self.app(scope, receive, send)
            return

        locale = self._detect_locale(scope.get("headers") or [])
        scope.setdefault("state", {})
        scope["state"]["locale"] = locale

        await self.app(scope, receive, send)

    def _detect_locale(self, headers: list) -> str:
        """5단계 locale 감지 우선순위 적용.

        Apply 5-tier locale detection priority.
        """
        # 1. Cookie `preferred_language` (사용자 명시 선택)
        # 1. Cookie `preferred_language` (explicit user choice)
        cookie_locale = self._parse_cookie_locale(headers)
        if cookie_locale and cookie_locale in self._supported:
            return cookie_locale

        # 2. Accept-Language 헤더 (RFC 7231 q-weight 파싱)
        # 2. Accept-Language header (RFC 7231 q-weight parsing)
        accept_locale = self._parse_accept_language(headers)
        if accept_locale and accept_locale in self._supported:
            return accept_locale

        # 3. 기본값 (settings.default_locale)
        # 3. Default (settings.default_locale)
        if settings.default_locale in self._supported:
            return settings.default_locale

        # 4. 극한 fallback (settings.locale_fallback)
        # 4. Ultimate fallback (settings.locale_fallback)
        return settings.locale_fallback

    @staticmethod
    def _parse_cookie_locale(headers: list) -> str | None:
        """Cookie 헤더에서 `preferred_language` 추출.

        Extract `preferred_language` from Cookie header.
        """
        for name, value in headers:
            if name.lower() != b"cookie":
                continue
            try:
                cookie_str = value.decode("utf-8", errors="ignore")
            except (AttributeError, UnicodeDecodeError):
                continue
            for item in cookie_str.split(";"):
                if "=" not in item:
                    continue
                key, val = item.split("=", 1)
                if key.strip() == "preferred_language":
                    return val.strip()
        return None

    @staticmethod
    def _parse_q_weight(seg: str) -> float:
        """RFC 7231 q-weight 단일 segment 파싱 — 사이클 93 PR-B (S3776 분리).

        Parse a single RFC 7231 q-weight segment (Cycle 93 PR-B — S3776 split).
        """
        seg = seg.strip()
        if not seg.startswith("q="):
            return 1.0  # default per RFC 7231
        try:
            return float(seg[2:])
        except (ValueError, IndexError):
            return 0.0

    @classmethod
    def _parse_lang_items(cls, header_str: str) -> list[tuple[str, float]]:
        """Accept-Language 본문 → (base_lang, q_weight) tuple list.

        Decompose header into (base_lang, q_weight) tuples (Cycle 93 PR-B — S3776 split).
        """
        items: list[tuple[str, float]] = []
        for part in header_str.split(","):
            segments = part.split(";")
            lang = segments[0].strip().lower()
            if not lang:
                continue
            # 첫 segment 외에서 q= 찾기 (default 1.0)
            # Find q= in non-first segments (default 1.0)
            q_weight = 1.0
            for seg in segments[1:]:
                if seg.strip().startswith("q="):
                    q_weight = cls._parse_q_weight(seg)
                    break
            # 정규화: "ko-KR" → "ko" (base lang only)
            # Normalize: "ko-KR" → "ko" (base lang only)
            items.append((lang.split("-")[0], q_weight))
        return items

    @classmethod
    def _parse_accept_language(cls, headers: list) -> str | None:
        """Accept-Language 헤더 RFC 7231 q-weight 파싱 후 최우선 locale 반환.

        Parse Accept-Language header per RFC 7231 q-weights, return top locale.
        예 (Example): "ko-KR,ko;q=0.9,en;q=0.8" → "ko"
        사이클 93 PR-B: S3776 (24→<15) — _parse_q_weight + _parse_lang_items 분리.
        """
        for name, value in headers:
            if name.lower() != b"accept-language":
                continue
            try:
                header_str = value.decode("utf-8", errors="ignore")
            except (AttributeError, UnicodeDecodeError):
                continue
            items = cls._parse_lang_items(header_str)
            if not items:
                continue
            # q-weight 내림차순 안정 정렬 (동일 q-weight 시 입력 순서 보존)
            # Stable sort by q-weight descending (preserves input order on ties)
            items.sort(key=lambda x: x[1], reverse=True)
            return items[0][0]
        return None
