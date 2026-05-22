---
description: 배포 / 환경 설정 작업 시 적용되는 SCAManager 규칙 (path-scoped). 상세 절차는 docs/runbooks/railway.md
paths:
  - "railway.toml"
  - "nixpacks.toml"
  - "requirements.txt"
  - "requirements-dev.txt"
  - ".env.example"
  - "Procfile"
  - "alembic.ini"
---

# 배포 규칙

> 상세 절차 + Railway 대시보드 설정: [`docs/runbooks/railway.md`](../../docs/runbooks/railway.md)

## 핵심 주의사항

- **NIXPACKS npm run build 자동 추가**: npm이 환경에 존재하면 `nixpacks.toml [phases.build] cmds` 명시 여부와 무관하게 `npm run build`를 자동 추가. 억제 유일 수단: `railway.toml`의 `buildCommand` (최상위 오버라이드).
- **slither + solc 빌드타임 준비**: `slither-analyzer` (pip) 설치만으로는 부족 — solc 컴파일러 바이너리 필요. `railway.toml`의 `buildCommand`에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인 의무.
- **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml`에 `nixPkgs = ["nodejs"]` 등을 명시하면 Python provider의 nix 자동 설치(python3 + pip 포함)를 **완전히 교체**. Python+Node.js 공존 패턴: `nixPkgs` 사용 금지, `nixpacks.toml` `[phases.setup]` `cmds`에서 NodeSource 스크립트로 Node.js 설치 (예: `curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs`), pip install은 Python provider 자동 처리 (`[phases.install]` 직접 작성 시 exit 127 위험).
- **Tailwind v4 빌드**: `package.json`에 `npm run build` 스크립트가 `@tailwindcss/cli`로 `src/static/css/dist/tailwind.css`를 생성. `railway.toml` buildCommand 끝의 `npm ci && npm run build`가 이를 수행. 이 두 명령 제거 시 Tailwind CSS 누락으로 UI 깨짐 — buildCommand에서 제거 금지.
- **APP_BASE_URL**: Railway 리버스 프록시 환경 필수 설정. **OAuth redirect_uri**와 **GitHub Webhook 등록 URL** 양쪽에 HTTPS URL 강제 적용 — 미설정 시 `http://`로 등록.
- **Railway 빌드 검증 필수**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`, `nixpacks.toml`, `requirements.txt` 변경 후 Railway 대시보드 빌드 로그 직접 확인 후 완료 선언.
- **빌드 실패는 로그 우선, 추측 수정 금지**: Railway/CI 빌드 실패 보고를 받으면 즉각 수정 PR 을 작성하지 말 것. 전체 빌드 로그(실패 구간 위아래 30줄)를 먼저 받아 근본 원인을 특정한 뒤 수정. 상세: [회고](../../docs/reports/2026-04-23-railway-rubocop-prism-retrospective.md).
- **gem/npm transitive 의존성 핀**: Ruby gem 또는 npm 패키지의 **직접 의존성만 버전 고정해도 transitive 의존성은 시간에 따라 바뀐다**. rubocop 1.57.2 는 pure Ruby 지만 transitive `rubocop-ast` 가 2024년 이후 prism 네이티브 확장을 필수로 요구하게 변경됨 → Railway 빌드 실패. 해결책은 `gem install rubocop-ast -v 1.36.2` (prism-free 마지막 버전) 를 rubocop 설치 **이전에** 명시 핀.
- **requirements.txt 분리**: `requirements.txt`(프로덕션 — Railway 자동 감지)와 `requirements-dev.txt`(개발 — `-r requirements.txt` 포함 + pytest/playwright) 분리. `pytest`, `playwright`는 `requirements-dev.txt`에만 유지.
- **FastAPI 버전 핀**: `requirements.txt` — `fastapi>=0.136.1` (CVE-2024-47874 / CVE-2025-54121 패치 버전). 다운그레이드 금지.
- **SMTP_PORT 빈 문자열**: Railway 환경에서 `SMTP_PORT=""`로 설정해도 `config.py`의 `coerce_smtp_port` field_validator가 587로 자동 변환 (크래시 없음). 다만 Railway Variables에서 빈 값 대신 명시적 숫자 설정 권장.
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 `config.py`에서 `postgresql://`로 자동 변환.
