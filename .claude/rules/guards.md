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

## 🔴 훅이 LLM 을 부르면 프롬프트 캐시는 **순서** 문제다 (R38 — 2026-08-04)

`cache_control` 마커를 붙였다는 사실만으로는 아무것도 보장하지 않는다. 캐시는 프리픽스
매칭이라 **가변 부분이 캐시 구간보다 앞에 있으면 매 요청이 새 항목을 쓰고 읽지는 못한다** —
비용이 오히려 1.25배가 된다. 렌더 순서는 `tools → system → messages` 이고, `cache_control`
은 그 블록까지의 **프리픽스 전체**를 캐시한다.

`doc_review_gate` 의 배치(문서 편집 1회 = 에이전트 3 호출):

| 위치 | 내용 | 캐시 |
|---|---|---|
| `system[0]` | 참조 컨텍스트(53,587자) — 3 에이전트 공통 | ✅ breakpoint |
| `system[1]` | 에이전트별 지시 — 서로 다름 | — |
| `user` | diff — 편집마다 다름 | — |

- **breakpoint 를 `system[0]` 에 거는 이유**: 캐시 구간이 '공통 부분' 하나로 끝나 **3 에이전트가
  같은 항목을 공유**한다. `system[1]` 에 걸면 에이전트마다 별개 항목이 되어 공유가 깨진다.
- 🔴 **최소 캐시 길이는 모델마다 다르고 단조롭지 않다** — `claude-haiku-4-5` 는 **4096 토큰**으로
  전 모델 중 가장 크다. 미달이면 **오류 없이 조용히** 캐시되지 않는다(`cache_creation_input_tokens`
  가 0). 컨텍스트 예산을 줄이는 변경은 이 하한을 함께 확인할 것.
- 🔴 **병렬 호출은 첫 편집에서 전부 miss** — 캐시 항목은 첫 응답이 스트리밍을 시작해야 읽을 수
  있는데 3 에이전트는 동시에 나간다. 이득은 **2회차 편집부터** 나온다(TTL 5분).
- **반증 수단**: 마커 존재가 아니라 `usage.cache_read_input_tokens` 가 2회차에 0이 아닌지 볼 것.
  구조 회귀는 `tests/unit/hooks/test_doc_review_gate.py::TestPromptCache` 가 고정한다.
- **실측 (2026-08-04)**: 1회차 `write=34,748 · read=0` ×3 → 2회차 `write=0 · read=34,748` ×3.
  🔴 **이 숫자가 증명하는 것과 아닌 것을 구분할 것** — 증명되는 것은 *캐시가 동작한다*(2회차
  입력의 ~96%가 캐시에서 옴). 증명되지 **않는** 것은 *3 에이전트가 항목 하나를 공유한다*:
  `usage` 에는 캐시 항목 식별자가 없어 '항목 1개를 3번 읽음' 과 '같은 크기 항목 3개를 각각
  읽음' 이 외부에서 구별되지 않는다. 공유는 **설계상 그렇다**(프리픽스 바이트+모델이 캐시 키
  이고 3 요청의 프리픽스가 동일)일 뿐 관측된 사실이 아니다. 1회차가 `write ×3` 인 것도
  같은 이유로 자연스럽다 — 병렬이라 셋 다 쓴다.
- **opt-out**: `DISABLE_PROMPT_CACHE=1` (`docs/reference/env-vars.md` 등재분과 같은 변수).

## 🔴 lint-js 검사 범위는 baseline 원장과 대조된다 (R17 — 2026-08-02)

`check_lint_js_nonvacuous.py` 는 정당 제외(justified) 집합을 커밋된
`scripts/lint_js_ignore_baseline.json` 과 대조한다 — 템플릿 `<script>` 에 무해한 Jinja 유사
토큰(`// {{ 1 }}`)을 심어 "정당 제외" 로 위장하는 우회(뮤테이션 GROK-12: 검사 대상 6→5 인데
EXIT=0)를 **baseline diff 없는 한 red** 로 만든다. 제외 집합을 바꾸는 변경은
`py -3 scripts/check_lint_js_nonvacuous.py --update-baseline` 결과를 **같은 PR 에** 포함할 것.
한계(정직 기준): 같은 PR 이 baseline 도 고치면 통과한다 — 이 축은 감소를 막지 않고 리뷰
가능한 명시 결정으로 승격할 뿐이며, 잔여는 review-time claim-review 가 방어한다.

## 🔴 뮤테이션 복원 순서 — `git add` 를 먼저 (R15 가드 검증 중 실제 발생, 2026-08-04)

`git checkout -- <파일>` 은 HEAD 가 아니라 **staging area(index)** 에 있는 내용을 되살린다.
따라서 방금 쓴 편집을 `git add` 하지 않은 채 뮤테이션→복원을 돌리면, 복원이 뮤테이션뿐
아니라 **내가 쓴 편집까지 지운다**. 그 다음 뮤테이션은 이미 원본으로 돌아간 파일을 건드리므로
red 가 떠도 그건 내 뮤테이션이 만든 red 가 아니다.

실측: `check_dependency_pins` 검증에서 1번째 복원이 파일을 구값으로 되돌려 놓는 바람에
3번째 뮤테이션(검사 범위 붕괴)이 **실행되지 않은 채 red 로 보였다**. stage 후 재측정해 4종을
다시 확인했다.

```bash
git add -A                      # ① 기준선을 index 에 고정 — 이 상태로 복원된다
sed -i 's/OLD/NEW/' target.md   # ② 뮤테이션
git diff --quiet target.md || echo "mutated != orig OK"   # ③ 실제로 바뀌었는지 확인
pytest ...                      # ④ red 관측
git checkout -- target.md       # ⑤ ① 의 기준선으로 복원
pytest ...                      # ⑥ baseline 이 다시 green 인지 확인
```

CRLF 축(윈도우에서 `write_text` 왕복이 파일을 변경 상태로 남기는 문제)은 별개이며
[[feedback-mutation-restore-crlf]] 가 정본이다.

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

## 🔴 훅 **입력** 디코딩 — `json.load(sys.stdin)` 금지 (2026-08-04)

아래 "훅 출력 채널" 규칙의 **입력 쪽 짝**이다. 출력이 Claude 에게 닿는지를 그 규칙이 다루듯,
이 규칙은 **입력이 훅에게 온전히 닿는지**를 다룬다.

`json.load(sys.stdin)` 는 텍스트 모드라 인터프리터의 stdin 인코딩에 의존한다.
**실훅 자식 프로세스 계측 (2026-08-04)**: `stdin.encoding=cp949` · `errors=surrogateescape` ·
`utf8_mode=0` · `PYTHONUTF8`/`PYTHONIOENCODING` 미설정. 결과가 둘 겹친다 —
(1) 한글이 **mojibake** 가 되고(`'문서 정합 가드'` 8자 → 13자), (2) 디코드 불가 바이트가
**lone surrogate** 로 escape 돼 이후 httpx UTF-8 인코딩에서 터진다.

- **정답**: `getattr(sys.stdin, "buffer", sys.stdin).read()` 로 바이트를 읽어 UTF-8 로 직접
  디코드(`doc_review_gate.read_payload`). `.buffer` 부재(StringIO 패치)는 텍스트 폴백.
- 🔴 **`#1276` 과의 관계**: 그 PR 이 봉인한 lone surrogate 의 **발생원이 이 디코드였다**.
  `_scrub_surrogates` 는 증상을 지웠고 원인은 남아 있었다 — 그래서 mojibake 심의가 계속됐다.
- 🔴 **진단 절차 — 반드시 실훅을 계측한다**: 셸에서 손으로 띄운 python 은 다른 환경이다
  (부모가 `PYTHONUTF8` 을 심으면 값이 달라진다). 훅 안에서 `sys.stdin.encoding` ·
  `sys.flags.utf8_mode` · 원문 길이를 파일로 덤프한 뒤 실제 편집을 1회 발생시켜 읽는다.
  이번에도 셸 측정과 Grok 측정이 엇갈렸고, **실훅 계측만이 결판을 냈다**.
- 🔴 **왕복 착시**: 잘못 디코드한 문자열을 같은 잘못된 인코딩으로 출력하면 원 바이트가
  복원된다 — "출력이 멀쩡하다" 는 증거가 아니다. **길이·코드포인트로 단언**할 것.
- 회귀 가드: `tests/unit/hooks/test_doc_review_gate.py::TestReadPayload` — 뮤테이션 4종
  (배선 되돌림 · **죽은 호출** · `json.loads(sys.stdin.read())` 한 글자 우회 · 텍스트 모드 읽기)
  전부 red. AST 존재 검사만으로는 죽은 호출이 통과하므로 **에이전트에 닿는 diff 를 직접
  검사하는 E2E 단언**을 함께 둔다.

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
