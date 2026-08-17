# SCAManager 아키텍처

FastAPI 단일 앱. GitHub Webhook → 정적분석 + Claude 리뷰 → 점수 → PR Gate → 알림까지
in-process 로 처리하고 결과를 대시보드로 낸다.

## src/ 트리

```
src/
├── main.py           # 앱 조립 — lifespan(alembic+http_client)·라우터·/static; add_middleware
│                     #   SecurityHeaders→LimitBodySize→Locale→RLSSession→Session→CORS(마지막=outermost)
├── config.py         # pydantic-settings Settings (정본 docs/reference/env-vars.md)
├── constants.py      # 배점·등급·HANDLED_EVENTS·PR_HANDLED_ACTIONS·타임아웃·TTL 단일 출처
├── crypto.py         # encrypt_token / decrypt_token
├── database.py       # engine·Base·FailoverSessionFactory·RLS 리스너·WorkerSessionLocal
├── logging_config.py # configure_logging(멱등) + 시크릿 리댁션 필터
├── scheduler.py      # 인앱 JOBS 6 — retry-pending-merges 60s·sweep-orphans 600s·trend/scan-security/retention/weekly
├── webhook/          # validator(HMAC)·loop_guard·_helpers(secret 캐시)·router
│   └── providers/    # github.py·telegram.py·railway.py
├── worker/           # pipeline.py — run_analysis_pipeline·build_notification_tasks
├── analyzer/
│   ├── pure/         # registry·language·review_prompt·review_guides(tier1~3+generic)
│   ├── io/           # static.py(Registry 위임)·ai_review.py(Claude)·tools/(22 어댑터)
│   └── configs/      # eslint `.mjs` 고정 — flat-config 로더가 ESM
├── scorer/           # calculator.py(calculate_score)·reliability.py(점수 신뢰도 판정)
├── gate/             # engine.py(run_gate_check)·actions/{approve,auto_merge,review_comment}·github_review·native_automerge·merge_verifier
├── notifier/         # __init__ 이 REGISTRY 등록 — telegram·discord·slack·webhook·email·n8n·commit_comment·create_issue
├── verifier/         # openai_client.py — 2nd-LLM 검증자 (SDK + httpx 폴백)
├── github_client/    # diff·issues·repos·checks·graphql·helpers·models
├── railway_client/   # 빌드 실패 웹훅 — models·logs·webhook
├── services/         # analytics·cron·dashboard·repo_insight·issue_registration·merge_retry·security_scan·saas·operations·cost_metrics
├── repositories/     # DB 접근 계층 — models/ 와 파일명 1:1 (+ claude_api_cost_repo)
├── models/           # ORM — repository·analysis·analysis_attempt·repo_config·gate_decision·merge_*·user 외
├── config_manager/   # manager.py — get_repo_config·upsert_repo_config·RepoConfigData
├── api/              # auth(API key)·deps·repos·stats·hook·users·repo_report·internal_cron·issues·admin
├── auth/             # session.py(require_login/require_admin)·github.py(OAuth)
├── ui/               # router·_helpers·routes/ 8종(overview·dashboard·settings·detail·admin 외)
├── shared/           # 횡단 헬퍼 — http_client·log_safety·ssrf·secure_compare·rls_context·*_metrics 외
├── middleware/       # rls_session·rate_limiter·locale
├── i18n/             # loader·filters·translations/(en·ko·ja)
├── templates/        # base·landing·overview·dashboard·repo_detail·repo_insights·analysis_detail·settings·admin_*
├── static/           # css/(tokens·themes·main·dist)·js/·vendor/·icons/·illustrations/
├── mcp/              # repo_report_tools.py — list_repo_reports·get_repo_report
├── cli/              # `python -m src.cli review` — git_diff·formatter
└── scripts/          # 일러스트 생성 도구 (production 미사용)
```

## 핵심 데이터 흐름

### 1. 수신 — `src/webhook/providers/github.py`

```
POST /webhooks/github → github_webhook()
  verify_github_signature(payload, X-Hub-Signature-256, get_webhook_secret(full_name)) → 401
  event ∉ HANDLED_EVENTS{push,pull_request,issues,check_suite} → ignored
  pull_request → _preprocess_pull_request()
      action ∉ PR_HANDLED_ACTIONS{opened,synchronize,reopened,closed,auto_merge_disabled} → ignored
      closed → _handle_merged_pr_event()(실머지 기록 + 이슈 close)
      auto_merge_disabled → _handle_auto_merge_disabled_event()
      synchronize → _handle_pr_synchronize()(구 SHA 재시도 행 포기) 후 진행
  issues → _handle_issues_event() · check_suite → _handle_check_suite_completed() → _trigger_retry_for_sha()
  _loop_guard_check()(봇·skip 마커) → _run_pipeline() → BackgroundTasks → 202
```

### 2. 분석 — `src/worker/pipeline.py::run_analysis_pipeline`

```
_extract_event_metadata() → _is_blank_sha() 면 return  브랜치/태그 삭제 push
_ensure_repo() → None 이면 _regate_pr_if_needed() 후 return  중복 SHA
_begin_attempt()  소실 흔적 — 비싼 작업 **전**에 쓰고 Analysis 영속화 직후 finish
_collect_files()  asyncio.to_thread — PyGithub 동기 I/O 격리
asyncio.gather(
    _run_static_with_timeout()  tools Registry, 타임아웃 시 static_incomplete 마커
    review_code()               AI_REVIEW_DISABLED 또는 RepoConfig.ai_review_enabled=False 면
                                API 호출 없이 disabled (정적분석은 계속)
)
calculate_score(analysis_results, ai_review)  배점 = docs/reference/scoring.md
_save_and_gate()
    find_by_sha() 재확인 → 중복이면 _race_recover_existing() → result_dict=None → notify skip
    save_new()                        DB unique 제약 first-writer-wins
    _persisted_score_is_unreliable()  AI 실패 시 score/grade NULL 저장
    pr_number 있으면 run_gate_check()
_finish_attempt()
build_notification_tasks() → NotifyContext → REGISTRY 순회 is_enabled()/send()
  → asyncio.gather(return_exceptions=True): telegram·discord·slack·webhook·email·n8n·
    commit_comment·create_issue
```

### 3. Gate — `src/gate/engine.py::run_gate_check` (PR 이벤트만)

```
GateContext → GATE_ACTIONS 중 is_applicable(config) 인 것만 asyncio.gather — 3옵션 독립
  ReviewCommentAction  pr_review_comment=on → PR 상세 리뷰 댓글
  ApproveAction        auto → score ≥ approve_threshold APPROVE / < reject_threshold REQUEST_CHANGES
                       semi → telegram_gate.send_gate_request() 인라인 키보드
  AutoMergeAction      auto_merge=on & score ≥ merge_threshold → engine._run_auto_merge()
      sensitive_paths  auth·마이그레이션·CI 워크플로 변경은 hold(재시도 집합 밖)
      merge_verifier   경계밴드 + OPENAI_API_KEY 시 2nd-LLM — unsafe/오류면 차단
      native_automerge.enable_or_fallback()  GraphQL → 실패 시 github_review.merge_pr() REST
      is_retriable_tag() & should_retry()  merge_retry 큐 → check_suite 웹훅/60초 job 이
                                           merge_retry_service.process_pending_retries() 실행
```

### 4. Telegram 반자동 콜백 · CLI Hook

```
POST /api/webhook/telegram  `gate:{decision}:{id}:{token}` HMAC + 리포 소유권 확인
  → gate_decision_repo.claim_decision()  원자적 claim — 리플레이·더블클릭 패자 skip
  → post_github_review() → approve & auto_merge 면 engine._run_auto_merge() 재사용

POST /repos/add  hook_token 발급 → Contents API 로 .scamanager/config.json + install-hook.sh
git push  GET /api/hook/verify(미등록이면 silent skip) → git diff → Anthropic Messages API
  → POST /api/hook/result (Analysis 저장) → exit 0 (push 는 항상 진행)
```

### 읽기 경로

HTML `/` · `/dashboard?mode={overview|insight|security|usage|repos}` · `/repos/add` ·
`/repos/{repo}[/insights|/settings|/analyses/{id}]` · `/admin/{tenants,rls-audit,operations}`.
JSON 은 같은 자원의 `/api/…` 대응 + `/api/internal/cron/*`(`scheduler.JOBS` 와 1:1).

## 파일을 추가·삭제·이름변경했다면

1. 위 트리에 한 줄(경로 + 역할)을 넣는다 — `scripts/check_architecture_tree_sync.py` 가 실제 `src/`
   패키지·최상위 모듈을 이 문서 **코드펜스 안** 트리 엔트리와 대조한다.
2. 흐름이 바뀌면 해당 블록의 함수명을, 신규 환경변수는 `docs/reference/env-vars.md` 를 갱신한다.
3. `py -3 scripts/pre_push_gate.py` 로 로컬 게이트를 돌린다.
