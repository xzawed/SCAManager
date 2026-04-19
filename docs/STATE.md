# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-04-19)

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **543개** | `make test` |
| E2E 테스트 | **26개** | `make test-e2e` |
| pylint | **9.70/10** | `make lint` |
| 커버리지 | **92%** | `make test-cov` (2052줄 중 160줄 미커버) |
| bandit HIGH | **0개** | 유지 기준 |

## Phase 이력

| Phase | 내용 | 완료일 |
|-------|------|--------|
| 스코어 버그 수정 | 89점 고정 문제 (SHA 이동 + AI status) | 2026-04-12 |
| 테스트 갭 분석 | P0~P3 우선순위 49개 식별 (당시 360개) | 2026-04-12 |
| n8n Phase 1 | Issue → claude_fix.sh → PR 자동화 | 2026-04-17 |
| n8n Phase 2 | 봇 PR auto_merge 누락 수정 (re-gate + 무한루프 가드) | 2026-04-19 |
| 회고 및 인프라 정비 | PostToolUse 훅 경로 수정, .gitattributes, docs 정비 | 2026-04-19 |

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
| **P1** | `gate/engine.py` 에러 경로 ~8개 테스트 |
| **P1** | `auth/github.py` OAuth 보안 분기 ~7개 테스트 |
| **P2** | 웹훅→gate 통합 테스트 (`tests/integration/test_webhook_to_gate.py`) |
| **P2** | `github_client/repos.py` commit_scamanager_files 테스트 |
| **P3** | 보안 심층 (OAuth state, HTML injection) |
| **P3** | 알림 엣지 케이스 (Telegram 4096자, SMTP 타임아웃) |
