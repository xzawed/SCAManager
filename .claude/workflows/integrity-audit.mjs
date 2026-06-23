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

// args 는 객체 또는 JSON 문자열로 도달할 수 있음 — 정규화
// args may arrive as an object or a JSON string — normalize to an object
function parseArgs(a) {
  if (typeof a === 'string') {
    try { return JSON.parse(a) } catch { return {} }
  }
  return a ?? {}
}

// ── 구조화 스키마 ────────────────────────────────────────
// Structured output schemas (StructuredOutput 강제 — 파싱 0)
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

// completeness critic 가 식별한 미검증 영역(gap) 목록 스키마
// Gap list schema — uncovered areas surfaced by the completeness critic
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

// ── 프롬프트 빌더 ────────────────────────────────────────
// Prompt builders
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

// completeness 비평가 프롬프트 — 5+1 의 +1 cross-verify 역할 (미검증 영역 식별)
// Completeness critic prompt — the +1 cross-verify of the 5+1 pattern (surface uncovered areas)
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

// 표적 gap 감사 프롬프트 — completeness 가 지목한 미검증 영역 집중 감사
// Targeted gap-audit prompt — focused audit of an area the completeness critic flagged
function gapAuditPrompt(gap) {
  return [
    '당신은 표적 감사관입니다. 다음 gap 을 집중 감사하세요:',
    `도메인: ${gap.domain} / 미검증 양식: ${gap.modality} / 사유: ${gap.why}`,
    '🔴 정책 6 강제: file:line `grep -n` 실측. findings 배열 반환 (없으면 빈 배열).',
  ].join('\n')
}

// 단일 렌즈로 결함 1건 판정 (적대적 검증관 에이전트)
// Judge one finding through a single lens (adversarial verifier agent)
// 고동시성에서 서브에이전트가 StructuredOutput 호출을 누락(flake)할 수 있으므로 1회 재시도.
// Subagents can skip the StructuredOutput call under high concurrency (flake), so retry once.
async function judgeLens(f, lens) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const v = await agent(verifyPrompt(f, lens), {
        label: `verify:${f.file}:${lens}${attempt ? ':retry' : ''}`, phase: 'Verify', schema: VERDICT_SCHEMA,
      })
      if (v) return v
    } catch {
      // StructuredOutput 누락/오류 — 재시도로 넘어감 / missed StructuredOutput — fall through to retry
    }
  }
  return null
}

// 결함 1건을 3 렌즈 병렬 판정 — 2/3 이상 real=true 시 confirmed.
// 검증 렌즈가 2개 미만만 응답하면 다수결 불가 → unverified 로 표시(조용한 false-negative 방지).
// Judge one finding across 3 lenses — confirmed when >= 2/3 vote real.
// If fewer than 2 lenses returned a verdict, majority is impossible → mark unverified (avoid silent false-negatives).
function verifyOne(f) {
  return parallel(['correctness', 'security', 'repro'].map((lens) => () => judgeLens(f, lens)))
    .then((vs) => {
      const valid = vs.filter(Boolean)
      const unverified = valid.length < 2
      return { ...f, real: !unverified && valid.filter((v) => v.real).length >= 2, unverified, verdicts: valid }
    })
}

// fresh 결함들을 소배치로 순차 검증 — area=gate(무결) 프로파일 모사로 고동시성 StructuredOutput 누락 차단.
// Verify fresh findings in small sequential batches — mirrors the clean area=gate profile to avoid
// high-concurrency StructuredOutput misses (full 33건 동시 검증 시 전면 붕괴 회귀 가드).
async function verifyFresh(fresh) {
  const VERIFY_BATCH = 4 // 배치당 4결함 × 3렌즈 = 12 에이전트 (area=gate 무결 수준)
  const out = []
  for (let i = 0; i < fresh.length; i += VERIFY_BATCH) {
    const chunk = fresh.slice(i, i + VERIFY_BATCH)
    out.push(...(await parallel(chunk.map((f) => () => verifyOne(f)))).filter(Boolean))
  }
  return out
}

// ── 오케스트레이션 (Task 5 범위: loop-until-dry + 다관점 verify + completeness critic) ──
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

// ── loop-until-dry (Task 4) — 정본 파라미터 (W2) ──
// 🔴 정본 값: .claude/workflows/_lib/loop-until-dry.template.mjs 와 동일 유지 의무.
//    drift 는 tests/unit/scripts/test_workflow_loop_sync.py 가드 테스트가 차단.
// Canonical params: must match _lib/loop-until-dry.template.mjs (drift blocked by the guard test).
const DRY_THRESHOLD = 2            // 연속 신규-0 라운드 N회 시 종료 / stop after N consecutive dry rounds
const MAX_ROUNDS_WITH_BUDGET = 5   // budget 설정 시 라운드 상한 / round cap with budget
const MAX_ROUNDS_NO_BUDGET = 3     // budget 미설정 시 보수적 상한 / conservative cap without budget
const BUDGET_FLOOR = 60_000        // 잔여 budget 하한 / remaining-budget floor
// seen = 이미 발견된 모든 결함 키 (verify reject/unverified 포함) — 재등장·무한루프 차단.
// seen = every finding key ever surfaced (incl. verify-rejected/unverified) — blocks re-emergence/infinite loop.
const seen = new Set()
const confirmed = []
const unverifiedAll = []
let dry = 0
let round = 0
const MAX_ROUNDS = budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET

phase('Discover')
while (dry < DRY_THRESHOLD && round < MAX_ROUNDS && (!budget.total || budget.remaining() > BUDGET_FLOOR)) {
  round++
  const found = (await parallel(domains.map((d) => () =>
    agent(auditPrompt(d, changedFiles, round), { label: `audit:${d.id}:r${round}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? [])

  const fresh = found.filter((f) => !seen.has(key(f)))
  if (!fresh.length) { dry++; log(`라운드 ${round}: 신규 0 (dry ${dry}/${DRY_THRESHOLD})`); continue }
  dry = 0
  fresh.forEach((f) => seen.add(key(f)))
  log(`라운드 ${round}: 신규 ${fresh.length}건 → 검증`)

  const judged = await verifyFresh(fresh)
  confirmed.push(...judged.filter((j) => j.real))
  unverifiedAll.push(...judged.filter((j) => j.unverified))
}

// ── completeness critic + 표적 gap 라운드 (Task 5) ──
phase('Completeness')
const gaps = await agent(completenessPrompt(domains, confirmed, scope), { label: 'completeness', phase: 'Completeness', schema: GAPS_SCHEMA })
if (gaps?.items?.length) {
  log(`completeness: gap ${gaps.items.length}건 → 표적 라운드`)
  const gapFound = (await parallel(gaps.items.map((g) => () =>
    agent(gapAuditPrompt(g), { label: `gap:${g.domain}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? []).filter((f) => !seen.has(key(f)))
  gapFound.forEach((f) => seen.add(key(f)))
  if (gapFound.length) {
    const gapJudged = await verifyFresh(gapFound)
    confirmed.push(...gapJudged.filter((j) => j.real))
    unverifiedAll.push(...gapJudged.filter((j) => j.unverified))
  }
}

// ── Report (구조화 데이터 반환 — 리포트 파일 작성은 호출자 책임) ──
phase('Report')
const finalConfirmed = dedupe(confirmed)
// fp_blocked = seen 전체 − confirmed − unverified = 검증 응답 받았으나 다수결 reject 된 것
// fp_blocked = total seen − confirmed − unverified = got verdicts but rejected by majority
const fpBlocked = seen.size - finalConfirmed.length - unverifiedAll.length
log(`종료: 라운드 ${round} / confirmed ${finalConfirmed.length} / fp ${fpBlocked} / unverified ${unverifiedAll.length}`)
return {
  scope,
  rounds: round,
  confirmed: finalConfirmed,
  unverified: unverifiedAll.length,
  unverified_findings: unverifiedAll.map((u) => ({ domain: u.domain, severity: u.severity, title: u.title, file: u.file, line: u.line })),
  roi: {
    fp_blocked: fpBlocked,
    new: finalConfirmed.length,
    p0: count(finalConfirmed, 'P0'),
    p1: count(finalConfirmed, 'P1'),
    p2: count(finalConfirmed, 'P2'),
  },
}
