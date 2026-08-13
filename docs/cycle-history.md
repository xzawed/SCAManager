# SCAManager 사이클 작업 이력 (사이클 60~166, 최신순)

<!-- guard-cue-quote: 이 문서는 과거 사이클의 작업 흐름을 서술하며 실행 지시 어휘를 인용한다. 지시가 아니라 기록이므로 do-not-execute 표지 대상이 아니다. -->

> CLAUDE.md tail entry 분리본. 사이클 60~166 이력 (본문 최신순 — 목차는 166부터, 하단에 60~92 archive).
> 🔴 **사이클 번호는 166 이후 date 기반(YYYY-MM-DD)으로 대체** (2026-06-16~ 최근 작업은 날짜 헤더 — `active.md` "사이클 167" 은 그 전환기 라벨). CLAUDE.md/README 의 "60~166" 은 번호 체계 이력 상한이며 최신 작업은 날짜로 식별.
> 본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무.

## 목차

- [문서를 룰에서 프로세스로 — 3층 분리 + 아카이브 정리 (2026-08-13~14 세션19, 4 PR #1342~#1345)](#문서를-룰에서-프로세스로--3층-분리--아카이브-정리-2026-08-1314-세션19-4-pr-13421345)
- [회고 P1 이행 + 결정 6건 + 진단 처방 P1~P4 + 5+1 회고 (2026-08-06~08 세션17, 22 PR #1297~#1318)](#회고-p1-이행--결정-6건--진단-처방-p1p4--51-회고-2026-08-0608-세션17-22-pr-12971318)
- [e2e drift 30건 해소 + 문서 설계 감사 + CLAUDE.md 200줄 (2026-08-05~06 세션16, 8 PR #1288~#1296)](#e2e-drift-30건-해소--문서-설계-감사--claudemd-200줄-2026-08-0506-세션16-8-pr-12881296)
- [게이트 stdin 봉인 + prompt caching + 구조화 출력 (2026-08-04~05 세션15~16, 12 PR #1276~#1287)](#게이트-stdin-봉인--prompt-caching--구조화-출력-2026-08-0405-세션1516-12-pr-12761287)
- [backlog 잔여 이행 + Grok 4중 claim-review (2026-08-02 세션14, 4 PR #1268~#1271)](#backlog-잔여-이행--grok-4중-claim-review-2026-08-02-세션14-4-pr-12681271)
- [5+1 회고 + Grok 6중 협업 + 가드 근본원인 분석 (2026-07-31~08-01 세션13, 19 PR #1248~#1266)](#51-회고--grok-6중-협업--가드-근본원인-분석-2026-07-3108-01-세션13-19-pr-12481266)
- [문서 claim-review 정정 + CONTRIBUTING/SECURITY 신설 + 전수 감사 P0 이행 (2026-07-30~31 세션12, 5 PR #1241~#1245)](#문서-claim-review-정정--contributingsecurity-신설--전수-감사-p0-이행-2026-07-3031-세션12-5-pr-12411245)
- [GitHub Issue 2건 처리 + 정책 19 집행면 + Grok 전반 검토 (2026-07-29~30 세션11, 9 PR #1228~#1237)](#github-issue-2건-처리--정책-19-집행면--grok-전반-검토-2026-07-2930-세션11-9-pr-12281237)
- [다른 PC 이식 준비 + 새 clone 경로 복구 + git 정리 (2026-07-27 세션10, 3 PR #1223~#1225)](#다른-pc-이식-준비--새-clone-경로-복구--git-정리-2026-07-27-세션10-3-pr-12231225)
- [GitHub 정리 + owed #1072 외부계약 반증 + 5+1 회고 (2026-07-26 세션9, 3 PR #1217~#1219)](#github-정리--owed-1072-외부계약-반증--51-회고-2026-07-26-세션9-3-pr-12171219)
- [종합감사 이행 + 5+1 회고 + 회고 P1 (2026-07-24 세션8, 8 PR #1194~#1201)](#종합감사-이행--51-회고--회고-p1-2026-07-24-세션8-8-pr-11941201)
- [SonarCloud QG 복구 + 5+1 회고 + 회고 결정 이행 (2026-07-22 세션7, 8 PR #1168~#1175)](#sonarcloud-qg-복구--51-회고--회고-결정-이행-2026-07-22-세션7-8-pr-11681175)
- [전체 문서·코드 구조 재구성 (2026-07-21 세션6, 10 PR #1157~#1166)](#전체-문서코드-구조-재구성-2026-07-21-세션6-10-pr-11571166)

> 🔴 이하 **143개 과거 사이클**은 §접은 이력에 1줄로 있고, 원문은
> [`docs/_archive/cycle-history-folded-2026-08.md`](_archive/cycle-history-folded-2026-08.md) 다.

## 문서를 룰에서 프로세스로 — 3층 분리 + 아카이브 정리 (2026-08-13~14 세션19, 4 PR #1342~#1345)

사용자가 문서 작성법 자체를 바꿨다 — *"룰과 규칙을 보강하는 방식이 아니라 **어떻게 수행하고
어떤 방식으로 프로세스와 플로우로 진행되는가**가 중요하다. 룰은 최소 기준으로 남기고 그때그때
Claude 와 Grok 이 협의한다."* 그 결정을 리포 구조로 옮긴 세션이다.

**3층 분리** — 프로세스(`docs/process/` 5) · 함정(`.claude/traps.md` 17 클래스) ·
규칙(`.claude/rules`·`policies`, 🔴 는 집행자 동반분만). 무집행 마커 **221개를 제거**했고
규칙 본문은 한 줄도 지우지 않았다(집행 비율 28% → **100%**). 처음엔 168건을 "삭제 후보" 로
분류했다가 표본을 읽고 폐기했다 — `alembic env.py fileConfig 가드 제거 금지` 같은 실제 운영
계약이 섞여 있었다.

**아카이브 56 파일(622KB) 삭제**. `git grep` 0건인 것만 골랐고, 그 과정에서 **P4-Gate-2**
(rubocop·golangci-lint 실바이너리 미실증)가 아무도 읽지 않는 파일에서 **3.5개월 늙고 있는 것**을
발견해 backlog R87 로 승격했다. 그것이 삭제의 근거다 — 총량 절감이 아니라.

**적대 검증이 세 PR 의 봉인 주장을 전부 깎았다.** Grok `019ffb93` 이 `#1345` 의
*"무집행 🔴 은 0이고 기계가 강제한다"* 를 **BROKEN** 으로 판정했다 — 🛑 로 쓴 무집행 규칙이
카운터에 안 잡히고(마커 위장), 표면 파일을 통째로 지워도 로컬은 `100.0%` + EXIT 0 을 인쇄했다.
반례 하나씩 막지 않고 **클래스로** 닫았다(마커 동의어 집합 · 배너가 *"안 쟀다"* 를 말한다).
무관한 가드 이름을 집행자로 적는 프록시 축은 **닫지 않고 명시**했다 — 의미 판정이라 정적으로
닫히지 않는다.

워크플로 `wf_d4c837bb-603`(15 에이전트)이 나머지 세 PR 도 깎았다: `#1343` 잔여 stub 5건 절단
(전문은 아카이브에 도달 가능 — 소실 아님) · `#1342` 어휘 생존 가드는 의미 뒤집기를 못 잡는다
(뮤테이션 3종 전건 통과) · `#1344` 의 테스트가 **자기 변경을 관측하지 않았다**(`_IMPORTANT` 에
중복 패턴을 만들어 단언이 base 에서도 참). 셋 다 고칠 수 있는 것만 고치고 나머지는
**R88·R89** 로 열어 뒀다.

**단위 7143 → 7148** (4 PR 순변화 +5, 통합 171 불변 = 7319 수집).

## 회고 P1 이행 + 결정 6건 + 진단 처방 P1~P4 + 5+1 회고 (2026-08-06~08 세션17, 22 PR #1297~#1318)

2026-08-06 회고(190 에이전트·확정 147)가 원장에 남긴 P1 을 순서대로 이행한 세션.
네 PR 전부 **Grok claim-review 를 거쳤고, 그중 3건이 `BROKEN` 판정**을 받아 2라운드로 갔다.

**`#1297` (R61) — 첫 블록이 text 라는 가정** — 4곳이 Anthropic 응답을 `content[0].text` 로
인덱싱하고 있었다. `content` 는 블록 배열이라 thinking·tool_use 가 앞서면 `AttributeError` 고,
그 넷이 전부 `except Exception` 안이라 **`api_error` 로 조용히 삼켜진다**. 모델이나 설정을 한 번
바꾸면 AI 리뷰가 전량 사망하되 원인은 안 보이는 형태다. `first_text_block` 헬퍼로 통일.
🔴 Grok 이 **5번째 호출부**(`scripts/i18n_comments/translate_comments.py`)를 찾았고 — 회고는 4곳이라
했다 — 정규식 가드가 `content[1]`·`content[-1]`·변수 별칭으로 **4가지 우회**를 허용한다는 것도
적발해 AST 기반으로 다시 썼다.

**`#1298` (R58) — e2e 초록의 공허화** — `live_server` 가 `pytest.skip` 을 던져서, **앱이 부팅조차
못 해도 121건 전건 skip 후 job 이 exit 0** 이었다. skip 을 `RuntimeError` 로 바꾸고 수집 건수
baseline(`e2e/EXPECTED_COUNT`)을 붙였다. 🔴 Grok 이 *"공허화 경로는 둘이 아니라 셋"* — **수집을
보존한 채 전건 skip** 하면 baseline 가드도 통과하고 exit 0 이다 — 을 지적해 `--e2e-min-passed`
통과 하한을 추가했다. 같은 라운드에서 수집 파서가 `2 tests collected, 1 error` 에서 **2 를 뽑아**
통과시키던 것과 배선 단언이 `guards.md` 가 금지한 substring 이던 것도 함께 봉인.

**`#1299` (R63) — 한 호출이 비용 2행** — `log_claude_api_call(status="success")` 가 파싱보다
**앞**이라, 추출 실패 시 success 와 error 가 **둘 다** 기록됐다(실측 `['success','error']`).
성공률 과대 + 비용 이중 계상이다. `ai_review` 는 홀더+`finally` 단일 기록으로, 두 서비스는
추출·파싱을 로그보다 앞으로. 🔴 Grok 2라운드가 잔여를 찾았다 — 1차 수정은 로그를 `json.loads`
뒤로만 옮겼는데 **유효 JSON 이 dict 가 아니면** 그 다음 줄 `data.get` 이 success 로그 **뒤에서**
터져 여전히 2행이었다. 로그를 결과 조립 뒤로 재이동.

**`#1300` (R65) — 실패 행의 토큰이 0** — R63 이 행 수는 고쳤지만 그 1행이 error 경로일 때
토큰을 0 으로 적었고, `log_claude_api_call` 의 docstring 이 *"에러 시 0"* 이라고 그 관행을
**처방**하고 있었다. 응답을 받은 뒤 실패한 경우 토큰은 이미 과금됐으므로 `monthly_cost` 가
과소가 된다. 🔴 Grok 이 가드의 공허함을 지적했다 — **모든 테스트가 `log_claude_api_call` 을
스파이로 대체하거나 `_persist_cost` 를 패치**해서, *"실패해도 비용이 기록된다"* 는 주장이 **한
번도 관측된 적이 없었다**. 호출부 실패에서 실제 `claude_api_calls` 행까지 무패치로 관통하는
테스트를 신설했고, 영속화를 끊는 뮤테이션에서 **그 테스트만** red 였다.

🔴 **이 세션이 남긴 것** — 네 PR 모두 *"고쳤다"* 까지는 혼자 도달했고, **"고친 것이 관측되는가"**
는 네 번 다 Grok 이 뒤집었다. 형태가 매번 같다: 내가 만든 관측자가 **내가 방금 고친 결함을 다시
넣어도 초록**이었다. 잔여는 정직하게 원장에 남겼다 — 백필 없음(과거 행은 그대로) · **R66**(SDK
재시도분은 원리적으로 비가시 = *"모른다"* 를 원장이 *"안다"* 처럼 보이게 한다) · R64(e2e 가
required check 가 아니라 빨개도 머지를 막지 않는다).

**사용자 결정 4건 처리 (`#1302`~`#1306`)** — 원장에 🔴 결정 대기로 쌓여 있던 항목을
사용자가 *"4개 다 필요한 부분이라 권장하는 순서로"* 지시해 R56 → R0-2 → R57 → R64 순으로
이행했다. 착수 전 **9-에이전트 설계 워크플로**(항목별 설계 → 적대 검증 → 완전성 비평)를
돌렸고, 그 검증이 **3건 BROKEN · 1건 WEAKENED** 판정을 내며 원래 계획을 여러 번 뒤집었다 —
특히 *"설치보다 설정 정정이 먼저"* 라는 순서가 그렇다.

**사용자 질문이 창의 성격을 바꿨다 (`#1308`~`#1312`)** — *"계속되는 실수와 검증 실패,
반복 발화되는 규칙이 문서 전체 규모의 문제로 보인다"*. 9-에이전트 진단(4 가설 → 각각
적대 반증 → 최종 판단)을 돌렸고 결론은 **"증상은 정확, 기전은 반대"** 였다.

🔴 **총량 가설 3/10 · "규칙이 지켜지지 않는다" 8/10.** 문서가 많아서 못 지키는 것이
아니라, **못 지킨 규칙마다 문서를 한 줄 더 쓴 결과**가 그 규모다. 결정적 반증:
`path-scoped rules 본문 sync` 는 **발화율 ~100% / 이행률 0%**, 정책 13 smoke 는
**0/42** — *"안 읽어서"* 로는 설명되지 않는다. 총량 축소는 두 번 시도해 두 번 다
순손실이었다(`#1296` → Grok BROKEN[행동 규칙 8건 소실] / R54 파생화 → 틀린 값 4지점 전파).

🔴 **사용자 직관이 맞은 지점**: 총 코퍼스는 2026-05 대비 **+148%**(강제 로드 −21%,
`.claude/rules` **+334%**)다. 8월 문서 감사가 *"총량 기각"* 이라 결론냈을 때
**줄어드는 축만 재고 334% 자란 축을 뺐다**. 다만 자란 곳이 배타적 지연 로드 풀이라
실현 로드는 창의 4% 수준이고, 문제는 **바이트가 아니라 집행 비율**이었다 —
🔴 규칙 **290**건 중 집행자 동반 **67건(23.1%)**.

**지배 원인**: *결함을 고친 당사자가 그 결함을 검증할 관측자를 같은 PR 안에서 만들고,
그 관측자는 하필 그 PR 이 고친 결함에만 맹목이다.* 이 창이 그것을 **자기 몸으로** 증명했다 —
테스트 수 `6840` 오판독이 `--fix` 로 4지점에 전파돼 사본은 완벽히 일치했고
(`check_docs_sync` ✅) PR 을 통과해 머지된 뒤 **main CI 가 12시간 49분 빨갰다**.
사용자가 *"확인해달라"* 고 하기 전까지 아무도 몰랐다.

**처방 4건을 전부 구현했다 (`#1309`~`#1312`)**:

| # | 처방 | 무엇을 바꿨나 |
|---|---|---|
| **P1** | 역-뮤테이션 게이트 | PR 의 생산 diff 를 되돌리고 그 PR 의 테스트만 재실행 — **red 아니면 실패**. 소급 6 PR 전건 red 로 채택 |
| **P2** | 드리프트 PR 차단 | `--advisory-drift` 제거. 이월은 `STATE-sync-deferred:` **명시 마커**로(계수됨) |
| **P3** | main red 관측자 | 지표를 *"발화했는가"* 가 아니라 **"몇 시간째인가"** 로. 실측 방치 **20h·12.8h** |
| **P4** | 🔴 예산제 | **집행자 없는 🔴 이 늘면 실패**. 바이트가 아니라 집행 비율을 잰다 |

🔴 **처방을 만드는 동안 내가 만든 가드가 나를 6번 막았다** — P1 뮤테이션 M2(no-op 축
무테스트) · CI 가 잡은 P1 의 배치 오류와 **`__pycache__` fail-open**(Linux 에서만 발현) ·
P2 뮤테이션 M3·M5(인용 면제 과잉 · 헬퍼 직접 호출) · P3 뮤테이션 M6(`in_progress`
필터 무판정력) · P4 패리티 2종. **이 프로젝트가 반복해 온 그 패턴을, 그것을 고치는
도구가 다시 범했다.** 그래서 매 처방마다 뮤테이션과 통제 실험을 돌렸다.

**R56 (`#1303`)** — pre-commit 이 이 머신에 **한 번도 설치된 적이 없어** 16 훅이 19 PR 내내
0회 실행됐고, **그래서 그 안의 결함도 함께 보이지 않았다.** 문서·가드 훅 7종이
`language: system` + `entry: python …` 이라 Windows Store 스텁으로 해소된다 —
실행 비교 실측: `system` = **Failed(exit 9009)** / `python` = **Passed**. 그냥 설치했다면
커밋이 전부 막혔을 것이다. 🔴 그리고 관측자는 **침묵한 적이 없었다** — 매 세션 loud 했지만
PATH 바이너리를 AND 조건으로 요구해 **설치에 성공해도 계속 빨강**이었다. 고칠 수 없는
빨강은 정상 빨강과 구별되지 않아 배너 피로로 신호를 죽인다. 설치 후 첫 실 커밋에서 계층이
실제로 차단했고(플레이스홀더 오탐), 가드를 약화시키지 않고 해당 파일만 뺐다.

**R0-2 (`#1304`)** — owed 원장 가드가 **원장에 적힌 것만** 세어, 부채를 등재하지 않는 것이
가장 싼 통과 경로였다(파일 부재 = 무음, 빈 원장 = "미결 0건"). 두 축을 넣었다: 원장 자체의
완전성(부재·읽기 실패·0행 → `판정 불가`)과 intake 정체(원장 갱신 이후 머지 PR 수, git 전용).
🔴 PR 본문을 읽어 '등재 대상인가' 를 판정하는 축은 **기각**했다 — 산문 판정 오탐 · 로컬
러너가 PR env 없이 도는 제약 · 워크플로 패리티 가드, 셋 다 설계 검증이 실측으로 짚었다.

**R57 (`#1305`)** — 정책 19 는 *실질 작업마다* 인데 가드는 **seal 어휘가 있을 때만** 요구했고,
나는 그 **가드 트리거를 정책 트리거로 오인**해 면제를 자기발급했다(25 PR 중 6건). 코드·가드
표면 트리거를 신설했다(실측 오탐 3/30). 🔴 Grok 이 **WEAKENED** 로 세 구멍을 찾았다:
CI 의 SHA env 가 load-bearing 인데 무검증 · `main()` 의 env→인자 사상 무검증 · 판정 불가에서
*"변경 없음"* 이라 단언. 부수로 **`WEAKENED` 를 합법 verdict 로 추가**했다 — Grok 이 실제로
내는 판정인데 목록에 없어, 표현 수단이 없으면 저자가 SURVIVES 로 반올림하게 된다.
⚠️ **새 트리거는 라이브로 분리 검증하지 못했다** — 최근 커밋이 전부 seal 어휘를 담고 있어
그 축이 먼저 발화한다. 근거는 단위 테스트(생산 `main()` 실행)와 뮤테이션 red 이지 라이브 관측이 아니다.

**R64 (`#1306`)** — e2e job 을 required check 로 승격(9 → 10). 근거는 실측이다:
`#1294` 이전 **2/17**, 이후 **16/16** — 빨강의 원인은 플레이크가 아니라 원인이 밝혀진 결함이었다.
🔴 라이브 설정을 관측하는 가드는 **만들지 않았다** — 필요한 토큰을 리포 시크릿에 두면
containment 가 성립하지 않고, 없는 관측을 있는 것처럼 보이게 하는 파일이 더 나쁘다.
대신 이름 drift(= required check 가 영원히 pending 이 되는 축)만 닫고 한계를 런북에 적었다.
🔴 **승격 비용이 같은 날 즉시 실현됐다** — GitHub Actions 장애(2026-08-06 15:22 UTC~, major
outage)로 required 체크가 러너를 못 받아 `#1306` 자신이 몇 시간 막혔다. `enforce_admins: true`
라 우회가 없다. 그 대응 절차(워크플로 완료 대기 → `gh run rerun --failed`)를 런북에 남겼다.

🔴 **부수 발견 2건이 이 창의 실질 수확일 수 있다.** ① TruffleHog 의 Lob 탐지기가 **정확히
40자인 `test_` 함수명**을 API 키로 매칭하고, Lob API 가 403/422 를 '활성 키' 로 취급해
**verified 로 확정**한다 — 리포에 같은 패턴이 **188건** 잠재하고, 그 줄을 건드리는 PR 마다
required 체크가 무작위로 red 가 된다(탐지기 제외 + 저술 시점 가드 2층으로 봉인).
② 훅 명령 7종이 **상대 경로**라 셸 cwd 가 리포를 벗어나면 Bash·Write·Edit 이 전부 잠기고
**자력 복구가 불가능**하다(서브에이전트도 같은 cwd 를 상속해 막힌다). 이번 조사 중 실제로
두 번 잠겼고, 탈출구는 `Monitor` 툴뿐이었다 — 우연히 찾은 경로이지 설계된 복구 수단이
아니다(R67, 결정 대기).

📌 **부수 정정**: `#1295` 는 **머지되지 않고 CLOSED** 됐고 실제 머지본은 `#1296` 인데,
cycle-history·STATE·owed 원장·backlog **4 문서가 `#1295` 를 구현으로 인용**하고 있었다.
전건 `#1296` 으로 정정 — 닫힌 PR 을 구현으로 가리키는 참조는 backlog **R55**(dangling 참조)가
다루는 클래스이고, **관측자가 없어 이번에도 사람이 눈으로 찾았다**.

**`#1313`·`#1314` — 서사 동기화와 auto-merge 봉인** — `#1313` 은 진단 처방 P1~P4 의 서사를
STATE·cycle-history 에 반영한 trailing sync 다. `#1314`(R68)는 사용자가 *"auto-merge 를 실제로
운용한다"* 고 확인해 실해가 확정된 뒤 이행했다 — `mergeable_state="blocked"` 는 GitHub 이
**(a) required check 진행 중** 과 **(b) 규칙상 충족 불가** 를 뭉뚱그린 값인데, 이전 계약은 전부
(b)로 처리해 **정상 PR 이 재시도 없이 영구 포기**됐다. `should_retry` 에 분기를 신설해
**CI 가 `running` 일 때만** 재시도로 확정한다 — `passed`·`failed`·`unknown` 을 종결로 두는 것이
핵심이다(그래야 (b)가 `max_attempts` 예산을 태우지 않는다).

### 🔴 5+1 회고 — 내가 만든 게이트 4개 중 3개가 같은 결함이었다

카덴스 트리거(머지 PR **18건** ≥ 임계 15)로 정식 회고에 진입했다(11 에이전트 ·
verdict_coverage 1.0). 1순위 질문은 *"이번 창에 만든 게이트 P1~P4 가 정말 작동하는가"* 였고,
답은 절반이었다. 전문: [`2026-08-08-retrospective.md`](_archive/reports/2026-08-08-retrospective.md).

**`#1315` — P0 3건 봉인.** 세 건 다 *관측자가 진실 대신 자기 사본을 잰다* 는 이 리포의
지배 형태다.

🔴 **`6840` 은 사람의 오판독이 아니었다.** `git ls-files` 는 머지 충돌 중인 경로를 stage
1/2/3 으로 **3번** 출력하고, 그 결과가 `parametrize` 2곳에 쓰여 충돌 `.md` 1건당 collected 가
**+4** 된다 — `6824 + 4×4 = 6840`. 배치-PR 충돌 4건 상태에서 잰 값이 `--fix` 로 4지점에
파생 전파됐고, **사본끼리는 완벽히 일치**해 `check_docs_sync` 가 ✅ 를 냈고, 머지 후 CI 가
6824 를 재서 main 이 12시간 49분 red 였다. `#1308` 이 이것을 *"오판독"* 으로 기록했는데
**그 규명이 틀렸다** — 계기가 거짓을 냈고 사람은 그 값을 정확히 읽었다. 원인 규명이
틀리면 처방도 틀린다: 전파 차단(P2)은 두 번째 방어선이지 원인 제거가 아니었다.

그리고 새 게이트 **3종 전부**가 `os.environ["PR_BODY"]` 원문을 정규식에 넘겨, HTML 주석 안
마커가 *"리뷰어 비가시 + 게이트 통과"* 를 성립시켰다 — `check_claim_review_trace` 가
backlog **R20 결함 1** 에서 이미 값을 치르고 닫아 둔 축의 **3중 재발**이다. 마커 관용구는
복제됐는데 **하드닝은 복제되지 않았다**. 교훈은 "복제하지 말라" 가 아니라
**"읽는 지점을 하나로 두라"** 다.

🔴 **그리고 Grok 이 내 봉인을 깼다** (`019fe026` — 1 BROKEN · 2 WEAKENED). 이월 마커를
커밋 메시지로 옮겨 "머지 후 소멸" 을 고쳤다고 적었는데, Grok 이 *"마커를 커밋 **본문**에 적고
**merge commit** 으로 머지하면 tip 은 `Merge pull request #N` 이라 마커가 없다"* 를 반례로 냈다.
실측 확인 — 이 리포는 `allow_merge_commit`·`allow_rebase_merge` 가 **둘 다 켜져 있다**.
도달 가능한 경로였고, 내 테스트는 `_git_text` 를 단일 문자열로 mock 해서 **머지 토폴로지를
한 번도 실행하지 않았다**. push 도 `before..after` **범위**로 읽도록 재설계하고 실제 `--no-ff`
머지 커밋을 만드는 테스트를 넣었다.

🔴 **가장 중요한 사실**: 11 에이전트 회고는 이 결함을 **못 찾았다.** 회고는 *"게이트가
작동하는가"* 를 물어 통과를 확인했고, Grok 은 *"이 봉인을 어떻게 깨는가"* 를 물어 깼다.
**질문의 형태가 결과를 갈랐다** — AGENTS.md 불변식 2(실경로 뮤테이션 red)를 지켰는데도
틀렸던 이유는, 내 뮤테이션이 **내가 상상한 실패 모드만** 골랐기 때문이다.

### 🔴 적대 검증 4라운드 — 내 주장이 세 번 깨졌다

회고 이후 사용자가 결정 2건을 승인했다: **(1) 가드 PR 은 Grok claim-review 필수 승격
(2) 머지 방식 3종 유지.** 그 구현이 `#1317` 이고, 구현 과정 자체가 이 창의 결론을 실증했다.

| 라운드 | 검증자 | 결과 |
|---|---|---|
| 1 | 11-에이전트 5+1 회고 | P0 5건 발견 — **이월 마커 결함은 놓침** |
| 2 | Grok `019fe026` | **BROKEN** — merge commit tip 에 마커가 없다 |
| 3 | Grok `019fe089` | **BROKEN** — 목록 밖 가드가 통과 + 내 테스트가 공허 |
| 4 | 11-에이전트 재검증 `wf_a3ad73e1-eca` | **거짓 집행자** — 내가 만든 관측자가 거짓을 초록으로 지킴 |

**`#1317` — 면제의 적용 범위를 좁혔다.** 관측자를 저술하는 PR(`scripts/` · 훅 · 워크플로 ·
CI 설정 · 그 테스트 · owed 원장)은 `claim-review-not-required` 로 통과할 수 없다.
문서 전용 PR 의 **인용**과 seal 주장 없는 일상 코드 변경은 그대로 면제된다 —
회고·원장 기록이 막히면 이 리포의 학습이 멈추고, 일상 리팩터까지 막으면 오탐이 진탐을
넘는다(정책 17).

🔴 **함께 흔적 계약을 벤더 중립화했다.** 면제를 닫는 순간 `session` 필드가 단일 벤더 형식만
받으면 그 서비스가 죽는 날 가드 작업이 영구 차단된다 — 봉인이 아니라 **가용성 사고**다.
워크플로 run id(`wf_…`)도 받되 자유 문자열은 거부한다(요건은 *되짚을 수 있는 식별자*).
내가 쓴 테스트가 이 문제를 먼저 잡았다.

**Grok 이 그 PR 자신을 BROKEN 판정했다** — 가드 판정이 `_CODE_SURFACES` 필터 **뒤**에 있어
`tools/check_new_guard.py` 같은 목록 밖 가드가 **도달조차 못 했고**, 내가 쓴 docs-only
테스트는 `base == head` 라 *"빈 diff 가 면제된다"* 만 증명하는 공허한 단언이었다. 둘 다
재현 후 고쳤고, 닫지 않은 잔여(열거의 원리적 불완전 · 흔적 위조 · 조기 return)는 **R74** 다.

### 🔴 `#1318` — 거짓 집행자, 그리고 CI 초록이 알려주지 않는 유실

`#1316` 이 E2E 셀의 총계를 121 로 고치면서 내역을 `109 표준 + 12 perf` 로 적었다.
실측은 **110 + 11** — 두 성분 다 거짓이다. 그리고 **같은 커밋이 만든 전용 집행자**가
`총계 == 표준 + perf` 만 봐서 **초록인 채로 그 거짓을 지켰다**. 합이 맞는 거짓 쌍은 무한히 많다.

🔴 **회고가 스스로 내린 진단 — *"집행자 붙은 숫자는 100% 정확, 안 붙은 숫자는 8곳 오류"* —
은 그 진단을 적은 커밋에서 반증됐다.** 실패 양식이 *미집행* 에서 **거짓 집행** 으로
옮겨갔고, 이쪽이 더 나쁘다. 미집행 숫자는 아무도 안 믿지만 초록 집행자가 지키는 숫자는
다음 사람이 믿는다. 성분 대조를 e2e 를 실제로 수집하는 유일한 지점(`check_e2e_scope.py`)
으로 옮기고, 단위 테스트는 **자기가 못 보는 축을 정직하게 적고** 그 축이 어딘가에서
집행되는지 배선 단언한다.

함께 닫은 것 둘: GitHub squash 가 커밋 ≥2 이면 각 제목에 붙이는 **`* ` 접두**가 이월 마커를
죽이던 것(운반체는 살았는데 표기가 바뀐 것 — 라운드 2와 같은 클래스), 그리고 마커를
**설명하기만 한** 커밋이 면제를 발급하던 fail-open.

🔴 **운영 교훈**: `#1317` 머지 시 마지막 커밋이 **유실**됐다 — push 직후 머지가 실행되며
GitHub 이 2 커밋만 인식했다. **main CI 는 초록이었다** — 유실분이 테스트 수를 바꾸지 않는
축이라 드리프트 가드가 발화하지 않았다. **CI 초록은 유실을 알려주지 않는다.**
머지 전 `gh pr view <N> --json commits` 로 커밋 수를 확인할 것.

## e2e drift 30건 해소 + 문서 설계 감사 + CLAUDE.md 200줄 (2026-08-05~06 세션16, 8 PR #1288~#1296)

사용자 발화 *"자꾸 실수나 번복된 거짓보고가 많습니다"* 로 시작한 근본원인 추적 세션.

**e2e (R7→R52)** — `#1288` 이 Playwright 122건을 CI 에 처음 배선하자 30건이 빨갛게 드러났다.
🔴 진짜 결함은 *"실행되지 않는 초록"* 이 아니라 **"실행된 적이 없어 아무도 몰랐던 빨강"** —
로컬 Windows 에서도 31건이 실패해(CI 28 ⊂ 로컬 29) **환경 원인은 0건**이었다. 근본원인 11개,
상위 2개(`data-theme`→`data-theme-target` 리네임 미추종 10건 · `/login` 301 로 **GitHub 페이지를
검증** 8곳)가 절반. `#1291` 이 29건 해소, `#1294` 가 잔여 1건(CSP 가 자기 폰트 차단 — 14개월간
폰트 미적용)을 해소해 **배선 이래 처음 전건 초록**.

**문서 설계 감사 (R54)** — Claude 11-에이전트 + Grok 독립, 양쪽 **총평 4/10**. 🔴 총량 가설은
기각(강제 로드 창의 12.3%, 3개월 +8%)되고 **형상**이 문제로 확정: `STATE.md:36` 이 한 줄
**30,806자** · `docs/**` path-scoped 규칙 **0개** · 같은 정수 **5지점 손유지**. `#1293` 이 이력을
표 밖으로 분해(최장 줄 2,764)하고 `--fix` 파생으로 손유지를 **5→1** 로 줄였다.

**CLAUDE.md 200줄 (`#1296`)** — Anthropic 공식 *"target under 200 lines"* 대비 **424줄(2.1배)**.
196줄·10,917 토큰으로 축소(-49%), 강제 로드 12.3%→7.1%.

🔴 **이 세션의 교훈은 "혼자서는 못 잡는다" 이다.** Grok claim-review 가 4라운드에 걸쳐
`WEAKENED`·`BROKEN` 판정을 냈고, 그중에는 **내가 만든 가드 2개가 공허**(항상 통과)하다는 것과
**축소가 행동 규칙 8건을 삼켰다**는 것이 포함된다. 5+1 회고(190 에이전트·확정 147)는 다시
그 축소가 만든 결함 3건을 잡았다. 측정 도구 자체가 결함원이던 사례가 5건이라 `AGENTS.md` 에
**측정 규율** 축을 신설했다.

## 게이트 stdin 봉인 + prompt caching + 구조화 출력 (2026-08-04~05 세션15~16, 12 PR #1276~#1287)

문서 심의 게이트를 두 세션 죽였던 결함들을 연속 봉인한 창. `#1279` = 게이트가 한글을
**mojibake 로 읽고 자기 손상을 근거로 차단**(cp949 stdin — `#1276` 의 lone surrogate 는 증상이고
이것이 원인). `#1282` = prompt caching 으로 편집당 ~110k → 2회차 ~15k. `#1286`·`#1289` =
Anthropic 구조화 출력(`output_config.format`)을 훅 + 서비스 3경로에 적용(R51). 🔴 그 라이브
검증이 **별개 운영 P0** 를 드러냈다 — `.env` 의 `CLAUDE_REVIEW_MODEL=`(빈 값)이 기본값을
덮어 **모든 AI 리뷰가 `api_error`** 였다(pydantic-settings 는 `""` 를 *제공된 값*으로 본다).

## backlog 잔여 이행 + Grok 4중 claim-review (2026-08-02 세션14, 4 PR #1268~#1271)

이전 세션 인수인계(backlog 현재 창 🟡 7건)의 착수 가능분 6건 이행 — 사용자 지시 = "잔여 작업을 Grok 과 함께".
매 PR Grok claim-review(4세션, 전부 HOLDS-with-caveat → 적발분 같은 PR fix-up) + test-writer TDD 선행
6라운드(worktree 격리) + 실경로 뮤테이션 21건 red. 회고 카덴스(17 PR ≥ 15) 발화에 사용자 결정 =
"작업 먼저 + 세션 말미 회고" — 5+1 회고(run `wf_d89db046-274`, 21 PR #1250~#1271)를 세션 말미 병행 기동.

- **R16+R17**(#1268, Grok `019fbe1f`): B8 빈 스캔 표면 exit 1 + `.claude/hooks/*.py` 표면 확대(오탐 0 실측) + 구문깨짐·`read_bytes` 미탐 봉합(Grok 적발 2건) · lint-js justified ↔ 커밋 baseline 대조(GROK-12 의 6→5 축소 EXIT=0 를 실경로 재연 red 로 전환). CodeQL #564(note) 시정. 뮤테이션 7/7 red.
- **R20**(#1269, Grok `019fbe32`): 정책 19 집행면 — HTML 주석 안 흔적/면제 불인정 · 단수형 `뮤테이션 N건/N종 red` 어휘 · 면제 `::notice` 계량 · SSOT 등재. 🔴 Grok 이 초판 정규식의 가시 텍스트 과제거(펜스 안 `<!--` 이후 가시 seal 은닉 fail-open · 가시 흔적 false red · `
` 워크플로 커맨드 위조)를 재현 적발 → **마크다운 인지 상태기계** 재설계 + diff 재확인 전건 HOLDS. 뮤테이션 7/7 red. 잔여 = session-id 재사용 축(gh 의존 제외).
- **R31**(#1270, Grok `019fbe49`): check_edit_allowed 행동 커버리지 0 → 함수 분해 + 23케이스. stdin 파손 silent → **loud fail-open**(additionalContext+systemMessage, deny 기각 사유 = 전 편집 차단 가드 자살). Grok 이 main() deny stdout freeze 갭 재현 적발 → 봉합. 뮤테이션 5/5 red.
- **R30+R24**(#1271, Grok `019fbe61`): pre_push_gate 인터프리터 이원 매 실행 인쇄(⚠️ 3.14↔3.12) + backlog 전장 R행 legality 백스톱(역사 창 17행 포함 실측 35행 전수). 🔴 생존 뮤테이션 1건 실측(⚠️-only 단언이 mismatch fallthrough 로 우연 통과) → 분기 고유 문구 단언으로 강화 후 red — "단언은 결과가 아니라 분기 고유 문구를 고정해야 한다".
- 🔴 **R34 신설 — #1263 라이브 반례**: 본문 수정 후 재검증 워크플로가 같은 job 이름으로 success check run 을 냈으나 branch protection 은 BLOCKED 유지(구 failure + 신 success 공존 실측) → 빈 커밋 새 SHA 로 우회. "(SHA,이름) 갱신" 설계 가정이 첫 라이브 사용에서 깨졌다.
- **라이브 실증**: 로컬 pre-push 훅 발화 · R30 드리프트 라인 · lint-js baseline 축 CI 첫 통과. 🔴 doc_review_gate 3 에이전트 세션 내내 전건 호출 실패(8회+) — R33-a 재개방(키 재확인 요청).
- 단위 6552→**6607**(+55) · 통합 171 불변 · 전체 **6778**. 프로세스 자기 결함 2건도 실측 시정: 전체 스위트 파이프라인 tail exit 오독(재실측으로 정정) · 이스케이프 3중 레이어 파일 파손 2회(복구 + chr() 기반 ASCII 소스 전환).

## 5+1 회고 + Grok 6중 협업 + 가드 근본원인 분석 (2026-07-31~08-01 세션13, 19 PR #1248~#1266)

**사용자 지시**: *"Grok과 함께 지속적으로 가드가 수행이 안되는 원인을 분석을 합니다. 문서 내용이 너무 길어서 그럴수 있습니다."*

**가설 판정 — 3/4 렌즈에서 반증.** 결정적 반례: 커밋 `af9c555`(2026-07-21)가 AGENTS.md 에 "substring 금지" 규칙을 **저술하면서 같은 커밋에 그 규칙을 위반하는 술어**를 담았다. 규칙을 쓰는 순간에도 지키지 못했으므로 원인은 "규칙이 멀어서 못 읽었다" 가 아니다. 보강: `tests/unit/scripts/` 파일을 열면 `guards.md` **와** `testing.md` 가 자동 주입되고 불변식 1은 `testing.md` 본문에 인라인이다(hop 0).

**가설이 참이었던 유일한 지점** = 문서 심의 **에이전트의 입력**. 사람/Claude 의 읽기가 아니라 기계 심의자가 길이로 잘려 있었다(아래 #1255).

**지배 원인(Grok 진단)** = *"보호 장치가 무장됐다는 것이 증명되지 않는다"* — (i) 저술 시점: 보호 대상을 도려내도 관측자가 초록 (ii) 실행 시점: 0회 실행이 무음.

| PR | 내용 |
|---|---|
| `#1248`~`#1253` | 배선 substring fail-open(11/12 GREEN→7/7 RED) · 훅 실행 관측 · 메모리 경로 · 동시성 stale-read 2건 · 테스트 수치 ground-truth 축 |
| `#1254` | eslint 설정-메타 오탐(`score-lie`) · pre-commit 미설치 관측면 |
| `#1255` | 🔴 **이 세션이 만든 가드 2종이 스스로 뚫렸다** — `_wiring_shape` 가 `$PY` 를 **이름으로** 신뢰해 `PY=echo; $PY x.py` 통과(실측 True) · liveness 오라클이 마커 문자열을 봐서 `echo` 가 **명령 텍스트를 되돌려주며** 통과. + 심의자 컨텍스트 **이중 절단**(CLAUDE.md 10.8% 도달·정책 0줄, STATE.md 0% 인데 헤더는 포함이라 표기) + 원장 요약 기계 대조(33행 중 5행만 감시받던 것). Grok `019fbaf8` 적발 3건 시정(접미사 경계·죽은 단락평가·last-wins). 뮤테이션 5/5·4/4·5/5 RED |
| `#1257` | 🔴 **그 심의 게이트는 애초에 한 번도 심의한 적이 없었다** — `ANTHROPIC_API_KEY` 부재로 3 에이전트 전부 실패 → veto `warn` → exit 0. **배선·실행·출력 다 하면서 아무것도 심의하지 않는다.** 6206건 스위트가 못 잡은 이유 = `tests/conftest.py:17` 이 **가짜 키를 주입**해 운영 실패 조건을 재현 불가로 만듦. Grok `019fbb2d` 가 내 수정에서 **C1=BROKEN**(선점검↔클라이언트가 `.env` 에서 갈라져 대상 사용자 계층이 더 나빠짐) 적발 → 시정 후 뮤테이션 10/10 RED |
| `#1258` | 🔴 **가드가 로컬에서 실행 불가했다** — `make: command not found`. CLAUDE.md 의 *"로컬 사전 확인은 `make gate`(CI 와 동일 기준)"* 가 **두 겹으로 거짓**(명령 부재 + 있었어도 13 가드 미실행). 같은 가드에 **두 번** 걸린 뒤 `scripts/pre_push_gate.py` 신설 — 자기가 못 보는 축을 매 실행 인쇄. 회귀 가드가 `ci.yml` 파싱 대조로 **저술 중 실제 누락 2건 적발** |

**원장**: R2-b ✅(브랜치 보호 200 + required check + `enforce_admins: true`) · R22·R23 ✅ · R24 부분 이행(그 항목의 "원리적으로 측정 불가" 주장이 **틀렸음**을 실측 정정) · 신규 **R29**(make 부재) **R30**(로컬 3.14 ↔ CI 3.12) **R31**(`check_edit_allowed` 커버리지 0 + stdin fail-open).

| `#1260` | 🔴 **advisory 고지가 Claude 에게 도달한 적이 없었다** — 훅 `print()` 는 공식 계약상 PreToolUse 에서 Claude 컨텍스트가 안 된다. **내 시정안(SessionStart 이관)은 Grok `019fbb65` 가 기각**(세션당 1회 = mid-session stale-green = 지배적 결함 재생산). 정답 = `additionalContext` + `systemMessage`, `permissionDecision` 미설정. **라이브 실증**: 수정 후 첫 편집에 즉시 도착. 뮤테이션 6/6 RED |
| `#1261` | 🔴 **조달되지 않는 분석기가 auto-merge 를 영구 차단**(R21) — 등록 25 중 9종이 조달 흔적 0 → 9개 언어 리포가 손댈 수 없는 사유로 차단. 조달 계약으로 갈라쳐 계약 안 부재만 차단, 밖은 가시화만. 계약↔조달파일 양방향 대조 가드. 뮤테이션 5/5 RED |

| `#1263` | 🔴 **내 제안 3건 중 2건이 Grok 설계 검토(`019fbc8e`)에서 기각** — pre-push yaml 배선(미설치 머신에서 안 도는 가드) · 미조달 9종 제거(정보 소실 + 자체 인프라 사용자 분석 상실). **내가 HIGH 로 매긴 것이 가장 위험했고 LOW 만 실효**. 지은 것 = 본문 편집 시 repo-integrity 재평가(동일 job 이름 + 단일 job — 형제 skip 은 직전 실패 세탁). `#1261` 이 거짓으로 만든 사용자 문구 3 로케일 정정. 뮤테이션 8/8 RED |

| `#1265` | 🔴 **문서 표면 전수 감사** — 101개를 91 에이전트로 정독(167 파일) + Grok 시스템 감사. 확정 53건 중 행동 4 클래스 이행: 게이트 주장 **9지점** drift(내가 `CLAUDE.md` 만 고쳐 키웠다) · `WorkerSessionLocal` 규칙이 **소비자 24 중 3에 미도달** · 완료 계획 **12개**가 "지금 실행하라" 로 읽힘(미체크 359) · 심의 **skip 50→4**. 뮤테이션 7/7 RED |
| `#1266` | **사실 오류 19건** 정정(전부 코드 직접 대조) — 🔴 `API_KEY` *"인증 생략"* → **503 fail-closed**(보안) · *"railway.toml cron"* → `railway.toml` 스스로가 불가하다고 적음 · `commit_sha`(SHA 결속) 누락 · TruffleHog *"이력 전체"* → **diff 범위만** · 등급 임계값 **AST 대조 가드** 신설 |

**수치**: 단위 6040→**6552** · 통합 165→**171** · 전체 **6723**.

**세션 자성**: observer-lie 를 고치는 코드가 observer-lie 를 만든 사례가 **6회**(배선 술어 · liveness 오라클 · 자격증명 선점검 · 고지 채널). 네 번 다 **Grok claim-review 또는 리포 자신의 가드**가 잡았다 — 단독 검증으로는 전부 놓쳤을 것이다. 🔴 그리고 **내가 내놓은 시정안이 기각된 것이 4회**(SessionStart 이관 · 무조건 차단 유지 · pre-push yaml 배선 · 미조달 분석기 제거). 기각이 없었으면 전부 더 나쁜 상태로 머지됐다. 🔴 **판정기 하나를 네 번 고쳤다**(줄 전체 부정어 → 문자 창 → 절 단위 → 열거 문맥) — 두 번은 fail-open, 두 번은 가드 자살이었다. 산문을 기계로 판정하려 할 때 양방향 오류가 얼마나 쉬운지의 기록으로 남긴다.

## 문서 claim-review 정정 + CONTRIBUTING/SECURITY 신설 + 전수 감사 P0 이행 (2026-07-30~31 세션12, 5 PR #1241~#1245)

사용자 요청 = *"Grok과 함께 Readme내용 검토 및 Topic을 등록해주시고, Contributing, Security 내용도 등록"*. Grok claim-review **2회**(README 1차 → 신규 문서 2차) + 전건 `grep` 실측.

**README P0 7건 (전부 실측 확인)**

1. 🔴 **"no data leaves your environment"**([README.md:51](../README.md)) — AI 리뷰가 `api.anthropic.com` 으로 diff 를 보내고([repos.py:221](../src/github_client/repos.py)) 알림 6채널이 외부로 나간다. self-hosted 를 **컨트롤 플레인 한정**으로 재서술.
2~5. 🔴 **CLI Hook 섹션 전체** — 훅은 2025-06-15 Agent SDK 크레딧 분리 대응으로 `claude -p` 를 폐지하고 Anthropic Messages API 를 직접 호출한다([repos.py:201-221](../src/github_client/repos.py), 폐지 사유가 **코드 주석에 명시**). 그런데 README 는 "ANTHROPIC_API_KEY 불필요 · 요구사항 = Claude Code CLI · Codespaces 미동작 · Tech Stack `claude -p`" 4곳을 그대로 유지했다. 사용자 결정 = **코드가 정답, README 정정**.
6. Semgrep **"35+ languages"** → `SUPPORTED_LANGUAGES` 실측 **22**([semgrep.py:23-32](../src/analyzer/io/tools/semgrep.py)). 모듈 docstring 은 "30+" 로 또 다른 값이라 3중 drift.
7. Telegram OTP **"6자리"** → `_OTP_LENGTH = 8`([users.py:33](../src/api/users.py)). 예시 `/connect 123456` 도 8자리로 교체.

**README P1 4건** — `"10 linters"` → `register()` 실측 **25종** · 설정 `"4카드"` → 실측 **6카드**([ui.md:14](../.claude/rules/ui.md)) · REST API 설명에 **fail-closed 503** 명시([auth.py:31-34](../src/api/auth.py)) · "필수 환경변수" 의미 구분(기동 차단은 `DATABASE_URL` + Telegram 2종뿐, [config.py:15-19](../src/config.py)).

🔴 **카드 번호 인용 자체가 drift 원천** — `Card ⑤` 2곳 중 1곳이 이미 오기(Telegram 연결은 ④ "알림 채널(발신)")이고, 템플릿 인라인 주석의 번호(③⑤⑥)와 `ui.md` 번호가 서로 어긋나 있었다. 번호 대신 **UI 라벨**로 치환해 drift 원천 제거.

**신규 문서 4종** — `CONTRIBUTING.md`/`.ko.md`(하이브리드: 외부 기여자 온보딩 본문 + 내부 20개 정책은 링크 위임 = CLAUDE.md 와 이중 SSOT 회피), `SECURITY.md`/`.ko.md`(비공개 신고 · 지원 버전 `main` only · in/out scope · **§"코드가 어디로 가는가"** 전체 egress · 보호 조치 표 · 알려진 트레이드오프 · 배포 하드닝).

🔴 **내가 쓴 신규 문서가 다시 observer-lie 였다 (Grok 2차, 머지 전 적발 P0 4건)**

정책 19 트리거("fail-closed/봉인/유출 0" 주장)에 해당해 초안에 Grok 을 **다시** 걸었다. 4건 전부 **보호 장치를 지워도 문장이 참으로 읽히는** 유형이었다.

- **"bandit·Semgrep 이 매 변경마다 `src/` 에 실행"** — Semgrep 은 **CI job 이 아니다**(`.github/workflows` 전역 grep 0). bandit 만 `lint-src` 에서 실행([ci.yml:183-208](../.github/workflows/ci.yml)).
- **"등록 분석기 25종이 네트워크 호출 없음"** — semgrep 이 그 25종에 포함되는데 **바로 위 표에서 `semgrep.dev` 접근을 자백**해 자기모순. → "나머지 24종" + `golangci-lint`/`clippy` 의 패키지 레지스트리 잔여 경로 명시.
- **"AI 배점 5점 미획득"** — 실측 **11점**(AI 3항목 55점 중 기본값 44점, [constants.py:9-11,23-25](../src/constants.py)).
- 🔴 **"이중언어 주석을 pre-commit 훅이 검사"** — 그 훅은 **2026-07-29 사용자 결정으로 해제**됐다([.pre-commit-config.yaml:129-139](../.pre-commit-config.yaml) 주석 처리). 세션11 이 해제한 것을 세션12 가 살아있다고 다시 적은 셈. **README 2곳에도 동일 오기재**(내가 새로 쓴 표 + 기존 설치 절차)가 있어 함께 정정.

**Grok P1 5건 반영** — egress 표에 **`DATABASE_URL` 누락 추가**(점수·AI 요약·분석기 이슈 메시지가 영속되므로 Supabase 등 외부 DB = 소스 파생 내용의 목적지) · "외부 전송 0" → **"줄이기"**(GitHub + 외부 DB + Go/Rust 레지스트리 잔여) · rate limit "모든 엔드포인트" 축소(admin/users/internal_cron 미적용) · **5-way sync 가드가 실제로는 Python 3-layer 만** 검사(파일명이 "5way" 라 이름 자체가 observer-lie) · 경로 없는 `pytest` 의 e2e 혼입은 `testpaths=tests` 로 **이미 방어됨**(내 서술이 stale).

**저장소 메타** — Topics **14개** 등록(`code-review`·`ai-code-review`·`static-analysis`·`code-quality`·`pull-request-automation`·`github-webhook`·`claude`·`anthropic`·`fastapi`·`python`·`telegram-bot`·`devsecops`·`self-hosted`·`quality-gate`) + Private vulnerability reporting **활성화**(`{"enabled":true}` 실측).

**SSOT drift 1건** — [STATE.md:39](STATE.md) 통합 테스트 추적셀 158 → **165**. 헤더(line 34)·세션 블록(line 19)은 이미 165 였고 셀만 뒤처져 있었다(#1228 의 +7 미반영). `pytest --collect-only -q tests/integration` = 165 실측.

🔴 **이 PC 에 pre-commit 미등록 실측** — `.git/hooks/` 가 **비어 있고** `pre-commit` 모듈 자체가 미설치 = **이 세션 커밋이 로컬 가드를 전부 우회**했다. 세션10 #1224 가 문서화한 "조용한 무보호"의 실사례가 같은 리포에서 재현된 것. 관련 가드는 수동 실행해 통과 확인(`check_docs_sync` ✅ · `check_architecture_tree_sync` ✅ · 시크릿 패턴/공백/EOF/대용량 ✅).

**검증** — `pytest tests/unit` = 6015 passed / 2 failed / 5 skipped. 실패 2건(`test_static_disabled.py`)은 **본 변경 이전부터 존재** — `git stash` 후 clean `main` 에서 동일 재현. 원인은 `pylint`/`flake8`/`bandit` **콘솔 스크립트가 PATH 부재**(`[WinError 2]`, 모듈로는 설치됨 pylint 4.0.6)라 로컬 한정이며 CI 무관. docs-only(`src/` 무변경)라 architecture.md 동기화 대상 없음. 단위 6022·통합 165·전체 6187 불변.

### Grok claim-review 흔적 (정책 19)

세션12 는 정책 19 집행면(`check_claim_review_trace.py`)이 **PR 본문에만** 흔적을 요구하지만, PR 본문은 편집 가능하고 머지 후 추적이 흩어지므로 세션 ID 를 **영구 이력에도** 남긴다.

- session: 019faeb9-b8f3-79c0-ade9-2a9a01883b3c
- claim: README.md 의 배지 수치·능력 카운트·엔드포인트·환경변수·마케팅 문구가 src/ 실제 코드와 일치하는가 (observer-lie 사냥 포함)
- verdict: BROKEN — P0 7건 적발. 전건 grep 재검증 결과 **Grok 오탐 0**.

- session: 019faed8-e4b4-7b11-8cc2-335982208fa0
- claim: 본 세션이 새로 쓴 SECURITY.md egress 목록·보호 조치 표와 CONTRIBUTING.md 프로세스 서술이 실제 코드·CI·pre-commit 설정과 일치하는가
- verdict: BROKEN — 자기 산출물에서 P0 4건 적발, 머지 전 전건 수정.

🔴 **집행면이 본 PR 을 실제로 잡았다** — 1차 push 에서 `Repo integrity guards` job 이 **fail**. 사유 = 본문의 `fail-closed`·`봉인` 어휘(기존 동작 서술/인용)에 대해 구조화된 흔적이 없었음. **면제 마커로 빠져나가지 않고** 실제 흔적을 기재해 통과시켰다. 세션11 이 만든 가드가 세션12 를 잡은 것 = 집행면이 저자와 무관하게 작동한다는 첫 실증.

---

### 후반부 — 전수 감사 + P0 이행 (#1243·#1244·#1245)

사용자 요청 = *"Claude와 Grok 전체 코드와 전체 문서를 확인하고 … 서비스의 품질과 은닉성 버그 그리고 사용 편의성"*. Claude 8-관점 워크플로(44 에이전트, 확정 30 / 반증 5) + Grok 독립 적대 감사 병렬.

**🔴 최우선 결함은 코드가 아니라 "가드가 전부 죽어 있음" 이었다 (#1243)**

`.claude/settings.json` 이 bare `python` 을 호출하는데 Windows 에서 그건 Microsoft Store 스텁이라 **exit 49** — 훅 6종이 한 번도 실행된 적이 없다. `block_credential_dump` 는 크리덴셜 덤프를 **0회 차단**했고 `check_edit_allowed` 의 수정 금지 파일 보호도 발화한 적이 없다. `.git/hooks/` 도 비어 있어(pre-commit 미설치) **로컬 보호 2계층이 동시에 내려간 상태**였다. `settings.json` 은 git 추적 대상이라 `py -3` 하드코딩은 타 플랫폼을 깨므로 셸 폴백(`command -v py … || python3`)을 썼다.

**훅이 살아나자 곧바로 다음 결함이 드러났다** — `doc_review_gate.py` 가 cp949 에서 `UnicodeEncodeError` 로 즉사(`ensure_ascii=False` + 한글 원문 출력). 🔴 근본은 인스턴스가 아니라 **가드의 사각**: [`guards.md`](../.claude/rules/guards.md)가 *"stdout UTF-8 가드 의무 … 전 스크립트 강제"* 라 적고 회귀 가드까지 뒀는데, `test_stdout_encoding_guard.py` 는 `scripts/*.py` 만 glob 하고 `.claude/hooks/` 는 범위 밖이었다 — 그 docstring 은 **"면제 없음 — 탐지 사각이 사고의 원인이었다"** 라고 적혀 있었다. 스코프를 넓히자 **위반 2건이 추가로 드러났다**.

**🔴 CLI 훅이 정적분석 0회로 45/45 만점을 받아 auto-merge 에 도달했다 (#1243 → #1244)**

`hook.py:259` 는 `calculate_score([], ...)` 를 부르고 주석이 스스로 *"CLI 훅은 정적 분석 없음 → code_quality=25, security=20 만점"* 이라 적어 뒀다. 더 나쁜 건 **테스트가 그 결함을 정상 동작으로 고정**하고 있었다는 것 — `test_run_gate_check_cli_hook_success_allows_automerge` 가 `assert_awaited_once()` 로 "success 면 머지된다" 를 봉인했고, 같은 파일 docstring 은 *"static_analysis_incomplete 가드는 CLI 훅이 정적분석을 안 돌려 incomplete=False 라 **무력**"* 이라고 **갭을 정확히 서술해 두고도 닫지 않았다**.

#1243 이 마커로 무검증 머지를 막았으나 부작용으로 semi-auto 승인 버튼까지 막혔다(사람 판단 창구 상실). #1244 가 근본 해결 — dedup 이 CLI 행을 **중복으로 보지 않게** 하고 full 분석이 그 행을 **제자리 교체**(row id 유지로 FK 보존). 즉 **CLI 훅이 실제 분석을 가리고 있었다**.

**분석기 커버리지 2단 봉인 (#1244 · #1245)**

| 상황 | 처리 | 근거 |
|---|---|---|
| 바이너리 부재로 **실행 0개** | incomplete 차단 | 조달로 고칠 수 있음. `.scss`+`.ps1`+`.dart`+`.proto` PR → **89(B)** 실측 재현 |
| 지원 분석기가 **애초에 0개**(21개 언어) | **차단 없이 가시화만** | lua·perl·haskell·r·julia·zig 등. 차단 시 해당 언어 리포 auto-merge **영구 불가**(사용자 결정) |

🔴 비대칭이 핵심이었다 — 도구가 *크래시*하면 incomplete 로 승격돼 머지가 막히는데, *부재*하면 조용히 통과했다. 둘 다 "이슈 0건" 인데 신뢰도 취급이 정반대였다.

**Grok 협업 — 자기 산출물에서 P0 를 반복 적발**

매 PR claim-review(5회). 🔴 **Claude 가 방금 쓴 것에서 P0 가 계속 나왔다**: SECURITY/CONTRIBUTING 초안 4건(Semgrep CI job 부재 · 25 vs 24 자기모순 · AI 미획득 5 vs 11점 · **해제된 훅을 살아있다고 서술**) · supersede 동시성 **이중 gate/notify**(기존 race 억제 신호를 교체 분기가 우회) · `is_enabled` 의미 혼동 과차단 · **21개 언어 홀**(내가 "R 하나" 로 축소 보고한 것을 전수로 정정). 전건 머지 전 수정.

**자기 정정 2건** — (1) `test_migration_completeness` 가 없다고 판단해 템플릿 줄을 지우려 했으나 **틀렸다**(내 grep 이 파일 *내용*만 재귀 검색해 파일명을 놓침. 교훈: 부재 증명에 내용 grep 금지, `find`/`git ls-files` 사용). (2) 뮤테이션 검증 1회가 `IndentationError` 를 냈는데 그건 **구문 오류로 인한 가짜 red** 라 판별 근거가 못 된다 — 조건 무력화(`if False and …`) + `ast.parse` 확인으로 재수행.

**검증** — 단위 6022→**6040**(+18) · 통합 165 불변 · 전체 **6205** · pylint **10.00 복원**(9.99 재drift 는 2026-07-19 이후 2번째이고, CI 게이트가 9.90 이라 **CI 는 이 drift 를 영영 못 잡는다**) · bandit exit 0 · CI 12/12 × 5 PR. 저장소 메타: Topics 14 + description 영문화 + Private vulnerability reporting 활성화(`{"enabled":true}` 실측).

**미해결(다음 세션)** — RLS 멀티테넌트 격리 실효성은 **쿼리를 실행할 수 없어 미판정**(감사 최대 미검증 영역, 코드가 "BYPASSRLS 면 RLS 미평가" 를 자인하고 실측 함수까지 둠). `models`·`railway_client`·`config_manager` 패키지는 **미조사**(= clean 아님).

---

### PR #1242 — PR 템플릿 실측 정정 + 정책 19 슬롯 + pylint 10.00 복원 + description 영문화

사용자 위임 2건("네 처리 부탁드립니다") = description 갱신 + PR 템플릿 `make lint` 오기재 수정. 템플릿은 **한 줄 문제가 아니었다** — 36 에이전트 워크플로(5 관점 finder → 적대 verify → completeness critic, 21 confirmed / 9 refuted)로 전 항목을 Makefile·CI·소스와 대조.

**실행 불가하거나 죽은 지시 4건**

1. 🔴 `make lint` 통과 (pylint 10.00 · bandit HIGH 0) — [Makefile:78-81](../Makefile)이 세 린터를 `|| true` 로 삼켜 **구조적으로 exit 0**. 체크박스가 반증 불가라 아무것도 증명하지 못한다. 단순 부정확이 아니라 **[CLAUDE.md:342](../CLAUDE.md)와 CONTRIBUTING 양 언어가 "근거로 쓰지 말라"고 명시한 것을 템플릿만 정면 요구**하고 있었다(회고 D13 이 템플릿 면에서 생존).
2. `pylint 10.00` — CI 강제 수치는 [ci.yml:203](../.github/workflows/ci.yml) `--fail-under=9.90`. 10.00 은 관측값이지 게이트가 아니라, 관측값이 흔들릴 때마다 템플릿이 **가짜 차단**을 만든다.
3. `make migrate` 왕복 검증 (`downgrade -1` → `upgrade head`) — [Makefile:126-127](../Makefile) `migrate:` 는 `alembic upgrade head` 2줄뿐이고 Makefile 전체에 `downgrade` **0건**. 명령을 실행해도 왕복이 안 되는 **실행 불가 지시**.
4. `docs/STATE.md 그룹 이력에 신규 파일 표 추가` — STATE.md 헤딩은 3개(현재 수치/주요 파일 역할/작업 이력)뿐. **그런 섹션이 없다.**

**정책 19 슬롯 신설 (유일한 순증)** — [ci.yml:161-168](../.github/workflows/ci.yml)이 매 PR 에 claim-review 흔적을 요구하는데 템플릿에 자리가 없어 **직전 #1241 이 실제 red**(자초). 🔴 **공허 통과 방지 실증**: 예시값이 가드 정규식을 만족하면 *모든* PR 이 가드를 무력화하므로 3 시나리오 실행 검증 — (a) 일반+미기입 exit 0 · (b) **seal+미기입 exit 1** · (c) seal+기입 exit 0. placeholder 를 `<...>` 로 감싸 hex 형식·닫힌 열거형·16자 하한을 전부 빗나가게 했다. Grok(019fb01f) 독립 재현 = **SURVIVES**, 추가로 `find_seal_claims(template)==[]`(템플릿 자체에 seal 어휘 0 = repo 전체 오발화 없음) 확인. 순 결과 62 → 74줄이나 **렌더 본문은 축소**(체크박스 13 → 12, 증가분 전부 주석).

**pylint 10.00 재drift → 복원 (사용자 결정)** — 실측 **9.99**. [STATE.md:46](STATE.md) 기록상 2026-07-19 D3 로 복원한 뒤 **두 번째** 재발이고, **CI 게이트가 9.90 이라 CI 는 이 drift 를 영영 못 잡는다**(관측값을 아무도 단언하지 않는 구조). 감점 6건 전부 C0103 invalid-name, 대상은 모듈 레벨 **가변** 상태 — `SessionLocal`/`WorkerSessionLocal`(세션 팩토리 인스턴스)·`_fernet`(지연 인스턴스)·streak 2종(가변 카운터)·`_client`(지연 싱글톤 슬롯). pylint 가 상수로 오분류한 것이라 UPPER_CASE 개명은 **의미상 틀리고** `SessionLocal` 은 16개 모듈이 쓴다 → inline `# pylint: disable=invalid-name` 6줄 + 사유 이중언어 주석(맥락 없던 2곳). 동작 변경 0. Grok 이 6건 각각 "naming bug 를 덮은 것이 아님" 확인.

**Grok P2 2건 반영** — (1) 템플릿 `CI lint-src 와 동일 기준` → `린터 기준은 CI lint-src 와 동일`(`lint-src` 는 pylint+bandit 만, 테스트는 별도 job) (2) [ci.yml:171](../.github/workflows/ci.yml) stale 주석이 "`make lint`/`make gate` 는 전부 `|| true` 로 삼켜 실패할 수 없고"를 **현재형**으로 서술 — `make gate`([Makefile:115-118](../Makefile))에는 `|| true` 가 없다. 이 주석을 읽으면 방금 템플릿·CONTRIBUTING 에 넣은 `make gate` 권고가 무의미하다고 결론내게 된다. 당시 문제 서술은 history 보존하고 도입 사실만 덧붙임.

🔴 **자기 정정 (본 세션 2번째)** — "`test_migration_completeness` 가 존재하지 않는다"고 판단해 해당 줄을 **삭제하려 했으나 틀렸다**. 내 grep 이 파일 *내용*만 재귀 검색해 파일명을 놓쳤고, 실제로는 `tests/unit/test_migration_completeness.py` 가 git 추적 + 테스트 2건(`:104`, `:141`)을 가진다. 워크플로 검증자가 잡아냈고 원문 보존. **교훈: 부재 증명에 내용 grep 을 쓰지 말 것 — `find`/`git ls-files` 로 파일명을 직접 확인.**

**의도적 DROP** — 워크플로 확정 21건 중 ORM 3건·env-vars 신설 등은 **이미 CI fail-closed**(`test_alembic_env_model_completeness`·`check_env_vars_sync`)라 체크박스 중복 = theater 이고, 전건 적용 시 62 → ~100줄(+60%). **읽히지 않는 템플릿은 조금 틀린 템플릿보다 나쁘다**는 기준으로 잘랐다. 최강 재고 후보 = 정책 13/14 슬롯(둘 다 CLAUDE.md:228,234 가 PR 본문 의무로 명시하나 ~14줄 증가라 보류 → 사용자 판단 요청).

**검증** — pylint **10.00/10**(`--fail-under=10.0` 도 exit 0) · bandit exit 0 · flake8 15(E501 baseline 불변) · `pytest tests/unit` **6017 passed / 5 skipped / 0 failed** · 가드 6종 ✅ · ci.yml YAML 파싱 정상(job 8). 🔴 **#1241 의 "선재 실패 2건" 원인 확정** = `pylint`/`flake8`/`bandit` 콘솔 스크립트 PATH 부재(`Scripts/` 추가 시 3건 전부 통과). 리포 결함 아님·CI 무관.

---

## GitHub Issue 2건 처리 + 정책 19 집행면 + Grok 전반 검토 (2026-07-29~30 세션11, 9 PR #1228~#1237)

열린 GitHub Issue 2건(#1226·#1227)을 Grok claim-review 와 함께 처리하고, 그 과정에서 **정책 19 위반이 재발**해 집행면을 신설했다.

**#1226 — 런타임 eslint 분석기 100% 무동작 (→ #1228)**: JS/TS 이슈가 항상 0 이라 감점 0 → 점수 인플레가 점수 기반 Gate(auto-approve/auto-merge)까지 전파. 이슈는 결함 2건(설정 경로 `..` 개수 · `--no-eslintrc` eslint 9 무효)을 보고했으나 **실측 5건**이었고 각각 단독으로 분석기를 죽인다. 🔴 **이슈가 처방한 수정만 적용하면 여전히 무동작** — 신규 3건: (3) `.json` 설정을 eslint 9+ flat-config 로더가 **ESM import** 하므로 `ERR_IMPORT_ATTRIBUTE_MISSING` (4) `files` glob 부재로 .jsx/.ts/.tsx 미매칭 (5) **cwd 미지정 → 임시파일이 base path 밖**(`tempfile.TemporaryDirectory()` vs 앱 cwd, eslint 9·10 공통). 결함 4·5 는 침묵보다 나쁘다 — 1~3 만 고치면 가짜 `File ignored` 경고가 **없는 결함으로 점수를 깎는다**. 조치 = 경로·플래그(`--no-config-lookup`)·`.mjs` 이식·`files` glob 6확장자·`@typescript-eslint/parser` 결선·cwd 지정 + **fail-open→fail-closed**(비-JSON stdout / ruleId=None 비-fatal 메타 메시지 → `RuntimeError` → `static.py` 가 `incomplete` 승격, #805/#806 대칭. 타임아웃·바이너리 부재는 의도적 미수행이라 `[]` 유지).

🔴 **관측자가 결함을 요구하고 있었다**: 단위 40건이 `subprocess.run` 을 전부 mock 해 "경로 문자열이 argv 에 들어갔는지" 만 보았고, 2건은 결함 자체를 단언했다 — `test_run_includes_no_eslintrc_flag`(운영 eslint 9 를 죽이는 플래그 요구) · `test_run_returns_empty_list_when_stdout_not_starts_with_bracket`(입력이 eslint 9 **실제 출력**인데 `[]` 단언 = 운영 무동작을 정상으로 인증). 반전 + 실바이너리 통합 테스트 신설(mock 이 결함 1·3·4·5 를 원리적으로 못 잡음).

**#1227 — lint-js 공허화 차단 (→ #1229)**: `make lint-js` 가 `npx eslint … || true` 라 모든 실패를 삼켰고 **어떤 CI workflow 에도 배선돼 있지 않았다**(`.github/` 전역 참조 0). settings.html 은 `<script>` 내 Jinja 보간 **17개(전 템플릿 최다)**인데 무시 목록 밖 = 유일 누락(파서 한계이지 JS 결함 아님). 사용자 결정 = **위반은 advisory, 공허화만 fail-closed**. semgrep 보류는 dependabot ignore 로 명시하되 silent-disable 방지를 위해 backlog H3 에 (기전·반증수단) 등재.

🔴 **내가 만든 가드가 그 자체로 observer-lie 였다**: 초판은 `eslint.config.mjs` 를 정규식 파싱해 커버리지를 추론했고, Grok claim-review 가 그 "봉인/양방향 강제" 주장을 **BROKEN** 판정 — 손실 있는 투영이라 (a) 두 번째 config 객체의 `ignores` (b) 작은따옴표 항목 (c) `files:` 축소 (d) 중첩 디렉토리 템플릿 4종이 전부 통과했다. 봉인 근거를 **eslint 실제 린트 결과 역산**(`실제_무시집합 = 디스크 전체(재귀) − 실제 린트된 파일`)으로 교체하니 설정 문법을 어떻게 바꾸든 린트 결과가 달라져 4종 전부 red(실파일 재현 검증).

**정책 19 집행면 신설 (→ #1230, backlog R2)**: 세션 초반 claim-review 1회를 "이행함" 으로 자기 처리한 뒤, 정작 자기가 만든 가드를 seal 주장으로 PR 2건 냈다. 🔴 **원인은 문서량이 아니다** — 트리거 단어를 **자기가 타이핑하고도** 호출하지 않았고(정책 19 는 always-loaded 문서에 3중 중복), Grok 이 문서량 가설을 명시 기각(원인 순위: 집행면 0 > 자기보고 준수 > one-shot 편향 > 마커 인플레[🔴 198개] > 문서량). 정책 8·owed 원장이 이미 밟은 산문→훅 승격 경로를 정책 19 에 적용. **자기 적용 검증 = 이번 세션 PR #1228·#1229 양쪽 차단**. 초판 역시 Grok 이 BROKEN 판정(빈 필드 3줄 통과·`not-required: x` 한 글자 자기면제·어휘 우회·shallow clone 으로 커밋 축 사멸) → 값 요구·본문 한정 면제·어휘 확대·`fetch-depth: 0` 반영. 🔴 **자기 적용에서 결함 1건 추가 발견** — 마커를 **설명하는 문장**이 면제로 오인돼 가드를 문서화하는 PR 이 스스로 면제됐다(seal 13건 통과 실측) → 줄 맨앞·비-백틱 앵커.

🔴 **머지 차단력은 아직 없다 (R2-b)**: ruleset `PRIMARY` 는 active 지만 규칙이 `deletion`·`non_fast_forward`·`pull_request` 뿐이고 **required_status_checks 0건** — red CI 로도 머지된다(실측: #1196 이 `Analyze (python)` FAILURE 상태로 머지). 🔴 그렇다고 지금 required 를 켜면 **score-based auto-merge 가 깨진다**: CI pending 중 `mergeable_state=blocked` → `BRANCH_PROTECTION_BLOCKED` 이고 이 태그는 `_RETRIABLE_TAGS`(`merge_reasons.py:60` = `{UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT}`)에 **없어 즉시 terminal**. 과거 브랜치 보호 거부(B6-a)와는 문제가 달라 충돌하지 않으나, **코드 선행 수정(blocked+pending 을 retriable 로) 후 설정** 순서가 강제된다.

**환경**: 이 PC 에 **Python 부재**(WindowsApps 스텁만)라 3.12 설치 후 진행 — 새 PC 이식 실측. Windows 는 `npx`/`eslint`/pylint 등이 `.cmd` 래퍼라 `CreateProcess` 불가(`WinError 2`)여서 가드는 `node <eslint.js>` 직접 호출로 작성.

**세션 후반 — 가드가 실전에서 즉시 작동했다**: 앞서 만든 두 가드가 같은 세션 안에서 실제 회귀를 잡았다. (a) 공허화 차단이 dependabot **#1232**(typescript 5.9.3→7.0.2)를 red 로 적발 — `@typescript-eslint/parser` peer 가 `>=4.8.4 <6.1.0` 이라 `npm ci` 가 **ERESOLVE 로 실패**하고, 그 파서는 eslint 분석기가 `.ts/.tsx` 를 파싱하는 수단이라 머지되면 **#1226 무동작으로 회귀**했을 것이다. 구판(`|| true`)이었다면 조용히 초록이었다 → **#1235** 로 `typescript >=6.1.0` ignore + backlog H4(해제 조건·반증 수단). dependabot 이 #1232 를 자동 종결. (b) 정책 19 게이트는 **#1234** 에서 CI 실행 성공(면제 마커 인식, 오탐 0) — 첫 실사용.

**Grok 전반 검토 (서비스 품질 관점)**: 사용자 요청으로 규칙·가드 체계 전반을 claim-review. 진단 = *"이 시스템은 Claude 가 봉인에 대해 거짓말하는 것을 막는 데 최적화돼 있고, 사용자가 인플레된 점수와 죽은 도구를 받는 것을 막는 데는 덜 최적화돼 있다"* — 오늘 발견(eslint 몇 달 무동작 + 테스트 40건 green)이 그 증거. 실측 규모: check 스크립트 16 · 훅 4 · pre-commit 17 · CI job 10 · 가드 테스트 42파일 · 규칙 문서 255KB · 🔴 마커 198개. 사용자 선택 3건 반영(**#1237**):
- 🔴 **`doc_review_gate` 심의 스코프 복구(R9)** — 2026-07-21 문서 재구성 이후 `AGENTS.md`(3-불변식 SSOT)·`.claude/rules/*.md`(154KB, 편집 표면 자동 로드)·`.claude/policies/*.md` 가 **전부 `skip`** 이었다. 심의 게이트가 정작 심의해야 할 표면을 통과시키는 false coverage. 실증: 이 세션이 `pipeline.md` 를 고쳤는데 미발화. → critical/important 복구 + **디스크 스캔** 회귀 가드(하드코딩 목록 대조는 신규 파일을 영영 못 잡는다), 뮤테이션 4/4 red.
- **E2E 배지 정직화(R7)** — `.github/workflows` 에 e2e 실행 0건인데 공개 리포에 초록 `122 passing` 배지. 커버리지는 그대로 두고 **주장만 사실과 맞췄다**(회색 `local only`).
- **bilingual 주석 훅 해제**(사용자 결정) — 커밋을 막는 유일한 *스타일* 규칙이었고 사고 인용이 없었다. 차단만 해제, CLAUDE.md 원칙·스크립트는 유지. 🔴 훅을 떼자 `test_guard_wiring_coverage` 가 "배선 안 된 가드" 로 red — 의도된 dead-wiring 탐지라 `_ADVISORY_ALLOWLIST` 에 **사유와 함께** 등재해 "그냥 안 배선" 과 구별.

**dependabot 3건 검증 워크플로** (12 에이전트 · 1.22M 토큰 · 적대 반증 3렌즈×3): #1236(typescript 6.0.3)·#1233(production-deps 5)·#1231(trufflehog) 전부 **SAFE**(반증 0/9) 판정 후 머지. #1236 은 격리 worktree 에서 `npm ci`·`npm install`·lock-free 3경로 실측 — semver 확인 결과 `6.0.3=true / 6.1.0=false / 7.0.2=false` 로 **ignore 경계 `>=6.1.0` 이 정확**했다(잔여 헤드룸 0 — 이후 6.0.x 패치뿐). **부수 발견 2건을 이슈로 승격**:
- **#1238** `tsc` 분석기가 typescript 핀 **밖**에 있다 — `railway.toml:3` 이 `npm install -g typescript` 로 **무핀 전역 설치**하고 `tsc.py:49` 가 `shutil.which("tsc")` 로 그것을 집는다. 즉 "typescript 를 <6.1.0 으로 봉인" 은 **eslint 파싱 축에만 참**이고 운영 tsc 는 7.x 로 drift 해 있을 수 있다 — **#1226 과 동일 클래스**(설치 실패는 `|| echo WARNING` 이 흡수, `is_enabled` 는 which 만 봄).
- **#1239** trufflehog SHA 핀이 **스캐너를 핀하지 않는다** — action `version` 기본값이 `latest` 라 실제 바이너리는 `ghcr.io/...:latest` 가변 태그(CI 로그 실증). 게다가 SHA 옆 주석이 `v3.95.7` 인데 실제는 v3.96.0 로 **3버전 drift**, 주석에 한국어 설명이 붙어 dependabot 재작성 휴리스틱이 안 먹는 것까지 확인 → 앞으로도 자동으로 벌어진다.

backlog **R13~R15** 추가(slither 실바이너리 테스트 0건 · `_PIP_DISTRIBUTION` 문자열-존재 가드 · fastapi 문서 drift).

🔴 **미결 — 브랜치 보호(R2-b)**: ruleset `PRIMARY` 는 active 지만 규칙이 `deletion`·`non_fast_forward`·`pull_request` 뿐이고 **required_status_checks 0건** → red CI 로도 머지된다(**#1196 이 `Analyze (python)` FAILURE 로 머지**된 실측). 그런데 지금 required 를 켜면 CI pending 중 `mergeable_state=blocked` → `BRANCH_PROTECTION_BLOCKED` 가 `_RETRIABLE_TAGS`(`merge_reasons.py:60`)에 없어 **즉시 terminal** → score-based auto-merge 파손. 과거 브랜치 보호 거부(B6-a)와는 문제가 다르나 **코드 선행 수정 후 설정** 순서가 강제된다. 사용자 결정 = **다음 세션 전용 진행**.

**수치**: 단위 5968→**6022**(+54) · 통합 158→**165**(+7) · 전체 **6187** 수집. 뮤테이션 실증 = eslint 10/10 · lint-js 가드 10/10 · 정책 19 가드 10/10(각 회차마다 약점 1~2건이 뮤테이션으로 드러나 테스트 보강).

---

## 다른 PC 이식 준비 + 새 clone 경로 복구 + git 정리 (2026-07-27 세션10, 3 PR #1223~#1225)

사용자 요청 = *"다른PC에서 동일하게 작업할수 있게 Github에 올려주시고 Git 정리해주세요"*. **올릴 것은 이미 없었다** — 미푸시 커밋 0·미커밋 변경 0·스태시 0이고 로컬 브랜치 3개는 전부 #1218~#1220 으로 머지된 상태(로컬 main 만 2 커밋 behind)였다. 그래서 실제 작업은 두 갈래로 갈렸다: (1) git 표면 정리, (2) **"다른 PC 에서 동일하게" 가 정말 성립하는지 문서 절차를 실측 검증**. 후자에서 세 건이 나왔고 셋 다 **실패가 아니라 침묵**으로 어긋나는 형태였다.

**git 정리**: 머지 판정은 `git cherry`/`--merged` 를 쓰지 않고(squash 전량 오탐 — 세션9 학습) **PR `state=MERGED` + 로컬 tip↔`headRefOid` + merge commit 의 `origin/main` 조상성** 3종으로 확정한 뒤 삭제(삭제 전 tip SHA 복구 매니페스트 저장). 최종 상태 = 로컬 `main` 단독·원격 `main` + dependabot 2(#1221 eslint·#1222 production-deps 는 의존성 결정이라 미머지로 남김)·워크트리 1·스태시 0.

🔴 **문서대로 하면 새 PC 는 첫 명령부터 실패했다** (#1224). `README.md:333`·`README.ko.md:392` 의 clone URL 이 `github.com/xzawed31/SCAManager` 인데 `gh api repos/xzawed31/SCAManager` = **404**(실제는 `xzawed/`). 같은 문서 상단 CI/CodeQL 배지는 `xzawed` 로 **올바르다** — 즉 문서 내부에서 이미 자기모순이었고 `git grep` 전수로 이 2줄만 어긋나 있었다. 배지는 렌더되므로 눈에 띄지만 clone 라인은 **새 PC 를 세팅할 때만 실행**되는 경로라 오래 살아남았다.

🔴 **gitignore 산출물을 템플릿이 링크한다** (#1224). `src/static/css/dist/tailwind.css` 는 빌드 산출물(gitignore)인데 `src/templates/base.html:31` 이 이를 링크한다. 그런데 설치 절차에는 `pip install` 만 있어(`make install` 은 pip+npm, CSS 빌드는 별도 `make css-build`) **새 clone 은 그 경로가 404 인 상태로 서버가 뜬다**. 가설이 아니라 **본 PC 에서도 파일이 없었다**(`Test-Path` False) — `make css-build` 로 12,196 bytes 생성 + `git status` 무시까지 실측 확인. `make css-build` 는 "Development Commands" 표에는 있었으나 **설치 절차를 순서대로 따라가는 경로에서는 도달하지 않는다**는 것이 함정의 본질.

🔴 **pre-commit 미등록 = 조용한 무보호** (#1224 fix-up). `.pre-commit-config.yaml` 의 로컬 가드(시크릿 스캔·docs 수치 정합·architecture 트리 싱크·이중언어·config 5-way)는 전부 pre-commit 경유인데 등록 단계가 설치 절차 밖(`docs/runbooks/secret-prevention.md` 한 곳)에 있었다 → 새 PC 는 **가드 0 상태로 커밋이 계속 성공**한다. `check-commit-msg-secrets` 가 `stages: [commit-msg]` 이고 config 에 `default_install_hook_types` 선언이 없어 `--hook-type` **2종 명시**가 필요하다는 점까지 실측 반영. 의존성 핀 추가(`requirements-dev.txt`)는 **하지 않았다** — `ci.yml:111~115` 가 "pre-commit 우회·미설치 시에도 서버측 강제"를 명시한 설계 판단이라 의존성 표면 변경은 사용자 결정으로 남기고 옵션 표만 제시.

**stale 커버리지 산출물 5건 untrack** (#1223). 2026-04-19(`0ca71ef`) 이후 갱신되지 않은 `coverage.json`(162KB)·`cov_db*/cov_ui*` 가 추적돼 있었고, `scripts/parse_coverage.py:24` 가 cwd 의 `coverage.json` 을 그대로 읽는다 → 재생성 없이 실행하면 **3개월 전 수치를 실패 없이 보고**한다. untrack + gitignore 봉인(사유 주석 동반)으로 이제 같은 실행이 시끄럽게 실패한다. **새 런북** `docs/runbooks/new-machine-setup.md`(#1225) = 리포가 실어 주지 않는 자산(`.env` 값·에이전트 메모리·MCP 사용자 스코프 설정·`gh` `workflow` scope)과 기계 검증 체크리스트. 🔴 **에이전트 메모리는 public 리포에 등재하지 않는다**(보안 발견·내부 운영 서사 포함, 공개는 비가역) — 수동 복사 또는 private 동기화 두 안만 제시. 테스트 무변경(단위 5968 불변), Code Scanning open 0.

## GitHub 정리 + owed #1072 외부계약 반증 + 5+1 회고 (2026-07-26 세션9, 3 PR #1217~#1219)

사용자 요청 = "Github 정리" 단독으로 시작. **원격 표면은 이미 깨끗**했고(열린 PR·이슈·Code Scanning·Dependabot 전부 0) 실제 대상은 잔존 브랜치·워크트리·캐시였다 — 원격 4 + 로컬 45 브랜치 삭제, 워크트리 10 제거(`.grok-build` 180MB→40K, `Temp/pc1` 19MB), Actions 캐시 5.55→**1.08 GiB**. 🔴 **판정 방법을 도중에 바꿨다**: `git cherry`·reverse-apply·`--merged` 가 squash 머지에서 **전량 오탐**(`fix/guard-detector-defects` 5커밋 전부 "미반영" 오판인데 실제 #1096 머지 완료)이라 근거에서 배제하고 **PR `state=MERGED` + tip↔`headRefOid` 대조 + 파일 내용 diff** 만 근거로 삼았다. 유일한 실제 유실 위험(`fix/p1-cluster-a-doc-shape` — 커밋 메시지가 "GitHub 500 이후 PR 이 반영 못함"을 명시)은 바이트 동일 확인 후 삭제. 삭제 전 전 브랜치 tip SHA 복구 매니페스트 저장. **#1217** = 카덴스 이월 승인 기록 의무(정책 8 진화 (6)) 이행 중 **원장 가드가 자기 파일의 정상 산출물에 red** 를 내는 것을 발견 — `deferral_records(...) == []` 로 **시점 의존 상태를 불변식에 고정**하고 있었다(append-only 원장에 정당한 첫 행을 넣는 순간 CI red). 보호 범위를 축소가 아니라 **확대**해 교체(목표 진입 세션 검증 신설 + 주석 예시 행 뮤테이션 대조군).

🔴 **owed #1072 = ❌ 전제 반증** (#1218). 원장이 지정한 검증 방법("운영 로그에서 422 관측")은 **결론을 낼 수 없는 레시피**였다 — 이 계정은 PR 작성자와 토큰이 동일(`xzawed`)해 APPROVE 가 self-approval 로도 422 를 내므로 두 원인이 구분 불가. webhook 없는 private 스크래치 리포로 외부 계약을 직접 프로빙: **구 SHA → 200**(거부 안 함, 리뷰가 그 SHA 로 기록) · **force-push 로 PR 에서 사라진 SHA → 200** · **존재하지 않는 SHA → 422** `The commitOID is not part of the pull request` · `APPROVE` + 없는 SHA → commitOID 오류가 **self-approval 오류보다 먼저**. 즉 GitHub 의 `commit_id` 검증 기준은 "head 인가"도 "PR 에 포함됐는가"도 아니라 **"저장소에 오브젝트가 존재하는가"** 뿐 — 분석된 SHA 는 정의상 존재하므로 이 가드는 **원리적으로 발화 불가**였고 운영 auto-approve **104 건 중 차단 0**(DB 실측, 99 건이 dependabot PR). 🔴 **형제 대조가 근본을 드러냈다**: `merge_pr(expected_sha=)` 는 틀린 sha 에 **409 `Head branch was modified` + 머지 차단**으로 계약이 **성립**한다 — merge 형제가 실제로 작동하니 approve 도 대칭이라 **가정**했고 그 가정은 테스트된 적이 없었다. 조치 = 결속을 **우리 코드**가 강제(`post_github_review` 가 POST 전 head 조회 → 불일치 시 `HeadMovedError`, POST 안 함) + 422 를 'head 이동'으로 단정하던 로그 정정. 잔여 한계(정직) = GET→POST 레이스, 리뷰 API 에 서버측 원자성 수단 **부재 실측 확인**.

**5+1 회고** (run `wf_47083cad-e71`): **197 에이전트**(0 error·0 skipped)·20.23M 토큰·3589 tool calls·확정 **161**(P0 2·P1 59·P2 100)·verdict_coverage **1.0**·FP **12** 차단·severity_adjust 53. 지배 주제 = 세션이 스스로 명명한 **"옳은 일을 하면 빨개지는 가드"** 의 **쌍대 발견** — owed 원장이 42 PR 동안 **0행 등재**이고 훅은 빈 원장을 "미결 0건" green 으로 읽는다(**부채를 등재하지 않는 것이 가장 싼 통과 경로**, P0-2). 2번째 주제 = **관측면이 자기 입력에 눈이 멂**(카덴스 기계의 입력인 회고 보고서 파일이 인간 기억에만 의존 — 워크플로는 보고서를 쓰지 않는다). **P0-1 봉인**(#1219) = credential 덤프 차단 훅이 복합 명령에서 fail-open(안전 세그먼트 1개가 명령 전체를 화이트리스트, 실측 우회 4종) → 세그먼트 단위 fail-closed. 🔴 회고 권장 정규식 `[;&|]{1,2}` 는 **파이프까지 분해**해 훅 자신의 안전 관용구를 차단하므로 **미채택** — 파이프라인은 하류 필터가 상류 덤프를 실제로 중화하지만 `;`/`&&` 는 그렇지 않다는 비대칭이 분해 경계의 근거. 회고가 **내 자기 산출물에서 P1 3건**을 적발(반증된 422 주장이 **내가 고친 파일 14줄 위**에 잔존 — 정책 16 grep 전수 미이행 · telegram 주석 근거 과장 · owed `#1072` 마커 ✅↔본문 ❌ 자기모순). 🔴 **2026-07-24 회고 보고서 미아카이브 확정(복구 불가)** — 회고는 수행됐으나 보고서 미생성 + journal 부재로, 카덴스가 2.1배 오보(42 PR 발화, 실제 갭 ~20)해 **본 회고가 22 PR 을 중복 재검토**했다. 미아카이브 3회차.

## 종합감사 이행 + 5+1 회고 + 회고 P1 (2026-07-24 세션8, 8 PR #1194~#1201)

종합감사(#1186~1193) 후속 이행. **P1-5 retry claim_token CAS**(#1194 — 마지막 P1, stale-reclaim 이중처리/상태 clobber 차단) + P2 안전 5클러스터(#1195 SEC-LOG bot-token 로그유출 계층1·#1196 NULL-COERCE AI필드·#1197 DATETIME naive/aware·#1198 CACHE-BOUND 무한캐시·#1199 DOCS-COLLAB path-rule/arch/sensitive-path) — 전부 뮤테이션 red 회귀가드. 카덴스 발화(22 PR)로 **5+1 회고**(run `wf_1a8ad24b`·111 에이전트·확정 **80**[P0 0·P1 18·P2 62]·verdict_coverage 1.0·FP 10) — 지배 테마 = **본 세션 자기 산출물 결함**(정책 8-5 적중, 7 distinct P1 root). 회고 P1 이행: check_dual_import **방향 대칭 가드**(#1200 — #1196 자초 CodeQL #560 4회차 재발 봉인, `+import X as`↔`from X import` 역방향) · DATETIME **grep 전수**(#1201 — #1197 3곳→공용 `to_naive_utc`) · 감사 잔여 32 P2 backlog 이관+아카이브 보고서 · env-vars/MEMORY defer 정정. 🔴 **자기 process 사고 2건**(정책 8-5 실증): #1196 자초 CodeQL 이중 import(testing.md gotcha 4회차) · `git add -A` 로 DATETIME 작업이 #1197 커밋 무임승차. 단위 5866→5929.

## SonarCloud QG 복구 + 5+1 회고 + 회고 결정 이행 (2026-07-22 세션7, 8 PR #1168~#1175)

SonarCloud QG 복구(#1168~1170 — new-code reliability 2건, 🔴 S5779↔CodeQL `py/uninitialized-local` cross-tool observer 연쇄를 `try/except` wrapper 제거로 해소). **5+1 회고**(run `wf_fad44f59`·93 에이전트·확정 **65**[P0 3·P1 18·P2 44]·FP 8) — 지배 = observer-lie 메타 층 이동(카덴스·아카이브·freshness 가드가 관측만·집행 없음). 4결정 이행: owed #1062 위험수용(#1172)·npm SCA dependabot monitor(#1173)·카덴스 이월 원장 기계 관측(#1174 정책 8진화6)·does-not-raise AST 가드(#1175, `test_failover.py:304` 실위반 봉인). 자기 적발 2건(정책 8-5). 단위 5850→5866.

## 전체 문서·코드 구조 재구성 (2026-07-21 세션6, 10 PR #1157~#1166)

사용자 "반복되는 실수가 문제" 우려 → Anthropic 권장 구조로 전체 재구성. 진단(deep-research 103
에이전트 + 다중 감사 168 에이전트·확정 121건) + **Grok 최고수준 적대검증 2회**(계획 근본 전제
2회 뒤집음) + 재감사. 산출: `AGENTS.md`(Claude·Grok dual-consumer 3-불변식 SSOT) · `guards.md`
(저술 표면 write-time 자동로드) · CLAUDE.md 473→405줄(정책 detail 이관·행동가이드 보존, 정책 17) ·
기계 가드 4종(anti-vacuous 매트릭스·guard-wiring 커버리지·architecture 트리·B8 fail-open floor) ·
/login 200→301 SSOT · 6-step 충돌 해소. 🔴 **정직한 천장**: 완전 fail-open 자동 탐지는 원리적
불가(오탐>진탐·#1136 은 test-as-guard)라 3층 방어(floor+write-time 규율+review claim-review)가
완성임을 AGENTS.md 에 명시. 재구성이 안전망 가드로 자체 검증됨(A2 규정·트리 fail-open 이동 시 red).

## 접은 이력 (과거 사이클 — 1줄 요약)

> 🔴 **원문은 지워지지 않았다** — 각 항목은 아카이브의 같은 앵커로 되돌아온다.
> 여기 한 줄은 *"그 시점에 무엇을 했는가"* 만 담는다.

- **회고 P1/P2 이행 + 사용자 결정 3건 + Grok 상시 협업 (2026-07-20 세션5, 19 PR #1130~#1149)** — 가드가 자기 병을 재생산하던 것 3건 봉인(#1145 스모크 훅 0-단언에 ✅·#1148 logging 주석이 오답 ([원문](_archive/cycle-history-folded-2026-08.md#회고-p1p2-이행--사용자-결정-3건--grok-상시-협업-2026-07-20-세션5-19-pr-11301149))
- **PR 머지 + Railway 운영 실측 + 관측자-거짓말 사냥 (2026-07-19 세션4)** — 열린 PR 2건 머지 후 Railway MCP 로 배포를 실측하는 과정에서 신규 결함 1건 발견. ([원문](_archive/cycle-history-folded-2026-08.md#pr-머지--railway-운영-실측--관측자-거짓말-사냥-2026-07-19-세션4))
- **관측 복구 P0 3건 + 5+1 회고 2회 + 회고 조치 13 PR (2026-07-19)** — 2026-07-19 세션3 — 관측 복구 P0 3건 + 5+1 회고 2회 + 회고 조치 (총 13 PR #1102~#1114)** — [[project-logging-wipe-token-leak-2026-07-19]] 인수인계 1건(cron 검증)에서 출발해 **관측  ([원문](_archive/cycle-history-folded-2026-08.md#관측-복구-p0-3건--51-회고-2회--회고-조치-13-pr-2026-07-19))
- **세션2 회고 + 회고 fix 4 트랙 11 PR (2026-07-18)** — 이전 세션([[project-premium-readiness-audit-2026-07-18]])의 잔여 CodeQL #545(#1070 이 자초한 `test_repo_detail_query.py` User FK-등록 import) 봉인부터 시작해 5+1 회고 → 회고  ([원문](_archive/cycle-history-folded-2026-08.md#세션2-회고--회고-fix-4-트랙-11-pr-2026-07-18))
- **프리미엄 준비도 감사 + Wave 0~2 코드전용 8 PR (2026-07-18)** — 사용자 요청 = "새 기능보다 완성도·안정성·기능 결함 보완" (프리미엄급 서비스 대비). → **6차원 프리미엄 멀티테넌트 준비도 감사**(wf_2e184916·29 에이전트·370만 토큰) 후 코드-전용 결함 하드닝 **8 PR (#1068~#1075) 전부 머지* ([원문](_archive/cycle-history-folded-2026-08.md#프리미엄-준비도-감사--wave-02-코드전용-8-pr-2026-07-18))
- **Grok 백로그 NULL-owner IDOR + 워커 내구성 6 PR (2026-07-17)** — [[project-grok-full-review-2026-07-17]] 의 확정 P1 백로그(P1-2 워커 내구성·P1-3 NULL-owner IDOR)와 그 파생 결함(R2/R3/R4)을 전량 착수 → **PR 6건 + CodeQL fix 1건 = 7 PR 전부 머지 ([원문](_archive/cycle-history-folded-2026-08.md#grok-백로그-null-owner-idor--워커-내구성-6-pr-2026-07-17))
- **설정 간소화 · 개요 count-up 봉인 · 회고 후속 (2026-07-09)** — 2026-07-08~09 세션 아크 (#1034~#1046). #1033 Anthropic 비용 제어 후속으로 설정 UX 간소화 + 개요 표시버그 봉인 + 정기 5+1 회고 + 회고 후속 4트랙. ([원문](_archive/cycle-history-folded-2026-08.md#설정-간소화--개요-count-up-봉인--회고-후속-2026-07-09))
- **Anthropic 비용 제어 3종 (2026-07-08)** — 🔴 **교훈**: (1) **`check-config-5way-sync` 훅=전체상태(diff 아님) 검사** → RepoConfig 신규 필드는 ORM+RepoConfigData+RepoConfigUpdate 원자 단일커밋 강제(Task 2.1+2.2 병합·ORM-o ([원문](_archive/cycle-history-folded-2026-08.md#anthropic-비용-제어-3종-2026-07-08))
- **5+1 회고 및 8 클러스터 fix 6 PR (2026-07-03)** — 사용자 "이전 세션 이후 작업 이어서" → 이전 세션(#1015~#1023) 완결 확인 → **회고 카덴스 갭 식별**(직전 정식 회고 2026-06-23 이후 4세션[06-25/06-29×2/07-03]·~30 PR[#989~#1023] 무회고, 06-25 "75줄  ([원문](_archive/cycle-history-folded-2026-08.md#51-회고-및-8-클러스터-fix-6-pr-2026-07-03))
- **심층 감사 및 note 하드닝 (2026-07-03)** — 사용자 요청: 열린 PR 검토·머지 + 서비스 안정성·잠재버그·은닉/악성코드·의도불일치 세밀 검증 + 실테스트. ([원문](_archive/cycle-history-folded-2026-08.md#심층-감사-및-note-하드닝-2026-07-03))
- **cross-vendor 감사 및 구조검토 (2026-06-29)** — 전체 코드(src 244 .py)+문서 Claude 8-차원 다중에이전트 wf(`wf_b30ca2e6`) + Codex 독립 cross-vendor 심층 감사 → 정리·구조 검토까지: ([원문](_archive/cycle-history-folded-2026-08.md#cross-vendor-감사-및-구조검토-2026-06-29))
- **B 백로그 3건 구현 C-1 RLS LIVE 검증 (2026-06-29)** — 2026-06-25 품질 감사의 잔여 보류 3건을 사용자 결정 후 PR 단위 구현(각 정책 18 Codex mutual) + RLS 운영 LIVE 심층검증: ([원문](_archive/cycle-history-folded-2026-08.md#b-백로그-3건-구현-c-1-rls-live-검증-2026-06-29))
- **전체 품질 감사 2라운드 다중에이전트 6 PR CodeQL 봉인 (2026-06-25)** — 전체 코드(src 244 .py 26K LOC) + 문서(docs 48K LOC) 2라운드 다중에이전트 품질 감사(`wf_f0e831cf` 15 클러스터 + `wf_00706a61` 5 클러스터, 67 발견·적대 검증·**운영 P0=0·코드 활성 P1=0**) → 6  ([원문](_archive/cycle-history-folded-2026-08.md#전체-품질-감사-2라운드-다중에이전트-6-pr-codeql-봉인-2026-06-25))
- **R13 평가 — native auto-merge 부적합·retry 큐 영구 primary (2026-06-24)** — 🔴 **핵심 발견**: native auto-merge enable **성공 0회**(전체 이력 2223 시도) · retry 큐(merge_retry_service)가 운영 유일 작동 머지 메커니즘(`merge_retry_queue` succeeded 938 · `u ([원문](_archive/cycle-history-folded-2026-08.md#r13-평가--native-auto-merge-부적합retry-큐-영구-primary-2026-06-24))
- **잔여작업 — docs drift 정정 · 회고 C10/C11 · C1 CodeQL cascade 가드 (2026-06-24)** — 날짜**: 2026-06-24 | **PR**: #977 / #978 / #979 (전부 머지) | **출처**: 사용자 "잔여작업 확인" → 4-투자자 감사(`wf_95bc1f45`, 코드 P0/P1 0) → "Claude 수행 가능 작업 우선 처리" ([원문](_archive/cycle-history-folded-2026-08.md#잔여작업--docs-drift-정정--회고-c10c11--c1-codeql-cascade-가드-2026-06-24))
- **회고 follow-up — retrospective.mjs dogfooding + 하드닝 (2026-06-23)** — 날짜**: 2026-06-23 | **브랜치**: fix/retrospective-followup-hardening | **출처**: `/retrospective` 워크플로우 첫 실전(`wf_fbf8355f-538`) 회고 결과 Option A ([원문](_archive/cycle-history-folded-2026-08.md#회고-follow-up--retrospectivemjs-dogfooding--하드닝-2026-06-23))
- **repo-automation PR-S — 정책 흐름 스킬 3종 (docs-sync · retrospective · codex-verify) (2026-06-23)** — 날짜**: 2026-06-23 | **브랜치**: feat/repo-automation-pr-s-skills | **출처**: repo-automation spec(`docs/design/2026-06-23-repo-automation-design.md`) Area 3 ([원문](_archive/cycle-history-folded-2026-08.md#repo-automation-pr-s--정책-흐름-스킬-3종-docs-sync--retrospective--codex-verify-2026-06-23))
- **repo-automation PR-W — 워크플로우 loop 단일출처화 + 회고 워크플로우 신규 (2026-06-23)** — 날짜**: 2026-06-23 | **브랜치**: feat/repo-automation-pr-w-workflows | **출처**: repo-automation spec(`docs/design/2026-06-23-repo-automation-design.md`) Are ([원문](_archive/cycle-history-folded-2026-08.md#repo-automation-pr-w--워크플로우-loop-단일출처화--회고-워크플로우-신규-2026-06-23))
- **회고 P2 백로그 — .env.example 무인증 footgun 제거 + 2nd-LLM 검증자 활성화 runbook (2026-06-23)** — 날짜**: 2026-06-23 | **브랜치**: fix/env-example-auth-footgun (#971) · docs/verifier-runbook-session-sync | **출처**: 2026-06-23 정밀 감사 세션 5+1 회고(`wf_ba64fd24 ([원문](_archive/cycle-history-folded-2026-08.md#회고-p2-백로그--envexample-무인증-footgun-제거--2nd-llm-검증자-활성화-runbook-2026-06-23))
- **repo-automation PR-H 신규 pre-commit 훅 3종 (2026-06-23)** — 날짜**: 2026-06-23 | **브랜치**: docs/repo-automation-spec | **spec**: docs/design/2026-06-23-repo-automation-design.md (Area 2) | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#repo-automation-pr-h-신규-pre-commit-훅-3종-2026-06-23))
- **회고 도구 개선 docs repo-integrity pre-commit 훅 (2026-06-23)** — 날짜**: 2026-06-23 | **PR**: chore/repo-integrity-hooks | **트리거**: 세션 5+1 회고 도구 관점(WF-1~5) | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#회고-도구-개선-docs-repo-integrity-pre-commit-훅-2026-06-23))
- **세션 다중 에이전트 회고 follow-up P2 (markdown escape 4번째 채널, 2026-06-23)** — 날짜**: 2026-06-23 | **PR**: fix/retro-p2-github-issue-escape | **트리거**: #962~#966 세션 5+1 다중 에이전트 회고(`wf_ba64fd24`) | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#세션-다중-에이전트-회고-follow-up-p2-markdown-escape-4번째-채널-2026-06-23))
- **감사 P2 하드닝 — 아웃바운드 markdown 인젝션 escape + 단일출처 2건 (2026-06-23)** — 날짜**: 2026-06-23 | **PR**: fix/audit-markdown-injection-singlesource | **트리거**: 69-에이전트 정밀 감사 P2(테스트/단일출처 + markdown 인젝션) | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#감사-p2-하드닝--아웃바운드-markdown-인젝션-escape--단일출처-2건-2026-06-23))
- **감사 보안 게이트 fail-open 봉인 3건 (auth fail-closed, static crash, retry sha-bound, 2026-06-23)** — 날짜**: 2026-06-23 | **PR**: fix/audit-failopen-hardening | **트리거**: 69-에이전트 정밀 감사 보안/게이트 잔여 3건 (High tier — 사용자 항목별 결정) | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#감사-보안-게이트-fail-open-봉인-3건-auth-fail-closed-static-crash-retry-sha-bound-2026-06-23))
- **native auto-merge SHA-atomicity fail-closed (#962, 2026-06-23)** — 날짜**: 2026-06-23 | **PR**: #962 (브랜치 fix/automerge-sha-atomicity-failclosed, main 5eb2348) | **트리거**: 69-에이전트 정밀 감사 보안/게이트 4건 중 #2 | **상태**: 머지 ([원문](_archive/cycle-history-folded-2026-08.md#native-auto-merge-sha-atomicity-fail-closed-962-2026-06-23))
- **정밀 감사(69-에이전트 다차원 워크플로우) + docs-drift 13건 정정 (#961, 2026-06-23)** — 날짜**: 2026-06-22~23 | **PR**: #961 (docs-drift) | **트리거**: 사용자 "전체 문서·코드 정합성·코드품질·보안강화 정밀 검증 (딥리서치 + 다이나믹 워크플로우)" | **상태**: #961 머지 / 보안·게이트 4건 항목별 확인 ([원문](_archive/cycle-history-folded-2026-08.md#정밀-감사69-에이전트-다차원-워크플로우--docs-drift-13건-정정-961-2026-06-23))
- **AI 리뷰 점수 NULL 폐기 분리 — 입력 diff 절단 시 점수 보존 (#960, 2026-06-22)** — 날짜**: 2026-06-22 | **PR**: #960 | **트리거**: 사용자 "Supabase 데이터 확인" → 점검 중 운영 이슈 발견 → "확인된 문제점 수행" | **상태**: 머지 대기 ([원문](_archive/cycle-history-folded-2026-08.md#ai-리뷰-점수-null-폐기-분리--입력-diff-절단-시-점수-보존-960-2026-06-22))
- **SonarCloud S6853 폼 라벨 7건 해소 + edit-guard hook 견고화 + 의존성 (2026-06-22 후속)** — 날짜**: 2026-06-22 | **PR**: #957·#958·#956·#944·#945 | **트리거**: 사용자 "후속작업" + "PR #944/#945 머지" | **상태**: 직전 세션(#948~#955) deferred 2건 + 선행 blocker + 의존 ([원문](_archive/cycle-history-folded-2026-08.md#sonarcloud-s6853-폼-라벨-7건-해소--edit-guard-hook-견고화--의존성-2026-06-22-후속))
- **SonarCloud 잔여 CRITICAL 전부 해소 (#951~#954, 2026-06-22)** — 🔴 **함정**: #954 replace_all 순서 실수(헬퍼 추가 후 replace_all → 헬퍼 자기참조 무한재귀, 17 test fail) → 즉시 복구. S1192 상수(#949) 때와 달리 헬퍼 본문이 교체 패턴을 포함해 발생 — **replace_all  ([원문](_archive/cycle-history-folded-2026-08.md#sonarcloud-잔여-critical-전부-해소-951954-2026-06-22))
- **SonarCloud BLOCKER 및 고복잡도 CRITICAL 정리 (#948~#950, 2026-06-22)** — 폼 입력 aria-label 게이트 복구(#946) 후 사용자 잔여 작업 점검 → SonarCloud 코드 스멜 정리. 게이트는 이미 OK·전 등급 A 라 **품질 개선 성격**(차단성 무). BLOCKER 1 + CRITICAL 10 중 고가치/저위험 항목 처리. ([원문](_archive/cycle-history-folded-2026-08.md#sonarcloud-blocker-및-고복잡도-critical-정리-948950-2026-06-22))
- **SonarCloud Quality Gate ERROR 복구 (폼 입력 20건 aria-label, 2026-06-22)** — 사용자 SonarQube 상태 점검 요청 → 공개 API 실측으로 **Quality Gate ERROR** 발견 (유일 실패 조건 `new_reliability_rating` C(3) > A(1) — 나머지 보안 A·커버리지 96.6%·중복 0.1%·핫스팟 0 정상). ([원문](_archive/cycle-history-folded-2026-08.md#sonarcloud-quality-gate-error-복구-폼-입력-20건-aria-label-2026-06-22))
- **2nd-LLM 머지 검증자 OpenAI-호환 base_url 일반화 (2026-06-19)** — 사용자 잔여작업 확인 중 2nd-LLM 머지 검증자 활성화 문의 — "OPENAI_API_KEY 를 API 아닌 SDK 또는 다른 방법으로 가능한지" + "추가 비용 0/최소(OpenAI 비구독자 또는 보유자 최소 비용)". 조사 결과: ([원문](_archive/cycle-history-folded-2026-08.md#2nd-llm-머지-검증자-openai-호환-base_url-일반화-2026-06-19))
- **개요 점수 0/100 실제 repo→개요 hx-boost 네비게이션 회귀 가드 e2e 추가 (2026-06-19)** — 사용자 운영 화면 보고: repo 상세 화면을 거친 뒤 개요(`/`)로 이동 시 모든 repo 카드 점수가 "0/100" 고착(등급 A/B 정상 = score 데이터 정상, count-up JS 만 미작동). ([원문](_archive/cycle-history-folded-2026-08.md#개요-점수-0100-실제-repo개요-hx-boost-네비게이션-회귀-가드-e2e-추가-2026-06-19))
- **정적 자산 immutable 캐시 → 배포 미전파 stale 사고 수정 (2026-06-18)** — 개요(`/`) 모든 repo 카드 점수 "0/100" 지속 — 사용자 운영 화면 보고 (2026-06-18)** — 등급 배지 A/B 정상(=score 데이터 정상)인데 점수만 "0/100" = JS count-up 미작동. count-up fix #936 머지·배포( ([원문](_archive/cycle-history-folded-2026-08.md#정적-자산-immutable-캐시--배포-미전파-stale-사고-수정-2026-06-18))
- **개요 점수 0/100 count-up 고착 — IO 미발동 안전망 + 이중 init dispose 회귀 P1 (1c0a483/75f942e) (2026-06-18)** — 개요(`/`) repo 카드 점수 "0/100" 고착 (commit 1c0a483 + 75f942e, 2026-06-18)** — effects.js `setupCountUp` 이 `.repo-card__score` 를 "0" pre-fill 후 `onceInView` ([원문](_archive/cycle-history-folded-2026-08.md#개요-점수-0100-count-up-고착--io-미발동-안전망--이중-init-dispose-회귀-p1-1c0a48375f942e-2026-06-18))
- **repo_detail 점수추이 차트 미표시 — I18N 스코프 격리 버그 (#933) (2026-06-18)** — repo_detail(`/repos/{name}`) scoreChart 영구 미표시 (#933, 2026-06-18)** — 사용자 운영 스크린샷 보고. F12: `Uncaught ReferenceError: I18N is not defined at buildChart ([원문](_archive/cycle-history-folded-2026-08.md#repo_detail-점수추이-차트-미표시--i18n-스코프-격리-버그-933-2026-06-18))
- **AI 리뷰 parse_error 근본 수정 (#931) (2026-06-18)** — AI 코드리뷰 parse_error 출시 이래 ~80% 만성 실패 근본 수정 (#931, 2026-06-18)** — 사용자 "잔여작업 확인" → 이전 미해결 "점수추이 차트 미표시" 재개. systematic-debugging 으로 데이터 파이프라인 역추적: ① 차트 ([원문](_archive/cycle-history-folded-2026-08.md#ai-리뷰-parse_error-근본-수정-931-2026-06-18))
- **repos 모드 점수추이 차트 미표시 수정 — #921 후속 다중 차트 가드 + 전 모드 Chart.js 로드 (#929) (2026-06-17)** — repos 모드 점수추이 차트 미표시 수정 (#929, 2026-06-17)** — 사용자 보고 "점수추이 그래프가 #921 수정 후에도 여전히 안 나타남. E2E·Playwright 로 확인 부탁". systematic-debugging + Playwright 실증으 ([원문](_archive/cycle-history-folded-2026-08.md#repos-모드-점수추이-차트-미표시-수정--921-후속-다중-차트-가드--전-모드-chartjs-로드-929-2026-06-17))
- **품질 감사 P2 백로그 해소 — 코드 nit + 문서 인용 2 PR (#926/#927) (2026-06-17)** — 품질 감사 P2 백로그 후속 (2026-06-17)** — 사용자 "후속 작업 부탁드립니다" → 품질 감사 세션(`wf_c9b58749`) confirmed P2 11건 중 잔여 처리. P1 2건(#923/#924)·doccon-1/3 은 직전 세션 머지 완료. **사 ([원문](_archive/cycle-history-folded-2026-08.md#품질-감사-p2-백로그-해소--코드-nit--문서-인용-2-pr-926927-2026-06-17))
- **전체 문서·코드 품질 감사 세션 — 9차원 다이나믹 워크플로우 + P1 2건 해소 (#923/#924) (2026-06-17)** — 품질 감사 세션 (2026-06-17)** — 사용자 "전체 문서와 전체 코드의 품질상태 점검 — 딥리서치 및 다이나믹 워크플로우 승인" → ① 브랜치 정리 ② 9차원 품질 감사 워크플로우 ③ P1 2건 해소. ([원문](_archive/cycle-history-folded-2026-08.md#전체-문서코드-품질-감사-세션--9차원-다이나믹-워크플로우--p1-2건-해소-923924-2026-06-17))
- **차트 hx-boost async 로드 race 가드 LIVE 머지 + sync (#921) (2026-06-17)** — 차트 hx-boost async 로드 race 가드 (#921, 2026-06-17)** — 사용자 "머지 이후 후속작업 수행" → 지난 세션 머지 대기 PR #921 squash 머지(CI 8/8 green·CLEAN·Codex PUSH OK 6/6) + 본 sync ([원문](_archive/cycle-history-folded-2026-08.md#차트-hx-boost-async-로드-race-가드-live-머지--sync-921-2026-06-17))
- **RLS Phase 4 운영 전환 검증 완료 (2026-06-16)** — step 2 URL 전환 실측**: `DATABASE_URL`→`scamanager_app`(rolbypassrls=false) · `DATABASE_URL_WORKER`→`scamanager_worker`(true) · `MIGRATION_DATABASE_URL`→p ([원문](_archive/cycle-history-folded-2026-08.md#rls-phase-4-운영-전환-검증-완료-2026-06-16))
- **잔여/후속 — 회고 P2 마지막 테스트 하드닝 CODE-3/TEST-2 (#919) (2026-06-16)** — 회고 P2 마지막 테스트 하드닝 (#919, 2026-06-16)** — 사용자 "후속작업 수행" → 회고 P2 잔여 2건(CODE-3·TEST-2) de-scope 해제. #918 이 IPv4/SSL 연결 경로(회귀 민감 영역)를 직접 수정 → retro 의 CODE ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속--회고-p2-마지막-테스트-하드닝-code-3test-2-919-2026-06-16))
- **잔여/후속 — broad-docs Railway IPv6 opt-in 정확화 (#918) (2026-06-16)** — broad-docs Railway IPv6 opt-in 정확화 (#918, 2026-06-16)** — 사용자 "권장·타당 방안으로 진행" → #916 에서 Codex 가 공식 docs 근거로 적발한 broad-docs 사실 오류 중 **LIVE 가이드**(미래 독자가 ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속--broad-docs-railway-ipv6-opt-in-정확화-918-2026-06-16))
- **잔여/후속 — 회고 P2 백로그 Phase 4 transition 안전 하드닝 (#915/#916) (2026-06-16)** — 회고 P2 백로그 Phase 4 transition 안전 하드닝 (#915/#916, 2026-06-16)** — 사용자 "이후 작업을 수행" → 2026-06-16 회고 P2 백로그 중 Claude 실행 가능 + 사용자 다음 ops(RLS Phase 4 step 1~ ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속--회고-p2-백로그-phase-4-transition-안전-하드닝-915916-2026-06-16))
- **잔여/후속 — 2026-06-16 세션 회고(정책 8, 5+1) + Option A follow-up (#912~#914) (2026-06-16)** — 2026-06-16 세션 회고 + Option A follow-up (#912~#914, 2026-06-16)** — 사용자 "후속 작업을 수행" → 메모리에 "🔵 다음 세션 우선 task"로 명시된 **2026-06-16 Railway follow-up 세션(#906 ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속--2026-06-16-세션-회고정책-8-51--option-a-follow-up-912914-2026-06-16))
- **잔여/후속 — Railway pre-deploy + 연결 invariants docs + MIGRATION_DATABASE_URL (#906~#908) (2026-06-16)** — 잔여/후속 — Railway pre-deploy fix + 연결 invariants docs + MIGRATION_DATABASE_URL (#906~#908, 2026-06-16)** — 사용자 "잔여/후속 작업 진행" → 2026-06-15 Railway↔Supaba ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속--railway-pre-deploy--연결-invariants-docs--migration_database_url-906908-2026-06-16))
- **마이그레이션 0039/0040 멱등화 — 운영 alembic 0038 고착 해소 (#904) (2026-06-15)** — 날짜**: 2026-06-15 | **트리거**: RLS Phase 4 step 0 배포 후 사용자 "재배포 완료, MCP 확인" → MCP 진단으로 alembic 0038 고착 발견 | **상태**: #904 squash 머지, Codex mutual round1/2 ([원문](_archive/cycle-history-folded-2026-08.md#마이그레이션-00390040-멱등화--운영-alembic-0038-고착-해소-904-2026-06-15))
- **starlette 1.0.1+ 마이그레이션 + dependabot 배치 — #902 · #897~#900 (2026-06-15)** — 날짜**: 2026-06-15 | **트리거**: 사용자 "잔여/후속 작업 확인" → RLS Phase 4 + dependabot 트랙 착수. dependabot 5건(#897~#901) CI fail 조사 | **상태**: #902 squash 머지 + dependa ([원문](_archive/cycle-history-folded-2026-08.md#starlette-101-마이그레이션--dependabot-배치--902--897900-2026-06-15))
- **회고 P2 백로그 해소 — P2-a/C22/C12 3 PR (#893~#895) (2026-06-14)** — 날짜**: 2026-06-14 | **트리거**: 사용자 "권장하는 순서로 진행" 위임 → integrity-audit 회고 P2 잔여 3건(P2-a 자율 + C22/C12 정책15 High tier 사용자 결정 A/A) 순차 처리 | **상태**: 3 PR squas ([원문](_archive/cycle-history-folded-2026-08.md#회고-p2-백로그-해소--p2-ac22c12-3-pr-893895-2026-06-14))
- **회고(5+1) P1 follow-up — README.ko 배지·#888 정적 가드·db.md U1 divergence (2026-06-14)** — 날짜**: 2026-06-14 | **트리거**: 사용자 "회고를 수행해주세요" → 5+1 다중 에이전트 회고(wf_7adc2655) → 사용자 결정 "P1 3건 fix PR" | **상태**: 1 PR, Codex mutual ([원문](_archive/cycle-history-folded-2026-08.md#회고51-p1-follow-up--readmeko-배지888-정적-가드dbmd-u1-divergence-2026-06-14))
- **정합성 감사 백로그 C12·C22·U1 머지 — 3 PR (#884~#886) (2026-06-13)** — 날짜**: 2026-06-13 | **트리거**: 사용자 "잔여/후속 작업 확인" → 상태 실측(메모리 stale 정정 — C12/C22 결정이 이미 내려져 PR 생성됨) → "순차 머지 위임" | **상태**: 3 PR squash 머지, 전 PR Codex mutu ([원문](_archive/cycle-history-folded-2026-08.md#정합성-감사-백로그-c12c22u1-머지--3-pr-884886-2026-06-13))
- **잔여/후속 세션 — C1 save_gate_decision dead wrapper 제거 (2026-06-13)** — 날짜**: 2026-06-13 | **트리거**: U2 머지(#882) 후 사용자 "머지 확인 + 다음 작업" → integrity-audit 백로그 C1 (결정 게이트 없는 유일한 자율-안전 항목) | **상태**: 1 PR, Codex mutual ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속-세션--c1-save_gate_decision-dead-wrapper-제거-2026-06-13))
- **잔여/후속 세션 — U2 effects.js hx-boost 애니메이션 재초기화 (2026-06-13)** — 날짜**: 2026-06-13 | **트리거**: 사용자 "잔여작업과 후속작업 확인" → 7항목 직접 재검증(read-only 워크플로 wf_6fea0937, 7 에이전트) → 사용자 결정 **U2** | **상태**: 1 PR, Codex mutual 대기 ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속-세션--u2-effectsjs-hx-boost-애니메이션-재초기화-2026-06-13))
- **정합성 감사 P2 백로그 처리 — 6 PR (#874~879) (2026-06-12)** — 전 PR TDD·Codex mutual OK(다수 NG 적발→동일 PR 즉시 수정→재검증, 정책 18 §3b — C10 None 미봉인·C11 failure 경로·C9 주석 이중언어·C30 테스트 등)·CI green·pylint 10.00. 단위 4907→4915(+ ([원문](_archive/cycle-history-folded-2026-08.md#정합성-감사-p2-백로그-처리--6-pr-874879-2026-06-12))
- **전체 정합성 감사 — 보안/correctness P1 4 PR (#868~871) (2026-06-12)** — 전 PR TDD(+12: #868+3·#869+1·#870+6·#871+2)·**Codex mutual OK**·CI green·pylint 10.00. 단위 4895→4907·통합 154·전체 5061. **docs 백로그 정정**: 커버리지 95→97%(8497줄/ ([원문](_archive/cycle-history-folded-2026-08.md#전체-정합성-감사--보안correctness-p1-4-pr-868871-2026-06-12))
- **잔여/후속 세션 — #865 검증자 봉인 P1-1 반자동 parity (2026-06-12)** — Codex mutual OK(#865 push 전)·CI 8/8 green. **검증자 봉인 P1 코드상 3건 전부 완료**(interpret_verdict #861·diff cap #863·parity #865) → 활성화(`OPENAI_API_KEY` BYO, 사용 ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속-세션--865-검증자-봉인-p1-1-반자동-parity-2026-06-12))
- **잔여/후속 세션 — #863 머지 (검증자 봉인 P1-4) (2026-06-12)** — Codex mutual OK(#863, 머지 전 완료)·CI 8/8 green. 단위 4880→4886(+6)·통합 154·전체 5040. pylint 10.00. ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속-세션--863-머지-검증자-봉인-p1-4-2026-06-12))
- **잔여/후속 세션 — docs 정합·회고·P2 하드닝 (#860/#861, 2026-06-11)** — 전 PR Codex mutual OK(정책 18)·CI 8/8 green. 단위 4864→4880(+16, #861)·통합 154·전체 5034. pylint 10.00. ([원문](_archive/cycle-history-folded-2026-08.md#잔여후속-세션--docs-정합회고p2-하드닝-860861-2026-06-11))
- **2nd-LLM 머지 검증자 도입 (cross-vendor AI 거버넌스 가드, 2026-06-11)** — 날짜**: 2026-06-11 | **브랜치**: feat/merge-verifier | **트리거**: 사용자 "현재 분석/동작 체계가 AI 거버넌스에 해당하는가, 아니면 별도 LLM 이 추가 투입돼 상호보완 협업해야 하는가" 문의 | **상태**: 브레인스토밍→sp ([원문](_archive/cycle-history-folded-2026-08.md#2nd-llm-머지-검증자-도입-cross-vendor-ai-거버넌스-가드-2026-06-11))
- **정합성 감사 + deep-research follow-up (2026-06-11) — #852~856** — 날짜**: 2026-06-11 | **PR**: #852~856 (5건 머지) | **트리거**: 사용자 "잔여작업 및 후속작업 확인" → "PR 우선 머지 + 이후 순차 진행" | **상태**: 직전 세션(2026-06-10/11) integrity-audit ful ([원문](_archive/cycle-history-folded-2026-08.md#정합성-감사--deep-research-follow-up-2026-06-11--852856))
- **사이클 166** — 전 PR Codex true mutual OK·CI green. 단위 4723→4726. ([원문](_archive/cycle-history-folded-2026-08.md#사이클-166))
- **사이클 166 적대 재검증 후속 (2026-06-09) — #838~#841** — 날짜**: 2026-06-09 | **PR**: #838~#841 (4건 머지) | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" (재요청) | **상태**: STATE overclaim + #32 위양성 적발 → 해소 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-166-적대-재검증-후속-2026-06-09--838841))
- **잔여작업 라운드 (2026-06-09~10) — #843/#844 (사용자 결정 C)** — 이전 보류 결정(③④' allowlist 유지 / #2 SaaS 유지)을 사용자 재결정(C)으로 수행. ([원문](_archive/cycle-history-folded-2026-08.md#잔여작업-라운드-2026-06-0910--843844-사용자-결정-c))
- **잔여 정리 라운드 A옵션 (2026-06-10)** — 전수 스캔(1차 42건 → critic 검증 후 고유 ~24건, 허위 2건 부분 기각)이 STATE '잔여 #2만' 선언 밖에서 신규 P1 사고를 적발 — 본 라운드로 정리. ([원문](_archive/cycle-history-folded-2026-08.md#잔여-정리-라운드-a옵션-2026-06-10))
- **RLS #2 Phase 4 admin 대시보드 cross-tenant 보존 — api/admin·ui/routes/admin hybrid (#849 후속) (2026-06-10)** — 날짜**: 2026-06-10 | **PR**: #850 | **트리거**: #849 머지 후 사용자 "이후 작업을 수행해주세요" → 마지막 코드 가능 #2 항목(/admin cross-tenant under-report) 해소 | **상태**: 코드 완료(#850 머 ([원문](_archive/cycle-history-folded-2026-08.md#rls-2-phase-4-admin-대시보드-cross-tenant-보존--apiadminuiroutesadmin-hybrid-849-후속-2026-06-10))
- **RLS #2 Phase 4 OAuth 로그인 blocker 해소 — auth_callback worker 세션 전환 (옵션 2) (2026-06-10)** — 날짜**: 2026-06-10 | **PR**: #849 | **트리거**: 사용자 "잔여 작업을 확인해주세요" → 잔여 #2 Phase 4 선행 blocker(OAuth users self-RLS) 옵션 표 제시 → 사용자 **옵션 ② (auth upsert work ([원문](_archive/cycle-history-folded-2026-08.md#rls-2-phase-4-oauth-로그인-blocker-해소--auth_callback-worker-세션-전환-옵션-2-2026-06-10))
- **RLS Phase 1 운영 + Phase 3 — 0041 FORCE + 실측 가시화 (2026-06-10)** — 날짜**: 2026-06-10 | **PR**: #848 | **트리거**: 사용자 "Claude가 MCP로 수행하기를 원합니다" (Phase 1 — 정책 12 DDL 사전 승인) → "네 바로 수행을 부탁드립니다" (Phase 3) | **상태**: Phase 1 운 ([원문](_archive/cycle-history-folded-2026-08.md#rls-phase-1-운영--phase-3--0041-force--실측-가시화-2026-06-10))
- **RLS Phase 2 — background 전용 worker 세션 분리 (2026-06-10)** — 정합성 감사 #2 (RLS owner-bypass) 의 선행 필수 코드 — role 분리 후 background 경로가 `app.user_id` 미설정으로 차단되는 파이프라인 붕괴(runbook L32/L57)를 막는 이중 세션 라우팅. ([원문](_archive/cycle-history-folded-2026-08.md#rls-phase-2--background-전용-worker-세션-분리-2026-06-10))
- **사이클 165** — 날짜**: 2026-06-08~09 | **PR**: #802~#814 (11건 머지) | **상태**: Task9 골든 리메디에이션 — P1 9/10 + P2 보안·파이프라인 하드닝 클러스터 5/5 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-165))
- **사이클 164** — 날짜**: 2026-06-08 | **PR**: #795·#796·#794 (3건 머지) | **상태**: area=gate 감사 잔여 6 결함 — 사용자 Q1~Q4 결정 이행 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-164))
- **사이클 163** — 날짜**: 2026-06-07 | **PR**: #783~#787 (5건 머지) | **상태**: area=gate P2 백로그 해소 (자기완결적 5건) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-163))
- **사이클 162** — 날짜**: 2026-06-07 | **PR**: #774~#781 (8건 머지) | **상태**: 잔여 백로그 전량 처리 + integrity-audit 워크플로우 완성 + 워크플로우 발견 area=gate P1 fix 3건 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-162))
- **사이클 161** — 날짜**: 2026-06-06 | **PR**: #764~#767 | **상태**: 정합성 감사 P1 백로그 해소 (직전 #759 full 감사 confirmed) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-161))
- **사이클 160** — 날짜**: 2026-06-06 | **PR**: #760~#763 | **상태**: integrity-audit 다이나믹 워크플로우 검증 + 현재 main 정합성 감사 fix ([원문](_archive/cycle-history-folded-2026-08.md#사이클-160))
- **사이클 159** — 날짜**: 2026-06-03 | **PR**: #743~#746 (PR-A/B/C/D) + #742 | **상태**: 157 회고 백로그 P2 전량 해소 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-159))
- **사이클 158** — 날짜**: 2026-06-03 | **PR**: #741 | **상태**: 회고 + docs 정합 봉인 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-158))
- **사이클 157** — 날짜**: 2026-06-02 | **PR**: #739~#740 (#8·#9) | **상태**: 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-157))
- **사이클 156** — 날짜**: 2026-06-02 | **PR**: #735~#738 (S1·S2·S4·S3) | **상태**: S1~S4 전부 머지 완료 (#735~#738) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-156))
- **사이클 155** — 날짜**: 2026-06-02 | **PR**: #734+ | **상태**: 작업 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-155))
- **사이클 154** — 날짜**: 2026-06-02 | **PR**: #733 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-154))
- **사이클 153** — 날짜**: 2026-06-01 | **PR**: #730~#731 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-153))
- **사이클 152** — 날짜**: 2026-06-01 | **PR**: #726~#728 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-152))
- **사이클 151** — 날짜**: 2026-06-01 | **PR**: #724 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-151))
- **사이클 150** — 날짜**: 2026-06-01 | **PR**: #717 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-150))
- **사이클 149** — 날짜**: 2026-06-01 | **PR**: #712~#715 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-149))
- **사이클 148** — 날짜**: 2026-06-01 | **PR**: #710 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-148))
- **사이클 147** — 날짜**: 2026-06-01 | **PR**: #707~#708 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-147))
- **사이클 146** — 날짜**: 2026-06-01 | **PR**: #702~#705 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-146))
- **사이클 145** — 날짜**: 2026-05-31 | **PR**: #698~#699 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-145))
- **사이클 144** — 날짜**: 2026-05-31 | **PR**: #694~#696 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-144))
- **사이클 143** — 날짜**: 2026-05-31 | **PR**: #684~#692 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-143))
- **사이클 142** — 날짜**: 2026-05-31 | **PR**: #673~#679 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-142))
- **사이클 141** — 날짜**: 2026-05-30 | **PR**: #669~#671 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-141))
- **사이클 140** — 날짜**: 2026-05-30 | **PR**: #665~#667 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-140))
- **사이클 139** — 날짜**: 2026-05-30 | **PR**: #660~#664 | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-139))
- **사이클 138** — 날짜**: 2026-05-27 | **PR**: #651 (`fix/dashboard-always-overview`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-138))
- **사이클 137** — 날짜**: 2026-05-26 | **PR**: #649 (`fix/dashboard-localstorage-redirect`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-137))
- **사이클 136** — 날짜**: 2026-05-25 | **PR**: #647 (`fix/analysis-detail-top-bottom-polish`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-136))
- **사이클 135** — 390px(iPhone 12 Pro) 뷰포트 before/after 스크린샷 비교 — 3개 섹션 모두 수정 확인 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-135))
- **사이클 134** — 날짜**: 2026-05-25 | **PR**: #643 (`chore/docs-cleanup-product-readme`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-134))
- **사이클 133** — 날짜**: 2026-05-25 | **PR**: #641 (`fix/nav-logo-text-color-token`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-133))
- **사이클 132** — 날짜**: 2026-05-25 | **PR**: #639 (`fix/theme-option-data-attr-collision`) | **상태**: ✅ 머지 완료 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-132))
- **사이클 131** — 1. T2 themes.css — T1이 stub 전환했으므로 `--ours` 수락 (grade-bg/bd는 tokens.css에 이미 존재) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-131))
- **사이클 130** — 1. pylint 10.00/10 복원 — 6건 inline disable + RegisterRequest docstring ([원문](_archive/cycle-history-folded-2026-08.md#사이클-130))
- **사이클 129** — 1. SonarCloud Coverage 75%/83% → 100% (21 tests 추가 — `_get_analysis_and_repo`·`_get_repo_or_404`·TOCTOU·HTTPError·naive-datetime 경로) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-129))
- **Phase F ~ Phase 12** — Tier1 정적분석 10종 + Observability (Sentry + Claude metrics + stage timing + MergeAttempt) ([원문](_archive/cycle-history-folded-2026-08.md#phase-f--phase-12))
- **그룹 60+61** — 그룹 60+61 (2026-05-02 단일 작업일 23 PR) 완료** — Phase 1+2 Insight Dashboard 재설계 (`/dashboard` MVP-B 출시 + 폐기 4종 + Auto-merge KPI + feedback CTA + leaderboard ([원문](_archive/cycle-history-folded-2026-08.md#그룹-6061))
- **사이클 62** — 사이클 62 (2026-05-03)** — cycle-61 v2 sync (#211) + e2e claude-dark 토큰 회귀 + WCAG 2.5.5 모바일 가드 7건 신설 (#212) + 5+1 에이전트 정합성 cleanup (P0 4 + P1 4 처리) + 정책  ([원문](_archive/cycle-history-folded-2026-08.md#사이클-62))
- **사이클 63~64** — 사이클 63** — Phase 3 SaaS 토대 시작 (4/6 PR 머지 #218~#221) — caching 인프라 + insight_narrative service + 라우트/모드 토글 UI + 사용자 신호 default+localStorage. CI fix (py ([원문](_archive/cycle-history-folded-2026-08.md#사이클-6364))
- **사이클 65~67** — 사이클 65~67 (2026-05-04)** — 회고 P1 100% 처리 종결 — 정합성 cleanup P0 12건 (#226 단위 80건 과대 정정 + Phase 3 누락 5건 + 정책 4건) + pre-existing 5 fail 4 사이클 누적 보류 종료 (#22 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-6567))
- **사이클 68~69** — 사이클 68 (2026-05-04)** — 4 사이클 종결 회고 (#232 5 에이전트 + cross-verify 생략 첫 사례 + 메모리 4건 신규/갱신) + 사이클 67 회고 P0 4건 정책 진화 묶음 (#233 정책 7 강화 단일 큰 PR + 정책 8 회고 패턴  ([원문](_archive/cycle-history-folded-2026-08.md#사이클-6869))
- **사이클 70~72** — 사이클 70 (2026-05-04 · #236)** — 사용자 신규 규칙 2건 정책화 — 정책 15 신설 (코드 작업 전 사전 사고) + 정책 16 신설 (코드 단순화 default — 4 원칙) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-7072))
- **사이클 73~74** — 사이클 73 (2026-05-04 · #243)** — 사이클 70~72 종결 회고 + sync 페어 (5 에이전트 + cross-verify 생략 + 메모리 3 신설 + 4 강화) + Code Scanning 6건 dismiss API 자체 처리 (4 used_in_ ([원문](_archive/cycle-history-folded-2026-08.md#사이클-7374))
- **사이클 75~77** — 사이클 75 진입 (#249)** — 사이클 70~74 종결 회고 + sync 페어. 메모리 신설 3건 + 정정 (메모리 카운트 + 단위 카운트 + 정책 16 line:span) ([원문](_archive/cycle-history-folded-2026-08.md#사이클-7577))
- **사이클 78~80** — 사이클 78 (2026-05-05)** — 영역 🅒 Telegram 본격화 (5 사이클 분할 첫 사이클): PR 1 (#253 머지) `feature_kill_switch` helper 모듈 신설 + 기존 2 사용처 마이그레이션 (NEW-P0-2 — Phase 4 5  ([원문](_archive/cycle-history-folded-2026-08.md#사이클-7880))
- **사이클 81** — 사이클 81 (모바일 Phase 1 MVP, 2026-05-05)** — PWA manifest + dashboard 모바일 KPI 우선순위 + settings 모바일 + form sweep (4 PR #262~#265). 통합 84→118 (+34 회귀 가드). `< ([원문](_archive/cycle-history-folded-2026-08.md#사이클-81))
- **사이클 82** — 사이클 82 (Tier B 묶음 + NEW-P0-1, 2026-05-05)** — alembic dialect 헬퍼 추출 (사용처 12) + 메모리 신설 2건 + Telegram 봇 차단 silent skip (NEW-P0-1) (#272/#274). 메모리 25→27 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-82))
- **사이클 83** — 사이클 83 (Tier B 11건 정책 진화 묶음, 2026-05-05)** — 정책 9 완화 + 정책 8 진화 (단일 작업일 ≥ 5 dispatch 사전 확인) + 정책 3 ⚠️ 마커 정량 기준 + 정책 1 진화 + 정책 5 cross-reference 강화 + 메모 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-83))
- **사이클 84** — 사이클 84 (다국어 i18n 18 PR + 회고 + Tier B, 2026-05-05~06)** — Phase 1~5 18 PR (#283~#304) — 영어/한국어/일본어 + UI/알림/AI 리뷰 전 영역. 단위 2236→2709 (+473) | 통합 118→129 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-84))
- **사이클 85~91** — 사이클 85 (Sentry 제거 + GitHub 정리 + CLAUDE.md Anthropic 200줄 정합 정정, 2026-05-06)** — Sentry 통합 완전 폐기 (40 테스트 + 105 LOC + 의존성 제거). GitHub 정리 62 branch 일괄 삭제 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-8591))
- **사이클 92~94** — 사이클 93 (정책 18 신설 — Claude ↔ Codex 양방향 mutual 검증 의무, 2026-05-09 · #362~#371)** — CI 분석 사고 직후 mutual 검증 필요성 확인. 정책 18 신설: Claude 작업(로컬 commit) → Codex 검 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-9294))
- **사이클 95~106** — 사이클 95 (2026-05-14 · #410~#413)** — 문서 정비 P2: testing.md SessionLocal 경고 추가 / architecture.md mockup-polar.html 항목 / AGENTS.md 중복 표 → 링크 3건 / STATE.md ([원문](_archive/cycle-history-folded-2026-08.md#사이클-95106))
- **사이클 107~109** — 사이클 109 (2026-05-19 · #516~#519)** — 전체 페이지 정밀 감사 + P0/P1/P2 14건 수정: **5+1 다중 에이전트 감사** (base.html/repo_detail/repo_insights/dashboard/analysis_detail ([원문](_archive/cycle-history-folded-2026-08.md#사이클-107109))
- **사이클 129** — 사이클 129 (2026-05-28 · #654~#658)** — Lint L-1 언어 확장 + hotfix 3건. **#654** Subagent-Driven Development 10-task 실행. **신규 정적분석기 15종**: hadolint(Dockerfil ([원문](_archive/cycle-history-folded-2026-08.md#사이클-129-1))
- **사이클 128** — 사이클 128 (2026-05-23 · #611)** — 테마 드롭다운 폰트 가시성 버그 수정. 근본 원인: `themes.css`의 `[data-theme="X"]` 셀렉터가 `<body>` 뿐 아니라 `<div class="theme-option" data-them ([원문](_archive/cycle-history-folded-2026-08.md#사이클-128))
- **사이클 127** — 사이클 127 (2026-05-23 · #605~#609)** — hx-boost JS 버그 재발 방지 4-레이어 + E2E 사전 실패 8건 해소. PR #604(사이클 126 이전) `const` 재선언 SyntaxError 사고 학습 → 구조적 대책 4종: **#6 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-127))
- **사이클 126** — 사이클 126 (2026-05-23 · #602)** — 차트 스파크라인 리디자인. 4개 line 차트(dashboard × 2 / repo_detail / analysis_detail) 전면 전환: `pointRadius: 0` (hover 시만 표시) → 포인트 밀 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-126))
- **사이클 125** — 사이클 125 (2026-05-23 · #600)** — 회고 P1/P2 전수 이행. **P1-1**: `src/auth/session.py` `get_current_user` DB 조회 `try/except Exception: return None` 추가 — INT_ ([원문](_archive/cycle-history-folded-2026-08.md#사이클-125))
- **사이클 123** — 사이클 123 (2026-05-23 · #595)** — B+C 작업. **B — P3 보안 심층 테스트**: `test_email.py` `test_build_html_escapes_xss_in_issue_message` 추가 — Telegram 4건 대비 Email ([원문](_archive/cycle-history-folded-2026-08.md#사이클-123))
- **사이클 124** — 사이클 124 (2026-05-23 · #597)** — B+C 작업. B — P3 보안 심층 테스트 2건: `test_session_security.py` `test_get_current_user_with_large_int_user_id_returns_none` (I ([원문](_archive/cycle-history-folded-2026-08.md#사이클-124))
- **사이클 122** — 사이클 122 (2026-05-23 · #593)** — 사이클 121 정책 9 승인 항목 이행. STATE.md 전체 테스트 행 수치 동기화 (3092→3095, 단위 2941→2944, passed 3088→3091) + `*(헤더 = 최신값, 이 셀 = pytes ([원문](_archive/cycle-history-folded-2026-08.md#사이클-122))
- **사이클 121** — 사이클 121 (2026-05-23 · #591)** — 5+1 다중 에이전트 회고 (P0 0건 / P1 1건 / FP 3건 차단). Tier B-1: MEMORY.md 신규 학습 메모리 2건 (kill-switch TDD 패턴 `feedback_kill_switch_ ([원문](_archive/cycle-history-folded-2026-08.md#사이클-121))
- **사이클 120** — 사이클 120 (2026-05-23 · #588~#589)** — 사이클 119 5+1 회고 Tier B 3건 전수 이행. **Tier B-1 (#588)**: `OPERATIONS_DASHBOARD_DISABLED` kill-switch 구현 — `admin.py`에 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-120))
- **사이클 119** — 사이클 119 (2026-05-22 · #586)** — 5+1 다중 에이전트 문서 감사 22건 정확도 수정 (Option C 전수 이행). **P0 7건**: SAAS_MULTITENANT_DISABLED 401→**503** 정정(session.py:82,94 실측 ([원문](_archive/cycle-history-folded-2026-08.md#사이클-119))
- **사이클 118** — 사이클 118 (2026-05-22 · #582~#584)** — 사이클 117/118 회고 P0/P1/P2 전수 이행. **P0-1**: `docs/architecture.md:122` templates 목록 `login` 제거 (login.html 삭제 후 잔존). ([원문](_archive/cycle-history-folded-2026-08.md#사이클-118))
- **사이클 117** — 사이클 117 (2026-05-22 · #565~#580)** — /login 중간 단계 제거 — GitHub OAuth 직행 + 오류 배너 + P0/P1/P2 회고 전수 이행. **핵심 변경**: `/login` 301 redirect → `/auth/github`  ([원문](_archive/cycle-history-folded-2026-08.md#사이클-117))
- **사이클 116** — 사이클 116 (2026-05-21 · #561~#563)** — 사이클 115 5+1 회고 (6 에이전트 병렬) + Tier A/B/C 전수 이행. **회고 결과**: P0 1건 확정 (`--border-color-subtle` 오타) + P0-1 false-posi ([원문](_archive/cycle-history-folded-2026-08.md#사이클-116))
- **사이클 115** — 사이클 115 (2026-05-21 · #555~#560)** — 사이클 114 5+1 회고 P1 3건 + 신규 발견 2건 구현. **#555 (A.1)**: `tests/unit/github_client/test_checks.py` `_classify_check_ru ([원문](_archive/cycle-history-folded-2026-08.md#사이클-115))
- **사이클 114** — 사이클 114 (2026-05-21 · #554)** — 5+1 회고 (6 에이전트 병렬): P0 1건 + P1 6건 + P2 4건 + false-positive 2건. **P0**: STATE.md 테스트 수치 3075 → 실측 3086 (+11 미반영) 정정. ** ([원문](_archive/cycle-history-folded-2026-08.md#사이클-114))
- **사이클 113** — 사이클 113 (2026-05-21 · #542~#553)** — 다중 에이전트(10+1) 전체 코드 정밀 감사 후 P0 버그 10건 전수 수정 + 5+1 회고 + Code Scanning 5 alert 해소. **감사**: B1~B10 에이전트 10회 + CV cro ([원문](_archive/cycle-history-folded-2026-08.md#사이클-113))
- **사이클 112** — 사이클 112 (2026-05-20 · #539~#540)** — 사이클 111 5+1 회고 P1 2건 처리. **docs 수치 sync** (#539): STATE.md 3055→3062, PR #537/#538 이력 추가. **LANG_NAMES DRY 해소 + _ ([원문](_archive/cycle-history-folded-2026-08.md#사이클-112))
- **사이클 110~111** — 사이클 110 (2026-05-19 · #530~#532)** — settings.html AI 리뷰 모델 선택기 카드 위치 변경 (#530). InsightNarrativeCache 에러 빈도 추적 — sdk_error/network_error/parse_error  ([원문](_archive/cycle-history-folded-2026-08.md#사이클-110111))
