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

- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀. 단, push 이벤트 먼저 처리 후 PR 이벤트 도착 시(`pr_number=None` Analysis 존재) `_regate_pr_if_needed()`가 `pr_number`를 부여하고 `run_gate_check` 재실행 — 알림 재발송 없음. 🔴 **first-writer-wins (사이클 164 #794)**: 기존 Analysis 의 `pr_number`가 이미 **다른 non-None 값**이면 덮어쓰지 않고 WARNING 후 skip — `_race_recover_existing`(동시 insert race 경로)과 대칭. 동일 head SHA를 두 PR이 공유할 때 댓글/승인/auto-merge가 잘못된 PR에 적용되는 것을 차단. 즉 `pr_number` 갱신은 **None → 최초 PR# 1회만** (동일 PR# 재수신은 no-op).
- 🔴 **정적분석 타임아웃/격리 (사이클 164 #795)**: `_run_static_with_timeout`는 `PIPELINE_ANALYSIS_TIMEOUT`(60s) **deadline 기반 파일별 순차** 실행 — (1) 타임아웃 시 완료된 파일 **부분결과 보존**(이전: 전량 폐기) + `incomplete=True`, (2) 단일 파일 `analyze_file` 예외는 빈 `StaticAnalysisResult`로 **격리**(나머지 파일·AI리뷰 계속), (3) **비어있지 않은 배치 전량 실패 → `incomplete=True`**(fail-closed 안전망). `incomplete`(`static_analysis_incomplete` 마커)는 `_save_and_gate`가 `Analysis.result`에 영속 → `AutoMergeAction`/`ApproveAction`이 읽어 auto-merge/auto-approve 차단(#779/#783). 일부 파일만 실패는 incomplete 아님(만점 인플레 미세 위험 수용 — Q2=A 결정).
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened`만 처리, `closed`/`labeled` 등은 무시.
- **AI 점수 스케일링**: Claude는 commit 0-20, direction 0-20, test 0-10으로 반환 → calculator가 commit 0-15, direction 0-25, test 0-15로 스케일링. `round()` 사용으로 banker's rounding 적용.
- **commit_scamanager_files**: GitHub Contents API `PUT /repos/{owner}/{repo}/contents/{path}` 사용. 파일 이미 있으면 GET으로 sha 조회 후 body에 포함해야 200 성공 (sha 누락 시 422 에러).
- **다언어 AI 리뷰**: `language.py`가 50개 언어를 감지(확장자·shebang·파일명), `review_prompt.py`가 언어별 체크리스트를 토큰 예산(8000 토큰) 내에서 조립. 비-코드 파일만 변경 시 테스트 점수 면제(test_score=10 → 15/15).
- **Analyzer Registry**: `src/analyzer/pure/registry.py` 의 REGISTRY 전역 목록 + `register()` (동일 name 중복 등록 방지). `src/analyzer/io/static.py` 가 `import src.analyzer.io.tools.{python,semgrep,eslint,shellcheck,cppcheck,slither,rubocop,golangci_lint}` 로 각 Analyzer 모듈 로드 → 모듈 import 시점에 자동 `register()` 호출. Phase S.3-B 이후 `pure/` vs `io/` 분리 구조.
- **category 기반 점수 집계**: `AnalysisIssue.category`("code_quality"|"security") 기준으로 점수 계산. tool 이름 무관 — 새 정적분석 도구 추가 시 category만 올바르게 설정하면 점수에 자동 반영. `CQ_WARNING_CAP=25` 단일 cap (구 pylint 15 + flake8 10 통합).
- **review_guides 구조**: `get_guide(lang, "full"|"compact")` — Tier1 full ~500토큰, compact 1줄. N≤3 전체 full, N≤6 Tier1 full+나머지 compact, N>10 상위 5개 compact만.
- **AI 리뷰 JSON 파싱**: Claude가 JSON 앞에 설명 텍스트를 붙이는 경우 `re.search`로 코드 블록 내 JSON만 추출.
- **봇 PR `create_issue` 루프 방지**: `pr_head_ref`가 `_BOT_PR_PREFIXES` (`claude-fix/`, `bot/`, `renovate/`, `dependabot/`) 중 하나로 시작하면 `create_issue`를 건너뜀.
- **봇 발신 / 자기 분석 루프 방지**: `src/webhook/providers/github.py::_loop_guard_check()`가 3-layer 체크 — (1) Kill-switch `SCAMANAGER_SELF_ANALYSIS_DISABLED=1`, (2) `loop_guard.is_bot_sender()` + BOT_LOGIN_WHITELIST 비포함 → 즉시 차단, (3) skip marker (`[skip ci]`, `[skip-sca]`, `[ci skip]`) + `BotInteractionLimiter` **화이트리스트 봇 한정** 시간당 6회 상한 (PR #100). 운영 runbook: `docs/runbooks/self-analysis.md`.
- **stage_metrics 필드 규약**: `issue_count` = 전체 이슈 합계 (`sum(len(r.issues))`), `file_count` = 분석 파일 수. 두 필드를 혼동하지 말 것.
- **커밋 메시지 추출**: `_extract_commit_message()`는 PR 이벤트 시 `title + "\n\n" + body`, Push 이벤트 시 `head_commit["message"]` 우선 사용.
- 🔴 **GitHub 페이로드의 None-able 키 정규화**: GitHub 가 `head_commit` / `pull_request` 키 값을 **`None` 으로 보낼 수 있다** (예: 브랜치 삭제 push). `data.get("head_commit", {}).get(...)` 체이닝은 default 가 적용되지 않아 NPE 발생 — 항상 `(data.get("head_commit") or {}).get(...)` 패턴으로 정규화. `_extract_commit_message`(pipeline.py)는 `if head:` 가드, `_loop_guard_check`(webhook/providers/github.py)는 `or {}` 패턴 사용. (PR #124 회귀 사고로 도입)
- **CLI Hook 인증/점수**: `GET /api/hook/verify`, `POST /api/hook/result`는 `hook_token` 파라미터로 인증(X-API-Key 불필요). pre-push 훅은 정적 분석 없이 AI 리뷰만 실행 → `calculate_score([], ai_review)` 호출.
- **분석 source 필드**: `pipeline.py`가 result JSON에 `"source": "pr"|"push"` 저장. 기존 레코드 대응으로 `result.get("source") or ("pr" if pr_number else "push")` fallback 파생.
- **GateDecision upsert / claim**: `save_gate_decision()`(자동 경로)은 동일 `analysis_id`로 이미 레코드가 있으면 UPDATE, 없으면 INSERT(upsert). 🔴 **반자동 telegram 경로(`handle_gate_callback`)는 `gate_decision_repo.claim_decision()`(insert-only, UNIQUE `analysis_id` IntegrityError→False)로 부수효과(GitHub 리뷰·auto-merge) 전에 결정을 원자적으로 claim** — first-writer-wins 로 동일 서명 콜백 리플레이/동시 더블클릭을 차단(#11). upsert 와 달리 update 분기가 없어 결정 뒤집기 불가. save_gate_decision upsert 는 수동 경로에서 제거됨.
- **Analyzer tools 자동 등록**: `tools/semgrep.py`, `tools/eslint.py`, `tools/shellcheck.py`, `tools/cppcheck.py`, `tools/slither.py`, `tools/rubocop.py`, `tools/golangci_lint.py`는 `analyze_file()`에서 해당 모듈을 import할 때 자동으로 `register()` 호출. 새 도구 추가 시 (1) `tools/` 아래 클래스 작성 + `register()` 호출, (2) `analyze_file()`에서 import, (3) SUPPORTED_LANGUAGES에 지원 언어 선언 세 단계 필수.
- **golangci-lint go.mod 자동생성**: `_GolangciLintAnalyzer.run()` 은 tmp_path 디렉토리에 `go.mod` 가 없으면 `_ensure_go_mod()` 로 최소 모듈 정의 (`module tempmod\ngo 1.21\n`) 를 자동 생성.
- **`_build_issue_body()` 시그니처**: `high_issues: list[dict]` 파라미터가 추가되어 있음. 직접 호출 시 반드시 high_issues 인자 포함.
- **Railway Webhook 토큰 인증**: `POST /webhooks/railway/{token}` 엔드포인트는 DB에서 `railway_webhook_token == token` 조회 후 `config is None → 404` 처리. `railway_api_token`은 Fernet 암호화 저장 — `decrypt_token()`으로 백그라운드 핸들러에 전달.
- **5-way 동기화 Railway 확장**: `railway_deploy_alerts`가 ORM/RepoConfigData/API body/settings 폼/PRESETS 5-way 동기화 적용 대상.
- **RailwayDeployEvent nested 구조**: `src/railway_client/models.py`의 `RailwayDeployEvent`는 3-그룹 nested dataclass — `event.project.project_id`, `event.commit.commit_sha` 등 sub-dataclass 경로로 접근. 평면(`event.project_id`) 접근은 2026-04-22 이후 제거됨. 신규 필드 추가 시 `RailwayProjectInfo` 또는 `RailwayCommitInfo`에 삽입.
- **asyncio.gather 내 Session 공유 금지**: `gather()` 내 코루틴은 각각 독립 `with SessionLocal() as db:` 사용 의무 — 세션 공유 시 트랜잭션 충돌. 교차 참조: [`.claude/rules/api.md`](.claude/rules/api.md) (사이클 113 P0-H 학습).
