---
description: 가드·훅·워크플로·검증 스크립트를 저술/수정할 때 적용되는 규칙 (path-scoped). 3-불변식(fail-closed·실경로 뮤테이션·배선 테스트)을 이 표면 편집 시 자동 로드해 observer-lie 재발을 예방한다.
paths:
  - "scripts/**"
  - ".claude/hooks/**"
  - ".claude/workflows/**"
  - "tests/unit/scripts/**"
  - "tests/unit/hooks/**"
---

# 가드·훅·워크플로 저술 규칙

> 🔴 이 파일이 자동 로드된다 = 당신은 지금 **가드가 실제로 저술되는 표면**을 편집 중이다.
> 이곳이 이 저장소가 가장 자주 실수하는 곳이다 — #1145 훅이 자기가 없애려던 false-green 을
> **3형태로 재생산**한 게 정확히 이 표면이었다.

## 🔴🔴 3-불변식 (정본 SSOT = [`AGENTS.md`](../../AGENTS.md) — 여기는 요약)

> 🔴 **full 규정·근거는 AGENTS.md 가 단일 body.** 아래는 write-time 리마인더 요약이다(drift 방지 —
> 상세를 여기 재서술하지 않는다). 저술 前 AGENTS.md §3-불변식을 정본으로 볼 것.

새 가드/훅/워크플로/검증 스크립트 저술 시 **예외 없이**:

1. **fail-closed** — 통과가 산문/echo/advisory 로 충족되면 안 됨.
   ❌ `binary in build_text`(echo 산문 통과·#1136) · `"사용자 회신" in row`("대기" 통과·#1156).
   ✅ AST(`ast.Call`·`ast.walk`) 실제 호출/값, 또는 실행 결과 관측. 자문: *주석·docstring·echo 로 통과 가능한가?*
2. **실경로 뮤테이션** — 합성 픽스처 금지. 실파일/심볼을 깨뜨려 red 관측 + `assert mutated != orig`(#1121).
3. **배선 테스트** — 정의≠배선, 순수함수 옳음≠진입점 도달(#1145). 산문 grep 아닌 실제 실행/호출 관측 +
   "실제 게이트(ci/pre-commit/SessionStart/PostToolUse)에 배선됐나" 동반 검증.

🔴 **신규 seal 프로세스 규율 (정적 오라클로 완전 자동화 불가 — Grok 확정)**: fail-open 은 산문
진위처럼 semantic 이라 구문적 완전 탐지기는 오탐>진탐(guard-suicide). 대신 **새 가드/테스트는
PR 본문에 실경로 뮤테이션-red + `assert mutated != orig`(불변식 2) 실증** 을 규율로 강제한다.
`check_guard_fail_open`(B8)은 floor(구조 도구 0)만 자동 차단 — 결정이 bare substring 인 semantic
잔여는 review-time claim-review(Grok)가 방어선. 천장 상세: [`AGENTS.md`](../../AGENTS.md) §정적 탐지의 천장.

## 🔴 배선 단언은 `_wiring_shape` 술어 의무 (2026-07-31 — substring 배선 판정 11건 fail-open 실측)

"이 가드가 배선됐나" 를 단언할 때 **`"<경로>" in <명령>` substring 금지**. 반드시
`tests/unit/scripts/_wiring_shape` 의 `invokes` / `any_invokes` / `surface_invokes` 를 쓴다.

- ❌ `assert any("check_x.py" in c for c in commands)` — `echo 'skipping scripts/check_x.py'` 통과
- ✅ `assert any_invokes(commands, "scripts/check_x.py")` — 명령어가 인터프리터여야 통과

**근거(실측)**: 배선 단언 10곳이 전부 substring 이었고, 격리 worktree 에서 보호 장치를 `echo` 로
중성화한 실경로 뮤테이션 12건 중 **11건이 GREEN**(`tests/unit/scripts`+`tests/unit/hooks` 498건
전부 초록). 무력화 대상에 SessionStart 카운터 2종 · 시크릿 덤프 차단 훅 · repo-integrity 백스톱
4종 · 정책 19 claim-review 집행면이 포함됐다. `#1243` 이 훅 command 6종을
`python X` → `PY=$(...); $PY X` 로 재작성했을 때 가드가 그 재작성과 `echo X` 를 **구별하지 못한
것**이 이 클래스의 실제 발동 경로다.

🔴 **술어가 잡지 못하는 것**(정직 기준): 조건부 skip 된 CI step · 배선됐으나 공허한 가드 본문 ·
`env A=b python x.py` / `sh -c "…"` / backtick / `eval` / `export PY=` / 따옴표 할당(`PY='python3'`)
같은 **allowlist 밖 호출 형태**(fail-closed 라 *거부*된다 — 그런 형태로 새 배선을 쓰면 이 술어가
실배선을 거부한다). 이 술어는 **"실행 연결이 끊겼는데 초록"** 만 끝낸다.

🔴 **인터프리터의 런타임 부재는 별도 축이다** — 형태상 `python X` 는 정당하므로 이 술어는
bare `python` 회귀(Windows Store 스텁 exit 49)를 **구별하지 못한다**. 그 축은
`tests/unit/scripts/test_hook_interpreter_liveness.py` 가 **실제 실행**으로 닫는다.
그 프로브의 오라클은 **Python 만 낼 수 있는 계산 결과**(`print(6*7)` → `42` 정확 일치)여야 한다 —
마커 문자열을 출력시키고 "출력에 마커 포함" 으로 보면 `echo` 가 **명령 텍스트를 되돌려주며**
통과한다(2026-08-01 실측 defeat).

🔴 **판정 정밀도 3 규칙**(2026-08-01 Grok claim-review `019fbaf8` 적발 — 전부 실측 defeat):
1. **경로는 경계에서만 일치** — 맨 `endswith` 는 `not_scripts/check_x.py` 를 `scripts/check_x.py`
   의 배선으로 오판한다(배선을 **다른 파일로 갈아끼워도** 초록).
2. **죽은 단락평가 분기는 배선 아님** — `true || python x.py` 는 텍스트를 한 글자도 지우지 않고
   중성화하는 수법이다. 단 **상수 명령(`true`/`:`/`false`)이 앞선 경우만** 죽었다고 본다 —
   실제 종료 코드 예측은 정적으로 불가하고, 무리하면 `set -e && python x.py` 같은 실배선을
   거부한다(정책 17).
3. **변수는 셸과 같이 last-wins** — "모든 할당이 인터프리터" 규칙은 `PY=echo; PY=python3; $PY x.py`
   (셸에서 python3 이 실제로 도는 형태)를 거부해 **가드 자살**이었다. 단 `$(...)` 치환 내부는
   분기마다 값이 달라지므로 **모든 후보**가 인터프리터여야 한다.

🔴 **기대값을 피검사 모듈에서 유도하지 말 것**(자기참조 공허화) — `doc_review_gate` 컨텍스트
가드가 기대 원천 목록을 `_CONTEXT_SOURCES` 에서 읽었더니 **원천을 삭제하면 루프가 안 돌아
GREEN** 이었다(뮤테이션 실측). 기대값은 테스트 쪽에 고정하고, 지문(fingerprint)도 **그 원천에만
있는 문구**를 쓴다 — `"3-불변식"` 은 CLAUDE.md 에도 2회 나와서 AGENTS.md 제거를 못 잡았다.

🔴 **B8 스캔 범위 = `scripts/check_*.py` + `.claude/hooks/*.py`** (R16 — 2026-08-02 훅 표면
확대, 오탐 0 실측 후). 표면 중 하나라도 glob 0건이면 **범위 붕괴로 exit 1**(빈 범위 위의 ✅ 는
GROK-9 뮤테이션이 실증한 fail-open 이었다). 성공 배너도 실제 스캔 범위를 명시한다.
🔴 **여전히 범위 밖**: **test-as-guard(`tests/**/test_*.py`)의 fail-open 은 자동 탐지되지
않는다** — AGENTS.md 가 기록한 최다 재발 사고(`#1136`·`#1156`)가 바로 그 표면이다
(`X in text` 는 정당한 presence 검사에도 흔해 확대 시 오탐>진탐 = 가드 자살, 정책 17).
이 표면은 write-time 규율(이 파일)과 review-time claim-review 로만 방어된다.

## 🔴 lint-js 검사 범위는 baseline 원장과 대조된다 (R17 — 2026-08-02)

`check_lint_js_nonvacuous.py` 는 정당 제외(justified) 집합을 커밋된
`scripts/lint_js_ignore_baseline.json` 과 대조한다 — 템플릿 `<script>` 에 무해한 Jinja 유사
토큰(`// {{ 1 }}`)을 심어 "정당 제외" 로 위장하는 우회(뮤테이션 GROK-12: 검사 대상 6→5 인데
EXIT=0)를 **baseline diff 없는 한 red** 로 만든다. 제외 집합을 바꾸는 변경은
`py -3 scripts/check_lint_js_nonvacuous.py --update-baseline` 결과를 **같은 PR 에** 포함할 것.
한계(정직 기준): 같은 PR 이 baseline 도 고치면 통과한다 — 이 축은 감소를 막지 않고 리뷰
가능한 명시 결정으로 승격할 뿐이며, 잔여는 review-time claim-review 가 방어한다.

## 🔴 push 전 로컬 게이트 = `py -3 scripts/pre_push_gate.py` (2026-08-01 신설)

새 가드를 저술했으면 **push 전에 이걸 돌린다.** CI 가 강제하는 repo-integrity 9종 +
PR-diff 한정 4종을 `make` 없이 실행한다.

- 🔴 **`make gate` 는 대체가 아니었다** — 그 타깃은 pytest·pylint·bandit 뿐이라 위 13 가드를
  **하나도** 돌리지 않는다. 게다가 이 개발 머신에는 `make` 자체가 없다(`command not found`).
  한 세션에서 `Block new dual-import` 에 **두 번** 걸렸고 두 번 다 로컬은 초록이었다(backlog R29).
- 🔴 **CI 에 가드를 추가하면 러너 목록도 갱신해야 한다** — 손유지 목록이 CI 와 갈라지면
  "로컬 초록" 이 아무것도 뜻하지 않게 된다. 회귀 가드
  `tests/unit/scripts/test_pre_push_gate.py::test_runner_covers_every_ci_guard_script` 가
  기대값을 **`ci.yml` 실파일에서 파싱**해 대조한다(작성 당시 실제 누락 2건을 적발했다).
- 🔴 **러너가 보지 못하는 축을 매 실행 인쇄한다**(CodeQL·Sonar·Codecov·TruffleHog·pip-audit·
  lint-js·PG job·통합테스트). "여기 초록 = CI 초록" 으로 읽히면 러너 자신이 새 observer-lie 다.
- advisory 가드(`check_test_count_sync --advisory-drift`)는 **exit 0 이면서 경고**하므로
  출력을 항상 표시한다 — 실패 시에만 인쇄하면 그 경고가 삼켜진다.
- 🔴 **`.pre-commit-config.yaml` 에 `stages: [pre-push]` 를 적는 방식은 기각됐다**
  (2026-08-01 Grok 설계 검토 `019fbc8e`) — pre-commit 이 그 훅 타입을 **따로 설치**해야
  동작하므로(`pre-commit install --hook-type pre-push`), 미설치 머신에서는 **한 번도 안 도는
  가드**가 된다. 이 리포가 반복해 고쳐 온 클래스를 새로 만드는 셈이다.
  대신 **로컬 `.git/hooks/pre-push`**(git 미추적 = 머신 고유)로 자동화하고, 그 존재 여부를
  `check_precommit_installed.py`(SessionStart, 실증된 채널)가 **관측**한다. 리포는 로컬 훅을
  강제할 수 없으므로 관측이 할 수 있는 전부다 — 진짜 집행면은 CI 다.

## 🔴 required status check 는 (SHA, 이름) 으로 식별된다 (2026-08-01)

PR 본문만 고쳤을 때 CI 를 다시 돌리려고 워크플로를 추가한다면:

- **같은 job `name:`** 을 써야 required check 가 **갱신**된다. 다른 이름이면 새 check 만 하나
  더 생기고 이전 빨간 check 는 그대로 남아 머지가 계속 막힌다.
- **같은 워크플로에서 형제 job 을 `if` 로 skip 시키지 말 것** — skip 은 성공으로 취급돼
  **직전에 실패한 required check 를 세탁**할 수 있다(fail-open). 별도 워크플로 + 단일 job 이 안전.
- 같은 이름을 쓰면 **step 목록도 원본과 같아야** 한다. 아니면 그 check 가 자기 의미보다 적은
  것을 검증하고도 초록이 된다. 형태 가드: `test_claim_review_body_edit_workflow.py`.
- `gh run rerun` 은 **원래 이벤트 payload**(옛 본문)를 재생하므로 본문 수정 검증에 쓸 수 없다.

## 🔴 훅 출력 채널 — `print()` 는 Claude 에게 도달하지 않는다 (2026-08-01 공식 계약 확인)

**PreToolUse/PostToolUse 훅의 plain stdout 은 디버그 로그로만 간다.** exit 0 의 stdout 이
Claude 컨텍스트가 되는 이벤트는 `UserPromptSubmit` · `UserPromptExpansion` · `SessionStart`
**셋뿐**이다. 실측도 일치했다 — `doc_review_gate` 의 advisory 배너가 CRITICAL 문서 3회
편집에서 에이전트 도구 결과에 **0회** 출현(그 고지는 theatre 였다).

| 목적 | 필드 | 대상 |
|---|---|---|
| Claude 가 보게 하려면 | `hookSpecificOutput.additionalContext` | 에이전트 |
| 사용자가 보게 하려면 | `systemMessage` (top-level) | 터미널 UI |
| 차단하려면 | `hookSpecificOutput.permissionDecision: "deny"` + `…Reason` | — |

🔴 **advisory 고지에 `permissionDecision` 을 얹지 말 것** — `"allow"` 는 사용자 권한 확인을
**건너뛸 수 있다**. `additionalContext` 는 권한 결정과 **독립**이라 미설정이면 정상 흐름이 유지된다.
회귀 가드: `test_advisory_never_carries_a_permission_decision`.

🔴 **SessionStart 로 이관하는 것은 해답이 아니다**(검토 후 기각) — SessionStart 는 세션당 1회라
세션 중간에 키 만료/취소가 나면 **stale-green** 이 된다. *"안 보이지만 live"* 가
*"보이지만 stale"* 보다 낫고, 올바른 답은 **live 하면서 보이게** 하는 `additionalContext` 다.

🔴 **텍스트 단언은 채널 회귀를 못 잡는다** — `assert "MARKER" in capsys.out` 은 bare `print` 로
되돌려도 통과한다. **JSON 형태를 파싱해 단언**할 것(실측: 이 파일의 초판 테스트가 정확히 그랬다).

## 🔴 뮤테이션 유효성 — `mutated != orig` 는 필요조건일 뿐이다

`assert mutated != orig`(불변식 2)를 통과해도 **동작이 안 바뀌는 뮤테이션**이 있다.
실측: `json.dumps(payload, ensure_ascii=True)` → `json.dumps(payload)` 는 **텍스트가 바뀌지만
기본값이 이미 `True`** 라 동작 무변경 → GREEN 을 fail-open 으로 오독할 뻔했다. 진짜 회귀는
`ensure_ascii=False` 로 **뒤집는** 것이었고 그건 즉시 RED 였다.

**default 적용**: 뮤테이션이 GREEN 이면 *"가드가 공허한가"* 를 묻기 **전에**
*"이 뮤테이션이 동작을 실제로 바꾸는가"* 를 먼저 확인한다. 기본값·no-op·죽은 분기를 건드리는
뮤테이션은 아무것도 증명하지 않는다.

## 스크립트 관용구 (이 표면 전용)

- 🔴 **stdout UTF-8 가드 의무** — `scripts/*.py` 는 전부 `_make_stdout_safe()`/`reconfigure` 호출
  (Windows cp949 에서 비-ASCII 출력 시 크래시). 회귀 가드: `test_stdout_encoding_guard.py`(전 스크립트 강제).
- **standalone 실행** — `scripts/` 는 `__init__.py` 없이 `python scripts/x.py` 로 실행(pre-commit·CI·
  SessionStart 훅). 공유 모듈 import 는 `sys.path` 조작 필요 → 검증된 관용구 복제, 누락은 테스트가 막음.
- **advisory vs blocking 명시** — 훅/스크립트가 exit 0(비차단 advisory)인지 exit 1(차단)인지 docstring 에
  명시. advisory 는 "가드는 있는데 아무것도 안 막는" 클래스를 만들 수 있으니 그 한계를 적는다(#1156).

## 워크플로(`.claude/workflows/*.mjs`) 규칙

- loop-until-dry 정본 = `_lib/loop-until-dry.template.mjs` (drift 가드: `test_workflow_loop_sync.py`).
- `Date.now()`·`Math.random()`·argless `new Date()` 사용 금지(resume 파손) — 타임스탬프는 args 로 주입.
- cross-verify=finding 강제(verdict_coverage 지표). 스킬은 워크플로를 감싸는 얇은 런처.
