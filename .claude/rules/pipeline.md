---
description: 파이프라인 / 비즈니스 로직 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/worker/pipeline.py"
  - "src/analyzer/**"
  - "src/scorer/**"
  - "src/webhook/**"
  - "src/gate/**"
---

# 파이프라인 / 비즈니스 로직 규칙

> 여기 남은 것은 규칙 · 왜 한 줄 · 가드 파일명이다. 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.

## 세션 라우팅

- 🔴 **background 진입점은 `WorkerSessionLocal` alias 의무** (본문 = [`db.md`](db.md) §WorkerSessionLocal).
  대상: `gate/engine`·`gate/actions/*`·`worker/pipeline`·`webhook/*`·`notifier/*` lazy·
  `api/{hook,internal_cron,repos,stats,repo_report}`. 웹 경로는 bare 유지, **혼용 금지**.
  신규 진입점은 `tests/unit/test_worker_session_routing.py` 의 `_BACKGROUND_MODULES` 등재 의무.
  *왜 여기 있나*: `db.md` path 매칭이 이 영역을 포함하지 않아 **자동 로드되지 않는다**.

## 미분석·실패가 만점으로 머지되면 안 된다

- **미분석·실패 상태가 만점으로 auto-merge 되면 안 된다.** 3축 전부 마커로 차단:
  - AI 리뷰 genuine 실패(`api_error`·`parse_error`) → `src/gate/_common.py` 의 `ai_review_failed()`
    → AutoMerge·Approve·telegram 반자동 **3경로 모두 차단**. `AI_REVIEW_FAILED_STATUSES` 변경 시 3경로 동시 검토.
    `no_api_key`/`empty_diff`/`disabled` 는 **의도적 미수행이라 제외**(회귀 방지).
  - content-fetch transient 실패(403/5xx) → `ChangedFile.fetch_failed` → `incomplete`
    (404·UnicodeDecode 등 영구 실패는 제외).
  - per-tool subprocess 타임아웃 → `AnalyzeContext.timed_out` → `StaticAnalysisResult.incomplete`.
    설계: re-raise 가 아니라 **ctx 신호** — 반환 계약("타임아웃 시 `[]`")을 보존해야 23+ 테스트가 안 깨진다.
- **바이너리 부재의 차단 여부는 "조달 계약" 으로 가른다.**
  `src/analyzer/io/static.py` 의 `PROVISIONED_ANALYZERS` 안 도구 부재 = **실배포 회귀 → `incomplete` 차단** /
  계약 밖 도구 부재 = **제품 미제공 → `uncovered_language` 가시화만**.
  *왜*: 무조건 차단하면 애초에 설치하지 않는 9종 언어가 **영구 auto-merge 불가**가 된다.
  🔴 조달을 추가/제거하면 이 목록도 갱신 의무.
  가드: `tests/unit/analyzer/test_procurement_contract.py` · `tests/unit/analyzer/test_static_incomplete.py`
- **외부 린터가 "실행됐지만 아무것도 분석 안 함" 은 `[]` 와 구별 불가 → 점수 인플레.** 계약 3항:
  (a) 실행 cwd = **분석 대상 파일의 디렉토리** (b) 비-JSON stdout = `RuntimeError`
  (c) `ruleId=None` + 非fatal = **"린트되지 않았다"** 라 집계 금지 + 예외로 중단.
  🔴 **mock 은 이 클래스를 원리적으로 못 잡는다** — 단위 40건 green 중 운영은 무동작이었다.
  신규/수정 외부 린터는 **실바이너리 통합 테스트 동반 의무**(`tests/integration/test_eslint_analyzer.py` 형식).
- **린터 메시지 3분류**: 코드 결함(집계) / 미린트(raise) / **우리 설정에 대한 메타(드롭)**.
  *왜*: 대상 리포가 자기 설정 룰을 참조하면 린터가 "모르는 룰" 로 보고하는데, 이를 결함으로 세면
  **정상 코드를 감점**(score-lie → auto-merge 전파)하고 미린트로 세면 정상 PR 이 incomplete 가 된다.
  구조 신호만으로 (c)를 (a)와 구별할 수 없어 텍스트에 의존한다 → 실바이너리 테스트가 유일한 방어다.

## 동시성 / 멱등성

- **race 판정용 재조회는 `populate_existing()` 의무.**
  *왜*: `with_for_update()` 는 SQL 잠금만 걸고 ORM 속성을 갱신하지 않아, identity map 의 stale 값으로
  판정하면 **gate(auto-merge) + notify 가 2회** 실행된다(Postgres 동일).
  회귀 가드는 **교차 세션**으로 짤 것 — 같은 세션 테스트는 결함이 있어도 통과한다.
  ⚠️ SQLite 는 `FOR UPDATE` 를 조용히 버린다 → 그 가드가 증명하는 것은 **stale read 차단**이지 행 잠금이 아니다.
  ⚠️ `populate_existing()` 은 **미flush 더티 속성을 무예외로 폐기**한다(운영은 `autoflush=False`).
- **멱등성 = commit SHA 중복 체크.** `pr_number` 갱신은 **None → 최초 PR# 1회만**(first-writer-wins);
  다른 non-None 값이면 WARNING 후 skip. *왜*: 동일 head SHA 를 두 PR 이 공유하면 댓글·승인·머지가 오배송된다.
- **`begin_attempt` 는 dedup 게이트가 아니다** — 반환 False 를 **의도적으로 무시**한다.
  중복 차단은 `Analysis.find_by_sha` first-writer-wins **단독 책임**이며, 두 메커니즘을 얽으면 동작이 갈라진다.
- **`claim_decision`(insert-only)** 는 부수효과 전에 결정을 원자적으로 claim — 리플레이·더블클릭 차단.
  `upsert` 와 달리 update 분기가 없어 **결정 뒤집기 불가**.

## 분석 소실 탐지

- **소실을 막지 않는다 — 탐지 가능하게 만든다.** `begin_attempt()` 를 **비싼 작업 전**,
  `_finish_attempt()` 를 **정상 종료 3곳**(파일 0건 / result None / **Analysis 영속화 직후·notify 앞**)에서 호출.
  남아 있는 오래된 행 = 소실된 분석(`find_orphaned`).
  **터미널 `except` 에서 `_finish_attempt` 금지** — 남은 행이 곧 실패 증거다.
  **gate 실패는 소실이 아니다** → 흔적 삭제(보존하면 정상 분석이 orphan 오탐).
  🔴 finish 는 **notify 앞** — 뒤에 두면 notify 예외가 정상 분석을 orphan 으로 오탐한다.
  신규 조기 return 경로 추가 시 `_finish_attempt` 동반 의무.
  가드: `tests/unit/worker/test_pipeline_attempt_durability.py` · `tests/unit/repositories/test_analysis_attempt_repo.py`

## 점수 영속화

- **AI genuine 실패 시 score/grade 를 NULL 로 저장**(인플레 89/B 를 집계에 넣지 않는다).
  hook(`src/api/hook.py`)과 pipeline(`_save_and_gate`) **양 경로 동일 동작 의무** — 한쪽만 고치면 집계 비대칭.
  🔴 **입력-diff 절단(`ai_review_truncated`)은 제외 — 점수 유지**(대형 PR 절반이 절단인데 전부 NULL 이면
  대시보드·리더보드에서 점수가 통째로 사라진다). 절단 시 auto-merge 차단은 **마커를 직접 읽는 별도 가드** 담당.
  가드: `tests/unit/worker/test_pipeline_save_and_gate.py`
  🔴 **R46 — 신뢰 불가 분류는 `src/scorer/reliability.py` 단일 출처**:
  - `should_null_persist_score` = genuine AI 실패만 (NULL 컬럼)
  - `score_is_unreliable` = CLI·incomplete·AI 기본값/disabled·uncovered 포함 → **점수는 남기고 집계만 제외**
    (상세 페이지 표시 유지 · 역사 행 rewrite 0). 대시보드 KPI 는 제외 건수를 공개한다.
  가드: `tests/unit/scorer/test_score_reliability.py`
  · `tests/unit/services/test_score_aggregate_reliability.py`
  · `tests/unit/notifier/test_score_reliability_disclosure_parity.py`
- **AI 점수 스케일링**: Claude commit 0-20 / direction 0-20 / test 0-10 → calculator 가 15/25/15 로 스케일.
  `round()` = banker's rounding.
- **category 기반 집계** — tool 이름 무관, `AnalysisIssue.category` 만 본다. `CQ_WARNING_CAP=25` 단일 cap.
  신규 도구는 category 만 맞으면 점수에 자동 반영된다.

## Webhook / 페이로드

- **GitHub 의 None-able 키는 `(data.get(k) or {})` 로 정규화.**
  *왜*: `.get(k, {})` 체이닝은 값이 `None` 이면 default 가 적용되지 않아 NPE(브랜치 삭제 push 실측).
- **PR action 필터** = `opened`/`synchronize`/`reopened` 만 처리.
- **봇 루프 방지 3층** = kill-switch → `is_bot_sender()` + whitelist → skip marker + 시간당 6회 상한.
  운영 runbook: `docs/runbooks/self-analysis.md`
- **`_extract_commit_message`** = PR 은 `title + body`, push 는 `head_commit["message"]`.
- **봇 PR 은 `create_issue` skip** — `pr_head_ref` 가 `claude-fix/`·`bot/`·`renovate/`·`dependabot/` 접두면 건너뛴다.

## Analyzer 등록

- **신규 도구 3단계**: `tools/` 하위 클래스 + `register()` → `static.py` import → `SUPPORTED_LANGUAGES` 선언.
  **+ `docs/architecture.md` 도구 목록 동기화 의무**(전체 목록 단일 출처) · 언어별 Tier 표 =
  [`docs/reference/language-coverage.md`](../../docs/reference/language-coverage.md) — 여기가 빠져
  조달된 6종(tsc·ktlint·sqlfluff·hadolint·tflint·yamllint)이 자기 언어 행에 없던 적이 있다.
- **`review_guides`**: `get_guide(lang, "full"|"compact")` — N≤3 전체 full, N≤6 Tier1 full+나머지 compact, N>10 상위 5 compact.
- **AI 리뷰 JSON 파싱**: 설명 텍스트가 앞에 붙을 수 있어 `re.search` 로 코드블록 내 JSON 만 추출.
- **다언어 감지** = 확장자·shebang·파일명 49종. 비-코드 파일만 변경 시 테스트 점수 면제.

## 기타 계약

- **리포별 AI kill-switch(`RepoConfig.ai_review_enabled`)** — `False` 면 API 호출 없이 `disabled` 반환(비용 0).
  설정 조회 예외 시 **fail-safe default `True`**(일시 실패가 AI 를 끄면 안 된다).
  전역 `AI_REVIEW_DISABLED` 가 리포별보다 우선. 검증 절차 = `docs/runbooks/cost-controls.md`
- **`asyncio.gather` 내 코루틴은 각각 독립 `SessionLocal()`** — 세션 공유 시 트랜잭션 충돌.
- **`_run_static_with_timeout`** = deadline 기반 **파일별 순차**, 타임아웃 시 부분결과 보존 + `incomplete`.
  단일 파일 예외는 격리, **비어있지 않은 배치 전량 실패 → `incomplete`**(안전망).
- **Railway webhook** `POST /webhooks/railway/{token}` — 토큰 미일치 404, `railway_api_token` 은 Fernet 복호화 후 전달.
  `RailwayDeployEvent` 는 **nested**(`event.project.project_id`) — 평면 접근 불가.
- **`commit_scamanager_files`** — 기존 파일이면 GET 으로 sha 조회 후 body 포함(누락 시 422).
- **CLI Hook** `GET /api/hook/verify`·`POST /api/hook/result` 는 `hook_token` 인증(X-API-Key 불필요).
- **분석 source** = result JSON 의 `"source": "pr"|"push"`, 구 레코드는 `pr_number` 유무로 파생.
- **`railway_deploy_alerts` 는 5-way 동기화 대상**(ORM↔Data↔API body↔폼↔PRESETS).
