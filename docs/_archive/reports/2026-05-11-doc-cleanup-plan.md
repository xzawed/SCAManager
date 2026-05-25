# 문서 정비 계획 — 2026-05-11 (사이클 95 착수 대상)

> 5+1 다중 에이전트 교차 검증 결과 (Agent 1~5 + cross-verify Agent 6)
> 우선순위: 정확도 → 효율성 → 볼륨 최적화

---

## 배경

Claude용 문서 (CLAUDE.md / `.claude/rules/`) 와 Codex용 문서 (AGENTS.md / `.codex/rules/`)를  
전체 코드와 대조해 세세하게 감사한 결과 P0 5건 / P1 10건 / P2 5건 발견.  
cross-verify 에이전트가 P0 broken link 1건을 false-positive로 차단, 신규 P0 2건을 추가.

---

## 🔴 P0 — 즉시 수정 (정확도 오류 · 운영 기능 무력화)

### P0-1: `.codex/hooks.json` + `doc_review_gate.py` 경로 하드코딩 버그 ★최우선

**증상**: `.codex/hooks.json`의 `PreToolUse` / `PostToolUse` 경로가 `f:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\`로 하드코딩됨. 실제 작업 환경 `d:\Source\SCAManager`와 불일치 → **두 hook 모두 미실행 상태** (Codex 파일 보호 게이트 무력화).  
동일하게 `.codex/hooks/doc_review_gate.py` 16줄 `_PROJECT_PREFIXES = ("f:/development/source/claude/scamanager/",)` 도 동일 오류.

**수정 방법**:
- `hooks.json`: 절대 경로 → 상대 경로 (`python .codex/hooks/check_edit_allowed.py`) 또는 환경 감지
- `doc_review_gate.py:16`: `_PROJECT_PREFIXES` 를 현재 작업 디렉토리 기반으로 동적 결정

### P0-2: CLAUDE.md 정책 10 "gh CLI 부재" 서술 오류

**증상**: CLAUDE.md ~274줄 "현재 SCAManager 환경: gh CLI 부재 + GITHUB_TOKEN 401 → 옵션 🅒 (URL 폴백) default 운영"  
실측: `gh version 2.88.1 (2026-03-12)` 설치·인증 완료 → 후속 Claude가 URL 폴백 진행하는 오작동 발생 위험.

**수정**: `gh CLI v2.88.1 설치 + xzawed 계정 인증 완료 → 옵션 🅐 (gh pr create) default`로 정정.

### P0-3: CLAUDE.md 메모리 경로 오류

**증상**: CLAUDE.md ~388줄 체크리스트의 메모리 경로 `f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager` → 실제 `d--Source-SCAManager`.  
Claude가 체크리스트를 실행할 때 경로를 찾지 못함.

**수정**: 경로를 `~/.claude/projects/d--Source-SCAManager/memory/` 로 정정.

### P0-4: CLAUDE.md 메모리 인덱스 완전 stale

**증상**: CLAUDE.md ~395줄 메모리 인덱스 "13건 (Project 5 + Feedback 8)" 및 파일명 목록(`score_bug_fix`, `db_migration`, `test_gap_analysis`, `settings_ux_redesign`, `poiesis_framework` / Feedback 8종) 이 전부 실제 파일과 불일치.  
실제 메모리 파일: `project_phase1_complete.md`, `project_phase7_ui_e2e.md`, `project_phase8a_oauth.md`, `project_phase8b_github_oauth_repo_add.md`, `user_schedule.md`, `user_language_preference.md` (6건 + MEMORY.md 인덱스).

**수정**: 인덱스를 "상세: MEMORY.md 참조" 1줄로 대체하거나 실제 파일명으로 교체.

### P0-5: CLAUDE.md `.claude/rules` 카테고리 수 "9개" → 실제 8개

**증상**: CLAUDE.md ~462줄 "9 카테고리 본문은 `.claude/rules/<area>.md`로 분리". 실제 파일: 8개.

**수정**: "8 카테고리"로 정정.

---

## 🟠 P1 — 중요 (기능/정합성 오류)

### P1-1: `memory/MEMORY.md` 데드 링크

`project_phase6_automerge.md` 참조가 있으나 실제 파일 없음 → 제거.

### P1-2: `doc-impact-analyzer.toml` 섹션명 오류

`.codex/agents/doc-impact-analyzer.toml` ~31줄 "완료 시 필수 3-step" → 실제 "완료 시 필수 5-step"으로 정정.

### P1-3: `docs/STATE.md` repositories 수 불일치

STATE.md "8종" → 실제 `src/repositories/` 10개 파일. architecture.md는 "10종"으로 정확.  
STATE.md 수정 필요.

### P1-4: `docs/STATE.md` E2E 테스트 수 추정 상태

STATE.md E2E "96개 (추정)" → 실측 88개 함수. `make test-e2e` 실행 후 정확한 수치로 갱신.

### P1-5: AGENTS.md 정책 15, 17 완전 누락

- **정책 15** (코드 작업 전 사전 사고 3 자문 + 위임 분류 3-tier) → Codex 코드 편집 전 사전 점검 절차 없음
- **정책 17** (문서 정리 시 안정성 > 권장 규격) → Codex가 문서 cleanup 시 기준 없음
- AGENTS.md §"항상 적용 규칙"에 요약 추가 필요.

### P1-6: `doc_review_gate.py` CRITICAL 패턴에 `AGENTS.md` 미포함

`.codex/hooks/doc_review_gate.py`의 `_CRITICAL` 패턴에 `CLAUDE.md`, `docs/STATE.md` 등은 있으나 `AGENTS.md` 없음.  
AGENTS.md 수정 시 3-에이전트 심의 게이트 미적용 → 추가 필요.

### P1-7: `.codex/rules/deploy.md` nixpacks 방법 오류

Claude rules: NodeSource 스크립트 방식 (실제 `nixpacks.toml`과 일치)  
Codex rules: `aptPkgs = ["nodejs", "npm"]` → 실제 방식과 불일치.  
Codex rules를 실제 nixpacks.toml 방식(NodeSource script)으로 교정.

### P1-8: AGENTS.md rules 경로 표 불완전

- `pipeline.md` 항목: `src/webhook/**`, `src/gate/**` 누락
- `deploy.md` 항목: `requirements-dev.txt`, `.env.example`, `Procfile`, `alembic.ini` 누락  
AGENTS.md §".codex/ 도구 설정" 표 정정 필요.

### P1-9: CLAUDE.md 완료 5-step 순서 오류

~418줄: `① 커밋 → ② PR 생성(gh pr create) → ③ git push`  
GitHub에서 PR을 만들려면 먼저 push가 필요. 정책 18 (push 전 Codex 검증)과도 충돌.  
권장 수정: `① 커밋 → ② Codex 검증 의뢰 → ③ git push → ④ PR 생성 → ⑤ STATE.md 갱신 → ⑥ 아키텍처 동기화`

### P1-10: `.codex/rules/` 8종에 🔴 항목 대거 누락

Codex rules가 Claude rules의 30~80% 압축이며 고위험(🔴) 항목 상당수 미포함.  
우선순위 높은 누락 항목:

| rules 파일 | 누락 🔴 항목 |
|-----------|------------|
| `api.md` | 5xx 자동 재시도 (신뢰 API 한정), PyGithub asyncio.to_thread 의무, race-recovery result_dict is None 시그널 |
| `pipeline.md` | RailwayDeployEvent nested 구조 (평면 접근 2026-04-22 제거), golangci-lint go.mod 자동생성 |
| `ui.md` | leaderboard_opt_in 폐기 (부활 금지), dashboard KPI 구조, Auto-merge KPI 시각 우선순위 |
| `deploy.md` | Tailwind v4 빌드 (`npm ci && npm run build` buildCommand 필수) |
| `testing.md` | PARITY GUARD 패턴, hot-path 함수 시그니처 변경 금지 |

---

## 🟡 P2 — 개선 (효율성·볼륨 최적화)

### P2-1: CLAUDE.md 정책 섹션 압축

정책 섹션 280줄 중 정책 8 (48줄), 정책 18 (40줄)이 비대. 진화 detail은 이미 `docs/policies/history.md`에 external. default rule 핵심 유지 + 압축으로 ~80줄 절감 가능. **정책 17 안정성 원칙 적용 필수 — 행동 drift 없이 압축해야 함**.

### P2-2: `docs/STATE.md` 볼륨 최적화

2012줄 중 작업 이력 ~1950줄. 그룹 85 이전 이력 `docs/_archive/STATE-groups-before-85.md`로 분리 가능.

### P2-3: AGENTS.md ↔ CLAUDE.md 중복 제거

핵심 명령 표, env-vars 요약 표, 브랜치 명명 표가 양쪽에 중복.  
AGENTS.md에서는 `docs/reference/env-vars.md` 링크로 대체 가능 (AGENTS.md 자기완결성 vs 중복 트레이드오프 판단 필요).

### P2-4: `.claude/rules/testing.md`에 역방향 추가

`.codex/rules/testing.md`에 있으나 `.claude/rules/testing.md`에 없는 유용한 항목:  
"SessionLocal Mock은 ORM 속성 오류 미감지 → 핵심 라우트에 실 DB 테스트 병행 필수"

### P2-5: `docs/architecture.md` 누락 항목

`src/static/mockup-polar.html` static/ 섹션에 미표기.

---

## 작업 분할 제안 (PR 단위)

| PR | 범위 | 파일 수 | 우선순위 |
|----|------|--------|--------|
| **PR-A** | P0 전체 fix (hooks.json 경로 + CLAUDE.md 메모리/gh CLI/카테고리 + MEMORY.md 데드링크) | 3~4개 | 즉시 |
| **PR-B** | P1-1~P1-6 (AGENTS.md 정책 15/17 추가 + doc_review_gate.py AGENTS.md CRITICAL 추가 + doc-impact-analyzer.toml 정정 + STATE.md 수치) | 4~5개 | 이번 사이클 |
| **PR-C** | P1-7~P1-10 (.codex/rules/ 🔴 누락 항목 추가 + AGENTS.md 경로 표 + deploy.md 정정 + 완료 5-step 순서) | 5~6개 | 이번 사이클 |
| **PR-D** | P2 전체 (볼륨 최적화 — 정책 17 안정성 원칙 5+1 검증 후 진행) | 多 | 다음 사이클 |

**PR-A → PR-B → PR-C 순서로 진행 권장**.  
각 PR은 Codex 검증 OK 받은 후 push (정책 18).

---

## 체크리스트 (다음 세션 작업자용)

### PR-A 착수 전 확인
```bash
gh run list --limit 3                           # CI 상태
gh api repos/xzawed/SCAManager/code-scanning/alerts --jq '[.[] | select(.state=="open")] | length'
git status
git checkout -b fix/doc-cleanup-phase-a
```

### PR-A 수정 대상 파일
- [ ] `.codex/hooks.json` — 경로 절대→상대 (또는 환경 감지)
- [ ] `.codex/hooks/doc_review_gate.py:16` — `_PROJECT_PREFIXES` 경로 수정
- [ ] `CLAUDE.md` — 정책 10 (gh CLI), 메모리 경로, 메모리 인덱스, 카테고리 수
- [ ] `C:\Users\dirtc\.claude\projects\d--Source-SCAManager\memory\MEMORY.md` — 데드링크 제거

### 검증
```bash
make test   # 테스트 전체 통과 확인
make lint   # lint 통과 확인
```

### Codex 검증 의뢰 (push 전 필수)
"PR-A 수정 내용 검토 요청: hooks.json 경로 수정 방식이 올바른지, CLAUDE.md 정책 10 정정이 실제 환경과 맞는지 확인 부탁"

---

*생성: 2026-05-11 사이클 95 준비 / 5+1 다중 에이전트 감사 결과*
