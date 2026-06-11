# 사이클 166~#859 회고 (5+1 다중 에이전트 + cross-verify)

> **일자**: 2026-06-11
> **대상 구간**: PR #820~#859 (직전 5+1 회고 = 2026-06-03 사이클 156~157)
> **방식**: 정책 8 — 5 관점 분리 병렬 디스패치 (코드회귀 / 프로세스·정책 / 문서정합 / 테스트·CI / 보안·운영) + cross-verify 6차 (general-purpose) + 종합/자유발언 (정책 9). read-only.
> **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" → 잔여 sweep 후 사용자 결정 C (회고 진행).

대상 라운드: Task9 full 감사 P2 백로그(#820~#836) · 적대 재검증(#838~#841) · 잔여작업 라운드(#843~#846) · RLS Phase 2~4 코드(#847~#851) · 정합성 감사 follow-up(#852~#856) · 2nd-LLM 머지 검증자(#859).

---

## 0. 테스트 카운트 실측 (정책 8 진화 3 — 추정 금지)

`pytest --collect-only -q` 실측 (2026-06-11):

| 범위 | 수집 | STATE 헤더 | 정합 |
|------|------|-----------|------|
| 전체 `tests/` | 5018 | 5018 | ✅ |
| 단위 `tests/unit` | 4864 | 4864 | ✅ |
| 통합 `tests/integration` | 154 | 154 | ✅ |

검증식 4864 + 154 = 5018 ✅. README.md:21 배지도 정합. **추정 0건, 전수 실측.**

---

## 1. 잘된 점 (관점별 핵심)

- **RLS worker 세션 라우팅(#847~#850)** — `tests/unit/test_worker_session_routing.py` 가 ast 전수 inventory(`_WEB_DB_MODULES`/`_BACKGROUND_MODULES`/`_SYSTEM_API_MODULES`/`_HYBRID_DB_MODULES`)로 src 전체 SessionLocal-import 파일을 양방향 분류 강제 — 미분류 신규 import 자동 fail. hybrid 모듈 엔드포인트별 분기까지 sentinel 가드 커버.
- **AI-fail NULL-persist(#853)** — `pipeline.py` `_ai_failed` 게이트가 score/grade 컬럼만 NULL 저장, result dict 진단은 보존 (hook #25/#814 와 정확한 대칭). `no_api_key`/`empty_diff` 제외로 회귀 방지.
- **claim_decision 원자화(#811)** — insert-only + UNIQUE(analysis_id) first-writer-wins, update 분기 부재로 결정 뒤집기 원천 차단 (사이클 165 Codex TOCTOU 학습 반영).
- **merge_verifier fail-closed(#859)** — 3중 try/except + 최외곽 catch-all 로 모든 실패를 차단 verdict 로 귀결. kill-switch 우선 + 순수 opt-in (OPENAI_API_KEY 미설정 시 비용 0). prompt-injection `<untrusted-data>` 경계. `merge_verifier_band` `Field(ge=1)` silent-무효화 방어.
- **RLS FORCE 실측(#848, 0041)** — `relforcerowsecurity` bound-param IN 절 실측 + `connection_bypasses_rls` 로 Phase 3~4 거짓안심 창 가시화.
- **프로세스** — 정책 18 Codex push 전 mutual 전 구간 일관 준수 (push 후 의뢰 안티패턴 0건). 6-step §⑤⑥ sync PR 일관 수행. 정책 10 @- 사고 재발 방지 가드 즉시 제도화(#846). 정책 12 MCP scope 준수.

---

## 2. 발견 사항 (P0 / P1 / P2 — cross-verify confirmed)

cross-verify: 5 관점 24 findings 중 **22 TRUE · 1 위양성**(db-migration.md drift = 동시 진행 docs PR 이 이미 정정 → 위양성 처리) · 1 카운트 오기(worker-routing well_done 81→실측 66, substance 무영향). 신규 위음성 P1 1건(반자동 parity ↔ 테스트 갭 동일 근원).

### P0
| # | 제목 | owner | next action |
|---|------|-------|------------|
| P0-1 | 정책 10 본문 @- 소실 — PR #838~#845 본문 8건이 리터럴 `@-` 로 GitHub 기록 전소 (#839만 회복, 7건 UI 상 미회복) | Claude + 사용자 | 7건 `gh pr view --json body` 길이 전수 재확인 + 누락분 `gh pr edit --body-file` 회복 / 정책 10 검증을 PostToolUse hook 자동 가드로 승격 검토 |

### P1 (8건)
| # | 제목 | owner | 비고 |
|---|------|-------|------|
| P1-1 | 2nd-LLM 검증자 반자동(Telegram) auto-merge 경로 우회 — 자동/반자동 parity 갭 + 동일 근원 테스트 갭 | Claude(옵션 표) + 사용자(설계 confirm) | INACTIVE 라 잠재. 키 활성화 전 봉인 의무. 안 A(검증자를 `engine._run_auto_merge` 진입부 단일출처화) 권장 |
| P1-2 | secret dangling commit `7d0fa1fe` 2026-06-11 현재도 gh api 200 OK — purge 미반영 5+사이클 방치 | 사용자(결정) | NEW-P0-N 스테일 블로커. (a)Support 재요청 / (b)revoke 완료=실위험0 보류 봉인 |
| P1-3 | Code Scanning open alert #504 (`openai_metrics.py:32` py/ineffectual-statement, FP) dismiss 없이 open — #859 가 open 0→1 회귀 | Claude(즉시 처분) | `await result` 부수효과 = CodeQL FP. dismiss + 사유 (정책 14) |
| P1-4 | merge_verifier PR diff 무제한(no token/size cap) OpenAI 전송 — 대형 PR 비용 폭증 + context-limit fail-closed 오차단 | Claude(활성화 전 cap) + 사용자(시점) | INACTIVE 라 잠재. build_verifier_prompt diff cap + max_completion_tokens 명시 |
| P1-5 | `.env.example` OPENAI_API_KEY 주석 stale ('Production 사용 X' 오정보) — STATE.md:5 와 모순 | Claude | **본 docs PR 에서 정정 완료** ✅ |
| P1-6 | STATE overclaim self-caught 실패 — '#2 외 전부 해소' 미검증 단언이 사용자 재요청 적대 재검증으로만 적발 | Claude | 완료 선언 직전 정책8 5+1 1 도메인을 'STATE 범위↔실코드 대조' 고정 배정 |
| P1-7 | 정책 8/9 회고 미수행/미보관 — 사이클 158 이후 아카이브 회고 0건 | Claude | **본 회고 보고서가 첫 해소** ✅ + 통합 회고 여부 사용자 결정 |
| P1-8 | 임시 PW 평문 채팅 노출 — Phase 4 전까지 운영 DB 접속 credential(worker=BYPASSRLS) 미교체 | 사용자(즉시 교체) + Claude(runbook 게이트) | Phase 4 무관 독립 — 지연 = 노출 창 연장 |
| P1-9 | `.env.example` MERGE_VERIFIER_BAND/OPENAI_VERIFIER_MODEL 미등재 (env-vars.md 에는 등재, 비대칭) | Claude | **본 docs PR 에서 추가 완료** ✅ |

### P2 (주요)
- interpret_verdict `bool(raw['safe'])` 가 문자열 'false'→True 오변환 fail-open 미세 경계 → `is True` 엄격 파싱 (INACTIVE 라 P2)
- `_call_via_http` httpx fallback 미테스트 — ImportError 분기 커버리지 갭 (검증자 fail-closed 직결)
- main CI `-q` 단독 → PG-gated 7건 silent skip 비가시 + pg-concurrency node-id drift 침묵 위험 → `-rs` + 수집 노드 수 단언
- verifier-차단 auto-merge 가 MergeAttempt DB 미기록 — VERIFIER_BLOCKED/ERROR 관측 row 0 (거버넌스 감사 갭, descope 의도)
- verifier reasons PR 코멘트 sanitize 부재 (try/except 격리로 심각도 낮음)
- claim_decision semi-auto score NULL fallback 암묵 의존 (주석 1줄 권장)
- env-vars.md 내부상수표 WEBHOOK_SECRET_CACHE_MAX/OPENAI_VERIFIER_TIMEOUT 누락 → **본 docs PR 에서 추가 완료** ✅
- 'background UX silent' soft-close 항목 차기 재확인 미수행 (cycle-history 주석에만 잔존)
- 정책 11 8조합 체크리스트 일괄 회신 누적 대기 (#822/#823/#824/#827/#839/#856)
- 의존 핀 정책 혼재(== vs >=) — lock 파일/상한 핀 검토 (사용자 결정 영역)
- pip install timeout/retry 복원력 부재 — #859 transitive 추가로 flaky 노출면 증가

---

## 3. 자유 발언 (정책 9)

### 바라는 점
1. **2nd-LLM 검증자(#859) 활성화 의향+시점** — 현재 INACTIVE. 키를 켜는 순간 P1-1/P1-4/interpret_verdict 가 P1 로 격상. '활성화 전 봉인' 권장.
2. **RLS Phase 4 + 임시 PW** — 코드 완료, 운영 게이트는 사용자 영역. 채팅 평문 PW 는 Phase 4 와 무관하게 즉시 교체 권장 (노출 창).
3. **통합 회고** — 사이클 158~166 + #838~#859 사후 통합 회고 1회 진행 여부 결정.

### Claude 자성
- **STATE overclaim self-caught 실패** — '완료 선언'과 '검증'을 분리 못 한 정책 4 위반. 사용자 재요청으로만 #32 위양성 적발.
- **정책 10 @- 재발** — 2026-06-10 학습 직후 구간(#838~845)에서 8건 재발. 수동 의무의 한계.
- **추정 카운트** — 본 회고 1차 well_done 의 worker-routing 81을 추정 보고 → cross-verify 가 실측 66 으로 정정. 정책 8 진화 3을 well_done 에까지 적용 못 함.
- **다음 사이클 개선 약속**: (a) 완료/STATE 범위 단언 직전 5+1 1 도메인 'STATE↔실코드 대조' 고정 self-verify (b) 정책 10 검증 자동 가드 승격 검토 (c) 감사 항목은 리포트 지목 EXACT line Read 확인 후 confirmed.

### 필요한 부분 (결정 입력)
1. dangling commit `7d0fa1fe` purge — (a)재요청 / (b)보류 봉인.
2. 검증자 활성화 의향+시점.
3. 임시 PW 즉시 교체 결정.
4. 의존 핀 정책 변경 의향 (확인 시 옵션 표 제시).

### 수정 제안
| 영역 | 제안 |
|------|------|
| 정책 10 자동화 | PR 본문 길이 검증을 PostToolUse hook 자동 가드로 승격 (수동 의무 8건 침묵 누락 방지) |
| STATE 범위 단언 | 종료 선언 직전 5+1 1 도메인 'STATE↔실코드 EXACT line 대조' 고정 + 정책18 §4 4번째 조건 검토 |
| 검증자 활성화 게이트 | 봉인 체크리스트(반자동 parity·diff cap·엄격 파싱·fallback 테스트)를 키 설정과 페어링 |
| 회고 정기화 | 정책5/9 종료 신호에 '회고 아카이브 여부' 체크 + 단일일 PR≥18 트리거 통합 회고 |
| CI PG 가시성 | 메인 잡 `-rs` + pg-concurrency 수집 노드 수 단언 (회귀 가드 누락 시 침묵 방지) |

---

## 4. 후속 처리 분류

- **본 PR 처리 완료** (docs 정합): P1-5(.env.example 주석)·P1-9(검증자 env)·P2(env-vars 내부상수)·P1-7(본 회고 아카이브).
- **Claude 자율 후속**: P1-3(#504 dismiss)·P0-1(7건 본문 회복)·P2 CI/테스트 하드닝.
- **사용자 결정 영역**: P1-1(검증자 parity 설계 confirm)·P1-2(purge)·P1-4(검증자 활성화)·P1-8(PW 교체)·의존 핀 정책.
