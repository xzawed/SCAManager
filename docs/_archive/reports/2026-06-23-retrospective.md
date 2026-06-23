# 2026-06-23 잔여작업 세션 회고 (retrospective.mjs 첫 dogfooding)

**워크플로우**: `wf_fbf8355f-538` (`.claude/workflows/retrospective.mjs`, PR-W W3 신설 후 첫 실전) | **scope**: session (#973·#974·#975)
**ROI**: findings_total 69 · confirmed 55 (P1 2 / P2 53) · FP 차단 14 · SEVERITY_ADJUST 12 · **verdict_coverage 1.0** · unverified 0 · 85 에이전트 · 3 라운드
**dogfooding 결과**: ✅ cross-verify=finding 강제 작동(69 전건 verdict) = "단일 패스 회고 13건 중 8건만 검증" 한계 실해소 입증. ⚠️ completeness critic 라운드가 마지막에 API 500(서버측 일시 오류)으로 실패 — gap 라운드 미수행(워크플로우 결함 아님, 단 resilience 갭 = C10-e).

> 본 보고서는 회고 P1 #39(회고 보고서 미아카이브 반복 — GAP-4/P2-2 "범위 모호"의 근본)를 직접 해소하기 위해 아카이브됨.

---

## 클러스터 (55 confirmed → 12 테마, 중복 제거)

### 🔴 C1. 자초 CodeQL cascade 근본 미봉인 (P1) — findings #1·#6·#22·#25·#45
- **실측**: main 기준 distinct 자초 CodeQL fix 5건(#516/#517/#520/#521/#522), test-cleanup 동형 4건(#517/#520/#521/#522). (cross-verify가 finder "7번째" 과장 정정 → 4건)
- **근본**: `tests/*` 가 (a) setup.cfg `per-file-ignores` F401/F841 무시 + (b) Makefile `flake8 src/` = tests/ 미스캔 + (c) CI 가 diff 에 flake8/pylint 미실행 → pre-merge 단계가 tests/ dead symbol 에 무력 → **main full-scan CodeQL 만 사후 포착 → 매번 별도 fix PR**.
- **권장**: tests/ 대상 dead-import/var 차단 pre-commit 가드(pyflakes tests/ 스코프 또는 vulture) PR-H 훅 세트 검토 / 또는 testing.md "test 정리 PR = 동일 PR 내 dead symbol 동반 제거" 체크리스트 1줄. (spec 8 비-목표 충돌 — 사용자 결정 영역, 본 follow-up 미포함)

### 🔴 C2. 회고 보고서 미아카이브 반복 (P1) — finding #39 → ✅ 본 follow-up 해소
- GAP-4/P2-2 "범위 모호"의 근본 원인. 회고 산출물(verdict_coverage·confirmed 등)이 docs/메모리에 환류되는 추적성 경로 미정의.
- **해소**: 본 보고서 아카이브 + retrospective.md runbook 에 "보고서 아카이브" 단계 명시.

### C3. W2 파라미터화 미완 (P2, 실버그) — #7·#26·#44·#49 → ✅ 본 follow-up 해소
- `integrity-audit.mjs:291` 로그 문자열 `dry ${dry}/2` 에 하드코딩 `/2` 잔존(DRY_THRESHOLD 미적용). retrospective.mjs 는 정정됨 = 비대칭. PR #974 본문 "명명 상수화" 단언과 불일치.
- **해소**: `/2` → `/${DRY_THRESHOLD}` 정정.

### C4. drift 가드 coverage 부분 (P2) — #8·#14·#18·#23·#27·#36·#42·#43·#50·#53 → ✅ 본 follow-up 부분 해소
- (a) MAX_ROUNDS 상수 '선언값'만 검사, '사용/배선' 미검증 → declared-but-unused 우회 가능. (b) round-cap·`dry=0` reset·`seen.add` 불변식 미강제. (c) `token not in text` substring = **주석 false-pass 안티패턴 재발**([[feedback-docs-sync-codeql-gotchas]] #936 학습 미적용).
- **해소**: 주석 제거(`_strip_comments`) 후 불변식 매칭 + 불변식 확장(seen.add·dry=0·round<MAX_ROUNDS·`budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET` 사용 강제) + 주석-only false-pass 회귀 테스트.

### C5. 신규 .mjs 순수 로직 단위 테스트 0 (P2, 백로그) — #10·#46
- retrospective.mjs 304줄의 dedupe/key/count/coverage 순수 함수가 drift 가드(정적 token)만 있고 행동 단위 테스트 없음. (워크플로우 런타임 글로벌 의존이라 격리 테스트 비용 큼 — 백로그)

### C6. retrospective.mjs runbook 비대칭 (P2) — #12·#30·#33·#48 → ✅ 본 follow-up 해소
- peer 워크플로우 integrity-audit 는 runbook 보유, retrospective.mjs 는 부재. **해소**: `docs/runbooks/retrospective.md` 신설.

### C7. 설계 spec 상태 헤더 stale (P2) — #11·#47 → ✅ 본 follow-up 해소
- `docs/design/2026-06-23-repo-automation-design.md` 상태 = "승인됨 → writing-plans 대기"인데 전량 머지 완료. **해소**: "완료(#969/#974/#975)" 갱신.

### C8~C12 (백로그)
- **C8** integrity-audit runbook 멀티파일 sync(신규 _lib·drift 가드 반영) + architecture.md scripts/ 단일출처에 check_docs_sync/toc_anchors 등록.
- **C9** drift 가드 pre-commit 승격(spec 8 비-목표 재평가 — 사용자 결정).
- **C10** retrospective.mjs 자체 결함: evidence/citation 출력 소실 · completeness 라운드 try/catch resilience(이번 500 연관) · SEVERITY_ADJUST adjusted_severity 기본값 · verdict_coverage<1.0 자동 재시도 부재(반자동).
- **C11** 자기 자동화 스펙 과대 기술 안티패턴(docs-sync.md 오기) → codex-verify.md/정책 15 에 "훅 동작 단언 시 소스 grep 실측" 체크포인트(백로그).
- **C12** 머지 후 로컬 브랜치 미정리(clean_gone) + drift 가드 `_WORKFLOWS` allowlist enrollment gap.

---

## 본 follow-up(fix/retrospective-followup-hardening) 처리 범위
✅ C2(보고서 아카이브) · C3(W2 `/2`) · C4(drift 가드 false-pass 봉인 + 불변식 확장) · C6(retrospective runbook) · C7(spec 헤더).
🔶 백로그(사용자 결정/저우선): C1(CodeQL cascade 근본 — spec 8 충돌) · C5(.mjs 단위테스트) · C8·C9·C10·C11·C12.

## dogfooding 평가 (retrospective.mjs 자기 검증)
- ✅ **핵심 ROI 입증**: verdict_coverage 1.0 (69 전건) — 단일 패스 회고 한계를 실데이터로 해소. loop-until-dry 3라운드·dedup·cross-verify=finding 정상.
- ✅ FP 14·SEVERITY_ADJUST 12 = cross-verify 가 finder 과장(예 "7번째 cascade"→4건)을 정정.
- ⚠️ 결함(C10): completeness critic 라운드 API 500 미복구(resilience) · evidence/citation 출력 소실 · 자유 발언·회고 질문은 워크플로우 스키마 밖(스킬/Claude 절차 의존).
