# SCAManager

> **문서 작성 원칙**: 이 프로젝트의 모든 문서는 Claude가 가장 읽기 쉽고 이해하기 편한 구조로 작성한다.
> 새 문서를 작성하거나 기존 문서를 수정할 때 이 원칙을 반드시 따른다.

> **코드 주석 원칙 (이중 언어)**: 모든 코드 주석은 **한국어와 영어를 병행**하여 작성한다.
> 한국어를 먼저 쓰고, 바로 다음 줄에 영어를 추가한다.
> 신규 코드 작성 시 즉시 적용하고, 기존 파일은 해당 파일을 수정할 때 함께 갱신한다.
> 예외: `# TODO`, `# FIXME`, `# type: ignore` 등 단어 하나짜리 표준 태그는 영어 단독 사용 허용.
>

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스. `git push` 시 Claude Code CLI 기반 자동 코드리뷰(pre-push hook)도 지원한다.

---

## 🧭 탐색

작업 착수 전 → [작업 시작 전](#작업-시작-전-매-작업-30초) · 완료 시 → [필수 원칙 6-step](#필수-원칙)
· 미해결 일감 → [`docs/backlog.md`](docs/backlog.md) · 아키텍처 → [`docs/architecture.md`](docs/architecture.md)
· 영역별 규칙 → `.claude/rules/<area>.md`(해당 파일 편집 시 **자동 로드**)
· 새 환경 → [`docs/runbooks/new-machine-setup.md`](docs/runbooks/new-machine-setup.md)

**3층 분리 (2026-08-13 사용자 결정)** — 문서가 룰을 보강하는 방식으로 쌓인 것을 되돌린다:

| 층 | 위치 | 무엇을 담는가 |
|---|---|---|
| **프로세스** | [`docs/process/`](docs/process/) | *어떻게 수행하는가* — 가드 저술 · 주장 검증 · 문서 압축 · PR 수명 |
| **함정** | [`.claude/traps.md`](.claude/traps.md) | *이렇게 틀렸었다* — 실제로 밟은 실패 클래스 (집행 불가 축)<br>계열 A~E · 개수는 그 파일이 정본 |
| **규칙** | `.claude/rules/` · `.claude/policies/` | *하지 마라* — 🔴 는 **집행자 동반분만**<br>(`scripts/check_red_budget.py`) |

🔴 **새 마커를 붙이려면 그것을 집행하는 가드를 같은 PR 에 넣어야 한다 — 예외 없음.**
집행 가드를 만들 수 **없는** 내용이면 마커 없이 평문 규칙으로 적는다(규칙문 자체는 그대로 유효하다).
과거 사고의 **실패 기전**이면 [`.claude/traps.md`](.claude/traps.md) 에 이름 붙여 넣는다.
집행: `scripts/check_red_budget.py` · `tests/unit/scripts/test_red_budget.py` — 무집행이 1건이라도 생기면 red.

**실측 (2026-08-14)**: 계측 표면 위 마커 **97건 · 무집행 0건**. 2026-08-13 에 무집행 **221개**의
마커를 뗐고(규칙 본문은 한 줄도 지우지 않았다), 2026-08-14 에 **계측 표면을 6개로 넓혀**
`docs/process/**`·`.claude/traps.md` 를 편입했다. 세는 대상은 🔴 하나가 아니라 **빨강 계열
필수 표기 전부**이며(다른 기호로 바꿔 카운터를 피하는 통로를 막는다), 그 목록의 정본은
`scripts/check_red_budget.py` 의 `_RED_MARKERS` 상수다. 근거: 이 세션에서 실수를 막은 것은
**기계 가드 12회 · 함정 기억 7회 · 외부 검증 4회**였고 **룰 텍스트는 ≈0회**였다.

⚠️ **이 가드가 못 재는 축 3가지 — 봉인이 아니다** (Grok `019ffb93` · 회고 `wf_2b615d5e-8c5` 실증):

1. **프록시** — *"규칙 블록에 실재하는 가드 파일명이 있는가"* 만 본다. 그 가드가 *그 규칙을*
   집행하는지는 판정하지 않으며, **무관한 가드 이름을 적어도 통과한다**.
2. **표면 삭제 축은 CI(PR)에서만** 돈다 — 로컬 EXIT 0 은 "통과" 가 아니라 "안 쟀음" 이다.
3. 🔴 **계수 범위가 리포 전체가 아니다** — `SURFACE_GLOBS` 6개 밖에 빨강 마커가 **약 475건**
   더 있다(`docs/backlog.md` 92 · `docs/STATE.md` 41 · `docs/runbooks/**` 등). 그것들은 원장·
   시점 기록이라 규칙 층과 성격이 다르지만, **«100%» 는 그 475건을 뺀 값**이다. 명령형 표면
   전체로 재면 집행률은 약 11% 다. 2026-08-13 에 이 축을 밝히지 않은 채 «무집행 0건» 을
   조건 없이 단언했고, 회고가 그것을 **P0-A** 로 적발했다.
   집행: `tests/unit/scripts/test_red_budget.py` 가 이 세 한계의 생존을 고정한다.

이 세 줄을 지우지 말 것 — 지우는 순간 이 게이트가 봉인으로 읽힌다.

> **반복적으로 놓치는 것**
> 1. ORM 컬럼 추가 후 마이그레이션 미생성 → 운영 500 ([db.md](.claude/rules/db.md))
> 2. 신규 파일 추가 후 `docs/architecture.md` 미동기화 → 다음 세션 혼란
> 3. **측정 도구를 검증하지 않고 그 숫자를 사실로 발행** ([AGENTS.md](AGENTS.md) §측정 규율)

## 핵심 명령

**`make` 이 없는 머신이 있다** (이 개발 PC 포함 — `make: command not found`). `make X` 실패는
환경 문제이지 리포 문제가 아니다. **push 전 게이트 = `py -3 scripts/pre_push_gate.py`**
(make 비의존, CI 강제 가드 13종 — backlog R29). 단위 테스트 = `py -3 -m pytest tests/unit`.

전체 타깃 목록은 `Makefile` 이 정본이다 (`make help` 또는 파일 직접 확인 — 여기 복제하지 않는다).
최초 설정: `cp .env.example .env` → `make install` → `make run`.
## 아키텍처

- **src/ 트리 + 모듈 역할**: [`docs/architecture.md`](docs/architecture.md)
- **핵심 데이터 흐름** (Webhook → pipeline → notify → gate): [`docs/architecture.md#핵심-데이터-흐름`](docs/architecture.md#핵심-데이터-흐름)
- **점수 체계** (배점 + 등급 + AI 스케일링): [`docs/reference/scoring.md`](docs/reference/scoring.md)
- **전체 정합성 감사 자동화**: `/integrity-audit [full|diff|area=<name>]` → `.claude/workflows/integrity-audit.mjs` (수동 5+1 감사의 결정론적 코드화 — loop-until-dry + 3-렌즈 adversarial verify + completeness critic, read-only P0/P1/P2 리포트). 운영 가이드: [`docs/runbooks/integrity-audit.md`](docs/runbooks/integrity-audit.md).
- **5+1 회고 자동화**: `/retrospective [area=<관점>]` → `.claude/workflows/retrospective.mjs` (정책 8 5+1 회고의 결정론적 코드화 — 5 관점 finder loop-until-dry + completeness critic + cross-verify=finding 강제[verdict_coverage 지표]). loop-until-dry 정본 = `.claude/workflows/_lib/loop-until-dry.template.mjs` (drift 가드: `tests/unit/scripts/test_workflow_loop_sync.py`). 운영 가이드: [`docs/runbooks/retrospective.md`](docs/runbooks/retrospective.md). 스킬: `/docs-sync`(수치·서사 동기화).

> **신규 파일 추가 시 [`docs/architecture.md`](docs/architecture.md) 동기화 의무** — src/ 트리 항목 + 핵심 데이터 흐름 갱신.

## 환경변수

전체 목록·설명·제약은 [`docs/reference/env-vars.md`](docs/reference/env-vars.md) 가 정본이다
(여기 복제하면 두 곳이 갈라진다 — 실제로 4건 누락 사고가 있었다).

**함정만 적는다**: `SESSION_SECRET` 은 **기본값 그대로면 기동을 막지 못한다** — 32자 미만
기동 차단은 **커스텀 값에만** 걸린다(3분기 정본 [`security.md`](.claude/rules/security.md)).
그래서 운영은 `ENVIRONMENT=production` 또는 https `APP_BASE_URL` 을 **반드시** 설정해야 한다 —
그 둘이 없으면 공개된 기본 시크릿으로 뜬다 ·
`APP_BASE_URL` 미설정 시 Railway 에서 OAuth/Webhook 이 `http://` 로 등록돼 전달 실패 ·
`CLAUDE_REVIEW_MODEL` 을 **빈 값으로 두면** 기본값을 덮어 AI 리뷰가 전부 `api_error`(#1289).
## 배포

운영 가이드 [`docs/runbooks/railway.md`](docs/runbooks/railway.md) · 규칙
[`.claude/rules/deploy.md`](.claude/rules/deploy.md)(배포 파일 편집 시 자동 로드).
운영 DB = Supabase + 온프레미스 PostgreSQL 이중, 모든 환경 동일 alembic 적용.
## Agent 작업 규칙

모든 AI 에이전트(Claude Code 및 서브에이전트)는 SCAManager 작업 시 아래 규칙을 **반드시** 따른다.
`.claude/` 디렉토리에 정의된 스킬과 에이전트는 선택이 아닌 의무적 도구다.

> **📚 협업 회고 + 사용자 합의 정책**: 2026-05-01 회고 결과 사용자가 합의한 협업 정책 5건은 [docs/_archive/reports/2026-05-01-collaboration-retrospective.md](docs/_archive/reports/2026-05-01-collaboration-retrospective.md) 참조. 다음 세션의 Claude 는 본 정책을 default 로 적용. 핵심 5건은 아래 "사용자 협업 정책 (2026-05-01 합의)" 섹션 명시.

### 사용자 협업 정책 (2026-05-01 합의)

> **아래는 default rule 만이다.** 사용자 발화 인용 · 진화 이력 · 검증 사례 · Why/How 는
> [`.claude/policies/active.md`](.claude/policies/active.md) 와
> [`history.md`](.claude/policies/history.md) 가 정본이다(정책 17 원칙 2).
> 판단이 갈리거나 위반 회복이 필요하면 **그 파일을 열 것** — 여기 요약만 보고 결정하지 않는다.

| # | default rule | detail |
|---|---|---|
| **1** | 옵션 제시 시 **장단점 표**(옵션·장점·단점·위험·권장시점) + ★ 권장 + "고려했으나 제시 안 한 안" 1줄. "전부다" 류 일괄 결정 **또는 다중 PR 빠른 진행 신호 ≥10회** 시 **검토 깊이 자가 보고 요청 의무**(누락 시 다음 응답에서 회복). 예외: 단순 머지 보고 + 옵션 표 결정 | [history](.claude/policies/history.md#정책-1-진화) |
| **2** | 모든 PR 본문에 §"🔍 사용자 검증 필요" — 시각/운영 확인 1~3개 명시. "tests pass" 만 적기 **금지** | [active](.claude/policies/active.md#정책-2) |
| **3** | 위임받은 작업 중 **Claude 가 판단한 항목**은 PR 본문 또는 응답 끝에 명시 | — |
| **4** | 단언과 회귀 가드를 **같은 PR** 에 묶는다. 가드 없는 단언은 사고 시 책임 귀속 불가 | — |
| **5** | 사이클 끝마다 종료 신호 명시. 다중 단계 발화("A+B+C 진행") 후 일부만 하고 종료하면 **잔여 단계 진행 신호 회신 의무**. **Phase 종료 진입 시 정책 2/5/8/11 4 정책 cross-reference 자가 검토 의무**(한 정책만 적용하면 나머지 3 위반). **NEW-P0-N(운영 사고 차단)은 매 사이클 회신 의무** — 보류 default·정책 9 완화 **모두 미적용** | [active](.claude/policies/active.md#정책-5-phase-종료-cross-reference) |
| **6** | 에이전트 프롬프트에 `line:span` 인용 강제. 정책·메모리 본문의 `file:line` 은 **`grep -n` 실측값**이어야 한다(추정 금지 — drift 실사고 5건) | — |
| **8** | 회고는 **최소 4~5 에이전트 병렬 + 관점 분리 + cross-verify 1건(5+1)**. Claude 단독 회고 금지. 직전 정식 회고 이후 **≥3 세션 또는 ≥15 PR** 시 강제 트리거(SessionStart 훅이 경고) · 이월하려면 `docs/runbooks/retro-cadence-deferrals.md` 에 **사용자 승인 인용 + 목표 세션 기록 의무**. **회고 범위 = 직전 회고 이후 머지 PR + 본 세션 산출물 전체**(기계 산출 `scripts/retro_scope.py`) — 세션 산출물이 빠지면 **가장 검증 덜 된 코드가 회고를 피한다**. 자기회고 갈음은 **사용자 명시 승인 시에만** | [active](.claude/policies/active.md#정책-8-회고-카덴스) |
| **9** | 회고 직후 **자유 발언 4 섹션**(바라는 점 / 자성 / 필요한 것 / 수정 제안). 완화: 회신 부재 시 자율 판단 보고로 대체 OK — 단 (a) 운영 사고 차단 (b) destructive (c) architecture/UX/데이터모델 은 **명시 회신 의무**. **Phase 종료 시** §"🔍 회고 질문(사용자 회신 의무)" 1줄 추가 | [active](.claude/policies/active.md) |
| **10** | PR 은 **직접 생성**(`gh pr create`) — URL 안내 금지. 본문은 **임시 파일 + `--body-file`** 로만(`@-`/stdin 금지 — 8건 본문 소실 사고) + 생성 직후 `gh pr view --json body` 길이 검증 | [active](.claude/policies/active.md#정책-10) |
| **11** | `templates/**`·`static/**` 등 **시각 변경 PR** 은 본문 최상단에 **4테마 × 모바일/데스크탑 8조합** 체크리스트. "테스트 통과" 만 적기 금지 — 정적↔시각 비대칭 명시 의무 | [active](.claude/policies/active.md#정책-11) |
| **12** | MCP: SELECT-only 자율 OK / **INSERT·UPDATE·DELETE·DROP·ALTER + PII·credential SELECT = 사전 승인 의무**. 호출 시 PR 본문에 결과 명시 | [active](.claude/policies/active.md#정책-12) |
| **13** | 매 사이클/Phase 종료 시 **3-endpoint smoke check** + PR 본문 §결과. 기대값 SSOT = [`operational-smoke-checks.md`](docs/runbooks/operational-smoke-checks.md) (리터럴 복제 금지 — 3 사본 drift 사고) | [active](.claude/policies/active.md#정책-13) |
| **14** | 매 사이클 종료 시 **Code Scanning open alert** 직접 검토 → fix / dismiss+사유 / suppress+회고. lint 통과 ≠ Security 탭 0 (CodeQL 별도 룰셋) | [active](.claude/policies/active.md#정책-14) |
| **15** | 모든 Edit/Write/destructive **직전 3 자문**(목적 정합? 영향 범위? 검증 방법?). 이해 부족 시 중단. **3-tier**: High(스키마·API·권한·데이터모델 = 사전 확인) / Medium(자율+보고) / Low(즉시) | [active](.claude/policies/active.md#정책-15) |
| **16** | 우선순위 **1.정확성 2.성능 3.가독성 4.최소 추상화(사용처 ≥3) 5.토큰 비용**. 같은 값·로직이 2+곳이면 수정 **직전** `grep -rn` 전수 열거. **명시 제외**(사전 확인 의무): `build_review_prompt` 토큰예산 축소 · `review_guides/` 압축 | [active](.claude/policies/active.md#정책-16) |
| **17** | 문서 정리는 **안정성 > 권장 규격**. **Anthropic 200줄 등 외부 권장 규격은 가이드라인 — 안정성과 충돌하면 거부한다.** default rule + 진화 1~2줄은 **본문 보존**, detail 만 external. 매 분리 단계마다 **5+1 회의 + 운영 검증 + 사용자 옵션 표 결정**. **매 작업/회고/PR 의무 영역(정책 8·11·5·9)은 본문 보존 default** — 분리 시 High tier 사전 확인. ≥18 PR 영역은 ≥5 사이클마다 정기 검증 | [active](.claude/policies/active.md#정책-17-why-how) |

#### 정책 7: 모든 작업은 PR 단위 (main 직접 작업 지양)

**예외 0.** 흐름: `git checkout main && pull` → `checkout -b <type>/<scope>` → 작업+commit
→ `push -u origin` → **`gh pr create`** → 사용자 머지. **금지**: `git push origin main` ·
main 에 commit 후 방치 · "사소한 docs 라 main 에 직접". 신규 파일·typo·docs-only 도 예외 없다.
접두사: `feat/` `fix/` `chore/` `docs/`. 위반 시 회복: [active](.claude/policies/active.md#정책-7).

#### 정책 18 폐기 (2026-07-10 — Codex 구독 해지)

Codex mutual 검증 폐기. **`codex exec` 실패 = 정상**(이상 징후로 보고 금지). 코드·문서의
"Codex 적발" 주석은 **당시 사실 기록(재작성 금지)**. 대체 = 정책 19 + Claude 단독 2-layer.

#### 정책 19: Claude ↔ Grok 협업 (default ON)

**SSOT = [`AGENTS.md`](AGENTS.md)(3-불변식·트리거) + [`docs/runbooks/ai-collaboration.md`](docs/runbooks/ai-collaboration.md).**
별도 지시 없으면 **실질 작업마다 Grok CLAIM-REVIEW 포함**(건너뛰려면 명시 지시).

- **트리거**: "봉인/완결/fail-closed/유출 0" 주장 → 그 주장 하나로 Grok 뮤테이션 패스.
  **1순위 사냥 = observer-lie**: *보호 장치를 삭제해도 여전히 참으로 보이는 것은?*
- **A2**: 새 seal 은 **실경로 뮤테이션 red** 없이 HOLDS 금지(합성 픽스처 불가).
- **2-phase 사용자 보고 게이트**(매 발화 의무): `배포|활성|봉인|운영|cron 실행됨` 포함
  문장은 라이브 근거 동반 또는 **`UNVERIFIED:` 접두사** 의무. `STATIC-ONLY-UNVERIFIED` 는
  사용자 보고 불가.
- **경계 = '소유 금지'**: Grok 은 정책·backlog 를 **저술하지 않는다**(claim-review 는 허용 —
  seal/HOLDS 주장 시 `owner-interrupt: claim-review` 명시). 호출 금지: 계획·WBS·구현 중간.
- 🔴 **집행면(CI)**: seal 어휘 PR 은 `check_claim_review_trace.py` 가 흔적(session/claim/verdict)을 강제.
- 🔴 **가드 표면 PR 은 면제 불가** (2026-08-08 사용자 결정 "필수로 승격") — 관측자를 저술하는
  PR 은 `claim-review-not-required` 로 통과할 수 없다. 대상 목록·예외·근거는 AGENTS.md 가 정본.
  집행: `check_claim_review_trace.py` · `tests/unit/scripts/test_claim_review_mandatory_on_guards.py`.

detail: [active](.claude/policies/active.md) · 진화 이력: [history](.claude/policies/history.md)

### 작업 시작 전 (매 작업 30초)

```bash
gh run list --limit 3                 # CI status (기존 vs 신규 실패 구분)
py -3 scripts/check_memory_refs.py    # 🔴 메모리 경로를 **유도**해 출력 (슬러그 하드코딩 금지)
git status && git checkout -b <브랜치명>   # main 직접 커밋 금지 (정책 7)
```

Code Scanning open alert 확인(정책 14)은 GitHub Security 탭 또는
`gh api repos/xzawed/SCAManager/code-scanning/alerts`.

> 🔴 **카운터 2종은 SessionStart 훅이 자동 실행한다** — 회고 카덴스(`check_retro_cadence.py`)와
> owed 원장 미결(`check_owed_verification.py`). 훅 stdout 이 컨텍스트에 주입되므로 **수동 실행
> 불필요**. 둘 다 advisory(비차단). 배선 회귀 가드: `test_session_start_wiring.py`.

**메모리 인덱스**는 매 세션 자동 로드된다. 신규 메모리 추가 시 MEMORY.md 인덱스 동기화 의무.
신규 fixture/테스트/패턴 작성 전 **메모리 grep 의무** — 같은 함정을 두 번 밟지 않기 위한 교차 세션 학습 반송자다(`feedback_` prefix 파일이 테스트/CI 함정을 기록한다).

### 필수 원칙

- **TDD 우선**: 구현 코드 작성 전 반드시 `test-writer` 에이전트로 테스트를 먼저 작성한다.
- **Hook = best-effort 조기 실패 탐지 (전체 게이트 아님)**: `src/` 파일 편집 후 PostToolUse Hook(`posttool_pytest_smoke.py`)이 **편집된 영역의 tests/unit 서브디렉토리만** 빠르게 실행(대응 없으면 collection 스모크)한다. ❌ 배너 시 즉시 조사. **전체 게이트는 push-time(6-step ②)로 위임** — 이 훅은 스코프 스모크라 통과가 전체 통과를 보장하지 않는다 (2026-07-18 P1 테마 C — 구 훅이 전체 5566 을 60s 타임아웃에 돌려 완주 불가·`|| true` 로 삼켜 false-green 이던 것을 봉인).
- **Phase 완료 조건**: 테스트 전체 통과 + **CI `lint-src` job 통과**(pylint `--fail-under=9.90` + bandit) + (파이프라인 변경 시 `pipeline-reviewer` 승인) 세 조건이 모두 충족될 때만 Phase 완료를 선언한다. **로컬 `make lint` 통과는 근거가 아니다** — 그 타깃은 세 린터를 `|| true` 로 삼키는 advisory 점검이다. 검증 가능한 근거는 CI job 결과뿐이다. **로컬 사전 확인은 `py -3 scripts/pre_push_gate.py` 를 쓴다** — `make` 이 없는 머신에서도 돌고, CI 가 강제하는 **repo-integrity 9종 + PR-diff 한정 4종**을 실행하며, **자기가 못 보는 축(CodeQL·Sonar·Codecov·TruffleHog·pip-audit·lint-js·PG job·통합테스트)을 매번 인쇄**한다. `--full` 이면 pylint·bandit·`pytest tests/unit` 도 돈다. ⚠️ **`make gate` 는 "CI 와 동일 기준" 이 아니었다**(2026-08-01 정정) — 그 타깃은 pytest·pylint·bandit 뿐이라 위 13 가드를 **하나도** 돌리지 않고, 애초에 이 머신에는 `make` 자체가 없다(backlog R29). 이전에는 `lint-strict`(fail-under)가 CI·pre-commit 어디에도 배선되지 않아 **"lint 통과" 주장이 기계로 검증 불가**했다(회고 D13).
- **완료 시 필수 6-step**: 작업이 완료되면 반드시 ① 커밋 → ② 🔴 **push 전 `pytest tests/unit` 전체 통과 실측** (영역 서브셋[`tests/unit/ui`+`i18n` 등]만 실행으로 대체 금지 — #1041 에서 i18n 키 제거가 타 영역 `test_i18n_settings._KEYS` parametrize 연쇄를 깨뜨렸으나 서브셋만 돌려 놓쳐 CI 6-fail. **인라인 cleanup·docs-only 예외 없음**. 🔴 **로컬 통과 ≠ CI 통과** — 로컬 인터프리터[3.14]와 CI[3.12]가 이원이라 버전 의존 회귀는 로컬이 못 잡는다. `pre_push_gate` 가 이 이원을 매 실행 인쇄한다 — backlog R30) → ③ `git push` → ④ PR 생성(`gh pr create`) → ⑤ `docs/STATE.md` 수치 갱신 (🔴 **손으로 고치는 곳은 §테스트 수 추적 이력 맨 아래 한 줄뿐** — 나머지 4지점[종합 수치·추적셀 머리·README 2배지]은 `py -3 scripts/check_docs_sync.py --fix` 가 그 한 줄에서 **파생**한다. 2026-08-05 문서 감사 P0-3: 같은 정수를 5곳에 손유지하던 것이 실제 drift 사고를 냈다 — N지점 동기화는 N-1번의 실패 기회다) + `docs/cycle-history.md` 사이클 이력 동기화 → ⑥ **docs/architecture.md 동기화** (신규 파일 추가·삭제·이름 변경 시 `src/` 트리와 `### 핵심 데이터 흐름` 내 언급 갱신) 를 순서대로 수행한다. 예외 없음.
  - **⑤ 배치-PR 이월 분기 (2026-07-09 rank6 — 병렬 STATE/badge 충돌 자초 학습)**: 세션 내 **동일 파일(STATE.md 수치 라인·README 배지)을 건드리는 미머지 PR 이 1건 이상 in-flight** 이면, per-PR ⑤는 **commit body 에 카운트 delta 만 기록**하고 STATE/배지 실갱신은 **세션 종료 시 단일 trailing sync PR 로 이월**한다. 이유: 여러 PR 이 STATE 동일 라인을 연속 write 하면 git merge conflict 자초(본 세션 ⑤ #1048 이 ③ 머지 후 README 인접-라인 충돌 자초 → 사후 수습). PR 착수 전 `git log --oneline main..<open-branches>` 또는 `gh pr list` 로 동일 파일 touch 미머지 PR 존재 여부 1줄 확인 의무.
- **README.md 배지 동기화**: 테스트 수·pylint·커버리지 수치가 바뀌면 `README.md` 21~25줄 배지도 함께 갱신한다. 수치 출처는 항상 `docs/STATE.md`.
- **신규 파일 추가 시 동기화 의무** (전례 3건 — 누락 시 다음 Phase 착수 전 보완):
  [`docs/architecture.md`](docs/architecture.md) 의 `src/` 트리 · `templates/`·`repositories/`·
  `services/` 목록 · 핵심 데이터 흐름 / 신규 환경변수는 [`docs/reference/env-vars.md`](docs/reference/env-vars.md)
  (`config.py` validator·최솟값 변경 시에도) / 해당 영역 [`.claude/rules/<area>.md`](.claude/rules/) 본문.
  rules 는 path 매칭으로 **자동 로드**되므로 본문이 stale 하면 Claude 가 틀린 지침을 받는다.

### 모바일 환경 보호 — 수정 금지 파일

수정 금지 파일(`alembic/versions/`, `src/templates/*.html`, `railway.toml`, `alembic.ini`) — 테스트 환경 없을 때 PreToolUse Hook 자동 차단. 상세: [docs/runbooks/workflow.md](docs/runbooks/workflow.md#모바일-환경-보호--수정-금지-파일)

**예외:** `make test` 가 정상 실행되는 환경(로컬 PC, GitHub Codespaces)에서는 모든 파일 수정이 허용된다.

### 작업 유형별 필수 실행 순서

작업 유형별 실행 순서 (새 기능 / 파이프라인 / Webhook-API / Phase 착수): [docs/runbooks/workflow.md](docs/runbooks/workflow.md#작업-유형별-필수-실행-순서)

### 파일 편집 에이전트 — 작업트리 격리 (병렬·단일 무관)

**파일을 편집하는 백그라운드 에이전트는 `isolation: worktree` 의무.** 격리 없는 에이전트는
메인 세션과 **같은 작업트리·`.git` 을 공유**해 브랜치·working tree 를 오염시킨다.
전례 2건(2026-04-27 병렬 3 에이전트가 한 브랜치에 커밋 / 2026-07-18 **단일** 에이전트가 메인
트리 오염) — **"단일이라 격리 불요" 는 오판**이다.

디스패치 3 조건: ① `isolation: worktree` ② 프롬프트 Step 1 에 고유 브랜치명 명시
(`git checkout -b docs/<고유-이름>`) ③ 완료 기준에 **PR URL 반환** 포함(분석만 하고 멈추는 사고 방지).

## 주의사항 (카테고리별 — `.claude/rules/<area>.md` path-scoped)

> **사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 `.claude/rules/<area>.md` 로 분리 (Anthropic 공식 path-scoped rules 패턴). Claude Code 가 해당 영역 파일 작업 시 자동 로드. 매 세션 의무 read 부담 0.

| 영역 | 규칙 파일 (매칭 경로 — 이 경로 편집 시 **자동 로드**) |
|------|------------------------------------------------|
| 테스트 | testing.md (`tests/**`, `e2e/**`, `**/conftest.py`, `pytest.ini`) → [`.claude/rules/testing.md`](.claude/rules/testing.md) |
| DB / 마이그레이션 | db.md (`alembic/**`, `src/models/**`, `src/database.py`, `src/repositories/**`) → [`.claude/rules/db.md`](.claude/rules/db.md) |
| 파이프라인 / 비즈니스 로직 | pipeline.md (`src/worker/pipeline.py`, `src/analyzer/**`, `src/scorer/**`, `src/webhook/**`, `src/gate/**`) → [`.claude/rules/pipeline.md`](.claude/rules/pipeline.md) |
| API / 알림 채널 | api.md (`src/api/**`, `src/notifier/**`, `src/webhook/**`, `src/gate/**`, `src/github_client/**`, `src/scheduler.py`, `src/main.py`) → [`.claude/rules/api.md`](.claude/rules/api.md) |
| 보안 | security.md (`src/auth/**`, `src/crypto.py`, `src/shared/log_safety.py`, `src/shared/ssrf.py`, `src/shared/secure_compare.py`, `src/api/auth.py`, `src/webhook/validator.py`, `src/main.py`, `src/logging_config.py`) → [`.claude/rules/security.md`](.claude/rules/security.md) |
| UI / 템플릿 | ui.md (`src/templates/**`, `src/static/**`, `src/ui/**`) → [`.claude/rules/ui.md`](.claude/rules/ui.md) |
| 다국어 / i18n | i18n.md (`src/i18n/**`, `src/middleware/locale.py`, `src/notifier/_language.py`, `src/analyzer/pure/review_guides/**`) → [`.claude/rules/i18n.md`](.claude/rules/i18n.md) |
| 배포 | deploy.md (`railway.toml`, `nixpacks.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `.python-version`, `alembic.ini`, `sonar-project.properties`) → [`.claude/rules/deploy.md`](.claude/rules/deploy.md) |
| 서비스 계층 | services.md (`src/services/**`, `src/verifier/**`, `src/config_manager/**`, `src/railway_client/**`, `src/mcp/**`, `src/cli/**`) → [`.claude/rules/services.md`](.claude/rules/services.md) |
| 가드 / 훅 / 워크플로 | guards.md (`scripts/**`, `.claude/hooks/**`, `.claude/workflows/**`, `tests/unit/scripts/**`, `tests/unit/hooks/**`) → [`.claude/rules/guards.md`](.claude/rules/guards.md) |
| 문서 / 원장 | docs.md (`docs/**`, `README.md`, `README.ko.md`, `CLAUDE.md`, `AGENTS.md`) → [`.claude/rules/docs.md`](.claude/rules/docs.md) |

표시는 과거 사고로 검증된 고위험 규칙이다 (각 `.claude/rules/<area>.md` 파일 본문 참조).

## 현재 상태

최신 수치는 [docs/STATE.md](docs/STATE.md) 참조. 사이클 이력: [`docs/cycle-history.md`](docs/cycle-history.md) (사이클 60~166).
