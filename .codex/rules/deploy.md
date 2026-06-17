---
description: 배포 / 환경 설정 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "railway.toml"
  - "nixpacks.toml"
  - "requirements.txt"
  - "requirements-dev.txt"
  - ".env.example"
  - ".python-version"
  - "alembic.ini"
  - "sonar-project.properties"
---

# 배포 규칙 (Codex)

> 상세 절차: [`docs/runbooks/railway.md`](../../docs/runbooks/railway.md)

- 🔴 **NIXPACKS npm run build 억제**: `railway.toml` 의 `buildCommand` 최상위 오버라이드만 억제 가능.
- 🔴 **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml` 에 `nixPkgs` 명시 시 Python provider nix 자동 설치 **완전 교체**. Python+Node.js 공존: `nixPkgs` 사용 금지, `[phases.setup]` `cmds`에서 NodeSource 스크립트 설치 (`curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs`). `[phases.install]` 직접 작성 금지 — pip 직접 호출 시 venv 미생성으로 "pip: command not found" (exit 127) 발생. `[phases.build]` 도 작성 금지 — `railway.toml` buildCommand 가 상위 오버라이드.
- **APP_BASE_URL**: Railway 필수 — OAuth redirect_uri + GitHub Webhook URL 양쪽 HTTPS 강제.
- **Railway 빌드 검증**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`/`nixpacks.toml`/`requirements.txt` 변경 후 대시보드 빌드 로그 직접 확인.
- **빌드 실패 시 로그 우선**: 즉각 수정 PR 금지 — 전체 빌드 로그(실패 구간 위아래 30줄) 먼저 확인.
- 🔴 **Railway pre-deploy = `alembic upgrade head`** (`railway.toml [deploy] preDeployCommand`, 2026-06-15): 트래픽 전 DB 마이그레이션 loud-fail(실패 시 배포 중단). lifespan 도 동일 실행하나 silent-fail 이라 pre-deploy 가 schema drift 가시화. 🔴 **Railway 대시보드 Settings→Deploy→Pre-deploy Command = 빈 값 권장**(railway.toml 단일 출처 — stale 설정 혼동/drift 차단; 부득이 설정 시 `alembic upgrade head` 동일 값 유지). ⚠️ 양쪽 정의 시 우선순위 Railway 버전/필드별 혼동 가능(일반 config-as-code=코드 우선, 대시보드 command 필드 예외 보고 존재) — Deploy 로그 확인. 전례(2026-06-15): railway.toml preDeployCommand **미정의** 상태라 대시보드 stale `npm run migrate`(`package.json` 미존재 스크립트) 사용됨 → "Deploy › Pre-deploy command failed" → 배포 미완료·alembic 0038 고착. **build 성공해도 deploy 단계서 차단** — Deploy/Pre-deploy 로그까지 확인.
- **requirements.txt 분리**: 프로덕션 = `requirements.txt` / 개발 = `requirements-dev.txt`. `pytest`/`playwright` 는 dev only.
- **slither + solc**: `railway.toml` buildCommand 에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인.
- **postgres:// → postgresql://**: `config.py` 에서 자동 변환됨.
- 🔴 **Supabase 연결 장애 = host 재도출 + 로컬 secret-safe probe (2026-06-15 prod 다운)**: redeploy/사용자 outsource 로 검증 금지. canonical host 는 Supabase MCP `get_project`/Dashboard Connect 재도출(pooler `aws-N` prefix 가변 — 로그 복사값=가설, 2026-06-15 `aws-0`→정답 `aws-1`). gitignore 된 `.dbpw` + 1회성 psycopg2 probe 로 `{host}×{user}×{port}` 매트릭스 직접 실행 `select 1` 확인. secret-in-local-file probe = 검증 capability(블로커 아님). 상세: `docs/runbooks/railway.md` §연결 invariants.
- 🔴 **Tailwind v4 빌드**: `railway.toml` buildCommand 끝의 `npm ci && npm run build`가 `@tailwindcss/cli`로 `src/static/css/dist/tailwind.css`를 생성. 이 두 명령 제거 시 UI 깨짐 — buildCommand에서 제거 금지.
