# 2026-07-23 종합 코드+문서 검증 — 아카이브 보고서 (스냅샷)

> 이 파일은 **불변 스냅샷**이다. 현재 상태·이월분은 [docs/backlog.md](../../backlog.md) 가 SSOT.
> 회고 P1-C(2026-07-24) — 감사 결정 기록을 리포 안에 남긴다(메모리-only observer-lie 시정).

## 감사 개요
- 다이나믹 워크플로우 `comprehensive-review.mjs`: 10 렌즈 × loop-until-dry × 3-skeptic 적대 verify + completeness critic
- **339 에이전트 · 34.8M 토큰 · 97분 → 확정 64(P0 0 · P1 11 · P2 53) · FP 32 · verdict_coverage 1.0**
- P1 11건: 10 봉인(#1186~#1193) + P1-5(#1194). P2 53건: 아래.

## P2 53건 — disposition

### ✅ 처리 완료 (21건 — #1195~#1201)

- [2C/1FP/3] (error-failmode) src/github_client/checks.py:289 — _required_contexts_cache is unbounded — no size cap, no stale-entry eviction (violates the codebase's own cache-bound invariant)
- [3C/0FP/3] (data-integrity-orm) src/repositories/claude_api_cost_repo.py:75 — claude_api_calls / dashboard_kpi compare aware Python datetimes against naive DateTime columns — diverges from the project's documented `_now_naive()` convention, making cost/KPI window boundaries PG-session-timezone-dependent
- [3C/0FP/3] (edge-input) src/analyzer/io/ai_review.py:293 — AI 응답의 문자열 필드가 null이면 사용자 노출 요약/피드백에 리터럴 "None" 문자열이 표시됨
- [3C/0FP/3] (edge-input) src/cli/formatter.py:109 — file_feedbacks 원소가 dict가 아니면 CLI format_result가 AttributeError로 크래시 (`make review` 로컬 리뷰)
- [3C/0FP/3] (resource-limits) src/github_client/checks.py:289 — _required_contexts_cache is an unbounded module-level cache (no size cap, no stale eviction)
- [3C/0FP/3] (resource-limits) src/webhook/loop_guard.py:106 — BotInteractionLimiter._events grows unbounded in key count (empty deques never removed, no MAX_KEYS cap)
- [3C/0FP/3] (collab-structure) docs/architecture.md:139 — architecture.md scripts/ 인벤토리가 배선된 가드 2종을 누락 — 6-step ⑥ drift + Grok grep-discoverability 저하
- [3C/0FP/3] (collab-structure) .claude/rules/security.md:3 — 보안 통제 모듈(SSRF·RLS·secure_compare)이 security.md 본문엔 있으나 paths 프론트매터엔 없어 편집 시 규칙 미로드 — logging_config 사고 재발 클래스
- [3C/0FP/3] (error-failmode) src/main.py:209 — 기동 경고가 '스케줄 cron 이 503 으로 실행 안 됨'이라고 단언 — 인앱 스케줄러 도입(2026-07-19) 후 사실과 반대라 운영자 오진단 유발
- [3C/0FP/3] (security-authz) src/api/hook.py:113 — hook_token accepted via ?token= query param leaks into access logs — not covered by the secret-redaction filter
- [3C/0FP/3] (api-webhook-contract) src/gate/engine.py:659 — engine._notify_merge_failure가 raw exc를 %s로 로깅 — Telegram bot-token URL이 트레이스백에 실림(형제 notify 함수는 전부 type(exc).__name__ 사용, 계층1 근본통제 위반)
- [2C/1FP/3] (api-webhook-contract) src/notifier/telegram.py:168 — Telegram HTML 메시지 truncate가 구조 무인지 — 4096자 초과 시 escape된 엔티티/태그 중간을 잘라 Telegram 400 'can't parse entities'로 상시 채널 알림 전량 소실
- [3C/0FP/3] (edge-input) src/notifier/github_comment.py:136 — file_feedbacks 원소의 issues가 JSON null이면 GitHub PR 코멘트 빌더·CLI가 TypeError로 크래시 (코멘트 무음 실패)
- [3C/0FP/3] (collab-structure) .claude/rules/security.md:36 — Security-rule coverage guard is scoped only to logging.Filter subclasses — the 'control code decoupled from its rule' class recurs at github_client/repos.py path-injection defense
- [3C/0FP/3] (error-failmode) src/services/cron_service.py:167 — cron_service telegram 발신 실패 시 raw exc 를 %s 로 로깅 — bot-token URL 유출 경로 (이미 보고된 engine._notify_merge_failure 와 동일 클래스의 미보고 인스턴스 2건)
- [3C/0FP/3] (api-webhook-contract) src/github_client/checks.py:148 — get_ci_status legacy Commit-Status fallback ignores required_contexts, so non-required check failures cause mergeable 'unstable' PRs to be prematurely abandoned as terminal
- [3C/0FP/3] (edge-input) src/api/hook.py:242 — hook.py가 CLI ai_result의 텍스트/리스트 필드를 타입 강제하지 않아 재게이트 시 PR 코멘트가 무음 붕괴 (ai_review._parse_response 파리티 이탈)
- [3C/0FP/3] (correctness-logic) src/services/analytics_service.py:112 — analytics_service compares aware-UTC datetimes against the naive Analysis.created_at column — weekly-report/trend-alert window boundaries are PG-session-timezone-dependent
- [3C/0FP/3] (data-integrity-orm) src/models/analysis_attempt.py:72 — analysis_attempts.started_at is INSERTed timezone-aware but the loss-detection sweep compares it against a NAIVE-UTC cutoff — orphan detection becomes PG-session-timezone dependent
- [2C/1FP/3] (collab-structure) .claude/rules/api.md:8 — src/github_client/(8모듈) + src/scheduler.py가 어떤 path-scoped rule에도 안 걸림 — Claude auto-load·Grok grep 양쪽에서 area 규칙 0
- [2C/0FP/2] (error-failmode) src/api/hook.py:243 — CLI hook result endpoint does not coerce non-score AI fields (asymmetric with pipeline _parse_response) — persists JSON null into Analysis.result

### ▶️ 이월 (32건 — docs/backlog.md 로 이관, 아래는 스냅샷)

- [3C/0FP/3] (correctness-logic) src/gate/actions/approve.py:104 — 민감 경로 가드가 auto-merge 경로에만 있고 auto-approve 경로에는 누락 — 동일 위협모델을 방어하는 다른 3개 가드와 비대칭
- [2C/1FP/3] (concurrency-idempotency) src/repositories/merge_retry_repo.py:329 — check_suite force-due 트리거가 매 완료마다 attempts_count 를 소진 — CI 이벤트 많은 리포에서 머지 가능한 PR 조기 abandon 가능
- [3C/0FP/3] (security-authz) src/notifier/_common.py:77 — escape_markdown claims to block 'mention injection' but does not escape '@' — GitHub @-mention injection via static-tool messages
- [3C/0FP/3] (api-webhook-contract) src/github_client/repos.py:217 — Pre-push hook re-embeds the fixed max_tokens truncation bug (2048 < ~2660 needed for Korean review JSON)
- [3C/0FP/3] (resource-limits) src/services/dashboard_service.py:304 — frequent_issues_v2 loads a full 365-day Analysis result-blob set into memory with no row limit
- [3C/0FP/3] (resource-limits) src/services/security_scan_service.py:78 — _fetch_alerts caps alerts at per_page=100 with no pagination — silent truncation beyond 100
- [3C/0FP/3] (collab-structure) scripts/check_guard_fail_open.py:76 — fail-open floor 가드(B8)의 면제 판정이 스스로 bare-substring fail-open — 산문 언급만으로 면제됨
- [3C/0FP/3] (correctness-logic) src/gate/merge_verifier.py:63 — 2nd-LLM verifier's manipulation/injection check is bypassed by high scores — the band restriction contradicts the verifier's own stated purpose
- [3C/0FP/3] (error-failmode) src/services/security_scan_service.py:90 — _fetch_alerts 가 GitHub 403(rate-limit)을 'GHAS 비활성'으로 오분류 — rate-limit 시 보안 alert 을 조용히 0 으로 보고
- [3C/0FP/3] (concurrency-idempotency) src/services/issue_registration_service.py:74 — register_issue 의 IntegrityError(TOCTOU 중복) 분기가 이미 생성된 중복 GitHub Issue 를 로그 없이 폐기 — SQLAlchemyError orphan 로깅과 비대칭
- [3C/0FP/3] (api-webhook-contract) src/webhook/providers/github.py:96 — PR 머지 시 'Closes #N' 이슈를 base 브랜치 무관하게 무조건 close — GitHub은 default 브랜치 머지만 close하므로 비-default 브랜치 머지 시 이슈 조기 종료
- [3C/0FP/3] (ui-template-i18n) src/templates/analysis_detail.html:1226 — analysis_detail 이슈등록 패널이 htmx:historyRestore 재초기화 미배선 — 뒤로가기 후 탭/등록 버튼 죽음 (같은 파일 형제 블록과 비대칭)
- [3C/0FP/3] (ui-template-i18n) src/templates/overview.html:225 — overview 카드가 avg_score 0(진짜 0점)을 Jinja truthiness 로 숨김 — 등급 배지는 표시되나 점수바/숫자 누락(대시보드 is not none 패턴과 불일치)
- [3C/0FP/3] (ui-template-i18n) src/templates/add_repo.html:267 — add_repo 스크립트가 historyRestore 미배선 — 뒤로가기 후 select change 리스너 소실로 submit 버튼 영구 disabled(리포 추가 불가)
- [1C/1FP/3] (collab-structure) tests/unit/scripts/test_guard_wiring_coverage.py:123 — Dead-wiring detector for hook references is tautological — can never catch a settings.json reference to a missing/renamed hook (4 PreToolUse/PostToolUse hooks unguarded)
- [3C/0FP/3] (collab-structure) scripts/check_guard_fail_open.py:67 — B8 fail-open floor guard cannot see aliased/from-imported structural tools — false-flags legitimate structural guards using `import re as _re`
- [2C/1FP/3] (correctness-logic) src/services/merge_retry_service.py:92 — 재시도 큐: transient 인프라/토큰/PR-fetch 실패가 attempts_count 를 소진 — 코드가 자신의 명시 의도('do NOT bump attempts_count')를 위반해 지속 장애 시 머지 가능한 PR 을 조용히 max_attempts_exceeded 로 포기
- [3C/0FP/3] (concurrency-idempotency) src/repositories/merge_retry_repo.py:493 — abandon_stale_for_pr blind-clears an in-flight retry claim (webhook↔worker lost-update, distinct from the reported worker↔worker stale-reclaim)
- [2C/1FP/3] (concurrency-idempotency) src/services/cron_service.py:111 — Weekly report / trend-check senders keep no 'already-sent' record — manual cron endpoint overlapping the scheduled run double-sends on a single instance
- [3C/0FP/3] (api-webhook-contract) src/webhook/providers/github.py:120 — Merged-PR webhook closes referenced issues synchronously inline in the request handler (not a BackgroundTask), risking GitHub's ~10s webhook delivery timeout
- [3C/0FP/3] (resource-limits) src/services/cron_service.py:131 — cron notify jobs hold one shared worker DB connection across an unbounded repo loop while blocking on per-repo Telegram I/O (incl. up to 30s 429 sleeps)
- [3C/0FP/3] (ui-template-i18n) src/templates/dashboard.html:579 — dashboard.html injects a chart label into a JS single-quoted string via HTML-escape (| e) instead of | tojson — latent i18n rendering corruption, inconsistent with the sibling label 690 lines later
- [3C/0FP/3] (error-failmode) src/notifier/telegram.py:214 — Telegram analysis-notify channel is dead for repos configured with only a per-repo notify_chat_id (no global TELEGRAM_CHAT_ID), while cron paths still deliver to that same chat — silent, asymmetric skip
- [3C/0FP/3] (security-authz) src/webhook/_helpers.py:60 — get_webhook_secret caches the fallback (global/empty) secret on a transient DB error, poisoning per-repo webhook auth for the full TTL
- [2C/1FP/3] (data-integrity-orm) src/repositories/merge_retry_repo.py:251 — merge_retry_repo.enqueue_or_bump: find-then-INSERT against partial-unique index with NO IntegrityError handling and NO rollback (asymmetric with every sibling first-writer-wins repo)
- [2C/0FP/3] (resource-limits) src/repositories/claude_api_cost_repo.py:81 — 비용 집계가 30일 윈도우의 ClaudeApiCall 행 전량을 Python 으로 로드해 합산(SQL SUM 부재) + claude_api_calls 테이블은 retention GC 대상에서 누락(무한 증가)
- [3C/0FP/3] (resource-limits) src/repositories/security_alert_log_repo.py:141 — count_by_classification 이 사용자 alert-log 전체 행을 LIMIT 없이 로드해 Python 으로 카운트(SQL GROUP BY 부재) + security_alert_process_logs 도 retention GC 부재
- [3C/0FP/3] (resource-limits) src/services/analytics_service.py:108 — 일일 트렌드 cron 이 전체 repo(find_all, 상한 없음)를 순회하며 repo 당 moving_average 를 2회 호출 — 각 호출이 윈도우 점수 행 전량을 Python 으로 로드해 평균(SQL AVG 부재)
- [3C/0FP/3] (ui-template-i18n) src/static/js/tweaks.js:35 — tweaks.js (design-playground controller) is loaded on every page and forces <html data-theme="dark"> from a never-written localStorage key, desyncing html from body's real theme
- [3C/0FP/3] (collab-structure) tests/unit/scripts/test_guard_wiring_coverage.py:61 — 가드 배선 커버리지 테스트가 '경로 형태 주석'을 실제 호출로 오판 — 불변식3 집행 가드가 스스로 불변식1(fail-open) 위반
- [3C/0FP/3] (collab-structure) scripts/check_architecture_tree_sync.py:66 — architecture 트리 싱크 가드가 교차 디렉토리 substring 충돌로 src/scripts/ 미등재를 못 잡는 fail-open
- [3C/0FP/3] (error-failmode) src/services/cron_service.py:156 — cron run_weekly_reports / run_trend_check hold the worker DB connection across per-repo sequential Telegram network I/O with no repo cap (missed sibling of scan_all_repos)
