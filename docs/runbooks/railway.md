# Railway 배포·운영

## 빌드·배포
- push 성공 ≠ 빌드 성공 — `Dockerfile`·`requirements*` 변경은 빌드 로그 실측(`Using detected Dockerfile`).
- 빌드 정본 = 루트 `Dockerfile`. 설치 실패를 삼키지 않는다(삼킨 실패는 레이어에 캐시된다). gem transitive 도 핀(`rubocop-ast`).
- 배포 설정 정본 = 대시보드 — 값·함정은 [deploy.md](../workflow/deploy.md). Start Command 는 비우거나(이미지 `CMD`) `/bin/sh -c "exec …"` 로 감싼다.
- `GET /health`=`{"status":"ok"}`, 내부 상태 미노출(`tests/unit/test_main.py`).

## DB
- 호스트 = pooler(`*.pooler.supabase.com`, MCP `get_project` 재도출) — egress IPv4-only, direct `db.<ref>`(IPv6-only) 불가.
- `getaddrinfo`→호스트 / `Tenant or user not found`→user 접미사 `postgres.<ref>` / `password authentication failed`→credential / `Network unreachable`→IPv6.
- 비밀번호는 gitignore 된 로컬 파일, 1회성 psycopg2 probe 로 {host}×{user}×{port} 전수(`connect_timeout=8`·스크럽·삭제). `select 1` 전 확정 보고 금지.
- `DB_FORCE_IPV4=true`(`src/database.py::_ipv4_connect_args(url:`)는 dual-stack 선호만 교정, IPv6-only 엔 no-op. 최후엔 유료 IPv4 add-on.

## cron·스케일·변수
주기 작업 = `src/scheduler.py`(운영만) · replica 1 — [deploy.md](../workflow/deploy.md). `APP_BASE_URL` 없으면 OAuth redirect_uri·Webhook 이 `http://`. `postgres://`→`src/config.py` 변환. [`env-vars.md`](../reference/env-vars.md).
