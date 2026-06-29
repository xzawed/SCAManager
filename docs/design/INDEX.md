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
| 2026-04-27 | [tier3-native-automerge-design](2026-04-27-tier3-native-automerge-design.md) | Tier 3 — GitHub native `enablePullRequestAutoMerge` 통합 — **PR-A 완료 (#103)** / **PR-B1 완료 (#114, auto_merge_disabled webhook + MergeAttempt lifecycle)** / **PR-B2 완료 (#115, 이중 enable 가드)** / **PR-B3 폐기 철회 (R13 평가 2026-06-24)**: 운영 DB + GitHub API 실측 = native enable 0회(근본 2겹: 전 리포 "Allow auto-merge" OFF + **branch protection 부재→PR UNSTABLE→enable "unstable status" 실패**, native 는 required checks 로 BLOCKED 시만 가능). 아키텍처 부정합(native=체크 기반 / SCAManager=점수 기반). **사용자 결정 = native 미추구, retry 큐 = 영구 primary**(938 머지) |
| 2026-05-01 | [ui-redesign-claude-linear-hybrid](2026-05-01-ui-redesign-claude-linear-hybrid.md) | UI/UX 개편 — Claude × Linear 하이브리드 (Phase 1A/1B/1C/2A Step A → Progressive 재설계 → 4-에이전트 감사 + 5-에이전트 cleanup 사이클로 진화). 그룹 55~57 의 기획 출처 |
| 2026-05-02 | [insight-dashboard-rework](2026-05-02-insight-dashboard-rework.md) | **Insight Dashboard 근본 재설계 기획** — 5-에이전트 병렬 분석. **✅ Phase 1+2+3 100% 완료 + postlude 완료** (사이클 64 #224 종료 + 사이클 66 #228 RLS middleware + #229 backfill 까지). MVP-B (Pulse + Trend) + URL 301 redirect + ~~leaderboard_opt_in 보존~~ → **Q3 정정 폐기** (alembic 0025) + Insight 모드 + Supabase RLS (alembic 0026) + 운영 활성화 미들웨어 (ASGI + contextvars + event listener). |
| 2026-05-18 | [page-performance-measurement-design](2026-05-18-page-performance-measurement-design.md) | 페이지 성능 측정 (TTFB/FCP/LCP/DCL/Load) E2E + 독립 스크립트 설계 (사이클 106 #500) |
| 2026-05-25 | [claude-design-ui-redesign-spec](2026-05-25-claude-design-ui-redesign-spec.md) | UI 전면 재설계 — Claude Design 연동 기획 스펙 (사이클 131 토큰 시스템·컴포넌트·WCAG) |
| 2026-05-25 | [phase1-preparation-plan](2026-05-25-phase1-preparation-plan.md) | Claude Design UI 재설계 Phase 1 — Preparation Package 구현 계획 |
| 2026-05-31 | [cycle-143-i18n-process-design](2026-05-31-cycle-143-i18n-process-design.md) | 사이클 143 — i18n 완성 + 프로세스 강화 설계 |
| 2026-05-31 | [cycle-143-implementation-plan](2026-05-31-cycle-143-implementation-plan.md) | 사이클 143 — i18n 완성 + 프로세스 강화 구현 계획 |
| 2026-06-05 | [integrity-audit-workflow-design](2026-06-05-integrity-audit-workflow-design.md) | **다이나믹 워크플로우 1단계** — 전체 정합성 감사 Workflow (B+C 결합: loop-until-dry 탐색 + 다관점 verify + completeness critic + 비용 상한). scope 파라미터화(full/diff/area), read-only P0/P1/P2 리포트. 사이클 104/109 수동 5+1 감사의 결정론적 코드화. **구현 완료 — `.claude/workflows/integrity-audit.mjs` + runbook + `/integrity-audit` (운영 사용 중)** |
| 2026-06-23 | [repo-automation-design](2026-06-23-repo-automation-design.md) | **repo-automation** — pre-commit 훅 sync 체커(docs 수치·env-vars·config 5-way·이중언어 주석) + 워크플로우 loop 단일출처(`_lib/loop-until-dry.template.mjs`) + 정책 흐름 스킬(docs-sync/retrospective/codex-verify) 설계 (#961~#987) |

> 각 문서는 당시 설계 시점의 결정을 반영하며, 이후 변경이 있다면 [docs/STATE.md](../STATE.md) 그룹 이력과 코드가 최우선 출처입니다.

> **Phase 4 후보 영역** (사이클 67 회고 #232 §5 — 사용자 결정 의무 — High tier 사전 확인): 🅐 멀티 테넌트 SaaS 본격화 (조직 단위 격리 + 팀 협업) / 🅑 모바일 영역 (PWA / 모바일 dashboard 우선) / 🅒 Telegram 본격화 (인라인 명령 확장 + 봇 통합) / 🅓 신규 정적분석/AI 통합 (Anthropic 새 모델 + 추가 도구) / 🅔 운영 모니터링 + Cleanup 우선 (RLS 효과 검증 + caching hit rate + 정책 카테고리 분류).

---

> **Phase 12 이후 신규 설계**: CI-aware Auto Merge Retry는 설계 문서 없이 TDD 기반으로 구현되었습니다. 구현 세부 사항은 `src/services/merge_retry_service.py`, `src/gate/retry_policy.py`, `docs/runbooks/merge-retry.md`를 참조하세요.
