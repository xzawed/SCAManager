---
description: 가드·훅·워크플로·검증 스크립트를 저술/수정할 때 적용되는 규칙 (path-scoped). 3-불변식(통과가 산문으로 충족되면 안 됨·실경로 뮤테이션·배선 테스트)을 이 표면 편집 시 자동 로드한다.
paths:
  - "scripts/**"
  - ".claude/hooks/**"
  - ".claude/workflows/**"
  - "tests/unit/scripts/**"
  - "tests/unit/hooks/**"
---

# 가드·훅·워크플로 저술 규칙

> 이 파일이 자동 로드된다 = 지금 **가드가 저술되는 표면**을 편집 중이다.
>
> **먼저 열 것 2건**:
> · 순서 = [`docs/process/guard-authoring.md`](../../docs/process/guard-authoring.md)
> · 함정 = [`.claude/traps.md`](../traps.md)
>
> 아래는 **이 표면에만 있는 세부 계약**이다. 일반 실패 클래스는 위 두 곳이 정본이다.

## 3-불변식 (정본 SSOT = [`AGENTS.md`](../../AGENTS.md) — 여기는 요약)

> full 규정은 AGENTS.md. 여기는 write-time 리마인더다. 저술 전 AGENTS.md §3-불변식을 연다.

새 가드/훅/워크플로/검증 스크립트:

1. **통과가 산문·echo·advisory 로 충족되면 안 된다.**
   ❌ `binary in build_text` · `"사용자 회신" in row` (주석·echo·"대기" 문구가 통과시킴)
   ✅ `ast.Call`/`ast.walk` 또는 실행 결과. 자문: *주석·docstring·echo 로 통과 가능한가?*
2. **실경로 뮤테이션** — 합성 픽스처 금지. 실파일/심볼을 깨뜨려 red + `assert mutated != orig`.
3. **배선 테스트** — 정의 ≠ 배선. 산문 grep 이 아니라 실제 실행/호출 + 게이트(ci/pre-commit/SessionStart/PostToolUse)에 붙었는지.

**신규 관측자**: 정적 오라클로 완전 자동화할 수 없다 (semantic). 대신 PR 본문에 실경로 뮤테이션-red + `assert mutated != orig` 를 적는다. `scripts/check_guard_fail_open.py` 는 구조 도구 0개인 `scripts/check_*.py`·`.claude/hooks/*.py` 만 막는다. 결정이 bare substring 인 잔여는 review-time claim-review.

## 배선 단언은 `_wiring_shape` 술어

"`<경로>` in `<명령>`" substring 금지. `tests/unit/scripts/_wiring_shape` 의 `invokes` / `any_invokes` / `surface_invokes` 를 쓴다.

- ❌ `assert any("check_x.py" in c for c in commands)` — `echo 'skipping scripts/check_x.py'` 통과
- ✅ `assert any_invokes(commands, "scripts/check_x.py")` — 인터프리터가 그 파일을 실행해야 통과

이 술어가 **안 보는 것**: 조건부 skip 된 CI step · 배선됐으나 공허한 본문 · `env A=b python x.py` / `sh -c` / backtick / `eval` / `export PY=` / 따옴표 할당. allowlist 밖 형태는 **거부**한다 (새 배선을 그 형태로 쓰면 실배선도 거부된다). 잡는 것은 **"실행 연결이 끊겼는데 초록"** 뿐이다.

🔴 **인터프리터 런타임 부재는 별도 축** — 형태상 `python X` 는 정당하므로 이 술어는 bare `python`(Windows Store 스텁 exit 49)을 구별하지 못한다. `tests/unit/scripts/test_hook_interpreter_liveness.py` 가 **실행**으로 본다. 오라클은 Python 만 낼 수 있는 결과여야 한다 (`print(6*7)` → `42` 정확 일치). 마커 문자열이 출력에 "포함"인지는 `echo` 가 명령 텍스트를 되돌려 통과한다.

**판정 정밀도** (`tests/unit/scripts/_wiring_shape`):

1. **경로는 경계에서만** — 맨 `endswith` 는 `not_scripts/check_x.py` 를 오인한다.
2. **죽은 단락평가 분기는 배선 아님** — `true || python x.py`. 상수 명령(`true`/`:`/`false`)이 앞선 경우만 죽은 것으로 본다. 실제 종료 코드 예측은 정적으로 불가 — `set -e && python x.py` 같은 실배선을 거부하지 말 것.
3. **변수는 셸과 같이 last-wins** — "모든 할당이 인터프리터"는 `PY=echo; PY=python3; $PY x.py` 를 거부해 가드가 자해한다. `$(...)` 안은 분기마다 값이 달라지므로 **모든 후보**가 인터프리터여야 한다.

**기대값을 피검사 모듈에서 유도하지 말 것.** `doc_review_gate` 컨텍스트 목록을 `_CONTEXT_SOURCES` 에서 읽으면 원천을 지워도 루프가 안 돌아 초록이다. 기대값은 테스트에 고정하고, 지문은 **그 원천에만 있는 문구**를 쓴다 (`"3-불변식"` 은 CLAUDE.md 에도 있어 AGENTS.md 제거를 못 잡는다).

**B8 스캔 범위** = `scripts/check_*.py` + `.claude/hooks/*.py` (`scripts/check_guard_fail_open.py`). glob 이 한쪽이라도 0건이면 범위 붕괴로 exit 1. 성공 배너에 실제 스캔 범위를 적는다.

**범위 밖**: `tests/**/test_*.py` 의 substring 통과는 자동 탐지하지 않는다 (`X in text` 는 정당한 presence 검사에도 흔해 확대 시 오탐>진탐). 그 표면은 이 파일의 write-time 규율 + claim-review.

## 훅이 LLM 을 부르면 캐시는 순서 문제다

`cache_control` 마커만으로는 아무것도 보장하지 않는다. 캐시는 프리픽스 매칭이라 **가변 부분이 캐시 구간보다 앞이면** 매 요청이 새 항목을 쓰고 읽지 못한다.

렌더 순서 = `tools → system → messages`. `cache_control` 은 그 블록까지 프리픽스 전체.

현재 `doc_review_gate` 배치 (`.claude/hooks/doc_review_gate.py` — breakpoint 2개):

| 블록 | 내용 | breakpoint |
|---|---|---|
| `system[0]` | CLAUDE.md + AGENTS.md (안정) | 있음 |
| `system[1]` | docs/STATE.md (가변) | 있음 |
| `system[2]` | 에이전트별 지시 | 없음 |

- breakpoint 를 `system[0]` 에 거는 이유: 3 에이전트가 같은 안정 프리픽스를 공유한다. `system[1]` 에만 걸면 에이전트마다 항목이 갈린다.
- 최소 캐시 길이는 모델마다 다르고 단조롭지 않다. `claude-haiku-4-5` 는 4096 토큰. 미달이면 오류 없이 `cache_creation_input_tokens=0`.
- 🔴 **병렬 호출은 첫 편집에서 전부 miss** — 항목은 첫 응답이 스트리밍을 시작해야 읽을 수 있다. 이득은 2회차부터 (TTL 5분).
- 반증: 마커가 아니라 `usage.cache_read_input_tokens` 가 2회차에 0이 아닌지. 구조 회귀 = `tests/unit/hooks/test_doc_review_gate.py::TestPromptCache`.
- `usage` 에는 항목 식별자가 없다. "한 항목을 3번 읽음"과 "같은 크기 항목 3개"는 외부에서 구별되지 않는다. 공유는 설계(동일 프리픽스+모델)이지 관측된 사실이 아니다.
- opt-out: `DISABLE_PROMPT_CACHE=1` (`docs/reference/env-vars.md`).

**관측 지표를 mock 으로 주입하면 배선을 증명하지 않는다.** `_usage` 를 테스트가 넣으면 생산 경로의 부착을 지워도 초록이다. `test_usage_is_attached_by_the_call_site_not_only_by_mocks` 가 생산 경로를 본다.

**고장 감지는 의도한 설정에서 켜지면 안 된다.** `DISABLE_PROMPT_CACHE=1` 이면 회계 0/0 이 정상이다.

**가변 원천은 안정 프리픽스에서 분리한다.** STATE 는 trailing sync 마다 바뀌고 CLAUDE.md·AGENTS.md 는 거의 안 바뀐다. 한 블록에 섞으면 STATE 한 번이 안정 원천까지 무효화한다. STATE 를 컨텍스트에서 **빼지 않는다** — 심의자가 수치를 못 본다. breakpoint 는 요청당 최대 4개, 여기서는 2개.

훅은 `PreToolUse` 라 **편집 적용 전** 디스크를 읽는다. STATE 를 고치는 편집 자체는 옛 내용으로 hit 하고, 새 내용은 **다음** 편집에 반영된다.

회귀: `TestPromptCache::test_stable_block_is_unchanged_when_only_the_volatile_source_changes` · `test_split_context_keeps_state_out_of_the_stable_part` (경로 문자열이 아니라 섹션 헤더 `=== docs/STATE.md ` — CLAUDE.md 본문이 그 경로를 산문으로 언급함).

**소스 일괄 치환**: `Path.write_text` 는 인코딩 전에 truncate 한다. lone surrogate 가 섞이면 파일이 0바이트가 된다. (a) 편집 전 `git add` 로 기준선 (b) 가능하면 Edit 툴 (c) 스크립트면 `s.encode("utf-8")` 를 먼저.

## lint-js 범위는 baseline 원장과 대조

`scripts/check_lint_js_nonvacuous.py` 는 정당 제외 집합을 커밋된 `scripts/lint_js_ignore_baseline.json` 과 대조한다. 템플릿 `<script>` 에 무해한 Jinja 유사 토큰을 심어 제외를 위장하면, baseline diff 없이 통과하지 못한다. 제외 집합을 바꾸면 `py -3 scripts/check_lint_js_nonvacuous.py --update-baseline` 결과를 **같은 PR** 에 넣는다.

한계: 같은 PR 이 baseline 도 고치면 통과한다. 감소를 막지 않고 리뷰 가능한 결정으로 올릴 뿐이다.

## 뮤테이션 복원 — `git add` 를 먼저

`git checkout -- <파일>` 은 HEAD 가 아니라 **index** 를 되살린다. 방금 쓴 편집을 stage 하지 않고 뮤테이션→복원하면 **편집까지 지워진다**.

```bash
git add -A                      # ① 기준선을 index 에 고정
sed -i 's/OLD/NEW/' target.md   # ② 뮤테이션
git diff --quiet target.md || echo "mutated != orig OK"
pytest ...                      # ④ red
git checkout -- target.md       # ⑤ ① 로 복원
pytest ...                      # ⑥ baseline green
```

Windows `write_text` CRLF 왕복은 별개 — [[feedback-mutation-restore-crlf]].

## push 전 로컬 게이트 = `py -3 scripts/pre_push_gate.py`

CI 가 강제하는 repo-integrity 가드(`_INTEGRITY` + `_INTEGRITY_WITH_ARGS`)와 PR-diff 한정 가드(`_DIFF_SCOPED` + flake8 F401/F841)를 `make` 없이 실행한다. **개수는 여기 적지 않는다 — 목록 정본은 `scripts/pre_push_gate.py` 의 그 튜플들이다**(2026-08-17 정정: 이 줄은 「repo-integrity 9종 + PR-diff 한정 4종 … 이 13종」 이라 적혀 있었고 실측은 13 + 4 = 17 이었다 — CLAUDE.md 가 금지한 개수 복제를 여기서 하고 썩혔다). `make gate` 는 pytest·pylint·bandit 뿐이라 이 가드들을 돌리지 않는다. 이 개발 머신에는 `make` 자체가 없을 수 있다.

- 🔴 **CI 에 가드를 추가하면 러너 목록도 갱신** — `tests/unit/scripts/test_pre_push_gate.py::test_runner_covers_every_ci_guard_script` 가 기대값을 `.github/workflows/ci.yml` 에서 파싱한다.
- 러너가 못 보는 축(CodeQL·Sonar·Codecov·TruffleHog·pip-audit·lint-js·PG job·통합테스트)을 **매 실행 인쇄**한다. "여기 초록 = CI 초록" 으로 읽히면 러너 자신이 거짓 관측이다.
- advisory (`check_test_count_sync --advisory-drift`) 는 exit 0 + 경고이므로 출력을 항상 보여 준다.
- 🔴 **`.pre-commit-config.yaml` 에 `stages: [pre-push]` 는 쓰지 않는다** — `pre-commit install --hook-type pre-push` 가 따로 필요하다. 미설치 머신에서는 한 번도 안 돈다. 대신 로컬 `.git/hooks/pre-push`(미추적) + `scripts/check_precommit_installed.py`(SessionStart, 관측만). 집행면은 CI.

## required status check 는 (SHA, 이름)

PR 본문만 고치고 CI 를 다시 돌리려면:

- **같은 job `name:`** — 다른 이름이면 새 check 만 생기고 이전 빨간 check 가 남아 머지가 막힌다.
- **같은 워크플로에서 형제 job 을 `if` 로 skip 하지 말 것** — skip 은 성공으로 취급돼 직전 실패를 세탁한다. 별도 워크플로 + 단일 job.
- 같은 이름이면 **step 목록도 원본과 같아야** 한다. 형태: `tests/unit/scripts/test_claim_review_body_edit_workflow.py`.
- `gh run rerun` 은 옛 이벤트 payload 를 재생하므로 본문 수정 검증에 쓰지 않는다.

🔴 **claim-review 흔적은 형식이 통과 조건이다** — `scripts/check_claim_review_trace.py` 가 정규식으로 찾는다. 의미가 맞아도 형식이 어긋나면 red.

| 요구 | 정규식 | 실패하는 표기 |
|---|---|---|
| 섹션 헤딩 | `^#{1,4}[^\n]*claim-?review` | `## Grok 2차 검토 …` (어휘 없음) |
| 판정 라인 | `^[-*\|\s]*verdict\s*[:\|]\s*(SURVIVES\|WEAKENED\|BROKEN\|CONFIRMED\|REFUTED\|HOLDS)\b` | `verdict-1: HOLDS` · `verdict: WEAKENEDX` |

로컬 검증:

```bash
PR_TITLE="$(gh pr view N --json title --jq .title)" \
PR_BODY="$(gh pr view N --json body --jq .body)" \
PR_BASE_SHA="$(gh pr view N --json baseRefOid --jq .baseRefOid)" \
PR_HEAD_SHA="$(gh pr view N --json headRefOid --jq .headRefOid)" \
py -3 scripts/check_claim_review_trace.py
```

본문만 고쳐서는 required check 가 갱신되지 않는다 — **커밋을 하나 더** 민다.

## LLM 응답 형식은 스키마로

프롬프트에 "JSON 만 출력하라"고 적는 것과 API 에 스키마를 거는 것은 다르다.

- `output_config={"format": {"type": "json_schema", "schema": …}}`. object 는 `additionalProperties: false` + 전 필드 `required`. `minLength` 같은 제약은 미지원.
- 지원 여부는 문서 표가 아니라 Models API: `client.models.retrieve(<id>).capabilities`.
- 스키마가 닫는 것은 스키마 축 하나. 절단(`stop_reason=max_tokens`)·호출 실패·빈 결과는 그대로다. R35(파싱 실패·`max_tokens` 절단·빈 결과를 approve 로 읽지 않는다, `tests/unit/hooks/test_doc_review_gate.py:570`) · R36(실패 원문 `detail` 을 버리지 않는다, `:616`) 방어를 지우지 않는다.
- enum 을 `list(_LEGAL_DECISIONS)` 로 단언하지 않는다. 테스트는 리터럴 `["approve", "warn", "block"]` (`test_schema_pins_the_legal_decisions_literally`).
- 스키마는 캐시 프리픽스에 들어간다. 크기가 다르면 항목이 갈린다. 에이전트별 스키마를 통일하지 않는다 — 없는 필드를 만들라고 시키게 된다.

## 훅 입력 디코딩 — `json.load(sys.stdin)` 금지

텍스트 모드는 인터프리터 stdin 인코딩에 의존한다 (Windows 자식: `cp949` · `surrogateescape` · `utf8_mode=0`). 한글 mojibake + lone surrogate → 이후 httpx UTF-8 에서 터진다.

정답: `getattr(sys.stdin, "buffer", sys.stdin).read()` 후 UTF-8 직접 디코드 (`.claude/hooks/doc_review_gate.py::read_payload`). `.buffer` 부재(StringIO)는 텍스트 폴백.

`_scrub_surrogates` 는 증상만 지운다. 원인을 이 디코드가 만든다.

진단은 **실훅 자식**을 계측한다. 셸에서 띄운 python 은 부모가 `PYTHONUTF8` 을 심으면 값이 다르다.

🔴 **왕복 착시**: 잘못 디코드한 문자열을 같은 잘못된 인코딩으로 출력하면 원 바이트가 복원된다. 길이·코드포인트로 단언. 회귀: `tests/unit/hooks/test_doc_review_gate.py::TestReadPayload` (배선 되돌림 · 죽은 호출 · `json.loads(sys.stdin.read())` · 텍스트 모드). AST 존재만으로는 죽은 호출이 통과하므로 에이전트에 닿는 diff 를 직접 보는 단언을 같이 둔다.

## 훅 출력 채널 — `print()` 는 Claude 에게 안 간다

PreToolUse/PostToolUse 의 plain stdout 은 디버그 로그다. exit 0 stdout 이 컨텍스트가 되는 이벤트는 `UserPromptSubmit` · `UserPromptExpansion` · `SessionStart` 셋뿐.

| 목적 | 필드 | 대상 |
|---|---|---|
| Claude 가 보게 | `hookSpecificOutput.additionalContext` | 에이전트 |
| 사용자가 보게 | `systemMessage` (top-level) | 터미널 UI |
| 차단 | `hookSpecificOutput.permissionDecision: "deny"` + `…Reason` | — |

advisory 에 `permissionDecision` 을 얹지 말 것 — `"allow"` 는 권한 확인을 건너뛸 수 있다. `additionalContext` 는 권한과 독립. `test_advisory_never_carries_a_permission_decision`.

SessionStart 로 옮기면 세션당 1회라 키 만료/취소가 stale-green 이 된다. live 하면서 보이게 하는 쪽은 `additionalContext`.

텍스트 단언(`"MARKER" in capsys.out`)은 bare `print` 로 되돌려도 통과한다. JSON 을 파싱해 단언한다.

## 뮤테이션 유효성 — `mutated != orig` 는 필요조건

텍스트가 바뀌어도 동작이 안 바뀌는 뮤테이션이 있다 (`ensure_ascii=True` → 기본값과 동일). GREEN 이면 *"가드가 공허한가"* 보다 *"이 뮤테이션이 동작을 바꾸는가"* 를 먼저 본다.

## 스크립트 관용구

- 🔴 **stdout UTF-8 가드** — `scripts/*.py` 는 `_make_stdout_safe()` / `reconfigure`. `tests/unit/scripts/test_stdout_encoding_guard.py`.
- **standalone** — `scripts/` 는 `__init__.py` 없이 `python scripts/x.py`. 공유 import 는 `sys.path` 조작, 검증된 관용구 복제.
- **advisory vs blocking** 을 docstring 에 명시. advisory 는 막아주는 것이 없다.

## 워크플로(`.claude/workflows/*.mjs`)

- loop-until-dry 정본 = `_lib/loop-until-dry.template.mjs` (`tests/unit/scripts/test_workflow_loop_sync.py`).
- `Date.now()` · `Math.random()` · argless `new Date()` 금지 — 타임스탬프는 args.
- cross-verify=finding 강제 (verdict_coverage). 스킬은 얇은 런처.
