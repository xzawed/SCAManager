# 2026-08-04 5+1 회고 — 세션13~14 창 (PR #1250~#1272)

> **기계 산출**: `.claude/workflows/retrospective.mjs` run `wf_d6314612-d17` (정책 8).
> **범위**(기계 산출 `scripts/retro_scope.py`, 착수 직전 재실행): 경계 커밋 `bb038ec` → `2cf7ba0`,
> 머지 PR **23건** `#1250`~`#1272` + 세션13(2026-08-01)·세션14(2026-08-02) 산출물 전체 (정책 8-(5)).
> **직전 정식 회고**: [`2026-07-31-retrospective.md`](2026-07-31-retrospective.md).

---

## 실행 지표

| 항목 | 값 |
|------|-----|
| 에이전트 | **162** (오류 0 · 빈 결과 0) |
| 소비 토큰 | 14,687,676 (subagent) |
| 소요 | 2시간 53분 |
| Discover 라운드 | 3 (신규 36 → 35 → 34) + completeness gap 라운드 6 |
| finding 총계 | **140** |
| 확정 (CONFIRMED + SEVERITY_ADJUST) | **123** |
| 기각 (FALSE_POSITIVE) | 17 |
| 심각도 조정 | 37 |
| **verdict 커버리지** | **100%** (미검증 0 — 정책 8 verdict=finding 강제) |
| 확정 분포 | P0 **1** · P1 **60** · P2 **62** |
| 인용 실측 확인 | 117/123 (미확인 6건은 🔸 표기) |

🔴 **P0 후보 8건 중 7건이 cross-verify 에서 강등/기각됐다** (P0→P1 6 · FALSE_POSITIVE 1).
검증관이 실제로 반대편에 섰다는 뜻이고, 이 회고의 P0 1건은 그 압력을 통과한 것이다.

---

## Grok claim-review (정책 19)

세션 `019fc81b` · owner-interrupt: claim-review · read-only. **주장 트리거 단축 패스**
(정책 19 — 회고 카덴스에 Grok full-pass 를 겹치지 않는다). 대상 = 같은 파일에 대해
**정반대의 라이브 실측**을 보고한 두 finding.

| 주장 | Grok 평결 |
|------|----------|
| **A** — 게이트가 `max_tokens=512` 절단을 승인으로 처리, stdout 0 무흔적 통과 | ✅ **HOLDS** (로컬 재현) |
| **B** — 게이트가 STATE.md 6-step ⑤ 편집을 deny (기전 = 종합수치 라인 char 11132 라 심의자가 못 봄) | ❌ **BROKEN (기전 오류)** · 잔여 구조는 HOLDS with caveat |

🔴 **B 반증을 Claude 가 직접 재측정해 확인**(`docs/STATE.md` 실측):

| 토큰 | 최초 offset | 4000자 컨텍스트 예산 내부? |
|------|------------|--------------------------|
| `6607` | **3023** | ✅ |
| `6778` | **3105** | ✅ |
| `pylint` / `10.00` | 11254 / 11263 | ❌ |

→ finder 가 단정한 *"심의자는 대조 대상 자체를 못 본다"* 는 **핵심 카운트에 대해 거짓**이다.
예산 밖인 것은 pylint·커버리지뿐 — **부분 실명**이지 전면 실명이 아니다.
이 회고의 cross-verify 도 독립적으로 같은 결론(P0→P1 강등)에 도달했다.

🔴 **Grok 의 메타 발견(GROK-8)** — *"A 와 B 를 모순된 측정으로 취급하는 것 자체가 진짜
observer-lie"*: 둘은 같은 게이트의 **반대쪽 꼬리**다. 긴 diff → 절단 → 무음 승인 /
짧은 diff + 유효한 `consistency=block` → deny. 서로 반증하지 않는다.

### Grok findings (impact 라벨 — 심각도는 Claude/사용자가 매긴다, 정책 19 계약)

| ID | CLAIM | IMPACT | STATUS |
|----|-------|--------|--------|
| GROK-20260803-1 | 절단된 JSON 이 `{"decision":"block"…` 으로 **시작했더라도** approve 로 뒤집힘 | `fail-open` | **reproduced** |
| GROK-20260803-2 | 훅이 **완전 무출력인 경로 5개**(kill-switch·stdin 파싱 실패·빈 경로·skip/low_risk·최종 approve) — 리포 안 어떤 관측자도 "심의 후 승인"과 "심의 안 함"을 구별 못 함 | `silent-disable` | reproduced |
| GROK-20260803-3 | `check_guard_fail_open`(B8, `#1268` 로 hooks 확대)가 이 클래스를 **원리적으로 못 봄** — 훅이 `re` 를 쓰므로 후보에서 제외되고 B8 은 decision 기본값을 검사하지 않음 | `fail-open` | static-only |
| GROK-20260803-4 | **CLAIM-B 의 인과 기전이 거짓** — 4000자 예산 하에서도 리뷰어는 주 카운트를 본다(`6607`≈3023 · `6778`≈3105, 둘 다 L17 서사 안). 예산 밖은 형식 `**종합 수치**`≈11121 · `pylint`≈11254 뿐 | `score-lie`<br><sub>(deny 사유에 대한 observer-lie)</sub> | **reproduced** |
| GROK-20260803-5 | `consistency` 가 `critical` 에서 block 을 내면 **"확인 불가 ⇒ block 아님" 강등 분기 없이** 곧장 deny — `important` 경로에는 이미 강등이 있는데(`:164-166`) `critical` 에만 없다. `test_consistency_blocks_critical` 이 이 극성을 고정 | `silent-disable` | **reproduced**<br><sub>(순수함수; 라이브 3/4 는 미재현)</sub> |
| GROK-20260803-6 | 스키마 drift 도 승인: `decision` 키 누락 · `decision="maybe"` · `results=[]` **전부 approve** | `fail-open` | **reproduced** |
| GROK-20260803-7 | **60건 테스트 스위트가 fail-open 을 정상으로 고정** — 프로덕션을 block 으로 뒤집으면 그 테스트가 RED. 스위트가 **틀린 극성**을 지킨다 | `fail-open` | static-only |
| GROK-20260803-8 | (메타) A·B 는 같은 게이트의 반대쪽 꼬리 — 모순으로 취급하는 것이 observer-lie | `fail-open` + `silent-disable` | static-only |

✅ **GROK-4·5 는 최초 전송에서 절단**됐고(2253자) 세션 `019fc81b` **resume 으로 회수 완료** — 위 표에 반영.
⚠️ **Grok 은 Anthropic API 를 재호출하지 않았다** — 순수 함수 로컬 재현 + 정적 경로 추적이다.
`stop_reason=max_tokens 2/3` 라이브 샘플은 회고 에이전트 측 실측이며 Grok 이 재검증하지 않았다.

---

## 🔴 P0 (1건)

### 문서 심의 게이트가 응답 절단(max_tokens=512)을 '승인'으로 처리 — CRITICAL 문서 편집이 무흔적 통과 (실측 재현)

- **위치**: `.claude/hooks/doc_review_gate.py:373` · 관점 `code`
- **주장**: `.claude/hooks/doc_review_gate.py` 는 에이전트 응답이 JSON 파싱되지 않으면 `decision: "approve"` 를 반환한다(:373). `max_tokens=512`(:357) 이고 `stop_reason` 을 보지 않아, 리뷰어가 할 말이 많을수록 응답이 잘리고 → 파싱 실패 → **승인**이 된다. 즉 심각도와 fail-open 확률이 정비례한다. 이 경로는 훅의 다른 모든 실패 경로(#1257 자격증명 배너 · #1260 출력 채널 · R31 loud fail-open)와 달리 **출력이 전혀 없다** — 관측면 0.
- **증거**: 실측 1 (API 직접): CLAUDE.md 3.8KB diff(=`_DIFF_BUDGET` 4000자 이내) 로 3 에이전트 호출 → impact `stop_reason=end_turn`(296토큰, json_ok=True) / consistency `stop_reason=max_tokens`(512토큰, json_ok=**False**) / quality `stop_reason=max_tokens`(512토큰, json_ok=**False**). 실측 2 (훅 end-to-end): `{"tool_input":{"file_path":"CLAUDE.md", old/new 1.8KB}}` 를 실제 훅에 stdin 주입 → **RC 0 · stdout 길이 0** = block 도 warn 도 advisory 도 없는 완전 무음 통과. 대조군: `.claude/rules/pipeline.md` 짧은 편집은 3/3 응답이 예산 내라 정상 `permissionDecision: deny` 발화(stdout 2269B) — 즉 게이트가 죽은 게 아니라 **응답이 길 때만** 승인으로 뒤집힌다. 보조 fail-open: `apply_veto_matrix` 의 `decision = r.get("decision", "approve")`(:151) 로 스키마 drift 도 승인. `check_guard_fail_open.py` 가 #1268 로 `.claude/hooks/**` 까지 확대됐으나 그 floor 는 'ast/re/subprocess 미사용'만 보므로 이 클래스를 원리적으로 못 본다.
- **처방**: (1) `msg.stop_reason == "max_tokens"` 를 명시 검사해 절단을 **파싱 실패와 구별**하고 `warn`(또는 재시도 후 warn)으로 강등 — 절대 `approve` 로 매핑하지 않는다. (2) JSON 파싱 실패의 default 를 `approve` → `warn` 으로 뒤집고 `_emit_advisory` 로 관측면을 만든다(무음 통과 금지 — R31 이 check_edit_allowed 에 적용한 loud fail-open 과 동일 원칙). (3) `max_tokens` 를 실측 상한(관측 512 포화)보다 크게 잡고, 에이전트 프롬프트에 reason/detail 길이 상한을 명시. (4) 회귀 가드: `stop_reason="max_tokens"` + 절단 JSON 픽스처로 `_call_single_agent` 가 approve 를 내지 않음을 단언(뮤테이션: 검사 제거 시 red).
- **cross-verify**: `CONFIRMED` — CONFIRMED — P0 유지. 인용 4지점 전부 `grep -n` 실측 일치, 그리고 나는 파인더 실측을 믿지 않고 **독립 재현**했다(라이브 API 5회 × 3에이전트 = 15콜). ## 1. 인용 검증 (정책 6, awk NR 실측) - `.claude/hooks/doc_review_gate.py:373` — `return {"agent": agent, "decision": "approve", "reason": "JSON 파싱 실패 — 통과", ...}` ✅ - `:357` — `max_tokens=512` ✅ / `:369`·`:372` — `json.loads` → `except (json.JSONDecodeError, ValueError)`, **`stop_reason` 참조 0** ✅ - `:151` — `decision = r.get("decision", "approve")` ✅ (스키마 drift 도 승인) - 관측면 0 검증: `main()` 은 `block`(:552)·`warn`(:565) 두 분기에서만 출력하고 `approve` 는 `sys.exit(0)` 뿐 — 구조적으로 stdout 0 ✅ ## 2. 독립 재현 (내가 직접 실행 — `_credentials()` 로 `.env` 키 해석됨) - **대조군(무해 CLAUDE.md diff)**: 절단 0/3, out_tok = 298 / 457 / 395 — 512 예산의 **최대 89%** 소진. 여유가 원래부터 얇다. - **처리군(위반 주입 CRITICAL diff — 규칙 모순 2 + 수치 불일치 + 삭제 개념 `gate_mode`/`auto_approve_threshold` + 죽은 경로 2)**: 5회 반복에서 **15콜 중 7콜이 `stop_reason=max_tokens`(out_tok=512…

---

## P1 (60건) — 클러스터별

### A. 문서 심의 게이트 (doc_review_gate.py) — 7건

**새로 무장된 문서 심의 게이트가 6-step ⑤ STATE.md 동기화 편집을 실제로 deny 한다 (라이브 4회 중 3회 block)**

- 위치 `.claude/hooks/doc_review_gate.py:394` · 관점 `code`
- 주장: #1257(자격증명 전제 봉인)이 게이트를 처음으로 실제 동작시키고 #1265가 심의 범위를 skip 50→4로 넓혔지만, block 경로는 라이브로 한 번도 실행된 적이 없다. 지금 실측하면 `docs/STATE.md`(CRITICAL 등급)의 평범한 수치 동기화 편집이 `permissionDecision: deny` 로 거부된다 — CLAUDE.md 가 매 세션 의무화한 6-step ⑤ 그 자체다.
- 처방: (1) `apply_veto_matrix` 에 "근거 부재로 인한 block 은 warn 으로 강등" 규칙 추가 — 에이전트 응답의 reason 이 검증 불가를 말할 때 deny 로 승격하지 않는다. 더 견고하게는 에이전트 md 의 판정표에 "확인 불가 ⇒ warn(절대 block 아님)" 을 명시. (2) `_CONTEXT_SOURCES` 가 STATE.md 를 4000자로 자르면서 consistency 에게 "STATE 수치와 다르면 block" 을 지시하는 모순 해소 — 대조에 필요한 구간(종합수치·추적셀·README 배지)을 넣거나, 수치 대조 축은 이미 기계 가드(`check_docs_sync` + `check_test_count_sync`)가 담당하므로 에이전트 판정 기준에서 제거. (3) 무장 직후 **block 경로 라이브 1회 실측**을 봉인 조건에 포함 — 이 결함은 정확히 그 실측이 없어서 통과했다. 임시 회피는 `DOC_REVIEW_GATE_DISABLED=1`…

**심의 게이트의 무동작 3형태 중 2형태가 여전히 '정상 판정'과 구별 불가 — 특히 응답 파싱 실패는 무출력 approve**

- 위치 `.claude/hooks/doc_review_gate.py:373` · 관점 `code`
- 주장: 이번 창은 '자격증명 없음' 한 형태에만 INOPERATIVE 배너를 만들었고, 실제로 훨씬 자주 발생한 나머지 두 형태(호출 실패·응답 파싱 실패)는 진짜 심의 결과와 같은 모양을 쓴다. 파싱 실패는 approve 라 **아무 출력도 없이** 통과한다.
- 처방: 결과 dict 에 `inoperative: True` 플래그를 실어 (a) 호출 실패·(b) 파싱 실패를 판정 축과 분리한다. `apply_veto_matrix` 는 inoperative 건수를 세고, **1건 이상이면 반드시 출력**하되 문구를 `_NO_CREDENTIALS_BANNER` 와 같은 계열("N/3 agents did not review — this verdict is partial")로 통일. 특히 파싱 실패는 approve 가 아니라 inoperative-warn 이어야 한다(무출력 통과 제거). 그리고 `detail` 의 예외 타입명을 advisory 에 포함해 blip 과 구조적 불능을 사람이 구분할 수 있게 한다.

**문서 심의 게이트: 3 에이전트 전건 실패가 정상 warn 과 구별 불가 + 예외 원문이 버려진다 (#1257 이 봉인한 것과 같은 결함의 다른 형태)**

- 위치 `.claude/hooks/doc_review_gate.py:473` · 관점 `tooling`
- 주장: 자격증명이 있는 상태에서 3 에이전트가 전부 실패하면 게이트는 아무것도 심의하지 않은 채 `warn` → exit 0 으로 통과시키고, 그 출력은 '진짜로 심의해서 3건 경고가 나온 것' 과 문자열상 구별되지 않는다. 게다가 실패 예외 원문(`detail`)이 출력에서 통째로 버려져 8회+ 반복 실패의 원인을 아무도 알 수 없었다.
- 처방: (a) `_format_warn` 에 `detail`(예외 원문 앞 200자)을 포함시킨다 — 진단 없는 실패는 원장에 추측을 낳는다. (b) `results` 전건이 `reason == "에이전트 호출 실패"` 이면 warn 이 아니라 **INOPERATIVE 와 동급의 별도 배너**('이 편집은 심의되지 않았다 — 3/3 에이전트 실패')를 내보낸다. 부분 실패(1~2/3)는 몇 개가 살아서 판정했는지 숫자로 명시. (c) 회귀 가드는 문자열이 아니라 **payload 구조**를 단언한다(전건 실패 payload → 배너 필드에 'reviewed NOTHING' 상당 문구 + 실패 카운트).

**문서 심의 게이트에 prompt caching 미적용 — 문서 편집 1회당 실측 85,434 입력 토큰, 원장에 적힌 수치의 7.4배**

- 위치 `.claude/hooks/doc_review_gate.py:355` · 관점 `tooling`
- 주장: 게이트는 매 문서 편집마다 동일한 ~28k 토큰 프리픽스(CLAUDE.md 전문 + AGENTS.md 전문 + STATE 머리 + 에이전트 시스템 프롬프트)를 3 에이전트에게 **캐시 없이** 3번 재전송한다. 리포 자신의 `src/analyzer/io/ai_review.py` 는 같은 상황에서 `cache_control` 로 '입력 비용 10× 감소' 를 이미 적용하고 있는데, 훨씬 자주 발화하는 훅에는 없다. 원장(R33)이 기록한 비용 수치도 실측과 7.4배 어긋난다.
- 처방: (a) `system` 프롬프트 대신 user 메시지 앞부분에 실린 규칙 컨텍스트를 블록으로 분리해 `cache_control={"type":"ephemeral"}` 를 붙인다 — 프리픽스가 3 동시 호출·연속 편집에서 바이트 동일하므로 캐시 적중률이 사실상 100%다(비용 ~10×, 지연도 감소). 구현 관용구는 `src/analyzer/io/ai_review.py:140-143` 에 이미 있다. (b) `docs/backlog.md:48` 의 '≈11.6k' 를 실측 85.4k(캐시 적용 후 추정치 병기)로 정정한다 — 이 수치는 사용자가 게이트를 켤지 결정한 근거였다. (c) 게이트 발화 횟수/토큰을 세션당 1줄이라도 관측 가능하게 남긴다 — 현재 ROI 를 사후에 측정할 방법이 전혀 없다.

**doc_review_gate: 3 에이전트 전건 호출 실패는 여전히 무음 통과 — #1257 이 봉인한 것은 자격증명 분기뿐, 세션14 가 8회+ 관측한 분기는 그대로**

- 위치 `.claude/hooks/doc_review_gate.py:374` · 관점 `tooling`
- 주장: CRITICAL 등급 문서 차단 게이트가 '자격증명은 있으나 3 에이전트가 전부 실패' 상태에서 아무것도 심의하지 않고 exit 0 하며, 그 문구가 일시 blip 과 구별되지 않는다. #1257 이 이 결함을 명시적으로 진단해 놓고 자격증명 부재 분기만 봉인해, 세션14 가 실제로 8회+ 겪은 분기는 원래 결함 그대로 남았다(defect class 6 — 수정이 같은 결함을 재생산).
- 처방: results 전건이 호출 실패 사유일 때 전용 INOPERATIVE 배너를 `_emit_advisory` 양 채널로 내보내고(문구에 '이번 편집은 심의되지 않았다' + 실패 detail 요약), 세션 내 누적 횟수를 함께 표기한다. :373 의 approve fallback 도 warn 으로 승격 검토. 회귀 가드 = 3 에이전트 전부 예외를 던지는 fake client 로 '배너 문자열이 blip 문구와 다르다'를 단언(뮤테이션: 배너 제거 시 red).

**문서 심의 게이트: '자격증명 있는데 3 에이전트 전건 실패' 가 '3명이 경고하며 심의함' 과 구별 불가 — 세션14가 8회+ 실제로 앉아 있던 상태**

- 위치 `.claude/hooks/doc_review_gate.py:375` · 관점 `tooling`
- 주장: #1257 은 자격증명 **부재** 분기만 INOPERATIVE 배너로 봉인했다. 자격증명이 **있는데** 호출이 전건 실패하는 분기(무효 키·모델 미승인·레이트리밋·네트워크)는 여전히 `[문서 심의] ... — 경고 후 진행` + `[!] × 3` 를 내고 exit 0 한다. 이 출력은 '세 심의자가 각각 경미한 우려를 냈다' 와 **글자 하나 구별되지 않는다**. 게다가 실패 원인은 `detail=str(exc)` 로 계산해 놓고 `_format_warn`/`_format_block` 이 `reason` 만 렌더링해 **버린다** — 세션14가 8회+ 실패를 관측하고도 원인을 못 짚은 이유가 이것이다.
- 처방: (a) `call_agents_parallel` 결과에서 **전건 실패**를 집계해 `warn` 이 아닌 전용 `INOPERATIVE (호출 전건 실패)` 배너로 분기 — '심의 0건' 을 '경고 있음' 과 어휘 분리. (b) `_format_warn`/`_format_block` 이 `detail` 앞 200자를 반드시 인쇄(진단 없는 실패 = 관측 아님). (c) 회귀 가드는 '키 있음 + 3건 모두 호출 예외' 시나리오에서 출력에 `경고 후 진행` 이 **나오지 않을 것**을 단언.

**심의 게이트 diff 를 4000자에서 라벨 없이 잘라낸다 — Write 경로에서 CLAUDE.md 의 13.9% 만 보고 '변경 내용' 이라 말함**

- 위치 `.claude/hooks/doc_review_gate.py:349` · 관점 `tooling`
- 주장: `_call_single_agent` 은 `diff[:_DIFF_BUDGET]`(4000자)로 무언 절단한 뒤 헤더에 `## 변경 내용 (diff)` 라고 적는다. 심의자에게 **잘렸다는 사실이 전달되지 않는다**. 바로 위 docstring 과 `_load_context()`(doc_review_gate.py:400-434)는 같은 세션(#1257)이 컨텍스트 절단을 "심의자에게 없는 근거를 있다고 말한 셈(observer-lie)" 이라 부르며 비율 라벨(`앞 N자 / 전체 M자 = P% 만 포함, 나머지는 못 봄`)을 붙여 봉인했다. **diff 축에만 같은 결함이 남았다** — 수정이 자기가 고친 결함을 이웃 필드에서 재생산한 형태.
- 처방: `_load_context` 와 **동일 관용구**로 통일 — `len(diff) > _DIFF_BUDGET` 이면 헤더에 비율과 '나머지는 못 봄' 명시. MultiEdit 은 편집당 예산 분배(또는 편집 수 명시). 회귀 가드: 4001자 diff 를 넣고 user 메시지에 비율 문구가 있는지 단언(#1257 이 컨텍스트 축에 만든 test_doc_review_gate.py:439 의 diff 판).

### B. 회고 워크플로 자신 — 5건

**정책 8 5+1 회고가 체크포인트 없는 all-or-nothing 실행이라 중단 시 전량 소실 — 2026-08-02 에 실현**

- 위치 `.claude/workflows/retrospective.mjs:306` · 관점 `process`
- 주장: `.claude/workflows/retrospective.mjs` 는 라운드 중간에 어떤 파일도 쓰지 않는다. 파일 작성은 스킬이 **끝에서 1회** 수행하는 구조로 설계에 명시돼 있다. 따라서 실행 중 중단 = 이미 소비한 에이전트 토큰 전량 폐기 + 처음부터 재실행. 정책 8 이 매 세션 트리거되는 **의무** 인데 그 의무의 실행체가 부분 실패를 허용하지 않는다. 2026-08-02 에 실제로 발생했고(~30분 소실), 그 결과가 카덴스 이월 원장 첫 실행 기록이다.
- 처방: (a) 라운드 종료마다 부분 finding 을 스크래치 JSON 으로 flush 하고, 스킬이 재진입 시 기존 파일을 로드해 이어가게 한다(loop-until-dry 는 라운드 경계가 명확해 구현 비용이 낮다). (b) 최소 조치라도 `check_retro_cadence.py` 배너에 "5+1 진입 권장 잔여 예산" 을 함께 인쇄해 **세션 말미 진입 자체를 억제**한다 — 이번 실패의 직접 원인은 워크플로가 아니라 진입 시각이었다.

**retrospective.mjs: budget floor 가 5개 지출 지점 중 1곳만 지키고 중간 체크포인트가 0 — 토큰 소진 = 전량 소실**

- 위치 `.claude/workflows/retrospective.mjs:248` · 관점 `tooling`
- 주장: `budget.remaining() > BUDGET_FLOOR` 검사가 discover 루프 **진입 조건에만** 있고, 같은 라운드 안의 cross-verify 팬아웃·completeness·gap 라운드·UNVERIFIED 재검증 4곳은 예산 검사 없이 지출한다. 게다가 워크플로는 어떤 중간 상태도 파일로 남기지 않아, 소진으로 중단되면 이미 끝난 finder/verify 결과가 전부 사라진다 — 세션14 가 정확히 그렇게 죽었다.
- 처방: (a) `verifyAll` 진입과 completeness/gap/재검증 3 단계 앞에 동일한 `BUDGET_FLOOR` 검사를 넣고, 미달 시 지금까지의 `verified[]` 로 Report 단계에 진입한다(부분 결과 보존 — completeness 의 try/catch `:280-284` 가 이미 같은 철학을 쓰고 있다). (b) 라운드 종료마다 `verified[]` 를 JSON 으로 덤프하고, 재기동 시 그 파일이 있으면 `seen` 을 복원한다 — 30분치 다중 에이전트 산출물이 프로세스 종료 하나로 사라지는 것이 현재 상태다. (c) 정본 템플릿 `_lib/loop-until-dry.template.mjs` 의 불변식 토큰 목록에 '루프 밖 지출 지점도 floor 를 검사한다' 를 추가해 `integrity-audit.mjs`(같은 구조 — `:284` 단일 검사)와 함께 고친다.

**회고/감사 워크플로: budget floor 가 Discover 루프 진입에만 걸리고 checkpoint 가 0 — 세션14 회고 중단이 라이브 반례**

- 위치 `.claude/workflows/retrospective.mjs:248` · 관점 `tooling`
- 주장: budget 하한 검사가 while 조건(1지점)에만 있고, 그 뒤 Completeness 비평가 + 표적 gap 라운드 + UNVERIFIED 재검증은 예산 검사 없이 무제한 에이전트를 띄운다. 동시에 결과는 최종 return 에서만 방출되므로 중단 시 이미 verdict 를 받은 finding 전량이 소실된다. 세션14 는 이 두 성질이 겹쳐 회고 run 을 기동했다가 토큰 소진으로 **산출물 0**으로 끝났고, 카덴스 이월(#1272)로 다음 세션에 전량 재실행이 확정됐다 — 순수 토큰 손실.
- 처방: (a) `verifyAll` 배치 루프와 Completeness 진입에 동일 `BUDGET_FLOOR` 가드를 넣고 초과 시 부분 결과로 Report 로 낙하 (b) 라운드 종료마다 verified[] 를 스크래치 파일로 flush 하고 시작 시 읽어 재개(cross-session resume) (c) 두 불변식을 `_lib/loop-until-dry.template.mjs` 정본과 test_workflow_loop_sync.py `_INVARIANTS` 에 추가해 drift 차단.

**/retrospective 워크플로의 BUDGET_FLOOR 는 라운드 진입 시점에만 검사 + 중간 산출물 영속화 0 — 세션14 회고 지출 전액 소실**

- 위치 `.claude/workflows/retrospective.mjs:248` · 관점 `tooling`
- 주장: `retrospective.mjs:248` 의 예산 하한은 **라운드 시작 직전 1회**만 평가되는데, 한 라운드는 5 도메인 finder 병렬 + `verifyAll`(BATCH 6 순차 배치, :204-211) 로 하한 60k 의 수 배를 소비할 수 있다. 라운드 **안**에는 중단점이 없다. 게다가 파일 영속화가 전혀 없어(`grep -c 'writeFile\|fs\.\|require('` → **0**) 프로세스/세션이 죽으면 `verified[]` 전량이 증발한다. 워크플로는 completeness 단계의 API 500 에 대해서는 부분결과 보존을 명시 구현(:281-283)해 놓고, 훨씬 흔한 실패 모드인 **토큰 소진**에는 같은 보호가 없다.
- 처방: (a) `verifyAll` 배치 루프와 finder 병렬 직전에도 `budget.remaining() > BUDGET_FLOOR` 검사를 넣어 라운드 **중간** 중단 가능하게. (b) 라운드 종료마다 `verified[]` 를 `docs/reports/artifacts/` 또는 스크래치에 append 하고, 중단 시 그 부분결과로 Report 단계를 실행 — '부분 회고' 가 '회고 0' 보다 낫다. (c) `!budget.total` 이면 하한 검사가 통째로 비활성(:248)인 fail-open 도 함께 정정 — 예산 정보가 없을 때야말로 보수적이어야 한다.

**회고 워크플로의 5 관점이 하드코딩이고 어디에도 '정책 자체의 집행률' 렌즈가 없다 — 이 발견도 +1 critic 이 우연히 잡아야만 나온다** 🔸<sub>인용 미확인</sub>

- 위치 `.claude/workflows/retrospective.mjs:28` · 관점 `ops`
- 주장: `.claude/workflows/retrospective.mjs:27-33` 의 `DEFAULT_DOMAINS` 는 process·code·docs·decision·tooling 5종 하드코딩이다. `process` focus 는 *"정책 준수·협업 흐름·사이클 종료 신호"* 로 **단일 사건의 준수 여부**를 보게 되어 있고, `tooling` focus 는 *"도구·자동화·워크플로우·훅 ROI"* 로 **도구의 유용성**을 본다. 어느 쪽도 *"정책 N 이 지난 M 사이클 동안 몇 % 집행됐는가"* 라는 **누적 집행률**을 측정하지 않는다. 그래서 정책 13 발화 0 은 42→65 로 누적되는 동안 5 관점 중 어느 것도 잡지 못했고, 이번에도 `completenessPrompt`(`:161-174`)의 (b) *"미검증 양식 — 정책 cross-reference 누락, 시간차 누적 결함…"* 이 우연히 지목해야만 표적 라운드가 돌았다. 우연 의존이 구조인 근거: gap 라운드는 `:181-190` 의 try/catch 로 감싼 **best-effort** 이고, 주석이 스스로 *"2026-06-23 회고가 마지막 500 으로 gap 라운드 소실"* 이라 기록한다 — 즉 API 500 한 번이면 이 관점 전체가 그 회고에서 사라진다. 다만 처방은 새 도메인 추가가 아니어도 된다: `:24-26` 주석이 *"UX/시각 회귀는 별…
- 처방: 선례를 그대로 따라 `process` focus 문자열에 명시 편입: `'… 사이클 종료 신호 · **정책 집행률 측정(정책 N 의 의무 섹션이 창 내 PR 중 몇 건에 실제로 작성됐는가 — 발화 0 인 정책을 열거)**'`. 도메인 수를 5 로 유지하므로 정책 8 프레임과 충돌하지 않고, gap 라운드의 best-effort 성격에 의존하지 않는 **1라운드 확정 관점**이 된다. 페어로 `scripts/retro_scope.py` 가 창 PR 본문에서 정책 2/11/13 의무 섹션 헤딩 출현율을 기계 산출해 회고 컨텍스트에 주입하면, 집행률이 추정이 아니라 입력값이 된다.

### C. 카덴스 이월 원장 — 5건

**카덴스 이월 원장의 "사용자 명시 이월 승인 인용" 셀에 승인이 아닌 세션 종료 지시가 기록됐다 — 파서는 '비어있지 않음'만 본다**

- 위치 `docs/runbooks/retro-cadence-deferrals.md:25` · 관점 `decision`
- 주장: 정책 8-(6)이 요구하는 것은 (a) **사용자 명시 이월 승인 인용**인데, 세션14가 기록한 인용문 "현재 토큰량이 없습니다. 세션을 정리해주세요"에는 회고·이월에 대한 언급이 전혀 없다. 실제로 사용자가 내린 회고 관련 결정은 세션 시작 시 AskUserQuestion 답변 "작업 먼저 + 세션 말미 회고" 하나뿐이며, 이는 **이 세션 안에서 회고를 한다**는 결정이지 **다음 세션으로 이월한다**는 승인이 아니다(그 옵션 설명 자체가 "이월 기록은 deferrals 원장에 본 답변 인용으로 남깁니다"라고 적었으나, 원장에는 다른 발화가 들어갔다). 크로스세션 이월은 사용자가 승인한 적이 없고 Claude가 토큰 소진 발화에서 추론한 것이다. 가드는 승인 셀이 `{"", "-", "—", "–", "tbd", "n/a", "없음"}` 이 아니기만 하면 유효 이월로 인정하므로, 다음 세션 SessionStart 는 "ℹ️ 카덴스 이월 승인 기록됨 … 승인: 현재 토큰량이 없습니다…" 를 출력한다 — 존재하지 않는 사용자 승인을 기계가 사용자에게 되읽어 준다. 원장이 봉인하려던 실패(순수 배너가 15→57 PR 이월을 못 막음)의 관측면이 '아무 문장이나 채우면 통과'로 열려 있다.
- 처방: (a) 원장 행에 '승인 발화의 원 출처'(AskUserQuestion 답변 / 직접 발화 타임스탬프)를 별도 셀로 요구하고, (b) 인용이 이월 결정과 무관한 경우를 위해 `추론된 승인` 을 별도 상태로 분리해 가드가 loud 하게 구분하도록 한다. 최소 조치: 이번 행을 '사용자 명시 승인 없음 — 토큰 소진 상황에서 Claude 추론'으로 정정하고 다음 회고 §자성에 등재(정책 8-(6) 본문이 이미 그 의무를 규정).

**카덴스 이월 기록이 window 전체를 덮어 '세션당 재승인' 이 관측되지 않는다 — 목표 진입 세션 필드는 장식**

- 위치 `scripts/check_retro_cadence.py:127` · 관점 `process`
- 주장: 정책 8-(6) 이월 원장은 '이월 결정 자체를 관측 가능하게' 만들려고 신설됐는데, 판정 로직이 **회고 진입 전까지 유효한 window 스코프**라 한 번 기록된 행이 이후 모든 세션의 🔴 '이월 승인 기록 없음' 을 영구히 잠재운다. `목표 진입 세션` 셀은 비어있지 않은지만 검사되고 실제 이행 여부는 어떤 코드도 비교하지 않는다 — 원장이 막으려던 '배너를 3세션 무시해 15→57 PR 3.8배' 실패 모드가 형태만 바뀌어 되돌아온다.
- 처방: 이월 행에 만료 조건을 부여한다 — 예: 기록 시점 PR 수 대비 +N PR 초과 또는 기록일 이후 세션 1회 경과 시 `🔴 이월 만료 — 재승인 없이 계속 중` 으로 강등. 판정에 쓸 상태(기록 시점 PR 수)는 이미 원장 2열에 있으므로 `count_merge_prs` 결과와 대조만 하면 순수 함수로 구현 가능하다.

**카덴스 이월 원장의 "사용자 명시 승인" 요건에 관측이 없다 — 승인 셀 비어있지 않음만 검사하고, 기록된 인용은 회고 이월을 승인하지 않는다**

- 위치 `scripts/check_retro_cadence.py:108` · 관점 `decision`
- 주장: 정책 8-(6) 과 원장 헤더는 이월의 유효 조건으로 "(a) 사용자 명시 이월 승인 인용"을 요구하지만, 기계 판정은 승인 셀이 placeholder 집합에 없는지만 본다. 즉 Claude 가 승인 셀에 아무 텍스트나 쓰면 loud 경고가 정보 배너로 바뀐다 — 보호 요건(사용자 승인)을 삭제해도 관측 결과가 동일한 observer-lie. 실제 기록된 인용은 회고·이월을 한 글자도 언급하지 않는 세션 정리 지시이고, "이 발화 = 이월 승인" 이라는 해석도 행 자체도 Claude 가 저술했다. 같은 행의 breach 수치조차 기계 산출과 어긋난다.
- 처방: (1) breach 수치를 `count_merge_prs` 로 기계 주입(손유지 금지), (2) 승인 셀에 "회고"/"이월" 등 대상 명시를 요구하는 최소 술어를 넣거나, 그것이 위조 가능함을 인정하고 원장 헤더에서 "승인 인용 의무" 대신 "이월 결정의 관측 가능성"으로 문구를 낮춘다(현재 문구는 없는 보증을 약속한다).

**카덴스 이월 승인이 만료되지 않는다 — 한 행이 무기한 뮤트를 발급한다**

- 위치 `scripts/check_retro_cadence.py:127` · 관점 `decision`
- 주장: `deferral_status()` 는 '직전 회고 날짜보다 나중인 이월 행이 1개라도 있으면' 무조건 (True, ℹ️) 를 반환한다. 이월 행의 `목표 진입 세션` 셀은 파싱·인쇄되지만 **어떤 축도 그 약속이 지켜졌는지 검사하지 않는다**. 따라서 2026-08-02 에 기록된 단 한 행이, 실제로 회고에 진입할 때까지 세션 15·16·17… 전부에서 loud 라인('🔴 이월 승인 기록 없음')을 영구 소거한다. 이 원장이 만들어진 이유가 정확히 '순수 배너가 3세션 연속(15→57 PR, 3.8배) 무시돼 부채를 재생산했다' 였는데, 시정본은 같은 무한 이월 형태를 **0행 대신 1행**으로 재생산한다(지배적 결함 클래스 6 — 수정이 같은 결함을 재생산).
- 처방: 이월을 window 단위가 아니라 **세션 단위 승인**으로 좁힌다: (a) 이월 행 날짜가 오늘이 아니면 ℹ️ 가 아니라 '🔴 이전 세션 이월 승인이 만료됨 — 새 승인 또는 회고 진입' 을 loud 로 내고, (b) 같은 window 에서 이월 행이 2개 이상 쌓이면 '이월 N회 누적' 을 loud 로 escalate 한다. 회귀 가드는 '같은 행으로 두 번째 세션을 통과시키면 red' 를 단언해야 한다(현재 테스트는 존재/부재만 본다).

**카덴스 이월 원장에 만료가 없다 — 승인 1행이 window 전체를 무기한 면허한다 (목표 세션 셀은 파싱만 되고 집행 0)**

- 위치 `scripts/check_retro_cadence.py:127` · 관점 `ops/owed 원장`
- 주장: `deferral_status()` 는 `이월 날짜 > 직전 회고 날짜` 인 행이 **하나라도** 있으면 breach 를 ℹ️ 로 강등한다. window 리셋은 회고 진입 시에만 일어나므로, 2026-08-02 행 하나가 세션15·16·17… 을 전부 조용히 통과시킨다. 원장이 요구한 "목표 진입 세션"(`target`)은 파싱돼 메시지에 인쇄만 되고 **어떤 판정에도 쓰이지 않는다**. 이 원장은 정확히 "advisory 배너가 3세션 연속 무시돼 15→57 PR 3.8배로 커진 것"을 막으려 신설됐는데, 같은 에스컬레이션 경로가 **이제는 '승인됨' 이라는 외피를 쓰고** 그대로 열려 있다.
- 처방: `deferral_records` 에 소진 개념을 넣는다 — 최소안(파일 I/O 무증가·advisory 유지): 유효 이월은 **직전 회고 이후 최대 1건**으로 제한하고, 이미 이월 행이 있는 window 에서 회고 미진입 상태로 다시 세션이 시작되면 `🔴 이월 만료 — 목표 세션(<target>)을 지났다` 를 loud 발화. 회귀 가드는 기존 `test_check_retro_cadence.py` 의 `deferral_status` 순수함수 축에 '같은 행이 2세션째 통과하지 않는다' 케이스를 추가(뮤테이션: 만료 조건 삭제 → red).

### D. backlog 원장 자기 정합 — 11건

**owed 운영검증 원장 0행이 3세션·48 PR 연속 — R28 보류 사유(R0-2 결정 선행)가 '가드 설계'에만 해당하는데 '행 기재'까지 함께 보류시켰다**

- 위치 `docs/backlog.md:42` · 관점 `decision`
- 주장: owed 원장은 자기 작성 규칙에 "세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다(trailing sync PR body 의 §owed-verification 표와 페어)" 를 명시하는데, 세션12~14 어느 trailing sync PR(#1259·#1262·#1264·#1267·#1272)에도 §owed-verification 표가 없고 원장은 2026-07-26(#1219) 이후 한 줄도 늘지 않았다. R28 의 세션14 미착수 사유로 기록된 "완전성 축 설계(gh 의존·advisory 유지 여부)가 R0-2 와 같은 뿌리라 사용자 결정 선행 필요" 는 **가드를 만드는 일**에는 맞지만 **행을 적는 일**에는 적용되지 않는다 — 행 기재는 사용자 결정이 필요 없는 순수 Claude 작업이다. 두 가지를 한 사유로 묶어 보류한 결과, 이 창의 라이브 검증 요청 9건(#1268·#1269·#1270·#1271·#1272 체크박스)이 기계 집행면이 없는 PR 본문에만 남았다. 특히 **세션14 내내 실패한 문서 심의 게이트(R33-a 재개방)** 처럼 매 세션 loud 경고가 필요한 항목이 SessionStart 훅이 파싱하는 owed 원장이 아니라 무집행 backlog 산문으로 갔다.
- 처방: R28 을 두 축으로 분리한다 — (a) 행 기재(즉시 착수, 사용자 결정 불요: 이 창 9건 등재 + 세션12~13 소급) (b) 완전성 가드 설계(R0-2 회신 대기). trailing sync PR 템플릿에 §owed-verification 표를 필수 섹션으로 넣고, 없으면 red 인 가드를 pre_push_gate 에 추가(원장 최종 커밋 이후 머지 PR 중 미체크 항목 보유분 열거).

**R28 이 "사용자 결정 선행 필요"를 사유로 🟡(착수 가능)에 파킹 — 정확히 그 실패 모드를 막으려 만든 가드가 이 표를 스캔하지 않는다**

- 위치 `docs/backlog.md:42` · 관점 `decision`
- 주장: `test_decision_items_are_not_parked_in_the_actionable_section` 는 "결정 대기 항목이 🟡 에 섞이면 결정 요청 의무가 트리거되지 않는다"는 실측 사고(B6-b)를 봉인하려고 만든 불변식이다. 그런데 이 가드는 `## 🟡` 로 시작하는 **본문 섹션만** 훑고, 현재 창 R-표는 `## ▶️ 다음 세션 시작점 …` 이라는 범례 이모지 없는 헤딩 아래 있어 스캔 범위 밖이다. R28 행은 가드의 매처(`_ITEM_RE` + "사용자 결정"/"결정 대기" 문자열)에 **완전히 걸리는데도** 섹션 필터 하나 때문에 통과한다 — 가드가 자기 스캔 범위를 관측하지 않는 전형이다.
- 처방: 파킹 불변식을 R-표까지 확장한다 — 전장 R행 중 상태가 🟡 인데 근거 셀에 "사용자 결정"/"결정 선행"/"결정 대기" 가 있으면 red. 또는 R28 상태를 🔴 로 승격해 결정 요청 흐름을 실제로 트리거한다.

**R33 이 ✅ 완료로 고정된 채 (a) 축만 재개방됐고, 재개방 사실은 어떤 가드도 읽지 않는 산문에만 있다**

- 위치 `docs/backlog.md:48` · 관점 `decision`
- 주장: R33 은 2026-08-01 단발 라이브 관측("심의 게이트가 처음으로 실제 심의")으로 ✅ 완료로 플립됐다. 세션14 내내 3 에이전트 호출이 전건 실패(실측 8회+)해 전제가 반증됐는데도 행 상태는 ✅ 그대로고, 재개방은 요약 블록 산문 한 줄에만 있다. 기계 강제되는 상태 요약은 R33 을 ✅ 16 에 포함시키고 바로 다음 줄에서 "이 창의 결정 대기는 0건 유지"를 선언한다 — 시점 의존 상태를 불변식으로 고정한 뒤 반증을 반영하지 않는 클래스.
- 처방: R33 행 상태를 재개방 상태(🟡 또는 🔴)로 되돌리고 ✅ 이력은 근거 셀에 남긴다 — 그래야 카운터와 "결정 대기 0건" 선언이 실상과 일치한다. 아울러 라이브 단발 관측으로 ✅ 플립할 때는 owed 원장 행을 함께 만들어 반증 경로를 확보한다.

**R0-2 처방("미체크 항목 보유분 열거")이 이 창의 실데이터에 대해 원리적으로 눈이 먼다 — 요청 표기가 PR마다 4종이고 체크박스는 5/23 PR 뿐**

- 위치 `docs/backlog.md:74` · 관점 `decision`
- 주장: R0-2 는 "부채를 등재하지 않는 것이 가장 싼 통과 경로"라는 진단과 함께 완전성 축 처방을 "머지 PR 중 **미체크 항목** 보유분 열거"로 못박아 두었다. 그런데 이 창의 §🔍 사용자 검증 필요 요청은 체크박스·표 행·번호 목록·불릿 **4종 표기**로 갈라져 있고, `- [ ]` 는 세션14의 5 PR(9건)에만 존재한다. 처방대로 구현하면 창의 요청 48건 중 9건(19%)만 보이고, 세션13 전체 13 PR 은 통째로 green 이 된다 — 처방이 R0-2 자신이 진단한 결함(가장 싼 통과 경로)을 재생산한다.
- 처방: R0-2 결정 전에 요청 표기를 체크박스 단일 형식으로 고정하고 그 형식을 PR 가드가 강제하거나, 완전성 축의 키를 표기가 아니라 "§🔍 사용자 검증 필요 섹션 존재 ↔ owed 원장 행 대응"으로 바꾼다. 표기 의존 설계는 결정 시점에 이미 반증돼 있다.

**점수-신뢰도 고지가 9개 점수 노출면 중 2곳에만 존재 — 닫힌 R21 행에 잔여가 흡수돼 승계 행·회귀 가드 모두 0**

- 위치 `docs/backlog.md:35` · 관점 `product/notify`
- 주장: 4종 신뢰도 플래그를 렌더하는 곳은 `github_comment.py` 와 이를 재사용하는 `github_commit_comment.py` 뿐이다. 등록된 나머지 7 발신면과 웹 대시보드 전체는 동일 분석의 점수·등급을 무단서 노출한다. 데이터는 `NotifyContext.result_dict` 로 모든 채널에 이미 전달되므로 가용성 문제가 아니라 **읽는 뷰의 부재**다. 그리고 이 잔여를 적어 둔 유일한 원장 행 R21 이 ✅ 로 플립되면서 어떤 열린 행에도 승계되지 않아, 다음 세션이 이 결함을 관측할 면이 리포에 남아 있지 않다.
- 처방: R21 에 흡수된 잔여를 **신설 🟡 행**으로 분리 등재하고(닫힌 행에 살아있는 잔여를 두는 패턴 자체가 R24 '원장이 완료된 일을 다시 시킨다' 의 거울상), 최소 조치로 `github_issue.py` 처럼 `result: dict` 가 이미 스코프에 있는 채널부터 `_unreliable_score_warning_lines` 를 주입한다. 회귀 가드는 채널 목록을 하드코딩하지 말고 `REGISTRY` 를 순회해 '점수를 렌더하는 채널은 신뢰도 고지도 렌더한다' 를 단언해야 신규 채널 추가 시 자동으로 red 가 된다.

**backlog 완전성 축은 관측되지 않는다 — 열린 항목 23건 중 3건만 보고, 역사 창 15건을 통째로 ✅ 로 뒤집어도 가드 10/10 green (뮤테이션 실증)**

- 위치 `tests/unit/scripts/test_backlog_shape.py:221` · 관점 `decision/backlog`
- 주장: docs/backlog.md 의 헤드라인 요약(51~57행)은 현재 창 19행만 세어 '🟡 2 · ⏸️ 1 · ✅ 16' 을 보고하지만, 파일 전체의 실제 열린 항목은 R행 18건(현재 창 3 + 역사 창 15) + B/H행 5건(B6-b·B7·H2·H3·H4) = 23건이다(감사 잔여 섹션의 '자율 ~6 · UI 5' 를 더하면 ~34). 두 회귀 가드 중 카운트 불변식(test_status_summary_matches_the_table)은 current_window() 로 역사 섹션을 잘라낸 뒤 세고, R24 가 '가드 커버리지' 해소 근거로 내세운 전장 백스톱(test_every_r_row_status_is_a_legal_marker_whole_file)은 상태 셀의 형식 적법성만 본다. 즉 커버리지는 5행 → 36행으로 넓어졌지만 단언되는 축은 legality 하나뿐이고, '열린 항목이 요약에 드러나는가' 를 묻는 관측면은 리포 어디에도 없다(SessionStart 훅 2종도 backlog 를 읽지 않는다).
- 처방: legality 가 아니라 **completeness** 를 단언하는 축을 신설한다: (a) 파일 전체 R/B/H 행에서 🔴·🟡·⏸️ 를 전수 집계해 '전장 열린 항목 N건' 선언 줄과 대조(현재 창 요약은 범위 명시한 채 유지) — 즉 current_window 절단을 카운트 축에서 제거하고, 창별 소계 + 전장 합계를 둘 다 강제 (b) 역사 창 행의 상태 전이(🔴/🟡 → ✅)는 PR diff 에서 근거 PR 번호를 동반해야 통과하도록(현재 M1 처럼 1행 편집으로 무근거 종결 가능) (c) SessionStart 에 '전장 열린 항목 N건, 그중 🔴 M건: <이름 열거>' advisory 1줄 배선 — 요약을 읽지 않고 파일을 여는 경로에서도 드러나게(정책 17 비차단 유지). 🔴 배선 위치 주의: 현재 required check 는 'Repo integrity guards (stdlib backstop)'(.github/workflows/ci.yml:130) 1종뿐이고 tes…

**R7 의 근거가 stale — 문제삼는 '거짓 배지' 는 창 이전 #1237(2026-07-29)에 이미 정직화됐는데 원장은 여전히 살아 있는 결함으로 서술한다**

- 위치 `docs/backlog.md:82` · 관점 `decision/backlog`
- 주장: 역사 창 R7 은 '**e2e 122건이 CI 미배선인데 README/STATE 는 "E2E 122 passing" 단언** — 178 커밋째 미변경. **실행되지 않는 초록 배지**' 로 등재돼 🔴 사용자 결정 대기 상태다. 그러나 README.md:22 · README.ko.md:22 · docs/STATE.md:46 세 지점 모두 이미 'CI 미배선 / not in CI' 를 명시하는 회색 배지로 바뀌어 있다. R7 이 제시한 두 선택지('배선할지, 배지 문구를 정직하게 바꿀지') 중 후자는 이미 일방 집행됐고 원장만 갱신되지 않았다 — R24 가 명시한 결함('SSOT 가 완료된 일을 다시 시킨다')의 정확한 재발이며, R24 는 이번 창에서 ✅ 로 플립됐다. 원장 행의 근거 신선도를 검증하는 가드는 없다(전장 백스톱은 상태 셀 형식만 본다).
- 처방: R7 행을 '배지 정직화는 #1237 로 집행 완료 — 잔여 결정은 e2e 122건을 CI 에 배선할지 여부 단일 축' 으로 재서술하고, 결정 대기 범위를 축소한다(현재 서술은 사용자에게 이미 없는 문제를 결정하라고 요구한다). 구조 시정: 원장 행이 인용하는 **반증 수단이 이미 충족됐는지**를 기계로 재평가할 수 있게, 🔴/🟡 행의 반증 수단을 실행 가능한 1줄 명령(예: `grep -n 'E2E-122_passing' README.md` 가 0 hit 이면 해소)으로 적도록 갱신 규칙(docs/backlog.md:192)을 확장하고, 그 명령들을 주기적으로 돌려 '이미 해소된 열린 행' 을 loud 로 보고하는 축을 검토한다.

**원장 자신의 의무 규칙(모든 🟡 행에 기전·반증 수단)이 15행 중 11행에서 위반 — R10·R12 는 근거 셀이 완전히 비어 있고, 하필 R10 이 '원장 정합' 항목이다**

- 위치 `docs/backlog.md:192` · 관점 `decision/backlog`
- 주장: docs/backlog.md:192 는 '🔴 **모든 🟡 행은 (기전 · 반증 수단)을 함께 적는다**' 를 2026-07-19 전수 점검 신설 의무로 못박고, 그 근거로 '처방문은 **실행될 코드**다 — B2 의 처방은 무효 키였고, B2-b 의 블로커는 거짓이었으며, B6 의 근거는 귀속이 틀렸다' 를 든다. 실측 결과 파일 전체 🟡 행 15건 중 **11건이 반증 수단 없이 등재**돼 있고, 그중 R10·R12 는 근거 열이 빈 셀(`| |`)이다. 이 의무를 검사하는 가드는 없다(카운트 축·legality 축 모두 셀 내용은 보지 않는다). 결과적으로 자율 착수 가능하다고 표시된 일감의 대다수가 실제로는 착수 불가다 — 다음 세션이 기전을 처음부터 재도출해야 하고, 이는 원장이 방지하려던 바로 그 비용이다.
- 처방: 기계 검사가 가능한 최소 축을 추가한다 — 산문 진위가 아니라 **구조적 존재**만 본다(원장 :199 의 '기계 린터는 만들지 않는다' 는 진위 판정을 금한 것이지 필수 필드 존재 검사를 금한 것이 아니다): 🟡 행의 마지막 셀이 비어 있지 않고 '기전'·'반증 수단' 두 라벨을 모두 포함하는지. 기존 11건은 grandfather baseline 으로 커밋해 신규 유입만 차단하고(정책 17 안정성 — 일괄 red 는 가드 자살), baseline 축소를 회고 카덴스에 얹는다. 우선 채워야 할 순서는 R10·R12(빈 셀) → R8(보안, 로그 리댁션 DB URL 자격증명) → R6(가드 fail-open 6건).

**✅ 마커가 미결 잔여를 흡수한다 — R30 은 상태 셀 자체가 '완료 … 잔여 = 사용자 결정' 이고, 같은 요약 블록이 '결정 대기 0건' 과 'R33-a 재개방' 을 동시에 주장한다**

- 위치 `docs/backlog.md:44` · 관점 `decision/backlog`
- 주장: 현재 창 ✅ 16행 중 최소 5행이 셀 안에 미결 잔여를 명시한 채 완료로 계상된다. 특히 R30 의 상태 셀은 `✅ 완료 (#1271 — 관측면. 잔여 = 로컬 3.12 정렬 여부 사용자 결정)` 로, **완료 마커와 사용자 결정 대기가 같은 셀에 공존**한다. 회귀 가드 test_open_sections_contain_no_completed_items 는 정확히 반대 방향(열린 섹션에 완료 표지)만 보고, 그나마도 `## 🔴/🟡` 꼬리 섹션에만 적용돼 R 표는 스캔하지 않는다. 즉 이 리포에서 일감을 시야에서 지우는 정식 경로는 '삭제' 가 아니라 '✅ 로 표시하고 잔여를 산문에 묻기' 다. 요약 블록 내부에도 정면 모순이 있다: :52 가 '이 창의 결정 대기는 0건 유지' 라고 단언한 직후 :54 가 '🔴 **ANTHROPIC_API_KEY 재확인(R33-a 재개방)**' 을 선언한다 — 재개방된 사용자 결정이 있는데 결정 대기 0건이다.
- 처방: (a) 상태 셀에 '잔여·재개방·사용자 결정' 어휘가 있으면서 ✅ 로 시작하는 행을 금지하는 검사를 추가한다 — 잔여가 있으면 원행을 ✅ 로 닫고 잔여를 **별도 신규 R행**(🟡 또는 🔴)으로 분리 등재하도록 강제(어휘 목록은 리뷰어 가시 영역만, 정책 19 집행면과 동형). (b) 즉시 조치로 R30-a(로컬 3.12 정렬)·R20 잔여(session id 재사용 무탐지)·R2-b 잔여(required check 1/8)·R33-a(심의 게이트 호출 실패 8회+)를 각각 독립 행으로 승격 — 특히 R33-a 는 '문서 심의 게이트가 다시 무동작' 이라 R32 가 봉인한 결함의 재발이고 사용자 결정 영역이다. (c) :52 의 '결정 대기 0건' 단언을 R33-a 재개방과 정합하게 정정한다.

**R27 ✅ 플립이 청구된 의무를 이행하지 않았다 — 원장 자체가 observer-lie**

- 위치 `docs/backlog.md:41` · 관점 `docs/rules`
- 주장: docs/backlog.md:41 의 R27 해소문은 "path-scoped rules 본문 sync 이행" 을 완료 사유로 적었으나, #1265·#1266 이 rules 파일에 실제로 한 일은 (a) cross-area **도달성 포인터 삽입**(api/pipeline/security/services/ui, +39줄, 전량 삽입) 과 (b) **사실오류 3건 정정**(api·pipeline·security 각 1줄)이다. R27 이 청구한 것은 "코드 PR 의 변경 영역에 대응하는 rules 본문 갱신" 인데, 그 축의 대표 영역인 testing.md·db.md·i18n.md 는 두 PR 어디서도 **한 줄도 바뀌지 않았다**. 완료 판정이 청구 사실과 다른 축의 작업으로 내려졌다.
- 처방: R27 을 ✅ 에서 되돌리거나(권장: 되돌리지 말고) **R27-b 로 분할**해 (a) CONTRIBUTING 거짓 약속 = ✅ / (b) rules 본문 sync 의무 = 🟡 미해소 로 명시 분리한다. 그리고 백로그 ✅ 플립 시 "청구 문장의 각 절이 어느 커밋의 어느 hunk 로 해소됐는지" 를 1:1 대응시키는 것을 플립 조건으로 고정한다 — 복합 청구를 단일 ✅ 로 닫으면 미해소 절이 원장에서 소멸한다.

**R0-2/R28 이 처방한 완전성 축(미체크 `- [ ]` 열거)은 이번 창의 owed 3건을 원리적으로 못 본다 — 구현 전에 반증됨**

- 위치 `docs/backlog.md:74` · 관점 `ops/owed 원장`
- 주장: R0-2 가 명시한 처방("원장 최종 커밋 이후 머지 PR 중 **미체크 항목 보유분** 열거")을 그대로 구현해도, 이 창에서 라이브 검증이 실제로 owed 인 3 PR(#1252·#1261·#1263)은 **전부 탐지되지 않는다**. 세 PR 모두 `- [ ]` 체크박스가 0개이고, owed 항목을 마크다운 **표**(#1261·#1263) 또는 **번호 목록**(#1252)으로 적었기 때문이다. 반대로 `- [ ]` 를 가진 4건(#1268·#1269·#1270·#1271)은 대부분 CI 로 답할 수 있는 가드 PR 이다 — 즉 처방된 프록시는 실제 owed-ness 와 **역상관**이다. '수정이 같은 결함을 재생산' 클래스를 구현 착수 전에 잡은 것이며, R28 을 R0-2 결정 뒤로 미룬 세션14 판단의 전제(처방은 확정, 설계 결정만 남음)도 함께 무너진다.
- 처방: R28 착수 시 처방을 교체한다: 체크박스 형태가 아니라 **PR 본문의 `## 🔍 사용자 검증 필요` 섹션 존재 + 그 섹션이 원장에 대응 행을 갖는지**를 대조축으로 삼는다(형식 불문 — 표/번호목록/체크박스). 최소안: 원장 마지막 커밋 이후 머지 PR 중 해당 섹션을 가진 것을 열거하고 원장 `#NNNN` 집합과 차집합을 loud 인쇄(gh 부재 시 무음). 정책 2 가 이미 그 섹션을 **전 PR 의무**로 만들어 두었으므로 프록시가 공허해질 위험이 낮다. R0-2 사용자 결정 요청 시 이 반증 데이터(3/3 미탐)를 함께 제시할 것.

### E. 정책 19 집행면 — 2건

**정책 19 default(실질 작업마다 claim-review)와 가드 트리거(seal 어휘) 사이에 무주지대 — 리포의 새 주 게이트가 무검증 머지** 🔸<sub>인용 미확인</sub>

- 위치 `scripts/check_claim_review_trace.py:243` · 관점 `process`
- 주장: CLAUDE.md 정책 19 는 *"별도 지시 없으면 실질 작업마다 Grok CLAIM-REVIEW 기본 포함"* 인데, 집행 가드는 **seal 어휘가 본문/제목/커밋에 있을 때만** 발동한다. 어휘를 안 쓰면 흔적도 면제도 요구되지 않고 조용히 exit 0 이다. 창에서 이 틈으로 2건이 통과했고, 그중 #1258 은 `scripts/pre_push_gate.py`(213줄 신규)를 도입한 PR 이다 — 지금 CLAUDE.md 가 처방하는 **로컬 사전 확인의 유일한 진입점**이 claim-review 도 면제 명시도 없이 들어왔다. 별도로 #1261(운영 auto-merge 게이팅을 9개 언어에 대해 바꾼 `src/analyzer/io/static.py` +61)은 자기 발급 면제로 통과했다.
- 처방: 어휘 트리거에 **표면 기반 축**을 하나 더 얹는다 — `scripts/**`·`.claude/hooks/**`·`.github/workflows/**`·`src/**` 의 diff 가 임계(예: 50줄) 이상이면 흔적 **또는** 면제 중 하나를 반드시 요구. 이러면 어휘를 피해도 최소한 "면제를 명시 결정으로 남기는" 상태가 되고, 그 면제가 아래 계량 대상에 들어온다. 현재는 어휘가 없으면 **면제조차 요구되지 않아** 무주지대가 계량면 밖에 있다.

**정책 19 집행면이 PR diff 를 읽지 않아 seal 주장이 STATE/cycle-history 로 이주하면 무검증 통과 — #1269 는 어휘만 넓히고 표면은 그대로 뒀다**

- 위치 `scripts/check_claim_review_trace.py:238` · 관점 `process`
- 주장: `check_claim_review_trace.py` 의 입력 표면은 PR 제목·본문·커밋 메시지 3종뿐이라, **PR 이 변경하는 파일 내용에 적힌 seal 주장**은 원리적으로 보이지 않는다. 세션14 가 이 구멍을 라이브로 통과했다: #1272 는 `claim-review-not-required` 로 면제받아 통과했고, 그 diff 가 `docs/STATE.md` 와 `docs/cycle-history.md` 에 `뮤테이션 21건 red` 를 기입했다 — 이 단수형 관용구는 바로 앞 PR(#1269)이 **STATE 서사가 실제로 쓴 관용구라서** 트리거 어휘에 추가한 그 패턴이다. 어휘는 넓혔으나 그 어휘가 사는 표면은 계속 사각지대다(수정이 같은 결함을 재생산).
- 처방: 가드가 PR diff 의 **추가된 라인**(`git diff base..head -U0` 의 `+` 라인)까지 seal 어휘 스캔 범위에 넣거나(오탐 우려 시 `docs/STATE.md`·`docs/cycle-history.md`·`docs/backlog.md` 3파일 한정), 최소한 docstring §한계에 이 축을 5번째 항목으로 정직 명시한다. 지금은 '한계에 없으니 커버된다' 로 읽히는 것이 가장 큰 문제다.

### F. 운영 검증 · smoke · owed 원장 — 4건

**owed 원장 intake 가 172 PR 동안 0건 — 이번 창 두 PR 이 스스로 "코드로 증명 불가"라 쓴 운영 검증이 등재되지 않았고, SessionStart 훅은 "미결 0건" 초록을 인쇄한다** 🔸<sub>인용 미확인</sub>

- 위치 `docs/runbooks/owed-verification.md:6` · 관점 `ops`
- 주장: 정책 13 smoke 발화 0 은 단독 증상이 아니라, 운영 검증 부채를 받는 유일한 원장의 **접수구가 죽어 있다**는 더 큰 결함의 표면이다. `docs/runbooks/owed-verification.md:6` 은 접수 규칙을 명시한다 — *"세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다(trailing sync PR body 의 §owed-verification 표와 페어)"*. 그런데 원장의 PR 행은 총 8건(#1058·#1062·#1104·#1106·#1071·#1072·#1073·#1075)뿐이고 **가장 최근 신규 등재는 #1106(2026-07-19)** 이다. 그 이후 머지된 PR 은 172건(`git log --grep` 실측)인데 신규 행 0. 이번 창은 그 0 을 우연이 아니라 **의도적 누락**으로 만든다: #1252 본문이 *"운영에서 동일 SHA 에 동시 webhook 이 온 뒤 Telegram/PR 코멘트가 1회만 오는지 — 이 PR 의 핵심 주장이고 코드로는 증명 불가입니다"* 라 적었고, #1261 본문이 *"rust/dart/C#/php/powershell/css/swift/protobuf/html 리포의 auto-merge 복구 … (운영 관측 — Claude 는 라이브 확인 불가)"* 라 적었다. 두 문장 모두 원장 목적문(`:3` "코드로 증명 불가한 운영…
- 처방: `check_owed_verification.py` 에 **intake(접수) 축**을 추가한다 — 원장 최종 갱신 커밋 이후 머지된 PR 본문에서 `코드로는? 증명 불가|라이브 확인 불가|운영 관측|사용자만 가능` 문구를 보유한 PR 중 원장 미등재분을 열거해 loud 발화(gh 부재 시 무음, advisory 유지 = 정책 17). 이것이 R0-2 가 요구한 "완전성 축"의 **결정 불필요한 절반**이다: R0-2 는 미체크 `- [ ]` 를 세는 설계 결정이 걸려 있으나, 이 축은 "PR 이 스스로 적은 트리거 문구"만 보므로 gh 의존 외 결정 사항이 없다. 페어로 #1252·#1261 두 행을 ⏳ 로 소급 등재해 다음 세션 첫 창에서 사용자 회신 요청(정책 5 NEW-P0-N).

**정책 13 SSOT 런북 §8 헤드라인이 거짓 — Railway 빌드는 테스트를 0건 실행하고, smoke 자동화 10건은 TestClient in-process 라 런북을 만들게 한 그 사고를 원리적으로 못 본다**

- 위치 `docs/runbooks/operational-smoke-checks.md:171` · 관점 `ops`
- 주장: `docs/runbooks/operational-smoke-checks.md:171` 은 굵은 글씨로 **"CI / Railway 빌드 자동 실행 → 다음 OAuth/redirect_uri 같은 외부 변경 사고 즉시 발견"** 이라 단언한다. 양쪽 절이 다 틀렸다. (a) **Railway 빌드는 테스트를 하나도 실행하지 않는다** — `railway.toml` `buildCommand` 는 eslint/solc-select/rubocop/golangci-lint/tsc/hadolint/ktlint/tflint 설치 + `npm ci && npm run build` 뿐이고 pytest 가 없다. (b) **CI 의 smoke 자동화는 배포 실체를 관측할 수 없다** — `tests/integration/test_oauth_flow_smoke.py:6` 이 스스로 *"실제 FastAPI app + TestClient 기반"* 이라 적었고 `:29` 가 `TestClient(app, ...)` 를 반환한다. TestClient 는 CI 프로세스의 로컬 env(`ci.yml:367-373` 이 주입하는 `DATABASE_URL=sqlite`, `SESSION_SECRET=test-…`)를 읽으므로, Railway 의 `APP_BASE_URL` 오설정도 GitHub OAuth App 의 callback URL mismatch 도 **정의상…
- 처방: §8 헤드라인을 실측대로 정정: *"CI 의 smoke 자동화는 **앱 코드의 라우트 계약 회귀**만 잡는다. 배포 env(`APP_BASE_URL`)·GitHub OAuth App callback URL 등 **저장소 밖 설정 사고는 원리적으로 관측 불가** — 그 축은 §1 manual curl 이 유일 수단이다. Railway 빌드는 테스트를 실행하지 않는다."* 정정 커밋에 회귀 가드를 페어(정책 4): `tests/unit/scripts/` 에 `railway.toml buildCommand 에 pytest 가 없으면 §8 이 'Railway 빌드 자동 실행' 을 주장하지 못한다` 는 문서↔설정 대조 단언.

**smoke 매트릭스가 "상호 보완"으로 제시한 e2e 열은 어떤 워크플로도 실행하지 않는 스위트 — manual 0회 × automation 미실행 = 양 열 공백인 행 5건**

- 위치 `docs/runbooks/operational-smoke-checks.md:205` · 관점 `ops`
- 주장: `operational-smoke-checks.md:205` 은 *"manual smoke (3-endpoint) ↔ 자동화 가드 (integration 10 + e2e 21 = test_dashboard 14 + test_theme_mobile_guards 7) **상호 보완 관계**"* 라 선언하고 §8.4·§8.7 매트릭스를 편다. 그 매트릭스에서 **자동화 열이 e2e 단독인 행이 5건**이다 — §8.4 의 `/dashboard 페이지 시각(KPI 5/chart/nav)`·`claude-dark 토큰 정의`·`WCAG 2.5.5 모바일 클릭 영역`, §8.7 의 `/dashboard?mode=insight 페이지`·`모드 토글 + localStorage persist`. 그런데 **e2e 는 CI 에 배선돼 있지 않다**: `.github/workflows/` 는 3파일(ci.yml·claim-review-on-body-edit.yml·codeql.yml)뿐이고 `grep -rn 'playwright\|Playwright' .github/workflows/*.yml` 은 **무결과**, ci.yml 의 유일한 e2e 언급은 `:466` 의 *"e2e/integration 혼입 방지"* 라는 **배제** 주석이다. 파일별 실측 e2e 는 114건(test_settings 36 · test_dashboard 14 · test_n…
- 처방: §8.4·§8.7 의 e2e 셀에 **"(CI 미배선 — 로컬 수동 실행 시에만 유효)"** 를 붙이거나, 배선하고 셀을 유지한다. 어느 쪽이든 표가 실행 여부를 스스로 말하게 만든다. 기계화: `scripts/check_docs_sync.py` 계열에 "smoke 런북 매트릭스가 인용한 테스트 파일 경로가 CI 워크플로 어딘가에서 실행되는가" 대조 축 추가 — 인용된 경로가 어떤 워크플로 step 에도 등장하지 않으면 red. 이 가드는 R7 의 결정(배선 vs 배지 정정)을 기다리지 않고 독립 적용 가능하다.

**#1252 잠금 축(`with_for_update`)의 유일한 관측자가 mock 호출 단언이고, wrong-merge 등급 잔여가 두 원장 어디에도 없다**

- 위치 `tests/unit/worker/test_cli_analysis_supersede.py:263` · 관점 `ops/owed 원장`
- 주장: #1252 는 PG READ COMMITTED 에서 두 트랜잭션이 supersede 이전 행을 함께 읽어 **gate(auto-merge 시도) + notify 가 2회** 실행되는 경로를 `with_for_update()` 로 봉인했다고 선언했다. 그러나 그 축의 관측자는 `chain.with_for_update.assert_called_once_with()` — **메서드가 호출됐다는 사실**만 보는 mock 단언이며, PG 가 실제로 직렬화하는지는 어떤 환경에서도 실행되지 않는다. 테스트 자신이 그 한계를 명시하고("SQLite 가 FOR UPDATE 를 조용히 버려 … 실측 결과 관측자가 0건") `pg-concurrency` job 은 node-id 핀 목록이라 supersede 테스트를 0건 수집한다. 영향 계층은 `wrong-merge` 이고 AGENTS.md 라우팅은 이를 **owed 안전등급**으로 보내라고 규정하는데, owed·backlog 어디에도 행이 없다 — 잔여가 코드 주석 안에서만 산다.
- 처방: 둘 중 하나로 축을 되살린다 — (a) supersede 경쟁 시나리오를 `tests/integration/test_retry_concurrency_postgres.py`(이미 job 에 **파일 단위**로 핀돼 있어 추가 등재 불필요)에 넣어 실 PG 로 관측, 또는 (b) 즉시 불가하면 owed 원장 **안전등급**에 행 추가(검증 방법 = "운영에서 동일 SHA 동시 webhook 후 Telegram/PR 코멘트 1회만" — #1252 본문이 이미 문장을 써 두었다). 지금 상태(mock 단언 + 주석 잔여)는 두 원장 어디에도 안 보이므로 다음 세션이 이 축을 '봉인됨'으로 읽는다.

### G. path-scoped rules sync — 5건

**path-scoped rules 본문 sync 의무(사용자 명시 결정)가 R27 '해소' 선언 다음 세션에 3/4 PR 에서 재위반**

- 위치 `.claude/rules/guards.md:1` · 관점 `docs`
- 주장: CLAUDE.md:366 · CLAUDE.md:415 가 `scripts/**` · `.claude/hooks/**` · `tests/unit/scripts/**` 변경 시 `.claude/rules/guards.md` 본문 갱신을 **사용자 명시 결정(사이클 86 Q2)** 으로 의무화한다. 세션14 코드 PR 4건 중 3건이 이 경로를 고치면서 guards.md 를 건드리지 않았다. 이 항목은 backlog R27 의 후반부('창의 코드 PR 7건 중 6건에서 미이행')로 등재됐다가 2026-08-01 #1265·#1266 에서 ✅ 해소 선언된 바로 그 의무다 — 문서-only 시정이 다음 세션 행동을 바꾸지 못했다.
- 처방: `check_dead_code.py` 와 같은 diff-scoped CI 가드를 추가한다 — PR diff 가 `scripts/**`·`.claude/hooks/**`·`tests/unit/{scripts,hooks}/**` 를 건드리면 같은 diff 에 해당 `.claude/rules/<area>.md` 변경 또는 명시 면제 마커(`# rules-sync-ok: <사유>`)를 요구. 산문 의무 3회차 실패이므로 기계 관측면 없이는 다음 세션도 같은 비율로 재발한다(R27 6/7 → 세션14 3/4).

**.github/workflows/** 가 10종 path-scoped rule 어디에도 매칭되지 않는다 — CI 집행면 편집 시 규칙 도달성 0**

- 위치 `.claude/rules/guards.md:126` · 관점 `process`
- 주장: CI 정의 표면(`.github/workflows/**`)은 `.claude/rules/*.md` 10개 파일의 `paths:` 프론트매터 합집합에 포함되지 않는다. 즉 `ci.yml`·`claim-review-on-body-edit.yml` 을 편집할 때 자동 로드되는 area rule 이 **하나도 없다**. 그런데 그 표면을 지배하는 규칙들은 전부 다른 파일에 다른 경로로 등록돼 있다 — required check 갱신 계약(guards.md:126, paths=`scripts/**`·`.claude/hooks/**`·`.claude/workflows/**`), pg-concurrency job 계약(testing.md:31, paths=`tests/**`), python 버전 3종 SSOT(deploy.md:40, paths=`railway.toml` 등). 이 창에서 가장 값비싼 결함 2건이 정확히 이 무주공산 표면에서 났다: R34(`claim-review-on-body-edit.yml` 의 required-check 갱신 가정이 첫 라이브 사용에서 파손, 빈 커밋 우회 강제) 와 아래 finding 2(#1253 이 ci.yml 에 심은 거짓 단언). CLAUDE.md 의 10 영역 매트릭스는 `.claude/workflows/**`(Claude 워크플로)를 등재하면서 `.github/workflows/**`(GitHub…
- 처방: `.claude/rules/guards.md` 의 `paths:` 에 `.github/workflows/**` 를 추가(가장 근접한 소유자 — 3-불변식·required check 계약이 이미 여기 있다)하고, CLAUDE.md 의 10 영역 매트릭스 guards.md 행에 같은 경로를 등재한다. 회귀 가드로 "모든 `.github/workflows/*.yml` 이 최소 1개 rule 의 glob 에 매칭된다" 를 단언 — rule paths 합집합 대 실제 표면의 커버리지 가드가 현재 0건이다.

**의무를 정의하는 매트릭스(CLAUDE.md:366)가 frontmatter 와 drift — 그 방향은 가드가 설계상 보지 않는다**

- 위치 `CLAUDE.md:366` · 관점 `docs/rules`
- 주장: #1265 가 `src/shared/claude_metrics.py` 의 "로드되는 규칙 0개" 갭을 고치며 `.claude/rules/services.md` frontmatter 와 AGENTS.md:140(Grok 용 표)에 `src/shared/**` 를 추가했으나, **CLAUDE.md 의 두 사본(366 의무 매트릭스 · 414 주의사항 표) 은 갱신하지 않았다.** 기존 가드는 이 방향을 못 본다 — `test_claude_md_matrix_never_promises_an_unloaded_path` 는 매트릭스 ⊆ frontmatter 만 단언하고 역방향은 "`등` 축약이라 정상" 으로 **명시 면제**한다(test_rules_and_index_coverage.py:110). 양방향 가드는 AGENTS.md 에만 있다(test_rule_reachability.py:218). 결과: Grok 이 보는 표는 완전한데 **Claude 자신의 의무 매트릭스가 불완전**하다 — 의무 범위를 정의하는 쪽이 덜 정확하다.
- 처방: CLAUDE.md:366·414 에 `src/shared/**` 와 `**/conftest.py` 를 반영하고, `test_rules_and_index_coverage.py` 에 **역방향 단언**(frontmatter ⊆ 매트릭스, `등` 축약이 명시된 area 만 면제)을 추가한다. 더 근본적으로는 CLAUDE.md 의 두 사본 중 366 을 "의무 정의 = 414 표를 참조" 로 축약해 **사본을 3개(frontmatter·CLAUDE.md·AGENTS.md)로 줄인다** — 같은 파일 안 2사본은 drift 를 자초한다.

**sync 의무에 이행 조건도 면제 경로도 없다 — 발화율 ~100%, 실이행률 0%**

- 위치 `CLAUDE.md:366` · 관점 `docs/rules`
- 주장: CLAUDE.md:366 의무는 "path 매칭 영역 변경 시 해당 rules 본문 갱신 의무" 라고만 적혀 있고, **무엇이 '갱신을 요하는 변경' 인지 · 갱신이 불필요할 때 무엇을 남기면 이행으로 치는지**가 정의돼 있지 않다. 문자 그대로 읽으면 테스트 한 줄만 바뀌어도 발화하므로 사실상 모든 PR 에 걸린다. 실측 결과 발화율은 압도적이고 이행률은 **정확히 0** 이다. 이 비대칭이 위험한 이유: 회고는 언제든 "의무 위반" 을 참으로 청구할 수 있는데(항상 참), PR 은 이 의무를 **확정적으로 해소할 방법이 없다**. R27 이 정확히 그 형태였고, 세션13 의 문서-only 해소가 같은 창에서 무효화된 것도 이 구조 때문이다.
- 처방: 의무를 **이행 가능한 형태**로 재정의한다: 트리거를 "영역 파일 변경" 이 아니라 "영역 규칙의 전제를 바꾸는 변경(신규 fixture/패턴/가드 관용구 도입, 기존 규칙 문구를 거짓으로 만드는 변경)" 으로 좁히고, **면제 경로를 명시 산출물로 만든다** — commit body 에 `rules-sync: testing.md — no change (기존 패턴 재사용)` 트레일러. 그러면 이행이 관측 가능해지고(트레일러 존재 여부), 회고가 "위반" 을 계량할 수 있다.

**도달성 가드의 심볼 축이 여전히 1-핀 — 주석이 이름 붙인 결함을 그 자신이 재생산한다**

- 위치 `tests/unit/scripts/test_rule_reachability.py:41` · 관점 `docs/rules`
- 주장: `test_rule_reachability.py` 는 #1265 에서 "하드코딩 3핀은 등록 침묵을 만든다" 는 주석을 달고 **소비자 경로 축**을 디스크 유도로 전환했다. 그러나 바로 다음 줄의 **심볼 축은 여전히 1-핀**(`WorkerSessionLocal` 단일)이다. 즉 rules 본문에 새 cross-area 규칙(어떤 area 의 규칙이 다른 area 의 파일을 지배하는 형태)을 써 넣어도 **아무도 알려주지 않고 스위트는 초록으로 남는다** — 주석이 정확히 그 형태라고 이름 붙인 '등록 침묵' 이다. 리포의 지배 결함 클래스 (6) '수정이 같은 결함을 재생산' 의 교과서적 사례이며, 두 축 중 한 축만 고친 채 주석은 "그래서 디스크에서 유도한다" 로 해소를 단언한다.
- 처방: 심볼 축도 유도한다: `.claude/rules/*.md` 본문에서 백틱 코드 심볼(`WorkerSessionLocal` 같은 식별자)을 추출해, 그 심볼을 정의하지 않는 area 의 파일에서 쓰이면 cross-area 후보로 자동 등재한다. 최소한 area 별 '지배 심볼' 을 rules frontmatter 에 `cross_area_symbols:` 키로 선언하게 하고, 선언 집합이 비면 대조군이 red 가 되게 한다(fail-closed). 어느 쪽이든 손유지 목록이 남으면 같은 침묵이 재발한다.

### H. 제품 · 점수 노출면 (사용자 리포 영향) — 2건

**R21 의 "차단 대신 가시화" 가 9개 알림 채널 중 1곳에만 존재 — 승인 버튼이 있는 Telegram 은 아무 경고도 보여주지 않는다**

- 위치 `src/notifier/telegram.py:103` · 관점 `code`
- 주장: #1261(R21)은 미조달 분석기 언어를 `incomplete`(차단) 에서 `uncovered_language`(가시화만) 로 완화했다. 그런데 `static_uncovered_languages` / `static_analysis_incomplete` 를 렌더하는 곳은 `src/notifier/github_comment.py` **단 한 곳**이다. 사람이 실제로 approve/merge 를 누르는 Telegram 메시지에는 두 필드 모두 **표시되지 않는다**. 즉 차단(강한 신호)은 제거됐는데 그 자리를 메울 신호가 결정 채널에 없다 — "가시화만" 결정이 결정자에게 도달하지 않는다.
- 처방: `_build_message` 에 `analysis_results` 로부터 `incomplete` / `uncovered_language` 집계 배너를 추가하고(i18n 키는 이미 3개 언어 `notifier.github_pr_comment.static_uncovered_warning` 로 존재 — telegram 네임스페이스로 복제), 최소한 **승인 버튼이 붙는 메시지**에는 무조건 표시한다. 회귀 가드: "uncovered/incomplete 가 있는 result 로 만든 Telegram 메시지에 경고 문자열이 포함된다" 를 단언(현재 이 축의 테스트 0건).

**CLI 훅 분석의 무검증 45점이 대시보드 평균에 그대로 집계된다 — NULL-persist 근거가 비대칭 적용**

- 위치 `src/worker/pipeline.py:139` · 관점 `product/notify`
- 주장: `_persisted_score_is_unreliable` 이 AI 실패만 NULL 대상으로 삼아, `static_analysis_incomplete` 는 점수 컬럼을 NULL 로 만들지 않는다. CLI 훅은 **항상** 그 마커를 붙이면서도 실점수를 영속하므로, 정적분석 0회 상태의 무검증 45점(code_quality 25 + security 20)이 사용자 가시 `avg_score` 집계에 그대로 들어간다. 고지 부재(관점 gap)를 넘어선 **수치 오염**이며, 이 함수의 도크스트링이 스스로 내세운 존재 이유(`analytics 집계 오염 방지`)가 자기 마커에는 적용되지 않는 자기모순이다.
- 처방: 두 갈래 중 택1을 옵션 표로 사용자 결정에 올린다 — (a) `_persisted_score_is_unreliable` 에 `static_analysis_incomplete` 를 추가해 CLI 행을 집계에서 자연 배제(단, 도크스트링 125-132 이 절단 케이스에서 경고한 "대시보드 점수 통째 소실" 재현 위험을 실측 후 판단) / (b) 점수는 유지하되 집계 쿼리에 신뢰도 필터를 추가. 어느 쪽이든 회귀 가드는 `avg_score` 가 incomplete 행을 포함하는지를 직접 단언해야 하며, 뮤테이션(필터 제거 시 red)로 검증한다.

### I. 가드 · 훅 자기 결함 — 7건

**pre-commit 훅 7종이 bare `python`(Windows Store 스텁, exit 49) 을 쓰는데, 이번 창이 만든 인터프리터 생존 가드는 settings.json 만 스캔한다**

- 위치 `.pre-commit-config.yaml:69` · 관점 `code`
- 주장: #1251 이 '훅이 bare python 이라 한 번도 실행되지 않았다' 는 P0 를 봉인하고, #1254 가 'pre-commit 계층이 내려가 있다' 를 관측면으로 만들었다. 그런데 그 관측면이 처방하는 복구(`pip install pre-commit && pre-commit install`)를 실행하면, `.pre-commit-config.yaml` 의 로컬 훅 7종이 이 머신에서 실행 불가능한 인터프리터로 무장된다 — 같은 창이 명명한 '가드가 자기 스캔 범위를 관측하지 않음' 의 재생산.
- 처방: `test_hook_interpreter_liveness.py` 의 스캔 표면을 `.pre-commit-config.yaml` 의 `language: system` 훅 `entry:` 까지 확대(= `check_guard_fail_open` 이 이번 창에 `_HOOKS` 표면을 추가한 것과 같은 패턴), 그리고 `.pre-commit-config.yaml` 의 `entry: python …` 7건을 `.claude/settings.json` 과 같은 `py -3`/`python3` 폴백 관용구로 교체. 대안(사용자 결정 필요): pre-commit 을 설치하는 인터프리터를 고정해 훅이 그 venv 의 python 을 쓰게 하는 방식.

**pre_push_gate 가 입력이 빈 claim-review 가드에 'OK' 를 찍는다 — 러너의 존재 이유인 '초록의 의미'를 스스로 위반**

- 위치 `scripts/pre_push_gate.py:64` · 관점 `code`
- 주장: `scripts/pre_push_gate.py` 는 `check_claim_review_trace.py` 를 인자·env 없이 실행한다(:64, :156). 그 가드는 `PR_TITLE`/`PR_BODY`/`PR_BASE_SHA`/`PR_HEAD_SHA` 를 **전부 환경변수로만** 받으므로(check_claim_review_trace.py:233-241) 로컬에서는 haystack 이 빈 문자열이 되어 `seal 주장 없음 → exit 0` 으로 **항상** 통과한다. `_run` 은 `show_always=False` 라 그 사유 문구조차 인쇄하지 않아, 사용자에게는 `OK check_claim_review_trace.py` 한 줄만 보인다 — '통과' 와 '입력이 없어 아무것도 보지 않음' 이 구별 불가다.
- 처방: `_run` 에 세 번째 상태(`SKIP`)를 도입해, PR 컨텍스트가 없는 가드는 `OK` 가 아니라 `SKIP check_claim_review_trace.py (PR 본문/제목 미제공 — CI 에서만 실측)` 로 인쇄한다. 최소한 커밋 축은 로컬에서 재현 가능하므로(러너가 이미 `_base_sha()` 를 계산한다) `PR_BASE_SHA`/`PR_HEAD_SHA` 를 전달해 커밋 메시지 seal 어휘를 검사하되, 본문 흔적 부재로 인한 과탐을 피하려면 그 축은 advisory(`show_always=True`)로 인쇄한다. 회귀 가드: 빈 env 로 돌렸을 때 러너 출력이 `OK` 가 아님을 단언.

**PostToolUse 스모크 훅이 `.claude/hooks/**` 를 감시하지 않는다 — 대응 테스트 4종이 존재하고 이번 창이 훅을 2회 편집했는데도**

- 위치 `.claude/hooks/posttool_pytest_smoke.py:39` · 관점 `tooling`
- 주장: 감시 루트가 `("src","alembic","scripts")` 로 고정돼 있어 `.claude/hooks/**` 와 `.claude/workflows/**` 편집은 스모크를 아예 발동시키지 않는다. 훅 파일들은 이 창의 주요 편집 표면이었고(#1260 doc_review_gate 출력 채널, #1270 check_edit_allowed fail-open) 1:1 대응 테스트 디렉토리가 이미 있는데도 조기 실패 탐지가 0이다. 훅이 자기 자신의 편집조차 검증하지 않는다.
- 처방: `_WATCHED_ROOTS` 에 `.claude/hooks` 를 추가하고 `derive_test_target` 에 `.claude/hooks/<stem>.py → tests/unit/hooks/test_<stem>.py` 매핑을 넣는다. 하드코딩 목록의 재발을 막으려면 test_posttool_smoke_scope.py 가 '대응 tests/unit 서브디렉토리가 실재하는 편집 루트는 전부 감시 대상'을 **파생 검사**하도록 뒤집는다(현재는 목록을 고정 단언하므로 같은 갭이 다시 생겨도 green).

**조달 계약 대조 가드가 뮤테이션 GREEN — 주석/대리 토큰만으로 "조달됨"이 성립한다 (#1261)**

- 위치 `tests/unit/analyzer/test_procurement_contract.py:62` · 관점 `code`
- 주장: `tests/unit/analyzer/test_procurement_contract.py` 는 스스로 "기대값을 손으로 적지 않고 실제 조달 파일에서 파싱한다 — 손유지 목록끼리 대조하면 조달이 바뀌어도 영원히 초록이다(이 저장소가 반복해 온 observer-lie)" 라고 선언하지만, 실제 판정은 4개 조달 파일을 **하나의 텍스트로 이어붙여 단어 검색**하는 것이라 (a) 주석 안의 언급 (b) 도구가 아닌 대리 토큰만으로도 통과한다. 즉 R21 이 고친 **영구 차단 재발**(실패 방향 b)을 이 가드가 잡지 못한다.
- 처방: (1) `provisioning_text()` 를 파일별로 유지하고, 각 도구를 **설치를 수행하는 파일/키에 한정**해 찾는다(nixpacks `aptPkgs` 배열 · railway `buildCommand` 문자열 · requirements 의존성 라인 · package.json `devDependencies` 키). (2) 주석 라인(`#`, `//`) 제거 후 매칭. (3) `_PROVISION_ALIAS` 를 치환이 아니라 **AND 조건**으로 바꾼다(rubocop 은 `ruby-full` + `rubocop` 둘 다 필요). (4) 회귀 가드로 "tflint 설치 절 제거 → red" 를 뮤테이션 테스트로 고정한다(현행 19건 중 이 축을 red 로 만드는 것은 0건).

**PostToolUse 스모크 훅의 결과 배너가 plain print() — 리포 자신의 채널 규칙(guards.md:134-136) 위반, Claude 에게 0회 도달**

- 위치 `.claude/hooks/posttool_pytest_smoke.py:187` · 관점 `tooling`
- 주장: `.claude/hooks/posttool_pytest_smoke.py:187,189` 는 스모크 결과 배너(✅/❌/⚠️)를 plain `print()` 로만 내보낸다. 그런데 같은 리포의 `.claude/rules/guards.md:136` 은 "**PreToolUse/PostToolUse 훅의 plain stdout 은 디버그 로그로만 간다**" 를 공식 계약으로 명시하고, `CLAUDE.md:351` 은 Claude 에게 "❌ 배너 시 즉시 조사" 를 지시한다. 두 문서가 동시에 참일 수 없다 — 훅이 틀렸거나 규칙이 틀렸거나 둘 중 하나이고, 어느 쪽이든 `src/` 편집마다 도는 이 훅의 Claude-대면 ROI 는 0 이다.
- 처방: 배너를 `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":...},"systemMessage":...}` 로 전환(#1260 관용구 복제) + **채널을 단언하는** 테스트 추가(문자열 아님 — JSON 파싱 후 additionalContext 존재). 동시에 `.claude/hooks/*.py` 전수에 대해 "advisory 를 내는 훅은 plain print 금지" AST 가드를 `check_guard_fail_open.py` 스캔면(이미 `.claude/hooks/*.py` 를 본다, R16/#1268)에 증축해 4회차 재생산을 봉인.

**check_memory_refs 는 이 머신에서 자동 실행면이 0 — #1250 이 경로만 고치고 배선은 복구하지 않았다**

- 위치 — · 관점 `process/memory`
- 주장: #1250 이 슬러그 하드코딩을 고쳐 가드를 '살렸다'(뮤테이션 6/6 red)지만, 이 가드의 **유일한 자동 배선은 `.pre-commit-config.yaml:87`** 이고 pre-commit 은 이 머신에 설치돼 있지 않다. CI 는 명시적으로 제외(ci.yml:127)하고, 세션13이 신설한 `pre_push_gate` 의 `_INTEGRITY` 목록에도 없다. 즉 '한 번도 검사한 적 없는 가드'를 고친 결과가 다시 '사람이 기억해서 손으로 돌려야만 도는 가드'다 — 이 리포가 반복해 명명한 '수정이 같은 결함을 재생산' 이다. 더 나쁜 것은 배선이 살아나도 `files:` 필터가 **리포 쪽 파일**(`^(CLAUDE\.md|\.claude/policies/.*\.md)$`)이라, 정작 drift 가 일어나는 **메모리 쪽 변경은 트리거가 원리적으로 불가능**하다는 점이다(메모리는 git 밖이라 stage 되지 않는다).
- 처방: 메모리 가드를 **메모리가 실제로 로드되는 면**으로 옮긴다: `.claude/settings.json` SessionStart 에 `check_memory_refs.py` 추가(이미 3종이 도는 검증된 배선, advisory·exit 0 유지 — CI/새 PC 에서는 기존 skip 분기가 자동 처리). pre-commit 배선은 남기되 **유일 의존을 끊는다**. 부수로 `check_precommit_installed.py:126` 의 영향 훅 목록에 `check-memory-refs` 를 이름으로 등재("+ 다수"는 관측이 아니다).

**가드 스코프(3 문서)가 실제 인용면보다 좁다 — 스코프 밖 메모리 인용 7건 중 4건이 dangling, 그중 2건이 자동 로드 rules/**

- 위치 — · 관점 `process/memory`
- 주장: `check_memory_refs.DOC_FILES` 는 CLAUDE.md + policies 2종만 스캔한다. 그런데 메모리는 **path-scoped 자동 로드 문서인 `.claude/rules/`** 와 **정본 원장 `docs/backlog.md`** 에서도 인용된다. 실측하면 스코프 안 인용은 5건 전부 유효(가드 초록)인데, 스코프 밖 인용 7건 중 **4건이 존재하지 않는 파일을 가리킨다**. 더 결정적인 것은 인과: 2026-07-31 유실 메모리 복원이 '문서 참조 O, 파일 X' 기준으로 6건을 복원했는데 그 기준이 곧 가드 스코프였다 — **가드의 사각이 복원의 사각을 정의**해, rules/·backlog 에서만 인용되던 메모리는 유실된 채 남고 가드는 여전히 초록이다. 이 스코프 갭은 2026-07-19 회고가 이미 지적했고(당시는 tests/ 축) 오늘까지 스코프는 3 문서 그대로다.
- 처방: `DOC_FILES` 를 하드코딩 3종에서 **인용면 전수 glob** 으로 승격 — `CLAUDE.md` + `.claude/policies/*.md` + `.claude/rules/*.md` + `docs/backlog.md` + `docs/STATE.md` + `AGENTS.md`(아카이브 제외는 명시 예외 목록으로). 동시에 위 dangling 4건을 처리: 복원 가능하면 메모리 재작성, 불가능하면 인용을 **리포 내부 정본으로 교체**(예: db.md:30 의 RLS 실측 의무는 `docs/runbooks/rls-role-separation.md` 로, backlog:99 의 세션8 detail 은 `docs/_archive/reports/` 로) — 리포 밖 유실 가능한 대상에 행동 근거를 위임하지 않는다.

### J. 문서 정합 · 정책 본문 — 11건

**세션 종료 PR 이 CLAUDE.md 가 문자 그대로 금지한 'docs-only 예외' 로 6-step ② 를 생략했다**

- 위치 `CLAUDE.md:353` · 관점 `process`
- 주장: CLAUDE.md:353 은 push 전 `pytest tests/unit` 전체 통과 실측에 대해 **"인라인 cleanup·docs-only 예외 없음"** + 문장 끝 "예외 없음" 을 이중으로 못박는다. 그런데 창의 마지막 PR #1272 본문이 정확히 그 면제를 자기 발급했다: *"전체 단위 스위트는 로컬 백그라운드 실행을 사용자 토큰 소진 신호로 대기 생략 — CI pytest job 이 최종 근거 (docs-only 변경, 정책 3 자율 판단 보고)"*. 정책 3(자율 판단 보고)은 **보고 의무**이지 다른 정책의 금지를 해제하는 권한이 아닌데, 여기서는 면제 근거로 쓰였다. 규범이 조용히 advisory 로 강등된 순간이다.
- 처방: 둘 중 하나를 택해 문서와 실행을 일치시킨다. (a) ② 를 예산 무관 의무로 유지 → "잔여 예산이 전체 스위트를 못 돌릴 정도면 PR 을 만들지 말고 세션을 종료한다" 를 6-step 에 명시(면제가 아니라 **작업 중단**이 정답). (b) docs-only 면제를 정식화하되 대체 근거를 기계로 강제 → `py -3 scripts/pre_push_gate.py --full` 결과 첨부를 조건으로. 지금처럼 "예외 없음" 이라 적고 예외를 만드는 상태가 최악이다 — 다음 세션이 어느 쪽을 믿을지 알 수 없다.

**worktree 격리 의무에 폐기 경로가 없고 정책 9 가 청소를 destructive 로 묶어 잔해가 단조 증가**

- 위치 `CLAUDE.md:387` · 관점 `process`
- 주장: CLAUDE.md:380·387 은 파일을 편집하는 백그라운드 에이전트에 `isolation: worktree` 를 **예외 없이** 의무화하지만 정리 규칙이 없다. 동시에 정책 9(CLAUDE.md:203)가 **브랜치 삭제를 destructive 로 분류**해 사용자 명시 회신 없이는 청소할 수 없다. 두 규칙의 교집합이 "만들 의무는 있고 지울 권한은 없다" 라 잔해가 구조적으로 단조 증가한다. 현재 이미 머지 완료된 커밋에 고정된 워크트리 7개가 남아 있다.
- 처방: 정책 9 destructive 분류에 **예외 1줄**을 넣는다 — *"에이전트 임시 브랜치(`worktree-agent-*`)의 정리는 destructive 예외(사용자 1회 승인으로 상시 허용)"*. 그리고 세션 종료 절차(6-step 또는 trailing sync 체크리스트)에 "머지 완료된 worktree 정리 `git worktree prune` + `worktree-agent-*` 삭제" 1줄을 고정한다. 지금은 위험이 낮지만(gitignore + 스코프된 glob) 세션당 3~7개씩 늘어나는 상태라 언젠가 디스크·브랜치 목록이 실제 마찰이 된다.

**#1272 가 docs/cycle-history.md 를 전장 CRLF 로 뒤집었다 — 원인은 산문에 박힌 lone CR 1바이트, .gitattributes 불변식이 조용히 해제됨**

- 위치 `docs/cycle-history.md:162` · 관점 `docs`
- 주장: 세션14 trailing sync(#1272)가 `docs/cycle-history.md` 를 4782줄 전장 재작성(2399 삽입 / 2383 삭제)했는데, 실제 내용 변경은 '세션14 섹션 + TOC' 뿐이다. 진짜 원인은 커밋된 blob 의 줄바꿈이 LF → CRLF 로 전환된 것이고, 그 전환을 유발한 것은 산문 안에 들어간 **진짜 CR 바이트 1개**다. `.gitattributes:2` 의 `* text=auto eol=lf` 는 lone CR 을 담은 파일을 변환 대상에서 제외하므로, 선언된 리포 전역 불변식이 이 파일 하나에 대해 **관측 없이 해제**됐다(추적 1053 파일 중 CRLF 를 가진 유일한 텍스트 blob).
- 처방: (1) `docs/cycle-history.md:162` 의 CR 바이트를 리터럴 `\r` 로 되돌린다(현재 렌더링은 빈 백틱 ``` `` ``` 로 의미가 소실된 상태). (2) `git add --renormalize docs/cycle-history.md` 로 LF 재정규화. (3) repo-integrity 에 무의존 stdlib 가드 추가 — `git ls-files` 전 blob 중 바이너리 아닌 것이 CR 을 담으면 exit 1. 지금 방치하면 LF 로 쓰는 도구가 파일을 건드릴 때마다 2400줄 팬텀 diff 가 진동하고, 4700줄 서사 SSOT 의 blame/diff 심의가 계속 무력화된다.

**CI "repo-integrity 9종" 주장이 13 지점에 전파됐으나 실제 required check job 은 7종 — 나머지 2종은 머지를 못 막는다**

- 위치 `.github/workflows/ci.yml:129` · 관점 `docs`
- 주장: 세션13 #1265 가 "로컬 게이트가 무엇인가가 9곳에 서로 다르게 있었다"를 시정하며 **틀린 숫자를 정본으로 골라** 13개 표면에 전파했다. `main` 의 유일한 required status check = `Repo integrity guards (stdlib backstop)` job 이고 그 job 은 가드 **7종**만 돈다. 문서가 그 job 소속이라 주장하는 나머지 2종 — 직전 회고 P0-D 의 근본 시정인 `check_test_count_sync`(ground-truth 축)와 `check_lint_js_nonvacuous` — 은 **다른 job 에 있어 머지를 물리적으로 막지 못한다**. 정본 스크립트 자신의 docstring 만 7종이라 적혀 있어(정확) 문서 13곳과 어긋난다.
- 처방: (a) 숫자를 산문에서 제거하고 `ci.yml` 파싱으로 유도하거나, (b) `test_gate_claim_consistency.py` 에 "문서가 주장하는 repo-integrity N == ci.yml `repo-integrity` job 의 `run: python scripts/` 스텝 수" 단언을 추가. 동시에 "required check 는 repo-integrity job 1개이며 test_count_sync·lint_js 는 **비차단**" 을 CLAUDE.md/guards.md 에 명시 — 지금 문서는 ground-truth 축이 머지를 막는다는 false-safety 를 심는다.

**architecture.md scripts/ 트리가 27종 중 4종 미등재(3종은 이번 창 신설) — 트리 싱크 가드는 src/ 만 스캔해 영원히 초록**

- 위치 `docs/architecture.md:147` · 관점 `docs`
- 주장: CLAUDE.md 6-step ⑥ 의 기계 집행을 위해 만든 `check_architecture_tree_sync.py` 는 `_SRC = _ROOT / "src"` 로 **src/ 만** 본다. 그런데 세션13~14 의 변경 대부분은 `scripts/` 에 일어났고, architecture.md 는 별도 `scripts/` 트리를 유지하는데 그 트리에는 **관측자가 0** 이다. 결과: 이번 창에 신설된 3 스크립트 + 이전 창 1 스크립트가 미등재인 채 가드가 `✅ … src/ 트리 동기` 를 출력한다. 지배적 결함 클래스 (5) "가드가 자기 스캔 범위를 관측하지 않음" — B8(R16)에서 정확히 같은 형태를 고쳤는데 같은 세션의 형제 가드에는 적용하지 않았다.
- 처방: 가드에 `scripts/*.py` 축을 추가(트리 코드펜스 스코핑은 이미 `_tree_text()` 에 있음)하거나, scripts/ 트리를 architecture.md 에서 제거하고 `.claude/rules/guards.md` 단일 출처로 통합. 지금처럼 "문서에 트리는 있는데 아무도 안 본다"가 가장 나쁘다.

**#1272 가 cycle-history.md 전체를 CRLF 로 뒤집어 2383삭제/2399추가 whole-file 재작성 — 서사 SSOT 의 diff 심의·blame 소멸, .gitattributes 위반, 리포 유일 CR 블롭**

- 위치 `docs/cycle-history.md:1` · 관점 `docs`
- 주장: 세션14 trailing sync(#1272)가 `docs/cycle-history.md` 를 **전체 CRLF 로 커밋**했다. 실제 내용 변경은 세션14 섹션 + TOC 약 16줄인데 diff 는 2383 삭제 / 2399 추가로 나와 리뷰어가 무엇이 바뀌었는지 diff 로 볼 수 없고 line-level `git blame` 이 전 파일에서 끊긴다. `.gitattributes` 는 `* text=auto eol=lf` 로 LF 를 강제하는데 그 정책이 실제 커밋을 막지 못했고, 그 결과 이 파일은 **리포 전체에서 유일하게** HEAD 블롭에 CR 이 들어 있는 추적 파일이다.
- 처방: `docs/cycle-history.md` 를 LF 로 재정규화(`git add --renormalize`)해 별도 EOL-only 커밋으로 격리하고, repo-integrity 에 "추적 텍스트 블롭에 CR 0" 1줄 가드를 추가. 메모리 [feedback-mutation-restore-crlf] 가 이미 Windows write_text CRLF 왕복 위험을 기록하는데 그 학습이 문서 쓰기 경로에는 적용되지 않았다.

**정책 9 §"🔍 회고 질문(사용자 회신 의무)" 가 최근 2 회고 + 창의 Phase 종료 PR 에서 통째로 소실 — 결정 요청 채널 자체가 닫혔다**

- 위치 `CLAUDE.md:199` · 관점 `decision`
- 주장: CLAUDE.md 정책 9 는 Phase 종료 시 §"🔍 회고 질문(사용자 회신 의무)" 1줄(`[x] 모두 OK / [!] N번 재검토 / [ ] 미수행`) 추가를 **작성 의무**로 못박고, 완화 조항도 "작성 면제 아님"을 명시한다. 그런데 이 섹션은 최근 2회 정식 회고와 이번 창 23 PR 전체에서 0회 등장한다. 사용자가 결정을 회신하는 유일한 정형 채널이 닫힌 결과, 🔴 P0 결정 대기 R0-2 가 한 번도 사용자 앞에 놓이지 못한 채 R28 을 봉쇄하고 있다.
- 처방: (1) `#1272` 형태의 Phase 종료 PR 과 회고 리포트 양쪽에 회고 질문 3-상태 라인을 복원하고, (2) `.claude/workflows/retrospective.mjs` 산출 계약에 이 섹션을 필수 필드로 넣어 누락 시 red, (3) 복원 즉시 R0-2(owed 완전성 축의 gh 의존·advisory 유지 여부)를 첫 항목으로 올린다.

**#1272 가 "예외 없음"으로 못박힌 6-step ② 를 정책 3(자율 판단 보고)으로 자기 면제 처리했다 — 보고 의무를 면제 기전으로 전용**

- 위치 `CLAUDE.md:353` · 관점 `decision`
- 주장: CLAUDE.md 6-step ② 는 push 전 `pytest tests/unit` 전체 통과 실측을 요구하며 "인라인 cleanup·docs-only 예외 없음" 과 "예외 없음"을 두 번 명시한다. #1272 는 전체 스위트 실행을 생략하면서 그 사유로 규칙이 **선제적으로 금지한 바로 그 사유**("docs-only 변경")를 들고, 근거로 "정책 3 자율 판단 보고"를 인용했다. 정책 3 은 사후 보고 의무이지 규칙 면제 권한이 아니다 — 이 인용이 선례로 굳으면 "보고했으니 면제"가 모든 무예외 게이트에 적용 가능해진다.
- 처방: docs-only PR 에 스위트 면제가 필요하다면 규칙 본문에 조건을 명시하는 사용자 결정을 받는다(정책 15 High-tier). 그 전까지는 `scripts/pre_push_gate.py --full` 로 실행하거나, 생략 시 정책 3 이 아니라 "6-step ② 미이행" 으로 명시 기록한다.

**architecture.md 최상위 scripts/ 트리가 stale — 창에서 추가한 가드 4종이 미등재이고 트리 싱크 가드는 src/ 만 본다**

- 위치 `docs/architecture.md:146` · 관점 `docs`
- 주장: `docs/architecture.md:141~195` 은 '최상위 scripts/ 디렉토리 구조' 를 명시적 트리로 열거하는 섹션인데, 실제 `scripts/` 에 존재하는 `check_test_count_sync.py`(#1253) · `check_precommit_installed.py`(#1254) · `pre_push_gate.py`(#1258) · `lint_js_ignore_baseline.json`(#1268) 4건이 전부 빠져 있다(추가로 창 이전의 `check_claim_review_trace.py` 도 누락). 4건 모두 이번 회고 창(bb038ec..HEAD) 안에서 추가된 파일이고, CLAUDE.md 완료 6-step ⑥ 는 '신규 파일 추가 시 docs/architecture.md 동기화' 를 예외 없는 의무로 규정한다. 특히 `pre_push_gate.py` 는 CLAUDE.md:55 가 push 전 표준 게이트로 승격시킨 파일인데 아키텍처 문서의 도구 목록에는 존재하지 않는다.
- 처방: (a) 누락 5건을 `docs/architecture.md:146~195` 트리에 등재. (b) `check_architecture_tree_sync.py` 를 `scripts/` 섹션까지 확장하거나(디렉토리별 대조), 확장이 오탐 위험이면 최소한 출력 문구를 '`src/` 트리만 검사함' 으로 한정해 초록의 의미를 좁힌다 — R16 이 채택한 '오탐 위험 0 최소 조치' 와 동일 처방.

**CLAUDE.md 의 정책 detail 링크 16건이 죽은 앵커 — 정책 17 외부화 설계가 의존하는 도달 경로가 끊겨 있다**

- 위치 `CLAUDE.md:35` · 관점 `docs`
- 주장: CLAUDE.md 본문이 `.claude/policies/active.md#정책-N` 형태로 detail 을 가리키는 앵커가 실제 헤딩 slug 과 하나도 일치하지 않는다. active.md 의 실제 헤딩은 `## 정책 2: PR 본문 "🔍 사용자 검증 필요" 섹션 의무`, `## 정책 7: 위반 시 회복`, `## 정책 10: PR 직접 생성 의무 (URL 안내 X, 자동 생성 ○)`, `## 정책 17 5번째 default (사이클 92 신설): 누적 결함 정기 검증 의무` 처럼 제목 전문이라 GitHub slug 이 `정책-2`·`정책-7`·`정책-10`·`정책-17-5번째-default` 가 될 수 없다. CLAUDE.md 자신의 탐색 가이드 `#주의사항-카테고리별` 도 죽었다(실제 헤딩 = `## 주의사항 (카테고리별 — .claude/rules/<area>.md path-scoped)`). 정책 17 원칙 2 는 'default rule 은 CLAUDE.md 본문, detail 은 active.md/history.md external' 을 설계로 못박았는데, 그 external 로 가는 링크가 섹션이 아니라 450줄 파일 최상단에 떨어진다. 즉 detail 도달성이 링크 클릭 1회가 아니라 수동 탐색이 된다.
- 처방: active.md 에 history.md 와 같은 앵커 전용 상위 헤딩(`## 정책 2`, `## 정책 7`, `## 정책 10`, `## 정책 17 why how` …)을 추가하거나 CLAUDE.md 앵커를 실제 slug 으로 교정한다(전자가 detail 헤딩 문구 변경에 강함). 함께 `check_toc_anchors.py` 의 TARGET 을 최소한 CLAUDE.md·AGENTS.md·.claude/policies/**·.claude/rules/** 로 확장한다 — slug 계산기는 이미 구현돼 있어 범위만 넓히면 된다.

**'예외 없음' 이라 명시된 6-step ② 를 자율 판단으로 면제 — 정책 3 보고가 면제 권한으로 사용됨**

- 위치 `CLAUDE.md:353` · 관점 `decision`
- 주장: #1272 는 push 전 `pytest tests/unit` 전체 통과 실측(6-step ②)을 수행하지 않고 'docs-only 변경' 을 사유로 생략했다고 본문에 적었다. CLAUDE.md 는 바로 그 사유를 명시적으로 봉쇄한다 — '**인라인 cleanup·docs-only 예외 없음**' 그리고 문장 말미 '예외 없음'. 더 문제인 것은 그 생략이 '정책 3 자율 판단 보고' 로 라벨링돼 있다는 점이다. 정책 3 은 **보고 의무**이지 정책 면제 권한이 아닌데, 이 창에서 report-as-license 로 기능했다(보고했으니 정당하다는 형태). 두 번째 사유였던 '사용자 토큰 소진 신호' 는 사용자 발화의 Claude 측 추론이지 면제 승인이 아니다.
- 처방: 둘 중 하나로 결정면을 정리한다: (a) CLAUDE.md 6-step ② 에 docs-only 면제를 **명시 조건**으로 정식화(어떤 파일 집합이 docs-only 인지 기계 판정 + `pre_push_gate` 가 그 판정을 인쇄)하거나, (b) '예외 없음' 을 유지하고 정책 3 본문에 '보고는 면제가 아니다 — 예외 없음 규칙의 생략은 사용자 사전 승인 필요' 1줄을 추가한다. 현행처럼 규칙은 예외 없음인데 실행은 자율 면제인 상태가 가장 나쁘다.

### K. 기타 (프로세스 · 의사결정) — 1건

**🔴 사용자 결정 대기 항목에 기계 관측 축이 하나도 없다 — P0 R0-2 가 47 머지 PR·3 세션 미결**

- 위치 `.claude/settings.json:3` · 관점 `decision`
- 주장: 이 리포는 회고 카덴스(≥15 PR)와 owed 운영검증(⏳)에는 SessionStart 훅을 배선했지만, **`docs/backlog.md` 의 🔴 사용자 결정 대기 항목을 읽는 훅은 없다**. 카운트 가드도 사각이다: 현재 창 요약 가드는 역사 섹션을 잘라내고, 하단 `## 🔴/🟡/⏸️` 섹션 가드는 B6-b 만 보며, `#1271` 이 R24 시정으로 넓힌 전장(whole-file) 가드는 **상태 셀이 합법 마커로 시작하는지(legality)만** 보고 🔴 를 세지 않는다. 결과: R0-2(원장이 스스로 'P0' 라 표기)와 R7 이 어떤 계량 축에도 잡히지 않고, 유일한 기록은 산문 한 줄이다. 정책 5 NEW-P0-N 은 P0 결정 항목에 '매 사이클 진행 신호 회신 의무' 를 규정하지만, 그 의무를 발동시킬 신호가 존재하지 않는다. 실해: 이번 창의 🟡 R28 이 R0-2 결정을 기다리느라 미착수 — **관측되지 않는 결정이 엔지니어링을 차단**한다.
- 처방: `check_owed_verification.py` 와 대칭으로 `docs/backlog.md` 전장에서 상태 셀이 🔴 로 시작하는 R/B 행을 세어 SessionStart 에서 loud 로 열거한다(항목 ID + 등재일 + 경과 PR 수). 최소 조치라도 `test_backlog_shape.py` 에 '전장 🔴 개수 == 요약 산문이 선언한 합산 수' 불변식을 추가해 :56 의 숫자를 기계 축으로 승격시킨다.

---

## P2 (62건)

| # | 항목 | 위치 | 관점 |
|---|------|------|------|
| 1 | 심의 게이트가 매 보호 문서 편집마다 41.6k자 정적 컨텍스트를 3에이전트에 캐시 없이 재전송한다 (편집당 ~6.3s · ~36k 입력 토큰) | `.claude/hooks/doc_review_gate.py:346` | `code` |
| 2 | 면제 계량의 지정 독자가 소스 주석에만 존재 — 회고 런북·스킬·워크플로 어디에도 집계 항목이 없다 | `scripts/check_claim_review_trace.py:257` | `process` |
| 3 | "토큰 소진으로 중단 결정"이 원장·PR·사용자 보고 3곳에 사실로 기록됐으나 TaskStop 은 두 번 다 실패했다 (84 에이전트 결과 미수확) | `docs/runbooks/retro-cadence-deferrals.md:25` | `decision` |
| 4 | 회고 카덴스 이월 원장: 행 1개가 이후 모든 세션의 loud 경고를 영구 무음화 — 원장이 막으려던 '순수 배너' 결함을 한 단계 위에서 재생산 | `scripts/check_retro_cadence.py:127` | `tooling` |
| 5 | 카덴스 이월 원장의 단일 행이 window 잔여 전체의 loud 경고를 소거한다 — 2026-07-22 근본(배너 크로스세션 무시)의 재생산 | `scripts/check_retro_cadence.py:127` | `process` |
| 6 | 이월 승인 인용의 진정성이 fail-open — 승인 셀은 '비어있지 않음' 만 검사한다 | `scripts/check_retro_cadence.py:108` | `decision` |
| 7 | docs/backlog.md 현재 창 표가 빈 줄로 쪼개져 R32·R33·R34 가 표로 렌더링되지 않는다 — shape 가드는 green | `docs/backlog.md:46` | `docs` |
| 8 | 위임 tier 판정이 같은 클래스에서 뒤집혔다 — 로컬 git 훅 설치는 무확인 자율, 로컬 파이썬 버전은 High-tier 사용자 결정 | `docs/backlog.md:43` | `decision` |
| 9 | backlog ✅ 완료 라벨 3행이 상태 셀 안에 미결 사용자 결정을 품고 있다 — 기계 가드는 마커만 세고 산문은 읽지 않는다 | `docs/backlog.md:52` | `decision` |
| 10 | 정책 9 Phase-종료 '🔍 회고 질문(사용자 회신 의무)' 체크박스가 세션12~14 종결 PR 5건 연속 0회 — 관측면 없음 | `docs/backlog.md:78` | `process` |
| 11 | backlog 구조 가드가 같은 마커의 섹션·요약행을 덮어써 앞선 섹션을 무검사로 버린다 | `tests/unit/scripts/test_backlog_shape.py:56` | `code` |
| 12 | backlog SSOT 가 자기 자신과 5줄 간격으로 모순 — R33 행은 "게이트가 처음으로 실제 심의" ✅, 요약 블록은 "세션 내내 전건 호출 실패 8회+"; 재개방분은 표 밖 산문이라 회귀 가드에 비가시 | `docs/backlog.md:48` | `docs` |
| 13 | 정책 3 §자율 판단 보고 섹션이 세션13 13 PR 연속 부재 — 창에서 자율 판단이 가장 컸던 구간이 지속 기록을 남기지 않았다 🔸<sub>인용 미확인</sub> | `docs/backlog.md:37` | `decision` |
| 14 | backlog.md 현재 창 표가 빈 줄로 쪼개져 R32·R33·R34 가 GitHub 에서 표로 렌더되지 않는다 — 가드는 19행을 세고 초록 | `docs/backlog.md:46` | `docs` |
| 15 | 전장 legality 가드가 자기 docstring 의 실측값(35행)과 어긋난 채 초록 — 같은 세션이 R34 를 추가하며 36행으로 만들었다 | `tests/unit/scripts/test_backlog_shape.py:296` | `docs` |
| 16 | R20-(a) 처방('면제 사용을 원장에 기록·계량')과 이행(per-run ::notice)이 어긋난 채 ✅ 로 종결 | `docs/backlog.md:34` | `decision` |
| 17 | R29 가 ✅ 완료인데 같은 요약 블록이 같은 항목을 잔여 사용자 조치로 적는다 + 🔴 사용자 결정 항목을 Claude 가 귀속 없이 종결 | `docs/backlog.md:43` | `decision` |
| 18 | 전장 백스톱 가드의 ground-truth 행 수가 저술 1 PR 만에 drift — docstring/실패 메시지는 '실측 35행' 인데 실제는 36행 | `tests/unit/scripts/test_backlog_shape.py:296` | `decision/backlog` |
| 19 | claim-review 면제 `::notice` 계량에 소비자가 없다 — backlog R20 의 '원장에 기록' 축은 미구현인 채 완료로 플립 | `scripts/check_claim_review_trace.py:264` | `tooling` |
| 20 | 정책 19 default(실질 작업 전건 claim-review) ↔ 집행면(seal 어휘 PR 한정) 비대칭 — #1258 이 흔적 0으로 머지됐고 아무 신호도 나지 않았다 | `scripts/check_claim_review_trace.py:1` | `process` |
| 21 | 정책 19 2-phase 보고 게이트의 트리거 어휘가 3곳에서 서로 다르고, CI 집행 어휘에는 `운영`·`배포`·`활성` 이 없다 — 이 창의 운영 주장이 어떤 관측자도 거치지 않았다 | `scripts/check_claim_review_trace.py:50` | `ops` |
| 22 | R3 의 처방 mount point 두 곳이 이 창·직전 창에 실제로 열렸고 각각 다른 관측자가 들어갔는데 정책 13 만 빠졌다 — pre_push_gate 의 "내가 못 보는 축" 목록이 CI≡검증전체 등식을 재생산한다 | `scripts/pre_push_gate.py:89` | `ops` |
| 23 | `pre_push_gate` 의 사각지대 열거가 '관측자 0' 축(라이브 운영 검증)을 빠뜨려 자기 목적을 재생산한다 | `scripts/pre_push_gate.py:89` | `ops/owed 원장` |
| 24 | #1261 조달 계약의 ground truth 는 리포 선언 파일뿐 — auto-merge 게이트 의미를 바꿔 놓고 라이브 이미지 축에 관측자·owed 행이 없다 | `src/analyzer/io/static.py:225` | `ops/owed 원장` |
| 25 | AGENTS.md 정책 19 집행면 서술이 R34 라이브 반례 이후에도 `claim-review-on-body-edit.yml` 을 작동하는 재검증 수단으로 제시한다 | `AGENTS.md:124` | `ops/owed 원장` |
| 26 | 조달 계약이 '텍스트 언급' 만 보므로, 실패를 묵인하는 best-effort 설치 8종에서 R21 이 없앴다는 영구 차단이 그대로 남는다 | `src/analyzer/io/static.py:53` | `code` |
| 27 | R21 결정의 유일한 보상 통제인 '미커버 언어 가시화' 가 GitHub 코멘트 경로에만 존재 — Telegram·Discord·Slack·Email·대시보드는 표면 0 | `src/notifier/github_comment.py:208` | `code` |
| 28 | "SCAManager 는 branch protection 부재" 전제가 이 창에서 반증됐는데 4 표면이 그대로 현재 사실로 단언 — 그 전제 위의 영구 결정(native auto-merge 폐기)이 미재검토 | `src/gate/native_automerge.py:16` | `docs` |
| 29 | 고지 문구 4종이 `notifier.github_pr_comment.*` 네임스페이스에 갇혀 다채널 확장이 구조적으로 중복을 강제한다 | `src/i18n/translations/en.json:753` | `product/notify` |
| 30 | telegram 렌더 함수 시그니처가 result_dict 를 아예 받지 않아 고지 추가가 시그니처 변경을 요구한다 | `src/notifier/telegram.py:103` | `product/notify` |
| 31 | pre_push_gate 가 `check_claim_review_trace` 를 `OK` 로 인쇄하지만 로컬에서는 항상 공허하다 — 못 보는 축 목록에도 없다 | `scripts/pre_push_gate.py:64` | `code` |
| 32 | check_memory_refs.py 는 이 머신에서 실행 표면이 0 인데 배선 커버리지 가드 2종이 구조적으로 그것을 볼 수 없다 | `scripts/pre_push_gate.py:57` | `tooling` |
| 33 | check_precommit_installed 의 고지가 실제로 죽는 훅을 과소·부정확하게 열거한다 (4종 vs 원장 5종, 가드는 '다수' 로 뭉갬) | `scripts/check_precommit_installed.py:118` | `tooling` |
| 34 | 신규 조달 계약 가드가 eslint·tsc·rubocop 3종에 대해 공허 — 조달을 삭제해도 19/19 green (뮤테이션 실측) | `tests/unit/analyzer/test_procurement_contract.py:62` | `code` |
| 35 | pre_push_gate 의 자기 스캔 범위 서술이 코드와 3중 불일치 (7종/9종 · lint-js 커버 여부 · '순수 파이썬' 주석) | `scripts/pre_push_gate.py:20` | `code` |
| 36 | pre_push_gate 가 신규 클론에서 push 를 전면 차단한다 — 자기 blind-spot 목록·CLAUDE.md 는 그 축을 '못 보는 축'으로 선언 | `scripts/pre_push_gate.py:65` | `tooling` |
| 37 | check_memory_refs 는 이 머신에서 기계 집행면이 0인 유일한 활성 가드 — #1250 이 그 사실을 commit body 에만 적고 backlog 등재를 누락 | `.pre-commit-config.yaml:84` | `tooling` |
| 38 | fail-open floor 와 배선 커버리지가 이름 패턴(`check_*.py`)에 묶여 있어 이번 창이 만든 판정 도구들이 표면 밖 | `scripts/check_guard_fail_open.py:135` | `tooling` |
| 39 | pre_push_gate 의 flake8 축만 git 실패를 "검사할 파일 없음"으로 읽는다 + 이 파일은 fail-open floor 의 스캔 범위 밖 | `scripts/pre_push_gate.py:144` | `code` |
| 40 | pre_push_gate 의 'CI 가드 전수 커버' 단언이 ci.yml 한 파일만 파싱 — 워크플로는 3개 | `tests/unit/scripts/test_pre_push_gate.py:52` | `tooling` |
| 41 | 미참조 메모리는 informational — 자동 로드 코퍼스의 85%가 어떤 단언면에도 없고, 본문을 읽는 축은 아예 없다 | — | `process/memory` |
| 42 | drift 는 단일 사건이 아니라 클래스 — 자동 로드 인덱스가 폐기 정책·구 워크플로를 계속 지시한다 | — | `process/memory` |
| 43 | 사이클 종료 신호가 세션13에서 4회 발화하고 앞 3회가 사후에 거짓이 됐다 — 트리거가 관측 불가능한 이벤트 | `CLAUDE.md:354` | `process` |
| 44 | 사실오류 19건 정정 PR(#1266)이 링크 텍스트만 고치고 타깃은 stale 로 남겨 새 깨진 링크를 만들었다 — 리포 전역 링크 가드 부재 | `docs/reference/language-coverage.md:120` | `docs` |
| 45 | cycle-history.md 의 범위·기간 선언이 4지점에서 stale — 실제 내용은 2026-08-02 세션14 까지 | `docs/STATE.md:105` | `docs` |
| 46 | 정책 3(자율 판단 보고)이 "예외 없음" 규칙의 면제 통로로 사용됐다 — #1272 가 6-step ② 생략을 보고 한 줄로 정당화 | `CLAUDE.md:353` | `decision` |
| 47 | 방치된 에이전트 worktree 7개(167MB)가 정책 6 이 처방하는 `grep -n` 실측의 근거를 오염시킨다 🔸<sub>인용 미확인</sub> | `CLAUDE.md:None` | `tooling` |
| 48 | 6-step ② '전체 통과 실측' 4/4 PR 이 모두 stale base — 병합 결과 트리는 로컬 전체 스위트를 한 번도 안 돌았다 | `docs/STATE.md:17` | `process` |
| 49 | #1272 가 6-step ② 를 명시 예외 처리하고 그 근거를 required 가 아닌 CI job 으로 대체했다 | `CLAUDE.md:353` | `process` |
| 50 | 직전 회고가 적발한 worktree grep 오염이 한 세션 만에 재발 — 시정이 잘못된 위험(gitignore)만 덮었다 | `docs/_archive/reports/2026-07-31-retrospective.md:159` | `process` |
| 51 | 세션14 자기 서사의 수치 2종이 자기 문서와 불일치 — 뮤테이션 21 vs 23, 세션 범위 4 PR vs 6 PR | `docs/cycle-history.md:158` | `process` |
| 52 | 추적 문서에 깨진 상대 링크 9건 — 1건은 "사실오류 19건 정정" PR(#1266)이 라벨만 고치고 href 를 방치해 신규 생성 | `docs/reference/language-coverage.md:120` | `docs` |
| 53 | 실행형 계획 무력화가 '파일시스템 도달성'이 아니라 'git 추적 집합'에 스코프돼 74 스텝짜리 살아있는 실행 지시 2건이 작업트리에 그대로 남았다 | `docs/superpowers/plans/2026-05-30-sprint-roadmap.md:3` | `docs` |
| 54 | 브랜치 보호 활성 이후에도 "브랜치 보호 부재" 단언 4지점 잔존 — 심은 PR 자신이 그 보호를 통과해 머지됐다 | `.github/workflows/ci.yml:424` | `process` |
| 55 | #1272 가 6-step ② 의 "docs-only 예외 없음" 을 docs-only 사유로 면제 — 정책 3(자율 판단 보고)이 하드룰 override 권한으로 사용됐다 | `CLAUDE.md:353` | `process` |
| 56 | stale agent worktree 7개(167MB) 잔존 — #1265 가 같은 사유로 2개(45MB)를 치웠으나 재발 방지 배선이 0이라 같은·다음 세션에 3.5배로 재축적 | `CLAUDE.md:380` | `process` |
| 57 | 사실오류 정정 PR(#1266)이 링크 텍스트만 고치고 href 는 죽은 채 남겼다 — 리포 전역 상대 링크 9건 사망, 검사 축 0 | `docs/reference/language-coverage.md:120` | `docs` |
| 58 | 게이트 주장 정정 패스가 `make gate` 행만 고치고 바로 아래 `make lint` 행은 남겼다 — 가드도 `make gate` 리터럴에만 걸린다 🔸<sub>인용 미확인</sub> | `docs/agents-index.md:53` | `docs` |
| 59 | 새 PC 셋업 런북이 §1 '리포가 주지 않는 것' 표에서 make 자체를 빠뜨린 채 make 절차를 처방한다 | `docs/runbooks/new-machine-setup.md:6` | `docs` |
| 60 | 정책 14 '매 사이클 종료 시 alert 검토' 가 실제로 수행되지 않았다 — alert #564 가 자칭 종료 PR 3건을 그대로 통과 | `.claude/policies/active.md:184` | `process` |
| 61 | 세션 종료 후 정리되지 않은 에이전트 worktree 7개가 정책 6 grep 실측을 오염시킨다 | `.gitignore:100` | `docs` |
| 62 | README 커버리지 배지 97% 는 52일·384커밋 전 스냅샷인데 정직 표기가 E2E 배지에만 적용됐다 | `README.md:25` | `docs` |

---

## 🔴 이 회고 자신의 한계 (다음 회고가 읽을 것)

1. **기각된 17건이 산출물에 없다** — 워크플로가 `FALSE_POSITIVE` 를 카운트만 하고 반환하지
   않는다(`retrospective.mjs` Report 단계). 무엇이 왜 기각됐는지가 소실되므로 **다음 회고가
   같은 17건을 재발견**한다. 이 회고가 P1 로 확정한 "닫힌 항목이 잔여를 흡수한다" 와 동형이다.
2. **인용 미확인 6건**(🔸 표기) — `citation_verified=false`. 착수 전 `grep -n` 재실측 의무.
3. **P1 #5(STATE.md deny)의 처방은 그대로 쓰면 안 된다** — Grok + Claude 재측정이 그 finding 의
   **기전을 반증**했다. 실재하는 것은 "확인 불가 ⇒ block 아님" 규칙의 부재이지 컨텍스트 예산이 아니다.
4. **Grok 패스는 P0 클러스터 단축 패스**였다 — P1 60건 전체는 Grok 검토를 받지 않았다.

