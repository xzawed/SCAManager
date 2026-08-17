## 게이트 · 알림

`POST /webhooks/github`(`src/webhook/providers/github.py:583`) → HMAC 검증 → `HANDLED_EVENTS` 필터(push·pull_request·issues·check_suite, `src/constants.py:134`) → 파이프라인 → 알림(`src/worker/pipeline.py:324`) + 게이트(`src/gate/engine.py:83`).

### 게이트 3옵션 — 병렬·독립
`GATE_ACTIONS`(`src/gate/actions/__init__.py:68`)를 `is_applicable(config)` 로 거른 뒤 `asyncio.gather`. 각 액션은 자기 `SessionLocal()` 을 연다.

- review_comment — `pr_review_comment` 참이면 PR 리뷰 댓글
- approve — auto 면 `score >= approve_threshold` APPROVE / `< reject_threshold` REQUEST_CHANGES / 사이는 skip, semi-auto 면 Telegram 인라인 버튼(`src/gate/actions/approve.py:87`)
- auto_merge — `score >= merge_threshold` 면 squash merge

### 알림 채널 추가
1. `alembic revision` 으로 `repo_configs` 컬럼 추가 → `src/models/repo_config.py` 에 `Column` 1줄
2. `src/config_manager/manager.py:13` `RepoConfigData` 에 필드 1줄(기본 None)
3. `src/notifier/<채널>.py` — `name` · `is_enabled(ctx)` · `async send(ctx)` 후 `register()` — `send` 는 언어를 `resolve_notification_language(db, config=ctx.config)`(`src/notifier/_language.py:38`)로 풀고, 점수를 렌더하면 신뢰도 고지(`unreliable_score_warning_lines`)를 넣는다. **둘 다 빠져도 CI 는 초록이다.** 호출
4. `src/notifier/__init__.py` 에 `import src.notifier.<채널>` 1줄 — 빠지면 REGISTRY 미등록으로 조용히 미발송
5. `src/api/repos.py`(필드 + `:88` URL 검증 목록) · `src/ui/routes/settings.py:54,229` · `src/templates/settings.html` 폼
6. 문구는 `src/i18n/translations/{ko,en,ja}.json` 3개 전부
7. 외부 HTTP 는 `src/notifier/_http.py` 의 `validate_external_url` + `build_safe_client` 만(https·redirect 금지), 로깅은 `url_host_for_log`

### 임계값 변경
기본값 `src/constants.py:84-86` — approve 75 / reject 50 / merge 75. 리포별 값 검증은 `src/config_manager/manager.py:62` 하나뿐이다(0~100 · approve >= reject · merge >= reject). UI·REST 모두 `upsert_repo_config` 를 지난다.

### 자동 머지 차단 순서 (`src/gate/engine.py:123`부터)
1. `auto_merge and score >= merge_threshold` 아니면 반환
2. `static_analysis_incomplete` · `ai_review_truncated` · `ai_review_failed` 중 하나라도 참이면 중단(`src/gate/actions/auto_merge.py:47,57,67` — approve 도 같은 3가드)
3. 민감 경로 검사 `:135` — auth/·token·jwt·`webhook/validator.py` 등. 해제 `SENSITIVE_PATH_GUARD_DISABLED=1`
4. 2차 LLM 검증 `:140` — `OPENAI_API_KEY` 설정 시에만. 해제 `MERGE_VERIFIER_DISABLED=1`
5. 분석 SHA ≠ 현재 head 면 머지도 큐 등록도 안 한다
6. 실패는 `src/gate/merge_reasons.py` 태그로 분류 후 재시도 큐. 워커 60초(`src/scheduler.py:141`), `MERGE_RETRY_ENABLED=false` 면 즉시 머지 legacy

### 검증
`py -3 -m pytest tests/unit/gate tests/unit/notifier tests/unit/webhook` → `py -3 scripts/pre_push_gate.py`

채널을 추가하면 함께 고친다 — 빠뜨리면 parametrize 가 조용히 그 채널을 건너뛴다.

- `tests/unit/notifier/test_ssrf_log_redaction.py:110` `_CASES`/`_IDS`
- `tests/unit/notifier/test_score_reliability_disclosure_parity.py:28`
  `_EXPECTED_REGISTRY_SCORE_CHANNELS` + 렌더러 dispatch
- `docs/architecture.md:22` 의 `REGISTRY N` 개수·목록
- 전역 크리덴셜(봇 토큰류)을 쓰면 [deploy.md](deploy.md) §환경변수 추가를 함께 밟는다
