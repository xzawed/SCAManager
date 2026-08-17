# 흐름 — 가드를 새로 쓸 때

> **언제 여는가**: 가드·테스트·완전성 검사·kill-switch 를 **새로 저술**할 때.
> 규정(3-불변식)의 정본은 [`AGENTS.md`](../../AGENTS.md) 다 — 여기는 **순서**를 적는다.

---

## 1. 무엇을 막으려는지 한 문장으로 적는다

*"이 가드가 없으면 어떤 일이 일어나는가"* 를 못 적으면 만들지 않는다.
이 저장소는 **집행자 없는 규칙**을 쌓은 이력이 있다.
규칙을 더 쓰는 것은 처방이 아니다.

---

## 2. TDD — 계약을 먼저 고정한다

테스트를 먼저 쓰고 **red 를 확인**한다. red 가 안 나오면 그 테스트는 아직 아무것도 안 잰다.

🔴 **통과 조건이 `X in text` 면 그 순간 fail-open 이다.** 산문·주석·`echo` 로 충족되면 안 된다.
(floor 집행: `scripts/check_guard_fail_open.py` — 구조 도구 0인 경우만 차단한다)
실측: `"missing_surfaces" in main_body` 로 배선을 검사한 테스트가
**보호 장치를 지워도 초록**이었다.
→ **실행 관측**을 쓴다 — `main()` 을 실제로 호출하고 exit code 를 단언한다.

---

## 3. 기대값을 피검사 대상에서 유도하지 않는다

기대 목록을 검사 대상 모듈에서 읽으면 **원천을 지우는 순간 루프가 안 돌아 GREEN** 이다.
리터럴로 못박는다. 지문도 **그 원천에만 있는 문구**를 쓴다.

---

## 4. 실경로 뮤테이션으로 red 를 실증한다

```bash
git add -A                                   # ① 기준선 고정 (D2 함정)
<실제 보호 장치를 깨뜨린다>                    # ② 합성 픽스처 금지
git diff --quiet <file> || echo "mutated OK" # ③ 적용 확인 (B2 함정)
pytest <가드>                                 # ④ red
git checkout -- <file>                       # ⑤ 복원
pytest <가드>                                 # ⑥ green
```

**과교정 대조군도 함께 만든다** — 정상 변경이 통과하는지. 없으면 *"항상 red"* 로 고쳐도
통과해 가드가 곧 꺼진다.

---

## 5. 배선을 따로 단언한다

정의 ≠ 배선. 순수 함수가 옳아도 **진입점이 그 함수에 도달하는지**는 별개다.

```python
from tests.unit.scripts._wiring_shape import surface_invokes
assert surface_invokes(ci_yml, "scripts/check_x.py")   # substring 금지
```

`"check_x.py" in commands` 는 `echo 'skipping scripts/check_x.py'` 로 통과한다(실측 11건).

---

## 6. 못 막는 것을 docstring 에 적는다

우회 표를 만든다 — **무엇이 차단되고 무엇이 통과하는지**.

| 우회 | 이 축 | 다른 축 |
|---|---|---|
| … | 차단 | 통과 |

한계를 적지 않으면 다음 사람이 **봉인으로 읽는다**. 이 저장소는
*"거짓 집행자가 무집행보다 나쁘다"* 를 메모리로 기록해 뒀다.

---

## 7. 외부 적대 검증 (정책 19)

가드 표면 PR 은 claim-review 면제 불가. 반례를 받으면
[`claim-and-verify.md`](claim-and-verify.md) §2-c 로 넘어간다 — **그 반례만 막고 끝내지 않는다**.

---

## 8. 규칙 옆에 가드 이름을 적는다 — 단, 실제로 그 규칙을 검사하는 것으로

🔴 `scripts/check_red_budget.py` 는 **파일명 실재만** 본다(스스로 프록시라 인정).
규칙과 무관한 가드 파일명을 붙였고 게이트는 통과했다 —
후속 감사가 잡을 때까지 살아 있었다.
→ 이름을 적기 전에 **그 파일을 열어** 그 규칙을 검사하는지 확인한다.

---

## 이 흐름이 막지 못하는 것

- **test-as-guard 의 fail-open 은 자동 탐지되지 않는다** — `X in text` 가 정당한 presence
  검사에도 흔해 확대 시 오탐>진탐(가드 자살). 이 표면은 이 흐름과 claim-review 로만 방어된다.
- **의미적 fail-open** 은 정적으로 판정 불가다. 천장을 인정하는 편이 성급한 봉인보다 정직하다.

---

## 프롬프트 캐시 — 훅이 LLM 을 부를 때 (`doc_review_gate`)

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

> 이 절은 2026-08-17 `.claude/rules/guards.md` 에서 이관됐다(#1417). 그 파일은
> `scripts/**` 편집마다 **전문이 자동 로드**되는데, 이 내용은 훅 하나의 설계론이라
> 매 세션 실릴 이유가 없다. 규칙·가드명·금지는 한 줄도 옮기지 않고 그대로 두었다.
