# Railway 배포 + 운영 DB 운영 가이드

> CLAUDE.md 분리본 (사이클 85 정리, 2026-05-06). Railway 배포 변경 / 운영 DB 작업 시 read 의무.

## 운영 DB 환경 (2026-05-02 기준)

Supabase PostgreSQL + 온프레미스 PostgreSQL 이중 setup. Railway PostgreSQL 도 호환 (legacy 또는 staging). 모든 환경에 동일 alembic 마이그레이션 적용 — schema 일관성 보장.

운영 SQL 검증 도구 `scripts/dev/verify_phase2_data.sql` + runbook [`docs/runbooks/phase2-data-readiness.md`](phase2-data-readiness.md) 가 4 환경 (Supabase Dashboard / Supabase MCP / 온프레미스 psql / Railway) 모두 호환 (`\echo` meta-command 미사용 + `section` 라벨 컬럼).

## 🔴 Railway ↔ Supabase 연결 invariants (2026-06-15 사고 학습)

> 2026-06-15 prod 수 시간 다운(pooler host `aws-0`→`aws-1` 한 줄)의 재발 방지. 연결/credential 장애 진단 시 이 박스를 먼저 읽는다. 핵심 메모리: `feedback-connectivity-probe-first`.

**① Railway egress = 기본 IPv4-only (Outbound IPv6 는 service별 opt-in·기본 비활성) → pooler(IPv4 도달 경로) 사용 의무.**
Railway 컨테이너는 **기본적으로** IPv6 아웃바운드를 사용하지 않는다(Railway Outbound IPv6 는 service별 opt-in — 미활성이 기본값, `src/database.py:23` 주석). 따라서 **Supabase pooler 엔드포인트(`*.pooler.supabase.com` — IPv4 도달 경로)** 를 사용한다. 🔴 direct 호스트(`db.<ref>.supabase.co`)는 2024년 이후 **IPv6-only**(IPv4 A 레코드 없음 — 유료 IPv4 add-on 별매)라 **Outbound IPv6 미활성 기본 Railway 에서 도달 불가** → pooler 사용(권장) 또는 Railway Outbound IPv6 opt-in 활성화 또는 유료 IPv4 add-on 필요. (Supabase IPv4 add-on 이 있으면 direct 도 IPv4 도달 가능.) `DB_FORCE_IPV4=true`(`src/config.py` `db_force_ipv4`, default `false` → `src/database.py::_ipv4_connect_args`)는 `socket.getaddrinfo(..., AF_INET)` 로 **A 레코드(IPv4)를 강제 선택**해 psycopg2 `hostaddr` 로 전달(SSL 은 hostname 으로 검증)하는 옵션이다 — **dual-stack 호스트에서 기본 해석이 라우팅 불가한 IPv6 을 고르는 것을 교정**하는 용도이며, A 레코드가 없는 IPv6-only 호스트에 IPv4 를 만들어내지는 못한다(해석 실패 시 `{}` 반환 = no-op → 원래 IPv6 해석으로 `Network unreachable`). 즉 *도달성*은 pooler(또는 유료 add-on)가 보장하고, `DB_FORCE_IPV4` 는 dual-stack 의 IPv6 선호를 교정하는 보조 수단이다. 🔴 **이 프로젝트 운영 기본값(Railway Outbound IPv6 미활성 + Supabase IPv4 add-on 미사용)에서는 direct `db.<ref>`(IPv6-only) 사용 금지 — pooler 사용** (Outbound IPv6 opt-in 또는 IPv4 add-on 시에만 direct 가능).

**② pooler `aws-N` 클러스터 prefix 는 project-specific·가변 — stale 로그 가정 금지.**
pooler 호스트의 `aws-0`/`aws-1`/`aws-2…` prefix 는 프로젝트가 올라간 Supavisor 클러스터에 따라 다르고 **이전될 수 있다**. canonical 호스트는 **Supabase Dashboard → Connect** 또는 **Supabase MCP `get_project`** 에서 매번 **재도출**한다. 🔴 첫 배포 로그·기존 `.env`·다른 문서에서 복사한 호스트 값은 *사실이 아니라 가설* 이다(2026-06-15 = `aws-0` 을 미검증 상속 → 수 시간 낭비. 정답 `aws-1` 은 repo `docs/guides/onpremise-migration-guide.md:339` 에 내내 존재 → `grep aws-1` 한 줄이면 발견). 호스트를 의심할 땐 `grep` 으로 repo 안 대안 호스트를 먼저 표면화한다.

**③ 유료 IPv4 add-on 은 최후 수단** — 무료 secret-safe probe 가 전 permutation(host·user·접미사·port·sslmode·IP-family)을 반증한 *후에만* 검토. 비용 결정 전에 "어떤 단일 변수가 틀렸는가"를 probe 로 먼저 좁힌다.

**④ 연결 장애 검증 프로토콜 (turn 1 부터 — prod 변경/사용자 outsource 가 아니라 *내가 통제하는* 검증면 우선):**
1. 모든 연결 파라미터를 가설로 열거 + 출처 태그. **로그 복사값 = 최우선 테스트 대상**(가설이지 사실 아님). `grep <값>` 으로 repo 대안 표면화.
2. canonical host = Dashboard Connect / MCP `get_project` 재도출 (stale 로그 금지).
3. **secret-safe probe = 정공법**: 사용자가 비번을 gitignore 된 로컬 파일(`.dbpw`)에 기록 → 내가 read 하는 1회성 probe(psycopg2 는 이미 의존성) 실행, 출력 `scrub()`(`<pw>` 치환), 실행 후 파일 삭제 + `.gitignore` 확인. "비번 echo 불가" 는 검증 *방법* 제약이지 *여부* 제약이 아니다.
4. **one-shot 매트릭스**: {host}×{user}×{port} 전 cross-product(틀렸다고 생각 안 한 고정 차원 포함), `connect_timeout=8`. redeploy 루프가 수 시간 덮는 공간을 1회로.
5. **에러 레이어 분류 (서로 다른 계층 — 혼동 금지)**: DNS `ENOTFOUND`/`getaddrinfo` 실패(호스트 자체가 미해석) = 잘못된 host·클러스터 prefix → ②번 host 재도출 / Supavisor `Tenant or user not found`(pooler 에 **도달했으나** tenant/user 거부) = 잘못된 user 접미사(`postgres.<ref>`)·tenant 라우팅 / `password authentication failed`·SCRAM = PG 까지 도달·credential 문제 / `Network unreachable` = transport(기본 IPv4 egress[Railway Outbound IPv6 미활성]에서 IPv6 direct 사용 — ①번).
6. 동일 입력이 시간차로 다른 레이어 실패 → "내 변경 탓"이 아니라 "환경이 움직였다" 1순위 가설 + ground truth 재fetch.
7. **확신은 내가 실행한 통과 검증(probe `select 1` OK) 후에만** — 그 전엔 `[가설 확신도 X%; 반증 테스트=…; 실행 중]`. "100%"·"마지막"은 검증 완료 후에만.
8. probe 산출물(`.dbpw`·`db_probe.py`)은 작업 종료 시 삭제 + `.gitignore` 가드 확인(이미 등재).

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

현재: `railway.toml`에 `buildCommand` = eslint/solc-select/rubocop/golangci-lint 전역 설치 + `npm ci && npm run build` (Tailwind v4 CSS 빌드 포함) 체인 설정됨. Node.js는 `nixpacks.toml` `[phases.setup]` NodeSource 스크립트(`deb.nodesource.com/setup_20.x`)로 설치. Python 의존성은 nixpacks Python provider 기본값(venv 자동 생성 + pip install)으로 처리 — `[phases.install]` 직접 작성 시 pip exit 127 위험 (2026-05-10 사고 사례: nixpacks.toml `[phases.install]` 명시 → Python venv provider 우선순위 충돌 → pip exit 127 → Railway 빌드 실패, #379 수정).

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
