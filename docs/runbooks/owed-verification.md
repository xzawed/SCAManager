# 미결 운영 검증 원장 (Owed Operational Verification Ledger)

> **목적**: 코드로 증명 불가한 운영/외부 검증(HSTS 헤더·쿠키 Secure·cron 실제 실행·외부 API 계약·DELETE 실행·이메일 실제 발송 등)을 남긴 PR 을 **append-only** 로 추적한다. 머지 = 코드 결정 종결이나, 운영 검증 증거는 사용자가 OK/NG 를 찍기 전까지 미결로 유실될 수 있다(회고 2026-07-18 P1#13·P2#31·P2#38).
>
> **작성 규칙**: 세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다(trailing sync PR body 의 §owed-verification 표와 페어). 사용자 회신(OK/NG/미수행) 전까지 **행 삭제 금지**(append-only). 정책 2 진화(Phase 종료 일괄 회신) + 정책 13(smoke check) + 정책 5 NEW-P0-N(안전등급은 매 사이클 회신 의무) 페어.
>
> **상태 범례**: ⏳ 미검증(사용자 회신 대기) · ✅ 검증 완료(OK) · ❌ 이슈 발견(NG) · ⏭️ 사용자 미수행(보류)

---

## 🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1058** | SMTP 이메일 **실제 발송** — 587 STARTTLS 수정 전까지 **출시 이래 100% 실패**였음. 수정이 실발송을 복구했는지 코드로 증명 불가 | **어떤 메일?** = 리포 **Settings → 알림 채널 → Email(`email_recipients`)** 에 설정한 수신 주소(쉼표 분리 가능). **선행 조건**: 운영 env 에 SMTP 4종(`SMTP_HOST`·`SMTP_PORT`=587·`SMTP_USER`·`SMTP_PASS`) 설정 + 해당 리포 `email_recipients` 채워짐(둘 중 하나라도 비면 채널 자체 비활성 → 발송 시도 없음). **절차**: 그 리포에 push/PR 이벤트 유발 → **`email_recipients` 주소의 수신함**에 `[Code Review]` 제목 메일 도착 확인. 대안: Railway 로그에서 SMTP `250` 응답(또는 `_use_start_tls`/`use_tls` 경로 진입) 확인 | 5·13 | ⏳ |
| **#1062** | NULL-owner 저장소 **쓰기 차단(IDOR)** 과잉 차단 여부 — 정상 소유자 흐름이 403 로 오차단되지 않는지 | 정상 소유 저장소에서 설정 변경·피드백 등 7 쓰기 라우트가 200 정상 동작 확인(운영 계정) | 15 | ⏳ |

## 운영/외부 계약 등급 (Phase 종료 일괄 회신 — 정책 2 진화)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1071** | prod 하드닝 — HSTS 헤더·쿠키 Secure·`/docs` 비노출이 Railway(https)에서 적용되는지 | `curl -I https://<app>/` → `Strict-Transport-Security` 헤더 존재 + `Set-Cookie … Secure` + `GET /docs` → 404 | 13 | ⏳ |
| **#1072** | approve SHA 결속 — head 이동 PR 에 approve 시도 시 GitHub **422 fail-closed** (외부 계약 미검증) | head 가 이동한 PR 에 반자동 approve 유발 → GitHub 422 반환 + gate 가 차단하는지 운영 로그 관측 | 13 | ⏳ |
| **#1073** | orphan sweep cron **실제 실행** — `analysis_attempts` 소실 탐지·표면화·정리 | 🔴 **로그 관측 불가 → DB 관측 대체**(§검증 수단 정정). `SELECT COUNT(*) FROM analysis_attempts WHERE started_at < NOW() - INTERVAL '1 hour'` = 0 유지면 정상. **2026-07-18 17:23 UTC 실측 = 총 0행**(관측 가능한 잔여물 없음 — 판별 보류) | 13 | ⏳ |
| **#1075** | retention sweep cron **실제 DELETE** — 만료 캐시·종결 큐 GC | 🔴 **로그 관측 불가 → DB 관측 대체**. `SELECT COUNT(*) FROM insight_narrative_cache WHERE expires_at < NOW()` — **2026-07-18 17:23 UTC 실측 = 8건 잔존**(최고령 만료 2026-05-05·74일). 매일 20:00 UTC 스케줄 실행 후 **0 이 되면 cron 실동작 확정** ← 현재 유일한 깨끗한 단독 테스트 | 13 | ⏳ |

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
