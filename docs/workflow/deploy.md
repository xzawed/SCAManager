## 배포 (Railway)

`.github/workflows/` 에 배포 워크플로는 없다. main 푸시 → Railway GitHub 연동이 `railway.toml` 을 읽어 배포한다. 대시보드의 Build/Pre-deploy 명령 칸은 비워 둔다(railway.toml 단일 출처).

한 배포의 순서:

1. **빌드** — NIXPACKS(`railway.toml:2`). `nixpacks.toml:7` aptPkgs + Node 20(`nixpacks.toml:9`) 설치 후 `railway.toml:3` buildCommand 가 analyzer 바이너리 8종을 설치하고 `npm ci && npm run build`(Tailwind → `src/static/css/dist/tailwind.css`, `package.json:7`) 로 끝난다. Python 버전 정본은 `.python-version`(3.12).
2. **pre-deploy** — `alembic upgrade head`(`railway.toml:21`). 실패하면 배포가 중단된다.
3. **기동** — `uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers`(`railway.toml:6`). import 시점에 `build_settings()`(`src/config.py:580`) 가 돌아 설정 검증 실패면 기동이 막힌다.
4. **lifespan** — `_validate_startup_config()` → `alembic upgrade head` 재실행(30초 타임아웃, 실패해도 기동. `STRICT_MIGRATION=true` 면 중단) → 스케줄러 기동(`src/main.py:223-269`).
5. **헬스체크** — `GET /health` 60초(`railway.toml:22`), 실패 시 최대 10회 재시작.

replica 는 `[deploy.multiRegionConfig.us-east4-eqdc4a] numReplicas`(`railway.toml:68`) 로만 지정한다 — `[deploy] numReplicas` 는 조용히 무시된다. 인앱 스케줄러(6 job, `src/scheduler.py:140`)가 단일 인스턴스 전제라 2 이상이면 주간 리포트가 중복 발송된다.

`railway.toml` 에 새 키를 넣을 때는 Railway 공식 레퍼런스로 존재를 확인한다 — 모르는 키는 에러 없이 무시된다. 가드: `tests/unit/scripts/test_railway_cron_guard.py` · `test_railway_scaling_guard.py`.

## 환경변수 추가

1. `src/config.py` `Settings`(`:16`)에 필드 선언. 기본값 없는 필드는 필수가 된다(현재 필수 3종 = `database_url` · `telegram_bot_token` · `telegram_chat_id`).
2. 제약이 있으면 `Field(ge=...)` 나 `field_validator` 를 같은 자리에 넣는다 — 잘못된 값은 기동 차단이 기본이다.
3. `docs/reference/env-vars.md` 표에 `` | `ENV_NAME` | 설명 | 예시 | `` 행 추가. `scripts/check_env_vars_sync.py` 가 Settings 필드와 대조해 미등재면 CI red.
4. `.env.example` 에 안전한 기본값으로 추가한다(위험 기본값 출하 금지 — `tests/unit/test_config.py:472`).
5. 운영은 Railway Variables 탭에 설정한다. 값을 비워 두지 않는다 — pydantic 은 빈 문자열을 "설정된 값"으로 보고 기본값을 덮는다.
6. `py -3 scripts/pre_push_gate.py` 통과 후 push.

기능 kill-switch 는 Settings 가 아니라 `os.environ` 의 `<FEATURE>_DISABLED`(`src/shared/feature_kill_switch.py:40`) 를 읽으며 3~4번 가드 범위 밖이다 — 등재는 손으로 한다.

## 운영 판정

`is_production`(`src/config.py:264`) = `ENVIRONMENT=production` 이거나 `APP_BASE_URL` 이 `https` 로 시작. 켜지면 `/docs`·`/redoc` 비노출 + 기본 `SESSION_SECRET` 기동 차단 + 스케줄러 기동이 함께 걸린다. 둘 다 없으면 공개된 기본 시크릿으로 뜬다.

## 의존성

`requirements.txt` 는 직접 의존성 전부 `==` 정확 핀(`fastapi==0.141.1` :5 · `starlette==1.6.0` :22). analyzer 바이너리를 추가하면 `tests/unit/scripts/test_analyzer_provenance.py` `_PROVENANCE` 에 (바이너리, 조달모드, 사유) 를 등재해야 CI 가 통과한다.

## 배포 실패 시

1. Railway 빌드 로그를 직접 본다 — push 성공은 빌드 성공이 아니다.
2. 실패 구간 앞뒤 30줄로 원인을 특정한다. 로그 없이 추측 수정하지 않는다.
3. 서비스를 먼저 되돌린다 — Railway 에서 **이전 배포 재배포**. 그다음 원인을 고친다.
4. 마이그레이션 단계 실패면 [db.md](db.md) §롤백.
