## 배포 (Railway)

`.github/workflows/` 에 배포 워크플로는 없다. main 푸시 → Railway 가 루트 `Dockerfile` 로 빌드하고 `railway.toml` 배포 설정을 얹는다(2026-12-01 부터는 대시보드 값).

한 배포의 순서:

1. **빌드** — `Dockerfile`(`railway.toml::builder = "DOCKERFILE"`): apt·핀 분석기 + Node 20 → venv requirements → `npm ci` + `npm run build`(`package.json::"build":`). `PROVISIONED_ANALYZERS` 부재면 빌드 실패(이전 배포 유지). 핀은 `ci.yml` 조달 step 과 같은 커밋에서 바꾼다.
2. **pre-deploy** — `alembic upgrade head`(`railway.toml::preDeployCommand =`). 실패하면 배포가 중단된다.
3. **기동** — `/bin/sh -c "exec uvicorn … --port $PORT …"`(`railway.toml::startCommand =` = 이미지 `CMD`). 시작 명령은 exec 형이라 셸로 감싸야 `$PORT` 가 확장된다. import 시점에 `src/config.py::settings = build_settings()` 가 돌아 설정 검증 실패면 기동이 막힌다.
4. **lifespan** — `_validate_startup_config()` → `alembic upgrade head` 재실행([db.md](db.md) §적용) → 스케줄러·루프 지연 프로브 기동(`src/main.py::async def lifespan`). 루프가 막히면 30초 창마다 `event loop lag` WARNING 한 줄.
5. **헬스체크** — `GET /health` 60초(`railway.toml::healthcheckPath`), 실패 시 최대 10회 재시작.

replica 는 `[deploy.multiRegionConfig.us-east4-eqdc4a] numReplicas`(`railway.toml::[deploy.multiRegionConfig.us-east4-eqdc4a]`) 로만 지정한다 — `[deploy] numReplicas` 는 조용히 무시된다. 인앱 스케줄러(`src/scheduler.py::JOBS = (`)가 단일 인스턴스 전제라 2 이상이면 주간 리포트가 중복 발송된다.

`railway.toml` 에 새 키를 넣을 때는 Railway 공식 레퍼런스로 존재를 확인한다 — 모르는 키는 에러 없이 무시된다. 가드: `tests/unit/scripts/test_railway_cron_guard.py` · `test_railway_scaling_guard.py` · `test_dockerfile_contract.py`.

## 환경변수 추가

1. `src/config.py::class Settings(` 에 필드 선언. 기본값 없는 필드는 필수가 된다(현재 필수 3종 = `database_url` · `telegram_bot_token` · `telegram_chat_id`).
2. 제약이 있으면 `Field(ge=...)` 나 `field_validator` 를 같은 자리에 넣는다 — 잘못된 값은 기동 차단이 기본이다.
3. `docs/reference/env-vars.md` 표에 `` | `ENV_NAME` | 설명 | 예시 | `` 행 추가. `scripts/check_env_vars_sync.py` 가 Settings 필드와 대조해 미등재면 CI red.
4. `.env.example` 에 안전한 기본값으로 추가한다(위험 기본값 출하 금지 — `tests/unit/test_config.py::def test_env_example_does_not_ship_keyless_api_auth`).
5. 운영은 Railway Variables 탭에 설정한다. 값을 비워 두지 않는다 — pydantic 은 빈 문자열을 "설정된 값"으로 보고 기본값을 덮는다.

기능 kill-switch 는 Settings 가 아니라 `os.environ` 의 `<FEATURE>_DISABLED`(`src/shared/feature_kill_switch.py::f"{feature}_DISABLED"`) 를 읽으며 3~4번 가드 범위 밖이다 — 등재는 손으로 한다.

## 운영 판정

`src/config.py::def is_production` = `ENVIRONMENT=production` 이거나 `APP_BASE_URL` 이 `https` 로 시작. 켜지면 `/docs`·`/redoc` 비노출 + 기본 `SESSION_SECRET` 기동 차단 + 스케줄러 기동이 함께 걸린다. 둘 다 없으면 공개된 기본 시크릿으로 뜬다.

## 의존성

`requirements.txt` 는 직접 의존성 전부 `==` 정확 핀(`requirements.txt::fastapi==0.141.1` · `requirements.txt::starlette==1.6.0`). analyzer 바이너리를 추가하면 `tests/unit/scripts/test_analyzer_provenance.py` `_PROVENANCE` 에 (바이너리, 조달모드, 사유) 를 등재해야 CI 가 통과한다.

## 배포 실패 시

1. Railway 빌드 로그를 직접 본다 — push 성공은 빌드 성공이 아니다. 로컬 재현은 `docker build -t scam-local .`.
2. 실패 구간 앞뒤 30줄로 원인을 특정한다. 로그 없이 추측 수정하지 않는다.
3. 서비스를 먼저 되돌린다 — Railway 에서 **이전 배포 재배포**. 그다음 원인을 고친다.
4. 마이그레이션 단계 실패면 [db.md](db.md) §롤백.
