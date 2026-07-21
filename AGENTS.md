# AGENTS.md — 비-Claude 에이전트(Grok·Codex 등) 진입점 + 가드 저술 규율 SSOT

> Claude Code 는 `CLAUDE.md` 를 자동 로드한다. **Grok·Codex 등 auto-load 가 없는 에이전트는
> 이 파일을 먼저 읽는다.** 이 파일은 두 부류가 **공유하는 단일 출처(dual-consumer SSOT)** 다.
> 상세 정책은 `CLAUDE.md`, 영역별 규칙은 `.claude/rules/<area>.md`, 협업 프로토콜은
> `docs/runbooks/ai-collaboration.md`.

## 이 저장소가 무엇인가

SCAManager — GitHub Push/PR 시 정적분석 + AI 코드리뷰를 자동 수행하고 점수 기반 PR
자동/반자동 Gate 와 대시보드를 제공하는 서비스. 핵심 명령: `make test`(전체) ·
`make lint`(advisory) · `make gate`(pytest + pylint fail-under + bandit, **실제 게이트**) ·
push 전 `pytest tests/unit` 전체 통과 의무.

---

## 🔴🔴 가드/관측자 저술 3-불변식 (이 저장소 최다 반복 실수의 SSOT)

> 이 저장소가 **가장 자주 반복하는 실패 클래스**다 — 코드 버그는 고쳤는데 **관측자(가드·
> 테스트·문서)가 계속 거짓말한다**(observer-lie). 실측 재발: #1136 · #1145 · #1140 · #1156 ·
> #1121. 새 가드/테스트/완전성 검사/kill-switch 를 저술할 때 **예외 없이** 아래 3 불변식을 지킨다.
>
> 🔴 **핵심 질문**: *보호 장치를 삭제해도 여전히 참으로 보이는 것은 무엇인가?*

### 불변식 1 — fail-closed (통과 조건이 '문자열이 어딘가 있으면' 이면 안 된다)

가드의 통과가 **산문·주석·echo·advisory** 로 충족되면 안 된다. 정적 검사는 **코드 구조**
(AST 호출·실제 값·실행 결과)를 봐야 하고, 산문은 그것을 만족시킬 수 없어야 한다.

- 🔴 **실측 재발**: `#1136` 조달 가드가 `echo 'WARNING: tsc install failed'` **경고 산문**으로
  통과 — 실제 설치가 사라져도 echo 문구만 남으면 "조달됨" 오판. tflint 를 잡으려던 가드가
  정확히 tflint 형 결함을 산문으로 눈감았다.
- 🔴 `#1156` 안전등급 자기인증 방지가 "사용자 회신 **대기**" 산문에 걸려 ✅ 를 통과시킴.
- **규칙**: substring/`X in source` 검사 금지. AST(`ast.Call`·`ast.walk`) 또는 실행 관측을 쓴다.
  산문이 통과시킬 수 있으면 그 가드는 fail-**open** 이다.

### 불변식 2 — 실경로 뮤테이션 (합성 픽스처로 HOLDS 금지)

새 seal(완전성 검사·가드·kill-switch)을 만들면 그 seal 을 **최소 1회 깨뜨려 red 를 확인**해야
HOLDS. 그리고 뮤테이션 대상은 seal 이 **보호한다고 주장하는 실제 운영 경로**(그 파일/심볼 또는
실 의존)여야 한다.

- 🔴 **합성 문자열·픽스처만 바꾸는 것으로는 불충족**. 근거: `#1121` 이 합성 입력으로 "뮤테이션
  실증" 을 PR 본문에 적었으나, **실제 `scheduler.py` 를 넣으면 docstring 이 마커를 만족시켜 축이
  죽어 있었다**(replica 5 로 올려도 8 passed).
- 🔴 **하네스 거짓 통과 주의**: 뮤테이션이 실제로 **적용됐는지** 먼저 단언하라
  (`assert mutated != orig`). sed/치환이 조용히 미적용인데 "N passed" 를 검증으로 오독한
  사고가 반복됐다.
- **규칙**: 커밋 본문에 "뮤테이션 N/N red" 를 적으려면 실파일 대상 · 적용 확인 · red 관측 3자를 실증.

### 불변식 3 — 배선 테스트 (정의 ≠ 배선; 순수 함수 옳음 ≠ 진입점 도달)

가드/헬퍼를 **정의만** 하고 **호출·배선**하지 않으면 dead code 다. 그리고 순수 함수가 옳아도
**진입점이 그 함수에 실제로 도달**하는지는 별개 단언이다.

- 🔴 **실측 재발**: `#1145` 스모크 훅의 alembic/scripts 감시 확장이 순수 함수엔 있는데 `main()`
  이 `is_src_file`(src 전용)로 게이트해 **런타임에서 통째로 dead** — 테스트는 순수 함수만 봤다.
- 🔴 `#1156` 2026-07-19 P0 시정이 advisory 훅(비차단·세션시작)뿐이라 **재위반을 못 막음** —
  진단은 있고 집행면이 없었다.
- **규칙**: 배선 테스트는 **산문 grep 이 아니라 실제 실행/호출을 관측**한다(큐에 등록된 태스크를
  실제 실행, `main()` 을 실제 stdin 으로 호출, AST 로 진입점이 그 심볼을 호출하는지). 신규
  가드는 반드시 "그 가드가 실제 게이트(ci/pre-commit/SessionStart/PostToolUse)에 배선됐나" 를
  동반 검증.

> ⚠️ **메타 경고 (이 저장소 메모리 자인)**: "문서-only 시정이 5회 실패 → 기계화해야 했다".
> 위 3 불변식을 **문서로만** 적고 기계 강제(A2 뮤테이션-red)가 없으면 이 파일 자체가 6번째
> 문서-only 시정이 된다. 신규 가드는 예외 없이 실경로 뮤테이션 red 로 증명한다.
>
> 🔴 **정적 탐지의 천장 (Grok 2회 적대검증으로 확정 — 2026-07-20)**: fail-open 방어는 아래
> 3층이 **완성이며, 완전 자동 탐지기는 원리적으로 불가**하다(감추지 않고 명시).
>
> 1. **불변식 3(배선)** — `test_guard_wiring_coverage`(실제 호출 관측, 산문 언급 아님).
> 2. **불변식 1 floor** — `check_guard_fail_open.py`(B8): 파일 읽어 판정하는 `scripts/check_*.py`
>    가 구조 도구(ast/re/subprocess)를 **하나도** 안 쓰면 차단(가장 egregious 케이스). 실제로 이
>    프로그램의 `check_architecture_tree_sync` 에서 fail-open 1건 적발.
> 3. **write-time 규율** — `.claude/rules/guards.md`(paths 에 `tests/unit/scripts/**`·
>    `.claude/hooks/**` 포함)가 **실제 실패 표면 편집 시 자동 로드**. 🔴 실측: 최다 재발 사고
>    `#1136`·`#1156` 은 `check_*.py` 가 아니라 **test-as-guard**(`test_analyzer_provenance`·
>    `test_owed_ledger_consistency`)에 있었다 — 그 표면에서 3-불변식이 write-time 에 로드된다.
>
> 🔴 **왜 "완전 탐지기" 를 안 만드는가** (Grok SURVIVES 판정): `X in file_text` 는 **마커·존재
> 검사에 정당하게** 쓰인다(B8 자신도 `_ESCAPE in src`). 결정 표현식 substring 을 구문적으로
> 차단하면 실측 **오탐 2 / 진탐 0**(둘 다 정당한 presence 검사) → guard-suicide(정책 17). 또
> literal-only 정제는 `#1136`(변수 `binary in _build_command()`)을 **놓친다**. **fail-open 은
> 산문의 진위처럼 semantic 이라 정적으로 판정 불가** — 남은 방어선은 **review-time Grok
> claim-review**(불변식 1의 semantic 잔여)뿐이고, 그것으로 충분하다. 이 천장을 인정하는 것이
> 성급한 완전 봉인(새 false-green)보다 정직하다.
>
> 🔴 **신규 seal 프로세스 규율** (Grok 대안 — AST 오라클 아니라 프로세스): 새 가드/테스트는
> **실경로 뮤테이션-red + `assert mutated != orig`**(불변식 2)를 PR 본문에 실증. 기계 오라클이
> 아니라 저술 규율(guards.md)·리뷰로 강제한다.

---

## Claude ↔ Grok 협업 (요약 — 상세 = `docs/runbooks/ai-collaboration.md`)

- **Grok default ON** (2026-07-20 사용자 지시): 별도 지시 없으면 실질 작업마다 Grok
  **CLAIM-REVIEW**(Claude 주장 반증). 파이프라인 단계가 아니라 claim-review/인터럽트.
- **1순위 사냥 = observer-lie** — 위 핵심 질문. seal/완결/fail-closed/유출-0 주장이 트리거.
- **A2**: 신규 관측자는 실경로 뮤테이션 없이 HOLDS 금지(불변식 2와 동일 — 이것이 SSOT).
- **경계**: Grok 은 정책·backlog 처방을 **저술하지 않는다**(claim-review 는 허용).
- 실무: 범위 좁게(2 클레임·400자 — 넓으면 타임아웃) · 절대경로 전달(`/tmp` 가 리포 드라이브로
  해석됨) · Grok 심각도 판단 불신(이진 반증 질문으로 우회).
- 🔴 **판정 착지 규약**: Grok 판정(HOLDS/BROKEN)은 외부 `.md` 기록 → Claude 1회 triage →
  영향 계층 라우팅(`wrong-merge`·`secret`·`fail-open` → `owed-verification.md` 안전등급 /
  `silent-disable` → `backlog.md`). 상세 = `ai-collaboration.md` §라우팅·§findings 스키마.

## 규칙·정책 어디서 찾나 (grep 진입점)

- 영역별 규칙: `.claude/rules/{testing,db,pipeline,api,security,ui,i18n,deploy,services,guards}.md`
  (Claude 는 매칭 파일 편집 시 자동 로드 / **Grok 은 auto-load 없으므로 이 목록을 grep**).
  🔴 **`guards.md`** = 가드/훅/워크플로 저술 시 로드되는 3-불변식(위 SSOT 의 편집-표면 사본).
- 협업 정책 1~19: `CLAUDE.md` (default rule) + `.claude/policies/{active,history}.md` (detail).
- 미결 검증 원장: `docs/runbooks/owed-verification.md`. 미해결 일감: `docs/backlog.md`.
- 현재 수치·상태: `docs/STATE.md`. 아키텍처·가드 배선: `docs/architecture.md`.
