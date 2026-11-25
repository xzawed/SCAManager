# Railway 배포·운영

## 빌드·배포
- push 성공 ≠ 빌드 성공 — `Dockerfile`·`requirements*` 변경은 빌드 로그 실측(`Using detected Dockerfile`).
- 빌드 정본 = 루트 `Dockerfile`. 설치 실패를 삼키지 않는다(삼킨 실패는 레이어에 캐시된다). gem transitive 도 핀(`rubocop-ast`).
- 배포 설정 정본 = 대시보드 — 값·함정은 [deploy.md](../workflow/deploy.md). Start Command 는 비워 둔다(이미지 `CMD`).
- `GET /health`=`{"status":"ok"}`, 내부 상태 미노출(`tests/unit/test_main.py`).

## DB
- 호스트 = pooler(`*.pooler.supabase.com` — `aws-N` 접두는 프로젝트마다 다르다 · 정본은 Supabase 대시보드 Connect, 사용자 확인) — egress IPv4-only, direct `db.<ref>`(IPv6-only) 불가.
- `getaddrinfo`→호스트 / `Tenant or user not found`→user 접미사 `postgres.<ref>` / `password authentication failed`→credential / `Network unreachable`→IPv6.
- 연결 확인은 사용자가 `!` 로 돌린다 — 에이전트는 {host}×{user}×{port} 전수 probe(`connect_timeout=8` · 출력은 위 오류 분류만 · 비밀번호와 접속 주소는 찍지 않는다)를 만들어 건네고 결과를 받는다. 에이전트 몫은 관측 역할 읽기(`scripts/observe_db.py`)와 배포 · 로그 · 상태 읽기다. `select 1` 전 확정 보고 금지.
- `DB_FORCE_IPV4=true`(`src/database.py::_ipv4_connect_args(url:`)는 dual-stack 선호만 교정, IPv6-only 엔 no-op. 최후엔 유료 IPv4 add-on.

## cron·스케일·변수
주기 작업 = `src/scheduler.py`(운영만) · replica 1 — [deploy.md](../workflow/deploy.md). `APP_BASE_URL` 없으면 OAuth redirect_uri·Webhook 이 `http://`. `postgres://`→`src/config.py` 변환. [`env-vars.md`](../reference/env-vars.md).
