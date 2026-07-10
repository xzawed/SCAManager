# repo-automation 강화 설계 — 신규 훅 3 · 신규 스킬 3 · 워크플로우 loop-engineering

> ⛔ **정책 18 (Claude ↔ Codex mutual 검증) 은 2026-07-10 폐기되었다** — 사용자가 Codex 구독을 해지해 `codex` 실행 파일이 없다.
> **본 문서에 남아 있는 "Codex 검증 의뢰 / Codex OK 후 push" 류 단계는 수행하지 않는다** (완료된 작업의 역사 기록).  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*
> 대체: Claude 단독 2-layer (정책 8 5+1 + `pipeline-reviewer` / opus whole-branch 적대 리뷰). push 전 게이트 = `pytest tests/unit` 전체 통과.

> **상태**: ✅ 완료 (PR-H #969 훅 · PR-W #974 워크플로우 · PR-S #975 스킬 전량 머지, 2026-06-23). 회고 follow-up = `fix/retrospective-followup-hardening`.
> **출처**: 2026-06-23 정밀 감사 세션 5+1 회고 도구 관점(WF) + 사용자 합의
> **구현**: 3 PR (PR-H 훅 → PR-W 워크플로우 → PR-S 스킬), 각자 TDD + Codex mutual + docs sync. 운영 가이드: [`docs/runbooks/retrospective.md`](../runbooks/retrospective.md) · [`docs/runbooks/integrity-audit.md`](../runbooks/integrity-audit.md).  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*

---

## 1. 목적 / 배경

2026-06-23 세션(#962~#968)의 5+1 회고가 식별한 **반복 수작업·반복 drift 사고**를 turn-0(pre-commit) 또는 재사용 스킬/워크플로우로 자동화한다. 이미 #968에서 docs-sync/toc-anchor/memory-refs 3 훅을 wiring했고, 본 설계는 그 위에 **훅 3종 추가 + 스킬 3종 추가 + 워크플로우 loop-engineering**을 더한다.

**성공 기준**: (a) 신규 훅이 현재 repo를 통과(dogfooding)하며 합성 위반은 차단, (b) 신규 스킬이 정책(8/10/18) 흐름을 결정론화, (c) 워크플로우 loop-until-dry가 단일 출처화되어 audit·회고가 공유.

---

## 2. 공통 원칙 (3 영역 일관)

- **stdlib 전용** + `Path(__file__).resolve().parents[1]` 루트 + Windows cp949 UTF-8 wrapper + `core(root)->(ok, msgs)` 테스트 가능 구조 (#968 / `scripts/check_memory_refs.py` 컨벤션 계승).
- 각 영역 **별도 PR** (정책 7 응집 단위 분할) — 각자 TDD + Codex mutual(정책 18) + STATE/cycle-history/README docs sync(6-step ⑤).  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*
- 신규 훅은 **모두 현재 repo 통과 의무**(dogfooding). 통과 못 하는 기존 위반 발견 시 = 그 자체가 fix 대상 또는 allowlist 등재(사유 명시).
- 신규 스킬은 `.claude/skills/*.md` 형식(기존 integrity-audit.md/lint.md/test.md 동형).
- 워크플로우는 `.claude/workflows/*.mjs`, 주입 글로벌(agent/parallel/phase/log/budget/args)만 사용(자체 import 0 — 단 Area 1 검증 게이트 참조).

---

## 3. Area 1 — 워크플로우 loop-engineering (PR-W)

### 3.1 현황 (실측)
`integrity-audit.mjs:266-294`는 **이미 loop-until-dry 구현**: `seen`-set(재출현/무한루프 차단) + dry-counter(K=2) + `MAX_ROUNDS`(budget 시 5/미설정 3) + budget floor(60k) + completeness-critic + 표적 gap 라운드. 반면 2026-06-23 세션의 회고는 **단일 패스 ad-hoc**로 실행돼 cross-verify가 13 finding 중 8만 검증한 한계가 있었다.

### 3.2 산출물 (3)

**(W1) 공유 loop-until-dry 패턴 단일 출처화**
- `integrity-audit.mjs`의 loop-until-dry 골격(seen-set + dry + budget cap + critic)을 추출.
- 🔴 **검증 게이트 (구현 1단계 실측)**: 워크플로우 스크립트가 sibling `.mjs`를 ES `import` 가능한가?
  - **가능** → `.claude/workflows/_lib/loop_until_dry.mjs` 실모듈로 추출, audit·retrospective가 import (진짜 DRY, 정책 16 단일출처).
  - **불가(샌드박스 제약)** → `.claude/workflows/_lib/loop-until-dry.template.mjs` 정본 스니펫 + 각 워크플로우 인라인 + **"인라인 패턴 == 정본 스니펫" 가드 테스트**(drift 방지로 단일출처 효과 대체).
  - 판정 근거를 PR-W 본문에 명시.

**(W2) integrity-audit.mjs 리팩터 + 튜닝**
- W1 공유 패턴 사용으로 전환(또는 정본 정합).
- 현재 하드코딩된 dry 임계 K(2)·`MAX_ROUNDS`(5/3)·budget floor(60k)를 스크립트 상단 상수로 파라미터화(가독성 + 향후 조정 용이).
- 행동 회귀 0 — 기존 dryRun 경로 및 출력 스키마 보존.

**(W3) 회고 워크플로우 신규** `.claude/workflows/retrospective.mjs`
- loop-until-dry 적용한 5+1(정책 8): N-관점 finder(프로세스/코드/문서/의사결정/도구 등 args로 도메인 주입)를 dry까지 루프 + completeness critic.
- 🔴 **cross-verify 강화**: verdict 개수 = finding 개수 강제(이번 세션 13/8 한계 해소) — 모든 finding이 CONFIRMED/FP/SEVERITY_ADJUST verdict를 받도록 보장.
- `args`로 세션 컨텍스트(머지 커밋·범위) 주입 받는 파라미터화.

### 3.3 테스트
워크플로우는 직접 단위 테스트 어려움 → (a) W1 불가-폴백 시 "인라인==정본" 가드 테스트, (b) `dryRun` 경로로 audit 스코프 산출 smoke, (c) 정본 스니펫의 핵심 불변식(seen dedup·dry 증가·budget guard) 문서화.

---

## 4. Area 2 — 신규 pre-commit 훅 3종 (PR-H)

`scripts/*.py`(stdlib) + `.pre-commit-config.yaml` Layer 1-D 추가. 각: 테스트 가능 core + 양방향 테스트(현재 repo 통과 + 합성 위반 차단) + 해당 파일 `files:` 필터 + `pass_filenames: false`.

### (H1) `scripts/check_env_vars_sync.py`
- **검사**: `src/config.py` `Settings` 클래스의 env 필드명 ↔ `docs/reference/env-vars.md` 테이블 등재 정합. 신규 환경변수 env-vars.md 미등재(사이클 82/119 Codex 반복 적발) 차단.
- **오탐 방지**: 내부 전용/비-env 필드는 스크립트 상단 `_INTERNAL_FIELDS` allowlist 제외. 매칭은 필드명→UPPER_CASE env 키.
- **files**: `^(src/config\.py|docs/reference/env-vars\.md)$`.
- **현재 통과 의무**: 미등재 발견 시 env-vars.md 보완 또는 allowlist 등재(사유).

### (H2) `scripts/check_bilingual_comments.py`
- **검사**: **staged diff의 신규 주석 라인**(추가된 `+` 라인 중 주석)이 한국어↔영어 병행(CLAUDE.md 이중언어 규칙) 위반인지 휴리스틱 탐지.
- **오탐 방지(보수적)**: (1) **변경 라인 한정**(전체 파일 X — pre-commit이 staged 파일/라인 전달), (2) `# TODO/FIXME/type: ignore/noqa/pylint:` 등 단어태그 예외, (3) **명백한 한글-only 주석 블록만** 플래그(영어 식별자/짧은 토큰 오탐 회피), (4) **pre-commit only**(CI 제외 — 휴리스틱이라 CI 차단 부적절).
- **files**: `\.py$` (src 한정 권장).
- 🔴 **리스크**: 휴리스틱 오탐 가능 → 보수적 판정으로 시작, 오탐 보고 시 즉시 완화. 첫 도입은 **경고형 검토**(차단 강도 낮게) 고려.

### (H3) `scripts/check_config_5way_sync.py`
- **검사**: RepoConfig ORM(`src/models/`) ↔ `RepoConfigData`(config_manager) ↔ `RepoConfigUpdate`(api/repos) ↔ settings 폼(`templates/settings.html` name=) ↔ PRESETS 필드 집합 일치. 알림 채널/필드 추가 시 NULL 덮어쓰기 운영 버그(api.md 5-way sync 반복) 차단.
- **오탐 방지**: 의도적 비대칭 필드(읽기전용/내부) allowlist 제외. HTML 폼 파싱은 `name="..."` 정규식 추출.
- 🔴 **리스크(fragile)**: HTML 폼 파싱 실패 시 해당 검사 skip(no-op) 보수 설계 — 5 정의처 중 파싱 가능한 것만 비교하되, 최소 ORM↔Data↔Update 3자는 견고.
- **files**: 5 정의처 경로 OR.

---

## 5. Area 3 — 신규 스킬 3종 (PR-S)

`.claude/skills/*.md` (기존 스킬 동형 — name/description frontmatter + 본문 절차).

### (S1) `.claude/skills/docs-sync.md`
- **역할**: PR# + 단위/전체 카운트 입력 → STATE 4갱신점(헤더 최신 블록·종합 수치·추적셀 시작 헤더·추적셀 항목) + cycle-history TOC/섹션(slug 자동 계산) + README.md/README.ko.md 배지 쌍 갱신 **체크리스트/가이드 렌더**.
- **페어**: `check_docs_sync`(검증) ↔ docs-sync 스킬(생성). 스킬이 생성, 훅이 commit-time 검증.

### (S2) `.claude/skills/retrospective.md`
- **역할**: Area 1의 `retrospective.mjs`(loop-until-dry) 호출을 codify — 정책 8 5+1 다중 에이전트 회고 결정론화. `integrity-audit.md` 스킬과 동형 구조(Workflow 호출 안내 + args 주입).
- **연계**: Area 1 W3와 페어(스킬=진입점, 워크플로우=실행).

### (S3) `.claude/skills/codex-verify.md`  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*
- **역할**: 정책 18 push 전 표준 흐름 codify — 브랜치 diff → Codex(codex-rescue) ground-truth 프롬프트(self-contained·직접 git show 지시·인라인 diff 길이 한도 회피) → OK 후 push / **Codex 다운 감지 시 자체검증 분기**(pylint+flake8+TDD RED→GREEN, 정책 18 예외).  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*

---

## 6. 구현 순서 / PR 분할

1. **PR-H (훅 3종)** — H1/H2/H3 + 테스트 + .pre-commit wiring + docs sync. 먼저(독립성 高).
2. **PR-S (스킬 3종)** — S1/S3 먼저(독립), S2(/retrospective)는 PR-W의 워크플로우 의존 → PR-W 후 또는 동시.
3. **PR-W (워크플로우 loop)** — W1 검증 게이트 → W2 리팩터 → W3 회고 워크플로우. S2와 페어.

> S2와 W3가 페어이므로 PR-W → PR-S 순서 또는 S2를 PR-W에 포함 가능(구현 plan에서 확정).

---

## 7. 리스크 / 미해결 결정 (plan/구현서 확정)

| 리스크 | 영향 영역 | 완화 |
|--------|----------|------|
| 워크플로우 sibling import 미지원 | W1 | 검증 게이트 → 정본 스니펫 + 인라인 가드 폴백 |
| 이중언어 주석 휴리스틱 오탐 | H2 | staged 라인 한정 + 보수 판정 + 경고형 시작 |
| 5-way HTML 폼 파싱 fragile | H3 | 파싱 실패 시 skip + 핵심 3자 견고 |
| scripts/ pylint 미게이트 | H1~3 | 기존 스크립트 컨벤션 정합(8.x 허용), src/ 게이트 무영향 |

---

## 8. 비-목표 (YAGNI)

- 훅의 CI 게이트 승격(현재 commit-time only) — 본 설계 범위 외(추후 별도 논의).
- WF-1 import-dup 훅 — 28 idiom으로 DROP 확정(#968 결정), 재도입 안 함.
- 회고 백로그 P2(NEW-GAP-1 .env.example footgun 등) — 별도 처리.
