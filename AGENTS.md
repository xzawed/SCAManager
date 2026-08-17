# AGENTS.md — 비-Claude 에이전트(Grok·Codex 등) 진입점 + 가드 저술 규율 SSOT

> Claude Code 는 `CLAUDE.md` 를 자동 로드한다. **Grok·Codex 등 auto-load 가 없는 에이전트는
> 이 파일을 먼저 읽는다.** 이 파일은 두 부류가 **공유하는 단일 출처(dual-consumer SSOT)** 다.
> 상세 정책은 `CLAUDE.md`, 영역별 규칙은 `.claude/rules/<area>.md`, 협업 프로토콜은
> `docs/runbooks/ai-collaboration.md`.

## 이 저장소가 무엇인가

SCAManager — GitHub Push/PR 시 정적분석 + AI 코드리뷰를 자동 수행하고 점수 기반 PR
자동/반자동 Gate 와 대시보드를 제공하는 서비스.

**로컬 검증 명령**

| 목적 | 명령 | 비고 |
|---|---|---|
| **push 전 게이트** | `py -3 scripts/pre_push_gate.py` | CI 가 강제하는 가드를 실행. 목록 정본 = 그 파일의 `_INTEGRITY` · `_DIFF_SCOPED`. `--full` 이면 pylint·bandit·`pytest tests/unit` 도. 자기가 못 보는 축을 매 실행 인쇄한다 |
| 단위 테스트 | `py -3 -m pytest tests/unit` | push 전 **전체** 통과 의무 (영역 서브셋 대체 금지) |
| 정적 린트 | `py -3 -m pylint src/` · `py -3 -m bandit -r src/ -q` | CI `lint-src` 와 동일. `--fail-under` 는 README 배지에서 파생 (`scripts/pre_push_gate.py` 의 `pylint_floor`) |

⚠️ **`make` 이 없는 머신이 있다**(이 개발 PC 포함 — `make: command not found`). `make test`/`make lint`/
`make gate` 가 실패하면 환경 문제이지 리포 문제가 아니다. `make gate` 는
**pytest·pylint·bandit 3종뿐**이라 `pre_push_gate.py` 가 돌리는 가드를 하나도 돌리지 않는다
(`tests/unit/scripts/test_gate_claim_consistency.py`). 유일한 진짜 집행면은 **CI** 다.

**AGENTS.md 가 아닌 것**: 이 문서는 가드/관측자 저술 규율(3-불변식)의 SSOT 이지, 저장소 전체
법률이 아니다. 정책 1~19 · 완료 6-step · TDD · PR 템플릿 의무는 [`CLAUDE.md`](CLAUDE.md) 에 있고,
도메인 규칙은 `.claude/rules/<area>.md` 에 있다(아래 §작업 전 열어야 할 규칙).

---

## 가드/관측자 저술 3-불변식 (이 저장소 최다 반복 실수의 SSOT)

> 이 저장소가 **가장 자주 반복하는 실패 클래스**다 — 코드 버그는 고쳤는데 **관측자(가드·
> 테스트·문서)가 계속 거짓말한다**(observer-lie). 새 가드/테스트/완전성 검사/kill-switch 를
> 저술할 때 **예외 없이** 아래 3 불변식을 지킨다.
>
> **핵심 질문**: *보호 장치를 삭제해도 여전히 참으로 보이는 것은 무엇인가?*

### 불변식 1 — fail-closed (통과 조건이 '문자열이 어딘가 있으면' 이면 안 된다)

가드의 통과가 **산문·주석·echo·advisory** 로 충족되면 안 된다. 정적 검사는 **코드 구조**
(AST 호출·실제 값·실행 결과)를 봐야 하고, 산문은 그것을 만족시킬 수 없어야 한다.

- **클래스**: `echo 'WARNING: … failed'` 가 설치 실패를 삼키면, 바이너리가 없어도 "조달됨" 으로 읽힌다.
  "사용자 회신 **대기**" 같은 advisory 산문이 통과를 충족해도 같다.
- **규칙**: substring/`X in source` 검사 금지. AST(`ast.Call`·`ast.walk`) 또는 실행 관측을 쓴다.
  산문이 통과시킬 수 있으면 그 가드는 fail-**open** 이다.
  바닥 집행: `scripts/check_guard_fail_open.py` (구조 도구 0개인 `scripts/check_*.py`·훅만).

### 불변식 2 — 실경로 뮤테이션 (합성 픽스처로 HOLDS 금지)

새 seal(완전성 검사·가드·kill-switch)을 만들면 그 seal 을 **최소 1회 깨뜨려 red 를 확인**해야
HOLDS. 그리고 뮤테이션 대상은 seal 이 **보호한다고 주장하는 실제 운영 경로**(그 파일/심볼 또는
실 의존)여야 한다.

- **합성 문자열·픽스처만 바꾸는 것으로는 불충족**. 실파일/심볼을 깨뜨려야 한다.
- **하네스 거짓 통과 주의**: 뮤테이션이 실제로 **적용됐는지** 먼저 단언하라
  (`assert mutated != orig`). sed/치환이 조용히 미적용인데 "N passed" 를 검증으로 오독하지 않는다.
- **규칙**: 커밋 본문에 "뮤테이션 N/N red" 를 적으려면 실파일 대상 · 적용 확인 · red 관측 3자를 실증.

### 불변식 3 — 배선 테스트 (정의 ≠ 배선; 순수 함수 옳음 ≠ 진입점 도달)

가드/헬퍼를 **정의만** 하고 **호출·배선**하지 않으면 dead code 다. 그리고 순수 함수가 옳아도
**진입점이 그 함수에 실제로 도달**하는지는 별개 단언이다.

- **규칙**: 배선 테스트는 **산문 grep 이 아니라 실제 실행/호출을 관측**한다(큐에 등록된 태스크를
  실제 실행, `main()` 을 실제 stdin 으로 호출, AST 로 진입점이 그 심볼을 호출하는지). 신규
  가드는 반드시 "그 가드가 실제 게이트(ci/pre-commit/SessionStart/PostToolUse)에 배선됐나" 를
  동반 검증.
  집행: `tests/unit/scripts/test_guard_wiring_coverage.py` · `tests/unit/scripts/_wiring_shape`.

### 불변식 2-b — 반례 일반화 (반례 하나를 막고 봉인을 선언하지 않는다)

> **왜 `불변식 4` 가 아닌가**: 리포가 `3-불변식` 을 이름으로 참조하고, 이 문서가 이미
> *"적용 술어가 다르면 번호를 붙이지 않는다"* 는 선례를 세웠다(§측정 규율). 이 규율은
> 술어가 **불변식 2(실경로 뮤테이션)와 같다** — 뮤테이션으로 seal 을 증명하는 순간에
> 적용된다. 그래서 **2 의 하위 축**으로 둔다. 총칭은 계속 `3-불변식` 이다.

**2026-08-13 사용자 결정 (A+B 혼합 채택 — R83).** 외부 적대 검증이 반례를 주면
그 반례를 red 로 만드는 것으로 **끝내지 않는다**. 두 의무가 함께 붙는다.

**A. 반례 일반화 의무 (결함을 막는다)**

1. 받은 반례가 속한 **클래스를 명명**한다(예: *"아카이브 내용 공동화"*).
2. 그 클래스의 **다른 인스턴스를 스스로 만들어** red 를 확인한다.
3. 그 뒤에야 *"닫았다"* 를 말할 수 있다.

**B. 봉인 선언 금지 default (거짓 보고를 막는다)**

뮤테이션 red 는 **"이 뮤테이션을 막았다"** 로만 보고한다. *"fail-open 을 닫았다"* ·
*"클래스를 봉인했다"* 는 **외부 적대 검증 1회를 더 거친 뒤에만** 쓴다.

- **A 와 B 는 다른 것을 막는다** — A 는 결함을, B 는 거짓 보고를. 하나만 지키면 절반이 남는다.
- 🔴 **집행 한계 (정직 기준)**: A 의 *"클래스 내 다른 인스턴스인가"* 는 **정적으로 판정 불가**다.
  형식 검사(뮤테이션 표 2행 이상)는 세탁 가능하므로 **기계 집행을 주장하지 않는다** —
  이것은 write-time 규율이고 방어선은 review-time claim-review 다. 어휘 생존만
  `tests/unit/scripts/test_agents_md_invariant_survival.py` 가 고정한다.

> 위 3 불변식을 **문서로만** 적고 기계 강제(A2 뮤테이션-red)가 없으면 이 파일 자체가
> 문서-only 시정이 된다. 신규 가드는 예외 없이 실경로 뮤테이션 red 로 증명한다.
>
> **정적 탐지의 천장**: 산문 통과를 막는 방어는 아래 3층이며, 완전 자동 탐지기는
> 원리적으로 불가하다(감추지 않고 명시).
>
> 1. **불변식 3(배선)** — `test_guard_wiring_coverage`(실제 호출 관측, 산문 언급 아님).
> 2. **불변식 1 floor** — `check_guard_fail_open.py`(B8): 파일 읽어 판정하는 `scripts/check_*.py`
>    가 구조 도구(ast/re/subprocess)를 **하나도** 안 쓰면 차단.
> 3. **write-time 규율** — `.claude/rules/guards.md`(paths 에 `tests/unit/scripts/**`·
>    `.claude/hooks/**` 포함)가 **실제 실패 표면 편집 시 자동 로드**. 최다 재발 표면은
>    `check_*.py` 가 아니라 **test-as-guard**(`test_analyzer_provenance` · `test_red_budget`)다.
>
> **왜 완전 탐지기를 안 만드는가**: `X in file_text` 는 **마커·존재 검사에 정당하게** 쓰인다
> (B8 자신도 `_ESCAPE in src`). 결정 표현식 substring 을 구문적으로 차단하면 정당한 presence
> 검사까지 막는다(정책 17 — 가드 자살). literal-only 정제는 변수에 담긴 경로
> (`binary in _build_command()`)를 놓친다. fail-open 은 산문의 진위처럼 semantic 이라
> 정적으로 판정 불가 — 남은 방어선은 **review-time Grok claim-review**(불변식 1의 semantic 잔여)다.
>
> **신규 seal 프로세스 규율**: 새 가드/테스트는
> **실경로 뮤테이션-red + `assert mutated != orig`**(불변식 2)를 PR 본문에 실증. 기계 오라클이
> 아니라 저술 규율(guards.md)·리뷰로 강제한다.

---

## 측정 규율 — 도구가 낸 숫자를 사실로 발행하지 않는다

> **위 3-불변식과 별개 축이다.** 이름을 `4번 불변식` 으로 붙이지 않는 이유는
> **적용 술어가 다르기 때문**이다 — 3-불변식은 *가드/테스트 파일을 쓸 때*(경로로 라우팅)
> 적용되지만, 이것은 *숫자나 판정을 내놓을 때* 적용된다. 리포가 `3-불변식` 을
> 이름으로 참조하므로 그 이름의 의미도 바꾸지 않는다.

적용 대상은 **숫자나 판정을 내놓는 모든 것** — 스크래치패드의 1회용 스크립트, 셸 파이프라인,
정규식 한 줄, `git`/`gh` 출력 파싱까지. 이것들은 `.claude/rules` 의 어떤 경로 패턴에도
매칭되지 않는다.

**도구가 틀리는 클래스** (같은 도구로 전후를 재면 양쪽이 같이 틀린다):

| 클래스 | 무엇이 깨지나 |
|---|---|
| 정규식 문자클래스가 너무 좁음 | 식별자를 잘라 건수가 틀린다 |
| 분할 경계가 항목 내부에도 등장 | 항목 수가 부푼다 |
| CRLF 로 목록을 만듦 | 다른 도구가 전건 not-found 로 읽는다 |
| 파이프라인 뒤 종료코드를 안 봄 | 항상 0 → false green |
| passed ↔ collected 혼동 | 단위가 달라 STATE 수치가 틀린다 |

**규칙**:

1. **도구의 출력을 쓰기 전에 도구를 시험한다** — 알려진 정답이 있는 입력에 돌려 본다.
   (예: 전수 목록의 **총합이 이미 아는 값과 맞는가**, 샘플 하나가 실제로 존재하는 심볼인가)
2. **분할·추출은 경계를 반증한다** — 구분자가 데이터 **내부**에 나타날 수 있는지 먼저 센다.
3. **같은 도구로 전후를 재고 "같다"고 하지 않는다** — 도구가 틀렸으면 양쪽이 같이 틀린다.
   무손실 검증은 **도구 무관 방식**(문자 멀티셋·해시)으로 한다.
4. **단위를 명시한다** — chars/bytes/passed/collected/tests/nodes 는 서로 다른 것이다.
5. **뮤테이션이 GREEN 이면 가드 공허를 묻기 전에 뮤테이션 유효성부터** —
   `assert mutated != orig` 없이 "안 잡혔다" 고 결론내지 않는다.

> **왜 불변식인가**: 도구가 틀리면 그 도구로 만든 관측도 틀리므로 **자기 점검이 원리적으로
> 불가능**하다. 그래서 규율로 앞단에서 막는다.

## Claude ↔ Grok 협업 (요약 — 상세 = `docs/runbooks/ai-collaboration.md`)

- **Grok default ON**: 별도 지시 없으면 실질 작업마다 Grok
  **CLAIM-REVIEW**(Claude 주장 반증). 파이프라인 단계가 아니라 claim-review/인터럽트.
- **1순위 사냥 = observer-lie** — 위 핵심 질문. seal/완결/fail-closed/유출-0 주장이 트리거.
- **A2**: 신규 관측자는 실경로 뮤테이션 없이 HOLDS 금지(불변식 2와 동일 — 이것이 SSOT).
- **경계**: Grok 은 정책을 **저술하지 않는다**(claim-review 는 허용).
- 실무: 범위 좁게(2 클레임·400자 — 넓으면 타임아웃) · 절대경로 전달(`/tmp` 가 리포 드라이브로
  해석됨) · Grok 심각도 판단 불신(이진 반증 질문으로 우회).
- 🔴 **집행면 (CI)**: seal 어휘가
  PR 제목·본문·PR 범위 커밋에 있으면 `repo-integrity` 의 `scripts/check_claim_review_trace.py`
  가 구조화 흔적(session/claim/verdict **값**) 없이는 exit 1. 면제 = 본문 줄머리
  `claim-review-not-required: <사유 16자+>` — 사용 시 `::notice` annotation 으로 계량된다.
  🔴 **가드 표면 PR 은 면제 불가**.
  판정 규칙은 두 줄이다:
  1. PR 이 **관측자를 저술하는 표면**(가드 스크립트·훅·워크플로·CI 설정·그 테스트)을
     건드리면 면제 **무효**. 정확한 경로 집합은 `scripts/check_claim_review_trace.py` 의
     `_GUARD_SURFACES` 가 집행하며, 그 값이 곧 판정이다(산문 사본을 두면 갈라진다).
  2. seal 주장 + 코드 표면 변경도 면제 **무효**.
  그 밖(문서 전용 PR 의 인용 · seal 주장 없는 일상 코드 변경)은 면제가 그대로 유효하다.
  🔴 `session` 은 **벤더 중립**(Grok id 또는 워크플로 `wf_…` run id)
  — 단일 벤더 형식만 받으면 그 서비스 장애가 가드 작업을 영구 차단한다.
  가드: `tests/unit/scripts/test_claim_review_mandatory_on_guards.py`.
  본문 판정은 **HTML 주석 스트리핑 후**다(리뷰어 비가시 영역은 흔적/면제로 불인정).
  본문 편집 재검증 = `.github/workflows/claim-review-on-body-edit.yml`. 위조·의미 진위는 원리적으로 못 잡는다
  (가드 docstring §한계 — 그 잔여가 바로 이 문서의 claim-review 프로세스다).
- **판정 착지 규약**: Grok 판정(HOLDS/BROKEN)은 외부 `.md` 기록 → Claude 1회 triage →
  영향 계층 라우팅(`wrong-merge`·`secret`·`fail-open`·`silent-disable` → GitHub Issues).
  상세 = `ai-collaboration.md` §라우팅·§findings 스키마.

## 규칙·정책 어디서 찾나 (grep 진입점)

**작업 전 열어야 할 규칙 — 경로별 표** (Grok 은 auto-load 가 **없다**. 이 표를 건너뛰면 규칙을
건너뛰는 것이다. Claude 도 아래 ⚠️ 행은 경로 매칭이 안 되므로 직접 열어야 한다.)

| 편집 대상 | 반드시 열 것 |
|---|---|
| `src/gate/**` · `src/api/**` · `src/notifier/**` · `src/webhook/**` · `src/github_client/**` · `src/scheduler.py` · `src/main.py` | `api.md` (+ `gate`/`webhook` 은 `pipeline.md` 도) |
| `src/worker/pipeline.py` · `src/analyzer/**` · `src/scorer/**` | `pipeline.md` + ⚠️ `db.md` §WorkerSessionLocal |
| `src/models/**` · `alembic/**` · `src/database.py` · `src/repositories/**` | `db.md` |
| `src/services/**` · `src/verifier/**` · `src/config_manager/**` · `src/railway_client/**` · `src/mcp/**` · `src/cli/**` · `src/shared/**` | `services.md` |
| `src/auth/**` · `src/crypto.py` · `src/shared/{log_safety,ssrf,secure_compare}.py` · `src/api/auth.py` · `src/webhook/validator.py` · `src/main.py` · `src/logging_config.py` | `security.md` |
| `src/templates/**` · `src/static/**` · `src/ui/**` | `ui.md` |
| `src/i18n/**` · `src/middleware/locale.py` · `src/notifier/_language.py` · `src/analyzer/pure/review_guides/**` | `i18n.md` |
| `tests/**` · `e2e/**` · `**/conftest.py` · `pytest.ini` | `testing.md` |
| `scripts/**` · `.claude/hooks/**` · `.claude/workflows/**` · `tests/unit/{scripts,hooks}/**` · `.pre-commit-config.yaml` | `guards.md` + 이 문서 §3-불변식 |
| `docs/**` · `README.md` · `README.ko.md` · `CLAUDE.md` · `AGENTS.md` | `docs.md` |
| `railway.toml` · `nixpacks.toml` · `requirements.txt` · `requirements-dev.txt` · `.env.example` · `.python-version` · `alembic.ini` · `sonar-project.properties` | `deploy.md` |

⚠️ **`db.md` 의 `WorkerSessionLocal` 규칙은 background·시스템 API 모듈을 지배하는데,
`db.md` 의 path 매칭은 그 경로들을 포함하지 않는다** — 즉 그 파일들을 편집할 때 **규칙이 자동으로
오지 않는다**. 목록 정본 = `tests/unit/test_worker_session_routing.py` 의
`_BACKGROUND_MODULES` · `_SYSTEM_API_MODULES`. 위반은 그 테스트가 사후에 잡지만, 작성 시점에
규칙을 못 보면 틀린 코드를 먼저 쓰게 된다.

- 영역별 규칙 원본: `.claude/rules/{testing,db,pipeline,api,security,ui,i18n,deploy,services,guards}.md`
  (Claude 는 매칭 파일 편집 시 자동 로드 / **Grok 은 auto-load 없으므로 위 표를 쓴다**).
  **`guards.md`** = 가드/훅/워크플로 저술 시 로드되는 3-불변식(위 SSOT 의 편집-표면 사본).
- **claim-review 를 수행한다면** `docs/runbooks/ai-collaboration.md` 를 **반드시 연다** —
  findings 계약 · 소유 금지(정책 저술 X) · P0/P1 부여 금지가 거기 있고, 이 문서의
  요약에는 없다.
- 협업 정책 1~19: `CLAUDE.md` (default rule) + `.claude/policies/active.md` (detail).
- 미결 운영 검증·미해결 일감: **GitHub Issues**.
- 현재 수치·상태: `docs/STATE.md`. 아키텍처·가드 배선: `docs/architecture.md`.
