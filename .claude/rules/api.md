---
description: API / 알림 채널 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/api/**"
  - "src/notifier/**"
  - "src/webhook/**"
  - "src/gate/**"
  - "src/github_client/**"
  - "src/scheduler.py"
  - "src/main.py"
---

# API / 알림 채널 규칙

> 🔴 **사고 재현·측정 로그는 [`docs/_archive/rules-incident-log.md#api`](../../docs/_archive/rules-incident-log.md#api) 로 옮겼다 — 규칙을 완화·삭제하려면 아카이브를 먼저 읽을 것** (2026-08-12 밀도 압축).
> 여기 남은 것은 규칙 · 왜 한 줄 · 가드 파일명뿐이며, 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.
> 역링크·앵커 도달성만 잰다(서사 보존은 기계 집행 아님 — R81 옵션 (b), 2026-08-15): `tests/unit/scripts/test_rules_archive_backlink.py`.

## 세션 라우팅

- 🔴 **background 진입점은 `WorkerSessionLocal` alias 의무** (본문 = [`db.md`](db.md) §WorkerSessionLocal).
  대상: `gate/engine`·`gate/actions/*`·`worker/pipeline`·`webhook/*`·`notifier/*` lazy·
  `api/{hook,internal_cron,repos,stats,repo_report}`. 웹 경로는 bare 유지, **혼용 금지**.
  신규 진입점은 `tests/unit/test_worker_session_routing.py` 의 `_BACKGROUND_MODULES` 등재 의무.
  *왜 여기 있나*: `db.md` path 매칭이 이 영역을 포함하지 않아 **자동 로드되지 않는다** — 사후 가드가
  잡더라도 작성 시점에 규칙을 못 보면 틀린 코드를 먼저 쓴다.

## SHA 결속 — 이 영역 최고 위험

- **auto-merge 는 `score` 를 산출한 커밋(`Analysis.commit_sha`)에만 결속된다.**
  *왜*: 분석(정적 60s + AI 리뷰) 중 push 된 **미검증 커밋 B 가 A 의 점수로 머지**됐다.
  경로: `run_gate_check(..., commit_sha=)` → `GateContext.commit_sha` → `AutoMergeAction`
  → `_run_auto_merge(analyzed_sha=)` → retry/legacy.
  - **fail-closed**: `analyzed_sha != head_sha` 면 **머지도 큐 등록도 하지 않고 return**.
    큐까지 막는 이유 = 잘못된 SHA 로 행이 생기면 재시도가 `sha_drift` 검사를 통과한다. 드롭해도 손실 0.
  - **legacy 경로도 `expected_sha` 전달 의무** — 미전달 시 `native_automerge` 가 스스로 live head 를 재조회해 결함 재현.
  - **semi-auto(telegram) 가 노출 최대** — 콜백 HMAC 에 **만료가 없어** 몇 시간 뒤 눌러도 그 시점 head 가 머지된다(레이스조차 불필요).
  - 🔴 **배선이 유일한 단일 실패점** — `commit_sha` 주입은 `src/worker/pipeline.py` 의 `run_gate_check` 호출 **3곳**뿐.
    빠지면 가드는 살아 있으나 `analyzed_sha=None` 으로 **영구 무력화**된다. 신규 호출부 추가 시 전달 의무.
    배선 집행: `tests/unit/worker/test_pipeline_save_and_gate.py`.
  - 🔴 **재시도 큐도 analyzed SHA 로 결속** — `effective_sha = analyzed_sha or observed_sha or merge_sha`.
    관측 head 로 결속하면 워커의 드리프트 검사가 통과해 미검증 커밋이 머지된다.
    결속 집행: `tests/unit/gate/test_analyzed_sha_binding.py`.
  - **머지 결속식 = `expected_sha = analyzed_sha or head_sha`** — head 조회에 실패해 `head_sha=""` 여도
    GitHub 이 `sha` 파라미터로 원자성을 검증한다. 이 폴백을 지우면 조회 실패 시 결속이 **스스로 풀린다**.
  - 🔴 **하위 호환**: `analyzed_sha=None` 이면 **기존 동작과 완전 동일**(가드 미적용)이다.
    이를 fail-closed 로 바꾸지 말 것 — 구 호출부와 의도된 None 경로를 오차단한다.
  가드: `tests/unit/gate/test_analyzed_sha_binding.py` · `tests/unit/worker/test_pipeline_save_and_gate.py`
- **SHA 결속의 서버측 강제는 merge 에만 있다 — approve 에는 없다.**
  `merge_pr(..., expected_sha=)` 는 GitHub 이 409 로 차단(실측). 그러나
  `post_github_review(commit_id=)` 는 **fail-closed 가 아니다** — 구 SHA·사라진 SHA 도 **200 수락**된다
  (422 는 저장소에 오브젝트가 아예 없을 때만 — 분석된 SHA 는 정의상 존재하므로 **원리적으로 발화 불가**였다).
  → approve 결속은 **POST 직전 head 를 직접 조회해 강제**하고 불일치 시 `HeadMovedError`(POST 안 함).
  **422 를 'head 이동' 으로 단정 금지** — 실제 사유는 self-approval 등이다.
  ⚠️ 잔여: GET→POST 레이스는 남는다(리뷰 API 에 서버측 원자성 수단 없음이 실측 확인). 새 head 의 synchronize 가 재게이트.
  🔴 **신규 외부 API 계약을 "형제가 그러니 이것도 그럴 것" 으로 가정 금지 — 계약별 실측 의무.**
  가드: `tests/unit/gate/test_approve_head_binding.py`

## 게이트 경로 단일화

- 🔴 **반자동(telegram) auto-merge 는 `engine._run_auto_merge` 에 위임** — 가드는 `AutoMergeAction` 미러링:
  (1) `decision == "approve"` (2) `config.auto_merge` (3) `not static_analysis_incomplete` (4) `not ai_review_failed(result)`.
  `score >= merge_threshold` 는 `_run_auto_merge` 내부 1회만(중복 금지).
  위임 집행: `tests/unit/services/test_merge_retry_service.py`.
- 🔴 **2nd-LLM 검증자 가드도 `_run_auto_merge` 단일출처** — 이전엔 `AutoMergeAction` 에만 있어 **반자동이 검증자를 우회**했다.
  양 호출자는 `result` 를 전달해야 diff/리뷰 요약을 검증할 수 있다
  (`tests/unit/services/test_merge_retry_service.py`).
  ⚠️ retry 서비스는 `_run_auto_merge` 미경유라 재검증하지 않는다 — **의도**다:
  `sha_drift` 검사 + `expected_sha` 원자성으로 **검증자가 승인한 동일 SHA 만** 머지되므로 verdict 가 stale 될 수 없다.
  `expected_sha` 바인딩 제거 금지(force-push 미검증 코드 머지 위험).
- **리플레이 가드** — `handle_gate_callback` 은 부수효과 **전에** `claim_decision()`(insert-only, UNIQUE)로 원자 claim.

## 알림 채널

- **`send_*` 는 keyword-only(`*`)** — positional 호출 시 TypeError. 단 `run_gate_check` 는 positional.
- **채널 추가 시 4곳 동기화**: `RepoConfig` ORM → `RepoConfigData` → `RepoConfigUpdate` → UI 폼.
  *왜*: 누락 시 REST 업데이트가 해당 필드를 **NULL 로 덮어쓴다**.
- **`ai_review_enabled` 는 4-way 동기화이며 PRESETS 미포함**(의도 — 알림 프리셋과 AI on/off 는 직교).
  검증 절차 = [`docs/runbooks/cost-controls.md`](../../docs/runbooks/cost-controls.md)
- **채널 독립성** — `asyncio.gather(return_exceptions=True)`. `repo_config` 로드 실패에도 Telegram 은 global fallback 발송.
- 🔴 **아웃바운드 markdown 인젝션 escape 의무** — untrusted `issue.message` 를 삽입할 때 채널별로:
  **GitHub·Discord(GFM)** = `escape_markdown()` / **Slack(mrkdwn)** = `escape_slack_mrkdwn()`(Slack 은 백슬래시 미지원).
  4채널 일괄(github_comment·discord·slack·github_issue). telegram 은 이미 전 동적 값 `html.escape()`.
  채널별 escape 집행: `tests/unit/notifier/test_markdown_escape.py`.
  🔴 **AI 요약·피드백은 escape 금지**(의도 markdown 프로즈 — 정책 16 명시 제외).
  ⚠️ **잔여 위험 수용**: `ai_summary` 는 untrusted diff 기반 AI 출력이라 **2차 인젝션 경로**이며 markdown 3채널은 무escape 다.
  가드: `tests/unit/notifier/test_markdown_escape.py` · `tests/unit/notifier/test_github_issue.py`
- **공통 헬퍼 사용 의무** — `_common.py` 의 `format_ref()`·`get_all_issues()`·`truncate_message()`·`truncate_issue_msg()`,
  `telegram_post_message`(httpx 직접 import 금지), `get_repo_or_404`, `github_api_headers`.
- **단일 출처** — GRADE 상수 = `src/constants.py` / `ChangedFile` = `src/github_client/models.py`.
- **Telegram 콜백 도메인 분리** — `scope ∈ {"gate","cmd"}` 별 HMAC. 신규 명령은 `cmd:<verb>:<id>:<token>` + **64-byte 한도** 검증.

## HTTP / 재시도 / 인증

- **신뢰 API 는 `get_http_client()` 싱글톤**, 외부 untrusted 는 `build_safe_client()`.
  `async with httpx.AsyncClient()` 매번 생성 금지.
- **외부 SDK 는 `timeout`·`max_retries` 명시 의무**(기본값과 같은 값이라도) — SDK 업그레이드 시 silent regression 차단.
  **값**: Anthropic SDK = **60s** · 신뢰 httpx = `HTTP_CLIENT_TIMEOUT` = **10.0s**(`src/constants.py`).
- **5xx 자동 재시도는 신뢰 API 한정**(max 3, backoff). Telegram 429 는 `retry_after` + cap 30s.
  **외부 untrusted webhook 은 재시도 금지** — idempotency 보장 불가라 중복 발송이 된다.
- **sync I/O(PyGithub·requests)는 `asyncio.to_thread` wrap 의무** — 직접 호출 시 이벤트 루프 블록.
- **Webhook 은 `X-Hub-Signature-256` 헤더가 **없거나** 서명이 불일치하면 GitHub·Telegram 모두 401**
  (200 반환 금지). 빈 시크릿(`GITHUB_WEBHOOK_SECRET` 미설정)도 즉시 401 — **부재와 불일치를 다른 케이스로 취급 금지**.
- 🔴 **webhook secret 캐시에 상한 의무**(`WEBHOOK_SECRET_CACHE_MAX`) — `get_webhook_secret` 는
  **서명 검증 전(pre-auth)** 위조 가능한 `full_name` 으로 호출되므로 상한 없이는 메모리 고갈(pre-auth DoS).
  신규 pre-auth 캐시도 동일 패턴. 가드: `tests/unit/webhook/test_secret_cache_bound.py`
- **신규 API 엔드포인트는 `@limiter.limit(RATE_LIMIT_API|RATE_LIMIT_HEAVY)` 필수**
  (상수 출처 = `src/middleware/rate_limiter.py`, 직접 문자열 금지).
  **예외**: `require_login` 이 이미 보호하면 미적용 허용(정책 3 보고) ·
  **webhook provider 는 미적용 컨벤션** — HMAC 이 미인증 폭주를 401 로 차단하고, IP 기반 limiter 는
  단일 출처 webhook 에 부정확해 정상 콜백을 오차단한다. **API 엔드포인트가 webhook 흉내로 limiter 누락 금지.**
- **Cron 엔드포인트는 `INTERNAL_CRON_API_KEY` 전용**(admin key 와 분리, `compare_digest`, 미설정 503).
  🔴 **트리거는 Railway cron 이 아니라 인앱 스케줄러** — `railway.toml [[deploy.cronJobs]]` 는 스키마에 없는 키라
  조용히 무시돼 5종이 한 번도 실행되지 않았다. 주기 작업 추가 시 `src/scheduler.py` 의 `JOBS` 등재 의무.
  가드: `tests/unit/test_scheduler.py`

## 기타 계약

- **`asyncio.gather` 내 코루틴은 각각 `with SessionLocal() as db:`** — 공유 시 identity map 오염 + commit 충돌.
  교차 참조: [`pipeline.md`](pipeline.md)
- **race-recovery 시그널 = `result_dict is None`** — 호출자는 `if result_dict is None: skip notify`.
- **`MergeAttempt` 관측은 `_run_auto_merge` 단일 출처**(자동·반자동 공통). `failure_reason` 은
  `src/gate/merge_reasons.py` 의 정규 태그. 실패 시 `get_advice()` + `create_merge_failure_issue()` 호출은
  **`auto_merge_issue_on_failure` 필드로 제어**되며 그 필드는 **5-way 동기화 대상**이다
  (ORM↔Data↔Update↔폼↔PRESETS) — 동기화를 빠뜨리면 설정이 무력화된다.
- **CI-aware 재시도** — `unstable`+CI running / `unknown` 은 실패가 아니라 `merge_retry_queue` 큐잉.
  **트리거는 둘이다** — `check_suite.completed` **웹훅** 또는 **1분 cron** → `process_pending_retries`
  (`src/services/merge_retry_service.py`). 한쪽을 "중복" 으로 제거하면 그 축의 재시도가 영구 정지한다.
  첫 지연·최종 결과만 알림(중간 무음).
- **`RepoConfig` 필드명** = `approve_mode`·`approve_threshold`·`reject_threshold`(구명 사용 시 AttributeError).
- **PR Gate 3옵션 독립** — `pr_review_comment`·`approve_mode`·`auto_merge+merge_threshold`.
- **`build_analysis_result_dict`** = `src/worker/pipeline.py` 모듈 레벨(pipeline·hook 공용).
- **`auto_merge`** 는 `repo` 스코프 또는 `pull_requests: write` 필요. Branch Protection 시 APPROVE 후에도 실패 가능.
- **Telegram chat_id 라우팅** = `analytics_service.resolve_chat_id(repo, config)` 단일 헬퍼.
- **Webhook 이벤트 목록** = `["push","pull_request","issues","check_suite"]`(기존 리포는 재등록 버튼으로 갱신).
