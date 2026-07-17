# SCAManager 전체 분석·검토 보고서 (Grok 플러그인 기반)

**작성일**: 2026-07-17
**대상**: `d:\Source\SCAManager` @ `f2b9b0d` (main, clean)
**규모**: src 246 파일 / 26,533 LOC · 테스트 311 파일 · 문서 153건

---

## 1. 방법론

2단계 교차 검증 구조. Grok이 발견하고, Claude가 반증을 시도했다.

| 단계 | 수행자 | 내용 |
|------|--------|------|
| 1차 발견 | **Grok** (구독 모드, read-only 위임 8건 병렬) | 8개 영역 독립 분석 — 아키텍처 / 보안 / 파이프라인 / DB·마이그레이션 / API·알림 / 테스트 / 문서 정합성 / UI·i18n·배포 |
| 2차 검증 | **Claude** (46 에이전트 병렬, 적대적) | Grok의 P0/P1 46건을 각각 "반증하라"는 지시로 재검토 — 실제 코드·가드·호출처·테스트 전수 확인 |
| 3차 비평 | **Claude opus** (완결성 비평) | "이 리뷰가 놓친 것은 무엇인가" — 미검토 차원 조사 |

전 단계에서 **file:line 실측 인용 없는 발견은 불채택**. 총 47 에이전트 / 541 tool call / 20.9분.

> **Codex mutual 검증은 면제** — 2026-07-10 구독 해지로 실행 파일 부재 (정책 18 폐기). 대체로 Claude 단독 2-layer(다중 에이전트 적대 검증 + opus 완결성 비평)를 적용했다.

---

## 2. 종합 판정

**운영 중인 코드에 즉시 조치가 필요한 P0는 없다.** Grok이 제기한 P0 4건은 검증에서 전부 살아남지 못했다.

| 구분 | Grok 원본 | 검증 후 확정 |
|------|----------:|------------:|
| **P0** | 4 | **0** |
| **P1** | 30 | **4** (신규 1건 포함) |
| **P2** | ~40 | 39 (+3 신규) |
| **반증 / 오탐** | — | **3** |

**Grok의 P0 정밀도는 0/4.** 다만 4건 모두 "완전한 허위"는 아니었다 — 사실관계는 맞았으나 **심각도 과대평가**였다. 3건(E2E CI 미실행 / OAuth 암호화 미검증 / 빈 웹훅 시크릿 401 미테스트)은 전부 "**미래에 누군가 가드를 지우면**"을 전제로 한 회귀 방어 격차이지, 현재 코드의 결함이 아니다. 가드는 모두 존재하고 정상 동작한다.

**Grok의 P1 정밀도는 약 10%** (30건 중 3건 유지). 대부분은 실재하는 사실이지만 구체적 실패 시나리오를 구성할 수 없어 P2로 하향됐다.

**핵심 비대칭**: Grok은 "**있어야 할 것이 없다**"(테스트·재시도·페이지네이션·핀 고정)를 P1으로 분류하는 경향이 강했다. 검증은 "**그래서 무엇이 잘못 동작하는가**"를 요구했고, 대부분 답이 없었다. 이는 Grok이 틀렸다기보다 **성숙한 코드베이스에서 정적 리뷰가 부딪히는 한계**다 — 남은 것은 대체로 진짜 위험이 아니라 방어 심도의 여지다.

---

## 3. 확정 P1 — 조치 권장 4건

### P1-1. 🔴 분석 SHA ↔ 머지 SHA 미결속 (stale-score 머지)

- **위치**: `src/gate/engine.py:167,175` · `src/gate/engine.py:416-418`(legacy) · `src/webhook/providers/telegram.py:182-185`(semi-auto)
- **문제**: auto-merge가 **분석이 끝난 시점에 PR head를 새로 조회**해서 그 SHA로 머지한다. `Analysis.commit_sha`는 게이트로 전달조차 되지 않는다 (`grep -rn "commit_sha" src/gate/` → 읽는 곳 0).
- **시나리오**: 커밋 A 분석 시작(정적 60s + AI 리뷰) → 도중 커밋 B push → A의 점수 95로 게이트 통과 → head 조회 = **B** → `expected_sha=B`로 머지 성공. **분석된 적 없는 B가 A의 점수로 main에 머지된다.** `expected_sha=B`가 오히려 "틀린 커밋이 원자적으로 머지되도록" 보장한다.
- **Grok이 놓친 더 나쁜 경로**: **semi-auto(Telegram) 경로는 레이스조차 필요 없다.** `telegram.py:90`은 `analysis` 행을 이미 로드해서 `commit_sha`를 손에 쥐고도 `:182`에서 버린다. 승인 버튼 HMAC(`:70`)은 **만료가 없어** 몇 시간 뒤 눌러도 그 시점의 head를 머지한다. Grok은 이 경로를 인용하지 않았다.
- **P0이 아닌 이유**: 현 배포는 단일 소유자(xzawed) 저장소 + fork PR 없음 + branch protection 부재 → 잘못 머지되는 커밋은 소유자 본인의 다음 push다. 보안 경계를 넘지 않고 사고 기록도 없다. 재시도 큐 구간은 `sha_drift` + `expected_sha=row.commit_sha`로 **이미 봉인돼 있다** — 노출은 "분석→head 관측" 구간뿐.
- **수정**: `GateContext`에 `commit_sha` 추가 → `_run_auto_merge(analyzed_sha=...)` → `head_sha != analyzed_sha`면 머지 중단(다음 synchronize 분석이 새 head를 게이트하므로 손실 없음). legacy·semi-auto 양 경로 동일 적용. `expected_sha=analyzed_sha`로 넘기면 GitHub가 직접 거절해 기존 #962 SHA 원자성 계약으로 수렴한다.
- **비고**: `.claude/rules/api.md`의 "재시도는 검증자가 승인한 정확한 SHA만 머지한다"는 단언은 **검증자 기준으로는 참**이나 `Analysis.commit_sha` 결속은 주장한 적 없다 → 문서화된 수용 위험이 아니라 **미문서화 격차**.

> Grok의 `PIPE-P0-1`과 `PIPE-P1-5`는 별개 항목으로 보고됐으나 **동일 근원**이다. Grok은 이를 "재시도 큐 결함"으로 오귀속했다 — 실제 결함은 전적으로 `engine.py:167`(관측 ≠ 분석)에 있고, 큐는 이미 틀린 SHA를 충실히 운반할 뿐 창을 넓히지 않는다.

### P1-2. 🔴 워커 내구성 부재 — 재배포/크래시 시 분석 조용히 소실 *(신규 — Grok 미발견)*

- **위치**: `src/webhook/providers/github.py:350-351` · `src/worker/pipeline.py:582,827-828`
- **문제**: 분석 파이프라인 전체가 **in-process FastAPI BackgroundTask**로 돈다. 내구 큐가 없다. `background_tasks.add_task(run_analysis_pipeline, ...)` 직후 GitHub에 **200을 먼저 반환**한다. 유일한 내구 기록은 `analysis_repo.save_new`(`:582`)인데, 이는 `_collect_files`와 Claude API 호출(timeout 60s, max_retries=2)이 **끝난 뒤**에야 도달한다.
- **시나리오**: 그 수 분간의 창에서 SIGTERM(Railway 재배포 — 빈번)·OOM·크래시 발생 → Analysis 행 없음 · 재시도 없음 · **GitHub는 이미 200을 받았으므로 재전송 없음**. `:827-828`은 `Exception`을 광범위하게 잡아 `logger.exception`만 한다 — dead-letter도, 실패 행도 없다. `:418` 중복제거는 Analysis 존재로 판단하므로 "시도했음"을 남기는 것조차 없어 **구멍을 탐지할 방법이 없다**.
- **왜 중요한가**: 이것은 Grok이 보고한 모든 정확성 findings의 **하부 전달 보장**이다. "auto-merge가 live head에 결속된다"를 고쳐도 분석이 아예 실행되지 않으면 무의미하다. 게다가 실패가 **조용하고 편향적**이다 — 가장 오래 걸리는 분석(큰 PR, 느린 Claude 호출)이 정확히 가장 죽기 쉽고, 분석이 증발한 PR은 "아직 분석 안 됨"과 영원히 구별되지 않는다.
- **수정**: 비싼 작업 **이전에** "attempted" 행을 쓰거나(최소), 내구 outbox/큐 도입(정공법). 기존 `merge_retry_service`는 머지 단계 전용이라 분석 단계를 커버하지 않는다.

### P1-3. 🟠 NULL-owner 저장소 IDOR — 로그인한 누구나 제어 가능

- **위치**: `src/ui/_helpers.py:62-69` · `src/ui/routes/overview.py:48-49`
- **문제**: `get_accessible_repo`는 `repo.user_id is not None and != current_user.id`일 때만 거부한다. **`user_id IS NULL`인 저장소는 모든 인증 세션을 통과한다.**
- **시나리오**: 공격자가 GitHub OAuth로 가입(`auth/github.py:98` — 무조건 User 생성) → `GET /` 에서 타인 저장소 노출 → `POST /repos/victim%2Fapp/settings`로 `auto_merge=on, merge_threshold=0, discord_webhook_url=<공격자 URL>` 설정(**타인 저장소의 모든 PR 자동 머지 + 알림 탈취**) → `POST /repos/victim%2Fapp/delete`로 GateDecision·Analysis·RepoConfig·Repository **영구 삭제**(GitHub 웹훅 DELETE는 실패하나 `_helpers.py:80-86`이 삼키고 DB cascade는 진행 → 데이터 손실 + 고아 웹훅 잔존).
- **Grok보다 나쁜 실상 (검증에서 발견)**: "legacy"라는 라벨은 **부정확하다**. NULL-owner는 동결된 과거 집단이 아니라 `src/worker/pipeline.py:401-403`이 **미등록 저장소 웹훅마다 계속 새로 생성한다**. 모집단이 정상 운영 중 증가한다. Grok은 인용한 2개 파일만 읽고 문서의 "legacy" 라벨을 그대로 물려받았다.
- **P0이 아닌 이유**: 두 번째 인간이 이 배포에 로그인해야 성립. 현 운영 현실은 단일 테넌트.
- **참고**: 코드베이스가 **이미 이 문제를 P1으로 인지**하고 있다 — `src/ui/routes/add_repo.py:120-129`에 "🔴 소유권 이전 전 GitHub 접근 검증 (WBS P1 — IDOR-인접)" 주석 존재.
- **수정**: NULL-owner 저장소는 admin 전용으로 제한하거나 GitHub 멤버십 검증 후 auto-claim. 최소한 비소유자 **쓰기**(settings/delete) 차단.

### P1-4. 🟡 SMTP 587 + `use_tls=True` → 이메일 채널 100% 실패

- **위치**: `src/notifier/email.py:140-147` (기본 포트 `src/config.py:85`)
- **문제**: `aiosmtplib.send(port=587, use_tls=True)`는 바이트 0에서 TLS ClientHello를 던진다. 587은 STARTTLS 포트라 평문 배너(`220 ... ESMTP`)로 응답 → 핸드셰이크 실패. 자동 STARTTLS 폴백(`smtp.py:553`)은 `not self.use_tls` 뒤에 있어 **절대 실행되지 않는다**.
- **시나리오**: 문서화된 설정 그대로(`docs/reference/env-vars.md:78`의 `smtp.gmail.com` 예시 + 기본 587) 따르면 **모든 이메일 알림이 100% 실패**한다. 예외는 `gather(return_exceptions=True)`가 삼키고 로그만 남으므로, 운영자는 "이메일이 안 온다"만 볼 뿐 UI 신호가 없다.
- **P0이 아닌 이유**: SMTP 미설정 시 휴면(`.env.example:49`에서 `SMTP_HOST` 비어 있음 → `is_enabled` False).
- **수정**: `use_tls=(port == 465)`, `start_tls=(port != 465)`. **`use_tls=False` 단독은 위험** — 서버가 STARTTLS를 광고하지 않으면 자격증명과 리포트를 **평문 전송**한다. `start_tls=True`를 명시해야 fail-closed. (`use_tls=True` + `start_tls=True` 동시 지정은 `ValueError`.)

---

## 4. 반증된 3건 — Grok 오탐

| ID | 주장 | 반증 근거 |
|----|------|----------|
| `ARCH-P1-6` | merge_retry_repo가 도메인 정책을 데이터 계층에 보유 (계층 위반) | **의견이며 사실관계가 거꾸로.** lease 원시연산은 양 방언에서 정확하고 테스트로 증명됨 — `test_merge_retry_repo.py` claim_batch 테스트 10건 + `test_retry_concurrency_postgres.py` 실 Postgres 2-스레드 배리어 동시성 증명. 오작동 시나리오 구성 불가. |
| `TEST-P1-2` | engine auto-merge 테스트가 `expected_sha` 배선을 단언하지 않음 | **뮤테이션 테스트로 반증.** `expected_sha=head_sha` 삭제 시 → `native_automerge.py:145-150`이 스스로 head를 조회해 `merge_pr`에 전달. PUT body에 여전히 `sha`가 실려 GitHub가 force-push된 head를 409로 거절. 자체 조회마저 실패하면 `:163-170`이 terminal NETWORK_ERROR 반환 + **머지 시도 자체를 안 함**. |
| `TEST-P1-5` | Telegram 게이트 스위트가 claim 성공을 자동 스텁 → replay 가드 회귀가 통과 | **3종 회귀 모두 실패로 잡힘.** 가드 삭제 → `test_telegram_provider.py:234` 실패. 심볼 리네임 → `test_gate_callback_seam_realdb.py:105` 실패(사이클 165 회고 P1-2로 이 시나리오 전용 제작됨). first-writer-wins 파괴 → 실 DB seam 테스트 실패. |

---

## 5. Grok이 놓친 영역 (완결성 비평)

| 영역 | 판정 | 요지 |
|------|------|------|
| **워커 내구성** | **P1** | → §3 P1-2. 8개 차원 중 어느 것도 파이프라인 *전달 보장*을 보지 않았다 (정확성만 봄). |
| 웹훅 폭주 시 동시성 한계 | P2 | 파이프라인 *내부*는 잘 제한됨(`pipeline.py:196-232` 순차 실행 + deadline). 그러나 **전역 한계 없음** — src/ 전체에 Semaphore 0. N개 동시 웹훅 = N개 파이프라인 × (스레드 + 분석 subprocess + Claude 호출) on 단일 컨테이너. 내구성 격차와 복합: 폭주 → OOM-kill → 진행 중 전부 조용히 소실. 비용 벡터이기도 함(`ai_review_enabled` 킬스위치는 *여부*를 통제하지 *동시 개수*를 통제하지 않음). |
| 데이터 보존 / PII 수명주기 | P2 | **보존 정책이 코드 어디에도 없다.** `Analysis.result`가 고객 소스코드 파생물(`ai_summary`/`security_feedback`/`file_feedbacks` + `author_login` 귀속)을 **무기한** 저장. 유일한 삭제 경로는 저장소 제거 시 `delete_by_repo_id` 뿐. `claude_api_calls`도 무한 증가. purge job 없음. → NULL-owner IDOR(§3 P1-3)이 **만료되지 않는 코퍼스**에 대해 훨씬 나쁘게 작용. |
| MCP 서버 표면 | P2 | `src/mcp/repo_report_tools.py`는 **유령 표면** — 스키마 dict만 있고 서버·디스패처·실행기·import 전부 없음(사실상 dead code). 그런데 `docs/architecture.md:128`은 살아있는 아키텍처로 등재. Grok의 문서 drift 클러스터(backfill_author.py 유령, Sentry 유령)가 놓친 4번째 항목. 잠재 함정: 누군가 실행기를 연결하는 날 검증 없는 `days` 파라미터(1~365 제약이 **설명 문자열에만** 존재)와 **테넌트 스코프 전무**를 그대로 물려받는다. |
| 타임존/datetime 정합성 | **이상 없음** | 조사 후 명시적 클리어. src/ 전체에 naive `utcnow()`/bare `now()` **0건** — 전부 `datetime.now(timezone.utc)`. `retry_policy.py:146-150`은 aware/naive 비교를 의도적·명시적으로 처리. cron은 `now` 주입 가능. |

---

## 6. 건전성 확인된 영역 (실측 증명)

Grok이 **긍정 통제도 함께 실측**한 점은 이 리뷰의 신뢰도를 높인다.

- **은닉/악성 코드: CLEAN** — 백도어·exfiltration·난독화·타임밤·매직 토큰·하드코딩 프로덕션 시크릿 **0**. `eval`/`exec`/`pickle`은 리뷰 가이드 *텍스트*에만 등장(실행 안 됨). 분석기 `subprocess.run`은 전부 list argv(`shell=True` 없음).
- **웹훅 HMAC**: timing-safe(`secure_str_compare`) + 빈 시크릿 → 401 fail-closed. Telegram도 fail-closed.
- **세션**: `httponly` + `SameSite=lax` + prod `https_only` + 세션 고정 방지(`session.clear()` 선행).
- **SHA 멱등성 + 레이스 복구**, AI `api_error`/`parse_error` 시 auto-merge/approve **fail-closed**, 절단 마커(`ai_review_truncated`) 동작.
- **마이그레이션 체인**: 단일 head **0044**, 43개 리비전 분기 없음. ORM 컬럼 중 마이그레이션 누락 **0**. `env.py`가 12개 모델 전부 등록해 autogenerate `drop_table` 차단.
- **로케일 파리티**: en/ko/ja = **816/816/816**, 대칭 차집합 **0**. 템플릿 사용 키 601개 중 누락 **0**.
- **STATE ↔ README 수치 정합**: 5421 / 5267+154 / E2E 122 / pylint 10.00 / 97% — `pytest --collect-only` 실측과 일치.
- **의존성**: Python 전부 `==` 핀 고정.
- **정적 자산 `no-cache` + ETag**: 결함이 아니라 **의도된 설계**(#938 학습)임을 Grok이 정확히 식별.

---

## 7. 권장 조치 순서

| 순위 | 항목 | 근거 |
|:----:|------|------|
| 1 | **P1-2 워커 내구성** — 최소 "attempted" 행을 비싼 작업 *이전*에 기록 | 다른 모든 정확성 수정의 하부 토대. 현재는 소실을 **탐지조차 불가**. |
| 2 | **P1-1 분석 SHA 결속** — `GateContext.commit_sha` + drift 시 fail-closed | 유일하게 "잘못된 머지"를 만들 수 있는 확정 결함. semi-auto 경로는 레이스도 불필요. |
| 3 | **P1-4 SMTP 587** — `start_tls=(port != 465)` | 결정론적 100% 실패이고 수정이 한 줄. 단, 채널 미사용이면 우선순위 하락. |
| 4 | **P1-3 NULL-owner 쓰기 차단** | 현 단일 테넌트에선 잠복. **다중 사용자 개방 전 필수 선결**. |
| 5 | P2 문서 drift 묶음 (FastAPI 배지 0.136→0.139.0 · STATE 11→12종 · language-coverage 매트릭스 · backfill_author.py/Sentry/MCP 유령 3건) | 저비용·저위험. 단일 docs PR로 일괄. |

**P0가 없으므로 긴급 대응은 불필요하다.** 1·2번은 별도 PR로, 5번은 docs 일괄 PR로 처리하는 것을 권장한다.

### 7.1 이번 세션 처리 범위 + 백로그 결정 (2026-07-17 사용자 결정)

| 항목 | 결정 | 상태 |
|------|------|------|
| **P1-1 SHA 결속** | 이번 세션 수정 | ✅ 진행 |
| **P1-4 SMTP 587** | 이번 세션 수정 | ✅ 진행 |
| **P1-2 워커 내구성** | **최소안 채택** — 비싼 작업(파일 수집·Claude 호출) *이전에* Analysis를 pending 상태로 선기록. 마이그레이션 1개(상태 컬럼)로 소실을 **탐지 가능**하게 만든다. 정공법(내구 outbox/큐)은 미채택 — 워커 프로세스 분리·스케줄러가 필요해 Railway 단일 컨테이너 구조와 충돌, 사실상 별도 Phase. | 🔜 백로그 (방향 확정) |
| **P1-3 NULL-owner IDOR** | **쓰기만 차단 채택** — NULL-owner 저장소의 settings 변경/삭제 차단, 조회는 현행 유지. admin 전용·auto-claim은 미채택(본인 저장소가 안 보이거나 외부 API 의존이 생겨 운영 흐름이 바뀔 위험 > 단일 테넌트 현 시점 이득). | 🔜 백로그 (방향 확정) |

> P1-2·P1-3은 **방향만 확정된 미착수 항목**이다. 재검토 없이 이 결정대로 진행 가능하되, 착수 시점에 전제(단일 테넌트 여부, Railway 구조)가 여전히 유효한지 1줄 확인할 것.

---

## 8. 이 리뷰의 한계 (정직한 고지)

- **정적 분석만 수행했다.** 테스트를 실행하지 않았고, 운영 endpoint smoke check(정책 13)·8조합 시각 검증(정책 11)·MCP 실측(정책 12)은 하지 않았다. **CI green ≠ 운영 정상**이며, 이 보고서의 어떤 판정도 운영 검증을 대체하지 않는다.
- **심각도 보정은 "이 배포에서 실제로 일어날 수 있는가"를 P0 기준으로 삼았다.** 이 기준 때문에 E2E CI 미실행·OAuth 암호화 뮤테이션 격차 같은 **방어 심도** 항목이 P2로 내려갔다. 이들은 실재하는 격차이며, "P2 = 무시해도 된다"는 뜻이 **아니다** — "오늘 깨진 것은 없다"는 뜻이다. 특히 E2E가 CI에서 한 번도 안 도는 것은 이 프로젝트의 사고 이력(hx-boost 클로저 오염 #1039, 차트 레이스, count-up 고착)과 정확히 겹치는 클래스다.
- **Grok 보고서 원본 8건은 스크래치패드에 보존**: `grok-01-architecture.md` ~ `grok-08-ui-i18n-deploy.md`.
