# 설계 문서 인덱스

SCAManager 의 주요 설계 문서 목록. 파일명 날짜 순.

| 날짜 | 문서 | 대상 범위 |
|------|------|----------|
| 2026-04-05 | [scamanager-design](2026-04-05-scamanager-design.md) | 시스템 전체 초기 설계 (baseline) |
| 2026-04-07 | [phase8a-auth-user-design](2026-04-07-phase8a-auth-user-design.md) | Phase 8A — OAuth 로그인 + User 모델 + 사용자별 대시보드 |
| 2026-04-07 | [phase8b-github-oauth-repo-add-design](2026-04-07-phase8b-github-oauth-repo-add-design.md) | Phase 8B — GitHub OAuth + 리포 추가 UI + Webhook 자동 생성 |
| 2026-04-09 | [settings-ui-redesign-design](2026-04-09-settings-ui-redesign-design.md) | Settings 페이지 UI v1 *(2026-04-17 v2 설계로 대체됨 — 아래 참조)* |
| 2026-04-10 | [pr-gate-three-options-design](2026-04-10-pr-gate-three-options-design.md) | PR Gate 3-옵션 분리 (pr_review_comment / approve_mode / auto_merge) |
| 2026-04-12 | [score-history-chart-design](2026-04-12-score-history-chart-design.md) | 점수 이력 차트 + 분석 상세 트렌드 |
| 2026-04-17 | [settings-preset-disclosure-design](2026-04-17-settings-preset-disclosure-design.md) | Settings UI v2 — 프리셋 + Progressive Disclosure |
| 2026-04-19 | [analyzer-registry-design](2026-04-19-analyzer-registry-design.md) | Analyzer Registry (Phase A) — pure/io 분리 |

> 각 문서는 당시 설계 시점의 결정을 반영하며, 이후 변경이 있다면 [docs/STATE.md](../STATE.md) 그룹 이력과 코드가 최우선 출처입니다.

---

> **Phase 12 이후 신규 설계**: CI-aware Auto Merge Retry는 설계 문서 없이 TDD 기반으로 구현되었습니다. 구현 세부 사항은 `src/services/merge_retry_service.py`, `src/gate/retry_policy.py`, `docs/runbooks/merge-retry.md`를 참조하세요.
