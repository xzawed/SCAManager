<!-- guard-cue-quote: 아래는 2026-08-13 5+1 회고의 시점 기록이며, 이 문서 자체가 실행 지시는 아니다. -->

# 5+1 회고 — 2026-08-13 (범위 #1317~#1338, 22 PR)

정책 8 회고. 범위는 디스패치 **직전** `scripts/retro_scope.py --json` 실측 —
직전 정식 회고 `2026-08-08-retrospective.md` · 경계 `4d0a8dd` → HEAD `25f446f3`.

## 실행 규모

| 축 | 값 |
|---|---:|
| 에이전트 | **205** |
| 서브에이전트 토큰 | **15.6M** |
| 툴 호출 | **3,683** |
| 소요 | **3시간 16분** |
| finder 라운드 | 3 (MAX_ROUNDS=3, 예산 미설정) |

🔴 **착수 시 비용 예측은 "30~45 에이전트" 였다 — 4.6배 틀렸다.** 원인은 finding 수 오판이 아니라
`crossVerify` 의 **finding 당 최대 3회 재시도**를 승수로 계산하지 않은 것이다. 정책 16#5 로 예측을
보고한 이상 이 오차를 기록한다. 앞으로 비용 보고는 `관점 × 라운드 + verify(finding × 재시도)` 형태로 적는다.

## ROI · verdict_coverage

| 지표 | 값 |
|---|---:|
| findings 총 | **182** |
| verdict 수신 | **172** |
| **verdict_coverage** | **1.00** |
| UNVERIFIED | **0** |
| CONFIRMED | 114 |
| SEVERITY_ADJUST | 58 |
| FALSE_POSITIVE (차단) | 10 |
| P0 / P1 / P2 (조정 후) | **8** / 83 / 81 |

🔴 **`verdict_coverage = 1.00`** — 전건이 verdict 를 받았다. 단일 패스 회고의 13/8 한계는 재발하지 않았다.

⚠️ **`SEVERITY_ADJUST` 가 34%(58/172)** 로 이례적으로 높다. cross-verify 가 실제로 일하고 있다는 증거이자,
**finder 프롬프트의 심각도 기준이 흔들린다**는 신호다 — 다음 회고에서 볼 축으로 남긴다.

## 관점별 분포

| 관점 | findings |
|---|---:|
| `tooling` | 36 |
| `docs` | 30 |
| `process` | 29 |
| `decision` | 28 |
| `code` | 16 |
| `docs (원장 귀속)` | 7 |
| `memory` | 7 |
| `docs (수치 정합)` | 6 |
| `code/guards` | 5 |
| `code/security` | 2 |
| `code/docs-consistency` | 2 |
| `guards` | 2 |
| `code/tooling` | 1 |
| `code/quality` | 1 |

## 🔴 P0 8건

### P0-1 · 감사가 적발한 P0 정정이 main 에 없는데, 인계 문서가 "#1335 에 포함" 이라고 단언한다

- 관점 `process` · 위치 `docs/runbooks/session-handoff-2026-08-12.md:155` · verdict **CONFIRMED**
- **주장**: 31-에이전트 문서 감사가 적발한 '집행자 오귀속' 정정 커밋 `e7159d8f` 는 PR #1335 머지 **63분 뒤**에 이미 머지된 브랜치에 얹혀 고아가 됐다. main HEAD 는 여전히 틀린 귀속을 들고 있는데, 리포에 영속화된 인계 문서는 그 정정이 머지됐다고 다음 세션에 알린다. 이번 세션이 만든 결함 중 유일하게 **아직 살아 있는** 것이고, 자기보고가 그것을 덮었다.
- **근거**: 라이브 실측(전부 이 세션에서 실행): · `git merge-base --is-ancestor e7159d8f HEAD` → **ANCESTOR=NO** · `git branch -a --contains e7159d8f` → `docs/rules-density`, `remotes/origin/docs/rules-density` **만** · `gh pr view 1335 --json commits` → 머지된 커밋 3건 = `8f83f4f1` `9161d291` `7a5af8ba`. `e7159d8f` **미포함** · 시각: PR #1335 머지 `2026-08-12T11:26:53Z` / `e7159d8f` author date `2026-08-12 21:29:31 +0900` = **12:29 UTC (머지 63분 후)** · `git grep -n test_hx_boost_listener_guards HEAD -- .claude/rules/` → `HEAD:.claude/rules/testing.md:87: 정적 축 집행: \`tests/unit/ui/test_hx_boost_listener_guards.py\`.` (틀린 귀속이 main 에 생존) · `git grep -n test_template_js_const HEAD -- .claude/ CLAUDE.md` → **0건**. 진짜 집행자 `tests/unit/ui/t
- **권고**: ① `docs/rules-density` 에서 `e7159d8f` 를 cherry-pick 해 신규 PR 로 main 에 올리고, `session-handoff-2026-08-12.md:155` 를 **정정**한다(이 문서는 이미 머지됐으므로 문장 수정도 PR 이어야 한다 — 정책 7). ② 근본: '머지된 PR 의 브랜치에 커밋을 더하는' 경로에 관측면이 없다. `gh pr view --json state` 가 MERGED 인 브랜치에 커밋이 얹히면 SessionStart 훅이 loud 발화하도록 배선하거나, 최소한 `git log --oneline main..<branch>` 를 세션 종료 체크에 넣는다. ③ 보고 규율: '정정했다/포함됐다' 는 정책 19 2-phase 게이트의 봉인 어휘와 같은 클래스다 — `git merge-base --is-ancestor` 라이브 근거 없이는 `UNVERIFIED:` 접두사 의무로 확장할 것.

### P0-2 · 자기 신고한 정정이 main 에 없는데 인계 문서가 '완료'로 단언한다 — 고아 커밋 e7159d8f

- 관점 `decision` · 위치 `docs/runbooks/session-handoff-2026-08-12.md:155` · verdict **CONFIRMED**
- **주장**: 이번 세션이 §'이 세션이 만든 결함(자기 보고)'에서 스스로 적발·정정했다고 기록한 '집행자 오귀속'은 main 에 반영되지 않았다. 정정 커밋은 이미 머지된 브랜치 위에 고아로 남아 있고, PR 도 열리지 않았다(정책 7 위반). 그런데 main 에 머지된 인계 문서는 그것을 '#1335 에 포함'으로 단언하고, 커밋 메시지는 Grok claim-review 를 종결 근거로 인용한다.
- **근거**: 실측: (1) `git show HEAD:.claude/rules/testing.md` → :86-87 이 여전히 `정적 축 집행: tests/unit/ui/test_hx_boost_listener_guards.py` — 그 파일에 const 검사 0건(`grep -c const tests/unit/ui/test_hx_boost_listener_guards.py` → 0). 진짜 스캐너 `tests/unit/ui/test_template_js_const.py` 는 실재. (2) 정정 커밋 `e7159d8f` 는 `origin/docs/rules-density` 에만 존재하고 main 콘텐츠에 없다 — `git log main -- .claude/rules/testing.md` 최신 = `5458c5e1`(#1335 squash)이고 그 스냅샷도 :87 이 틀린 값이다. (3) 시각: e7159d8f authored `2026-08-12T21:29:31+09:00`(=12:29Z) vs #1335 merged `2026-08-12T11:26:53Z` — 머지 약 1시간 **후** 커밋해 머지된 브랜치에 push, PR 없음. (4) 인계 문서 :155 = "정정 커밋 `e7159d8f`(#1335 에 포함)". (5) e7159d8f 커밋 메시지가 "Grok claim-review 019ff5ed 가 이 정정이 완전한지 독립 확인했다(
- **권고**: ① e7159d8f 를 cherry-pick 해 PR 로 머지하고 인계 문서 :155 를 실제 상태로 정정. ② 문서·커밋이 `정정 커밋 <sha>` 형태로 종결을 주장하면 그 sha 의 **내용이 main 에 도달했는지** 대조하는 가드 신설(sha 도달성이 아니라 diff 도달성 — squash 때문에 ancestor 검사는 항상 거짓이다). ③ 더 값싼 대안: 머지된 PR 의 head 브랜치 tip 이 mergedAt 이후 authored 면 red 를 내는 체크(이번 5 PR 중 정확히 이 1건만 걸린다 — 실측). ④ 정책 19 2-phase 보고에 '종결 주장은 main 실측 인용 동반'을 명시.

### P0-3 · 자진신고한 '정정 커밋 e7159d8f' 는 main 에 없다 — 결함은 살아 있고, 그 사실이 main 문서로 발행됐다

- 관점 `tooling` · 위치 `.claude/rules/testing.md:87` · verdict **CONFIRMED**
- **주장**: 세션이 스스로 적발·정정했다고 보고한 집행자 오귀속이 실제로는 main 에 그대로 있다. 정정 커밋 e7159d8f 는 #1335 머지 63분 **뒤에** 이미 머지된 브랜치 docs/rules-density 위에 커밋됐고, 열린 PR 이 0건이라 영구히 머지될 수 없다. 그런데 #1336 이 그 거짓 완료 주장을 main 문서에 영속화했다 — 다음 세션은 닫힌 항목으로 읽는다.
- **근거**: `git merge-base --is-ancestor e7159d8f HEAD` → NO. `git show HEAD:.claude/rules/testing.md | sed -n '87p'` → "정적 축 집행: `tests/unit/ui/test_hx_boost_listener_guards.py`." (정정 전 값). `git log --oneline main..docs/rules-density` → e7159d8f 포함 4건. 시각: #1335 머지 2026-08-12T11:26:53Z(=20:26 KST, headRefOid 7a5af8ba) vs e7159d8f 커밋 21:29:31 KST → 머지 후 63분. `gh pr list --state open` → 0건. 반면 docs/runbooks/session-handoff-2026-08-12.md:155 는 "정정 커밋 `e7159d8f`(#1335 에 포함)" 이라고 단언하며 main 에 있다. 그 커밋 본문은 "Grok claim-review 019ff5ed 가 이 정정이 완전한지 독립 확인했다" 고 적었으나, 확인된 것은 **정정 내용**이지 **머지 여부**가 아니다. 실측: `grep -n 'const|let ' tests/unit/ui/test_hx_boost_listener_guards.py` → 0건, 실제 스캐너는 tests/unit/ui/test_templ
- **권고**: (1) e7159d8f 를 cherry-pick 한 새 PR 로 testing.md:87 을 즉시 정정하고, 같은 PR 에서 handoff:155 의 거짓 완료 주장을 정정한다. (2) 회귀 가드: 머지된 PR 의 headRefOid 와 그 원격 브랜치 tip 을 대조해 **머지 후 커밋**을 SessionStart 에서 경고하는 관측자를 신설한다(현 4종 SessionStart 훅 중 이 축 0). 판별식은 `gh pr view N --json headRefOid` != `git rev-parse origin/<branch>` 이며, squash 재사용 브랜치 오탐은 '해당 커밋 내용이 main 에 존재하는가' 로 걸러야 한다(본 조사에서 #1317 이 그 오탐이었다).

### P0-4 · 승인 기록은 5파일인데 실행은 7파일 — High tier 결정의 범위가 기록 없이 확대됐다

- 관점 `decision` · 위치 `docs/runbooks/doc-volume-reduction-plan.md:124` · verdict **CONFIRMED**
- **주장**: #1335 는 커밋 본문에 "문서 총량 감축 제안서(#1334) §3-C′ 실행. 사용자 승인 2026-08-12" 한 줄만 남기고 `.claude/rules/` 7파일을 압축했다. 그러나 그 §3-C 가 정의한 범위는 5파일(i18n·deploy·ui·db·testing, −약 43,836자)이고, 추가된 2파일(pipeline.md·api.md)은 제안서 자신의 측정이 **실익 없음으로 명시 배제**한 파일이다. 승인 기록과 실행 범위가 불일치하며, 리포 어디에도 범위 확대를 재승인한 흔적이 없다. C 는 제안서가 스스로 `🔴 High tier` 로 분류한 항목이라 정책 15 상 사전 확인 대상이고, `.claude/rules/**` 는 path-scoped 자동로드 = 행동 임계 표면이다.
- **근거**: docs/runbooks/doc-volume-reduction-plan.md:124 = "**C**: `i18n`·`deploy`·`ui`·`db`·`testing` 의 사고 로그를 external. **−약 43,836자**" · :122 = "### C. rules 5파일 서사 분리 (🔴 High tier · ★보류) / C′ 변형" · :61 = "실익은 **i18n·deploy·ui·db·testing 5파일**에 집중된다". 배제 근거도 같은 문서의 실측 표다 — :55 `pipeline.md` 서사 비중 53%, :56 `api.md` 23~41% (5파일은 62~75%). 실제 실행: `git show --stat 5458c5e1 -- .claude/rules/` → api.md·db.md·deploy.md·i18n.md·pipeline.md·testing.md·ui.md **7 files changed, 621 insertions(+), 356 deletions(-)**, 총 −61,525자 (승인 추정치의 1.40배). 커밋 본문의 유일한 결정 근거는 5번째 줄 한 문장이다. 부수 정황: 범위 밖 2파일이 곧 Grok 이 sandbox 를 무시하고 삭제한 그 2파일이다(handoff:158 `pipeline.md` 105줄).
- **권고**: (a) `pipeline.md`·`api.md` 압축분을 HEAD 원문과 대조해 규칙 실질(집행자 파일명·조건)이 보존됐는지 1회 사후 검증하고, (b) 제안서 §7 결정 표에 실제 승인 범위를 사용자 발화 인용과 함께 append 한다. (c) 규율로 올릴 것: High tier 항목은 커밋 본문에 '승인' 두 글자가 아니라 **승인된 대상 목록**을 열거해야 한다 — 목록이 없으면 범위 초과를 사후에 판별할 수단이 사라진다.

### P0-5 · 규칙 파일 삭제가 탐지되지 않을 뿐 아니라 required 체크에서 '개선' 으로 채점된다 (실경로 뮤테이션 실증)

- 관점 `tooling` · 위치 `.claude/rules/guards.md:1` · verdict **CONFIRMED**
- **주장**: .claude/rules/guards.md(49 🔴)와 docs.md 를 인덱스에서까지 삭제(=커밋된 삭제 재현)한 상태에서 tests/unit/scripts + tests/unit/hooks 1449건이 전건 통과하고, repo-integrity 가드 7종이 전부 exit 0 이며, CI 차단 게이트인 check_red_budget 은 무집행 🔴 221→171(−50)·집행률 28.0%→31.3% 로 **개선을 보고**한다. PR 이면 delta ≤ 0 이라 ✅ 통과다. 즉 가드 저술 규칙과 문서 규칙을 통째로 지우는 것이 이 리포에서 가장 값싼 '집행률 개선' 수단이다.
- **근거**: 실경로 뮤테이션(복원 검증 완료 — blob sha 0c37eb39/30c9f077 일치, git status 클린): ① `git rm --cached` + `rm` 로 guards.md·docs.md 제거 → `py -3 -m pytest tests/unit/scripts tests/unit/hooks -q` = **1449 passed, 0 failed** ② check_docs_sync·check_toc_anchors·check_architecture_tree_sync·check_guard_fail_open·check_env_vars_sync·check_config_5way_sync·check_conflict_markers 전부 exit=0 ③ `py -3 scripts/check_red_budget.py` = 「🔴 249건 · 집행자 동반 78건 (31.3%) · 무집행 171건」(정상 트리는 307/86/28.0%/221). 왜 나머지 7파일은 보호되는가: tests/unit/scripts/test_rules_archive_backlink.py:49 가 `_COMPRESSED_AREAS`(ui·pipeline·api·db·testing·deploy·i18n) 7개를 리터럴로 못박아 삭제 시 red(i18n.md 삭제로 실측 확인). 남은 4개(guards·security·services·docs)의 유일한 방어선은 test
- **권고**: ① test_rule_reachability.py:94 의 `>= 8` 바닥값을 11파일 **로스터 리터럴 + 파일별 존재·바이트 하한** 단언으로 교체(CLAUDE.md 경로 매트릭스에서 유도해도 되나, 그 표 자체가 test_claude_md_path_matrix... 로 이미 고정돼 있으므로 자기참조 공허화가 아니다). ② scripts/check_red_budget.py 에 **표면 파일 수 감소 = 판정 불가(exit 1)** 를 넣는다 — 지금은 표면이 사라지면 분모가 줄어 자동으로 '개선' 이 된다(AGENTS.md 3-불변식 1 fail-closed 위반). ③ 회귀 가드는 '규칙 파일 1개를 지우면 red' 를 실경로 뮤테이션으로 실증할 것.

### P0-6 · 감사 잔여 finding 42건 + 결정 대기 5건이 backlog 결정 원장을 우회 — 회신 의무가 부착되지 않았다

- 관점 `decision` · 위치 `docs/backlog.md:304` · verdict **CONFIRMED**
- **주장**: 128건 문서 감사가 종료됐으나 잔여 findings 와 결정 대기 항목이 `docs/backlog.md` §'🔴 사용자 결정 대기' 로 이관되지 않았다. 그 결과 다음 사이클의 '사용자 회신 요청 의무'(정책 5/9 페어)는 여전히 B6-b 1건만 열거하고, 감사가 만든 결정 5건(High tier 1건 · 운영 P0 성격 1건 포함)과 P1 12 · P2 30 은 어떤 의무에도 걸리지 않는다.
- **근거**: `docs/backlog.md:301-305` 갱신 규칙 = "신규 회고·감사 종료 시 **잔여 findings 를 여기로 이관**한다. 보고서는 시점 스냅샷으로 아카이브에 남기고, '지금 뭐가 남았나' 는 이 파일이 답한다" + ":305 🔴 **결정 대기 항목은 다음 사이클 진입 시 사용자 회신 요청 의무**(정책 5/9 페어)". 실측: `:277-279` §🔴 사용자 결정 대기 = **B6-b 1행뿐**, `:234` 요약표도 "🔴 결정 대기 | **1** (B6-b)". 감사 산출물은 정반대 경로로 갔다 — `docs/_archive/reports/2026-08-12-docs-audit.md:6` 이 "행동 처방과 결정 대기 항목은 session-handoff-2026-08-12.md 가 정본이다" 로 위임하고, 그 보고서 본문은 루브릭·한계·점수표·디렉토리 평균뿐(`:8`,`:26`,`:34`,`:167` — findings 목록 0건). 수신처인 `docs/runbooks/session-handoff-2026-08-12.md:129` 는 "확정 P0 7 · P1 12 · P2 30 · 오탐 반증 21" 을 단언하지만 실제로 열거하는 것은 미해결 P0 5행(`:131-139`)과 결정 5건(`:141-147`) 뿐이다. 즉 P1 12 · P2 30 + 감사 스스로 밝힌 UNVERIFIED 131건(`audit:29`)은 리
- **권고**: backlog §'🔴 사용자 결정 대기' 에 감사 결정 5건을 (기전·반증수단 포함, 갱신 규칙 :306) 이관하고 §'🟡 착수 가능' 에 P1/P2 잔여를 등재한다. 날짜 붙은 handoff 런북을 결정 정본으로 지목하는 `audit:6` 의 위임을 backlog 로 되돌린다. 가드 후보: 감사·회고 보고서가 아카이브에 추가될 때 같은 PR 이 backlog 를 수정했는지 대조.

### P0-7 · 아카이브 보존 가드가 공동화된 아카이브에서 전건 green — Grok WEAKENED 를 닫았다는 봉인 주장이 거짓

- 관점 `tooling` · 위치 `tests/unit/scripts/test_rules_archive_backlink.py:27` · verdict **CONFIRMED**
- **주장**: #1335 가 Grok claim-review 019ff591 의 WEAKENED 반례를 닫았다며 추가한 5축(리터럴 지문 + 인용 다양성)은 **명명된 뮤테이션 하나만** 막았다. 실서사를 100% 제거하고 채움 문자열로 바꿔도 6축 전건 통과한다. 파일 27줄의 단언 *"채움 문자열은 둘 다 통과하지 못한다"* 는 실측으로 거짓이다.
- **근거**: 합성 아카이브를 만들어 가드 6축 술어를 그대로 실행했다. 구성 = 원본 헤더 + 7개 `## <area>` 절, 각 절은 `_SECTION_FINGERPRINTS`(:60-68)의 지문 3종 + `\`area_cite_0..24\`` 형태의 합성 백틱 토큰 25종 + `X` 2,100자, 전체를 rules 합계(40,126)보다 1자 크게 패딩 → 40,127자. 결과: anchor_sections_exist PASS · min_2000(:53) PASS · fingerprints(:130) PASS · citations>=25(:72,:142) PASS · non_executable(:152) PASS · archive>rules(:168) PASS = **ALL 6 GREEN**. 실아카이브는 101,380자인데, 이 통과본에 담긴 실서사는 지문 21개 + 합성 토큰 175개 ≈ 2,800자뿐이다. 즉 보존 서사의 ~97% 를 지우고 `X` 로 채워도 관측자가 참으로 보인다. Grok 반례(2000자 X + 패딩)와 **동일 클래스**이며, 추가된 두 축은 절당 지문 3개·백틱 토큰 25개라는 고정 비용만 부과한다.
- **권고**: (1) `test_archive_is_larger_than_the_rules_it_replaced`(:168) 의 비교 대상을 rules 합계가 아니라 **압축으로 제거된 분량**(base 합계 − head 합계 = 61,418자)의 하한으로 바꾼다 — 현재 하한 40,126 은 실크기 101,380 의 40% 라 사실상 무구속이다. (2) 절별 하한도 `_MIN_SECTION_CHARS=2000` 리터럴 대신 **base 커밋의 해당 규칙 파일 크기에서 파생**한다(git show cbae8c9d:.claude/rules/<area>.md). (3) 인용 다양성은 개수가 아니라 **base 원문에 실재하던 백틱 토큰과의 교집합 비율**로 잰다 — 합성 토큰 25개로 채우는 경로가 지금 열려 있다. (4) 정책 19 2-phase 보고 기준: #1335 본문·가드 docstring 의 "닫았다" 서술을 정정하거나 `UNVERIFIED:` 로 강등해야 한다.

### P0-8 · 결번 8차의 귀속 재구성이 틀렸다 — #1335 는 8차였던 적이 없다 (처방대로 복원하면 원장이 오염된다)

- 관점 `docs (원장 귀속)` · 위치 `docs/STATE.md:305` · verdict **CONFIRMED**
- **주장**: 이 gap 의 전제("빠진 8차 자리에 해당하는 것이 #1335")는 거짓이다. 8차 ordinal 은 #1331(README 충돌 마커 + pylint 진리값)의 **머지 전 브랜치**가 이미 점유했고, 그 PR 이 rebase 되며 11차로 재번호되면서 8이 **비워진** 것이다. #1335 는 8차를 가진 적이 없다. 따라서 "빠진 8차에 #1335 를 복원한다"는 처방은 7차(→7053)와 9차(7053→) 사이에 **체인이 닫히지 않는 거짓 행**을 삽입한다.
- **근거**: `git log --all -S"세션19 8차" -- docs/STATE.md` → `d44ebb93` (origin/fix/readme-badge-truth, 2026-08-12 07:58) 가 유일 도입. 그 커밋의 STATE diff: `- **세션19 8차 — README 충돌 마커 + pylint 진리값 (문서감사 PR-4) +21** (7053→**7074** 단위 …)`. 최종 머지본 `docs/STATE.md:305` = `**세션19 11차 — README 충돌 마커 + pylint 진리값 (문서감사 PR-4) +23** (7060→**7083**)`. 같은 제목·같은 PR, ordinal 만 8→11, base 7053→7060. 한편 머지 순서 실측(`git log --oneline main`)은 #1332 → #1333 → #1334 → **#1335** → #1337 → #1331 → #1336 → #1338 이므로 #1335 의 시간축 위치는 10차(#1334)와 11차(#1331) **사이**이지 8차가 아니다. 세션19 체인은 6949→6994→7009→7022→7034→7038→7045→7053→7058→7060→7083→7125 로 **결번 자리에 수치 공백이 없다**.
- **권고**: 8차 자리를 backfill 하지 말 것. (a) §추적 이력 **꼬리에** 정정 행을 append 하고(체인 델타 0, `= **N** 수집`·`→ **N** 단위` 형식 유지해야 `_history_tail` 이 red 안 남), 그 행에 #1335 의 per-PR 실측(아래 P1-5/P2-8 수치)과 "8차는 #1331 의 재번호로 비었음"을 함께 적는다. (b) ordinal 은 저술 시점이 아니라 **머지 후**에 부여하도록 6-step ⑤ 문구를 바꾼다 — 머지 전에는 알 수 없는 값을 손으로 적는 것이 이 결함의 기전이다.

## P1 83건 · P2 81건

전문은 워크플로 산출물에 있다. 여기에는 P1 상위 20건만 제목으로 싣는다 —
🔴 **나머지를 요약하지 않는다**: 요약이 원문을 대체하면 다음 세션이 요약만 읽고 닫는다.

| # | 관점 | 위치 | 제목 |
|---:|---|---|---|
| 1 | `process` | `docs/runbooks/session-handoff-2026-08-12.md:151` | #1338 이 6-step ② 자기면제를 자백한 본문에서, 정책 13·9 를 같은 형태로 다시 자기면제했다 |
| 2 | `process` | `scripts/check_test_count_sync.py:208` | 게이트가 인쇄한 처방을 그대로 따랐더니 그 게이트가 red 가 됐다 — self-consumption 축이 규율에 없다 |
| 3 | `process` | `scripts/pre_push_gate.py:143` | pre_push_gate 가 로컬에서 아무것도 평가하지 않은 가드에 "OK" 를 찍고 "전건 통과" 로 요약한다 |
| 4 | `process` | `scripts/check_red_budget.py:38` | 🔴 예산 게이트가 재는 것은 '가드 이름이 적혀 있는가' 뿐 — 오귀속은 원리적으로 초록이다 |
| 5 | `process` | `CLAUDE.md:65` | .claude/skills 6종이 구조상 로드 불가인데 CLAUDE.md 는 "선택이 아닌 의무적 도구" 라고 단언한다 |
| 6 | `process` | `docs/_archive/reports/2026-08-12-docs-audit.md:31` | 47-에이전트 감사가 자기 분모를 검증하지 않았다 — 분할 시 합집합·중복 무검증으로 CRITICAL 23건 누락 |
| 7 | `process` | `docs/runbooks/session-handoff-2026-08-12.md:131` | 감사에 시간축이 없어, 이미 고쳐 푸시된 미머지 브랜치를 못 보고 P0 3건을 오채점했다 |
| 8 | `code/security` | `src/config.py:532` | R77 봉인이 URL 쿼리스트링 자격증명을 마스킹하지 못한다 — 기동 오류에 비밀번호가 평문으로 인쇄된다 |
| 9 | `code/security` | `src/scheduler.py:95` | `Settings()` 직접 생성 경로가 남아 있고 그것을 막는 회귀 가드가 없다 (정책 4 위반) |
| 10 | `code/docs-consistency` | `AGENTS.md:19` | #1331 이 pylint floor 를 배지 파생으로 바꿨으나 "CI 동일 기준" 이라 적힌 9 지점이 9.90 리터럴로 남았다 |
| 11 | `code/tooling` | `.claude/skills/retrospective.md:1` | `.claude/skills/` 6종이 구조상 로드되지 않는데 CLAUDE.md·agents-index 가 슬래시 명령으로 등재했다 |
| 12 | `code/guards` | `scripts/check_docs_sync.py:52` | `check_docs_sync._first()` 가 다중 매치를 경고 없이 첫 건으로 좁힌다 — 같은 파일의 `_history_tail` 과 규율이 반대 |
| 13 | `docs` | `scripts/check_docs_sync.py:112` | check_docs_sync._first() 다중매치 fail-open — 두 번째 드리프트 주장은 검사되지 않는다 (뮤테이션 실증) |
| 14 | `docs` | `docs/runbooks/session-handoff-2026-08-12.md:20` | 가드 개수 '13종' 이 10개 파일 18줄에서 거짓 — 실측 17종이고, 이번 세션의 '정정'(16종)도 틀렸다 |
| 15 | `docs` | `AGENTS.md:19` | #1331 이 pylint 게이트를 배지 파생으로 바꿨으나 '9.90 = CI 동일 기준' 산문 8지점이 남았다 — 5지점 가드가 CLAUDE.md·AGENTS.md 를 보지 않는다 |
| 16 | `docs` | `.claude/rules/testing.md:87` | .claude/rules/testing.md 의 const/let 🔴 규칙이 무관한 가드를 집행자로 지목 — 진짜 가드는 따로 있고 check_red_budget 은 구별하지 못한다 |
| 17 | `decision` | `docs/runbooks/docs-consolidation-status.md:26` | 자칭 '정본' 진행상태 문서가 자기 세션 3개 머지를 반영 못해 완료분 재작업을 지시한다 |
| 18 | `decision` | `scripts/pre_push_gate.py:12` | 게이트 가드 개수 — 값 5종 공존, 정정 목표값(16)이 기록 시점에 이미 오답, 분모도 과소 |
| 19 | `decision` | `docs/runbooks/session-handoff-2026-08-12.md:159` | Grok 위임 경계 결정이 SSOT 밖 날짜 문서에만 있어 다음 호출에 도달하지 않는다 |
| 20 | `tooling` | `.claude/rules/api.md:64` | 압축이 집행자 인용을 **옮겨 붙였다** — api.md 에 미보고 오귀속 2건 + 진짜 집행 규칙 1건의 인용 소실 |

… 외 P1 63건 · P2 81건.

## 🔴 회고 중 라이브 재현한 것 2건

회고가 낸 P0 중 둘은 **이 세션에서 직접 재현**했다. 정적 독해가 아니라 실행 근거다.

### 1. `e7159d8f` 고아 — 확정, 이 PR 에서 회수

```
git merge-base --is-ancestor e7159d8f origin/main   → NO
git branch -a --contains e7159d8f                   → docs/rules-density 만
origin/main:.claude/rules/testing.md:87             → 틀린 귀속이 살아 있음
origin/main:docs/runbooks/...handoff...:155         → "(#1335 에 포함)" 거짓 단언
```

기전: `#1335` 는 11:26 UTC 머지, `e7159d8f` 는 12:29 UTC 커밋 — **이미 머지·삭제된 브랜치에
63분 뒤 얹었다**. 당시 push 출력이 `* [new branch]` 였고(삭제된 브랜치 재생성 신호) 놓쳤다.

### 2. 🔴 아카이브 보존 가드 — **내 봉인 주장이 거짓이었다**

`#1335` 본문에 *"Grok 반례가 이제 14 failed"* 라고 적고 그것을 fail-open 을 닫은 것으로 제시했다.
**클래스는 열려 있다.** 회고 중 재현:

```
서사 100% 제거 → 지문 3종 + 무의미 백틱 인용 30종 + 필러 문장 + 길이 패딩
→ pytest tests/unit/scripts/test_rules_archive_backlink.py  →  38 passed
```

내가 닫은 것은 Grok 이 준 **그 특정 뮤테이션 하나**(2000자 `X`)뿐이다.
파일 27줄의 단언 *"채움 문자열은 둘 다 통과하지 못한다"* 는 실측으로 거짓이다.

🔴 메모리 [[feedback-mutation-red-is-not-sufficient]] 가 규정한 클래스 그대로다 —
*"내 뮤테이션은 내가 상상한 실패 모드만 고른다."* 반례를 받아 고칠 때
**그 반례만 막고 봉인을 선언한 것**이 이번 세션의 가장 큰 규율 실패다.

## 정직 기준 — 이 회고가 못 본 것

- **`log()` 가 journal 에 안 실린다.** 라운드 경계·`log` 메시지가 진행 표시로만 가서, 세션이 끊기면
  *"몇 라운드에서 무엇이 나왔는지"* 를 사후 재구성할 수 없다. 이 리포가 반복해 고쳐 온
  *"관측은 하는데 기록이 안 남는"* 클래스이며, **이번 회고 자신이 그 사례다**.
- **P0 3건이 같은 사실을 셋으로 센다** — `e7159d8f` 고아 건이 process·decision·tooling 세 관점에서
  각각 제출됐다. 관점 분리의 부수 효과이고, P0 개수를 액면가로 읽으면 과대집계다.
- **fix 는 수행하지 않았다**(정책 7·15). 후속 PR 1건(고아 커밋 회수 + 거짓 단언 정정)을 제외하면 전부 결정 대기다.

