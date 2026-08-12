<!-- guard-cue-quote: 아래는 2026-08-12 세션의 상태 기록이며, 이 문서 자체가 실행 지시는 아니다. -->

# 세션 인계 — 2026-08-12 (다른 머신에서 이어받기)

> 🔴 **이 문서는 상태 스냅샷이다.** 착수 전 `git pull` 후 아래 "먼저 확인" 3줄을 **실행해서**
> 값을 갱신할 것 — 여기 적힌 수치는 작성 시점이며 손유지라 늙는다.

## 먼저 확인 (30초)

```bash
gh pr list --state open                 # 미머지 PR
gh run list --branch main --limit 3     # main 초록/빨강
py -3 scripts/pre_push_gate.py          # 로컬 게이트 (make 불필요)
```

환경 구성은 [`new-machine-setup.md`](new-machine-setup.md) 가 정본이다.
🔴 그 문서 `:95` 의 기대값 "13종"은 **틀렸다** — 실측 16종(repo-integrity 12 + PR-diff 4).
새 머신에서 16이 나와도 정상이다(아래 §미해결 2 참조).

---

## 1. 이번 세션에 머지된 것

**PR #1335** `docs(rules): rules 7파일 밀도 압축 −61% + 서사 보존 집행 가드` — 머지 완료(체크 13/13).

- `.claude/rules/` 7파일 **101,544 → 40,019자 (−61%)**. 걷어낸 사고 재현·측정 로그는
  [`docs/_archive/rules-incident-log.md`](../_archive/rules-incident-log.md) 에 원문 보존.
- 신규 가드 `tests/unit/scripts/test_rules_archive_backlink.py` (38건) — 역링크·앵커·절 보존·
  **리터럴 지문·인용 다양성** 5축.
- 🔴 압축은 그대로 두면 CI 를 깼다: `check_red_budget` **Δ+37 EXIT=1**. 원인은 서사 삭제가
  아니라 **줄바꿈**이었다 — HEAD 는 한 줄 평균 390자 미포장이라 🔴 와 가드 파일명이 같은
  물리 줄에 있었는데, 80칼럼 포장이 블록을 다음 🔴 줄에서 끊어 집행자를 분리했다.
  🔴 표식 자체는 오히려 줄었다(162→142). 집행자 재부착으로 **Δ−2** 로 종결, 집행 비율 16.9% → 28.0%.

> 🔴 **여기서 배운 것**: `check_red_budget` 을 `PR_BASE_SHA` 없이 돌린 `EXIT=0` 은 통과가
> 아니라 **"증감을 판정하지 않음"** 이다. 초록이 아니라 *안 쟀음*. 게이트는 PR 변수와 함께
> 돌린 결과만 근거로 인용할 것.

---

## 2. 🔴 지금 main 이 red 다 (이 세션이 유발)

**증상**: `tests/unit/scripts/test_deferral_marker_survives_merge.py::test_git_failure_is_not_an_exemption`
실패. 로컬 재현됨.

**기전** — `scripts/check_test_count_sync.py:224-225`:

```python
commits = _git_text("log", "--format=%B", f"{base}..{head}") if base and head else ""
return commits or _git_text("log", "-1", "--format=%B"), read_pr_body()
```

범위를 **요청했는데 조회가 실패하면** tip 으로 물러난다. 그러면 그 tip 의 마커를
**다른 push 의 면제로 상속**한다. docstring 은 이를 "fail-closed" 라 적었지만
**tip 에 마커가 없을 때만 참**이었다. `#1335` 가 `STATE-sync-deferred:` 마커의 **첫 실사용**이라
그 마커가 스쿼시 머지로 tip 에 실렸고, 잠재 fail-open 이 즉시 발현했다.

**고칠 방향** (착수 안 함 — 사용자 판단 대기):

```python
requested = bool(base and head)
commits = _git_text("log", "--format=%B", f"{base}..{head}") if requested else ""
if requested and not commits:
    return "", read_pr_body()   # 범위 요청 실패 → tip 상속 금지 (fail-closed)
return commits or _git_text("log", "-1", "--format=%B"), read_pr_body()
```

🔴 가드 표면이므로 **claim-review 면제 불가**(정책 19) + 실경로 뮤테이션 필요.
기존 테스트는 **live tip 에서 기대값을 유도**해 수개월간 우연히 초록이었다 — 밀폐 테스트 동반 권장.

**부수 학습**: 메모리 `feedback_activate_skipped_guard_reveals_bug` 의 인접 사례.
*가드의 첫 실사용이 그 가드의 잠재 결함을 드러낸다.*

---

## 3. 🔴 머지 대기 — PR #1331

`fix(guards): main 이 깨져 있었다 — README 충돌 마커 + pylint 배지 진리값`
**MERGEABLE / CLEAN / 체크 13건 전부 SUCCESS**. 머지는 사용자 몫(정책 7).

이 PR 하나가 확정 P0 **3건**을 닫는다:

| # | 결함 | 현재 main 상태 |
|---|---|---|
| 1 | `README.md`·`README.ko.md` **21·23·25줄 미해결 병합 충돌 마커** | 살아 있음 (공개 첫 화면) |
| 2 | pylint 배지 5지점이 `10.00` 단언 — 실측 **9.99** | 살아 있음 |
| 3 | 충돌 마커 가드 **0건** (`scripts/check_conflict_markers.py` 부재) | 살아 있음 |

⚠️ 그 PR 의 STATE 수치(7254/7083)는 이미 낡았다 — 현재 실측 **7269/7098**. 머지 후 trailing sync 필요.

> 🔴 왜 가드가 초록이었나: `scripts/check_docs_sync.py:52-56` 의 `_first()` 가
> `pattern.search()` = **첫 매치만** 본다. 첫 배지가 STATE 와 맞으면 그 아래 충돌 잔해가
> 구조적으로 안 보인다. `--fix` 도 `count=1` 이라 stale 사본을 남긴다.
> `ci.yml:167` · `.pre-commit-config.yaml:95` 에 **배선된 채 공허**하다.

---

## 4. 전 문서 감사 결과 (128건 채점)

에이전트 47 · 토큰 5.5M · Grok claim-review 3세션. 상세는
[`docs/_archive/reports/2026-08-12-docs-audit.md`](../_archive/reports/2026-08-12-docs-audit.md).

평균 **61.6**점 · BROKEN 32 / NEEDS_WORK 70 / GOOD 26. 확정 P0 7 · P1 12 · P2 30 · 오탐 반증 21.

### 미해결 P0 (PR #1331 로 안 닫히는 것)

| 결함 | 근거 | 영향 |
|---|---|---|
| `CONTRIBUTING.md:95`·`ko:93` "E2E 는 CI 에 없다" | `ci.yml:586` e2e job 실재, `:643` `--e2e-min-passed=100` | 기여자가 CI 가 안 잡는다고 믿고 PR 을 연다 |
| `branch-protection.md:117-121` 이 auto-merge 종결 판정을 코드와 **정반대**로 서술 | `src/gate/merge_reasons.py:80-82` 는 `BRANCH_PROTECTION_BLOCKED` 를 재시도 대상에 **포함** | 운영자가 정상 재시도를 "영구 포기"로 오판 |
| **스킬 6종이 하나도 로드되지 않는다** | `.claude/skills/*.md` 는 평문. `find -name SKILL.md` → **0건**. 라이브 반증: `Skill({skill:"retrospective"})` → `Unknown skill` | CLAUDE.md·agents-index 가 등재한 `/명령` 전부 미동작 |
| `scripts/i18n_comments/glossary.md` 의 유일한 소비자가 그 파일을 안 읽는다 | `GLOSSARY_PATH` = 정의만 되고 read 0회 | 번역 계약이 산문으로만 존재 |
| **가드 개수 13→16 거짓이 13지점** + 모든 PR 본문에 주입 | `PULL_REQUEST_TEMPLATE.md:19` · `CLAUDE.md:32,149` · `AGENTS.md:17,23` · `guards.md:208-211` · `new-machine-setup.md:95` 외. 자칭 `pre_push_gate.py:12,20` 은 **"7종"** (세 번째 값) | 리포에 7·9·13·16 네 숫자 공존. 이 축에 집행자 0 |

### 결정 대기 5건

1. **PR #1331 머지** (P0 3건 종결)
2. **가드 개수 정정** — 13지점 손수정은 다시 낡는다. `pre_push_gate.py` 에 `guard_inventory()` 노출 + 문서 수치 대조 가드를 **같은 PR** 에(정책 4)
3. **스킬 6종 구조 이동** (`<name>/SKILL.md`) — 행동 임계 파일 이동이라 **High tier 사전 확인**
4. **고아 문서 9건** — `docs/design/brief/` 5 · `docs/reports/` 2 · `docs/superpowers/plans/` 2. 색인할지 지울지
5. **CONTRIBUTING·branch-protection 정정** — 문서만 고치면 되는 저비용 건

---

## 5. 이 세션이 만든 결함 (자기 보고)

- **집행자 오귀속** — `testing.md` 의 const/let 규칙에 무관한 가드
  (`test_hx_boost_listener_guards.py`, grep 0건)를 붙였다. 진짜는 `test_template_js_const.py`.
  정정 커밋 `e7159d8f`(#1335 에 포함). 🔴 예산 게이트는 *"블록에 실재하는 파일명이 있는가"* 만
  보고 *"그 가드가 그 규칙을 검사하는가"* 는 안 본다 — `check_red_budget.py:38-40` 이
  스스로 "프록시다" 라고 적어둔 한계를 같은 세션에 실증했다.
- **Grok 이 `sandbox:read-only` 를 무시**하고 `.claude/rules/pipeline.md` 105줄을 삭제했다.
  `git checkout` 으로 복원·검증(120줄, HEAD 동일). 🔴 **앞으로 Grok 호출은 사전 `git add`
  또는 작업트리 격리 동반** — Windows 는 샌드박스 강제가 불완전하다.
- **감사 자신의 분모가 틀렸다** — 자진신고 279건 vs 실측 205(디스크)/203(추적).
  아카이브 담당 2 에이전트가 각자 "나머지 전부"를 세어 이중계상, **CRITICAL 23건이
  채점에도 미검사 신고에도 없었다**. 완전성 비평이 잡아 2차 갭 감사로 메웠다.

---

## 6. 미완료 · 진행 중

- **정책 8 5+1 회고** — 카덴스 breach(직전 회고 2026-08-08 이후 머지 PR 17건 ≥ 임계 15).
  워크플로 기동했으나 **세션 종료 시점에 미완**(에이전트 74 기동 / 70 결과).
  범위 = `#1317~#1334` + 본 세션 산출물. 🔴 **다음 세션에서 재실행**(resume 은 same-session 한정).
  이월하려면 [`retro-cadence-deferrals.md`](retro-cadence-deferrals.md) 에 사용자 승인 인용 의무.
- **owed 원장 운영등급 미결 8건** — `#1314 #1315 #1306 #1303 #1296 #1289 #1279 #1276`.
  안전등급 미결 0. 이번 세션에 **#1276/#1279 의 라이브 근거가 나왔다** — 문서 심의 게이트가
  매 편집마다 실제로 3-에이전트 심의를 수행했고, **같은 형태의 변경을 `api.md` 는 통과·
  `pipeline.md` 는 차단**했다(backlog R80 비결정성의 실측 반례). 원장 등재 미이행.
- **6-step ⑤ trailing sync** — `#1335` 가 `STATE-sync-deferred` 로 이월했다.
  현재 실측 **7269 (단위 7098 + 통합 171)** vs STATE **7231 (단위 7060)**.
  `#1331` 머지 후 단일 trailing sync PR 로 처리할 것.

---

## 7. 참조

- 감사 보고서(항목별 점수 128건, 필터·정렬 가능): 세션 아티팩트 — 리포 사본은
  [`docs/_archive/reports/2026-08-12-docs-audit.md`](../_archive/reports/2026-08-12-docs-audit.md)
- 문서 총량 감축 제안서(결정 5건 중 C′ 만 실행): [`doc-volume-reduction-plan.md`](doc-volume-reduction-plan.md)
- rules 압축 원문 보존: [`docs/_archive/rules-incident-log.md`](../_archive/rules-incident-log.md)
- Grok claim-review 세션: `019ff591`(가드 반례) · `019ff5b7`(감사 설계 BROKEN) · `019ff5ed`(감사 결과 WEAKENED)
