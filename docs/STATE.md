# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-04-19, Phase 0 — 50개 언어 AI 리뷰)

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **896개** | `make test` (+207 from Phase 0) |
| E2E 테스트 | **38개** | `make test-e2e` (Chromium Playwright) |
| pylint | **9.79/10** | `make lint` |
| 커버리지 | **96.2%** | `make test-cov` (database.py 100%, ui/router.py 99.4%) |
| bandit HIGH | **0개** | 실측 확인 (1.9.4 Python 3.14 대응) |
| flake8 | **0건** | `flake8 src/` |

## Phase 이력

| Phase | 내용 | 완료일 |
|-------|------|--------|
| 스코어 버그 수정 | 89점 고정 문제 (SHA 이동 + AI status) | 2026-04-12 |
| 테스트 갭 분석 | P0~P3 우선순위 49개 식별 (당시 360개) | 2026-04-12 |
| n8n Phase 1 | Issue → claude_fix.sh → PR 자동화 | 2026-04-17 |
| n8n Phase 2 | 봇 PR auto_merge 누락 수정 (re-gate + 무한루프 가드) | 2026-04-19 |
| 회고 및 인프라 정비 | PostToolUse 훅 경로 수정, .gitattributes, docs 정비 | 2026-04-19 |
| P2 통합 테스트 | webhook→gate end-to-end 3 시나리오 (StaticPool SQLite + 이중 SessionLocal patch) | 2026-04-19 |
| P1 테스트 보강 | gate/engine.py 에러경로 8개 + breakdown=None 버그 수정, auth/github.py OAuth 분기 7개 | 2026-04-19 |
| P2 테스트 보강 | github_client/repos.py commit_scamanager_files 6개 (신규/기존파일, HTTP오류, config내용, trailing slash, 인증헤더) | 2026-04-19 |
| P3 알림 엣지 케이스 | Telegram 4096자 절단 4종 + HTTP오류 전파 3종, SMTP 연결/인증 에러·From 기본값·Subject 검증 4종 | 2026-04-19 |
| P3 보안 심층 | HTML injection(email 2+telegram 2), OAuth CSRF state, Jinja2 autoescape 검증 (+6) | 2026-04-19 |
| P3 CLAUDE.md 정비 | 주의사항 빈도 기반 재정렬, psycopg2·N+1·Supabase SSL 3항목 제거, 보안 2항목 추가 | 2026-04-19 |
| 품질 감사 7라운드 | 정상성/커버리지/결정성/격리성/pylint/flake8/bandit+E2E 다각도 검증. 보고서: docs/reports/2026-04-19-code-quality-audit.md | 2026-04-19 |
| 감사 결과 수정 | P0 bandit 1.9.4(Python 3.14 대응), P1 E2E 26/26 복구+payload.py 제거, P2 lint 0건, P3 +48 테스트(634총) | 2026-04-19 |
| n8n Phase 3: Issue 자동 close | PR merge 시 Closes #N 키워드 파싱 → Issues API close (SCAManager-side 방어적 보장) | 2026-04-19 |
| auto_merge 견고성 강화 | merge_pr tuple 반환 + mergeable_state 재시도 + Telegram 실패 알림 (+12 테스트) | 2026-04-19 |
| P0-4 private→public | _build_result_dict→build_analysis_result_dict, _save_gate_decision→save_gate_decision, _build_notify_tasks→build_notification_tasks | 2026-04-19 |
| P0-2 Notifier 레지스트리 | NotifyContext dataclass + Notifier Protocol + REGISTRY + build_notification_tasks 루프 축약 | 2026-04-19 |
| P0-3 Repository 계층 | repository_repo/analysis_repo 신설 + pipeline·router db.query 직접 사용 교체 | 2026-04-19 |
| P0-1 RepoConfig 동기화 해소 | dataclass fields 루프 + model_dump() — 새 채널 추가 시 7곳→4곳 | 2026-04-19 |
| P1 RuntimeWarning 수정 | test_pipeline.py MagicMock→RepoConfigData 교체 (coroutine never awaited 제거) | 2026-04-19 |
| P2 docstring 보강 | ui/router.py 8개 + config.py 1개 함수 docstring 추가 (pylint 9.73→9.77) | 2026-04-19 |
| P2 database.py 커버리지 | FailoverSessionFactory 예외경로·probe루프·get_db 제너레이터 (+16 테스트, 75%→100%) | 2026-04-19 |
| P3 ui/router.py 커버리지 | app_base_url/GateDecision cascade/add_repo 분기/reinstall_hook/reinstall_webhook 분기 (+11 테스트, 83.9%→99.4%) | 2026-04-19 |
| Phase 0 다언어 AI 리뷰 | language.py(50언어 감지) + review_guides(Tier1×10/Tier2×20/Tier3×20) + review_prompt.py(토큰 예산) + ai_review.py 통합 (+207 테스트, pylint 9.77→9.79) | 2026-04-19 |

## 갱신 방법

Phase 완료 후:
```bash
# 수치 확인
make gate          # pytest + pylint + flake8 + bandit 한번에
make test-cov      # 커버리지

# 이 파일 수치 업데이트 후 커밋
git add docs/STATE.md
git commit -m "docs(state): Phase X 완료 — 테스트 NNN개, pylint X.XX"
```

## 잔여 갭 (우선순위순)

| 우선순위 | 항목 |
|---------|------|
| ~~P1~~ | ~~`gate/engine.py` 에러 경로~~ **완료** (+8, breakdown=None 버그 수정 포함) |
| ~~P1~~ | ~~`auth/github.py` OAuth 보안 분기~~ **완료** (+7, app_base_url·display_name·500경로) |
| ~~P2~~ | ~~웹훅→gate 통합 테스트~~ (`tests/integration/test_webhook_to_gate.py`) **완료** |
| ~~P2~~ | ~~`github_client/repos.py` commit_scamanager_files 테스트~~ **완료** (+6) |
| **P3** | 보안 심층 (OAuth state, HTML injection) |
| ~~P3~~ | ~~알림 엣지 케이스 (Telegram 4096자, SMTP 타임아웃)~~ **완료** (+11) |
| ~~P3~~ | ~~보안 심층 (OAuth CSRF, HTML injection, Jinja2 autoescape)~~ **완료** (+6) |
| ~~P3~~ | ~~CLAUDE.md 주의사항 빈도 기반 재정렬·축소~~ **완료** |
