---
description: 배포 / 환경 설정 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "railway.toml"
  - "nixpacks.toml"
  - "requirements.txt"
  - "requirements-dev.txt"
  - ".env.example"
  - "Procfile"
  - "alembic.ini"
---

# 배포 규칙 (Codex)

> 상세 절차: [`docs/runbooks/railway.md`](../../docs/runbooks/railway.md)

- 🔴 **NIXPACKS npm run build 억제**: `railway.toml` 의 `buildCommand` 최상위 오버라이드만 억제 가능.
- 🔴 **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml` 에 `nixPkgs` 명시 시 Python provider nix 자동 설치 **완전 교체**. Python+Node.js 공존: `nixPkgs` 사용 금지, `[phases.setup]` `cmds`에서 NodeSource 스크립트 설치 (`curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs`). `[phases.install]` 직접 작성 금지 — pip 직접 호출 시 venv 미생성으로 "pip: command not found" (exit 127) 발생. `[phases.build]` 도 작성 금지 — `railway.toml` buildCommand 가 상위 오버라이드.
- **APP_BASE_URL**: Railway 필수 — OAuth redirect_uri + GitHub Webhook URL 양쪽 HTTPS 강제.
- **Railway 빌드 검증**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`/`nixpacks.toml`/`requirements.txt` 변경 후 대시보드 빌드 로그 직접 확인.
- **빌드 실패 시 로그 우선**: 즉각 수정 PR 금지 — 전체 빌드 로그(실패 구간 위아래 30줄) 먼저 확인.
- **requirements.txt 분리**: 프로덕션 = `requirements.txt` / 개발 = `requirements-dev.txt`. `pytest`/`playwright` 는 dev only.
- **slither + solc**: `railway.toml` buildCommand 에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인.
- **postgres:// → postgresql://**: `config.py` 에서 자동 변환됨.
- 🔴 **Tailwind v4 빌드**: `railway.toml` buildCommand 끝의 `npm ci && npm run build`가 `@tailwindcss/cli`로 `src/static/css/dist/tailwind.css`를 생성. 이 두 명령 제거 시 UI 깨짐 — buildCommand에서 제거 금지.
