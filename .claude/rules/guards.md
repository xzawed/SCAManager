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

🔴 **술어가 잡지 못하는 것**(정직 기준): 조건부 skip 된 CI step · 인터프리터의 런타임 부재 ·
배선됐으나 공허한 가드 본문. 이 술어는 **"실행 연결이 끊겼는데 초록"** 만 끝낸다.

🔴 **B8 범위 밖**: `check_guard_fail_open.py` 는 `scripts/check_*.py` 만 glob 하므로
**test-as-guard(`tests/**/test_*.py`)의 fail-open 은 자동 탐지되지 않는다** — AGENTS.md 가
기록한 최다 재발 사고(`#1136`·`#1156`)가 바로 그 표면이다. 이 표면은 write-time 규율(이 파일)과
review-time claim-review 로만 방어된다.

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
