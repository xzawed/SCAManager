# 2nd-LLM 머지 검증자 활성화 Runbook

> 2nd-LLM cross-vendor merge verifier (#859) 운영 활성화 가이드.
> 2nd-LLM cross-vendor merge verifier activation guide.
>
> 출처: 2026-06-23 정밀 감사 세션 회고 P2 (DQ-3). 코드 단일 출처: [`src/gate/merge_verifier.py`](../../src/gate/merge_verifier.py) · 환경변수: [`docs/reference/env-vars.md`](../reference/env-vars.md#머지-검증자-2nd-llm-cross-vendor-opt-in).

## 개요 / Overview

Claude 코드 리뷰를 **다른 vendor 의 LLM**(OpenAI-호환 엔드포인트)이 독립 검증해 **경계 점수 자동머지 후보**만 한 번 더 거른다. 재채점이 아니라 **머지 안전성 + 리뷰 조작 탐지** 2축 판정이다.
A different-vendor LLM independently double-checks only **borderline-score auto-merge candidates** — not a re-score, but a two-axis judgment of **merge safety + review-manipulation detection**.

- **순수 opt-in**: `OPENAI_API_KEY` 미설정 = 검증자 **완전 비활성**(비용 0, 동작 변화 0). 코드는 완비(built-but-INACTIVE) — 활성화 = **런타임 env 설정만**.
- **fail-closed**: 불안전/조작 의심/검증자 오류/대형 diff → 자동머지 **차단 + PR 코멘트**. 검증 실패가 머지를 통과시키지 않는다.
- **Pure opt-in**: unset `OPENAI_API_KEY` = verifier fully disabled (zero cost, zero behavior change). Code is complete; activation is **runtime env config only**.

## 무엇을 검증하나 / What it judges

검증자는 JSON 으로 2가지만 답한다 (`_VERIFIER_SYSTEM_PROMPT`):
The verifier answers only two things in JSON:

1. **`safe`** — 이 변경을 auto squash-merge 해도 안전한가? (회귀 / 보안 / 테스트 누락)
2. **`manipulation_detected`** — 이전 Claude 리뷰가 diff 에 삽입된 지시(prompt injection)로 조작됐거나 diff 와 모순되는가?

diff 는 `<untrusted-data>...</untrusted-data>` 경계로 감싸 **데이터로만** 취급(지시 아님). 엄격 파싱(`interpret_verdict`): `safe` 는 **명시적 `true`** 일 때만 안전, `manipulation_detected` 는 **명시적 `false`** 일 때만 무조작 — 그 외(문자열/정수/None/키 누락)는 전부 차단 쪽으로 fallback.

## 언제 호출되나 / When it runs

`should_verify` 3조건 **모두** 충족 시에만 호출 (`merge_verifier.py:66`):
Invoked only when all three hold:

| 조건 | 설명 |
|------|------|
| kill-switch off | `MERGE_VERIFIER_DISABLED` 이 truthy(`1`/`true`/`yes`) 가 아님 (`feature_kill_switch.py` `_TRUTHY_VALUES`) |
| 키 존재 | `OPENAI_API_KEY` 가 빈 문자열이 아님 |
| 경계 밴드 | `merge_threshold <= score < merge_threshold + MERGE_VERIFIER_BAND` |

고득점(`>= mt + band`)·머지 미달(`< mt`)은 **skip**(비용 절감). 검증 가드는 [`engine._run_auto_merge`](../../src/gate/engine.py) **단일 출처**에서 1회 — **자동**(`AutoMergeAction`)·**반자동**(Telegram `handle_gate_callback`) 양 경로 공유(#859 P1-1 parity). **재시도 경로**(`process_pending_retries`)는 재검증하지 않으나, `expected_sha` 바인딩(#962)+`sha_drift` 검사로 **검증자가 승인한 동일 SHA 만 머지**하므로 verdict 가 stale 될 수 없다(api.md §검증자 staleness 안전).

## 활성화 — 비용 옵션 / Activation cost options

클라이언트는 **OpenAI-호환**(`chat/completions` + `response_format=json_object`) 공급자면 모두 동작한다. 권장 = **무료 GitHub Models(추가 비용 0)**.
The client works with any **OpenAI-compatible** provider. Recommended = **free GitHub Models (zero added cost)**.

| 옵션 | `VERIFIER_BASE_URL` | `OPENAI_API_KEY` | `OPENAI_VERIFIER_MODEL` | 비용 |
|------|---------------------|------------------|--------------------------|------|
| ★ **GitHub Models** (권장) | `https://models.github.ai/inference` | GitHub PAT(`models:read` 권한) | 공급자 카탈로그의 소형 모델명 | **0** (무료 티어) |
| Groq / OpenRouter | 공급자 엔드포인트 | 공급자 키 | 공급자 모델명 | 0~저가 |
| OpenAI 직접 | 빈 값(기본 엔드포인트) | OpenAI 키 | `gpt-5-mini`(기본) | 유료(소액) |

> 🔴 무료 티어 rate-limit 으로 검증 호출이 실패하면 **fail-closed**(해당 PR 자동머지 보류 = 안전, 수동 검토 폴백). 비용 vs 안전 trade-off 에서 안전을 택한다.

## 활성화 절차 (Railway) / Activation steps

1. **공급자 선택 + 키 발급** — GitHub Models 면 GitHub Settings → Developer settings → PAT 발급(`models:read`).
2. **Railway Variables 설정** (대시보드 또는 CLI):
   - `OPENAI_API_KEY` = 공급자 키 (**활성화 트리거** — `config.py` 기본값은 빈 문자열이라 미설정 시 검증자 비활성)
   - `VERIFIER_BASE_URL` = 비-OpenAI 공급자 엔드포인트 (OpenAI 직접이면 비워둠)
   - `OPENAI_VERIFIER_MODEL` = 공급자 모델 ID (저비용 소형 권장)
   - `MERGE_VERIFIER_BAND` = 경계 밴드 폭(기본 10 — 필요 시 조정)
3. **Redeploy** — 새 컨테이너가 env 를 읽음.
4. **검증** (아래 §검증).

## 검증 / Verify activation

경계 밴드 점수 PR 의 자동머지가 트리거되면:
When an auto-merge for a borderline-band PR triggers:

- **안전 판정** → 정상 squash-merge (추가 코멘트 없음).
- **차단 판정** → PR 에 코멘트 `🛑 Auto-merge withheld by the 2nd-LLM cross-vendor verifier (Claude review ↔ GPT verification) — merge-safety check failed.` + 구조화 로그:
  - `merge verifier blocked auto-merge (tag=<VERIFIER_BLOCKED|VERIFIER_ERROR> status=<...>) — repo=... pr=...: <reasons>`
  - `VERIFIER_BLOCKED` = 정상 판정의 unsafe/조작 / `VERIFIER_ERROR` = 검증자 api/parse 오류(fail-closed).

활성화 전(키 미설정)에는 `should_verify` 가 `False` 라 위 경로가 **전혀 실행되지 않는다**(코멘트/로그 없음 = 비활성 확인).

## fail-closed 동작 / Fail-closed behavior

| 상황 | 동작 |
|------|------|
| diff > `VERIFIER_DIFF_CHAR_CAP`(60,000자) | OpenAI **미호출** + 차단 (대형 PR 수동 머지, 비용 0·결정론적) |
| OpenAI api 오류 / 타임아웃(`OPENAI_VERIFIER_TIMEOUT`=60s) | `VERIFIER_ERROR` 차단 |
| 비-JSON / 키 누락 응답 | `parse_error` 차단 |
| 무료 티어 rate-limit | 차단(수동 검토 폴백) |

## 비활성화 / Disable

- **즉시 kill-switch**(운영 사고 시): `MERGE_VERIFIER_DISABLED=1`(또는 `true`/`yes`) → `should_verify` 즉시 `False`.
- **완전 비활성**: `OPENAI_API_KEY` 제거 → 검증자 완전 off(원래 동작 복귀).

## 비용 통제 / Cost control

- **경계 밴드 PR 만** 호출(고득점·미달 skip).
- diff **hunk 만** 전송(전체 파일 아님) — 토큰 절감.
- 응답 토큰 상한 `VERIFIER_MAX_OUTPUT_TOKENS`(8192).
- 무료 GitHub Models 사용 시 **추가 비용 0**.

## 알려진 한계 / Known limitations

- **검증 가드 차단은 로그/코멘트로만 감사** — `merge_attempt` DB row 는 `engine` 단일 출처 규칙(api.md) 보존이라 가드 차단이 별도 DB row 를 남기지 않는다. (회고 P2 백로그: "verifier-blocked DB 기록" = 활성화 PR 재검토 항목.)
- 재시도 경로는 초기 머지 1회만 검증(위 §언제 호출되나 — SHA-bound 라 안전).

## 관련 / References

- 환경변수: [`docs/reference/env-vars.md` §머지 검증자](../reference/env-vars.md#머지-검증자-2nd-llm-cross-vendor-opt-in)
- 코드: [`src/gate/merge_verifier.py`](../../src/gate/merge_verifier.py) · [`src/verifier/openai_client.py`](../../src/verifier/openai_client.py)
- 게이트 가드 규칙: [`.claude/rules/api.md`](../../.claude/rules/api.md) §2nd-LLM 검증자 가드
- 설계: [`docs/superpowers/specs/2026-06-11-merge-verifier-design.md`](../superpowers/specs/2026-06-11-merge-verifier-design.md)
