# Railway 배포 + 운영 DB 운영 가이드

> CLAUDE.md 분리본 (사이클 85 정리, 2026-05-06). Railway 배포 변경 / 운영 DB 작업 시 read 의무.

## 운영 DB 환경 (2026-05-02 기준)

Supabase PostgreSQL + 온프레미스 PostgreSQL 이중 setup. Railway PostgreSQL 도 호환 (legacy 또는 staging). 모든 환경에 동일 alembic 마이그레이션 적용 — schema 일관성 보장.

운영 SQL 검증 도구 `scripts/dev/verify_phase2_data.sql` + runbook [`docs/runbooks/phase2-data-readiness.md`](phase2-data-readiness.md) 가 4 환경 (Supabase Dashboard / Supabase MCP / 온프레미스 psql / Railway) 모두 호환 (`\echo` meta-command 미사용 + `section` 라벨 컬럼).

## 시작 명령

```bash
# 시작 명령 (railway.toml에 설정됨 — --proxy-headers 포함)
uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers
# DB 마이그레이션은 앱 lifespan에서 자동 실행
```

## Railway 대시보드 설정

- **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
- **Variables** 탭에서 나머지 환경변수 설정 (`${{Postgres.DATABASE_URL}}`)
- `APP_BASE_URL` 반드시 설정 — OAuth redirect_uri HTTPS 보장

## 헬스체크

`GET /health` → `{"status":"ok"}` (timeout: 60초).

🔴 **`active_db` 등 내부 상태는 의도적으로 미노출** — 정보 노출 방지. `tests/unit/test_main.py::test_health_returns_status_ok` 가 회귀 보장. DB failover 모니터링이 필요하면 별도 인증 엔드포인트 (`INTERNAL_CRON_API_KEY` 또는 admin key 기반) 신설 권장.

## NIXPACKS 빌드 설정 우선순위

| 우선순위 | 설정 위치 | 적용 범위 |
|---------|----------|---------|
| 1 | `railway.toml`의 `buildCommand` | 빌드 명령 최상위 오버라이드 |
| 2 | `nixpacks.toml`의 `[phases.build]` | NIXPACKS 빌드 단계 설정 |
| 3 | `nixpacks.toml`의 `providers` | NIXPACKS 언어 감지 오버라이드 |
| 4 | NIXPACKS 자동 감지 | `requirements.txt`, `package.json` 등 파일 기반 |

현재: `railway.toml`에 `buildCommand = "npm install -g eslint@9 @typescript-eslint/parser @typescript-eslint/eslint-plugin"` 설정됨. Node.js는 `nixpacks.toml` aptPkgs로 설치, eslint 전역 설치는 buildCommand에서 수행.

## requirements.txt 분리

```
requirements.txt      ← Railway(프로덕션) 전용 — pytest/playwright 제외
requirements-dev.txt  ← 로컬 개발 환경 — pytest, playwright 포함 (-r requirements.txt 포함)
```

## 배포 주의사항

- **NIXPACKS npm run build 자동 추가**: npm이 환경에 존재하면 `nixpacks.toml [phases.build] cmds` 명시 여부와 무관하게 `npm run build`를 자동 추가. 억제 유일 수단: `railway.toml`의 `buildCommand` (최상위 오버라이드). eslint 등 npm 전역 설치가 필요하면 buildCommand에 직접 작성.
- **slither + solc 빌드타임 준비**: `slither-analyzer` (pip) 설치만으로는 부족 — solc 컴파일러 바이너리가 있어야 실제 `.sol` 분석 가능. `railway.toml`의 `buildCommand`에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인으로 빌드 이미지에 solc 0.8.20 사전 포함 → 런타임 첫 분석에서 `STATIC_ANALYSIS_TIMEOUT=30` 내 완료 보장. pragma 가 다른 버전이면 slither 가 자동 fallback 다운로드 시도(네트워크 있으면 성공, 없으면 `success=false` → `[]` graceful degradation). solc 버전 변경 필요 시 `railway.toml` buildCommand 의 두 번 solc 버전 문자열만 교체.
- **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml`에 `nixPkgs = ["nodejs"]` 등을 명시하면 Python provider의 nix 자동 설치(python3 + pip 포함)를 **완전히 교체**한다. Python+Node.js 공존 패턴: `nixPkgs` 사용 금지, `aptPkgs = ["nodejs", "npm"]`으로 Node.js 설치, pip install은 Python provider 자동 처리.
- **APP_BASE_URL**: Railway 리버스 프록시 환경 필수 설정. **OAuth redirect_uri**와 **GitHub Webhook 등록 URL** 양쪽에 HTTPS URL 강제 적용 — 미설정 시 `http://`로 등록.
- **Railway 빌드 검증 필수**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`, `nixpacks.toml`, `requirements.txt` 변경 후 Railway 대시보드 빌드 로그 직접 확인 후 완료 선언.
- **빌드 실패는 로그 우선, 추측 수정 금지**: Railway/CI 빌드 실패 보고를 받으면 즉각 수정 PR 을 작성하지 말 것. 전체 빌드 로그(실패 구간 위아래 30줄)를 먼저 받아 근본 원인을 특정한 뒤 수정. 2026-04-23 rubocop/prism 사건에서 "추측 기반 1차 수정 → 2차 재실패 → 로그 분석 후 3차 성공" 패턴으로 1시간 낭비 실적 있음. 상세: [회고](../reports/2026-04-23-railway-rubocop-prism-retrospective.md).
- **gem/npm transitive 의존성 핀**: Ruby gem 또는 npm 패키지의 **직접 의존성만 버전 고정해도 transitive 의존성은 시간에 따라 바뀐다**. rubocop 1.57.2 는 pure Ruby 지만 transitive `rubocop-ast` 가 2024년 이후 prism 네이티브 확장을 필수로 요구하게 변경됨 → Railway 빌드 실패. 해결책은 `gem install rubocop-ast -v 1.36.2` (prism-free 마지막 버전) 를 rubocop 설치 **이전에** 명시 핀. 새 Ruby 도구 추가 시 동일 패턴 주의.
- **SMTP_PORT 빈 문자열**: Railway 환경에서 `SMTP_PORT=""`로 설정 시 pydantic ValidationError 크래시. Railway Variables에서 SMTP_PORT 값을 삭제하거나 숫자로 설정.
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 `config.py`에서 `postgresql://`로 자동 변환.
