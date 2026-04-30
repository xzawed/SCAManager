# SCAManager 12-에이전트 종합 감사 보고서 (2026-04-30)

## 개요

사용자 요청 — "전체 에이전트가 전체 코드를 세세하게 검토하고 토의 및 모의 테스트를 진행하여 가장 이상적이고 정확한 수행 작업 프로세스로 이뤄져 있는지, 코드 정돈 + 효율적 배치, 속도/품질 저하 이슈를 10번 이상 검증한 후 종합 계획" — 에 따라 12개 전문 에이전트를 2 Round 로 병렬 디스패치한 결과 보고서.

본 보고서는 **Phase H (Resilience & Performance Hardening) + Phase I (Hygiene & Observability)** 의 착수 근거 문서.

---

## 검증 방법

### Round 1 — 8개 영역 병렬 감사

| 에이전트 | 영역 | 산출물 |
|---|---|---|
| `Explore` | 아키텍처 / 모듈 배치 | A 5건 / B 5건 / C 0건 — 기초 견고 |
| `pipeline-reviewer` | 파이프라인 + 비즈니스 로직 | Critical 5건 + 개선 5건 |
| `general-purpose` | 성능 / 속도 | Critical 3건 + 개선 5건 |
| `general-purpose` | 보안 (OWASP) | Critical 0건 / High 5건 |
| `general-purpose` | DB / 마이그레이션 | Critical 3건 + High 5건 |
| `general-purpose` | 테스트 커버리지 | Critical 3건 + 개선 5건 |
| `general-purpose` | 외부 API 통합 | Critical 4건 + High 5건 |
| `general-purpose` | 관측성 / 모니터링 | Critical 6건 + 권장 5건 |

### Round 2 — Cross-cutting + 누락 영역 + 우선순위 + 미래 가독성

| 에이전트 | 영역 | 산출물 |
|---|---|---|
| `Explore` | CLI / scripts / cron / templates | Critical 3건 + High 5건 |
| `general-purpose` | Cross-cutting 패턴 5종 검증 | 패턴별 일관성 점수 + 우선 수정 추천 |
| `general-purpose` | 비용/효과 우선순위 분석 | 6 묶음 PR + Phase H/I 로드맵 |
| `doc-quality-reviewer` | 미래 Claude 가독성 트랩 | 5 docstring 보완 + 3 STATE/CLAUDE 정정 |

---

## 영역별 등급

| 영역 | 등급 | 핵심 |
|------|------|------|
| 아키텍처 / 모듈 배치 | **A** | 도메인 단방향 의존 ✓, Registry 자동 등록 ✓, 1500줄 이상 거대 파일 0 |
| 파이프라인 무결성 | **B+** | 멱등성·MergeAttempt lifecycle 견고, race-recovery 흐름 result_dict 불일치 |
| 성능 / Latency | **C** | PyGithub blocking + 도구 fan-out 직렬 + 복합 인덱스 부재 → Critical |
| 보안 | **B+** | HMAC/SQL/Path 견고, Rate limit + 입력 크기 + sanitize 18곳 미적용 |
| DB / 마이그레이션 | **B** | 0007+ batch_alter 1곳, gate_decisions cascade 누락, claim_batch SKIP LOCKED 미구현 |
| 테스트 커버리지 | **A-** | 단위 1931 + 통합 72, OTP/CLI 실패 모드/모듈 캐시 격리 갭 |
| 외부 API 통합 | **C+** | Tier 3 PR-A 분류 표준 13 호출 지점 미전파, 재시도 정책 부재 |
| 관측성 / 모니터링 | **B-** | Sentry/stage_timer 양호, MergeAttempt audit 미노출 + AI cost 일별 집계 부재 |
| CLI / Templates / Cron | **B** | settings.html 9 JS 헬퍼 양호, cron N+1 + CLI 실패 모드 미커버 |
| 문서-코드 정합성 | **B+** | Phase 4 메타 회고 후 대부분 일관, claim_batch SKIP LOCKED 모순 잔존 |

종합: **B+ → A** 진입에 묶음 PR 6개 (≈36h) 충분.

---

## Critical 발견사항 10건

### 즉시 패치 (이번 주)

| # | 위치 | 사고 시나리오 | 수정 비용 |
|---|------|-----|----|
| **C1** | `src/analyzer/io/ai_review.py:67` Anthropic SDK timeout 미설정 (기본 600초) | Claude API hang → BackgroundTask 슬롯 10분 점유 | 1줄 |
| **C2** | `src/worker/pipeline.py:283` race-recovery 시 `result_dict=None` → notify 사일런트 실패 | 동시 PR 이벤트 시 알림 채널 6개 모두 KeyError | ~15줄 |
| **C3** | `src/github_client/diff.py:18-29` PyGithub blocking in async (no `asyncio.to_thread`) | 20파일 PR 시 GitHub API 21회 직렬 → 이벤트 루프 5-15초 블록 | ~30줄 |
| **C4** | `src/notifier/telegram.py:22-23` Telegram 429 retry-after 미처리 | 봇 그룹 차단 (spam) → cron 누적 시 운영 중단 | ~20줄 |

### Cross-cutting (묶음 PR 처리)

| # | 영역 | 핵심 |
|---|------|----|
| **C5** | `_check_suite_debounce` + `_required_contexts_cache` | 무제한 성장 (multi-tenant 1000 repo 시 leak) |
| **C6** | `claim_batch` SKIP LOCKED | CLAUDE.md vs 코드 불일치, 수평 확장 시 더블-클레임 |
| **C7** | `gate_decisions.analysis_id` ON DELETE CASCADE | 누락 시 FK 위반 잠재 |
| **C8** | `_get_ci_status_safe` 중복 | engine.py + merge_retry_service.py 한쪽 수정 시 분기 깨짐 |
| **C9** | `/health` `active_db` 누락 | CLAUDE.md 와 불일치 → 외부 모니터링이 failover 미감지 |
| **C10** | Telegram gate 콜백 토큰 도메인 격리 비대칭 | `_make_callback_token` vs `_parse_gate_callback` HMAC 비대칭 |

---

## 묶음 PR 6개 추천

### Phase H — Resilience & Performance Hardening (2주)

| PR | 묶음 | 시간 | 영향 |
|----|------|------|------|
| **PR-1: 외부 API timeout + 재시도 통일** | C1 + SMTP 30s + 5xx tenacity 재시도 (전 채널) | 4h | API hang 0, p99 latency -40% |
| **PR-2: 알림/Gate 회복력** | C2 race-recovery + C4 Telegram 429 + `run_gate_check` 3-옵션 `asyncio.gather` 병렬화 | 6h | 알림 누락 0, gate latency -30% |
| **PR-3: GitHub 호출 정합성** | C3 PyGithub `asyncio.to_thread` + `Repository.owner` joinedload + `list_user_repos` 페이지네이션 | 8h | 이벤트 루프 블록 해소, 100+ repo 사용자 UX |
| **PR-4: DB 일관성 + 큐 견고화** | C6 SKIP LOCKED + C7 CASCADE + 복합 인덱스 3종 | 7h | 동시성 안전 + 분석 쿼리 -50% |

### Phase I — Hygiene & Observability (1주)

| PR | 묶음 | 시간 | 영향 |
|----|------|------|------|
| **PR-5: 코드 dedup + 문서 정합** | C8 통합 (`src/shared/ci_utils.py`) + C9 `/health` active_db + C10 콜백 토큰 격리 | 3h | CLAUDE.md 약속 일치 |
| **PR-6: 관측성/보안 위생** | C5 캐시 LRU bound + `logger.error → exception` 16곳 + `sanitize_for_log` 18곳 + `POST /api/hook/result` 입력 크기 제한 | 8h | 메모리 안정 + Sentry 그룹화 + SonarCloud taint 0 |

총 **6 PR / 36h** (W1: PR-1·2, W2: PR-3·4, W3: PR-5·6).

---

## 보류 / 장기 (Phase J 이후)

| 항목 | 보류 사유 |
|------|----------|
| 분석 도구 ProcessPoolExecutor fan-out | 현재 파일당 ~2s, 복잡도 ↑ vs 대기 시간 단축 미미 |
| `top_issues` JSONB 쿼리 (Postgres only) | SQLite 분기 부담 |
| Railway GraphQL 5종 분류 | 빈도 < 1/월 |
| AI cost 일별 집계 테이블 | UI 작업 4-6h, 로그 grep 으로 해결 가능 |
| MergeAttempt audit UI | Phase F.4 흡수 |
| PR 단건 회귀 알림 | 노이즈 위험, 옵트인 설계 필요 |
| OAuth refresh | GitHub 토큰 무기한 → 사용자 revoke 만 처리 |
| `gate/engine.py` 676줄 분할 | 책임 명확, 즉각 분할 필요 없음 |

---

## 미래 Claude 가 빠질 수 있는 트랩 (즉시 docstring 보완)

| 트랩 | 위치 | 권장 보완 |
|------|------|-----------|
| `_get_ci_status_safe` 한쪽만 수정 | engine.py:338 + merge_retry_service.py:280 | 양쪽 docstring 동기화 표지 + parity 테스트 |
| `_run_auto_merge_legacy` else 분기 | engine.py:473 (`new_state=LEGACY`) | "PR-B 폴백 제거 후 도달 불가 — 삭제 예정" |
| `PATH_NO_ATTEMPT` 사용 가능 착각 | native_automerge.py:54 | "현재 NO callsite — D2 캐시 도입 시까지 미사용" |
| `has_tests=False → test_score=0` | ai_review.py:127 | 다른 fallback (7점) 과 점수 다름 경고 |
| CLAUDE.md `claim_batch` 사양 vs 코드 불일치 | merge_retry_repo.py:225 | 단일 워커 가정 명시 + SKIP LOCKED 도입 시점 표기 |

---

## 추가 발견 (Round 2 — CLI/Templates/Cron)

- `src/services/cron_service.py` weekly cron 4N 쿼리 (N=리포 수) → batch fetch 권장 (Phase J 후속)
- `src/cli/__main__.py` pre-push hook grade F exit 2 회귀 테스트 부재 — PR-6 에 +5 테스트
- `src/templates/settings.html:1102` `tbody.innerHTML = html` — PRESETS user-configurable 시 XSS 위험 — 주석으로 가드
- `src/api/internal_cron.py:48` `hmac.compare_digest(None, expected)` → `if not api_key: 503` 가드 확인 필요

---

## 예상 수치 변화

| 지표 | 현재 | Phase H 종료 | Phase H+I 종료 |
|------|------|---------------|------------------|
| 단위 테스트 | 1931 | +20 (1951) | +35 (1966) |
| 통합 테스트 | 72 | +5 (77) | +5 (77) |
| 커버리지 | 95% | +0.5% (95.5%) | +1% (96%) |
| pylint | 10.00 | 유지 | 유지 |
| pipeline p99 latency | baseline | **-30~40%** | 동일 |
| 외부 API 사일런트 실패 | 월 5-10건 | <1건 | ~0 |
| Sentry "GitHub sync hang" | 월 5-10 | 0 | 0 |
| SonarCloud taint warnings | ~18 | 18 | 0 |

---

## 권장 진행 순서

1. **W1 (~2026-05-07)** — PR-1 (timeout) + PR-2 (회복력) 우선 머지
2. **W2 (~2026-05-14)** — PR-3 + PR-4 — Phase H 종결
3. **W3 (~2026-05-21)** — PR-5 + PR-6 — Phase I 종결
4. **W4 (~2026-05-28)** — 12-에이전트 Round 2 재감사로 잔여 회귀 검증
5. **2026-05-06** — PR-B3 (`merge_retry_service` 폐기 평가) — Phase H 와 독립 진행

---

## 안전성 우선 분할 전략

각 묶음 PR 내부에서도 **최소 단위 분할** 권장 — 변경 범위가 커질수록 회귀 위험 증가.

예: PR-1 분할 가능
- PR-1A: Anthropic SDK timeout=60s + SMTP timeout=30s 만 (src/ 2줄)
- PR-1B: tenacity 재시도 도입 (의존성 추가, 별도)

각 PR 마다:
1. 회귀 방지 테스트 먼저 (TDD Red)
2. src/ 최소 변경 (TDD Green)
3. pylint + bandit + SonarCloud QG 통과 확인
4. 머지 후 다음 단계

---

## 결론

**B+ 등급 프로젝트** — 운영 중인 production 시스템으로 충분한 견고성. 다만 4건의 사일런트 실패 위험 (C1~C4) 은 즉시 패치 권장. Phase H + I 6 PR / 36h 로 **A 등급** 진입 가능.

12 에이전트가 일관적으로 식별한 cross-cutting 패턴 (외부 API 분류 부재, 무제한 캐시, logger.error 손실, async/sync 경계) 은 묶음 PR 로 처리할 때 ROI 가 가장 크다.

본 보고서는 Phase H 착수 시점에서 단일 진실 소스로 사용. 각 PR 머지 시 본 문서의 해당 항목을 ✅ 체크하여 진행 추적.
