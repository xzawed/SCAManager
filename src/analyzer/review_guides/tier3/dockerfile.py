"""Dockerfile review guide — Tier 3."""

FULL = """\
## Dockerfile 검토 기준
- **베이스 이미지**: `latest` 태그 금지 → 버전 명시(`python:3.12-slim`), `slim`/`alpine` 경량 이미지
- **멀티스테이지**: 빌드 의존성과 런타임 분리, 최종 이미지 크기 최소화
- **레이어 캐시**: `COPY requirements.txt` → `RUN pip install` → `COPY . .` 순서(캐시 효율)
- **보안**: `USER` 비-root 실행, 시크릿을 `ENV`/`ARG`에 하드코딩 금지(`--secret` 활용)
- **클린업**: `RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` 한 줄
- **HEALTHCHECK**: 프로덕션 컨테이너 헬스체크 필수, `EXPOSE` 문서화
"""

COMPACT = "## Dockerfile: latest 금지, 멀티스테이지, COPY 캐시 순서, USER 비-root, 시크릿 ENV 금지, HEALTHCHECK"
