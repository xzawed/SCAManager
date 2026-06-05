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
