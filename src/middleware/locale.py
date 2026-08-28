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
import re
from src.config import settings
from src.shared.feature_kill_switch import is_disabled

# RFC 7231 §5.3.1 의 qvalue 문법 그대로:
#     qvalue = ( "0" [ "." 0*3DIGIT ] ) / ( "1" [ "." 0*3DIGIT ] )
# 🔴 「어떤 형식이 잘못됐나」를 열거하면 열거 밖은 전부 통과한다. 문법에 맞는지를
# 묻는다 — 지수 표기·부호·선행 0·유니코드 숫자·범위 초과가 한 조건에 다 걸린다.
# Match the grammar instead of enumerating malformed shapes.
_QVALUE = re.compile(r"0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?")

logger = logging.getLogger(__name__)


# `*` 는 태그가 아니라 **언어 범위**다 (RFC 7231 §5.3.5).
# The wildcard is a language *range*, never a literal tag.
_WILDCARD = "*"

# 「범위가 비어 다음 항목을 보라」— `None`(기본값을 써라)과 구별해야 한다.
# Sentinel: empty range. Must not collide with None, which means "use the default".
_NO_RANGE = object()


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
        accept_locale = self._parse_accept_language(
            headers, self._supported, settings.default_locale)
        if accept_locale:
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
    def _parse_q_weight(seg: str) -> float | None:
        """RFC 7231 q-weight 단일 segment 파싱. **None = 파싱 실패**(거부가 아니다).

        🔴 예전 판은 파싱 실패에도 `0.0` 을 돌려줬다. 그런데 q=0 은 RFC 7231 §5.3.1
        에서 「수용 불가(not acceptable)」라는 **뜻이 있는 값**이다. 두 뜻이 같은 값에
        겹치면, 「거부된 언어를 뺀다」는 규칙이 **깨진 q 를 보낸 클라이언트의 언어까지**
        뺀다 — `"ko;q=abc"` 가 `ko` 대신 기본 로케일이 된다.

        🔴 무엇이 「진짜 0」인지는 **문법**이 정한다. `float()` 이 0.0 을 주는 것과
        클라이언트가 0 을 쓴 것은 다르다 — `q=+0` · `q=00` · `q=.0` · `q=0e0` ·
        `q=1e-400` · `q=\u0660`(아랍-인도 숫자) 는 전부 `float()` 에서 0.0 이지만
        qvalue 가 아니다. 이것들을 거부로 읽으면 클라이언트가 거부한 적 없는 언어가
        사라진다. 범위 밖(`q=1.5` · `q=inf`)과 NaN 도 같은 문법 하나에 걸린다.

        Return None when the segment is unparseable — that is not a rejection.
        """
        seg = seg.strip().lower()  # 파라미터명은 대소문자 무시 / case-insensitive per RFC
        if not seg.startswith("q="):
            return 1.0  # default per RFC 7231
        if not _QVALUE.fullmatch(seg[2:]):
            return None
        return float(seg[2:])

    @classmethod
    def _parse_lang_items(
        cls, header_str: str
    ) -> tuple[list[tuple[str, float]], set[str]]:
        """Accept-Language 본문 → (후보 목록, **명시된 태그 집합**).

        🔴 명시 집합에는 `q=0` 으로 거부된 태그도 들어간다. 후보 목록에서는
        빠지지만 「사용자가 이 언어를 언급했다」는 사실은 남아야 한다 — `*` 의
        범위를 후보 목록에서 뽑으면 거부된 언어가 `*` 를 타고 되살아난다.

        Returns candidates plus every explicitly mentioned tag (q=0 included):
        the wildcard range must not re-admit a language the client rejected.
        """
        items: list[tuple[str, float]] = []
        mentioned: set[str] = set()
        for part in header_str.split(","):
            segments = part.split(";")
            lang = segments[0].strip().lower()
            if not lang:
                continue
            # 첫 segment 외에서 q= 찾기 (default 1.0)
            # Find q= in non-first segments (default 1.0)
            q_weight = 1.0
            rejected = False
            for seg in segments[1:]:
                if not seg.strip().lower().startswith("q="):
                    continue
                parsed = cls._parse_q_weight(seg)
                if parsed is None:
                    # 파싱 실패 — 최하위 우선순위로 두되 **후보로는 남긴다**.
                    # Unparseable: rank last, but keep it as a candidate.
                    q_weight = 0.0
                elif parsed == 0:
                    # 🔴 q=0 은 「수용 불가」 (RFC 7231 §5.3.1) — 항목을 만들지 않는다.
                    # 선택 루프는 가중치를 다시 보지 않으므로, 여기서 빼지 않으면
                    # 클라이언트가 명시적으로 거부한 언어가 그대로 뽑힌다.
                    # A q of 0 means "not acceptable" — never emit it as a candidate.
                    rejected = True
                else:
                    q_weight = parsed
                break
            # 정규화: "ko-KR" → "ko" (base lang only)
            # Normalize: "ko-KR" → "ko" (base lang only)
            base = lang.split("-")[0]
            if base != _WILDCARD:
                mentioned.add(base)
            if rejected:
                continue
            items.append((base, q_weight))
        return items, mentioned

    @classmethod
    def _resolve_wildcard(
        cls, supported: frozenset, mentioned: set[str], default: str | None
    ) -> str | None | object:
        """`*` 의 범위를 풀어 고른다. 범위가 비면 `_NO_RANGE` (호출부가 다음 항목으로).

        RFC 7231 §5.3.5 에서 `*` 는 **헤더에 명시되지 않은 나머지 전부**를 가리킨다.
        그 안에서는 우열이 없으므로:

        - 기본값이 범위 안이면 `None` — 기본값이 이미 클라이언트를 만족시킨다.
        - 기본값이 범위 밖이면(거부됐거나 더 낮은 q 를 받았으면) 범위에서 고른다.
          🔴 `sorted()` 로 고른다 — `supported` 는 frozenset 이라 순회 순서가
          실행마다 다를 수 있고, `settings.supported_locales` 의 나열 순서에
          결합하면 설정을 재배열하는 것만으로 화면 언어가 바뀐다.

        Resolve the wildcard range; the default wins when it is inside the range.
        """
        candidates = supported - mentioned
        if not candidates:
            return _NO_RANGE
        if default in candidates:
            return None
        return sorted(candidates)[0]

    @classmethod
    def _parse_accept_language(cls, headers: list, supported: frozenset | None = None,
                               default: str | None = None) -> str | None:
        """Accept-Language 를 RFC 7231 q-weight 로 파싱해 **수용 가능한** 최우선 locale 반환.

        🔴 `supported` 를 받는 이유: 예전 판은 최고 q 하나만 돌려줬고, 그것이 지원 목록에
        없으면 호출부가 **그냥 버려** 기본 로케일로 갔다. 그래서 클라이언트가 지원 언어를
        명시적으로 요청했는데도 영어가 나갔다(감사 C1, #1519 실측):

            "zh-CN,ko;q=0.9"                   -> en   (ko 여야 한다)
            "fr-FR,fr;q=0.9,ja;q=0.8,en;q=0.7" -> en   (ja q=0.8 > en q=0.7)

        RFC 7231 §5.3.5 는 최고 q 의 **acceptable** 언어를 고르라고 한다 — 미지원 언어를
        건너뛰고 다음을 본다. `supported` 가 None 이면 옛 동작(최고 q 그대로)이다.

        Parse per RFC 7231 q-weights and return the top *acceptable* locale.
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
            items, mentioned = cls._parse_lang_items(header_str)
            if not items:
                continue
            # q-weight 내림차순 안정 정렬 (동일 q-weight 시 입력 순서 보존)
            # Stable sort by q-weight descending (preserves input order on ties)
            items.sort(key=lambda x: x[1], reverse=True)
            if supported is None:
                return items[0][0]
            # 🔴 미지원 언어는 **건너뛴다** — 버리지 않는다. 버리면 그 아래의 지원
            # 언어가 있어도 기본 로케일로 간다.
            # Skip unsupported languages instead of discarding the whole header.
            for lang, _weight in items:
                if lang == _WILDCARD:
                    picked = cls._resolve_wildcard(supported, mentioned, default)
                    if picked is _NO_RANGE:
                        continue
                    return picked
                if lang in supported:
                    return lang
            return None
        return None
