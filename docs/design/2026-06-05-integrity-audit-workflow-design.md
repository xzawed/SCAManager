# 전체 정합성 감사 Workflow 설계
# Integrity Audit Workflow Design

> **작성일**: 2026-06-05
> **상태**: 구현 완료 — `.claude/workflows/integrity-audit.mjs` + `docs/runbooks/integrity-audit.md` runbook + CLAUDE.md `/integrity-audit` 참조 (운영 사용 중)
> **범위**: 다이나믹 워크플로우 적용 1단계 (개발/운영 프로세스 코드화) — 첫 워크플로우
> **상위 목표**: Claude 기능 극대화를 위한 분석·프로세스 고도화. 2개 하위 프로젝트로 분해됨:
>   1. **(본 문서)** 개발/운영 프로세스를 Workflow로 코드화·검증
>   2. (후속) 검증된 패턴을 SCAManager 제품 분석 파이프라인 고도화에 확장

---

## 1. 목적과 배경

### 1.1 문제

SCAManager는 매 사이클 **수동으로** 5+1 다중 에이전트 전수 감사(사이클 104, 109 등)를 돌린다.
- Claude가 매번 손으로 5~6개 에이전트를 디스패치 → 비결정적·재현 불가
- 관점 분리·중복 제거·adversarial verify·ROI 집계를 매번 즉흥 구성
- 정책 6(line:span 인용 의무)·정책 8(5+1 cross-verify)·정책 8 진화(ROI 정량)를 사람이 기억해 적용

### 1.2 해결

사이클 104/109의 수동 5+1 전수 감사를 **결정론적 Workflow 스크립트**로 코드화한다.
- 재사용 가능·재현 가능·세션 간 호출 가능
- 정책을 스크립트 구조에 내장 (인용 강제·다관점 verify·ROI 자동 집계)
- **read-only** — 검증된 P0/P1/P2 리포트만 생성. fix는 사용자가 정책대로 PR 결정

### 1.3 비목표 (YAGNI)

- ❌ 자동 코드 수정 / 자동 fix PR 생성 (정책 15 사전 사고 / 18 mutual / 12 destructive 승인과 충돌)
- ❌ tournament·self-repair 같은 과설계 하니스 (read-only 감사엔 불필요)
- ❌ 단일 거대 에이전트 1회 감사 (정책 6: 인용 없는 보고 false-positive 80%)

---

## 2. 아키텍처 접근법: B+C 결합

| 구성 요소 | 출처 | 역할 |
|----------|------|------|
| scope 인식 팬아웃 | C (하이브리드) | `full`/`diff`/`area`가 도메인 팬아웃 폭 결정 |
| loop-until-dry 탐색 | B (최대 심층) | K회 연속 새 결함 0까지 finder 라운드 반복 — 누적 결함 tail 포착 |
| 다관점 verify | B (최대 심층) | finding별 correctness/security/repro 3 렌즈 병렬 판정 |
| completeness critic | C (하이브리드) | 수렴 후 "미커버 도메인·미검증 modality" 식별 → gap 1라운드 추가 |
| 비용 상한 | C (하이브리드) | `MAX_ROUNDS` + `budget.remaining()` 가드로 B의 비결정 비용 통제 |

**핵심 통찰**: C가 B를 감싼다. B의 무한 탐색에 C의 라운드 상한·budget 가드를 부여해 "Claude 기능 극대화"와 "토큰 비용 통제(정책 16 #5)"를 동시 달성.

---

## 3. 호출 방법 (3-레이어)

| 레이어 | 형태 | 비고 |
|--------|------|------|
| 1. 저장형 Workflow | `.claude/workflows/integrity-audit.mjs` | 이름으로 호출, 세션 간 재사용 (1급 진입점) |
| 2. 얇은 스킬 래퍼 (선택) | `/integrity-audit [full\|diff\|area=<subsystem>]` | 발견성 ↑. 내부에서 Workflow 호출 |
| 3. 인라인 | "전체 감사 돌려줘" → Claude가 직접 Workflow 호출 | 임시 호출 |

> 사용자가 명시적으로 호출 = 정책 8 진화 (1)의 "단일 작업일 ≥5 에이전트 dispatch 사전 확인"에 대한 **명시적 동의**로 간주. 자동 트리거 아님.

### 3.1 scope 모드 (`args.scope`, 미지정 시 `full`)

| 모드 | 동작 | 도메인 팬아웃 |
|------|------|--------------|
| `full` (default) | src + docs + tests 전수 | 8 도메인 전부 |
| `diff` | `git diff main...HEAD` 변경 파일만 | 변경 파일이 닿는 도메인만 |
| `area=<name>` | 지정 서브시스템 (예: `area=gate`) | 해당 도메인 1개 + 인접 1개 |

---

## 4. 도메인 분해 (8 도메인)

`.claude/rules/` 8-area 매트릭스 + 정책 8 doc-audit 도메인 분리를 계승. 비중복.

| # | 도메인 | 매칭 경로 | 감사 초점 |
|---|--------|----------|----------|
| 1 | 파이프라인/분석 | `worker/pipeline.py`, `analyzer/**`, `scorer/**` | 멱등성·오류 처리·점수 정합 |
| 2 | Gate/머지 | `gate/**`, `services/merge_retry_service.py` | 재시도 terminality·임계값 단일출처 |
| 3 | 보안/인증 | `auth/**`, `crypto.py`, `shared/log_safety.py`, `webhook/validator.py` | SQLi·로그 인젝션·세션·HMAC |
| 4 | API/알림/웹훅 | `api/**`, `notifier/**`, `webhook/**`, `main.py` | SSRF·소유권 검증·디스패처 |
| 5 | DB/모델/마이그레이션 | `models/**`, `database.py`, `repositories/**`, `alembic/**` | ORM↔마이그레이션 drift·RLS·FK |
| 6 | UI/i18n | `templates/**`, `static/**`, `ui/**`, `i18n/**`, `middleware/locale.py` | XSS·hx-boost 핸들러 누적·번역 fallback |
| 7 | 문서 정합성 | `CLAUDE.md`, `docs/**`, `.claude/rules/**`, `STATE.md`, `architecture.md` | 수치·경로·선언↔현실 불일치 |
| 8 | 테스트/커버리지 | `tests/**`, `e2e/**`, `conftest.py`, fixture sync | dead assertion·fixture↔ORM sync |

### 4.1 검증 렌즈 3종 (B의 다관점 verify)

finding별 병렬 적용. 2/3 이상 `real=true` = 진짜 결함.

| 렌즈 | 질문 |
|------|------|
| `correctness` | 주장한 결함이 실제 동작을 파손하는가? |
| `security` | 실제 데이터/권한 노출·보안 영향이 있는가? |
| `repro` | 구체적 트리거 경로가 있는가? + 정책 6 `grep -n`으로 인용 `file:line` 실존 재확인 (`citation_verified`) |

---

## 5. 오케스트레이션 흐름 (5 단계)

```js
export const meta = {
  name: 'integrity-audit',
  description: 'SCAManager 전체 정합성 감사 — read-only P0/P1/P2 리포트',
  phases: [
    { title: 'Scope' },
    { title: 'Discover' },
    { title: 'Verify' },
    { title: 'Completeness' },
    { title: 'Report' },
  ],
}

// ── 1. Scope 해소 (순수 코드) ──────────────────────────
phase('Scope')
const scope = args?.scope ?? 'full'
const domains = resolveDomains(scope)        // full=8 / diff=변경파일 도메인 / area=1+1
const changed = scope === 'diff' ? await gitDiffFiles() : null

// ── 2. 발견 루프 (B: loop-until-dry, C: 라운드 상한) ───
const seen = new Set(), confirmed = []
let dry = 0, round = 0
const MAX_ROUNDS = budget.total ? 5 : 3      // 비용 상한 (budget 미설정 시 보수적 3)
while (dry < 2 && round < MAX_ROUNDS && (!budget.total || budget.remaining() > 60_000)) {
  round++
  // 도메인 감사관 병렬 — 각자 file:line 인용 의무 (정책 6)
  const found = (await parallel(domains.map(d => () =>
    agent(auditPrompt(d, changed, round), { phase: 'Discover', schema: FINDINGS_SCHEMA })
  ))).filter(Boolean).flatMap(r => r.findings)

  const fresh = found.filter(f => !seen.has(key(f)))    // dedup vs seen (순수 코드)
  if (!fresh.length) { dry++; continue }
  dry = 0; fresh.forEach(f => seen.add(key(f)))

  // ── 3. 다관점 verify (B: correctness/security/repro 3 렌즈) ──
  const judged = await parallel(fresh.map(f => () =>
    parallel(['correctness', 'security', 'repro'].map(lens => () =>
      agent(verifyPrompt(f, lens), { phase: 'Verify', schema: VERDICT_SCHEMA })))
      .then(vs => ({ ...f, real: vs.filter(Boolean).filter(v => v.real).length >= 2,
                          verdicts: vs }))))
  confirmed.push(...judged.filter(j => j.real))
}

// ── 4. Completeness critic (C: +1 = 6차 cross-verify 코드화) ──
phase('Completeness')
const gaps = await agent(completenessPrompt(domains, confirmed, scope), { schema: GAPS_SCHEMA })
if (gaps.items.length) {                              // gap 발견 시 1회 추가 라운드
  const gapFound = (await parallel(gaps.items.map(g => () =>
    agent(gapAuditPrompt(g), { phase: 'Discover', schema: FINDINGS_SCHEMA })))).filter(Boolean)
    .flatMap(r => r.findings).filter(f => !seen.has(key(f)))
  gapFound.forEach(f => seen.add(key(f)))
  const gapJudged = await parallel(gapFound.map(f => () =>
    parallel(['correctness', 'security', 'repro'].map(lens => () =>
      agent(verifyPrompt(f, lens), { phase: 'Verify', schema: VERDICT_SCHEMA })))
      .then(vs => ({ ...f, real: vs.filter(Boolean).filter(v => v.real).length >= 2, verdicts: vs }))))
  confirmed.push(...gapJudged.filter(j => j.real))
}

// ── 5. ROI 집계 + 리포트 (read-only 산출물) ────────────
phase('Report')
return {
  scope, rounds: round,
  confirmed: dedupe(confirmed),
  roi: {
    fp_blocked: seen.size - confirmed.length,   // verify에서 reject된 수
    new: confirmed.length,
    p0: count(confirmed, 'P0'), p1: count(confirmed, 'P1'), p2: count(confirmed, 'P2'),
  },
}
```

### 5.1 핵심 설계점

- **dedup은 `seen` 기준** (`confirmed` 아님) — verify에서 reject된 finding이 다음 라운드 재등장해 무한 반복하는 것 방지 (Workflow 문서의 수렴 함정 회피). gap 라운드 결과도 `seen`에 추가.
- **C가 B를 감쌈** — `MAX_ROUNDS` + `budget.remaining() > 60_000` 가드로 loop-until-dry에 상한 부여 → 비결정 비용 통제.
- **`parallel` 사용 이유** (pipeline 아님) — 라운드 내 dedup이 *모든* 도메인 결과를 필요로 하는 barrier. Workflow 문서의 "dedup across full result set" 정당 사례에 해당.
- **순수 헬퍼** (`resolveDomains`, `gitDiffFiles`, `key`, `dedupe`, `count`, `*Prompt`) — 스크립트 내 plain JS. `key(f)` = `${f.file}:${f.line}:${f.title}` 정규화 (대소문자·공백 정규화).

---

## 6. 구조화 스키마 (StructuredOutput 강제 — 파싱 0)

```js
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain:   { type: 'string' },
          severity: { type: 'string', enum: ['P0', 'P1', 'P2'] },
          title:    { type: 'string' },
          file:     { type: 'string' },
          line:     { type: 'integer' },
          claim:    { type: 'string' },   // 결함 주장 (1~2문장)
          evidence: { type: 'string' },   // grep -n 실측 근거
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
    real:               { type: 'boolean' },
    lens:               { type: 'string', enum: ['correctness', 'security', 'repro'] },
    reason:             { type: 'string' },
    citation_verified:  { type: 'boolean' },   // repro 렌즈: file:line 실존 grep 확인
  },
  required: ['real', 'lens', 'reason'],
}

const GAPS_SCHEMA = {
  type: 'object',
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain:   { type: 'string' },
          modality: { type: 'string' },   // 미검증 양식 (마이그레이션 drift / env-var 등재 / .claude/rules sync 등)
          why:      { type: 'string' },
        },
        required: ['domain', 'modality', 'why'],
      },
    },
  },
  required: ['items'],
}
```

### 6.1 정책 6 인용 강제

모든 감사관 프롬프트에 강제 조건 명시:
> "모든 `file:line`은 `grep -n` 실측 후 작성한다. 추정 line 번호 금지. evidence 필드에 실측 근거를 인용한다."

`repro` 렌즈가 `citation_verified`로 인용 `file:line` 실존을 재확인 → 환각 보고 80% 차단 (정책 6 검증치).

---

## 7. 리포트 산출물

**경로**: `docs/reports/YYYY-MM-DD-integrity-audit-<scope>.md` (워크플로우 반환값을 Claude가 메인 루프에서 작성 — Workflow 스크립트는 파일시스템 접근 불가)

**구조**:
1. **헤더** — scope · 라운드 수 · 총 소요 · ROI 집계 (정책 8 진화: `fp_blocked` N / `new` N / P0·P1·P2 카운트)
2. **본문** — 도메인별 confirmed finding 표: `severity · file:line · claim · 3-렌즈 verdict (✅/❌/✅)`
3. **푸터** — "🔍 사용자 검증 필요" 섹션 (정책 2) + 권장 fix 우선순위 (P0 먼저). fix는 사용자가 PR 결정.

> 산출물은 사이클 회고/감사 보고서와 동일한 `docs/reports/` 관례를 따른다.

---

## 8. 거버넌스 정합

| 정책 | 통합 방식 |
|------|----------|
| 6 (line:span 실측) | 감사관 프롬프트 강제 조건 + `repro` 렌즈 `citation_verified` 재확인 |
| 8 (5+1 cross-verify) | 본 Workflow가 5+1을 코드화 — 도메인 팬아웃 = 다수 관점, completeness critic = +1 |
| 8 진화 (ROI 정량) | 리포트 ROI 집계 자동 (`fp_blocked` / `new` / severity 카운트) |
| 15 / 18 (사전 사고·mutual) | read-only이므로 감사 자체는 면제. 후속 fix PR 단계에서 사용자가 적용 |
| 16 #5 (토큰 효율) | `MAX_ROUNDS` + `budget.remaining()` 가드 + scope 축소로 비용 상한 |
| 2 (사용자 검증 섹션) | 리포트 푸터 "🔍 사용자 검증 필요" 섹션 |

---

## 9. 검증 계획

이 Workflow가 실제 작동하는지 단계적 검증:

1. **`scope=diff` (회귀 가드)** — 현재 브랜치에 1회 dry run → 결함 0~소수 확인. 변경 파일 도메인 선택이 정확한지.
2. **`scope=area=gate` (단독 동작)** — gate 도메인 단독 + 인접 1개 팬아웃 확인.
3. **`scope=full` (골든 비교)** — 1회 전수 → 사이클 109 수동 감사가 찾은 P0(예: `database.py` RLS f-string SQL injection)과 같은 류를 재발견하는지 대조.
4. **리포트 정확성** — 출력 리포트의 `docs/reports/` 포맷·ROI 집계·file:line 인용 실존 확인.

> 골든 비교(3)는 워크플로우 품질의 핵심 회귀 가드. 수동 감사 대비 재현율을 정성 평가.

---

## 10. 후속 (2단계 — 본 spec 범위 외)

본 워크플로우 검증 후, 같은 B+C 패턴을 **SCAManager 제품 분석 파이프라인**(`run_analysis_pipeline`)에 확장:
- 현재 단일 `review_code()` (Claude AI 1회 호출) → 다관점/다라운드 리뷰로 고도화 검토
- 별도 spec → plan → 구현 사이클 (정책 7 PR 단위)

---

## 11. 미해결/결정 필요 (구현 계획 단계에서 확정)

- `MAX_ROUNDS` 정확값 (budget 설정 시 5 / 미설정 시 3 — 검증 단계에서 조정)
- 얇은 스킬 래퍼(`/integrity-audit`) 구현 여부 — 1차는 저장형 Workflow만, 발견성 필요 시 추가
- `area` 모드의 "인접 도메인" 매핑 테이블 정의
