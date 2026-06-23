// loop-until-dry 정본 템플릿 (참조 전용 — 워크플로우는 이 파일을 ES import 불가)
// Canonical loop-until-dry template (REFERENCE ONLY — workflows cannot ES-import this file)
//
// 🔴 런타임 실측 (2026-06-23, PR-W W1 검증 게이트):
//    워크플로우 스크립트는 sibling .mjs 를 import 할 수 없다.
//      - 정적 `import { x } from './y.mjs'` → SyntaxError ("import call expects one or two arguments")
//      - 동적 `await import('./y.mjs')`      → "import() is not available in workflow scripts."
//    Runtime-verified: workflow scripts cannot import sibling .mjs
//    (static import → SyntaxError, dynamic import() → unavailable).
//
// 따라서 정책 16 단일출처는 'import' 가 아니라 '인라인 복사 + drift 가드 테스트' 로 달성한다.
// Single-source (policy 16) is therefore achieved by 'inline copy + drift guard test',
// not by import. The guard test (tests/unit/scripts/test_workflow_loop_sync.py) enforces that
// every consumer workflow declares identical params and contains the core invariants.
//
// 사용처 / Used by: integrity-audit.mjs, retrospective.mjs

// ── 정본 파라미터 (모든 사용처가 동일 값으로 인라인 `const` 선언 의무) ──
// Canonical parameters (every consumer must inline-declare identical `const` values).
// 값 변경 시 본 템플릿 + 모든 사용처를 동시에 갱신해야 함 (가드 테스트가 drift 차단).
// Changing a value requires updating this template AND every consumer together
// (the guard test blocks drift).
export const LOOP_PARAMS = {
  DRY_THRESHOLD: 2,            // 연속 신규-0 라운드 N회 시 종료 / stop after N consecutive dry rounds
  MAX_ROUNDS_WITH_BUDGET: 5,   // budget.total 설정 시 라운드 상한 / round cap when a budget is set
  MAX_ROUNDS_NO_BUDGET: 3,     // budget 미설정 시 보수적 상한 / conservative cap without budget
  BUDGET_FLOOR: 60_000,        // 잔여 budget 이 이 값 미만이면 중단 / stop when remaining budget < this
}

// ── 정본 스켈레톤 (인라인 복사 기준 — 핵심 불변식 4종) ──
// Canonical skeleton (inline-copy reference — the 4 core invariants the guard test checks):
//
//   const DRY_THRESHOLD = 2
//   const MAX_ROUNDS_WITH_BUDGET = 5
//   const MAX_ROUNDS_NO_BUDGET = 3
//   const BUDGET_FLOOR = 60_000
//
//   const seen = new Set()                                   // (1) dedup: 발견된 모든 finding 키
//   const confirmed = []
//   let dry = 0, round = 0
//   const MAX_ROUNDS = budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET  // (3) round cap
//   while (dry < DRY_THRESHOLD &&                            // (2) dry counter: 연속 신규-0 종료
//          round < MAX_ROUNDS &&
//          (!budget.total || budget.remaining() > BUDGET_FLOOR)) {  // (4) budget floor
//     round++
//     const found = /* 도메인 병렬 finder — domains parallel finder */
//     const fresh = found.filter((f) => !seen.has(key(f)))   // (1) dedup
//     if (!fresh.length) { dry++; continue }                 // (2) 신규 0 → dry 증가
//     dry = 0
//     fresh.forEach((f) => seen.add(key(f)))
//     /* verify fresh → confirmed.push(...) */
//   }
//   // + completeness critic + 표적 gap 라운드 / + completeness critic + targeted gap round
//
// 불변식 토큰 (가드 테스트가 각 사용처에서 존재 확인):
// Invariant tokens (guard test asserts each consumer contains them):
//   "seen.has(key("  ·  "dry < DRY_THRESHOLD"  ·  "dry++"  ·  "budget.remaining() > BUDGET_FLOOR"
