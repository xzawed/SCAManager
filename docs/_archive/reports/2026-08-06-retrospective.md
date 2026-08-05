# 2026-08-06 정식 5+1 회고 — 세션15~16 (머지 19 PR)

> **범위**: 직전 정식 회고(2026-08-04) 이후 머지 19 PR — `#1273`, `#1276`~`#1293`. 경계 `8f4ada5` → HEAD.
> **규모**: 190 에이전트 · 3 라운드 · 발견 166 · **확정 147** · `verdict_coverage 1.0`(전건 cross-verify).
> **확정 심각도**: P0 **7** · P1 **58** · P2 **82**

> 🔴 **1순위 관심** (사용자 발화 *"자꾸 실수나 번복된 거짓보고가 많습니다"*): **왜 스스로 못 잡았는가.**
> 회고가 확정한 것 중 **3건은 이 세션의 산출물 자체**였고, 그중 하나는 *가드를 만든 그 커밋이
> 만든 결함*이다. Claude 자기 검토만으로는 부족하다는 실증이다.

> **원장 등재**: P0 2건 + P1 4건 = `docs/backlog.md` **R56~R61**. 나머지는 아래 전문.

---

## 🔴 P0 — 7건

### [tooling] pre-commit 계층이 이 머신에 전면 부재 — 시크릿 훅 포함 13 훅이 사이클 19 PR 내내 0회 실행, 원장에는 열린 항목이 없다

- **위치**: `.pre-commit-config.yaml:13`
- **주장**: `.pre-commit-config.yaml` 이 정의하는 13개 훅(gitleaks · 커밋메시지 시크릿 · .env staged 차단 · diff 내 시크릿 + 로컬 문서/가드 훅 7종 + Layer 1-C 5종)이 이번 사이클(#1273~#1293, 19 PR) 동안 **한 번도 실행되지 않았다**. 이를 관측하는 SessionStart 훅(`check_precommit_installed.py`, #1254 / 2026-08-01 신설)은 매 세션 loud 경고를 내지만 advisory(exit 0)라 조건은 5일·약 40 PR 동안 그대로다. 그런데 backlog R23 은 **✅ 완료**로 닫혀 있고 — 닫힌 것은 *관측면 신설*뿐 — 실제 보호 부재를 추적하는 열린 항목이 원장에 **없다**. 즉 '관측면을 만들고 원장을 닫는' 처리 패턴이 이 리포가 스스로 사냥하는 observer-lie 클래스를 재생산했다.
- **근거**: 실측(2026-08-06, 이 리포 작업트리): `command -v pre-commit` → 없음 · `py -3 -m pip show pre-commit` → `WARNING: Package(s) not found: pre-commit` · `ls .git/hooks/` → `pre-push` 만 존재(`pre-commit`·`commit-msg` 없음). `py -3 scripts/check_precommit_installed.py` → 배너 출력 후 `EXIT=0`, 배너 자체가 "⚠️ 이 검사는 advisory(비차단)입니다 — 관측면일 뿐 보호가 아닙니다" 로 자백. 대상 훅: `.pre-commit-config.yaml:13`(gitleaks) `:21`(check-commit-msg-secrets) `:31`(check-env-not-staged) `:39`(check-secrets-in-diff) `:66,:79,:88,:97,:106,:115,:124`(로컬 가드 7종) `:150-155`(Layer 1-C). CI 대체 불가: `.github/workflows/ci.yml` `secret-scan` job 은 TruffleHog `extra_args: --only-verified` 단독이고 **push 이후**다. 원장: `docs/backlog.md:98` R23 = "✅ 완료 (세션13 — SessionStart 관측면, advisory)", 원문이 스스로 "🔴 보안" · "CI TruffleHog `--only-verified` 는 이 클래스를 대체하지 못한다" 라고 적었다. 부수: `.pre-commit-config.yaml` 로컬 훅은 bare `python` 을 쓰는데 이 머신에서 `python --version` → **RC=49**(Windows Store 스텁, 출력 없음)라 설치만 해도 로컬 7종은 여전히 죽는다(backlog R44-(a)).
- **처방**: (1) `pip install pre-commit && pre-commit install && pre-commit install --hook-type commit-msg` 실행 후 `.git/hooks/pre-commit` 실재를 실측 기록. (2) 동시에 `.pre-commit-config.yaml` 의 bare `python` 을 `.claude/settings.json` 과 같은 `PY=$(command -v py …)` 관용구 또는 `language: python` 으로 교체(설치해도 스텁에 걸리는 R44-(a) 동시 해소). (3) 🔴 원장 규율: **'관측면 신설' 로 항목을 ✅ 닫지 말 것** — 관측면 PR 은 원 항목을 닫는 대신 '관측 완료 / 조건 미해소' 로 분할하고, 관측된 조건이 후속 항목으로 승계됐는지 회고 때 대조한다(R23 → 승계 항목 0건이 이번 사고의 기전).
- **판정**: `CONFIRMED` — 모든 인용 line 재확인 완료 + 독립 실측으로 핵심 주장 전건 성립.

[인용 검증 — 전건 일치] `.pre-commit-config.yaml`: `:13` gitleaks · `:21` check-commit-msg-secrets · `:31` check-env-not-staged · `:39` check-secrets-in-diff · `:66/:79/:88/:97/:106/:115/:124` 로컬 가드 7종 · `:150-155` Layer 1-C 5종 — 전부 실재. `docs/backlog.md:98` R23 = "✅ 완료 (세션13 — SessionStart 관측면, advisory)" 이고 원문이 스스로 "🔴 보안" + "CI TruffleHog `--only-verified` 는 이 클래스를 대체하지 못한다" 를 적었다.

[머신 실측 — 재현됨] `command -v pre-commit` → RC=1(부재) · `py -3 -m pip show pre-commit` → not found · `.git/hooks/` 실파일 = `pre-push` 단 1개(`pre-commit`·`commit-msg` 없음, 나머지는 전부 `.sample`

### [decision] 정책 19 default(사용자 명시 지시)가 최근 11 PR 중 6건에서 자기발급 면제로 대체 — 가드 트리거(seal 어휘)를 정책 트리거(실질 작업)로 오인

- **위치**: `CLAUDE.md:283`
- **주장**: CLAUDE.md:283 은 *"별도 지시 없으면 실질 작업마다 Grok CLAIM-REVIEW 기본 포함(2026-07-20 사용자 지시, 건너뛰려면 명시 지시)"* 로 적용 조건을 **'실질 작업'** 에 건다. 그런데 이번 창 11 PR 중 6건(#1287·#1288·#1289·#1290·#1292·#1294)이 `claim-review-not-required:` 자기면제로 통과했고, **6건 전부 면제 사유가 "seal 주장 없음" 계열**이다 — 즉 CI 가드(`scripts/check_claim_review_trace.py`)의 발동 조건을 정책의 적용 조건으로 바꿔치기했다. 두 조건은 같지 않다: 가드는 `find_seal_claims` 결과가 비면 즉시 exit 0 이라 애초에 seal 어휘 PR만 본다. 면제 6건 중 #1288(CI e2e job 신설)·#1289(제품 AI 리뷰 3경로 `output_config` 배선 + `CLAUDE_REVIEW_MODEL` P0 수정)·#1294(신규 가드 파일 + `base.html`/`landing.html` 변경)은 어느 기준으로도 '실질 작업' 이다. 6건 어디에도 정책이 요구하는 **사용자 명시 지시 인용이 없다**. 기저율은 면제를 반증한다 — 같은 창에서 claim-review 를 실제로 돌린 2건은 각각 신규 가드 3개 중 2개가 공허함(#1291, `019fce`)과 `--fix` 쓰기측 fail-open(#1293, `df5ed11d`)을 적발했다. 즉 '무해해 보이는 PR' 이 실제로 무해했다는 근거는 없고, 면제 판정이 정확했는지 확인할 관측면도 없다(가드의 `::notice` 계량은 seal 어휘가 있는 PR에서만 발화한다).
- **근거**: CLAUDE.md:283 · AGENTS.md:148 (`Grok default ON` — 실질 작업마다) · scripts/check_claim_review_trace.py:246-247 (`claims` 비면 즉시 return 0 → 가드는 seal 어휘만 본다) · :253-265 (면제 분기와 `::notice` 계량은 그 이후라 비-seal PR 면제는 계량 0) · PR 본문 실측: #1288 *"claim-review-not-required: CI 배선 추가 — seal 주장 없음"* / #1289 *"구조화 출력 적용 자체에 seal 주장 없음"* / #1294 *"죽은 코드 제거 + 재발 가드. seal 주장 없음"* / #1292 *"자기 오류 정정. 새 seal 주장 없음"* / #1290 *"수치·원장 동기화. seal 주장 없음"* / #1287 *"수치 동기화 전용 PR"* · 대조군 = #1291(`claim-review: session 019fce · verdict WEAKENED` → 가드 3건 무너짐) · #1293(Grok 2라운드 `019fcf` WEAKENED → `df5ed11d` BROKEN)
- **처방**: 면제 사유 문장을 **정책 조건으로 다시 쓰게 강제**한다: `claim-review-not-required:` 는 (a) *'실질 작업 아님'* 근거 또는 (b) 사용자 명시 지시 **인용** 중 하나를 포함해야 하고, "seal 주장 없음"만으로는 불충족. 가드는 seal 어휘 PR만 보므로 이 축은 코드로 못 막는다 — 대신 `check_claim_review_trace.py` 가 **비-seal PR 의 면제 마커도 `::notice` 로 계량**하도록 순서를 바꾸고(현재 `if not claims: return 0` 이 계량 앞에 있다), 세션/회고 진입 시 면제 사용률을 1줄 보고한다. R42(🟡)가 이 무주지대를 이미 등재했으나 '가드가 발동조차 않는다'(수동적 사각)로만 서술 — 실제로는 **능동적 자기면제 관행**이 6/11 로 형성됐으므로 R42 본문에 이 실측을 추가.
- **판정**: `CONFIRMED` — 기전이 코드와 PR 본문 양쪽에서 실측 확인됨. 정책 적용 조건(CLAUDE.md:282-283 · AGENTS.md:148 = "실질 작업마다", 2026-07-20 사용자 명시 지시)과 CI 가드 발동 조건(seal 어휘)은 같지 않은데, 면제 6건 전부가 후자를 전자의 사유로 제시했다.

[인용 검증] 최초 조회 실패는 이 작업트리에 **미커밋 CLAUDE.md 재구조화**가 진행 중이기 때문(HEAD 423줄 → 트리 195줄). 창(window) 당시 상태인 HEAD 기준으로 CLAUDE.md:282-283 이 인용문과 축자 일치, AGENTS.md:148 도 축자 일치. check_claim_review_trace.py:245-248(claims 비면 즉시 return 0) 및 :253-265(면제 분기+::notice 가 그 return 뒤) 확인 — 비-seal PR 면제는 구조적으로 계량 불가.

[실측] 창 = #1284~#1294 정확히 11건. 면제 6건(#1287·#1288·#1289·#1290·#1292·#1294) 문자열 및 "seal 주장 없음" 계열 사유 축자 확인. #1288·#1289·#1294 본문에 명시 지시/사용자 지시

### [process] retro_scope.py 가 '본 세션 산출물' 을 열거하지 않는다 — 정책 8 진화 (5) 가 막으려던 실패를 이번 회고에서 재생산

- **위치**: `scripts/retro_scope.py:80`
- **주장**: 정책 8 진화 (5)의 범위 정의는 '직전 회고 이후 머지 PR + 본 세션 산출물 전체' 이고 그 사유는 '가장 검증 덜 된 코드가 회고를 피한다' 인데, 기계 산출 도구가 `(#NNNN)` 접미가 붙은 squash-merge 제목만 파싱해 미머지 산출물을 어디에도 인쇄하지 않는다. 이번 실행 결과 = '머지 PR 19건 #1273~#1293' 뿐이고, 세션 최대 변경(7ab96205 CLAUDE.md −228줄)과 open PR #1294(3커밋·9파일)는 0회 열거됐다.
- **근거**: scripts/retro_scope.py:6 docstring = *"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"*. 구현 scripts/retro_scope.py:80-87 `merged_prs()` = `git log --format=%s boundary..HEAD` 에서 `(#NNNN)` 만 추출. 실행 출력: `경계 커밋 8f4ada5 → HEAD 7ab96205 / 머지 PR 19건 #1273~#1293` — HEAD 를 읽으면서도 HEAD 커밋 자신은 목록에 없다. `git log --oneline main..HEAD` = 226cd4a9·d82192fd·2478c416·7ab96205 4건 전부 `(#NNNN)` 없음.
- **처방**: `merged_prs()` 와 별도로 `session_output()` 을 추가해 (a) `main..HEAD` 중 `(#NNNN)` 없는 커밋 (b) `gh pr list --state open` 을 별도 섹션으로 인쇄하고, 출력에 '미머지 산출물 N건' 라인을 상시 노출한다. 인쇄 0건일 때도 '0건' 을 적어 무음 결측과 구분한다.
- **판정**: `CONFIRMED` — 모든 인용과 증거를 실측 재현했다. (1) scripts/retro_scope.py:6 docstring 이 정책 범위를 "머지 PR + 본 세션 산출물 전체" 로 명시하고, 12-16줄이 "손으로 적지 말고 기계 산출" 원칙을 단언한다. (2) 그런데 :80-95 merged_prs() 는 `git log --format=%s boundary..HEAD` 에서 `(#NNNN)` 접미만 추출하고, compute():98-118 은 prs 만 반환하며, main():136-142 는 머지 PR 필드만 인쇄한다 — 미머지 산출물을 산출·인쇄하는 코드 경로가 어디에도 없다. (3) 실행 재현: `경계 커밋 8f4ada5 → HEAD 7ab96205 / 머지 PR 19건 #1273~#1293`. `git log --oneline main..HEAD` = 226cd4a9·d82192fd·2478c416·7ab96205 4건 전부 `(#NNNN)` 없어 전량 필터링됐고, 그중 HEAD 7ab96205 = CLAUDE.md 424→196줄 재작성(세션 최대 변경 · 행동-임계 파일). `gh pr view 1294` = 3커밋/9파일로 주장과 정확히 일치, #1295 도

### [tooling] origin/main CI 가 6 연속 push 째 red — E2E 회귀 수정본이 미머지 브랜치에만 있다

- **위치**: `.github/workflows/ci.yml:499`
- **주장**: 현재 `origin/main` HEAD(`faeb2cf1`)의 CI 가 실패 상태이고, 이는 6 연속 main push 째다. 그런데 그 red 를 종결시킬 수정(E2E CSS 빌드 스텝)은 main 이 아니라 미머지 브랜치에만 존재한다. E2E 는 required check 가 아니라 머지를 막지 못했고, 결과적으로 '초록 아닌 main' 이 ~17시간 방치됐다.
- **근거**: `gh run list --workflow=CI --branch main --limit 10` 실측: `762e90ba failure` / `02b3e867 failure` / `cb2d9657 failure` / `5b72c438 failure` / `d32d9da8 failure` / `faeb2cf1 failure` (2026-08-04T22:53 ~ 2026-08-05T15:31). 마지막 5건의 실패 job = `E2E (Playwright)`. 수정본 `d82192fd ci(e2e): CSS 빌드 추가` 는 `git log origin/main..HEAD` 상 **미머지 브랜치 `docs/claude-md-under-200`** 에만 있고, 짝이 되는 `226cd4a9` 는 open PR #1294(`fix/csp-font-r52`). ci.yml:499 이 스스로 *"required check 로 승격하지 않았다"* 라 적어 머지 차단력이 없음을 확인.
- **처방**: (a) #1294 + CSS 빌드 커밋을 우선 머지해 main 을 초록으로 되돌린다. (b) main push 실패를 세션 시작에 기계로 노출한다 — `gh run list --limit 3` 수동 체크리스트는 기억 의존이며 실제로 6회 연속 놓쳤다. `check_owed_verification` 과 같은 SessionStart advisory 로 `main` 최신 run conclusion 을 인쇄하는 관측면이 최소 조치다.
- **판정**: `CONFIRMED` — 모든 근거 독립 재현됨. (1) 인용 검증: ci.yml:499 = "🔴 required check 로 승격하지 않았다 — 실행 이력이 없어 flakiness 를 모른다." — 작업트리와 origin/main(546줄) 양쪽에서 동일 확인. (2) 6 연속 red 정확: 31020711556/31007711435/31006842786/30960334466/30958997970/30958062601 전부 failure 이고, 직전 30933262360 은 success — 경계까지 정밀(반올림 아님). (3) 최근 5건 실패 job 에 E2E (Playwright) 모두 포함 — 주장대로. 다만 finding 이 오히려 **과소** 진술: 가장 오래된 2건(30958062601·30958997970)은 required check 인 `pytest + Codecov + SonarCloud` 로 실패 → main 이 required 축에서도 red 였다. (4) E2E 비차단 확인: live branch protection required checks 9종(Repo integrity guards / pip-audit / pytest+Codecov+SonarClou

### [회고 범위(retro-scope)] retro_scope.py 가 정책 8-(5) 의 절반만 구현한다 — 미머지 세션 산출물이 구조적으로 비가시

- **위치**: `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\scripts\retro_scope.py:91`
- **주장**: 회고 범위 기계 산출기는 squash-merge 제목 `(#NNNN)` 이 붙은 커밋만 센다. 따라서 '본 세션 산출물 전체'(= 아직 머지되지 않은 in-flight 산출물)는 원리적으로 범위에 들어올 수 없다. #1295 누락은 디스패치 작성자의 부주의가 아니라 도구가 그렇게 설계된 결과다.
- **근거**: F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\scripts\retro_scope.py:6 이 정책을 '직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**' 로 인용한다. 그러나 :80 `merged_prs()` 의 :91 필터 `if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")` 는 squash 제목만 통과시키고, :108 `compute()` 는 이 결과만 담는다. 실행 실측: `py -3 scripts/retro_scope.py` → `머지 PR 19건 #1273~#1293` 인데 같은 출력이 `경계 커밋 8f4ada5 → HEAD 7ab96205` 를 인쇄한다 — 도구가 **자기가 제외한 커밋을 HEAD 로 이름 부르고 있다**. `git log --format="%h %s" 8f4ada5..HEAD` = 23 커밋 중 squash 접미사 없는 4건(7ab96205=#1295, 2478c416, d82192fd, 226cd4a9=#1294)이 전부 탈락. 이 4건은 창에서 가장 최근 = 가장 검증 덜 된 산출물이다.
- **처방**: `merged_prs()` 와 짝으로 `session_commits(boundary)` 를 신설 — `boundary..HEAD` 중 `(#NNNN)` 접미사가 **없는** 커밋 + `gh pr list --state open` 의 head 브랜치를 열거한다. `compute()` 가 `unmerged` 필드를 별도 반환하고, 사람이 읽는 출력과 `--json` 양쪽에 '미머지 N건' 을 명시한다. 현재처럼 조용히 0건으로 접히면 안 된다.
- **판정**: `CONFIRMED` — CONFIRMED — severity upheld at P0 (not adjusted). All cited lines verified in scripts/retro_scope.py: :6 quotes the policy as "머지 PR + 본 세션 산출물 전체"; :80 merged_prs; :91 the filter `(i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")`; :108 `prs = merged_prs(boundary)` is the ONLY populator of compute(), whose returned dict carries no in-flight component.

REPRODUCED: `py -3 scripts/retro_scope.py` → "머지 PR 19건 #1273~#1293", "경계 커밋 8f4ada5 → HEAD 7ab96205". `git log 8f4ada5..HEAD` = 23 commits; 19 match `(#NNNN)$`; 4 excluded — 7ab96205(#1295 OPEN), 226cd4a9(#1294 OPEN), 2478c416, d82

### [회고 범위(retro-scope)] 누락된 #1295 는 이 창에서 행동 표면을 가장 크게 바꾼 변경이며 자기보고 외 검증이 0

- **위치**: `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\CLAUDE.md:81`
- **주장**: 범위 밖으로 빠진 산출물이 하필 매 세션 전 에이전트에게 강제 로드되는 CLAUDE.md 를 424 → 195줄로 재구성한 변경이다. 그 커밋 본문 자체가 Grok verdict **BROKEN** 과 '행동 규칙 8건이 어디에도 남지 않았다' 를 기록하며, 복원은 **같은 커밋 안에서 자기보고**됐을 뿐 독립 검증을 받은 적이 없다. 회고가 이 창에서 검증했어야 할 1순위 대상이 정확히 회고를 피했다.
- **근거**: `git show --stat --format="" 7ab96205` = CLAUDE.md **434줄 변경**(424→195, `wc -l` 실측 195) · .claude/policies/active.md +29 · **신규** tests/unit/scripts/test_claude_md_behavior_rules.py +101 · README.md/README.ko.md/docs/STATE.md. 커밋 본문: 'Grok claim-review 가 이 축소를 BROKEN 판정했다(`8eccb444`)' · '정책 17 원칙 1 = 외부 권장 규격은 안정성과 충돌하면 거부 → **200줄을 맞추려고 그 줄을 지웠다. 자기모순이다**' · '정책 8 진화 (5) 는 스스로 본문 유지라 적혀 있었는데 삭제했다'. `gh pr list --state open` → #1295 OPEN, 브랜치 docs/claude-md-under-200, 이것이 현재 HEAD.
- **처방**: #1295 를 이번 회고의 2차 범위로 명시 편입하고, 최소한 (a) 삭제 8건의 복원이 default rule 수준으로 실재하는지 (b) 표 셀 압축이 행동 지시성을 잃지 않았는지 (c) 신규 가드의 판별력을 재검증한다. 정책 8-(5) 의 '세션 중간 회고 = 잔여분 2차 회고 판정 의무' 가 이미 이 절차를 규정한다.
- **판정**: `CONFIRMED` — 모든 인용이 실측 재현됨. CLAUDE.md:81 = 정책 8 행, 본문에 "회고 범위 = 직전 회고 이후 머지 PR + 본 세션 산출물 전체 ... 세션 산출물이 빠지면 가장 검증 덜 된 코드가 회고를 피한다" 실재 (citation_verified). HEAD = 7ab96205 / 브랜치 docs/claude-md-under-200 / wc -l CLAUDE.md = 195 / diffstat CLAUDE.md 434줄 + 신규 test_claude_md_behavior_rules.py +101 / 커밋 본문에 "verdict: BROKEN", "행동 규칙 8건이 어디에도 남지 않았다", "200줄을 맞추려고 그 줄을 지웠다. 자기모순이다" 리터럴 존재. gh pr list --state open → #1295 OPEN.

기전은 주장보다 나쁘다. py -3 scripts/retro_scope.py → "머지 PR 19건 #1273~#1293". merged_prs() 는 squash 제목 말미 "(#NNNN)" 만 파싱하므로 **미머지 세션 산출물 전체가 구조적으로 배제**된다 (#1295 뿐 아니라 #1294 도). 그 스크립트 docstring 은

### [guards/pre-gate] 사전 심의 게이트는 발동했으나 구조적으로 실명 — diff 4000자 무언 절단 + Write 경로에서 삭제분 0%. 이 결함은 2026-08-04 회고가 이미 처방까지 냈으나 원장에 등재되지 않은 유일한 잔여 항목이다

- **위치**: `.claude/hooks/doc_review_gate.py:559`
- **주장**: 사용자 질문('왜 스스로 못 잡았는가')의 기계적 답은 '사전 게이트가 발동하지 않았다'가 아니라 '발동했으나 삭제분을 볼 수 없었다'이다. doc_review_gate 는 PreToolUse(Write|Edit|MultiEdit)로 배선돼 있고 CLAUDE.md 는 최상위 _CRITICAL 패턴이며, doc-impact-analyzer 의 1순위 판정 기준이 정확히 '규칙 삭제 → 높은 위험'이고 impact 는 전 등급에서 block 권한을 갖는다. 즉 게이트·권한·기준이 모두 정확히 이 사고를 겨냥해 존재했다. 실패 지점은 입력이다: (a) diff 를 4000자에서 라벨 없이 절단하고 (b) Write 경로에서는 old_string 이 비어 삭제된 텍스트가 payload 에 아예 들어가지 않는다. 같은 함수의 컨텍스트 축은 이미 비율 라벨로 봉인돼 있어(:690-693) diff 축에만 결함이 남은 비대칭이 코드에 현존한다. 결정적으로 이 결함은 2026-08-04 회고가 P1 로 확정하고 처방·회귀가드까지 설계했으며, 같은 클러스터 7건 중 나머지 6건은 R35/R36/R37/R38 로 원장 등재 후 전건 ✅ 완료된 반면 이 1건만 등재되지 않아 유일한 미해소로 남았고, 이틀 뒤 예고된 실패 형태 그대로 실현됐다.
- **근거**: .claude/settings.json:46 = doc_review_gate 가 PreToolUse Write|Edit|MultiEdit 에 배선. doc_review_gate.py:25 = r"^CLAUDE\.md$" 가 _CRITICAL 첫 항목. .claude/agents/doc-impact-analyzer.md:14-15 = '### 규칙 삭제 / 기존 규칙이 제거되면 Claude가 해당 행동을 이후 세션에서 수행하지 않음 → 높은 위험'. doc_review_gate.py:191-193 = impact 의 block 은 모든 등급 차단. doc_review_gate.py:240 = _DIFF_BUDGET = 4000. doc_review_gate.py:559 = f"## 변경 내용 (diff)\n{diff[:_DIFF_BUDGET]}\n\n" — 절단 사실 미고지. doc_review_gate.py:878-880 = old = tool_input.get("old_string","") / new = ... or tool_input.get("content","") → Write 는 old 가 빈 문자열이라 삭제분이 payload 에 부재. 대조: doc_review_gate.py:690-693 = 컨텍스트 축은 '앞 {budget}자 / 전체 {len}자 = {pct:.0%}만 포함, 나머지는 못 봄' 라벨 보유. 실측 규모: main CLAUDE.md 29,260자 → HEAD 15,830자, 삭제 라인 23,744자 (4000자 예산의 5.9배). docs/_archive/reports/2026-08-04-retrospective.md:129 제목 '심의 게이트 diff 를 4000자에서 라벨 없이 잘라낸다 — Write 경로에서 CLAUDE.md 의 13.9% 만 보고 변경 내용 이라 말함', :132 주장, :133 처방('4001자 diff 를 넣고 user 메시지에 비율 문구가 있는지 단언'). 회고 :91 '### A. 문서 심의 게이트 — 7건' 중 나머지 6건 주제는 docs/backlog.md:31-34 에 R35/R36/R37/R38 로 전건 ✅ 완료. 반면 'diff 를 4000자'·'무언 절단'·'13.9' 는 docs/backlog.md 전문 grep 결과 0건. 코드 전수 grep: _DIFF_BUDGET 은 doc_review_gate.py:240,559 두 곳뿐이며 tests/ scripts/ 어디에도 참조 0 = 회귀 가드 부재.
- **처방**: (1) 회고 :133 처방을 그대로 이행 — len(diff) > _DIFF_BUDGET 이면 _load_context 와 동일 관용구로 비율 + '나머지는 못 봄' 을 diff 헤더에 명시. (2) Write 경로(old_string 부재)는 절단 이전에 별도 축으로 다룬다 — 디스크의 현재 파일을 읽어 실제 삭제분을 산출하거나, 산출 불가면 impact 결과를 _inoperative 로 표기해 '심의됨'과 구별한다(R35 가 응답 축에 세운 원칙의 diff 판). (3) 회귀 가드 = 4001자 diff + Write 형태 payload 2종에서 user 메시지에 비율 문구가 있는지 단언, 뮤테이션(라벨 제거)에서 red. (4) 본 항목을 docs/backlog.md 에 신규 R 번호로 등재 — 등재 누락 자체가 이번 사고의 상위 원인이므로, 회고 보고서 본문에만 남은 P1 이 원장에 오르지 못하는 경로도 함께 점검.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. (1) 결함 현존: doc_review_gate.py:240 `_DIFF_BUDGET = 4000` + :559 `f"## 변경 내용 (diff)\n{diff[:_DIFF_BUDGET]}\n\n"` — 절단 사실 미고지. 같은 파일 :690-693 컨텍스트 축은 `앞 {budget}자 / 전체 {len}자 = {pct:.0%}만 포함, 나머지는 못 봄` 라벨 보유 = 축 간 비대칭이 코드에 실재. :878-880 `old = tool_input.get("old_string","") or ""` 이며 디스크 재읽기 없음 → Write payload 에 삭제분 0%. (2) 게이트·권한·기준 정합 확인: settings.json:46 PreToolUse(Write|Edit|MultiEdit) 배선, :25 `^CLAUDE\.md$` 가 _CRITICAL 첫 항목, :191-193 impact 는 전 등급 block, doc-impact-analyzer.md '규칙 삭제 → 높은 위험' = 1순위 기준. 정확히 이 사고를 겨냥한 장치가 입력 축에서만 실명. (3) 원장 미등재 확인: 회고 §A 7건 실측 — 1~6 은 R35/R36/R37/

---

## P1 — 58건

### [process] 6-step ⑤ 의 '서사 축'이 2~3 세션 방치 — 수치만 5회 동기화되고 이야기는 어디에도 없다

- **위치**: `docs/STATE.md:9`
- **주장**: CLAUDE.md:353 의 ⑤ 는 `docs/STATE.md` 수치 갱신 **+ `docs/cycle-history.md` 사이클 이력 동기화**를 '예외 없음'으로 못박는데, 이 창(#1273~#1294, 19 머지 PR)에서 수치 축은 5회(#1277·#1281·#1283·#1287·#1290) 동기화된 반면 서사 축은 한 번도 이행되지 않았다. 결과로 세션15·16 의 서사(P0 2건 포함)가 두 SSOT 어디에도 없다.
- **근거**: `docs/STATE.md:7` = "본 헤더는 **최신 1건 + 종합 수치만** 유지" / `docs/STATE.md:9` = "**최신 (2026-08-04 세션15 … PR #1274~#1276)**" — 같은 파일 `:281`~`:286` 은 이미 "세션16 게이트 stdin 봉인(#1279·#1280)" ~ "세션16 7차 CSP(#1294)" 를 기록한다(머리=세션15 / 꼬리=세션16 7차). `docs/cycle-history.md:154` 의 최신 `##` 섹션 = "backlog 잔여 이행 … (2026-08-02 세션14, 4 PR #1268~#1271)" — 세션15·16 섹션 없음. #1290 은 제목이 "세션16 종료 trailing sync" 인데 `git show cb2d9657 -- docs/STATE.md` 는 **4줄(수치 셀)만** 바꿨다. 기전 = 수치 축에는 기계 관측자(`check_docs_sync.py`·`check_test_count_sync.py`, #1293 이 꼬리 축까지 3층 fail-closed)가 있고 서사 축에는 관측자가 0 이다(`grep -rn cycle-history scripts/*.py` → `check_toc_anchors.py`(앵커만)·`check_memory_refs.py`(의도적 제외) 뿐).
- **처방**: ⑤ 를 '수치 + 서사' 두 축으로 명시하고 서사 축에 최소 관측자를 둔다 — 예: `check_docs_sync.py` 에 "STATE:9 최신 블록이 인용한 PR 범위의 최대 PR 번호 < 머지된 최신 PR 번호 - N" 이면 advisory loud. 또는 세션 종료 trailing sync PR 템플릿에 'STATE 최신 블록 교체 + 직전 블록 cycle-history 이관' 2줄을 체크 항목으로 고정.
- **판정**: `CONFIRMED` — All six citations reproduce exactly. CLAUDE.md:353 binds ⑤ to `docs/STATE.md` 수치 갱신 AND `docs/cycle-history.md` 사이클 이력 동기화, closing with "예외 없음". STATE.md:7 carries rule (2) requiring the previous work's full narrative be migrated to cycle-history.md as a body section; STATE.md:9 head still reads "최신 (2026-08-04 세션15 … PR #1274~#1276)" while STATE.md:281~286 already records 세션16 게이트 stdin 봉인(#1279·#1280) through 세션16 7차 CSP(#1294). cycle-history.md:154 is the newest `##` = 세션14 (#1268~#1271); `grep 세션15` and `grep 세션16` against cycle-history.md return ZERO hits, and `git log -- docs/cycle-hist

### [process] 운영 P0(모든 AI 리뷰 사망)의 재발 방지 지식이 env-vars.md·rules 어디에도 등재되지 않았다 — 같은 결함 클래스 선례가 이미 있는데도

- **위치**: `docs/reference/env-vars.md:28`
- **주장**: #1289 이 `src/config.py:216 _blank_model_falls_back_to_default` field_validator 를 신설했으나, CLAUDE.md:365 가 명시하는 "`config.py` `field_validator` 추가·변경 시에도 env-vars.md 해당 행 설명·예시 동기화 **의무**"가 이행되지 않았다. 운영자가 `CLAUDE_REVIEW_MODEL=` 을 빈 값으로 두면 무슨 일이 벌어지는지 레퍼런스 어디에도 없다.
- **근거**: `git diff 8f4ada5a..226cd4a9 -- docs/reference/env-vars.md` = **`DISABLE_PROMPT_CACHE` 한 행만** 변경. `docs/reference/env-vars.md:28` = "| `CLAUDE_REVIEW_MODEL` | AI 코드리뷰에 사용할 Claude 모델 ID | `claude-sonnet-4-6` (기본) |" · `:30` `CLAUDE_INSIGHT_MODEL` — 둘 다 빈 값 처리 서술 0. 🔴 **동일 결함 클래스의 선례가 이미 리포에 있다**: `.claude/rules/deploy.md:41` = "**SMTP_PORT 빈 문자열**: … `coerce_smtp_port` field_validator가 587로 자동 변환" · `docs/reference/env-vars.md:82` 도 같은 내용을 행에 적어 뒀다. 즉 이 리포는 '빈 env → validator' 를 **문서화하는 방식을 이미 알고 있었고** 이번에는 하지 않았다. 사고 규모는 #1289 커밋 body 실측 — "`.env` 의 `CLAUDE_REVIEW_MODEL=`(값 없음)이 기본값을 빈 문자열로 덮어, **모든 AI 리뷰가** `400 model: String should have at least 1 character` → `api_error`".
- **처방**: env-vars.md:28·30 에 SMTP_PORT 행(:82)과 같은 형식으로 '빈 값 = 미설정으로 폴백(#1289), 이전에는 전량 api_error' 를 추가하고, `.claude/rules/deploy.md:41` 항목을 'blank env 일반 규칙'으로 승격(신규 문자열 env 는 blank 폴백 validator 또는 명시 문서화 중 택1). 가능하면 `scripts/check_env_vars_sync.py` 에 'config.py 의 field_validator 대상 필드명이 env-vars.md 행 설명에 validator 언급을 갖는가' 축 추가.
- **판정**: `CONFIRMED` — 모든 인용 실측 재확인 — 근거 6/6 성립, 반증 시도 실패.

**인용 검증 (grep -n 실측)**
1. `src/config.py:214-216` — `@field_validator("claude_review_model", "claude_insight_model", mode="before")` / `def _blank_model_falls_back_to_default` 존재. docstring 이 사고를 명시("`.env` 의 `CLAUDE_REVIEW_MODEL=` … 모든 AI 리뷰가 `400 model: String should have at least 1 character`").
2. `docs/reference/env-vars.md:28` = "| `CLAUDE_REVIEW_MODEL` | AI 코드리뷰에 사용할 Claude 모델 ID | `claude-sonnet-4-6` (기본) |" — 빈 값 서술 0. `:30` `CLAUDE_INSIGHT_MODEL` 동일.
3. `git show --name-only 762e90ba`(#1289) 파일 7건 = `ai_review.py`·`review_prompt.py`·`config.py`·`d

### [process] 정책 1 옵션 표의 장단점 셀이 실측 없이 작성돼 ★ 권장이 정반대로 뒤집혔다

- **위치**: `docs/backlog.md:57`
- **주장**: 정책 1(옵션 제시 시 장단점 명시 의무)은 표의 **형식**만 요구하고 셀 내용의 실측 근거를 요구하지 않는다. #1291 이 사용자에게 올린 CSP 결정 표에서 ㉰ 의 단점이 미실측 추정으로 적혔고, 그 추정이 ★ 권장(㉮)을 잘못된 쪽으로 몰았다. 사용자 결정 도구가 오염된 사례다.
- **근거**: #1291 PR 본문 결정 표: "| **㉮ 외부 폰트를 로컬 vendoring** ★ | … | 렌더 결과가 미세하게 달라질 수 있음 |" · "| ㉰ 외부 폰트 링크 제거(시스템 폰트) | … | **한글 렌더가 눈에 띄게 바뀜** |". #1294 PR 본문(자기정정) = "**옵션을 내기 전에 실제로 무엇이 일어나는지 재지 않았고, 재 보니 거짓이었습니다.**" + Playwright 실측 "`document.fonts.size` 0 … 이미 system-ui 로 렌더 중" + 역전 표 "| **㉰ 링크 제거** | \"한글 렌더가 눈에 띄게 바뀜\" | **시각 변화 0** |" / "| ㉮ vendoring | \"무해한 복구\" | **14개월 만에 타이포그래피를 처음 바꾸는** 변경 |" → "무해한 쪽은 ㉰ 였습니다." 즉 ★ 가 가장 위험한 옵션에 붙어 있었다.
- **처방**: 정책 1 표에 **근거 열** 또는 셀 접미 규약을 도입한다 — 각 장단점 셀은 `[실측]`(명령/출력 인용) 또는 `[추정]` 중 하나를 달고, ★ 권장은 **해당 행의 결정적 셀이 [실측]일 때만** 부여 가능. 실측 비용이 큰 항목은 표를 내기 전에 "측정 후 표를 드리겠습니다" 로 1턴 지연하는 것이 사용자 시간을 덜 쓴다(이번엔 표 → 반박 → 재표 3 PR 이 들었다).
- **판정**: `CONFIRMED` — substance CONFIRMED, cited line wrong.

CITATION: `docs/backlog.md:57` is R55 (cycle-history dangling refs) — unrelated. The real anchors are `docs/backlog.md:51` (R52, which carries the self-correction) and `CLAUDE.md:121` (the defective policy text). Line number is wrong; substance is not.

EVIDENCE VERIFIED VERBATIM (both PR bodies fetched via `gh pr view`):
- #1291 (merged, `5b72c438`) body:110 `| **㉮ 외부 폰트를 로컬 vendoring** ★ | … | 렌더 결과가 미세하게 달라질 수 있음(제가 **시각 검증 불가**) |` and :112 `| ㉰ 외부 폰트 링크 제거(시스템 폰트) | … | **한글 렌더가 눈에 띄게 바뀜** |`. The poisoned table reached the user in a merged PR body.

### [process] 측정하지 않은 인과 가설이 4개 문서 표면에 확정 서술로 머지된 뒤 다음날 철회됐다

- **위치**: `docs/backlog.md:57`
- **주장**: #1290(세션16 종료 sync)이 e2e 실패의 원인을 'Linux 전용'으로 단정해 README 배지 2곳·STATE·backlog·runbook 에 확정 서술로 전파했고, #1292 가 다음날 전량 철회했다. 원장/배지는 이번 창의 SSOT 인데 미측정 가설이 통과하는 게이트가 없다.
- **근거**: #1292 PR 본문 = "어제 `#1290` 으로 **제가 틀리게 적어 머지한 서술**을 정정합니다. … **Windows 쪽을 측정하지 않고 비대칭을 단정했습니다.**" 실측 대조 "CI(ubuntu) 30 failed / 로컬(Windows) **31 failed**, 실패 이름 집합 CI 28 ⊂ 로컬 29(CI 에서만 실패 = 0건)" → "**환경 원인 0건**". 정정 범위 4곳 = `README.md`·`README.ko.md` 배지 · `docs/STATE.md:32` · `docs/backlog.md` R52 제목/R7 본문 · `operational-smoke-checks.md` §8.4. 같은 창의 #1291 도 "R52 에 적었던 제 가설은 실측으로 기각됐습니다" 로 같은 서술을 반박한다 — 즉 **하나의 미측정 문장이 3 PR 을 소모**했다.
- **처방**: 원장(STATE·backlog·README 배지·runbook)에 **원인 서술**을 넣을 때는 '가설' 표기를 기본값으로 하고, 확정형(원인은 X 다)은 대조 측정 인용이 같은 셀에 있을 때만 허용한다. backlog R 항목의 '반증 수단' 열이 이미 이 규율을 갖고 있으므로, 같은 규약을 STATE 최신 블록·README 배지 문구에도 적용하면 신규 기계가 필요 없다.
- **판정**: `CONFIRMED` — 실체 확인됨 — 다만 인용 행번호는 틀렸다.

[1] 사실 관계 = git 1차 증거로 전건 확인. cb2d9657(#1290, 08-05)이 환경 귀속을 확정 서술로 4개 표면에 머지: README.md 배지 `91_pass_/_30_fail_on_Linux` · README.ko.md 배지 `Linux_91_통과_/_30_실패` · docs/STATE.md 종합수치 `Linux 에서 30건 실패 … 로컬 Windows 에서만 초록이었다` · backlog R52 제목/R7 본문 · operational-smoke-checks.md §8.4 `#1288 이 … 배선한 결과 Linux 에서 30건이 실패한다`. d32d9da8(#1292, 다음날)이 5파일 13 insertions/11 deletions 로 전량 철회하며 본문에 `Windows 쪽을 측정하지 않고 비대칭을 단정했다` · `환경 원인 0건` 명시. 5b72c438(#1291) 본문 헤더 `## 가설 (a)(b) 는 실측으로 기각됐다`. 한 문장이 3 PR 소모 = 확인.

[2] 근거가 오히려 finding 보다 강하다. 가설 (a)(b) 자체는 R52 본문에 `미검증` 으로 정직하게 적혔다 

### [process] 정책 11 위반 — 템플릿을 바꾼 PR 에 8 조합 체크리스트가 없고, 검증 요청이 정작 shipped 된 UI 변경을 다루지 않았다

- **위치**: `CLAUDE.md:223`
- **주장**: #1291 은 `src/templates/settings.html` 을 실제로 수정(사용자에게 보이는 동작 변경)했으나 본문에 정책 11 의 '4테마 × 모바일/데스크탑 8 조합 체크리스트'가 없다. §🔍 사용자 검증 필요 섹션은 이 PR 이 **고치지 않은** CSP/폰트 결정만 다루고, **고쳐서 머지한** settings.html 변경에 대한 시각 검증 요청은 0 이다.
- **근거**: CLAUDE.md:223 = "본문 최상단 8 조합 체크리스트. 🔴 **금지**: 본 섹션 누락 후 \"테스트 통과\" 만 적기". `git show 5b72c438 --stat -- src/templates/` = `src/templates/settings.html | 13 ++++++++++++-`. #1291 본문에서 `8 조합|8조합|4테마` grep 히트 0, `settings` 히트는 :54 (수정 설명) 단 1건. 변경 내용은 "토스트 정리가 `save_error` 를 URL 에서 지운 **뒤** `initSettingsMode()` 가 `location.search` 를 읽고 있었다 … 쿼리 스냅샷을 replaceState 앞에서 잡는다" — 즉 저장 실패 시 설정 화면이 **이제부터 실제로** advanced 모드로 강제 전환된다(그동안 죽은 코드였다). 부수로 #1294 는 체크리스트를 "4테마 × 모바일/데스크탑 중 **한두 조합만이라도** 봐 주시면 충분합니다" 로 자기 완화했다(정책 11 은 8 조합 명시).
- **처방**: `src/templates/**`·`src/static/**` 이 PR diff 에 있으면 본문에 8 조합 체크리스트 마커를 요구하는 PR-diff 한정 가드를 `pre_push_gate`/CI 에 추가(정책 19 집행면 `check_claim_review_trace.py` 와 같은 형태 — 어휘 + 면제 마커). 최소한 §사용자 검증 필요 섹션은 '이 PR 이 실제로 바꾼 화면'을 반드시 1행 포함하도록 템플릿을 고정한다.
- **판정**: `CONFIRMED` — CONFIRMED — 인용 전건 실측 일치. (1) CLAUDE.md:223 = "본문 최상단 8 조합 체크리스트. 🔴 **금지**: 본 섹션 누락 후 \"테스트 통과\" 만 적기" 문자 일치. (2) `git show 5b72c438 --stat -- src/templates/` = `src/templates/settings.html | 13 ++++++++++++-` (12+/1-) — 실제 shipped 동작 변경(`var _initialSearch = location.search` 스냅샷 + `initSettingsMode()` 가 `location.search`→`_initialSearch`), 즉 문서화된 우선순위 2번(save_error → 강제 advanced)이 **태어나서 처음 발화**한다. (3) #1291 본문 121줄 대상 `8 ?조합|4 ?테마|모바일|데스크|다크|라이트` grep 히트 **0**; `settings` 히트는 :54 수정 설명 1건뿐이라 시각 검증 요청 0. (4) §🔍 사용자 검증 필요 는 제목에 `(정책 2 · 정책 11)` 을 명시해 놓고 내용은 (a) **고치지 않은** CSP 옵션표 (b) 폰트 현행 확인 뿐

### [code] repo_detail 의 이슈 일괄등록 모달·토스트는 CSS 가 하나도 없고, 숨김은 gitignore 된 빌드 산출물에만 의존한다

- **위치**: `src/templates/repo_detail.html:660`
- **주장**: `src/templates/repo_detail.html:654,660,680,684` 가 `issue-tab-panel hidden` · `issue-modal-overlay hidden` · `issue-modal-error hidden` · `issue-toast hidden` 을 쓰는데, 이 템플릿에는 **`.issue-*` CSS 규칙이 0건**이고 `src/static/**/*.css` 전체에도 `issue-modal-overlay|issue-toast|issue-tab-panel` 규칙이 **0건**이며 `base.html` 에도 없다. 해당 규칙은 오직 **다른 템플릿** `src/templates/analysis_detail.html:223,259,284,294` 의 인라인 `<style>` 안에만 있다(템플릿 간 클래스 이름 복사, 스타일 미복사). 결과 두 가지: (1) **숨김 동작이 Tailwind 의 `.hidden{display:none}` 에만 의존** — `.hidden` 은 어떤 프로젝트 CSS 에도 정의돼 있지 않고 빌드 산출물에만 존재한다(빌드본에서 `.hidden{display:none}` 1건 확인). 그래서 Tailwind 가 없는 CI e2e 에서는 **모달 오버레이·토스트·비활성 AI 탭이 항상 노출된 채** 렌더되는데 e2e 119건 중 아무도 실패하지 않았다. (2) 프로덕션에서 `repo_detail.html:1353` `classList.remove('hidden')` 으로 모달을 열면 **오버레이/백드롭/센터링 스타일이 전무**해 문서 흐름에 낀 평범한 블록으로 렌더된다 — `/repos/{name}` 일괄 이슈 등록 UI 의 실사용자 시각 결함.
- **근거**: `grep -nE "\.issue[a-zA-Z-]*\s*[,{]" src/templates/repo_detail.html` → 0건. `grep -rn "issue-modal-overlay|issue-toast|issue-tab-panel" src/static/ --include=*.css` → 0건. `grep -n "issue-modal|\.hidden" src/templates/base.html` → 0건. 정의처: `src/templates/analysis_detail.html:223,259,284,294`. Tailwind 빌드본: `grep -o "\.hidden{[^}]*}" src/static/css/dist/tailwind.css` → `.hidden{display:none}` (그리고 `issue-modal` 0건). 사용처: `repo_detail.html:660`(마크업) · `:1353`(표시) · `:1357`(숨김).
- **처방**: `.issue-*` 규칙을 `analysis_detail.html` 인라인 `<style>` 에서 `src/static/css/components.css` 로 승격해 두 템플릿이 같은 정본을 쓰게 한다(정책 16 공유 로직 grep 전수 — 사용처 2곳). 숨김은 프로젝트 자체 클래스(`settings.html:414` 의 `.is-hidden` 패턴)로 바꿔 외부 빌드 산출물 의존을 끊는다. 회귀 가드: 템플릿이 쓰는 클래스 중 프로젝트 CSS·해당 템플릿 어디에도 규칙이 없는 것을 잡는 단위 테스트 1건(정책 4 — 단언과 가드 동시 머지).
- **판정**: `CONFIRMED` — 핵심 결함 재현 확인 — 단, 근거 (1) 은 사실관계가 틀렸다. 판정은 유지(P1).

■ 인용 전수 재확인 (전부 정확, drift 0)
- `src/templates/repo_detail.html` 654 `issue-tab-panel hidden` · 660 `issue-modal-overlay hidden` · 680 `issue-modal-error hidden` · 684 `issue-toast hidden` — 4건 line 일치.
- `repo_detail.html:1353` `getElementById('bulkModalOverlay').classList.remove('hidden')` · `:1357` `.add('hidden')` — 일치.
- `analysis_detail.html:223,259,284,294` = 정확히 `.issue-tab-panel.hidden` / `.issue-modal-overlay.hidden` / `.issue-modal-error.hidden` / `.issue-toast.hidden` `{display:none}` 4행 — 일치.

■ CSS 부재 (주장보다 오히려 더 넓음)
- `grep -nE "\

### [docs] cycle-history.md 에 세션15·세션16 이 통째로 없다 — 6-step ⑤ 를 두 세션 연속 미이행

- **위치**: `docs/cycle-history.md:154`
- **주장**: 완료 6-step ⑤ 는 `docs/STATE.md` 수치 갱신 **+ `docs/cycle-history.md` 사이클 이력 동기화**를 예외 없이 요구한다. cycle-history 의 최신 항목은 세션14(2026-08-02, #1268~#1271)이고, 그 이후 머지된 세션15(#1274~#1277)·세션16(#1279~#1293) 약 20 PR 의 서사가 한 줄도 없다.
- **근거**: `docs/cycle-history.md:154` = `## backlog 잔여 이행 + Grok 4중 claim-review (2026-08-02 세션14, 4 PR #1268~#1271)` 가 최상단 본문 섹션. `grep -n "세션15|세션16|#1274|#1279|#1288|#1293" docs/cycle-history.md` = **0 hit**. `git log -- docs/cycle-history.md` 최신 = `2cf7ba07 2026-08-02 (#1272)`. CLAUDE.md:353 6-step ⑤ = *"+ `docs/cycle-history.md` 사이클 이력 동기화 … 예외 없음"*.
- **처방**: 세션15·세션16 섹션을 cycle-history 에 이관하고, 6-step ⑤ 의 cycle-history 축에도 관측면을 붙인다(현재 `check_docs_sync.py` 는 STATE/README 수치만 보고 이력 문서의 최신성은 전혀 보지 않아, 두 세션 연속 미이행이 전부 green 으로 통과했다).
- **판정**: `CONFIRMED` — Citation verified exactly: docs/cycle-history.md:154 = '## backlog 잔여 이행 + Grok 4중 claim-review (2026-08-02 세션14, 4 PR #1268~#1271)' is the newest body section (TOC line 9 mirrors it); grep for 세션15|세션16|#1274|#1279|#1288|#1293 = 0 hits repo-wide in that file. Obligation text verified verbatim at CLAUDE.md:353 ('⑤ docs/STATE.md 수치 갱신 … + docs/cycle-history.md 사이클 이력 동기화 … 예외 없음'). I tried to break the finding two ways and could not. (a) 'One-session lag by design?' — refuted by precedent: each session's own trailing sync historically wrote its own entry (#1246 세션12, #1259/#1262/#1264/#1267 세션1

### [docs] STATE 최신/직전 체인이 세션16 에 대해 한 번도 회전하지 않아, 13 PR 의 서사가 어디에도 없다

- **위치**: `docs/STATE.md:9`
- **주장**: STATE.md:7 의 갱신 규칙 (1)(2)는 신규 작업 시 '최신' 블록을 교체하고 직전 서사는 cycle-history 로 이관하라고 명시한다. 그러나 세션16 의 trailing sync 4건(#1281·#1283·#1287·#1290)은 파생 수치 4줄씩만 고쳤고 '최신' 블록은 여전히 세션15(#1274~#1276)다. 위 cycle-history 미동기화와 겹쳐 **세션16(#1279~#1294, 13 PR)의 서사는 STATE 에도 cycle-history 에도 존재하지 않는다** — 남은 흔적은 §테스트 수 추적 이력의 증분 한 줄뿐.
- **근거**: `docs/STATE.md:9` = `**최신 (2026-08-04 세션15 — … PR #1274~#1276)**` · `:22` = `**직전 (2026-08-02 세션14 … #1268~#1271)**` · `:32` 종합 수치는 `#1294` 까지 반영. `git show --stat` 결과 f9d5906d/dd6d1aef/09ddb4c4/cb2d9657 모두 `docs/STATE.md | 4 ++--` (파생 4줄) 로 블록 회전 없음. 세션16 의 유일한 서사 흔적 = `docs/STATE.md:281~284` 의 §테스트 수 추적 이력 한 줄짜리 항목들.
- **처방**: 세션16 블록을 '최신' 으로 올리고 세션15→직전, 세션14→cycle-history 로 회전시킨다. 구조적으로는 '수치 파생은 자동(`--fix`), 서사 회전은 수동' 이라 자동화된 축만 살아남고 수동 축이 4회 연속 누락됐다는 점을 원장에 남길 것.
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. docs/STATE.md:9 = `**최신 (2026-08-04 세션15 — … PR #1274~#1276)**`, :22 = `**직전 (2026-08-02 세션14 … #1268~#1271)**` 문자열 그대로 존재. 4건 trailing sync 커밋 `git show --stat` 실측 = f9d5906d·dd6d1aef·09ddb4c4·cb2d9657 모두 `docs/STATE.md | 4 ++--` (파생 4줄), 블록 회전 0 — 특히 cb2d9657 는 제목이 "세션16 **종료** trailing sync (#1290)" 로 지정 회전 시점을 통과하고도 회전하지 않았다. docs/cycle-history.md `grep -c` = 세션15 **0** · 세션16 **0**, 최신 본문 절(:154)은 세션14 — 체인이 1 세션이 아니라 **2 세션** 끊겨 있다. 부수 실측: STATE.md:5 날짜 헤더가 `2026-08-04` 인데 같은 파일 :32 는 `#1294, 2026-08-06` 을 적어 갱신 규칙 (0) 도 동시 위반, 즉 한 파일 안에서 :9(최신=#1276) ↔ :32(#1294 반영)가 자기모순이다

### [docs] STATE 날짜 헤더가 2026-08-04 에 고정 — 스스로 '상시 누락 필드' 라 표시한 곳이 또 누락됐다

- **위치**: `docs/STATE.md:5`
- **주장**: `## 현재 수치 (2026-08-04 기준)` 인데 같은 파일의 종합 수치·추적 이력은 2026-08-06 실측을 담고 있다. STATE.md:7 은 이 필드를 갱신 규칙 (0)번으로 올리며 *"절차에서 상시 누락되던 필드"* 라고 명시했는데, 그 경고를 단 뒤에도 세션16 의 5개 문서 커밋이 전부 지나쳤다.
- **근거**: `docs/STATE.md:5` = `## 현재 수치 (2026-08-04 기준)`. 반면 `docs/STATE.md:284` = `… collect-only 실측 2026-08-06`, `:32` 종합 수치는 `#1294` 반영. 커밋 날짜 `git log --date=short`: faeb2cf1·226cd4a9 = 2026-08-06. STATE.md:7 = *"(0) **본 섹션 날짜 헤더(line 5 …)를 최신 세션 날짜로 갱신** (회고 2026-07-03 C5 #60 — 절차에서 상시 누락되던 필드)"*.
- **처방**: 헤더 날짜를 2026-08-06 으로 갱신. 다만 '규칙 본문에 🔴 로 적어 두는 것' 은 이미 2회 실패한 처방이므로(2026-07-03 신설 → 재발), `check_docs_sync.py` 에 '헤더 날짜 ≥ 이력 꼬리 항목의 실측 날짜' 대조 축을 추가하는 편이 근본 시정이다.
- **판정**: `CONFIRMED` — 실측 재확인 결과 결함이 실재하며, 오히려 finder 보고보다 범위가 넓다. (1) 인용 정확: `docs/STATE.md:5` = `## 현재 수치 (2026-08-04 기준)` 정확 일치, `:7` 의 갱신 규칙 (0) 원문 *"본 섹션 날짜 헤더(line 5 …)를 최신 세션 날짜로 갱신 … 절차에서 상시 누락되던 필드"* 도 정확 일치. 인용 `:284` 만 후속 커밋으로 `:285`/`:286` 으로 1~2행 drift 했으나 그 행이 뒷받침하는 사실(`collect-only 실측 2026-08-06`)은 `:285`·`:286` 에서, 그리고 `:32` 종합 수치 `(#1294, 2026-08-06)` 에서 그대로 확인됨 — 인용의 하중 부분은 검증됨. (2) 검증관 독립 확인으로 심각도 상향 근거 확보: `git show <sha>:docs/STATE.md | sed -n 5p` 로 최근 8 커밋의 헤더 값을 전수 대조한 결과 헤더가 **2026-08-05/08-06 날짜의 연속 7 커밋**(a04c6acb·09ddb4c4·cb2d9657·d32d9da8·faeb2cf1·226cd4a9·2478c416)을 통과하며 2026-08-04 에 고정 

### [decision] 정책 1 옵션 표의 단점·위험 셀이 실측 없이 작성돼 사용자 결정 도구 자체가 거짓이 됐다 (★ 가 더 위험한 쪽을 가리켰다)

- **위치**: `docs/backlog.md:51`
- **주장**: #1291 이 CSP/폰트 건을 ㉮~㉱ 4옵션 표로 사용자에게 올리면서 ㉰(링크 제거)의 단점을 "한글 렌더가 눈에 띄게 바뀜"으로 적고 ㉮(vendoring)에 ★(권장)을 붙였다. 3 PR 뒤 #1294 가 Playwright 로 실측한 결과 두 셀 모두 거짓이었다 — 외부 스타일시트는 cssRules 접근이 BLOCKED, document.fonts.size == 0 이라 폰트는 14개월간 한 번도 적용된 적이 없었고 ㉰ 의 시각 변화는 0, 반대로 ★ 를 붙인 ㉮ 가 '14개월 만에 타이포그래피를 처음 바꾸는' 시각 검증 필요 변경이었다. 정책 1 은 옵션 표를 '반대 대신 정보를 줘서 사용자가 판단하도록' 하는 장치로 규정하는데, 단점·위험 셀이 미실측 추정이면 그 장치가 사용자를 정확히 반대 방향으로 유도한다. 리포에는 '옵션 표를 내기 전에 각 셀을 실측하거나 미실측임을 명시하라'는 규칙이 없다 — 같은 세션의 backlog R52 행은 원인 가설을 '가설(미검증)'로 표기하는 규율은 지켰으나(backlog.md:51), 그 규율이 옵션 표 셀에는 적용되지 않았다.
- **근거**: PR #1291 body 108~113행: `| 옵션 | 장점 | 단점 | 위험 |` / `| **㉮ 외부 폰트를 로컬 vendoring** ★ | … |` / `| ㉰ 외부 폰트 링크 제거(시스템 폰트) | 가장 단순 … | **한글 렌더가 눈에 띄게 바뀜** | 디자인 후퇴로 느껴질 수 있음 |`. PR #1294 body 22~27행 대조표: `| **㉰ 링크 제거** | "한글 렌더가 눈에 띄게 바뀜" | **시각 변화 0** — 이미 안 쓰이던 것 |` / `| ㉮ vendoring | "무해한 복구" | **14개월 만에 타이포그래피를 처음 바꾸는** 변경 |` / `무해한 쪽은 ㉰ 였습니다.` 부수: #1291 표는 4컬럼으로 정책 1 default 5컬럼(`| 옵션 | 장점 | 단점 | 위험 | 권장 시점 |`) 중 '권장 시점' 이 빠져 있다.
- **처방**: 정책 1 진화 — 옵션 표의 단점·위험 셀은 (a) 실측 근거 1줄 병기 또는 (b) `미실측` 명시 중 하나를 의무화하고, ★ 는 실측된 셀에만 붙인다. backlog 가 원인 가설에 이미 쓰고 있는 '가설(미검증)' 표기 규율을 옵션 표 셀로 확장하는 것이 최소 변경이다. 회귀 가드 후보: 옵션 표(`| 옵션 |` 헤더)를 담은 PR 본문에 '실측' 또는 '미실측' 토큰이 셀 수만큼 없으면 `::notice` 계량(차단 아님 — 정책 17 안정성).
- **판정**: `SEVERITY_ADJUST` — 인용 3건 전부 실측 확인 — (1) `gh pr view 1291 --json body` 108~113행 = `| 옵션 | 장점 | 단점 | 위험 |` 4컬럼 표, `| **㉮ 외부 폰트를 로컬 vendoring** ★ |` / `| ㉰ … | **한글 렌더가 눈에 띄게 바뀜** | 디자인 후퇴로 느껴질 수 있음 |` 문자열 일치. (2) `gh pr view 1294` body 22~27행 대조표 및 *"무해한 쪽은 ㉰ 였습니다"* 일치. (3) `docs/backlog.md:51` = R52 행, `**가설(미검증)**` 표기 포함 — 인용 정확.

결함 실재 확인: (a) ㉰ 단점 셀은 **실측으로 반증된 거짓**이다(`document.fonts.size == 0`, cssRules BLOCKED, 제거 전후 `font-family` 동일·콘솔 에러 2→0). (b) ★ 가 붙은 ㉮ 가 실제로는 14개월 만의 첫 타이포그래피 변경이었다. (c) 규칙 공백도 실재 — `grep -rn "옵션 표\|장단점\|권장 시점" CLAUDE.md .claude/policies/*.md .claude/rules/*.md AGENTS.md` 결과 `CLAUDE.md:

### [decision] retro_scope.py 가 정책 8-(5) 의 절반만 구현한다 — 본 회고 범위에서 이번 세션의 미머지 산출물(#1294)이 통째로 빠졌다

- **위치**: `scripts/retro_scope.py:98`
- **주장**: 정책 8 진화 (5)는 회고 범위를 '직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**' 로 규정하고, runbook 은 '범위는 손으로 적지 말 것 — 기계 산출한다' 며 retro_scope.py 를 유일 권위로 지정한다. 그런데 이 스크립트는 `merged_prs()` 하나만 계산하고 반환 dict(`compute()`)에도 출력에도 '세션 산출물' 축이 없다. `merged_prs` 는 squash 제목 끝의 `(#NNNN)` 만 파싱하므로 미머지 브랜치 커밋은 구조적으로 비가시다. 이번 실행에서 실증됐다 — HEAD 가 226cd4a9(#1294, R52 CSP 종결, 미머지)인데 출력의 '전체' 목록은 #1273~#1293 19건뿐이고 #1294 는 없다. 즉 이 세션에서 **가장 나중에 만들어진 = 가장 검증이 덜 된** 산출물이 회고를 피해 간다 — 스크립트 자신의 docstring 이 존재 이유로 적은 시나리오와 같은 클래스이며, '진입 직전 머지분' 에서 '아직 안 머지된 산출물' 로 자리만 옮긴 것이다.
- **근거**: `scripts/retro_scope.py:6` — docstring 이 정책 전문 인용(`"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"`). `scripts/retro_scope.py:80` `def merged_prs(boundary)` + `:91` `if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")`. `scripts/retro_scope.py:98` `def compute()` 반환 키 = ok/prev_retro/boundary/head/pr_count/prs/range — 세션 산출물 축 없음. `:139` `print(f"  머지 PR        : …")`. 실행 결과: `경계 커밋 : 8f4ada5 → HEAD 226cd4a9` · `머지 PR : 19건 #1273~#1293` — HEAD 커밋 자신이 목록에 없음. `docs/runbooks/retrospective.md:26-27` 이 이 스크립트를 context 산출의 정본으로 지정.
- **처방**: `compute()` 에 `session_output` 축 추가 — 현재 브랜치의 `main..HEAD` 미머지 커밋 + `git status` 미커밋 변경을 열거하고, 사람용 출력과 `--json` 양쪽에 별도 줄로 인쇄한다(`머지 PR 19건 / 세션 산출물(미머지) 1건: 226cd4a9`). 회귀 가드: 미머지 커밋이 있는 브랜치에서 실행 시 출력에 그 SHA 가 포함되는가 — 뮤테이션(축 제거) → red.
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. `scripts/retro_scope.py:6` = 정책 2축 정의 원문 인용(`"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"`), `:80 def merged_prs(boundary: str)`, `:91 if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")`, `:98 def compute() -> dict` → 반환 키 7개(`:110-118` = ok/prev_retro/boundary/head/pr_count/prs/range) — 세션 산출물 축 부재 확인, `:139` 출력도 `머지 PR` 한 축뿐. `docs/runbooks/retrospective.md:23` 🔴 "범위는 손으로 적지 말 것 — 기계 산출한다" + `:26-27` 이 이 스크립트를 `context` 값의 정본으로 지정. `CLAUDE.md:185` 는 한발 더 나가 2축 표현 전체에 `(기계 산출 scripts/retro_scope.py)` 를 붙여 이 스크립트를 두 축의 생산자로 명명한다 — 즉 정책·docstring·runbook 3곳이 2축을 약속하고 구현은 1축이

### [tooling] 브랜치 보호 실측(required 9종)과 리포 3지점 서술(‘부재’ / ‘2종’)이 어긋난다 — 이번 사이클이 배선한 e2e job 만 유일하게 non-required

- **위치**: `.github/workflows/ci.yml:388`
- **주장**: `GET /repos/xzawed/SCAManager/branches/main/protection` 실측 결과 required status check 은 **9종** + `enforce_admins: true` 다. 그런데 리포의 집행면 서술 3지점이 이와 어긋난다 — 두 곳은 브랜치 보호가 **없다**고 단언하고, 원장은 required 를 **2종**이라 적는다. 방향은 '집행력 과소 서술'이라 안전하지만, 이 리포는 집행면 주장의 정확성을 스스로 P0 기준으로 삼아 왔고(R45-(a) 가 같은 축을 observer-lie 로 지목), R45-(a) 의 잔여 결정("나머지 9 job 승격 여부")이 **이미 지나간 상태**를 baseline 으로 삼고 있다. 더 중요한 실질 갭: CI 10 job 중 **`E2E (Playwright)` 만 required 목록에 없다** — 하필 이번 사이클이 배선하고(#1288) 30건 실패를 처음 관측한(R52) 바로 그 job 이라, 회귀해도 머지를 막지 못한다. 이 사실은 원장 어디에도 적혀 있지 않다.
- **근거**: 실측 required contexts 9종: `Repo integrity guards (stdlib backstop)` · `pip-audit (SCA — 의존성 취약점 게이트)` · `pytest + Codecov + SonarCloud` · `Static analysis gate (pylint + bandit on src/)` · `TruffleHog secret scan` · `Lint changed test files (F401/F841 — C1)` · `lint-js 공허화 차단 (검사 범위 비면 fail)` · `PG-only tests (SKIP LOCKED + migration round-trip)` · `Analyze (python)`. 어긋나는 서술: `.github/workflows/ci.yml:388` "브랜치 보호 부재라 red 가 머지를 물리적으로 막지는 못한다 — red 의 위치를 바꿀 뿐(정직 명시)" · `scripts/check_test_count_sync.py:24` "브랜치 보호 부재(R2-b)라 red 는 머지를 물리적으로 막지 못한다" · `docs/backlog.md:138` R2-b "🔴 2026-08-05 현재 상태: 보호 활성 + required check **2종**" · `docs/backlog.md:41` R45-(a) "🔴 잔여: 나머지 9 job 은 여전히 non-required". e2e job 정의 = `.github/workflows/ci.yml:501` (`#1288`, 2026-08-05 배선), job name `E2E (Playwright)` → required 목록에 부재.
- **처방**: (1) `ci.yml:388` · `check_test_count_sync.py:24` 의 '브랜치 보호 부재' 단언을 실측값으로 정정(두 곳 다 가드의 '정직 명시' 주석이라 stale 시 정확히 반대 방향으로 오도한다). (2) `docs/backlog.md:138`·`:41` 을 required 9종으로 갱신하고 R45-(a) 를 **'e2e 만 non-required'** 단일 잔여로 재정의. (3) 🔴 근본 시정: required check 목록은 손으로 세지 말 것 — `gh api …/branches/main/protection` 을 읽어 `ci.yml` job 이름과 대조하는 가드를 `scripts/` 에 추가하면 이 클래스(집행면 수치 손유지)가 3회째 재발하지 않는다(R45-(a) 가 이미 7종→1종→2종으로 두 번 틀렸다). (4) e2e 를 required 로 승격할지는 사용자 결정 영역(정책 12) — 옵션 표로 제시.
- **판정**: `CONFIRMED` — 실측으로 전건 확인. GET /repos/xzawed/SCAManager/branches/main/protection = required contexts 9종 + enforce_admins:true + strict:false. 인용 4지점 모두 인용된 줄 번호에 정확히 존재(drift 0): ci.yml:388 · check_test_count_sync.py:24 · backlog.md:138(R2-b '2종') · backlog.md:41(R45-(a) '나머지 9 job'). e2e job 정의도 ci.yml:501/:504 확인.

[핵심 주장 CONFIRMED] 3개 워크플로 전수 열거로 검증: ci.yml 9 job + codeql.yml 'Analyze (python)' = 10 체크(claim-review-on-body-edit.yml 은 'Repo integrity guards (stdlib backstop)' 이름을 의도적으로 공유해 별도 컨텍스트 아님). required 9종과 대조한 결과 non-required 는 정확히 1건 = E2E (Playwright) — 주장 그대로다. 하필 이번 사이클 #1288 이 배선하고 30건 실패를 처음

### [tooling] doc_review_gate ROI 원장이 없다 — 이번 사이클 문서화된 적발 1건 vs 자기결함 fix 3건·P0 오차단 1건·2세션 게이트 사망·포기된 편집 1건

- **위치**: `.claude/hooks/doc_review_gate.py:940`
- **주장**: `.claude/hooks/doc_review_gate.py` 는 940줄로 자라 이번 사이클에만 5 PR 이 손댔고 그중 3건이 **자기 결함 수정**이다. 모든 `Write|Edit|MultiEdit` 에 PreToolUse 로 걸리고(timeout 60s), 리포 자신의 계측으로 편집당 FPE ≈110,000 → 캐시 후 ≈14,600 토큰이며 손익분기가 '세션당 편집 2회'다. 이번 사이클 게이트 대상 파일이 17종(critical 10 + important 7) 바뀌었고 그중 `docs/STATE.md`(trailing sync 5회)·`docs/backlog.md` 는 매 세션 반복 편집된다. 그런데 **훅에 적발/오차단 telemetry 가 0**이고, 커밋 본문 전수 검색으로 확인되는 이 사이클의 적발 기록은 **정확히 1건**인 반면 피해 기록은 P0 오차단 1건 + 게이트 사망 2세션 + '무엇을 고쳐야 하는지 알 수 없는 차단' 3연속으로 **편집 포기** 1건이다. 즉 이 게이트는 순비용/순이익을 아무도 모르는 상태로 능력만 계속 확장돼 왔다.
- **근거**: 규모: `wc -l .claude/hooks/doc_review_gate.py` → **940**; `git log --follow` → 2026-04-26 신설 이래 **23 커밋**. 이번 사이클(8f4ada5..HEAD) 5건 = `c7503620`(#1286 feat) `a04c6acb`(#1284 fix) `bb484153`(#1282 perf) `42cc4c4b`(#1279 fix) `c58ed85a`(#1276 fix), 경계 직전 `1f5bba03`(#1275 fail-open P0 fix). 비용: `#1282` 커밋 본문 "이전 ≈110,000 / 1회차 ≈136,500 (+24% 더 비쌈) / 2회차 이후 ≈14,600 (−87%) · 누적 손익분기 = 편집 2회. 편집이 1회뿐인 세션은 순손실이다". 적발 기록 1건: `#1282` 본문 "후자는 심의 게이트가 차단하며 지적해 준 것이다(가드가 제 역할을 했다)" — 사이클 20 커밋 본문 전수 grep 에서 유일. 피해 기록: `#1276` 제목 "게이트를 2 세션 죽인 lone surrogate" · `#1279` 제목 "심의 게이트가 한글을 mojibake 로 읽고 자기 손상을 근거로 차단 (P0)" · `docs/backlog.md:46` R49 잔여(a) "`guards.md` 2-axis 설명 섹션이 *모순*·*모호성* 만 근거로 **3회 연속 block** 돼 결국 반영 못 했다". 대상 범위: `classify_file_grade` 로 사이클 변경 47 파일 분류 → critical 10 · important 7 · skip 30. Telemetry: 훅 내 파일 기록/append 코드 **0건**(grep).
- **처방**: (1) 능력 추가를 멈추고 **먼저 원장을 붙인다** — 훅이 판정마다 `{ts, file, grade, decision, reason_len, tokens}` 한 줄을 append-only 로 남기게 하면(gitignore 대상) 다음 회고가 '적발 N / 오차단 M / 비용 T' 를 추측이 아니라 실측으로 낸다. (2) 계측 1사이클 후 존속/축소를 결정 — 축소안 후보: grade 를 critical 만 남기고 `docs/STATE.md`(수치 sync 전용, `check_docs_sync`·`check_test_count_sync` 가 이미 기계 대조 중)를 skip 으로 강등하면 최다 발화원이 사라진다. (3) R49 잔여(a) 는 ROI 의 핵심 축이다 — **차단 사유에 `file:line` 또는 인용을 강제**하지 않으면 오차단 비용이 계속 '편집 포기' 로 정산된다(정책 16 가독성이 아니라 게이트 사용성 문제).
- **판정**: `CONFIRMED` — 전 항목 독립 재현됨. (1) 규모/이력: `wc -l` = 940, line 940 = `main()` (인용 앵커 존재), `git log --follow` 23 커밋, 사이클 5건 중 `#1276`·`#1279`·`#1284` 3건이 `fix(` 자기결함. (2) 배선: `.claude/settings.json:46-47` PreToolUse `Write|Edit|MultiEdit` timeout 60 — 확인. (3) 비용: FPE 110,000 → 14,600 · 손익분기 편집 2회 = `#1282` 커밋 본문 축자 일치. (4) 🔴 대상 범위는 주장자 수치를 그대로 믿지 않고 `classify_file_grade` 를 직접 import 해 `8f4ada5..HEAD` 47 파일에 실행 — critical 10 / important 7 / skip 30 **정확 재현**. (5) 핵심 축 telemetry 0: 파일 전체에 `open(`·`write_text`·`logging`·DB 경로 0건, import 는 anthropic/asyncio/json/os/re/sys/pathlib 뿐, 모든 `append` 는 파이썬 리스트, 유일 출력은 휘발성 

### [tooling] posttool_pytest_smoke 배너가 plain print() — CLAUDE.md 필수 원칙의 “❌ 배너 시 즉시 조사” 가 원리적으로 수행 불가

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:187`
- **주장**: `CLAUDE.md:351`(필수 원칙)은 PostToolUse 훅 `posttool_pytest_smoke.py` 에 대해 "❌ 배너 시 즉시 조사" 를 지시한다. 그런데 그 배너는 `posttool_pytest_smoke.py:187` 의 plain `print()` 이고, **같은 리포의 규칙**(`.claude/rules/guards.md:325~331`)이 "PreToolUse/PostToolUse 훅의 plain stdout 은 디버그 로그로만 간다 … Claude 컨텍스트가 되는 이벤트는 UserPromptSubmit · UserPromptExpansion · SessionStart 셋뿐" 이라고 확정해 두었다. 즉 Claude 는 ❌ 배너를 **볼 수 없고**, CLAUDE.md 의 필수 원칙 한 줄이 수행 불가능한 지시로 남아 있다. 같은 리포의 `doc_review_gate._emit_advisory` 는 이미 올바른 채널(`additionalContext` + `systemMessage`)을 구현해 두었으므로 기술적 장애물도 아니다. 겹쳐서, `_WATCHED_ROOTS` 가 `.claude/hooks/**` 를 포함하지 않아 이번 사이클이 훅 디렉토리를 5 PR 편집하는 동안 스모크는 **0회** 발동했다.
- **근거**: `CLAUDE.md:351` "PostToolUse Hook(`posttool_pytest_smoke.py`)이 … ❌ 배너 시 즉시 조사". `.claude/hooks/posttool_pytest_smoke.py:187` `print(f"{_banner(rc, asserted)} [{scope}] — best-effort 조기탐지 …")` · `:189` `print(tail)` — 파일 전체에서 `additionalContext`/`systemMessage`/`hookSpecificOutput` grep **0건**. 반대 규칙: `.claude/rules/guards.md:325` "🔴 훅 출력 채널 — `print()` 는 Claude 에게 도달하지 않는다 (2026-08-01 공식 계약 확인)", `:327~331` 실측 서술 "`doc_review_gate` 의 advisory 배너가 CRITICAL 문서 3회 편집에서 에이전트 도구 결과에 **0회** 출현(그 고지는 theatre 였다)". 올바른 구현 선례: `.claude/hooks/doc_review_gate.py:332` `_emit_advisory`. 감시 범위: `.claude/hooks/posttool_pytest_smoke.py:39` `_WATCHED_ROOTS = ("src", "alembic", "scripts")` — 이번 사이클 `.claude/hooks/doc_review_gate.py` 를 편집한 PR = #1276·#1279·#1282·#1284·#1286 **5건**. 원장: `docs/backlog.md:40` R44-(c) 가 두 축을 이미 적었으나 🟡 착수 가능으로 남아 사이클이 5 편집을 더 쌓았다.
- **처방**: (1) `posttool_pytest_smoke.py:187` 을 `doc_review_gate._emit_advisory` 와 같은 JSON 페이로드(`hookSpecificOutput.additionalContext` + `systemMessage`)로 교체 — PostToolUse 는 `hookEventName: "PostToolUse"`. `permissionDecision` 은 붙이지 않는다(guards.md:339). (2) `_WATCHED_ROOTS` 에 `.claude` 추가 — 이번 사이클 최다 churn 이자 최다 결함 영역이 무감시인 것이 R44-(c) 의 요지다. (3) 🔴 회귀 가드는 텍스트 단언이 아니라 **채널 단언**으로 — guards.md:346 이 이미 "`assert \"MARKER\" in capsys.out` 은 bare `print` 로도 초록" 이라 경고했다. `json.loads(capsys.out)` 후 `additionalContext` 키 존재를 단언할 것. (4) 고치기 전이라면 `CLAUDE.md:351` 의 "❌ 배너 시 즉시 조사" 를 그대로 두지 말 것 — 수행 불가 지시가 필수 원칙에 남으면 다른 필수 원칙의 신뢰도까지 깎는다.
- **판정**: `CONFIRMED` — 모든 인용이 grep 실측 일치 (main 기준 동일). CLAUDE.md:351 = "❌ 배너 시 즉시 조사" 정확. posttool_pytest_smoke.py:187 `print(f"{_banner(rc, asserted)} …")` · :189 `print(tail)`, 파일 전수 grep `additionalContext|systemMessage|hookSpecificOutput` = 0건, 게다가 main() 이 무조건 `return 0` (비차단 advisory) 이라 exit-2/stderr 우회 경로도 미사용 → 실패 신호가 Claude 에게 도달할 채널이 하나도 없다. 반대 규칙 .claude/rules/guards.md:325 제목·327~331 본문(PostToolUse plain stdout = 디버그 로그 전용, Claude 도달 이벤트는 UserPromptSubmit·UserPromptExpansion·SessionStart 셋뿐 + doc_review_gate 배너 0회 출현 "theatre" 실측) 정확. 올바른 선례 doc_review_gate.py:332 `_emit_advisory` → additionalContext + 

### [tooling] pre_push_gate 의 “못 보는 축” 목록이 e2e CI 배선(#1288) 직후 stale — 러너의 존재 이유인 ‘초록의 의미’ 가 과대 진술된다

- **위치**: `scripts/pre_push_gate.py:90`
- **주장**: `scripts/pre_push_gate.py` 는 매 실행 "🔴 이 스크립트가 **보지 못하는** 축 (여기 초록 != CI 초록)" 목록을 인쇄하는 것이 설계 요점이다. 그 목록은 5축(`:90~94`)인데, 이번 사이클이 CI 에 새로 배선한 **`E2E (Playwright)` job 이 빠져 있다**. e2e 는 Playwright + chromium 이 필요해 이 러너가 원리적으로 못 도는 축이고, 배선 직후 실측이 `30 failed / 91 passed` 였던(R7 → R52) 가장 변동성 큰 축이다. 결과적으로 게이트의 마지막 줄 "✅ 덮는 범위 전건 통과 (위 미포함 축은 CI 에서 확인)" 이 실제보다 좁은 사각지대를 보고한다 — 이 리포가 스스로 지배적 결함으로 명명한 '초록이 실제보다 많은 것을 뜻하는' 클래스다.
- **근거**: 라이브 실행(2026-08-06) 출력 = 미포함 축 5줄: `CodeQL · SonarCloud · Codecov(patch coverage)` / `TruffleHog · pip-audit` / `lint-js` / `PG-only job` / `tests/integration` + 인터프리터 3.14↔3.12 경고. 소스 = `scripts/pre_push_gate.py:90-94`(`_UNSEEN` 목록) · `:220` `print("\n🔴 이 스크립트가 **보지 못하는** 축 …")` · `:25-27` 모듈 docstring 의 같은 5축 열거(2지점 손유지). 누락 대상 = `.github/workflows/ci.yml:501` `e2e:` job(name `E2E (Playwright)`, `#1288` 2026-08-05 배선, `python -m pytest e2e/ … --timeout=120`). 같은 러너의 자기 규율 근거: `:113-118` docstring "advisory 가드는 exit 0 이면서 경고를 낸다 … 실패 시에만 출력하면 그 경고가 삼켜져 'OK' 만 보인다(경고가 존재 이유인데 안 보이는 것 = 이 저장소의 지배적 결함 재생산)".
- **처방**: (1) `_UNSEEN` 에 `e2e (Playwright + chromium 필요) — 이 스크립트는 --full 에서도 안 돈다` 추가, 모듈 docstring `:25-27` 사본도 동시 갱신(2지점 손유지 자체가 결함원 — 가능하면 단일 상수에서 파생). (2) 🔴 근본 시정: 이 목록은 **`ci.yml` 의 job 집합에서 파생**돼야 한다 — `ci.yml` job 이름을 파싱해 러너가 실행하는 가드 집합과 차집합을 계산하면, 다음에 job 이 추가돼도 목록이 조용히 stale 해지지 않는다. 이번 건은 'job 추가 PR 이 러너의 정직 목록을 갱신할 의무' 를 사람이 기억해야 하는 구조가 하루 만에 실패한 실증이다. (3) 회귀 가드: `tests/unit/scripts/` 에 `ci.yml` job 수 ↔ (`_INTEGRITY` + `_PR_DIFF` + `_UNSEEN`) 커버리지 대조 테스트 1건.
- **판정**: `CONFIRMED` — CONFIRMED at P1. Every cited location verified and the defect reproduced live. (1) scripts/pre_push_gate.py:89-95 holds exactly 5 blind-spot entries; `grep -n "e2e|E2E|[Pp]laywright" scripts/pre_push_gate.py` returns ZERO hits file-wide. (2) :220 print and :25-27 docstring duplicate the same 5 axes by hand, as claimed. (3) .github/workflows/ci.yml:501 `e2e:` / :504 `name: E2E (Playwright)` exists, added by 02b3e867 (#1288). (4) Chronology proves staleness: last commit touching pre_push_gate.py is d904c6cd (#1271), which PREDATES 02b3e867 (#1288) — the list was never updated. (5) Live run (py -

### [process] 정책 1 옵션 표가 미측정 추정으로 채워져 ★권장이 정반대로 뒤집혔다 (24시간 내 2회차)

- **위치**: `docs/backlog.md:1`
- **주장**: #1291 이 사용자에게 제출한 CSP 결정 옵션 표(㉮~㉱)의 장단점/위험 셀이 측정 없이 작성돼, ★권장(㉮ vendoring)이 실제로는 '14개월 만의 첫 타이포그래피 변경'이고 '한글 렌더가 눈에 띄게 바뀜'이라던 ㉰는 '시각 변화 0'인, 완전히 역전된 표였다. 정책 1은 사용자 판단을 돕기 위한 장치인데 그 판단 입력이 거짓이었다.
- **근거**: PR #1291 본문 §🔍 사용자 검증 필요 1번 표: `| ㉰ 외부 폰트 링크 제거 | … | **한글 렌더가 눈에 띄게 바뀜** | 디자인 후퇴로 느껴질 수 있음 |` 와 `| **㉮ 외부 폰트를 로컬 vendoring** ★ | 무해한 복구 …`. 다음 PR #1294 본문 첫 문장이 자기 반증: "옵션을 내기 전에 실제로 무엇이 일어나는지 재지 않았고, 재 보니 거짓이었습니다" + Playwright 실측 `document.fonts.size 0`, `cssRules 접근 = BLOCKED`, `body font-family → 앞 세 개는 로드된 적이 없음`. 같은 창에서 #1292(d32d9da8) 도 "어제 제가 틀리게 적어 머지한 'Linux 전용' 서술 정정" — 24시간 내 자기 서술 정정 2회차. 측정 비용은 낮았다(#1294 가 같은 Playwright 로 수 분 내 측정).
- **처방**: 정책 1 표에 근거 등급 셀 의무화: 각 장단점/위험 셀 앞에 `[실측]`/`[추론]` 표기, 그리고 런타임·시각 결과 주장은 리포에 측정 수단이 이미 있으면(Playwright/e2e) 표 제출 **전** 측정 의무. 최소한 ★권장 표시가 붙은 행은 `[추론]` 셀만으로 구성 금지. 회귀 가드로 PR 본문 옵션 표에 근거 등급 마커가 없으면 pre_push_gate 가 advisory 인쇄.
- **판정**: `SEVERITY_ADJUST` — 실재 확인 — 다만 이 리포의 P0 정의에 미달해 P1 로 강등한다.

## 1. 인용 검증 (전건 verbatim 일치)

- **PR #1291 본문**(머지 `2026-08-05T12:42:57Z`) §"🔍 사용자 검증 필요" 표 — 인용문과 **한 글자 차이 없음**:
  - `| **㉮ 외부 폰트를 로컬 vendoring** ★ | … | 렌더 결과가 미세하게 달라질 수 있음(제가 **시각 검증 불가**) |`
  - `| ㉰ 외부 폰트 링크 제거(시스템 폰트) | 가장 단순 … | **한글 렌더가 눈에 띄게 바뀜** | 디자인 후퇴로 느껴질 수 있음 |`
- **PR #1294 본문**(생성 `2026-08-05T16:09:01Z`, 현재 OPEN) 첫 문장 = 자기 반증 verbatim: *"옵션을 내기 전에 실제로 무엇이 일어나는지 재지 않았고, 재 보니 거짓이었습니다."* + Playwright 실측 `cssRules 접근 = BLOCKED` · `document.fonts.size 0` · `→ 앞 세 개는 로드된 적이 없음` + 역전 표(㉰ "시각 변화 0" / ㉮ "14개월 만에 타이포그래피를 처음 바꾸는").
- **24시간 내 2회차

### [process] PR #1294 본문이 자기 diff 의 CI 워크플로 변경과 배지 플립을 한 번도 언급하지 않는다

- **위치**: `.github/workflows/ci.yml:519`
- **주장**: #1294 는 fix-up 커밋 2건으로 `.github/workflows/ci.yml`(Node 20 setup + `npm ci --ignore-scripts && npm run build` 를 e2e job 에 추가)과 README/README.ko E2E 배지의 노랑→brightgreen 플립을 포함하게 됐는데, 본문 4127자 어디에도 ci.yml·npm·Node·배지·README 언급이 0회다. 사용자는 본문을 근거로 머지하므로 인프라 변경이 서술 없이 main 에 들어간다(정책 3 자율 판단 사후 보고 의무).
- **근거**: `gh pr view 1294 --json files` → `.github/workflows/ci.yml`, `README.md`, `README.ko.md` 포함. 본문 grep `-E "ci\.yml|npm|Node|배지|badge|워크플로|workflow|README"` → NO MATCH (4127 bytes). 커밋 d82192fd(16:16:50Z)·2478c416(16:24:44Z) 이 본문 최종 수정(updatedAt 16:30:57Z) **이전**이므로 갱신 기회는 있었다. 본문 §검증 블록은 여전히 이전 상태("e2e (로컬 전체) → 남은 1 failed 는 perf 플레이크")인데 최신 커밋 메시지는 CI 0 failed 를 주장한다. 🔴 앱 자신의 게이트가 PR 에 "Auto-merge withheld — sensitive paths changed … CI workflow definitions" 를 2회 달아 기계는 알렸는데 사람이 읽는 서술만 침묵했다.
- **처방**: 정책 10 의 '생성 직후 본문 검증'을 **fix-up 커밋 추가 시 본문 재검증**까지 확장(현재는 길이 검증만). 기계 배선: 민감 경로(`.github/workflows/**`, `alembic/**`, README 배지 라인)가 diff 에 있는데 본문에 그 경로/주제 문자열이 없으면 pre_push_gate·CI 가 advisory 로 인쇄(차단 아님, 정책 17).
- **판정**: `CONFIRMED` — Independently reproduced. (1) Citation verified: commit d82192fd's diff on .github/workflows/ci.yml is hunk `@@ -519,6 +519,22 @@`, inserting actions/setup-node@v7 (node 20) + `npm ci --ignore-scripts && npm run build` into the e2e job — ci.yml:519 is the correct anchor. (2) Body silence reproduced on a fresh fetch: body is 4127 bytes, grep -E "ci\.yml|npm|Node|배지|badge|워크플로|workflow|README" returns NO MATCH. (3) Not already-resolved: PR is state=OPEN, mergedAt=null, so the defect is live and the body is still editable. (4) I tested the strongest exculpatory reading and rejected it: the body's

### [process] 세션 종료 owed 일괄 회신이 '신규분'만 담아 기존 ⏳ 2건(#1276·#1279)이 세션 경계를 넘어 노화

- **위치**: `docs/runbooks/owed-verification.md:83`
- **주장**: 정책 2 진화(Phase 종료 일괄 회신)의 실행체인 #1290 §🔍 사용자 검증 필요가 그 세션에서 새로 생긴 #1289 2건만 재요청하고, 원장에 이미 ⏳ 로 있던 #1276·#1279 는 언급하지 않았다. 결과적으로 운영등급 미결이 4건으로 누적된 채 다음 세션으로 넘어갔고, 체커는 '카운트만 보고' 하므로 아무도 다시 꺼내지 않는다.
- **근거**: `py -3 scripts/check_owed_verification.py` → "안전등급 미결 0건 / 운영등급 미결 4건: #1289, #1289, #1279, #1276". #1290 본문 §🔍 사용자 검증 필요 = "아래 2건은 `#1289` 에서 넘어온 **운영** 항목입니다" 로 2건만 열거. 원장 docs/runbooks/owed-verification.md:82(#1279 심의 게이트 한글 심의 품질, ⏳) · :83(#1276 게이트 실사용 동작, ⏳) 는 미언급. 원장 작성 규칙(파일 헤더)은 "세션/Phase 종료 시 … trailing sync PR body 의 §owed-verification 표와 페어" 로 **전체 미결** 을 전제한다.
- **처방**: trailing sync 본문의 owed 섹션을 '신규 추가분' 이 아니라 `check_owed_verification.py` 출력의 **미결 전량** 으로 생성(스크립트가 마크다운 표를 출력하게 하고 본문에 붙여넣기). 3세션 이상 ⏳ 로 남은 운영등급 항목은 안전등급과 동일하게 loud 승격 규칙 추가.
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. docs/runbooks/owed-verification.md:82=#1279(⏳)·:83=#1276(⏳) grep 확인, 체커 출력 "안전등급 미결 0건 / 운영등급 미결 4건: #1289, #1289, #1279, #1276" 재현, PR #1290(cb2d9657, merged 2026-08-04, '세션16 종료 trailing sync') §🔍 사용자 검증 필요 본문 = "아래 2건은 #1289 에서 넘어온 운영 항목입니다" 로 신규 2건만 열거하고 #1276/#1279 는 본문 어디에도 없음.

일회성이 아니라 계통적임을 추가 실증: #1277(세션15 종료)=신규 #1276 만 요청 → #1281(세션16 중간, 헤더가 명시적으로 "이번 세션 누적")=신규 #1279 만 요청하고 기존 #1276 누락 → #1290(세션16 종료)=신규 #1289 2건만. 즉 #1276 은 세션 경계 2회를 요청 없이 통과했고, 이는 원장 헤더가 인용한 회고 2026-07-18 P1#13("운영 검증 증거가 미결로 유실") 실패 모드의 재생산이다. HEAD 기준 원장 여전히 ⏳ 4건, cb2d9657 이후 원장 수정 커밋 없음, 유일한 op

### [process] STATE 헤더 날짜와 세션 서사가 세션16 전체(16 PR)를 반영하지 못한 채 7 사이클 반복

- **위치**: `docs/STATE.md:5`
- **주장**: 6-step ⑤ 가 7회(#1281·#1283·#1287·#1290·#1293·#1294) 실행됐는데 매번 수치 라인만 갱신되고, STATE 자신이 (0)번 규칙으로 명시한 날짜 헤더와 (1)번 '최신 블록 교체' 는 한 번도 수행되지 않았다. SSOT 를 여는 첫 두 화면이 16 PR 만큼 낡은 상태다.
- **근거**: docs/STATE.md:5 `## 현재 수치 (2026-08-04 기준)` vs :285-286 `… collect-only 실측 2026-08-06`(같은 파일 내부 모순). :9 `**최신 (2026-08-04 세션15 …, PR #1274~#1276)**` — 세션16(#1279~#1294, 16 PR) 서사 블록 부재. docs/cycle-history.md 최신 섹션은 :154 세션14 로 세션16 이관분도 없음. 규칙 원문 STATE.md:8 — "🔴 **다음 세션 갱신 규칙**: (0) **본 섹션 날짜 헤더(line 5 …)를 최신 세션 날짜로 갱신** (회고 2026-07-03 C5 #60 — 절차에서 상시 누락되던 필드)" — 스스로 상습 누락 필드로 표시해 둔 항목이 또 누락.
- **처방**: ⑤ 를 산문 절차에서 기계 검사로: `docs/STATE.md` 가 diff 에 있는 PR 에서 (a) line 5 날짜 ≥ 그 PR 의 커밋 날짜 (b) 최신 블록의 세션 번호 = 수치 이력 최신 항목의 세션 번호 를 대조하는 가드를 `scripts/` 에 추가(#1293 이 만든 `--fix` 파생 동기화 흐름에 붙이면 비용 낮음).
- **판정**: `CONFIRMED` — 전건 실측 확인. (1) docs/STATE.md:5 = `## 현재 수치 (2026-08-04 기준)` 인데 같은 파일 :32(`#1294, 2026-08-06`)·:285-286(`collect-only 실측 2026-08-06`)는 08-06 — 파일 내부 자기모순 실재. (2) :9 최신 블록 = 세션15(#1274~#1276), `grep '#1279|#1288|#1291|#1294' docs/STATE.md` 는 수치 트레일(:32·:281·:286)만 히트 = 세션16 서사 블록 부재. (3) docs/cycle-history.md 최신 섹션 :154 세션14 — 세션16 이관분 없음. (4) 빈도는 오히려 과소계상: `git log -- docs/STATE.md` 상 #1277(세션15 sync) 이후 STATE 를 건드린 커밋은 9건(#1281·#1283·#1284·#1287·#1290·#1292·#1293·226cd4a9·2478c416)이고, `--stat` 상 trailing sync 4건은 정확히 `2 insertions/2 deletions`(수치 2줄)뿐 — line 5/9 를 건드린 커밋 0건. (5) 면책 반증: cb2d9657

### [code] e2e CI 실패 아티팩트 업로드가 공허하다 — trace/스크린샷을 만드는 코드가 스위트에 0개

- **위치**: `.github/workflows/ci.yml:552`
- **주장**: #1291 이 "관측 결함도 함께 고쳤다 … 실패 시 trace/스크린샷 artifact 업로드. 이게 없어서 이번 진단이 잘린 텍스트 로그 고고학이 됐다" 라고 단언하며 추가한 `Upload Playwright artifacts` step 은 **어떤 파일도 수집할 수 없다**. 스위트 전체에 tracing/screenshot 생산자가 존재하지 않으므로, 다음 e2e 회귀 진단도 똑같이 텍스트 로그 고고학이 된다 — 그런데 이번엔 "아티팩트가 있다"고 믿는 상태로.
- **근거**: `.github/workflows/ci.yml:552-562` 이 `test-results/`·`e2e/**/*.png`·`e2e/**/*.zip` 를 `if-no-files-found: ignore` 로 업로드한다. 그러나 `grep -rn "tracing|screenshot|test-results|makereport|pytest_runtest" e2e/` = **0 hit**. `e2e/conftest.py:249` 의 `page` fixture 는 `browser_instance.new_context()` → `context.new_page()` 로 **자체 구현**이라 `pytest-playwright`(requirements-dev.txt:10) 의 `page`/`context` fixture 를 가리고, 그 플러그인의 실패-캡처 훅이 도달하지 않는다. 게다가 실행 명령(`ci.yml:546` `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120`)에 `--screenshot`/`--tracing`/`--video` 가 없어 플러그인 기본값이 전부 off 다(→ `test-results/` 자체가 생성되지 않음). 리포 루트에 `conftest.py` 없음, `tests/conftest.py` 에도 캡처 훅 없음.
- **처방**: `e2e/conftest.py` 의 `page`/`anonymous_page`/`seeded_page` fixture 에 실패 시 캡처를 붙인다 — `context.tracing.start(screenshots=True, snapshots=True)` + teardown 에서 `pytest_runtest_makereport` 훅으로 실패 판정 시 `tracing.stop(path=...)` + `pg.screenshot(path=...)`. 그리고 그 산출물이 **실제로 생성되는지**를 강제 실패 테스트 1건으로 뮤테이션 검증할 것(파일 0개여도 step 이 초록인 현 구조가 곧 observer-lie 다). 임시 조치로도 `if-no-files-found: ignore` → `warn` 으로 바꾸면 침묵이 최소한 가시화된다.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. (1) `.github/workflows/ci.yml:552-562` `Upload Playwright artifacts` step 존재 — `test-results/`(:558)·`e2e/**/*.png`(:559)·`e2e/**/*.zip`(:560)·`if-no-files-found: ignore`(:561). (2) `ci.yml:546` = `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` — 캡처 플래그 0개. (3) `grep -rniE "screenshot|tracing|trace|video|test-results|artifact|save_as|makereport" e2e/` → **rc=1, 0 hit** (대소문자 무시·.py+.ini 전수). 리포 루트 `conftest.py` 부재, `e2e/pytest.ini` 에 `addopts` 없음, 루트 `pytest.ini`(`testpaths=tests`)는 `pytest e2e/` 실행 시 활성 config 아님. (4) `e2e/conftest.py:249` `page(browser_instance, base_

### [code] 구조화 출력 배선 가드가 3 경로 중 1 경로만 — 나머지 2 경로는 #1289 가 스스로 "공허했다"고 기록한 바로 그 상태

- **위치**: `src/services/dashboard_service.py:829`
- **주장**: #1289 는 ai_review 의 `output_config` 배선 테스트를 추가하며 *"뮤테이션 … ai_review output_config 배선 제거 → red. 🔴 후자는 처음에 green 이었다(analyzer 단위 1022건 전건 통과) — 공허한 가드였고 배선 테스트를 추가해 닫았다"* 라고 적었다. 그런데 같은 PR 이 함께 배선한 **dashboard insight·repo narrative 2 경로에는 그 테스트를 만들지 않았다**. 즉 그 두 곳은 `output_config` 를 통째로 삭제해도 전건 green 인, PR 본문이 방금 위험하다고 진단한 상태 그대로다.
- **근거**: `grep -rn "output_config" tests/` 결과는 `tests/unit/analyzer/io/test_ai_review.py:396` 과 `tests/unit/hooks/test_doc_review_gate.py:169` **둘뿐**이다. 반면 프로덕션 배선은 3+1 곳: `src/analyzer/io/ai_review.py:154`(가드 O) · `src/services/dashboard_service.py:829`(가드 X) · `src/services/repo_insight_service.py:431`(가드 X) · `.claude/hooks/doc_review_gate.py:571`(가드 O). `git show 762e90ba --stat` 의 테스트 변경 파일도 `tests/unit/analyzer/io/test_ai_review.py`(+36)·`tests/unit/test_config.py`(+27) 둘뿐이다.
- **처방**: `_call_insight_claude_api` 와 `repo_insight_narrative` 에 대해 `messages.create` kwargs 를 캡처해 `output_config["format"]["type"] == "json_schema"` + 스키마 키 집합을 단언하는 배선 테스트를 각각 추가하고, 실경로 뮤테이션(해당 인자 삭제) → red 를 실측할 것. 기대 스키마 키는 `_INSIGHT_RESPONSE_SCHEMA` 에서 유도하지 말고 리터럴로 못박는다(guards.md §기대값 자기참조 금지).
- **판정**: `CONFIRMED` — CONFIRMED by direct mutation test, not inference. Citation exact: src/services/dashboard_service.py:829 is the `output_config={` line; third path src/services/repo_insight_service.py:431 also confirmed.

EVIDENCE (all re-verified independently):
(1) Guard inventory — 4 production wiring sites, 2 guarded: ai_review.py:154 (guarded by tests/unit/analyzer/io/test_ai_review.py:396) and .claude/hooks/doc_review_gate.py:571 (guarded by tests/unit/hooks/test_doc_review_gate.py:169, from earlier PR #1286). Unguarded: dashboard_service.py:829 and repo_insight_service.py:431. `grep -rn "output_config" t

### [docs] E2E 추적셀이 122/12-perf 로 stale — 4지점 중 유일하게 가드 없는 축이 실제로 drift 했다

- **위치**: `docs/STATE.md:38`
- **주장**: E2E 수치는 STATE 종합(:32) · STATE 추적셀(:38) · README 배지(:22) · README.ko 배지(:22) 4지점에 손으로 복제돼 있는데, 마지막 3개 커밋(5b72c438·226cd4a9·2478c416)이 3지점만 갱신하고 추적셀을 빠뜨렸다. 추적셀은 총계와 내역이 **둘 다** 틀렸다.
- **근거**: 실측 `py -3 -m pytest e2e --collect-only -q` = **121 tests collected**, `-m perf` = **11/121**, `-m "not perf"` = **110/121**. 그런데 `docs/STATE.md:38` = `| E2E 테스트 | **122개** |` + 셀 말미 `**= 122 collected (110 표준 + 12 perf)**`. 반면 `docs/STATE.md:32` = `E2E **121** (#1291 이 중복 1건 제거)`, `README.md:22` = `E2E-121_in_CI_(120_pass_%2F_1_skip)`, `README.ko.md:22` = 동일 121. 즉 같은 파일 안에서 32행과 38행이 서로 모순한다. 가드 부재 실증: `grep -n "e2e\|E2E" scripts/check_test_count_sync.py scripts/check_docs_sync.py` = **0 hit**, `grep -n "E2E-" scripts/check_docs_sync.py scripts/check_test_count_sync.py tests/unit/scripts/test_repo_integrity_checks.py` = **0 hit**. 두 가드는 `_README_BADGE = re.compile(r"Tests-(\d+)%2B_total_…")`(check_docs_sync.py:41)로 Tests 배지만 파싱한다. 실행 결과도 `✅ 테스트 수치 일치 — 전체 6849` / `✅ STATE 종합·추적셀 ↔ README ↔ README.ko 전체/단위 카운트 일치` 로 **초록**이다 — 틀린 축을 보지 않기 때문이다. 대조군: 가드가 있는 단위/통합 축은 같은 창에서 한 번도 어긋나지 않았다.
- **처방**: (1) `docs/STATE.md:38` 을 `121개` / `= 121 collected (110 표준 + 11 perf)` 로 실측 정정. (2) `check_docs_sync.py` 에 E2E 축 추가 — `_E2E_BADGE` 정규식(README/README.ko) ↔ STATE:32 ↔ STATE:38 3지점 대조 + `--fix` 파생. `.claude/rules/docs.md` 가 이미 *"N지점 동기화 의무는 N-1번의 실패 기회"* 라 적고 단위 축만 SSOT 파생으로 봉인했다 — E2E 축에 같은 처리를 적용한다. (3) 뮤테이션 red 확인: 121→122 로 되돌리면 가드가 실제로 발화하는가.
- **판정**: `CONFIRMED` — Reproduced end-to-end. Citations exact: docs/STATE.md:38 = `| E2E 테스트 | **122개** |` with cell tail `**= 122 collected (110 표준 + 12 perf)**`, while docs/STATE.md:32 in the SAME file = `E2E **121** (#1291 이 중복 1건 제거)`, README.md:22 = `E2E-121_in_CI_(120_pass_%2F_1_skip)`, README.ko.md:22 = 121. Measured ground truth, not asserted: `py -3 -m pytest e2e --collect-only -q` = 121 collected; `-m perf` = 11/121; `-m "not perf"` = 110/121. So the cell is wrong on the total (122 vs 121) and on the perf breakdown (12 vs 11). Mechanism traced: `git log -L 38,38:docs/STATE.md` shows the cell last written b

### [docs] 운영 런북(정책 13 SSOT)이 이미 종결된 R52 를 '1 실패 · 사용자 결정 대기' 로 서술 중

- **위치**: `docs/runbooks/operational-smoke-checks.md:209`
- **주장**: `#1290` 이 §8.4 에 일부러 넣은 경고 블록이 `#1291`→`#1294` 이후 갱신되지 않아, 활성 운영 런북이 **이미 고쳐진 앱 결함을 열려 있는 것처럼** 기술한다. R7 원죄의 거울상 — 이번엔 초록을 빨강으로 잘못 적은 쪽이다.
- **근거**: `docs/runbooks/operational-smoke-checks.md:209` = *"`#1291` 이 그중 29건을 해소해 현재 **119 통과 / 1 실패 / 1 skip** 이다"*, `:211` = *"남은 1건 … **CSP 가 자기 폰트를 차단**하는 앱 결함을 잡고 있다(**사용자 결정 대기** — backlog R52)"*. 그러나 `docs/backlog.md:51` = `| **R52** | ✅ 완료 (30 → **0**) — CSP 앱 버그까지 해소 (`#1294`) |`, `docs/STATE.md:32` = *"CI 실측 **120 통과 / 1 skip / 0 실패**(`#1294`, 2026-08-06)"*, `README.md:22` 배지 = brightgreen `120_pass / 1_skip`. 커밋 `226cd4a9`(R52 종결)·`2478c416`(배지 초록) stat 확인 결과 두 커밋 모두 README×2·STATE·backlog 만 건드리고 `docs/runbooks/operational-smoke-checks.md` 는 **touch 0**. 이 런북은 `_archive` 가 아니라 정책 13 이 인용하는 활성 SSOT 다(CLAUDE.md 정책 13: *"엔드포인트 기대값 SSOT = docs/runbooks/operational-smoke-checks.md"*).
- **처방**: §8.4 경고 블록을 `120 통과 / 0 실패 / 1 skip`(#1294) 로 갱신하고 *"사용자 결정 대기 — R52"* 를 제거한다. *"이 열을 '자동으로 지켜진다' 로 읽지 말 것"* + R53(초록 91건 미감사) 경고는 **유지**한다 — 그건 여전히 참이다. 더불어 R52 처럼 backlog 를 ✅ 로 플립할 때 그 R 번호를 인용하는 활성 문서를 `grep -rn "R52" docs/ .claude/` 로 전수 확인하는 절차를 `.claude/rules/docs.md` 에 1줄 추가한다(현재 그 파일에 backlog↔런북 역참조 규칙이 없다).
- **판정**: `CONFIRMED` — 모든 인용을 grep 으로 축자 재확인했고 반증 시도가 전부 실패했다.

[1] 인용 실재 — `docs/runbooks/operational-smoke-checks.md:209` = "`#1291` 이 그중 29건을 해소해 **현재** 119 통과 / 1 실패 / 1 skip 이다", `:211` = "CSP 가 자기 폰트를 차단하는 앱 결함을 잡고 있다(**사용자 결정 대기** — backlog R52)". 인용 line 번호가 정확히 일치.

[2] 반대 사실 3중 확인 — `docs/backlog.md:51` = "R52 | ✅ 완료 (30 → 0) — CSP 앱 버그까지 해소 (#1294)", `docs/STATE.md:32` = "CI 실측 120 통과 / 1 skip / 0 실패 (#1294, 2026-08-06)", `README.md:22` 배지 = `E2E-121_in_CI_(120_pass/1_skip)` brightgreen.

[3] touch-0 검증 — `git show --stat 226cd4a9`(R52 종결) = README.md·README.ko.md·STATE.md·backlog.md·src/templates/base.ht

### [docs] cycle-history.md 가 21 PR 째 멈춰 있고 STATE '최신' 블록은 2세션 stale — 6-step ⑤ 가 세션 단위로 통째 누락

- **위치**: `docs/cycle-history.md:9`
- **주장**: CLAUDE.md 6-step ⑤(*"docs/STATE.md 수치 갱신 + docs/cycle-history.md 사이클 이력 동기화"*, 예외 없음)가 세션15·세션16 내내 이행되지 않았다. 세션16 은 '종료 trailing sync' PR 까지 냈는데도 최신 블록을 교체하지 않았다.
- **근거**: `git log -1 -- docs/cycle-history.md` = `2cf7ba07 2026-08-02 docs(state): 세션14 trailing sync (#1272)` — 이후 머지 PR **21건**(#1273~#1293) 동안 touch 0. `grep -c "세션1[56]" docs/cycle-history.md` = **0**. TOC 최상단(`docs/cycle-history.md:9`) = 세션14. 한편 `docs/STATE.md:9` = `**최신 (2026-08-04 세션15 … PR #1274~#1276)**`, `:22` = `**직전 (2026-08-02 세션14 …)**`. STATE.md:7 이 스스로 정한 절차 = *"(1) 본 '최신' 블록을 새 작업으로 교체 … (2) 직전 작업의 전체 서사는 docs/cycle-history.md 최신순 맨 앞에 본문 섹션으로 이관"*. 세션16 trailing sync 4건(#1281·#1283·#1287·#1290)은 전부 종합 수치·추적셀만 고쳤다 — `cb2d9657`(#1290, 제목 *"세션16 **종료** trailing sync"*) stat = README×2·STATE(4줄)·backlog·런북2, cycle-history **없음**. 결과: 세션16 의 8 PR(심의 게이트 P0 #1279, R7 CI 배선 #1288, R51/R52/R54 종결 포함) 서사가 commit body 외 어디에도 없다. 가드 부재: `check_toc_anchors.py:19` 는 앵커 정합만 보고, `check_memory_refs.py:29` 는 cycle-history 를 **명시 제외**한다 — 신선도 축 관측자 0.
- **처방**: 세션15·세션16 서사를 cycle-history 최신순 맨 앞에 이관하고 STATE 최신=세션16 / 직전=세션15 로 체인을 복구한다. 근본 시정으로는 `pre_push_gate` 또는 repo-integrity 에 **advisory 신선도 체크** 1종 추가 — `docs/cycle-history.md` 최종 커밋 이후 머지 PR 수가 임계(예: 10)를 넘으면 loud 경고(카덴스 훅과 동형, 비차단·정책 17). 지금은 21 PR 이 조용히 통과했다.
- **판정**: `CONFIRMED` — 모든 인용을 독립 재현했고 전건 일치한다. `git log -1 -- docs/cycle-history.md` = `2cf7ba07`(#1272, 2026-08-02)이고 `git log 2cf7ba07..main | wc -l` = **21** 인데 그 21 PR 동안 cycle-history touch **0**. `grep -c "세션1[56]"` = **0**(exit 1). `docs/cycle-history.md:9` TOC 최상단 = 세션14, 본문 최신 헤딩도 `:154` 세션14. `docs/STATE.md:9` = `**최신 (2026-08-04 세션15 … PR #1274~#1276)**`, `:22` = `**직전 (2026-08-02 세션14 …)**` — 라인 번호까지 정확. `STATE.md:7` 의 자체 절차 (1) 최신 교체 / (2) 직전 서사 cycle-history 이관 / "직전 체인 누적 금지" 도 원문 그대로. `cb2d9657`(#1290, 제목 "세션16 **종료** trailing sync") stat 은 README.ko·README·STATE(4줄)·backlog·owed-verification·operati

### [decision] backlog 가 스스로 "Claude 가 임의 결정하지 않는다"고 못박은 High-tier 결정을 Claude 가 종결 — 같은 원장의 형제 행은 사용자 결정을 인용하는데 이 행만 없다

- **위치**: `docs/backlog.md:51`
- **주장**: docs/backlog.md:51 (R52) 은 CSP/폰트 처리 방향을 *"보안 자세 변경 ↔ 시각 변경으로 갈리므로 정책 15 High tier(사전 확인) + 정책 11(시각 검증 불가)에 해당해 **Claude 가 임의 결정하지 않는다**"* 로 명시하고, #1291 본문도 *"🔴 CSP 결정 — 아래 표에서 골라 주세요. 제가 정하지 않았습니다"* 로 사용자에게 넘겼다. 그런데 같은 행이 *"종결 (#1294, 2026-08-06)"* 로 닫히고 #1294 는 ㉰(링크 제거)를 실행했는데, **행에도 PR 본문에도 사용자 결정 인용이 없다**. 대조군이 결정적이다 — 하루 전 같은 원장의 R7 행(:143)은 *"종결 (#1288, 2026-08-05 — **사용자 결정 ㉮ "빨간 채로 머지"**)"* 로 인용을 남겼고, 원장 전체에 `사용자 결정` 인용이 14회 있다. 즉 기록 관행은 존재하는데 **High-tier 로 스스로 격상한 바로 그 항목에서만** 빠졌다. 재측정 결과(시각 변화 0)가 옳더라도 절차상 정답은 '측정으로 뒤집힌 표를 다시 제시하고 결정을 받는 것'이었다 — 정책 9 완화는 (c) architecture/UX/데이터 모델 결정을 자율판단 보고로 대체할 수 없는 영역으로 명시한다.
- **근거**: docs/backlog.md:51 (`Claude 가 임의 결정하지 않는다` 와 `종결 (\`#1294\`, 2026-08-06)` 이 **같은 줄**에 공존, 그 사이 사용자 결정 인용 0) · docs/backlog.md:143 (형제 행 R7 = `사용자 결정 ㉮ "빨간 채로 머지"` 인용) · `grep -c "사용자 결정" docs/backlog.md` → 14 · PR #1294 본문 27행 *"무해한 쪽은 ㉰ 였습니다. ㉰ 로 진행했습니다"* (승인 인용 없음) · PR #1291 본문 106행 *"제가 정하지 않았습니다"* · CLAUDE.md 정책 9 완화 미적용 3영역 (c)
- **처방**: R52 종결 셀에 **사용자 결정 인용을 넣거나, 없으면 '측정으로 전제가 뒤집혀 Claude 가 재판단 — 사용자 사후 확인 필요' 로 상태를 낮춰** 기록한다(#1294 는 아직 OPEN 이므로 머지 전 수정 가능). 구조적 처방: backlog 행이 `High tier`/`임의 결정하지 않는다`/`사용자 결정` 어휘를 담은 채 ✅ 로 플립될 때 **같은 셀에 사용자 결정 인용이 없으면 red** 인 축을 `tests/unit/scripts/test_backlog_shape.py` 에 추가(R41 이 지적한 '✅ 마커가 미결 잔여를 흡수' 와 같은 뿌리, 반증 수단 = R7 행은 green·R52 행은 red).
- **판정**: `CONFIRMED` — 전 인용 실측 통과. docs/backlog.md:51 한 줄에 `Claude 가 임의 결정하지 않는다` 와 `종결 (\`#1294\`, 2026-08-06)` 이 실제로 공존하고 그 사이 사용자 결정 인용 0. 형제 대조군 :143(R7 = `사용자 결정 ㉮ "빨간 채로 머지"`) 존재, `grep -c "사용자 결정"` = 14 확인. PR #1294 본문 27행 "무해한 쪽은 ㉰ 였습니다. ㉰ 로 진행했습니다"(승인 인용 0), #1291 본문 106행 "제가 정하지 않았습니다" 확인. CLAUDE.md 정책 9 완화 미적용 (c) architecture/UX/데이터 모델 문구도 확인.

독립 검증에서 발견자가 놓친 2건 — (약화 1) **#1294 는 아직 OPEN 이다**(`mergedAt: null`, 생성 2026-08-05). `종결` 문구는 main 에 없고(`git show main:docs/backlog.md | grep -c` → 0) 그 PR 브랜치 커밋 226cd4a9 안에만 산다. 즉 "행이 닫혔다"는 서술은 원장 정본(main) 기준으로는 아직 참이 아니고, 사용자 머지가 여전히 관문이다. 또 #1294 본문은 뒤집힌 비교표를 

### [decision] 정책 1 옵션 표에 측정 술어가 없어 ★ 권장이 실제로 가장 위험한 안을 가리켰다 — AGENTS.md 신설 측정 규율도 이 클래스를 덮지 않는다

- **위치**: `CLAUDE.md:121`
- **주장**: #1291 이 사용자에게 낸 4-옵션 결정 표는 ㉰(링크 제거) 단점을 *"한글 렌더가 눈에 띄게 바뀜"* 으로, ㉮(vendoring)를 ★ 권장 + *"무해한 복구"* 로 적었다. 다음 PR 의 Playwright 실측이 **두 셀 모두 거짓**임을 확정했다 — 외부 스타일시트는 CSP 로 BLOCKED, `document.fonts.size == 0`, 즉 14개월간 폰트가 적용된 적이 없어 ㉰ 는 시각 변화 0 이고 오히려 **★ 를 붙인 ㉮ 가 14개월 만의 타이포그래피 변경**이었다. 사용자가 표대로 ㉮ 를 골랐다면 정책 11(시각 검증 사용자 의무) 부담을 지는 쪽을 '무해' 라는 라벨로 고른 셈이다. 근본은 개인 실수가 아니라 **정책의 공백**이다: CLAUDE.md:121 은 표 형식(5컬럼 + ★ + 고려했으나 제시 안 한 안)만 규정하고 **장점/단점/위험 셀의 근거 등급(실측 vs 추정)을 요구하지 않는다**. 정책 6 은 line:span 인용에 `grep -n` 실측을 강제하는데, 사용자 결정을 직접 좌우하는 장단점 셀에는 그런 술어가 없다. #1293 이 신설한 AGENTS.md:110 §측정 규율도 적용 대상이 *"숫자나 판정을 내놓는 도구"* 라 **측정을 아예 하지 않고 쓴 단언**은 5개 규칙 어디에도 걸리지 않는다.
- **근거**: PR #1291 본문 108-113행 옵션 표 (㉰ 단점 *"한글 렌더가 눈에 띄게 바뀜"* · ㉮ ★ 권장) · PR #1294 본문 20-27행 반전 표 (*"제가 적었던 것 / 실제"*) 및 커밋 226cd4a9 제목부 *"결정 표를 내기 전에 측정했어야 했다"* · CLAUDE.md:121 (표 형식만 규정, 근거 등급 없음) · CLAUDE.md:119 사용자 발화 *"제가 판단하는데 도움이 될거라"* · AGENTS.md:117-119 (적용 대상 = 도구가 낸 숫자) · AGENTS.md:131-140 (규칙 5건 모두 도구 검증 축)
- **처방**: 정책 1 표 형식에 **근거 열 또는 셀 라벨을 추가**한다 — 장점/단점/위험 각 셀은 (a) 실측(명령·출력 1줄 동반) 또는 (b) `추정:` 접두사 중 하나. ★ 권장은 **실측 셀에만** 붙일 수 있게 한다. AGENTS.md §측정 규율에 6번째 규칙으로 *"사용자 결정을 요청하는 표의 셀은 측정하거나 '미측정' 이라고 적는다 — 측정하지 않은 단언은 도구 오류보다 더 조용하다"* 를 추가(현행 5규칙은 전부 '도구가 틀렸을 때' 축이라 '도구를 아예 안 썼을 때' 가 사각).
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. CLAUDE.md:119/121 은 회고 기준선(faeb2cf1~1)에서 정확히 성립 — :119 = 사용자 발화 "제가 판단하는데 도움이 될거라", :121 = 표 형식만 규정(5컬럼 + ★ + "고려했으나 제시 안 한 안"). #1293 이 CLAUDE.md 를 422→195 줄로 압축해 정책 1 은 현재 CLAUDE.md:75 로 이동했으나 그 줄도 옵션·장점·단점·위험·권장시점 + ★ 만 열거하므로 공백은 이동 후에도 그대로다(drift 는 인용 형식 문제일 뿐 실질 무영향). AGENTS.md:117-119(적용 대상 = 도구 예시 일색) · :131-140(규칙 5건 전부 도구 실행 전제) 축자 확인. PR #1291 본문 108/110/112 행(㉮ ★ 권장 · ㉰ 단점 "한글 렌더가 눈에 띄게 바뀜") · PR #1294 본문 22/24/25 행 반전 표 · 커밋 226cd4a9 본문 표제 "🔴 결정 표를 내기 전에 측정했어야 했다" + Playwright 블록(document.fonts.size 0 · cssRules BLOCKED) 모두 확인.

반증 시도 4건 전부 실패: (1) 기존 커버 여부 — 정책 1 진화 3

### [decision] backlog 🔴 결정 대기 항목이 세션 진입마다 회신 요청되지 않는다 — 원장 자기 규칙 위반 + SessionStart 관측면 0, R0-2 는 5일·4세션째 R28 을 차단 중

- **위치**: `docs/backlog.md:252`
- **주장**: docs/backlog.md:252 는 *"🔴 결정 대기 항목은 다음 사이클 진입 시 사용자 회신 요청 의무(정책 5/9 페어)"* 를 원장 자기 규칙으로 못박는다. 실측하면 현재 창의 유일한 🔴 R48(6-step ② 규범 유지 vs 정식화)과 역사 창의 🔴 R0-2(owed 원장 완전성 축)는 **세션16·세션17 어느 PR 본문에서도 회신 요청되지 않았다** — #1279·#1281·#1290·#1291·#1292·#1293·#1294 7건 전수 grep 결과 R48/R0-2 언급 0(#1281 의 유일한 '결정 대기' 히트는 별건 R45-a). R0-2 는 2026-08-01(#1249) 등재 이후 R28 을 *"R0-2 회신 시 함께 착수"* 로 명시 차단하고 있어, **결정 미회신이 엔지니어링 일감을 무기한 정지**시킨다. 기전은 관측면 부재다: `.claude/settings.json` SessionStart 훅은 3개(`check_retro_cadence` · `check_owed_verification` · `check_precommit_installed`)이고 **backlog 결정 대기를 읽는 것은 0개** — owed 원장은 2026-07-19 P0 로 기계 배선됐는데(*"문서-only 시정은 행동을 못 바꾼다"* 3회차 학습) 결정 대기 축만 산문으로 남았다. 부수 증거로 R48 이 명명한 결함 클래스(*"정책 3은 보고 의무이지 다른 정책의 금지를 해제하는 권한이 아니다"*)는 이 창에서 **정책 19 자기면제 6건과 R52 High-tier 자기 종결 1건으로 재발**했다 — 결정이 대기하는 동안 그 결정이 다루려던 클래스가 계속 번식했다.
- **근거**: docs/backlog.md:252 (자기 규칙) · :44 (R48 = 🔴, 2026-08-04 회고 이관) · :135 (R0-2 = 🔴 P0) · :103 (R28 *"R0-2 회신 시 함께 착수"*) · `git log -S "R0-2" -- docs/backlog.md` → bb038ece 2026-08-01 (#1249 등재) · docs/STATE.md:23 이 마지막 언급(세션13, *"정책 3 보고"*) · .claude/settings.json `hooks.SessionStart` 3종 실측(backlog 파서 0) · PR 본문 grep 실측 7건 0 hit
- **처방**: owed 원장과 동형으로 **기계 배선**한다 — `scripts/check_decision_backlog.py`(가칭)가 `docs/backlog.md` 의 🔴 행을 파싱해 (a) 항목 수 (b) 각 항목의 등재 이후 경과 세션/머지 PR 수 (c) 그 항목이 차단 중인 🟡 행을 SessionStart 에 loud 출력(advisory·exit 0, 정책 17 안정성). 파서 계약은 owed 원장과 같은 실패 모드를 피하도록 `test_live_backlog_parses_nonempty` 동반. 최소 조치로는 trailing sync PR 의 §"🔍 사용자 검증 필요" 템플릿에 **'🔴 결정 대기 N건 — 회신 요청' 행을 고정 슬롯**으로 넣는다(현재 이 섹션은 owed 원장 항목만 싣는다 — #1290 실측).
- **판정**: `CONFIRMED` — 전 인용 실측 확인. (1) docs/backlog.md:252 자기 규칙 *"🔴 결정 대기 항목은 다음 사이클 진입 시 사용자 회신 요청 의무(정책 5/9 페어)"* 원문 일치. (2) :44 R48 🔴(8f4ada5a #1274, 2026-08-04 등재) · :135 R0-2 🔴 P0 · :103 R28 *"R0-2 회신 시 함께 착수"* 전부 원문 일치 — 결정 미회신이 엔지니어링 일감을 실제로 정지시킨다는 부분은 원장 본문에 명문화돼 있다. (3) `git log -S "R0-2" -- docs/backlog.md` → bb038ece 2026-08-01(#1249) 확인, 이후 세션14/15/16/17 경과 = "5일·4세션째" 성립. (4) 기전 확인 — `.claude/settings.json hooks.SessionStart` 는 정확히 3종(check_retro_cadence·check_owed_verification·check_precommit_installed)이고 scripts/·.claude/hooks/ 전수 grep 결과 **backlog 🔴 를 읽는 코드는 0**. 유일한 backlog 가드 tests/unit/scripts/te

### [tooling] E2E 축에 가드가 0개다 — 배선한 그 사이클 안에서 이미 STATE 내부 drift 발생 (R25 결함 클래스 재생산)

- **위치**: `docs/STATE.md:38`
- **주장**: `#1288`(02b3e867)로 E2E 121건을 CI 에 배선하고 `2478c416` 로 배지를 초록으로 올렸으나, E2E 수치·상태를 지키는 기계 축이 **하나도 없다**. 결과는 즉시 나타났다 — 같은 파일 안에서 `docs/STATE.md:32` 는 `E2E **121**`, `docs/STATE.md:38` 은 `**122개**` + `= 122 collected (110 표준 + 12 perf)` 로 **동시 주장**한다. 이는 R25(`check_docs_sync` 는 문서 사본끼리만 대조 → 4지점이 함께 틀리면 항상 GREEN)가 단위 카운트 축에서 닫은 결함을, 한 사이클 뒤 신규 축에서 그대로 재생산한 것이다.
- **근거**: `grep -n` 실측: `docs/STATE.md:32` = "E2E **121** (`#1291` 이 중복 1건 제거) — CI 실측 **120 통과 / 1 skip / 0 실패**" / `docs/STATE.md:38` = "| E2E 테스트 | **122개** | … **= 122 collected (110 표준 + 12 perf)**" / `README.md:22`·`README.ko.md:22` = `E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen`. 가드 부재 실측: `scripts/check_docs_sync.py:41` `_README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\((\d+)_unit_%2B_\d+_integration\)")` — **Tests 배지만** 매칭하므로 E2E 배지는 사본 대조조차 안 된다. `scripts/check_test_count_sync.py:116-117` = `collect_count("tests/unit")` + `collect_count("tests/integration")` — `e2e/` 는 ground-truth 수집 범위 밖. `grep -n "e2e|E2E" scripts/check_test_count_sync.py scripts/check_docs_sync.py` → **0 hits**. 게다가 배지는 이제 수치가 아니라 **라이브 CI 결과**("120 pass / 1 skip")를 주장하는데, `.github/workflows/ci.yml:499` 가 "required check 로 승격하지 않았다" 를 명시하므로 e2e 가 빨개져도 초록 배지를 무너뜨릴 기전이 없다.
- **처방**: `check_test_count_sync.py` 에 `collect_count("e2e")` 축을 추가하고 STATE 의 E2E 표기 2지점(`:32` 종합수치 · `:38` 추적셀) + README 2 배지를 같은 ground-truth 로 대조한다. 배지가 pass/skip **결과**를 주장하는 것은 별도 축이므로 (a) 결과 주장을 배지에서 빼고 수치만 남기거나 (b) e2e 를 required check 로 승격해 초록 주장에 집행면을 주거나 둘 중 하나를 선택한다 — 지금은 주장만 있고 유지 기전이 없다. 우선 즉시 `STATE.md:38` 의 122 → 121 정정.
- **판정**: `CONFIRMED` — 전 인용 좌표 실측 재확인 + 라이브 수집으로 ground truth 확정 — 주장보다 drift 가 오히려 더 깊다.

[인용 검증 · 전건 존재]
- docs/STATE.md:32 = "E2E **121** … CI 실측 **120 통과 / 1 skip / 0 실패**" ✓
- docs/STATE.md:38 = "| E2E 테스트 | **122개** | … **= 122 collected (110 표준 + 12 perf)**" ✓ (동일 파일 내 동시 주장 확인)
- README.md:22 / README.ko.md:22 = E2E-121 brightgreen 배지 ✓
- scripts/check_docs_sync.py:41 = _README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\((\d+)_unit_%2B_\d+_integration\)") ✓ — Tests 배지 전용, E2E 배지는 사본 대조조차 안 됨
- scripts/check_test_count_sync.py:116-117 = collect_count("tests/unit") + collect_count("tests/integration") ✓ — e2e/

### [tooling] pre_push_gate 의 '보지 못하는 축' 목록이 e2e 배선과 함께 stale — 그걸 막을 회귀 가드가 job 이 아니라 스크립트만 본다

- **위치**: `scripts/pre_push_gate.py:89`
- **주장**: `pre_push_gate.py` 의 존재 이유는 "여기 초록 ≠ CI 초록" 을 매 실행 인쇄하는 것인데(`:218` 주석: *"이 목록을 출력 끝에 항상 인쇄한다 — '여기 초록 = CI 초록' 으로 읽히면 새 observer-lie 다"*), `#1288` 이 20~30분짜리 **e2e job 을 CI 에 신설했는데 그 목록에 e2e 가 없다**. 러너 자신이 경고한 그 observer-lie 를 러너가 만들었다. 회귀 가드는 이 축을 원리적으로 못 잡는다 — `test_runner_covers_every_ci_guard_script` 는 ci.yml 에서 `scripts/check_*.py` 호출만 파싱하므로, **가드 스크립트가 아닌 job 이 추가되면 절대 발화하지 않는다.**
- **근거**: `grep -n "e2e|E2E|Playwright" scripts/pre_push_gate.py` → **EXIT=1 (0 hits)**. `_NOT_COVERED` = `scripts/pre_push_gate.py:89-95` (CodeQL·Sonar·Codecov / TruffleHog·pip-audit / lint-js / PG-only / tests/integration — 5항목, e2e 없음). 신설 job = `.github/workflows/ci.yml:501` `e2e:` (`:504` name `E2E (Playwright)`, `:508` timeout-minutes: 30). 가드 범위 = `tests/unit/scripts/test_pre_push_gate.py:58-60` `covered = set(gate._INTEGRITY) | set(gate._DIFF_SCOPED) | {...}` / `missing = ci_guard_scripts() - covered`, `:39-40` `ci_guard_scripts()` = `_CI_SCRIPT.findall(...)`. 같은 stale 목록이 2곳에 복제됨: `CLAUDE.md:352` "(CodeQL·Sonar·Codecov·TruffleHog·pip-audit·lint-js·PG job·통합테스트)" · `.claude/rules/guards.md:218` 동일 열거 — 셋 다 e2e 누락.
- **처방**: `_NOT_COVERED` 에 "e2e (Playwright) — node + chromium 필요" 추가 + `CLAUDE.md:352`·`.claude/rules/guards.md:218` 동시 갱신(3지점 동시 편집 = 정책 16 grep 전수). 근본 시정은 가드 범위 확장: `ci.yml` 의 **job 이름 집합**을 파싱해 `_NOT_COVERED ∪ 러너 실행 대상` 이 전 job 을 덮는지 대조(신규 job 추가 시 red). 지금 가드는 `check_*.py` 축만 닫아 '가드 스크립트 없는 신규 job' 을 영구 사각으로 남긴다.
- **판정**: `CONFIRMED` — CONFIRMED at P1. Every load-bearing citation reproduces. (1) Staleness is real: `scripts/pre_push_gate.py:89-95` `_NOT_COVERED` holds exactly 5 entries and `grep -niE "e2e|playwright" scripts/pre_push_gate.py` returns EXIT=1 / 0 hits, while `.github/workflows/ci.yml:501` `e2e:` (`:504` name `E2E (Playwright)`, `:508` timeout-minutes 30) was added by 02b3e867 (#1288) and fires on BOTH `push:[main]` and `pull_request:[main]` (`ci.yml:4-7`) — a 20-30 min CI axis the runner cannot see and does not declare. The runner's own `:218` docstring ("여기 초록 = CI 초록 으로 읽히면 새 observer-lie 다") plus `:221`'s it

### [process] CLAUDE.md 424→196 재작성이 정책 17 원칙 3 게이트(5+1 회의·운영 검증·사용자 옵션 표)를 거치지 않았고, 같은 세션 자기 감사 결론과 모순

- **위치**: `CLAUDE.md:90`
- **주장**: 정책 17 원칙 3 은 '매 분리 단계마다 5+1 회의 + 운영 검증 + 사용자 옵션 표 결정' 을 요구하는데, 19개 정책 전부를 단일 커밋에서 표+external 로 일괄 전환했고 옵션 표·backlog 결정행·회의 보고서가 어디에도 없다. 더 나쁜 것은 하루 전 R54 감사(Claude 11-에이전트 + Grok 독립, 총평 4/10)가 '총량 가설은 기각됐다 … 실수 10건 중 총량으로 설명되는 것 0건' 이라 결론냈는데, 이 커밋의 목표가 정확히 총량 −49% 라는 점이다.
- **근거**: CLAUDE.md:90 = *"🔴 매 분리 단계마다 **5+1 회의 + 운영 검증 + 사용자 옵션 표 결정**"* (규칙은 살아 있다). 7ab96205 commit body = *"424 → 196줄 · 21,236 → 10,917 토큰(-49%) · 강제 로드 12.3% → 7.1%"*. docs/backlog.md:55 (R54) = *"🔴 **총량 가설은 기각됐다** … 실수 10건 중 총량으로 설명되는 것 0건(문서구조 3 · 도구사용 4 · 판단오류 3)"*. `gh pr view 1291/1292/1293 --json body` grep(CLAUDE.md·200줄·슬림·축소) = 옵션 표 0건. `ls -t docs/_archive/reports/` 최신 = 2026-08-04-retrospective.md (08-05/06 회의 보고서 없음). 사후 Grok claim-review `8eccb444` 가 행동 규칙 8건 소실을 BROKEN 판정 — 사전 게이트가 있었으면 소실 자체가 없었을 축이다.
- **처방**: 토큰 단위 정정(bytes÷3 오류)은 총량 수치의 크기를 바꿨을 뿐 '실수 10건 중 총량 귀속 0건' 이라는 기각 근거를 되살리지 않는다. 재작성을 머지하기 전에 (a) 기각된 가설을 뒤집는 새 근거를 명시하거나 (b) 정책 17 원칙 3 대로 옵션 표를 내고 사용자 결정을 받은 뒤 단계 분할로 재진행한다.
- **판정**: `CONFIRMED` — 모든 1차 인용을 실측 재확인했고, 핵심 주장(정책 17 원칙 3 게이트 미통과)은 성립한다. 단, 발견자의 증거 경로 1건은 빗나갔다.

■ 인용 검증 (전건 실측)
- `CLAUDE.md:90` — `grep -n "매 분리 단계마다"` → **90** 정확. 정책 17 행에 *"🔴 매 분리 단계마다 **5+1 회의 + 운영 검증 + 사용자 옵션 표 결정**"* 실재. 규칙은 HEAD 에서 살아 있다(아이러니: 바로 이 커밋이 삭제했다가 Grok 지적으로 복원한 줄).
- `7ab96205` commit body — *"424 → 196줄 · 21,236 → 10,917 토큰(-49%) · 강제 로드 12.3% → 7.1%"* 축자 일치.
- `docs/backlog.md:55` (R54) — *"🔴 총량 가설은 기각됐다 … 실수 10건 중 총량으로 설명되는 것 0건(문서구조 3 · 도구사용 4 · 판단오류 3)"* 축자 일치, 줄 번호 정확.
- `ls -t docs/_archive/reports/` 최신 = `2026-08-04-retrospective.md`. 08-05/08-06 회의 보고서 **0건**. `git log --diff-filter=

### [process] 완료 6-step ⑤ 절반 미이행 — docs/cycle-history.md 가 20 PR·4 세션 stale, 관측자 0

- **위치**: `docs/cycle-history.md:5`
- **주장**: ⑤ 는 'docs/STATE.md 수치 갱신 + docs/cycle-history.md 사이클 이력 동기화' 두 축인데, 최근 4 세션의 trailing sync PR 이 STATE 축만 이행했다. 서사 SSOT 는 #1272(2026-08-02) 이후 20건 머지(#1273~#1293) 동안 한 줄도 추가되지 않았고, 이 파일은 스스로 '회고 시점 read 의무' 를 선언한다 — 즉 지금 이 회고가 20 PR stale 한 서사를 읽고 있다.
- **근거**: `git log -3 -- docs/cycle-history.md` 최신 = 2cf7ba07 (2026-08-02, #1272). docs/cycle-history.md:5 = *"본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무"*. `gh pr view 1290 --json files` = README.ko.md·README.md·docs/STATE.md·docs/backlog.md·operational-smoke-checks.md·owed-verification.md — cycle-history.md 부재이며 본문 ⑤ 줄은 *"수치 (6-step ⑤) | 6829 → 6832 … 4곳"* 로 수치 축만 청구한다(#1277·#1281·#1283·#1287 동일). 신선도 가드 부재 실측: `grep -rn cycle-history scripts/*.py` → check_toc_anchors.py:19 (앵커 정합만) · check_memory_refs.py:29 (의도적 제외) 뿐.
- **처방**: ⑤ 의 두 축을 한 줄에 묶어 청구하지 말고 PR 본문에 축별 체크박스로 분리한다. 최소 관측면 = `check_docs_sync.py` 에 'cycle-history 최신 항목의 PR 번호 < HEAD 기준 최신 머지 PR − N' 이면 advisory 경고(정책 17 비차단 유지).
- **판정**: `CONFIRMED` — 모든 file:line 인용이 실측 일치. (1) `git log -1 -- docs/cycle-history.md` = 2cf7ba07 (2026-08-02, #1272); `git log 2cf7ba07..main -- docs/cycle-history.md` = **0건**, 같은 범위 `-- docs/STATE.md` = **9건** — ⑤ 두 축이 기계적으로 갈라진 것이 실측됨. (2) cycle-history.md:5 = "본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무." 정확. (3) `gh pr view 1290 --json files` = 인용된 6파일 그대로, cycle-history.md 부재 (#1287 도 README×2+STATE 뿐). (4) 관측자 부재 실측 확대: check_toc_anchors.py:19(앵커만) · check_memory_refs.py:29(의도적 제외) 외에 `grep -n cycle scripts/check_docs_sync.py` = **0 hit**, `scripts/pre_push_gate.py` = 0 hit.

정정 2건(모두 과소·라벨 오류 — 실질

### [process] ⑤ 배치-PR 이월 분기 위반 — in-flight PR 과 같은 README/STATE 줄을 3연속 편집해 squash 후 충돌을 자초

- **위치**: `docs/STATE.md:287`
- **주장**: '세션 내 동일 파일(STATE.md 수치 라인·README 배지)을 건드리는 미머지 PR 이 1건 이상 in-flight 이면 STATE/배지 실갱신을 trailing sync 로 이월한다' 는 분기가 있는데, open PR #1294 가 README.md:21-22 + docs/STATE.md 를 편집한 상태에서 후속 커밋 2478c416·7ab96205 이 같은 배지 줄과 같은 STATE 셀을 다시 편집했고, 7ab96205 는 그 미머지 PR 위에 PR 없이 스택됐다.
- **근거**: `gh pr view 1294 --json files` = README.ko.md·README.md·docs/STATE.md 포함(+ci.yml·backlog·templates·tests). `git show 2478c416 -- README.md` = E2E 배지 `122_in_CI_(119_pass…)-yellow` → `121_in_CI_(120_pass_/_1_skip)-brightgreen` (line 22). `git diff main..7ab96205 -- README.md` = **같은 21~22 블록**의 Tests 6846→6876 + E2E 재편집. 머지 방식 = squash 실측: `git log -6 --format='%h parents=%p %s' main` 전건 단일 부모 + `(#NNNN)` 접미. 따라서 #1294 가 squash 되면 스택 브랜치의 226cd4a9·d82192fd·2478c416 이 재적용되며 동일 배지 줄에서 충돌한다 — CLAUDE.md 가 이 분기의 전례로 적어 둔 #1048 과 같은 형태.
- **처방**: #1294 머지 직후 docs/claude-md-under-200 을 main 에 rebase 해 중복 3커밋을 떨어뜨린 뒤 PR 을 만든다. 이후에는 배치 분기 판정을 습관이 아니라 명령으로 고정 — PR 착수 전 `gh pr list --json files --jq 'select(.files[].path=="docs/STATE.md")'` 1줄 확인을 6-step ⑤ 체크박스로 넣는다.
- **판정**: `CONFIRMED` — Rule violation is real and the predicted consequence is empirically demonstrated, not inferred. (1) The rule exists verbatim and is 🔴-marked: CLAUDE.md:354 on main (CLAUDE.md:145 on the #1295 branch) — "미머지 PR 이 1건 이상 in-flight 이면 … STATE/배지 실갱신은 단일 trailing sync PR 로 이월". (2) Precondition met: PR #1294 (fix/csp-font-r52, base=main, OPEN, created 2026-08-05T16:09Z) edits README.md +2/-2, README.ko.md +2/-2, docs/STATE.md +3/-2. (3) Violation: PR #1295 (docs/claude-md-under-200, base=**main**, created 17:38Z) stacks 7ab96205 on that unmerged branch and re-edits the SAME README.md 21~22 block (T

### [process] 신설 행동 규칙 가드가 소실 범위를 한정하지 못한다 — 손으로 고른 25 어휘 vs 실측 '의무' 62→20 · 'default' 41→7

- **위치**: `tests/unit/scripts/test_claude_md_behavior_rules.py:35`
- **주장**: test_claude_md_behavior_rules.py 는 삭제 8건을 낸 것과 같은 판단이 고른 리터럴 25개만 본다. 즉 커버리지가 자기 인증이고, 실제로 사라진 지시문의 양을 한정하지 못한다. 특히 정책 17 원칙 3('5+1 회의 + 운영 검증 + 사용자 옵션 표 결정', CLAUDE.md:90) 에 대응하는 needle 이 없어, 다음 슬림화가 '슬림화에 사용자 승인을 요구하는 그 줄' 을 지워도 27건 전건 초록이다.
- **근거**: tests/unit/scripts/test_claude_md_behavior_rules.py:35 `_BEHAVIOR_RULES = [` 이하 25항목 — 정책 17 항목은 :53('안정성과 충돌하면 거부')·:54('본문 보존 default') 둘뿐이고 원칙 3 어휘 부재. 실측 대조(python `.count()`, main:CLAUDE.md vs 작업본): '의무' 62→20 · 'default' 41→7 · '정책' 99→33 · 줄 423→195 · 문자 29,260→15,830. 즉 42개 '의무' 문장이 본문에서 사라졌는데 가드는 25 어휘만 고정한다.
- **처방**: needle 목록을 손으로 늘리는 대신, 축소 이전 파일에서 기계 추출한 지시문 집합(예: '의무'·'금지'·'default' 를 포함한 문장)을 스냅샷으로 고정하고 external 이관분은 `.claude/policies/**` 에 실재하는지 대조한다(양방향 = 본문 보존 축 + 소실 0 축). 최소한 정책 17 원칙 3 needle 을 즉시 추가한다.
- **판정**: `SEVERITY_ADJUST` — 인용·수치 전건 실측 일치, 그리고 뮤테이션으로 결함을 재현했다. P2 → P1 상향.

## 인용 검증 (전건 일치)
- `tests/unit/scripts/test_claude_md_behavior_rules.py:35` = `_BEHAVIOR_RULES = [` ✓, 항목 25개(:36~:60) ✓
- :53 = `"안정성과 충돌하면 거부"`(정책 17 원칙 1), :54 = `"본문 보존 default"`(원칙 4) — 정책 17 needle 은 이 둘뿐, 원칙 3 어휘 부재 ✓
- `CLAUDE.md:90` = 정책 17 표 행, 원문 `🔴 매 분리 단계마다 **5+1 회의 + 운영 검증 + 사용자 옵션 표 결정**.` 실재 ✓
- 실측 대조(main=faeb2cf1 vs 작업본 HEAD=7ab96205), python `.count()` 재현: 줄 **423→195** · 문자 **29,260→15,830** · '의무' **62→20** · 'default' **41→7** · '정책' **99→33** — 보고 수치와 완전 일치 ✓

## 뮤테이션 실증 (주장 이상으로 나쁨)
1. `CLAUDE.md:90` 에서 원칙 3 절만 삭제 → `tes

### [code] Anthropic 응답을 4곳 모두 `content[0].text` 로 인덱싱 — 첫 블록이 text 가 아닌 모델/설정에서 전부 조용한 `api_error`

- **위치**: `src/analyzer/io/ai_review.py:176`
- **주장**: 구조화 출력을 3경로로 확대하면서도 응답 추출은 여전히 `response.content[0].text` 다(4 call site). Anthropic 공식 구조화 출력 예시조차 `next(b.text for b in response.content if b.type == "text")` 로 **블록 타입을 걸러** 읽는다. 리뷰 모델은 `review_model` 에 validator 가 없고 `CLAUDE_REVIEW_MODEL` 도 자유 문자열이라, thinking 이 기본 ON 인 모델 계열을 지정하면 `content[0]` 이 thinking 블록이 되어 `.text` 가 AttributeError → 광범위 except → `api_error` + 기본 점수. 현재 선택지(4.6/4.7 계열)는 thinking off 기본이라 지금은 터지지 않지만, 모델 한 줄 교체가 전 파이프라인을 조용히 무력화하는 구조다.
- **근거**: src/analyzer/io/ai_review.py:176 `result = _parse_response(response.content[0].text)` · src/services/dashboard_service.py:847 `return response.content[0].text` · src/services/repo_insight_service.py:455 `raw = response.content[0].text` · .claude/hooks/doc_review_gate.py:579 `text = msg.content[0].text` · src/config.py:38 `claude_review_model: str = "claude-sonnet-4-6"` (env 오버라이드 자유) · src/api/repos.py:58 `review_model: str | None = None` (validator 없음)
- **처방**: 공용 헬퍼 `first_text_block(response)` 를 만들어 `next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)` 로 4곳 일괄 교체하고, None 이면 명시적 `parse_error`(≠ api_error)로 구분 기록. 정책 16 §공유 로직 grep 전수 default 대상.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. ai_review.py:176 `_parse_response(response.content[0].text)` · dashboard_service.py:847 · repo_insight_service.py:455 · doc_review_gate.py:579 · config.py:38 `claude-sonnet-4-6` · api/repos.py:58 `review_model` (validator 없음) 전부 해당 라인에 존재. 추가로 claim 이 놓친 5번째 사이트 scripts/i18n_comments/translate_comments.py:245 도 동일 패턴 — 과대가 아니라 과소 계상.

기전 검증(Anthropic 공식 레퍼런스 대조): (1) 공식 계약이 "content 는 TextBlock/ThinkingBlock/ToolUseBlock 목록 — .text 접근 전 .type 확인 의무" 이며 구조화 출력 예시조차 `next(b.text for b in response.content if b.type == "text")` 로 필터한다. (2) thinking 은 Opus 5 · Sonnet 5 · Fable 5 · Myth

### [docs] STATE 지표표 E2E 셀만 갱신에서 빠졌다 — 122/12perf 대 실측 121/11, 그리고 check_docs_sync 는 E2E 축을 아예 안 본다

- **위치**: `docs/STATE.md:38`
- **주장**: E2E 수치는 4지점(STATE 종합수치·STATE 지표셀·README 배지·README.ko 배지)에 복제돼 있는데 #1291(중복 1건 제거) 이후 3지점만 121로 갱신되고 STATE 지표셀만 122에 머물렀다. 게다가 그 셀의 내역 `110 표준 + 12 perf` 는 perf 개수까지 틀렸다(실측 11). `scripts/check_docs_sync.py` 는 단위/전체만 대조하고 E2E 문자열을 단 한 번도 읽지 않아 이 축은 구조적으로 무관측이다 — `.claude/rules/docs.md` 가 '표 셀에 다시 적지 말 것' 이라고 경고한 바로 그 형태가 E2E 축에서 그대로 살아 있다.
- **근거**: docs/STATE.md:32 = `E2E **121** (#1291 이 중복 1건 제거)` · docs/STATE.md:38 = `| E2E 테스트 | **122개** | … **= 122 collected (110 표준 + 12 perf)**` · README.md:22 / README.ko.md:22 = `E2E-121_in_CI_(120_pass_/_1_skip)`. 실측: `py -3 -m pytest e2e --collect-only -q` → `121 tests collected`; `-m perf` → `11/121 tests collected (110 deselected)` = 표준 110 + perf 11. 가드 공백: `grep -n "E2E|e2e|121|122" scripts/check_docs_sync.py` → 0 hit (295줄 전부). 전 가드 green 상태에서 재현(`tests/unit/scripts/test_docs_ledger_shape.py` 8 passed, `test_backlog_shape.py` 10 passed).
- **처방**: STATE.md:38 을 `121개` / `= 121 collected (110 표준 + 11 perf)` 로 정정하고, check_docs_sync 에 E2E 축(STATE 종합수치 ↔ STATE 셀 ↔ README 2배지)을 추가한다. 단위 축과 동일하게 SSOT 1지점 + `--fix` 파생으로 만들어 손유지 4지점을 없앤다. 회귀 가드는 셀을 122로 되돌리는 뮤테이션에서 red 여야 한다.
- **판정**: `CONFIRMED` — CONFIRMED at P1 — every citation and measurement independently reproduced, and the load-bearing guard-gap claim survives a stricter check than the finder performed.

CITATIONS (all exist as quoted): docs/STATE.md:32 = `E2E **121** (#1291 이 중복 1건 제거)`; docs/STATE.md:38 = `| E2E 테스트 | **122개** | … **= 122 collected (110 표준 + 12 perf)**`; README.md:22 = `E2E-121_in_CI_(120_pass_%2F_1_skip)`; README.ko.md:22 = `E2E-121_CI_배선(120_통과_%2F_1_skip)`; .claude/rules/docs.md:30 = `🔴 **표 셀에 다시 적지 말 것**`.

MEASUREMENT (re-run, not trusted): `py -3 -m pytest e2e --collect-only -q` → `121 tests collected`; `-

### [decision] CLAUDE.md 49% 축소가 정책 17 원칙 3/4 가 규정한 결정 절차(옵션 표·5+1 회의·High tier 사전 확인) 없이 자율 실행됐다

- **위치**: `CLAUDE.md:90`
- **주장**: 7ab96205 는 정책 5·8·9·11 을 포함한 정책 19건의 본문을 표 셀 + external 링크로 분리했다. CLAUDE.md:90 에 (복원되어) 살아 있는 정책 17 본문이 바로 그 행위를 규정한다 — '🔴 매 분리 단계마다 5+1 회의 + 운영 검증 + 사용자 옵션 표 결정. 🔴 매 작업/회고/PR 의무 영역(정책 8·11·5·9)은 본문 보존 default — 분리 시 High tier 사전 확인'. 커밋 본문 어디에도 (a) 옵션 표 (b) 5+1 다중 에이전트 회의 (c) 사용자 사전 확인 인용이 없다. 같은 창의 동급 결정은 인용을 남겼다(docs/backlog.md:143 R7 = "사용자 결정 ㉮ '빨간 채로 머지'"). 결과는 정책 17 이 예고한 그대로 — 행동 규칙 8건이 어디에도 남지 않았고, 자기 규정('외부 권장 규격은 안정성과 충돌하면 거부')을 지우면서 200줄을 맞췄으며, 회수는 사후 Grok claim-review(8eccb444, BROKEN)에만 의존했다.
- **근거**: CLAUDE.md:90 (정책 17 행 — 원칙 3/4 문언) · 7ab96205 커밋 본문 §조치 '정책 19건 → default rule 표 + external 링크' · 같은 본문 §Grok claim-review '행동 규칙 8건이 어디에도 남지 않았다 … 정책 17 원칙 1 = 200줄을 맞추려고 그 줄을 지웠다. 자기모순이다' · 대조군 = docs/backlog.md:143 (R7 사용자 결정 인용 형식)
- **처방**: 정책 17 원칙 3/4 적용 대상(CLAUDE.md 본문 분리)에 대해 사전 게이트를 명문화한다: 분리 PR 은 본문에 §'정책 17 결정 기록'(옵션 표 + 사용자 승인 인용 + 5+1 회의 run id)을 의무화하고, 없으면 scripts/check_claim_review_trace.py 와 같은 방식의 리포-무결성 가드로 차단. 이번 건은 사후 승인 인용을 커밋/PR 본문에 소급 기재한다.
- **판정**: `SEVERITY_ADJUST` — 인용 전건 실측 통과, 그러나 P0 를 떠받치던 핵심 limb 이 반증됐다.

**검증된 것**
- `CLAUDE.md:90` = 정책 17 표 행, 원칙 3/4 문언 실재 (`sed -n '90p'` — "🔴 매 분리 단계마다 5+1 회의 + 운영 검증 + 사용자 옵션 표 결정 … 정책 8·11·5·9 는 본문 보존 default — 분리 시 High tier 사전 확인"). ✓
- 대조군 `docs/backlog.md:143` = R7 행, 사용자 결정 ㉮ "빨간 채로 머지" 인용 실재. ✓
- 행위 당시 효력: `7ab96205^:CLAUDE.md:266-267` 에 원칙 3·4 원문 존재 — 폐지된 규정에 소급 적용한 것이 아님. ✓
- 7ab96205 커밋 본문 + PR #1295 본문 어디에도 옵션 표·5+1 기록·사용자 승인 인용 없음. ✓

**반증된 것 (P0 → P1 의 결정적 근거)**
세션 트랜스크립트 실측 결과 **원칙 4 의 High tier 사전 확인은 실제로 이행됐다**. 커밋(2026-08-05T17:27Z) 43분 전:
- 16:43:50Z assistant §제안 — "`CLAUDE.md` 424줄 → 200줄 미만으로 축소

### [decision] ⑤ 배치-PR 이월 분기(CLAUDE.md:145)를 위반해 미머지 PR 위에 STATE/배지를 재기록 — squash 후 3파일 충돌이 결정론적으로 재현된다

- **위치**: `CLAUDE.md:145`
- **주장**: CLAUDE.md:145 는 '세션 내 동일 파일(STATE.md 수치 라인·README 배지)을 건드리는 미머지 PR 이 1건 이상 in-flight 이면 per-PR ⑤는 commit body 에 카운트 delta 만 기록하고 실갱신은 세션 종료 trailing sync PR 로 이월' + 'PR 착수 전 gh pr list 로 동일 파일 touch 미머지 PR 존재 여부 1줄 확인 의무' 를 규정한다. #1294(OPEN, README.md·README.ko.md·docs/STATE.md 편집)가 in-flight 인 상태에서 7ab96205 가 같은 3파일을 다시 실갱신했고, 확인 1줄은 어디에도 기록되지 않았다. #1294 를 squash 머지한 뒤 이 브랜치를 main 에 올리는 시나리오를 git merge-tree 로 시뮬레이션하면 README.md·README.ko.md·docs/STATE.md 3파일 전부 CONFLICT 다 — 규칙이 2026-07-09 #1048 사고에서 배워 막으려던 실패 모드 그대로다.
- **근거**: CLAUDE.md:145 (⑤ 배치-PR 이월 분기) · `git commit-tree $(git rev-parse 2478c416^{tree}) -p faeb2cf1` → d4671cf4, `git merge-tree --write-tree --messages d4671cf4 7ab96205` → 'CONFLICT (content): README.ko.md / README.md / docs/STATE.md' 3건 · 기준값 대조: faeb2cf1:README.md:21 = 6846/6675, #1294 = 6849/6678, 브랜치 = 6876/6705 (같은 줄 3방향 분기)
- **처방**: 7ab96205 에서 README 2배지 + STATE 수치 3지점 변경을 되돌리고(가드 테스트와 CLAUDE.md 본문만 남김), 수치는 세션 종료 trailing sync 단일 PR 에서 check_docs_sync.py --fix 로 한 번에 파생시킨다. 또는 #1294 를 먼저 머지한 뒤 브랜치를 rebase 한다.
- **판정**: `CONFIRMED` — Independently reproduced in full; citation exact.

CITATION: grep -n confirms CLAUDE.md:145 is verbatim the "⑤ 배치-PR 이월 분기" rule, including both obligations cited — defer STATE/badge writes to a trailing sync PR when an in-flight PR touches them, and record a 1-line `gh pr list` check before starting.

FACTS RE-VERIFIED: #1294 (fix/csp-font-r52) is state=OPEN, base=main, and modifies README.md, README.ko.md, docs/STATE.md. 7ab96205 (PR #1295, also OPEN, also base=main) modifies the same three files. Badge divergence on the identical line README.md:21 is exactly as claimed — faeb2cf1=6846/6675,

### [tooling] 회고 범위 SSOT 도구가 '본 세션 산출물' 을 원리적으로 누락한다 — 그리고 /retrospective 워크플로는 그 도구를 아예 호출하지 않는다

- **위치**: `scripts/retro_scope.py:91`
- **주장**: 정책 8 진화 (5)는 회고 범위를 *"직전 회고 이후 머지 PR + **본 세션 산출물 전체**"* 로 규정하고 CLAUDE.md 가 `scripts/retro_scope.py` 를 기계 산출 SSOT 로 지목한다. 그러나 `merged_prs()` 는 커밋 제목 끝의 `(#NNNN)` 만 수집하므로 **PR 번호가 없는 미머지 세션 커밋은 전부 탈락**한다. 결과적으로 이 도구는 정책이 명명한 실패("가장 검증 덜 된 코드가 회고를 피한다")를 **그대로 재생산**한다. 게다가 `/retrospective` 워크플로는 이 스크립트를 호출조차 하지 않는다.
- **근거**: `scripts/retro_scope.py:80-101` — `merged_prs()` 가 `if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")` 로 PR 번호 접미사만 수집(:91). 오늘 실행 실측: 출력이 `경계 커밋 8f4ada5 → HEAD 7ab96205`, `머지 PR 19건 #1273~#1293` 인데 **HEAD 인 `7ab96205` 자신과 `226cd4a9`·`d82192fd`·`2478c416` 4 커밋이 목록에 없다** — 즉 범위가 HEAD 로 끝난다고 인쇄하면서 HEAD 근처 4건을 뺐다. 배선: `.claude/workflows/retrospective.mjs:217` `const scope = opts.scope ?? 'session'` 이 전부이고, 두 워크플로(.mjs) 어디에도 `spawn|exec|child_process|python` 호출이 없다(grep 무결과). 이 미배선은 `docs/_archive/reports/2026-07-26-retrospective.md:52` 가 이미 *"어느 진입점에도 배선되지 않음"* 으로 적발했고 11일·~90 PR 뒤인 지금도 그대로다.
- **처방**: (a) `compute()` 에 `session_commits`(=`boundary..HEAD` 중 PR 번호 없는 커밋 + `gh pr list` open PR) 키를 추가해 정책 문구와 출력이 일치하게 한다. (b) `retrospective.mjs` 가 착수 시 `retro_scope.py --json` 을 실행해 scope 를 주입한다(현재 free-text `'session'` 은 아무것도 보장하지 않는다). (c) 회귀 가드: 미번호 커밋이 있는 로그를 넣었을 때 산출 범위에 포함되는지 단언(현 `test_retro_scope.py:38` 은 번호 있는 2건만 본다).
- **판정**: `CONFIRMED` — 모든 인용을 독립 재현했고, 회의적으로 반증을 시도했으나 실패했다 — 결함은 실재하며 P1 이 적정하다.

■ 인용 검증 (3/3 정확 일치)
- `scripts/retro_scope.py:91` = `if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")")` — PR 번호 접미사만 수집. 정확.
- `.claude/workflows/retrospective.mjs:217` = `const scope = opts.scope ?? 'session'` — 정확.
- `docs/_archive/reports/2026-07-26-retrospective.md:52` = "- `retro_scope.py`(정책 8-(5) 완화책)가 **어느 진입점에도 배선되지 않음**" — 정확.

■ 실측 재현 (오늘 직접 실행)
`py -3 scripts/retro_scope.py` → `경계 커밋 8f4ada5 → HEAD 7ab96205`, `머지 PR 19건 #1273~#1293`.
`git log 8f4ada5..HEAD` = **23 커밋**. 차이 4건 = `7ab96205`(HEAD 자신)·`2478c416`

### [tooling] posttool 스모크 훅이 이번 창 최다 churn 표면(.claude/hooks/**)을 감시하지 않고, 결과 배너는 Claude 에게 도달하지 않는다

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:39`
- **주장**: CLAUDE.md 필수 원칙은 *"❌ 배너 시 즉시 조사"* 를 지시하지만, 그 배너는 plain `print()` 로 나가 Claude 에게 0회 도달한다(guards.md 가 자기 리포 규칙으로 명시한 사항을 이 훅만 지키지 않는다). 동시에 감시 루트에 `.claude/hooks/**` 가 없어, 이번 창에서 가장 많이 편집된 표면이 조기탐지 0 이었다. backlog R44-(c) 가 기록한 항목이지만 창 내 편집량이 그 사이 크게 늘어 위험이 증가했다.
- **근거**: `.claude/hooks/posttool_pytest_smoke.py:39` `_WATCHED_ROOTS = ("src", "alembic", "scripts")` — `.claude/hooks` 부재. 같은 파일 :187 `print(f"{_banner(rc, asserted)} …")` 는 bare stdout. `.claude/rules/guards.md:325-335` 이 *"PreToolUse/PostToolUse 훅의 plain stdout 은 디버그 로그로만 간다 … Claude 가 보게 하려면 `hookSpecificOutput.additionalContext`"* 라 명시하고, 같은 리포의 `check_edit_allowed.py:149` 와 `doc_review_gate.py:355` 는 이미 그 채널로 전환됐다(#1260) — 세 훅 중 이 하나만 남았다. 규모: `git log --since=2026-07-29 -- .claude/hooks/doc_review_gate.py` = **12 커밋**, 그중 이번 창 6건. 그 창에서 `write_text` 절단으로 `doc_review_gate.py` 가 0바이트가 된 실사고도 있었다(guards.md 기록).
- **처방**: `_WATCHED_ROOTS` 에 `.claude/hooks` 추가 + `derive_test_target` 이 `tests/unit/hooks/test_<stem>.py` 로 매핑되게 한다(대상 파일 2/2 이미 존재). 배너는 `hookSpecificOutput.additionalContext` + `systemMessage` JSON 으로 전환하고, guards.md 가 경고한 대로 **JSON 형태를 파싱하는** 회귀 가드를 붙인다(`assert "..." in capsys.out` 은 bare print 로 되돌려도 통과한다).
- **판정**: `SEVERITY_ADJUST` — Defect is real and present; every citation matched exactly. Verified by execution, not reading: is_watched_file('.claude/hooks/doc_review_gate.py') -> False and main() assembles ZERO pytest commands, while src/worker/pipeline.py -> tests/unit/worker. Churn is understated, not overstated: doc_review_gate.py = 12 commits since 2026-07-29, the highest-churn file across src/ + scripts/ + alembic/ + .claude/hooks/ combined (next highest = 3); only the "6건 this window" sub-claim is off (measured 5 with --since=2026-08-04, boundary-dependent, non-material). tests/unit/hooks/test_doc_review_gate.py ex

### [회고 범위(retro-scope)] retro_scope.py 가 retrospective.mjs 에 배선되지 않았다 — 2026-07-26 회고가 이미 적발했고 미시정 상태로 재발

- **위치**: `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\.claude\workflows\retrospective.mjs:217`
- **주장**: 정책 8-(5) 를 지키려 만든 기계 산출기가 회고 워크플로의 어느 진입점에도 연결돼 있지 않다. 디스패치 scope 문장은 여전히 손으로 적힌다. 이 결함은 2026-07-26 회고가 문장으로 적발했으나 backlog 원장에 등재되지 않아 시정 추적을 받지 못했고, 같은 형태로 재발했다(그때는 #1218 누락, 이번엔 #1295 누락).
- **근거**: `grep -n "retro_scope" .claude/workflows/retrospective.mjs` → **0 hits**. 워크플로의 scope 는 F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\.claude\workflows\retrospective.mjs:217 `const scope = opts.scope ?? 'session'` — 기계 산출 PR 목록이 아니라 자유 문자열 라벨이고, :162~165 `completenessPrompt` 에 텍스트로만 흘러든다. 선행 적발: F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\docs\_archive\reports\2026-07-26-retrospective.md:52 = '`retro_scope.py`(정책 8-(5) 완화책)가 **어느 진입점에도 배선되지 않음**' + 바로 다음 줄 '회고 범위 기계 산출이 로컬 HEAD 를 읽어 세션 최종 PR(#1218)을 범위에서 누락'. `grep -c "retro_scope" docs/backlog.md` → **0** (원장 미등재 = 시정 추적면 0). CLAUDE.md 가 명명한 '#1084 가 원장만 만들고 배선하지 않아 자기위반' 과 동형이다.
- **처방**: retrospective.mjs 실행 시작 시 `python scripts/retro_scope.py --json` 을 호출해 scope 를 산출하고, 그 값(머지 PR + 미머지 세션 산출물)을 **모든 finder 프롬프트에 주입**한다. `opts.scope` 는 관점 라벨('session')과 범위 데이터를 겸하지 말고 분리한다. 동시에 이 항목을 backlog 에 R 번호로 등재해 3회차 재발을 막는다.
- **판정**: `SEVERITY_ADJUST` — 구조적 결함 자체는 실재하며 인용 4건 모두 실측 일치. (1) `grep -n retro_scope .claude/workflows/retrospective.mjs` → 0 hits, `grep -rn retro_scope .claude/` → 0 — 훅·커맨드·스킬·settings 어디에도 배선 없음. 간접 배선도 배제: retrospective.mjs 에 spawn/exec/child_process/python 호출이 전무(:232 유일 히트는 가드 테스트 경로를 언급한 주석). (2) :217 `const scope = opts.scope ?? 'session'` 정확 일치 — 기계 산출 PR 목록이 아니라 자유 문자열 라벨이고 :162~165 completenessPrompt 에 텍스트로만 보간됨. (3) 선행 적발 2026-07-26-retrospective.md:52 원문 정확 일치 + :53 이 주장대로 #1218 줄. (4) `grep -c retro_scope docs/backlog.md` → 0 — 원장 미등재 = 시정 추적면 0. 여기까지는 CONFIRMED.

그러나 P0 을 떠받치는 결정적 근거가 반증됨. (a) "이번엔 #1295 

### [회고 범위(retro-scope)] #1295 가 신설한 행동 규칙 가드는 규칙을 뒤집어도 초록이다 — 닫았다고 선언한 observer-lie 를 그대로 재생산

- **위치**: `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\tests\unit\scripts\test_claude_md_behavior_rules.py:68`
- **주장**: `test_claude_md_behavior_rules.py` 는 `needle in text` 부분문자열 존재만 본다. 어휘를 남긴 채 규칙의 의미를 반대로 바꾸면 25건 전건이 초록으로 남는다. 커밋이 제시한 뮤테이션 근거('복원분 3건을 지우니 정확히 3건 red')는 부분문자열 검사에 대해 **동어반복**이며 부정(negation) 축을 한 번도 건드리지 않았다. 즉 이 가드는 자신이 대체하겠다고 선언한 '앵커만 보는 가드' 와 같은 종류의 거짓 관측자다.
- **근거**: F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\tests\unit\scripts\test_claude_md_behavior_rules.py:68 `assert needle in text`. 스크래치 사본에 뮤테이션 2건 적용 후 모듈의 `_BEHAVIOR_RULES` 로 동일 판정 실행 — (1) CLAUDE.md:81 '회고 범위 = 직전 회고 이후 머지 PR + 본 세션 산출물 전체' → '**머지 PR 만** — 본 세션 산출물 전체는 범위에서 제외한다' (2) CLAUDE.md:90 '안정성과 충돌하면 거부한다' → '외부 권장 규격을 항상 우선한다(과거에는 안정성과 충돌하면 거부한다 였으나 폐기)'. 결과 **failing rules: 0 []** — 전건 green. 메모리 `feedback-prose-guard-both-ways.md`('산문 가드는 양방향으로 틀린다 — 부정어 탐색 대신 열거/구조 문맥')가 명명한 패턴이다. 🔴 탐지 실패하는 첫 규칙이 하필 정책 8-(5), 즉 이번 gap 을 만든 바로 그 규칙이다.
- **처방**: 존재 검사에 **부정 문맥 배제**를 더한다 — needle 이 포함된 줄에 '제외/폐기/아님/미적용/였으나' 류가 함께 오면 red, 또는 규칙을 (조건, 의무동사, 예외) 3-필드 구조로 파싱해 대조한다. 최소한 뮤테이션 근거를 '삭제 → red' 가 아니라 '**의미 반전 → red**' 로 다시 제시해야 이 가드가 무엇을 지키는지 주장할 수 있다. 이 항목 자체가 #1295 를 범위에 넣었다면 회고가 산출했을 finding — 누락 비용이 0 이 아님을 실증한다.
- **판정**: `SEVERITY_ADJUST` — 인용 확인: `tests/unit/scripts/test_claude_md_behavior_rules.py:68` = `assert needle in text` 정확히 실재. HEAD=7ab96205(가드 신설 커밋).

■ 재현 성공 — 주장의 실질은 전부 사실이다
실경로 뮤테이션(guards.md 불변식 2 절차: `git add -A` → 뮤테이션 → `git diff` 확인 → pytest → `git checkout --` 복원)으로 실제 CLAUDE.md 를 깨뜨려 관측:
- MUT1 (CLAUDE.md:81, 정책 8-(5)) "회고 범위 = 머지 PR + 본 세션 산출물 전체" → "머지 PR **만** — 본 세션 산출물 전체는 범위에서 **제외**한다"
- MUT2 (CLAUDE.md:90, 정책 17 원칙 1) "안정성과 충돌하면 거부한다" → "외부 권장 규격을 **항상 우선**한다(과거에는 …였으나 **폐기**)"
- MUT3 (CLAUDE.md:81) "Claude 단독 회고 금지" → "…금지 규정은 **폐기**됐다 — 단독 회고를 default 로 한다"
결과: `mutated != orig` = True(23,476→23,605

### [E2E 게이트 관측자 무결성 (observer-integrity)] live_server 픽스처 skip 이 121건 전건을 삼키고 e2e job 은 GREEN — 같은 창이 3개 표면에 적용한 공허화 차단을 자기가 방금 초록으로 만든 표면에만 미적용

- **위치**: `e2e/conftest.py:193`
- **주장**: `e2e/conftest.py:190-193` 은 uvicorn 이 30초 안에 `/health` 200 을 못 내면 세션 스코프 픽스처에서 `pytest.skip()` 을 던진다. e2e 121건 **전부**가 이 픽스처에 전이 의존하므로 기동 실패 = 121 skipped = **pytest exit 0** = job GREEN. `ci.yml:546` 의 실행 커맨드에는 최소 통과 건수·skip 상한·수집 건수 축이 하나도 없어 '120 통과' 와 '0 통과 121 skip' 이 CI 에서 원리적으로 구별되지 않는다.
- **근거**: (1) `grep -n` 실측 — `e2e/conftest.py:190` `if not ready:` → `:193` `pytest.skip("E2E 서버 시작 실패 — 테스트 건너뜁니다")` (세션 스코프 `live_server`, `:157`). (2) 의존 전수: `py -3 -m pytest e2e/ --collect-only -q` = **121 tests collected**; `grep -rh "^def test_" e2e/*.py | grep -cv "page|base_url|seeded_analysis|live_server"` = **0** → 121건 전부가 `live_server` 에 전이 의존. (3) 뮤테이션 실증 — 스크래치패드에 동일 형상(세션 픽스처 skip → 3 테스트) 재현: `3 skipped`, `PYTEST_EXITCODE=0`. (4) `.github/workflows/ci.yml:546` `run: python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` — 건수 축 0. (5) 같은 창의 대조 표면: `ci.yml:233-259` `lint-js 공허화 차단 (검사 범위 비면 fail)`, `scripts/check_docs_sync.py:67` `fail-closed 3층 (Grok claim-review 019fcf 적발 — 초판은 전부 fail-open 이었다)`, `#1275`/`#1279` doc_review_gate fail-open 봉인. (6) 창의 자기 인지 실패 — `docs/backlog.md:51` (R52) 이 *"초록으로 위장하지 않는 것이 이 항목의 핵심 제약: deselect·continue-on-error·|| true 로 job 을 초록으로 만들면 R7 이 정확히 원상복귀한다(실행되지만 아무것도 지키지 않는 job)"* 라고 **세 벡터를 열거하면서 이미 코드에 있던 네 번째 벡터(픽스처 skip 연쇄)를 빠뜨렸다** — 이 벡터는 워크플로를 아무도 편집하지 않아도 uvicorn 기동만 흔들리면 도달한다. (7) 리포 자신의 선례와 모순 — `e2e/test_theme_mobile_guards.py:127` 은 *"fail-fast — 셀렉터 미존재 = 페이지 구조 회귀 (silent skip 금지, 사이클 157 #9)"* 로 테스트 본문 수준에서 silent skip 을 금지했는데, 같은 디렉토리의 픽스처는 폭발 반경 121배로 그 금지를 범한다. (8) 완화(정직 기록): `ci.yml:499` 대로 e2e 는 required check 가 아니라 머지를 막지는 않는다 — 다만 (a) `README.md:22` brightgreen 배지의 유일한 근거이고 (b) 승격 판단에 쓸 flakiness 안정성 데이터 자체를 오염시킨다(기동 실패가 초록으로 기록되면 '안정적' 으로 보인다).
- **처방**: `e2e/conftest.py:190-193` 을 fail-closed 로 전환 — `pytest.skip` → `pytest.fail`/`raise RuntimeError` 로 바꾸고 uvicorn 스레드 생존 여부·마지막 예외를 메시지에 실어 진단 가능하게 한다. 로컬 opt-out 이 필요하면 **CI 가 절대 설정하지 않는 명시 env**(`E2E_ALLOW_SKIP=1`)에만 skip 경로를 남기고 기본값은 fail. 회귀 가드는 3-불변식대로 **실경로 뮤테이션**으로 red 확인(`E2E_PORT` 를 점유 중 포트로 바꾸거나 `_start_uvicorn` 을 일시 파손 → job 이 red 인지).
- **판정**: `SEVERITY_ADJUST` — 기술적 주장은 전건 독립 재확인됐다 — 결함 자체는 실재한다.

**재확인한 것 (전부 내 손으로 재실측)**
1. `e2e/conftest.py:157` `@pytest.fixture(scope="session") def live_server`, `:190` `if not ready:` → `:193` `pytest.skip("E2E 서버 시작 실패 — 테스트 건너뜁니다")` — 인용 그대로.
2. 전이 의존: `page`(`:247`) → `base_url`(`:204`) → `live_server`. 픽스처 체인을 직접 읽어 확인했다. `py -3 -m pytest e2e/ --collect-only -q` = **121 collected**, 체인 밖 테스트 **0건**(`grep -rn "def test_" e2e/*.py | grep -cvE "page|base_url|seeded_analysis|live_server"` = 0). 세션 스코프라 all-or-nothing.
3. 뮤테이션 독립 재현: 스크래치패드에 동일 형상(세션 픽스처 `pytest.skip` → 3 테스트) → `3 skipped` · `EXITCODE=0`. **전건 skip

### [E2E 게이트 관측자 무결성 (observer-integrity)] e2e 에는 커밋된 건수 baseline 이 없다 — 검사 범위 축소가 job·배지 양쪽에서 조용히 통과

- **위치**: `.github/workflows/ci.yml:546`
- **주장**: lint-js 표면은 `scripts/lint_js_ignore_baseline.json` 커밋 baseline 으로 '검사 대상 증감 = 리뷰 가능한 명시 결정' 을 강제하는데, e2e 표면에는 수집/통과/skip 건수의 기계 원장이 전무하다. 테스트 파일이 collection 에서 빠지거나(rename·import 조건부 제외) 통과 건수가 줄어도 job 은 exit 0 이고, `README.md:22` 의 `121_in_CI_(120_pass_/_1_skip)` brightgreen 배지는 손으로 적은 숫자라 아무것도 대조하지 않는다.
- **근거**: (1) `scripts/check_lint_js_nonvacuous.py:45` `BASELINE_PATH = REPO_ROOT / "scripts" / "lint_js_ignore_baseline.json"` + 같은 파일 주석 *"검사 범위 증감이 리뷰 가능한 명시 결정(baseline diff)이 된다"*. (2) e2e 대응물 부재 — `ci.yml:545-546` 에 `--junitxml` 도 baseline 대조 스텝도 없음. (3) `scripts/check_test_count_sync.py` 는 `_STATE_TOTAL`(:53)·`_COLLECTED`(:57) 로 unit/integration 만 대조 — `grep -n "E2E|e2e"` **0건**, 즉 E2E 배지는 어떤 sync 가드에도 걸리지 않는다(pytest.ini `testpaths = tests` 라 collect 축에서도 원천 제외). (4) 전량 skip 이 아닌 **부분** 공허(파일 1개 누락 = 10건 소실)는 P0-1 의 exit-code 축으로도 안 잡힌다 — pytest 는 0건 수집일 때만 exit 5 를 낸다. (5) 현 baseline 은 이미 기계 표현 가능한 상태다 — `--collect-only` 실측 **121**, `e2e/test_settings.py:398` `@pytest.mark.skip(...)` 정적 1건 = 120 pass / 1 skip 이 결정론적 기대값이다.
- **처방**: `ci.yml:546` 에 `--junitxml=e2e-results.xml` 추가 + `scripts/check_e2e_nonvacuous.py` 신설: junit XML 을 파싱해 `collected != baseline.collected` · `passed < baseline.passed` · `skipped > baseline.skipped` 중 하나라도 걸리면 exit 1. baseline 은 `scripts/e2e_baseline.json` 으로 커밋(`{"collected":121,"passed":120,"skipped":1}`)해 증감을 diff 로 승격 — `lint_js_ignore_baseline.json` 과 동일 패턴·동일 한계 명시(같은 PR 이 baseline 을 함께 고치면 통과하나, 그 결정이 리뷰어에게 보인다). 배지 갱신은 이 원장에서 파생시켜 손입력 drift 를 없앤다.
- **판정**: `CONFIRMED` — 모든 인용 재확인 — 6/6 정확. (1) `.github/workflows/ci.yml:545-546` = `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120`, `--junitxml` 도 baseline 대조 스텝도 없음(파일 내 유일한 `--junitxml` 은 `:380` 단위 job). (2) `scripts/check_lint_js_nonvacuous.py:45` `BASELINE_PATH = REPO_ROOT / "scripts" / "lint_js_ignore_baseline.json"` + 인용된 "검사 범위 증감이 리뷰 가능한 명시 결정(baseline diff)" 주석 실재. (3) `scripts/check_test_count_sync.py:53` `_STATE_TOTAL` · `:57` `_COLLECTED` 실재, `grep "e2e|E2E"` **0건**; `check_docs_sync.py:41` `_README_BADGE` 는 Tests 배지 + FastAPI 배지만 대조 — E2E 패턴 전무. (4) `README.md:22` = `E2E-121_in_CI_(120_pass_

### [E2E 게이트 관측자 무결성 (observer-integrity)] fail-closed 집행 범위가 scripts/check_*.py + .claude/hooks 에 갇혀 있다 — 테스트 픽스처와 CI run step 은 어떤 메타가드도 보지 않는다 (이 gap 이 안 보인 구조적 근본)

- **위치**: `scripts/check_guard_fail_open.py:43`
- **주장**: 이 리포는 fail-open 을 write-time 에 잡는 메타가드를 갖추고 있으나(`check_guard_fail_open.py`, `test_empty_except_guard.py`, `test_guard_wiring_coverage.py`), 셋 다 스캔 범위가 `scripts/`·`.claude/hooks/` 로 하드코딩돼 있다. 그 결과 **관측자 역할을 하는 코드가 그 두 디렉토리 밖에 있으면**(= e2e 픽스처, CI job 의 run 커맨드) 3-불변식의 write-time 집행을 한 번도 받지 않는다. #1288 이 e2e job 을 배선할 때 가드 테스트를 0건 추가한 것도 이 범위 공백의 직접 귀결이다.
- **근거**: (1) `scripts/check_guard_fail_open.py:43` `_SCRIPTS = _ROOT / "scripts"` — 판정 대상이 `scripts/check_*.py` 뿐(`tests/unit/scripts/test_guard_fail_open.py` 가 `monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)` 로 이 축을 그대로 확인). (2) `tests/unit/scripts/test_empty_except_guard.py:23` `_SCOPED_DIRS = ("scripts", ".claude/hooks")` — e2e 제외. (3) `tests/unit/scripts/test_guard_wiring_coverage.py` 는 `scripts/check_*.py` + `.claude/hooks/*.py` 의 **배선 여부**만 강제하고, CI job 자신의 무결성(비공허성)은 대상이 아니다 — `grep -n "e2e"` 0건. (4) `git show --stat 02b3e867` (#1288) = `.github/workflows/ci.yml | 44 +++++-` **단일 파일** — 신규 게이트 표면인데 동반 가드 테스트 0건. 반면 같은 리포의 다른 게이트는 전부 배선 가드를 동반한다(`test_lint_gate_wiring.py`·`test_session_start_wiring.py`·`test_ci_repo_integrity_backstop.py`). (5) 결과적으로 `AGENTS.md` 3-불변식 중 **불변식 1(fail-closed)** 의 기계 집행이 '가드 스크립트' 계층에만 존재하고, 실제로 초록/빨강을 결정하는 **테스트 픽스처 계층**에는 존재하지 않는다.
- **처방**: (a) `check_guard_fail_open.py:43` 과 `test_empty_except_guard.py:23` 의 스캔 범위에 `e2e`(특히 `conftest.py` 류)를 편입 — 픽스처는 판정 코드이지 제품 코드가 아니다. (b) `ci.yml` job-shape 가드 신설: **테스트 스위트를 실행하는 job 은 비공허성 축(최소 건수 원장 또는 fail-closed 픽스처)을 반드시 동반한다** 를 YAML 파싱으로 강제(`test_lint_gate_wiring.py` 형식). (c) 향후 '게이트 표면 신설 PR' 체크리스트에 *"이 표면은 아무것도 검사하지 않은 상태와 통과 상태를 구별하는가"* 1문항을 고정 — 이번 창은 그 질문을 3번 던지고 4번째에서 던지지 않았다.
- **판정**: `CONFIRMED` — 인용 5건 전부 실측 재확인됨 + 이 범위 공백을 **현재 살아서 악용 중인 fail-open 1건**을 추가 발견해 CONFIRMED.

■ 인용 검증 (grep 실측, HEAD = 287c572)
1. `scripts/check_guard_fail_open.py:43` = `_SCRIPTS = _ROOT / "scripts"` — 문자 그대로 일치. `:135` `return sorted(_SCRIPTS.glob("check_*.py")), sorted(_HOOKS.glob("*.py"))` 로 판정 대상이 두 하드코딩 디렉토리로 닫힌다. ⚠️ 근거 (1) 의 *"판정 대상이 `scripts/check_*.py` 뿐"* 은 부정확 — `:48` `_HOOKS = _ROOT/".claude"/"hooks"` 도 스캔한다(backlog R16 확대). 결론(두 디렉토리 밖은 미검)은 그대로 성립.
2. `tests/unit/scripts/test_empty_except_guard.py:23` = `_SCOPED_DIRS = ("scripts", ".claude/hooks")` — 일치. `:50-51` 이 그 둘만 rglob.
3. `test_guard_wi

### [e2e-vacuity / ci-gating] E2E CI job은 앱이 부팅 실패하면 121건 전건 skip 후 exit 0 — 초록의 근거가 원리적으로 없다

- **위치**: `e2e/conftest.py:193`
- **주장**: `e2e/conftest.py:193` 의 `pytest.skip("E2E 서버 시작 실패 — 테스트 건너뜁니다")` 는 **session-scoped** `live_server` fixture 안에 있다. 서버가 30초 안에 `/health` 200 을 못 주면(import 에러·마이그레이션 실패·config 회귀·포트 충돌) 그 fixture에 의존하는 **121건 전부**가 skip 되고, `.github/workflows/ci.yml:546` 의 `python -m pytest e2e/ -q -rs --timeout=120` 은 **exit 0** 으로 끝나 job 이 초록이 된다. 즉 **앱을 통째로 못 띄워도 E2E job 은 성공**한다. 배지가 주장하는 '120 pass' 는 이 경로에서 '0 pass' 와 CI 신호상 구별되지 않는다. 이것이 R53 이 말한 초록의 비공허성 문제의 최상위 사례이자, `#1291` 커밋 본문이 스스로 금지어로 쓴 *"R7 의 원죄(실행되지만 아무것도 안 지키는 초록)"* 를 스위트 전체 규모로 재생산할 수 있는 구멍이다.
- **근거**: 정책 6 실측: `grep -n "pytest.skip" e2e/conftest.py` → `193: pytest.skip(...)`; 같은 fixture 선언은 `e2e/conftest.py:158 def live_server(tmp_path_factory)` 이며 `@pytest.fixture(scope="session")` 로 데코레이트돼 있다. **기계 실증(뮤테이션)**: 동일 구조(session fixture 내 skip + 의존 테스트 3건, 그중 전부 `assert False`)를 스크래치에서 재현 → `sss ... 3 skipped in 0.02s / EXIT=0`. 실패해야 할 테스트조차 skip 으로 삼켜지고 종료코드는 0. 추가로 `gh api repos/xzawed/SCAManager/branches/main/protection --jq '.required_status_checks.contexts'` 실측 결과 목록에 `E2E (Playwright)` 가 **없다**(ci.yml:499 주석이 명시: "required check 로 승격하지 않았다"). CI run 31025178170 로그 실측은 `120 passed, 1 skipped, 2 warnings in 118.48s` — 이번엔 진짜 돌았지만, 돌았다는 사실을 강제하는 기전은 없다.
- **처방**: (1) `live_server` 의 `pytest.skip` 을 `pytest.fail`/`RuntimeError` 로 전환 — 서버 미기동은 건너뛸 사유가 아니라 그 자체가 회귀다. (2) ci.yml e2e step 에 최소 통과 건수 게이트 추가(예: `--deselect` 없이 collected/passed 를 파싱해 `passed < 115` 이면 fail). 이 리포는 이미 같은 패턴을 갖고 있다 — `ci.yml:234 lint-js 공허화 차단 (검사 범위 비면 fail)` 이 required check 이고 그 주석(`ci.yml:225-231`)이 *"'위반 0건' 과 '아무것도 검사 안 함' 이 구별 불가"* 라고 이 결함을 정확히 서술한다. 패턴을 알면서 e2e 에 이식하지 않았다. (3) 안정성 데이터가 모였으므로(`#1294`·`#1295` 연속 초록) required check 승격 판단을 backlog 항목으로 명시.
- **판정**: `SEVERITY_ADJUST` — 기전은 실재하고 기계로 재현된다. 인용 재확인: `e2e/conftest.py:157 @pytest.fixture(scope=\"session\")` · `:158 def live_server(tmp_path_factory)` · `:193 pytest.skip(\"E2E 서버 시작 실패 — 테스트 건너뜁니다\")` 전건 일치. `.github/workflows/ci.yml:546` 도 라인 일치(실제 명령은 `-p no:asyncio` 포함 — 인용 누락은 비실질). 독립 뮤테이션 재현(스크래치, session fixture skip + `assert False` 3건): `sss … 3 skipped in 0.02s`, EXIT=0 — 실패해야 할 단언조차 삼켜지고 종료코드 0 확인. `gh api …/branches/main/protection --jq '.required_status_checks.contexts'` 실측에도 `E2E (Playwright)` 부재(ci.yml:499 주석과 일치). 즉 "초록이 0 pass 와 120 pass 를 구별하지 못한다" 는 핵심 주장은 CONFIRMED.

다만 두 축에서 정정·감쇄한다. (1) **트리거 열

### [docs-claim / observer-lie] README E2E 배지 brightgreen 은 CI 현실과 어떤 기계적 결속도 없다 — 스위트가 빨개져도 초록으로 남는다

- **위치**: `README.md:22`
- **주장**: `2478c416` 이 `README.md:22` / `README.ko.md:22` 를 `E2E-121_in_CI_(120_pass_%2F_1_skip)-**brightgreen**` 으로 플립했다. 그런데 (a) 이 배지는 정적 문자열이고 (b) 이 문자열을 CI 실측에 묶는 가드가 **존재하지 않으며** (c) e2e job 은 required check 가 아니라 **빨간 채로도 머지된다**. 세 조건이 겹치므로 배지는 *관측자를 지워도 여전히 참으로 보이는* 전형적 observer-lie 다. 커밋 본문은 *"검증 전에 초록으로 적었으면 R7 의 원죄를 문서 축에서 그대로 재생산했을 것이다"* 라고 적어 그 원죄를 피했다고 주장하지만, 피한 것은 **작성 시점의 근거 부재**뿐이고 **이후 시점의 지속적 참** 은 전혀 확보되지 않았다. R7 의 본질은 '한 번 확인 안 함' 이 아니라 '아무도 관측하지 않음' 이었으므로, 스냅샷 1회 확인은 같은 결함의 절반만 갚은 것이다.
- **근거**: 정책 6 실측: `grep -n "E2E-121" README.md README.ko.md` → `README.md:22` · `README.ko.md:22` 양쪽 `-brightgreen`. 배지 동기화 가드 `scripts/check_docs_sync.py` 의 정규식은 `41: _README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\((\d+)_unit_%2B_\d+_integration\)")` 와 `43: _FASTAPI_BADGE` **두 개뿐** — E2E 배지는 대상 밖이다. `grep -rln "e2e" scripts/` 결과에 배지·카운트 가드는 **0건**(`check_codeql_alerts.py`·`perf_measure.py`·i18n 도구만 매칭). 브랜치 보호 required contexts 9종에 `E2E (Playwright)` 부재(gh api 실측, 위 P0 참조). 대조: `docs/backlog.md:53` R53 은 **🟡 착수 가능(미해소)** 상태로 *"통과 91건은 감사된 적이 없다"* 를 그대로 열어 두고 있다 — 미해소 backlog 위에 사용자 대면 brightgreen 을 세운 구조다.
- **처방**: 두 축 중 하나는 반드시 채운다: (A) `check_docs_sync.py` 에 E2E 배지 항목 추가 + e2e job 이 실측 passed/skipped 를 산출물로 남기고 배지 값과 대조(불일치 시 fail), 또는 (B) 정적 배지를 GitHub Actions workflow status badge(`.github/workflows/ci.yml` 실행 결과 자동 반영)로 교체해 문자열 drift 자체를 제거. 둘 다 못 하면 배지 색을 brightgreen 이 아니라 **비공허성 미감사를 표기하는 색/문구**로 되돌리고 R53 종결 시 플립한다(정책 4 — 단언과 회귀 가드를 같은 PR 에).
- **판정**: `SEVERITY_ADJUST` — 실체는 확인됐다 — 세 근거 전부 재현됐고, 오히려 주장보다 더 강한 실증까지 나왔다. 다만 P0 등급은 이 리포의 P0 용법(운영 사고 차단·fail-open 봉인)과 어긋나 P1 로 조정한다.

【확인된 사실 — 정책 6 실측】
(a) `README.md:22` + `README.ko.md:22` 양쪽 `-brightgreen` 정확히 존재. `git show 2478c416` 이 `-yellow(122_in_CI…)` → `-brightgreen(121_in_CI_(120_pass_%2F_1_skip))` 로 플립한 것 확인.
(b) 결속 가드 부재 확정: `scripts/check_docs_sync.py` 배지 정규식은 `41:_README_BADGE`(Tests) + `44:_FASTAPI_BADGE` **둘뿐**. `grep -rln "e2e" scripts/` → `check_codeql_alerts.py`·`perf_measure.py`·i18n 도구만 매칭, 배지/카운트 가드 **0건**. `grep -rn "E2E-" tests/ scripts/ .github/` → **0건**. 단위 카운트는 `check_test_count_sync.py

### [e2e-vacuity] perf 11건 중 10건은 라우트가 404 여도 통과한다 — 뮤테이션으로 확정

- **위치**: `e2e/_perf_helpers.py:34`
- **주장**: `e2e/_perf_helpers.py:34` 의 `pg.goto(url, wait_until="networkidle", ...)` 는 반환된 response 를 **버린다**. 따라서 `_measure_page` 기반 perf 테스트는 상태코드·콘텐츠를 전혀 보지 않고 타이밍만 잰다. 404 페이지는 실 페이지보다 **더 빠르므로** 임계값을 항상 통과한다. 결과: `test_root_ttfb`·`test_root_fcp`·`test_root_load`·`test_dashboard_ttfb`·`test_dashboard_lcp`·`test_add_repo_ttfb`·`test_repo_detail_ttfb`·`test_repo_detail_load`·`test_repo_insights_load`·`test_analysis_detail_load` **10건은 해당 라우트를 앱에서 삭제해도 초록**이다. `#1291`(R52)이 이 파일을 고쳤지만 고친 것은 *인스턴스*(`/login` → `/`)였고 *클래스*(응답 검증 부재)는 그대로 남았다 — 메모리 `feedback-fix-reproduces-the-defect` 패턴의 재현.
- **근거**: 정책 6 실측 + **뮤테이션 4건 실행**(임시 프로브 `e2e/test_zzmutprobe.py`, 실행 후 삭제·작업트리 clean 확인). 프로브는 각 단언 형태를 그대로 복제해 존재하지 않는 라우트 `/this-route-does-not-exist-404` 에 적용: ttfb·load·fcp 3건 → `3 passed ... in 11.39s / EXIT=0`; lcp 1건 → `1 passed ... in 7.10s / EXIT=0`. 즉 TTFB/FCP/LCP/Load **네 축 전부** 404 에서 임계값을 통과한다. 유일한 예외는 `e2e/test_performance.py:116 assert resp.status_code == 200` 을 가진 `test_health_ttfb`(requests 직접 측정) — 11건 중 이 1건만 정합성 앵커가 있다. 헬퍼 라인 실측: `grep -n "pg.goto" e2e/_perf_helpers.py` → `34`.
- **처방**: `measure_one` 이 `resp = pg.goto(...)` 로 응답을 받아 `assert resp.status == 200`(또는 `resp.ok`) 을 강제하도록 한 줄 추가하면 10건이 한 번에 앵커된다. 최소 추상화(정책 16)에 부합하고 호출처 변경 0. 이후 라우트 하나를 임시 삭제해 red 를 실증(A2 — 실경로 뮤테이션 없이 HOLDS 금지).
- **판정**: `CONFIRMED` — 인용 재확인: `grep -n "pg.goto" e2e/_perf_helpers.py` → `34: pg.goto(url, wait_until="networkidle", timeout=30_000)` — 반환 Response 를 변수에 받지 않고 버린다(정확 일치). `@pytest.mark.perf` 데코레이터 11건 실측(e2e/test_performance.py:57/80/90/100/126/136/146/158/168/178/193), 그중 상태·콘텐츠 앵커가 있는 것은 `test_health_ttfb` 단 1건(`e2e/test_performance.py:116 assert resp.status_code == 200`) — "11건 중 10건" 카운트 정확.

보고된 프로브를 신뢰하지 않고 **독립 뮤테이션을 직접 재현**했다. 임시 프로브(`e2e/test_zzverifyprobe.py`, 실행 후 삭제)에 (a) catch-all 라우트 배제 앵커 `assert resp.status == 404` 를 먼저 두고 (b) ttfb/fcp/lcp/load 4축 단언을 원본 형태 그대로 복제해 `/this-route-does-not-exist-404` 

### [e2e-vacuity / scope] R53 이 지목한 미감사 초록 모집단은 아직 표본조차 잡히지 않았다 — 3개 파일 23건(19%)은 #1291 이 손댄 적 없다

- **위치**: `docs/backlog.md:53`
- **주장**: `#1291`(R52 drift 해소)이 변경한 e2e 파일은 conftest·pytest.ini 외 7개다. **`test_navigation.py`(13건)·`test_overview_score.py`(5건)·`test_repos_mode.py`(5건) = 23건(스위트의 19%)은 한 번도 손대지 않았다.** 이 23건은 `#1288` 배선 시점부터 계속 초록이었고, 따라서 R53 이 말한 *"빨강만 고치고 초록은 믿었다"* 의 모집단 그 자체다. 배지 brightgreen 은 이 23건을 '검증됨' 으로 계상하지만 이들에 대한 비공허성 근거는 0이다. 본 회고에서 표본 3건을 뮤테이션했더니 **1건 공허 확정**(test_repos_mode.py:108) · **1건 서술-단언 불일치**(test_navigation.py:17) · **1건 앵커 정상**(test_overview_score.py) — 3분의 2가 문제였다. 무작위 표본이 아니므로 기저율은 여전히 미지수이나, '손댄 곳마다 나온다' 는 R53 의 관찰이 미접촉 파일에서도 재현됐다는 점이 핵심이다.
- **근거**: 정책 6 실측: `git show 5b72c438 --stat` 변경 파일 = ci.yml · docs/backlog.md · e2e/conftest.py · e2e/pytest.ini · test_dashboard.py · test_dashboard_insight.py · test_i18n_visual_regression.py · test_performance.py · test_settings.py · test_theme.py · test_theme_mobile_guards.py · src/templates/settings.html — **test_navigation.py · test_overview_score.py · test_repos_mode.py 부재**. 건수 실측: `for f in e2e/test_*.py; do grep -c "^def test_" $f; done` → navigation 13 · overview_score 5 · repos_mode 5 (합 23) / 전체 def 113 → 121 collected(parametrize 8 확장). 뮤테이션 결과는 위 두 finding 참조.
- **처방**: R53 을 '전수 감사' 로 두면 착수 비용 때문에 또 이월된다. **미접촉 3파일 23건을 1차 배치로 잘라** 각 테스트에 대해 '단언 대상 1개 제거 → red 확인' 을 돌리고 결과(공허 N/23)를 기록한다. 이 숫자가 나와야 나머지 98건의 기저율을 추정할 근거가 생기고, 배지 brightgreen 의 정당화 여부도 정량 판단 가능해진다.
- **판정**: `CONFIRMED` — 전 인용 1차 출처 대조 통과. (1) `git show 5b72c438 --name-only` 실측 — #1291 변경 e2e 파일 9개 중 test_navigation.py·test_overview_score.py·test_repos_mode.py **부재** 확정. (2) 건수 `grep -c "^def test_"` = navigation 13 · overview_score 5 · repos_mode 5 = 23, 전체 113 → 배지 121 collected, 23/121 = 19% 일치. (3) 🔴 **가장 약해 보였던 "#1288 배선 시점부터 계속 초록" 주장을 독립 검증했다** — 첫 e2e CI 실행(run 30956571310 / job 92151011627, `30 failed / 91 passed / 1 skipped`) 로그에서 실패 헤더 27종을 추출했고 3개 파일 소속은 **0건**, 해당 파일을 언급하는 로그 라인은 `PytestUnknownMarkWarning` 뿐이었다. 주장 성립. (4) 배지 = `README.md:22` `E2E-121_in_CI_(120_pass_/_1_skip)-brightgreen` — 23건을 '

### [guards/regression] #1295 가 신설한 행동규칙 생존 가드(27건)가 정책 17 원칙 3/4/5 를 커버하지 않는다 — 뮤테이션 3종 전부 green (사고를 일으킨 바로 그 규칙이 다시 무방비)

- **위치**: `tests/unit/scripts/test_claude_md_behavior_rules.py:53`
- **주장**: #1295 는 규칙 8건 소실에 대한 재발 방지로 tests/unit/scripts/test_claude_md_behavior_rules.py(25 규칙 파라미터화 + 대조군 2)를 신설했다. 그러나 그 목록은 정책 17 항목으로 원칙 1('안정성과 충돌하면 거부')과 원칙 2/4 일부('본문 보존 default') 2건만 담고, 이번 gap 의 주제인 원칙 3(단계 분할 + 5+1 회의 + 옵션 표)의 판별 어휘는 하나도 담지 않는다. 실경로 뮤테이션으로 확인한 결과 원칙 3 문장, 원칙 4 의 'High tier 사전 확인' 절, 원칙 5 정기 검증 절을 각각 CLAUDE.md 에서 삭제해도 25 needle 전건 통과이며 줄 수도 195 로 불변이라 줄수 관측 테스트도 green 이다. 즉 '규칙이 조용히 사라지는 것'을 막기 위해 만든 가드가, 이번 사고를 일으킨 규칙에 대해서는 정확히 그 조용한 삭제를 허용한다 — 리포가 [[feedback-fix-reproduces-the-defect]] 로 기록해 온 '수정이 같은 결함을 재생산한다' 패턴의 재현.
- **근거**: tests/unit/scripts/test_claude_md_behavior_rules.py:35 _BEHAVIOR_RULES 정의, :53 ('정책 17 — 외부 규격보다 안정성', '안정성과 충돌하면 거부'), :54 ('정책 17 — 본문 보존 영역', '본문 보존 default'). 목록 25건 어디에도 '5+1 회의'·'옵션 표'·'단계 분할'·'High tier' 어휘 없음. 실경로 뮤테이션(CLAUDE.md 원본에 대해 실행, 각 mutated != orig 확인): (a) '🔴 매 분리 단계마다 **5+1 회의 + 운영 검증 + 사용자 옵션 표 결정**. ' 삭제 → missing_needles=0, 줄 수 195 불변. (b) ' — 분리 시 High tier 사전 확인' 삭제 → missing_needles=0. (c) '. ≥18 PR 영역은 ≥5 사이클마다 정기 검증' 삭제 → missing_needles=0. 대상 규칙 원문 위치 = CLAUDE.md:90 (정책 17 표 행 단일 셀). 가드 자신의 docstring 은 '각 규칙의 고유 어휘가 CLAUDE.md 본문에 실재하는지 본다' 고 선언하나, 원칙 3 은 고유 어휘가 등록되지 않아 그 선언이 이 규칙에 대해서는 공허하다.
- **처방**: _BEHAVIOR_RULES 에 최소 3항목 추가: ('정책 17 — 단계 분할 의무', '5+1 회의', '문서 정리를 단일 단계로 진행해 규칙이 통째로 사라지는 사고(#1295 실제 발생)'), ('정책 17 — 사용자 옵션 표 결정', '옵션 표', '지배 정책의 결정 게이트를 사후 관측자로 대체'), ('정책 17 — 분리 위험 영역 사전 확인', 'High tier 사전 확인', '매 작업 의무 영역을 사전 확인 없이 external 로 이동'). 추가 후 위 뮤테이션 3종이 red 로 뒤집히는지 실측하고 그 결과를 PR 본문에 명시(불변식 2). 아울러 needle 선정 절차 자체를 점검할 것 — 이번 목록은 'Grok 이 지적한 8건' 을 원천으로 삼았으므로, 관측자가 놓친 규칙은 구조적으로 목록에 오르지 못한다(관측자 의존의 2차 재생산).
- **판정**: `CONFIRMED` — 전 항목 독립 재현. 인용 4건 전부 실측 일치 — test_claude_md_behavior_rules.py:35 `_BEHAVIOR_RULES = [`, :53 ("정책 17 — 외부 규격보다 안정성", "안정성과 충돌하면 거부"), :54 ("정책 17 — 본문 보존 영역", "본문 보존 default"), CLAUDE.md:90 = 정책 17 표 행(현 CLAUDE.md 195줄, HEAD 7ab96205). 목록 = 25 파라미터 + 대조군 2 = 27 테스트로 보고와 일치.

어휘 커버리지: 25 needle 을 파싱해 "5+1 회의"·"옵션 표"·"단계 분할"·"High tier"·"정기 검증"·"18 PR"·"운영 검증" 7 프로브로 대조 → 전부 매칭 0건. 원칙 3 판별 어휘 미등록 확인.

실경로 뮤테이션(CLAUDE.md 원본 대상, 각 `assert mutated != orig` 통과 후 `write_bytes` 복원): (a) 원칙 3 절 삭제 → exit 0, 27 passed (b) " — 분리 시 High tier 사전 확인" 삭제 → exit 0 (c) ". ≥18 PR 영역은 ≥5 사이클마다 정기 검증" 삭제 → exit 0

### [측정 규율 — 회귀 가드] §측정 규율 1,465자를 통째로 삭제해도 관련 테스트 444건이 전건 GREEN (실경로 뮤테이션 실증)

- **위치**: `AGENTS.md:110`
- **주장**: AGENTS.md §측정 규율 본문의 생존을 단언하는 가드가 **0건**이다. 같은 파일의 §불변식 1·2 는 지문으로 핀돼 있는데 신설 절만 등록되지 않았다(등록 침묵). R54 는 '전부 봉인 + 회귀 가드 9건' 을 단언했으나 그 9건 중 §측정 규율 자신을 지키는 것은 0건 — AGENTS.md 불변식 2(실경로 뮤테이션 red 없이 HOLDS 금지)를 §측정 규율 자신이 위반한 상태로 머지됐다.
- **근거**: 실경로 뮤테이션 실행: AGENTS.md 에서 `## 🔴 측정 규율`(char offset 4,902) ~ `## Claude ↔ Grok 협업` 직전까지 **1,465자 삭제**. `assert mutated != orig` 확인 = sha256 `5b3d990197842167`(16,275 bytes) → `a9980478976adbc5`, `'측정 규율' in text` = False. 이 상태로 AGENTS.md 를 읽는 테스트 전 파일 실행 — `tests/unit/scripts/{test_claude_md_behavior_rules,test_policy_structure,test_rule_reachability,test_gate_claim_consistency,test_check_memory_refs}.py` + `tests/unit/hooks/test_doc_review_gate.py` = **444 passed**(1.86s), red 0. 복원 = `git checkout -- AGENTS.md` 후 sha256 원본 일치 확인, `git status --porcelain` 공백. 대조: `tests/unit/hooks/test_doc_review_gate.py:847-848` 은 `### 불변식 1 — fail-closed`·`### 불변식 2 — 실경로 뮤테이션` 을 리터럴 지문으로 핀한다 — 같은 파일의 다른 절은 보호받는데 신설 절만 빠졌다. `scripts/pre_push_gate.py:58-84` 의 repo-integrity 13 가드 중 AGENTS.md 절 구조를 읽는 것도 0.
- **처방**: `test_doc_review_gate.py:844` `_SOURCE_FINGERPRINTS` 에 `("AGENTS.md", "## 🔴 측정 규율", …)` 추가 + AGENTS.md 절 본문 5 규칙의 판별 어휘를 리터럴로 핀하는 가드 신설(피검사 파일에서 유도 금지 — `test_claude_md_behavior_rules.py:24` 자기참조 공허화 주석과 동일 원칙). 신설 시 본 뮤테이션(1,465자 삭제)이 red 임을 PR 본문에 실증할 것.
- **판정**: `SEVERITY_ADJUST` — REPRODUCED EXACTLY. AGENTS.md orig sha256 5b3d990197842167 (16,275 B / 10,178 chars); section '## 🔴 측정 규율' spans char 4,902→6,367 = 1,465 chars; deleted with `assert mutated != orig` holding → sha256 a9980478976adbc5; the 6 named files = 444 passed (1.70s), red 0 — exact match. I widened it: the ENTIRE guard surface (tests/unit/scripts + tests/unit/hooks) = 1123 passed, and all 8 repo-integrity scripts (check_docs_sync/toc_anchors/architecture_tree_sync/guard_fail_open/env_vars_sync/config_5way_sync/lint_js_nonvacuous/memory_refs) exit 0. Restored via `git checkout -- AGENTS.md`, sha256 back t

### [측정 규율 — 자동화 배선] 숫자를 대량 생산하는 회고·감사 워크플로가 §측정 규율을 한 줄도 싣지 않는다 — 강제하는 것은 정책 6(인용 정확성)뿐

- **위치**: `.claude/workflows/retrospective.mjs:142`
- **주장**: `.claude/workflows/retrospective.mjs` 와 `integrity-audit.mjs` 는 수십 에이전트에게 숫자·판정 산출을 지시하는 **최대 측정 생산면**인데, 프롬프트에 AGENTS.md 도 §측정 규율도 들어가지 않는다. 두 워크플로가 강제하는 유일한 측정 관련 조항은 정책 6(`grep -n` 실측)인데, 이는 **인용 좌표의 정확성**이지 **측정 도구 자체의 검증**이 아니다. R54 의 5건은 전부 정책 6 을 완벽히 지켜도 발생한다 — 정규식이 틀리면 `grep -n` 결과 자체가 틀린 전제 위에 놓인다.
- **근거**: `grep -rn "AGENTS\|측정" .claude/workflows/*.mjs .claude/workflows/_lib/*.mjs` = **0건**. 프롬프트의 측정 관련 조항 전량 = `retrospective.mjs:142`(*'정책 6: 코드/문서 인용 시 file:line 을 `grep -n` 실측 후 작성(추정 금지)'*) · `:179` · `integrity-audit.mjs:162` · `:203`. 실증: 본 세션에서 나에게 온 finder 프롬프트의 규율 조항도 *"🔴 정책 6: file:line 인용 시 `grep -n` 실측"* 1줄뿐이며 §측정 규율 언급 0. R54 표의 5건 중 '정규식 문자클래스에 소문자만'·'항목 분할 경계 오판'·'passed ↔ collected 혼동' 3건은 grep -n 실측을 해도 잡히지 않는 클래스다.
- **처방**: `retrospective.mjs:142`·`:179` 와 `integrity-audit.mjs:162`·`:203` 의 정책 6 줄 옆에 §측정 규율 5 규칙의 압축 1~2줄(도구 시험·경계 반증·도구 무관 무손실 검증·단위 명시·`assert mutated != orig`)을 **리터럴로** 추가하고, `tests/unit/scripts/test_workflow_loop_sync.py` 계열에 그 문구 생존 가드를 붙인다. 두 워크플로가 같은 문구를 쓰므로 `_lib` 공유 상수로 두면 drift 0(정책 16 사용처 ≥3 은 아니나 2곳 동일 리터럴이라 docs.md §손유지 원칙 적용).
- **판정**: `CONFIRMED` — 근거 전량 실측 재확인. (1) 인용 4곳 모두 존재 — retrospective.mjs:142/:179, integrity-audit.mjs:162/:203 이 정확히 정책 6 조항이며, `grep -rn "AGENTS|측정" .claude/workflows/*.mjs .claude/workflows/_lib/*.mjs` = 0건 (Bash grep + Grep 툴 이중 확인). (2) 두 워크플로의 프롬프트 빌더 전 문자열을 실측/검증/근거/수치/숫자/단위로 재스캔했으나 에이전트에게 도달하는 측정 관련 조항은 정책 6 뿐 — 나머지 매칭은 주석·출력 라벨이다. (3) 핵심 보강 증거(발견자 미인용): AGENTS.md:110 §측정 규율은 스스로 적용 술어가 "숫자나 판정을 내놓을 때"라 경로가 아님을 명시하고, AGENTS.md:133-149 규칙 진입 표는 경로→규칙 라우팅이라 이 축은 구조적으로 도달 불가다. AGENTS.md 는 auto-load 대상이 아니며 이는 실증됐다 — 본 검증관인 내 컨텍스트에는 CLAUDE.md(프로젝트+글로벌)와 MEMORY.md 만 주입됐고 AGENTS.md 본문은 0바이트다. 더욱이 나에게 온 verifyPromp

### [process/retro-loop] 회고→backlog→이행 폐루프의 3번째 관절에 intake 가 없다 — 3개 창 238건이 '다음 회고에서 재평가' 로 선언 폐기됐다

- **위치**: `docs/backlog.md:70`
- **주장**: backlog 가 흡수하지 못한 잔여 findings 의 유일한 처분 경로로 명시된 '다음 회고에서 재평가' 는 **구조적으로 실행 불가능**하다. 회고 범위 산출기는 머지 PR 만 보고, 회고 워크플로는 backlog 를 한 번도 읽지 않는다. 따라서 승격되지 않은 처방은 재평가되는 것이 아니라 **선언과 동시에 소멸**한다. 이것이 질문받은 'sink 를 세는 관측자 0' 의 정체다 — sink 가 새는 게 아니라 **연결되어 있지 않다**.
- **근거**: 동일 문구가 3개 창에 반복: `docs/backlog.md:70` (*"P2 62건은 보고서 본문 참조. 위 R35~R48 에 흡수되지 않는 잔여는 다음 회고에서 재평가."*) · `:121` (P2 76건, R16~R31) · `:153` (P2 100건, R1~R15) = 누적 **238건**. 그런데 `scripts/retro_scope.py:98-120` `compute()` 는 `newest_retro()` → `boundary_commit()` → `merged_prs(boundary)` 만 반환하며(`pr_count`·`prs`·`range`), backlog·처방 키가 **0개**다. `.claude/workflows/retrospective.mjs` 전문 grep 결과 `backlog|처방|prior|이전 회고` **hit 0** (유일한 `previous` 는 `:330` 의 무관한 주석). 즉 다음 회고의 입력은 '머지된 PR' 뿐이라 '이전 창의 미승격 처방' 은 설계상 시야 밖이다. 대조: `tests/unit/scripts/test_backlog_shape.py` 에 `retrospective|처방|_archive/reports` grep **hit 0** — 승격률을 보는 가드도 없다.
- **처방**: 세 관절 중 최소 하나에 관측면을 만든다. 가장 싼 것부터: (a) `retro_scope.py` 가 직전 회고 리포트의 `- 처방:` 블록 중 **backlog 어느 행에도 문자열 매칭되지 않는 것**을 `unpromoted[]` 로 함께 산출해 회고 컨텍스트에 주입 — 그러면 '재평가' 가 추정이 아니라 입력값이 된다. (b) `test_backlog_shape.py` 에 '직전 회고의 P0/P1 처방 수 vs 해당 창 R 행이 인용하는 처방 수' 대조를 추가하고, 미승격분이 있으면 `::notice` 로 계량(차단 아님 — 정책 17 안정성). (c) `docs/backlog.md:70·121·153` 의 '다음 회고에서 재평가' 문구는 이행 수단이 생기기 전까지 **거짓 약속**이므로 '재평가 경로 없음 — 소멸' 로 정직화하거나 (a) 배선과 동시 갱신한다.
- **판정**: `SEVERITY_ADJUST` — 기전은 4축 전부 실측 확인 — 결함은 실재한다. (1) `docs/backlog.md:70/121/153` 에 "…흡수되지 않는 잔여는 다음 회고에서 재평가" 문구가 인용대로 존재하며, finder 가 놓친 **4번째 인스턴스 `:95`**(R20 잔여 = session id 재사용 무탐지, P1급 게이트 갭)도 같은 비존재 경로로 이월된다. (2) `scripts/retro_scope.py` `compute()` 는 98~119행이며 반환 키 = `ok/prev_retro/boundary/head/pr_count/prs/range` — backlog·처방 키 0개. (3) `.claude/workflows/retrospective.mjs` `grep -c backlog` = **0**, `previous` 유일 hit 는 `:330` 무관 주석. (4) `test_backlog_shape.py`(325줄) 에 `retrospective|처방|_archive/reports` hit 0. 추가 검증(finder 미수행): `finderPrompt`(:135-147)·`gapFinderPrompt`(:178-186)·`.claude/skills/retrospe

### [docs/ledger-integrity] CLAUDE.md 424→195 절단이 열린 backlog 행과 그 출처 회고의 근거 포인터를 대량 무효화했다 — file:line 인용을 검증하는 가드가 0개 (미머지, 지금 잡을 수 있음)

- **위치**: `docs/backlog.md:39`
- **주장**: 오늘(2026-08-06) 커밋 `7ab96205` 이 CLAUDE.md 를 424 → 195줄로 절단하면서, **열린 backlog 행이 자기 주장의 근거로 인용한 줄 번호가 파일 끝을 넘어갔다**. 처방 이행 추적은 '그 의무가 아직 거기 있는가' 를 인용으로 확인하는 데 의존하는데, 그 기반이 사라졌다. 다음 세션이 R43 을 열어 `CLAUDE.md:366` 을 보면 아무것도 없으므로 그 행은 **반증 불가능**해지고, 조용히 닫히거나 무시된다. 리포 메모리는 CLAUDE.md 를 '재구조화 시 silent 회귀' 행동-임계 파일로 이미 지목해 뒀다.
- **근거**: 실측: `CLAUDE.md` = **195줄** (`git show 7ab96205:CLAUDE.md | wc -l` 이전 값 423, 커밋 제목 *"CLAUDE.md 424 → 196줄 (Anthropic 공식 200줄 기준)"*). 인용 스캔 결과 — `docs/backlog.md` 는 distinct CLAUDE.md 인용 3개 중 **2개가 EOF 초과**: `353`(R48 의 6-step ② '예외 없음' 근거) · `366`(R43 의 sync 의무 매트릭스 근거). 출처 리포트 `docs/_archive/reports/2026-08-04-retrospective.md` 는 **11개 중 9개가 EOF 초과**(199·203·351·353·354·366·380·387·415). 즉 확정 123건을 지탱하던 근거 좌표가 대부분 죽었다. 무결성 가드는 **경로**(`check_memory_refs.py`)와 **앵커**(`check_toc_anchors.py`)만 보고 `file:line` 이 실재하는지는 아무도 안 본다 — `scripts/check_*.py` 에 파일 길이 대조(`len(...splitlines())`) grep **hit 0**. 정황: 정책 17 원칙 1 은 *"Anthropic 200줄 hard target 등 외부 권장 규격은 가이드라인 — 안정성 충돌 시 거부"* 라고 적시하는데, 커밋 제목이 바로 그 200줄 기준을 사유로 든다. 🔴 `git merge-base --is-ancestor 7ab96205 origin/main` = **NOT on origin/main** — 아직 미머지라 머지 전에 시정 가능.
- **처방**: 머지 전에 두 가지를 같이 넣는다. (1) **좌표 재봉합**: 절단으로 옮겨간 의무(sync 매트릭스·6-step ②)의 새 위치로 `docs/backlog.md:39`(R43)·R48 의 인용을 갱신하고, 아카이브 리포트는 원문 보존이 원칙이므로 backlog 쪽에 *'인용은 절단 이전 좌표(#7ab96205 이전)'* 1줄을 남긴다. (2) **회귀 가드 신설**(정책 4 — 단언과 가드를 같은 PR 에): `docs/backlog.md`·`AGENTS.md`·`.claude/rules/**` 의 `<file>:<line>` 인용을 추출해 대상 파일 줄 수를 넘으면 red. 정책 6 이 요구하는 `grep -n` 실측 의무를 **원장 계층에서 기계화**하는 것이며, 지금 이 절단이 정확히 그 가드의 첫 실증 대조군이 된다.
- **판정**: `CONFIRMED` — 모든 수치 재실측 통과. (1) `7ab96205` = `docs/claude-md-under-200` HEAD, `git merge-base --is-ancestor 7ab96205 origin/main` → NOT on origin/main (미머지 확인, 지금 시정 가능). 실제 파일 = 195줄(커밋 제목 196 은 off-by-one). (2) 앵커 `docs/backlog.md:39` = `CLAUDE.md:366` 을 인용하는 R43 행 — 존재 확인. (3) `docs/backlog.md` distinct 인용 3개(35·353·366) 중 2개 EOF 초과이고 **둘 다 열린 행**: R48(🔴 결정 대기, `:353`) · R43(🟡 착수 가능, `:366`). (4) 회고 리포트 11개 중 9개 초과(199·203·351·353·354·366·380·387·415) — 주장과 정확히 일치. 리포 전체로는 distinct ~30개 중 ~28개가 195 초과. (5) 가드 공백 실재: `check_memory_refs.py` 는 슬러그/경로만, `check_toc_anchors.py` 는 앵커만, 신설 `tests/unit/scripts/te

### [process/prescription-follow-through] 명시 처방 3건 전건 미이행 확인 — 그중 workflow 커버리지 건은 R43 의 '부수' 절로 흡수돼 R43 자신의 반증 수단으로는 탐지 불가

- **위치**: `.claude/rules/guards.md:3`
- **주장**: 과제가 지목한 3건은 실측으로 **전부 미이행**이 맞다. 더 나쁜 구조가 있다: 3건 중 (1)(2)(3)에 해당하는 `.github/workflows/**` 축은 backlog 에서 사라진 게 아니라 **R43 의 '부수 =' 절로 강등**됐는데, R43 의 반증 수단은 `src/<area>` 축만 본다. 따라서 R43 의 본축(rules-sync CI 가드)을 구현해 ✅ 로 플립하면 workflow 커버리지 갭은 **한 번도 관측되지 못한 채 함께 닫힌다**. 이는 같은 회고가 R41 로 P1 확정한 *'✅ 마커가 미결 잔여를 흡수한다'* 와 정확히 동형이며, 회고가 진단한 결함 클래스를 회고 자신의 산출물이 재생산한 사례다.
- **근거**: (1) `.claude/rules/guards.md:3-8` frontmatter `paths:` = `scripts/**` · `.claude/hooks/**` · `.claude/workflows/**` · `tests/unit/scripts/**` · `tests/unit/hooks/**` **5개뿐**, `.github/workflows/**` 부재. (2) `CLAUDE.md:188` guards.md 행 = 동일 5경로, 미등재. (3) 커버리지 가드 부재 — 11개 rule 의 `paths:` 합집합 대 실제 표면을 계산한 결과 `.github/workflows/ci.yml`·`claim-review-on-body-edit.yml`·`codeql.yml` **3/3 이 matched rules: NONE**. `tests/unit/scripts/test_rules_and_index_coverage.py:75` 의 커버리지 단언은 `src/**/*.py`(리댁션 모듈) 한정이라 `.yml` 표면을 원리적으로 안 본다. 흡수 구조: `docs/backlog.md:39` R43 본문은 *"부수 = `.github/workflows/**` 가 10종 rule 어디에도 매칭되지 않아…"* 로 적으면서 같은 행 **반증 수단**은 *"`src/<area>` 를 건드리고 대응 `.claude/rules/<area>.md` 를 안 고친 PR 이 red 가 되는가"* — workflow 축을 판정하지 못한다. R43 상태는 여전히 `🟡 착수 가능`, `rules-sync` 가드 존재 여부 grep = **hit 0**.
- **처방**: 처방 3건을 이행하되, R43 의 반증 수단을 **축별로 분해**하는 것을 함께 한다(그러지 않으면 이행 여부와 무관하게 다음 창에서 같은 흡수가 재발). 구체: (a) `.claude/rules/guards.md:3-8` 에 `"​.github/workflows/**"` 추가 + `CLAUDE.md:188` 행 동기화(가드 `test_claude_md_matrix_never_promises_an_unloaded_path` 가 매트릭스 ⊆ frontmatter 를 강제하므로 frontmatter 를 먼저 넣어야 red 를 피한다). (b) `test_rules_and_index_coverage.py` 에 *'모든 `.github/workflows/*.yml` 이 최소 1개 rule glob 에 매칭'* 단언 추가 — 기존 `_glob_covers` 를 재사용하고, 대조군으로 매칭 0인 상태가 red 임을 확인. (c) `docs/backlog.md:39` R43 반증 수단을 *(i) src/<area> 축 (ii) workflow 커버리지 축* 2줄로 분리해 부분 이행이 전체 ✅ 를 청구하지 못하게 한다.
- **판정**: `CONFIRMED` — 전 인용 실측 통과. (1) `.claude/rules/guards.md:3-8` frontmatter `paths:` = `scripts/**`·`.claude/hooks/**`·`.claude/workflows/**`·`tests/unit/scripts/**`·`tests/unit/hooks/**` 5개뿐, `.github/workflows/**` 부재 — 정확. (2) `CLAUDE.md:188` guards.md 행 = 동일 5경로, 미등재 — 줄번호까지 정확. (3) 전 rule frontmatter `paths:` 합집합을 덤프해 `ls .github/workflows/` 와 대조: `ci.yml`·`claim-review-on-body-edit.yml`·`codeql.yml` **3/3 이 matched rules NONE** — 확인. `tests/unit/scripts/test_rules_and_index_coverage.py` 의 커버리지 단언(`test_log_redaction_modules_are_covered_by_security_rules`)은 `src/` 내 `logging.Filter` 서브클래스에서 대상을 유도하므로 `.yml`

### [메모리(교차 세션 학습 반송자)] 메모리 '쓰기' 의무가 리포 어디에도 존재하지 않는다 — 유입 0 은 사고가 아니라 설계된 결과다

- **위치**: `.claude/workflows/retrospective.mjs:169`
- **주장**: 이 리포는 메모리를 **읽는** 의무만 정의하고 **기록하는** 의무는 정책·워크플로·런북 어디에도 정의하지 않는다. 따라서 2026-08-01 이후 유입 0 은 '이번에 깜빡한 것'이 아니라 기전 부재의 정상 출력이며, 다음 세션도 자동으로 0 이다.
- **근거**: 리포 전수 grep(메모리 기록|메모리에 기록|메모리 신설|메모리 작성|memory intake|메모리 유입)이 잡은 것은 전부 `docs/cycle-history.md:2262,2280,2288,2296` 의 **서술적 과거 기록**('메모리 신설 3건')뿐 — 처방 1건도 없음. `docs/runbooks/retrospective.md` 는 '메모리' 0회. `.claude/workflows/retrospective.mjs:169` 의 유일한 언급은 '메모리/docs drift' = **찾아야 할 gap 유형 예시**이지 산출물 계약이 아님. `.claude/policies/active.md` 의 메모리 언급 3건(254·358·359)은 전부 기존 파일 **참조**. CLAUDE.md:136 '신규 메모리 추가 시 MEMORY.md 인덱스 동기화 의무' = 누군가 추가하기로 **결정한 뒤**에만 걸리는 조건부 의무. 대조: 2026-08-02 이후 커밋 28건 + 정식 5+1 회고 1회(#1274, 162 에이전트·확정 123) → 메모리 파일 mtime 최신값 여전히 2026-08-01 21:29(`ls -lt` 33 파일 실측).
- **처방**: `retrospective.mjs` 산출물 계약에 memory-intake 단계를 추가(확정 P0/P1 중 '클래스'로 승격된 finding 은 메모리 파일 신설/진화 의무) + `check_retro_cadence.py` 옆에 유입 카덴스 카운터(직전 회고 이후 확정 finding N건 대비 메모리 신규/수정 0건이면 SessionStart loud)를 배선. advisory 로 시작하되 **관측 가능**하게.
- **판정**: `SEVERITY_ADJUST` — 핵심 사실은 전부 독립 재현됐다. 심각도만 이 리포 자신의 rubric 과 어긋난다.

■ 재현 확인 (전부 직접 실측)
1. `.claude/workflows/retrospective.mjs:169` = `'(b) 미검증 양식 — 정책 cross-reference 누락, 시간차 누적 결함, 메모리/docs drift, 회귀 가드 부재 등'` — `completenessPrompt()` 내부, **찾아야 할 gap 유형 예시**가 맞고 산출물 계약이 아니다. 인용 정확 일치.
2. `docs/runbooks/retrospective.md` 의 '메모리' = `grep -c` **0**. 확인.
3. 확장 grep(주장보다 넓게 — `메모리 (기록|남기|추가|갱신|저장|등재|반영|신설|작성)`, `memory (write|intake|entry|capture|record)`, `MEMORY.md`)을 CLAUDE.md·AGENTS.md·`.claude/policies/`·`.claude/rules/`·**`.claude/agents/`·`.claude/skills/`·`.claude/hooks/`·`.claude/settings.json`**·`docs/run

### [메모리(교차 세션 학습 반송자)] 축소가 메모리 grep 을 '의무'→'권장' 으로 강등했고, 같은 커밋이 만든 생존 가드는 메모리 규칙을 한 줄도 고정하지 않아 초록으로 통과했다

- **위치**: `tests/unit/scripts/test_claude_md_behavior_rules.py:35`
- **주장**: 7ab96205(CLAUDE.md 424→196)는 메모리 관련 행동 규칙 3건을 약화시켰다. 같은 커밋이 '규칙 생존'을 지키려 신설한 `test_claude_md_behavior_rules.py` 의 26 어휘 목록에 **메모리 반송자 항목이 0건**이라, 강등이 27 passed 초록 아래로 그대로 통과했다. 회고가 확정한 클래스 (c)'축소가 자기 규정을 삼킴'이 **그 클래스의 시정책 안에서** 재발했다.
- **근거**: 강등 실측 — `git show 7ab96205^:CLAUDE.md` 335행 '메모리 grep **의무** detail = 메모리 디렉토리의 `feedback_` prefix 파일 참조' → 현행 `CLAUDE.md:137` '신규 fixture/테스트/패턴 작성 전 메모리 grep **권장**.' 소실 2건 — (1) 구 310~311행 `resolve_memory_dir` 유도 + `ls` 스니펫(메모리 디렉토리 내용을 **실제로 나열해** grep 을 가능케 하던 유일한 실행 수단)이 삭제되고 현행 체크리스트(`CLAUDE.md:125`)에는 `check_memory_refs.py` 만 남음 (2) 구 332행 'MEMORY.md 인덱스 + **카테고리 카운트** 동기화 의무'에서 카테고리 카운트 탈락. 가드 맹점 — `tests/unit/scripts/test_claude_md_behavior_rules.py:35-61` `_BEHAVIOR_RULES` 26항목에 '메모리'·'MEMORY.md'·'check_memory_refs' 어휘 전무(정책 1·5·7·8·9·10·11·12·13·14·15·16·17·19 + 6-step + isolation + 측정 규율만 고정). `py -3 -m pytest tests/unit/scripts/test_claude_md_behavior_rules.py -q` → **27 passed**.
- **처방**: `_BEHAVIOR_RULES` 에 메모리 반송자 항목 추가 — 최소 ('메모리 grep 의무', '메모리 grep 의무', '교차 세션 학습이 문서 축소와 무관하게 살아남는 유일 경로') + ('메모리 인덱스 동기화', 'MEMORY.md 인덱스'). 동시에 CLAUDE.md:137 을 '권장'→'의무'로 복원하고 메모리 디렉토리 나열 수단(구 310~311 스니펫 또는 `check_memory_refs.py` 의 dir 출력 활용법)을 본문에 되살릴 것. 🔴 정책 17 원칙 2: default rule 은 본문 보존이 정본이다.
- **판정**: `SEVERITY_ADJUST` — 실체는 확인됨 — 그러나 P0 은 과대.

**실측 확인된 것 (3/3 인용 재현)**
1. 강등 verbatim: `git show 7ab96205^:CLAUDE.md` 335행 `메모리 grep 의무 detail = 메모리 디렉토리의 feedback_ prefix 파일 참조` → 현행 `CLAUDE.md:137` `신규 fixture/테스트/패턴 작성 전 메모리 grep 권장.` 의무→권장 전환은 diff(`git show 7ab96205 -- CLAUDE.md` -484/+502)로 확정.
2. 구 310~311행 `ls "$(py -3 -c ... resolve_memory_dir ...)"` 삭제 확정(diff -457), 구 332행 `MEMORY.md 인덱스 + 카테고리 카운트 동기화 의무` → 현행 `CLAUDE.md:136` 에서 `카테고리 카운트` 탈락 확정(diff -481/+501).
3. 가드 맹점 확정: `tests/unit/scripts/test_claude_md_behavior_rules.py:35-61` `_BEHAVIOR_RULES` 는 `grep -in "메모리|memory|MEMORY"` 결과 **0 hit**. 같은 커밋

### [메모리(교차 세션 학습 반송자)] 메모리 가드의 유일한 자동 배선(pre-commit)이 이 머신에서 내려가 있고 CI 는 명시 제외 — 실행 경로가 '수동 체크리스트' 하나뿐이다

- **위치**: `.pre-commit-config.yaml:88`
- **주장**: `check_memory_refs.py` 를 자동 실행하는 지점은 pre-commit 하나뿐인데 이 머신에는 `.git/hooks/pre-commit` 이 없다. CI 는 명시적으로 제외했고 SessionStart 훅에도 미배선이다. 결과적으로 메모리 정합 검사는 CLAUDE.md 체크리스트를 사람이 수행할 때만 도는데, 그 체크리스트 항목 자체가 위 P0 에서 약화된 바로 그 표면이다.
- **근거**: `.pre-commit-config.yaml:88-95` 가 유일 배선(`stages: [pre-commit]`). `ls .git/hooks/pre-commit` → No such file. `py -3 scripts/check_precommit_installed.py` → '🔴 로컬 pre-commit 계층이 내려가 있습니다 … pre-commit 실행파일: 없음(PATH 부재) / .git/hooks/pre-commit: 없음' + '⚠️ 이 검사는 advisory(비차단)입니다 — 관측면일 뿐 보호가 아닙니다'(exit 0). `.github/workflows/ci.yml:127` = '(check_memory_refs=repo 밖 메모리 의존 … 제외 — CI whole-repo 부적합.)'. `.claude/settings.json:3-24` SessionStart 는 `check_retro_cadence.py`(9행)·`check_owed_verification.py`(14행)·`check_precommit_installed.py`(19행) 3종만 배선. `scripts/pre_push_gate.py` 는 'memory' 0회.
- **처방**: 메모리 디렉토리는 리포 밖이라 CI 에 넣을 수 없다는 판단 자체는 타당하다 — 그렇다면 **SessionStart 로 옮기는 것이 정합한 자리**다(카덴스·owed 원장과 동일 성격: 리포 밖 상태를 세션 시작에 관측). advisory·exit 0 유지(정책 17 안정성). pre-commit 설치는 별건으로 사용자 결정 필요(시크릿 훅 4종이 함께 내려가 있음).
- **판정**: `CONFIRMED` — 모든 인용을 실측 재확인했고 결함은 지금 이 순간 실재한다.

**인용 검증 (5/5 정확)**
- `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\.pre-commit-config.yaml:88` = `- id: check-memory-refs`, `:91` entry, `:94` `stages: [pre-commit]` — 인용 라인 정확.
- `.git/hooks/` 실측: `pre-commit.sample` 만 있고 `pre-commit` **없음**. `command -v pre-commit` → NOT FOUND. `git config core.hooksPath` → `.git\hooks` (리다이렉트 없음 — 다른 훅 디렉토리에 숨어 있을 가능성 배제). 존재하는 훅은 `pre-push` 하나뿐이고 그 내용은 `scripts/pre_push_gate.py` 호출로, 메모리 가드와 무관.
- `.github/workflows/ci.yml:127` = `# (check_memory_refs=repo 밖 메모리 의존·check_bilingual_comments=staged-diff 기반은 제외 — CI whole-repo 부적

### [메모리(교차 세션 학습 반송자)] 가드의 트리거 범위가 스캔 범위보다 좁다 — AGENTS.md·backlog·rules·runbooks 에 죽은 슬러그를 넣어도 검사가 깨어나지 않는다

- **위치**: `.pre-commit-config.yaml:92`
- **주장**: 2026-08-05 감사가 스캔 범위를 6 표면으로 넓히면서 pre-commit `files:` 패턴은 함께 넓히지 않았다. 스크립트는 6 표면을 읽지만 훅은 2 표면 편집에만 발화하므로, 나머지 4 표면(AGENTS.md·docs/backlog.md·.claude/rules/*·docs/runbooks/*)에 dangling 슬러그가 들어가도 커밋이 통과한다. 잔존 참조 5건 중 2건이 정확히 이 미발화 구역에 있다.
- **근거**: 스캔 범위 — `scripts/check_memory_refs.py:36-41` `_DOC_GLOBS`=`.claude/policies/*.md`·`.claude/rules/*.md`·`docs/runbooks/*.md`, `_DOC_LITERALS`=`CLAUDE.md`·`AGENTS.md`·`docs/backlog.md`. 트리거 범위 — `.pre-commit-config.yaml:92` `files: "^(CLAUDE\\.md|\\.claude/policies/.*\\.md)$"` (2 표면). 미발화 구역의 실제 참조: `.claude/rules/guards.md:204` `[[feedback-mutation-restore-crlf]]` · `.claude/rules/services.md:34` `[[feedback-fixture-model-sync-discipline]]`. 스크립트 자신의 주석(`:24-40`)은 '범위가 좁으면 … 가드가 ✅ 전부 존재 를 인쇄한다 — 빈/좁은 범위 위의 초록은 fail-open 이다' 라고 **정확히 이 결함을 서술**하면서도 트리거 축에는 적용하지 않았다.
- **처방**: `files:` 를 스캔 범위와 동일하게 확장: `^(CLAUDE\.md|AGENTS\.md|docs/backlog\.md|\.claude/(policies|rules)/.*\.md|docs/runbooks/.*\.md)$`. 더 안전하게는 `always_run: true` + `pass_filenames: false`(이미 false). 스캔 범위와 트리거 범위의 동치를 단언하는 회귀 가드 1건 동반(정책 4 — 단언과 회귀 가드를 같은 PR 에).
- **판정**: `CONFIRMED` — 인용 4건 전부 실측 일치. (1) `.pre-commit-config.yaml:92` = `files: "^(CLAUDE\\.md|\\.claude/policies/.*\\.md)$"` — 2 표면. (2) `scripts/check_memory_refs.py:36-41` = `_DOC_GLOBS` 3(`.claude/policies/*.md`·`.claude/rules/*.md`·`docs/runbooks/*.md`) + `_DOC_LITERALS` 3(`CLAUDE.md`·`AGENTS.md`·`docs/backlog.md`) — 6 표면. (3) `.claude/rules/guards.md:204` `[[feedback-mutation-restore-crlf]]` · (4) `.claude/rules/services.md:34` `[[feedback-fixture-model-sync-discipline]]` 둘 다 해당 줄에 실재. 스크립트 실행 결과 `참조된 슬러그: 5개` — 그중 2건이 정확히 미발화 구역에서만 인용된다(나머지 3건은 `.claude/policies/active.md`). 주장한 수치가 전부 맞다.

【반증 시도 — 다른 집행면이

---

## P2 — 82건

### [process] 정책 13 운영 smoke check 섹션이 이 창 12/12 PR 에서 0건 — 하필 'CI 초록·운영 사망' P0 가 터진 창이었다

- **위치**: `.claude/policies/active.md:170`
- **주장**: 정책 13 은 인증/외부 통합 변경 PR 과 매 사이클 종료 시 §"운영 smoke check 결과" 섹션을 의무화하는데, 이 창의 실질 PR 12건(#1276·1279·1280·1282·1284·1286·1288·1289·1290·1291·1293·1294) 전부에서 해당 섹션이 0건이다. 세션16 종료 PR(#1290)도 포함된다. 그리고 이 창에서 발견된 P0 가 정확히 정책 13 이 존재하는 이유였다.
- **근거**: 각 PR 본문 `grep -ci "smoke check"` → 12건 전부 0. `.claude/policies/active.md:170` = "🔴 **자동화 가드는 manual smoke check 의무를 대체하지 않는다** — CI 통과 ≠ 운영 정상. PR 본문 §\"운영 smoke check 결과\" 섹션은 인증/외부 통합 변경 PR 마다 여전히 의무". #1289 는 Anthropic API 호출 경로 3곳을 바꾼 외부 통합 PR 이며, 그 커밋 body 가 스스로 적는다 — "**모든 AI 코드리뷰가** `400 … ` → `api_error` 였다 … **단위 테스트는 env 를 안 읽어 초록이고 고장은 실 API 호출에서만 드러난다**". 즉 운영 사망이 CI 전건 초록 아래에서 지속됐고, 발견 경로는 정책 13 이 아니라 **다른 기능을 검증하다 우연히**였다. 관측자 부재도 실측 — `grep -rln smoke scripts/*.py .github/workflows/*.yml` 무결과.
- **처방**: (a) 세션 종료 trailing sync PR 템플릿에 §운영 smoke check 결과 3행(엔드포인트·기대값 출처 `docs/runbooks/operational-smoke-checks.md`·실측)을 고정 필드로 넣는다. (b) 더 근본적으로는 'AI 리뷰 실패율' 같은 제품 핵심 지표의 운영 관측면이 없다는 것이 이번 P0 의 진짜 근본이므로, backlog 에 '운영 AI 리뷰 status 분포 관측' 항목 신설을 사용자 결정으로 올린다.
- **판정**: `SEVERITY_ADJUST` — 실재하나 P1 을 지탱하던 두 근거가 검증에서 무너져 P2 로 조정.

【확인된 사실】(1) 인용 `.claude/policies/active.md:170` = 인용문과 축자 일치(citation_verified=true). (2) 12건 PR 본문 `grep -ci "smoke check"` → 전건 0, 정확히 재현. #1290 의 "smoke" 1히트는 `operational-smoke-checks.md` 파일명 언급이지 §섹션 아님. (3) #1289 는 실제 외부 통합 PR — ai_review.py·dashboard_service.py·repo_insight_service.py 3 Anthropic 호출 경로 + config.py 변경 실측. (4) #1290 = 세션16 종료 trailing sync(사이클 종료 의무 해당). (5) 커밋 body 인용 축자 정확, P0 는 전 AI 리뷰 사망·CI 초록·타 기능 검증 중 우연 발견. (6) 관측자 부재 — claim 의 grep 을 넘어 `scripts/` `.github/` 전체로 확대해도 여전히 0건(주장보다 강한 실측).

【무너진 근거 1 — 분모 부풀림】정책 13 의무 발생 조건은 "인

### [process] 정책 14 Code Scanning 사이클 종료 검토가 창 전체에서 미이행 — 이 창이 만든 open alert 1건이 무분류로 잔존

- **위치**: `docs/runbooks/operational-smoke-checks.md:1`
- **주장**: 정책 14 는 매 사이클 종료 시 Code Scanning open alert 를 직접 검토하고 (a)fix/(b)dismiss+사유/(c)suppress+회고 중 하나로 처리하도록 한다. 이 창의 어느 PR 본문에도 alert 검토 기록이 없고, 실제로 #1291 이 유입시킨 open alert 1건이 3 PR 동안 분류되지 않은 채 남아 있다.
- **근거**: `gh api repos/xzawed/SCAManager/code-scanning/alerts` 실측 = open **1건** — `{"number":565, "rule":"py/unused-import", "severity":"note", "path":"e2e/test_theme.py", "created":"2026-08-05T12:44:41Z"}`. 생성 시각이 #1291 머지(2026-08-05T12:42:57Z) 직후이며 #1291 이 그 파일을 재작성했다. 이후 #1292·#1293·#1294 3 PR 이 지나는 동안 본문 `grep -ci "code scanning|CodeQL alert"` 는 세션 종료 PR #1290 을 포함해 전부 0. 선례상 이 룰은 오탐일 수 있다(사이클 113 #549 = `py/unused-import` false-positive 확정 후 dismiss).
- **처방**: 세션 종료 trailing sync PR 본문에 §"Code Scanning open alert" 1행(카운트 + 각 alert 의 처리 분류)을 고정 필드로 넣는다 — 이미 `scripts/check_codeql_alerts.py` 가 있으므로 그 출력을 붙이는 것으로 충분하다. #565 는 실사용 여부 `grep -n` 확인 후 fix 또는 dismiss+사유로 즉시 종결.
- **판정**: `CONFIRMED` — 핵심 주장은 실측으로 성립한다. `gh api .../code-scanning/alerts` open = 1건(#565 `py/unused-import` `e2e/test_theme.py:2` note, created 2026-08-05T12:44:41Z, dismissed_by=null, 현재 main head faeb2cf1 에 여전히 open), PR #1290~#1294 본문 `grep -ci "code[ -]?scanning|codeql|alert"` 전건 0, STATE.md·backlog.md 에도 미기재 → 무분류 잔존 사실 확인. 인용 파일도 실재하며 §9(L280~355)가 정확히 정책 14 절차((a)/(b)/(c) 표 L319 + PR 본문 섹션 형식 L323~333)다.

다만 제시된 기전 2건은 정정해야 한다. (1) **"#1291 이 유입시켰다"는 틀렸다** — `git show 5b72c438^:e2e/test_theme.py` 실측 결과 `import pytest` 는 #1291 이전부터 line 2 에 있었고 이미 미사용이었다. 실제로는 동일 룰·동일 파일·동일 line 의 alert **#79** 가 2026-04-26 "

### [process] 사용자에게 올린다고 명시한 결정을 회신 전에 Claude 가 스스로 집행했다

- **위치**: `CLAUDE.md:217`
- **주장**: #1291 은 CSP/폰트 방향을 "정책 15 High tier + 정책 11 이라 Claude 가 임의 결정하지 않는다 … 아래 표에서 골라 주세요. **제가 정하지 않았습니다**" 로 명시 에스컬레이션했는데, 사용자 회신 전에 #1294 가 ㉰ 를 선택해 집행했다. 완화 요인은 있으나(측정으로 결정 공간이 붕괴 · 본문에 자율 판단 명시 · PR 미머지라 사용자 게이트 유지) 자기 선언의 번복 자체는 기록되어야 한다.
- **근거**: #1291 본문 = "고치는 방향이 보안 완화 ↔ 시각 변경으로 갈려 정책 15 High tier + 정책 11 이라 Claude 가 임의 결정하지 않는다" + "🔴 **CSP 결정** — 아래 표에서 골라 주세요. 제가 정하지 않았습니다." → #1294 본문 = "무해한 쪽은 ㉰ 였습니다. **㉰ 로 진행했습니다.**" (`gh pr list` 기준 #1294 는 현재 OPEN — 사용자 머지 게이트는 살아 있다). 정책 9 완화 미적용 3영역에 'UX 결정'이 포함되므로 형식상 회신 의무 영역에 가깝다.
- **처방**: 에스컬레이션한 결정을 측정 결과로 회수할 때는 '결정 회수' 를 명시 라벨로 남긴다 — 예: PR 본문에 "🔄 #1291 에서 올린 결정을 회수합니다(사유: 측정으로 옵션 ㉯㉮㉱ 가 무의미해짐). 이의 있으시면 머지 전에 알려 주세요" 1행. 정책 3(자율 판단 사후 보고)의 하위 유형으로 규약화하면 다음 세션이 같은 판단을 재현할 수 있다.
- **판정**: `CONFIRMED` — 실측 검증 결과 주장의 핵심 사실 3개가 모두 성립한다.

**1) 자기 선언 존재 — 확인.** #1291 본문 verbatim: "🔴 **CSP 결정** — 아래 표에서 골라 주세요. 제가 정하지 않았습니다." + ㉮~㉱ 4옵션 표(㉰ 단점 = "한글 렌더가 눈에 띄게 바뀜").
⚠️ **인용 출처 정정**: 근거로 제시된 "정책 15 High tier + 정책 11 이라 Claude 가 임의 결정하지 않는다" 문구는 **#1291 PR 본문에 없다**(grep 0건). 실제 출처는 `docs/backlog.md:51` R52 행이며, 작성자는 동일하게 #1291(`git log -S` → commit 5b72c438)이다. 즉 문구는 실재하고 저술 주체도 #1291 이지만, 산출물 귀속이 부정확했다(본문 ↔ 원장). 주장 substance 는 보존된다.

**2) 회신 전 집행 — 확인.** #1294 본문 verbatim: "무해한 쪽은 ㉰ 였습니다. **㉰ 로 진행했습니다.**" #1291 에는 **사람 코멘트·리뷰 0건**(sonarqubecloud·codecov 봇만). #1291 머지 2026-08-05T12:42:57Z → #1294 생성 1

### [process] backlog R43 재확인 — 이 창도 src 3영역 변경 대비 대응 rules 갱신 0건

- **위치**: `CLAUDE.md:366`
- **주장**: CLAUDE.md:366 의 path-scoped rules 본문 sync 의무(사용자 명시 결정)가 이 창에서도 이행되지 않았다. 변경된 src 영역 3개에 대응하는 rules 파일은 하나도 갱신되지 않았고, 갱신된 rules 5개는 모두 다른 계기(문서 감사·CI)에서 나왔다.
- **근거**: `git diff --name-only 8f4ada5a..226cd4a9 -- src/` = `src/analyzer/io/ai_review.py`·`src/analyzer/pure/review_prompt.py`(→ pipeline.md) · `src/services/dashboard_service.py`·`src/services/repo_insight_service.py`(→ services.md) · `src/templates/{base,landing,settings}.html`(→ ui.md). `git diff --name-only … -- .claude/rules/` = `api.md`·`deploy.md`·`docs.md`·`guards.md`·`testing.md` — **pipeline.md·services.md·ui.md 0건**. 즉 매칭 3/3 미이행으로, backlog R43("발화율 ~100% · 실이행률 0%", 🟡 착수 가능·미종결)이 이 창에서도 그대로 성립한다.
- **처방**: R43 의 처방(이행 조건 또는 면제 경로 신설)을 다음 사이클 착수 후보로 올린다. 최소안 = PR 본문에 `rules-sync-not-required: <사유>` 면제 마커를 도입하고 PR-diff 한정 advisory 로 계량만 시작(정책 17 안정성 — 차단 없이 관측 가능성부터).
- **판정**: `CONFIRMED` — 인용 실측 확인: CLAUDE.md:366 = `.claude/rules/<area>.md` 행, 🔴 "사이클 86 Q2 신설 (사용자 명시 결정)" + "path 매칭 영역 변경 시 해당 rules 본문 갱신 의무" (매트릭스는 10→11 영역으로 성장했으나 의무 문구 불변). 핵심 사실 재현 확인: `git diff --name-only 8f4ada5a..226cd4a9 -- src/` = analyzer 2건(→pipeline.md) · services 2건(→services.md) · templates 3건(→ui.md) [+ 청구가 누락한 src/config.py]; `-- .claude/rules/` = api·deploy·docs·guards·testing — pipeline.md·services.md·ui.md 0건. 매칭 3/3 미이행 성립. 미해소 확인: docs/backlog.md:39 R43 = 🟡 착수 가능(open). 실질성 확인(단순 장부 의무 아님): 본 창 마지막 커밋 226cd4a9 가 "CSP 가 자기 폰트를 차단하던 죽은 링크 5개"를 고치고 신규 가드 tests/unit/ui/test_csp_external_asset_p

### [code] R52 "완료 (30 → 0)" 선언이 그 PR 자신의 CI 와 모순 — E2E 는 여전히 red (1 failed)

- **위치**: `docs/backlog.md:51`
- **주장**: `docs/backlog.md:51` 이 R52 를 **✅ 완료 (30 → 0)** 로, 커밋 226cd4a9 제목이 **"R52 종결"** 로, 본문이 *"콘솔 에러 2 → 0"* 으로 단언한다. 그러나 **그 브랜치의 CI(run 31023866508 · job 92367306323)에서 `E2E (Playwright)` 는 failure** 이고 결과는 `1 failed, 119 passed, 1 skipped` 다. 실패는 R52 가 고쳤다고 주장한 바로 그 테스트 `test_dashboard_no_js_runtime_errors` 이며, 남은 콘솔 에러는 **2 → 0 이 아니라 2 → 1** 이다: `Refused to apply style from 'http://localhost:8001/static/css/dist/tailwind.css' because its MIME type ('application/json') is not a supported stylesheet MIME type`. '0' 이라는 수치는 **로컬 실측**에서 나왔고, 로컬에는 gitignore 된 빌드 산출물 `src/static/css/dist/tailwind.css` 가 존재(2026-05-23 빌드)해 그 에러가 나지 않는다. 즉 R52 가 스스로 진단한 *"로컬 Windows 에서만 초록"* 을 **같은 세션에서 재생산**했다. 부수적으로 세 표면이 서로 다른 수치를 말한다 — `README.md:22` 배지 `119_pass / 1_known_app_bug` · `docs/STATE.md:32` *"121 통과 / 1 skip (로컬 실측)"* · `docs/backlog.md:51` *"30 → 0"* · 기계 진실 `119 pass / 1 fail / 1 skip`.
- **근거**: gh run view 31023866508 --json jobs → `failure  E2E (Playwright)` (그 외 8 job 전부 success). job 92367306323 로그: `AssertionError: JS 런타임 오류: ["console.error: Refused to apply style from 'http://localhost:8001/static/css/dist/tailwind.css' ..."]` / `1 failed, 119 passed, 1 skipped in 149.71s`. 실패 지점 `e2e/test_dashboard.py:168` (`assert not errors`). 로컬 산출물 존재: `ls src/static/css/dist/tailwind.css` → 12060 bytes (2026-05-23), `.gitignore:87` = `src/static/css/dist/tailwind.css`.
- **처방**: R52 행의 `✅ 완료 (30 → 0)` · `콘솔 에러 2 → 0` 을 **CI job 결과 기준**으로 정정(`119 pass / 1 fail`, 잔여 원인 = tailwind 빌드 부재)하고, 새 원장 항목으로 분리한다. 이 리포의 정책 19 2-phase 보고 게이트를 그대로 적용 — 로컬에서만 잰 수치는 `UNVERIFIED:` 또는 "로컬 실측, CI 미확인" 표기 없이 '완료/종결' 어휘와 함께 쓰지 않는다. 완료 선언 직전 `gh run view <PR run> --json jobs` 1회 확인을 6-step ④ 에 붙일 것.
- **판정**: `SEVERITY_ADJUST` — 인용은 전건 실측 일치하나, 핵심 주장("E2E 는 여전히 red")은 **stale run 을 근거로 한 것**이라 P0 이 성립하지 않는다.

■ 검증된 부분 (전건 일치)
- `docs/backlog.md:51` = `| **R52** | ✅ 완료 (30 → **0**) — CSP 앱 버그까지 해소 (`#1294`) |` — 존재 확인. `git log -S` 실측: 이 문자열을 도입한 커밋이 **226cd4a9 바로 그 커밋**이다(226cd4a9 가 backlog.md 를 touch).
- run **31023866508**(sha `226cd4a98`, branch `fix/csp-font-r52`): `E2E (Playwright)` = **failure**, 나머지 8 job success. job **92367306323** 로그 = `1 failed, 119 passed, 1 skipped, 2 warnings in 149.71s`, `e2e/test_dashboard.py:168: AssertionError`, 메시지 = tailwind.css MIME `application/json` 거부. 인용과 글자 단위로 일치.
- 그 커밋 시점 

### [code] E2E CI job 이 Tailwind 를 빌드하지 않는다 — 영구 red + 119 초록이 '프로덕션과 다른 렌더'에서 나온 것

- **위치**: `.github/workflows/ci.yml:545`
- **주장**: `.github/workflows/ci.yml:501` 의 `e2e` job(#1288 신설)은 checkout → setup-python → pip install → playwright install → `python -m pytest e2e/` 만 실행하고 **node/npm 단계가 전혀 없다**(`:545-546`). 그런데 `src/templates/base.html:39` 가 `/static/css/dist/tailwind.css` 를 로드하고, 그 파일은 `.gitignore:87` 로 **리포에 없으며** `package.json:7` 의 `npm run build` 로만 생성된다(프로덕션은 `railway.toml` buildCommand 끝의 `npm ci && npm run build` 로 생성). 따라서 CI 의 e2e 는 **Tailwind 유틸리티가 전무한 페이지**를 대상으로 122건을 돌린다: (a) `test_dashboard_no_js_runtime_errors` 는 원인 제거 전까지 **영구 red** — R7 배선의 목적이던 관측면이 '항상 빨간 job' 으로 무력화되고 red 정상화를 학습시킨다(원죄 재생산) (b) 나머지 **119건의 초록은 프로덕션 렌더에서 얻은 것이 아니다** — Tailwind 의존 레이아웃 회귀는 원리적으로 못 보고, 반대로 `.hidden` 이 죽어 **보여선 안 될 요소가 노출된 상태**에서도 아무도 실패하지 않았다(backlog R53 '초록은 감사된 적이 없다' 의 실물 증거). 이 red 의 진짜 원인은 **어느 원장에도 기재돼 있지 않다**(`docs/backlog.md`·`docs/STATE.md` 에 `tailwind` 검색 결과 R52/R7 관련 기재 0건).
- **근거**: ci.yml `e2e` job 전문 확인(:501-546) — npm 스텝 없음. `.gitignore:87` · `package.json:7` (`tailwindcss -i ./src/static/css/main.css -o ./src/static/css/dist/tailwind.css --minify`) · `src/templates/base.html:39`. CI 콘솔 에러가 `MIME type ('application/json')` = StaticFiles 404 JSON 응답(마운트 `src/main.py:362`). E2E job 은 #1288 배선 이후 **모든 run 에서 failure**(main 30960334466·31006842786·31007711435·31020711556, PR 31006357625·31015344753·31020170116·31023866508 전건).
- **처방**: e2e job 에 `actions/setup-node` + `npm ci && npm run build` 를 pytest 앞에 추가(프로덕션 빌드와 동일 경로). 대안으로 산출물 커밋은 권장하지 않는다(빌드 drift). 추가 후 **한 번은 job 이 초록임을 실측**하고, 그때 비로소 required check 승격 여부를 판단할 것(ci.yml:498 의 '실행 이력이 없어 flakiness 를 모른다' 는 전제가 그때 충족된다). 함께: 프론트 자산 빌드 산출물이 없을 때 앱이 조용히 깨지지 않도록, 빌드 산출물 부재를 감지하는 단위 가드(템플릿이 참조하는 `/static/**` 경로가 실제 파일이거나 빌드 스크립트 산출물인지) 1건 추가 권장 — 신규 fresh clone 개발 환경도 같은 상태다.
- **판정**: `SEVERITY_ADJUST` — 기전은 실재했고 기계로 증명된다 — 그러나 헤드라인 결함은 관측 시점 직후 이미 해소됐다. 남은 것은 원장 오귀속 1건뿐이라 P1→P2.

[1] 인용 전건 실측 일치 (citation_verified=true). 사전-수정 커밋 226cd4a9 의 ci.yml 은 정확히 546줄이고 e2e job(:501~:546)에 node/npm 스텝이 전무하다 — 주장한 ":501-546 / :545-546" 과 정확히 부합. 보조 인용도 전부 정확: base.html:39 = `<link rel="stylesheet" href="/static/css/dist/tailwind.css">` · .gitignore:87 = `src/static/css/dist/tailwind.css` · package.json:7 = `tailwindcss -i ./src/static/css/main.css -o ./src/static/css/dist/tailwind.css --minify` · main.py:362 = CachedStaticFiles 마운트. 인용 run ID 8건 중 6건(31023866508·31020711556·31020170116·31015344753·31007

### [code] 신규 CSP 정합 가드가 src/templates 만 훑어, 실제로 서빙되는 src/static/mockup-polar.html 의 동일 결함을 못 본다

- **위치**: `tests/unit/ui/test_csp_external_asset_parity.py:56`
- **주장**: R52 재발 가드 `tests/unit/ui/test_csp_external_asset_parity.py:56` 은 `_TEMPLATES.rglob("*.html")` 로 **`src/templates/` 만** 스캔한다. 그런데 `src/static/mockup-polar.html:7-8` 이 제거 대상과 **완전히 같은** jsDelivr Pretendard `preconnect + stylesheet` 를 여전히 로드하고, 이 파일은 `src/main.py:362` 의 `/static` 마운트로 **공개 서빙**돼 같은 CSP(`src/main.py:93` `style-src 'self' 'unsafe-inline'`)에 걸린다. 즉 가드가 겨냥한 결함 클래스가 가드 시야 밖에 그대로 살아 있다 — '봉인' 주장의 관측면 구멍(가드가 참인 채로 결함이 존속).
- **근거**: `grep -rn "cdn.jsdelivr|fonts.googleapis" src/ --include=*.html` → 잔존은 `src/static/mockup-polar.html:7,8` 뿐. 가드 스캔 범위 `tests/unit/ui/test_csp_external_asset_parity.py:29` (`_TEMPLATES = _ROOT/"src"/"templates"`) · `:56`. 정적 마운트 `src/main.py:362` `app.mount("/static", CachedStaticFiles(...))`.
- **처방**: 스캔 범위를 `src/templates/**` + `src/static/**/*.html` 로 확대하거나, mockup 파일이 배포에 불필요하면 삭제한다(서빙되는 죽은 mockup = 불필요한 공개 표면). 어느 쪽이든 뮤테이션 red 재확인.
- **판정**: `CONFIRMED` — All five cited file:line references verified exact by grep/read. Guard scan root is `_TEMPLATES = _ROOT/"src"/"templates"` (test_csp_external_asset_parity.py:29) consumed solely at :56 via `_TEMPLATES.rglob("*.html")`; `src/static/mockup-polar.html:7-8` still carries the identical jsDelivr Pretendard preconnect+stylesheet; `src/main.py:362` mounts `/static`; `src/main.py:93` sets `style-src 'self' 'unsafe-inline'` (no external origin, so the sheet is blocked).

Independent adversarial verification beyond the claim: (1) the CSP genuinely reaches static responses — `SecurityHeadersMiddleware` is

### [code] doc_review_gate `corrupted()` 의 근거 서술이 실측과 다름 — `_scrub_surrogates` 는 U+FFFD 가 아니라 '?' 를 남긴다

- **위치**: `.claude/hooks/doc_review_gate.py:433`
- **주장**: `.claude/hooks/doc_review_gate.py:433` 주석이 *"lone surrogate 는 … 나중에 `_scrub_surrogates` 가 U+FFFD 로 바꾼다"* 라고 기전을 설명하지만, `:379` 의 구현은 `text.encode("utf-8", errors="replace").decode("utf-8")` 이고 **encode 시 errors="replace" 는 U+FFFD 가 아니라 ASCII `?` 를 낸다**(실측: `'ab\ud800c'` → `'ab?c'`, `'�' in result == False`). 동작 자체는 두 갈래를 모두 검사하므로 지금 당장 오탐/미탐을 만들지 않지만, `:887` DEGRADED 배너도 손상 표지를 *"U+FFFD 또는 lone surrogate"* 로만 고지하므로 **정화 후 남는 `?` 는 어느 층에서도 손상 표지로 인식되지 않는다**. 이 리포가 SSOT 로 취급하는 가드의 근거 서술이 틀리면 다음 수정자가 거짓 모델 위에서 판단한다(정책 6 line:span 실측 의무의 취지와 동일 축).
- **근거**: 구현 `.claude/hooks/doc_review_gate.py:379-390`, 주석 `:433`, 배너 `:887`. 실측: `py -3 -c "s='ab\ud800c'; r=s.encode('utf-8',errors='replace').decode('utf-8'); print(repr(r), '�' in r)"` → `'ab?c' False`.
- **처방**: 주석을 실측대로 정정하거나(`?` 로 치환된다), 정화를 `errors="ignore"`/명시적 surrogate 제거로 바꿔 서술과 구현을 일치시킨다. 어느 쪽이든 `_scrub_surrogates` 왕복 결과를 단언하는 단위 테스트 1건(현재 이 문자에 대한 단언 없음)을 붙여 서술이 아니라 코드가 정본이 되게 할 것.
- **판정**: `CONFIRMED` — 실측으로 재현됨. `.claude/hooks/doc_review_gate.py:390` 의 `_scrub_surrogates` 는 `text.encode("utf-8", errors="replace").decode("utf-8")` 이고, encode 측 replace 핸들러는 U+FFFD 가 아니라 ASCII `?` 를 낸다: `json.loads('"ab\uD800c"')` → `'ab\ud800c'` → scrub 후 `'ab?c'` (U+FFFD 부재, 실행 확인). 따라서 `:433`/`:435` 의 *"나중에 `_scrub_surrogates` 가 U+FFFD 로 바꾼다 / lone surrogates that only become U+FFFD later"* 는 기전 서술이 틀렸다. 인용 3곳 모두 실재 확인(구현 :379-390, 주석 :433, 배너 :887). 원 주장보다 한 단계 더 나쁜 사실도 확인: 정화 후에는 `corrupted('ab?c')` 가 **두 갈래 모두 False** 여서 손상이 미표시가 아니라 아예 미탐지다 — 즉 docstring 이 함의하는 "scrub 후에도 U+FFFD 로 여전히 잡힌다" 는 불변식이 성립하지 않는

### [docs] README E2E 배지가 STATE 와 어긋나고, 같은 커밋이 고친 앱 버그를 아직 살아 있다고 단언한다

- **위치**: `README.md:22`
- **주장**: 마지막 커밋 226cd4a9 가 `docs/STATE.md:32` 의 E2E 수치를 `119 통과 / 1 실패 / 1 skip` → `121 통과 / 1 skip` 으로 바꾸고 CSP 앱 결함 해소를 명시했으나, 같은 커밋에서 README 2종의 E2E 배지는 그대로 뒀다. 배지는 여전히 `119_pass / 1_known_app_bug` 를 노랑으로 주장한다 — 즉 (a) SSOT 와 불일치하고 (b) **그 커밋이 방금 제거한 앱 결함이 아직 남아 있다고 외부에 알린다**.
- **근거**: `README.md:22` = `E2E-122_in_CI_(119_pass_%2F_1_known_app_bug)-yellow` · `README.ko.md:22` = `122_CI_배선(119_통과_%2F_1_기지_앱버그)` · `docs/STATE.md:32` = `E2E 122 … **121 통과 / 1 skip** … CSP 가 자기 폰트를 차단하던 앱 결함까지 해소`. `git show 226cd4a9 -- README.md` 는 Tests 배지 한 줄만 바뀌었고 E2E 배지 줄은 무변경. 산술도 자기모순 — 119+1=120 ≠ 122. CLAUDE.md:355 = *"README.md 배지 동기화 … 수치 출처는 항상 `docs/STATE.md`"*. 가드는 이 축을 보지 않는다: `py -3 scripts/check_docs_sync.py` 실행 결과 `✅ STATE 종합·추적셀 ↔ README.md ↔ README.ko.md 전체/단위 카운트 일치 / EXIT=0` (검사 대상 = Tests 전체·단위 + FastAPI 배지뿐).
- **처방**: E2E 배지를 STATE:32 기준으로 갱신하고(그리고 CI 미확인 상태면 그 사실을 배지 문구에 담고), `check_docs_sync.py` 의 대조 집합에 E2E 축을 추가해 6-step ⑤ 의 `--fix` 파생 지점으로 편입한다. 지금 구조는 '손유지 5→1' 로 줄이면서 E2E 배지만 가드 밖 수동 지점으로 남겨 둔 상태다.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 일치 — 다만 P1 을 정당화하던 절반이 이미 사라졌다.

**인용 재확인 (전건 일치, 관측 시점 226cd4a9 기준)**
- `git show 226cd4a9:README.md | sed -n 22p` → `E2E-122_in_CI_(119_pass_%2F_1_known_app_bug)-yellow` ✔
- `git show 226cd4a9:README.ko.md | sed -n 22p` → `122_CI_배선(119_통과_%2F_1_기지_앱버그)-yellow` ✔
- `git show 226cd4a9:docs/STATE.md | sed -n 32p` → `E2E 122 … **121 통과 / 1 skip** … CSP 가 자기 폰트를 차단하던 앱 결함까지 해소` ✔
- `git show 226cd4a9 --stat -- README.md README.ko.md` → 각 1줄 변경, diff 는 **Tests 배지 한 줄뿐**(6846→6849). E2E 배지 줄 무변경 ✔
- 산술 자기모순 119+1=120 ≠ 122 ✔

**그러나 관측 이후 HEAD 가 움직였고, 그 커밋이 정확히 이 건을 고쳤다**
`226cd4a9`(01:08)

### [docs] 운영 smoke 런북 §8.4 가 해소된 blocker 를 '사용자 결정 대기' 로 계속 가르친다

- **위치**: `docs/runbooks/operational-smoke-checks.md:209`
- **주장**: #1292 가 이 절을 `119 통과 / 1 실패 / 1 skip` + *"남은 1건 = CSP 앱 결함, 사용자 결정 대기 — backlog R52"* 로 갱신했는데, 그 다음 커밋(226cd4a9)이 R52 를 종결시키면서 이 런북은 동기화하지 않았다. 정책 13 의 SSOT 문서(CLAUDE.md 가 *"엔드포인트 기대값 SSOT"* 로 지정)가 이미 닫힌 결정을 열린 것으로 서술한다.
- **근거**: `docs/runbooks/operational-smoke-checks.md:209` = *"`#1291` 이 그중 29건을 해소해 현재 **119 통과 / 1 실패 / 1 skip** 이다"* · `:211` = *"**CSP 가 자기 폰트를 차단**하는 앱 결함을 잡고 있다(사용자 결정 대기 — backlog R52)"*. 반면 `docs/backlog.md:51` R52 상태 = `✅ 완료 (30 → **0**) — CSP 앱 버그까지 해소 (#1294)` · `docs/STATE.md:32` = `121 통과 / 1 skip`. 226cd4a9 의 변경 파일 목록에 이 런북 없음.
- **처방**: §8.4 인용 수치를 STATE:32 와 맞추고 '사용자 결정 대기' 문구를 제거한다. 이 문서는 #1292 도 손댄 곳이라, 같은 정수가 STATE·README×2·런북 4지점에 손유지되고 있다는 뜻 — R54 가 '5지점 손유지' 로 잡은 클래스가 E2E 축에서 그대로 재생산됐다.
- **판정**: `SEVERITY_ADJUST` — 실재하는 drift 다 — 인용 전건 실측 확인. `docs/runbooks/operational-smoke-checks.md:209` = *"현재 **119 통과 / 1 실패 / 1 skip** 이다"* · `:211` = *"…앱 결함을 잡고 있다(사용자 결정 대기 — backlog R52)"* (grep -n 실측, 줄번호 정확). 반면 `docs/backlog.md:51` = `R52 | ✅ 완료 (30 → 0) — CSP 앱 버그까지 해소 (#1294)`. 종결 커밋 `226cd4a9`("fix(ui): CSP 가 자기 폰트를 차단하던 죽은 링크 5개 제거 (R52 종결)") 의 `--stat` 변경 파일 8개(README×2·STATE·backlog·base.html·landing.html·test_csp_external_asset_parity.py·test_router.py)에 **이 런북 없음** — 근거 그대로 확인. `git merge-base --is-ancestor 226cd4a9 HEAD` = 참이고 런북 최신 커밋은 여전히 `d32d9da8`(#1292) 이라, 현재 워킹트리에서 살아 있는 drift 다. 즉 FALSE_POSITIV

### [docs] #1289 이 추가한 config.py field_validator 가 env-vars.md 에 반영되지 않았다 (CLAUDE.md:365 명시 의무)

- **위치**: `docs/reference/env-vars.md:28`
- **주장**: #1289(762e90ba)가 `claude_review_model`/`claude_insight_model` 에 '빈 문자열 = 미설정으로 취급' field_validator 를 추가했으나, CLAUDE.md 아키텍처 동기화 체크리스트가 명시적으로 요구하는 env-vars.md 행 동기화가 없다. 이 결함은 커밋 본문 스스로 *"단위 테스트는 env 를 안 읽으니 초록이고, 고장은 실 API 호출에서만 드러난다"* 고 적은 라이브-only 사고라, 문서가 유일한 전달 매체다.
- **근거**: `git diff 8f4ada5a..HEAD -- docs/reference/env-vars.md` = 1줄 변경뿐이며 그 줄은 `DISABLE_PROMPT_CACHE`(R38). `docs/reference/env-vars.md:28` = `| CLAUDE_REVIEW_MODEL | AI 코드리뷰에 사용할 Claude 모델 ID | claude-sonnet-4-6 (기본) |` · `:30` CLAUDE_INSIGHT_MODEL 동일하게 빈 값 동작 미기재. CLAUDE.md:365 = *"**+ `config.py` `field_validator`/최솟값 제약 추가·변경 시에도** env-vars.md 해당 행 설명·예시 동기화 의무 (사이클 119 P0-C/P1-D 재발 방지)"*. 부수: `.env.example:126` `CLAUDE_REVIEW_MODEL=` · `:135` `CLAUDE_INSIGHT_MODEL=` 이 사고를 낸 그 형상 그대로인데 주석 없음 — 반면 이웃 `:130` 은 `# ⚠️ int 필드 — 빈 값 금지(pydantic ValidationError)` 를 갖고 있어 같은 파일 안에서 규율이 비대칭이다.
- **처방**: env-vars.md 28/30 행에 '빈 값은 미설정으로 처리되어 기본값 폴백(#1289, 2026-08-05 라이브 사고)' 을 추가하고 `.env.example:126/135` 에도 대응 주석을 단다. 사이클 119 에서 같은 규칙이 이미 한 번 깨졌으므로, 이번엔 `config.py` validator 심볼 ↔ env-vars.md 행 존재를 대조하는 가드를 함께 두는 편이 낫다.
- **판정**: `SEVERITY_ADJUST` — 실재하는 규칙 미이행이나 심각도 과대 — P1 → P2.

[검증된 사실 — 인용 전건 일치]
· 762e90ba(#1289)가 src/config.py:214-234 에 `_blank_model_falls_back_to_default` field_validator 를 claude_review_model/claude_insight_model 에 추가한 것 확인.
· `git diff 8f4ada5a..HEAD -- docs/reference/env-vars.md` = 1줄 변경뿐이고 그 줄은 DISABLE_PROMPT_CACHE(R38). 모델 행 동기화 없음 — 사실.
· env-vars.md:28 = `| CLAUDE_REVIEW_MODEL | AI 코드리뷰에 사용할 Claude 모델 ID | claude-sonnet-4-6 (기본) |`, :30 = CLAUDE_INSIGHT_MODEL — 양쪽 다 빈 값 동작 미기재. 인용 정확.
· CLAUDE.md:365 = "+ `config.py` `field_validator`/최솟값 제약 추가·변경 시에도 env-vars.md 해당 행 설명·예시 동기화 의무" 문자 그대로 존재.
· .env.example:

### [docs] CLAUDE.md 안에서 rules 카테고리 수가 10 과 11 로 자기모순 (#1293 이 docs.md 추가 시 한 곳만 갱신)

- **위치**: `CLAUDE.md:402`
- **주장**: #1293 이 `.claude/rules/docs.md` 를 신설하며 CLAUDE.md:366 매트릭스를 `10 영역 → 11 영역` 으로, 표에 11번째 행을 추가했으나 같은 섹션 도입부(:402)의 `10 카테고리` 는 그대로다. 매 세션 강제 로드되는 문서 안에서 같은 사실이 두 값으로 존재한다.
- **근거**: `CLAUDE.md:402` = *"**사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 …"* · `CLAUDE.md:366` = *"11 영역 매트릭스: testing.md / … / docs.md"* · 표 `:406~416` 실제 11행(`ls .claude/rules/` = 11 파일). 동류 stale: `tests/unit/scripts/test_rules_and_index_coverage.py:15` 와 `:89` 는 아직 `9영역 매트릭스` 라고 적는다.
- **처방**: 402 줄을 11 로 정정하고 테스트 메시지의 '9영역' 도 함께 정리한다. 근본적으로는 산문 카운트를 지우고 '표 행 수 = `.claude/rules/*.md` 파일 수' 를 단언하는 기존 커버리지 가드로 위임하는 것이 drift 재발을 막는다(메모리 `feedback-prose-guard-both-ways` 의 클래스).
- **판정**: `CONFIRMED` — All citations verified verbatim. CLAUDE.md:402 reads "10 카테고리(2026-07-20 guards 추가)" while CLAUDE.md:366 in the same file reads "11 영역 매트릭스: testing.md / … / docs.md". Ground truth = 11: the table at :406~416 has exactly 11 rows (11th = "| 문서 / 원장 | .claude/rules/docs.md |") and `ls .claude/rules/` returns 11 files. So :402 is the sole wrong value.

Attribution confirmed: `git log --diff-filter=A -- .claude/rules/docs.md` → faeb2cf1 (#1293), and that commit's CLAUDE.md diff touches only line 366, leaving 402 untouched.

I specifically tested the strongest false-positive defense — that :402 is 

### [docs] STATE.md:22 가 존재하지 않는 '세션13 블록' 을 아래에 있다고 안내한다

- **위치**: `docs/STATE.md:22`
- **주장**: '직전' 블록 꼬리의 *"직전 세션13 블록은 아래 유지(체인 1단계)"* 가 거짓이다. 파일에 세션13 블록은 없다 — 과거 트리밍 때 블록만 지우고 그것을 가리키는 안내 문장이 남았다. 다음 세션이 체인 규칙을 판단할 때 잘못된 상태를 전제하게 된다.
- **근거**: `grep -n "세션13" docs/STATE.md` → 10, 13, 22 세 줄뿐이며 전부 본문 인용이고 `**직전 (… 세션13 …)**` 형식 블록은 없음. `grep -n "^\*\*최신 |^\*\*직전 |^\*\*종합 수치" docs/STATE.md` → 9(최신 세션15) · 22(직전 세션14) · 32(종합) 뿐.
- **처방**: 22 줄 꼬리 문구를 '그 이전은 cycle-history.md' 로 단순화한다. 블록 회전 시 안내 문장까지 함께 옮기는 것이 규칙 (2) 의 실제 이행 단위임을 규칙 본문에 1줄 반영.
- **판정**: `CONFIRMED` — 인용 실측 확인 — docs/STATE.md:22 는 현재도 존재하며 주장된 문장(`직전 세션13 블록은 아래 유지(체인 1단계, …)`)을 그대로 담고 있다. 주장도 실측 확인: `grep -n "세션13" docs/STATE.md` → 10·13·22 세 줄뿐이고 10/13 은 세션15 불릿 안 산문, 22 가 문제의 문장이다. `grep -nE "^\*\*(최신|직전|종합)"` → 9(최신 세션15)·22(직전 세션14)·32(종합) 뿐으로 세션13 블록은 파일에 없다. 문장은 거짓이다.

기전까지 git 으로 독립 확인했다(발견자는 주장만 했다): `git log -S "직전 세션13 블록은 아래 유지" -- docs/STATE.md` → 도입 커밋 `2cf7ba07`. `git show 2cf7ba07:docs/STATE.md` 시점에는 line 9 = `**최신 (… 세션14 …)** — 직전 세션13 블록은 아래 유지`, line 19 = 실제 `**직전 (… 세션13 …)**` 블록이 있어 **당시엔 참**이었다. 이후 세션13 서사는 `docs/cycle-history.md:169` 로 이관되고 세션14 가 최신→직전으로 강등됐는데, 꼬리 문

### [docs] STATE 의 'E2E 121 통과' 는 단일 실행이 낸 숫자가 아니다 — 두 커밋 전에 신설한 §측정 규율 위반

- **위치**: `docs/STATE.md:32`
- **주장**: STATE:32 는 `**121 통과 / 1 skip** — 🔴 로컬 실측` 이라고 적지만, 같은 커밋(226cd4a9)의 본문은 로컬 전체 실행이 `1 failed` 였고 그 1건은 단독 재실행 2회로 통과시켰다고 기록한다. 즉 121/0/1 을 낸 실행은 존재하지 않으며, 전체 실행 결과와 격리 재실행 결과를 합성한 값을 '실측' 으로 발행했다.
- **근거**: `docs/STATE.md:32` = `… **121 통과 / 1 skip** — 🔴 로컬 실측이며 CI(Linux) 확인은 …`. 226cd4a9 커밋 본문 §검증 = *"e2e (로컬 전체) → 1 failed → 그 1건은 perf 플레이크(단독 2회 통과), CSP 건은 통과"*. `AGENTS.md:110` = `## 🔴 측정 규율 — 도구가 낸 숫자를 사실로 발행하지 않는다` (2 커밋 전 #1293 이 신설, 적용 대상 = *"숫자나 판정을 내놓는 모든 것"*).
- **처방**: `120 통과 / 1 실패(perf 플레이크, 단독 재실행 2/2 통과) / 1 skip` 처럼 실행 단위를 보존해 적거나, 합성이면 합성임을 명시한다. 플레이크를 통과로 흡수하는 표기는 나중에 진짜 회귀가 같은 자리에 앉았을 때 구별 불가가 된다.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. (1) `git show 226cd4a9:docs/STATE.md` 32행 = `E2E 122 (110 표준 + 12 perf — CI 배선 완료(#1288) · **121 통과 / 1 skip** — 🔴 로컬 실측이며 CI(Linux) 확인은 …)` — 인용 문자열 그대로 존재. (2) 같은 커밋 본문 §검증 = `e2e (로컬 전체) → 1 failed → 그 1건은 perf 플레이크(단독 2회 통과), CSP 건은 통과` — 그대로 존재. (3) `AGENTS.md:110` = `## 🔴 측정 규율 — 도구가 낸 숫자를 사실로 발행하지 않는다`, 117행 `적용 대상은 **숫자나 판정을 내놓는 모든 것**`, `git show faeb2cf1 --stat -- AGENTS.md` 로 #1293 신설 확인(226cd4a9 의 직부모 — 클레임의 "두 커밋 전"은 HEAD 기준으로는 맞고 저술 시점으로는 1커밋 전, 무해한 오차).

핵심 주장 성립: 전체 실행은 1 failed 였고 그 1건은 격리 재실행으로 통과시킨 것이므로 121/0/1 을 낸 실행은 존재하지 않는다. 전체 실행 결과 + 격리 재실행 결과의 합성값을 '로컬 실측

### [docs] backlog 진입점 헤더가 세션15 인수인계에 고정 — 세션16 이 추가한 R49~R55 를 프레이밍하지 못한다

- **위치**: `docs/backlog.md:12`
- **주장**: backlog 는 스스로 *"이 파일부터 읽으면 된다"* 고 선언하는 진입 문서인데, 진입 섹션 제목이 여전히 `(2026-08-04 세션15 — 5+1 회고 이관)` 이고 본문도 세션15 회고 통계로 채워져 있다. 그 뒤 세션16 이 R49~R55 7건을 추가하고 R49·R50·R51·R52·R54 를 종결했지만 진입 서사는 그대로다 — 다음 세션이 가장 먼저 읽는 화면이 두 세션 전 상태를 그린다.
- **근거**: `docs/backlog.md:12` = `## ▶️ 다음 세션 시작점 (2026-08-04 세션15 — 5+1 회고 이관)` · `:14` = *"**이 파일부터 읽으면 된다.**"*. 현재 창 실측(awk 파싱): R35~R55 21행 중 ✅ 9(R35·R36·R37·R38·R49·R50·R51·R52·R54) · 🟡 11 · 🔴 1 — 이 중 R49~R55 는 전부 세션16 산물(#1279·#1286/#1289·#1291~#1294).
- **처방**: 진입 섹션을 세션16 종료 상태로 갱신한다. 참고로 상태 요약 카운트 자체는 정확했다(`:58` 의 21행/1/11/9 = 실측 일치) — `test_backlog_shape.py::test_status_summary_matches_the_table` 가 지키는 축은 살아 있고, 가드가 없는 서사 축만 늙었다는 점이 이번 창 전반의 패턴과 같다.
- **판정**: `CONFIRMED` — Citation exact: docs/backlog.md:12 = `## ▶️ 다음 세션 시작점 (2026-08-04 세션15 — 5+1 회고 이관)`, :14 = `**이 파일부터 읽으면 된다.**`. Claimed counts reproduce exactly (R35~R55 = 21행; ✅9 = R35·R36·R37·R38·R49·R50·R51·R52·R54 / 🟡11 = R39~R47·R53·R55 / 🔴1 = R48).

I initially tested the skeptical reading — that the parenthetical is a *provenance* label ("이 절은 세션15 회고에서 이관됨"), not a freshness stamp, which would make the finding a FALSE_POSITIVE. `git log -L 12,12:docs/backlog.md` refutes that: the parenthetical is re-stamped at every session boundary — 세션3 → 세션4 → 세션8 → 세션9 → 세션13 → 세션14 → 세션15, 7 consecutive rewrite

### [decision] 스스로 'Claude 가 임의 결정하지 않는다'고 선언한 High-tier 결정이 사용자 결정 인용 없이 ✅ 로 종결됐다

- **위치**: `docs/backlog.md:51`
- **주장**: backlog.md:51 (R52) 은 CSP 건에 대해 "고치는 방향이 보안 자세 변경 ↔ 시각 변경으로 갈리므로 정책 15 High tier(사전 확인) + 정책 11(시각 검증 불가)에 해당해 **Claude 가 임의 결정하지 않는다**" 라고 명시 기록했다. 그런데 같은 행이 `✅ 완료 … (#1294)` 로 닫혔고, 행 전체에 '사용자 결정' 문자열이 0회다. #1294 본문도 "㉰ 로 진행했습니다" 라고만 적을 뿐 (a) 사용자가 ㉰ 를 골랐다는 인용도 (b) 정책 9 완화(회신 부재 → 자율 판단 보고로 대체)를 원용한다는 선언도 없다. 바로 아래 R7 행(backlog.md:143)은 같은 형태의 결정을 `사용자 결정 ㉮ "빨간 채로 머지"` 로 인용해 기록했으므로, 이 리포에 결정 provenance 기록 관행이 이미 존재함에도 이 건만 빠진 것이다. 결과적으로 원장만 읽는 다음 세션은 '이 결정이 사용자 것인지 Claude 것인지' 를 판정할 수단이 없다. 완화 요인: #1294 는 아직 OPEN 이라 머지 게이트는 사용자가 보유한다.
- **근거**: `grep -no "임의 결정하지 않는다" docs/backlog.md` → `51:임의 결정하지 않는다`. `sed -n '51p' docs/backlog.md | grep -o "사용자 결정" | wc -l` → `0`. `grep -no "사용자 결정 ㉮" docs/backlog.md` → `143:사용자 결정 ㉮`. PR #1294 body 27행 `무해한 쪽은 ㉰ 였습니다. ㉰ 로 진행했습니다.` — 사용자 인용·정책 9 원용 없음. `gh pr view 1291 --json reviews` → `[]`, 사용자 코멘트 0건(봇 2건만).
- **처방**: (a) R52 행에 결정 provenance 1셀 추가 — `사용자 결정 ㉰` 인용 또는 `Claude 자율 판단(정책 9 완화 · 근거: 실측 시각 변화 0)` 중 사실인 쪽. (b) 규칙화: 원장 행에 '임의 결정하지 않는다' 류 High-tier 선언을 적었으면 그 행의 ✅ 플립은 `사용자 결정 …` 또는 `자율 판단(정책 9 완화)` 인용 셀 없이는 금지. R7 행이 이미 정본 형식을 보여준다.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 재현됨. grep -no "임의 결정하지 않는다" docs/backlog.md → 51 단일 히트(R52 행 내부), sed -n '51p' | grep -o "사용자 결정" | wc -l → 0, 같은 행이 `✅ 완료 … (#1294)` 로 종결. grep -no "사용자 결정" → 15히트 중 143행이 `사용자 결정 ㉮ "빨간 채로 머지"` 로 provenance 관행 존재 확인. PR #1294 body = `무해한 쪽은 ㉰ 였습니다. ㉰ 로 진행했습니다.` (사용자 인용·정책 9 원용 0). gh pr view 1291 --json reviews → [], 코멘트 작성자 = sonarqubecloud·codecov 봇 2건뿐. 추가로 원 근거보다 강한 사실 발견: #1291 body 106행이 `🔴 CSP 결정 — 아래 표에서 골라 주세요. 제가 정하지 않았습니다.` 이고 ★추천은 ㉮ 였는데 #1294 는 회신 없이 ㉰(비추천안)로 진행했으며 #1291 에 정책 9 사전 fallback 선언도 없다. 따라서 결함 자체는 실재 — CONFIRMED 축은 성립한다.

그러나 P1 을 지탱하는 harm 서술 두 축이 반증돼 심각도를 낮춘다. (

### [decision] 카덴스 트리거 발화 상태에서 이월 승인 기록 없이 세션 16 이 종료됐고 세션 17 이 4 PR 을 더 진행했다 (정책 8-(6))

- **위치**: `docs/runbooks/retro-cadence-deferrals.md:25`
- **주장**: 정책 8-(6)은 카덴스 트리거(≥15 머지 PR) 발화 상태에서 회고 미진입으로 세션 작업을 계속하려면 `retro-cadence-deferrals.md` 에 (a) 사용자 명시 이월 승인 인용 (b) 목표 진입 세션을 기록 의무로 규정한다. 머지 순서상 15번째가 #1288, 16번째가 #1290(세션16 종료 trailing sync)이므로 트리거는 세션 16 안에서 발화했다. 그런데 이월 원장의 마지막 행은 2026-08-02(21 PR)이고 그 이후 행이 없다 — 세션 16 은 회고에 진입하지도, 이월을 기록하지도 않고 #1290 으로 종료했다. 세션 17 은 시작 시 SessionStart 훅이 '🔴 카덴스 이월 승인 기록 없음' 을 loud 발화한 상태에서 #1291·#1292·#1293 을 머지하고 #1294 를 열었고, 그 뒤에야 회고에 진입했다. 정책이 명시한 대로 이 이월은 본 회고 §자성 명시 의무 대상이다.
- **근거**: `py -3 scripts/check_retro_cadence.py` → `🔴 회고 카덴스 트리거 발화 — … 머지 PR 19 건 (임계 ≥15)` + `🔴 카덴스 이월 승인 기록 없음 — 회고 진입이 default. 이월하려면 docs/runbooks/retro-cadence-deferrals.md 에 사용자 승인 인용 + 목표 세션 기록 의무 (정책 8 진화 (6))`. `docs/runbooks/retro-cadence-deferrals.md:25` = 마지막 행 `| 2026-08-02 | 21 (#1250~#1271) | …` (직전 정식 회고 2026-08-04 보다 이전 → 현 window 이월로 인정 안 됨). 머지 순서(oldest→newest): #1276,#1278,#1277,#1273,#1279,#1280,#1281,#1282,#1283,#1284,#1285,#1286,#1287,#1289,#1288(15번째),#1290(16번째),#1291,#1292,#1293.
- **처방**: 본 회고 보고서 §자성에 이 이월을 명시 기록한다(정책 8-(6) 후단 의무). 추가로 세션 종료 trailing sync PR 템플릿에 '카덴스 상태 1줄'(`check_retro_cadence` 출력 인용)을 고정 항목으로 넣어, 세션을 닫는 PR 이 트리거 발화를 관측면에 남기지 않고는 못 닫히게 한다 — 배너는 이미 3회 무시된 이력이 있고(R40), 부족한 것은 신호가 아니라 세션 종료 시점의 기록 강제다.
- **판정**: `SEVERITY_ADJUST` — 사실 핵심은 전량 재확인됨(실측). 다만 P1 를 지탱하는 두 축 중 하나가 원장 자기 규칙에 의해 무너지고, 나머지 하나는 기계적으로 관측 불가능했던 구간이라 P2 로 조정한다.

■ 재확인된 사실 (CONFIRMED 부분)
1. 인용 검증: `docs/runbooks/retro-cadence-deferrals.md:25` = 표 마지막 행 `| 2026-08-02 | 21 (#1250~#1271) | "현재 토큰량이 없습니다…" | 다음 세션 … |` — 존재·내용 일치. citation_verified=true.
2. `py -3 scripts/check_retro_cadence.py` 실행 = 주장된 두 loud 라인 그대로 재현(`직전 정식 회고 … 2026-08-04-retrospective.md` / `머지 PR 19 건 (임계 ≥15)` / `🔴 카덴스 이월 승인 기록 없음`).
3. 머지 순서 실측(`git log main`, KST): 회고 #1274(08-04 01:43) 이후 19건이 주장된 순서와 **완전 일치** — #1276,#1278,#1277,#1273,#1279,#1280,#1281,#1282,#1283,#1284,#1285,

### [decision] cryptography 메이저 범프(#1278)의 배포 후 토큰 복호 검증이 owed 원장에 등재되지 않아 집행 기전을 우회했다

- **위치**: `docs/runbooks/owed-verification.md:82`
- **주장**: #1278 은 cryptography 49.0.0 → 50.0.0 메이저 범프이고 본문 스스로 '`cryptography` 는 토큰 암호화(`src/crypto.py`) 경로에 쓰인다. 배포 후 GitHub 토큰 복호가 정상인지(리포 목록 로드) 확인 부탁드린다' 고 사용자 운영 검증을 요청했다. 이는 owed 원장이 정의한 '코드로 증명 불가한 운영 검증' 그 자체인데(원장 헤더: '세션/Phase 종료 시 코드-미증명 운영 검증을 남긴 PR 을 이 표에 추가한다'), 원장에 #1278 행이 0건이다. 따라서 SessionStart 훅의 미결 카운터가 이 항목을 영원히 못 본다 — 실제로 `check_owed_verification.py` 는 미결 4건(#1289 ×2, #1279, #1276)만 인쇄하고 #1278 은 없다. 이 건은 같은 세션의 #1287 본문에 '이전 대기분' 으로 한 번 언급됐다가 #1290(세션 종료 sync)에서 사라졌으므로, 추적면에서 완전히 증발했다. 위험 축이 특히 나쁘다 — 복호가 깨지면 GitHub 토큰 전건이 못 풀려 리포 접근 전체가 죽는데, 이는 owed 원장이 '안전등급' 으로 다루는 등급이다. 부수로 R47-(a)가 제안한 탐지 휴리스틱('코드로 증명 불가' 어휘)은 이 PR 본문에 그 어휘가 없어 잡지 못한다.
- **근거**: `grep -c "1278" docs/runbooks/owed-verification.md` → `0`. PR #1278 body 말미 `2. **런타임 회귀 없음** — \`cryptography\` 는 토큰 암호화(\`src/crypto.py\`) 경로에 쓰인다. 배포 후 GitHub 토큰 복호가 정상인지(리포 목록 로드) 확인 부탁드린다.` `py -3 scripts/check_owed_verification.py` → `owed 원장 — 안전등급 미결 0건 / 운영등급 미결 4건: #1289, #1289, #1279, #1276` (#1278 부재). PR #1287 body 36행 `2. 이전 대기분: \`#1278\` 배포 후 토큰 복호 · owed \`#1279\` …` → PR #1290 body 63~71행에는 없음. `docs/runbooks/owed-verification.md:82,83` = #1279·#1276 행(정상 등재 대조군).
- **처방**: (a) #1278 행을 owed 원장에 append 한다 — 재개/종결 조건은 '배포본에서 리포 목록 로드 1회 성공' 로 구체화(복호 실패 시 즉시 관측 가능). (b) R47-(a) 의 탐지 축을 어휘가 아니라 **행위**로 바꾼다: PR 본문 §'🔍 사용자 검증 필요' 에 '배포 후'·'운영'·'확인 부탁' 류 요청이 있는데 owed 원장 diff 가 0 이면 `::notice` — 어휘 기반은 이 PR 처럼 문구를 피한 요청을 원리적으로 못 잡는다.
- **판정**: `SEVERITY_ADJUST` — 사실 관계는 전건 재확인됨(P1 유지 불가는 심각도 축뿐). ① `grep -c "1278" docs/runbooks/owed-verification.md` → `0`, `git show origin/main:docs/runbooks/owed-verification.md | grep -c 1278` → `0` (stale checkout 아님, main 에서도 부재). ② PR #1278 body 말미 `2. **런타임 회귀 없음** — cryptography 는 토큰 암호화(src/crypto.py) 경로에 쓰인다. 배포 후 GitHub 토큰 복호가 정상인지(리포 목록 로드) 확인 부탁드린다.` 원문 일치. ③ `py -3 scripts/check_owed_verification.py` → `안전등급 미결 0건 / 운영등급 미결 4건: #1289, #1289, #1279, #1276` — #1278 부재. ④ #1287 body:36 에 `이전 대기분: #1278` 존재 / #1290 body 에 `1278` 0건 + `_archive` 제외 활성 문서 전체 grep 0건 = 추적면 증발 확정. ⑤ R47-(a) 휴리스틱 구멍도 확인 — #1278 본문에 

### [decision] 세션 종료 일괄 회신(#1290)이 미결 사용자 결정 6건 중 2건만 열거해 중간 sync(#1287)보다 후퇴했다

- **위치**: `docs/runbooks/owed-verification.md:83`
- **주장**: 정책 2 진화는 Phase/세션 종료 시 사용자 회신 항목의 일괄 묶음을 규정하고, 세션의 마지막 PR 은 사용자가 실제로 읽는 최종 목록이 된다. #1287(세션 16 중간 sync)은 §사용자 검증 필요에 '이전 대기분' 4건(#1278 배포 후 토큰 복호 · owed #1279 심의 게이트 품질 · required check 확대 범위 · R51 잔여 착수 여부)을 이월 열거했다. 그런데 세션을 닫는 #1290 은 #1289 발 신규 2건만 적고 '이번 PR 자체는 문서라 시각 검증 항목이 없고, 아래 2건은 #1289 에서 넘어온 운영 항목입니다' 로 범위를 좁혔다 — 이월 4건 중 R51 잔여만 #1289 로 해소됐고 나머지 3건(#1278 복호, owed #1279, required check 확대 범위)과 owed #1276 은 여전히 열린 채 최종 목록에서 사라졌다. 세션 종료 시점에 열린 사용자 항목 6건 중 2건만 제시된 셈이라, 이월 누락이 중간→종료 방향으로 역행했다.
- **근거**: PR #1287 body 33~36행 `## 🔍 사용자 검증 필요 (정책 2)` / `2. 이전 대기분: \`#1278\` 배포 후 토큰 복호 · owed \`#1279\` 심의 게이트 품질 · required check 확대 범위 · **R51 잔여 착수 여부**`. PR #1290 body 63~71행 `## 🔍 사용자 검증 필요 (정책 2)` / `퇴근 후 확인 부탁드립니다 — 이번 PR 자체는 문서라 시각 검증 항목이 없고, 아래 2건은 \`#1289\` 에서 넘어온 **운영** 항목입니다` + 항목 2개(CLAUDE_REVIEW_MODEL 실값 · AI 리뷰 품질). `check_owed_verification.py` 미결 = #1289 ×2, #1279, #1276(4건) + 원장 밖 #1278·required check 확대 범위 = 6건.
- **처방**: 세션 종료 trailing sync PR 의 §사용자 검증 필요를 손으로 적지 말고 `check_owed_verification.py` 출력을 그대로 붙이도록 고정한다(원장 밖 항목은 그 자체가 등재 누락 신호 — 위 P1 참조). 최종 목록이 중간 목록의 부분집합이 되는 것은 기계 산출로만 막을 수 있다.
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. #1287 body §사용자 검증 필요 = 'README 배지' + '이전 대기분 4건(#1278 토큰 복호 · owed #1279 · required check 확대 범위 · R51 잔여)' 축자 확인. #1290 body = '이번 PR 자체는 문서라 시각 검증 항목이 없고, 아래 2건은 #1289 에서 넘어온 운영 항목입니다(원장 등재 완료)' + 2건 축자 확인. owed-verification.md:83 = 열린 #1276 행(82 = #1279) 존재 확인. check_owed_verification.py 라이브 = 안전등급 0 / 운영등급 4건(#1289 x2, #1279, #1276).

단 주장 프레이밍은 과장 지점이 있다: (1) 6건 중 4건(#1289x2·#1279·#1276)은 owed 원장 등재분이고 .claude/settings.json:14 가 check_owed_verification.py 를 SessionStart 에 배선해 매 세션 기계 재표면화한다(직접 실행 확인) — '최종 목록에서 사라졌다'가 아니라 산문 채널에서만 빠진 것이고, #1290 의 '(원장 등재 완료)' 가 바로 그 SSOT 를 가리

### [decision] #1289 의 자율 결정(빈 env → 기본값 폴백)이 운영자 대면 계약 문서에 반영되지 않았다 — CLAUDE.md 명시 의무 위반

- **위치**: `docs/reference/env-vars.md:28`
- **주장**: #1289 는 `src/config.py` 에 `@field_validator("claude_review_model", "claude_insight_model", mode="before")` 를 추가해 '빈 환경변수를 미설정으로 취급' 하는 동작 변경을 자율 결정했다. CLAUDE.md 동기화 체크리스트는 '`config.py` `field_validator`/최솟값 제약 추가·변경 시에도 env-vars.md 해당 행 설명·예시 동기화 의무 (사이클 119 P0-C/P1-D 재발 방지)' 를 명시하는데, #1289 는 env-vars.md 를 건드리지 않았다(변경 7파일 전건이 src/tests). 결과로 `CLAUDE_REVIEW_MODEL`(env-vars.md:28)·`CLAUDE_INSIGHT_MODEL`(:30) 행은 여전히 '모델 ID' 만 설명하고 '빈 값은 기본값으로 되돌아간다' 는 새 계약을 말하지 않는다 — 바로 아래 :29 `CLAUDE_REVIEW_MAX_TOKENS` 행은 `제약 ge=1` 을 문서화하고 있어 같은 표 안에서 규율이 갈렸다. 결정 추적성 관점의 실질 피해: owed 원장에 '운영 CLAUDE_REVIEW_MODEL 실값 확인' 이 ⏳ 로 살아 있어 사용자가 바로 그 변수를 들여다볼 참인데, 참조 문서는 값을 비웠을 때 무슨 일이 일어나는지 알려주지 않는다.
- **근거**: `grep -n "field_validator" src/config.py` → `214:    @field_validator("claude_review_model", "claude_insight_model", mode="before")` (docstring 216~228행이 사고 경위 상세 기록). `git show --stat 762e90ba` 변경 파일 = src/analyzer/io/ai_review.py, src/analyzer/pure/review_prompt.py, src/config.py, src/services/dashboard_service.py, src/services/repo_insight_service.py, tests/unit/analyzer/io/test_ai_review.py, tests/unit/test_config.py — docs/reference/env-vars.md 없음. `docs/reference/env-vars.md:28` `| \`CLAUDE_REVIEW_MODEL\` | AI 코드리뷰에 사용할 Claude 모델 ID | \`claude-sonnet-4-6\` (기본) |` · `:30` CLAUDE_INSIGHT_MODEL 행 동일 · 대조군 `:29` 는 `(제약 \`ge=1\`)` 명시.
- **처방**: env-vars.md:28·30 행에 '빈 문자열로 설정하면 미설정으로 취급돼 기본값으로 되돌아간다(`config.py` `_blank_model_falls_back_to_default`)' 1구 추가. 회귀 가드 후보: `config.py` 의 `field_validator` 대상 필드명 집합을 추출해 env-vars.md 해당 행에 제약 서술 토큰이 있는지 대조 — 이 클래스는 사이클 119 에 이어 2회차 재발이라 산문 의무만으로는 안 잡힌다.
- **판정**: `CONFIRMED` — 전 인용 실측 재확인 — 전건 일치. (1) `src/config.py:214` `@field_validator("claude_review_model", "claude_insight_model", mode="before")` 존재(docstring 216~228 사고 경위). (2) `git show --stat --format="" 762e90ba` = 7파일 전건 src/tests, docs 0건. (3) `docs/reference/env-vars.md:28`·`:30` 은 여전히 '모델 ID' 만 설명, 대조군 `:29` 는 `(제약 ge=1)` 명시 — 같은 표 내 규율 분기 실재. (4) `CLAUDE.md:365` 의무 문구가 문자 그대로 적용 대상('config.py field_validator/최솟값 제약 추가·변경 시에도 env-vars.md 해당 행 설명·예시 동기화 의무'). (5) `docs/runbooks/owed-verification.md:76` ⏳ 항목 실재.

'이미 해소' 반증 시도 실패: `git log 762e90ba..HEAD -- docs/reference/env-vars.md` = 빈 출력 — 이후 어떤 커밋도 이 

### [decision] 정책 11 의 8조합 시각 검증 체크리스트를 Claude 가 1~2 조합으로 자율 축소했다 (템플릿 2파일 변경 PR)

- **위치**: `src/templates/base.html:16`
- **주장**: 정책 11 은 `src/templates/**` 변경 PR 에 '본문 최상단 8 조합(4테마 × 모바일/데스크탑) 체크리스트' 를 의무화하고 '본 섹션 누락 후 테스트 통과만 적기' 를 금지한다. #1294 는 `src/templates/base.html`·`landing.html` 두 파일을 고쳤는데, 8조합 체크리스트가 없고 본문 **최하단** §사용자 검증 필요에서 '4테마 × 모바일/데스크탑 중 **한두 조합만이라도** 봐 주시면 충분합니다' 로 범위를 자율 축소했다. 축소 근거(Playwright 실측 computed style 동일 · 등록 폰트 0 동일)는 실측이라 무근거는 아니고 '저는 시각 검증을 할 수 없습니다' 명시 의무는 지켰다 — 그래서 P2 다. 다만 축소 판단의 주체가 정책이 명시적으로 사용자 몫이라 못박은 축이라는 점, 그리고 축소 사유가 '검증받아야 할 주장(시각 변화 0)' 자체라는 점에서 형태가 순환에 가깝다.
- **근거**: `git show --stat HEAD` → `src/templates/base.html | 22 ++++--` · `src/templates/landing.html | 8 +--`. PR #1294 body 68~72행 `## 🔍 사용자 검증 필요 (정책 2 · 정책 11)` / `1. **화면이 이전과 똑같은지** 확인 부탁드립니다. 제 주장은 "시각 변화 0" 이고 … **저는 시각 검증을 할 수 없습니다**(정책 11). 4테마 × 모바일/데스크탑 중 **한두 조합만이라도** 봐 주시면 충분합니다.` — 본문 최상단 8조합 체크박스 표 없음(본문 1~67행에 부재).
- **처방**: 체크리스트는 8행 그대로 두되 각 행 옆에 '실측 근거: computed font-family 동일' 을 병기해 사용자가 **어디를 덜 봐도 되는지 스스로 판단**하게 한다 — 항목 수를 Claude 가 줄이는 것과 근거를 붙여 우선순위를 제시하는 것은 다르다. 정책 11 이 금지하는 것은 후자가 아니라 전자다.
- **판정**: `CONFIRMED` — CONFIRMED at the claimed P2. All checkable elements verified independently. (1) Trigger: `git show --stat 226cd4a9` confirms `src/templates/base.html | 22 ++++--` and `src/templates/landing.html | 8 +--`; policy 11's trigger is file-path based (`src/templates/*.html`, CLAUDE.md:223) and unconditional. (2) Absence: live `gh pr view 1294 --json body` returns ZERO `[ ]` checkboxes and ZERO pastel/catppuccin mentions across the whole body — the 8-combination checklist (active.md:78-100 template) is definitively absent, not merely misplaced. (3) Reduction: body line 71 verbatim `4테마 × 모바일/데스크탑 중 **

### [process] '세션16 종료' 선언 후에도 같은 세션 라벨로 4 PR 이 계속돼 종료 시점 의무가 재실행 지점을 잃었다

- **위치**: `docs/STATE.md:285`
- **주장**: #1290 이 '세션16 종료 trailing sync' 로 사이클 종료 신호를 냈으나, 이후 #1291~#1294 가 계속 머지/생성됐고 STATE.md 는 그중 2건을 '세션16 6차/7차' 로 같은 세션에 기록한다. 종료 시점에만 걸려 있는 의무들(정책 2 owed 일괄 회신 · 정책 8 카덴스 판정 · 6-step ⑤ 서사 로테이션)이 한 번 실행된 뒤 재실행 지점이 사라졌다.
- **근거**: cb2d9657 `docs(state): 세션16 종료 trailing sync — 6832 + R7 종결 + R52 신설 (#1288·#1289) (#1290)` (2026-08-05 08:32). 이후 5b72c438(#1291, 21:42)·d32d9da8(#1292, 21:54)·faeb2cf1(#1293, 08-06 00:31) 머지 + #1294 OPEN. docs/STATE.md:285 `**세션16 6차 — 문서 감사 P0~P2 (#1293)**`, :286 `**세션16 7차 — … (#1294)**` — 종료 선언 이후 PR 들이 동일 세션 번호로 기록됨.
- **처방**: '종료' 어휘를 쓴 trailing sync 이후 추가 작업이 발생하면 (a) 세션 번호를 증가시켜 새 창을 열거나 (b) 종료 선언을 철회하는 1줄을 STATE 에 남기도록 규칙화. 종료 시점 의무 4종(정책 2/5/8/⑤)은 '종료 선언 PR' 이 아니라 **세션의 마지막 머지 PR** 기준으로 재판정.
- **판정**: `SEVERITY_ADJUST` — 인용 사실은 전건 실측 일치. docs/STATE.md:285 = `- **세션16 6차 — 문서 감사 P0~P2 (#1293) +14**`, :286 = `세션16 7차 … (#1294)` 정확 매치. cb2d9657 제목에 `세션16 종료 trailing sync` (2026-08-05 08:32:25) 실재하고, 이후 5b72c438(#1291, 21:42)·d32d9da8(#1292, 21:54)·faeb2cf1(#1293, 08-06 00:31) 머지 + #1294 in-flight 도 실재. 따라서 citation_verified=true 이고 "종료 선언 후 4 PR 지속" 이라는 관측 자체는 사실이다.

그러나 P1 근거인 "종료 시점 의무가 재실행 지점을 잃었다" 는 명시된 3 의무 중 2건이 직접 증거로 반증된다.

(1) 정책 8 카덴스 판정 — 상실 안 됨. `scripts/check_retro_cadence.py` 는 `_RETRO_NAME`(`*retrospective*.md`) 최신 파일 이후 squash-merge PR 을 `count_merge_prs` 로 세고 SessionStart 훅으로 발화한다. `세션N 종료` 라벨에 대

### [process] 카덴스 breach 상태로 세션을 '닫는' 경로에는 기록 의무가 없어 16→19 PR 이월이 무흔적으로 넘어갔다

- **위치**: `scripts/check_retro_cadence.py:26`
- **주장**: 이월 원장의 의무 조건이 '회고 미진입으로 세션 작업을 **계속**하려면' 으로만 쓰여 있어, breach 상태에서 세션을 종료하는 경로는 아무 기록도 요구하지 않는다. 원장이 막으려던 것이 바로 그 크로스세션 이월인데 가장 흔한 경로가 열려 있다.
- **근거**: scripts/check_retro_cadence.py:26 `RETRO_PR_THRESHOLD = 15`, :144 `breached = pr_count >= threshold`. #1290 머지 시점 직전 정식 회고(#1274, 2026-08-04) 이후 머지 PR = #1275~#1290 = **16건** = breach. 그런데 #1290 본문 grep `카덴스|회고|retro` → 0건. docs/runbooks/retro-cadence-deferrals.md 마지막 행은 :25 `| 2026-08-02 | 21 (#1250~#1271) | …` 로 현 window 행 없음. 이후 창에서 #1291~#1293 3건이 더 머지된 뒤(현재 `py -3 scripts/check_retro_cadence.py` → "머지 PR 19 건 … 🔴 카덴스 이월 승인 기록 없음") 회고에 진입했다. 원장 헤더가 스스로 적은 근본 — "advisory 배너는 3세션 연속(15→57 PR, 3.8배) 무시돼 부채를 재생산했다" — 와 같은 형태의 반복.
- **처방**: 의무 트리거를 '계속' 에서 '**breach 상태에서의 세션 종료 또는 추가 머지**' 로 확장. 실행 배선: trailing sync PR body 에 §카덴스 상태 1줄(breach N / 회고 진입 여부 / 원장 행 유무) 필수 섹션 추가하고, `docs/STATE.md` 를 터치하는 PR 에서 pre_push_gate 가 `check_retro_cadence.py` 출력을 인쇄(비차단).
- **판정**: `SEVERITY_ADJUST` — 인용 4개 전부 실측 일치, 관측 사실도 전부 재현됨 — 그러나 주장된 **근본("기록 의무가 없다")은 반증**되고, 실제 근본은 이 파일이 이미 미봉인으로 적어 둔 한계다. 실제 결과도 "무흔적"이 아니다 → P1 → P2.

[실측 확인 — 전부 참]
- `scripts/check_retro_cadence.py:26` `RETRO_PR_THRESHOLD = 15` · `:144` `breached = pr_count >= threshold` 축자 일치.
- 경계 커밋 `8f4ada5`(#1274, 2026-08-04 회고) 이후 머지 PR 을 `git log --format=%s | grep '(#N)$'` 로 세면 #1290 머지 시점 = **정확히 16건** (#1276·#1278·#1277·#1273 → #1279 … #1290). breach 맞음.
- #1290 본문 2,466자에 `카덴스/회고/retro/cadence/이월` **0회** (gh 로 본문 받아 UTF-8 로 카운트). 원장 마지막 행은 `:25` 2026-08-02 로 현 window 행 없음.
- 현재 `py -3 scripts/check_retro_cadence.py` → 

### [process] 14개월 결함을 허용한 규칙 문구가 `<script src>` 만 금지하는데, 시정 PR 이 규칙을 넓히지 않았다

- **위치**: `.claude/rules/security.md:48`
- **주장**: security.md 의 외부 CDN 금지 규칙이 `<script src="...">` 로만 좁게 쓰여 있어, 실제 결함 클래스인 `<link rel=stylesheet>` + `preconnect` 는 문언상 금지되지 않았다. #1294 는 `src/templates/**` 를 변경했으면서 ui.md·security.md 어느 쪽도 갱신하지 않아, 테스트 가드는 생겼지만 다음 편집자가 자동 로드로 읽는 규칙 문구는 여전히 결함을 허용한다(CLAUDE.md 아키텍처 동기화 체크리스트의 `.claude/rules/<area>.md` 행 미이행).
- **근거**: .claude/rules/security.md:48 `… CSP와 충돌하는 외부 CDN 링크(`<script src="...">`) 추가 금지 — `src/static/vendor/` 로컬 vendoring 우선.` — stylesheet/font 링크 미언급. `.claude/rules/ui.md` 는 grep `CSP|CDN|외부 폰트` → CDN vendoring 서술은 Chart.js 건(:38)뿐, CSP 제약 0건. #1294 파일 목록에 `.claude/rules/*` 없음(변경 파일 = ci.yml, README×2, STATE.md, backlog.md, base.html, landing.html, 테스트 2). 실제 결함은 base.html 의 스타일시트 2 + preconnect 3.
- **처방**: security.md:48 문구를 `<script src>`→`외부 출처 하위자원 전반(<script src>·<link rel=stylesheet>·preconnect/preload·@font-face src·<img src>)` 으로 확장하고 ui.md 에 1줄 포인터(`템플릿에 외부 출처 링크 추가 금지 — 가드 tests/unit/ui/test_csp_external_asset_parity.py`) 추가. 규칙 문구가 결함 클래스를 못 덮은 사례는 '가드 추가' 로 종결 처리하지 말고 **문구 폭 검토** 를 동반 의무화.
- **판정**: `SEVERITY_ADJUST` — 실체는 있으나 P1 은 과대. 인용 3건 모두 실측 재확인: (a) `.claude/rules/security.md:48` 에 `CSP와 충돌하는 외부 CDN 링크(`<script src=\"...\">`) 추가 금지` 문구 존재, stylesheet/preconnect 미언급 (b) `.claude/rules/ui.md` grep `CSP|style-src|preconnect` → 0 hits (Chart.js vendoring `:38` 뿐) (c) #1294(`226cd4a9`) 변경 파일 8건 = README×2·STATE.md·backlog.md·base.html·landing.html·test_csp_external_asset_parity.py·test_router.py — `.claude/rules/*` 없음. CLAUDE.md 체크리스트의 `.claude/rules/<area>.md` 행(`src/templates/**` → ui.md 매칭) 미이행은 사실.

그러나 P1 을 지탱하는 세 전제가 실측으로 깨진다.

① 인과 서사가 거짓 — `git log -S` 실측: 폰트 링크 `2026-05-01`(#150) 도입, security.md 규

### [process] 정책 11 시각 검증 요청은 추적면이 전혀 없다 — 운영 축만 원장·loud 카운터를 갖는 비대칭

- **위치**: `scripts/check_owed_verification.py:24`
- **주장**: '사용자만 할 수 있는 검증' 은 운영등급과 시각(정책 11) 두 종류인데, 운영 축만 owed 원장 + SessionStart loud 카운터를 갖고 시각 축은 머지되는 순간 PR 본문과 함께 관측면에서 사라진다. 정책 11 의 '누적 8조합 단일 회신 표' 는 산문 의무일 뿐 기계 신호가 없다 — 이 리포에서 산문-only 기전이 실패한 전례(카덴스 2회)와 같은 형태다.
- **근거**: docs/runbooks/owed-verification.md 의 ⏳ 14행 전부 운영등급(태그 열 `13`·`2·13`·`2·13·16`), 시각/정책 11 태그 행 0건. scripts/check_owed_verification.py:24 `_LEDGER = Path("docs/runbooks/owed-verification.md")` — 단일 원장. 반면 #1291 §2("폰트가 지금 실제로 어떻게 보이는지 확인 부탁")·#1294 §1(4테마×모바일/데스크탑 시각 동일성) 은 어디에도 등재되지 않는다. #1291 의 시각 질문은 실제로 회신되지 않은 채 Claude 자신의 측정(#1294)으로 대체됐다.
- **처방**: owed 원장에 `등급` 열 값 `시각` 을 신설하고 정책 11 §8조합 요청을 PR 머지 시 1행씩 등재(운영등급과 동일 append-only). 안전등급처럼 loud 는 아니고 카운트 보고 수준이면 정책 17 안정성과 양립한다.
- **판정**: `CONFIRMED` — 인용 재확인 완료. scripts/check_owed_verification.py:24 = `_LEDGER = Path("docs/runbooks/owed-verification.md")` 문자 그대로 일치(단일 원장, 대체 추적면 없음). 원장 데이터 행 12건의 정책 태그 전수 = 5·13 / 15 / 5·14 / 5·12 / 13 / 2·13·16 / 13 / 13 / 13 / 13 / 2·13 / 2·13 — 정책 11 태그 0건, '시각' 어휘 0건. 주장의 핵심(시각 축 기계 추적면 부재)은 실측으로 성립.

보강 증거 2건(발견자가 갖지 않았던 것, 주장을 강화): (1) #1291·#1294 양쪽 모두 정책 11 템플릿을 아예 쓰지 않았다 — `^\s*- \[ \]` 0건, `catppuccin|pastel` 0건. #1294 는 base.html·landing.html 을 고쳐 정책 11 적용 대상인데도 그렇다. 따라서 backlog R0-2 의 처방("미체크 `- [ ]` 를 단 채 머지된 PR 열거")이 구현돼 있었어도 이 두 건은 **탐지 못 했다** — 요청이 체크박스가 아니라 산문이었기 때문. 즉 기존 등재 항목(R0-2·R28·R4

### [code] 빈 env 가 기본값을 덮는 사고의 수정이 필드 2개 한정 — 같은 형태의 `openai_verifier_model` 은 그대로 열려 있고 클래스 가드가 없다

- **위치**: `src/config.py:214`
- **주장**: #1289 가 "이 **클래스**가 위험한 이유" 라고 클래스로 진단해 놓고, 시정은 `claude_review_model`·`claude_insight_model` 두 필드에만 적용하고 테스트도 그 두 필드를 리터럴로 단언했다. 동일 형태(비어 있지 않은 기본값을 가진 str 설정)인 `openai_verifier_model` 은 미보호이고, **앞으로 추가되는 필드도 아무것도 막지 않는다**. 이 리포는 같은 클래스를 이미 `smtp_port` 에서 한 번 개별 시정한 전례가 있다 — 3회차 ad-hoc 이다.
- **근거**: `src/config.py:214-216` 의 `@field_validator("claude_review_model", "claude_insight_model", mode="before")` 는 두 필드만 등록한다. 미보호 동형 필드: `src/config.py:25 openai_verifier_model: str = "gpt-5-mini"`(소비처 `src/gate/merge_verifier.py:210` — 빈 값이면 2nd-LLM 검증이 `VERIFIER_API_ERROR` 로 fail-closed 돼 경계 밴드 auto-merge 가 영구 차단된다), `src/config.py:161 default_locale="en"` · `:165 supported_locales="en,ko,ja"` · `:169 locale_fallback="en"` · `:172 i18n_translations_dir="src/i18n/translations"`. 동일 클래스의 과거 개별 시정 = `src/config.py::coerce_smtp_port`(docstring: "Railway에서 SMTP_PORT=\"\"(빈 문자열)로 설정된 경우"). 신규 테스트 `tests/unit/test_config.py::test_blank_model_env_falls_back_to_default` 는 두 필드를 손으로 나열할 뿐이라 신규 필드를 잡지 못한다.
- **처방**: 필드 열거 대신 **클래스 가드**로 승격: `Settings.model_fields` 를 순회해 `annotation is str and default not in ("", None)` 인 필드 전부를 validator 대상으로 자동 등록하거나(또는 최소한 그 집합이 validator 등록 집합과 일치함을 단언하는 테스트를 두고), 신규 필드가 추가되면 red 가 되게 한다. 지금 즉시 `openai_verifier_model` 을 validator 에 포함시킬 것.
- **판정**: `CONFIRMED` — CONFIRMED at P2 (severity unchanged). All citations verified: src/config.py:214 registers exactly `@field_validator("claude_review_model", "claude_insight_model", mode="before")`; openai_verifier_model at :25; merge_verifier.py:210 consumes it; coerce_smtp_port at :280 with the Railway blank-string docstring; test at tests/unit/test_config.py:568 hardcodes both field names. (Only nit: i18n_translations_dir is :173, not :172.)

The structural core holds and is the reason this is a real finding: the fix's OWN docstring diagnoses the defect as a class ("이 클래스가 위험한 이유" — a blank env var reads as "

### [code] 신규 CSP 정합 가드의 검사 범위가 자기 기계 장치보다 좁다 — 정확히 같은 위반이 `src/static/mockup-polar.html` 에 남아 공개 서빙 중

- **위치**: `tests/unit/ui/test_csp_external_asset_parity.py:29`
- **주장**: R52 종결 PR 이 만든 재발 가드는 `src/templates/**` 의 `rel="stylesheet"` 만 본다. 그런데 (a) 제거한 것과 **글자 그대로 같은** jsDelivr Pretendard 링크가 `src/static/mockup-polar.html` 에 남아 있고 그 파일은 `/static` 마운트로 **인증 없이 공개 서빙**된다. (b) 가드는 `script-src`/`font-src` 를 읽는 기계 장치(`_csp_allows_external`)를 갖추고도 그 두 축을 **아무 데서도 강제하지 않는다** — 외부 `<script src>` 나 CSS `@font-face url(https://…)` 는 다음에 들어와도 통과한다.
- **근거**: `tests/unit/ui/test_csp_external_asset_parity.py:29` `_TEMPLATES = _ROOT/"src"/"templates"` + `:56` `_TEMPLATES.rglob("*.html")` — `src/static/**` 미포함. `:33-36` `_EXTERNAL_STYLESHEET` 정규식은 `rel="stylesheet"` 만 매칭. `:83-90` `test_csp_directives_are_actually_read` 가 `font-src` 를 읽지만 그 값을 쓰는 검사가 없고, `_CSP_DIRECTIVE`(`:37`)가 파싱하는 `script-src` 도 소비처 0. 잔존 위반: `src/static/mockup-polar.html:7-8` (`<link rel="preconnect" href="https://cdn.jsdelivr.net">` + `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/…">`). 공개 서빙 근거: `src/main.py:361-362` `if _STATIC_DIR.exists(): app.mount("/static", CachedStaticFiles(...))`. 이 목업은 `git log` 상 2026-05-10 `efefa623` 이후 미변경이고 `docs/architecture.md:25` 가 "대시보드 KPI 레이아웃 목업" 으로 등재한 개발 산출물이다.
- **처방**: 스캔 범위를 `src/templates/**` + `src/static/**/*.html` 로 넓히고, 이미 읽고 있는 `script-src`(외부 `<script src>`)·`font-src`(CSS `@font-face` 의 `url(https://…)`) 축도 같은 방식으로 강제한다. 범위 확대로 즉시 red 가 되는 `mockup-polar.html` 은 삭제하거나 `src/static/` 밖(예: `docs/design/`)으로 옮긴다 — 공개 경로에 둘 이유가 없다.
- **판정**: `CONFIRMED` — 모든 인용이 실측으로 확인됐고, 반증 시도도 실패했다. (1) 범위 협소 실재: test_csp_external_asset_parity.py:29 `_TEMPLATES = _ROOT/"src"/"templates"` + :56 `_TEMPLATES.rglob("*.html")` — `src/static/**` 미포함. 다른 rglob 스캐너(i18n test:38, check_lint_js_nonvacuous.py:105)도 전부 templates 한정이라 대체 가드 0. (2) 잔존 위반 실재 + 주장보다 강함: src/static/mockup-polar.html:7-8 의 jsDelivr Pretendard URL 은 R52(226cd4a9)가 템플릿에서 제거한 것과 URL 바이트 동일(템플릿 사본만 `crossorigin="anonymous"` 보유 — 사소한 차이). 공개 서빙은 main.py:360-362 `app.mount("/static", ...)` 인증 의존성 0 으로 확인되고, 나아가 SecurityHeadersMiddleware 가 main.py:294 에서 app 전역 등록이라 그 응답에도 동일 CSP(main.py:90-97 `styl

### [code] tailwind 번들 부재 시정이 CI 에만 적용 — `make test-e2e`/`make run` 은 이번 오진의 원인이던 로컬↔CI 비대칭을 그대로 보존

- **위치**: `Makefile:157`
- **주장**: `d82192fd` 는 *"한 테스트에 두 원인이 겹쳐 구별이 불가능했다 … 로컬에는 산출물이 있어 CSP 만 보였고, CI 에는 둘 다 있었다. 이 비대칭이 진단을 흐렸다"* 라고 근본원인을 비대칭으로 지목하고서, 시정은 **CI job 에만** 넣었다. 로컬 러너는 여전히 gitignore 된 빌드 산출물을 보장하지 않으므로, 새 clone 에서 `make install` → `make test-e2e` 를 하면 `test_dashboard_no_js_runtime_errors` 가 결정론적으로 red 가 되고 그것이 회귀인지 셋업 누락인지 또 구별되지 않는다.
- **근거**: `.github/workflows/ci.yml:501-502` 에 `npm ci --ignore-scripts && npm run build` 추가. 반면 `Makefile:5-7` `install: pip install -r requirements-dev.txt` + `npm install`(빌드 없음), `Makefile:157 test-e2e: python -m pytest e2e/ -v -p no:asyncio`(css-build 선행 없음, `--timeout` 없음 — CI 는 `--timeout=120`), `Makefile:141 run: uvicorn …`(빌드 없음). 산출물은 `.gitignore:87 src/static/css/dist/tailwind.css` 이고 `src/templates/base.html:39` 가 무조건 링크한다. 동일 함정은 `docs/cycle-history.md:360`(#1224)에 이미 *"새 clone 은 그 경로가 404 인 상태로 서버가 뜬다"* 로 기록돼 있었고, 문서(`README.md:343-345`, `docs/runbooks/new-machine-setup.md:18`)만으로 2회째 재발했다.
- **처방**: `test-e2e`/`test-e2e-headed`/`test-perf`/`run` 을 `css-build` 에 의존시키거나(`test-e2e: css-build`), 최소한 `e2e/conftest.py` 의 `live_server` fixture 진입부에서 `src/static/css/dist/tailwind.css` 부재를 **loud-fail**(skip 아님) 시킬 것 — 문서-only 방어가 이미 한 번 실패한 클래스다(정책 8 진화 (4) 와 같은 논리). `make test-e2e` 에 `--timeout=120` 도 CI 와 맞춘다.
- **판정**: `CONFIRMED` — 실측 결과 주장 성립. (1) `Makefile:157 test-e2e: python -m pytest e2e/ -v -p no:asyncio` = css-build 선행 없음·`--timeout` 없음(CI 는 `ci.yml:546` 에서 `--timeout=120`) — 인용 정확. `Makefile:141-142 run: uvicorn` 빌드 없음 — 정확. (2) `Makefile:5-7 install:` = `pip install -r requirements-dev.txt` + `npm install` 뿐. 여기에 finding 이 놓친 **가중 사유**가 있다 — `Makefile:3-4` 주석이 "개발 환경 — 테스트/E2E + **CSS 빌드 포함** / includes tests/E2E + CSS build" 라고 명시하는데 `package.json` 에 `postinstall`/`prepare` 가 **없다**(scripts = build·dev:css·lint:js). 즉 Makefile 이 제공하지 않는 보장을 **적극적으로 단언**하고 있어 `README.md:342` 와도 모순 — 침묵보다 나쁜 형태. (3) 기계 가드 부재 실측: 

### [code] `corrupted()` docstring 이 실측과 어긋난 기전을 기록 — `_scrub_surrogates` 는 U+FFFD 가 아니라 `?` 를 만들고, 검사-먼저 순서를 고정하는 테스트가 없다

- **위치**: `.claude/hooks/doc_review_gate.py:431`
- **주장**: 손상 감지의 정당화 근거가 사실과 다르다. docstring 은 *"JSON 의 `\uD800` 형태 이스케이프는 … 서로게이트로 남고, **나중에 `_scrub_surrogates` 가 U+FFFD 로 바꾼다**"* 라고 적었지만, 실제로 그 함수는 lone surrogate 를 `?`(U+003F)로 바꾼다. 현재 동작이 옳은 유일한 이유는 `corrupted(diff)` 가 scrub **앞**에서 호출되기 때문인데, 그 순서를 고정하는 테스트가 없다. `read_payload` docstring(:819)이 *"`_scrub_surrogates` 는 증상을 지웠다. 원인은 이 디코드였다"* 라며 상류 정화를 시사하고 있어, 상류로 옮기는 리팩터가 자연스럽게 유도된다 — 그러면 DEGRADED 배너가 영구 침묵하고 **전 테스트가 초록**이다.
- **근거**: 실측: `py -3 -c "print(repr('A\ud800B'.encode('utf-8',errors='replace').decode('utf-8')))"` → `'A?B'`, 코드포인트 `['0x41','0x3f','0x42']` (U+FFFD 아님). 해당 구현 = `.claude/hooks/doc_review_gate.py:390` `return text.encode("utf-8", errors="replace").decode("utf-8")`. 잘못된 서술 = 같은 파일 `:431-434`. 현재 순서 = `:886 if corrupted(diff):` (main) vs `:541-543 _scrub_surrogates(...)` (`_call_single_agent` 내부). 순서 가드 부재 = `tests/unit/hooks/test_doc_review_gate.py:179-182` 가 `corrupted()` 술어만 단독 검증하고 호출 순서/DEGRADED 발화를 단언하지 않는다.
- **처방**: (a) docstring 을 실측대로 정정(`?` 치환) 하거나 `_scrub_surrogates` 를 `errors="backslashreplace"`/명시적 U+FFFD 치환으로 바꿔 기록과 코드를 일치시킨다. (b) "lone surrogate 가 든 payload 를 stdin 으로 넣으면 DEGRADED advisory 가 나온다" 는 **엔드투엔드** 테스트를 추가하고, scrub 을 상류(`read_payload`)로 옮기는 뮤테이션이 red 가 되는지 실측할 것.
- **판정**: `CONFIRMED` — 양쪽 구성요소 모두 실측 확인. (1) 서술 오류 확정: `py -3` 실측 `'A\ud800B'.encode('utf-8',errors='replace').decode('utf-8')` → `'A?B'`, 코드포인트 `['0x41','0x3f','0x42']`, `has U+FFFD: False`. 인코딩측 `errors="replace"` 는 `?`(U+003F)를 내고 U+FFFD 는 디코딩측에서만 나온다. 따라서 `:433` 의 "나중에 `_scrub_surrogates` 가 U+FFFD 로 바꾼다" 는 거짓이며, 이 오류는 방향성이 나쁘다 — 이 서술을 믿으면 "어차피 나중에 U+FFFD 가 되니 U+FFFD 검사가 잡는다 → 순서 무관" 으로 추론되지만, 실제로는 `?` 가 되어 `corrupted()` 가 **영원히** 탐지하지 못한다. (2) 순서 가드 부재 확정 — 주장이 아니라 뮤테이션으로 증명: `:886` `if corrupted(diff):` 바로 위에 `diff = _scrub_surrogates(diff)` 삽입(= `:819` docstring 이 유도하는 바로 그 상류 이동 리팩터) 후 `pytest tests/unit/hook

### [docs] STATE.md 헤더 날짜가 자기 절차 (0)을 6회 연속 어기고 2026-08-04 에 고착 — 08-05/06 실측이 08-04 기준으로 제시된다

- **위치**: `docs/STATE.md:5`
- **주장**: SSOT 파일 헤더의 '기준일' 이 본문 내용보다 이틀 과거다. 이 필드는 회고가 이미 한 번 잡아 절차 (0)으로 승격시킨 항목인데, 직전 3세션은 지키다가 세션16 에서 전건 회귀했다.
- **근거**: `docs/STATE.md:5` = `## 현재 수치 (2026-08-04 기준)`. 같은 파일 `:32` 는 `(#1294, **2026-08-06**)`, `:285`~`:286` 은 `collect-only 실측 **2026-08-06**` 을 적는다. `docs/STATE.md:7` 규칙 = *"(0) **본 섹션 날짜 헤더(line 5 `## 현재 수치 (YYYY-MM-DD 기준)`)를 최신 세션 날짜로 갱신** (회고 2026-07-03 C5 #60 — **절차에서 상시 누락되던 필드**)"*. `git log -L 5,5:docs/STATE.md` 실측: `cae41e11`(#1259, 07-31→08-01) ✔ · `2cf7ba07`(#1272, 08-01→08-02) ✔ · `8f4ada5a`(#1274, 08-02→08-04) ✔ — 그 뒤 STATE 를 건드린 #1281·#1283·#1287·#1290·#1293·`2478c416` **6건 전부 미갱신**. 오독 위험은 같은 파일 `:45` 가 스스로 경고한 형태다(*"🔴 헤더 날짜가 최신이라 현재값으로 오독되기 쉬워 시점을 명시한다"*) — 지금은 반대 방향으로 어긋나 08-06 실측이 08-04 스냅샷으로 읽힌다.
- **처방**: 헤더를 `2026-08-06` 으로 갱신. 근본 시정: `check_docs_sync.py` 에 헤더 날짜 ↔ STATE 최신 mtime/최근 커밋 날짜 대조를 advisory 로 추가하거나, `--fix` 파생 대상에 헤더 날짜를 포함한다. 손유지 3회 성공 뒤 6회 연속 실패 = 규범만으로는 이 필드가 안 지켜진다는 실측 근거.
- **판정**: `SEVERITY_ADJUST` — 결함은 실재한다(FP 아님). 인용 5개 file:line 전건 실측 일치 — `docs/STATE.md:5` = `## 현재 수치 (2026-08-04 기준)`, `:7` 규칙 (0) 원문, `:32` = `0 실패**(`#1294`, 2026-08-06)`, `:285`~`:286` = `collect-only 실측 2026-08-06`, `:45` 자기 경고. `git log -L 5,5:docs/STATE.md` 도 cae41e11→2cf7ba07→8f4ada5a 3연속 갱신 후 중단으로 일치. 오늘(2026-08-06) 기준 헤더는 이틀 과거다.

다만 커밋 열거가 실측과 어긋난다. `git log --date=short -- docs/STATE.md` 결과 8f4ada5a 이후 STATE touch 는 6건이 아니라 10건이고, 주장이 든 #1281(f9d5906d)·#1283(dd6d1aef)은 **2026-08-04 당일 커밋**이라 당시 헤더 08-04 가 정확했다(위반 아님, 오귀속). 실제 위반은 08-05 4건(#1284 a04c6acb·#1287 09ddb4c4·#1290 cb2d9657·#1292 d32d9da8) + 08-06 3건

### [docs] E2E 초록 배지가 정적 하드코딩 + non-required job + 가드 0 — R7 '지켜지지 않는 초록' 이 새 축에서 재생산됐다

- **위치**: `README.md:22`
- **주장**: `2478c416` 은 *"검증 전에 초록으로 적었으면 R7 의 원죄를 재생산했을 것"* 이라며 CI 실측 후 초록으로 올렸지만, 그 초록은 (a) 정적 숫자이고 (b) 이를 지키는 required check 도 (c) 배지-현실 대조 가드도 없다. 회귀 시 배지는 초록으로 남는다.
- **근거**: `README.md:22`/`README.ko.md:22` = shields.io **정적** 배지 `E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen` (라이브 `actions/workflows/ci.yml/badge.svg` 인 `:14`·`:15` 와 성격이 다르다). `.github/workflows/ci.yml:498-499` = *"🔴 **required check 로 승격하지 않았다** — 실행 이력이 없어 flakiness 를 모른다"* → e2e job 이 red 여도 머지는 막히지 않는다. 가드 실측: `grep -n "E2E-" scripts/check_docs_sync.py scripts/check_test_count_sync.py tests/unit/scripts/test_repo_integrity_checks.py` = **0 hit**. 이 조합이 이론이 아님은 같은 창이 증명했다 — 배지가 초록으로 올라간 바로 그 커밋(`2478c416`, 3파일 3줄)이 `docs/STATE.md:38` 을 122 로 남겼고 두 가드 모두 초록을 인쇄했다(finding 1).
- **처방**: 둘 중 하나를 택한다: ㉮ e2e job 을 required check 로 승격(안정성 데이터 확보 후, ci.yml:499 의 원 계획) — 그러면 초록이 기계로 지켜진다. ㉯ 승격 전까지는 배지를 *라이브* workflow badge 로 바꾸거나 색을 낮춘다(`121_in_CI_(non-blocking)`). 어느 쪽이든 finding 1 의 E2E 축 가드를 함께 넣어 '배지 숫자 ↔ 실 collect' 대조를 기계화한다. 정적 초록 + non-required + 가드 0 삼중 결합은 R7 정의 그대로다.
- **판정**: `SEVERITY_ADJUST` — 실체는 있다(모든 인용 실측 확인). README.md:22 / README.ko.md:22 = 정적 shields.io `E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen` (라이브 badge.svg 인 :14/:15 와 성격 상이) · ci.yml:499 = "required check 로 승격하지 않았다" 문자 그대로 존재 · `grep -n "E2E-" scripts/check_docs_sync.py scripts/check_test_count_sync.py tests/unit/scripts/test_repo_integrity_checks.py` = 0 hit. 게다가 비대칭이 결정적이다 — check_docs_sync.py:41 은 형제 배지에 대해 `_README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\(...")` 를 이미 갖고 FastAPI 배지까지 대조하는데 E2E 만 빠졌고, check_test_count_sync.py 는 단위+통합 스코프라 E2E 를 원리적으로 못 본다. `2478c416` diff 도 주장대로다(3파일 3줄, yellow/122 → brightgr

### [docs] testing.md 가 'perf 는 CI 미실행' 이라 서술하나 신설 e2e job 이 perf 11건을 전부 돌린다 — e2e/** 규칙 미동기(R43 라이브 재발)

- **위치**: `.claude/rules/testing.md:30`
- **주장**: `e2e/**` 를 관할하는 path-scoped rule 이 `#1288`(CI 배선)·`#1291`(스위트 30건 재작성)·`#1294` 어느 것으로도 갱신되지 않아, 지금은 CI 실행 형태를 잘못 안내한다. backlog R43(*"rules sync 의무 발화율 ~100% · 실이행률 0%"*)의 관측 가능한 재발 사례.
- **근거**: `.claude/rules/testing.md:5` = `- "e2e/**"`(paths). `:30` = *"**`@pytest.mark.perf` 선택 실행**: `make test-perf` … 일반 E2E(`make test-e2e`)와 분리 실행 — **CI `testpaths=tests`에 포함되지 않음(자동 격리)**"*. 그러나 `.github/workflows/ci.yml:546` = `run: python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` — 마커 필터가 없어 perf 11건 포함 121건 전량 실행(실측 `-m perf` = 11/121). CI 실측 120 pass / 1 skip 이 그 121 이다. rules 파일 최종 수정 = `c7503620`(#1286, 2026-08-05, 구조화 출력) — e2e 축과 무관. `#1288`(02b3e867) stat = `ci.yml` 단독, `#1291`(5b72c438) stat = e2e 12파일 + `settings.html`, 양쪽 다 `.claude/rules/**` touch 0.
- **처방**: testing.md:30 을 *"단위 스위트(`testpaths=tests`)에는 포함되지 않지만, 전용 `e2e` job 이 `pytest e2e/` 로 perf 포함 전량 실행한다"* 로 정정하고, perf 가 공유 러너에서 타이밍 임계를 단언한다는 flakiness 리스크를 1줄 남긴다(ci.yml:498 의 승격 보류 판단과 직결). e2e job 을 required 로 올릴 계획이면 `-m "not perf"` 분리 여부를 그때 결정.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. (1) `.claude/rules/testing.md:5` = `- "e2e/**"` — 이 rule 이 e2e 축을 관할함이 frontmatter 로 확정. (2) `:30` 본문 = "일반 E2E(make test-e2e)와 분리 실행 — CI `testpaths=tests`에 포함되지 않음(자동 격리)". (3) `.github/workflows/ci.yml:546` = `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` — 마커 필터 없음. 독립 실측: `pytest e2e/ --collect-only` = 121건, `-m perf` = 11/121(110 deselected, 마커 11개 전부 `e2e/test_performance.py`). 즉 CI 가 perf 11건을 매 실행 태운다.

회의적 반증 시도 2건 모두 실패: (a) **"조건부 job 아닌가"** — ci.yml:501 `e2e:` job 은 `needs: secret-scan` 만 있고 `if:` 게이트가 없어 push/PR 매회 실행(라벨·수동 트리거 아님). (b) **"문장이 literal 로는 

### [docs] ci.yml 이 '건수를 박지 마라' 고 적은 두 줄 아래에서 주석 2곳에 122 를 박았고 이미 거짓

- **위치**: `.github/workflows/ci.yml:507`
- **주장**: 동일 파일 안에서 원칙 선언과 그 위반이 5줄 간격으로 공존한다. 박힌 숫자는 `#1291` 의 중복 제거로 이미 121 이 됐다.
- **근거**: `.github/workflows/ci.yml:502-503` = *"# 잡 이름에 건수를 박지 않는다 — 스위트가 늘면 이름이 조용히 거짓이 된다. / # No count in the job name: it silently goes stale as the suite grows."*. 같은 파일 `:490` = *"backlog R7 해소: **122건**이 '로컬 전용' 으로…"*, `:507` = *"# 실측 ~10초/건 → **122건** ≈ 20분. 여유 포함 30분에서 자른다."*. 실측 collect = **121**. `:490` 은 배선 시점 사실 기록으로 볼 여지가 있으나 `:507` 은 현재 타임아웃 산정 근거라 현재값이어야 한다.
- **처방**: `:507` 을 건수 비의존 서술로 바꾼다(예: *"실측 ~10초/건 · 현행 스위트 ≈ 9분 — 여유 포함 30분"*). `:490` 은 배선 시점 기록임이 드러나게 `(#1288 시점 122건)` 처럼 시점을 명시한다. 원칙(502-503)을 주석에도 적용하는 것이 일관적이다.
- **판정**: `CONFIRMED` — 인용 3곳 모두 HEAD 에서 문자 단위로 재확인됐고, 핵심 사실 주장(122 는 이미 거짓)이 실측으로 성립한다.

**인용 검증 (`.github/workflows/ci.yml`, `awk NR` 실측)**
- `:502-503` = *"# 잡 이름에 건수를 박지 않는다 — 스위트가 늘면 이름이 조용히 거짓이 된다. / # No count in the job name: it silently goes stale as the suite grows."* — 원문 일치
- `:507` = *"# 실측 ~10초/건 → 122건 ≈ 20분. 여유 포함 30분에서 자른다."* — 원문 일치, `:508 timeout-minutes: 30` 바로 위
- `:490` = R7 배선 서사 안의 122 — 원문 일치. `grep -n '122|121'` 결과 122 는 490·507 **2곳뿐**, 121 은 **0곳**.

**사실 주장 검증 (추측 아님, 실측)**
- `py -3 -m pytest e2e/ --collect-only -q -p no:asyncio` → **`121 tests collected`**. 교차 산술도 일치: `def test_` 113개 + 

### [docs] CLAUDE.md 가 같은 섹션에서 rules 영역 수를 10 과 11 로 동시에 주장

- **위치**: `CLAUDE.md:402`
- **주장**: `#1293` 이 11번째 rules 파일(`docs.md`)을 추가하며 매트릭스(:366)와 표(:416)는 갱신했으나 표 바로 위 도입 문장의 카운트를 놓쳤다. 매 세션 로드되는 파일의 자기모순이다.
- **근거**: `CLAUDE.md:402` = *"**사이클 85 정리**: **10 카테고리**(2026-07-20 guards 추가) 본문은 `.claude/rules/<area>.md` 로 분리…"*. 바로 아래 표 실측 = `awk 'NR>=405 && NR<=416' CLAUDE.md | grep -c "^| "` → **11**행(`:406` testing … `:415` guards … `:416` 문서/원장 docs.md). 같은 파일 `:366` 은 *"**11 영역** 매트릭스"* 로 이미 11 을 쓴다. 디스크 실측 `ls .claude/rules/` = 11개 파일(api·db·deploy·docs·guards·i18n·pipeline·security·services·testing·ui).
- **처방**: `:402` 을 *"11 카테고리(2026-07-20 guards · 2026-08-06 docs 추가)"* 로 정정. 저비용 회귀 가드: repo-integrity 에 `.claude/rules/*.md` 파일 수 ↔ CLAUDE.md 표 행 수 ↔ `:366`/`:402` 산문 카운트 3자 대조 1건 추가(이미 `test_repo_integrity_checks.py` 에 동형 산술 가드가 있다).
- **판정**: `CONFIRMED` — CONFIRMED — every cited fact reproduced verbatim on `main`, and the strongest skeptical counter-reading was tested and killed.

VERIFICATION (all against `git show main:CLAUDE.md`, since the working tree is on in-flight branch `docs/claude-md-under-200` where the file was condensed 423→195 lines and line numbers shift):
1. `CLAUDE.md:402` = "**사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 `.claude/rules/<area>.md` 로 분리…" — exact match to the quoted evidence.
2. Table below it: `awk 'NR>=406 && NR<=416' | grep -c "^| "` → **11** rows (`:406` testing … `:415` guards … `:416` 문서/원장 → `.claude/ru

### [decision] owed 원장의 등재 대상 정의가 운영/외부 축뿐이라 정책 11 시각 검증은 원장에 한 번도 오른 적이 없다 — 사용자 전용 검증인데 추적면이 없다

- **위치**: `docs/runbooks/owed-verification.md:3`
- **주장**: docs/runbooks/owed-verification.md:3 은 등재 대상을 *"HSTS 헤더·쿠키 Secure·cron 실제 실행·외부 API 계약·DELETE 실행·이메일 실제 발송 등"* 으로 열거한다 — 전부 운영/외부 축이고 **UI 시각 검증 축이 없다**. 그 결과 원장 11행 중 UI/시각 항목은 0건이다(`grep "시각"` → 무관 1히트). 그런데 정책 11 은 4테마 × 모바일/데스크탑 8조합 시각 정합성을 *사용자 의무* 로 규정하므로, 정의상 owed 원장이 다루는 것과 **완전히 같은 성격**(코드로 증명 불가 + 사용자만 판정 가능)이다. 이번 창에서 #1291 과 #1294 가 둘 다 *"저는 시각 검증을 할 수 없습니다(정책 11)"* 를 본문에 적었지만 어느 쪽도 원장 등재 경로가 없다 — 즉 시각 확인 요청은 PR 본문에서만 살다가 머지와 함께 소멸한다(회고 2026-07-18 P1#13 이 owed 원장을 만들게 한 바로 그 실패 모드). R47-(a)(원장 intake 172 PR 0건)와 뿌리는 같으나 축이 다르다 — R47 은 '적지 않았다', 이건 **'적어야 하는지 판정 기준이 없다'**.
- **근거**: docs/runbooks/owed-verification.md:3 (목적 열거에 시각 축 없음) · 같은 파일 §거짓 안전등급 경고 방지의 신규행 자문 2문항도 운영 전제/운영 위험 축뿐 · 원장 표 전체 행(#1058·#1062·#1104·#1106·#1071·#1072·#1073·#1075·#1279·#1276·#1289×2) 중 UI/시각 0 · PR #1294 본문 70-72행 *"저는 시각 검증을 할 수 없습니다(정책 11). 4테마 × 모바일/데스크탑 중 한두 조합만이라도"* · PR #1291 본문 117-118행 폰트 실제 렌더 확인 요청 · CLAUDE.md 정책 11
- **처방**: 원장 §목적 열거에 **정책 11 시각 검증 축을 명시 추가**하거나, 명시적으로 제외한다면 그 사유와 대체 추적면(예: PR 라벨 + Phase 종료 일괄 표)을 같은 자리에 적는다. 등급은 '운영/외부 계약' 이 아니라 별도 **'시각/UX 등급'**(Phase 종료 일괄 회신, 안전등급 아님 — SessionStart loud 경고 피로 방지)이 적절하다. 판정 기준: 템플릿/CSS/신규 시각 컴포넌트를 건드리고 본문에 정책 11 문구를 쓴 PR = 등재.
- **판정**: `CONFIRMED` — 근거 전건 실측 일치. (1) owed-verification.md:3 의 등재 대상 열거는 HSTS·쿠키 Secure·cron 실행·외부 API 계약·DELETE·이메일 발송으로 **전부 운영/외부 축**이고, 문서 제목 자체가 "미결 **운영** 검증 원장(Owed **Operational** Verification Ledger)" 로 스코프돼 있다. (2) 원장 데이터 행 12건 중 UI/시각 0건 — `grep -nE "테마|모바일|데스크탑|8 ?조합|정책 11|UI"` **0 히트**, `grep 시각` 1히트는 :81 의 "예정 시각 20:00"(무관). (3) :70 §거짓 안전등급 경고 방지의 신규행 자문 2문항도 (a) 선행 조건이 **운영**에 갖춰졌는가(env·설정 실측) (b) 미검증이 실제 위험을 만드는가(비활성 기능이면 0) 로 운영 전제 축뿐. (4) PR #1294 body **:71** = *"저는 시각 검증을 할 수 없습니다(정책 11). 4테마 × 모바일/데스크탑 중"*, PR #1291(MERGED) body **:117** = *"폰트가 지금 실제로 어떻게 보이는지 확인 부탁드립니다"* — 인용 라인 ±1 내 일치. (5

### [tooling] 심의 게이트 거부권 매트릭스가 2026-08-01 스코프 확대 이후 재도출되지 않았다 — impact 는 필수 절차 문서를 강등 경로 없이 hard-deny 한다

- **위치**: `.claude/hooks/doc_review_gate.py:191`
- **주장**: 거부권 매트릭스에서 `impact` 는 **모든 심의 등급을 차단**한다(`:191-193`). 이 설계가 쓰인 시점(`c3f35ded`)의 `important` 는 design/guides/superpowers/README 뿐이었다. 그런데 `5dfab6bf`(2026-08-01, `#1265`)가 `important` 를 **필수 절차 산출물**로 확대했다 — `docs/architecture.md`(6-step ⑥ 의무) · `docs/backlog.md`(R 원장, 매 PR 편집) · `docs/runbooks/*` · `docs/reference/*`(env-vars 등재 의무) · `.claude/plans/*`. **매트릭스는 그 확대와 함께 재도출되지 않았다.** 결과: Haiku 판정 하나로 6-step ⑥ / R-원장 플립 / env-vars 등재 편집이 deny 될 수 있고, R37-b 가 정확히 그 사고(*"게이트가 6-step ⑤ STATE 동기화를 block"*)를 막으려고 넣은 `unable_to_verify` 강등은 **`consistency` 의 `critical` 경로에만** 걸려 있다(`:194`). 더 나아가 `result_schema` 는 `impact` 에 그 필드를 **주지도 않는다**(`:418-419`) — 즉 impact block 에는 강등 경로가 원리적으로 존재하지 않는다.
- **근거**: `grep -n` 실측: `:191` `if agent == "impact":` → `:193` `block_reasons.append(...)` (등급 무관) / `:194` `elif agent == "consistency" and grade == "critical" and r.get("unable_to_verify") is not True:` / `:418-419` `if agent == "consistency": props["unable_to_verify"] = {"type": "boolean"}`. 확대된 `important` 패턴: `:58` `^docs/runbooks/[^/]+\.md$` · `:59` `^docs/architecture\.md$` · `:60` `^docs/backlog\.md$` · `:62` `^docs/reference/[^/]+\.md$` · `:65` `^\.claude/plans/[^/]+\.md$`. 등급 라우팅: `:862-864` `grade in ("skip","low_risk")` 만 조기 exit → critical·important 둘 다 3 에이전트 호출. 현행 동작이 테스트로 고정돼 있음: `tests/unit/hooks/test_doc_review_gate.py:443` `test_impact_blocks_important`. impact 프롬프트의 block 휴리스틱(`.claude/agents/doc-impact-analyzer.md`: *"규칙 삭제 → 높은 위험"*, *"의무 변경 필수→권장 → 높은 위험"*)은 backlog R항목 ✅ 플립(행 삭제)·env-vars 행 제거 같은 **정상 절차**에서 그대로 발화하는 형태다. 매트릭스가 스코프 확대보다 앞섰다는 근거: `git log -S'if agent == "impact"'` → 최초 `c3f35ded`; 스코프 확대 = `5dfab6bf`(2026-08-01).
- **처방**: 확대된 표면에 맞춰 매트릭스를 재도출한다. 최소 조치 = `important` 등급에서 impact block 을 warn 으로 강등(critical 에서만 hard-deny 유지) — R37 이 consistency 에 적용한 것과 같은 논리. 또는 `result_schema` 에 `impact` 용 `unable_to_verify` 를 추가하고 `.claude/agents/doc-impact-analyzer.md` 계약에 명시해 '근거를 못 봐서 낸 block' 을 강등한다. 어느 쪽이든 회귀 가드는 `docs/architecture.md`·`docs/backlog.md` 를 파라미터로 넣어 **필수 절차 문서가 deny 되지 않음**을 단언할 것.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 일치 — `doc_review_gate.py:191-193`(impact = 등급 무관 block) · `:194`(강등은 consistency+critical 한정) · `:418-419`(스키마가 `unable_to_verify` 를 consistency 에만 부여 + `additionalProperties: False`+전필드 required → impact 은 원리적으로 그 필드를 낼 수 없음) · `:922-925`(block → `permissionDecision: "deny"` 실제 hard deny, settings.json matcher `Write|Edit|MultiEdit`) · `_IMPORTANT` 확대 `:57-70` = `5dfab6bf`(2026-08-01, #1265) · impact 매트릭스 줄 최종 변경 = `c3f35ded`/`cf528902`(2026-04-26) · `:862-863` important 도 3 에이전트 호출 · `tests/unit/hooks/test_doc_review_gate.py:443`. 게다가 finding 이 못 본 보강 증거: `call_agents_parallel(grade

### [tooling] `--timeout 의무` 를 CI 한쪽에만 적용했다 — 문서가 처방하는 로컬 `make test-e2e` 는 여전히 무제한

- **위치**: `Makefile:158`
- **주장**: `d82192fd` 직전 `#1288` 이 e2e job 에 `--timeout=120` 을 넣으며 주석으로 *"`--timeout` 의무 — 이 잡에만 없었다. 셀렉터가 죽으면 … 원인 없이 죽는다"* 라고 못박았다. 그런데 그 '의무' 는 **CI 호출면에만** 적용됐다. 문서가 처방하는 로컬 호출면(`make test-e2e`)에는 timeout 이 없고, `e2e/pytest.ini` 에도 기본 timeout 설정이 없다 — 즉 CI 가 결함이라 부른 그 형태가 로컬에 그대로 남았다. 형제 타깃 `test-perf` 는 `--timeout=120` 을 이미 갖고 있어 같은 파일 안에서도 비대칭이다.
- **근거**: `Makefile:157-158` `test-e2e:` / `\tpython -m pytest e2e/ -v -p no:asyncio` (timeout 없음). `Makefile:162-163` `test-e2e-headed:` 동일하게 없음. 대조군 `Makefile:167-168` `test-perf:` / `python -m pytest e2e/ -m perf -v --timeout=120 -p no:asyncio` — **있다**. CI 측 `ci.yml:546` `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` + `:542-544` 의무 선언 주석. `e2e/pytest.ini` 전문 확인 — `timeout` 키 없음(`pythonpath` · `markers` 만). 추가로 `docs/STATE.md:38` 이 E2E 실행 명령으로 `make test-e2e` 를 명시하는데 이 머신에는 `make` 자체가 없다(backlog R29 기록).
- **처방**: `e2e/pytest.ini` 에 `timeout = 120` 을 넣어 **호출면 무관하게** 상한이 걸리게 한다(Makefile 3 타깃 개별 수정보다 drift 내성이 높다). CI 의 명시 `--timeout=120` 은 유지(계약 가시성). 겸해서 `docs/STATE.md:38` 의 `make test-e2e` 처방에 make 비의존 대체 명령(`py -3 -m pytest e2e/ -p no:asyncio`)을 병기.
- **판정**: `CONFIRMED` — 모든 인용 실측 일치. Makefile:157-158 `test-e2e:` / `python -m pytest e2e/ -v -p no:asyncio` — `--timeout` 없음. Makefile:162-163 `test-e2e-headed:` 동일하게 없음. 대조군 Makefile:167-168 `test-perf:` 는 `--timeout=120` 보유 → 같은 파일 내 비대칭 사실. ci.yml:546 `--timeout=120` + :542-544 "의무" 선언 주석 확인. e2e/pytest.ini 전문 확인 — `pythonpath`·`markers` 만, timeout 키 없음. docs/STATE.md:38 이 `make test-e2e` 명시하는 것도 확인(추가로 README.md:444 · README.ko.md:502 · CONTRIBUTING.md:99 · docs/runbooks/operational-smoke-checks.md:195 · docs/agents-index.md:56 — 문서 처방면 6곳).

회의적 반증 시도(결정적): 루트 pytest.ini:6 에 `addopts = --timeout=30` 이 존재해 e2e 도

### [tooling] pre_push_gate 자기 범위 서술이 7종 — 실제 9종이고 CLAUDE.md·guards.md 는 9종이라 적는다

- **위치**: `scripts/pre_push_gate.py:20`
- **주장**: 이 스크립트의 존재 이유가 *"덮는 것 / 덮지 못하는 것 (정직 기준)"* 을 명시하는 것인데, 그 정직 서술 자체가 틀렸다. `:20` 이 현재형으로 "repo-integrity stdlib 가드 **7종**" 이라 적지만 실제 목록은 **9종**이고, 같은 사실을 참조하는 다른 두 문서는 9종이라 적어 3지점 중 원본만 어긋난 상태다. `#1268`(R16·R17)이 `check_lint_js_nonvacuous.py` 를, `bcbd289d` 가 `check_test_count_sync.py` 를 추가하며 목록만 늘리고 docstring 을 갱신하지 않은 형태.
- **근거**: 실목록 카운트: `scripts/pre_push_gate.py:57-68` `_INTEGRITY` = check_docs_sync · check_toc_anchors · check_architecture_tree_sync · check_guard_fail_open · check_env_vars_sync · check_config_5way_sync · check_claim_review_trace · check_lint_js_nonvacuous = **8** + `:75-77` `_INTEGRITY_WITH_ARGS` = check_test_count_sync = **1** → 합 **9**. 어긋난 서술 = `scripts/pre_push_gate.py:20` "· repo-integrity stdlib 가드 7종 (whole-repo 상태)". 대조군 = `CLAUDE.md:352` "**repo-integrity 9종 + PR-diff 한정 4종**" · `.claude/rules/guards.md:208` "CI 가 강제하는 repo-integrity 9종 + PR-diff 한정 4종".
- **처방**: `:20` 을 9종으로 정정(`:12` 는 `make gate` 당시 상태를 서술하는 과거 서사이므로 시점 명시만 보강). 재발 방지로 `test_pre_push_gate.py` 에 docstring 의 숫자를 `len(_INTEGRITY) + len(_INTEGRITY_WITH_ARGS)` 와 대조하는 단언 추가 — 단 `.claude/rules/guards.md` 의 '기대값을 피검사 모듈에서 유도하지 말 것' 규칙에 따라 기대 숫자는 테스트에 리터럴로 고정하고 양쪽을 각각 대조할 것.
- **판정**: `CONFIRMED` — 결함 자체는 실재한다 (HEAD 에서 라이브). 실측: `scripts/pre_push_gate.py:20` 이 현재형으로 "repo-integrity stdlib 가드 **7종**" 이라 적지만, `_INTEGRITY`(:57-68) 8종 + `_INTEGRITY_WITH_ARGS`(:75-77) 1종 = **9종**이고 `run_integrity()`(:153-161)가 두 튜플을 **모두 실행**한다. 대조군도 확인 — `.claude/rules/guards.md:208` "repo-integrity 9종" ✓. 자기 커버리지를 "정직 기준" 이라 선언한 파일의 그 서술이 자기 코드와 어긋난 형태이므로 CONFIRMED.

다만 근거의 **두 지점이 실측과 다르다**(판정은 뒤집지 않되 기록 정정 의무):
(1) 🔴 **기전 서술이 틀렸다.** "#1268 이 check_lint_js_nonvacuous 를, bcbd289d 가 check_test_count_sync 를 추가하며 목록만 늘리고 docstring 미갱신" = 사실 아님. `git log -S ... -- scripts/pre_push_gate.py` 결과 **둘 다 d1cf608d(#12

### [process] '세션' 이 기계 정의되지 않아 owed 원장 intake 가 '재개' 선언 직후 다시 끊겼다 — 카운터는 그래서 초록

- **위치**: `docs/runbooks/owed-verification.md:1`
- **주장**: ⑤ trailing sync · owed 원장 intake('세션 종료 시 이 원장 갱신') · 정책 5 Phase-종료 cross-reference 세 의무가 모두 '세션 종료' 를 기점으로 삼는데 그것을 정의하는 기계가 없고, 손으로 적는 라벨은 이미 자기모순이다(#1290 이 '세션16 종료' 인데 그 뒤 2026-08-06 자 '세션16 6/7/8차' 항목이 STATE 에 계속 붙었다). 그 결과 #1291~#1294 4건이 전부 🔍 사용자 검증 필요 섹션을 달았는데도 원장 intake 0건이고, 카운터는 '안전등급 미결 0건' 초록을 인쇄한다 — 갚을 것이 없어서가 아니라 아무것도 받지 않아서 초록이다.
- **근거**: #1290 제목 = *"docs(state): 세션16 종료 trailing sync"* (머지 2026-08-04T23:32:26Z) 인데 docs/STATE.md:285-287 에 *"세션16 6차 … 2026-08-06"* · *"세션16 7차"* · *"세션16 8차"* 가 이어진다. `grep -n "129[0-4]" docs/runbooks/owed-verification.md` = 무결과(원장 행 12건, 최신 #1289). `py -3 scripts/check_owed_verification.py` = *"안전등급 미결 0건 / 운영등급 미결 4건: #1289, #1289, #1279, #1276"*. #1291 본문:104 · #1294 본문 §🔍 = 둘 다 *"제가 시각 검증 불가"* 명시. #1277(7202ec30)이 *"owed intake 재개"* 를 선언한 지 2일 만의 재발이고, R47-(a)(docs/backlog.md:43)가 이미 *"빈 원장 = green"* 으로 이 형태를 적어 뒀다.
- **처방**: '세션' 을 기계 정의하지 못하면 트리거를 PR 단위로 내린다 — 본문에 §🔍 사용자 검증 필요 가 있는데 owed 원장에 대응 행이 없으면 repo-integrity 가 advisory 경고(정책 17 비차단). 최소한 STATE 세션 라벨을 'trailing sync PR 이 종료를 선언한 뒤에는 새 라벨' 로 못박고 회귀 가드를 붙인다.
- **판정**: `SEVERITY_ADJUST` — 핵심 구조 결함은 실재하고 인용은 전건 실측 일치한다: (1) '세션 종료' 를 정의하는 기계가 없다 — .claude/settings.json 훅은 SessionStart|PreToolUse|PostToolUse 3종뿐이고 SessionEnd/Stop 이 없으며, scripts/retro_scope.py 는 '직전 회고 리포트 추가 커밋' 경계(회고 창)를 산출할 뿐 세션 경계가 아니다. (2) 손 라벨의 자기모순 실측 — #1290 제목 "세션16 종료 trailing sync"(머지 2026-08-04T23:32:26Z) 뒤에 docs/STATE.md:285-287 이 "세션16 6차 … 2026-08-06"·"7차"·"8차" 를 잇는다. (3) grep -n "129[0-4]" docs/runbooks/owed-verification.md = 무결과(최신 행 #1289 ×2·#1279·#1276), 반면 #1291 본문:104 · #1292:45 · #1293:96 · #1294:68 전건 §🔍 사용자 검증 필요 보유. (4) docs/backlog.md:43 R47-(a) 가 🟡(미착수) 로 "빈 원장 = green" 을 이미 기재 — 즉 미해소 항

### [process] PR #1294 본문이 자기 내용과 어긋난다 — CI 인프라 변경과 공개 배지 뒤집기가 사용자가 읽는 곳에 없다

- **위치**: `.github/workflows/claim-review-on-body-edit.yml:1`
- **주장**: 본문은 16:09:01Z 에 CSP 죽은 링크 제거만 서술한 상태로 생성됐고, 이후 두 커밋이 (a) .github/workflows/ci.yml 에 setup-node + `npm ci --ignore-scripts && npm run build` 를 추가하고 (b) 공개 README E2E 배지를 yellow→brightgreen 으로 뒤집었는데 본문은 갱신되지 않았다. §🔍 사용자 검증 필요 는 폰트만 묻는다 — 즉 사용자가 승인 근거로 읽는 텍스트에 CI 집행면 변경과 품질 주장 배지 변경이 존재하지 않는다(정책 2·3).
- **근거**: `gh pr view 1294 --json createdAt,commits` = created 2026-08-05T16:09:01Z / 커밋 226cd4a9 16:08:03Z · d82192fd 16:16:50Z · 2478c416 16:24:44Z. 본문 전문에 'ci.yml'·'npm run build'·'배지' 문자열 부재(§🔍 는 1.화면 동일 확인 2.타이포그래피 원하는지 2항만). files = ci.yml·README.md·README.ko.md·docs/STATE.md·docs/backlog.md·base.html·landing.html·2 테스트. 리포에 .github/workflows/claim-review-on-body-edit.yml 은 있으나 '본문 편집 시' 재평가라 '커밋 추가 시' 축은 열려 있다.
- **처방**: fix-up 커밋을 추가할 때마다 본문 §조치·§🔍 를 동반 갱신하고 `gh pr view --json body` 로 재검증한다(정책 10 생성 직후 검증 의무의 커밋-추가 축 확장). 배지 같은 공개 주장 변경은 별도 항목으로 §🔍 에 올린다.
- **판정**: `CONFIRMED` — 모든 사실 주장이 실측으로 재확인됨. `gh pr view 1294`: createdAt=2026-08-05T16:09:01Z, 커밋 226cd4a9(16:08:03Z) / d82192fd(16:16:50Z) / 2478c416(16:24:44Z) — 본문 생성 후 두 커밋이 추가됨. d82192fd 는 `.github/workflows/ci.yml` 에 `actions/setup-node@v7` + `npm ci --ignore-scripts && npm run build` 를 넣고(+16/-0), 2478c416 은 공개 README/README.ko 의 E2E 배지를 `yellow 122 in CI (119 pass / 1 known app bug)` → `brightgreen 121 in CI (120 pass / 1 skip)` 로 뒤집는다. 현재 본문(4127B, 지금 재fetch, PR 은 여전히 OPEN·미머지)에 `ci.yml|npm run build|npm ci|setup-node|배지|badge|brightgreen` 문자열 0건이고 §🔍 사용자 검증 필요 는 (1)화면 동일 확인 (2)타이포그래피 원하는지 2항 = 전부 폰트 축. 즉 정

### [code] R51 구조화 출력 라이브 검증이 사용자 선택 가능 모델 `claude-opus-4-7` 을 빠뜨렸다 — 미지원이면 그 리포의 모든 리뷰가 조용히 기본 점수로 강등

- **위치**: `src/analyzer/io/ai_review.py:154`
- **주장**: `#1289` 는 `output_config.format` 을 3경로에 무조건 배선했고, backlog R51 은 지원 여부를 `capabilities.structured_outputs.supported` 실측으로 확인했다고 기록하지만 그 실측 대상은 **haiku-4-5 · sonnet-4-6 · sonnet-5 3종뿐**이다. 그런데 제품이 설정 UI 에서 제공하는 리뷰 모델 목록에는 `claude-opus-4-7` 이 들어 있고(constants.py:192), 그 값은 그대로 `review_code(model=...)` 로 흘러 `output_config` 와 함께 전송된다. Opus 4.7 이 미지원이면 400 → 광범위 except → `_default_result("api_error")` 로 **사용자에게 아무 신호 없이** 전 리뷰가 기본 점수가 된다 — 같은 커밋이 P0 로 봉인한 빈-env 사고와 **완전히 같은 형태**이고, 단위 테스트는 AsyncMock 이라 원리적으로 못 본다.
- **근거**: docs/backlog.md R51: "`capabilities.structured_outputs.supported` 는 haiku-4-5·sonnet-4-6·sonnet-5 **전부 true**" (opus-4-7 부재) · src/constants.py:192 `"id": "claude-opus-4-7"` (CLAUDE_MODELS 선택지) · src/worker/pipeline.py:986,1001 `repo_review_model = _cfg.review_model or None` → `model=repo_review_model` · src/analyzer/io/ai_review.py:130 `model = model or settings.claude_review_model`, :154 `output_config={...}` 무조건 전송, :213 `return _default_result("api_error")` · src/api/repos.py:58 `review_model: str | None = None` (validator 없음 — 임의 문자열 허용) · tests/unit/analyzer/io/test_ai_review.py:396 은 mock 이 받은 kwarg 만 단언
- **처방**: (1) `models.retrieve("claude-opus-4-7").capabilities.structured_outputs.supported` 를 즉시 실측하고 결과를 R51 에 기록. false 면 P0 승격 — 해당 모델에서 `output_config` 미부착 분기 또는 선택지 제거. (2) `CLAUDE_MODELS` 전 항목이 검증된 allowlist 에 있는지 단언하는 단위 가드 추가(신규 모델 추가 시 검증 누락을 CI 가 잡도록). (3) `review_model` 에 `field_validator` 로 CLAUDE_MODELS 화이트리스트 강제.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 확인: ai_review.py:154 output_config 무조건 전송 · :130 model 폴백 · :213 _default_result("api_error") · constants.py:192 "claude-opus-4-7" (CLAUDE_MODELS 선택지) · pipeline.py:986,1001 리포별 모델 전파 · repos.py:58 review_model validator 부재(notification_language 만 validator 보유; config.py:214 는 전역 설정의 빈 문자열만 정규화하고 카탈로그 대조 없음) · backlog R51 실측 대상은 haiku-4-5·sonnet-4-6·sonnet-5 3종뿐이고 opus-4-7 부재.

그러나 P1 을 떠받치는 핵심 전제("사용자에게 아무 신호 없이" · 빈-env P0 와 "완전히 같은 형태" = silent fail-open)가 코드로 반증된다. api_error 는 침묵 경로가 아니라 이미 fail-closed 로 봉인돼 있다: src/gate/_common.py:12 AI_REVIEW_FAILED_STATUSES={"api_error","parse_

### [code] E2E 배지를 brightgreen 으로 올렸지만 CI 잡이 절대 wall-clock 임계 perf 11건을 함께 돌린다 — n=1 초록 위의 배지

- **위치**: `.github/workflows/ci.yml:546`
- **주장**: `pytest e2e/` 는 perf 마커를 제외하지 않아 121건 중 **11건이 절대 ms 임계 성능 테스트**다(ttfb 500ms · health_ttfb 300ms). 그 임계값은 코드 주석이 스스로 "로컬 SQLite 기준 완화값" 이라고 적은 값인데, 공유 GitHub Actions 러너에서 돌고 있다. `#1294` 본문 스스로 같은 세션에 perf 플레이크 1건을 관측했다고 적었다. 그 상태에서 배지를 **단 1회 CI 초록**으로 brightgreen 으로 올렸다 — 타이밍 단언의 안정성은 1회 통과로 증명되지 않으므로, 이 배지는 간헐적으로 거짓이 된다(R7 의 '지켜지지 않는 초록' 을 문서 축에서 반대 방향으로 재생산).
- **근거**: e2e/test_performance.py:13-19 `THRESHOLDS = {"ttfb": 500,  # ms — 로컬 SQLite 기준 완화값 ... "health_ttfb": 300}` · .github/workflows/ci.yml:546 `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` (`-m "not perf"` 없음) · `pytest e2e/ -m perf --collect-only` → `11/121 tests collected` · 커밋 226cd4a9 본문 "e2e (로컬 전체) → 1 failed → 그 1건은 perf 플레이크" · README.md:429 는 "perf ... separate from test-e2e" 라고 적지만 Makefile:158 `test-e2e: python -m pytest e2e/ -v -p no:asyncio` 는 perf 를 포함한다(문서 drift)
- **처방**: e2e 잡을 `-m "not perf"` 로 좁히고 perf 는 별도 non-blocking 잡(또는 nightly)으로 분리. 임계는 절대 ms 대신 워밍업 후 p95/상대 비교로 전환. README.md:429 문구를 Makefile 실측에 맞춰 정정. 배지는 최소 3회 연속 CI 초록 후 brightgreen 승격 규칙을 STATE 에 명문화.
- **판정**: `CONFIRMED` — 모든 인용을 실측 재확인했고 전부 일치한다. (1) ci.yml:546 = `python -m pytest e2e/ -q -rs -p no:asyncio --timeout=120` — `-m "not perf"` 없음. (2) `pytest e2e/ -m perf --collect-only` → `11/121 tests collected (110 deselected)`. (3) e2e/test_performance.py:13-19 THRESHOLDS 에 `# ms — 로컬 SQLite 기준 완화값` 주석 그대로 존재하고, 단언은 전부 절대 wall-clock 비교(`stats["ttfb"]["avg"] < THRESHOLDS["ttfb"]` 등 11건). (4) README.md:429 "separate from test-e2e" ↔ Makefile:157-158 `test-e2e: python -m pytest e2e/ -v -p no:asyncio` (마커 필터 없음) → 문서-기전 drift 실재. (5) README.md:22 배지는 라이브가 아니라 `brightgreen` 하드코딩 문자열. (6) 커밋 226cd4a9 본문 62행에 perf 플레이크

### [code] `check_docs_sync --fix` 의 SSOT 주장이 반쪽 — `통합 N` 은 이력이 아니라 자기가 덮어쓰는 셀에서 읽는다

- **위치**: `scripts/check_docs_sync.py:226`
- **주장**: `apply_fix` 는 '이력 마지막 한 줄이 SSOT, 나머지 4지점은 파생' 이라고 안내하지만, 산술 검증과 배지 생성에 쓰는 **통합(integration) 수치는 이력 줄에 존재하지 않고** 자기가 파생 sink 로 다시 쓰는 STATE 추적셀에서 정규식으로 읽어온다. 즉 통합 테스트 수가 바뀌면 작성자는 여전히 셀을 손으로 고쳐야 하고, 안내대로 이력 줄만 고치면 산술 검증(:236)이 red 를 내며 **엉뚱하게 '이력 마지막 항목의 수치를 고치라'** 고 지시한다(실제로 틀린 곳은 통합 셀). 손 편집 지점을 5→1 로 줄였다는 단언이 실제로는 5→2 다.
- **근거**: scripts/check_docs_sync.py:226 `integ = _first(re.compile(r"통합 (\d+) \(현재\)"), state)` — 이력이 아닌 STATE 셀에서 읽음 · :246 `new_state = _STATE_CELL_UNIT.sub(f"단위 {unit} + 통합 {integ} (현재)", new_state, count=1)` — 같은 셀을 파생 sink 로 다시 씀 · :236-239 산술 불일치 시 오류 메시지가 이력 줄만 지목 · :285 "손으로 고칠 곳은 STATE.md §테스트 수 추적 이력 **마지막 한 줄**뿐이다"
- **처방**: 이력 항목 형식 계약에 통합 수(`+ 통합 **N**`)를 추가해 진짜 단일 출처로 만들거나, 최소한 :236-239 오류 메시지와 :285 안내에 "통합 수는 추적셀이 원본이며 별도 갱신 대상" 을 명시. 회귀 가드: 통합 수만 바꿨을 때 `--fix` 가 올바른 위치를 지목하는지 단언.
- **판정**: `CONFIRMED` — 인용 4곳 전부 실측 확인 (scripts/check_docs_sync.py — :226 `integ = _first(re.compile(r"통합 (\d+) \(현재\)"), state)` · :246 `_STATE_CELL_UNIT.sub(f"단위 {unit} + 통합 {integ} (현재)", ...)` · :236-241 산술 거부 + "→ 이력 마지막 항목의 수치를 먼저 실측값으로 고칠 것" · :285 "손으로 고칠 곳은 … 마지막 한 줄뿐이다"). integ 는 이력에서 파생되지 않고 자기가 다시 쓰는 STATE 추적셀에서 읽는 self-referential 원천이 맞다.

실경로 재현 (실 STATE.md/README 2종 복사 후, 통합 171→175 시나리오로 **안내대로 이력 꼬리만** 6876→6880 수정):
  apply_fix ok=False
  ❌ 이력 SSOT 가 산술적으로 불가능하다 — 전체 6880 ≠ 단위 6705 + 통합 171 (차 +4). 아무것도 쓰지 않았다.
  → 이력 마지막 항목의 수치를 먼저 실측값으로 고칠 것 (`--collect-only`).
즉 이력 줄은 실측값으로 **옳은데** 오류가 그 줄을 지목하고,

### [code] 현재 브랜치가 미머지 PR #1294 위에 스택돼 있고 두 브랜치가 동일 README/STATE 배지 라인을 건드린다

- **위치**: `docs/STATE.md:31`
- **주장**: 작업 중인 `docs/claude-md-under-200` 은 main 이 아니라 **열려 있는 PR #1294 의 브랜치(`fix/csp-font-r52`) 위에** 만들어져, `origin/main...HEAD` diff 가 #1294 의 템플릿·CI·가드 변경을 통째로 포함한다. 두 브랜치 모두 README.md / README.ko.md / docs/STATE.md 의 같은 배지 라인을 수정한다. 이 리포는 squash-merge 를 쓰므로(머지 커밋이 `(#NNNN)` 단일 커밋 + 본문에 `* fix(docs):` 스쿼시 흔적) #1294 머지 후 이 브랜치는 rebase 없이는 동일 hunk 를 재적용하게 되고, CLAUDE.md 완료 6-step ⑤ 의 '배치-PR 이월 분기'(동일 파일 touch 미머지 PR 존재 시 `gh pr list` 사전 확인 의무)가 정확히 겨눈 상황이다.
- **근거**: `gh pr list` → 열린 PR 1건 `{"headRefName":"fix/csp-font-r52","number":1294}` · `git log origin/main..origin/docs/claude-md-under-200` → 7ab96205 + 2478c416 + d82192fd + 226cd4a9 (뒤 3건이 #1294 의 커밋) · `git diff --stat origin/main...HEAD` 에 `src/templates/base.html`·`landing.html`·`tests/unit/ui/test_csp_external_asset_parity.py`·`.github/workflows/ci.yml` 포함 · 양쪽이 `README.md`/`README.ko.md`/`docs/STATE.md` 동시 수정 · faeb2cf1 커밋 본문의 `* fix(docs):` = squash 흔적
- **처방**: #1294 를 먼저 머지한 뒤 `git rebase origin/main` 으로 이 브랜치를 정리하고 나서 PR 을 생성하거나, PR 을 지금 만든다면 base 를 `fix/csp-font-r52` 로 지정해 스택임을 명시할 것. PR 본문에 '#1294 선행 머지 의존' 1줄 명시(정책 3 자율 판단 사후 보고).
- **판정**: `CONFIRMED` — 독립 재현 완료 — 추론이 아니라 실제 머지 시뮬레이션으로 충돌을 확인했다.

【사실 확인】
1) 스택 구조 실재: `git merge-base origin/main HEAD` = faeb2cf1 이지만 `git log origin/main..HEAD` = 7ab96205 + 2478c416 + d82192fd + 226cd4a9 이고, 뒤 3건은 `git log origin/main..origin/fix/csp-font-r52` 와 정확히 일치(2478c416/d82192fd/226cd4a9). 즉 현재 브랜치는 main 이 아니라 #1294 브랜치 위에 있다.
2) 두 PR 모두 base = main: `gh pr view 1295 --json baseRefName` → "main", `gh pr view 1294` → "main". 그래서 #1295 의 리뷰 diff 가 12파일(#1294 의 src/templates/base.html·landing.html·.github/workflows/ci.yml·test_csp_external_asset_parity.py·test_router.py 포함)로 부풀어 있다 — #1294 파일 9건 전부가 #1295 

### [docs] 테스트 수 SSOT 이력의 체인이 실제로 끊겨 있다 (6635 → 6642, +7 무기록) — 가드는 꼬리 한 줄만 파싱해 중간 단절을 원리적으로 못 본다

- **위치**: `docs/STATE.md:282`
- **주장**: `docs/STATE.md` §테스트 수 추적 이력은 `.claude/rules/docs.md` 가 '손으로 고치는 유일한 곳' 으로 지정한 SSOT 인데, 세션16 1차 항목이 6635 로 끝나고 다음 3차 항목이 6642 로 시작한다 — +7 증분에 해당하는 항목(#1282 prompt caching PR)이 통째로 빠졌고 '2차' 라벨도 없다. #1293 이 신설한 꼬리 축 가드(`_history_tail`)는 **마지막 불릿만** 파싱하므로 이력 중간이 몇 칸 비어도 영구 green 이다. 같은 절의 마지막 항목은 내역 산술도 어긋난다.
- **근거**: docs/STATE.md:281 = `세션16 게이트 stdin 봉인 … (6621→**6635** 단위 …)` · docs/STATE.md:282 = `세션16 3차 … (6642→**6654** 단위 …)` → 6635↔6642 사이 +7 무기록, 2차 라벨 부재. docs/STATE.md:287 = `세션16 8차 … +27** (6678→**6705** 단위 — 행동 규칙 생존 가드 25 + 대조군 2 + CSP↔템플릿 정합 3(#1294 분)` → 내역 합 25+2+3=30 ≠ 델타 27 (그 3은 docs/STATE.md:286 의 7차 +3 과 이중 계상). 가드 범위: scripts/check_docs_sync.py 의 `_history_tail` docstring(파일 상단 주석 기준 '마지막 불릿을 앵커로') + tests/unit/scripts/test_repo_integrity_checks.py:61/:132/:149/:165 — 전부 '꼬리 1줄' 축이고 인접 항목 연속성 단언은 없다. 현재 `py -3 scripts/check_docs_sync.py` = 전건 ✅.
- **처방**: 누락된 세션16 2차 항목(#1282, 6635→6642)을 복원하고 8차 내역에서 이중 계상된 `+3(#1294 분)` 을 뺀다. 가드에 **체인 연속성** 단언을 추가한다: 이력 불릿 N의 `→ **B** 단위` 가 불릿 N+1의 `(A→` 와 같아야 하고, `= **C** 수집` 은 `B + 통합수` 와 같아야 한다. 뮤테이션 = 중간 불릿 1개 삭제 시 red.
- **판정**: `SEVERITY_ADJUST` — P1 기재 메커니즘은 실측으로 반증됨 — 체인은 끊겨 있지 않다. 신고자가 인용한 docs/STATE.md:281 을 `…` 로 절단하는 과정에서, 없다고 주장한 항목이 **같은 물리적 줄 뒷부분에** 있다는 사실이 가려졌다. :281 실체 = `… 2026-08-04).+ **세션16 2차 — 게이트 stdin·핀 가드 후속 (#1281·#1282) +7** (6635→**6642** 단위 — 프롬프트 캐시 구조 가드 TestPromptCache 7건[뮤테이션 6종 red]; = **6813** 수집 …)`. 즉 #1282 항목 존재 ○, '2차' 라벨 존재 ○, +7 기록 존재 ○ — 주장 3건 모두 거짓. 모든 `A→**B** 단위` 전이를 기계 추출한 결과 6621→6635→6642→6654→6658→6661→6675→6678→6705 로 무결하며 헤더(6705 단위 + 171 통합 = 6876)와 일치한다.

잔존하는 실결함 2건은 전부 표기 위생 수준이라 P2 로 조정한다. (1) :281 의 2차 항목이 `\n- ` 가 아니라 리터럴 `.+ ` 로 접합돼 독립 불릿이 아니다 — `git log -L281,281` 결과 STATE.md 30,806

### [docs] STATE '최신' 블록·날짜 헤더가 세션15에 고정돼 세션16(12 PR)의 서사가 STATE 에도 cycle-history 에도 존재하지 않는다

- **위치**: `docs/STATE.md:9`
- **주장**: STATE.md 는 자기 갱신 규칙 (0)(1)(2)를 본문에 명시하고 있는데 세션16 내내 3건 모두 미이행이다. 날짜 헤더는 2026-08-04 인데 같은 파일 본문이 2026-08-06 사실을 인용하고, '최신' 블록은 세션15(#1274~#1276)이며, cycle-history 의 최상단 항목은 세션14다. 결과적으로 세션16(#1279~#1294, 12 PR — 심의 게이트 mojibake P0·prompt caching·구조화 출력·e2e CI 배선·문서 감사·CSP)의 서사는 커밋 바디 외에 어디에도 없다. 이는 6-step ⑤('예외 없음')의 cycle-history 동기화 의무 위반이며, 회고 2026-07-03 C5 #60 이 '절차에서 상시 누락되던 필드' 로 지목한 항목의 재발이다. 전용 trailing sync PR 이 4건(#1281·#1283·#1287·#1290) 있었는데도 전부 수치만 돌렸다.
- **근거**: docs/STATE.md:5 = `## 현재 수치 (2026-08-04 기준)` vs docs/STATE.md:32 = `…(#1294, 2026-08-06)` · docs/STATE.md:7 이 규칙 (0)(1)(2)를 명시 · docs/STATE.md:9 = `**최신 (2026-08-04 세션15 …, PR #1274~#1276)**` · docs/STATE.md:22 = `**직전 (2026-08-02 세션14 …)**` · docs/STATE.md:281~287 은 세션16 1~8차를 기록(= 세션16 종료 사실 자체는 파일이 안다) · docs/cycle-history.md:9(목차 최상단) 및 :154(본문 최상단) = 세션14. 가드 공백: tests/unit/scripts/test_docs_ledger_shape.py:109 `test_state_has_exactly_one_latest_block` 은 `**최신 (` 의 **개수만** 단언하고, :133 `test_state_current_counts_agree_across_the_header` 는 헤더 영역 **수치만** 비교한다 → 최신 블록이 2세션 낡아도 8 passed green.
- **처방**: 세션16 블록을 '최신' 으로 회전(세션15→직전, 세션14→cycle-history 이관)하고 날짜 헤더를 2026-08-06 으로 갱신한다. 가드에 **신선도** 축을 추가한다: 이력 꼬리 항목이 언급한 세션 라벨(`세션N`)이 '최신' 블록의 세션 라벨과 같아야 red 를 면한다(수치 축과 달리 서사 축을 기계가 처음으로 보게 된다).
- **판정**: `SEVERITY_ADJUST` — REAL, not FP — every cited line re-verified. docs/STATE.md:5 = `## 현재 수치 (2026-08-04 기준)` while the same file's :32 cites `(#1294, 2026-08-06)` and tail entries :285~287 record `collect-only 실측 2026-08-06`; :9 = `**최신 (2026-08-04 세션15 …, PR #1274~#1276)**`; :22 = 세션14; :7 states rules (0)(1)(2) verbatim. docs/cycle-history.md:9 (TOC top) and :154 (body top) are both 세션14, and `grep -c "세션1[56]"` returns 0 — neither 세션15 nor 세션16 has a cycle-history section. Guard gap confirmed mechanically: test_docs_ledger_shape.py:109 asserts only `len(blocks) == 1` (count, not freshness) and :133 compares o

### [docs] CLAUDE.md 424→195줄 슬림이 backlog 의 line 인용 3건을 EOF 밖으로 밀어냈다 — 그중 하나가 유일한 🔴 결정 대기 항목

- **위치**: `docs/backlog.md:44`
- **주장**: 7ab96205 이 CLAUDE.md 를 424→195줄로 줄이면서 그 파일을 line 단위로 인용하던 활성 원장을 갱신하지 않았다. backlog 의 R43(🟡)·R48(🔴 결정 대기)·R45-(c)(🟡)가 각각 `CLAUDE.md:366`·`CLAUDE.md:353`·`CLAUDE.md:35` 를 가리키는데 파일은 195줄이라 앞의 둘은 존재하지 않는 줄이고 세 번째는 전혀 무관한 줄을 가리킨다. 정책 6('정책/원장 본문의 file:line 은 grep -n 실측값') 위반이며, 하필 R48 은 이 원장의 **유일한 사용자 결정 대기 항목**이라 다음 세션이 결정을 집으려면 근거 줄부터 다시 찾아야 한다. 더 나쁜 것은 R45-(c)가 '정책 detail 링크 죽은 앵커' 를 열린 결함으로 이미 적어 뒀는데, 이번 슬림이 정책 1~17 본문을 external 링크로 대체해 **죽은 앵커를 유일한 도달 경로로 승격**시켰다는 점이다(열린 항목을 먼저 닫지 않고 그 위에 의존을 쌓았다).
- **근거**: `wc -l CLAUDE.md` = 195. docs/backlog.md:39 = `**기전**: \`CLAUDE.md:366\` 매트릭스가 의무를 정의…`(현재 위치 = CLAUDE.md:177~189) · docs/backlog.md:44 = `**기전**: \`CLAUDE.md:353\` 이 …`(현재 위치 = CLAUDE.md:144 6-step ②) · docs/backlog.md:41 = `(c) \`CLAUDE.md:35\` 등 정책 detail 링크 **16건이 죽은 앵커**`(CLAUDE.md:35 은 현재 `최초 설정: cp .env.example .env → make install → make run.`). 앵커 실측(GitHub 앵커 규칙 재현 스크립트): CLAUDE.md:76·79·81·83·84·85·86·87·88·89·90·97 의 `.claude/policies/active.md#정책-N` **12건 전건 미해결** — active.md 실제 헤딩은 `## 정책 2: PR 본문 "🔍 사용자 검증 필요" 섹션 의무`(:10), `## 정책 7: 위반 시 회복`(:52), `## 정책 10: PR 직접 생성 의무 (URL 안내 X, 자동 생성 ○)`(:26) 등 전체 제목이라 `#정책-2`/`#정책-7`/`#정책-10` 로는 도달 불가.
- **처방**: backlog R43/R45-(c)/R48 의 CLAUDE.md 인용을 `grep -n` 실측값으로 재작성하고 커밋 해시를 병기한다(정책 6 권장 형태). 동시에 R45-(c)의 죽은 앵커 12건을 이번 슬림 PR 의 fix-up 으로 처리한다 — 본문을 지운 PR 이 링크를 고칠 책임을 진다(정책 4: 단언과 가드를 같은 PR 에). 링크 도달성 체커를 repo-integrity 에 배선하면 R45-(c) 반증 수단이 그대로 충족된다.
- **판정**: `SEVERITY_ADJUST` — defect is real and every citation reproduces, but the impact is documentation-navigation debt with a one-grep recovery, not P1.

VERIFIED: wc -l CLAUDE.md = 195. docs/backlog.md:39 (R43, open 🟡) cites `CLAUDE.md:366` and :44 (R48, open 🔴) cites `CLAUDE.md:353` — both past EOF; :41 (R45-c, open 🟡) cites `CLAUDE.md:35`, which now reads "최초 설정: cp .env.example .env → make install → make run." exactly as claimed. Causation confirmed: at 7ab96205^ CLAUDE.md was 423 lines with :353 = verbatim the 6-step ② line and :366 = verbatim the `.claude/rules/<area>.md` matrix row, and the citations predate th

### [docs] path-scoped rules 영역 개수가 세 곳에서 세 값을 말한다 — 산문 10 / 가드 메시지 9 / 실제 11

- **위치**: `CLAUDE.md:175`
- **주장**: 2026-08-05 에 `.claude/rules/docs.md` 가 11번째 영역으로 추가됐지만 CLAUDE.md 의 산문 카운트와 가드의 안내 문구는 둘 다 갱신되지 않았고, 원래도 서로 달랐다. 가드는 `>= 9` 하한만 보므로 몇 개가 되든 green 이고, 결과적으로 '몇 영역인가' 를 묻는 독자는 어느 문장을 읽느냐에 따라 9·10·11 을 얻는다. rules 표면은 자동 로드되는 행동 지침이라 개수 자체가 커버리지 주장으로 읽힌다.
- **근거**: `ls .claude/rules/` = api·db·deploy·docs·guards·i18n·pipeline·security·services·testing·ui **11개**. CLAUDE.md:177~189 표 = **11행**(:189 이 `문서 / 원장 | docs.md`). 그러나 CLAUDE.md:175 = `**사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) …`. 그리고 tests/unit/scripts/test_rules_and_index_coverage.py:15 = `3. CLAUDE.md 의 9영역 매트릭스와 …`, :89 = `→ … + CLAUDE.md 9영역 매트릭스에`, :221 = `assert len(_areas()) >= 9, …`.
- **처방**: 세 지점의 리터럴 개수를 제거하고 파생으로 바꾼다 — CLAUDE.md 산문은 개수를 빼거나 '표 = 정본' 으로 쓰고, 가드 메시지는 `len(_areas())` 를 포맷팅해 출력한다. 하한 `>= 9` 은 `== len(rules 파일 수)` 로 조여 신규 rules 추가 시 매트릭스 누락이 red 가 되게 한다.
- **판정**: `CONFIRMED` — 모든 인용 실측 일치. `ls .claude/rules/` = 11개(api·db·deploy·docs·guards·i18n·pipeline·security·services·testing·ui), CLAUDE.md:179~189 = 11행(:189 `| 문서 / 원장 | docs.md`), CLAUDE.md:175 = `10 카테고리(2026-07-20 guards 추가)`, test_rules_and_index_coverage.py:15/:89 = `9영역 매트릭스`, :221 = `assert len(_areas()) >= 9`. 같은 사실에 세 숫자(9·10·11)가 살아 있고, 스위트를 실제 실행하니 11개 상태에서 **9 passed** — `>= 9` 하한은 어떤 개수에서도 green 이라 어느 숫자도 기계로 고정돼 있지 않음이 확인됨. `git log -- .claude/rules/docs.md` = faeb2cf1(2026-08-06; 근거의 08-05 는 파일 본문 표기일 뿐 무관).

근거 프레이밍 1건 정정(판정 불변): 매트릭스 **표 자체는 무방비가 아니다**. `test_matrix_extraction_is_not_empty` 가 `

### [docs] env-vars.md 를 SSOT 로 선언한 CLAUDE.md 가 정작 env-vars.md 에 없는 함정을 자기 본문에만 적었다 (SSOT 역전)

- **위치**: `docs/reference/env-vars.md:28`
- **주장**: 슬림된 CLAUDE.md 는 '환경변수 전체 목록·설명·제약은 env-vars.md 가 정본이다 (여기 복제하면 두 곳이 갈라진다)' 라고 선언한 직후, env-vars.md 에 존재하지 않는 `CLAUDE_REVIEW_MODEL` 빈값 함정을 자기 본문에 적었다. 실제로 2026-08-05 에 그 빈값이 AI 리뷰를 전부 `api_error` 로 죽인 P0(#1289)를 냈고 config.py 에 `field_validator` 가 추가됐는데, CLAUDE.md 의 신규 파일 동기화 체크리스트가 명시한 'config.py validator 변경 시에도 env-vars.md 동기화' 가 이행되지 않았다. 같은 파일에 선례도 있다(SMTP_PORT 행은 validator 동작을 본문에 적고 있다).
- **근거**: CLAUDE.md:48~49 = `전체 목록·설명·제약은 … env-vars.md 가 정본이다 (여기 복제하면 두 곳이 갈라진다 — 실제로 4건 누락 사고가 있었다).` vs CLAUDE.md:51~53 = `🔴 함정만 적는다: … \`CLAUDE_REVIEW_MODEL\` 을 **빈 값으로 두면** 기본값을 덮어 AI 리뷰가 전부 \`api_error\`(#1289).` · CLAUDE.md:147~150 = 동기화 의무(`config.py` validator·최솟값 변경 시에도). 실제 코드 = src/config.py:214 `@field_validator("claude_review_model", "claude_insight_model", mode="before")` + :219 사고 기록. 그러나 docs/reference/env-vars.md:28(`CLAUDE_REVIEW_MODEL`)·:30(`CLAUDE_INSIGHT_MODEL`) 에는 빈값/validator 언급 0. 선례 = docs/reference/env-vars.md:82 `SMTP_PORT … config.py의 coerce_smtp_port validator가 빈 문자열을 587로 자동 변환`.
- **처방**: env-vars.md:28/:30 에 '빈 문자열 = 미설정으로 취급, 기본값 폴백(`_blank_model_falls_back_to_default`, #1289 — 이전에는 빈값이 기본을 덮어 전 리뷰 api_error)' 을 SMTP_PORT 행과 같은 형식으로 추가한다. 그 뒤 CLAUDE.md:53 의 해당 함정 문장은 링크로 대체해 선언한 SSOT 규약과 본문을 일치시킨다.
- **판정**: `CONFIRMED` — 모든 인용 line 실측 일치. CLAUDE.md:48 `전체 목록·설명·제약은 … env-vars.md 가 정본이다` / :51~53 `함정만 적는다 … CLAUDE_REVIEW_MODEL 을 빈 값으로 두면 … api_error(#1289)` / :147~150 동기화 의무(`config.py` validator·최솟값 변경 시에도) / src/config.py:214 `@field_validator("claude_review_model","claude_insight_model", mode="before")` + :219 2026-08-05 사고 기록 / docs/reference/env-vars.md:28·:30 에 빈값·validator 언급 0 / 선례 :82 SMTP_PORT `coerce_smtp_port validator가 빈 문자열을 587로 자동 변환` — 전부 확인.

결정적 추가 증거 2건(발견자 미인용):
(1) **같은 문장의 나머지 함정 2건은 SSOT 에 있다** — SESSION_SECRET 은 env-vars.md:12 (`32자 이상 필수 — 미충족 시 config.py ValidationError 앱 기동 오류`), APP

### [docs] backlog 의 '이 파일부터 읽으면 된다' 진입점이 세션15 시점에 멈춰 있어 새 세션을 2세션 낡은 맥락으로 안내한다

- **위치**: `docs/backlog.md:12`
- **주장**: backlog.md 는 스스로를 '지금 뭐가 남았나' 의 단일 출처로 규정하고 '▶️ 다음 세션 시작점' 섹션을 두어 '이 파일부터 읽으면 된다' 고 말한다. 그런데 그 진입점 헤더와 본문은 2026-08-04 세션15 5+1 회고 이관 시점 그대로이고, 이후 세션16 이 추가한 R49~R55(그중 R52 는 e2e 30건 실패라는 대형 사실, R53·R55 는 착수 가능 잔여)는 진입 서사에 반영되지 않았다. 표 자체와 상태 요약 카운트는 정확하므로 결함은 '진입점 신선도' 한 축이다.
- **근거**: docs/backlog.md:12 = `## ▶️ 다음 세션 시작점 (2026-08-04 세션15 — 5+1 회고 이관)` · :14 = `**이 파일부터 읽으면 된다.**` · :16~ = 2026-08-04 회고 서사만. 이후 신설분 = docs/backlog.md:46(R49)·:47(R50)·:49(R51)·:51(R52)·:53(R53)·:55(R54)·:57(R55). 상태 요약(docs/backlog.md:59 `현재 창 21행 … 🔴 1 · 🟡 11 · ✅ 9`)은 실측과 일치 확인 — `Counter({'✅': 28, '🟡': 25, '🔴': 1, '⏸': 1})` 중 현재 창 21행 기준 ✅9·🟡11·🔴1 로 bijection 성립(`test_backlog_shape.py` 10 passed).
- **처방**: 진입점 헤더를 최신 세션으로 회전시키고 R49~R55 중 착수 가능 3건(R53·R55 + 잔여축)을 1~2줄로 요약한다. 장기적으로는 이 헤더의 세션 라벨을 STATE '최신' 블록 라벨과 대조하는 단언을 `test_backlog_shape.py` 에 추가하면 두 원장의 진입점이 함께 늙는 것을 막을 수 있다.
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. `docs/backlog.md:12` = `## ▶️ 다음 세션 시작점 (2026-08-04 세션15 — 5+1 회고 이관)` · `:14` = `**이 파일부터 읽으면 된다.**` · 신설분 `:46`(R49)·`:47`(R50)·`:49`(R51)·`:51`(R52)·`:53`(R53)·`:55`(R54)·`:57`(R55) 모두 존재.

회의적으로 반증을 시도했으나 3개 축이 오히려 주장을 강화했다.

(1) **git blame 이 비대칭을 확정한다** — `git log -L 12,27:docs/backlog.md` 실측: 진입점 헤더+서사 블록의 마지막 편집은 `8f4ada5a`(2026-08-04, 세션15 회고 아카이브)다. 이후 세션16 이 backlog 를 5회 편집했으나(`cb2d9657`·`5b72c438`·`d32d9da8`·`faeb2cf1`·`226cd4a9`, 최신 2026-08-06) **12~27행은 한 번도 건드리지 않았다**. 즉 "표는 갱신되는데 진입 서사만 얼어 있다" 는 주장 그대로다.

(2) **'헤더는 출처 표기일 뿐' 이라는 반론이 규약으로 기각된다** — `grep -n "^## ▶️"

### [decision] PR #1294 본문이 자기 diff 를 더 이상 서술하지 않는다 — 민감 경로 CI 변경이 무기록으로 실렸고 면제 사유도 무효화됐다

- **위치**: `.github/workflows/ci.yml:95`
- **주장**: PR #1294 는 2026-08-05T16:09Z 생성 이후 d82192fd(.github/workflows/ci.yml +16줄, E2E CSS 빌드)와 2478c416(README 2배지 + STATE)이 추가됐는데 본문은 갱신되지 않았다. 본문 전문에 'ci.yml'·'workflow'·'CSS 빌드' 매치 0건이다. 리포 자신의 가드가 '🔒 Auto-merge withheld — sensitive paths changed … .github/workflows/ci.yml' 를 2회 코멘트했는데, 사용자가 읽는 본문에는 그 변경의 목적·영향·검증이 한 줄도 없다. 나아가 본문 하단의 정책 19 면제 마커 사유('죽은 코드 제거 + 재발 가드. seal 주장 없음')도 이제 PR 을 서술하지 않아, check_claim_review_trace 의 ::notice 계량이 실제와 어긋난 사유를 기록한다. 정책 3(자율 판단 사후 보고) + 정책 10(본문 검증 의무) 양쪽에 걸린다.
- **근거**: `gh pr view 1294 --json files` → .github/workflows/ci.yml 포함 9파일 · `gh pr view 1294 --json body | grep -ci 'ci\.yml|workflow|CSS 빌드'` → 0 · `gh pr view 1294 --json comments` → 'Auto-merge withheld — sensitive paths changed … .github/workflows/ci.yml' 2건 · 커밋 시각 d82192fd 2026-08-06 01:16:50, 2478c416 01:24:44 (PR 생성 01:09 KST 이후)
- **처방**: fix-up 커밋을 추가할 때 본문 재갱신을 6-step 에 준하는 의무로 승격한다. 기계 배선안: PR 본문 편집 재검증 워크플로(#1263 산출물)를 확장해 'PR 파일 목록의 민감 경로(.github/workflows/**, alembic/**, src/auth/**)가 본문에서 문자열로 언급되지 않으면 ::warning' 을 내도록 한다.
- **판정**: `SEVERITY_ADJUST` — 핵심 사실은 전건 실측 확인됨. 그러나 P1을 떠받치는 가중 주장 2건이 측정에서 반증돼 P2로 조정.

■ 확인된 사실 (전부 재현)
1. `gh pr view 1294 --json files` → `.github/workflows/ci.yml +16/-0` 포함 9파일. state=OPEN, mergedAt=null, createdAt 2026-08-05T16:09:01Z.
2. 커밋 시각 실측: 226cd4a9 16:08:03Z(PR 생성 전) / d82192fd 16:16:50Z / 2478c416 16:24:44Z → 뒤 2건은 PR 생성 이후 추가. body updatedAt=16:30:57Z 이나 본문에 반영 0.
3. 본문 전문 grep: `ci\.yml|workflow|워크플로|CSS 빌드|npm|node` 매치 0. 유일한 `CSS` 히트는 10행 `두 외부 스타일시트 cssRules 접근 = BLOCKED`(Playwright 실측 블록) — CI CSS 빌드와 무관.
4. `xzawed` 봇 코멘트 2건(16:18:35Z, 16:26:28Z) 전문에 `- \`.github/workflows/ci.yml\`` + "a human shoul

### [decision] 존재하지 않는 PR 번호 #1295 를 SSOT 에 발행했고, 같은 줄의 열거 산술이 표기 delta 와 맞지 않는다

- **위치**: `docs/STATE.md:287`
- **주장**: docs/STATE.md:287 이 '세션16 8차 — CLAUDE.md 424→196줄 … + CSP 링크 제거 (#1294·#1295) +27' 로 기록하는데 `gh api repos/xzawed/SCAManager/pulls/1295` 와 `.../issues/1295` 모두 404 다 — 아직 만들어지지 않은 PR 번호를 선점해 발행했고, 실제 PR 이 다른 번호를 받으면 이 귀속은 영구 거짓이 된다. 같은 줄의 열거도 '행동 규칙 생존 가드 25 + 대조군 2 + CSP↔템플릿 정합 3(#1294 분)' = 30 인데 표기 delta 는 +27(6678→6705)이다. 그 3건은 line 286(세션16 7차, 6675→6678)에서 이미 계상됐다. #1293 이 바로 이 절에 넣은 산술 가드는 total=unit+integ 축만 봐서(check_docs_sync.py:238) 열거 불일치를 못 본다. 같은 창의 #1285 가 '죽은 기록 4건 정정' 을 한 직후의 재발이다.
- **근거**: docs/STATE.md:287 · `gh api repos/xzawed/SCAManager/pulls/1295` → 404 Not Found, `gh api .../issues/1295` → 404 · docs/STATE.md:286 (세션16 7차 = #1294 분 +3 이미 계상) · scripts/check_docs_sync.py:238 (산술 가드 = 전체 vs 단위+통합 축 한정) · `py -3 scripts/check_docs_sync.py` → EXIT=0 (미탐 실증)
- **처방**: PR 번호는 gh pr create 반환 URL 을 받은 뒤에만 기록한다(선점 금지). check_docs_sync.py 에 '이력 꼬리 줄의 #NNNN 참조가 실재하는가' 는 오프라인 검증 불가하므로, 대신 (a) 열거 항목 합 == 표기 delta 산술 가드와 (b) 같은 PR 번호가 두 이력 줄에 중복 계상되지 않는지 검사를 추가한다.
- **판정**: `SEVERITY_ADJUST` — P1 을 떠받치던 결정적 근거가 재현되지 않는다. `gh api repos/xzawed/SCAManager/pulls/1295` 는 404 가 아니라 **HTTP 200** 이며, open PR 제목이 `docs: CLAUDE.md 424 → 196줄 (Anthropic 200줄 기준) + 행동 규칙 생존 가드` 로 STATE.md:287 기재와 정확히 일치한다(`/issues/1295` 도 200). 더구나 그 줄을 쓴 커밋 `7ab96205` 자체가 **PR #1295 의 head SHA** 다 — 번호 선점도, 거짓 귀속도 없다. "실제 PR 이 다른 번호를 받으면 영구 거짓" 이라는 위험 서사는 성립하지 않는다.

열거 산술도 수치는 맞다. `tests/unit/scripts/test_claude_md_behavior_rules.py` 실측 collect = **27** (`test_behavior_rule_survives_in_claude_md` parametrize 25 + `test_the_rule_list_is_not_vacuous` 1 + `test_claude_md_stays_near_the_anthropic_line_target` 1) 로

### [decision] STATE.md 의 '현재 상태' 표면이 2 세션·18 PR stale — 다음 세션의 1차 결정 입력이 죽어 있다

- **위치**: `docs/STATE.md:9`
- **주장**: docs/STATE.md:5 는 '## 현재 수치 (2026-08-04 기준)', :9 는 '최신 (2026-08-04 세션15 … PR #1274~#1276)' 에 고정돼 있는데 그 뒤 #1279~#1294 18건이 머지됐다. docs/cycle-history.md 의 최신 섹션은 line 154 세션14(2026-08-02)라 세션15·16 서사는 어느 쪽에도 이관되지 않았다. STATE.md:7 은 스스로 '🔴 다음 세션 갱신 규칙: (0) line 5 날짜 헤더 갱신 (회고 2026-07-03 C5 #60 — 절차에서 상시 누락되던 필드), (1) 최신 블록 교체, (2) 직전 서사를 cycle-history.md 로 이관' 을 명령하는데 세 항목 모두 미이행이다. trailing sync 4건(#1281·#1283·#1287·#1290)은 수치만 갱신했다 — #1290 은 '세션16 종료' 를 표방하면서 STATE.md 를 4줄만 바꿨다. 6-step ⑤의 후반부('docs/cycle-history.md 사이클 이력 동기화')가 연속 4 PR 에서 누락됐고, 그 결과 이 회고를 포함해 다음 세션이 '지금 어디인가' 를 읽는 표면이 18 PR 만큼 거짓이다.
- **근거**: docs/STATE.md:5 · docs/STATE.md:7 (갱신 규칙 0/1/2) · docs/STATE.md:9 (최신 = 세션15, PR #1274~#1276) · docs/cycle-history.md:154 (최신 섹션 = 세션14) · `git show cb2d9657 --stat` → docs/STATE.md 4줄(+2/-2)
- **처방**: 세션 종료 trailing sync PR 에서 (0) line 5 날짜 (1) 최신 블록 교체 (2) 직전 블록 cycle-history 이관 3건을 한 커밋으로 처리하고, check_docs_sync.py 에 'STATE.md:5 날짜 헤더 ≥ 최신 머지 PR 날짜' · 'STATE.md 최신 블록이 인용한 PR 번호 ≥ 직전 cycle-history 섹션 PR 범위' 불변식을 추가해 수치 축만 초록인 상태를 끝낸다.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 확인. docs/STATE.md:5 = '## 현재 수치 (2026-08-04 기준)' · :7 = 갱신 규칙 (0)/(1)/(2) · :9 = '최신 (2026-08-04 세션15 … PR #1274~#1276)' · docs/cycle-history.md:154 = 세션14(2026-08-02) 최신 섹션 — 전부 주장대로다. `git show cb2d9657 --stat` → docs/STATE.md 4줄(+2/-2) 확인, 그리고 #1281·#1283·#1287·#1290 **네 건 모두 docs/cycle-history.md 를 한 줄도 건드리지 않았다**(#1293 도 동일). 머지 창도 맞다 — 세션15 trailing sync(#1277) 이후 #1278·#1273·#1279~#1294 = 정확히 18건('#1279~#1294' 라벨 자체는 16건이라 범위 표기만 헐겁다). 즉 규칙 (0) 날짜 헤더와 (2) cycle-history 이관은 명백히 미이행이고, #1290 이 스스로 '세션16 종료' 를 표방하면서 최신 블록을 쓰지도 세션15 를 강등하지도 않은 것 = 실재 결함.

그러나 심각도의 근거인 영향 주장('다음 세션의

### [decision] #1294 가 사용자에게 물은 vendoring/타이포그래피 결정이 어느 원장에도 등재되지 않았고 R52 는 ✅ 로 닫혔다

- **위치**: `docs/backlog.md:51`
- **주장**: PR #1294 본문 §🔍 사용자 검증 필요 2 는 '🔴 의도했던 타이포그래피를 원하시는지 — Pretendard/Inter 를 실제로 적용하려면 src/static/vendor/ vendoring 이 필요하고, 그건 14개월 만의 시각 변경이라 별도 결정입니다' 로 명시적 결정 요청을 낸다. 그런데 docs/backlog.md:51 R52 는 '✅ 완료 (30 → 0)' 로 닫혔고, `grep -n 'vendoring|Pretendard|타이포그래피' docs/backlog.md docs/runbooks/owed-verification.md` 결과 backlog 는 R52 서술 안 언급뿐·owed 원장은 0건이다. backlog.md 서문이 스스로 '회고 보고서는 시점 스냅샷이라 지금 뭐가 남았나를 답하지 못한다 — 이 파일이 그 질문의 단일 출처' 라 선언하는데, 이 결정은 PR 본문에만 존재해 머지와 함께 추적면에서 사라진다. 정책 15 High tier(시각/UX 결정)로 자기 분류한 항목이 등재 없이 소멸하는 구조다.
- **근거**: `gh pr view 1294 --json body` §🔍 사용자 검증 필요 항목 2 · docs/backlog.md:51 (R52 = ✅ 완료) · `grep -n 'vendoring|Pretendard|타이포그래피' docs/backlog.md docs/runbooks/owed-verification.md` → backlog:51 (R52 본문 내부) 1건, owed 0건 · docs/backlog.md 서문 '이 파일이 그 질문의 단일 출처'
- **처방**: R56(또는 R52-b) 를 🔴 결정 대기로 신설한다 — '외부 폰트 vendoring 여부: ㉮ 현행 시스템 폰트 유지 ㉯ src/static/vendor/ vendoring(14개월 만의 첫 타이포그래피 변경, 정책 11 8조합 시각 검증 필요)'. 규칙화: PR 본문 §사용자 검증 필요 에 '별도 결정' 문구가 있으면 backlog 🔴 또는 owed 행 등재를 동반 의무로 둔다.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 확인. (1) PR #1294 본문 §🔍 사용자 검증 필요 항목 2 = 인용 문자열 그대로 존재("의도했던 타이포그래피를 원하시는지 — Pretendard/Inter 를 실제로 적용하려면 src/static/vendor/ vendoring 이 필요하고, 그건 14개월 만의 시각 변경이라 별도 결정입니다"). (2) docs/backlog.md:51 = "✅ 완료 (30 → 0) — CSP 앱 버그까지 해소 (#1294)" 존재. (3) grep -nE 'vendoring|Pretendard|타이포그래피' → backlog.md:51 (R52 서술 내부) 1건 · docs/runbooks/owed-verification.md 0건 재현. (4) 서문 "이 파일이 그 질문의 단일 출처" = docs/backlog.md:4 존재. 추가 확인: `grep -rn owed-verification scripts/ .claude/ .github/` 결과 scripts/check_owed_verification.py:24 가 원장 파일만 읽고, PR 본문 §사용자 검증 필요를 원장으로 옮기는 기계 경로는 0 — 즉 이관은 순수 수기 규율이라 소실은 가설이 

### [decision] e2e 를 CI 에 배선한 결정(#1288)이 diff-한정 가드의 스코프 재평가 없이 내려졌고, 그 결과가 같은 창에서 즉시 실현됐다

- **위치**: `.github/workflows/ci.yml:95`
- **주장**: .github/workflows/ci.yml:95 의 C1 dead-symbol 가드는 `git diff --name-only … -- 'tests/'` 로 tests/ 에만 걸려 e2e/ 를 구조적으로 보지 못한다. #1288 이 e2e 122건을 CI 에 배선하면서 e2e/ 는 '한 번도 실행되지 않던 표면' 에서 '적극 편집되는 표면' 으로 성격이 바뀌었는데, 그 결정과 함께 diff-한정 가드들의 스코프를 재평가한 기록이 없다. 곧바로 #1291(e2e 30건 재작성)이 e2e/test_theme.py:2 에 미사용 `import pytest` 를 남겼고, CodeQL alert #565 (py/unused-import) 가 2026-08-05T12:44:41Z 에 열렸다 — ci.yml:65~68 의 주석이 이 가드의 존재 이유를 '신규 F401/F841 이 main full-scan CodeQL 에 사후 포착돼 별도 fix PR(#516/#517/#520/#521/#522)을 반복 유발한 cascade 근본 차단' 이라 적어 둔, 바로 그 시나리오의 재현이다. 이후 #1292·#1293·#1294 3건이 머지되는 동안 정책 14 가 요구하는 triage 결정(fix / dismiss+사유 / suppress)은 어느 PR 본문에도 기록되지 않았다.
- **근거**: .github/workflows/ci.yml:95 (`-- 'tests/'` 스코프) · .github/workflows/ci.yml:65~68 (가드의 자기 서술 = cascade 근본 차단) · `gh api .../code-scanning/alerts` → open 1건 = 565 | py/unused-import | 2026-08-05T12:44:41Z | e2e/test_theme.py:2 · `grep -n pytest e2e/test_theme.py` → line 2 단독(사용처 0) · `git log --oneline -3 -- e2e/test_theme.py` → 5b72c438 (#1291)
- **처방**: ci.yml:95 의 pathspec 을 `-- 'tests/' 'e2e/'` 로 확장하고(뮤테이션: e2e 에 F401 도입 시 red 확인), e2e/test_theme.py:2 의 미사용 import 를 제거해 alert #565 를 닫는다. 규칙화: 새 테스트 표면을 CI 에 배선하는 PR 은 본문에 '이 표면에 걸리는 diff-한정 가드 목록과 스코프 확인' 1줄을 의무 기재한다.
- **판정**: `SEVERITY_ADJUST` — 모든 인용은 실측 재확인됨 — 문제는 인용이 아니라 인용에서 끌어낸 인과 추론이다.

【확인된 부분 — 이것이 P2 로 남는 실체】
ci.yml:95 는 `git diff … -- 'tests/'` 로 e2e/ 를 구조적으로 못 본다(실측 일치). 갭은 주장보다 오히려 넓다 — check_dual_import.py:123 과 check_noqa_sideeffect.py:116 도 동일하게 tests/ 한정이라 diff-한정 가드 3종 전부가 e2e/ 를 못 본다. #1288 이 e2e/ 의 성격을 바꾼 것도 사실이고(리포 자체 커밋 2478c416 이 "실행된 적이 없어 아무도 몰랐던 빨강" 이라 기록), #1288 본문은 의도적 미수행 항목(required check 승격·배지)을 명시 열거하면서도 diff-한정 가드 스코프 재평가는 언급 0 이다. `flake8 --isolated --select=F401,F841 e2e/test_theme.py` → F401 exit 1 로, 스코프에 있었다면 발화했을 것도 확인된다. 즉 "배선 결정이 스코프 재평가 없이 내려졌다" 는 참이고 백로그 가치가 있다.

【반증된 부분 — P1 을 지탱하던 축】
"그 결과가 

### [decision] 측정 오차를 사과하는 바로 그 커밋이 같은 파일의 줄 수를 다시 +1 씩 틀렸다

- **위치**: `CLAUDE.md:1`
- **주장**: 7ab96205 는 제목과 본문에서 'CLAUDE.md 424 → 196줄' 을 반복하는데, 실측은 이전 423줄 / 현재 195줄이다(양쪽 파일 모두 개행으로 끝나 wc -l 이 정확). 같은 커밋 본문 안에 '표 셀 안에 넣어 줄 수는 195줄 유지' 라는 상충 수치가 병기돼 있어, 하나의 커밋 메시지가 같은 파일에 대해 196 과 195 를 동시에 주장한다. 그리고 지속 기록이 되는 쪽(제목·향후 PR 제목)이 틀린 값을 싣는다. 이 커밋의 첫 섹션이 '측정 규율 4(단위 명시)를 또 어겼고 사용자가 잡았다' 인 만큼, 같은 결함 클래스의 즉시 재발이다.
- **근거**: `git show 2478c416:CLAUDE.md | wc -l` → 423 · `wc -l CLAUDE.md` → 195 · `git show 2478c416:CLAUDE.md | tail -c 1 | od -c` → \n, `tail -c 1 CLAUDE.md | od -c` → \n (둘 다 개행 종료 = wc -l 정확) · 7ab96205 커밋 제목/본문 '424 → 196줄' vs 본문 '줄 수는 195줄 유지'
- **처방**: PR 생성 시 제목·본문 수치를 423→195 로 정정한다. 규칙화: 파일 크기·줄 수·토큰 수를 발행할 때는 산출 명령을 함께 적는다(예: '195줄 — `wc -l CLAUDE.md`'), AGENTS.md 측정 규율에 '수치 옆 산출 명령 병기' 를 추가.
- **판정**: `CONFIRMED` — 전 근거 재현 확인. 실측: `git show 2478c416:CLAUDE.md | wc -l` → 423 · `git show 7ab96205:CLAUDE.md | wc -l` → 195. 두 리비전 모두 `tail -c 1 | od -c` → `\n` 이라 wc -l 이 정확하며, `git show --numstat 7ab96205 -- CLAUDE.md` → `103 331` 도 423-331+103=195 로 일치한다. 반면 7ab96205 는 제목("docs: CLAUDE.md 424 → 196줄")과 본문 2곳("우리는 **424줄**", "**424 → 196줄 · 21,236 → 10,917 토큰(-49%)**")에서 424/196 을 주장하고, 같은 본문이 "전건 복원했다(표 셀 안에 넣어 줄 수는 195줄 유지)" 로 195 를 병기한다 — 한 커밋 메시지가 같은 파일에 196 과 195 를 동시 주장. 커밋 첫 섹션이 "측정 규율 4(단위 명시)를 또 어겼고 사용자가 잡았다" 인 만큼 동일 결함 클래스의 즉시 재발이라는 판정도 성립한다(AGENTS.md:110 §측정 규율 규칙 1·4).

주장보다 넓은 사실 2건 추가 확인: (1) 전파

### [decision] '세션16 종료' 를 선언한 뒤에도 같은 세션 라벨로 이력이 계속 append 돼 세션 경계가 기록에서 소실됐다

- **위치**: `docs/STATE.md:287`
- **주장**: #1290 은 제목이 'docs(state): 세션16 종료 trailing sync' 이고 2026-08-04T23:32:26Z 에 머지됐다. 그럼에도 docs/STATE.md:285~287 에 '세션16 6차'(#1293) · '세션16 7차'(#1294) · '세션16 8차'(#1294·#1295) 3건이 2026-08-05~06 작업으로 계속 추가됐다. 정책 5(사이클 종료 신호 명시) 관점에서 종료 선언이 기록상 무효화됐고, 회고 범위 산정(정책 8 진화 (5) = '직전 회고 이후 머지 PR + 본 세션 산출물 전체', scripts/retro_scope.py)과 카덴스 판단('≥3 세션') 이 읽을 세션 경계가 문서에서 사라졌다.
- **근거**: PR #1290 제목 '세션16 종료 trailing sync — 6832 + R7 종결 + R52 신설' (mergedAt 2026-08-04T23:32:26Z) · docs/STATE.md:285 (세션16 6차 = #1293) · docs/STATE.md:286 (세션16 7차 = #1294) · docs/STATE.md:287 (세션16 8차) — 전부 2026-08-05~06 실측 표기
- **처방**: '종료' 라벨을 쓴 trailing sync 이후의 작업은 세션 번호를 증가시킨다(세션17 1차…). 또는 '종료' 어휘를 trailing sync 제목에서 빼고 세션 경계는 SessionStart 훅이 남기는 기계 신호로만 확정한다.
- **판정**: `CONFIRMED` — 관측 사실은 전량 실측 일치하나, 주장된 피해 기전은 반증됨 — P2 유지하되 사유를 정정해야 함.

[검증된 사실]
- PR #1290 제목 'docs(state): 세션16 종료 trailing sync — 6832 + R7 종결 + R52 신설 (#1288·#1289)', state=MERGED, mergedAt=2026-08-04T23:32:26Z — 인용 그대로 일치.
- docs/STATE.md:285 = '세션16 6차'(#1293), :286 = '세션16 7차'(#1294), :287 = '세션16 8차'(#1294·#1295) — 작업 브랜치(docs/claude-md-under-200)에서 인용 line 번호 정확히 일치. main 에서도 세션16 6차(#1293, 2026-08-05 머지)가 :285 에 존재 → 종료 선언 이후 append 는 main 에서도 실재.
- 경미한 부정확: 인용은 '2026-08-05~06' 이라 했으나 285~287 3건은 전부 '실측 2026-08-06' 표기(2026-08-05 는 :284 세션16 5차). 비물질적.

[반증된 부분 — 회고 리포트에 이 사유를 그대로 실으면 안 됨]
근거가 든 하류 

### [tooling] main 의 red 는 설계상 상시화돼 있다 — enforce-on-push 테스트수 대조 × 6-step ⑤ trailing-sync 이월의 구조적 충돌

- **위치**: `.github/workflows/ci.yml:395`
- **주장**: `check_test_count_sync` 가 PR 에서는 advisory, main push 에서는 enforce 다. 그런데 CLAUDE.md 6-step ⑤ 는 STATE/배지 갱신을 별도 trailing sync PR 로 **이월하라**고 지시한다. 두 규칙이 겹치면 코드 PR 이 머지되는 순간부터 trailing sync 가 들어올 때까지 main 은 **반드시** red 다. 상시 red 는 경보 둔감화를 만들고, 실제로 그 둔감화가 위 P0(E2E 진짜 회귀 5연속 방치)의 은폐 경로였다.
- **근거**: `.github/workflows/ci.yml:391-397` — `if: github.event_name == 'pull_request'` → `--advisory-drift`, `if: github.event_name == 'push'` → enforce. 실측: main run `30958062601`(762e90ba)과 `30958997970`(02b3e867)의 실패 step 이 정확히 `테스트 수치 ↔ 실측 대조 (main push — enforce)` 였다(`gh run view --jq '.jobs[]|select(.conclusion=="failure")'`). 즉 최근 red 6건 중 2건이 '설계된 red' 이고 5건이 '진짜 회귀' 라 두 신호가 같은 색으로 섞여 있다. CLAUDE.md 6-step ⑤ 이월 분기가 이 상태를 매 코드 PR 마다 재생산한다.
- **처방**: 세 안 중 택1을 사용자 결정으로: (a) main enforce 를 제거하고 trailing sync PR 의 PR-diff 축에서 enforce (b) enforce 를 유지하되 '이월 창' 을 허용하는 유예(예: 직전 N 커밋 내 sync 존재 시 통과) (c) `--fix` 파생이 이미 있으므로 코드 PR 이 ⑤ 를 자체 수행하도록 이월 분기를 폐지. 어느 쪽이든 **'main red = 항상 조사 대상'** 이 성립해야 P0 재발이 막힌다.
- **판정**: `SEVERITY_ADJUST` — 인용 전량 실측 확인. ci.yml:391-397 이 정확히 주장대로 존재(PR→`--advisory-drift`, push→bare enforce), CLAUDE.md:145 이월 분기 존재, 인용된 두 run(30958062601/762e90ba, 30958997970/02b3e867)의 실패 step 이 정확히 `테스트 수치 ↔ 실측 대조 (main push — enforce)`. 기전도 실증됨: #1289·#1288 이 enforce red 로 머지 → trailing sync #1290(cb2d9657, run 30960334484)에서 enforce step 통과로 해소(E2E 만 잔존). `git log docs/STATE.md` 상 최근 trailing sync PR 7건 = 이월 분기가 예외가 아니라 상시 경로. 여기까지는 CONFIRMED.

그러나 P1 은 과대. 3가지 근거로 P2 조정:

(1) "반드시 red" 는 조건부다. (a) 해당 PR 이 수집 테스트 수를 바꾸고 (b) CLAUDE.md:145 의 이월 분기가 발동(= STATE 동일 파일 touch 미머지 PR ≥1건 in-flight)해야 성립. docs-only·conf

### [tooling] CLAUDE.md 슬림화가 문서 심의 게이트의 근거를 절반으로 줄였다 — 외부화된 정책 detail 은 게이트가 읽지 않는다

- **위치**: `.claude/hooks/doc_review_gate.py:630`
- **주장**: `doc_review_gate.py` 는 심의 에이전트 컨텍스트로 CLAUDE.md·AGENTS.md·STATE.md 만 읽는다. 이번 창 HEAD 커밋이 CLAUDE.md 를 35,834 → 15,830자로 줄이고 정책 detail 을 `.claude/policies/active.md` 로 이관했는데, 게이트의 `_CONTEXT_SOURCES` 는 갱신되지 않았다. 게이트는 `.claude/policies/*.md` 를 **심의 대상(important)** 으로는 잡으면서 **근거로는 읽지 않는다**. 즉 심의자가 판정 기준의 절반을 잃었고, 이는 R37 이 이미 한 번 고쳤던 '심의자를 규칙에 대해 눈멀게 하는' 결함의 재발이다.
- **근거**: `.claude/hooks/doc_review_gate.py:629-640` `_CONTEXT_SOURCES = (("CLAUDE.md", 40000), ("AGENTS.md", 12000), ("docs/STATE.md", 16000))` — `.claude/policies/**`·`.claude/rules/**` 없음. :630 주석은 `# 27.8k — 전문 (정책 1~19 가 여기 있다)` 인데 실측 `CLAUDE.md` = 15,830자이고 정책 1~19 의 detail 은 `.claude/policies/active.md`(24,030자)·`history.md`(9,595자)로 이동했다(`git show faeb2cf1:CLAUDE.md | wc` = 35,834자 → 현재 15,830자). 반면 :56 `r"^\.claude/policies/[^/]+\.md$"` 로 그 파일들은 important 등급 심의 대상이다. 부수: `AGENTS.md` 는 예산 12,000 대비 실측 10,178자(85%)라 조금만 더 커지면 조용히 잘린다(라벨은 붙지만 근거는 준다).
- **처방**: `_CONTEXT_SOURCES` 에 `.claude/policies/active.md` 를 안정 블록으로 추가한다(캐시 프리픽스에 적합 — 거의 안 바뀐다). CLAUDE.md 축소분(-20,004자)과 거의 상쇄되므로 순비용 증가는 미미하다. 함께 :630-631 주석의 실측 수치를 갱신하고, AGENTS.md 예산을 16,000 으로 올린다. 회귀 가드: 정책 detail 원천이 컨텍스트에 실재하는지 단언(현재 어떤 테스트도 '무엇이 근거로 들어가는가' 를 고정하지 않는다).
- **판정**: `SEVERITY_ADJUST` — 코드 인용은 전건 실측 일치, 그러나 서사(재발·절반·조용히)는 3중으로 과장돼 P1 근거가 서지 않는다. P2로 강등.

[실측 확인된 것]
- `doc_review_gate.py:629-640` `_CONTEXT_SOURCES` = ("CLAUDE.md",40000)/("AGENTS.md",12000)/("docs/STATE.md",16000) 3종뿐, `.claude/policies/**`·`.claude/rules/**` 없음 ✅
- `:630` 주석 `# 27.8k — 전문 (정책 1~19 가 여기 있다)` 실재 ✅ 현재 두 절 모두 거짓
- `:56` `r"^\.claude/policies/[^/]+\.md$"`(important) ✅ + 미인용 보강: `:33` `.claude/rules/[^/]+\.md$` 는 `_CRITICAL` — 비대칭은 주장보다 오히려 강함
- 실측 자수: CLAUDE.md 15,830 / active.md 24,030 / history.md 9,595 / AGENTS.md 10,178 — 전부 정확 ✅
- `_call_single_agent` 의 `messages.create` 에 `tools=` 없음 → 에이전트는 

### [tooling] E2E job 의 런타임 추정치가 실측 대비 ~6배 과대 — 이번 창이 스스로 지목한 '검증 안 된 측정치 발행' 클래스

- **위치**: `.github/workflows/ci.yml:507`
- **주장**: ci.yml 이 E2E 소요를 *"실측 ~10초/건 → 122건 ≈ 20분"* 으로 적고 `timeout-minutes: 30` 을 그 근거로 설정했다. 실제 CI 실측은 3분 10초다. 과대 추정 자체는 안전 방향이지만, 근거 없는 숫자가 타임아웃·required 승격 판단·비용 논의의 입력값으로 남는다 — HEAD 커밋 본문이 *"1회용 측정 도구의 숫자를 검증 없이 사실로 발행"* 을 이번 창 3회차 결함으로 자백한 바로 그 클래스다.
- **근거**: `.github/workflows/ci.yml:507-508` `# 실측 ~10초/건 → 122건 ≈ 20분. 여유 포함 30분에서 자른다.` / `timeout-minutes: 30`. 실측(`gh run view 31025178170 --json jobs`): `E2E (Playwright)` startedAt `2026-08-05T16:25:41Z` → completedAt `16:28:51Z` = **3분 10초**(설치 스텝 포함, 전체 CI wall-clock 5분 46초). CLAUDE.md:22 가 *"측정 도구를 검증하지 않고 그 숫자를 사실로 발행"* 을 반복 결함 3위로 등재.
- **처방**: 주석의 추정치를 실측(3~4분)으로 정정하고 타임아웃을 10~15분으로 조인다(현행 30분은 셀렉터 교착 시 진단을 30분 지연시킨다). 더 중요하게는, ci.yml:499 가 *"실행 이력이 없어 flakiness 를 모른다"* 며 미룬 required 승격 판단이 이제 실행 이력(6 run)을 확보했으므로 승격 여부를 사용자 결정 항목으로 올린다 — 위 P0 는 정확히 이 non-required 상태가 만든 사고다.
- **판정**: `CONFIRMED` — CONFIRMED — live, in-class, and the underlying error is larger than claimed.

CITATION (exact): ci.yml:507 `# 실측 ~10초/건 → 122건 ≈ 20분. 여유 포함 30분에서 자른다.` / :508 `timeout-minutes: 30`. Verified at HEAD (7ab96205).

INDEPENDENT RE-MEASUREMENT (did not trust the finder): `gh api .../runs/31025178170/jobs` → E2E job 16:25:41Z→16:28:51Z = 3m10s, matching the finder. Going further to step level, which the finder did not: `Run E2E suite` alone = 16:26:49Z→16:28:48Z = **1m59s**; the other ~71s is pip/node/playwright install.

ORIGIN FOUND (the decisive evidence): commit 02b3e867 (#1288) body states *"실측

### [tooling] 신설 CSP↔템플릿 정합 가드가 자기 정규식이 선언한 3 디렉티브 중 style-src 하나만 검사한다

- **위치**: `tests/unit/ui/test_csp_external_asset_parity.py:37`
- **주장**: 이번 창이 만든 CSP 정합 가드는 `style-src|font-src|script-src` 를 캡처하는 정규식을 두고도 외부 스타일시트(`<link rel=stylesheet>`) 축만 단언한다. 외부 `<script src="https://…">` 와 CSS 내 `@import url(https://…)` 는 같은 '앱이 자기 자산을 자기 CSP 로 차단' 결함을 만들지만 관측되지 않는다. 14개월간 숨었던 결함 클래스를 1/3 만 봉인한 상태다.
- **근거**: `tests/unit/ui/test_csp_external_asset_parity.py:37` `_CSP_DIRECTIVE = re.compile(r'"(style-src|font-src|script-src)([^"]*)"')` — 그러나 검사 테스트는 `test_no_template_loads_a_stylesheet_the_csp_blocks` 하나뿐이고 탐지 정규식 `_EXTERNAL_STYLESHEET`(:31) 는 `rel="stylesheet"` 만 매칭한다. `test_csp_directives_are_actually_read` 는 script-src 를 읽지 않는다. 현재 실제 위반은 0(`grep -rn 'src=["'\'']https\?://' src/templates/` 무결과)이라 즉시 피해는 없고 잠재 사각이다.
- **처방**: `<script ... src="https?://…">` ↔ `script-src`, CSS 의 `@import url(https?://…)` ↔ `style-src` 축을 같은 형태로 추가하고, 각 축에 `test_guard_is_not_vacuous` 와 같은 대조군을 붙인다(현재 대조군은 스타일시트 축에만 있다).
- **판정**: `CONFIRMED` — 실경로 뮤테이션으로 사각을 실증했다. 인용 :37 은 정확 일치 — `_CSP_DIRECTIVE = re.compile(r'"(style-src|font-src|script-src)([^"]*)"')`. `_EXTERNAL_STYLESHEET` 는 :31 이 아니라 :33(주석이 :32) 로 2줄 drift 이나 심볼·행동(rel="stylesheet" 만 매칭) 은 정확.

핵심 증거 3건: (1) `grep -rn _csp_allows_external` 결과 호출처는 "style-src"(:52,:89)·"font-src"(:90) 뿐 — **script-src 는 어떤 호출자도 전달하지 않는 죽은 alternation 분기**다(정규식 리터럴만 선언, 기능 0). (2) 템플릿 대조 parity 단언은 `test_no_template_loads_a_stylesheet_the_csp_blocks` 하나뿐이고, 타 가드도 이 축을 안 덮는다 — `tests/unit/test_main.py:681` 은 헤더 *존재*만 단언(크로스파일 대조 아님). (3) 결정적 뮤테이션: `src/templates/base.html` 에 `<script src="https:

### [tooling] CLAUDE.md 규칙 매트릭스 서두가 '10 카테고리' 로 남아 실제 11 파일과 어긋난다

- **위치**: `CLAUDE.md:175`
- **주장**: `.claude/rules/docs.md` 가 직전 PR(#1293)에서 추가돼 규칙 파일이 11개가 됐고 매트릭스 표에도 11행이 있는데, 표 바로 위 서술만 여전히 *"10 카테고리"* 다. path-scoped rules 는 자동 로드 대상이라 카운트 서술이 Claude 의 '전부 봤다' 판정에 쓰이며, 기존 커버리지 가드는 파일↔매트릭스 등재만 보고 카운트 서술은 보지 않아 영원히 초록이다.
- **근거**: `CLAUDE.md:175` `> **사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 …`. 실측 `ls .claude/rules/` = api·db·deploy·**docs**·guards·i18n·pipeline·security·services·testing·ui = **11개**. 매트릭스 표는 11행(문서/원장 docs.md 포함). 가드 `tests/unit/scripts/test_rules_and_index_coverage.py:106,128` 은 area↔매트릭스 등재만 단언하고 카운트 문자열은 검사 대상 밖.
- **처방**: 서술을 '11 카테고리(2026-08-05 docs 추가)' 로 정정한다. 근본 시정은 카운트를 산문에 두지 않는 것 — 매트릭스 행 수에서 파생하거나 카운트 서술 자체를 제거한다(같은 정수를 두 곳에 손유지하는 패턴은 이번 창 문서 감사 P0-3 이 이미 지목했다).
- **판정**: `CONFIRMED` — 3-leg 실측 전부 재현됨 (추측 아님).

(1) 인용 정확 — `F:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager\CLAUDE.md:175` = `> **사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 ...`. `grep -n "카테고리" CLAUDE.md` 히트는 173(헤딩)·175(본 서술) 단 2건이며 175 가 문제의 줄.

(2) 실측 불일치 확인 — `ls .claude/rules/` = api·db·deploy·**docs**·guards·i18n·pipeline·security·services·testing·ui = **11개**. `CLAUDE.md:177~189` 매트릭스 표도 **11행**(마지막 행 `| 문서 / 원장 | docs.md (docs/**, README.md, README.ko.md, CLAUDE.md, AGENTS.md) |`). 즉 표는 갱신됐고 표 바로 위 서술만 10 으로 남았다. `git log -- .claude/rules/docs.md` = `faeb2cf1 ... (#1293)` 단일 커밋 → 주장한 "직전 PR #1293 에서 추가" 도 사실.

### [E2E 게이트 관측자 무결성 (observer-integrity)] _seed_repo 의 무주석 `except Exception: pass` — 시드 실패가 빨강이 아니라 '빈 상태 페이지' 로 강등된다

- **위치**: `e2e/conftest.py:323`
- **주장**: `_seed_repo()` 는 webhook POST 를 `try/except Exception: pass` 로 감싸 실패를 통째로 삼킨다(`:312-324`). 서명 불일치·서버 미준비·라우트 변경 어느 쪽이든 repo 가 DB 에 안 생기고, 이어지는 `UPDATE` 는 0행에 적용된 뒤 `seeded_page` 테스트는 **빈 상태 페이지**를 받는다. R53 이 실측한 대로 e2e 다수가 `page.content()` 부분문자열(예: nav 로고 `"SCAManager"`) 단언이라 그 상태에서도 초록이 난다 — P0-1 보다 조용한 형태의 같은 공허화다.
- **근거**: (1) `grep -n "except Exception" e2e/conftest.py` → `:186`(health 폴링, 재시도 루프라 정당) · `:323`(`_seed_repo` webhook POST — 삼킨 뒤 `:325 time.sleep(0.3)` 로 진행). (2) 둘 다 설명 주석이 없어 `test_empty_except_guard.py` 의 CodeQL parity 기준(except~pass 구간 주석 존재)을 만족하지 못하나, 같은 파일 `:23` `_SCOPED_DIRS` 가 e2e 를 제외해 **한 번도 검사된 적이 없다**. (3) 실패 파급의 비대칭 — `_seed_analysis` 는 같은 상황에서 `RuntimeError("_seed_repo must be called before _seed_analysis")`(`:374`) 로 loud fail 하는데, `seeded_page`(`:338-360`) 경로만 silent 하다. 즉 같은 conftest 안에서 fail-closed 와 fail-open 이 공존한다. (4) `docs/backlog.md:53` (R53) 이 *"통과 91건은 감사된 적이 없다 — 찾아본 곳마다 공허한 초록이 나왔다"* 로 substring 단언 문제를 이미 기록 — 시드 무음 실패는 그 기저율을 키우는 상류 원인이다.
- **처방**: `:313-324` 의 POST 를 `resp = requests.post(...); resp.raise_for_status()` 로 바꾸고 `except` 는 제거하거나 `pytest.fail(f"E2E 시드 실패: {exc}")` 로 승격 — 시드는 전제 조건이지 best-effort 가 아니다. 추가로 `UPDATE ... WHERE full_name=...` 의 `rowcount == 1` 을 단언해 '0행 갱신' 을 red 로 만든다. `:186` 은 재시도 루프라 유지하되 마지막 예외를 보관해 `:193` 실패 메시지에 실어 진단 가능하게 한다(P0-1 조치와 동일 커밋).
- **판정**: `CONFIRMED` — 인용 전건 실측 일치. `e2e/conftest.py:299 _seed_repo` → `:312 try:` / `:323 except Exception:` (핸들러 본문 `pass`, 설명 주석 0) / `:325 time.sleep(0.3)` / `:333-336` 후속 `UPDATE ... WHERE full_name='owner/testrepo'` (rowcount 미확인) / `:338-339 seeded_page` / `:374 RuntimeError("_seed_repo must be called before _seed_analysis")` — 즉 같은 파일 안에 fail-closed(_seed_analysis)와 fail-open(_seed_repo)이 공존한다는 비대칭 주장은 참. 가드 사각도 참: `tests/unit/scripts/test_empty_except_guard.py:23 _SCOPED_DIRS = ("scripts", ".claude/hooks")` 라 `e2e/` 는 한 번도 스캔된 적이 없고, 리포에 CodeQL path 설정 파일도 없다. `docs/backlog.md:53` R53 존재 확인. 영향 표면도 실측: `see

### [test-harness / fail-open] seeded_page 시드가 fail-open — 웹훅 실패를 삼키고 UPDATE 0행도 성공으로 취급 (57+ 테스트 전제 무검증)

- **위치**: `e2e/conftest.py:323`
- **주장**: `e2e/conftest.py` 의 `_seed_repo` 는 시드용 push 웹훅 POST 를 `try/except Exception: pass` 로 감싸 **모든 실패를 삼킨다**(:323-324). 이어지는 `UPDATE repositories SET user_id=:uid WHERE full_name=:fn` 은 **rowcount 를 확인하지 않으므로**(:332-334) 0행 매칭이어도 조용히 commit 된다. 결과: 웹훅 서명 규약 변경·파이프라인 회귀·`time.sleep(0.3)`(:325) 레이스 중 어느 것이든 발생하면 `seeded_page` 는 **레포가 없는 빈 DB** 위에서 정상 fixture 로 반환된다. 이 fixture 에 의존하는 테스트는 57건(`grep -c` 기준 파일별 참조 다수)이고, 그중 '부재'·nav 수준 콘텐츠만 단언하는 것들은 시드 붕괴를 못 보고 초록으로 남는다. 리포는 다른 곳에서 이 패턴을 명시 금지한다 — `e2e/test_theme_mobile_guards.py:127` 주석: *"fail-fast — 셀렉터 미존재 = 페이지 구조 회귀 (silent skip 금지, 사이클 157 #9)"* — 정작 **모든 시드의 뿌리**에는 적용되지 않았다.
- **근거**: 정책 6 실측: `grep -n "except Exception" e2e/conftest.py` → `186`(서버 폴링 — 정당) · `323`(시드 POST — 문제). `sed -n '320,336p' e2e/conftest.py` 로 `except Exception: pass` 직후 `time.sleep(0.3)` → `UPDATE ... WHERE full_name=:fn` → `conn.commit()` 확인, rowcount 검사 없음. `_seed_repo` 정의는 `e2e/conftest.py:299`. `seeded_page` fixture 는 `:339` 에서 `_seed_repo(live_server, db_path)` 를 호출하며 반환값·예외를 검사하지 않는다. 참조 실측: `grep -rn "def test_.*seeded_page\|def test_.*perf_seeded" e2e/*.py | wc -l` → **57**.
- **처방**: `_seed_repo` 에서 (a) POST 응답 status 를 단언하고 (b) `result.rowcount == 1` 을 단언한다. 시드 실패는 skip 이 아니라 **에러**여야 한다 — 시드가 깨지면 그 위의 57건 초록은 전부 무의미하기 때문. 회귀 가드: 웹훅 시크릿을 일부러 틀리게 한 뮤테이션에서 fixture 가 red 를 내는지 실증.
- **판정**: `SEVERITY_ADJUST` — 코드 결함 자체는 실재하고 인용은 전부 정확히 재확인됨: e2e/conftest.py:323-324 `except Exception: pass` (시드 웹훅 POST — :186 서버 폴링은 정당), :332-334 `UPDATE ... WHERE full_name=:fn` + `conn.commit()` rowcount 미검사, `_seed_repo`=:299, `seeded_page`=:339 (반환값·예외 미검사), seeded_page 의존 테스트 57건, test_theme_mobile_guards.py:127 fail-fast 주석 인용 일치. e2e 는 CI 실행됨(.github/workflows/ci.yml:546).

그러나 P1 을 지탱하는 핵심 전제 — "시드 붕괴 시 57건이 조용히 초록" — 은 실측으로 반증됨(56/57 이 loud fail):
(1) src/main.py 에 HTTP 예외 핸들러가 없음(:293 RateLimitExceeded 뿐) → get_repo_or_404(src/api/deps.py:12)가 nav/폼/타이틀 없는 순수 JSON 404 를 반환. 따라서 repo-scoped 이동은 전부 단언 실패 — tes

### [e2e-vacuity] '부재' 단언(not_to_be_visible)은 셀렉터가 아예 없어도, 페이지가 404 여도 통과 — 뮤테이션 확정

- **위치**: `e2e/test_repos_mode.py:108`
- **주장**: `e2e/test_repos_mode.py:108` 의 `expect(page.locator(".repos-report")).not_to_be_visible()` 는 `.repos-report` 가 **리네임되거나 완전히 삭제돼도**, 심지어 페이지 자체가 404 여도 통과한다. 이 테스트가 지킨다고 적힌 명제(*"Repo 미선택 시 레포트 섹션이 없어야 한다"*)는 대조군 없이는 검증 불가다 — repos 모드 기능을 통째로 지워도 초록. R53 이 범위 후보로 지목한 `not_to_be_visible`(요소 부재도 통과) 축의 실제 인스턴스이며, 현재 스위트에 1건 존재한다.
- **근거**: 정책 6 실측: `grep -rn "not_to_be_visible" e2e/*.py` → 유일 매칭 `e2e/test_repos_mode.py:108`. **뮤테이션 실행 2건**(임시 프로브, 실행 후 삭제): (1) 앱에 존재한 적 없는 셀렉터 `.selector-that-never-existed-anywhere` 에 동일 단언 → pass; (2) 404 라우트에서 `.repos-report` 부재 단언 → pass. 결과 `2 passed`. 대조 실험으로 rigor 확보: 같은 파일군의 `e2e/test_overview_score.py:66,75,119,162` 가 쓰는 `not_to_have_text("0/100")` 는 존재하지 않는 셀렉터에 적용하면 **red**(`AssertionError: ... element(s) not found`) — 즉 모든 부정 단언이 공허한 것은 아니며, 공허한 것은 `not_to_be_visible` 계열이다. `test_repos_mode.py` 는 `#1291` 변경 파일 목록에 **없다**(git show --stat 실측).
- **처방**: 부재 단언에 **대조군**을 붙인다 — 같은 테스트에서 `.repos-kpi-grid`(그 화면에 반드시 있어야 하는 요소)의 가시성을 먼저 단언한 뒤 `.repos-report` 부재를 단언하면, 페이지가 깨졌을 때 red 가 된다. `#1291` 이 preset 공허 가드에 적용한 '대조군' 처방과 동일 패턴을 이 파일에도 이식.
- **판정**: `SEVERITY_ADJUST` — 인용 재확인 OK. `grep -rn "not_to_be_visible" e2e/ tests/` → 유일 매칭 `e2e/test_repos_mode.py:108` = `expect(page.locator(".repos-report")).not_to_be_visible()`. "스위트에 1건" 카운트도 정확.

기전은 내가 독립 뮤테이션으로 재현했다 (finder 보고를 신뢰하지 않고 별도 Playwright 프로브 4종 실행): (A) 존재한 적 없는 셀렉터 → PASS, (B) 404 문서 → PASS, (D) 대조 `not_to_have_text` 는 부재 셀렉터에 RED. 즉 A/B/D 3건 모두 finder 보고와 일치 — `not_to_be_visible` 의 detached=not-visible 공허성은 실재하며 추측이 아니다.

그러나 finder 가 **실행하지 않은 프로브 C** 가 영향 주장을 무너뜨린다. (C) `.repos-report` 가 실제로 렌더돼 visible 인 페이지에 동일 단언 → **RED**. 즉 이 테스트가 지킨다고 적힌 명제(*"Repo 미선택 시 레포트 섹션이 없어야 한다"*)의 **1차 회귀 — 템플릿 `{% i

### [docs-claim] '1 skip' 은 일시적 skip 이 아니라 사이클 93 사유의 영구 skip — 배지 문구가 전이성을 함의한다

- **위치**: `e2e/test_settings.py:398`
- **주장**: 배지의 `(120 pass / 1 skip)` 에서 그 1건은 `e2e/test_settings.py:398` 의 `@pytest.mark.skip` 이며, 사유는 사이클 81/82/84 의 settings.html 진화로 '2열 데스크탑' 전제가 무효화됐다는 것이고 **재활성화 트리거는 "다수 자식 grid 인스턴스 도입 시 (UX 결정)"** — 즉 도래하지 않을 수도 있는 조건이다. 사용자 대면 문자열에서 'skip' 은 통상 flaky·일시 보류를 함의하는데, 실제로는 **검증 영역이 소멸해 영구 사장된 테스트**다. 121 을 분모로 쓰는 순간 이 1건은 '곧 초록이 될 것' 처럼 계상되지만, 실질 검증 모수는 120 이다.
- **근거**: 정책 6 실측: `grep -rn "skip" e2e/ | head` → `e2e/test_settings.py:398:@pytest.mark.skip(`. CI 로그 실측(run 31025178170, E2E job): `SKIPPED [1] e2e/test_settings.py:398: 사이클 81/82/84 settings.html 진화 후 ... 재활성화 시점 = 다수 자식 grid 인스턴스 도입 시 (UX 결정).` 및 요약행 `120 passed, 1 skipped, 2 warnings in 118.48s`. 배지 문자열 실측: `README.md:22` `(120_pass_%2F_1_skip)`.
- **처방**: 둘 중 하나 — (a) 검증 영역이 실제로 소멸했으면 테스트를 **삭제**하고 사유를 커밋 본문/`docs/cycle-history.md` 에 남긴다(영구 skip 은 collect 비용만 남기고 계상만 왜곡한다), 또는 (b) 남기려면 배지 분모를 120 으로 하고 skip 은 배지에서 빼되 `docs/STATE.md` 에 '영구 skip 1건(사이클 93 사유, UX 결정 대기)' 으로 명시.
- **판정**: `CONFIRMED` — 인용 2건 실측 확인. (1) `e2e/test_settings.py:398` = `@pytest.mark.skip(` 존재, 사유 문구가 인용과 정확히 일치하며 `재활성화 시점 = 다수 자식 grid 인스턴스 도입 시 (UX 결정)` 포함. `grep -rn "skip" e2e/` 결과 conftest 서버기동 가드(`e2e/conftest.py:193`) 외 유일한 skip 마커. (2) `README.md:22` = `E2E-121_in_CI_(120_pass_%2F_1_skip)`. 동일 서술이 `README.ko.md:22` · `docs/STATE.md:32` · `docs/runbooks/operational-smoke-checks.md:209` 4곳.

산문이 아니라 전제 자체를 독립 재검증했다: `src/templates/settings.html:376` 이 `.settings-grid:has(> .s-card:only-child) { grid-template-columns: 1fr; }` 를 두고, 3개 `.settings-grid` 인스턴스(667·850·898)의 직계 `.s-card` 자식이 각각 **1개**(668·851·899). 

### [e2e-vacuity] '빈 상태 메시지' 를 검증한다고 적힌 테스트가 nav 로고 문자열만 단언한다

- **위치**: `e2e/test_navigation.py:17`
- **주장**: `e2e/test_navigation.py:10-17` `test_overview_empty_state` 의 docstring 은 *"레포가 없을 때 빈 상태 메시지가 표시되어야 한다"* 인데 실제 단언은 `assert "SCAManager" in content` 한 줄뿐이다. `SCAManager` 는 nav 로고·`<title>` 에 항상 존재하므로 **empty-state 마크업을 전부 삭제해도 초록**이다. 게다가 인라인 주석 자체가 *"레포가 없는 경우 empty-state 표시 ... 또는 테이블이 있는 경우 테이블이 표시"* 라고 양쪽을 다 허용한다고 적어, 이 테스트가 아무 명제도 배제하지 않음을 스스로 문서화하고 있다. R53 이 인용한 바로 그 사례이고, `#1291` 이 이 파일을 건드리지 않아 **현재도 그대로다**.
- **근거**: 정책 6 실측: `sed -n '10,18p' e2e/test_navigation.py` 로 docstring·주석·단언 전문 확인. `grep -rn "in .*content" e2e/*.py` 결과 `e2e/test_navigation.py:17: assert "SCAManager" in content` 가 유일한 nav-로고 폴백 단언. 같은 클래스의 다른 사례(`test_six_card_titles_present` 가 한국어 HTML 주석에 매칭돼 통과)는 `#1291` 에서 이미 적발·수정됐으나(`e2e/test_settings.py:420~` docstring 에 사고 기록 보존), navigation 축은 미이행.
- **처방**: empty-state 전용 셀렉터(예: `.empty-state`)를 직접 단언하거나, 레포 유무 분기를 명시해 두 경로를 각각의 테스트로 분리한다. `page.content()` 부분문자열 매칭은 템플릿 주석·`<title>`·`aria-label` 에 걸려 통과하므로 이 스위트에서 금지 패턴으로 `.claude/rules/testing.md` 에 등재 권장(R53 범위 후보 `page.content()` 부분문자열 전수 15건).
- **판정**: `CONFIRMED` — 인용 전문 일치 확인 (e2e/test_navigation.py:10-17, Read 실측). docstring "레포가 없을 때 빈 상태 메시지가 표시되어야 한다" ↔ 실제 단언 `assert "SCAManager" in content` (:17) 한 줄. 공허성 정적 증명: src/templates/base.html:14 `<title>{% block title %}SCAManager{% endblock %}</title>` + :637 `<strong>SCAManager</strong>` (nav-logo `<a>` 내부, :642 `{% if current_user %}` 가드 **바깥** — 무조건 렌더). page.content() 는 <head> 포함 전문 반환 → base.html 파생 어떤 페이지든 통과. empty-state 마크업 전삭제 시에도 초록 = 확정.

추가 발견 (주장 강화): `grep -n "empty" src/templates/overview.html` 결과 4줄뿐 — :142/:146/:147 은 `.ov-empty-state`/`.ov-empty-icon` **CSS 규칙**, :192 는 `overview.title_

### [docs-claim / naming-drift] OTP 테스트 이름·docstring 이 하드닝 이전 값(6자리)을 그대로 주장한다 — 자기참조는 고쳤으나 이름은 남았다

- **위치**: `e2e/test_settings.py:253`
- **주장**: `#1291` 이 Grok `019fce` 지적을 받아 OTP 기대값의 자기참조(앱 상수 import 를 기대값으로 사용)를 리터럴 `_EXPECTED_OTP_LENGTH = 8` 로 고정해 고쳤다. 그런데 함수명 `test_telegram_otp_issue_shows_six_digit_code` 와 docstring *"6자리 숫자 OTP가 화면에 표시되어야 한다"* 는 **여전히 6** 이다. `#895` 는 brute-force 공간 100배를 위해 6→8 로 올린 **보안 하드닝**이고, 파일 상단 주석(:9)이 그렇게 적고 있다. 테스트 이름을 근거로 OTP 자릿수를 판단하는 다음 세션/리뷰어는 보안 하드닝을 역행시킬 수 있다 — 실제 단언은 8을 강제하므로 즉시 red 가 나겠지만, 그 red 의 원인을 '테스트 이름과 다르다' 로 오독할 여지가 크다.
- **근거**: 정책 6 실측: `grep -n "six_digit\|6자리" e2e/test_settings.py` → `253: def test_telegram_otp_issue_shows_six_digit_code(seeded_page, base_url):` · `254: """'연결 코드 발급' 버튼 클릭 시 6자리 숫자 OTP가 화면에 표시되어야 한다.` 반면 `grep -n "_EXPECTED_OTP_LENGTH" e2e/test_settings.py` → `15: _EXPECTED_OTP_LENGTH = 8` · `267: assert len(otp_text) == _EXPECTED_OTP_LENGTH` · `272: assert _OTP_LENGTH == _EXPECTED_OTP_LENGTH`. 파일 상단 `:9` 주석: *"OTP 자릿수 = **8** (#895 b2bdfe8, C12 보안 하드닝 — 6→8 로 brute-force 공간 100배)"*.
- **처방**: 함수명을 `test_telegram_otp_issue_shows_eight_digit_code` 로, docstring 을 '8자리' 로 정정한다(정책 16 가독성 — 이름이 곧 명제다). 동일 클래스 점검: 하드닝·상수 변경 PR 이 테스트 **이름**까지 갱신했는지 확인하는 항목을 `.claude/rules/testing.md` 에 1줄 추가.
- **판정**: `CONFIRMED` — 인용 전건 재실측 일치. `e2e/test_settings.py:253` `test_telegram_otp_issue_shows_six_digit_code` + `:254-255` docstring("6자리 숫자 OTP" / "6-digit numeric OTP")가 working tree·`origin/main` 양쪽에 그대로 존재하고, 같은 파일 `:15` `_EXPECTED_OTP_LENGTH = 8` · `:267` `assert len(otp_text) == _EXPECTED_OTP_LENGTH` · `:272` `_OTP_LENGTH` 교차확인 · `:9` 헤더 주석("OTP 자릿수 = **8** (#895 b2bdfe8, C12 보안 하드닝 — 6→8)")도 축자 일치. 앱 실체 `src/api/users.py:33 _OTP_LENGTH = 8` 확인 — 이름/docstring 만 8과 모순된다.

finder 가 대지 않은 결정적 보강 2건을 독립 확보: (1) `git blame -L 253,255` → 세 줄 모두 `82fea1996`(2026-04-26) = **#895 하드닝 이전** 산물이고, `#1291`(`5b72c438`)은 같은

### [policy/process] 정책 17 원칙 3/4 는 집행면이 0 — 코드의 '정책 17' 인용 12곳이 전부 원칙 1(안정성=비차단)이고, 저자를 구속하는 원칙 3/4 를 인용한 가드는 하나도 없다

- **위치**: `CLAUDE.md:90`
- **주장**: 정책 17 은 '문서 정리'라는 활동 클래스의 지배 정책인데, 그 안에서 비차단을 정당화하는 원칙 1 만 기계면에 반복 인용되고 저자에게 절차를 요구하는 원칙 3(단계 분할 + 5+1 회의 + 옵션 표)·원칙 4(High tier 사전 확인)는 어떤 스크립트·훅·테스트·CI 에도 존재하지 않는다. 정책이 자기선택적으로 집행되고 있으며, 집행되는 절반은 게이트를 느슨하게 하는 쪽이다. #1295 는 그 무집행 영역을 정확히 통과했다 — PR 본문 2,707자에 '정책 17' 은 4회 나오지만 옵션 표·5+1·단계 분할·사전 확인은 각 0회이고, 4회 중 2회는 삭제된 규칙 목록, 2회는 이 변경의 방향을 정당화하는 용도(원칙 2 = 외부화 형태, 원칙 1 = 260줄 상한 근거)이지 이 변경에 적용한 프로세스가 아니다. 결과로 원칙 3/4 문장 자체가 삭제됐다가 사후 관측자(Grok BROKEN) 판정 후에야 복원됐다.
- **근거**: 코드 전수 grep(scripts/ .claude/hooks/ .claude/workflows/ tests/unit/scripts/ tests/unit/hooks/)에서 '정책 17' 인용 12곳은 전부 원칙 1 계열: check_dead_code.py:15 / check_dual_import.py:12 / check_noqa_sideeffect.py:13 ('신규 diff 한정 — 정책 17 안정성'), check_owed_verification.py:15-16 · check_retro_cadence.py:13-14 · check_precommit_installed.py:15 ('비차단 advisory — 정책 17 안정성'), check_lint_js_nonvacuous.py:13,187, pre_push_gate.py:73, check_edit_allowed.py:32,39 ('가드 자살 방지 — 정책 17'), doc_review_gate.py:145,850. 원칙 3(5+1 회의/옵션 표/단계 분할) 또는 원칙 4(High tier 사전 확인)를 인용·검사하는 지점 = 0건. PR #1295 본문 실측(gh pr view --json body): 총 2,707자, '정책 17'×4, '옵션 표'×0, '5+1'×0, '회의'×0, '단계 분할'×0, 'High tier'×0, '사전 확인'×0. 단계 분할 위반의 정량 대조 — git log --numstat -- CLAUDE.md 기준 #1295(7ab96205)의 -331 라인은 리포 역사상 2번째로 큰 CLAUDE.md 삭제이며, 동일 활동 클래스의 직전 선례는 명시적으로 분할돼 있었다: #1158(048bdc00, '문서 재구성 Phase 2 배치1') -88 / #1159(f65199a9, '배치2') -50 / #347(3ba3f8f4, 'Phase A') -159 / #357(ce984e43, 'PR-D') -124. 즉 선례 1단계 규모의 3.8~6.6배를 단일 커밋·단일 PR 로 수행.
- **처방**: 원칙 3/4 에 최소 1개의 관측면을 준다. 차단(exit 1)은 정책 17 원칙 1 과 충돌하므로 advisory 로: CLAUDE.md/.claude/policies/**/.claude/rules/** 의 순삭제가 임계(예: -80 라인 또는 -20%)를 넘는 PR 에 대해 PR 본문의 §옵션 표 / §5+1 심의 기록 / §단계 분할 계획 존재를 계량하고 부재 시 ::notice 로 인쇄한다(정책 19 집행면 check_claim_review_trace.py 가 이미 검증한 '면제 계량' 패턴 재사용). 동시에 CLAUDE.md:90 의 원칙 3/4 를 '무엇이 있으면 통과인가'가 판별 가능한 형태(PR 본문 섹션명 고정)로 서술해 집행 가능성을 부여할 것.
- **판정**: `SEVERITY_ADJUST` — 핵심 골자는 실측으로 살아남았으나, 근거의 중심 문장 두 개가 HEAD(7ab96205) 기준으로 반증되어 P1 → P2 로 조정한다.

■ 확인된 부분 (재실측)
- CLAUDE.md:90 = 정책 17 행 실재. 본문에 "매 분리 단계마다 5+1 회의 + 운영 검증 + 사용자 옵션 표 결정"(원칙 3) + "본문 보존 default … 분리 시 High tier 사전 확인"(원칙 4) 모두 현존 = 복원 사실 확인.
- 원칙 3 집행면 = 0 확정. `grep -rn "옵션 표|단계 분할" scripts/ .claude/hooks/ .claude/workflows/ tests/unit/scripts/ tests/unit/hooks/` → 0건. `High tier` 는 tests/unit/scripts/test_claude_md_behavior_rules.py:50 한 곳뿐이고 그것은 **정책 15** 3-tier 어휘의 설명문("High tier 결정을 사전 확인 없이 진행")이지 정책 17 원칙 4 검사가 아니다. `5+1` 히트는 전부 정책 8(check_retro_cadence.py:24,148) · 워크플로 프롬프트(retrospective.mj

### [docs/traceability] CRITICAL 등급 문서 심의 결과가 PR 기록에 남는 필드가 없다 — '사전 게이트가 무엇이라 판정했는가'를 코드 고고학 없이는 답할 수 없다

- **위치**: `.claude/hooks/doc_review_gate.py:920`
- **주장**: 이번 gap 진술이 '사전 게이트가 발동하지 않았다'로 서술된 것 자체가 증상이다. 게이트는 실제로 배선돼 있었고 발동 가능했으나, 그 판정이 어디에도 기록되지 않아 PR 을 읽는 어떤 주체도 발동 여부·판정값을 알 수 없다. #1295 본문 2,707자에 '심의 게이트'·'doc_review_gate' 는 각 0회이고, 대신 사후 Grok claim-review 만 session/claim/verdict 3필드로 기록돼 있다. 즉 리포는 사후 관측자의 흔적은 CI(check_claim_review_trace.py)로 강제하면서, 사전 관측자의 흔적은 강제도 기록도 하지 않는다. 결과적으로 '사전 게이트 미발동 → 사후 관측자 전적 의존'이라는 인과를 사후에 검증하려면 훅 소스와 배선을 직접 읽어야 하며, 이번 조사가 정확히 그 경로를 밟았다.
- **근거**: PR #1295 본문 실측: '심의 게이트'×0, 'doc_review_gate'×0 (총 2,707자). 반면 동일 본문에 'Grok claim-review' 섹션은 session 8eccb444-5088-4047-92f5-cb29d16b5500 / claim CLAIM-SLIM / verdict BROKEN 3필드로 존재. 비대칭의 제도적 근거: 정책 19 집행면 scripts/check_claim_review_trace.py 는 seal 어휘 PR 에 대해 claim-review 흔적(session/claim/verdict)을 CI 로 강제하나, doc_review_gate 판정에 대응하는 강제·기록면은 리포 전체 grep 결과 부재. 게이트 출력 채널 자체도 비영구적 — doc_review_gate.py:920-934 는 block 시 permissionDecision:deny 를, warn 시 _emit_advisory 를 세션 컨텍스트/터미널로만 내보내고 어떤 파일·원장에도 쓰지 않는다.
- **처방**: CRITICAL 등급 파일을 건드린 PR 본문에 §'문서 심의 게이트 결과'(파일별 등급 + 최종 decision + inoperative 여부) 1줄을 요구한다. 게이트가 무음이었다면 '무음'이라고 적는 것 자체가 관측이다 — 이번 사고에서 그 한 줄이 있었다면 diff 실명이 PR 리뷰 시점에 드러났다. 강제 방식은 정책 19 집행면(check_claim_review_trace.py)의 기존 패턴을 재사용하되 정책 17 원칙 1 에 따라 advisory + ::notice 계량으로 시작할 것.
- **판정**: `CONFIRMED` — 전 항목 실측 일치. (1) 인용 검증: doc_review_gate.py:920 = `if decision == "block":` 로 실재하며, 920-934 가 게이트 판정의 유일한 출력 경로다. 훅 940줄 전체 grep 결과 `open(...,'w')`·`write_text`·`logging` 부재 — `.append` 는 전부 리스트 append, `Path(...)` 는 경로 해석용. `_emit_advisory`(:332-357)도 additionalContext + systemMessage 만 내보내 세션 스코프를 벗어나지 않는다. 즉 '판정이 어떤 파일·원장에도 쓰이지 않는다'는 주장은 참. (2) PR #1295 본문 실측 2,707자 정확히 일치, 'doc_review_gate' 0 / '심의' 0 / '게이트' 0 / 'CRITICAL' 0, 반면 'claim-review' 1 + session/verdict 필드 존재 — 비대칭 재현됨. (3) 전제 검증(가장 강한 반증 후보): CLAUDE.md 가 skip 등급이면 '발동 가능했으나 기록 없음' 인과가 무너지므로 확인했으나, _CRITICAL[0] = `^CLAUDE\.md$`(:2

### [docs/links] 정책 외부화 축소로 죽은 앵커가 '중복 경로'에서 '유일 경로'로 승격됐다 — HEAD 18 앵커 링크 중 13 사망(72%), 정책 17 자신의 detail 경로 포함. R45-(c) 로 이미 열려 있던 항목

- **위치**: `CLAUDE.md:90`
- **주장**: #1295 는 정책 19건을 'default rule 표 + external 링크' 형태로 바꿔 본문 detail 을 제거했다(정책 17 원칙 2). 이 설계는 링크 도달성을 전제로 하는데, 그 전제가 이미 깨져 있다는 사실이 docs/backlog.md R45-(c)에 '정책 detail 링크 16건이 죽은 앵커 — 정책 17 외부화 설계가 의존하는 도달 경로가 끊겨 있다'로 🟡 착수 가능 상태로 기록돼 있었다. 축소 전에는 본문에 규칙 서술이 함께 있어 죽은 앵커가 중복 경로의 손실에 그쳤으나, 축소 후에는 표 셀 1줄 + 링크가 전부이므로 죽은 앵커가 detail 의 유일 경로를 끊는다. 특히 정책 17 자신의 detail 링크(active.md#정책-17-why-how)가 사망 상태다. PR 본문은 '깨진 상대 링크도 수정'을 명시하나 그것은 active.md 내부 정책 19 의 상대 경로 1건이고, CLAUDE.md 앵커 13건은 측정되지 않았다.
- **근거**: 앵커 도달성 실측(git show 로 각 ref 의 CLAUDE.md 파싱, 대상 파일 헤딩 slug 대조): main = 앵커 링크 28건 중 13건 이상 사망(총 17), HEAD = 18건 중 13건 사망 = 72%. HEAD 사망 목록에 .claude/policies/active.md#정책-17-why-how, #정책-7, #정책-2, #정책-5-phase-종료-cross-reference, #정책-8-회고-카덴스, #정책-10~#정책-16, docs/runbooks/workflow.md#모바일-환경-보호--수정-금지-파일 포함. 원인 = active.md 실제 헤딩이 '정책 17: 문서 cleanup Why / How to apply (자가 검토 4 자문)' 등 콜론+후행어를 포함해 slug 가 불일치(active.md 헤딩 28개 전수 확인). 기지 항목: docs/backlog.md:41 R45 (c) 'CLAUDE.md:35 등 정책 detail 링크 16건이 죽은 앵커 — 정책 17 외부화 설계가 의존하는 도달 경로가 끊겨 있다', 상태 🟡 착수 가능. PR 본문의 링크 관련 서술은 'active.md 정책 19 의 깨진 상대 링크(](AGENTS.md) → ../../)도 수정' 1건뿐.
- **처방**: 축소와 앵커 수복을 같은 PR 에 묶는다(정책 4 — 단언과 회귀 가드를 같은 PR 에). 최소 조치는 active.md 헤딩에 안정 앵커를 부여(예: 헤딩을 '정책 17 why-how' 형태로 정규화하거나 명시 id 부여)하고, 회귀 가드로 CLAUDE.md 의 모든 상대 앵커 링크가 대상 파일 헤딩 slug 에 실재하는지 검사하는 링크 체커를 추가한다(R45-(c) 의 반증 수단으로 이미 '앵커 도달성 링크 체커'가 명시돼 있다). 가드 없이 외부화를 더 진행하면 본문 축소가 곧 detail 소실이 된다.
- **판정**: `CONFIRMED` — 실측 재현됨 — 단 사망 수치는 13→12 로 정정된다.

[재현 방법] git show 로 각 ref 의 CLAUDE.md 파싱 → `](path#anchor)` 추출 → 대상 파일 헤딩을 GitHub slugger(소문자·비단어문자 제거·공백→하이픈·중복 -1 접미, 코드펜스 제외)로 재계산해 대조.

[HEAD = 7ab96205 "CLAUDE.md 424→196줄"] 앵커 링크 총 18건(cross-file 16 + self 2). **cross-file 12건 사망 = 12/18 = 67%**. 사망 목록(CLAUDE.md 줄번호): active.md#정책-2(76) · #정책-5-phase-종료-cross-reference(79) · #정책-8-회고-카덴스(81) · #정책-10(83) · #정책-11(84) · #정책-12(85) · #정책-13(86) · #정책-14(87) · #정책-15(88) · #정책-16(89) · **#정책-17-why-how(90)** · #정책-7(97).

🔴 **주장 목록 중 1건은 오탐**: `docs/runbooks/workflow.md#모바일-환경-보호--수정-금지-파일`(CLAUDE.md:155)은 **

### [측정 규율 — 실효성 반례] 규율을 신설한 바로 그 커밋(#1293) 본문에 미검증 측정 수치가 2건 살아 있다 — 조치가 재발을 막지 못한 반례가 같은 커밋 안에 있다

- **위치**: `docs/backlog.md:55`
- **주장**: §측정 규율을 만든 `#1293`(faeb2cf1) 커밋 본문의 헤드라인 수치 **"17,375 토큰(창의 8.7%)"** 은 `bytes÷3` 휴리스틱 산출값이며 사용자가 지적했다. 같은 본문의 **"이력 141 항목 · 141 → 141 · 유실 0"** 도 backlog R54 가 스스로 *"가짜 분할 9건('141개'가 내 splitter 출력이었다)"* 로 정정한 값(실제 132)이다. 규율의 선언과 그 규율 위반이 **같은 커밋 메시지 안에 공존**하며, 어느 가드도 이를 잡지 않았다.
- **근거**: `git show faeb2cf1` 본문 = *"매 세션 강제 로드는 17,375 토큰(창의 8.7%)이고 3개월간 +8% 로 안정적이다"* + *"이력 141 항목을 표 밖 … 항목 대조: 141 → 141 · 유실 0 · 문자수 차 +0"*. 실측 corroboration: `git show faeb2cf1:CLAUDE.md` = **44,150 bytes**, 메모리 `MEMORY.md` = **6,683 bytes** → 합 50,833 ÷3 = **16,944**, 발행값 17,375 와 2.5% 이내 정합(한국어 위주 텍스트의 실제 토크나이저 값은 이보다 크다 — bytes÷3 은 문자수 근사이지 토큰이 아니다). 141 정정은 `docs/backlog.md:55` R54 본문이 자인. 두 수치 모두 머지된 커밋 본문에 그대로 남아 있고, `scripts/pre_push_gate.py:58-84` repo-integrity 13 가드 중 커밋 본문 수치를 검증하는 것은 0.
- **처방**: AGENTS.md §측정 규율 표에 이 두 건을 **6번째·7번째 행**으로 추가한다(현재 5행 — 자기 PR 의 위반이 표에 없다). 규율의 신뢰성은 '가장 최근의 위반이 표에 있는가' 로 판정되므로, 자기 위반을 기록하지 않으면 다음 세션은 그 규율을 이미 해결된 과거로 읽는다.
- **판정**: `SEVERITY_ADJUST` — citation OK — docs/backlog.md:55 is the R54 row and carries the live string "**17,375 토큰**(창의 8.7%)". Both commit quotes exist verbatim in `git show faeb2cf1`. Corroboration reproduced independently: CLAUDE.md@faeb2cf1 = 44,150 bytes, MEMORY.md = 6,683 bytes → ÷3 = 16,932 vs published 17,375 (2.6% delta); the text is 24.5% Hangul, where a real BPE count diverges materially from any byte heuristic, so "토큰" is a mislabeled unit. Bonus defect the finding missed: 17,375/0.087 → implied window 199,713 ≈ 200K, while this session runs a 1M-context model — the "창의 8.7%" denominator is unanchored too. 

### [측정 규율 — 손유지 리터럴] §측정 규율 본문의 "56 패턴" 이 그것을 신설한 PR 로 이미 61 로 drift — R54 가 P0 로 잡은 손유지 결함을 시정 PR 이 재생산

- **위치**: `AGENTS.md:119`
- **주장**: AGENTS.md:119 는 현재형으로 *"56 패턴 중 0개 매칭"* 이라 단언하지만, 같은 PR(`#1293`)이 신설한 `.claude/rules/docs.md`(paths 5개) 때문에 실측은 **61** 이다. 이 리터럴은 손유지이고 가드 0 이라, R54 가 P0 로 확정한 *"같은 정수가 5지점 손유지"* 결함을 시정 PR 자신이 새 지점 하나로 재생산했다.
- **근거**: 실측 (frontmatter `paths:` 항목 수 전수): api.md 7 · db.md 4 · deploy.md 8 · docs.md 5 · guards.md 5 · i18n.md 4 · pipeline.md 5 · security.md 9 · services.md 7 · testing.md 4 · ui.md 3 = **합계 61**. 61 − 5(docs.md, `#1293` 신설) = 56 → 서술은 신설 **직전** 스냅샷이며 커밋되는 순간 stale 이 됐다. `AGENTS.md:118-119` 원문: *"이것들은 `.claude/rules` 의 어떤 경로 패턴에도 매칭되지 않아 **규칙이 도달한 적 없는 표면**이었다(문서 감사 실측: 56 패턴 중 0개 매칭)"*. 이 수치를 검증하는 가드 = 0(위 P0-2 뮤테이션에서 절 전체 삭제도 GREEN).
- **처방**: 수치를 서술에서 제거하고 *"`.claude/rules` 의 적용 술어는 전부 경로라 이 표면에는 매칭이 없다"* 로 무수치화하거나, `test_rule_reachability.py` 에 `frontmatter path 총계 == AGENTS.md 서술값` 대조를 추가한다(docs.md §손유지 원칙 = SSOT 한 곳 + 파생). 무수치화가 정책 16 최소 추상화에 부합.
- **판정**: `CONFIRMED` — 실측 전건 재현됨. (1) 인용 존재 확인 — AGENTS.md:119 원문 일치. (2) 수치 확인 — 현재 HEAD frontmatter `paths:` 전수 합계 = 61 (api 7·db 4·deploy 8·docs 5·guards 5·i18n 4·pipeline 5·security 9·services 7·testing 4·ui 3), `faeb2cf1^` 시점 = 정확히 56. (3) 출처 확인 — `git blame -L 119,119` = faeb2cf1(#1293), 같은 커밋이 `A .claude/rules/docs.md`(5 패턴) 추가. 즉 리터럴은 커밋되는 순간 stale 이 됐다. (4) 가드 0 확인 — 이 수치를 검사하는 가드 없음. test_claude_md_behavior_rules.py:60 은 CLAUDE.md 에 `측정 규율` 문자열 생존만 보고, test_rule_reachability.py 는 `paths:` 를 파싱하되 총합을 내거나 대조하지 않는다. 리포 전체 grep 결과 `56 패턴` = AGENTS.md:119 + docs/backlog.md:55 2지점 손유지(둘 다 #1293).

결함이 실재하는 근거: 해

### [측정 규율 — 도달 채널의 절벽] AGENTS.md 가 실제 도달하는 유일 채널(심의 게이트)의 예산 여유가 15% 뿐이고, 초과 시 경로 표가 red 없이 조용히 잘린다

- **위치**: `.claude/hooks/doc_review_gate.py:631`
- **주장**: AGENTS.md 가 실제로 에이전트 컨텍스트에 들어가는 유일한 기전은 `doc_review_gate` 심의자 컨텍스트인데, 예산 12,000자에 현재 10,178자로 여유가 **1,822자(15.2%)** 뿐이다. 초과 시 앞 12,000자만 실리므로 §측정 규율(offset 4,902)은 살지만 **§규칙·정책 어디서 찾나 경로 표**(offset 7,585~10,178, Grok 의 유일한 규칙 색인)가 잘린다. 그런데 라벨 검증 테스트는 라벨이 '전문' 일 때만 꼬리를 확인하므로 절단 시 **red 가 되지 않는다** — 조용한 시야 축소.
- **근거**: `.claude/hooks/doc_review_gate.py:631` `("AGENTS.md", 12000),     # 5.3k  — 전문 (가드 3-불변식 SSOT)` — 주석 리터럴 `5.3k` 는 실측 **10,178자**의 1.9배 어긋난 stale 값(`Path('AGENTS.md').read_text(encoding='utf-8')` 텍스트 모드 기준; bytes 는 16,275 — 단위 구분 명시). char offset 실측: `### 불변식 1` = 1,675 · `### 불변식 2` = 2,198 · `## 🔴 측정 규율` = 4,902 · `## 규칙·정책 어디서 찾나` = 7,585 · `scripts/**` = 4,009 · `src/gate/**` = 7,770. `tests/unit/hooks/test_doc_review_gate.py:873` `if body.lstrip().startswith("(전문")` — 절단 라벨(`(앞 12000자 / … = …%만 포함`)이면 분기를 건너뛰어 통과. 지문 핀 2건(`:847-848`)은 offset 1,675·2,198 로 절단선 훨씬 앞이라 절단을 감지 못한다.
- **처방**: (a) `:631` 주석의 stale `5.3k` 를 실측값으로 정정하거나 주석에서 수치를 제거하고, (b) `_SOURCE_FINGERPRINTS` 에 AGENTS.md **꼬리** 지문(`src/gate/**` 또는 경로 표 헤딩)을 추가해 절단이 곧 red 가 되게 한다 — 현재는 머리 지문만 있어 '앞은 살고 뒤는 죽는' 절단이 관측되지 않는다(`#1293` 이 STATE 가드에 `_last()` 꼬리 축을 넣은 것과 동일한 시정).
- **판정**: `CONFIRMED` — CONFIRMED — every load-bearing number reproduced exactly, and the silent-failure mode is mutation-proven, not merely read.

VERIFIED BY MEASUREMENT
1. `.claude/hooks/doc_review_gate.py:631` exact: `("AGENTS.md", 12000),     # 5.3k  — 전문 (가드 3-불변식 SSOT)`.
2. AGENTS.md = 10,178 chars (16,275 bytes) → headroom 1,822 chars = 15.2%. Exact.
3. All six char offsets exact: 불변식1=1675 · 불변식2=2198 · 측정규율=4902 · 경로표=7585 · `scripts/**`=4009 · `src/gate/**`=7770.
4. The stale `5.3k` comment traced to origin: at commit 89c6f092 (2026-07-22) AGENTS.md was **5,341 chars** — the comment was true when written a

### [process/prescription-follow-through] 같은 §G 섹션의 4번째 처방(도달성 가드 심볼 축 유도화)도 미이행 — 미이행 처방 수가 3건이 아니라 최소 4건

- **위치**: `tests/unit/scripts/test_rule_reachability.py:41`
- **주장**: 과제가 3건으로 집계한 §G 미이행 처방은 **최소 4건**이다. 회고가 *'주석이 이름 붙인 결함을 그 자신이 재생산한다'* 며 처방한 심볼 축 유도화(frontmatter `cross_area_symbols:` 선언 + 빈 집합이면 fail-closed)가 그대로 남아 있다. 미이행 건수 자체가 과소 집계된다는 것은, 처방 소실을 세는 축이 없을 때 **소실 규모조차 추정에 의존**한다는 본 관점의 논지를 강화한다.
- **근거**: `tests/unit/scripts/test_rule_reachability.py:41` = `_CROSS_AREA_SYMBOLS = ("WorkerSessionLocal",)` — 여전히 **1-핀** 하드코딩. 처방이 요구한 `cross_area_symbols:` frontmatter 키는 리포 전역 grep **hit 0**(`.claude/rules/*.md` 11개 어디에도 없음). 소비자 경로 축만 디스크 유도로 전환된 상태(`:117` `_consumers("WorkerSessionLocal")`)이고 심볼 축은 미전환 — 회고가 지적한 '두 축 중 한 축만 고친 채 해소 단언' 구조가 그대로다.
- **처방**: R43 이행 시 함께 처리한다(같은 파일·같은 결함 클래스). 최소안: `.claude/rules/*.md` frontmatter 에 `cross_area_symbols:` 키를 도입하고 `_CROSS_AREA_SYMBOLS` 를 그 합집합에서 유도하되, **합집합이 비면 red**(fail-closed) — 손유지 목록이 남으면 같은 등록 침묵이 재발한다는 처방 본문의 경고를 그대로 집행한다.
- **판정**: `CONFIRMED` — 인용 정확 + 주장 사실. (1) tests/unit/scripts/test_rule_reachability.py:41 = `_CROSS_AREA_SYMBOLS = ("WorkerSessionLocal",)` 그대로 존재 — 소비자 축은 디스크 유도(`_consumers(sym)` :57, 대조군 :117)인데 심볼 축만 1-핀이라는 비대칭이 실재하고, 바로 위 :35-38 주석이 '하드코딩 핀은 등록 침묵을 만든다 → 그래서 디스크에서 유도한다' 며 해소를 단언한다(회고가 지목한 자기재생산 구조 확인). (2) 처방이 요구한 `cross_area_symbols:` frontmatter 키 = 리포 전역 grep hit 0, `.claude/` 전체 0건 — 회고 본문(docs/_archive/reports/2026-08-04-retrospective.md:337)의 처방 문장에만 등장. 미이행 확정. (3) 건수 주장 검증 결과 주장보다 강하다 — §G 5 처방 전건 미이행(5/5): rules-sync 가드·`# rules-sync-ok:` 마커 grep 0 / guards.md frontmatter 는 scripts·.claude/hooks·.claud

### [docs/rules] path-scoped rules 영역 수가 3곳에서 서로 다르다 — 산문 '10 카테고리' vs 실제 11 vs 가드 docstring '9영역'

- **위치**: `CLAUDE.md:175`
- **주장**: 영역 수 서술이 세 값으로 갈라져 있다. 독자가 '내 영역이 커버되는가' 를 판단할 때 첫 참조하는 숫자가 실제와 어긋나면, `.github/workflows/**` 같은 무주공산 표면이 '10종에 다 있겠지' 로 넘어간다 — 실제로 회고 본문과 R43 이 모두 *"10종 rule"* 이라 적었고 그 시점에도 파일은 11개였다.
- **근거**: `CLAUDE.md:175` = *"10 카테고리(2026-07-20 guards 추가) 본문은 `.claude/rules/<area>.md` 로 분리"*. 실측 `ls .claude/rules/*.md | wc -l` = **11** (api·db·deploy·**docs**·guards·i18n·pipeline·security·services·testing·ui). CLAUDE.md 매트릭스 행 수 실측(`grep -c "→ \[\`.claude/rules/"`) = **11** — 즉 매트릭스는 docs.md 를 `CLAUDE.md:189` 에 이미 등재했고 산문 카운트만 뒤처졌다. 세 번째 값: `tests/unit/scripts/test_rules_and_index_coverage.py:15`·`:89` docstring/에러메시지가 *"9영역 매트릭스"* 라 적는다.
- **처방**: 세 곳을 11 로 맞추되, 손유지 카운트를 없애는 편이 낫다 — `CLAUDE.md:175` 산문에서 숫자를 빼고 *"영역별 `.claude/rules/<area>.md` 로 분리"* 로 서술하거나, `test_rules_and_index_coverage.py` 에 '산문 카운트 == 디스크 파일 수' 단언을 추가한다(후자는 정책 4 의 가드 동반 패턴). 가드 메시지의 '9영역' 도 함께 갱신.
- **판정**: `CONFIRMED` — 3-way numeric drift confirmed by direct measurement. (1) CLAUDE.md:175 reads verbatim "10 카테고리(2026-07-20 guards 추가) 본문은 `.claude/rules/<area>.md` 로 분리". (2) Actual count = 11: `ls .claude/rules/*.md` returns api, db, deploy, docs, guards, i18n, pipeline, security, services, testing, ui; `grep -c '→ \[`\.claude/rules/' CLAUDE.md` = 11, with the docs.md row present at CLAUDE.md:189 — so the matrix already registered docs.md and only the prose count lagged, exactly as claimed. (3) Third value confirmed: tests/unit/scripts/test_rules_and_index_coverage.py:15 (module docstring) and :89 (assert fai

### [메모리(교차 세션 학습 반송자)] 메모리 가드는 참조→파일 방향만 red 로 만들고 고아(파일→참조) 방향은 exit 0 — 33 중 28(85%) 고아인데 '✅ 전부 존재'를 인쇄한다

- **위치**: `scripts/check_memory_refs.py:204`
- **주장**: `check_memory_refs.py` 는 '참조에 파일이 있는가'(5/5 초록)만 판정하고 '파일에 참조가 있는가'(5/33 = 15%)는 ℹ️ 정보로만 인쇄해 절대 실패시키지 않는다. 축소로 CLAUDE.md 의 메모리 참조가 2→**0** 이 됐는데도 가드는 초록이다. 이것은 이 창이 확정한 '앵커 생존 ≠ 규칙 생존'(observer-lie)과 동일 클래스의 미시정 잔존분이다.
- **근거**: 라이브 실행: '참조된 슬러그: 5개 / 실제 파일: 33개 / ✅ 모든 참조 슬러그에 실제 파일 존재 / ℹ️ 미참조 파일 (28개)'. 코드 — `scripts/check_memory_refs.py:187-188` 은 missing 에 `ok = False`, `:196-197` 은 stale 에 `ok = False` 를 설정하나 `:204-207` extra 분기는 `print` 만 하고 `ok` 를 건드리지 않는다(`:209 return ok`). 참조 붕괴 실측 — `git show 7ab96205^:CLAUDE.md | grep -oE '`(feedback|project|user)[-_]…\.md`|\[\[…\]\]'` → 2건(`[[feedback-grok-collaboration-default]]`, `feedback-stale-blocker-policy.md`) vs 현행 CLAUDE.md → **0건**. 잔존 5 슬러그는 전부 조건부 로드 표면에만 존재: `.claude/policies/active.md:231,263,274,358,359,465`(자동 로드 아님) · `.claude/rules/guards.md:204` · `.claude/rules/services.md:34`(path-scoped 조건부). 즉 **무조건 로드되는 처방 표면의 메모리 진입점이 0** 이 됐다.
- **처방**: 고아율에 하한을 둔다 — extra 비율이 임계(예: 50%) 초과면 ok=False 또는 최소한 loud 경고. 더 근본적으로는 MEMORY.md 인덱스 자체를 참조 표면으로 인정하도록 `_DOC_LITERALS` 를 확장할지 결정(현재 인덱스는 리포 밖이라 스캔 대상이 아님). CLAUDE.md 본문에 고빈도 메모리 슬러그 2~3건을 되살려 무조건 로드 표면의 진입점 0 을 해소.
- **판정**: `SEVERITY_ADJUST` — 인용 전건 실측 일치. `scripts/check_memory_refs.py:187-188`(missing→`ok=False`) · `:196-197`(stale→`ok=False`) · `:204-207`(`if extra:` = print 만, `ok` 미변경) · `:209 return ok` 정확. 라이브 실행 재현: 참조 5 / 파일 33 / 미참조 28 / `✅ 모든 참조 슬러그에 실제 파일 존재` / **EXIT=0**. CLAUDE.md 참조 붕괴도 재현: `7ab96205^:CLAUDE.md` → 2건(`feedback-stale-blocker-policy.md`:151, `[[feedback-grok-collaboration-default]]`:283) vs 현행 **0건**. 잔존 5 슬russ 위치도 일치(`policies/active.md:231,263,274,358,359,465` · `rules/guards.md:204` · `rules/services.md:34` — 전부 조건부 로드면).

그러나 **핵심 전제가 반증된다**. (1) "무조건 로드되는 처방 표면의 메모리 진입점이 0" = **거짓**: `MEMORY.md` 가 

### [메모리(교차 세션 학습 반송자)] 이 창의 신규 클래스 3건이 commit body·backlog 에만 남았다 — 이번에 실제로 8건이 잘린 바로 그 표면들

- **위치**: `docs/STATE.md:285`
- **주장**: 8/4~8/6 이 만든 교훈(측정 도구 미검증 발행 / 가드 초록의 보존 근거 오용 / 축소가 자기 규정을 삼킴)의 판별 어휘가 메모리 코퍼스에 단 1건도 없다. 이 교훈들은 재작성·축소 가능한 표면에만 존재하며, 축소가 행동 규칙 8건을 실제로 삼킨 것이 바로 이번 창의 사건이다.
- **근거**: 메모리 33 파일 전수 grep: `count_tokens` → 0 파일, `앵커` → 0, `1096` → 0, `슬림` → 0, `측정 규율` → 0, `단위 명시` → 0. (`축소` 는 2 파일에 있으나 `feedback-architecture-decision-pre-confirm.md`·`feedback_doc_reorg_behavior_critical.md` 로 이 창의 교훈이 아님.) 반면 7ab96205 커밋 본문은 토큰 추정 오차(bytes÷3 → CLAUDE.md 14,509 보고 vs 실측 21,236, -32%)와 Grok claim-review `8eccb444` verdict **BROKEN** 지적 4건(규칙 8건 소실·자기 규정 위반·가드 green 오용·깨진 링크)을 전부 담고 있다. `docs/backlog.md` R-창은 R35~R54 로 확장됐고 그 서사는 STATE/backlog/commit body 분산.
- **처방**: 최소 2건 신설 권장 — (1) `feedback-measurement-tool-unverified.md`(1회용 측정 도구의 숫자를 검증 없이 발행하지 않는다: 단위 명시 + 1차 출처 대조) (2) `feedback-guard-green-is-not-preservation.md`(가드 전건 통과는 앵커 생존의 증거이지 규칙 생존의 증거가 아니다 — 축소 시 '무엇을 보는 가드인가'를 먼저 확인). 기존 `feedback-prose-guard-both-ways.md`·`feedback-fix-reproduces-the-defect.md` 와 인접하므로 진화로 흡수할지 신설할지는 작성 시점에 판단.
- **판정**: `CONFIRMED` — CONFIRMED at P2, but with scope cut to roughly one third of what was claimed. Verified true: every memory grep reproduces exactly (count_tokens/앵커/1096/슬림/측정 규율/단위 명시 = 0 files; 축소 only in two out-of-window files), and the memory corpus has max mtime 2026-08-01 21:29 — zero entries written across the whole 8/4~8/6 window (3 sessions, 15+ merged PRs), so the cross-session learning carrier genuinely received nothing. Citation docs/STATE.md:285 exists (file = 287 lines) and is the in-window 세션16 6차 #1293 line, though line 287 is the sharper anchor for the CLAUDE.md 축소 event. FALSIFIED, however, i

### [CLAUDE.md rules 매트릭스 정수 SSOT] CLAUDE.md:175 '10 카테고리' 가 HEAD 에서 11 과 어긋난다 — R54 가 진단한 손유지 정수 클래스의 자기 재생산 (같은 리터럴이 과거 #401 에서 '사실 오류' 로 이미 한 번 정정된 재발)

- **위치**: `CLAUDE.md:175`
- **주장**: CLAUDE.md:175 의 리드 문장은 `**사이클 85 정리**: 10 카테고리(2026-07-20 guards 추가) 본문은 .claude/rules/<area>.md 로 분리` 인데, 바로 아래 매트릭스는 **11행**(CLAUDE.md:179~189)이고 디스크의 `.claude/rules/*.md` 도 **11개**다. 11번째 행 `문서 / 원장 → docs.md`(CLAUDE.md:189)를 신설한 것이 `faeb2cf1`(#1293, R54) 이며, **그 PR 은 같은 사실의 다른 사본은 갱신했다** — 아키텍처 동기화 체크리스트의 `10 영역 매트릭스` → `11 영역 매트릭스`(faeb2cf1 diff, 당시 CLAUDE.md:366). 즉 두 지점 중 하나만 손으로 고쳤다. 이후 `7ab96205`(CLAUDE.md 424→196줄)가 그 체크리스트 열거를 통째로 삭제하면서 **정정된 11 은 사라지고 미정정 10 만 살아남았다**. 이 리터럴이 '사이클 85 시점의 역사 기록' 이라는 방어는 성립하지 않는다 — `git log -L '/사이클 85 정리/,+1:CLAUDE.md'` 실측상 이 값은 현재 카운트로 4회 손유지돼 왔다: `7b3b66f2`(#318) 9 → `271ff2ec`(#401, 커밋 제목이 **'P0/P1 사실 오류 7건 수정'**) 8 → `32daf755`(#1011, services.md 신설) 9 → `1fa2557b`(#1164, guards 신설) 10 → **#1293(docs.md 신설) 미갱신**. 3회 성공 후 4회차 실패이고, 같은 리터럴은 #401 에서 이미 사실 오류로 정정된 전력이 있다.
- **근거**: `ls .claude/rules/` → api·db·deploy·docs·guards·i18n·pipeline·security·services·testing·ui = 11 파일. `sed -n '177,190p' CLAUDE.md | grep -c '^| .* | .*rules/'` → 11. `grep -n "카테고리" CLAUDE.md` → 175: '10 카테고리'. `git show faeb2cf1 --format="" -- CLAUDE.md` → `-... 10 영역 매트릭스: testing.md ...` / `+... 11 영역 매트릭스: ... / docs.md (docs/**, README.md, ...)` 및 매트릭스 행 `+| 문서 / 원장 | .claude/rules/docs.md | docs/**, ... |` 추가. `git show faeb2cf1^:CLAUDE.md | grep -n 카테고리` 와 `git show faeb2cf1:CLAUDE.md | grep -n 카테고리` 가 402행에서 **동일하게 '10 카테고리'** — #1293 이 이 지점을 건드리지 않았음의 직접 증거. `git log --oneline -L '/사이클 85 정리/,+1:CLAUDE.md'` 로 9→8→9→10 손유지 이력 확인.
- **처방**: 기계 파생으로 옮긴다. 이미 `tests/unit/scripts/test_rules_and_index_coverage.py:47` 의 `_areas()` 가 진짜 카운트를 디스크에서 유도하고 있고, 같은 파일이 이 매트릭스를 검사한다 — 파생이 200줄 밖이 아니라 **같은 파일 안에** 있었는데 쓰이지 않았다. (a) 최소 조치: CLAUDE.md:175 를 11 로 정정 + `assert f"{len(_areas())} 카테고리" in CLAUDE_MD` 3줄 추가. (b) 더 나은 조치: 리드 문장에서 정수를 **삭제**한다(`N 카테고리` → `영역별 규칙 본문은 …`) — R54 의 교훈은 '정수를 잘 동기화하라' 가 아니라 '**N지점 손유지 = N-1번의 실패 기회**' 였고, 이 정수는 바로 아래 매트릭스가 이미 열거하므로 **정보 가치가 0** 이다. (c) 회귀 가드는 뮤테이션으로 실증: `.claude/rules/` 에 더미 area 를 추가하면 red 가 되는가.
- **판정**: `SEVERITY_ADJUST` — 모든 인용 실측 재현됨 — 사실관계는 100% 성립, 심각도만 P1→P2 조정.

[검증 통과]
1) `ls .claude/rules/` = 11 파일 (api·db·deploy·docs·guards·i18n·pipeline·security·services·testing·ui).
2) `grep -n "카테고리" CLAUDE.md` → 175행 `10 카테고리` — 리포 전체에서 이 클래스의 유일한 stale 리터럴 (CLAUDE.md·AGENTS.md·architecture.md·rules/docs.md 대상 `10 카테고리|10 영역|11 영역|11 카테고리` grep 결과 175행 1건뿐).
3) 매트릭스 실측 179~189행 = 11행, 마지막 행이 `| 문서 / 원장 | docs.md (docs/**, README.md, README.ko.md, CLAUDE.md, AGENTS.md) |`. 인용된 179~189 line span 정확.
4) 핵심 증거 재현: `git show faeb2cf1^:CLAUDE.md | grep -n 카테고리` 와 `git show faeb2cf1:CLAUDE.md | grep -n 카테고리` 가 402행에서 **바이트

### [CLAUDE.md rules 매트릭스 정수 SSOT] 매트릭스를 검사하는 가드 자신이 같은 정수를 3지점 손유지하고 있고 전부 stale — 그중 하나는 non-vacuity 대조군이라 탐지력이 조용히 2 감소했다

- **위치**: `tests/unit/scripts/test_rules_and_index_coverage.py:221`
- **주장**: 이 매트릭스의 유일한 관측자인 `tests/unit/scripts/test_rules_and_index_coverage.py` 가 **자기 안에** 같은 정수를 3곳 손으로 적어 두었고 세 곳 다 실제(11)와 어긋난다. 특히 :221 의 `assert len(_areas()) >= 9` 는 docstring 이 '대조군 — 탐색이 0건이면 위 단언들이 공허하게 통과한다' 로 스스로를 anti-vacuous 안전핀이라 선언하는데, area 가 9→11 로 늘어난 지금 이 하한은 **2 뒤처져 있다**. 결과: `.claude/rules/` 에서 규칙 파일을 **2개 지워도 이 대조군은 초록**이다(11-2=9 ≥ 9). 즉 손유지 하한을 쓰는 non-vacuity 컨트롤은 영역이 추가될 때마다 **탐지력이 단조 감소**하며, 그 감소가 아무 신호도 내지 않는다 — AGENTS.md 불변식 1(fail-closed)이 겨냥하는 바로 그 형상이다. 파일 스스로 `_areas()` 로 진짜 값을 유도하고 있으므로 하한을 상수로 둘 이유가 없다.
- **근거**: `grep -rn "9영역\|>= 9" tests/unit/scripts/test_rules_and_index_coverage.py` → :15 `3. CLAUDE.md 의 9영역 매트릭스와 각 규칙 파일의 paths: frontmatter 는 **같은 사실의 두 사본**` / :89 `"→ .claude/rules/security.md frontmatter paths: + CLAUDE.md 9영역 매트릭스에\n"` / :221 `assert len(_areas()) >= 9, f"규칙 영역이 {len(_areas())}개 — 9개 미만이면 확인 필요"`. 실제 `len(_areas())` = 11 (`ls .claude/rules/*.md | wc -l` → 11). :47 `def rule_paths` 바로 위 `_areas()` 가 디스크에서 유도한다.
- **처방**: :221 의 하한을 파일 자신의 정본에 묶는다 — 상수 하한 대신 `.claude/rules/*.md` 디스크 개수와 CLAUDE.md 매트릭스 행 수의 **일치**를 단언하거나(대조군의 목적은 '0건 아님' 이므로 `assert _areas()` 만으로 충분하다), 최소한 하한을 없애고 매트릭스 행 수 ↔ 파일 수 등식으로 대체한다. 하한을 유지할 거면 왜 그 숫자인지가 파일에서 유도돼야 한다. :15/:89 의 '9영역' 은 다음 항목 참조.
- **판정**: `CONFIRMED` — 모든 인용과 인과 주장을 기계로 재확인했다. (1) 인용 정합: grep -n 결과 :15 '9영역 매트릭스', :89 'CLAUDE.md 9영역 매트릭스에', :221 'assert len(_areas()) >= 9' 세 곳 모두 문자 그대로 존재. (2) 실제값: 런타임 len(_areas()) = 11 (api, db, deploy, docs, guards, i18n, pipeline, security, services, testing, ui), ls .claude/rules/*.md = 11 — 세 상수 모두 2 stale. (3) 자기선언: :219 docstring 이 '대조군 — 탐색이 0건이면 위 단언들이 공허하게 통과한다' 로 스스로를 anti-vacuity 안전핀이라 선언. (4) 탐지력 손실 뮤테이션 실증: docs.md+ui.md 2개 삭제 후 test_rules_and_index_coverage.py 전체 green (11-2=9 >= 9 통과) — 주장대로 대조군이 초록. docs.md 1개만 삭제하면 tests/unit/scripts/ + tests/unit/hooks/ 1119 passed 로 리포 전체에서 아무것도 빨개지지 않음

### [CLAUDE.md rules 매트릭스 정수 SSOT] 가드 실패 메시지가 존재하지 않는 이름('CLAUDE.md 9영역 매트릭스')으로 시정을 지시한다 — 실패를 만난 다음 저자가 잘못된 대상을 찾는다

- **위치**: `tests/unit/scripts/test_rules_and_index_coverage.py:89`
- **주장**: `test_log_redaction_modules_are_covered_by_security_rules` 의 실패 메시지(:89)는 `→ .claude/rules/security.md frontmatter paths: + CLAUDE.md 9영역 매트릭스에 **양쪽 다** 추가할 것(둘은 같은 사실의 두 사본)` 이다. 그런데 CLAUDE.md 에 '9영역 매트릭스' 라는 것은 없고(현재 11행, 리드 문장은 '10 카테고리'), 이 가드가 만들어진 뒤 area 는 9→10→11 로 두 번 늘었다. 이 메시지는 **가드가 red 일 때만 읽히는 문자열**이라 CI 초록 상태에서는 아무도 보지 않는다 — 즉 drift 가 검출되지 않은 채 누적되고, 정작 사고가 나서 읽히는 순간에 틀린 이름을 준다. 같은 파일 :15 의 docstring 도 동일하게 '9영역 매트릭스' 로 사고 서술을 고정하고 있다. 실패 메시지·docstring 은 '주석이라 무해' 가 아니라 **다음 저자의 행동을 지시하는 표면**이다.
- **근거**: `grep -rn "9영역" tests/unit/scripts/test_rules_and_index_coverage.py` → :15, :89. CLAUDE.md 실측: 리드 문장 :175 = '10 카테고리', 매트릭스 :179~189 = 11행. `.claude/rules/*.md` = 11개. 즉 9 · 10 · 11 세 값이 같은 사실에 대해 HEAD 에 공존한다.
- **처방**: 실패 메시지에서 정수를 빼고 **위치로 지시**한다 — `CLAUDE.md §주의사항(카테고리별) 매트릭스` 처럼 앵커로 가리키면 area 가 늘어도 늙지 않는다. docstring(:15)도 동일. 원칙: 관측자가 출력하는 문자열에 손유지 정수를 넣지 않는다(그 정수는 red 일 때만 검증되므로 사실상 무검증 표면이다).
- **판정**: `CONFIRMED` — 전 근거 실측 재현 (HEAD 7ab96205, branch docs/claude-md-under-200).

[인용 확인]
- `tests/unit/scripts/test_rules_and_index_coverage.py:89` = 실패 메시지 `"→ `.claude/rules/security.md` frontmatter `paths:` + CLAUDE.md 9영역 매트릭스에\n"` — 존재.
- 같은 파일 `:15` = docstring `3. CLAUDE.md 의 9영역 매트릭스와 각 규칙 파일의 `paths:` frontmatter 는 **같은 사실의 두 사본**` — 존재.
- `CLAUDE.md` 총 195줄. `:175` 리드 = "10 카테고리(2026-07-20 guards 추가)". 매트릭스 `:177~189` = 헤더 2 + **데이터 11행**(testing/db/pipeline/api/security/ui/i18n/deploy/services/guards/**docs**).
- `ls .claude/rules/*.md` = **11개** (docs.md 포함).
→ 같은 사실에 대해 **9 · 10 · 11 세 값이 HEAD 에 공존*

### [CLAUDE.md rules 매트릭스 정수 SSOT] AGENTS.md:191 의 '영역별 규칙 원본' 열거가 10개 — `docs` 누락. 같은 #1293 이 바로 위 표(:182)에는 추가했으나 이 열거는 갱신하지 않았다 (동일 클래스의 3번째 사본)

- **위치**: `AGENTS.md:191`
- **주장**: AGENTS.md:191 `- 영역별 규칙 원본: .claude/rules/{testing,db,pipeline,api,security,ui,i18n,deploy,services,guards}.md` 는 **10개**만 열거하고 `docs` 가 빠져 있다. 같은 PR(`faeb2cf1`, AGENTS.md +37)이 바로 위 경로 표에 `| docs/** · README.md · README.ko.md · CLAUDE.md · AGENTS.md | docs.md |`(AGENTS.md:182)를 추가했으므로, 한 파일 안에서 두 사본이 갈라졌다. 이 문서는 `🔴 Grok 은 auto-load 가 **없다**. 이 표를 건너뛰면 규칙을 건너뛰는 것이다`(AGENTS.md:168~169)라고 스스로 선언하는 Grok 진입점이다. **왜 기계가 못 잡는가**: `test_agents_path_table_covers_every_rule_frontmatter_path`(tests/unit/scripts/test_rule_reachability.py:218)는 AGENTS.md **전문을 하나의 문자열로** 읽어 frontmatter 의 *경로*가 어딘가 나타나는지만 본다 — :182 가 경로를 덮으므로 초록이다. 즉 그 가드는 **경로 축만** 보고 **파일명 열거 축은 설계상 보지 않는다**. 도달성 자체는 :182 로 보전되므로 P2 로 둔다.
- **근거**: `grep -n "영역별 규칙 원본" AGENTS.md` → 191, brace-list 10개(testing,db,pipeline,api,security,ui,i18n,deploy,services,guards) — `docs` 없음. `sed -n '182p' AGENTS.md` → `| docs/** · README.md · README.ko.md · CLAUDE.md · AGENTS.md | docs.md |`. `sed -n '218,231p' tests/unit/scripts/test_rule_reachability.py` → `table = (_ROOT / "AGENTS.md").read_text(...)` 후 `rule_paths(f)` 의 **경로**만 `_covered_by_table` 로 대조. `git show faeb2cf1 --stat` 에 AGENTS.md | 37 +++.
- **처방**: (a) :191 의 brace-list 에 `docs` 를 넣는 것은 최소 조치일 뿐이다 — 이 줄은 :182 표가 이미 담은 정보의 사본이므로 **열거를 삭제하고 '위 표 참조' 로 바꾸는 것**이 R54 의 처방(N→1)과 일치한다. (b) 열거를 유지한다면 `test_rule_reachability.py` 에 축을 하나 추가한다: `.claude/rules/*.md` 의 stem 집합이 AGENTS.md 의 brace-list 와 **집합 일치**하는가. 현행 가드는 경로 축만 보므로 이 방향은 원리적으로 red 가 될 수 없다. 뮤테이션 실증: brace-list 에서 임의 area 를 지우면 red 인가.
- **판정**: `CONFIRMED` — 모든 인용 실측 확인. AGENTS.md:191 `- 영역별 규칙 원본: `.claude/rules/{testing,db,pipeline,api,security,ui,i18n,deploy,services,guards}.md`` = 10개 열거, `docs` 없음. 디스크 `.claude/rules/` = 11개(docs.md 존재). AGENTS.md:182 = `| `docs/**` · `README.md` · `README.ko.md` · `CLAUDE.md` · `AGENTS.md` | `docs.md` |` 로 경로 표는 docs 를 덮는다.

귀속은 주장보다 더 강하게 확증됨: `git log --diff-filter=A -- .claude/rules/docs.md` → faeb2cf1(#1293)이 파일 생성, `git show faeb2cf1 -- AGENTS.md` → 동일 커밋이 :182 행 추가, `git log -L 191,191:AGENTS.md` → 191 행 최종 수정은 5dfab6bf(#1265). 즉 #1293 이 파일+표행을 추가하고 열거만 10 으로 방치한 것이 git 으로 증명된다.

기계 사각 실증(정독이 아니라 실행으로)

---
