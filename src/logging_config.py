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
import sys

# 운영 로그 포맷 — 시각·레벨·모듈명·메시지. Railway 로그 뷰에서 출처 추적이 가능해야 한다.
# Production log format; the module name must be visible to trace where a line came from.
_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# 이 핸들러가 우리가 붙인 것임을 표시 — 재호출 시 중복 부착 방지(idempotent).
# Marks our handler so repeat calls do not stack duplicates.
_MARKER = "_scamanager_configured"


def configure_logging(level=logging.INFO):
    """root 로거에 stdout 핸들러를 부착하고 레벨을 설정한다 (idempotent).
    Attach a stdout handler to the root logger and set the level (idempotent).

    🔴 stdout 사용 — Railway 는 stdout/stderr 를 모두 수집하나, 애플리케이션 정보 로그를
    stderr 로 보내면 오류 로그와 뒤섞여 운영 판독이 어려워진다.
    """
    root = logging.getLogger()
    root.setLevel(level)

    if any(getattr(h, _MARKER, False) for h in root.handlers):
        return  # 이미 설정됨 — 중복 부착 시 로그가 배로 출력된다 / already configured

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    setattr(handler, _MARKER, True)
    root.addHandler(handler)
