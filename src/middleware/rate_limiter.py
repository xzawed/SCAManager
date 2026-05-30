"""API Rate Limiting 미들웨어 설정.
API rate limiting middleware configuration using slowapi.
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# IP 기반 rate limit — 메모리 스토리지, .env 파일 읽기 비활성화 (Windows cp949 인코딩 충돌 방지)
# IP-based rate limit — in-memory storage, disable .env reading to avoid Windows cp949 encoding conflicts
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    config_filename="",  # .env 파일 자동 탐색 비활성화 / Disable automatic .env file lookup
)

# 엔드포인트 카테고리별 기본 제한 상수
# Default rate limit constants per endpoint category
RATE_LIMIT_API = "60/minute"    # 일반 API (repos 목록, stats 조회)
RATE_LIMIT_HEAVY = "10/minute"  # 무거운 API (분석 트리거, 대용량 연산)
