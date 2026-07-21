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

## 🔴🔴 3-불변식 (정본 SSOT = [`AGENTS.md`](../../AGENTS.md))

새 가드/훅/워크플로/검증 스크립트를 저술할 때 **예외 없이**:

### 1. fail-closed — 통과가 산문으로 충족되면 안 된다

- ❌ `binary in build_command_text` — `echo 'WARNING: tsc failed'` 산문이 통과시킨다(#1136).
- ❌ `"사용자 회신" in row` — "사용자 회신 **대기**" 가 통과시킨다(#1156).
- ✅ AST(`ast.Call`·`ast.walk`)로 **실제 호출/값**을 보거나, 실행 결과를 관측한다.
- 🔴 자문: *이 검사는 주석·docstring·echo 문구로 통과될 수 있는가?* 그렇다면 fail-**open** 이다.

### 2. 실경로 뮤테이션 — 합성 픽스처로 HOLDS 금지

- 새 가드를 만들면 **그 가드가 보호한다는 실파일/심볼을 깨뜨려 red 를 관측**해야 완료.
- ❌ 합성 문자열만 바꾸는 뮤테이션(#1121: 실 `scheduler.py` 를 넣으면 docstring 이 만족시켜 dead 였다).
- 🔴 **하네스 거짓 통과**: 뮤테이션 적용 여부를 먼저 단언(`assert mutated != orig`). sed 미적용을
  "N passed" 로 오독한 사고가 이 세션에 3회. 커밋 본문 "뮤테이션 N/N red" 는 실파일·적용확인·red 3자 실증.

### 3. 배선 테스트 — 정의≠배선, 순수함수 옳음≠진입점 도달

- 정의만 하고 호출·배선 안 하면 dead code(전 스위트 green 인데 무동작).
- 순수 함수(`derive_test_target`)가 옳아도 **진입점(`main()`)이 그것을 실제로 호출**하는지는 별개(#1145).
- 배선 테스트는 **산문 grep 아닌 실제 실행/호출 관측** — 큐 태스크 실제 실행, `main()` 실 stdin 호출,
  AST 로 진입점 호출 확인. 신규 가드는 "그 가드가 실제 게이트(ci/pre-commit/SessionStart/PostToolUse)에
  배선됐나" 를 동반 검증.

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
