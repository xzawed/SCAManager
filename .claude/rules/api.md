---
description: API / 알림 채널 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/api/**"
  - "src/notifier/**"
  - "src/webhook/**"
  - "src/gate/**"
  - "src/main.py"
---

# API / 알림 채널 규칙

- **keyword-only 강제 (`*`)**: 모든 `send_*` notifier 함수와 `run_gate_check()` 등은 `def fn(*, arg1, arg2)` 형태. 테스트에서 positional 호출 시 TypeError — 반드시 키워드 인자로 호출.
- **RepoConfig 필드명**: `approve_mode`(구 `gate_mode`), `approve_threshold`(구 `auto_approve_threshold`), `reject_threshold`(구 `auto_reject_threshold`) — 구 필드명 사용 시 AttributeError.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 반드시 동기화. 누락 시 REST API 업데이트 시 해당 필드가 NULL로 덮어써지는 버그 발생.
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없거나 서명 불일치 시 401 반환 — 로컬 테스트 시 서명 생성 필요. 빈 시크릿(`GITHUB_WEBHOOK_SECRET` 미설정)이면 즉시 401.
- **Webhook 서명 실패 일관성**: GitHub / Telegram webhook 모두 서명 불일치 시 `HTTPException(401)` 반환. 200 OK 반환 금지.
- **알림 독립성**: `_build_notify_tasks()` 디스패처, `asyncio.gather(return_exceptions=True)`로 실행 — 한 채널 실패해도 나머지 채널은 정상 전송. `repo_config` 로드 실패 시에도 Telegram은 global fallback으로 항상 발송.
- **PR Gate 3-옵션 독립**: `pr_review_comment`·`approve_mode`·`auto_merge+merge_threshold` 완전 독립. `post_pr_comment_from_result(result: dict, ...)` 사용 — `AiReviewResult` 객체 불필요. `run_gate_check` 시그니처: `(repo_name, pr_number, analysis_id, result, github_token, db, config: RepoConfigData | None = None)`.
- **build_analysis_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수. pipeline과 hook.py 두 곳에서 Analysis.result dict를 생성할 때 사용. `score`·`grade` 필드 포함.
- **GRADE 상수 단일 출처**: `src/constants.py`에 `GRADE_EMOJI`, `GRADE_COLOR_DISCORD`, `GRADE_COLOR_HTML`, `GRADE_COLOR_ANSI` 정의. 각 모듈에 로컬 정의 금지.
- **ChangedFile / github_api_headers 단일 출처**: `src/github_client/models.py`가 ChangedFile 정의 출처. `src/github_client/helpers.py`의 `github_api_headers(token)` 사용.
- **telegram_post_message**: `src/notifier/telegram.py`의 공용 헬퍼. `src/gate/telegram_gate.py`도 이 헬퍼 사용 — `httpx` 직접 import 금지.
- **get_repo_or_404**: `src/api/deps.py`의 `get_repo_or_404(repo_name, db)` 사용.
- **auto_merge GitHub 권한**: `merge_pr()`은 `repo` 스코프 또는 Fine-grained `pull_requests: write` 권한 필요. Branch Protection Rules가 있으면 APPROVE 후에도 Merge 실패 가능.
- **http_client 싱글톤 원칙**: 신뢰 API (GitHub/Telegram/Railway) 호출은 `src/shared/http_client.py::get_http_client()` 를 통해 연결 풀 재사용. 외부 untrusted URL (Discord/Slack/custom_webhook/n8n) 은 `src/notifier/_http.py::build_safe_client()` 사용. `async with httpx.AsyncClient()` 매번 생성 금지.
- **MergeAttempt 관측 (Phase F.1+F.2)**: `log_merge_attempt()`로 모든 머지 시도(성공·실패·deferred·terminal)를 DB에 기록 — `src/gate/engine.py::_run_auto_merge` **단일 출처**(자동/반자동 공통). 반자동(`src/webhook/providers/telegram.py::handle_gate_callback`)은 area=gate Q1 이후 `engine._run_auto_merge`에 위임하므로 자동 경로와 동일하게 retry 큐잉·SHA 가드·CI 재판별·terminal/deferred 알림·관측을 공유한다(반자동 인라인 `merge_pr`+`log_merge_attempt` 제거). `failure_reason`은 `src/gate/merge_reasons.py`의 정규 태그. **Phase F.3**: `engine.py::_run_auto_merge` 실패 시 `get_advice(reason)` + 조건부 `create_merge_failure_issue()` 호출 — `auto_merge_issue_on_failure` 필드(5-way sync 적용)로 Issue 생성 제어.
- 🔴 **반자동 auto-merge = 자동 경로 위임 (area=gate Q1)**: Telegram 반자동 승인(`handle_gate_callback`)의 auto-merge 는 `engine._run_auto_merge(config, github_token, repo_name, pr_number, score, analysis_id=...)`에 위임 — 가드는 `AutoMergeAction` 미러링: (1) `decision == "approve"`(reject 시 머지 금지) (2) `config.auto_merge` (3) `not result.get("static_analysis_incomplete")`(#779/#783) (4) `not ai_review_failed(result)`(#804 — api_error/parse_error 시 차단). `score >= merge_threshold` 체크는 `_run_auto_merge` 내부 단일 수행(중복 금지). 🔴 **리플레이 가드(#11)**: handle_gate_callback 은 위 부수효과(post_github_review·_run_auto_merge) **전에** `gate_decision_repo.claim_decision()`(insert-only UNIQUE analysis_id first-writer-wins)로 결정을 원자적 claim — 동일 서명 콜백 리플레이/동시 더블클릭 패자는 skip. 상세 룰: [`pipeline.md`](pipeline.md) GateDecision claim 항목.
- **notifier 공통 헬퍼**: `src/notifier/_common.py`의 `format_ref()`, `get_all_issues()` (호출자 캐시 권장), `truncate_message()`, `truncate_issue_msg()`를 사용.
- **webhook secret TTL 캐시**: `get_webhook_secret(full_name)` 함수가 `_webhook_secret_cache` dict에 5분(WEBHOOK_SECRET_CACHE_TTL=300초) TTL로 per-repo 시크릿을 캐시. 리포 시크릿 변경 후 최대 5분간 구 시크릿으로 검증.
- **Telegram 콜백 도메인 분리**: `_make_callback_token(bot_token, scope, payload_id)`이 `scope ∈ {"gate","cmd"}`별 다른 HMAC 생성. 신규 명령 추가 시 `cmd:<verb>:<id>:<token>` 준수, 64-byte 한도 검증. `test_callback_data_within_64_bytes_all_commands` 단위 테스트 강제.
- **Cron 엔드포인트 인증**: `POST /api/internal/cron/*`는 `INTERNAL_CRON_API_KEY` 전용 (admin key와 분리). Railway `[[deploy.cronJobs]]` 트리거. `hmac.compare_digest` 타이밍 안전 비교. 미설정 시 503 반환.
- **Telegram chat_id 라우팅 우선순위**: cron 알림의 chat_id 결정은 `analytics_service.resolve_chat_id(repo, config)` 단일 헬퍼 — `RepoConfig.notify_chat_id` → `Repository.telegram_chat_id` → `settings.telegram_chat_id` → None(skip + WARNING).
- **CI-aware Auto Merge 재시도**: `mergeable_state=unstable`+CI running 또는 `unknown` 상태일 때 단일 실패가 아닌 `merge_retry_queue` 큐잉. `check_suite.completed` 웹훅 또는 1분 cron 으로 재시도. 트리거: `src/services/merge_retry_service.py::process_pending_retries`. 첫 지연 시 Telegram 1회, 최종 성공/실패 시 1회. 중간 재시도는 무음.
- **`merge_pr` SHA atomicity**: `merge_pr(..., expected_sha=...)` 는 `PUT /pulls/{n}/merge` 에 `sha` 파라미터를 포함해 force-push 된 코드의 의도치 않은 머지를 GitHub 측에서 차단.
- **Webhook 이벤트 구독 갱신**: `create_webhook` 이벤트 목록은 `["push","pull_request","issues","check_suite"]`. 기존 등록 리포는 settings 페이지의 "Webhook 재등록" 버튼으로 갱신.
- 🔴 **외부 SDK timeout/max_retries 명시 의무 (Phase H PR-1A/1B-1)**: 새 외부 SDK (Anthropic/aiosmtplib/유사) 클라이언트 인스턴스화 시 `timeout` 명시 (Anthropic SDK = 60s, httpx 신뢰 API = `HTTP_CLIENT_TIMEOUT` = 10.0s — `src/constants.py`), `max_retries` 명시 (SDK 기본값과 동일 값이라도 명시). SDK 업그레이드로 default 변경 시 silent regression 차단. 회귀 가드 테스트 동반.
- 🔴 **5xx 자동 재시도 — 신뢰 API 한정 (Phase H PR-1B-2/2B)**: GitHub/Telegram/Anthropic/Railway 등 신뢰 API 의 일시 5xx + transient network error 는 자동 재시도 (exponential backoff, max 3회). Telegram 429 는 `retry_after` 파싱 + cap 30s. **외부 untrusted webhook (Discord/Slack/n8n/custom_webhook) 는 재시도 금지** — idempotency 보장 불가, 중복 발송 부작용. 채널별 (Telegram L80~ / GitHub graphql `_GRAPHQL_*` / Anthropic SDK `max_retries`) 인라인 구현.
- 🔴 **PyGithub 등 sync I/O 는 `asyncio.to_thread` wrap 의무 (Phase H PR-3A)**: async 컨텍스트(BackgroundTask, lifespan 등) 내부에서 sync HTTP 클라이언트 (PyGithub, requests) 호출 시 반드시 `asyncio.to_thread(fn, ...)` 로 wrap. 직접 호출 시 이벤트 루프 블록 → 다른 webhook/cron 정체.
- 🔴 **race-recovery 시그널 컨벤션 (Phase H PR-2A)**: 파이프라인 내 race recovery 분기는 `result_dict is None` 을 시그널로 사용. 호출자는 `if result_dict is None: skip notify` 로 명시적 처리.
- 🔴 **Rate limiting 데코레이터 의무 (사이클 142 Phase C A1 #675)**: 신규 API 엔드포인트 추가 시 `@limiter.limit(RATE_LIMIT_API)` 또는 `@limiter.limit(RATE_LIMIT_HEAVY)` 데코레이터 필수. 누락 시 DoS 취약.
  - `RATE_LIMIT_API = "60/minute"` — 조회성 엔드포인트 (GET, 상태 조회)
  - `RATE_LIMIT_HEAVY = "10/minute"` — 쓰기/삭제 엔드포인트 (PUT, DELETE, POST 고비용)
  - `src/middleware/rate_limiter.py:20-21` 상수 정의 출처 — 직접 문자열 작성 금지, import 사용
  - **예외**: `Depends(require_login)` 과 `@limiter.limit()` 조합 시 FastAPI 422 충돌 발생 가능 — `users.py` 인증 엔드포인트처럼 require_login 이 이미 DoS 보호 역할이면 미적용 허용 (PR 본문 정책 3 보고 의무)
  - 🔴 **예외 (webhook provider) — 사이클 165 회고 P2**: secret/HMAC 인증 webhook provider (`src/webhook/providers/*` — github/telegram/railway) 는 `@limiter` **미적용 컨벤션** (3 provider 전부 일관). 이유: (1) webhook secret + per-event HMAC 인증이 미인증 폭주를 동기 경로 401 에서 차단(claim INSERT 등 비용은 인증 통과 후 background task), (2) IP 기반 limiter(`get_remote_address`)가 단일 출처(Telegram/GitHub/Railway 서버 IP 풀) webhook 에 부정확 → 정상 콜백 오차단 위험이 추가 방어 이득보다 큼. 신규 webhook provider 추가 시 동일 컨벤션. (신규 **API** 엔드포인트는 위 의무 적용 — webhook 흉내로 limiter 누락 금지.)
- 🔴 **`asyncio.gather` 내부 shared Session 금지 (사이클 113 P0-H)**: `asyncio.gather()` 로 동시 실행되는 코루틴들이 단일 `Session` 인스턴스를 공유하면 SQLAlchemy identity map 오염 + 동시 `commit()` 충돌 발생. 각 코루틴은 `with SessionLocal() as db:` 블록을 독립적으로 열어야 함. 전례: `src/gate/engine.py` — `_run_approve_decision` + `_run_auto_merge` 를 gather 전에 db 파라미터 제거 후 각 함수 내부에서 독립 Session 생성으로 수정 (사이클 113 P0-H).
  - **올바른 패턴**: `await asyncio.gather(_run_approve_decision(...), _run_auto_merge(...))` — 각 함수 내부에서 `with SessionLocal() as db:` 독립 사용
  - **금지 패턴**: `await asyncio.gather(_run_approve_decision(db=db, ...), _run_auto_merge(db=db, ...))` — 동일 db 공유
  - 교차 참조: [`.claude/rules/pipeline.md`](.claude/rules/pipeline.md) (파이프라인 레이어 동일 규칙 — 사이클 115 PR #556 추가)
