"""Dockerfile review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Dockerfile review checklist
- **Base image**: No `latest` tag → pin versions (`python:3.12-slim`); use `slim` / `alpine` for size
- **Multi-stage**: Separate build deps from runtime; minimize final image size
- **Layer cache**: Order `COPY requirements.txt` → `RUN pip install` → `COPY . .` (cache efficient)
- **Security**: `USER` non-root; never hardcode secrets in `ENV` / `ARG` (use `--secret`)
- **Cleanup**: `RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` in one line
- **HEALTHCHECK**: Required for production containers; document `EXPOSE`
"""

COMPACT = "## Dockerfile: no latest, multi-stage, COPY cache order, USER non-root, no ENV secrets, HEALTHCHECK"

FULL_KO = """\
## Dockerfile 검토 기준
- **베이스 이미지**: `latest` 태그 금지 → 버전 명시(`python:3.12-slim`), `slim`/`alpine` 경량 이미지
- **멀티스테이지**: 빌드 의존성과 런타임 분리, 최종 이미지 크기 최소화
- **레이어 캐시**: `COPY requirements.txt` → `RUN pip install` → `COPY . .` 순서(캐시 효율)
- **보안**: `USER` 비-root 실행, 시크릿을 `ENV`/`ARG`에 하드코딩 금지(`--secret` 활용)
- **클린업**: `RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` 한 줄
- **HEALTHCHECK**: 프로덕션 컨테이너 헬스체크 필수, `EXPOSE` 문서화
"""

COMPACT_KO = "## Dockerfile: latest 금지, 멀티스테이지, COPY 캐시 순서, USER 비-root, 시크릿 ENV 금지, HEALTHCHECK"

FULL_JA = """\
## Dockerfile レビュー基準
- **ベースイメージ**: `latest` タグ禁止 → バージョン明示 (`python:3.12-slim`)、`slim` / `alpine` 軽量イメージ
- **マルチステージ**: ビルド依存とランタイムを分離、最終イメージサイズを最小化
- **レイヤーキャッシュ**: `COPY requirements.txt` → `RUN pip install` → `COPY . .` の順序 (キャッシュ効率)
- **セキュリティ**: `USER` 非 root 実行、シークレットを `ENV` / `ARG` にハードコード禁止 (`--secret` 活用)
- **クリーンアップ**: `RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` を 1 行に
- **HEALTHCHECK**: 本番コンテナに必須、`EXPOSE` を文書化
"""

COMPACT_JA = "## Dockerfile: latest 禁止、マルチステージ、COPY キャッシュ順、USER 非 root、ENV シークレット禁止、HEALTHCHECK"
