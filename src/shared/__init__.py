"""공용 인프라 유틸리티.
Shared infrastructure utilities.

- `http_client`: FastAPI lifespan 관리 httpx.AsyncClient 싱글톤 (내부 신뢰 API 용)
- `log_safety`: 로그 인젝션 방지 sanitizer (CR/LF 제거 + 길이 제한)

도메인 로직이 아닌 모든 계층(`api/`, `ui/`, `worker/`, `notifier/` 등)에서
공유하는 기초 유틸. `src/constants.py`, `src/crypto.py`, `src/config.py` 와
동일한 "기초 유틸" 레이어지만, 본 디렉토리는 **복수 함수를 노출하는 모듈**
에 한정 (단일 상수 집합은 상위 src/ 루트 유지).
"""
