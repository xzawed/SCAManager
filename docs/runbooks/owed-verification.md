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
| **#1058** | SMTP 이메일 **실제 발송** — 587 STARTTLS 수정 전까지 **출시 이래 100% 실패**였음. 수정이 실발송을 복구했는지 코드로 증명 불가 | 이메일 알림 활성 리포에서 push/PR 이벤트 유발 → 수신함에 실제 도착 확인. 또는 Railway 로그에서 SMTP 250 응답 확인 | 5·13 | ⏳ |
| **#1062** | NULL-owner 저장소 **쓰기 차단(IDOR)** 과잉 차단 여부 — 정상 소유자 흐름이 403 로 오차단되지 않는지 | 정상 소유 저장소에서 설정 변경·피드백 등 7 쓰기 라우트가 200 정상 동작 확인(운영 계정) | 15 | ⏳ |

## 운영/외부 계약 등급 (Phase 종료 일괄 회신 — 정책 2 진화)

| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |
|----|----------|----------|------|------|
| **#1071** | prod 하드닝 — HSTS 헤더·쿠키 Secure·`/docs` 비노출이 Railway(https)에서 적용되는지 | `curl -I https://<app>/` → `Strict-Transport-Security` 헤더 존재 + `Set-Cookie … Secure` + `GET /docs` → 404 | 13 | ⏳ |
| **#1072** | approve SHA 결속 — head 이동 PR 에 approve 시도 시 GitHub **422 fail-closed** (외부 계약 미검증) | head 가 이동한 PR 에 반자동 approve 유발 → GitHub 422 반환 + gate 가 차단하는지 운영 로그 관측 | 13 | ⏳ |
| **#1073** | orphan sweep cron **실제 실행** — `analysis_attempts` 소실 탐지·표면화·정리 | Railway cron 로그에서 orphan sweep 실행 + `INTERNAL_CRON_API_KEY` 설정 확인(미설정 시 무음 중단) | 13 | ⏳ |
| **#1075** | retention sweep cron **실제 DELETE** — 만료 캐시·종결 큐 GC | Railway cron 로그 `retention sweep — purged expired_cache=N terminal_queue=N` 관측 + pending 행 보존 확인 | 13 | ⏳ |

---

## 회신 방법

사용자는 각 행의 상태를 `✅/❌/⏭️` 로 갱신하거나, Claude 에게 결과를 전달하면 Claude 가 갱신한다. `❌`(NG) 발견 시 = 즉시 fix PR 착수(정책 7). 전 행 `✅`/`⏭️` 확정 시 = 원장에서 **아카이브 섹션으로 이동**(본 상단 표는 미결만 유지).

> 🔴 이 원장은 회고 2026-07-18 P1#13(8-PR Wave 종료 시 owed 운영검증 미취합) 조치로 신설됐다. 세션 종료 시 이 원장 갱신이 정책 5 Phase-종료 cross-reference 자가 검토(정책 2/5/8/11)의 하위 체크다.
