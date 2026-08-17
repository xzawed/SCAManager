# Railway 배포·운영

## 배포
1. `railway.toml`·`nixpacks.toml`·`requirements*.txt` 변경은 push 후 Railway 빌드 로그를 직접 본다 — push 성공은 빌드 성공이 아니다.
2. 실패하면 실패 구간 앞뒤 30줄로 원인을 특정한 뒤 고친다 — 로그 없이 추측 수정 금지.
3. 마이그레이션 게이트 = `preDeployCommand = alembic upgrade head`(실패 시 배포 중단). 대시보드 Pre-deploy 는 비워 둔다(`railway.toml` 단일 출처).
4. `GET /health` = `{"status":"ok"}` 확인(timeout 60). 내부 상태 미노출이 계약 — `tests/unit/test_main.py`.

## 빌드
1. 빌드 명령은 `railway.toml` `buildCommand` 에만 쓴다 — npm 이 있으면 NIXPACKS 가 `npm run build` 를 자동 추가하며 억제 수단은 이것뿐이다.
2. 시스템 패키지는 `nixpacks.toml` `[phases.setup] aptPkgs`(`unzip` 없으면 tflint 설치가 조용히 죽는다). Python 은 `providers=["python"]` 기본 venv+pip 에 맡긴다 — `[phases.install]`·`nixPkgs` 는 pip exit 127.
3. 분석기 전역 설치는 `|| echo WARNING` 으로 감싼다 — 실패해도 그 분석기만 꺼진다. gem/npm 은 transitive 도 핀한다(rubocop 앞에 `rubocop-ast`).
4. 의존성: 운영 `requirements.txt` / 로컬 `requirements-dev.txt`.

## DB 연결 (Supabase·온프레미스, alembic 동일)
1. 호스트는 pooler(`*.pooler.supabase.com`)를 쓰고 Connect/MCP `get_project` 로 매번 재도출한다 — Railway egress 는 IPv4-only 기본이라 IPv6-only direct `db.<ref>` 는 도달 불가이고, 로그의 `aws-N` prefix 는 가설이다.
2. 에러 계층 분류: `getaddrinfo` 실패=호스트 / `Tenant or user not found`=user 접미사(`postgres.<ref>`) / `password authentication failed`=credential / `Network unreachable`=transport(IPv6).
3. 비밀번호는 gitignore 된 로컬 파일로 받아 1회성 psycopg2 probe 로 {host}×{user}×{port} 전 조합을 `connect_timeout=8` 로 한 번에 친다(출력 스크럽·산출물 삭제). redeploy 반복 금지.
4. `DB_FORCE_IPV4=true`(`src/database.py::_ipv4_connect_args`)는 dual-stack 의 IPv6 선호만 교정한다 — IPv6-only 호스트엔 no-op. 유료 IPv4 add-on 은 최후 수단.
5. probe `select 1` 통과 전에는 확정 보고 금지.

## 주기 작업·스케일
Railway cron 금지 — `[[deploy.cronJobs]]` 는 스키마에 없는 키라 무시된다. 주기 작업은 `src/scheduler.py` 에 등록한다(운영에서만 기동). replica 는 `[deploy.multiRegionConfig.<region>] numReplicas` 로만 지정하며 1 이다(단일 인스턴스 전제). 가드: `tests/unit/scripts/test_railway_*_guard.py`.

## 변수
`APP_BASE_URL` 미설정 시 OAuth redirect_uri·Webhook 이 `http://` 로 등록된다. `postgres://` 는 `src/config.py` 가 변환한다. 목록: [`env-vars.md`](../reference/env-vars.md).
