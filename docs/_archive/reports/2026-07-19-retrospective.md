# 5+1 회고 — 2026-07-19 (세션 2)

> 정책 8 진화 (4) **회고 카덴스 강제 트리거** 발화로 진입 — 직전 정식 회고([2026-07-18](2026-07-18-retrospective.md)) 이후 머지 **22 PR**(#1078~#1101), 임계 ≥15.
> 실행 = `.claude/workflows/retrospective.mjs` (loop-until-dry + 전건 cross-verify).

## 실행 요약

| 항목 | 값 |
|------|-----|
| 에이전트 | **164** |
| 라운드 | 3 (+ completeness gap 라운드) |
| 총 finding | 142 |
| **확정(confirmed)** | **135** |
| false-positive | 7 |
| verdict 커버리지 | **100%** (전건 검증 — 미검증 0) |
| 총 토큰 | 14,010,729 |
| 총 tool call | 2,030 |

**심각도 분포**: **P0** 11건 · **P1** 66건 · **P2** 58건

**관점 분포**: docs 33 · process 23 · tooling 21 · decision 18 · code 15 · observability 11 · tooling/process 6 · security 4 · code/architecture 4

**verdict 분포**: CONFIRMED 86 · SEVERITY_ADJUST 49

### cross-verify ROI (정책 8 진화 (2) — 정량 명시 의무)

| 지표 | 값 |
|------|-----|
| fp_blocked | 7 |
| confirmed | 135 |
| severity_adjusted | 49 |
| p0 | 11 |
| p1 | 66 |
| p2 | 58 |

---

## 본 세션 조치 현황 (P0 11건)

회고는 세션 **진행 중**에 돌았고, 확정된 P0 11건 중 **9건은 회고 완료 시점에 이미 수정돼 있었다**(회고가 독립적으로 같은 결함에 도달해 교차 확인된 형태). 잔여 2건은 **운영자 전용 조치**라 코드로 종결 불가.

| # | 요약 | 조치 |
|---|------|------|
| 1 | 검증 증거를 운영 경로가 아닌 import 경로에서 수집 (#1100 inert) | ✅ 근본 수정 **#1102** + 가드가 lifespan 재현 |
| 2 | alembic `fileConfig` 가 앱 로깅을 런타임 파괴 | ✅ **#1102** |
| 3 | owed 원장이 반증된 오귀인을 '재확인 불필요' 로 기록 | ✅ **#1102**(정정 섹션) · **#1105** |
| 4 | 반증 루프 2회차 붕괴 — 자체 검증 실패를 외부 귀인으로 종결 | ✅ 프로세스 교훈 + **#1102** 정정 |
| 5 | 수정 종결 근거를 운영에 없는 경로에서 수집 | ✅ **#1102** 가드가 `alembic.command.current` 로 실제 `env.py` 실행 |
| 6 | 배선 단언 가드가 import-time 만 측정 ('가드의 가드' 3회차) | ✅ **#1102** — 뮤테이션 실증(가드 제거 시 5건 FAIL) |
| 7 | httpx INFO 로깅으로 Telegram 봇 토큰 평문 기록 | ✅ **#1104** 2계층 리댁션 |
| 8 | 반증된 오귀인이 **자동 로드 메모리**에 사실로 잔존 | ✅ 메모리 반증 표기 정정 |
| 9 | Telegram 토큰 로테이션이 **집행면 밖 산문**으로만 존재 | ✅ **#1106** 원장 등재 / 🔺 **사용자 로테이션 대기** |
| 10 | `INTERNAL_CRON_API_KEY` 로테이션 저장소 기록 0 + 원장이 '✅ 유효' 단언 | ✅ **#1106** 등재·문구 정정 / 🔺 **사용자 로테이션 대기** |
| 11 | 의무를 사용자 로컬 메모리에 둔 것 = 인지 의존 산문 4회차 | ✅ **#1106** |

🔺 = 코드로 종결 불가한 **운영자 전용** 잔여 조치 (원장 안전등급 ⏳ 로 기계 추적 중).

🔴 **본 회고의 최대 교훈**: 세션이 "문서-only 시정은 행동을 못 바꾼다" 를 **두 번 P0 로 진단해놓고**, 정작 자신이 만든 로테이션 의무를 채팅과 로컬 메모리에만 남겼다(#9~#11). 진단과 실천의 괴리가 **같은 세션 안에서** 재생산된다.

---

## 🔴 P0 (11건)

### P0-1. [process] 검증 증거를 운영 경로가 아닌 로컬 import 경로에서 수집 — #1100 이 무력(inert) 상태로 배포되고 사용자에게 관측 불가한 검증을 요구

- **위치**: `src/main.py:215`
- **verdict**: CONFIRMED
- **주장**: #1100 은 PR 본문에 '실출력 확인: 2026-07-19 11:51:36 INFO [src.scheduler] scheduler started — 5 jobs' 를 검증 증거로 제시했으나, 이 관측은 `import src.main` 시점(src/main.py:42 `configure_logging()`) 경로다. 운영 startup 은 그 뒤 lifespan 에서 `_run_migrations`(src/main.py:215)를 돌리고, 그 안의 alembic/env.py:19 `fileConfig(config.config_file_name)` 가 root 핸들러·레벨·`disable_existing_loggers` 를 통째로 덮어써 #1100 의 수정을 무효화한다. 즉 '검증했다'고 선언한 경로가 실패가 발생하는 경로와 다르다.
- **권고**: (1) 운영 사고 fix 의 검증 증거는 '해당 실패가 발생하는 진입 경로'에서 수집한 것만 인정 — import 시점 관측을 lifespan 동작의 증거로 대체 금지. (2) 회귀 가드로 `_run_migrations()` 호출 **후** root 로거가 INFO 유효·우리 핸들러 유지·`uvicorn.access` 미disabled 임을 단언하는 테스트 추가(현 5건은 모두 이 상호작용을 재현하지 않음). (3) alembic/env.py 의 `fileConfig` 를 앱 인프로세스 실행 시 skip 하도록 분기.

### P0-2. [code] alembic fileConfig 가 앱 로깅을 런타임에 파괴 — #1100 의 수정이 운영에서 무력(inert)

- **위치**: `alembic/env.py:19`
- **verdict**: CONFIRMED
- **주장**: `alembic/env.py:19` 의 `fileConfig(config.config_file_name)` 가 앱 lifespan 내 `_run_migrations` 경로로 실행되면서 `configure_logging()` 이 방금 설정한 로깅을 통째로 되돌린다. 결과적으로 #1100 은 단위 테스트 5개가 모두 통과하지만 운영에서는 한 줄도 복구하지 못한다. 호출 순서: `src/main.py:42` `configure_logging()` (import 시점) → `src/main.py:215` `asyncio.to_thread(_run_migrations)` → `src/main.py:102` `command.upgrade(alembic_cfg, "head")` → `alembic/env.py:19` `fileConfig(...)`. 스케줄러 기동(`src/main.py:259`)은 마이그레이션보다 뒤이므로 #1099 의 `scheduler started — 5 jobs` 를 포함한 모든 job 로그도 전부 소실된다.
- **권고**: alembic 공식 관용구로 인-프로세스 호출 시 로깅 재설정을 차단한다. `src/main.py:101` 에서 `alembic_cfg.attributes['configure_logger'] = False` 를 설정하고, `alembic/env.py:18-19` 를 `if config.config_file_name is not None and config.attributes.get('configure_logger', True): fileConfig(config.config_file_name, disable_existing_loggers=False)` 로 교체한다. `disable_existing_loggers=False` 는 CLI 경로(`preDeployCommand = "alembic upgrade head"`, railway.toml:21)에 대한 심층 방어로 함께 둔다. 검증은 코드 리뷰가 아니라 배포 후 Railway 로그에 `DB migration completed` 다음 줄들과 `scheduler started — 5 jobs` 가 실제로 나타나는지로 한다.

### P0-3. [docs] owed 원장이 반증된 오귀인을 '재확인 불필요' 확정 사실로 기록 — 다음 세션을 능동적으로 오도

- **위치**: `docs/runbooks/owed-verification.md:36`
- **verdict**: CONFIRMED
- **주장**: docs/runbooks/owed-verification.md:36 이 로그 소실 원인을 'Railway deploy 로그 수집 끊김 … **앱 문제 아님**' 으로 단정하고, 이를 line 29 `### 이미 확인된 것 (재확인 불필요)` 섹션 아래에 배치했다. 본 세션 확정 P0 에 따르면 이 진단은 **반대**다 — 원인은 앱 측(alembic fileConfig 가 uvicorn.access 로거를 disable)이며, 원장은 다음 세션에게 '재확인하지 말라'고 명시적으로 지시하고 있다.
- **권고**: line 36 행을 즉시 정정(❌ 앱 문제 아님 → 🔴 앱 측 원인 확정: alembic fileConfig 가 앱 로깅 파괴)하고 `재확인 불필요` 섹션에서 제거. 원장에 '반증 시 정정' 규칙 추가 — 현재 작성 규칙(line 5)은 append-only 와 행 삭제 금지만 규정할 뿐, **기록된 진단이 틀렸을 때의 정정 절차가 없다**. 이것이 오귀인이 3세션 생존한 문서 측 기전이다.

### P0-4. [decision] 반증 루프 2회차 붕괴 — 자체 검증 항목이 두 번째로 실패했는데 외부 귀인으로 종결

- **위치**: `docs/runbooks/owed-verification.md:36`
- **verdict**: CONFIRMED
- **주장**: #1099·#1100 이 각각 PR 본문 §🔍 사용자 검증 필요 에 동일한 반증 테스트("배포 후 로그에 `scheduler started — 5 jobs` 가 뜨는지")를 명시했다. 1회차 실패는 올바른 근본 원인(#1100 로깅 미설정)을 산출했으나, 2회차 실패는 "Railway 로그 수집 문제 — **앱 문제 아님**" 이라는 외부 귀인으로 종결됐다. 같은 반증 테스트의 연속 실패는 '수정이 무력(inert)' 가설의 가장 강한 신호인데, 그 가설이 한 번도 세워지지 않았다.
- **권고**: 규칙 신설: PR 자체 §사용자 검증 필요 항목이 **2회 연속 실패**하면 1순위 가설은 반드시 '수정이 무력' 이며, 외부(플랫폼) 귀인은 **긍정 통제 없이 금지**. 본 건의 긍정 통제 = 같은 지점에서 WARNING 레벨 라인 1줄 동시 방출 → WARNING 은 보이는데 INFO 만 안 보이면 플랫폼이 아니라 우리 문제로 확정. 부재(absence) 관측은 단독으로 외부 귀인 근거가 될 수 없음을 정책 13 에 명문화.

### P0-5. [decision] 수정 종결 근거를 운영에 존재하지 않는 경로에서 수집 — "실출력 확인" 이 마이그레이션 없는 경로

- **위치**: `src/main.py:215`
- **verdict**: CONFIRMED
- **주장**: #1100 커밋 본문은 `실출력 확인 2026-07-19 ... INFO [src.scheduler] scheduler started — 5 jobs: ...` 를 수정 완료 근거로 제시했다. 그러나 운영 기동 순서상 이 라인은 마이그레이션 **이후**에만 방출되므로, 인용된 관측은 `_run_migrations` 가 동일 프로세스에서 실행되지 않는 경로에서만 얻을 수 있다. 즉 관측 경로와 배포 경로를 가르는 단 하나의 변수가 정확히 파괴자였다.
- **권고**: 관측성(observability) 수정은 컴포넌트 직접 호출이 아니라 **실제 기동 진입점(lifespan)** 을 통과시켜 검증한다. 회귀 가드 = 임시 DB 에 대해 lifespan 을 실행(실 alembic upgrade 포함)한 뒤 `src.*` INFO 레코드가 **생존**하는지 단언하는 테스트. 즉시 수정 = src/main.py 의 `_run_migrations` 직후 `configure_logging()` 재호출(멱등이므로 안전) 또는 alembic/env.py 의 `fileConfig` 를 앱-인프로세스 실행 시 우회.

### P0-6. [tooling] 배선 단언 가드가 import-time 만 측정 — 파괴는 lifespan 에서 일어나 측정창 밖. '가드의 가드' 주제의 3회차 재생산

- **위치**: `tests/unit/test_logging_config.py:75`
- **verdict**: CONFIRMED
- **주장**: #1100 은 '모듈만 있으면 dead code' 교훈을 적용해 배선 단언 테스트를 넣었지만, 측정 시점이 import-time 이라 파괴 시점(lifespan 내 마이그레이션)을 구조적으로 볼 수 없다. 가드가 검증하는 명제는 '호출되었는가'이고, 정작 필요한 명제는 '런타임에 여전히 유효한가'였다. 4개 테스트 전부 green 인데 운영 효과는 0.
- **권고**: (1) 즉시 수정: `_run_migrations` 직후 `configure_logging()` 재호출, 또는 alembic Config 에 `attributes['configure_logger']=False` 를 세워 fileConfig 자체를 건너뛴다(railway.toml preDeployCommand 가 이미 마이그레이션을 수행하므로 lifespan 경로는 비-Railway fallback 전용). (2) 가드 규칙 승격: 전역 프로세스 상태(logging·warnings·locale·signal)를 설정하는 코드의 배선 테스트는 'import 후'가 아니라 '전체 startup 시퀀스 종료 후' 상태를 단언해야 한다.

### P0-7. [code] #1100 + alembic 봉인이 httpx INFO 로깅을 켜면서 Telegram 봇 토큰이 운영 로그에 평문 기록된다

- **위치**: `src/logging_config.py:57`
- **verdict**: CONFIRMED
- **주장**: `configure_logging()` 이 root 레벨을 INFO 로 올리면서, 그때까지 lastResort(WARNING) 로 버려지던 `httpx` 라이브러리의 요청 로그가 살아났다. httpx 는 모든 요청을 `logger.info('HTTP Request: %s %s ...', request.method, request.url, ...)` 로 남기는데, Telegram Bot API 는 **토큰이 URL 경로에 들어간다**(`/bot{token}/sendMessage`). 결과: 알림 1건마다 봇 토큰 전체가 Railway 로그에 평문으로 적힌다. 동일 경로로 Discord/Slack/n8n webhook URL(경로 자체가 시크릿) 도 노출된다 — 4 notifier 전부 `build_safe_client()` = httpx 사용. 이 사고는 #1100 단독이 아니라 **본 세션의 alembic 봉인(24d90b8)이 #1100 을 운영에서 유효화하면서 비로소 실제 노출로 전환**된다 — 즉 지금 머지되면 다음 배포부터 유출이 시작된다. 저장소에는 httpx 로거 억제가 단 한 곳도 없다(`grep -rn 'getLogger("httpx")' src/ tests/unit/conftest.py` = 0건). 프로젝트에는 Telegram 토큰 유출 전례(PR #497, 보안 3중 가드 신설)가 있어 동일 사고 클래스의 재발이다.
- **권고**: `configure_logging()` 안에서 `logging.getLogger("httpx").setLevel(logging.WARNING)` (+ `httpcore`) 을 명시 억제하거나, 시크릿 경로를 마스킹하는 `logging.Filter` 를 root 핸들러에 부착한다. 회귀 가드는 산문 검사 금지 원칙대로 **실제 httpx 요청 1건을 MockTransport 로 발생시키고 캡처 로그에 봇 토큰 문자열이 없음을 단언**할 것(alembic 가드 test_alembic_env_logging_guard.py 가 채택한 관측-상태 단언 패턴과 동일). 이미 배포된 로그가 있다면 봇 토큰 회전 필요 여부를 사용자에게 확인(비-AI 채널 의무).

### P0-8. [docs] 반증된 오귀인이 자동 로드 메모리에 사실로 잔존 — 정정이 저-트래픽 문서에만 적용됨

- **위치**: `C:/Users/dirtc/.claude/projects/d--Source-SCAManager/memory/project-cron-scheduler-observability-2026-07-19.md:36`
- **verdict**: CONFIRMED
- **주장**: 본 세션이 반증한 "Railway 로그 수집 문제, 앱 문제 아님" 오귀인이 repo 문서(owed-verification.md)에서만 정정되고, **매 세션 자동 주입되는 메모리에는 그대로 사실로 남아 있다**. 다음 세션은 정정본을 읽기 전에 반증된 주장을 먼저 학습한다.
- **권고**: 메모리 3개 지점(MEMORY.md:3 · 대상 파일 :3/:32/:36) 을 동일 커밋에서 정정하고, §32 를 `~~취소선~~ + 반증 완료(2026-07-19)` 형태로 교체. 규칙화: **운영 진단이 반증되면 정정 대상 = repo 문서 + 메모리 양쪽 동시**(메모리가 자동 주입이므로 우선순위 상). owed-verification.md:98 의 교훈 문장이 메모리에도 존재해야 한다.

### P0-9. [tooling/process] Telegram 봇 토큰 로테이션 — 유일한 운영자 전용 보안 조치가 카운터 집행면 밖 산문으로만 존재하며, main 에는 아예 없다

- **위치**: `docs/runbooks/owed-verification.md:45`
- **verdict**: CONFIRMED
- **주장**: 유출된 `TELEGRAM_BOT_TOKEN` 의 로테이션은 코드로 대체 불가한 운영자 전용 잔여 조치인데, 저장소 내 유일한 기록이 `docs/runbooks/owed-verification.md:45` 의 산문 한 줄이다. `scripts/check_owed_verification.py` 의 `_ROW`(:32)는 첫 셀이 `#\d+` 인 **표 데이터 행만** 매칭하고 `parse_rows`(:42-47)는 `SAFETY_TIER_MARKER` 섹션 내부만 안전등급으로 분류하므로, 산문은 스캔 대상이 아니다 → SessionStart 훅이 이 항목을 **결코 경고하지 않는다**. 더 나아가 `git show main:docs/runbooks/owed-verification.md | grep -n 로테이션` = **NOT PRESENT ON MAIN** — 이 산문조차 미머지 브랜치 `docs/owed-cron-verified`(c887469) 에만 있다. #1104(`94f56e1`, 브랜치 `fix/redact-secrets-in-logs`) 도 미머지라 그 commit body 의 '잔여 조치' 도 아직 main 부재이며, 머지되면 git 히스토리로 가라앉아 반복 재부상하지 않는다.
- **권고**: #1105(원장 갱신) 머지 전에 안전/데이터 등급 표에 `**#1104**` 키 행을 추가한다 — 검증 항목='TELEGRAM_BOT_TOKEN 로테이션(로그 평문 유출 5건, 코드 회수 불가)', 검증 방법='BotFather `/revoke` → Railway 변수 교체 → Telegram 알림 1건 정상 수신 확인', 상태=⏳. 그래야 SessionStart 훅이 매 세션 loud 경고한다. 산문 45줄은 배경 설명으로 존치하되 표 행이 정본.

### P0-10. [tooling/process] INTERNAL_CRON_API_KEY 로테이션 — Claude 자신이 유발한 credential 노출인데 저장소 기록 0건이고, 원장은 오히려 '✅ 유효' 로 단언한다

- **위치**: `docs/runbooks/owed-verification.md:40`
- **verdict**: CONFIRMED
- **주장**: gap 브리프에 없던 **두 번째** 로테이션 미결이 존재한다. 메모리 `project-logging-wipe-token-leak-2026-07-19.md:15` 기록: *"Claude 가 Railway 변수 조회 시 grep 패턴(`CRON`)이 **값까지 매칭**해 대화 기록에 평문 출력(정책 12 위반)"*. 이 항목은 저장소 어디에도 없다 — 산문조차 없다. 더 심각한 것은 같은 원장 `:40` 이 `| INTERNAL_CRON_API_KEY | ✅ Railway 에 설정됨·유효 |` 를 **'이미 확인된 것 (재확인 불필요)'** 표(:33) 안에 넣어, 실제로는 로테이션이 필요한 키를 **재점검 면제 대상으로 명시 단언**한다. 이는 같은 원장이 :90/:107 에서 P0 로 규정한 *"오귀인이 원장에 사실로 기록되어 다음 세션을 오도"* 패턴의 즉시 재생산이다. 유일한 기록처인 메모리는 `~/.claude/projects/` 하위 = 저장소 밖 → 버전관리·PR 리뷰·CI 가시성 전무, 사용자가 기기를 바꾸면 소실.
- **권고**: (1) 원장 :40 행의 `✅ 유효` 를 즉시 정정 — `⚠️ 로테이션 필요(2026-07-19 대화 기록 평문 노출)` 로 바꾸고 '재확인 불필요' 표에서 제거. (2) 안전등급 표에 로테이션 행 추가(PR 키는 본 정정 PR 번호 사용). (3) 재발 방지 규칙을 메모리가 아니라 `.claude/rules/security.md` 에 등재 — `railway variables --kv` 결과를 grep 하지 말 것, `cut -d= -f1` 로 이름만 추출 후 필터.

### P0-11. [tooling/process] 의무를 사용자 로컬 메모리에 둔 것 = 이번 세션이 두 번 유죄 선고한 '인지 의존 산문' 시정의 4회차

- **위치**: `docs/runbooks/owed-verification.md:126`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P0 → P0)
- **주장**: gap 브리프의 '영원히 재부상하지 않는다' 는 **정정이 필요하다** — 두 로테이션 의무는 `MEMORY.md:3` 인덱스와 메모리 본문 :12-16(§'🔴 미결 사용자 조치 (다음 세션 진입 시 회신 요청 의무)')에 실재하고, MEMORY.md 는 매 세션 자동 로드된다. 따라서 완전 무형은 아니다. 그러나 이는 **집행이 아니라 인지 의존 산문**이며, 이번 세션이 이미 두 번 불충분하다고 판정한 바로 그 시정 계급이다 — 회고 카덴스는 CLAUDE.md 산문으로 2회 연속 실패한 뒤 #1080 으로 기계화됐고, owed 원장은 #1084 산문-only 가 P0 로 규정된 뒤 #1095 로 배선됐다. 여기에 더해 메모리는 `~/.claude/projects/d--Source-SCAManager/memory/` 소재 = **저장소 밖**이라 버전관리·PR 리뷰·CI·팀 공유 어디에도 걸리지 않는다. 카운터가 존재하는데도 그 집행면 밖에 기록했다는 점에서 앞선 3회와 형태가 다르며, 실패 모드는 동일하다.
- **권고**: 메모리를 보조로 두되 **정본은 저장소 내 원장 표**로 승격한다. 추가로 '이번 세션이 만든 운영자 전용 조치'를 세션 종료 6-step ⑤ 의 하위 체크로 명문화 — 원장 표 편입 없이 메모리에만 기록하는 것을 금지 패턴으로 `.claude/rules/security.md` 에 등재.

---

## P1 (66건)

### P1-1. [process] 추론(귀인)이 owed 원장에 '실측·재확인 불필요'로 기록되어 다음 세션의 반증 기회를 구조적으로 봉쇄

- **위치**: `docs/runbooks/owed-verification.md:36`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: owed-verification.md:29 의 '### 이미 확인된 것 (재확인 불필요)' 표 안에 :36 '🔴 Railway deploy 로그 수집 ❌ … uvicorn access log 24h 0건 … **앱 문제 아님** → 로그 기반 검증 불가, **DB 관측이 유일 수단**' 이 들어갔다. 'access log 0건'은 관측이지만 '앱 문제 아님(=플랫폼 수집 장애)'은 **귀인**이며, 실제 원인은 fileConfig 의 `disable_existing_loggers=True` 가 `uvicorn.access` 로거를 비활성화한 것 = 정확히 앱 문제다. 관측과 귀인을 같은 표에 섞고 '재확인 불필요' 라벨을 붙여, 다음 세션이 이 가설을 재검토할 경로를 문서로 차단했다.
- **권고**: 원장 표를 '관측(fact)' 과 '해석(inference)' 두 컬럼으로 분리하고, '재확인 불필요' 는 관측에만 부여한다. 외부 플랫폼 귀인('앱 문제 아님')은 앱 측 배제 실험(예: 명시적 WARNING 라인 1건 방출 후 수집 여부)을 통과하기 전까지 ⏳ 로 유지. 현 :36 과 :86 행은 즉시 정정 필요(귀인 반전).

### P1-2. [process] '기계 신호로 승격' 을 단언한 P0 시정(#1080)이 실제로는 미배선 — 문서-only 시정 4회차, 15 PR 간 무효

- **위치**: `CLAUDE.md:51`
- **verdict**: CONFIRMED
- **주장**: #1080 은 '문서-only 정책이 두 번 연속 실패해 기계 신호로 승격' 이라 CLAUDE.md 에 단언했으나, diff 는 `scripts/check_retro_cadence.py` 신설 + CLAUDE.md 체크리스트에 `python scripts/check_retro_cadence.py` 한 줄 추가가 전부이고 어떤 집행면에도 배선되지 않았다. 즉 '기계화' 의 실체는 'Claude 가 기억해서 실행할 명령' 으로, P0 가 지적한 실패 계층과 동일하다. SessionStart 배선은 15 PR 뒤 #1095 에서야 이뤄졌다.
- **권고**: '기계화/자동화' 라는 표현을 PR·정책 본문에 쓸 때 **집행면 diff(.claude/settings.json hook, .github/workflows, pre-commit) 동반을 필수 조건**으로 못박는다. 스크립트 신설만으로는 '도구 추가' 라 부르고 '기계 신호' 라 부르지 않는다. 검증: 신규 가드 PR 은 '이 가드를 무력화했을 때 무엇이 loud fail 하는가' 1줄 명시(뮤테이션 서술) 의무.

### P1-3. [process] 2026-07-19 5+1 회고(186 에이전트·확정 147건)의 리포트가 미아카이브 — 카덴스 카운터 실명 + P1 55·P2 90 미추적

- **위치**: `docs/STATE.md:19`
- **verdict**: CONFIRMED
- **주장**: STATE.md:19 는 2026-07-19 범위 한정 5+1 회고(wf_40082e43, 186 에이전트, 확정 147 = P0 2·P1 55·P2 90) 실시를 기록하지만, `docs/_archive/reports/` 에는 2026-07-19 리포트 파일이 없다(최신 = 2026-07-18-retrospective.md). 결과 (1) 카덴스 카운터가 이 회고를 못 보고 '23 PR 미회고' 로 보고해 신호가 부풀려지고, (2) 확정 147건 중 #1095~#1098 로 처리된 P0 2건 + 일부 P1 외 나머지(P1 55·P2 90 대부분)가 어떤 원장에도 남지 않았다.
- **권고**: 회고 실시 = 리포트 아카이브까지가 1 단위(직전 사이클 #1078 은 이행했다). 범위 한정 회고도 파일명에 `retrospective` 를 포함해 아카이브하고, 미처리 P1/P2 는 백로그 표로 이월. 아카이브 없는 회고는 카운터 관점에서 '일어나지 않은 것' 이므로 카운터 신뢰도까지 훼손한다.

### P1-4. [process] 인수인계 헤더 '단 하나의 미완 검증' 이 기계 카운터 상태(미결 6건)와 정면 모순 — 다음 세션의 경고 무시 학습 유발

- **위치**: `docs/runbooks/owed-verification.md:13`
- **verdict**: CONFIRMED
- **주장**: #1101 이 원장 최상단에 추가한 :13 '**단 하나의 미완 검증**이 남았고' 는 같은 파일 :44~:45 의 안전등급 ⏳ 2건(#1058 SMTP 실발송·#1062 IDOR 과잉차단)과 :51~:54 운영등급 4건을 부정한다. 실제 `check_owed_verification.py` 실행은 '안전등급 미회신 2건: #1058, #1062 / 운영등급 4건' 을 loud 경고한다. 다음 세션은 SessionStart 에서 '6건 미결' 경고와 '단 하나' 헤더를 동시에 받게 되며, 산문이 기계 신호를 무력화하는 방향으로 작동한다. 또한 정책 5 NEW-P0-N(안전등급 매 사이클 명시 회신 의무)이 세션 종료 PR(#1101)에서 이행되지 않아 안전등급 2건이 5세션째 ⏳ 로 누적됐다(원장 :109 스스로 '4세션째 누적' 이라 기록).
- **권고**: 인수인계 헤더 문구를 '**cron 검증** 미완 1건 + 안전등급 사용자 회신 대기 2건 + 운영등급 4건' 으로 정정한다. 원칙: 원장 산문 요약은 파서가 세는 ⏳ 카운트와 **수치 일치 의무**(불일치 시 회귀 가드로 차단 — 이미 `test_live_ledger_parses_nonempty` 가 있으므로 '헤더 주장 카운트 == 파싱 카운트' 단언 추가가 저비용).

### P1-5. [process] #1100 이 owed 원장에 미등재 — 원장 자체의 작성 규칙 위반, 그 결과 이번 P0 가 기계 경고 사각지대에 남음

- **위치**: `docs/runbooks/owed-verification.md:5`
- **verdict**: CONFIRMED
- **주장**: 원장 :5 작성 규칙은 '세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다' 이고, #1100 은 PR 본문 §'🔍 사용자 검증 필요' 에 배포 후 Railway 로그 관측 3항목을 명시한 = 정확히 그 부류다. 그런데 원장에 #1100 행이 없다. 더욱이 #1101 은 #1100 이후에 작성되어 같은 파일을 편집했음에도 등재하지 않았다. 결과적으로 이번 세션에서 확정된 P0(로깅 무력화)의 검증 항목이 기계 카운터의 감시 대상에서 빠졌다.
- **권고**: PR 본문에 §'🔍 사용자 검증 필요' 가 존재하고 그 내용이 운영 관측이면 원장 등재를 **기계 강제**한다(PR 게이트: body 에 해당 섹션 + 운영 키워드 매칭 시 owed-verification.md diff 동반 요구). 현재는 사람이 기억하는 구조라 이번처럼 세션 마지막 PR 조차 놓친다.

### P1-6. [process] 'P0 해결' 조기 선언이 같은 세션에 재발 — #1099 가 #1095 를 정정해놓고 3시간 뒤 #1100 이 동일 패턴 반복

- **위치**: `src/main.py:216`
- **verdict**: CONFIRMED
- **주장**: #1099 커밋 본문은 '직전 #1095 의 따옴표·-f 수정은 실재 결함이었으나 명령 자체가 실행되지 않아 무의미했다. "P0 해결" 보고는 성급했다' 로 자기 정정했다. 그럼에도 같은 세션 3시간 뒤 #1100 이 로컬 import 관측만으로 '검증' 을 선언하고 사용자에게 관측 불가능한 확인 절차를 넘겼다 — 정정이 서술로만 남고 그 다음 PR 의 규율로 전환되지 않았다. 근본은 '코드 머지 완료' 와 '운영 효과 확인' 을 단일 라벨('해결/검증')로 보고하는 관행이다.
- **권고**: 운영 사고 fix 보고를 2단 상태로 강제한다 — '코드 결정 종결(머지)' / '운영 효과 미검증(owed 등재)'. 단일 '해결·검증' 라벨 금지. #1099 가 남긴 교훈('저장소 밖 설정은 테스트가 못 잡는다')이 정작 저장소 **안** 상호작용(alembic↔app 로깅)에서 재발한 만큼, 교훈을 '외부 설정' 이 아니라 '테스트가 재현하지 않는 실행 경로' 로 일반화해 기록할 것.

### P1-7. [code] 명백해 보이는 수정(마이그레이션 후 configure_logging 재호출)은 함정 — src.* 로거는 여전히 침묵하고 로그는 이중 출력된다

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: P0 의 가장 자연스러운 대응인 '마이그레이션 직후 `configure_logging()` 재호출' 은 문제를 고치지 못하면서 고쳐진 것처럼 보이게 만든다. `src/logging_config.py` 의 `configure_logging` 은 root 로거만 조작하므로, `disable_existing_loggers=True` 로 `disabled=True` 가 찍힌 `src.*` 87개 로거를 되살리지 못한다. 동시에 `_MARKER` 기반 멱등성 가드는 alembic 이 붙인 외래 stderr 핸들러를 인식하지 못해 제거하지 않으므로, 우리 stdout 핸들러가 추가되어 root 에 핸들러 2개가 공존한다.
- **권고**: 재호출 방식을 채택하지 말고 P0 권고대로 fileConfig 자체를 차단한다. 부득이 재호출 경로를 남긴다면 (a) `disable_existing_loggers=False` 를 반드시 병행하고 (b) `configure_logging` 이 재부착 전에 `_MARKER` 없는 외래 핸들러를 정리하도록 보강해야 한다. 검증 단언은 root 핸들러 존재 여부가 아니라 `logging.getLogger('src.main').disabled is False` 와 실제 emit 캡처(caplog/StringIO)로 세울 것.

### P1-8. [code] '가드의 가드' 연장 — 결함을 잡을 수 있는 단언은 이미 존재했으나 운영 순서를 재현하는 시나리오가 없어 발화하지 못했다

- **위치**: `tests/unit/test_logging_config.py:41`
- **verdict**: CONFIRMED
- **주장**: #1100 의 테스트는 결함 탐지 능력이 없어서 실패한 것이 아니라, 결함이 발생하는 순서를 한 번도 구성하지 않아서 실패했다. `tests/unit/test_logging_config.py:41` 의 `assert logging.getLogger('src.scheduler').isEnabledFor(logging.INFO)` 는 이 결함을 정확히 탐지할 수 있다. 그러나 모든 테스트가 `configure_logging()` 호출 직후에만 단언하고, 운영의 실제 순서(configure_logging → 마이그레이션 → 서비스 기동)를 재현하지 않는다. 배선 단언인 `test_main_configures_logging_at_import` (`tests/unit/test_logging_config.py:75-86`) 도 import 시점의 root 핸들러 존재만 확인하므로 lifespan 이후 상태에 대해 아무것도 말하지 않는다.
- **권고**: 단언을 늘리지 말고 **순서를 재현하는 테스트 1개**를 추가한다: `configure_logging()` → `command.upgrade(Config('alembic.ini'), 'head')`(또는 최소 재현으로 `fileConfig('alembic.ini')`) → `assert not logging.getLogger('src.scheduler').disabled` + `assert logging.getLogger('src.main').isEnabledFor(logging.INFO)`. 일반화된 규율로 `.claude/rules/testing.md` 에 '배선 단언은 import 시점이 아니라 startup 완료 후 상태에서 세운다' 를 추가할 것 — 이번 결함의 재발 형태는 로깅에 국한되지 않는다.

### P1-9. [code] 오귀인이 운영 원장에 사실로 기록되어 3세션 검증을 봉쇄 — 반증 증거가 오히려 결론의 근거로 읽혔다

- **위치**: `docs/runbooks/owed-verification.md:36`
- **verdict**: CONFIRMED
- **주장**: `docs/runbooks/owed-verification.md:36` 이 로그 소실을 '**앱 문제 아님**' 으로 단정하고 'DB 관측이 유일 수단' 이라는 운영 결론을 확정했다. 이 판정은 틀렸을 뿐 아니라, 판정의 근거로 인용된 실측이 실은 정반대(앱 문제)를 가리키는 증거였다. 그 결과 #1073·#1075 의 검증 경로가 로그 관측에서 DB 관측으로 우회 설계되었고(:79-90 §검증 수단 정정), cron 검증이 3세션째 미완으로 남았다.
- **권고**: P0 수정 후 :36 행과 :79-90 §검증 수단 정정 을 정정하고, 폐기가 아니라 '오귀인 이력' 으로 남겨 동일 추론 실패를 다음 세션이 재현하지 않게 한다. 규율로는 '외부 인프라 탓' 결론에 도달하기 전 반증 질문 1개를 의무화할 것 — *'그 가설이 설명하지 못하는 관측이 이미 표에 있는가?'* 본 건에서는 '왜 alembic 로그만 살아남았는가' 한 문장이 즉시 진단을 뒤집었을 것이다.

### P1-10. [docs] STATE.md(SSOT)가 운영에서 무력한 #1100 로깅 수정을 해소된 것으로 서술

- **위치**: `docs/STATE.md:25`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: docs/STATE.md:25 는 #1100 을 '`src/logging_config.py` 신설(stdout 핸들러·INFO·멱등) + `main.py` import 시점 배선' 으로 종결 서술하고, 그 영향으로 'owed 원장의 로그 확인 절차가 물리적으로 불가능' 했던 문제가 풀린 것처럼 읽힌다. 실제로는 configure_logging(src/main.py:42) 직후 lifespan 마이그레이션(src/main.py:215)이 설정을 통째로 덮어써 운영에서 inert 다. 프로젝트가 단일 진실 소스로 선언한 문서가 미해결 P0 를 해결로 기록했다.
- **권고**: STATE.md:25 에 '🔴 운영 무력(inert) — alembic fileConfig 가 덮어씀, 후속 PR 필요' 를 즉시 병기. 더 근본적으로, 6-step ⑤(STATE 갱신)가 '무엇을 했는가' 만 기록하고 '운영에서 실제로 동작하는가' 는 기록하지 않는 구조 — 로컬 단위 테스트 통과를 곧 해소로 승격시키는 문서 관행이 P0 를 은폐했다.

### P1-11. [docs] src/logging_config.py 신규 파일이 docs/architecture.md 에 미등재 — 6-step ⑥ 위반

- **위치**: `docs/architecture.md:34`
- **verdict**: CONFIRMED
- **주장**: #1100 이 `src/logging_config.py` 를 신설했으나 docs/architecture.md 의 src/ 트리에 등재하지 않았다. CLAUDE.md 6-step ⑥ 및 아키텍처 동기화 체크리스트가 신규 src/ 파일 등재를 예외 없이 의무화한다. 같은 세션의 #1099 는 scheduler.py 를 정상 등재했으므로 규칙 미인지가 아니라 개별 PR 누락이다.
- **권고**: architecture.md src/ 트리에 logging_config.py 한 줄 추가하되, 설명에 alembic fileConfig 상호작용 경고를 함께 명시(단순 등재로 끝내면 P0 재발 지식이 트리에 남지 않는다).

### P1-12. [docs] STATE.md '최신' 블록이 자체 갱신 규칙 3개를 동시 위반 — 헤더 범위·불릿 상한·날짜

- **위치**: `docs/STATE.md:9`
- **verdict**: CONFIRMED
- **주장**: docs/STATE.md:9 블록 제목은 '총 17 PR #1077~#1092' 라 선언하는데 그 아래 불릿이 #1094~#1100 까지 이어 붙어 제목과 내용이 불일치한다. 이는 STATE.md:7 이 명시적으로 금지한 '헤더에 직전 체인 누적' 그 자체이며, 같은 규칙 (3) '불릿 5~8줄' 도 실측 15줄로 초과, 규칙 (0) 날짜 헤더도 2026-07-19 작업을 담은 채 2026-07-18 로 정체돼 있다. 규칙 (0) 은 문서 자체가 '절차에서 상시 누락되던 필드' 라 경고한 항목의 재발이다.
- **권고**: '최신' 블록을 2026-07-19 세션으로 교체하고 세션2 서사는 cycle-history 로 이관(P1-4 와 동일 작업). 규칙 (0)(3) 은 doc_review_gate 가 이미 CRITICAL 게이팅 대상이라 명시했으므로, 산문 규칙이 아니라 기계 체크(날짜 헤더 vs 최신 커밋 날짜·블록 불릿 수)로 승격 검토 — 문서-only 규칙이 반복 실패한 카덴스 트리거와 동형 패턴이다.

### P1-13. [docs] owed 원장이 #1100·#1099 를 추적 대상에서 누락 — 원장이 정의한 목적에 정확히 부합하는 PR

- **위치**: `docs/runbooks/owed-verification.md:5`
- **verdict**: CONFIRMED
- **주장**: owed-verification.md 는 line 3 에서 '코드로 증명 불가한 운영 검증(… cron 실제 실행 …)을 남긴 PR' 을 추적한다고 선언하고 line 5 에서 세션 종료 시 등재를 의무화하지만, 추적 행은 #1058·#1062·#1071·#1072·#1073·#1075 6건뿐이다. 본 세션 최대 리스크 PR 인 #1100(운영 로그 실제 출력 — 현재 inert 확정)과 #1099(스케줄러 실기동)이 자체 행 없이 누락됐다. 원장이 가장 필요한 순간에 스스로를 적용하지 않았다.
- **권고**: #1100 행 추가(검증 방법 = 운영 stdout 에 `[src.scheduler] scheduler started` 실제 출력 확인, 현재 상태 = ❌ inert 확정)·#1099 자체 행 추가. 등재 누락이 반복되는 구조라면 SessionStart 훅(check_owed_verification.py)을 '미결 경고' 뿐 아니라 '직전 세션 머지 PR 중 원장 미등재 후보 열거' 로 확장 검토.

### P1-14. [decision] 핸드오프가 양 분기 모두 오도 — "재확인 불필요" 가 다음 세션 탐색 공간을 틀린 방향으로 좁힘

- **위치**: `docs/runbooks/owed-verification.md:22`
- **verdict**: CONFIRMED
- **주장**: #1101 인수인계는 다음 세션 작업을 SQL 쿼리 1개 + 2분기 판정표로 축소했는데, 두 분기 모두 실제 상태(로깅 파괴로 스케줄러 관측 불가)로 이어지지 않는다. 분기 '0' 은 #1073·#1075 를 ✅ 종결시키고 무력한 로깅 수정을 영원히 덮는다. 분기 '8' 은 `src/scheduler.py` 기동 경로 조사를 지시하는데, 스케줄러는 정상 기동 중일 수 있고 결함은 관측성에 있다. 게다가 §"이미 확인된 것 (재확인 불필요)" 헤더가 **바로 그 틀린 행**을 재검토 대상에서 명시적으로 제외한다.
- **권고**: 핸드오프 판정표는 **각 분기가 배제하지 못하는 가설**을 함께 적는다(본 건: '스케줄러는 돌지만 로그가 안 보인다' 는 두 분기 어디에도 없음). 부재 기반(negative) 관측에는 '재확인 불필요' 표기를 금지한다. 판정표 작성 시 '이 표가 틀렸다면 어떤 관측이 그것을 드러내는가?' 1줄 의무화.

### P1-15. [decision] append-only 원장에 결론 무효화 기전 부재 — 낡은 근거가 사실로 고착

- **위치**: `docs/runbooks/owed-verification.md:5`
- **verdict**: CONFIRMED
- **주장**: 원장은 행 삭제를 금지(append-only)하고 상태를 ⏳/✅/❌/⏭️ 4종으로만 표현한다. '근거가 이후 변경으로 무효화됨' 상태가 없어서, 2026-07-18 측정치가 2026-07-19 #1100(로깅 변경) 머지 **이후**의 인수인계 문서에 여전히 유효한 사실로 전재됐다. 기계 게이트(`check_owed_verification.py`)는 안전등급 ⏳ 건수만 세므로 **틀린 결론은 카운터에 보이지 않는다** — 원장이 잘못된 확신을 담아도 무음이다.
- **권고**: 원장에 `근거 일자` 컬럼 신설 + `scripts/check_owed_verification.py` 에 검사 추가 — 행의 근거 일자가 해당 행이 지목한 서브시스템을 건드린 최신 커밋보다 오래되면 ⚠️ 경고(무효화 후보). 상태 범례에 `♻️ 근거 무효(재측정 필요)` 추가. 파서 계약(:105 상태=마지막 셀, PR=`**#NNNN**`) 변경 시 test_check_owed_verification.py 동반 갱신.

### P1-16. [decision] '실행 확인 전 수정' 패턴이 같은 세션에 2회 반복 — #1099 가 도출한 교훈의 추상화 수준이 너무 좁았다

- **위치**: `src/scheduler.py:10`
- **verdict**: CONFIRMED
- **주장**: #1095 는 cron 명령의 따옴표·`-f` 결함을 코드 정독으로 찾아 고치고 'P0 해결' 을 보고했으나, #1099 가 명령 자체가 한 번도 실행된 적 없음(`cronSchedule=null`)을 밝혀 무의미했음이 드러났다. #1099 는 이를 정직하게 자기보고했으나, 도출한 교훈을 **'저장소 밖 설정'** 으로 한정해 추상화했다. 그 결과 같은 세션의 #1100 에서 **저장소 안** 상호작용(alembic↔앱 로깅)에 동일 패턴이 재발했다 — 기전이 실제로 동작하는지 확인하지 않고 코드가 옳다는 것만으로 수정 완료를 선언.
- **권고**: 'P0 해결' 선언 전 **기전이 실행됨을 보이는 측정 1건** 의무(코드 정합성 근거만으로는 불가). #1099 교훈을 재추상화: '저장소 밖 설정' → **'실행 시점이 테스트 하네스 밖에 있는 모든 것'** — lifespan 순서, import 부수효과, 프로세스 내 서드파티 전역 재설정(logging/warnings/signal)을 포함. 이 확장을 .claude/rules/deploy.md + services.md 에 반영.

### P1-17. [decision] #1101 에 §자율 판단 보고 누락 — 사이클 최대 영향 판단을 '문서 전용' 으로 분류

- **위치**: `docs/runbooks/owed-verification.md:11`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1101 은 §🔍 사용자 검증 필요 에 "없습니다 — 이 PR 은 문서 전용" 이라 적고 §자율 판단 보고 섹션을 두지 않았다. 그러나 이 PR 이 내린 판단 — (a) 로그 부재의 외부 귀인 확정, (b) 4개 항목을 '재확인 불필요' 로 봉인, (c) 다음 세션 작업을 쿼리 1개로 축소 — 은 본 사이클에서 후속 세션 행동에 가장 큰 영향을 준 결정이다. 'docs only = 저위험' 분류가 결정 아티팩트의 레버리지를 반영하지 못했다.
- **권고**: 정책 3 에 명문화: **다음 세션의 조사 범위·우선순위를 설정하는 문서 PR** 은 코드 PR 과 동일하게 §자율 판단 보고 의무(문서 전용 예외 없음). 특히 '재확인 불필요'·'종결'·'범위 축소' 문구를 포함하는 PR 은 그 판단의 근거와 근거 일자를 자율 판단 보고에 명시.

### P1-18. [tooling] 사이클 81 CI Run #522 caplog 사고 = 본 P0 의 조기 경보였으나 '테스트 격리 문제'로 오진 → 회피 규약으로 제도화되어 탐지면이 영구 제거됨

- **위치**: `tests/integration/test_pwa_manifest.py:10`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 본 세션 P0(alembic fileConfig 가 앱 로깅 파괴)는 이미 사이클 81 에 CI 에서 발화했다. 당시 증상은 'lifespan 진입 시 후속 단위 테스트 caplog 깨짐(CI Run #522 fail 58)' 이었고, 팀은 이를 test ordering 부작용으로 진단해 '테스트에서 lifespan 진입 금지' 규약을 4+ 파일에 제도화했다. 그 회피가 운영 로깅 파괴를 감지할 수 있는 유일한 테스트 표면을 제거했고, 그래서 #1100 이 green 인 채 운영에서 무력일 수 있었다.
- **권고**: 회피를 단언으로 전환한다: `with TestClient(app):` 로 lifespan 을 실제 진입한 뒤 (a) root.level == INFO (b) _scamanager_configured 핸들러 생존 (c) logging.getLogger('src.scheduler').isEnabledFor(INFO) (d) uvicorn.access.disabled is False 를 단언하는 테스트를 추가하고, 세션 오염 차단은 fixture teardown 의 로깅 상태 복원으로 처리한다. 규칙화: '테스트가 불편해서 끄는 경로'는 반드시 근본 원인 1줄과 함께 기록하고, 다음 회고에서 재평가 대상으로 표시한다.

### P1-19. [tooling] railway.toml cron 가드가 '이미 덴 키' 1개 denylist — 스키마 allowlist 가 아니라 동일 무음실패 클래스가 그대로 재발 가능

- **위치**: `tests/unit/scripts/test_railway_cron_guard.py:35`
- **verdict**: CONFIRMED
- **주장**: #1099 사고의 본질은 'Railway 가 모르는 키를 조용히 무시한다'는 플랫폼 성질인데, 신설 가드는 그 성질이 아니라 그 성질의 인스턴스 1개(`cronJobs`)만 차단한다. 오타 키(`restartPolicyMaxRetires`)나 새로 지어낸 키(`deploy.workers`)는 완전히 동일하게 무음 무시되며 가드는 통과한다. 가드가 사고 클래스를 봉인한 것이 아니라 사고 사례를 봉인했다.
- **권고**: `[build]`/`[deploy]` 의 알려진 Railway 키 집합을 allowlist 로 두고 미지 키 발견 시 fail 하도록 전환한다(신규 키 도입 시 allowlist 갱신을 강제 = 의도적 승인 지점). 동일 원칙을 nixpacks.toml 등 플랫폼 config 전반에 적용.

### P1-20. [tooling] '저장소 밖 설정을 코드로 옮긴다'는 #1099 의 교훈이, 같은 세션 저장소 안의 config↔code 상호작용(alembic.ini↔앱 로깅)에는 미적용

- **위치**: `alembic.ini:95`
- **verdict**: CONFIRMED
- **주장**: #1099 는 스스로 교훈을 명문화했다 — '저장소 밖 설정이 조용히 어긋나던 실패 모드를 코드로 옮긴 것이 이 사고의 교훈'. 그러나 실패 클래스의 정의를 '저장소 밖'으로 좁게 잡은 탓에, 저장소 안에 있으면서 런타임에 전역 프로세스 상태를 조용히 덮어쓰는 alembic.ini 는 같은 클래스로 인식되지 않았고 같은 세션에 미탐지로 남았다. 교훈의 일반화 실패가 P0 를 통과시킨 구조적 원인이다.
- **권고**: 실패 클래스를 '저장소 밖 설정' 이 아니라 '앱 코드가 단언하지 않는 선언적 설정'으로 재정의하고, 전역 프로세스 상태를 변경하는 설정 파일(alembic.ini logging 섹션, pytest.ini, .env 로딩, warnings/locale 설정)을 인벤토리화해 각각 상호작용 단언 1개씩을 붙인다. 우선순위 1순위는 alembic.ini ↔ src/logging_config.py.

### P1-21. [process] 자기 수정의 반증 증거를 인프라 탓으로 재해석하고 '재확인 불필요' 표에 사실로 기록

- **위치**: `docs/runbooks/owed-verification.md:36`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1100 은 '배포 후 Railway 로그에 INFO 3줄이 보일 것' 이라는 예측을 PR 본문에 명시하고 12:09 머지됐다. 배포 후 그 3줄은 나타나지 않았다 — 즉 자신의 수정이 실패했다는 1급 반증이다. 그런데 41분 뒤 #1101(12:50)은 이를 앱 실패로 판정하지 않고 'Railway deploy 로그 수집 ❌ … **앱 문제 아님**' 으로 원장(docs/runbooks/owed-verification.md:36)에, 그것도 §'이미 확인된 것 (재확인 불필요)'(:29) 표에 확정 사실로 기록해 main 에 머지했다. 30분 뒤 24d90b8 이 앱 자신(alembic fileConfig)이 원인임을 양방향 실증했다. 결정적으로, 인프라 귀인의 근거로 인용된 측정 자체(원장 :106 '총 11줄 — 컨테이너 시작 + alembic 뿐')가 이미 정답의 지문을 담고 있었다 — 로그는 무작위로 끊긴 게 아니라 **정확히 alembic 직후**에 끊겼다. 로그를 '몇 줄인가'(양)로만 읽고 '어디서·무엇 다음에 끊겼는가'(경계)로 읽지 않은 것이 3세션을 잃은 단일 판독 실패다.
- **권고**: ① **예측 관측치 계약**: 운영 전용 증상의 P0 수정 PR 은 '배포 후 관측될 구체 신호'를 명시하고, 그 신호가 부재하면 **기본 판정 = 수정 실패(❌)**. 환경 귀인은 통제군을 갖춘 반증 실험을 제시할 때만 허용. ② **로그 진단 규율**: '로그가 적다/없다'로 결론 내기 금지 — 마지막 줄의 발신자와 그 직후에 실행되는 코드 경로를 반드시 기록. 본 사고에서 이 한 줄이면 즉시 해결됐다.

### P1-22. [process] 운영 전용 P0 수정(#1099·#1100)이 정작 owed 원장에 ⏳ 행으로 등재되지 않음 — 원장의 존재 목적 자체가 우회됨

- **위치**: `docs/runbooks/owed-verification.md:3`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: owed 원장은 '코드로 증명 불가한 운영 검증'을 추적하려고 신설됐다(:3). 그런데 이 사이클의 두 운영 전용 P0 수정 — #1099(인앱 스케줄러 실제 기동) · #1100/24d90b8(운영 로그 실제 출력) — 은 **원장에 자기 검증 행이 없다**. 원장의 ⏳ 6행은 전부 이전 사이클 것(#1058·#1062·#1071·#1072·#1073·#1075)이고, #1099 는 #1073/#1075 대리행에 문장으로만 언급(:22), #1100 은 산문(:94)에만 등장한다. 결과: STATE.md:20·:25 는 #1095·#1100 을 '조치' 로 기록했지만 둘 다 운영에서 무의미/무력이었고, '코드 머지 완료' 와 '운영 관측 완료' 를 구분하는 상태가 어디에도 없어 3연속 P0 시정이 모두 '해결' 로 계상됐다. 자기 자신에게 가장 필요한 순간에 자기가 만든 추적 장치를 쓰지 않은 것 — #1084 원장이 '문서-only' 였던 것과 같은 계열의 재발(4회차)이다.
- **권고**: **운영 전용 증상 P0 = owed 원장 행 자동 추가를 머지 조건화**. `scripts/check_owed_verification.py` 를 확장해 '운영 전용' 라벨이 붙은 P0 fix PR 번호가 원장 행에 없으면 경고. STATE 사고 항목 상태를 3단계(코드 머지 / 운영 관측 대기 / 확인 완료)로 분리해 '머지=해결' 계상을 구조적으로 차단.

### P1-23. [process] 핸드오프 헤드라인 '단 하나의 미완 검증' 이 같은 파일의 ⏳ 6건과 모순 — 안전등급 2건이 5세션째 억제될 구조

- **위치**: `docs/runbooks/owed-verification.md:13`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1101 이 원장 최상단에 넣은 '**단 하나의 미완 검증**이 남았고, 쿼리 1개면 끝난다'(:13)는 같은 파일의 실제 미결과 정면 충돌한다 — 안전등급 ⏳ 2건(#1058 SMTP·:44, #1062 IDOR·:45) + 운영등급 ⏳ 4건(:51~:54) = **6건**. 이 두 신호는 다음 세션에서 정확히 충돌하도록 배선돼 있다: SessionStart 훅의 `check_owed_verification.py` 는 '안전등급 미회신 2건(#1058·#1062)' 을 loud 경고로 주입하는데, 파일을 열면 최상단이 '남은 건 하나뿐' 이라고 말한다. 위치상 서사가 이긴다. #1058·#1062 는 정책 5 NEW-P0-N(매 사이클 명시 회신 의무) 영역이고 스크립트 docstring(:7)이 스스로 '4세션째 ⏳ 누적' 이라 적고 있으며, 메모리 `feedback-stale-blocker-policy` 가 4사이클 누적을 명시 금지한다. 핸드오프 문구가 이를 5세션째로 밀어낸다.
- **권고**: 핸드오프 섹션의 건수를 **⏳ 행에서 파생**시키거나 최소한 '미결 6건 중 오늘 즉시 실행 가능한 것 1건' 으로 한정 표기. 회귀 가드로 `핸드오프 헤드라인 건수 == pending_rows() 길이` 를 단언하는 테스트 추가(원장은 이미 기계 파싱되므로 비용 0에 가깝다). 다음 세션 진입 전 #1058·#1062 명시 회신 요청 의무 이행.

### P1-24. [process] 기계 카운터 2종이 SessionStart 에만 배선 — 의무 시점(사이클 종료)과 측정 시점(세션 시작)의 불일치

- **위치**: `.claude/settings.json:1`
- **verdict**: CONFIRMED
- **주장**: #1080·#1095 는 '인지 의존을 측정 신호로 전환' 하려고 회고 카덴스·owed 카운터를 기계화했으나, `.claude/settings.json` 에는 `SessionStart`(matcher `startup|resume`) 배선만 있고 `Stop`/`SessionEnd` 계열 배선이 없다. 그런데 두 의무는 모두 **종료 시점** 의무다 — 정책 8 진화 (4)는 '사이클 종료 = 회고 진입 판정', 정책 5 NEW-P0-N 은 '다음 사이클 진입 전 회신'. 실제로 2026-07-19 세션은 시작 시점에 이미 16 PR(임계 15 초과)이라 카운터가 발화한 상태에서 출발해 7 PR 을 더 머지하고 핸드오프(#1101)로 닫았으며, 종료 시점에는 어떤 신호도 재발화하지 않았다. 세션이 길어질수록(본 사이클처럼 8 PR·수 시간) 시작 시 배너는 컨텍스트 뒤편으로 밀리고 compact 시 완전 소실된다. '측정은 기계화했으나 호출 시점이 어긋난' 형태로, #1095 가 지적한 '측정은 기계화·호출은 산문' 결함의 잔여분이다.
- **권고**: 동일 두 스크립트를 `Stop`(또는 `SessionEnd`) 훅에도 배선해 **종료 시점 재발화**시킨다(advisory·exit 0 유지 — 정책 17 안정성 불변). SessionStart matcher 에 `compact` 추가 검토. 회귀 가드 `tests/unit/scripts/test_session_start_wiring.py` 를 종료 훅까지 커버하도록 확장.

### P1-25. [process] 원장의 산문·비-PR 표는 기계 가드 사각지대 — 최고 권위 문구('재확인 불필요')가 0 검증으로 통과

- **위치**: `scripts/check_owed_verification.py:32`
- **verdict**: CONFIRMED
- **주장**: `check_owed_verification.py` 의 `_ROW` 정규식은 첫 셀이 `**#NNNN**` 인 행만 파싱하고(:32-33), 상태는 마지막 셀의 ⏳ 유무로만 판정한다(:39). 따라서 §'이미 확인된 것 (재확인 불필요)' 표(:29-36)는 `| 항목 | 결과 |` 형식이라 **파서에 전혀 보이지 않는다**. 이 사이클이 실증한 대로, 가장 해로운 오류(틀린 부정 결론 '앱 문제 아님')는 정확히 이 무가드 영역에 기록됐고 '재확인 불필요' 라는 최고 권위 라벨까지 달았다. 더구나 원장 스키마에는 결론이 **측정된 것인지 추론된 것인지**, 측정 수단·일시가 무엇인지 구분하는 칼럼이 없다 — ✅ 4행(:33-36) 중 3개는 실제 프로브 결과지만 문제의 1개는 추론이었는데 표기가 동일했다.
- **권고**: 원장 표에 **근거 등급 칼럼(측정/추론) + 측정 수단·일시** 추가. '~는 문제 아님' 류 **부정 결론은 통제군을 인용할 때만** §재확인 불필요에 기재 허용, 아니면 §가설(미검증) 로 분리. 파서를 확장해 §재확인 불필요 표의 행 중 측정 수단이 비었거나 N일 경과한 항목을 경고 대상에 포함.

### P1-26. [process] 존재 확인 없이 세부 수정 — #1095 는 한 번도 실행된 적 없는 명령의 인자를 고치고 'P0 해결' 로 보고

- **위치**: `docs/runbooks/owed-verification.md:104`
- **verdict**: CONFIRMED
- **주장**: #1095 는 railway cron 5종의 따옴표·`-f` 결함을 셸 eval 실증 + 뮤테이션 검증 가드까지 붙여 수정하고 P0 종결로 보고했으나, #1099 가 밝힌 대로 `[[deploy.cronJobs]]` 자체가 Railway 스키마에 없는 키라 **명령이 애초에 실행되지 않았다** — 수정은 실재 결함이었지만 무의미했다. 핵심은 순서 규율의 부재다: '기전이 실행되는가(존재)' 를 확인하기 전에 '올바르게 실행되는가(정확성)' 로 직행했다. 판별 검사(`cronSchedule=null` 조회)는 MCP 1콜이었고, 같은 세션이 이미 Railway CLI 로 로그를 뽑고 있었다(원장 :104-109) — 도구는 손에 있었고 질문이 없었다. 오히려 강한 실증(셸 eval)과 회귀 가드를 만든 것이 확신을 키워 존재 검증 생략을 정당화했다. 같은 `railway logs` 출력 한 번이 (a) access log 부재 (b) cron 미실행 (c) alembic 직후 컷오프 세 질문에 답할 수 있었으나 (a)만 질문됐다.
- **권고**: 외부 트리거 영역(cron·스케줄러·webhook·CI) 수정 시 **turn-0 의무 = 트리거가 실제 발화한 증거 1건 제시**(마지막 실행 시각 / 부작용 흔적 / 스케줄 필드 실측). 증거 부재 시 '미실행 가설' 을 먼저 배제한 뒤 인자 수정에 착수. 또한 진단 측정 1회당 '이 출력이 답할 수 있는 질문' 을 열거하고 미질문 항목을 남기지 않는 체크(#1095 의 `railway logs` 가 3질문 중 1질문에만 쓰였다).

### P1-27. [code] 인앱 스케줄러가 cron 엔드포인트 6종 중 5종만 이관 — scan-security(GHAS 폴링)는 출시 이래 한 번도 실행된 적 없고, 문서는 실행된다고 단언한다

- **위치**: `src/scheduler.py:126`
- **verdict**: CONFIRMED
- **주장**: #1099 는 `railway.toml` 의 무효 cron 5종을 `src/scheduler.py` JOBS 5종으로 이관했다. 그러나 `POST /api/internal/cron/scan-security`(`src/api/internal_cron.py:104`, Cycle 73 F1 — GitHub Code/Secret Scanning alert 폴링 + audit log) 는 JOBS 에 없다. 구 `railway.toml` 에도 없었으므로(cronJobs 5블록 전수 확인) 이 기능은 **저장소 역사상 한 번도 주기 실행된 적이 없다** — 정책 14(Code Scanning alert 운영 체크)가 자동 폴링에 기대던 부분이 전부 수동에 의존해 왔다. 더 나쁜 건 #1099 가 이 갭을 문서에 **거짓으로 봉인**한 점: env-vars.md 가 6종을 나열한 뒤 '주기 실행은 인앱 스케줄러가 서비스 함수를 직접 호출한다' 고 단언한다(scan-security 는 거짓). 신규 가드도 이 클래스를 못 잡는다 — `test_railway_cron_guard.py:54` 는 `src/scheduler.py` 파일 존재만 단언하고, `tests/unit/test_scheduler.py:106` 은 5라는 숫자를 하드코딩할 뿐 **cron 라우터 엔드포인트 ↔ JOBS 파리티를 어디서도 단언하지 않는다**. 즉 '설정은 있는데 실행은 0' 이라는 이번 사고의 형태가 신규 엔드포인트마다 재발 가능하다.
- **권고**: (a) scan-security 를 JOBS 에 추가할지 / 엔드포인트를 폐기할지 사용자 결정(정책 15 High tier — 운영 기능 활성화). (b) 결정과 무관하게 **파리티 가드 신설**: `src.api.internal_cron.router.routes` 를 열거해 각 cron 경로가 `scheduler.JOBS` 에 대응 job 을 갖거나 명시적 예외 목록에 있음을 단언(하드코딩 5 대신 구조 단언). (c) env-vars.md:40 의 거짓 단언을 즉시 정정.

### P1-28. [code] #1091 already_merged 미러링이 외부/수동 머지를 SCAManager 자동머지 성공으로 계상 — PR 자신의 목적(GC 후 결과 보존)이 그 경로에서만 무효

- **위치**: `src/services/merge_retry_service.py:220`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1091 은 종결 4경로를 MergeAttempt 에 미러링해 `merge_retry_queue` 7일 GC(#1075) 후에도 결과 이력을 보존하려 했다. 그런데 `already_merged` 경로는 `success=True, reason=None` 으로 기록되고, `log_merge_attempt` 는 **success=True 일 때 reason 을 아예 버린다**(`failure_reason`/`detail_message` 는 `if not success` 분기에서만 채워짐). 결과: MergeAttempt 행만 보면 '우리가 자동머지에 성공한 건' 과 '이미 남이 머지해 놓은 걸 확인한 건' 이 완전히 동일하다. 구분 정보(`mark_succeeded(reason=ALREADY_MERGED)`)는 큐 행에만 있고 그 큐 행은 7일 뒤 GC 대상 — 즉 PR 의 명시 목표('GC 후 최종 결과 이력 보존')가 하필 이 경로에서만 달성되지 않는다. 운영 영향: 대시보드 머지 성공률이 부풀려진다. `_simple_success` 는 raw attempt 를 세고(`dashboard_service.py:376`), `_retry_aware_success` 도 distinct PR 의 success 집합에 넣는다(`:397`). CI 대기로 큐에 들어간 뒤 사람이 손으로 머지한 PR 이 전부 '자동머지 성공' 으로 집계된다. 모델에는 이 구분을 담을 `state` 컬럼(`src/gate/_merge_attempt_states.py` — LEGACY/ENABLED_PENDING_MERGE/ACTUALLY_MERGED/DISABLED_EXTERNALLY)이 이미 있는데 미러링은 기본값 LEGACY 를 그대로 뒀다.
- **권고**: already_merged 미러링에 `state=` 로 구분 상태를 부여(기존 상수 재사용 또는 신규 `externally_merged` 추가 — 스키마 변경 시 정책 15 High tier 사전 확인)하고, 대시보드 성공률 집계에서 해당 state 를 제외할지 사용자 결정. 최소한 회귀 가드에 'already_merged 미러링 행이 자동머지 성공과 구분 가능하다' 는 단언을 추가한다(현 가드는 success/reason 만 단언해 이 결함을 통과시킨다).

### P1-29. [docs] STATE.md(선언된 SSOT)가 #1100 을 '완료된 수정'으로 계속 단언 — 정정이 owed 원장에만 착지

- **위치**: `docs/STATE.md:25`
- **verdict**: CONFIRMED
- **주장**: 본 세션이 #1100 의 운영 무력(inert)을 확정하고 owed 원장에는 정정을 기록했으나, 프로젝트가 스스로 '단일 진실 소스'로 선언한 docs/STATE.md 는 갱신되지 않았다. 두 SSOT 급 문서가 '앱 로깅이 고쳐졌는가'에 대해 정반대를 말한다.
- **권고**: 24d90b8 브랜치에 docs/STATE.md:25 정정을 fix-up 으로 추가 — 해당 불릿에 "⚠️ 이 수정은 alembic fileConfig 가 즉시 되돌려 운영 무력이었음(2026-07-19 반증) → 실효 수정은 alembic/env.py `is_configured()` 가드" 1줄 삽입. 원칙화: **운영 사실이 반증되면 owed 원장과 STATE.md 를 같은 커밋에서 동시 정정**(단일 정정 착지점 금지).

### P1-30. [docs] 기계화된 docs 의무는 100% 준수, 문서-only docs 의무는 100% drift — 세션 자체 P0 테마가 docs 도메인에서 그대로 재현

- **위치**: `scripts/check_docs_sync.py:10`
- **verdict**: CONFIRMED
- **주장**: 본 창의 docs 정합 결과는 '가드 유무'로 완전히 갈렸다. CI 가드가 있는 doc 의무는 전부 지켜졌고, 가드 없는 doc 의무는 전부 깨졌다. 즉 '문서-only 시정은 행동을 못 바꾼다'(회고 P0, 3회차)가 docs 도메인 자신에게서 4회차로 재현됐다.
- **권고**: docs 의무를 '가드 있음/없음'으로 전수 분류하고, 무가드 항목 중 회귀 전례가 있는 3종을 turn-0 기계화: (1) `check_architecture_tree_sync.py` — `src/**/*.py` 파일 집합 ↔ architecture.md 트리 등재 집합 양방향(신규 파일 누락 + 삭제 파일 잔존 동시 차단, `# arch-exempt:` allowlist). (2) STATE 날짜/PR-범위 단언(위 finding). (3) .env.example ↔ config.py `*_disabled` 계열 동기화. 🔴 이번 회고에서 '가드 추가' 자체가 또 문서-only 가 되지 않도록, 각 가드는 **뮤테이션 실증**(가드 제거 시 FAIL 확인) 결과를 PR 본문에 기재.

### P1-31. [docs] src/logging_config.py 가 docs/architecture.md src/ 트리 미등재 — 같은 세션 scheduler.py 는 등재된 비대칭(🔴 전례 4회차)

- **위치**: `docs/architecture.md:34`
- **verdict**: CONFIRMED
- **주장**: #1100 이 추가한 신규 src 파일이 architecture.md 트리에 없다. 같은 세션 #1099 의 src/scheduler.py 는 정상 등재됐으므로 '절차 미인지'가 아니라 '건별 누락'이며, CLAUDE.md 가 🔴 로 표시하고 전례 3건을 명시한 의무의 4회차 위반이다.
- **권고**: architecture.md 트리 database.py↔scheduler.py 인근에 `├── logging_config.py  # 앱 로깅 설정(stdout 핸들러·INFO·멱등) — main.py import 시점 배선. 🔴 alembic fileConfig 가 이를 파괴하던 사고(2026-07-19) 가드 = tests/unit/migrations/test_alembic_env_logging_guard.py` 1줄 추가(24d90b8 브랜치 fix-up 권장 — 같은 P0 응집 단위). 근본 대응은 위 '가드 없는 docs 의무 기계화' finding 의 check_architecture_tree_sync.

### P1-32. [decision] 본 세션 최우선 미검증 3건이 owed 원장의 집행 카운터에 한 건도 등재되지 않음 — 같은 날 배선한 가드가 자기 세션 산출물에 눈이 멀었다

- **위치**: `docs/runbooks/owed-verification.md:5`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1099(인앱 스케줄러 실동작)·#1100(운영 로그 복구)·24d90b8(alembic fileConfig 봉인)은 모두 '코드로 증명 불가한 운영 검증'의 정의에 정확히 부합하는데, owed 원장의 파싱 대상 표에 **단 한 행도 추가되지 않았다**. 세 건은 산문 섹션에만 존재한다. 결과적으로 SessionStart 훅이 다음 세션에 출력할 경고는 프로젝트 최우선 미결(cron P0)을 **이름조차 부르지 않는다**.
- **권고**: (1) #1099·#1100·alembic fix 를 안전/운영등급 표에 정식 행으로 추가(#1099 = 안전등급 — 5종 스케줄 작업 전면 미실행 = NEW-P0-N). (2) 가드 강화: 직전 N개 머지 커밋 중 `fix(cron|observability)` 등 운영-검증형 PR 번호가 원장 표에 존재하는지 대조하는 완결성 테스트 추가 — 현재 가드는 파서 건강성만 검사한다. (3) 원장 규칙 :5 에 '산문 서술은 행을 대체하지 못한다(파서 비가시)' 1줄 명시.

### P1-33. [decision] 반증된 전제('cron 은 로그로 판별 불가')가 정정 후에도 같은 파일 4곳에 사실로 존치 — 오귀인을 다음 세션에 재주입하는 경로가 그대로 남았다

- **위치**: `docs/runbooks/owed-verification.md:100`
- **verdict**: CONFIRMED
- **주장**: alembic fileConfig 발견으로 '로그 관측 불가' 진단의 근거가 무너졌고 :36 과 :79-98 에서 정정됐다. 그러나 **같은 결론을 실측 사실로 단언하는 다른 4개 지점은 손대지 않았다**. 다음 세션이 :100 섹션 제목('실행 불가 (2026-07-18 실측)')을 먼저 읽으면 로깅 복구로 되살아난 가장 빠른 검증 경로(로그 1줄 확인)를 다시 포기하고 DB 관측만 시도한다 — 이번 사고를 3세션 끌었던 바로 그 결정을 재생산한다.
- **권고**: 정책 16 진화(공유 로직 grep 전수)를 문서에도 적용: 진단·전제를 정정할 때 `grep -n <전제 문구>` 로 동일 파일·타 문서 전수 확인 후 일괄 갱신하고 '전수 확인 N곳' 1줄 명시. 즉시 조치로 :53·:54·:100·:111 에 '로깅 복구(alembic fix) 이후 로그 관측이 되살아났다 — 아래 §오귀인 정정 참조' 를 병기.

### P1-34. [decision] '재확인 불필요' 목록이 직접 실측과 추론을 동일 등급으로 취급 — 오귀인이 통과한 구조적 통로가 아직 열려 있다

- **위치**: `docs/runbooks/owed-verification.md:29`
- **verdict**: CONFIRMED
- **주장**: 인수인계 문서는 4개 항목을 '재확인 불필요' 로 확정했다. 그중 3건은 직접 프로브 결과(401/200, /health 5/5, env 존재)이고 1건은 **반증 실험 없는 추론**이었다. 두 등급이 동일한 표·동일한 시각적 무게로 제시됐고, 표 헤더의 '재확인 불필요' 가 추론에도 그대로 적용됐다. 잘못된 것은 정확히 그 추론 1건이었다. :36 정정은 **인스턴스만 고쳤고 기전은 그대로** — 표는 여전히 `| 항목 | 결과 |` 2컬럼이라 다음 추론도 같은 경로로 '확정 사실' 이 된다.
- **권고**: '이미 확인된 것' 표에 **근거등급 컬럼(직접실측 / 추론)** + **재현 명령/쿼리 컬럼** 을 추가하고, '재확인 불필요' 지위는 재현 명령이 적힌 직접실측에만 부여한다. 추론은 별도 '가설(미검증)' 섹션으로 분리 — 시각적 동급 배치가 오귀인 승격의 실제 통로였다.

### P1-35. [decision] 한 세션에 '해결' 선언 2회 연속 무력화(#1095·#1100) — 종결 판정 기준이 '머지' 이고 운영 재측정 게이트가 없다

- **위치**: `docs/runbooks/owed-verification.md:98`
- **verdict**: CONFIRMED
- **주장**: 동일 사고(cron 무실행/관측 불가)에 대해 이 세션은 두 번 종결을 선언했고 두 번 다 운영에서 무력이었다. #1095 는 실재 결함을 고쳤으나 명령 자체가 실행되지 않아 무의미했고, #1100 은 마이그레이션이 즉시 되돌려 inert 였다. 공통 결정 결함은 진단 실력이 아니라 **종결 판정 기준**이다 — 두 건 모두 '머지 + 단위 테스트 green' 시점에 해결로 보고되고, 운영 재측정은 사용자 체크리스트로 위임됐다. 그리고 이번에 얻은 교훈은 runbook 산문 1줄로만 남아, 같은 세션이 P0 로 규정한 '문서-only 시정' 안티패턴의 4회차가 된다.
- **권고**: 종결 어휘를 상태로 분리해 강제한다 — 운영에서만 관측 가능한 증상의 fix 는 커밋/PR 에서 '해결/봉인' 을 쓰지 못하게 하고 **'코드 종결 · 운영 미검증'** 상태로만 표기 + owed 원장 행 생성을 의무화(위 P0 항목과 페어). 이 규칙은 runbook 이 아니라 CLAUDE.md 필수 원칙 또는 커밋 메시지 검사 훅에 둔다 — 산문 권고는 이 세션이 이미 3회 실패시킨 형식이다.

### P1-36. [decision] 사용자 위임 검증 항목의 재triage 부재 — 검증 수단이 바뀌었는데 위임 경계는 한 번 정해진 뒤 재검토되지 않는다

- **위치**: `docs/runbooks/owed-verification.md:44`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 원장 행은 최초 등재 시점의 '사용자 의무' 분류를 그대로 유지하며, (a) 노후화 에스컬레이션 규칙과 (b) 검증 환경 변화에 따른 재분류 절차가 둘 다 없다. 카운터는 advisory(항상 exit 0)라 누적을 막지 못한다. 실제로 #1073·#1075 의 검증 수단은 로깅 복구로 방금 바뀌었는데(로그 관측 부활) 행 본문은 여전히 'DB 관측 대체' 로 고정돼 있고, #1058·#1062 는 4세션째 동일 문구로 대기 중이다.
- **권고**: 원장 표에 **등재 세션 / 경과 세션** 컬럼을 추가하고, 안전등급 ⏳ 가 3세션 초과 시 Claude 가 (1) Claude 실행 가능한 대체 프로브 제안(예: #1062 는 통합 테스트로 상당 부분 대체 가능) 또는 (2) 행 폐기 권고 중 하나를 **반드시 제시**하도록 규칙화. 아울러 관측 환경이 바뀐 PR 머지 시 영향받는 원장 행의 '검증 방법' 셀 재검토를 6-step ⑤ 하위 체크로 편입.

### P1-37. [tooling] 사이클 81 '테스트 위생' 우회가 본 P0 를 ~40 사이클 은폐 — 운영 신호를 테스트 잡음으로 오분류

- **위치**: `tests/integration/test_pwa_manifest.py:9`
- **verdict**: CONFIRMED
- **주장**: `with TestClient(app)` 로 lifespan 진입 시 **후속 테스트의 caplog 가 깨지는** 현상(CI Run #522, 58 fail)이 사이클 81 에 관측됐고, 조치는 '모든 테스트에서 lifespan 진입 금지' 였다. 그런데 그 증상은 `disable_existing_loggers=True` 가 기존 로거를 전부 죽이는 **이번 P0 의 정확한 관측 서명**이다. 즉 프로젝트는 운영 결함을 이미 한 번 목격했고, 유일한 관측 경로를 제거하는 방식으로 봉인했다 — 그 결과 출시 이래 앱 INFO 로그 0건이 2026-07-19 까지 미발견.
- **권고**: 정책화 — **‘실제 기동 경로를 태우면 다른 테스트가 깨진다’ 는 테스트 위생 문제가 아니라 전역 상태 오염의 운영 신호로 1차 triage 의무**(우회 코멘트 작성 전 근본 원인 1줄 규명). 회귀 가드: 우회 주석 3곳에 “원인=alembic fileConfig(#24d90b8 봉인)” 를 기재하고, 격리 fixture 가 생겼으므로 최소 1개 파일은 lifespan 진입으로 복원해 관측 경로를 되살릴 것.

### P1-38. [tooling] PostToolUse·PreToolUse 훅에 settings.json 배선 가드 부재 — SessionStart 만 기계 단언(#1084 '미배선' P0 와 동형)

- **위치**: `tests/unit/hooks/test_posttool_pytest_smoke.py:55`
- **verdict**: CONFIRMED
- **주장**: #1080/#1084 회고가 '문서-only·미배선' 을 P0 로 규정하고 `test_session_start_wiring.py` 로 SessionStart 2종의 **실행 기전**을 단언했다. 그러나 같은 클래스의 나머지 훅 — 특히 false-green 사고 후 재작성된 `posttool_pytest_smoke.py`(#1082) — 은 settings.json 배선을 단언하는 테스트가 없다. 누군가 PostToolUse 엔트리를 지워도 전 스위트 green 이고 훅은 조용히 inert 가 된다. '필수 원칙 — Hook 신뢰' 의 토대가 다시 인지 의존으로 회귀한다.
- **권고**: test_session_start_wiring.py 의 추출기를 훅 종류 파라미터화(`SessionStart|PreToolUse|PostToolUse`)해 3종 전부에 '등록된 command 문자열에 스크립트 경로 존재 + matcher 커버리지 + 파일 실재' 를 단언. 부정 통제(엔트리 제거 시 FAIL) 뮤테이션 실증 동반 — 본 사이클이 확립한 '가드의 가드' 기준 적용.

### P1-39. [tooling] railway.toml 가드가 인스턴스 한정(`cronJobs` 키 1개) — 무효 키 무음 무시라는 결함 '클래스' 는 그대로 열려 있음

- **위치**: `tests/unit/scripts/test_railway_cron_guard.py:56`
- **verdict**: CONFIRMED
- **주장**: 이번 P0 의 본질은 '`cronJobs` 라는 특정 키가 나빴다' 가 아니라 **Railway 가 모르는 키를 조용히 무시하고, 우리 쪽에 스키마 검증이 없어 설정 존재 = 동작 이라는 착각이 성립한다** 는 것이다. 신규 가드는 `cronJobs` 재도입만 차단한다 — 다음에 `preDeployCmd`·`healthcheckTimeoutSeconds`·`restartPolicyMaxRetry` 같은 오타/발명 키를 넣으면 **동일 사고가 다른 이름으로 재발**하고 가드는 침묵한다. #1099 커밋 본문이 스스로 '저장소 밖 설정이 조용히 어긋나던 실패 모드' 를 교훈으로 적었는데, 그 교훈이 인스턴스 수준에서만 코드화됐다.
- **권고**: 가드를 화이트리스트로 전환 — `set(config["deploy"]) <= KNOWN_DEPLOY_KEYS` / `set(config["build"]) <= KNOWN_BUILD_KEYS` 단언(미지 키 발견 시 실패 메시지에 'Railway 스키마 확인 후 화이트리스트 등재' 안내). 20줄·의존성 0. 동일 패턴을 nixpacks.toml 에도 적용 검토.

### P1-40. [tooling] cron 실동작 증거가 '1회용·소멸성 자연실험' 뿐 — 소진 후 스케줄러 생존을 확인할 재생 가능한 신호가 없음

- **위치**: `src/scheduler.py:166`
- **verdict**: CONFIRMED
- **주장**: 출시 이래 cron 5종이 전부 죽어 있었는데 **어떤 도구도 이를 감지하지 못했고**, 3세션 조사 끝에 남은 유일한 검증 수단이 '만료 캐시 8건이 20:00 UTC 후 0 이 되는지' 라는 소모성 관측이다. 원장 스스로 “이 8건을 다른 방법으로 지우지 말 것 — 지우면 검증 신호가 **영구 소실**된다” 고 경고한다. 즉 이번 1회 검증에 성공하든 실패하든 **다음 회차 검증 수단은 남지 않는다**. #1099 가 '저장소 밖 설정 → 코드' 로 옮겨 배선을 테스트 가능하게 만든 것은 옳지만, 배선 존재(테스트)와 **런타임 생존**(운영)은 별개이며 후자에 대한 관측면이 여전히 0 이다(`/health` 는 `{"status":"ok"}` 만 반환).
- **권고**: 스케줄러 heartbeat 을 DB 로 승격 — job 별 `last_run_at`·`last_status` 1행 upsert(신규 테이블 또는 기존 메타 테이블). 그러면 (a) MCP SELECT 만으로(정책 12 자율 허용) 매 세션 즉시 생존 확인 (b) 소모성 아님 = 재생 가능 (c) '마지막 실행 > 2×주기' 를 향후 자동 경보로 승격 가능. 로그 의존 검증을 DB 의존 검증으로 대체하는 것이 이번 사고의 진짜 일반화된 교훈이다.

### P1-41. [process] owed 원장이 자기 목적 1순위 항목(#1099 스케줄러 실동작·#1100 로깅 도달)을 등재하지 않아, 사이클 최중요 검증이 집행 훅에 비가시

- **위치**: `docs/runbooks/owed-verification.md:3`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1095 가 원장을 SessionStart 훅에 배선해 '문서-only 시정 3회차' 를 봉인했으나, 같은 세션의 후속 PR #1099·#1100 이 원장에 행을 추가하지 않았다. 결과적으로 사이클 전체에서 가장 중요한 미결 운영 검증(인앱 스케줄러가 운영에서 실제로 도는가)이 기계 게이트에 등록되지 않았다. 봉인은 '집행 계층' 에서 이뤄졌으나 '작성 계층' 에서 같은 write-only 실패가 24시간 내 재발했다.
- **권고**: 원장 append 를 PR 단위 의무로 승격 — 6-step 에 '⑦ 코드-미증명 운영 검증을 남긴 PR 은 머지 전 원장 행 추가' 를 넣고, `scripts/check_owed_verification.py` 에 역방향 검사를 추가한다: 최근 N PR 중 `src/scheduler.py`·`cron_service`·`logging_config`·외부 계약 경로를 건드렸는데 대응 행이 없으면 loud 경고. 산문 서술은 행의 보조일 뿐 대체 불가임을 원장 §작성 규칙(line 5)에 명문화.

### P1-42. [process] 세션 종료 PR #1101 의 §'🔍 사용자 검증 필요' = '없습니다' 가 같은 파일의 안전등급 ⏳ 2건·전체 ⏳ 6건과 정면 모순 (정책 2 + 정책 5 NEW-P0-N)

- **위치**: `docs/runbooks/owed-verification.md:13`
- **verdict**: CONFIRMED
- **주장**: 사이클을 닫는 인수인계 PR 이 사용자 검증 요청을 '없습니다' 로 비우고 서사를 '단 하나의 미완 검증' 으로 좁혔다. 그러나 그 PR 이 편집한 바로 그 파일에 ⏳ 6건이 있고 그중 2건은 정책 5 NEW-P0-N(매 사이클 명시 회신 의무) 안전등급이다. 다음 세션은 '거의 끝났다' 는 잘못된 프레임을 상속받고, 안전등급 2건은 또 한 사이클 누적된다 — 메모리 `feedback-stale-blocker-policy.md`(4사이클 누적 금지)가 경고한 바로 그 패턴의 재생산.
- **권고**: 세션 종료 PR 의 §'🔍 사용자 검증 필요' 를 **기계 출력으로 생성**한다 — `check_owed_verification.py` 의 stdout 을 그대로 붙여넣고 '없습니다' 는 카운터가 0 일 때만 허용. 'N 건 중 하나만 즉시 실행 가능' 같은 우선순위 서술은 허용하되, 잔여 건수 은닉은 금지(정책 2 진화).

### P1-43. [process] 회고 카덴스 카운터가 SessionStart 전용 샘플링이라 '장세션 중 임계 돌파' 를 구조적으로 놓친다 — 봉인 대상 실패 모드와 감지 창이 어긋남

- **위치**: `.claude/settings.json:3`
- **verdict**: CONFIRMED
- **주장**: #1080 이 신설한 카덴스 카운터는 `SessionStart`(matcher `startup|resume`) 에만 배선돼 세션 **시작 시 1회** 만 측정한다. 그런데 이 카운터가 봉인하려던 P0(~46 PR 무회고)은 한 세션 안에서 다수 PR 이 누적되며 발생한다. 본 사이클이 그대로 재현했다 — 임계 ≥15 는 #1094 부근에서 세션 **도중** 돌파됐고, 세션은 그 뒤 8 PR(#1094~#1101)을 더 머지한 뒤 회고 없이 종료했으며, 카운터는 한 번도 발화하지 못했다(배선 자체가 #1095 로 세션 중간에 들어와 그 세션 시작 시점에는 존재하지도 않았다).
- **권고**: Stop 또는 SessionEnd 훅에 동일 카운터를 추가하거나(비차단 유지), 6-step ⑤ trailing sync 단계가 `check_retro_cadence.py` 를 호출하도록 배선한다. 최소한 세션 종료 인수인계 PR 본문에 카운터 실측 1줄을 의무화 — '가드의 가드' 주제를 카운터 자신에게도 적용.

### P1-44. [code] 확정 P0 의 영향 범위가 과소 서술됨 — INFO 뿐 아니라 src.* 의 ERROR/CRITICAL/exception 도 출시 이래 전부 소실

- **위치**: `alembic/env.py:34`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 세션 확정 P0 는 영향을 '앱 INFO 로그 소실 + uvicorn.access 비활성' 으로 서술하지만, 실제 기전은 레벨 문제가 아니라 로거 자체의 disabled 화다. fileConfig 의 disable_existing_loggers=True 는 기존 src.* 로거에 disabled=True 를 세팅하고, disabled 로거는 레벨·핸들러 검사 이전에 레코드를 폐기한다. 따라서 마이그레이션 이후 src.* 가 내보낸 WARNING/ERROR/CRITICAL/exception 도 전부 소실됐다. 이 '레벨-형' 오진단이 #1100 이 운영에서 무력했던 직접 원인이다 — #1100 은 root 레벨(INFO)과 stdout 핸들러를 고쳤을 뿐이고, disabled=True 는 그 둘을 모두 우회한다.
- **권고**: (1) 사고 서술을 '레벨 강등' 이 아니라 '로거 disabled' 로 정정 — STATE.md·owed 원장·#1100/#1101 커밋 서사에 반영. 표현이 레벨-형으로 남으면 다음 세션이 또 레벨만 고친다. (2) 회귀 가드에 `logging.getLogger('src.<mod>').disabled is False` 와 ERROR 발화 캡처를 명시 단언으로 추가 — 현행 `isEnabledFor(INFO)` 는 결과적으로 disabled 를 함의하지만 의도가 레벨로 읽혀 다음 편집자가 약화시키기 쉽다. (3) except 블록 124곳의 fail-safe 설계 전체가 '로그로 남으니 삼켜도 안전' 전제 위에 있으므로, 로깅 복구 후 운영 WARNING/ERROR 실제 발화량을 1회 실측해 그동안 은폐된 만성 실패가 있는지 확인.

### P1-45. [code] 인앱 스케줄러의 lifespan 배선을 단언하는 테스트가 없음 — 사고와 동일한 '설정 존재·실행 0' 이 전 스위트 green 으로 재현 (뮤테이션 실증)

- **위치**: `tests/unit/scripts/test_railway_cron_guard.py:56`
- **verdict**: CONFIRMED
- **주장**: #1099 는 '저장소 밖 설정이 조용히 어긋나던 실패 모드를 코드로 옮기고 배선을 테스트가 단언한다' 를 근거로 인앱 스케줄러를 채택했으나, 실제로 단언되는 것은 모듈 내부 구조(JOBS 5종·주기 값·job 호출 가능성)뿐이고 src/main.py lifespan 이 scheduler.start() 를 실제로 호출하는지는 어떤 테스트도 검증하지 않는다. 즉 스케줄러가 lifespan 에서 떨어져 나가면 사고와 완전히 동일한 형태(등록은 되어 있고 실행은 0)가 되지만 CI 는 전부 통과한다. 2026-07-17 메모리의 '배선이 진짜 작업 — 미배선 dead code 인데 전 스위트 green' 교훈이 이틀 만에 같은 형태로 재발했다.
- **권고**: tests/unit/test_main.py 에 lifespan 배선 단언 추가 — `monkeypatch.setattr('src.main.scheduler.start', spy)` 후 lifespan 진입 시 spy 호출 + 반환 태스크가 종료 시 scheduler.stop 에 전달되는지 단언(정지 누수까지 페어). 아울러 test_railway_cron_guard.py:54 의 is_file() 단언은 '대체 기전 실재' 를 증명하지 못하므로 main.py 가 scheduler.start 를 호출한다는 AST/소스 단언으로 승격. 이번 뮤테이션 결과(74건 green)를 가드 docstring 에 실측 근거로 기록.

### P1-46. [docs] owed 원장 정정이 '추가'만 되고 전파 안 됨 — 상단 인수인계 지시가 하단 정정과 정면 모순

- **위치**: `docs/runbooks/owed-verification.md:13`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: alembic 정정(§79~98)이 파일 **하단에 append** 되면서, 다음 세션이 가장 먼저 읽는 상단 §"다음 세션 이어받기 — 즉시 실행"(11~27) 과 검증 행 53·54, §검증 수단 정정(100~113)은 **여전히 '로그 관측 불가 → DB 관측 유일'** 을 지시한다. 같은 파일이 서로 반대되는 두 절차를 동시에 담고 있고, 스테일 지시가 정정보다 ~70줄 먼저 나온다.
- **권고**: 정정 시 **동일 주장을 담은 전 지점을 grep 으로 열거 후 일괄 갱신**(정책 16 진화 '공유 로직 grep 전수' 의 문서판). 최소 조치: (a) 상단 §11~27 에 '로그 경로 복구됨 — 배포 후 `scheduler started — 5 jobs` 확인이 1차, DB 쿼리가 2차' 명시, (b) 행 53·54 검증 방법을 로그+DB 병기로 갱신, (c) §100~113 헤더에 `(2026-07-19 부분 반증 — 앱 로그 부분은 §오귀인 정정 참조)` 표기. append-only 규칙은 **행 삭제 금지**이지 **스테일 지시 유지 의무가 아니다**.

### P1-47. [docs] 186 에이전트·147 confirmed 회고가 아카이브 보고서 0건 — STATE 한 줄로만 존재, 백로그 소실

- **위치**: `docs/STATE.md:19`
- **verdict**: CONFIRMED
- **주장**: 2026-07-19 범위 한정 5+1 회고(186 에이전트·확정 147건 = P0 2·P1 55·P2 90)가 **보고서 파일을 남기지 않았다**. #1095~#1098 로 조치된 소수를 뺀 나머지 ~140건(P1 55 포함)은 재조회 불가. 2026-05-06 이후 모든 회고가 아카이브된 전례와 단절되며, 직전 #1078 은 61 confirmed 를 아카이브했다.
- **권고**: (a) 147 confirmed 를 `docs/_archive/reports/2026-07-19-scoped-retrospective.md` 로 아카이브 + INDEX.md 등재(미조치 P1 55건이 백로그로 남게), (b) **'정식 회고'(아카이브+카덴스 리셋) vs '범위 한정 회고'(비아카이브+비리셋) 판정 기준을 정책 8 본문에 1줄 명문화** — `check_retro_cadence.py:30~32` 주석이 이미 '리뷰를 회고로 오인 시 잘못 리셋' 을 P0 근본으로 경고하고 있으므로 그 역방향 모호성도 같은 등급.

### P1-48. [docs] architecture.md 신규 파일 등재 6건 누락 — 의무는 문서-only, 검증 가드 0

- **위치**: `docs/architecture.md:34`
- **verdict**: CONFIRMED
- **주장**: 본 사이클 신규 파일 6개가 architecture.md 트리에 없다: `src/logging_config.py`(#1100) 및 신규 가드 스크립트 5종. 같은 세션의 `src/scheduler.py`(#1099)는 등재됐으므로 규칙 인지 문제가 아니라 **PR 별 준수 편차**이며, architecture.md 를 참조하는 자동 가드는 저장소 전체에 하나도 없다.
- **권고**: 회고 P0 주제('문서-only 시정은 행동을 못 바꾼다' 3회차)의 docs 도메인 적용 사례. `scripts/check_architecture_tree.py` 신설 — `src/*.py` 와 최상위 `scripts/check_*.py` 가 architecture.md 코드블록에 문자열로 존재하는지 stdlib 단언, pre-commit + CI 배선. 기존 `check_docs_sync.py` 와 동형이라 구현 비용 낮고 누락 방향을 원리적으로 탐지 가능(자기참조 아님).

### P1-49. [decision] 오귀인은 정정했으나 그 오귀인 위에 세운 하위 결정은 재도출하지 않음 — 원장이 여전히 폐기된 전제로 다음 세션을 구속

- **위치**: `docs/runbooks/owed-verification.md:55`
- **verdict**: CONFIRMED
- **주장**: #1102(24d90b8)는 '로그 소실 = Railway 문제'라는 오귀인을 반증하고 line 36 을 정정했으나, **그 오귀인으로부터 파생된 검증 전략은 그대로 남겼다**. #1073·#1075 행은 지금도 '🔴 로그 관측 불가 → DB 관측 대체'라고 지시하고(현재 line 55·56), 핸드오프는 20:00 UTC 를 기다리는 DB 경로에 다음 세션을 묶으면서 '🔴 이 8건을 다른 방법으로 지우지 말 것 — 지우면 검증 신호가 영구 소실된다'(line 27)는 제약까지 부과한다. 그러나 로깅이 복구된 지금 src/scheduler.py:166 이 기동 시 'scheduler started — 5 jobs' 를, :97 이 **60초마다** 'scheduler retry_pending_merges: counts=...' 를 INFO 로 남기므로, 실동작 확정은 배포 후 약 1분의 로그 관측으로 끝난다. 즉 다음 세션은 1분이면 얻을 판정을 위해 최대 24시간을 대기하고, 대체 불가능한 DB 신호 8행을 보존해야 하는 제약을 지게 된다. 정정 PR 자신의 근거(#1100 본문 §사용자 검증 필요 1~3번이 정확히 이 로그 라인들을 검증 절차로 명시)와도 어긋난다. 결정 결함의 성격: 근본 사실을 뒤집으면서 그 사실에 의존하던 결론 집합을 역추적하지 않았다.
- **권고**: #1073·#1075 행의 검증 방법을 '로그 우선(배포 후 60초 내 scheduler 라인 관측) → DB 대조(보조)' 로 재작성하고, line 27 의 8행 보존 제약을 '로그로 확정되면 해제' 로 완화한다. 프로세스로는 오귀인 정정 PR 의 체크리스트에 '이 사실에 의존해 내린 하위 결정 열거 + 각각 재도출' 단계를 의무화(정책 16 §공유 로직 grep 전수의 사실-의존 버전 — 정정된 명제를 grep 해 파생 결론을 전수 확인).

### P1-50. [decision] '저장소 밖 설정은 조용히 어긋난다'며 채택한 인앱 스케줄러의 안전 전제 자체가 핀되지 않은 저장소 밖 설정(replica 수)

- **위치**: `src/scheduler.py:18`
- **verdict**: CONFIRMED
- **주장**: #1099 의 채택 논거는 '대시보드·외부 cron 은 저장소 밖 설정이라 이번처럼 어긋나도 테스트가 못 잡는다'(PR 본문 §왜 인앱인가, src/scheduler.py:11-13 동일 취지)였다. 그런데 채택된 인앱 스케줄러의 정확성은 '현재 단일 인스턴스 운영'이라는 전제에 의존하며(src/scheduler.py:18-20: 다중 인스턴스 시 weekly 리포트 **중복 발송 가능**), 그 replica 수는 railway.toml 에 전혀 핀돼 있지 않고 Railway 대시보드에만 존재한다 — 즉 **동일한 클래스의 저장소 밖 설정**이다. 검증: railway.toml·nixpacks.toml 에 numReplicas/replica 키 0건, tests/ 전체에 'replica' 참조 0건. 따라서 운영자가 수평 확장을 누르는 순간 weekly 리포트가 중복 발송되지만 어떤 테스트·가드·경고도 이를 표면화하지 못한다. 이 저장소는 이미 동일 문제에 대한 규율을 보유하고 있다 — railway.toml 의 preDeployCommand 주석은 '🔴 Railway 대시보드 Settings→Deploy→Pre-deploy Command 는 빈 값 권장(railway.toml 단일 출처)'로 대시보드 값을 코드로 끌어오는 패턴을 명시한다(2026-06-15 사고 학습). 그 규율이 이번 결정에는 적용되지 않았다.
- **권고**: railway.toml [deploy] 에 numReplicas = 1 을 명시 핀하고, tests/unit/scripts/test_railway_cron_guard.py(이미 railway.toml 을 tomllib 로 파싱 중)에 'numReplicas 가 1 이 아니면 FAIL — 스케줄러 중복 실행 전제 붕괴' 단언을 추가한다. 이렇게 하면 수평 확장 시도가 CI 에서 advisory lock 도입 의무를 강제로 표면화한다. 더불어 '한계(의도적 수용)'로 기록된 조건부 미래 의무는 PR 본문·docstring 산문이 아니라 **발화 조건을 감지하는 가드**로 배선하는 것을 default 로 정책화한다(정책 4 — 단언과 회귀 가드를 같은 PR 에).

### P1-51. [decision] 미실행 탐지 불가라는 P0 의 본질을 대체 기전이 그대로 승계 — job 실행 증거가 영속 기록 없이 로그 전용

- **위치**: `src/scheduler.py:93`
- **verdict**: CONFIRMED
- **주장**: 원 P0 의 본질은 'cron 이 안 돈다'가 아니라 **'12주간 안 도는데 아무도 몰랐다'**(2026-04-27 8af36be 도입 → 2026-07-19 발각)는 탐지 불능이다. 그런데 대체 기전은 실행 증거를 오직 로그로만 남긴다 — src/scheduler.py 의 5개 job 본문(:97·:103·:109·:115·:121)은 전부 logger.info 만 호출하고, src/ 및 alembic/versions/ 전체에 last_run/job_run/heartbeat/scheduler_state 참조가 0건이다. 즉 job 이 다시 조용히 멈춰도 질의 가능한 상태가 남지 않는다. 이 설계는 특히 취약한데, (a) 로그 채널은 제품 출시 이래 전 기간 죽어 있었고(#1102), (b) 원장 자신이 '로그 관측 불가 → DB 관측 대체'라고 결론지어 로그를 신뢰 불가 채널로 판정했으며, (c) 실제 검증 시 팀이 fallback 한 수단이 DB 관측이었다. 결정 결함: 사고의 표면(스케줄이 안 걸림)은 코드로 옮겼으나 사고의 근본(비실행이 관측 가능하지 않음)은 채널만 바꿔 재생산했다. job 당 last_run_at 1행이면 '스케줄러가 도는가'가 #1073·#1075 처럼 소진성 부작용(만료 캐시 8행)에 의존하지 않는 상시 질의로 전환된다.
- **권고**: job 실행 기록 테이블(job_name·last_run_at·last_status·last_detail) 1개를 추가하고 각 job 이 종료 시 upsert 하게 한다. 그러면 (a) 스케줄러 생존이 SELECT 1회로 판정되고, (b) owed 원장의 cron 검증 항목이 소진성 신호(8행 보존 제약, line 27) 없이 상시 검증 가능해지며, (c) 'last_run_at 이 주기의 3배를 초과하면 경고' 같은 미실행 탐지를 나중에 얹을 수 있다. 최소 구현이면 정책 16(단순화)과 충돌하지 않는다 — 표 1개·upsert 1줄.

### P1-52. [decision] 외부 제공자 스키마를 검증하지 않은 채 근인 계층에 가드를 구축 — deploy 규칙의 검증 술어가 '빌드 성공'이라 무음 무시 키를 원리상 탐지 불가

- **위치**: `.claude/rules/deploy.md:25`
- **verdict**: CONFIRMED
- **주장**: #1095 는 186 에이전트·확정 147건의 5+1 회고 산물로 railway.toml cron 명령의 따옴표·-f 결함을 잡고 **뮤테이션 실증된 8건 가드**(tests/unit/scripts/test_railway_cron_guard.py)로 봉인한 뒤 'P0 해결'을 보고했다. 하루 뒤 #1099 는 그 키(`[[deploy.cronJobs]]`)가 **Railway 스키마에 존재하지 않아** 명령이 애초에 실행되지 않았음을 확정했고, 가드는 155줄 중 153줄이 삭제되는 전면 재작성을 거쳐 '재도입 차단'으로 역할이 반전됐다. 즉 존재하지 않는 기전의 문법을 고정하는 데 회고 최대 산출물과 뮤테이션 검증이 투입됐다. 결정 결함의 위치는 '전제 미검증'이다 — '이 설정 키가 실제로 제공자에게 읽히는가'를 아무도 묻지 않았고, 그 답을 주는 도구(mcp__railway__get_service_config, #1099 가 cronSchedule=null·nextCronRunAt=null 실측에 실제로 사용)는 #1095 시점에 이미 배선돼 있었다. 구조적 원인: .claude/rules/deploy.md:25 의 검증 의무가 '**빌드 로그** 직접 확인 후 완료 선언'으로 정의돼 있는데, 무음 무시되는 설정 키는 **빌드를 성공시키므로** 이 술어로는 원리상 통과한다. 같은 사각지대가 2026-06-23(69 에이전트)·2026-07-03(92)·2026-07-18(186) 등 다수 대규모 감사에서 12주간 유지된 이유를 설명한다 — 모든 감사 차원이 저장소 내부 정합(코드↔코드·코드↔문서·테스트↔코드)이고 저장소↔제공자 실효 상태 대조 렌즈가 없다.
- **권고**: .claude/rules/deploy.md:25 의 검증 술어를 '빌드 성공'에서 '**제공자 실효 상태 read-back**'으로 교체한다 — railway.toml 의 배포 동작 키를 추가·변경하면 mcp__railway__get_service_config 로 해당 설정이 제공자 측에 실제 반영됐는지(예: cronSchedule non-null) 확인 후 완료 선언. 회고/감사 워크플로에는 '외부 계약 검증' 렌즈를 1개 추가해 railway.toml·nixpacks.toml·GitHub API 계약 등 저장소 밖에서 해석되는 선언을 제공자 실측과 대조하게 한다. 원칙: 가드는 근인 계층에 짓기 전에 그 기전이 실재하는지 먼저 반증한다(정책 15 자문 (b) 영향 범위 인지의 전제 검증판).

### P1-53. [tooling] #1099 의 "배선은 test_scheduler.py 가 단언한다" 는 거짓 — lifespan 배선을 단언하는 테스트가 저장소에 0건 (뮤테이션 실증)

- **위치**: `src/main.py:259`
- **verdict**: CONFIRMED
- **주장**: 이번 P0 수정(#1099)이 저장소 밖 Railway cron 을 인앱 스케줄러로 옮기면서 그 정당성으로 내세운 핵심 단언 — "배선은 tests/unit/test_scheduler.py 가 단언한다" — 이 사실이 아니다. test_scheduler.py 는 src/main.py 를 한 번도 import 하지 않으며(`grep -c "src.main" tests/unit/test_scheduler.py` = 0), lifespan 이 scheduler.start() 를 호출한다는 사실을 어떤 테스트도 단언하지 않는다. 결과적으로 P0 의 실제 실패 모드(= 등록은 돼 있으나 아무도 실행하지 않는 무음 미실행)만 정확히 커버 밖에 남았다 — JOBS 등록·스케줄 계산·job 호출·start/stop 의미론은 전부 단언되지만, '기동된다'만 빠졌다.
- **권고**: tests/unit/test_scheduler.py 에 lifespan 배선 단언 1건 추가 — src.main 의 lifespan 을 실제로 진입시켜 scheduler.start 가 호출되고 반환 태스크가 finally 에서 stop 되는지 단언(monkeypatch 로 start/stop 스파이). test_session_start_wiring.py 가 산문 대신 settings.json 실행 기전을 단언한 것과 동일한 규율. 추가 전까지 5개 파일의 "배선을 단언한다" 문구를 "JOBS 등록·스케줄을 단언한다(배선 미단언)" 로 정정할 것 — 거짓 단언이 다음 세션의 검증 판단을 오도한다(오귀인이 원장에 사실로 기록돼 조사 방향을 틀었던 이번 사이클 교훈의 동형).

### P1-54. [tooling] #1096 의 git fail-CLOSED 봉인이 4번째 `_git` 사본(카덴스 카운터)을 누락 — 완결성 테스트가 하드코딩 3종이라 구조적으로 탐지 불가

- **위치**: `scripts/check_retro_cadence.py:77`
- **verdict**: CONFIRMED
- **주장**: #1096 이 `_git` fail-OPEN 을 fail-CLOSED 로 봉인하면서 대상을 "CI 배선 가드 3종"으로 스코프했고, 그 결과 SessionStart 에 배선된 scripts/check_retro_cadence.py 의 4번째 `_git` 사본이 fail-OPEN 인 채 남았다. 더 중요한 것은 누락 방지용으로 신설된 완결성 테스트가 하드코딩된 3-원소 집합 동등성을 단언해 **신규/기존 사본을 원리적으로 발견할 수 없다**는 점이다 — 테스트 docstring 의 "신규 가드 추가 시 누락 방지" 주장이 이미 존재하는 반례로 반증된다.
- **권고**: (a) check_retro_cadence.py `_git` 을 나머지 3종과 동일한 fail-CLOSED 로 전환하되, advisory 훅 특성상 exit 2 대신 loud 경고 배너 + 명시적 'UNKNOWN' 판정(false-green 금지)으로 종결할 것 — 세션을 죽이지 않으면서 침묵도 만들지 않는 형태. (b) test_all_three_helpers_covered 를 하드코딩 집합에서 **디스커버리 방식**으로 교체 — `scripts/*.py` 를 스캔해 `def _git` 을 정의하는 모듈을 전부 수집하고 각각 fail-closed 계약을 parametrize 단언. 그래야 5번째 사본이 생겨도 자동 편입된다(현 형태는 '가드의 가드'가 아니라 '가드의 스냅샷').

### P1-55. [tooling] 가드 포트폴리오 12종이 전부 정적·저장소-내 분석 — 런타임 부팅 관측을 단언하는 가드 0건이라 이번 두 P0 가 속한 클래스가 통째로 무방비

- **위치**: `src/scheduler.py:166`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: scripts/check_*.py 12종 + 훅 3종은 모두 텍스트/AST/설정 파일 정합성을 본다. 반면 이번 사이클의 확정 P0 2건은 (a) 저장소 밖 플랫폼 스키마(Railway cron 무효 키)와 (b) 저장소 안이지만 **런타임 모듈 상호작용**(alembic fileConfig 가 앱 로깅 파괴)이었고, 어느 가드 클래스로도 탐지 불가능했다. 두 P0 모두 운영 프로브(Railway CLI·DB 관측)로만 발견됐다. 22 PR 중 절반가량이 가드 신설/수리였는데도 가드가 잡아낸 P0 는 0건이라는 비대칭이 이 사이클의 tooling ROI 신호다.
- **권고**: lifespan boot-smoke 테스트 1건 신설 — 실제 src.main lifespan 을 진입시켜 caplog/stdout 에 `DB migration completed` 와 `scheduler started — 5 jobs` 가 **실제로 도달하는지** 단언. 이 단일 테스트가 (1) #1100 이 운영에서 무력이던 P0 클래스, (2) 본 회고 F1 의 스케줄러 배선 갭, (3) 향후 임의 모듈이 로깅을 재설정하는 회귀를 동시에 봉인한다 — 신규 가드 스크립트 추가보다 ROI 가 높고, 가드 수를 늘리지 않아 정책 16(최소 추상화)과도 정합한다. 기존 tests/unit/migrations/test_alembic_env_logging_guard.py 가 alembic 측 절반을 이미 검증하므로 나머지 절반(lifespan 종단)만 채우면 된다.

### P1-56. [security] 리댁션 패턴이 Telegram 1종만 커버 — Discord·Slack·n8n·custom webhook 토큰이 평문 로깅 (6 호출처, PR #1104 OPEN 중 수정 가능)

- **위치**: —
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: `_SECRET_URL_PATTERNS` 는 `api\.telegram\.org/bot` 단 1개다. 그러나 저장소 자체 코드가 credential-in-path URL 을 평문으로 WARNING 로깅하는 호출처가 6곳 존재하며, Discord(`/api/webhooks/<id>/<token>`)·Slack(`/services/T../B../<secret>`)·n8n(`/webhook/<uuid>` = capability token) 은 Telegram 과 동일하게 토큰이 경로에 있다. 필터를 직접 실행해 실증했다: telegram redacted=True / discord=False / slack=False / n8n=False. 🔴 gap 서술보다 트리거가 넓다 — 호출처 5곳은 `validate_external_url` 이 False 를 반환하는 **모든** 경로에서 전문 URL 을 로깅하는데, 여기에는 운영자 오설정(http://)뿐 아니라 `_http.py:73` 의 **일시적 DNS 해석 실패**도 포함된다. 즉 설정이 완벽해도 DNS 순단 한 번이면 4개 provider 의 webhook 토큰이 운영 로그에 남는다. 또한 단일 검증 실패가 `_http.py:46` + 호출처 1곳 = **2줄** 중복 유출을 만든다. 심각도 근거: #1104 자신이 동일 클래스(Telegram 평문 로그 유출)를 P0 으로 등급했으므로, provider 4종 확대 + 무설정오류 트리거는 저장소 자체 캘리브레이션상 P0 이다.
- **권고**: PR #1104 가 OPEN 인 지금 동일 PR 에 fix-up commit (정책 10 fix-up default). 2겹 권장: (1) 패턴 추가 — `(discord(app)?\.com/api/webhooks/\d+/)[^/\s]+`, `(hooks\.slack\.com/services/T[^/]+/B[^/]+/)[^/\s]+` + 쿼리스트링 `([?&](?:token|key|secret|access_token)=)[^&\s]+`. (2) 🔴 근본 수정 — denylist 는 신규 provider 마다 영구 지연하므로, 6 호출처가 **전문 URL 을 아예 로깅하지 않도록** `f"{parsed.scheme}://{parsed.hostname}"` 만 남기는 allowlist 전환. n8n·custom 은 self-hosted 임의 경로라 패턴화 불가 → (2) 없이는 원천 미봉인. 회귀 가드는 provider 4종 parametrize 로 봉인.

### P1-57. [tooling/process] 신설한 '경고 피로' 기준을 제거(#1058)에만 적용하고 추가에는 한 번도 적용하지 않은 단방향 가드

- **위치**: `docs/runbooks/owed-verification.md:54`
- **verdict**: CONFIRMED
- **주장**: 같은 세션이 #1103 으로 안전등급 편입 기준 2가지를 신설했다(`:54`): (a) 검증 선행 조건이 운영에 실제 구비됐는가 (b) 미검증이 실제 위험을 만드는가. 그런데 이 기준을 **표에서 빼는 판정(#1058 → ⏭️)에만** 쓰고, **넣는 판정에는 단 한 번도 돌리지 않았다**. 두 로테이션 항목을 기준에 대입하면 둘 다 완전 충족한다 — (a) `TELEGRAM_BOT_TOKEN` 은 `docs/reference/env-vars.md:8` 필수 환경변수이자 현재 활성 알림 경로라 운영자가 BotFather `/revoke` + Railway 변수 교체로 **즉시 수행 가능**(#1058 이 탈락한 '선행 설정 부재' 와 정반대) (b) 유효한 credential 이 보존된 운영 로그·대화 기록에 남아 있어 **위험이 이미 실재**(#1058 이 탈락한 '비활성 기능=위험 0' 과 정반대). 즉 기준은 신설 즉시 자신이 편입시켰어야 할 항목을 놓쳤다. 2026-07-18 프리미엄 준비도 감사가 명명한 only-one-side-guarded 비대칭의 재현.
- **권고**: `:54` 기준 문단에 양방향 적용 의무를 명시한다 — "이 자문은 **행 제거 시뿐 아니라 행 추가 판정 시에도** 수행한다. 세션 종료 시 그 세션이 만든 운영자 전용 조치(로테이션·수동 설정·외부 계정 작업)를 열거해 2 기준에 대입하고, 둘 다 충족하면 안전등급 표에 편입한다." 기준 신설 PR 에는 그 기준을 기존 미편입 항목 전체에 1회 소급 적용한 결과를 함께 싣는다.

### P1-58. [tooling/process] 원장 스키마가 PR 번호 없는 의무(운영자 조치·Claude 유발 유출)를 구조적으로 표현 불가 — 재발이 보장된 설계

- **위치**: `scripts/check_owed_verification.py:32`
- **verdict**: CONFIRMED
- **주장**: `_ROW = re.compile(r"^\|\s*\*{0,2}(#\d+)\*{0,2}\s*\|")`(:32) 는 **첫 셀이 반드시 `#숫자`** 여야 매칭한다. 즉 원장의 데이터 모델은 '모든 미결은 특정 PR 에서 파생된다' 를 가정한다. 그러나 이번 세션이 만든 미결 2건은 그 가정 밖이다 — INTERNAL_CRON_API_KEY 노출은 PR 이 아니라 **Claude 의 대화 중 명령 실수**에서 발생했고, 로테이션은 코드 변경이 아니라 **운영자 계정 조치**다. 결과적으로 성실한 미래 Claude 가 이 의무를 원장에 남기려 해도 **파싱 가능한 슬롯이 없다** → 자연히 산문으로 밀려나고, 산문은 카운터가 못 본다. 이번 gap 은 규율 실패이기 이전에 스키마 실패이며, 스키마를 두면 같은 형태가 반복된다.
- **권고**: `_ROW` 를 `^\|\s*\*{0,2}((?:#\d+|[A-Z_]{4,}|OPS-\d+))\*{0,2}\s*\|` 류로 확장해 PR 번호·환경변수명·운영 티켓 키를 모두 키로 허용하고, `test_check_owed_verification.py` 에 비-PR 키 행이 파싱되는지 단언하는 테스트를 추가한다(현 11 테스트는 전부 PR 키 전제). 확장 전이라면 최소 조치로 로테이션 항목에 유발 PR 번호(#1104)를 키로 붙여 우회한다.

### P1-59. [observability] 스케줄러 런타임 탐지 축 전무 — job 별 last-run·heartbeat·경보 0건 (사고 재발 시 탐지 지연 동일)

- **위치**: `src/scheduler.py:145`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1099/#1102 는 실행 축(인앱 이관)과 테스트 시점 배선 단언만 덮었다. 운영 중 특정 job 이 조용히 멈춰도 이를 드러내는 상태·질의 가능 신호가 코드 어디에도 없다 — 이번 P0 의 본질('수개월간 미실행을 아무도 몰랐다')은 그대로 재현 가능하다.
- **권고**: (1) `src/scheduler.py` 에 모듈 레벨 `_LAST_RUN: dict[str, dict]`(name → started_at/finished_at/last_error/consecutive_failures)를 `_run_job_forever` 안에서 갱신. (2) 노출은 `/health` 가 아니라 **이미 존재하는 admin 면**(`src/api/admin.py:90` `GET /operations`, `operations_service.operations_kpi`)에 job 상태 카드 1개 추가 — 인증된 운영 화면이라 정보 노출 우려 없음. (3) daily/weekly 는 재시작 시 in-memory 상태가 소실되므로 **DB 영속화 필수**(경량 `job_run` 테이블 또는 기존 upsert 패턴 재사용). (4) 6번째 supervisor job 이 `now - finished_at > 2×주기` 인 job 을 `src/notifier/telegram.py` 로 경보 — 기존 알림 채널 재사용이라 신규 의존성 0(정책 16).

### P1-60. [observability] 태스크 사망이 무신호 — `start()` 에 done_callback 없고 `stop()` 이 사망 원인 예외를 삼킨다

- **위치**: `src/scheduler.py:165`
- **verdict**: CONFIRMED
- **주장**: 5개 태스크 중 하나가 어떤 이유로든 종료되면 이를 감지·기록하는 코드가 없다. 종료 경로에서 예외를 await 하지만 광범위 `except` 로 무조건 폐기해 사망 원인조차 남지 않는다.
- **권고**: `start()` 에서 `task.add_done_callback(_on_task_done)` 배선 — 콜백이 `task.cancelled()` 가 아닌 종료를 `logger.error` + `_LAST_RUN[name]["dead_at"]` 로 기록. `stop()` 의 광범위 except 는 `except asyncio.CancelledError: pass` / `except Exception: logger.exception(...)` 로 분리해 종료 시점에도 사망 원인이 남게 한다.

### P1-61. [observability] scan-security = 스케줄이 한 번도 없었던 6번째 cron — #1099 가 '깨진 5 블록'을 정본으로 복제하며 필요 집합 감사를 건너뛰었다

- **위치**: `src/api/internal_cron.py:103`
- **verdict**: CONFIRMED
- **주장**: `POST /api/internal/cron/scan-security` 는 스스로를 cron 폴링 트리거라 문서화하지만 구 railway.toml 에도 신 스케줄러에도 등록된 적이 없다. 즉 GitHub Code/Secret Scanning alert 폴링은 **출시 이래 주기 실행이 0회**이며, 어떤 탐지 축으로도 드러나지 않는다 — '등록되지 않은 job' 은 last-run 감시조차 대상으로 삼지 못하기 때문이다.
- **권고**: scan-security 의 주기 실행 필요 여부를 명시 결정할 것 — (a) 필요 시 `JOBS` 에 6번째 등록(정책 14 의 수동 Security 탭 점검과 역할 분담 명시) (b) 불필요 시 엔드포인트 docstring 에서 'cron' 표현 제거 + 수동 전용 명시. 함께 **회귀 가드**: `tests/unit/test_scheduler.py` 에 'cron 성격 서비스 함수 ↔ JOBS 등록' 대응 단언 추가 — 지금 테스트(:106 `test_all_five_cron_jobs_registered`)는 5라는 숫자를 고정할 뿐 '집합이 완전한가'를 묻지 않아 이 누락을 구조적으로 통과시킨다.

### P1-62. [observability] 정책 13 정기 smoke check 에 스케줄러 항목 0 — 유일한 반복 운영 의례가 스케줄러를 건드리지 않는다

- **위치**: `docs/runbooks/operational-smoke-checks.md:6`
- **verdict**: CONFIRMED
- **주장**: 매 사이클/Phase 종료마다 수행되는 운영 점검 절차가 3-endpoint(`/health`·`/auth/github`·`/login`)에 한정돼 있어, 스케줄러 정지는 어떤 정기 점검에도 걸리지 않는다. 탐지는 계속 ad-hoc 인간 로그 읽기에 의존한다.
- **권고**: P0 항목의 admin job-status 면이 생기면 정책 13 smoke check 에 4번째 항목으로 '스케줄러 5(또는 6) job 의 last_finished 가 각 주기의 2배 이내' 1줄 추가. 면이 생기기 전 임시 조치로도 `retry-pending-merges`(60초)·`sweep-orphans`(600초) 로그 존재 확인 1줄은 즉시 추가 가능 — 같은 루프이므로 interval job 생존이 전체 루프 생존의 대리 지표가 된다(#1073 종결 논리와 동일).

### P1-63. [observability] 런타임 사후 조건 부재 — 관측 소실이 스스로를 은폐하는 구조가 그대로 남아 있다

- **위치**: `src/main.py:216`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 두 사고 모두 '조용히' 발생했다(#1100 = 출시 이래 수개월, #1102 = 3세션). 원인은 로깅 불변식이 깨졌을 때 그것을 알릴 수단이 로깅 자신뿐이라는 자기참조다. 현재 lifespan 은 마이그레이션 직후 불변식을 재확인하지 않는다. 저장소 차원 소스 스캔 가드를 추가해도 이 자기은폐 구조는 해소되지 않는다 — 스캔은 알려진 기전만 막고, 3번째 기전은 정의상 미지이기 때문이다.
- **권고**: `src/main.py:216` 직후에 사후 조건을 삽입한다 — `logging_healthy()`(P0-1) 로 검증하고, 깨졌으면 완전 복구(핸들러+레벨+`disabled` 해제) 후 `logger.warning` 으로 **복구가 필요했다는 사실 자체**를 크게 남긴다. 이렇게 하면 미지의 3번째 기전이 무엇이든 (a) 자동 복구되고 (b) 수개월 무성 소실이 배포 1회당 한 줄 경보로 전환된다. 기전 열거에 의존하지 않는 유일한 방어라는 점이 핵심 — 소스 스캔보다 우선순위가 높다.

### P1-64. [observability] gap 이 제안한 저장소 차원 소스 스캔 가드는 실제 사고 2건 중 어느 것도 잡지 못했을 것

- **위치**: `alembic/env.py:35`
- **verdict**: CONFIRMED
- **주장**: gap 진술은 `scripts/check_*.py` 패턴이 '이 클래스에 정확히 부합하는데도 채택되지 않았다'고 판정했으나, 검증 결과 그 진단은 형상이 맞지 않는다. #1100 은 호출의 **부재**였고(존재를 스캔하는 가드는 부재를 탐지할 수 없다), #1102 의 파괴적 호출은 `alembic/env.py:35` 로 **CLI 경로에서는 정당하고 필수적인 코드**다. 따라서 스캔 가드는 필수 라인에 위양성을 내거나, 사고를 일으킨 바로 그 라인을 allowlist 에 넣어야 한다. 이 불변식 클래스는 구문적(syntactic)이 아니라 행동적(behavioral)이다.
- **권고**: 소스 스캔을 1차 방어로 채택하지 않는다. P0-2 의 런타임 사후 조건을 1차로 두고, 보조망이 필요하면 스캔의 판정 기준을 '호출 존재'가 아니라 '**승인된 소유자 2곳(`src/logging_config.py`, `alembic/env.py`) 밖의 신규 호출 유입**'으로 좁혀 2차로만 배치한다. 회고 결론에 '이 클래스는 check_*.py 패턴 부적합'을 명시해 다음 세션이 같은 오진단을 반복하지 않게 한다.

### P1-65. [docs] STATE.md(SSOT)가 #1100 을 로그소실 P0 의 '해결'로 기록 — #1102(무력화 봉인) 미반영으로 반증된 서사를 그대로 보유

- **위치**: `docs/STATE.md:25`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: docs/STATE.md:25 는 로그 전소실 P0 를 `src/logging_config.py` 신설 + `main.py` import 시점 배선으로 종결된 것처럼 서술한다. 그러나 본 세션 확정 P0 = 그 수정이 alembic `fileConfig` 에 의해 운영에서 무력(inert)이었고 #1102 가 이를 봉인했다. STATE.md 전문에 `1102` 0회·`fileConfig` 0회. 즉 '단일 진실 소스'로 선언된 문서가 반증된 인과를 유일 서사로 보유하며, 정정은 runbook 한 곳에만 존재한다. 이는 직전 세션의 '앱 문제 아님' 오귀인이 원장에 사실로 남아 cron 검증을 3세션 차단한 것과 **동일한 실패 형태의 한 계층 위 재발**이다.
- **권고**: STATE.md:25 를 '#1100 신설 → #1102 로 alembic fileConfig 파괴 봉인' 2단 서사로 정정하고 fileConfig 근본원인 1줄을 SSOT 본문에 명시. 정정이 runbook 단독으로 존재하는 상태를 해소 (다음 세션 진입점은 STATE.md 이므로 runbook-only 정정은 도달 보장 없음).

### P1-66. [docs] cycle-history.md 에 2026-07-19 세션(#1094~#1103, 10 PR) 항목 0건 — P0 3건 서사가 기관 기억에서 누락된 채 세션 종료 임박

- **위치**: `docs/cycle-history.md:145`
- **verdict**: CONFIRMED
- **주장**: docs/cycle-history.md 최신 항목은 line 145 `## 세션2 회고 + 회고 fix 4 트랙 11 PR (2026-07-18)` 이고 2026-07-19 세션 항목이 전무하다. 6-step ⑤ 의 배치-PR 이월 분기가 세션 중 지연을 허용하는 것은 맞으나, **이월은 세션 종료 시 trailing sync PR 로 반드시 회수**되어야 하는 부채다. 현재 세션은 owed 원장 종결 커밋(c887469)까지 도달해 종료 국면인데 trailing sync 는 미생성이다. 누락 대상이 사소하지 않다 — cron 5종 전면 미실행·앱 로그 전소실·alembic 로깅 파괴 3건은 cycle-history 가 존재하는 이유 그 자체인 제도적 지식이다.
- **권고**: 세션 종료 전 trailing sync PR 에서 2026-07-19 세션 섹션 신설 — P0 3건(cron 미실행·로그 소실·alembic fileConfig 무력화) + 오귀인 반증 경로를 본문에 기록. 수치 정정(finding 2)·날짜 헤더(finding 4)·STATE 서사 정정(finding 1)을 같은 PR 로 묶어 회수.

---

## P2 (58건)

### code (6)

- 저장소 안 상호작용에 대한 가드 부재 — #1099 가 '저장소 밖 설정' 에서 얻은 교훈이 저장소 안에서 재발했다 — `src/scheduler.py:166`
- SessionStart 카운터 2종이 cwd 의존 상대경로 + 파일 부재 시 무음 통과 — '원장을 못 읽는 상태'와 '미결 0건'이 구분되지 않는다 — `scripts/check_owed_verification.py:24`
- 스케줄러가 실행 흔적을 DB 에 남기지 않음 — 사고를 3세션째 검증 불가로 만든 관측 공백을 대체 기전이 그대로 승계 — `src/scheduler.py:166`
- 주기 작업 실행 여부를 보안 하드닝 휴리스틱(is_production)에 결속 — 비-HTTPS 배포에서 5종 무음 미실행, 통지는 죽은 채널(INFO) — `src/scheduler.py:86`
- _retry_pending_merges 가 1분마다 Settings() 를 새로 인스턴스화 — 싱글톤 단일 출처 이탈 — `src/scheduler.py:94`
- docstring 의 '알려진 한계' 목록이 실제 한계 2종(고정지연 드리프트·배포 중 컨테이너 중첩)을 누락 — `src/scheduler.py:15`

### code/architecture (4)

- advisory lock 이월 의무가 docstring 단독 — 저장소 전체에 재부상 기전 0 — `src/scheduler.py:20`
- daily/weekly 미실행 catch-up 부재 — #1099 가 봉인한 '조용한 미실행' 을 좁은 형태로 재도입, owed #1075 검증 false-NG 경로 — `src/scheduler.py:16`
- 프로세스 회귀 — 문서-only 시정을 P0 로 규정하고 기계화한 바로 그날, 동일 형태의 문서-only 의무를 신규 생성(4회차) — `docs/runbooks/owed-verification.md:139`
- 등록처 구조 공백 — '조건부 코드 의무' 를 수용하는 register 가 프로젝트에 존재하지 않는다 — `docs/runbooks/owed-verification.md:3`

### decision (3)

- 스케줄러의 수용된 한계가 사용자 결정 항목으로 표면화되지 않았고, 그 한계가 핸드오프 판정 기준을 무효화한다 — `src/scheduler.py:14`
- 인수인계 문서가 '단 하나의 미완 검증' 이라 단언 — 실제 미결은 6건, 그중 안전등급 2건(정책 5 NEW-P0-N 매 사이클 회신 의무) — `docs/runbooks/owed-verification.md:13`
- 원장 산문 요약이 append-only 표를 덮어써 안전등급 회신 의무를 무음화 — 기계 카운터는 행만 파싱해 검증 불가 — `docs/runbooks/owed-verification.md:13`

### docs (19)

- cycle-history.md 에 2026-07-19 세션(#1094~#1101, 8 PR·P0 2건) 항목 부재 — `docs/cycle-history.md:8`
- .claude/rules/deploy.md 가 railway.toml 을 스코프로 선언하고도 cron 스키마 함정 0건 기록 — `.claude/rules/deploy.md:4`
- alembic↔앱 로깅 상호작용 함정이 어느 rules 문서에도 미기록 — 재발 방지 지식 미정착 — `.claude/rules/db.md:1`
- cycle-history.md 에 2026-07-19 작업 전량 부재 — P0 2건 포함 15 PR 이력 공백 — `docs/cycle-history.md:145`
- STATE.md 날짜 헤더·'최신' 블록 제목 stale + 서사 체인 누적 — 자기 문서에 명시된 2개 규칙 동시 재위반 — `docs/STATE.md:5`
- owed 원장의 '실행 가능한 표 셀'이 반증된 제약을 계속 인코딩 — 정정은 서술 섹션에만 착지, 파서는 구조적으로 탐지 불가 — `docs/runbooks/owed-verification.md:53`
- SCHEDULER_DISABLED 가 .env.example 누락 — 형제 kill-switch 8종은 전부 등재된 단독 예외 — `.env.example:188`
- .claude/rules/deploy.md 미동기화 — railway.toml 이 deploy.md 의 path 인데 cron P0 기록 0건 (api.md 는 동기화된 비대칭) — `.claude/rules/deploy.md:4`
- docs/runbooks/railway.md 에 cron P0 기록 0건 + lifespan 마이그레이션을 무해한 것으로 기술(=로깅 파괴 기전) — `docs/runbooks/railway.md:38`
- '1분 cron' 기전 서술이 3개 문서에 잔존 — 출시 이래 거짓이던 주장이 모든 감사를 통과한 구조적 이유 — `README.md:223`
- cycle-history.md 에 2026-07-19 세션(#1094~#1101) 항목 전무 — 6-step ⑤ 절반만 수행 — `docs/cycle-history.md:145`
- #1099 가 .claude/rules/deploy.md 미동기화 — railway.toml 편집 시 자동 로드되는 유일한 가이드에 cron 교훈 부재 — `.claude/rules/deploy.md:4`
- STATE.md 날짜 헤더 스테일(2026-07-18) — 스스로 '상시 누락' 이라 표기한 필드가 또 누락 — `docs/STATE.md:5`
- check_docs_sync.py = 회고가 센 3건에 미포함된 4번째 자기참조 count-lock — `scripts/check_docs_sync.py:10`
- docs/README.md 런북 인덱스 15개 중 2개 미등재 — 반복 drift, 미검증 — `docs/README.md:49`
- 단위 테스트 수치 drift 9건 — 단일 원인은 #1102 의 6-step ⑤ 전면 누락 (#1094~#1100 은 전건 정확) — `docs/STATE.md:26`
- check_docs_sync.py 는 문서-vs-실측 drift 계열에 설계상 green — 균일 stale 값에 '✅ 일치' 출력으로 거짓 확신 생성 — `scripts/check_docs_sync.py:10`
- STATE.md:5 날짜 헤더 stale — 이 필드 전용으로 신설된 anti-drift 규칙이 그 필드에서 재실패, 기계 가드 0건 — `docs/STATE.md:5`
- 6-step ⑤ 배치-PR 이월 분기에 부채 추적 기전 부재 — 이월 사실이 커밋 본문/인간 기억에만 존재 — `scripts/check_owed_verification.py:1`

### observability (5)

- job 이 hang 하면 태스크는 살아있고 로그도 안 나온다 — 태스크 감시만으로는 못 잡는 무음 정지 — `src/scheduler.py:151`
- 재시작 시 daily/weekly 스킵을 '의도적 수용' 했으나 보상 탐지가 없다 — 이번 사고와 동일 클래스가 설계로 잔존 — `src/scheduler.py:16`
- 종결 증거가 휘발성 로그 스트림 3줄 — 질의 불가·재현 불가로 다음 사고 때 같은 조사를 처음부터 반복한다 — `docs/runbooks/owed-verification.md:62`
- 가드는 운영 합성 경로가 아니라 그 재구성본을 테스트한다 — lifespan 테스트 26건이 전부 마이그레이션을 mock 으로 제거 — `tests/unit/migrations/test_alembic_env_logging_guard.py:102`
- CLI 보존 테스트는 env.py import 순서 회귀에 대해 공허해질 수 있다 (sys.modules 캐시) — `alembic/env.py:10`

### process (7)

- 6-step ⑤ 미이행 — 07-19 세션 8 PR(#1094~#1101, P0 2건 포함)이 cycle-history 에 전무, STATE 와 비대칭 — `docs/cycle-history.md:1`
- PR §검증 증거에 환경 라벨 부재 — 로컬 재현 출력이 운영 확인처럼 읽힘 — `docs/runbooks/owed-verification.md:94`
- 정책 13 3-endpoint smoke 기록이 /health 단독 — 사이클이 앱 lifespan 을 3회 변경했음에도 — `docs/runbooks/owed-verification.md:34`
- 6-step ⑤ 미이행 상태로 세션 종료 — cycle-history.md 에 #1094~#1101 8 PR(운영 P0 2건 포함) 서사 전무, 배치-이월이 요구한 trailing sync PR 부재 — `docs/cycle-history.md:145`
- 6-step ⑥ / 아키텍처 동기화 체크리스트 위반 — 신규 파일 src/logging_config.py 가 docs/architecture.md src/ 트리에 미등재 (전례 4번째) — `docs/architecture.md:34`
- STATE.md 날짜 헤더·'최신' 블록이 2026-07-18·#1077~#1092 로 고착 — SSOT 자신이 '상시 누락 필드' 로 주석한 항목의 재발 — `docs/STATE.md:5`
- 책임 원장이 '재확인 불필요' 억제 섹션을 획득 — append-only 증거 장부가 조사 중단 장치로 변질 — `docs/runbooks/owed-verification.md:29`

### security (3)

- #1104 테스트 226줄·리댁션 8건이 전부 Telegram — provider 클래스 미parametrize 로 false-green ('가드의 가드' 연장) — —
- 동일 6 호출처가 `sanitize_for_log` 도 미적용 — 사용자 제어 webhook_url 로그 인젝션(CRLF) 경로 — —
- 프로세스: 미머지 PR 이 회고 scope 밖으로 새는 구멍 + 정책 16 `grep -rn` 전수 의무 미적용 — —

### tooling (10)

- 오귀인이 owed 원장에 '확정 사실'로 기록되어 검증 방법론까지 바꿨고, append-only 규칙 탓에 다음 세션을 오도하도록 고착됨 — `docs/runbooks/owed-verification.md:36`
- PostToolUse 스모크 훅이 src/ 직속 파일을 collection-only 로 강등 — 정확 대응 테스트가 존재하는 6종이 한 번도 실행되지 않음 — `.claude/hooks/posttool_pytest_smoke.py:60`
- check_memory_refs 스코프(3 문서)가 실제 인용면보다 좁아 tests/ 의 dangling 메모리 참조 미검출 — #1098 이 고친 것과 동일 결함 클래스 — `scripts/check_memory_refs.py:25`
- SessionStart 카운터 2종은 ROI 실증(본 회고가 그 산물) — 다만 owed 카운터에 경과/에스컬레이션 차원이 없어 동일 배너 반복에 따른 습관화 위험 — `scripts/check_owed_verification.py:64`
- lifespan 테스트 15건 전부가 `_run_migrations` 를 mock — 앱 기동 부작용면(side-effect surface)을 관측하는 테스트가 0 — `tests/unit/test_main.py:117`
- PostToolUse pytest 훅이 `src/` 직속 파일에 테스트 신호 0 — 본 사이클 P0 3건이 전부 그 사각지대 — `.claude/hooks/posttool_pytest_smoke.py:73`
- bandit·flake8·pylint 가 **어디서도 실패하지 않는다** — `make lint` 는 `|| true`, CI/pre-commit 미배선인데 커밋 본문은 '게이트 통과' 로 보고 — `Makefile:74`
- SessionStart 카운터 2종이 cwd 상대경로 + 무음 fail-open — 자기가 봉인하려던 '조용히 inert' 클래스에 자신이 노출 — `scripts/check_owed_verification.py:96`
- PostToolUse 스모크 훅이 src/ 전용 — 이번 사이클 최다 결함 영역(alembic/)과 최다 churn 영역(scripts/)이 커버 밖 — `.claude/hooks/posttool_pytest_smoke.py:34`
- owed 카운터는 원장 파일 부재 시 완전 무음 — 카덴스 카운터의 skip 배너와 비대칭이라 '미결 0건'과 구별 불가 — `scripts/check_owed_verification.py:94`

### tooling/process (1)

- 산문에 적힌 보안 의무를 잡아낼 가드 부재 — 기존 11 테스트는 표 파싱 무결성만 방어 — `tests/unit/scripts/test_check_owed_verification.py:116`
