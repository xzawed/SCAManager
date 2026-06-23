// 회고 Workflow — 정책 8 (5+1 다중 에이전트 회고) 의 결정론적 코드화.
// Retrospective workflow — deterministic codification of policy 8 (5+1 multi-agent retrospective).
//
// loop-until-dry 정본: .claude/workflows/_lib/loop-until-dry.template.mjs (인라인 복사 + 가드 테스트).
// cross-verify 강화: 모든 finding 이 verdict 를 받도록 강제 (verdict=finding) — 단일 패스 회고의
//   "13건 중 8건만 검증" 한계 해소.
// loop-until-dry canonical: _lib/loop-until-dry.template.mjs (inline copy + guard test).
// Cross-verify hardening: every finding must receive a verdict (verdict=finding) — fixes the
//   single-pass retro limitation where only 8 of 13 findings were verified.
export const meta = {
  name: 'retrospective',
  description: 'SCAManager 5+1 회고 — 다관점 finder loop-until-dry + 전건 cross-verify (verdict=finding 강제)',
  phases: [
    { title: 'Scope' },
    { title: 'Discover' },
    { title: 'Verify' },
    { title: 'Completeness' },
    { title: 'Report' },
  ],
}

// ── 회고 관점 도메인 (정책 8 — 비중복 5종) ──
// Retrospective perspective domains (policy 8 — 5 non-overlapping lenses)
const DEFAULT_DOMAINS = [
  { id: 'process', focus: '정책 준수·협업 흐름·사이클 종료 신호 / policy compliance, collaboration flow, cycle-close signals' },
  { id: 'code', focus: '코드 품질·회귀·테스트 커버리지·시간차 결함 / code quality, regressions, coverage, time-lag defects' },
  { id: 'docs', focus: '문서 정합·drift·STATE/README 동기화 / doc consistency, drift, STATE/README sync' },
  { id: 'decision', focus: '의사결정 추적성·위임 경계·자율 판단 보고 / decision traceability, delegation, autonomy reporting' },
  { id: 'tooling', focus: '도구·자동화·워크플로우·훅 ROI / tooling, automation, workflows, hook ROI' },
]

// ── 순수 헬퍼 ────────────────────────────────────────────
// Pure helpers

// args 는 객체 또는 JSON 문자열로 도달할 수 있음 — 정규화.
// args may arrive as an object or a JSON string — normalize to an object.
function parseArgs(a) {
  if (typeof a === 'string') {
    try { return JSON.parse(a) } catch { return {} }
  }
  return a ?? {}
}

// finding 정규화 키 — 중복 제거용 (관점 + 위치 + 제목, 대소문자·공백 정규화).
// 프로세스/의사결정 finding 은 file:line 이 없을 수 있어 위치는 선택적.
// Normalized finding key for dedup (domain + location + title; location optional for process findings).
function key(f) {
  const loc = f.file ? `${String(f.file).toLowerCase().trim()}:${f.line ?? ''}` : ''
  return `${String(f.domain).toLowerCase().trim()}|${loc}|${String(f.title).toLowerCase().trim().replace(/\s+/g, ' ')}`
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

// 심각도별 카운트 (SEVERITY_ADJUST 시 조정된 심각도 우선).
// Count by severity (prefer adjusted severity when SEVERITY_ADJUST).
function count(findings, sev) {
  return findings.filter((f) => (f.adjusted_severity ?? f.severity) === sev).length
}

// ── 구조화 스키마 (StructuredOutput 강제 — 파싱 0) ──
// Structured output schemas

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
          file: { type: 'string' },   // 선택 — 프로세스/의사결정 finding 은 N/A / optional
          line: { type: 'integer' },  // 선택 / optional
          claim: { type: 'string' },
          evidence: { type: 'string' },
          recommendation: { type: 'string' },
        },
        required: ['domain', 'severity', 'title', 'claim'],
      },
    },
  },
  required: ['findings'],
}

// cross-verify verdict — 모든 finding 이 받아야 함 (verdict=finding 강제).
// Cross-verify verdict — every finding must receive one (verdict=finding enforcement).
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'FALSE_POSITIVE', 'SEVERITY_ADJUST'] },
    adjusted_severity: { type: 'string', enum: ['P0', 'P1', 'P2'] },
    reason: { type: 'string' },
    citation_verified: { type: 'boolean' },
  },
  required: ['verdict', 'reason'],
}

// completeness critic 가 식별한 미검증 영역(gap) 목록 스키마.
// Gap list schema — uncovered areas surfaced by the completeness critic.
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

function finderPrompt(domain, context, round) {
  return [
    `당신은 SCAManager 회고 분석관입니다. 관점 "${domain.id}" 로 직전 작업/사이클을 회고합니다.`,
    `회고 초점: ${domain.focus}`,
    context ? `세션 컨텍스트: ${context}` : '',
    round > 1 ? '이전 라운드에서 이미 보고된 항목은 제외하고, 더 깊은/놓친 항목만 보고하세요.' : '',
    '각 항목은 P0(운영 사고/정책 위반)/P1(정합성·프로세스 결함)/P2(개선 기회) 로 분류.',
    '🔴 정책 6: 코드/문서 인용 시 file:line 을 `grep -n` 실측 후 작성(추정 금지). 프로세스 항목은 사용자 발화·커밋·PR 을 인용.',
    'self-contained: 다른 에이전트 결과에 의존하지 말 것 (병렬성 보호).',
    'false-positive 회피: 추측·취향이 아닌 실제 영향·근거 있는 항목만. findings 배열 반환(없으면 빈 배열).',
  ].filter(Boolean).join('\n')
}

function verifyPrompt(f, context) {
  return [
    '당신은 회고 cross-verify 검증관입니다 (5+1 의 +1 역할). 기본 입장은 회의적입니다.',
    `주장된 항목: [${f.severity}] ${f.title} (관점 ${f.domain})` + (f.file ? ` @ ${f.file}:${f.line ?? ''}` : ''),
    `근거: ${f.claim}` + (f.evidence ? ` / 증거: ${f.evidence}` : ''),
    context ? `세션 컨텍스트: ${context}` : '',
    '판정 의무: CONFIRMED(실제 결함/개선) / FALSE_POSITIVE(근거 부족·추측·이미 해소) / SEVERITY_ADJUST(실제이나 심각도 조정 — adjusted_severity 명시).',
    '인용된 file:line 이 있으면 grep 으로 존재 재확인 후 citation_verified 에 반영.',
    '반드시 verdict 1건 반환 — 모든 finding 은 검증받아야 함 (verdict=finding 강제).',
  ].filter(Boolean).join('\n')
}

// completeness 비평가 — 5+1 의 +1 cross-verify 역할 (미검증 관점/양식 식별).
// Completeness critic — the +1 of the 5+1 pattern (surface uncovered perspectives/modalities).
function completenessPrompt(domains, verified, scope) {
  return [
    '당신은 회고 완전성 비평가입니다 (5+1 의 +1 역할).',
    `회고 scope: ${scope}. 커버된 관점: ${domains.map((d) => d.id).join(', ')}.`,
    `현재까지 검증된 항목 ${verified.length}건.`,
    '다음 미검증 영역을 식별하라:',
    '(a) 깊이 점검 안 된 관점',
    '(b) 미검증 양식 — 정책 cross-reference 누락, 시간차 누적 결함, 메모리/docs drift, 회귀 가드 부재 등',
    '각 gap 은 {domain, modality, why}. 진짜 누락만 — 추측 금지. 없으면 빈 배열.',
  ].join('\n')
}

function gapFinderPrompt(gap, context) {
  return [
    '당신은 표적 회고 분석관입니다. 다음 gap 을 집중 회고하세요:',
    `관점: ${gap.domain} / 미검증 양식: ${gap.modality} / 사유: ${gap.why}`,
    context ? `세션 컨텍스트: ${context}` : '',
    '🔴 정책 6: file:line 인용 시 `grep -n` 실측. findings 배열 반환(없으면 빈 배열).',
  ].filter(Boolean).join('\n')
}

// finding 1건을 cross-verify — 고동시성 StructuredOutput 누락(flake) 대비 최대 3회 재시도.
// 재시도 소진 시 UNVERIFIED 로 명시 표기(조용한 누락 방지 — 13/8 한계 해소).
// Cross-verify one finding — up to 3 retries for high-concurrency StructuredOutput misses.
// On exhaustion, mark UNVERIFIED explicitly (avoid silent gaps — fixes the 13/8 limitation).
async function crossVerify(f, context) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const v = await agent(verifyPrompt(f, context), {
        label: `verify:${f.domain}:${String(f.title).slice(0, 24)}${attempt ? `:retry${attempt}` : ''}`,
        phase: 'Verify', schema: VERDICT_SCHEMA,
      })
      if (v && v.verdict) return { ...f, ...v }
    } catch {
      // StructuredOutput 누락/오류 — 재시도로 넘어감 / missed StructuredOutput — fall through to retry
    }
  }
  return { ...f, verdict: 'UNVERIFIED', reason: 'verdict 미수신 (재시도 소진) / no verdict after retries' }
}

// fresh finding 전건을 소배치로 순차 cross-verify — 고동시성 StructuredOutput 누락 차단.
// Cross-verify every fresh finding in small sequential batches — avoids high-concurrency misses.
async function verifyAll(fresh, context) {
  const BATCH = 6
  const out = []
  for (let i = 0; i < fresh.length; i += BATCH) {
    const chunk = fresh.slice(i, i + BATCH)
    out.push(...(await parallel(chunk.map((f) => () => crossVerify(f, context)))).filter(Boolean))
  }
  return out
}

// ── 오케스트레이션 ──
// Orchestration
const opts = parseArgs(args)
const scope = opts.scope ?? 'session'
const context = opts.context ?? opts.mergeCommits ?? null
const dryRun = opts.dryRun === true
const domains = Array.isArray(opts.domains) && opts.domains.length
  ? DEFAULT_DOMAINS.filter((d) => opts.domains.includes(d.id))
  : DEFAULT_DOMAINS

phase('Scope')
log(`회고 scope=${scope} → 관점 [${domains.map((d) => d.id).join(', ')}]` + (context ? ` / 컨텍스트 有` : ''))

if (dryRun) {
  return { scope, dryRun: true, domains: domains.map((d) => d.id), context }
}

// ── loop-until-dry — 정본 파라미터 (정본: _lib/loop-until-dry.template.mjs) ──
// 🔴 정본 값과 동일 유지 의무 — drift 는 tests/unit/scripts/test_workflow_loop_sync.py 가드 차단.
// Canonical params — must match _lib/loop-until-dry.template.mjs (drift blocked by the guard test).
const DRY_THRESHOLD = 2            // 연속 신규-0 라운드 N회 시 종료 / stop after N consecutive dry rounds
const MAX_ROUNDS_WITH_BUDGET = 5   // budget 설정 시 라운드 상한 / round cap with budget
const MAX_ROUNDS_NO_BUDGET = 3     // budget 미설정 시 보수적 상한 / conservative cap without budget
const BUDGET_FLOOR = 60_000        // 잔여 budget 하한 / remaining-budget floor

// seen = 발견된 모든 finding 키 (재출현·무한루프 차단) / every surfaced finding key (blocks re-emergence/infinite loop)
const seen = new Set()
// verified = verdict 를 받은 모든 finding (CONFIRMED/FP/SEVERITY_ADJUST/UNVERIFIED) / all findings that got a verdict
const verified = []
let dry = 0
let round = 0
const MAX_ROUNDS = budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET

phase('Discover')
while (dry < DRY_THRESHOLD && round < MAX_ROUNDS && (!budget.total || budget.remaining() > BUDGET_FLOOR)) {
  round++
  const found = (await parallel(domains.map((d) => () =>
    agent(finderPrompt(d, context, round), { label: `retro:${d.id}:r${round}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? [])

  const fresh = found.filter((f) => !seen.has(key(f)))
  if (!fresh.length) { dry++; log(`라운드 ${round}: 신규 0 (dry ${dry}/${DRY_THRESHOLD})`); continue }
  dry = 0
  fresh.forEach((f) => seen.add(key(f)))
  log(`라운드 ${round}: 신규 ${fresh.length}건 → cross-verify`)

  verified.push(...(await verifyAll(fresh, context)))
}

// ── completeness critic + 표적 gap 라운드 ──
// Completeness critic + targeted gap round
phase('Completeness')
const gaps = await agent(completenessPrompt(domains, verified, scope), { label: 'completeness', phase: 'Completeness', schema: GAPS_SCHEMA })
if (gaps?.items?.length) {
  log(`completeness: gap ${gaps.items.length}건 → 표적 라운드`)
  const gapFound = (await parallel(gaps.items.map((g) => () =>
    agent(gapFinderPrompt(g, context), { label: `gap:${g.domain}`, phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap((r) => r.findings ?? []).filter((f) => !seen.has(key(f)))
  gapFound.forEach((f) => seen.add(key(f)))
  if (gapFound.length) verified.push(...(await verifyAll(gapFound, context)))
}

// ── Report (구조화 데이터 반환 — 리포트 파일 작성은 호출자/스킬 책임) ──
// Report (returns structured data — writing the report file is the caller/skill's job)
phase('Report')
const all = dedupe(verified)
const confirmed = all.filter((v) => v.verdict === 'CONFIRMED' || v.verdict === 'SEVERITY_ADJUST')
const falsePositives = all.filter((v) => v.verdict === 'FALSE_POSITIVE')
const unverified = all.filter((v) => v.verdict === 'UNVERIFIED')
// verdict 커버리지 = 검증받은 / 전체 (1.0 == 모든 finding 검증됨 — 13/8 한계 해소 지표).
// Verdict coverage = verified / total (1.0 == every finding verified — the 13/8-limitation metric).
const coverage = all.length ? (all.length - unverified.length) / all.length : 1
log(`종료: 라운드 ${round} / finding ${all.length} / confirmed ${confirmed.length} / fp ${falsePositives.length}` +
    ` / unverified ${unverified.length} / verdict 커버리지 ${(coverage * 100).toFixed(0)}%`)
return {
  scope,
  rounds: round,
  findings_total: all.length,
  verdict_coverage: coverage,
  confirmed: confirmed.map((f) => ({
    domain: f.domain, severity: f.adjusted_severity ?? f.severity, title: f.title,
    file: f.file ?? null, line: f.line ?? null, claim: f.claim,
    recommendation: f.recommendation ?? null, verdict: f.verdict, reason: f.reason,
  })),
  unverified_findings: unverified.map((f) => ({ domain: f.domain, severity: f.severity, title: f.title })),
  roi: {
    fp_blocked: falsePositives.length,
    confirmed: confirmed.length,
    severity_adjusted: all.filter((v) => v.verdict === 'SEVERITY_ADJUST').length,
    p0: count(confirmed, 'P0'),
    p1: count(confirmed, 'P1'),
    p2: count(confirmed, 'P2'),
  },
}
