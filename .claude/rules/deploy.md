---
description: 배포 / 환경 설정 작업 시 적용되는 SCAManager 규칙 (path-scoped). 상세 절차는 docs/runbooks/railway.md
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

# 배포 규칙

> 상세 절차 + Railway 대시보드 설정: [`docs/runbooks/railway.md`](../../docs/runbooks/railway.md)
> 여기 남은 것은 규칙 · 왜 한 줄 · 가드 파일명이다. 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.

## 조용히 무시되는 것들 — 이 영역 최다 재발 클래스

- 🔴 **`railway.toml` 신규 키는 공식 레퍼런스 대조 의무 — 무효 키는 에러 없이 무시된다.**
  *왜*: `[[deploy.cronJobs]]` 가 스키마에 없는 키라 **cron 5종이 출시 이래 한 번도 실행되지 않았다**.
  "설정했으니 동작할 것" 은 근거가 아니다 — 대시보드/API 로 **적용 여부를 확인**할 것.
  키 형태 집행: `tests/unit/scripts/test_railway_cron_guard.py` · `tests/unit/scripts/test_railway_scaling_guard.py`.
- 🔴 **analyzer 조달은 두 축으로 강제한다 — 한 축이 다른 축을 대체할 수 없다.**
  - **축 A** `tests/unit/scripts/test_build_command_deps.py` — buildCommand 호출 명령 ⊆ 조달 출처
  - **축 B** `tests/unit/scripts/test_analyzer_provenance.py` — 등록 analyzer → 조달 모드 전단사
  축을 갈아끼우면 원래 결함(analyzer silent-disable)이 다시 열린다.
  모드는 **닫힌 집합**(`build_install`·`apt`·`pip`·`nixpacks_setup`·`optional_absent_ok`),
  신규 analyzer 는 `_PROVENANCE` 등재 의무(미등재 = CI FAIL).
  `optional_absent_ok` 도피처 차단 3종: 사유 문자열 의무 / 실제 조달되는 바이너리를 optional 표기 금지 / **전부 optional 금지**.
- **buildCommand 가 쓰는 명령은 조달 출처 등재 의무** — 설치 단계가 `|| echo` 로 삼켜지면
  바이너리 없이도 빌드가 초록이고 analyzer 만 조용히 죽는다.
- **NIXPACKS 는 npm 이 있으면 `npm run build` 를 자동 추가한다** — 명시 여부와 무관. 억제 수단은 제한적이므로
  `railway.toml buildCommand` 최상위 지정이 우선순위 정본.
- **`nixpacks.toml` 의 `nixPkgs` 는 오버라이드가 아니라 교체다** — 명시하면 Python provider 의
  python3+pip 자동 설치가 **완전히 사라진다**.

## 버전 핀

- **전 직접 의존성 `==` 정확 핀** + SCA 게이트(`pip-audit`). `>=` 금지.
  *왜*: transitive 는 시간에 따라 바뀌므로 직접 의존성만 고정해도 빌드가 갈린다.
- **`.python-version` 이 Railway nixpacks Python 빌드 버전의 SSOT**(현재 `3.12`).
- **FastAPI/starlette 핀은 dependabot 정기 bump 대상** — 현재 `fastapi==0.141.1` + `starlette==1.4.1`.
  🔴 **이 인용 리터럴은 장식이 아니라 검사 대상이다** — `check_dependency_pins` 가 `requirements.txt` 실핀과
  대조하는 ground-truth 축이라, 지우면 *"검사 범위 붕괴"* 로 red 다(2026-08-12 압축 중 실제 발생).
  핀 변경 시 이 인용 + README FastAPI 배지 동시 갱신(가드: `scripts/check_docs_sync.py`).
- **`requirements.txt`(프로덕션, Railway 자동 감지) ↔ `requirements-dev.txt`(`-r` 포함 + pytest/playwright) 분리.**
- **slither 는 `solc` 바이너리가 별도 필요** — pip 설치만으로 부족(`solc-select install/use` 를 buildCommand 에).
- **Tailwind v4** — `npm run build` 가 `src/static/css/dist/tailwind.css` 생성. buildCommand 끝의 `npm ci && npm run build` 유지.

## 배포 절차

- **`git push` 성공 ≠ Railway 빌드 성공** — `railway.toml`·`nixpacks.toml`·`requirements.txt` 변경 후
  **빌드 로그를 직접 확인**할 것.
- **빌드 실패는 로그 우선, 추측 수정 금지** — 실패 보고를 받고 즉시 수정 PR 을 만들지 말 것.
  전체 로그(실패 구간 위아래 포함)를 먼저 읽는다.
- **pre-deploy = `alembic upgrade head`**(`railway.toml [deploy] preDeployCommand`) — 새 컨테이너가
  트래픽을 받기 전 DB 마이그레이션 완료를 보장한다.
- **Supabase 연결 장애는 host 재도출 + 로컬 secret-safe probe 로 진단** — redeploy 루프나
  사용자 outsource 로 검증하지 말 것. canonical host 는 Supabase 대시보드가 정본이다.

## 환경변수

- **`APP_BASE_URL` 은 Railway 필수** — OAuth redirect_uri 와 Webhook 등록 URL 양쪽에 HTTPS 를 강제한다.
  미설정 시 `http://` 로 등록돼 전달이 실패한다. (SESSION_SECRET 과의 결합 = [`security.md`](security.md))
- **`SMTP_PORT=""` 는 `coerce_smtp_port` 가 587 로 변환**(크래시 없음) — 그래도 명시 숫자 권장.
- **`postgres://` URL 은 `postgresql://` 로 자동 변환**(`DATABASE_URL_FALLBACK`·`DATABASE_URL_WORKER` 동일).
- **`DATABASE_URL_WORKER`** 미설정 시 `DATABASE_URL` 재사용 — 설정 절차는
  [`docs/runbooks/rls-role-separation.md`](../../docs/runbooks/rls-role-separation.md)
- 전체 목록·제약은 [`docs/reference/env-vars.md`](../../docs/reference/env-vars.md) 가 정본이다.

## 정적 분석 설정

- **SonarCloud CPD 제외** = `sonar.cpd.exclusions=tests/**,src/templates/**`(테스트 반복 패치·Jinja2 구조 반복).
  신규 제외 추가 시 사유를 PR 본문에 명시.
