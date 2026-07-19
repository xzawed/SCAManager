# 미결 운영 검증 원장 (Owed Operational Verification Ledger)

> **목적**: 코드로 증명 불가한 운영/외부 검증(HSTS 헤더·쿠키 Secure·cron 실제 실행·외부 API 계약·DELETE 실행·이메일 실제 발송 등)을 남긴 PR 을 **append-only** 로 추적한다. 머지 = 코드 결정 종결이나, 운영 검증 증거는 사용자가 OK/NG 를 찍기 전까지 미결로 유실될 수 있다(회고 2026-07-18 P1#13·P2#31·P2#38).
>
> **작성 규칙**: 세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다(trailing sync PR body 의 §owed-verification 표와 페어). 사용자 회신(OK/NG/미수행) 전까지 **행 삭제 금지**(append-only). 정책 2 진화(Phase 종료 일괄 회신) + 정책 13(smoke check) + 정책 5 NEW-P0-N(안전등급은 매 사이클 회신 의무) 페어.
>
> **상태 범례**: ⏳ 미검증(사용자 회신 대기) · ✅ 검증 완료(OK) · ❌ 이슈 발견(NG) · ⏭️ 사용자 미수행(보류)

---

## ✅ 인앱 스케줄러 실동작 확정 (2026-07-19 05:0x UTC — 로그 직접 관측)

`#1102`(alembic 로깅 파괴 봉인) 배포 직후 운영 로그가 복구되면서, **3세션째 막혀 있던 cron 검증이 20:00 UTC 대기 없이 즉시 종결**됐다. 더 이상 DB 우회 관측이 필요 없다 — **로그가 직접 증거**다.

```
04:34:50 INFO [src.scheduler] scheduler started — 5 jobs: retry-pending-merges,
                              sweep-orphans, trend, retention-sweep, weekly-reports
04:35:54 INFO [src.scheduler] scheduler retry_pending_merges: counts={...}   ← 이후 ~61초 간격 연속
04:44:51 INFO [src.scheduler] scheduler sweep_orphans: surfaced=0
04:54:52 INFO [src.scheduler] scheduler sweep_orphans: surfaced=0            ← 정확히 600초 간격
05:04:53 INFO [src.scheduler] scheduler sweep_orphans: surfaced=0
```

| 확인 항목 | 결과 |
|-----------|------|
| 5종 job 등록 | ✅ 기동 로그에 전부 명시 |
| interval job 실행 | ✅ `retry-pending-merges` ~61초 · `sweep-orphans` 정확히 600초 주기 (33분 연속 관측) |
| `#1073` orphan sweep | ✅ **종결** — cron 전용 경로가 실제 실행 중 |
| `#1075` retention sweep | ⏳ 잔여 — **daily 20:00 UTC** 라 아직 미도래. 단 같은 스케줄러 루프이고 로그가 살아 있으므로 그날 로그의 `scheduler retention_sweep: counts={...}` 한 줄로 확인된다 |

🔴 **만료 캐시 8건을 다른 방법으로 지우지 말 것** — `#1075` 의 DELETE 실증 신호다(캐시 TTL=1h 이나 2.5개월간 8건만 생성·최신 10일 전이라 재생성 안 됨). 수동 `retention-sweep` 호출도 금지.

### 이미 확인된 것 (재확인 불필요)

| 항목 | 결과 |
|------|------|
| 인앱 스케줄러 기동·interval job 실행 | ✅ **로그 실측 확정** (위 표) |
| 서비스 계층(엔드포인트·인증·`cron_service`·worker DB 세션) | ✅ 정상 — 잘못된 키 **401** / 정상 키 **200 `{"status":"ok","orphans_surfaced":0}`** |
| 앱 헬스 | ✅ `/health` **200** (0.5~0.8s) — 재시작 루프 아님 |
| `INTERNAL_CRON_API_KEY` | ✅ Railway 에 설정됨·유효 |
| 🔴 ~~Railway **deploy 로그 수집**~~ | ❌ **오귀인이었다 — 2026-07-19 반증·수정 완료(`#1102`).** 원인은 Railway 가 아니라 **앱 자신**(`alembic/env.py` 의 `fileConfig` 가 마이그레이션 시 앱 로깅 파괴). 아래 §오귀인 정정 참조 |

⚠️ weekly 리포트 첫 발송 = 다음 주 **월요일 00:00 UTC**(출시 이래 0회 발송).

🔴 **로깅 복구가 드러낸 잠복 결함**: 로그가 살아나자 **Telegram 봇 토큰이 URL 경로에 평문으로 남고 있음**이 드러났다(httpx 가 요청 URL 전문을 INFO 로깅 — 실측 5건). `#1104` 로 2계층 리댁션 적용. **이미 남은 토큰은 코드로 회수 불가 → 토큰 로테이션 필요**(운영자 영역).

## 🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1058** | ~~SMTP 이메일 실제 발송~~ → **검증 불가 + 운영 위험 0 확정** (2026-07-19 실측 재분류). 이메일 채널은 운영에서 **한 번도 활성인 적이 없다** — "고장난 발송이 복구됐는지"가 아니라 **"설정된 적이 없다"** 가 사실. 587 STARTTLS 수정 자체는 실재 코드 결함 교정이나 **운영 효과 0** | **재분류 근거 (실측)**: ① Railway SMTP 변수 **0개**(`SMTP_HOST`·`SMTP_PORT`·`SMTP_USER`·`SMTP_PASS` 전부 미설정) ② `repo_configs` **8건 중 `email_recipients` 설정 0건** → `src/notifier/email.py:126` 의 `if not recipients or not smtp_host: return` 에서 **즉시 반환**(발송 코드 미진입). 살아있는 이메일 경로가 없으므로 미검증 상태가 위험을 만들지 않는다. **재개 조건**: 사용자가 SMTP 4종 + 대상 리포 `email_recipients` 를 설정하면 → 상태를 ⏳ 로 되돌리고, 그 리포에 push/PR 유발 후 `email_recipients` 주소 수신함에서 `[Code Review]` 제목 메일 도착 확인 | 5·13 | ⏭️ |
| **#1062** | NULL-owner 저장소 **쓰기 차단(IDOR)** 과잉 차단 여부 — 정상 소유자 흐름이 403 로 오차단되지 않는지 | 정상 소유 저장소에서 설정 변경·피드백 등 7 쓰기 라우트가 200 정상 동작 확인(운영 계정) | 15 | ⏳ |

🔴 **거짓 안전등급 경고 방지 (2026-07-19 학습)** — 안전등급 ⏳ 는 SessionStart 훅이 **매 세션 loud 경고**로 띄우는 자리다. 따라서 이 표에는 **사용자가 실제로 회신할 수 있는 항목만** 남긴다. `#1058` 은 선행 설정이 없어 **사용자가 회신할 수 없는데도** 4사이클째 경고를 발생시켰다 — 경고 피로가 쌓이면 진짜 안전 항목(`#1062`)까지 함께 무시된다. **신규 안전등급 행 추가 시 자문**: (a) 이 검증에 필요한 **선행 조건이 운영에 실제로 갖춰져 있는가**(env·설정 실측 확인) (b) 미검증 상태가 **실제 위험을 만드는가**(비활성 기능이면 위험 0). 둘 중 하나라도 아니면 안전등급이 아니라 ⏭️ + 재개 조건 명시가 맞다.

## 운영/외부 계약 등급 (Phase 종료 일괄 회신 — 정책 2 진화)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1071** | prod 하드닝 — HSTS 헤더·쿠키 Secure·`/docs` 비노출이 Railway(https)에서 적용되는지 | ✅ **2026-07-19 실측 3/3 충족**: ① `strict-transport-security: max-age=31536000; includeSubDomains` 존재 ② `/auth/github` 세션 쿠키 = `path=/; Max-Age=604800; httponly; samesite=lax; **secure**` ③ `GET /docs` → **404** | 13 | ✅ |
| **#1072** | approve SHA 결속 — head 이동 PR 에 approve 시도 시 GitHub **422 fail-closed** (외부 계약 미검증) | head 가 이동한 PR 에 반자동 approve 유발 → GitHub 422 반환 + gate 가 차단하는지 운영 로그 관측 | 13 | ⏳ |
| **#1073** | orphan sweep cron **실제 실행** — `analysis_attempts` 소실 탐지·표면화·정리 | ✅ **2026-07-19 로그 직접 관측으로 종결**. `#1102` 로 로깅 복구 후 `[src.scheduler] scheduler sweep_orphans: surfaced=0` 이 **정확히 600초 간격**으로 반복 확인(04:44:51 · 04:54:52 · 05:04:53). cron 전용 경로가 실제 실행 중임이 확정 — DB 우회 관측 불필요 | 13 | ✅ |
| **#1075** | retention sweep cron **실제 DELETE** — 만료 캐시·종결 큐 GC | ⏳ **daily 20:00 UTC 라 미도래**(스케줄 특성상 대기 외 방법 없음). 🔴 검증 수단은 이제 **로그 직접 관측**(DB 우회 불필요 — `#1102` 로 복구): 20:00 UTC 이후 로그에서 `[src.scheduler] scheduler retention_sweep: counts={...}` 확인. 교차 확인 = `SELECT COUNT(*) FROM insight_narrative_cache WHERE expires_at < NOW()` 가 **8 → 0**. 같은 스케줄러 루프의 interval job 이 이미 실동작 확정(`#1073`)이라 실행 자체는 높은 확신 | 13 | ⏳ |

---

## 회신 방법

사용자는 각 행의 상태를 `✅/❌/⏭️` 로 갱신하거나, Claude 에게 결과를 전달하면 Claude 가 갱신한다. `❌`(NG) 발견 시 = 즉시 fix PR 착수(정책 7). 전 행 `✅`/`⏭️` 확정 시 = 원장에서 **아카이브 섹션으로 이동**(본 상단 표는 미결만 유지).

## 🔴🔴 근본 원인 확정 — Railway cron 은 **한 번도 실행된 적이 없다** (2026-07-19 P0)

`#1073`·`#1075` 가 검증되지 않던 진짜 이유. `railway.toml` 의 `[[deploy.cronJobs]]` 는 **Railway 스키마에 존재하지 않는 키**라 조용히 무시됐다.

| 실측 | 결과 |
|------|------|
| SCAManager 서비스 `cronSchedule` / `nextCronRunAt` | **둘 다 null** |
| Railway cron 설정 방식 (공식 문서) | 서비스당 **단일** `deploy.cronSchedule` 또는 대시보드 — **배열 미지원** |
| 20:00 UTC 스윕 3.5h 경과 후 만료 캐시 | **8건 잔존** (실행됐다면 `purge_expired` 가 0으로 만들었어야 함) |

→ weekly · trend · retry-pending-merges · sweep-orphans · retention-sweep **5종 전부 미실행**.
(직전 #1095 의 따옴표·`-f` 수정은 실재 결함이었으나 **명령 자체가 실행되지 않아 무의미**했다.)

✅ **대체 = 인앱 스케줄러 `src/scheduler.py`** (lifespan 기동·운영 전용). 배선을 `tests/unit/test_scheduler.py` 가 단언한다 — 저장소 밖 설정이 조용히 어긋나던 실패 모드를 코드로 옮긴 것이 이 사고의 교훈이다.

🔴 **따라서 #1073·#1075 는 스케줄러 배포 후에야 검증 가능**하다. 검증 기준은 아래 DB 관측을 그대로 사용한다(`insight_narrative_cache` 만료 8건 → 0).

## 🔴🔴 오귀인 정정 — 로그 소실은 Railway 가 아니라 **앱 결함**이었다 (2026-07-19 반증)

직전 세션이 *"Railway 로그 수집이 초기 출력 후 끊김 — **앱 문제 아님**"* 으로 기록한 진단은 **틀렸다**. 이 오귀인이 원장에 사실로 남아 다음 세션의 조사 방향을 잘못 유도했다(로그 경로 포기 → DB 관측만 남김).

**진짜 원인**: `alembic/env.py` 의 `fileConfig(config.config_file_name)` 가 **앱 lifespan 안에서** 실행된다 (`src/main.py:215` `_run_migrations` → `command.upgrade`). `logging.config.fileConfig()` 의 기본값이 `disable_existing_loggers=True` 이고 `alembic.ini` 가 `[logger_root] level = WARN` + stderr 핸들러이므로, 마이그레이션이 앱 로깅 설정을 **통째로 덮어쓴다**.

| 항목 | 마이그레이션 이전 | 이후 |
|------|-----------------|------|
| root level | INFO | **WARNING** |
| root handler | `configure_logging()` 의 stdout 핸들러 | **alembic stderr 핸들러** (우리 것 제거) |
| `uvicorn.access` 로거 | 정상 | **`disabled=True`** ← access log 24h 0건의 정체 |
| `src.*` 로거 INFO | 활성 | **전부 비활성** ← scheduler·cron 로그 소실 |

**운영 로그가 이 기전을 그대로 증언한다** — `[src.main] startup: production hardening = ON`(마이그레이션 **이전**, main.py:213)은 보이고, 바로 다음 줄인 `DB migration completed`(마이그레이션 **직후**, main.py:216)부터 전부 사라진다. 모든 배포에서 동일한 12줄 컷오프가 재현됐다.

**따라서 #1100(로깅 설정 신설)은 운영에서 무력(inert)이었다** — `configure_logging()` 직후 마이그레이션이 즉시 되돌렸기 때문. 단위 테스트는 alembic 상호작용을 재현하지 않아 통과했다.

✅ **수정**: `alembic/env.py` 가 `is_configured()` 로 인프로세스 마이그레이션을 식별해 fileConfig 를 건너뛴다 (alembic CLI 단독 실행은 기존대로). 회귀 가드 = `tests/unit/migrations/test_alembic_env_logging_guard.py` (뮤테이션 실증 — 가드 제거 시 5건 FAIL).

🔴 **교훈**: 관측 부재를 외부 인프라 탓으로 돌리기 전에 **앱 자신이 관측을 끄고 있는지** 먼저 배제하라. "앱 문제 아님" 같은 단정은 반증 실험 없이 원장에 기록하지 말 것.

## 🔴 검증 수단 정정 — "Railway cron 로그 관측"은 실행 불가 (2026-07-18 실측)

`#1073`·`#1075` 는 검증 방법으로 *"Railway cron 로그에서 sweep 실행 확인"* 을 명시했으나, **그 관측 수단이 존재하지 않는다**.

| 실측 (2026-07-18, Railway CLI) | 결과 |
|--------------------------------|------|
| `railway logs --deployment --lines 500 --since 24h` | **총 11줄** — 컨테이너 시작 + alembic 뿐 |
| 같은 로그에서 access log(`"GET`/`"POST`) 건수 | **0줄** (uvicorn `--no-access-log` 아닌데도 미유입) |
| `railway logs --http` 에서 cron 경로 | **0건** — cron 은 `http://localhost:$PORT` 내부 호출이라 엣지 프록시 미경유 |
| cron 실행이 배포 항목으로 기록되는가 | ❌ — 배포 목록은 커밋당 1건뿐 |

→ **cron 실행 여부는 로그로 판별 불가.** 대체 수단 = **cron 으로만 도달 가능한 경로의 DB 부작용 관측**(위 표 참조). `retry-pending-merges` 는 webhook 으로도 트리거되므로 **cron 단독 증거가 되지 못한다**(2026-07-18 실측: `merge_retry_queue` pending 0·16:14 처리 — 정상이나 cron 증거 아님).

관련 실측(같은 날): 수정 전 cron 형태(리터럴 `$INTERNAL_CRON_API_KEY` 전송)를 운영에 재현 → **HTTP 401** 확인(`/health` 200 통제군 대비). `INTERNAL_CRON_API_KEY` 는 Railway 에 **설정돼 있음** → 키가 아니라 셸 미확장이 원인이라는 진단이 운영에서 확정(#1095 로 수정).

## 🔴 집행 기전 (2026-07-19 P0 — 원장이 write-only 였던 자기위반 봉인)

이 원장은 **기계 배선**돼 있다. `scripts/check_owed_verification.py` 가 위 표를 파싱해 **안전등급 ⏳ 미결 건이 있으면 세션 시작 시 loud 경고**하고, 훅 stdout 이 Claude 컨텍스트에 주입된다.

| 요소 | 값 |
|------|-----|
| 실행 주체 | `.claude/settings.json` `hooks.SessionStart` (matcher `startup\|resume`) |
| 판정 | 안전등급 ⏳ ≥1건 → breached (운영등급 미결은 카운트만 보고 — 정책 2 진화 Phase 종료 일괄) |
| 성격 | advisory (비차단·항상 exit 0) — 세션/커밋/PR 미간섭 (정책 17) |
| 회귀 가드 | `tests/unit/scripts/test_check_owed_verification.py` · `test_session_start_wiring.py` |

🔴 **표 형식 변경 시 파서 동반 확인 의무** — 상태 컬럼이 **마지막 셀**, PR 셀이 `**#NNNN**` 형태라는 두 계약에 파서가 의존한다. 형식이 바뀌면 파싱 0행 = 카운터가 무음으로 눈이 먼다(`test_live_ledger_parses_nonempty` 가 이 무음 실패를 차단).

> 🔴 이 원장은 회고 2026-07-18 P1#13(8-PR Wave 종료 시 owed 운영검증 미취합) 조치로 신설됐다. 세션 종료 시 이 원장 갱신이 정책 5 Phase-종료 cross-reference 자가 검토(정책 2/5/8/11)의 하위 체크다.
>
> 🔴 **2026-07-19 회고 P0 — 신설 당시 이 원장은 어떤 집행면에도 배선되지 않은 기록 전용 장치였다.** 회고가 P0 로 규정한 '문서-only 시정은 행동을 못 바꾼다'를 같은 세션에 재생산(3회차)했고, 그 결과 안전등급 2건이 4세션째 ⏳ 로 누적됐다. 위 §집행 기전이 그 시정이다.
