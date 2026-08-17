# SCAManager 아키텍처

FastAPI 단일 앱. Webhook → 정적분석 + Claude 리뷰 → 점수 → PR Gate → 알림을 in-process 로 처리하고
결과를 대시보드로 낸다.

## src/ 트리

```
src/
├── main.py           # 앱 조립 — lifespan(alembic+http_client)·라우터
│                     #   SecurityHeaders→LimitBodySize→Locale→RLSSession→Session→CORS(outermost)
├── config.py         # Settings — 정본 docs/reference/env-vars.md
├── constants.py      # 배점·등급·HANDLED_EVENTS·PR_HANDLED_ACTIONS·타임아웃 SSOT
├── crypto.py         # encrypt_token/decrypt_token
├── database.py       # engine·Base·FailoverSessionFactory·RLS 리스너
├── logging_config.py # 멱등 설정·시크릿 리댁션
├── scheduler.py      # 인앱 JOBS 6 — `/api/internal/cron/*` 와 1:1
├── webhook/          # HMAC 검증·loop_guard · providers/{github,telegram,railway}
├── worker/           # pipeline.py — 분석 파이프라인
├── analyzer/         # pure/ · io/(static·ai_review·tools/ 23) · configs/(eslint 은 `.mjs`)
├── scorer/           # 점수 계산·신뢰도 판정
├── gate/             # engine·actions/·native_automerge·merge_verifier
├── notifier/         # REGISTRY — telegram·discord·slack·webhook·email·n8n·github_commit_comment·github_issue
├── verifier/         # 2nd-LLM(OpenAI) 검증자
├── github_client/    # PyGithub 래퍼 — diff·issues·checks·graphql
├── railway_client/   # 빌드 실패 웹훅
├── services/         # dashboard·merge_retry·security_scan·saas·operations 외
├── repositories/     # DB 접근 — models/ 와 파일명 1:1
├── models/
├── config_manager/   # 리포 설정 read/upsert
├── api/
├── auth/             # 세션 가드 · GitHub OAuth
├── ui/
├── shared/           # http_client·log_safety·ssrf·secure_compare·rls_context 외
├── middleware/       # rls_session·rate_limiter·locale
├── i18n/             # translations/(en·ko·ja)
├── templates/
├── static/
├── mcp/              # repo_report 도구
├── cli/              # `python -m src.cli review`
└── scripts/          # 일러스트 생성 (production 미사용)
```

## 핵심 데이터 흐름

```
POST /webhooks/github → github_webhook()  (webhook/providers/github.py)
  verify_github_signature()(X-Hub-Signature-256) 실패 → 401
  event·action 이 constants.HANDLED_EVENTS · PR_HANDLED_ACTIONS 밖이면 ignored
  closed → _handle_merged_pr_event() · synchronize → _handle_pr_synchronize()(구 SHA 포기)
  check_suite → _handle_check_suite_completed() → _trigger_retry_for_sha()
  _loop_guard_check()(봇·skip 마커) → _run_pipeline() → BackgroundTasks → 202

run_analysis_pipeline()  (worker/pipeline.py)
  blank SHA·중복 SHA → 조기 return · _begin_attempt() → _collect_files()(to_thread)
  gather(_run_static_with_timeout(), review_code())  타임아웃 → static_incomplete 마커
      AI 리뷰 off(AI_REVIEW_DISABLED·RepoConfig.ai_review_enabled) → disabled, 정적은 계속
  calculate_score()  배점 = docs/reference/scoring.md
  _save_and_gate()  find_by_sha() 재확인 → 중복이면 notify skip · save_new() first-writer-wins
      AI 실패 시 score/grade NULL 저장 · pr_number 면 run_gate_check()
  _finish_attempt() → build_notification_tasks() → REGISTRY send() gather

run_gate_check()  PR 이벤트만  (gate/engine.py)
  GATE_ACTIONS 중 is_applicable(config) 만 gather — 3옵션 독립
  ReviewCommentAction  pr_review_comment=on → PR 리뷰 댓글
  ApproveAction    auto: ≥approve_threshold APPROVE / <reject_threshold REQUEST_CHANGES
                   semi: telegram_gate.send_gate_request() 인라인 키보드
  AutoMergeAction  auto_merge=on & ≥merge_threshold → _run_auto_merge()
      sensitive_paths(auth·마이그레이션·CI) → hold · merge_verifier 경계밴드 2nd-LLM unsafe → 차단
      native_automerge.enable_or_fallback() GraphQL → 실패 시 REST merge_pr()
      재시도 가능 태그 → merge_retry 큐. check_suite 웹훅/60초 job 이 process_pending_retries()
```

그 밖의 진입점

```
POST /api/webhook/telegram  `gate:{decision}:{id}:{token}` HMAC + 소유권 확인 →
  claim_decision()(원자적 — 리플레이·더블클릭 패자 skip) → post_github_review() → _run_auto_merge()
POST /repos/add → hook_token 발급 · Contents API 로 .scamanager/config.json + install-hook.sh
git push → /api/hook/verify(미등록 시 skip) → git diff → Anthropic API → /api/hook/result → exit 0
```

읽기 경로 — `/` · `/dashboard?mode={overview|insight|security|usage|repos}` ·
`/repos/{repo}[/insights|/settings|/analyses/{id}]` · `/admin/*`, JSON 은 `/api/…` 대응.

## 파일을 추가·삭제·이름변경했다면

트리 코드펜스에 한 줄을 넣는다 — `scripts/check_architecture_tree_sync.py` 가 실제 `src/`
패키지·최상위 모듈을 그 펜스와 대조한다. 신규 환경변수는 `docs/reference/env-vars.md`.
