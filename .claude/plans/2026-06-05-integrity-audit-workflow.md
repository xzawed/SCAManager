# 전체 정합성 감사 Workflow 구현 계획
# Integrity Audit Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사이클 104/109의 수동 5+1 전수 감사를 결정론적 `.claude/workflows/integrity-audit.mjs` Workflow 스크립트로 코드화하여, read-only P0/P1/P2 정합성 리포트를 재현 가능하게 생성한다.

**Architecture:** B+C 결합 — scope 인식 팬아웃(C)으로 감싼 loop-until-dry 도메인 탐색(B) + 다관점(correctness/security/repro) adversarial verify(B) + completeness critic(C) + `MAX_ROUNDS`·`budget` 비용 상한(C). 워크플로우는 구조화 결함 데이터를 반환하고, **리포트 파일 작성과 `diff` scope의 git diff 수집은 호출자(메인 루프/스킬) 책임**이다 (Workflow 런타임은 파일시스템/shell 접근 불가).

**Tech Stack:** Claude Code Workflow 도구 (plain JS ESM 스크립트, `agent()`/`parallel()`/`phase()`/`log()`/`budget` 프리미티브), StructuredOutput 스키마, `.claude/skills/` 슬래시 명령.

---

## ⚠️ 검증 모델 (필독 — 일반 TDD 와 다름)

이 산출물은 **Workflow 오케스트레이션 JS 스크립트**이며 프로젝트의 Python/pytest 런타임에서 import·실행할 수 없다 (Workflow 전용 런타임에서 `agent`/`parallel`/`args`/`budget` 전역으로 동작). 따라서 pytest 기반 TDD 가 적용되지 않는다. 대신 **실행 기반 검증 + 무비용 dryRun 게이트**를 사용한다:

| 검증 수단 | 비용 | 검증 대상 |
|----------|------|----------|
| `args.dryRun=true` 경로 | ~0 (에이전트 0) | scope 해소·도메인 매핑·diff 매핑 등 **결정론적 로직** |
| `scope=area=gate` 실행 | 소 (2 도메인 × 라운드) | 오케스트레이션 plumbing·스키마·verify 파이프라인 end-to-end |
| `scope=full` 골든 비교 | 대 (8 도메인) | 사이클 109 수동 감사 재현율 (최종, **사용자 사전 승인 필수**) |

각 Task 는 "코드 추가 → 무비용 또는 소비용 실행 검증 → commit" 순서. `scope=full` 실행은 정책 8(≥5 에이전트)·정책 16#5(토큰)에 따라 **Task 9 에서 사용자 명시 승인 후에만** 수행한다.

---

## 파일 구조

| 파일 | 책임 | 신규/수정 |
|------|------|----------|
| `.claude/workflows/integrity-audit.mjs` | 워크플로우 스크립트 (meta + 도메인 정의 + 순수 헬퍼 + 프롬프트 빌더 + 스키마 + 5단계 오케스트레이션) | 신규 |
| `.claude/skills/integrity-audit.md` | `/integrity-audit` 슬래시 명령 — 호출자 책임(diff scouting + Workflow 호출 + 리포트 작성) 캡슐화 | 신규 |
| `docs/runbooks/integrity-audit.md` | 운영 가이드 — 호출법·scope·비용·리포트 해석·거버넌스 | 신규 |
| `CLAUDE.md` | "핵심 명령" 또는 Agent 작업 규칙에 워크플로우 1줄 등재 | 수정 |
| `docs/STATE.md` | 작업 이력에 사이클 항목 추가 | 수정 |
| `docs/cycle-history.md` | 사이클 이력 1줄 (6-step 의무) | 수정 |

> 리포트 산출물(`docs/reports/YYYY-MM-DD-integrity-audit-<scope>.md`)은 **실행 시점**에 생성되며 plan 파일이 아니다.

---

## Task 1: 워크플로우 스켈레톤 — meta + 도메인 정의 + 순수 헬퍼 + dryRun 게이트

**Files:**
- Create: `.claude/workflows/integrity-audit.mjs`

- [ ] **Step 1: 디렉토리 생성 + 스크립트 초기 작성**

`.claude/workflows/integrity-audit.mjs` 전체 내용 (이 Task 범위 = meta + 도메인 + 헬퍼 + scope 해소 + dryRun 조기 반환):

```js
// 전체 정합성 감사 Workflow — 사이클 104/109 수동 5+1 감사의 결정론적 코드화
// Integrity audit workflow — deterministic codification of the manual 5+1 audit (cycles 104/109)
export const meta = {
  name: 'integrity-audit',
  description: 'SCAManager 전체 정합성 감사 — read-only P0/P1/P2 리포트 (다관점 verify + completeness critic)',
  phases: [
    { title: 'Scope' },
    { title: 'Discover' },
    { title: 'Verify' },
    { title: 'Completeness' },
    { title: 'Report' },
  ],
}

// ── 도메인 정의 (경로 매칭 규칙) ──────────────────────────
// Domain definitions (path-matching rules) — .claude/rules 8-area 매트릭스 계승
const DOMAINS = [
  { id: 'pipeline', paths: ['src/worker/pipeline', 'src/analyzer/', 'src/scorer/'],
    focus: '멱등성·오류 처리·점수 정합 / idempotency, error handling, score integrity' },
  { id: 'gate', paths: ['src/gate/', 'src/services/merge_retry_service'],
    focus: '재시도 terminality·임계값 단일출처 / retry terminality, threshold single-source' },
  { id: 'security', paths: ['src/auth/', 'src/crypto', 'src/shared/log_safety', 'src/webhook/validator'],
    focus: 'SQLi·로그 인젝션·세션·HMAC / SQLi, log injection, session, HMAC' },
  { id: 'api', paths: ['src/api/', 'src/notifier/', 'src/webhook/', 'src/main.py'],
    focus: 'SSRF·소유권 검증·디스패처 / SSRF, ownership checks, dispatcher' },
  { id: 'db', paths: ['src/models/', 'src/database', 'src/repositories/', 'alembic/'],
    focus: 'ORM↔마이그레이션 drift·RLS·FK / ORM-migration drift, RLS, FK' },
  { id: 'ui', paths: ['src/templates/', 'src/static/', 'src/ui/', 'src/i18n/', 'src/middleware/locale'],
    focus: 'XSS·hx-boost 핸들러 누적·번역 fallback / XSS, handler accumulation, translation fallback' },
  { id: 'docs', paths: ['CLAUDE.md', 'docs/', '.claude/rules/'],
    focus: '수치·경로·선언↔현실 불일치 / metrics, paths, declaration-reality mismatch' },
  { id: 'tests', paths: ['tests/', 'e2e/', 'conftest.py'],
    focus: 'dead assertion·fixture↔ORM sync / dead assertions, fixture-ORM sync' },
]

// area=<name> 인접 도메인 매핑 (primary 1 + adjacent 1)
// area=<name> adjacency map (primary 1 + adjacent 1) — 데이터 흐름 근접도 기준
const ADJACENCY = {
  pipeline: 'gate', gate: 'pipeline',
  security: 'api', api: 'security',
  db: 'pipeline', ui: 'tests',
  docs: 'tests', tests: 'docs',
}

// ── 순수 헬퍼 ────────────────────────────────────────────
// Pure helpers
function resolveDomains(scope, changedFiles) {
  if (scope === 'full') return DOMAINS
  if (scope.startsWith('area=')) {
    const name = scope.slice(5).trim()
    const primary = DOMAINS.find((d) => d.id === name)
    if (!primary) throw new Error(`unknown area: ${name}`)
    const adj = DOMAINS.find((d) => d.id === ADJACENCY[name])
    return adj ? [primary, adj] : [primary]
  }
  if (scope === 'diff') {
    const files = changedFiles ?? []
    const hit = DOMAINS.filter((d) => files.some((f) => d.paths.some((p) => f.includes(p))))
    return hit.length ? hit : DOMAINS // 매칭 0 시 안전하게 전체 / fall back to full if nothing matched
  }
  throw new Error(`unknown scope: ${scope}`)
}

// finding 정규화 키 — 중복 제거용 (대소문자·공백 정규화)
// Normalized finding key for dedup (case + whitespace normalized)
function key(f) {
  return `${String(f.file).toLowerCase().trim()}:${f.line}:${String(f.title).toLowerCase().trim().replace(/\s+/g, ' ')}`
}

function dedupe(findings) {
  const seen = new Set()
  const out = []
  for (const f of findings) {
    const k = key(f)
    if (!seen.has(k)) { seen.add(k); out.push(f) }
  }
  return out
}

function count(findings, sev) {
  return findings.filter((f) => f.severity === sev).length
}

// args 는 객체 또는 JSON 문자열로 도달할 수 있음 — 정규화 (실측: scriptPath 호출 시 문자열 도달)
// args may arrive as an object or a JSON string — normalize to an object
function parseArgs(a) {
  if (typeof a === 'string') {
    try { return JSON.parse(a) } catch { return {} }
  }
  return a ?? {}
}

// ── 오케스트레이션 (Task 1 범위: scope 해소 + dryRun 조기 반환) ──
const opts = parseArgs(args)
const scope = opts.scope ?? 'full'
const dryRun = opts.dryRun === true
const changedFiles = opts.changedFiles ?? null

phase('Scope')
const domains = resolveDomains(scope, changedFiles)
log(`scope=${scope} → 도메인 [${domains.map((d) => d.id).join(', ')}]` +
    (changedFiles ? ` / 변경파일 ${changedFiles.length}건` : ''))

if (dryRun) {
  return { scope, dryRun: true, domains: domains.map((d) => d.id), changedFiles }
}

// (Task 2 이후 발견·검증·리포트 단계 추가)
return { scope, domains: domains.map((d) => d.id), confirmed: [], note: 'orchestration not yet implemented' }
```

- [ ] **Step 2: dryRun 으로 scope 해소 검증 (무비용)**

다음 3회 호출을 실행한다 (Workflow 도구). **⚠️ 실측: 이름(`name`) 해소는 빌트인(deep-research/code-review)만 가능 → `.claude/workflows/` 는 `scriptPath` 절대경로로 호출해야 한다**:
1. `Workflow({ scriptPath: '<abs>/.claude/workflows/integrity-audit.mjs', args: { scope: 'full', dryRun: true } })`
   기대 반환: `domains` 8개 전부 `['pipeline','gate','security','api','db','ui','docs','tests']`
2. `…args: { scope: 'area=gate', dryRun: true }` → `domains` = `['gate','pipeline']` (primary + adjacency)
3. `…args: { scope: 'diff', dryRun: true, changedFiles: ['src/gate/engine.py','docs/STATE.md'] }` → `domains` = `['gate','docs']`

> 셋 다 에이전트 0개 — 토큰 ~0. **실측 제약 2건**: (a) `name` 해소 불가 → `scriptPath` 필수. (b) `args` 는 JSON **문자열**로 도달 → 스크립트가 `parseArgs()` 로 정규화 (위 코드 반영됨).

- [ ] **Step 3: 반환값이 기대와 일치하는지 확인**

위 3회 반환 `domains` 배열이 정확히 기대값과 같은지 대조. area 해소(gate→[gate,pipeline]) + diff 매핑(gate/docs)이 핵심 회귀 포인트.

- [ ] **Step 4: Commit**

```bash
git add .claude/workflows/integrity-audit.mjs
git commit -m "feat(workflow): integrity-audit 스켈레톤 — scope 해소 + dryRun 게이트

feat(workflow): integrity-audit skeleton — scope resolution + dryRun gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 단일 발견 라운드 + FINDINGS_SCHEMA + 감사 프롬프트

**Files:**
- Modify: `.claude/workflows/integrity-audit.mjs`

- [ ] **Step 1: 스키마 + 감사 프롬프트 빌더 추가**

`DOMAINS`/`ADJACENCY` 정의 **아래**, 순수 헬퍼 근처에 추가:

```js
// ── 구조화 스키마 ────────────────────────────────────────
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain: { type: 'string' },
          severity: { type: 'string', enum: ['P0', 'P1', 'P2'] },
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          claim: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['domain', 'severity', 'title', 'file', 'line', 'claim'],
      },
    },
  },
  required: ['findings'],
}

// ── 프롬프트 빌더 ────────────────────────────────────────
function auditPrompt(domain, changedFiles, round) {
  const scopeNote = changedFiles
    ? `변경 파일에 한정: ${changedFiles.filter((f) => domain.paths.some((p) => f.includes(p))).join(', ') || '(이 도메인 직접 변경 없음 — 인접 영향만 점검)'}`
    : `도메인 전체 경로: ${domain.paths.join(', ')}`
  return [
    `당신은 SCAManager 정합성 감사관입니다. 도메인 "${domain.id}" 를 감사합니다.`,
    `감사 초점: ${domain.focus}`,
    scopeNote,
    round > 1 ? '이전 라운드에서 이미 보고된 결함은 제외하고, 더 깊은/놓친 결함만 보고하세요.' : '',
    '각 결함은 P0(운영 사고/보안)/P1(정합성 결함)/P2(품질) 으로 분류.',
    '🔴 정책 6 강제: 모든 file:line 은 `grep -n` 실측 후 작성. 추정 line 금지. evidence 필드에 실측 근거 인용.',
    'false-positive 회피: 단순 스타일·취향 차이는 보고 금지. 동작/보안/정합 영향이 있는 것만.',
    'findings 배열로 반환 (없으면 빈 배열).',
  ].filter(Boolean).join('\n')
}
```

- [ ] **Step 2: 오케스트레이션에 단일 발견 라운드 추가**

Task 1 의 마지막 임시 `return` (`note: 'orchestration not yet implemented'`) 을 **삭제**하고 그 자리에 추가:

```js
phase('Discover')
const round1 = (await parallel(domains.map((d) => () =>
  agent(auditPrompt(d, changedFiles, 1), { label: `audit:${d.id}:r1`, phase: 'Discover', schema: FINDINGS_SCHEMA })
))).filter(Boolean).flatMap((r) => r.findings ?? [])

log(`발견 라운드 1: 총 ${round1.length}건 (검증 전)`)
return { scope, rounds: 1, findings: dedupe(round1) }
```

- [ ] **Step 3: area=gate 로 발견 단계 검증 (소비용)**

`Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'area=gate' } })` 실행.
기대: gate + pipeline 2 에이전트가 각각 FINDINGS_SCHEMA 로 반환. `findings` 배열이 스키마(domain/severity/title/file/line/claim)를 만족. 결함 0건도 정상(빈 배열).

- [ ] **Step 4: 반환 스키마 준수 확인**

반환된 각 finding 이 `severity ∈ {P0,P1,P2}`, `file`/`line` 존재, `claim` 비어있지 않은지 확인. file:line 이 실존 파일을 가리키는지 1~2건 표본 `grep -n` 으로 대조.

- [ ] **Step 5: Commit**

```bash
git add .claude/workflows/integrity-audit.mjs
git commit -m "feat(workflow): integrity-audit 단일 발견 라운드 + FINDINGS 스키마

feat(workflow): integrity-audit single discovery round + FINDINGS schema

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 다관점 adversarial verify + VERDICT_SCHEMA

**Files:**
- Modify: `.claude/workflows/integrity-audit.mjs`

- [ ] **Step 1: VERDICT_SCHEMA + verify 프롬프트 + verifyFresh 헬퍼 추가**

스키마 블록에 추가:

```js
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    real: { type: 'boolean' },
    lens: { type: 'string', enum: ['correctness', 'security', 'repro'] },
    reason: { type: 'string' },
    citation_verified: { type: 'boolean' },
  },
  required: ['real', 'lens', 'reason'],
}
```

프롬프트 빌더에 추가:

```js
function verifyPrompt(f, lens) {
  const lensQ = {
    correctness: '이 결함 주장이 실제 동작을 파손하는가? 코드를 직접 읽고 확인하라.',
    security: '이 결함이 실제 데이터/권한 노출·보안 영향을 갖는가?',
    repro: '구체적 트리거 경로가 존재하는가? 그리고 인용된 file:line 이 실제로 존재하는지 grep 으로 재확인하라 (citation_verified 에 반영).',
  }[lens]
  return [
    '당신은 적대적 검증관입니다. 기본 입장은 "반증(real=false)" 입니다.',
    `검증 렌즈: ${lens} — ${lensQ}`,
    `주장된 결함: [${f.severity}] ${f.title} @ ${f.file}:${f.line}`,
    `근거: ${f.claim}`,
    '확신이 없으면 real=false. 명확히 진짜일 때만 real=true.',
  ].join('\n')
}
```

오케스트레이션 영역 상단(첫 `phase('Scope')` **위**)에 verifyFresh 헬퍼 정의:

```js
// fresh 결함들을 3 렌즈(correctness/security/repro) 병렬 검증 — 2/3 이상 real=true 시 confirmed
// Verify fresh findings via 3 lenses in parallel — confirmed when >= 2/3 vote real
async function verifyFresh(fresh) {
  return (await parallel(fresh.map((f) => () =>
    parallel(['correctness', 'security', 'repro'].map((lens) => () =>
      agent(verifyPrompt(f, lens), { label: `verify:${f.file}:${lens}`, phase: 'Verify', schema: VERDICT_SCHEMA })))
      .then((vs) => {
        const valid = vs.filter(Boolean)
        return { ...f, real: valid.filter((v) => v.real).length >= 2, verdicts: valid }
      })))).filter(Boolean)
}
```

- [ ] **Step 2: 발견 라운드 뒤에 verify 연결**

Task 2 의 `return { scope, rounds: 1, findings: dedupe(round1) }` 를 **삭제**하고 교체:

```js
const fresh1 = dedupe(round1)
phase('Verify')
const judged1 = await verifyFresh(fresh1)
const confirmed1 = judged1.filter((j) => j.real)
log(`검증: ${fresh1.length}건 중 ${confirmed1.length}건 confirmed`)
return { scope, rounds: 1, confirmed: confirmed1, fp_blocked: fresh1.length - confirmed1.length }
```

- [ ] **Step 3: area=gate 로 verify 파이프라인 검증 (소비용)**

`Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'area=gate' } })` 실행.
기대: 발견된 각 finding 당 3 렌즈 에이전트가 verdict 반환. `confirmed` = 2/3 이상 real=true 인 것만. `fp_blocked` 카운트가 (발견 - confirmed) 와 일치.

- [ ] **Step 4: 다수결 로직 확인**

진행 트리(`/workflows`)에서 verify:* 에이전트가 finding 당 3개씩 뜨는지, 반환 `confirmed` 가 다수결을 반영하는지 확인.

- [ ] **Step 5: Commit**

```bash
git add .claude/workflows/integrity-audit.mjs
git commit -m "feat(workflow): integrity-audit 다관점 adversarial verify (3 렌즈 다수결)

feat(workflow): integrity-audit perspective-diverse adversarial verify (3-lens majority)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: loop-until-dry + MAX_ROUNDS·budget 비용 상한

**Files:**
- Modify: `.claude/workflows/integrity-audit.mjs`

- [ ] **Step 1: 단일 라운드를 loop-until-dry 로 교체**

Task 3 의 `phase('Discover')` 부터 `return {...}` 까지 전체 블록을 **삭제**하고 교체:

```js
const seen = new Set()
const confirmed = []
let dry = 0
let round = 0
const MAX_ROUNDS = budget.total ? 5 : 3 // budget 설정 시 5, 미설정 시 보수적 3

phase('Discover')
while (dry < 2 && round < MAX_ROUNDS && (!budget.total || budget.remaining() > 60_000)) {
  round++
  const found = (await parallel(domains.map((d) => () =>
    agent(auditPrompt(d, changedFiles, round), { label: `audit:${d.id}:r${round}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? [])

  const fresh = found.filter((f) => !seen.has(key(f)))
  if (!fresh.length) { dry++; log(`라운드 ${round}: 신규 0 (dry ${dry}/2)`); continue }
  dry = 0
  fresh.forEach((f) => seen.add(key(f)))
  log(`라운드 ${round}: 신규 ${fresh.length}건 → 검증`)

  const judged = await verifyFresh(fresh)
  confirmed.push(...judged.filter((j) => j.real))
}

phase('Report')
const finalConfirmed = dedupe(confirmed)
return {
  scope,
  rounds: round,
  confirmed: finalConfirmed,
  roi: {
    fp_blocked: seen.size - finalConfirmed.length,
    new: finalConfirmed.length,
    p0: count(finalConfirmed, 'P0'),
    p1: count(finalConfirmed, 'P1'),
    p2: count(finalConfirmed, 'P2'),
  },
}
```

- [ ] **Step 2: dedup 대상이 `seen` 인지 확인 (수렴 함정 회피)**

코드 리뷰: `fresh` 필터가 `seen` 기준이고, verify 에서 reject 된 finding 도 이미 `seen` 에 들어가 다음 라운드 재등장하지 않는지 확인 (무한 루프 방지 핵심).

- [ ] **Step 3: area=gate 로 루프 종료 조건 검증 (소비용)**

`Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'area=gate' } })` 실행.
기대: 라운드가 "2회 연속 신규 0" 또는 `MAX_ROUNDS(=3)` 도달 시 종료. `log` 에 `dry 1/2`, `dry 2/2` 진행이 보이는지 확인. `roi` 객체에 fp_blocked/new/p0/p1/p2 채워짐.

- [ ] **Step 4: Commit**

```bash
git add .claude/workflows/integrity-audit.mjs
git commit -m "feat(workflow): integrity-audit loop-until-dry + MAX_ROUNDS·budget 상한

feat(workflow): integrity-audit loop-until-dry + MAX_ROUNDS/budget cap

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: completeness critic + gap 라운드 + GAPS_SCHEMA

**Files:**
- Modify: `.claude/workflows/integrity-audit.mjs`

- [ ] **Step 1: GAPS_SCHEMA + completeness/gap 프롬프트 추가**

스키마 블록에 추가:

```js
const GAPS_SCHEMA = {
  type: 'object',
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain: { type: 'string' },
          modality: { type: 'string' },
          why: { type: 'string' },
        },
        required: ['domain', 'modality', 'why'],
      },
    },
  },
  required: ['items'],
}
```

프롬프트 빌더에 추가:

```js
function completenessPrompt(domains, confirmed, scope) {
  return [
    '당신은 완전성 비평가입니다 (5+1 의 +1 cross-verify 역할).',
    `감사 scope: ${scope}. 커버된 도메인: ${domains.map((d) => d.id).join(', ')}.`,
    `현재까지 confirmed 결함 ${confirmed.length}건.`,
    '다음 미검증 영역을 식별하라:',
    '(a) 깊이 점검 안 된 도메인',
    '(b) 미검증 modality — 마이그레이션 ORM drift, 신규 env-var 의 docs/reference/env-vars.md 등재, .claude/rules path-scoped sync, 테스트 수 배지 동기화 등',
    '각 gap 은 {domain, modality, why}. 진짜 누락만 — 추측 금지. 없으면 빈 배열.',
  ].join('\n')
}

function gapAuditPrompt(gap) {
  return [
    '당신은 표적 감사관입니다. 다음 gap 을 집중 감사하세요:',
    `도메인: ${gap.domain} / 미검증 양식: ${gap.modality} / 사유: ${gap.why}`,
    '🔴 정책 6 강제: file:line `grep -n` 실측. findings 배열 반환 (없으면 빈 배열).',
  ].join('\n')
}
```

- [ ] **Step 2: 루프 종료 후 ~ `phase('Report')` 사이에 completeness 단계 삽입**

Task 4 의 `while (...) { ... }` 닫는 `}` 와 `phase('Report')` **사이**에 삽입:

```js
phase('Completeness')
const gaps = await agent(completenessPrompt(domains, confirmed, scope), { label: 'completeness', schema: GAPS_SCHEMA })
if (gaps?.items?.length) {
  log(`completeness: gap ${gaps.items.length}건 → 표적 라운드`)
  const gapFound = (await parallel(gaps.items.map((g) => () =>
    agent(gapAuditPrompt(g), { label: `gap:${g.domain}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? []).filter((f) => !seen.has(key(f)))
  gapFound.forEach((f) => seen.add(key(f)))
  const gapJudged = await verifyFresh(gapFound)
  confirmed.push(...gapJudged.filter((j) => j.real))
}
```

- [ ] **Step 3: area=gate 로 completeness 단계 검증 (소비용)**

`Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'area=gate' } })` 실행.
기대: 루프 종료 후 `completeness` 에이전트 1개가 GAPS_SCHEMA 반환. gap 이 있으면 표적 감사 + verify 추가 라운드 1회, 없으면 바로 Report. gap 결과도 `seen` 에 추가되어 최종 dedup 정확.

- [ ] **Step 4: Commit**

```bash
git add .claude/workflows/integrity-audit.mjs
git commit -m "feat(workflow): integrity-audit completeness critic + gap 표적 라운드

feat(workflow): integrity-audit completeness critic + targeted gap round

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `/integrity-audit` 슬래시 명령 래퍼 (호출자 책임 캡슐화)

**Files:**
- Create: `.claude/skills/integrity-audit.md`

> 워크플로우 런타임은 git/파일시스템 접근 불가 → `diff` scope 의 변경 파일 수집과 리포트 작성은 호출자 책임. 이 스킬이 그 책임을 캡슐화한다.

- [ ] **Step 1: 스킬 파일 작성**

`.claude/skills/integrity-audit.md` 전체:

```markdown
---
description: 전체 정합성 감사 Workflow 실행 — read-only P0/P1/P2 리포트 생성
---

`.claude/workflows/integrity-audit.mjs` 워크플로우를 실행하고 결과를 `docs/reports/` 리포트로 작성한다.

## 인자 해석

- `/integrity-audit` 또는 `/integrity-audit full` → `args: { scope: 'full' }` (8 도메인 전수, **토큰 다량 — 사용자 확인 후 실행**)
- `/integrity-audit diff` → 먼저 `git diff --name-only main...HEAD` 실행해 변경 파일 목록 수집 → `args: { scope: 'diff', changedFiles: [...] }`
- `/integrity-audit area=<name>` → `args: { scope: 'area=<name>' }` (`<name>` ∈ pipeline/gate/security/api/db/ui/docs/tests)

## 실행 절차

1. (diff 모드만) `git diff --name-only main...HEAD` 로 changedFiles 수집.
2. `Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: {...} })` 호출.
3. 반환된 `{ scope, rounds, confirmed[], roi }` 를 `docs/reports/YYYY-MM-DD-integrity-audit-<scope>.md` 로 작성 (아래 포맷).
4. 리포트 경로와 ROI 요약(P0/P1/P2 카운트 + fp_blocked)을 사용자에게 보고. **fix 는 사용자가 정책 7/15/18 에 따라 PR 로 결정** — 자동 수정 금지.

## 리포트 포맷

\`\`\`markdown
# 정합성 감사 리포트 — <scope> (YYYY-MM-DD)

| 항목 | 값 |
|------|-----|
| scope | <scope> |
| 라운드 | <rounds> |
| confirmed | <new> (P0 <p0> / P1 <p1> / P2 <p2>) |
| false-positive 차단 | <fp_blocked> |

## 도메인별 confirmed 결함

| severity | file:line | 도메인 | claim | 3-렌즈 (C/S/R) |
|----------|-----------|--------|-------|----------------|
| P0 | path:line | domain | ... | ✅/✅/✅ |

## 🔍 사용자 검증 필요 (정책 2)
- P0 우선 검토 권장 — 운영 사고/보안 영향
- fix 는 정책 7(PR 단위)/15(사전 사고)/18(Codex mutual)에 따라 진행
\`\`\`

## 비용·거버넌스 주의

- `full` 은 8 도메인 × 다라운드 = 다수 에이전트. 정책 8(≥5 에이전트)·16#5(토큰) — 사용자 명시 호출 = 동의로 간주하되, 매 실행 전 예상 비용 1줄 보고.
- 워크플로우는 read-only. 코드/문서 수정 없음.
```

- [ ] **Step 2: 스킬 인식 확인**

`/integrity-audit` 가 스킬 목록에 노출되는지 확인 (세션 재시작 또는 스킬 리로드 필요할 수 있음). 노출 안 되면 Task 7 runbook 에 "인라인 Workflow 직접 호출" 대체 경로 명시.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/integrity-audit.md
git commit -m "feat(skill): /integrity-audit 슬래시 명령 — diff scouting + 리포트 작성 캡슐화

feat(skill): /integrity-audit slash command — diff scouting + report writing

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 운영 runbook + 문서 동기화 (6-step)

**Files:**
- Create: `docs/runbooks/integrity-audit.md`
- Modify: `CLAUDE.md`
- Modify: `docs/STATE.md`
- Modify: `docs/cycle-history.md`

- [ ] **Step 1: runbook 작성**

`docs/runbooks/integrity-audit.md` 작성 — 내용: 목적(수동 5+1 코드화), 호출 3-레이어(저장형/스킬/인라인), scope 모드 표, 비용 가이드(area<diff<full), 리포트 해석법, 거버넌스(read-only·fix는 사용자 PR), 검증 모델(dryRun·area=gate·full 골든), B+C 아키텍처 1단락. spec 문서([docs/design/2026-06-05-integrity-audit-workflow-design.md](../design/2026-06-05-integrity-audit-workflow-design.md)) 링크.

- [ ] **Step 2: CLAUDE.md 에 1줄 등재**

`CLAUDE.md` "Agent 작업 규칙" 섹션 또는 "핵심 명령" 표 근처에 1줄:
> 전체 정합성 감사 자동화: `/integrity-audit [full|diff|area=<name>]` → `.claude/workflows/integrity-audit.mjs` (read-only P0/P1/P2 리포트, runbook: `docs/runbooks/integrity-audit.md`).

- [ ] **Step 3: STATE.md 작업 이력 + cycle-history.md 1줄 추가**

`docs/STATE.md` "작업 이력" 에 본 사이클 항목 추가 (다이나믹 워크플로우 1단계 — integrity-audit 워크플로우 도입). `docs/cycle-history.md` 에 동일 1줄.

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks/integrity-audit.md CLAUDE.md docs/STATE.md docs/cycle-history.md
git commit -m "docs: integrity-audit runbook + CLAUDE.md·STATE·cycle-history 동기화

docs: integrity-audit runbook + CLAUDE.md/STATE/cycle-history sync

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: diff 골든 회귀 검증 (현재 브랜치, 소비용)

**Files:** (코드 변경 없음 — 검증 only)

- [ ] **Step 1: diff scope 실행**

`git diff --name-only main...HEAD` 로 현재 브랜치 변경 파일 수집 → `Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'diff', changedFiles: [...] } })`.
기대: 변경 파일이 닿는 도메인만 팬아웃 (대부분 docs). confirmed 결함 0~소수. 무한 루프 없이 정상 종료.

- [ ] **Step 2: 리포트 작성 경로 검증**

반환값을 `docs/reports/2026-06-05-integrity-audit-diff.md` 로 Task 6 포맷에 맞춰 작성. ROI 표·도메인별 표·사용자 검증 섹션이 정확한지 확인.

- [ ] **Step 3: Commit (리포트 산출물)**

```bash
git add docs/reports/2026-06-05-integrity-audit-diff.md
git commit -m "test(workflow): integrity-audit diff 골든 회귀 검증 리포트

test(workflow): integrity-audit diff golden regression report

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: full 골든 비교 (사용자 사전 승인 필수, 토큰 다량)

**Files:** (코드 변경 없음 — 최종 검증)

- [ ] **Step 1: 사용자 승인 확보**

`scope=full` 은 8 도메인 × 다라운드 = 다수 에이전트. **실행 전 사용자에게 예상 비용 + 승인 요청** (정책 8·16#5). 승인 없으면 이 Task 보류.

- [ ] **Step 2: full 실행 + 골든 비교**

`Workflow({ scriptPath: '.claude/workflows/integrity-audit.mjs', args: { scope: 'full' } })` 실행.
기대 골든: 사이클 109 수동 감사가 찾은 류의 결함(예: `database.py` RLS f-string SQL injection 같은 P0)을 재발견하는가? 재현율을 정성 평가. false-positive 가 verify 에서 적절히 차단되는가?

- [ ] **Step 3: 리포트 작성 + 재현율 평가 기록**

`docs/reports/2026-06-05-integrity-audit-full.md` 작성 + runbook 에 "골든 비교 결과 + 재현율 관찰" 1단락 추가.

- [ ] **Step 4: Commit**

```bash
git add docs/reports/2026-06-05-integrity-audit-full.md docs/runbooks/integrity-audit.md
git commit -m "test(workflow): integrity-audit full 골든 비교 (사이클 109 재현율 평가)

test(workflow): integrity-audit full golden comparison (cycle 109 recall eval)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 최종: Codex mutual 검증 + push + PR (정책 18·7·10)

모든 Task 완료 후 **push 전**:
1. Codex 검증 의뢰 (정책 18 — push 전 의무). NG 시 자율 수정 금지 → 옵션 표 + 사용자 confirm.
2. Codex OK 후 `git push -u origin feat/integrity-audit-workflow`.
3. `gh pr create` — PR 본문에 §"🔍 사용자 검증 필요"(정책 2) + §"자율 판단 보고"(정책 3) + 검증 모델 설명 + full 골든 비교 결과.

---

## 미해결 항목 확정 (spec 섹션 11 → 본 계획에서 결정)

| 항목 | 결정 |
|------|------|
| `MAX_ROUNDS` | budget 설정 시 5 / 미설정 시 3 (Task 4). full 골든(Task 9) 후 필요 시 조정 |
| 스킬 래퍼 | **포함** — Task 6 `/integrity-audit` (diff scouting·리포트 작성 호출자 책임 캡슐화) |
| area 인접 도메인 | Task 1 `ADJACENCY` 맵 확정 (pipeline↔gate / security↔api / db→pipeline / ui→tests / docs→tests) |
| diff 변경파일 수집 | **호출자 책임** (Workflow 런타임 git 불가) — 스킬/메인루프가 `git diff` 후 `args.changedFiles` 전달 |
| 리포트 파일 작성 | **호출자 책임** (Workflow 런타임 파일시스템 불가) — 워크플로우는 구조화 데이터 반환, 메인루프/스킬이 Write |
| 워크플로우 호출 방식 | **`scriptPath` 절대경로 필수** (실측 — `name` 해소는 빌트인 deep-research/code-review 만 가능, `.claude/workflows/` 자동 등록 안 됨) |
| args 전달 형식 | **JSON 문자열로 도달** (실측 — scriptPath 호출 시) → 스크립트 `parseArgs()` 가 객체/문자열 양쪽 정규화 |
