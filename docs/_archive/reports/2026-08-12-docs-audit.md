<!-- guard-cue-quote: 아래는 2026-08-12 문서 감사의 시점 기록이며, 이 문서 자체가 실행 지시는 아니다. -->

# 전 문서 감사 — 2026-08-12

워크플로 3회 · 에이전트 47 · 토큰 5.5M · 툴 호출 1,764 · Grok claim-review 3세션.
행동 처방과 결정 대기 항목은 [`session-handoff-2026-08-12.md`](../../runbooks/session-handoff-2026-08-12.md) 가 정본이다.

## 채점 루브릭

| 축 | 배점 | 내용 |
|---|---:|---|
| 집행/배선 | 30 | 의무에 기계 집행자가 있는가 + 그 집행자가 공허하지 않은가 |
| 정확성 | 25 | 단언이 코드·실측과 일치하는가 (반증 시도) |
| 신선도 | 15 | stale 수치·경로·죽은 링크·끊긴 앵커·충돌 마커 |
| 도달성 | 15 | seed(README·CLAUDE·AGENTS)로부터 **inbound** 도달 |
| 밀도/중복 | 15 | SSOT 위반 · 결정에 불필요한 분량 |

🔴 초판은 정확성 30 / 집행 20 이었고 Grok 이 **BROKEN** 판정했다 — 이 리포의 지배 실패는
"규칙이 틀림"이 아니라 "규칙이 도달하는데 안 지켜짐"(무집행 🔴 221/307 · 정책 13 준수 0/42 ·
R43 이행률 0%)이라 집행을 정확성보다 무겁게 재가중했다.

🔴 아카이브 정확성 면제도 철회했다 — 활성 규칙 7파일이 아카이브를 링크하고 CLAUDE.md 가
아카이브 회고서를 정책 출처로 지목하므로, **문서를 아카이브로 옮기면 채점을 피하면서
조종은 계속하는 탈출구**였다. 링크됨·스크립트가 읽음·잔여 계약 자진선언 중 하나면 Tier A.

## 한계 (정직 기준)

- **적대 검증 커버리지 35%** — P0/P1 201건 중 70건만 검증(배치 상한). 나머지 131건은 UNVERIFIED 이며 확정 49건에 미포함.
- **아카이브 96건 중 19건만 열었다.** 나머지는 표본 밖.
- **시간축이 없었다** — 한 브랜치 한 시점만 봐서, 이미 고쳐져 푸시된 미머지 브랜치(#1331)를 못 봤다. P0 3건을 "집행자 0"으로 오채점했다.
- **감사의 분모가 틀렸다** — 자진신고 279건 vs 실측 205(디스크)/203(추적). CRITICAL 23건이 누락됐고 2차 갭 감사로 메웠다.
- **부재를 관측할 수 없다** — 방법이 "문서가 지목한 가드를 연다"이므로 문서가 언급하지 않는 가드는 순회에 도달하지 않는다.

## 항목별 점수 (128건, 낮은 순)

| 문서 | 판정 | 집행/30 | 정확/25 | 신선/15 | 도달/15 | 밀도/15 | 합계 |
|---|---|---:|---:|---:|---:|---:|---:|
| `docs/superpowers/plans/2026-05-30-sprint-roadmap.md` | BROKEN | 0 | 3 | 1 | 1 | 3 | **8** |
| `docs/runbooks/_archive/sentry-activation.md` | BROKEN | 2 | 3 | 1 | 5 | 10 | **21** |
| `docs/_archive/user-actions-remaining.md` | BROKEN | 2 | 8 | 4 | 2 | 10 | **26** |
| `CONTRIBUTING.ko.md` | BROKEN | 4 | 5 | 4 | 10 | 10 | **33** |
| `scripts/i18n_comments/glossary.md` | BROKEN | 3 | 6 | 5 | 5 | 14 | **33** |
| `scripts/check_conflict_markers.py` | BROKEN | 2 | 12 | 3 | 5 | 11 | **33** |
| `.claude/skills/test.md` | BROKEN | 5 | 8 | 5 | 4 | 11 | **33** |
| `docs/_archive/superpowers/specs/2026-05-25-claude-design-ui-redesign.md` | BROKEN | 0 | 8 | 26 | 0 | 0 | **34** |
| `docs/STATE.md` | BROKEN | 5 | 6 | 5 | 13 | 6 | **35** |
| `docs/runbooks/new-machine-setup.md` | BROKEN | 4 | 5 | 4 | 11 | 11 | **35** |
| `README.md` | BROKEN | 4 | 6 | 5 | 14 | 7 | **36** |
| `docs/agents-index.md` | BROKEN | 4 | 5 | 4 | 12 | 11 | **36** |
| `CLAUDE.md` | BROKEN | 5 | 5 | 4 | 15 | 8 | **37** |
| `README.ko.md` | BROKEN | 4 | 5 | 5 | 12 | 12 | **38** |
| `.claude/rules/guards.md` | BROKEN | 5 | 5 | 4 | 14 | 10 | **38** |
| `AGENTS.md` | BROKEN | 5 | 5 | 4 | 14 | 11 | **39** |
| `scripts/pre_push_gate.py` | BROKEN | 8 | 6 | 3 | 13 | 9 | **39** |
| `docs/reports/2026-06-08-integrity-audit-full.md` | NEEDS WORK | 11 | 13 | 2 | 6 | 8 | **40** |
| `docs/_archive/README.md` | BROKEN | 3 | 5 | 7 | 13 | 12 | **40** |
| `src/scripts/README.md` | BROKEN | 8 | 7 | 4 | 8 | 13 | **40** |
| `docs/_archive/p4-gate-verification.md` | BROKEN | 2 | 22 | 18 | 0 | 0 | **42** |
| `.github/PULL_REQUEST_TEMPLATE.md` | BROKEN | 6 | 5 | 4 | 15 | 12 | **42** |
| `docs/backlog.md` | BROKEN | 6 | 12 | 6 | 13 | 6 | **43** |
| `docs/guides/operational-verification.md` | BROKEN | 5 | 8 | 7 | 10 | 13 | **43** |
| `docs/design/brief/05-page-inventory.md` | BROKEN | 16 | 12 | 8 | 2 | 5 | **43** |
| `docs/design/brief/02-component-inventory.md` | BROKEN | 16 | 13 | 8 | 2 | 5 | **44** |
| `docs/integrations/external-quality-services.md` | BROKEN | 4 | 12 | 8 | 12 | 9 | **45** |
| `docs/reports/2026-06-06-integrity-audit-area-gate.md` | NEEDS WORK | 12 | 13 | 3 | 6 | 11 | **45** |
| `.claude/skills/webhook-test.md` | BROKEN | 6 | 15 | 12 | 4 | 10 | **47** |
| `docs/reference/language-coverage.md` | NEEDS WORK | 5 | 12 | 8 | 15 | 8 | **48** |
| `docs/design/2026-04-19-analyzer-registry-design.md` | BROKEN | 13 | 9 | 5 | 13 | 8 | **48** |
| `docs/superpowers/plans/2026-05-30-phase-e-gate-action-registry.md` | NEEDS WORK | 4 | 24 | 20 | 0 | 0 | **48** |
| `docs/design/2026-04-07-phase8a-auth-user-design.md` | BROKEN | 13 | 8 | 5 | 13 | 10 | **49** |
| `.claude/skills/integrity-audit.md` | BROKEN | 8 | 16 | 9 | 4 | 13 | **50** |
| `docs/runbooks/phase2-data-readiness.md` | BROKEN | 6 | 14 | 6 | 14 | 12 | **52** |
| `docs/runbooks/static-assets.md` | BROKEN | 15 | 13 | 3 | 11 | 10 | **52** |
| `docs/design/brief/03-design-direction.md` | NEEDS WORK | 16 | 18 | 10 | 2 | 6 | **52** |
| `docs/design/2026-04-09-settings-ui-redesign-design.md` | NEEDS WORK | 13 | 10 | 7 | 13 | 10 | **53** |
| `docs/runbooks/docs-consolidation-status.md` | NEEDS WORK | 8 | 14 | 11 | 8 | 13 | **54** |
| `docs/design/brief/04-theme-roles.md` | NEEDS WORK | 16 | 20 | 12 | 2 | 5 | **55** |
| `docs/design/2026-05-01-ui-redesign-claude-linear-hybrid.md` | NEEDS WORK | 13 | 11 | 7 | 14 | 10 | **55** |
| `docs/_archive/reports/2026-05-01-collaboration-retrospective.md` | NEEDS WORK | 8 | 14 | 10 | 15 | 8 | **55** |
| `.claude/plans/2026-04-07-phase8a-auth-user.md` | NEEDS WORK | 26 | 8 | 7 | 9 | 5 | **55** |
| `docs/runbooks/docs-consolidation-plan.md` | NEEDS WORK | 10 | 17 | 10 | 8 | 11 | **56** |
| `docs/guides/github-integration-guide.md` | NEEDS WORK | 6 | 16 | 13 | 10 | 11 | **56** |
| `docs/guides/onpremise-migration-guide.md` | NEEDS WORK | 7 | 14 | 9 | 15 | 11 | **56** |
| `docs/cycle-history.md` | NEEDS WORK | 12 | 20 | 5 | 15 | 5 | **57** |
| `docs/runbooks/merge-retry.md` | NEEDS WORK | 10 | 15 | 8 | 14 | 10 | **57** |
| `.claude/policies/history.md` | NEEDS WORK | 15 | 16 | 8 | 9 | 10 | **58** |
| `docs/runbooks/rls-role-separation.md` | NEEDS WORK | 19 | 11 | 6 | 15 | 7 | **58** |
| `docs/design/2026-05-18-page-performance-measurement-design.md` | NEEDS WORK | 13 | 13 | 8 | 13 | 11 | **58** |
| `docs/_archive/reports/perf-2026-05-18-2314.md` | NEEDS WORK | 12 | 15 | 6 | 13 | 13 | **59** |
| `tests/unit/scripts/test_pre_push_gate.py` | NEEDS WORK | 18 | 12 | 7 | 10 | 12 | **59** |
| `docs/_archive/reports/INDEX.md` | NEEDS WORK | 24 | 15 | 10 | 3 | 8 | **60** |
| `scripts/check_docs_sync.py` | NEEDS WORK | 15 | 10 | 11 | 13 | 11 | **60** |
| `CONTRIBUTING.md` | NEEDS WORK | 12 | 14 | 9 | 14 | 12 | **61** |
| `docs/design/brief/00-service-overview.md` | NEEDS WORK | 16 | 23 | 13 | 2 | 7 | **61** |
| `.claude/skills/lint.md` | NEEDS WORK | 8 | 22 | 12 | 4 | 15 | **61** |
| `docs/README.md` | NEEDS WORK | 18 | 20 | 10 | 4 | 10 | **62** |
| `docs/runbooks/db-migration.md` | NEEDS WORK | 12 | 17 | 10 | 13 | 10 | **62** |
| `docs/design/2026-04-07-phase8b-github-oauth-repo-add-design.md` | NEEDS WORK | 13 | 16 | 9 | 13 | 11 | **62** |
| `.claude/skills/docs-sync.md` | NEEDS WORK | 22 | 15 | 13 | 4 | 8 | **62** |
| `docs/design/2026-04-17-settings-preset-disclosure-design.md` | NEEDS WORK | 15 | 15 | 9 | 13 | 11 | **63** |
| `docs/design/2026-04-12-score-history-chart-design.md` | NEEDS WORK | 15 | 16 | 9 | 13 | 11 | **64** |
| `tests/unit/scripts/test_gate_claim_consistency.py` | NEEDS WORK | 20 | 14 | 8 | 10 | 12 | **64** |
| `.claude/plans/2026-04-07-phase8b-github-oauth-repo-add.md` | NEEDS WORK | 26 | 16 | 9 | 9 | 4 | **64** |
| `docs/runbooks/branch-protection.md` | NEEDS WORK | 20 | 12 | 8 | 14 | 11 | **65** |
| `docs/runbooks/operational-smoke-checks.md` | NEEDS WORK | 21 | 14 | 7 | 15 | 8 | **65** |
| `docs/design/INDEX.md` | NEEDS WORK | 13 | 19 | 9 | 15 | 9 | **65** |
| `docs/design/2026-05-02-insight-dashboard-rework.md` | NEEDS WORK | 15 | 20 | 8 | 14 | 8 | **65** |
| `.claude/plans/2026-04-05-phase1-mvp.md` | NEEDS WORK | 26 | 15 | 10 | 9 | 5 | **65** |
| `.claude/policies/active.md` | NEEDS WORK | 18 | 15 | 10 | 14 | 9 | **66** |
| `docs/design/2026-04-05-scamanager-design.md` | NEEDS WORK | 15 | 17 | 10 | 13 | 11 | **66** |
| `.claude/plans/2026-04-05-phase3-gate-engine.md` | NEEDS WORK | 26 | 16 | 10 | 9 | 5 | **66** |
| `docs/reference/scoring.md` | NEEDS WORK | 6 | 21 | 15 | 15 | 10 | **67** |
| `docs/design/2026-05-25-phase1-preparation-plan.md` | NEEDS WORK | 24 | 17 | 10 | 13 | 3 | **67** |
| `docs/design/2026-05-31-cycle-143-i18n-process-design.md` | NEEDS WORK | 13 | 21 | 10 | 13 | 11 | **68** |
| `.claude/plans/2026-04-05-phase2-ai-review.md` | NEEDS WORK | 26 | 17 | 10 | 9 | 6 | **68** |
| `.claude/agents/test-writer.md` | NEEDS WORK | 10 | 22 | 10 | 14 | 12 | **68** |
| `docs/runbooks/railway.md` | NEEDS WORK | 13 | 19 | 9 | 15 | 13 | **69** |
| `docs/design/2026-04-10-pr-gate-three-options-design.md` | NEEDS WORK | 15 | 20 | 10 | 13 | 11 | **69** |
| `docs/runbooks/self-analysis.md` | NEEDS WORK | 17 | 16 | 9 | 14 | 14 | **70** |
| `.claude/plans/2026-04-05-phase4-dashboard.md` | NEEDS WORK | 26 | 18 | 10 | 9 | 7 | **70** |
| `docs/integrations/n8n-auto-fix.md` | NEEDS WORK | 6 | 24 | 15 | 15 | 11 | **71** |
| `docs/design/2026-04-27-tier3-native-automerge-design.md` | NEEDS WORK | 15 | 21 | 11 | 14 | 10 | **71** |
| `docs/_archive/STATE-groups-13-61-2026-05.md` | NEEDS WORK | 30 | 27 | 14 | 0 | 0 | **71** |
| `docs/architecture.md` | NEEDS WORK | 20 | 19 | 8 | 15 | 10 | **72** |
| `docs/design/2026-05-31-cycle-143-implementation-plan.md` | NEEDS WORK | 24 | 19 | 10 | 13 | 6 | **72** |
| `docs/_archive/reports/2026-07-18-scoped-retrospective.md` | NEEDS WORK | 14 | 21 | 12 | 14 | 11 | **72** |
| `.claude/agents/pipeline-reviewer.md` | NEEDS WORK | 10 | 23 | 11 | 13 | 15 | **72** |
| `docs/_archive/rules-incident-log.md` | NEEDS WORK | 22 | 19 | 10 | 12 | 10 | **73** |
| `.claude/plans/2026-04-05-phase5-n8n-stats.md` | NEEDS WORK | 26 | 17 | 11 | 9 | 10 | **73** |
| `docs/_archive/reports/2026-07-19-retrospective-2.md` | NEEDS WORK | 17 | 20 | 12 | 14 | 11 | **74** |
| `.claude/plans/2026-06-05-integrity-audit-workflow.md` | NEEDS WORK | 26 | 19 | 12 | 9 | 8 | **74** |
| `.claude/rules/services.md` | NEEDS WORK | 19 | 21 | 11 | 15 | 9 | **75** |
| `docs/design/2026-06-23-repo-automation-design.md` | NEEDS WORK | 16 | 23 | 12 | 13 | 12 | **76** |
| `docs/_archive/reports/2026-08-11-docs-scoring-report.md` | NEEDS WORK | 13 | 22 | 15 | 15 | 11 | **76** |
| `docs/runbooks/secret-prevention.md` | NEEDS WORK | 20 | 20 | 11 | 13 | 13 | **77** |
| `docs/runbooks/workflow.md` | NEEDS WORK | 23 | 16 | 10 | 15 | 13 | **77** |
| `docs/design/2026-05-25-claude-design-ui-redesign-spec.md` | NEEDS WORK | 24 | 17 | 11 | 14 | 11 | **77** |
| `.claude/plans/2026-06-23-repo-automation-hooks.md` | GOOD | 27 | 21 | 12 | 9 | 8 | **77** |
| `.claude/skills/retrospective.md` | GOOD | 24 | 20 | 14 | 5 | 14 | **77** |
| `docs/_archive/reports/2026-08-10-docs-system-audit.md` | NEEDS WORK | 15 | 21 | 13 | 15 | 14 | **78** |
| `.claude/rules/pipeline.md` | NEEDS WORK | 22 | 19 | 11 | 15 | 12 | **79** |
| `docs/runbooks/merge-verifier.md` | GOOD | 17 | 24 | 10 | 15 | 13 | **79** |
| `docs/runbooks/doc-volume-reduction-plan.md` | GOOD | 21 | 21 | 11 | 12 | 14 | **79** |
| `.claude/rules/db.md` | GOOD | 25 | 18 | 10 | 15 | 12 | **80** |
| `.claude/rules/docs.md` | GOOD | 18 | 21 | 12 | 15 | 14 | **80** |
| `docs/_archive/superpowers/plans/2026-05-24-ai-issue-registration.md` | GOOD | 22 | 30 | 28 | 0 | 0 | **80** |
| `.claude/agents/doc-impact-analyzer.md` | GOOD | 26 | 18 | 9 | 13 | 14 | **80** |
| `docs/design/2026-06-05-integrity-audit-workflow-design.md` | GOOD | 17 | 24 | 13 | 15 | 12 | **81** |
| `.claude/rules/api.md` | GOOD | 23 | 21 | 12 | 14 | 12 | **82** |
| `.claude/rules/testing.md` | GOOD | 22 | 20 | 12 | 15 | 13 | **82** |
| `docs/runbooks/ai-collaboration.md` | GOOD | 23 | 22 | 10 | 15 | 12 | **82** |
| `docs/_archive/reports/2026-08-08-retrospective.md` | GOOD | 19 | 22 | 15 | 15 | 11 | **82** |
| `.github/workflows/ci.yml` | GOOD | 24 | 21 | 12 | 14 | 11 | **82** |
| `.claude/agents/doc-consistency-reviewer.md` | GOOD | 26 | 17 | 13 | 13 | 13 | **82** |
| `.claude/rules/i18n.md` | GOOD | 22 | 20 | 12 | 15 | 14 | **83** |
| `docs/runbooks/integrity-audit.md` | GOOD | 18 | 22 | 14 | 15 | 14 | **83** |
| `.claude/agents/doc-quality-reviewer.md` | GOOD | 27 | 21 | 9 | 13 | 14 | **84** |
| `docs/runbooks/owed-verification.md` | GOOD | 27 | 22 | 14 | 15 | 8 | **86** |
| `docs/reference/env-vars.md` | GOOD | 25 | 23 | 12 | 15 | 11 | **86** |
| `.claude/rules/deploy.md` | GOOD | 23 | 22 | 14 | 15 | 13 | **87** |
| `docs/runbooks/cost-controls.md` | GOOD | 22 | 24 | 12 | 15 | 14 | **87** |
| `docs/runbooks/retrospective.md` | GOOD | 21 | 24 | 13 | 15 | 14 | **87** |
| `.claude/rules/security.md` | GOOD | 25 | 24 | 14 | 15 | 10 | **88** |
| `.claude/rules/ui.md` | GOOD | 24 | 23 | 13 | 15 | 13 | **88** |
| `docs/runbooks/retro-cadence-deferrals.md` | GOOD | 28 | 25 | 15 | 15 | 15 | **98** |

## 디렉토리별 평균

| 디렉토리 | 평균 | 건수 |
|---|---:|---:|
| `docs/runbooks/_archive` | 21.0 | 1 |
| `docs/superpowers/plans` | 28.0 | 2 |
| `scripts/i18n_comments` | 33.0 | 1 |
| `docs/_archive/superpowers/specs` | 34.0 | 1 |
| `src/scripts` | 40.0 | 1 |
| `(루트)` | 40.7 | 6 |
| `.github` | 42.0 | 1 |
| `docs/reports` | 42.5 | 2 |
| `scripts` | 44.0 | 3 |
| `docs/_archive` | 50.4 | 5 |
| `docs` | 50.8 | 6 |
| `docs/design/brief` | 51.0 | 5 |
| `docs/guides` | 51.7 | 3 |
| `.claude/skills` | 55.0 | 6 |
| `docs/integrations` | 58.0 | 2 |
| `tests/unit/scripts` | 61.5 | 2 |
| `.claude/policies` | 62.0 | 2 |
| `docs/design` | 64.7 | 19 |
| `docs/reference` | 67.0 | 3 |
| `.claude/plans` | 68.0 | 9 |
| `docs/_archive/reports` | 69.5 | 8 |
| `docs/runbooks` | 69.5 | 22 |
| `.claude/agents` | 77.2 | 5 |
| `.claude/rules` | 78.4 | 11 |
| `docs/_archive/superpowers/plans` | 80.0 | 1 |
| `.github/workflows` | 82.0 | 1 |

평균 **61.6** · 최저 8 · 최고 98 · BROKEN 32 / NEEDS_WORK 70 / GOOD 26

🔴 최고(`.claude/rules` 78.4)와 최저(`docs/superpowers/plans` 28.0)의 차이는 품질 노력이 아니라
**독자의 존재**다. rules 는 path 매칭으로 매일 자동 로드되고, superpowers/plans 는 gitignore
대상이라 CI 가 존재조차 모른다.

