<!-- guard-cue-quote: 실행 지시 어휘는 감사 증거로 인용된 것이며 이 문서 자체의 지시가 아니다. -->

> 🟢 **이 문서는 살아 있는 계획입니다** — `docs/_archive/` 의 시점 기록과 다릅니다.
> 진행 상태는 [`docs/runbooks/docs-consolidation-status.md`](docs-consolidation-status.md) 가 정본입니다.
> 🔴 착수 전 그 상태 문서를 먼저 읽으세요 — 이미 완료된 묶음을 다시 하지 않기 위해서입니다.

# SDD + TDD 문서·가드 정리 기획안 (2026-08-11)

> **한 문장 요약**: RRS 순위표는 실행 근거에서 **철회**한다(R2 = BROKEN). 이번 정리의 단위는 "문서"가 아니라 **"명제 + 그 명제의 집행자"** 이며, 11 묶음 · 12 PR 로 집행한다. 각 묶음은 SPEC → RED → GREEN → GUARD 4단이고, **red 를 못 만든 항목은 이 문서에서 기각**했다(실제로 2건 기각).

---

## 0. 이 기획안이 서 있는 지반

### 0.1 3라운드가 남긴 것

| 라운드 | 판정 | 이 계획에 미치는 효과 |
|---|---|---|
| R1 교정 | NEEDS_FIX | 축 재수집 없이는 순위 발행 불가 (C12) |
| R2 적대 | **BROKEN** | 🔴 **상위 15 작업지시서 무효 · 하위 26 처분 무효 · 중간 62 미탐 증명** → 순위 기반 조치 전면 철회 |
| R3 문서↔코드 | NEEDS_FIX | ✅ **이 계획의 실질 전부**. 내용에서 직접 유도된 14 결함, 전건 `file:line` |

**R3 D15 가 준 유일한 일반 법칙이 이 계획의 설계 원리다**:

> 불일치 14건 중 14건이 **집행자 없는 축**에 있었고, 집행자 있는 축의 불일치는 **0건**이었다.
> → 문서 품질은 저자의 성실도가 아니라 **그 축에 기계가 붙어 있는가**의 함수다.

따라서 이 계획은 문서를 고치는 계획이 아니라 **축마다 집행자를 붙이는 계획**이고, 문서 정정은 그 부산물이다. 순서도 항상 `가드 먼저 → 문서 나중`이다(R3 C12).

### 0.2 이 세션이 실행으로 재측정한 것 (재현 명령 포함)

전부 `F:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager` 에서 실행했다.

| # | 측정 | 결과 | 재현 |
|---|---|---|---|
| 1 | pylint (CI 핀) | **9.99/10** — 배지 10.00 거짓 확정 | `py -3.12 -m pylint src/` (pylint 4.0.6 · Python 3.12.10 = `requirements.txt:29` · `ci.yml:244` 핀) |
| 2 | pylint (로컬) | **9.99/10** — 동일 (pylint 3.3.1 · Py 3.14.2) | `py -3 -m pylint src/` |
| 3 | 게이트 예산 | CLAUDE 16,155/40,000=**0.4039** · AGENTS 10,807/12,000=**0.9006** · STATE 93,300/16,000=**5.8312** | `py -3 -c "from pathlib import Path; ..."` |
| 4 | `scripts/` 트리 갭 | 최상위 31 중 **8 미등재** + 서브디렉토리 2개 통째 미등재 | AST/문자열 대조 스크립트 |
| 5 | `.claude/` 등재 | `grep -c '\.claude' docs/architecture.md` → **0** | 동일 |
| 6 | 라우트 갭 | 고유 라우트 **49**, 3 문서 어디에도 없음 **9** | AST(`APIRouter(prefix)` × `@router.<verb>`) + `{param}` 정규화 |
| 7 | 실행형 계획 위험 | 후보 36(중복제거) · 현 배치 내 12(위반 0) · **배치 밖 배너없음 24** (실행어휘 14 / 임계-only 10) | `_EXECUTION_CUE`·`_DONE_MARKER` 를 `docs/**`+`.claude/**` 전역 적용 |
| 8 | SessionStart | **4종** (retro_cadence · owed_verification · check_main_red · check_precommit_installed) | `.claude/settings.json:6-30` |
| 9 | 러너 가드 상수 | repo-integrity **12** (`_INTEGRITY` 11 + `_INTEGRITY_WITH_ARGS` 1) · PR-diff **4** (`_DIFF_SCOPED` 3 + flake8) | `scripts/pre_push_gate.py:58-97` |
| 10 | 스케줄러 | `JOBS` **6종** (config.py:187 주석은 5종) | `src/scheduler.py:140-147` |

### 0.3 🔴 감사 보고서 자체를 반증한 것 — **기각 2건**

작성 규칙 1("red 를 못 만들면 기각")을 이 문서 자신에게 먼저 적용했다.

| 기각 항목 | 출처 | 반증 |
|---|---|---|
| **R3 D8 / C6** — `AGENTS.md:187` 이 `src/shared/**` 를 약속하는데 `services.md` frontmatter 에 없다 | R3 | **거짓.** `.claude/rules/services.md` frontmatter 에 `- "src/shared/**"` 가 **이미 있다**(2026-08-01 Grok `019fbd1e` 적발 후 추가, 주석까지 남아 있음). 역방향 가드를 지금 만들면 **red 가 0건**이다 → 명세가 아니다 → **기각** |
| **R2 C6** — "실행형 위험 **27건**" | R2 | **중복 계상.** `docs/_archive/superpowers ⊂ docs/_archive` 를 두 배치로 세어 7건이 중복됐다. 중복 제거 실측 = **24건**. 게다가 24 중 **11건이 오탐**(아래 0.4) → 실 조치 대상 **13건** |

### 0.4 🔴 R2 C6 의 술어가 만드는 오탐 2종 (내가 실행으로 발견)

`_UNCHECKED_THRESHOLD ≥5` 축을 전역 확장하면 **살아 있는 운영 절차에 "실행하지 마라" 를 붙이게 된다**.

- **인용 오탐 1건** — `docs/cycle-history.md` 는 미체크 0인데 `cue=True` 다. 실제 매칭은 `:37` `:970` 의 *"brainstorming→writing-plans→**subagent-driven-development**"* 라는 **과거 흐름 서술**이다. (메모리 `feedback-prose-guard-both-ways`: 인용 면제 없는 산문 가드는 정정 기록을 막는다.)
- **살아있는 체크리스트 오탐 10건** — `.claude/policies/active.md`(11, 정책 11 4테마 시각 확인 목록) · `.claude/rules/db.md`(6) · `docs/runbooks/rls-role-separation.md`(7, RLS Phase 4 운영 게이트) · `docs/guides/operational-verification.md`(6) · `docs/integrations/external-quality-services.md`(7) · `docs/runbooks/_archive/sentry-activation.md`(5) 등.

→ **결론**: 전역 확장은 `cue` 축(실행 어휘 자기 발화)만 하고, `unchecked` 축은 계획 디렉토리에 묶어 둔다. (묶음 B)

### 0.5 이 세션이 **재확인하지 않은** 인용 (그대로 쓰지 않는다)

정직 표기 — 아래는 R1/R2/R3 의 주장이며 내가 실행으로 다시 재지 않았다. 계획에서는 **가드가 파생하도록** 설계하고, 산문 수치로는 발행하지 않는다.

- `ci.yml` repo-integrity job 의 스텝 수 8(PR)/6(main push) — R3 D1
- `doc_review_gate` `_CRITICAL`/`_IMPORTANT` AST 적용 시 99/199 문서 심의 대상 — R2 D5
- `code_consumers` 4 위음성 모드 · `consumer_files` 8-표본 절단 — R1 D2/D3
- 8-gram containment 중복률 · 세션 transcript 관측자 효과 — R2 D7/D2

---

## 1. SPEC-0 — 이 프로젝트에서 "정리" 의 정의

> **정리 = 문서가 주장하는 명제를, 기계가 검사 가능한 명제로 바꾸는 것.**

허용되는 처분은 3가지뿐이다.

1. **참으로 만든다** — 값이 틀렸으면 값을 고친다 (예: pylint 10.00 → 9.99)
2. **파생시킨다** — 같은 값이 N지점에 있으면 1지점에서 유도한다 (예: 가드 개수 9지점)
3. **삭제한다** — 검사 불가능한 주장은 문장을 지운다 (예: "13종" 이라는 숫자 자체)

**허용되지 않는 처분**: 파일 삭제 · 경로 이동 · 총량 축소. 근거는 §5.

---

## 2. 채점 — AR (Actionability Rank), 기계 계산 가능

RRS 는 **문서**를 채점했고 그래서 깨졌다(편집 1회로 26/26 처분이 소멸 — R2 D1). AR 은 **명제(묶음)** 를 채점한다.

```
AR = f × s × e × i

f (falsifiable)  ∈ {0, 1}   지금 이 리포에서 red 를 만들 수 있는가.  f=0 이면 항목 자체를 기각한다.
s (severity)     ∈ {1,2,3}  3 = 런타임 파손 또는 보안 노출 / 2 = 발행된 지시·기준이 틀려 잘못된 조치 유발 / 1 = 값 drift(독자 오도)
e (enforcement)  ∈ {1,2,3}  3 = 거짓 집행자(초록으로 거짓 보증) / 2 = 집행자 0 / 1 = 부분 집행
i (independence) ∈ {0.5, 1} 1 = 선행 묶음 없이 착수 / 0.5 = 선행 의존
```

🔴 **사람이 매기는 항목은 `s` 하나뿐이다.** 재현 절차를 고정한다 — `s=3`: 해당 조치를 실행하거나 해당 서술을 믿었을 때 **프로세스가 죽거나 시크릿이 노출**되는가(코드 경로로 증명). `s=2`: 그 문서가 **다른 행위자에게 지시**를 내리는가(작업지시서·게이트 기준·러너 커버리지). `s=1`: 나머지. `f`·`e`·`i` 는 전부 기계 판정이다.

| 묶음 | f | s | e | i | **AR** | 근거 |
|---|---|---|---|---|---|---|
| **B** 실행 오인 위험 | 1 | 3 | 3 | 1 | **9** | 현 가드가 12건 초록 = 거짓 집행자. 완료 계획 재실행 = 유일한 즉시 운영 사고 |
| **E** SESSION_SECRET | 1 | 3 | 2 | 1 | **6** | 공개 기본 시크릿으로 기동 성공 경로 실재 |
| **J** 처분 지시 철회 | 1 | 3 | 2 | 1 | **6** | 발행된 지시 실행 시 `translate_comments.py` 런타임 파손 |
| **A** pylint 진리값 | 1 | 2 | 2 | 1 | **4** | 배지 = CI 기준의 근거. 집행자 0 |
| **D** 가드 개수 산문 | 1 | 2 | 2 | 1 | **4** | "13종 돌렸다" 는 잘못된 안심 |
| **F** 배선 서술 | 1 | 2 | 2 | 1 | **4** | Grok 은 auto-load 없음 → 열거 누락 = 규칙 도달 0 |
| **G** architecture SSOT | 1 | 2 | 2 | 1 | **4** | AGENTS.md:212 가 지정한 SSOT 가 비어 있음 |
| **C** 게이트 예산 | 1 | 2 | 3 | 0.5 | **3** | 거짓 집행자이나 A 선행 필요 |
| **H** 라우트 문서 | 1 | 1 | 2 | 1 | **2** | 값 drift |
| **I** 봉인 함정·주석 | 1 | 1 | 2 | 1 | **2** | 없는 위험을 피하게 함 |
| **K** 데이터셋 v2 | 1 | 2 | 2 | 0.5 | **2** | 조건부 — §6 결정 5 |
| ~~R3 C6 shared 매핑~~ | **0** | — | — | — | **기각** | red 0건 (§0.3) |
| ~~R2 처분 밴드 26건~~ | **0** | — | — | — | **기각** | 편집 1회로 소멸 (R2 D1) |

---

## 3. 묶음 = PR

각 묶음은 **독립 PR** 이다. 브랜치 접두는 정책 7 을 따른다.

---

### PR-1 · 묶음 B — 실행 오인 위험 (AR 9)
`fix/plan-execution-cue-global`

**SPEC**
> 실행 지시 어휘(`executing-plans|subagent-driven-development|task-by-task|REQUIRED SUB-SKILL`)를 **자기 문장으로** 담은 문서는 리포 어디에 있든 최상단에 do-not-execute 표지(`실행 대상이 아닙니다|do not execute`)를 가진다. 인용은 면제되며, 면제는 명시 마커로만 성립한다.

**RED — 지금 왜 실패하는가 (실측)**
- 현 스캐너 `tests/unit/scripts/test_plans_are_not_executable.py:47` 의 `for base in (".claude/plans", "docs/design")` → **2 배치만** rglob. 그 안에서 12건 발견, 위반 **0** → **green**.
- 같은 술어를 `docs/**` + `.claude/**` 전역 적용(중복제거): 후보 **36**, 배치 밖 배너 없음 **24**.
- 그중 `cue=True` **14**, `unchecked≥5`-only **10**.
- 조치 대상 = 14 − `docs/cycle-history.md`(인용 오탐) = **13건 red**:

  | # | 문서 | 미체크 |
  |---|---|---|
  | 1 | `docs/_archive/superpowers/plans/2026-05-11-ui-redesign.md` | 87 |
  | 2 | `docs/_archive/superpowers/plans/2026-05-24-ai-issue-registration.md` | 62 |
  | 3 | `docs/superpowers/plans/2026-05-30-sprint-roadmap.md` | 45 |
  | 4 | `docs/_archive/2026-04-21-settings-redesign.md` | 44 |
  | 5 | `docs/_archive/superpowers/plans/2026-05-12-repo-insights.md` | 40 |
  | 6 | `docs/_archive/2026-04-26-doc-review-gate.md` | 39 |
  | 7 | `docs/_archive/2026-04-24-auto-merge-f3-advisor.md` | 35 |
  | 8 | `docs/_archive/2026-04-27-settings-ux-redesign.md` | 35 |
  | 9 | `docs/_archive/2026-04-21-cppcheck.md` | 34 |
  | 10 | `docs/superpowers/plans/2026-05-30-phase-e-gate-action-registry.md` | 29 |
  | 11 | `docs/_archive/superpowers/plans/2026-05-09-claude-codex-docs-setup.md` | 25 |
  | 12 | `docs/_archive/superpowers/plans/2026-05-20-multilang-insight-docs-sync.md` | 20 |
  | 13 | `docs/_archive/2026-04-20-railway-deploy-failure-issue.md` | 0 (어휘만) |

**GREEN — 최소 변경**
1. 술어를 2축으로 분리: `cue` 축 = 전역 강제 / `unchecked≥5` 축 = `.claude/plans`·`docs/design` 유지.
2. `cue` 매칭 시 **코드펜스·인용부호 내부는 제외**, 잔여 예외는 `<!-- guard-cue-quote: <사유> -->` 마커로만. `docs/cycle-history.md` 에 마커 1줄.
3. 13 문서 최상단에 표지 1줄(🔴 **이 문서는 실행 대상이 아닙니다** — 완료된 기록).

**GUARD**
- `tests/unit/scripts/test_plans_are_not_executable.py`
  - `test_the_scan_finds_plan_documents` 하한을 **≥30** 으로 상향 (anti-vacuity — 스캐너가 조용히 좁아지면 fail)
  - `test_cue_axis_is_global` (전역 배치)
  - `test_quotation_is_exempt_only_with_marker` — `cycle-history` 는 green, **마커를 제거하면 red** (뮤테이션)
  - `test_unchecked_axis_stays_in_plan_dirs` — 술어 전역 확장 시 `active.md`·`rls-role-separation.md` 가 red 가 되면 fail (오탐 회귀 가드)
- **배선**: 이미 `tests/unit` → CI `test-and-analyze` + `pre_push_gate --full`

**위험도**: Medium (자율 + 보고) — 문서 상단 1줄 추가 + 테스트 범위 확장
**롤백**: 13 배너 revert + `_plan_docs()` 배치 튜플 1줄 revert
**순서 의존**: 없음. 다른 묶음과 파일 충돌 없음(STATE·README 미접촉)

---

### PR-2 · 묶음 J — 처분 지시 철회 + 원장 등재 (AR 6)
`docs/withdraw-disposal-orders`

**SPEC**
> 이 세션의 발행물은 **경로 이동·삭제를 지시하지 않는다.** 이미 발행된 처분 지시는 철회 기록과 함께 무효화된다.

**RED**
- `scripts/i18n_comments/glossary.md` 가 RRS 에서 `D-아카이브후보`(#177) 처분 지시를 받았다. 실측 소비자 2:
  - `scripts/i18n_comments/translate_comments.py:48` — `GLOSSARY_PATH = BASE_DIR / "scripts" / "i18n_comments" / "glossary.md"` (**세그먼트 조립** → 경로 리터럴 grep 위음성)
  - `.claude/hooks/doc_review_gate.py:67` — `r"^scripts/i18n_comments/glossary\.md$"` (**앵커 고정** → 이동 시 IMPORTANT 등급이 조용히 소멸)
- 즉 지시대로 이동하면 **런타임 파손 + 게이트 등급 silent 강등**. 직전 감사 전제3 직접 위반.

**GREEN**
- `docs/backlog.md` 에 신규 항목 등재:
  - **R75** RRS 순위 발행 금지 — edit-invariance·관측자 불변 검사 통과 전까지 순위는 근거가 아니다 (반증 수단: `band(p) == band(p|days=0)` 이 26/26 fail)
  - **R76** `glossary.md` 처분 지시 철회 + 소비자 2 근거
  - **R77** 소비자 탐지 4모드 미구현(경로 조립 · 정규식/glob · bare-basename · 디렉토리 glob) — 데이터셋 v2 선행 조건

**GUARD**
- `tests/unit/scripts/test_disposal_orders_are_grounded.py` (신규): 리포 내 어떤 문서도 `glossary.md` 처분을 지시하지 않는다 + **anti-vacuity** (`assert 스캔 대상 > 0`)
- 근본 가드는 묶음 K 에 속하므로 여기서는 **원장 기록이 산출물**이다. (정책 19 경계: backlog 저술은 Claude 소유 — Grok 위임 금지)

**위험도**: Low (즉시)
**롤백**: backlog 3행 revert
**순서 의존**: 없음

---

### PR-3 · 묶음 E — SESSION_SECRET 3분기 (AR 6)
`fix/session-secret-doc-parity`

**SPEC**
> `SESSION_SECRET` 의 실패 모드를 서술하는 모든 문서는 `src/config.py` 의 분기 구조와 **1:1** 로 대응한다.

**RED — 실측 코드 분기 (`src/config.py:240-261`)**
```
(1) 커스텀 값 ∧ len < 32                       → ValueError (기동 차단)
(2) 값 == "dev-secret-change-in-production"    → logger.warning 후 return v   ← 🔴 기동 성공
(3) is_production 판정 시 2층 가드 (main.py)    → RuntimeError
    is_production (config.py:278-280) = ENVIRONMENT=="production"  OR  app_base_url.startswith("https")
```
→ **ENVIRONMENT 미설정 ∧ APP_BASE_URL 미설정/http 인 배포는 공개된 기본 시크릿으로 기동에 성공한다.**

틀린 절대 단언 **3지점** (전부 "기동 실패" 로 단정):
- `CLAUDE.md:51` — *"32자 이상이 아니면 **기동 실패**(validator)"*
- `docs/reference/env-vars.md:12` — *"미충족 시 `config.py` `ValidationError` 앱 기동 오류"*
- `.claude/rules/security.md:27` — *"32자 미만이면 ValidationError 앱 기동 오류 (경고가 아닌 하드 실패)"*

🔴 **같은 파일 `.claude/rules/security.md:50` 은 정확하다** (커스텀값 조건 + RuntimeError 2층). **한 규칙 파일 안에서 :27 이 :50 을 반증한다.**

**GREEN**
- `:50` 을 정본으로 채택, `:27` 삭제 후 `:50` 참조로 통합. `CLAUDE.md:51`·`env-vars.md:12` 를 3분기 서술로 교체.
- `CLAUDE.md:52` 의 `APP_BASE_URL` 함정과 **결합 관계를 명시**한다 — 현재는 두 함정이 나란히 적혀 있으면서 하나가 다른 하나를 무력화한다는 사실이 빠져 있다.

**GUARD**
- `tests/unit/test_config.py::test_documented_session_secret_failure_modes`
  - 3 분기를 **실제로 실행**해 (1)(2)(3) 결과를 단언
  - 문서 3지점에서 `기동 실패|하드 실패|ValidationError 앱 기동 오류` 절대 단언이 남아 있으면 fail
  - **anti-vacuity**: 정규식이 아무것도 못 뽑으면 fail (`assert m is not None`)
- **배선**: `tests/unit` → CI + `pre_push_gate --full`

**위험도**: **문서 정정 = Medium** / **분기 (3) 유지 여부 = High (사용자 사전 확인 — §6 결정 3)**
**롤백**: 문서 3지점 revert + 테스트 삭제
**순서 의존**: 없음

---

### PR-4 · 묶음 A — pylint 진리값 (AR 4) 🔴 **묶음 C 의 선행**
`fix/pylint-badge-truth`

**SPEC**
> README.md · README.ko.md 배지, `docs/STATE.md` 2지점, `.github/workflows/ci.yml` 주석의 pylint 값은 **CI 핀 조합에서 `pylint src/` 가 실제로 내는 점수와 같고**, CI 의 `--fail-under` 는 그 값에서 파생된다.

**RED — 실측**
```
py -3.12 -m pylint src/   (pylint 4.0.6 / Python 3.12.10 = CI 핀)  → 9.99/10
py -3    -m pylint src/   (pylint 3.3.1 / Python 3.14.2 = 로컬)     → 9.99/10   (두 조합 동일)

잔여 3건:
  src/config.py:236          E1136 Value 'cls.model_fields' is unsubscriptable
  src/analyzer/io/ai_review.py:215  E1125 Missing mandatory keyword argument 'duration_ms'
  src/worker/pipeline.py:1   C0302 Too many lines in module (1089/1000)
```
**10.00 주장 5지점**: `README.md:23` 배지 · `README.ko.md:23` 배지 · `docs/STATE.md:23`(종합 수치) · `docs/STATE.md:35`(pylint 행) · `.github/workflows/ci.yml:251-252` 주석.
**집행자 0**: `scripts/check_docs_sync.py` 는 `_README_BADGE`(:41 Tests) 와 `_FASTAPI_BADGE`(:44) 만 본다 — pylint·Coverage·E2E 배지 축은 **검사 대상이 아니다**. CI 는 `ci.yml:254` `--fail-under=9.90` 만 강제하므로 9.99 는 초록이다.

**GREEN — 2안 (사용자 결정, §6 결정 1)**
- (a) ★ **배지·STATE·주석을 9.99 로 정정** — 즉시, 문서만 변경
- (b) 3 결함 해소해 10.00 회복 — `pipeline.py` 1089줄 분할 = 아키텍처 변경이므로 **이 계획 밖**(§5-9)

🔴 `E1125 missing-kwoa duration_ms` 는 **진짜 버그 후보**다(문서 문제가 아님). §6 결정 4 로 분리.

**GUARD**
- `scripts/check_docs_sync.py::check_lint_badge` (신규)
  - 2단계 ①: 5지점 **문서 간 동치** — 무의존, 즉시 실행 가능
  - 2단계 ②: `ci.yml` 의 `--fail-under` 를 **배지에서 파싱해 주입** (리터럴 `9.90` 하드코딩 폐기) → 배지가 10.00 이면 CI 가 10.00 을 강제하고, 못 지키면 **배지를 내리는 것이 유일한 통과 경로**가 된다. 산문이 게이트를 만족시킬 수 없다(AGENTS.md 불변식 1).
- **뮤테이션**: 배지 1지점을 임의 값으로 바꾸면 red / `check_lint_badge` 를 no-op 로 만들면 red
- **배선**: `pre_push_gate.py::_INTEGRITY`(이미 `check_docs_sync.py` 등재) + `ci.yml` repo-integrity job
- **동일 처리 대상 등재**: Coverage 97% · E2E 121 배지도 같은 무집행 상태 → 같은 함수에서 커버

**위험도**: **Medium** (문서 + 가드) / GREEN 선택 = **High (사전 확인)**
**롤백**: 5지점 revert + `check_lint_badge` 함수 삭제 + `ci.yml` 리터럴 복구
**순서 의존**: 🔴 **묶음 C 보다 반드시 먼저.** 이유는 아래.

> 🔴 **순서 의존의 근거 (직전 감사 확정 사항)**
> 묶음 C 는 게이트 예산 가드를 *"STATE 슬라이스가 배지가 주장하는 pylint **값**을 담는가"* 로 교체한다. 그런데 값이 **10.00 인 채로** 교체하면 두 지점이 서로 동치이므로 **가드가 초록으로 거짓을 보증**한다. 무집행 거짓보다 **집행된 거짓이 나쁘다**(메모리 `feedback-false-enforcer-is-worse-than-none`). 따라서 진리값 정정(A) → 예산 가드 교체(C) 순서는 선택이 아니라 **정확성 조건**이다.

---

### PR-5 · 묶음 C — 게이트 예산: 거짓 집행자 교체 (AR 3) 🔴 **PR-4 이후**
`fix/gate-budget-real-enforcer`

**SPEC 4건**
1. `_CONTEXT_SOURCES` 에서 '전문' 이라 주석된 원천은 실제로 예산 안에 들어온다.
2. 예산 대비 **85% 초과** 원천은 fail 한다 (절단은 silent·이산 실패이므로 임계 직전이 가장 위험).
3. 주석의 크기 리터럴은 존재하지 않는다 — 라벨에서 파생한다.
4. STATE 슬라이스는 **README 배지가 주장하는 pylint 값 문자열**을 포함한다.

**RED — 실측**
```
CLAUDE.md   16,155 / 40,000 = 0.4039     주석 ':661  # 27.8k — 전문'   → +72% 과대
AGENTS.md   10,807 / 12,000 = 0.9006 🔴  주석 ':662  # 5.3k  — 전문'   → 2배 과소, 여유 1,193자
STATE.md    93,300 / 16,000 = 5.8312     주석 ':670  # 91k'            → 오차 2.5%
```
**현행 집행자가 거짓이다** — `tests/unit/hooks/test_doc_review_gate.py` 의 `test_state_context_budget_reaches_the_aggregate_numbers` 마지막 단언이 `assert "pylint" in state_section` 이다. 이것은 **STATE 앞 16,000자 안에 `pylint` 라는 단어가 있으면 참**이다. 값이 무엇인지, 대조가 가능한지는 보지 않는다 — 직전 감사가 P0 로 확정한 *"예산가드가 산문으로 충족되는 거짓 집행자"* 가 바로 이 줄이다.
그리고 `CLAUDE/AGENTS` 의 '전문' 주장에 대한 `len(content) <= budget` 단언은 **존재하지 않는다**.

**GREEN**
- `doc_review_gate.py:661,662,670` 의 `# 27.8k` `# 5.3k` `# 91k` 리터럴 **삭제** (라벨은 이미 `load_context_parts()` 가 `f"(전문 {len(content)}자)"` 로 파생 중 — 주석만 복제였다).
- AGENTS.md 0.9006 처리는 **사용자 결정** (§6 결정 2): ★ **예산 12,000 → 16,000 상향** 권장.

**GUARD**
- `tests/unit/hooks/test_doc_review_gate.py`
  - `test_whole_sources_actually_fit` — '전문' 원천은 `len(read_text()) <= budget`
  - `test_whole_source_headroom_warns_at_85pct` — 0.85 초과 시 fail, 메시지에 실측 비율. **현재 AGENTS.md 0.9006 → 즉시 red**
  - `test_state_slice_carries_the_pylint_value` — `"pylint"` 지문 대신 **README 배지에서 파싱한 값 문자열**을 STATE 슬라이스에서 찾는다
  - **뮤테이션 의무**: STATE 예산을 4000 으로 되돌리면 red / 배지 값을 바꾸면 red / 위 3 테스트를 하나씩 제거하면 각각 red
- **배선**: `tests/unit/hooks` → CI + `pre_push_gate --full`

**위험도**: 🔴 **High (사전 확인)** — `_CONTEXT_SOURCES` 예산 변경은 **심의 에이전트의 입력 변경**이고, 그 에이전트는 모든 Write/Edit 를 차단할 수 있는 경로다. 부수 제약: `doc_review_gate.py:475`·`:533` 이 캐시 프리픽스 최소 길이 하한을 언급하므로 예산 **하향**은 별도 검토 필요(이 PR 은 상향만).
**롤백**: `_CONTEXT_SOURCES` 튜플 1줄 revert + 신규 테스트 3개 삭제
**순서 의존**: 🔴 **PR-4 머지 후에만 착수**

---

### PR-6 · 묶음 D — 가드 개수 산문 파생화 (AR 4)
`docs/derive-guard-counts`

**SPEC**
> 가드 개수를 말하는 산문은 존재하지 않거나, 러너 상수에서 파생된다.

**RED — 3원 불일치 (실측)**
```
러너 상수 (scripts/pre_push_gate.py:58-97)
  _INTEGRITY 11 + _INTEGRITY_WITH_ARGS 1 = repo-integrity 12
  _DIFF_SCOPED 3 + flake8 1              = PR-diff 4
러너 자신의 산문 (:12, :20-21)            = "repo-integrity 7종 · PR-diff 한정 4종"
문서 9지점                                = "9종 + 4종" 또는 "13종"
```
🔴 **같은 파일 안에서 상수(12)와 docstring(7)이 갈라져 있다.** 세 값 중 상수와 맞는 산문은 **0개**.

문서 9지점 (grep 실측): `CLAUDE.md:32`("13종") · `CLAUDE.md:146`("9종+4종", "13 가드") · `AGENTS.md:17`("9종+4종") · `AGENTS.md:23`("13 가드") · `README.md:437`("13 guards") · `README.md:438`("the 13 guards") · `README.ko.md:495`("13종") · `README.ko.md:496`("13 가드") · `.claude/rules/guards.md:208-209`("9종+4종") · `:210`("13 가드")

**GREEN**
- `pre_push_gate.py` 에 `guard_inventory() -> dict[str, int]` + `--count` 플래그 추가.
- 9지점의 숫자를 **삭제**하고 *"`py -3 scripts/pre_push_gate.py --count` 가 정본"* 으로 대체. docstring `:12,:20-21` 정정.

**GUARD**
- `tests/unit/scripts/test_guard_count_docs.py::test_prose_guard_counts_match_the_runner`
  - 9 문서 + docstring 에서 `(\d+)\s*(?:종|가드|guards)` 를 뽑아 `guard_inventory()` 와 대조
  - `ci.yml` 의 repo-integrity job 스텝을 **YAML 파싱**해 3원(러너 상수 · CI · 산문) 동치 단언 — 🔴 §0.5 의 미확인 인용(8/6)을 산문으로 쓰지 않고 **가드가 재게** 한다
  - **anti-vacuity**: 정규식이 0개를 뽑으면 fail (R2 D13 — 줄긁기 정규식이 조용히 1/3 로 축소된 실사고)
- **TDD 요구**: 현재 상태에서 **9지점 전부 red 로 시작**해야 한다. red 가 안 나오면 정규식이 잘못 뽑는 것이다.
- **배선**: `tests/unit/scripts` → CI + `pre_push_gate --full`

**위험도**: Medium
**롤백**: 문서 9지점 revert + `--count` 플래그 · 테스트 삭제
**순서 의존**: 없음. 🔴 단 `CLAUDE.md` 를 PR-7 과 공유 → PR-6 → PR-7 순으로 직렬화

---

### PR-7 · 묶음 F — 배선·인벤토리 서술 파생화 (AR 4)
`docs/derive-wiring-inventory`

**SPEC**
> 훅 배선과 규칙 인벤토리를 말하는 산문은 `.claude/settings.json` · 파일시스템에서 파생되거나, 그와 동치임이 기계로 검사된다.

**RED — 4지점 실측**

| 지점 | 문서 주장 | 실측 |
|---|---|---|
| `CLAUDE.md:135` | *"카운터 **2종**은 SessionStart 훅이 자동 실행"* | `.claude/settings.json:6-30` = **4종** (`check_main_red.py`·`check_precommit_installed.py` 추가) — 두 관측자가 **문서상 존재하지 않는다** |
| `CLAUDE.md:145` | *"`src/` 파일 편집 후 PostToolUse Hook"* | `posttool_pytest_smoke.py:39` `_WATCHED_ROOTS = ("src", "alembic", "scripts")` — 문서가 **과소** 서술. `.claude/hooks/**` 는 여전히 미감시(backlog R44-c) |
| `CLAUDE.md:178` | *"**10 카테고리**"* | `.claude/rules/*.md` = **11개**. 바로 아래 표는 **11행** — 자기 문단 내 불일치 |
| `AGENTS.md:202` | `{testing,db,pipeline,api,security,ui,i18n,deploy,services,guards}.md` | **`docs` 누락**. auto-load 없는 Grok 이 이 열거만 보면 문서·원장 규칙의 존재를 모른다. 같은 파일 `:186-198` 표에는 `docs.md` 행이 있어 **한 파일 안 두 목록이 갈린다** |

**GREEN**
- 4지점 정정. `CLAUDE.md:145` 는 *"`src`·`alembic`·`scripts` 편집 후"* 로 고치고, `.claude/hooks/**` 미감시를 **알려진 갭**으로 명시(backlog R44-c 링크) — 좁게 적어 갭을 숨기는 것이 현 상태다.
- `CLAUDE.md:178` 의 숫자를 삭제하고 *"`.claude/rules/*.md` 전체"* 로.

**GUARD**
- `tests/unit/scripts/test_session_start_wiring.py` 에 축 추가 — settings.json SessionStart 스크립트명 전수를 뽑아 **CLAUDE.md 본문이 전부 이름으로 언급**하는지 (현재 2건 미언급으로 red)
- 동일 파일에 `_WATCHED_ROOTS` ↔ CLAUDE.md 문장 대조
- `tests/unit/scripts/test_rules_and_index_coverage.py` 에 `test_agents_md_rule_enumeration_is_complete` — AGENTS.md `{...}` 열거 ↔ 실제 파일 stem 집합 **동치** (현재 `docs` 누락으로 red)
- **anti-vacuity 전건 필수**
- **배선**: `tests/unit/scripts` → CI + `pre_push_gate --full`

**위험도**: Medium
**롤백**: `CLAUDE.md` 4지점 + `AGENTS.md` 1지점 revert + 테스트 축 삭제
**순서 의존**: PR-6 이후 (CLAUDE.md 동일 파일)

---

### PR-8 · 묶음 G — architecture.md = 가드 배선 SSOT 의 집행면 (AR 4)
`fix/architecture-tree-sync-3axes`

**SPEC**
> `AGENTS.md:212` 가 `docs/architecture.md` 를 *"아키텍처·가드 배선"* SSOT 로 지정하므로, `.claude/{hooks,agents,skills,workflows}` 전수와 최상위 `scripts/` 전수는 그 문서에 등재된다. **약속을 지우거나 집행하거나 둘 중 하나여야 한다.**

**RED — 실측**
```
grep -c '\.claude' docs/architecture.md  →  0        🔴 문자열이 0회 등장
```
미등재 실물:
- **훅 4/4** — `block_credential_dump.py` · `check_edit_allowed.py` · `doc_review_gate.py` · `posttool_pytest_smoke.py` (전부 `.claude/settings.json` 에 PreToolUse/PostToolUse 로 배선됨)
- **에이전트 5/5** — `doc-consistency-reviewer` · `doc-impact-analyzer` · `doc-quality-reviewer` · `pipeline-reviewer` · `test-writer`. 앞 3개는 `doc_review_gate.py` 의 운영 본체(모든 Write/Edit 를 차단할 수 있는 경로)인데 **CLAUDE.md · AGENTS.md · README · architecture 어디에도 없다**
- **스킬 4/6** — `docs-sync` · `integrity-audit` · `retrospective` · `webhook-test` (`lint`·`test` 만 등재)
- **워크플로 3/3** — `integrity-audit.mjs` · `retrospective.mjs` · `_lib`
- **최상위 `scripts/` 8/31 미등재** — `check_claim_review_trace.py`(정책 19 집행면) · `check_e2e_scope.py` · `check_main_red.py` · `check_precommit_installed.py` · `check_red_budget.py` · `check_reverse_mutation.py` · `check_test_count_sync.py` · **`pre_push_gate.py`**(CLAUDE.md:32 가 "유일한 push 전 게이트" 로 처방하는 진입점)
- **서브디렉토리 2개 통째** — `scripts/dev/`(2 파일) · `scripts/i18n_comments/`(6 파일, `glossary.md` 포함)

집행자의 분해능 한계: `scripts/check_architecture_tree_sync.py:66-90` 은 `src/` 의 **패키지 디렉토리 + 최상위 모듈만** 대조한다. `scripts/`·`.claude/`·패키지 **내부** 모듈은 **재고 있지 않다** — "지켜지고 있다" 가 아니라 "안 재고 있다".

**GREEN**
- `docs/architecture.md` 에 **§가드·에이전트 배선** 신설 (훅 4 · 에이전트 5 · 스킬 6 · 워크플로 3 + 각 배선 지점)
- `scripts/` 트리에 8 항목 + 서브디렉토리 2개 보강

**GUARD**
- `scripts/check_architecture_tree_sync.py` 에 축 2개 추가:
  - (i) 최상위 `scripts/*.py` 전수 + 서브디렉토리
  - (ii) `.claude/{hooks,agents,skills,workflows}/*` 전수
  - (선택 iii) `src/**/*.py` 패키지 **내부** 모듈 — R3 D13(`src/shared/time_utils.py`·`src/cli/__main__.py` 누락)
- **TDD**: 확장 직후 **≈26건 red 로 시작**(8 스크립트 + 2 디렉토리 + 4 훅 + 5 에이전트 + 4 스킬 + 3 워크플로). **0건이면 매처가 공허**하다.
- **뮤테이션**: architecture.md 에서 임의 1항목 삭제 → red
- **배선**: `pre_push_gate.py::_INTEGRITY`(이미 등재) + `ci.yml` repo-integrity + pre-commit

**위험도**: Medium
**롤백**: architecture.md 섹션 삭제 + 가드 축 2개 revert
**순서 의존**: 없음. 단 PR-9 와 architecture.md 공유 → PR-8 → PR-9

---

### PR-9 · 묶음 H — 라우트↔문서 동기 가드 신설 (AR 2)
`feat/route-docs-sync-guard`

**SPEC**
> `src/**` 의 모든 라우트 경로는 `README.md` · `README.ko.md` · `docs/architecture.md` 중 **최소 1곳**에 등장한다.

**RED — 실측 (AST, `APIRouter(prefix=)` 결합, `{param}` 정규화)**
```
고유 라우트 49 · 세 문서 어디에도 없음 9
  /admin/operations · /admin/rls-audit · /admin/tenants
  /api/admin/operations · /api/admin/rls-audit · /api/admin/tenants
  /api/github/repos
  /api/users/me/preferred-language
  /repos/{}/analyses/{}/feedback
```
동기 가드 부재: env-vars 축에는 `check_env_vars_sync.py`, src 트리 축에는 `check_architecture_tree_sync.py` 가 있는데 **라우트 축만 없다**.

**GREEN**
- 9 라우트를 문서화. admin 계열 6종은 `docs/architecture.md` 가 적절(운영 전용).

**GUARD**
- `scripts/check_route_docs_sync.py` (신규)
  - 🔴 **AST 로 뽑는다** — 정규식 줄긁기 금지(R2 D13 실사고: 후행 쉼표 6줄 때문에 커버리지를 3배 과소평가)
  - `{param}` / `{param:path}` 정규화 규칙을 스크립트 안에 명시
  - 예외는 `# route-undocumented-ok: <사유>` 인라인 마커로만 허용하고 **계수해서 인쇄**
- **TDD**: 현재 9 라우트 red 로 시작
- **배선**: `pre_push_gate.py::_INTEGRITY` + `ci.yml` repo-integrity

**위험도**: Medium
**롤백**: 가드 파일 삭제 + `_INTEGRITY`·`ci.yml` 1줄씩 revert
**순서 의존**: PR-8 이후 (architecture.md)

---

### PR-10 · 묶음 I — 봉인된 함정 · 코드 주석 drift (AR 2)
`fix/stale-traps-and-comments`

**SPEC**
> `CLAUDE.md` §환경변수 "함정만 적는다" 블록의 각 줄은 **(a) 현재 재현 가능**하거나 **(b) 봉인 지점 `file:line`** 을 단다. 코드 주석의 개수 단언은 정본 상수와 일치한다.

**RED — 실측 3건**
1. `CLAUDE.md:53` — *"`CLAUDE_REVIEW_MODEL` 을 빈 값으로 두면 … 전부 `api_error`(#1289)"* → **이미 봉인됨**. `src/config.py:217-238` `_blank_model_falls_back_to_default`(field_validator, mode="before")가 공백/빈 문자열을 `cls.model_fields[info.field_name].default` 로 되돌린다.
   🔴 **같은 3줄 블록에서 오차가 양방향이다** — `:51` 은 라이브 구멍을 봉인됐다 하고(묶음 E), `:53` 은 봉인된 함정을 라이브라 한다. 독자는 **없는 위험을 피하느라 있는 위험을 지나친다**.
2. `src/config.py:187-188` 주석 — *"`SCHEDULER_DISABLED=1` 시 **5종** job 미기동 (retry-pending-merges·sweep-orphans·trend·retention-sweep·weekly-reports)"* → `src/scheduler.py:140-147` `JOBS` = **6종** (`scan-security` 누락). 문서(`env-vars.md:41`·`architecture.md:35`)는 6종으로 **맞다** — 이번 감사에서 유일하게 "문서가 맞고 코드 주석이 틀린" 방향.
3. `pre_push_gate.py` docstring `:12,:20-21` 자기모순 → 묶음 D 에서 처리(중복 회피).

**GREEN**
- `CLAUDE.md:53` 을 *"(#1289 — `src/config.py:217-238` `_blank_model_falls_back_to_default` 로 봉인됨)"* 로 정정
- `src/config.py:187` 주석 5종 → 6종 + `scan-security` 추가

**GUARD**
- `tests/unit/test_cron_scheduler_parity.py::test_kill_switch_comment_matches_job_count` — 주석에서 `(\d+)종` 을 뽑아 `len(JOBS)` 와 대조. 🔴 산문 grep 이므로 **anti-vacuity 필수** (`assert m is not None`)
- `tests/unit/scripts/test_claude_md_behavior_rules.py` 에 축 추가 — §환경변수 함정 블록의 각 🔴 줄이 (a) 재현 마커 또는 (b) `file:line` 봉인 링크를 갖는지
- **배선**: `tests/unit` → CI + `pre_push_gate --full`

**위험도**: Low (즉시)
**롤백**: 2지점 revert + 테스트 2개 삭제
**순서 의존**: PR-7 이후 (CLAUDE.md)

---

### PR-11 · trailing sync (필수 · 마지막)
`docs/trailing-sync-cleanup-cycle`

**왜 분리하는가**: PR-1~10 이 각각 테스트를 추가하므로 `docs/STATE.md §테스트 수 추적 이력` 과 README Tests 배지가 매 PR 바뀐다. CLAUDE.md 6-step ⑤ 배치-PR 분기(2026-07-09 rank6)에 따라 **per-PR ⑤ 는 commit body 에 delta 만 기록**하고 실갱신은 이 PR 로 이월한다.

🔴 **인접-라인 충돌 주의**: PR-4(묶음 A)가 `README.md:23` pylint 배지를, 이 PR 이 `README.md:21` Tests 배지를 건드린다. **#1048 이 정확히 이 형태로 충돌을 자초했다.** → PR-4 머지 **후**에 이 브랜치를 자른다.

**내용**: `docs/STATE.md §테스트 수 추적 이력` 맨 아래 한 줄 갱신 → `py -3 scripts/check_docs_sync.py --fix` 로 나머지 4지점 파생 + `docs/cycle-history.md` 사이클 이력 + `docs/architecture.md` 최종 확인.
**위험도**: Low
**롤백**: 전체 revert 가능(문서 전용)

---

### PR-12 · 묶음 K — 데이터셋 v2 (🔴 조건부 · 사용자 승인 시에만)
`feat/doc-metrics-v2-invariants`

이 묶음은 **정리가 아니라 계기 재제작**이다. §6 결정 5 로 분리한다.

**SPEC (전부 기계 검사)**
```
M1 edit-invariance     for p in DISPOSAL: band(p) == band(p | days_since_edit=0)      현재 26/26 fail
M2 observer-invariance band(p) 불변 when 감사 세션 제외 · when ss += 1                현재 17/17 fail
M3 소비자 4모드        경로 조립 · 정규식/glob(훅 소스 AST 파싱) · bare-basename · 디렉토리 glob
                       🔴 리터럴 소비자와 패턴 소비자를 분리 — 구조적 잠금은 리터럴만
M4 U 축 전수화         consumer_files 8-표본 절단 → enforcer_consumers 정수 축. 구간이 갈리면 M0
M5 자기선언 축 + 대조군 "5축 기계가 `grep -l ARCHIVED` 보다 나은 판정을 낸 건수" 를 발행 의무
M6 중복 containment    8-gram. ≥0.90 은 삭제가 아니라 '정본 지정 + 링크 대체'
M7 개별 뮤테이션       for g in [모든 술어·스위치]: assert band_changes(remove=g) >= 1
                       red 를 못 만드는 술어는 삭제하거나 (vacuous-on-corpus) 표기 의무
```

🔴 **이 묶음의 산출물은 순위표가 아니라 위 검사의 통과다.** M1~M7 통과 전에는 어떤 순위도 발행하지 않는다(R2 C12).

**위험도**: **High (사전 확인)** — 큰 작업이며, PR-1~10 과 달리 즉시 가치를 내지 않는다
**순서 의존**: PR-1~10 전부 이후

---

## 4. 순서 그래프

```
독립 착수 가능 (병렬 3):
  PR-1  B  실행 오인          AR 9   ─┐
  PR-2  J  처분 지시 철회      AR 6   ─┤  파일 충돌 없음
  PR-3  E  SESSION_SECRET     AR 6   ─┘

직렬 (진리값 → 집행자):
  PR-4  A  pylint 9.99        AR 4   ──▶  PR-5  C  게이트 예산   AR 3
                                             🔴 필수 순서: 값이 거짓인 채로
                                                가드를 붙이면 거짓이 봉인된다

직렬 (CLAUDE.md 공유):
  PR-6  D  가드 개수          AR 4   ──▶  PR-7  F  배선 서술    AR 4  ──▶  PR-10 I  봉인 함정  AR 2

직렬 (architecture.md 공유):
  PR-8  G  architecture SSOT  AR 4   ──▶  PR-9  H  라우트 가드  AR 2

마지막 (README 인접-라인 충돌 회피 — PR-4 머지 후 브랜치 컷):
  PR-11    trailing sync

조건부 (사용자 승인):
  PR-12 K  데이터셋 v2        AR 2
```

**총 PR 수: 11 (+조건부 1).** 최소 실행 가능 집합 = **PR-1 · PR-2 · PR-3** (AR 9/6/6, 전부 독립, 다른 무엇도 기다리지 않는다).

---

## 5. 🔴 하지 않을 것 (검토했으나 기각)

| # | 기각 항목 | 사유 |
|---|---|---|
| 1 | **문서 삭제·경로 이동 일체** | 직전 감사 전제3(소비자 grep 증명 없는 이동 금지) + R2 D6 실증(D-아카이브후보 9건 이동 시뮬 → **9/9 가 C-현상유지로 복귀** = 조치가 근거를 지운다) + `glossary.md` 런타임 파손 실측. **이번 계획에 이동·삭제는 0건이다.** |
| 2 | **총량·용량 절감 근거** | 전제1(게이트=세션비용 0.48%, 문서를 0자로 줄여도 97% 남는다). RRS 발행물의 밴드별 '자수' 컬럼도 같은 이유로 기각 — R2 D10 이 **심사 자신의 기준에 대한 자기면제**로 적발했다 |
| 3 | **RRS 상위 15 작업지시서 실행** | R2 D5 로 8/8 오탐. 특히 #1 `docs/runbooks/rls-role-separation.md` 는 **이미 완료된 절차**다 — `.claude/rules/db.md:30` *"✅ Phase 4 운영 전환 검증 완료 (2026-06-16, docs #920)"* · `docs/cycle-history.md:59` · `:1215` · `:1222`(잔여는 선택 심층검증뿐). "55일 stale" 은 위험이 아니라 **작업이 끝난 결과**다. #3 `.claude/rules/api.md` 는 `doc_review_gate` **CRITICAL** 등급 대상이다 |
| 4 | **`CLAUDE.md`/`AGENTS.md` 축소** | 정책 17(외부 권장 규격은 가이드라인 — 안정성과 충돌하면 거부) + `#1296` 실증(424→196줄 → Grok BROKEN, 행동 규칙 8건 소실) + R54 실증(5지점→1줄 파생이 틀린 값 하나를 4지점 자동 전파). **AGENTS.md 0.9006 은 축소가 아니라 예산 상향으로 푼다** |
| 5 | **`src/shared/**` 규칙 매핑 수정 (R3 C6)** | **red 0건** — `services.md` frontmatter 에 이미 있다(§0.3). 작성 규칙 1 에 따라 기각 |
| 6 | **E-삭제후보 17건 / D-아카이브후보 9건 처분** | R2 D3 — E 와 D 를 가르는 축이 `ss==0` 단 하나이고, 그 축의 93% 가 **trailing-whitespace 린터 출력·`ls`·`git status` 부수 등장**이다. 쌍둥이 문서가 이 노이즈로 갈린다(`auto-merge-f3-advisor.md`=E / `-design.md`=D). 근거 무효 |
| 7 | **`docs/design/brief/02,04,05` 100% 중복 즉시 정본화** | 중복 containment 축이 데이터셋에 없고, RRS 의 F8(계열 무결성)이 오히려 이 3건을 **보호**한다(R2 D7). 묶음 K(M6) 통과 후로 이월 — backlog 등재만 |
| 8 | **`_UNCHECKED_THRESHOLD` 축 전역 확장** | §0.4 실증 — 살아있는 운영 체크리스트 10건에 "실행하지 마라" 를 붙이게 된다. `cue` 축만 전역화한다 |
| 9 | **`src/worker/pipeline.py` 1089줄 분할** | 아키텍처 변경이지 문서 정리가 아니다. pylint C0302 해소는 §6 결정 1(b) 로 분리 |
| 10 | **접근 티어(T4 미접근 63건) 기반 정리** | R2 C11 — *"진짜 재해 문서는 T4 에 없다"*. 축은 '얼마나 읽혔나' 가 아니라 '무슨 사건이 나면 읽히나' 여야 하고, 그 축은 데이터셋에 없다 |

---

## 6. 잔여 사용자 결정 (정책 15 High tier — 사전 확인 의무)

| # | 결정 | 옵션 | 장점 | 단점 | 위험 | ★권장 |
|---|---|---|---|---|---|---|
| **1** | pylint 배지 | (a) 9.99 로 정정 | 즉시·문서만·PR-5 선행 조건 충족 | 배지가 내려감 | 없음 | ★ **(a)** |
| | | (b) 3결함 해소 후 10.00 | 숫자 회복 | `pipeline.py` 분할 = 아키텍처 변경, PR-5 를 무기한 대기시킴 | 문서 정리 PR 에 코드 리팩터가 섞임 | |
| **2** | AGENTS.md 예산 (현 0.9006) | (a) 12,000 → 16,000 상향 | 정책 17 정합. 문서 성장 여유 확보 | 심의 프롬프트 토큰 +5.2k | 캐시 프리픽스 하한 재확인 필요(`doc_review_gate.py:475,533`) | ★ **(a)** |
| | | (b) AGENTS.md 축소 | 예산 유지 | `#1296` 에서 순손실 실증 · 전제1 위반 | 가드 3-불변식 SSOT 소실 | |
| **3** | `SESSION_SECRET` 분기 (3) | (a) 경고-only 유지 + 문서만 정정 | dev 호환 보존 | 오설정 배포가 공개 시크릿으로 기동 | **UNVERIFIED**: 현 Railway 배포의 `ENVIRONMENT`/`APP_BASE_URL` 실태를 확인하지 않았다 | ★ **(a) + 실태 확인 후 재평가** |
| | | (b) 비-prod 도 차단 | 구멍 봉쇄 | 로컬 dev 기동 절차 변경 | 기존 개발 환경 파손 가능 | |
| **4** | `E1125 missing-kwoa duration_ms` (`ai_review.py:215`) | 진짜 버그 조사 착수 여부 | 코드 결함일 가능성 | 별도 PR 필요 | 리뷰 지연 계측이 조용히 누락 중일 수 있음 | ★ **착수 (별도 PR, 이 계획 밖)** |
| **5** | 묶음 K (데이터셋 v2) | (a) 보류 | PR-1~10 이 실행 가능한 전부 | 순위 발행 영구 불가 | 없음 | ★ **(a) 보류** |
| | | (b) 착수 | 측정 기반 복구 | 큰 작업 · 즉시 가치 0 | 또 한 번 BROKEN 판정 가능 | |

**고려했으나 제시하지 않은 안**: `docs/_archive/**` 62문서 전체를 별도 리포로 분리 — 전제3(이동 금지)에 직접 위반이고 `docs/_archive/README.md` 가 62문서의 유일 진입점이라 색인이 끊긴다.

---

## 7. 묶음 공통 — 정책 준수 체크리스트

각 PR 본문에 아래를 포함한다.

- **정책 2**: §"🔍 사용자 검증 필요" — 시각/운영 확인 1~3개. "tests pass" 만 적기 금지
- **정책 4**: 단언과 회귀 가드를 **같은 PR** 에 (이 계획은 전 묶음이 GUARD 를 동반한다 — 설계상 만족)
- **정책 10**: `gh pr create --body-file <임시파일>` + 생성 직후 `gh pr view --json body` 길이 검증
- **정책 13**: 3-endpoint smoke check + §결과 (기대값 SSOT = `docs/runbooks/operational-smoke-checks.md`)
- **정책 14**: Code Scanning open alert 검토
- **정책 15**: 위 각 묶음에 3-tier 명시됨
- **6-step ⑤**: PR-11 로 이월 (commit body 에 delta 만)

### 🔴 정책 19 — 이 계획의 **11 PR 중 8개가 가드 표면**이다

`scripts/check_claim_review_trace.py:293-303` 의 `_GUARD_SURFACES` = `scripts/` · `.claude/hooks/` · `.claude/workflows/` · `.claude/settings.json` · `.github/workflows/` · `.pre-commit-config.yaml` · `tests/unit/scripts/` · `tests/unit/hooks/` · `docs/runbooks/owed-verification.md`, 그리고 `_GUARD_FILENAME` 이 `check_*.py` · `test_*guard*.py` 를 이름으로도 잡는다.

→ **PR-1 · 3 · 4 · 5 · 6 · 7 · 8 · 9 · 10 은 전부 가드 표면**이다. 2026-08-08 사용자 결정("필수로 승격")에 따라 **`claim-review-not-required` 로 자기 면제할 수 없다**. 각 PR 본문에 `(session · claim · verdict)` 3필드 흔적이 없으면 CI red 다. 계획 착수 전에 이 비용을 인지해야 한다.

### `check_red_budget.py` 와의 관계

이 계획은 🔴 규칙을 **늘리지 않고**, 기존 🔴 에 집행자를 붙인다(무집행 🔴 223 → 감소 방향). 예산 게이트에 유리하게 작동한다. 단 묶음 E·I 가 새 🔴 문장을 쓴다면 같은 PR 안의 신규 테스트 파일명을 블록 안에 명시해 '집행자 동반' 판정을 받게 한다.

---

## 8. 이 계획이 스스로에게 적용한 규율 (자기 점검)

| 규율 | 이 문서에서 |
|---|---|
| red 를 못 만들면 기각 | **2건 기각** — R3 C6(shared 매핑, red 0) · RRS 처분 밴드 26건(편집 1회로 소멸) |
| 계기를 먼저 의심 | R2 의 "27건" 을 재실행해 **중복 계상 + 오탐 11건** 을 발견. R3 의 pylint 버전(4.0.6)도 로컬은 3.3.1 이었으므로 **CI 핀 조합으로 재측정** |
| 합계 뮤테이션을 증거로 인정하지 않음 | 묶음 B·C 의 GUARD 는 **개별 스위치 뮤테이션**을 요구한다 (R1 C1 — M1 의 "밴드변동 51" 이 F3 48 + F8 3 의 합계였다) |
| 산문 가드는 양방향으로 틀린다 | 묶음 B 에 **인용 면제**를, 묶음 D·I·F 전건에 **anti-vacuity** 를 명세에 포함 |
| 값 복제 금지 | 묶음 A(배지→`--fail-under`) · C(주석 리터럴 삭제) · D(가드 개수) · F(카테고리 수) 가 전부 **파생화**다 |
| 2-phase 보고 게이트 | §0.5 에 재확인하지 않은 인용 4건을 명시. §6 결정 3 의 Railway 실태는 `UNVERIFIED` 로 표기 |

---

### 파일 경로 (절대)

- 리포: `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager`
- 이 계획이 참조한 데이터셋: `C:\Users\dirtc\AppData\Local\Temp\claude\f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager\a1ec48db-ceee-44fe-85e6-c847f67c25d4\scratchpad\doc_metrics.json` — 🔴 **이 계획은 이 데이터셋의 순위를 사용하지 않는다.** 묶음 K 의 입력으로만 남긴다.
- 재현 스크립트가 필요한 측정(§0.2 의 4·6·7)은 인라인 Python 으로 실행했으며, 묶음 B·G·H 의 GUARD 가 그 로직을 리포 안 영구 가드로 이관한다.
