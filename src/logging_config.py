"""애플리케이션 로깅 설정 — INFO 로그가 실제로 출력되게 만드는 단일 지점.
Application logging configuration — the single place that makes INFO logs actually emit.

🔴 배경 (2026-07-19): 앱이 `logging.basicConfig`/`dictConfig` 를 **한 번도 호출하지 않아** 모든
`logging.getLogger(__name__).info(...)` 가 핸들러 없는 root 로 갔다. Python 은 핸들러가 없으면
`logging.lastResort`(레벨 WARNING) 로 처리하므로 **앱의 INFO 로그가 출시 이래 전부 소실**됐다.
Railway 로그에 uvicorn·alembic 만 보이던 이유 — 그 둘은 각자 핸들러를 설정한다.
Without any logging configuration, Python's last-resort handler emits WARNING+ only, so every
application INFO log was silently dropped.

실측 영향 / Measured impact:
- `retention sweep — purged expired_cache=N` 등 운영 관측 라인이 한 번도 보이지 않았다
- owed 원장의 검증 절차("Railway cron 로그에서 sweep 실행 확인")가 물리적으로 불가능했다
- 인앱 스케줄러(#1099)의 `scheduler started — 5 jobs` 도 보이지 않아 배포 검증이 막혔다

🔴 uvicorn 로거와 중복되지 않는다 — uvicorn 은 자체 로거에 핸들러를 붙이고 `propagate=False`
로 두므로 root 핸들러로 다시 올라오지 않는다.
No duplication with uvicorn: its loggers carry their own handlers and do not propagate.
"""
import logging
import re
import sys

# 운영 로그 포맷 — 시각·레벨·모듈명·메시지. Railway 로그 뷰에서 출처 추적이 가능해야 한다.
# Production log format; the module name must be visible to trace where a line came from.
_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# 이 핸들러가 우리가 붙인 것임을 표시 — 재호출 시 중복 부착 방지(idempotent).
# Marks our handler so repeat calls do not stack duplicates.
_MARKER = "_scamanager_configured"

# 🔴 시크릿을 URL **경로**에 넣는 외부 서비스 — 로그 유출 마스킹 패턴 (2026-07-19 P0).
# Telegram Bot API 는 `https://api.telegram.org/bot<TOKEN>/sendMessage` 처럼 토큰이 경로에 있어
# 요청 URL 을 로깅하는 라이브러리(httpx 등)가 그대로 토큰을 남긴다. 캡처 그룹 1(도메인+`/bot`)은
# 보존하고 토큰만 `***` 로 바꿔 **운영 판독성은 유지**한다.
# External services that put secrets in the URL *path*; keep the readable prefix, mask the token.
# 🔴 2026-07-19 2차 회고 P1 — 정책 16 진화(공유 로직 grep 전수) 미이행 시정.
# #1104 는 "오늘 로그에 보인" telegram 1건만 등록했으나, 구조가 동일한 채널이 4개 더 있고
# 그 URL 전문을 **우리 코드가** WARNING 으로 직접 로깅하고 있었다(notifier 5곳).
# Slack/Discord webhook 은 URL 자체가 credential 이다(경로의 토큰만 알면 누구나 발신 가능).
# Added after a retrospective found 4 more secret-in-URL channels our own code logged verbatim.
_SECRET_URL_PATTERNS = (
    re.compile(r"(api\.telegram\.org/bot)[^/\s]+"),
    re.compile(r"(hooks\.slack\.com/services/)\S+"),
    re.compile(r"(discord(?:app)?\.com/api/webhooks/)\S+"),
    # 🔴 인바운드 쿼리스트링 시크릿 (종합감사 P2) — uvicorn.access 는 경로+쿼리를 통째로 로깅한다.
    # `hook_token` 은 `?token=<secret>`(deprecated 하위호환)로도 전달돼 access 로그에 평문으로
    # 남았다. 파라미터명은 보존하고 값만 마스킹 — 위 필터가 uvicorn.access 핸들러에도 부착된다.
    # Inbound query-string secrets: uvicorn.access logs the full path+query, so a token/api_key
    # value would land verbatim. Preserve the param name, mask the value only.
    # `api[_-]?key` 는 apikey/api_key/api-key 를 모두 커버하므로 별도 apikey 대안 불필요(S5855).
    # api[_-]?key already matches apikey/api_key/api-key — no separate `apikey` alternative (S5855).
    re.compile(r"([?&](?:token|api[_-]?key|access[_-]?token|hook[_-]?token)=)[^&\s\"']+",
               re.IGNORECASE),
)

# 리댁션 대상이 예외 텍스트일 때 쓰는 기본 포맷터 — exc_info → 문자열 변환 전용.
# Default formatter used only to turn exc_info into text for redaction.
_EXC_FORMATTER = logging.Formatter()


def _redact(text):
    """등록된 시크릿 패턴을 `***` 로 치환 — 변경이 없으면 원본 그대로 반환.
    Mask registered secret patterns; returns the input unchanged when nothing matched."""
    out = text
    for pattern in _SECRET_URL_PATTERNS:
        out = pattern.sub(r"\1***", out)
    return out


class _RedactSecretsFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    # R0903: logging.Filter 규약이 `filter()` 단일 메서드다 — 메서드를 늘리는 것이 오히려 규약 위반.
    # R0903: the logging.Filter contract is a single filter() method; adding more would break it.
    """로그 레코드에서 시크릿을 마스킹하는 심층 방어 필터.
    Defense-in-depth filter that masks secrets in log records.

    🔴 배경 (2026-07-19): #1102 로 앱 로깅이 복구되자마자 Telegram 봇 토큰이 운영 로그에
    평문으로 남고 있음이 드러났다(실측 5건). 로그가 죽어 있던 동안 잠복해 있던 유출 경로다.
    계층 1(httpx 침묵)이 1차 차단이지만, **우리 코드가 실수로 토큰을 로깅하는 경우**나
    httpx 의 WARNING 경로(재시도·타임아웃)는 이 필터만이 막는다.
    Layer 1 silences httpx at INFO; this filter is the only guard for our own accidental logging
    and for httpx's WARNING-level paths (retries/timeouts).

    🔴 무해성 원칙 — 마스킹이 **발생한 경우에만** record 를 변형한다. 마스킹이 없으면
    `msg`/`args` 가 원본 그대로 남아 다운스트림 핸들러·포맷터가 평소대로 동작한다.

    🔴 **"lazy % 포맷이 보존된다" 는 표현은 부정확했다** — `_redact_message` 는 검사를 위해
    **모든 레코드에** `record.getMessage()` 를 호출하므로 포맷 비용은 이미 지불된다.
    보존되는 것은 *지연 실행* 이 아니라 **레코드 불변성**이다(변형 없음 → 재포맷 오류 0).
    Not lazy formatting — getMessage() runs for every record. What is preserved is record
    immutability when nothing matched, not deferred formatting.
    """

    def filter(self, record):
        self._redact_message(record)
        self._redact_traceback(record)
        if record.stack_info:
            record.stack_info = _redact(record.stack_info)
        return True

    @staticmethod
    def _redact_message(record):
        """msg 축 — 포맷된 메시지에 시크릿이 있으면 완성 문자열로 대체.
        Message axis; replace with the finished string when a secret was masked."""
        try:
            text = record.getMessage()
        except (TypeError, ValueError):
            # 포맷 인자 불일치 — 여기서 삼키지 않고 핸들러가 평소대로 처리하게 둔다.
            # Malformed format args; let the handler surface it as usual.
            return

        redacted = _redact(text)
        if redacted != text:
            # 완성된 문자열로 대체하므로 args 를 비워야 재포맷 시 오류가 없다.
            # Replace with the finished string; args must be cleared to avoid re-formatting.
            record.msg = redacted
            record.args = ()

    @staticmethod
    def _redact_traceback(record):
        """exc_info 축 — 🔴 이 축이 실제 운영 유출 경로였다 (2026-07-19 2차 회고 P0).

        Exception axis — the path that actually leaked in production.

        `#1104` 는 msg 축만 덮어 "2계층 봉인" 을 선언했으나, Telegram 알림 실패 시
        예외가 uvicorn 으로 전파되면 **트레이스백에 토큰이 박힌 URL 이 원문 그대로** 남았다
        (`RuntimeError: Client error '401 ...' for url 'https://api.telegram.org/bot<TOKEN>/...'`).
        재현으로 확인된 결함이다.

        🔴 `exc_text` 를 채워두면 `Formatter.format()` 이 **그 값을 재사용**하므로,
        uvicorn 의 자체 Formatter(ColourizedFormatter)를 교체하지 않고도 마스킹이 적용된다.
        Populating exc_text makes Formatter.format() reuse it, so uvicorn's own formatter is
        covered without replacing it.

        🔴 이미 캐시된 `exc_text` 가 있으면 **그것을 리댁션**한다 — 앞선 핸들러가 포맷하며
        캐시를 채웠을 수 있고, 그 경우 새로 계산하면 캐시된 원문이 그대로 출력된다.
        If exc_text is already cached (an earlier handler formatted it), redact that value.
        """
        if not record.exc_info:
            return
        current = record.exc_text or _EXC_FORMATTER.formatException(record.exc_info)
        redacted = _redact(current)
        if redacted != record.exc_text:
            record.exc_text = redacted


def is_configured():
    """이 모듈이 root 로거를 이미 설정했는지 여부.
    Whether this module has already configured the root logger.

    🔴 용도 (2026-07-19 P0): `alembic/env.py` 가 이 함수로 **인프로세스 마이그레이션**을 식별한다.
    앱 lifespan 이 `configure_logging()` 후 마이그레이션을 돌리는데, alembic 의
    `fileConfig(alembic.ini)` 는 root 를 WARN + stderr 로 되돌리고
    `disable_existing_loggers=True` 로 `uvicorn.access`·`src.*` 로거를 전부 비활성화한다.
    → 앱이 이미 설정했으면 alembic 은 로깅에 손대지 않는다 (CLI 단독 실행은 기존대로).
    Used by alembic/env.py to detect in-process migrations: when the app has already configured
    logging, alembic must not re-apply alembic.ini (which would reset root to WARN/stderr and
    disable every existing logger). Standalone alembic CLI runs are unaffected.
    """
    return any(getattr(h, _MARKER, False) for h in logging.getLogger().handlers)


def configure_logging(level=logging.INFO):
    """root 로거에 stdout 핸들러를 부착하고 레벨을 설정한다 (idempotent).
    Attach a stdout handler to the root logger and set the level (idempotent).

    🔴 stdout 사용 — Railway 는 stdout/stderr 를 모두 수집하나, 애플리케이션 정보 로그를
    stderr 로 보내면 오류 로그와 뒤섞여 운영 판독이 어려워진다.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # 🔴 계층 1 — httpx 침묵 (2026-07-19 P0 시크릿 유출 차단).
    # httpx 는 INFO 에서 **요청 URL 전문**을 로깅한다. Telegram 처럼 토큰이 경로에 있는 API 는
    # 그 한 줄로 credential 이 통째로 로그에 남는다. 앱 자체 관측은 `src.shared.stage_metrics`·
    # `merge_metrics` 가 담당한다.
    #
    # 🔴 **손실이 0 은 아니다** — 강등으로 사라지는 것은 httpx 의 **INFO 요청 라인**
    # (`HTTP Request: POST https://... "200 OK"`)이고, 이는 개별 외부 호출의 URL·상태를
    # 한 줄로 보던 디버깅 수단이다. 대체 관측(`stage_metrics`·`merge_metrics`)은
    # **stage·merge 범위**라 그 축을 1:1 로 대신하지 못한다. 시크릿 유출 차단과 맞바꾼
    # 의도적 손실로 읽을 것 — 필요 시 `logging.getLogger("httpx").setLevel(INFO)` 로
    # 일시 복원하되 **토큰이 경로에 있는 API 호출이 없을 때만** 하라.
    # The demotion does cost the per-request INFO line; the cited replacements are
    # stage/merge-scoped and do not cover that axis 1:1.
    # 멱등성 early-return **앞**에 둔다 — 재호출로도 복구되도록(비대칭 방지).
    # Layer 1: httpx logs full request URLs at INFO; for token-in-path APIs that leaks the
    # credential. Placed before the idempotency return so a repeat call restores it.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # 🔴 계층 2b — uvicorn 계열 핸들러에 직접 부착 (2026-07-19 2차 회고 P0).
    # uvicorn 로거는 `propagate=False` + 자체 핸들러라 **root 핸들러의 필터가 구조적으로
    # 도달하지 못한다**. 백그라운드 태스크 예외를 uvicorn 이 `exc_info` 로 남기는 경로가
    # 실제 유출 지점이었으므로, root 부착만으로는 봉인되지 않는다.
    # uvicorn's loggers carry their own handlers with propagate=False, so a filter on the root
    # handler can never see them — the actual leak path had to be covered directly.
    # 멱등성 early-return **앞**에 둔다 — uvicorn 은 우리보다 늦게 설정될 수 있다.
    _attach_redaction_to_uvicorn()

    if any(getattr(h, _MARKER, False) for h in root.handlers):
        return  # 이미 설정됨 — 중복 부착 시 로그가 배로 출력된다 / already configured

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    # 🔴 계층 2 — 리댁션 필터를 **핸들러**에 부착 (로거가 아니라).
    # 로거에 붙이면 자식 로거에서 전파된 레코드를 놓친다 — 핸들러는 전파 경로의 종점이라
    # **root 로 전파되는** 레코드는 전부 통과한다.
    #
    # 🔴 **"어떤 로거에서 온 레코드든 통과한다" 가 아니다** — `propagate=False` 인 로거
    # (uvicorn 계열)는 애초에 root 까지 오지 않으므로 이 핸들러가 **구조적으로 볼 수 없다**.
    # 그래서 계층 2b(위)가 그 로거들에 필터를 직접 부착한다. 두 계층은 **다른 집합**을 덮는다.
    # `#1104` 가 "2계층 봉인" 을 선언하고도 실제로 유출한 이유가 정확히 이 착각이었다 —
    # 이 주석의 이전 판이 그 착각을 그대로 가르치고 있었다(2026-07-19 2차 회고 P0).
    # NOT "every record from any logger": propagate=False loggers never reach root, which is
    # why layer 2b attaches directly. The two layers cover disjoint sets — conflating them is
    # exactly the mistake that made #1104's "sealed" claim false.
    handler.addFilter(_RedactSecretsFilter())
    setattr(handler, _MARKER, True)
    root.addHandler(handler)


def _attach_redaction_to_uvicorn():
    """uvicorn 계열 로거의 각 핸들러에 리댁션 필터를 1개씩만 부착 (idempotent).
    Attach the redaction filter to each uvicorn handler exactly once."""
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            # 🔴 중복 부착 금지 — 재호출 시 필터가 쌓이면 매 레코드마다 정규식이 n배 돈다.
            # Never stack duplicates; repeat calls would run the regexes n times per record.
            if not any(isinstance(f, _RedactSecretsFilter) for f in handler.filters):
                handler.addFilter(_RedactSecretsFilter())
