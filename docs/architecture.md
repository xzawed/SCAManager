# SCAManager 아키텍처

FastAPI 단일 앱 — Webhook → 정적분석+Claude 리뷰 → 점수 → PR Gate → 알림 in-process, 결과는 대시보드.

## src/ 트리

```
src/
├── main.py  # 앱 조립 — lifespan(alembic+http_client)·라우터
│  SecurityHeaders→LimitBodySize→Locale→RLSSession→Session→CORS(outermost)
├── config.py  # Settings — 정본 docs/reference/env-vars.md
├── constants.py  # 배점·등급·HANDLED_EVENTS·PR_HANDLED_ACTIONS·타임아웃 SSOT
├── crypto.py
├── database.py  # engine·Base·FailoverSessionFactory·RLS 리스너
├── logging_config.py  # 멱등 설정·시크릿 리댁션
├── scheduler.py  # 인앱 JOBS 6 — `/api/internal/cron/*` 와 1:1
├── webhook/  # HMAC 검증·loop_guard · providers/{github,telegram,railway}
├── worker/
├── analyzer/  # pure/ · io/(static·ai_review·tools/ 23) · configs/(eslint=`.mjs`)
├── scorer/
├── gate/  # engine·actions/·native_automerge·merge_verifier
├── notifier/  # REGISTRY 8 — telegram·discord·slack·webhook·email·n8n·github_{commit_comment,issue}
├── verifier/  # 2nd-LLM(OpenAI)
├── github_client/  # PyGithub 래퍼
├── railway_client/  # 빌드 실패 웹훅
├── services/  # dashboard·merge_retry·security_scan·saas·operations
├── repositories/  # models/ 와 파일명 1:1
├── models/
├── config_manager/  # 리포 설정 read/upsert
├── api/
├── auth/  # 세션 가드·GitHub OAuth
├── ui/
├── shared/  # http_client·log_safety·ssrf·secure_compare·rls_context
├── middleware/  # rls_session·rate_limiter·locale
├── i18n/  # translations/(en·ko·ja)
├── templates/
├── static/
├── mcp/
├── cli/  # `python -m src.cli review`
└── scripts/  # production 미사용
```

## 핵심 데이터 흐름

```
POST /webhooks/github (webhook/providers/github.py)
  HMAC 실패 → 401 · HANDLED_EVENTS·PR_HANDLED_ACTIONS 밖 → ignored
  synchronize → 구 SHA 포기 · check_suite → _trigger_retry_for_sha()
  loop_guard(봇·skip 마커) → BackgroundTasks → 202
run_analysis_pipeline() (worker/pipeline.py)
  blank·중복 SHA → 조기 return · gather(정적, review_code()) 타임아웃 → static_incomplete 마커
  AI off(AI_REVIEW_DISABLED·RepoConfig.ai_review_enabled) → disabled, 정적은 계속
  배점 = docs/reference/scoring.md → find_by_sha() 재확인(중복이면 notify skip)
  save_new() first-writer-wins · AI 실패 시 score/grade NULL · pr_number 면 run_gate_check()
  알림 = REGISTRY send() gather
run_gate_check() PR 만 (gate/engine.py)
  GATE_ACTIONS(ReviewComment·Approve·AutoMerge) 중 is_applicable(config) 만 gather — 3옵션 독립
  Approve ≥approve_threshold APPROVE / <reject_threshold REQUEST_CHANGES(auto) ·
   semi = telegram_gate.send_gate_request() 인라인 키보드
  AutoMerge ≥merge_threshold · sensitive_paths(auth·마이그레이션·CI) → hold ·
   merge_verifier 경계밴드 2nd-LLM unsafe → 차단 · native_automerge GraphQL → 실패 시 REST merge_pr()
   재시도 태그 → merge_retry 큐(check_suite 웹훅·60초 job → process_pending_retries())

POST /api/webhook/telegram `gate:{decision}:{id}:{token}` HMAC+소유권 →
  claim_decision() 원자적(리플레이·더블클릭 패자 skip) → post_github_review()
POST /repos/add hook_token 발급 · Contents API → .scamanager/config.json + install-hook.sh
git push → /api/hook/verify(미등록 시 skip) → git diff → Anthropic API → /api/hook/result → exit 0
읽기 — `/dashboard?mode={overview|insight|security|usage|repos}` ·
 `/repos/{repo}[/insights|/settings|/analyses/{id}]` · `/admin/*` · JSON=`/api/…`
```

파일 추가·삭제 시 트리 펜스에 한 줄 — `scripts/check_architecture_tree_sync.py` 가 실제 `src/`
패키지·모듈을 그 펜스와 대조한다.
