## 게이트 · 알림

POST `src/webhook/providers/github.py::/webhooks/github.` → HMAC 검증 → `src/constants.py::HANDLED_EVENTS` 필터 → 파이프라인 → 알림(`src/worker/pipeline.py::async def _send_notifications`) + 게이트(`src/gate/engine.py::a.is_applicable(config)`).

### 게이트 3옵션 — 병렬·독립
`src/gate/actions/__init__.py::GATE_ACTIONS:` 를 `is_applicable(config)` 로 거른 뒤 `asyncio.gather`. 각 액션은 자기 `SessionLocal()` 을 연다.

- review_comment — `pr_review_comment` 참이면 PR 리뷰 댓글
- approve — auto 면 `score >= approve_threshold` APPROVE / `< reject_threshold` REQUEST_CHANGES / 사이는 skip, semi-auto 면 Telegram 인라인 버튼(`src/gate/actions/approve.py::def _run_semi_auto`)
- auto_merge — `score >= merge_threshold` 면 squash merge

### 알림 채널 추가
1. `alembic revision` 으로 `repo_configs` 컬럼 추가 → `src/models/repo_config.py` 에 `Column` 1줄
2. `src/config_manager/manager.py::class RepoConfigData` 에 필드 1줄(기본 None)
3. `src/notifier/<채널>.py` — `name` · `is_enabled(ctx)` · `async send(ctx)` 후 `register()` — `send` 는 언어를 `src/notifier/_language.py::def resolve_notification_language`(db, config=ctx.config)로 풀고, 점수를 렌더하면 신뢰도 고지(`unreliable_score_warning_lines`)를 넣는다. **둘 다 빠져도 CI 는 초록이다.**
4. `src/notifier/__init__.py` 에 `import src.notifier.<채널>` 1줄 — 빠지면 REGISTRY 미등록으로 조용히 미발송
5. `src/api/repos.py`(필드 + `src/api/repos.py::def validate_webhook_url` URL 검증 목록) · `src/ui/routes/settings.py::WEBHOOK_URL_FIELDS =` · `src/templates/settings.html` 폼
6. 문구는 `src/i18n/translations/{ko,en,ja}.json` 3개 전부
7. 외부 HTTP·로깅은 [security.md](security.md) 「새 코드에 붙이는 것」의 외부 URL 규칙을 따른다

### 임계값 변경
기본값 `src/constants.py::GATE_DEFAULT_APPROVE_THRESHOLD`. 리포별 값 검증은 `src/config_manager/manager.py::def _validate_thresholds` 하나뿐이다(0~100 · approve >= reject · merge >= reject). UI·REST 모두 `upsert_repo_config` 를 지난다.

### 자동 머지 차단 순서
1. `src/gate/engine.py::config.auto_merge and score >=` merge_threshold 아니면 반환
2. `static_analysis_incomplete` · `ai_review_truncated` · `ai_review_failed` 중 하나라도 참이면 중단(`src/gate/actions/auto_merge.py::static_analysis_incomplete"` — approve 도 같은 3가드)
3. 민감 경로 검사 `src/gate/engine.py::sensitive_paths_block_merge  #` — auth/·token·jwt·`webhook/validator.py` 등. 해제 `SENSITIVE_PATH_GUARD_DISABLED=1`
4. 2차 LLM 검증 `src/gate/engine.py::verifier_blocks_merge  #` — `OPENAI_API_KEY` 설정 시에만. 해제 `MERGE_VERIFIER_DISABLED=1`
5. 분석 SHA ≠ 현재 head 면 머지도 큐 등록도 안 한다
6. 실패는 `src/gate/merge_reasons.py` 태그로 분류 후 재시도 큐. 워커 60초(`src/scheduler.py::retry-pending-merges":`), `MERGE_RETRY_ENABLED=false` 면 즉시 머지 legacy

### 페이지 Claude 호출 (`src/services`)
다섯 다 넣는다 — `new_async_anthropic(..., retry_after_cap=ANTHROPIC_RETRY_AFTER_CAP_PAGE_SECONDS)` · await 전 `src/services/repo_insight_service.py::release_session_before_claude(db)` · `try` **안의** `src/services/dashboard_service.py::async with asyncio.timeout(ANTHROPIC_PAGE_DEADLINE_SECONDS)`(밖이면 기록·라벨이 빠진다) · `recent_error*` 적중이면 호출 생략 · await 앞뒤 동기 DB(비용 로그 포함)는 `run_in_threadpool`. 새로 고침은 라우트가 무효화 후 `src/ui/_helpers.py::redirect_without_refresh` 로 303. CI 는 팩토리 경유만 본다(`tests/unit/shared/test_anthropic_retry_after_cap.py::test_only_the_factory`) — 나머지는 틀려도 초록.

### 검증
`py -3 -m pytest tests/unit/gate tests/unit/notifier tests/unit/webhook`

채널을 추가하면 함께 고친다 — 빠뜨리면 parametrize 가 조용히 그 채널을 건너뛴다.

- `tests/unit/notifier/test_ssrf_log_redaction.py::_CASES =` · `_IDS`
- `tests/unit/notifier/test_score_reliability_disclosure_parity.py::_EXPECTED_REGISTRY_SCORE_CHANNELS =` + 렌더러 dispatch
- `docs/architecture.md::REGISTRY 8` 의 `REGISTRY N` 개수·목록
- 전역 크리덴셜(봇 토큰류)을 쓰면 [deploy.md](deploy.md) §환경변수 추가를 함께 밟는다
