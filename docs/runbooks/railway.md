# Railway 배포·운영

## 빌드·배포
- push 성공 ≠ 빌드 성공 — `railway.toml`·`nixpacks.toml`·`requirements*` 변경은 빌드 로그 실측.
- 빌드 명령은 `railway.toml` `buildCommand` 에만 — npm 있으면 NIXPACKS 가 `npm run build` 추가, 억제 수단은 이것뿐.
- 시스템 패키지 = `nixpacks.toml` `aptPkgs`(`unzip` 없으면 tflint 실패). Python 은 기본 venv+pip — `[phases.install]`·`nixPkgs` = pip exit 127.
- 전역 설치는 `|| echo WARNING` 로 감싸고 gem/npm transitive 도 핀(`rubocop-ast`).
- 게이트 = `preDeployCommand = alembic upgrade head`, 대시보드 Pre-deploy 는 비운다.
- `GET /health`=`{"status":"ok"}`(timeout 60), 내부 상태 미노출(`tests/unit/test_main.py`).

## DB
- 호스트 = pooler(`*.pooler.supabase.com`, MCP `get_project` 재도출) — egress IPv4-only, direct `db.<ref>`(IPv6-only) 불가.
- `getaddrinfo`→호스트 / `Tenant or user not found`→user 접미사 `postgres.<ref>` / `password authentication failed`→credential / `Network unreachable`→IPv6.
- 비밀번호는 gitignore 된 로컬 파일, 1회성 psycopg2 probe 로 {host}×{user}×{port} 전수(`connect_timeout=8`·스크럽·삭제). `select 1` 전 확정 보고 금지.
- `DB_FORCE_IPV4=true`(`src/database.py::_ipv4_connect_args(url:`)는 dual-stack 선호만 교정, IPv6-only 엔 no-op. 최후엔 유료 IPv4 add-on.

## cron·스케일·변수
`[[deploy.cronJobs]]` = 스키마 밖(무시) — 주기 작업은 `src/scheduler.py`(운영만). replica = `[deploy.multiRegionConfig.<region>] numReplicas`=1. `APP_BASE_URL` 없으면 OAuth redirect_uri·Webhook 이 `http://`. `postgres://`→`src/config.py` 변환. 가드 `test_railway_*_guard.py` · [`env-vars.md`](../reference/env-vars.md).
