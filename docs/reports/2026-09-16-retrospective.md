# 회고 2026-09-16 — `#1628~#1684`

## 범위 — 기계 산출이 이 사이클의 마지막 PR 을 놓쳤다 (P0 참조)

| | 값 |
|---|---|
| 기계 산출 범위 | `#1628~#1683 (55 PR, boundary 69b2b47 .. head 2613028e)` |
| 경계 커밋 | `69b2b47` (직전 리포트 `2026-09-07-retrospective.md` 추가 커밋) |
| head | `2613028e` — 🔴 `main` 이 아니라 피처 브랜치 tip 이다 |
| 기계가 센 PR | **55건** |
| 🔴 실제 범위 | **56건** — `#1684` 는 회고 실행 중 main 에 머지됐는데 열거에 없다(P0) |
| 🔴 정직성 필드 | `gh_only: []` · `unmeasured: []` — 둘 다 「안 잰 축 없음」을 인쇄했다(P0) |
| 🔴 호출자 컨텍스트 | 객체로 넘겨 전 에이전트가 `[object Object]` 를 받았다(P1) |

재현:

```bash
py -3 scripts/retro_scope.py --json                 # 55건 · gh_only [] · unmeasured []
gh pr view 1684 --json state,baseRefName,mergedAt   # MERGED · main · 실행 중 머지
```

🔴 `#1684` 의 **내용** 은 `boundary..HEAD` diff 안에 있었다(그 4커밋이 곧 head 다).
빠진 것은 **열거와 정직성 필드** 이고, 그래서 「이 창에 무엇이 있었는가」를 PR 목록으로 읽은
에이전트에게는 보이지 않았다. 이 리포트의 범위는 `#1684` 를 **포함** 한다.

## ROI

| 지표 | 값 |
|---|---|
| 라운드 (loop-until-dry) | 3 |
| 총 발견 | 151 |
| 확정 | **140** |
| 오탐 차단 | 11 |
| 심각도 조정 | 28 |
| verdict 커버리지 | 1 |
| 미검증 잔여 | 0 |
| 실행 중 범위 이동 | 없음 |
| P0 / P1 / P2 | 2 / 61 / 77 |

에이전트 176 · 오류 0 · 3h29m · 1,604만 토큰.
5관점(process·code·docs·decision·tooling) 비중복 finder → 확정 전건 cross-verify.

## P0 (2건 — 같은 뿌리)

두 건 모두 `scripts/retro_scope.py` 의 **리터럴 `HEAD`** 다. 별개 관점의 finder 둘이
서로 다른 증거로 같은 자리에 도달했다.

### P0-1. 이 세션 자신의 최신 산출물 #1684 가 회고 범위를 빠져나갔다 — 그리고 탈출 탐지 두 축이 모두 «깨끗함» 을 인쇄한다

- 좌표: `scripts/retro_scope.py` — 줄번호가 아니라 아래 근거의 인용 문자열이 앵커다
- 주장: 정책 8-(5)(가장 검증 덜 된 산출물이 회고를 피한다)가 세 번째 기전으로 실제 발생했다. PR #1684 는 2026-09-16T11:37:14Z 에 base=main 으로 머지됐고(+357/-13), 그 headRefName 이 바로 이 회고가 HEAD 로 읽고 있는 브랜치(`fix/w15-self-tint-text-siblings`)다. 그런데 기계 산출 범위는 `#1628~#1683` 이고 #1684 가 없다. 더 나쁜 것은 정직성 필드 둘(`gh_only: []`·`unmeasured: []`)이 «차집합 0 — git log 산출과 일치» 를 인쇄한다는 점이다. 재실행으로 고쳐지지 않는다 — 구조적이다.
- 근거: 방금 실측(#1684 머지 이후): `py -3 scripts/retro_scope.py --json` → {"head": "2613028e", "range": "#1628~#1683", "gh_only": [], "unmeasured": []}. `git merge-base --is-ancestor 2613028e main` → NO. 결정적 대조: `git log --format=%s 69b2b47..origin/main · grep -c '(#1684)'` → **1**, `git log --format=%s 69b2b47..HEAD · grep -c '(#1684)'` → **0**. 기전 둘: (a) scripts/retro_scope.py:110 `out = _git(["log", "--format=%s", f"{boundary}..HEAD"])` 와 :292 `head = _git(["rev-parse", "--short", "HEAD"])` 가 리터럴 HEAD = 체크아웃된 피처 브랜치 끝을 읽는다. (b) gh 교차대조의 판정식이 scripts/retro_scope.py:205 `if base != "main" and merged_at[:10] >= cut` 라서 base=main 인 #1684 를 원리적으로 못 본다(`gh pr view 1684 --json baseRefName` → "main"). 🔴 이 근본 원인은 직전 회고가 이미 확정했다 — docs/reports/2026-09-07-retrospective.md:81 「31 · decision · … `merged_prs` 가 `origin/main` 이 아니라 리터럴 `HEAD` 를 읽는다」. 확정 → 미시정 → 이번 창에서 실제 발화.
- 처방: scripts/retro_scope.py:110·292 의 `HEAD` 를 `origin/main` 으로 바꾸고 호출 전 `git fetch origin main` 을 강제한다(피처 브랜치에서 돌려도 main 기준이 나오게). 그리고 gh 교차대조를 base 축 하나로 두지 말고 「창 날짜 안에 머지됐는데 `prs_git` 에 없는 모든 PR」을 gh_only 로 싣는다 — base=main 인 탈출은 현 판정식이 영원히 못 본다. 회귀 시험: 「피처 브랜치를 체크아웃한 상태에서 main 에 머지된 PR 이 열거에 남는가」. 이번 회고의 리포트에는 #1684 를 범위에 **추가**해 적는다.

### P0-2. 이 사이클의 마지막·최소검증 산출물 PR #1684 가 회고 범위를 통째로 빠져나갔다 — 직전 회고가 P1-31 로 이름까지 적은 «리터럴 HEAD» 가 고쳐지지 않은 채 실현됐다

- 좌표: `scripts/retro_scope.py` — 줄번호가 아니라 아래 근거의 인용 문자열이 앵커다
- 주장: 기계 산출은 `pr_count:55 · range:#1628~#1683 · gh_only:[] · unmeasured:[]` 를 내놓았고 워크플로는 이를 「차집합 0 — git log 산출과 일치」로 소비했다. 그러나 PR #1684 는 `state=MERGED · baseRefName=main · mergedAt=2026-09-16T11:37:14Z · +357/-13` 이고 `src/templates/analysis_detail.html`·`src/templates/settings.html`·`src/static/css/components.css`·신규 가드 2종(`tests/unit/ui/test_css_comment_nesting.py`·`test_self_tint_text_idiom.py`)·`README.md`·`README.ko.md`·`docs/STATE.md` 를 바꾼다. 즉 창 안에서 «가장 늦게 머지된 = 가장 검증이 덜 된» 산출물이 두 축 모두에서 보이지 않았다. 정책 8-(5) 가 존재 이유로 삼은 시나리오의 3회차 재발이며, 이번에는 기전이 stacked PR(1회차)도 경계 갭(2회차)도 아닌 **HEAD 자체**다.
- 근거: ① `scripts/retro_scope.py` = `out = _git(["log", "--format=%s", f"{boundary}..HEAD"])` — 리터럴 HEAD. ② 이 세션의 HEAD 는 main 이 아니라 피처 브랜치다: `git rev-parse --abbrev-ref HEAD` → `fix/w15-self-tint-text-siblings`, `git rev-parse origin/main` → `c9d3f37a`(=#1684 squash), `git rev-parse main` → `ce2e8f67`(#1675). ③ 그 브랜치의 4커밋 제목은 전부 `(#1639 W15)` 로 끝난다 — #1639 는 PR 이 아니라 **Issue**(`gh issue view 1639` → OPEN `[WBS] UI 전수 실측`), 그래서 `(#1684)` 는 어디에도 없다: `git log --format='%s' 69b2b47..2613028e · grep -c '(#1684)'` → **0**. ④ GitHub 대조축은 `scripts/retro_scope.py` = `if base != "main" and merged_at[:10] >= cut:` — base 가 main 인 #1684 는 원리적으로 걸리지 않는다. ⑤ `scripts/retro_scope.py` = `head = _git(["rev-parse", "--short", "HEAD"])` 는 HEAD 를 «보고» 만 하고 `origin/main` 과 대조하지 않으며, `unmeasured`(306행)에 그런 축 이름이 없다 — 「안 쟀다」가 아니라 「일치한다」로 출력된다. ⑥ 직전 회고 `docs/reports/2026-09-07-retrospective.md` P1-31 = 「`merged_prs` 가 `origin/main` 이 아니라 리터럴 `HEAD` 를 읽는다」. 처방 PR #1630(`46308f2d`)의 diff 는 같은 함수 주변에 `report_head`·`github_stacked_prs` 를 추가하면서 110행은 한 글자도 바꾸지 않았다(`git show 46308f2d -- scripts/retro_scope.py`). ⑦ `origin/main` 은 이미 로컬에 c9d3f37a 로 받아져 있었다(`.git/FETCH_HEAD` Sep 16 21:11) — 데이터가 없어서 못 본 게 아니다.
- 처방: `merged_prs` 의 범위 상한을 `HEAD` 가 아니라 `origin/main`(fetch 후)으로 고정하고, `HEAD != origin/main` 이면 `unmeasured` 에 `head-not-main` 을 넣어 소비자가 「안 쟀다」로 읽게 한다. GitHub 대조축의 판정식에서 `base != "main"` 조건을 떼고 «창 기간에 머지된 전체 PR 집합 − git log 산출» 을 차집합으로 보고한다(과포함은 `mergedAt` 창으로 이미 통제됨). 회귀 테스트: (a) HEAD 가 피처 브랜치일 때 base=main 머지 PR 이 열거에 남는가, (b) 커밋 제목 말미 `(#N)` 이 Issue 번호일 때 오계수하지 않는가. 그리고 이번 회고는 **#1684 를 범위에 넣어** 다시 심의해야 한다.

## P1 (61건)

| # | 관점 | 제목 | 좌표 |
|---|---|---|---|
| 1 | process | 회고 `context` 가 객체로 전달돼 (a) 이번 회고 전 에이전트가 세션 컨텍스트를 「[object Object]」로 받았고 (b) 정책 8-(5) 집행 신호가 55/55 오경보가 됐다 | `.claude/workflows/retrospective.mjs` |
| 2 | process | 직전 회고 확정 125건 중 이름을 대고 닫힌 것은 7 PR 분뿐이고, 나머지는 CLAUDE.md 가 지정한 원장(GitHub Issues)에 0건 등재됐다 | `CLAUDE.md` |
| 3 | process | 회고가 main 밖 브랜치 HEAD 에서 돌아 창 안의 미머지 커밋 4건이 어떤 열거에도 없는데, 기계 산출은 `unmeasured: []` 로 「안 잰 축 없음」을 단언한다 | `scripts/retro_scope.py` |
| 4 | code | 내린 모델 `claude-opus-4-7` 이 화면·기록 두 가격 경로에서 2.5× 갈린다 — 가드는 자기 dict 만 돌아 못 본다 | `src/constants.py` |
| 5 | code | e2e 하네스의 «자격증명 파생» 이 DB 접속 URL 을 못 잡는다 — 개발 PC `.env` 의 `MIGRATION_DATABASE_URL` 로 `alembic upgrade head` 가 나갈 수 있다 | `e2e/conftest.py` |
| 6 | code | e2e 대비 감사가 재는 토큰이 `--text-2`·`--text-3` 둘뿐이다 — 「400조합」이 실제로 덮는 글자는 일부다 | `e2e/test_theme_mobile_guards.py` |
| 7 | code | `--warning` 을 글자로 쓰는 세 자리가 pastel 에서 2.63~2.79:1 — `--success-text`·`--accent-text` 형제가 warning 에만 없다 | `src/templates/analysis_detail.html` |
| 8 | code | `.repos-rec-*` 뱃지가 리터럴 `#fff`/`#000` 을 테마 토큰 면에 얹어 dark 2.77 · catppuccin 2.32 — 그리고 이 팔은 어떤 테스트도 렌더한 적이 없다 | `src/templates/dashboard.html` |
| 9 | code | `retrospective.mjs` 가 `context` 객체를 문자열로 이어 붙여 «세션 컨텍스트: [object Object]» 를 만들고, 그 값으로 범위 대조를 한다 | `.claude/workflows/retrospective.mjs` |
| 10 | code | 점수 바 등급색이 화면마다 다르다 — #1651 이 analysis_detail 에서 내린 리터럴이 overview·repo_detail 에는 그대로 있다 | `src/templates/overview.html` |
| 11 | docs | CLAUDE.md 가 #1668 로 폐기된 검증 규칙(「거짓초록 1건 심기」)을 계속 가르친다 — 자기 SSOT 와 모순 | `CLAUDE.md` |
| 12 | docs | 사이클의 지배 계약(AA 대비·24px 타깃·자기 틴트 금지·죽은 토큰 금지)이 영역 문서에 한 줄도 없다 — 가드 16개는 이미 push 를 막는다 | `docs/workflow/ui-i18n.md` |
| 13 | decision | 회고 `context` 가 객체로 들어와 「[object Object]」로 평탄화 — 전 에이전트가 세션 맥락 0, 정책 8-(5) 판별식은 항상-발화로 공허화 | `.claude/workflows/retrospective.mjs` |
| 14 | decision | 직전 회고 확정 125건 중 118건이 어떤 열린 원장에도 없다 — 리포트 자신이 P1-11·P1-20·P2-37 로 지목한 결함의 3연속 재발 | `docs/reports/2026-09-07-retrospective.md` |
| 15 | decision | 회고 착수 신호에 집행면이 없어 55 PR(임계의 3.7배)에서야 발화 — 그 「임계 15」는 리포지토리 어느 표면에도 없다 | `docs/reports/2026-09-07-retrospective.md` |
| 16 | tooling | E2E CI 임계경로가 한 사이클에 3배 — 수집 래칫은 단조 증가, 30분 타임아웃 근거 주석은 아직 122건 기준 | `.github/workflows/ci.yml` |
| 17 | tooling | 새로 넣은 Bash-쓰기 탐지 훅이 «한 번 알린 경로» 를 영구히 침묵시킨다 — 억제 상태가 세션을 넘어 남는다 | `.claude/hooks/detect_protected_bash_write.py` |
| 18 | tooling | #1630 이 만든 «리포트 머지 갭» 축에 생산자 계약이 없다 — 다음 리포트 저자가 head 를 빠뜨리면 즉시 미측정으로 되돌아간다 | `.claude/skills/retrospective/SKILL.md` |
| 19 | tooling | 직전 회고가 지목한 «merged_prs 가 리터럴 HEAD 를 읽는다» 가 미해소 — 새로 붙인 gh 대조는 이 부류를 원리적으로 못 덮는다 | `scripts/retro_scope.py` |
| 20 | process | `context` 가 문자열이 아니라 객체다 — 호출자 브리프가 통째로 소실되고, 범위 대조는 영구히 공허하다 | `.claude/workflows/retrospective.mjs` |
| 21 | process | CLAUDE.md 가 명령하는 「판정식 규칙」의 집행자가 `.claude/**` 와 `.mjs` 를 설계상 못 본다 — 직전 회고 P1-10 미시정 | `scripts/check_witness_set_predicates.py` |
| 22 | process | 이번 창에 신설한 역방향 메모리 가드(#1636)가 리포 루트 좌표를 못 봐 «삭제금지» 라고 적힌 죽은 파일 2건 위에서 초록을 인쇄한다 | `scripts/check_memory_refs.py` |
| 23 | process | 직전 회고 확정 125건 중 9건만 시정됐고, «정본» 이라고 선언된 이월 원장(GitHub Issue)에는 0건이 들어 있다 | `docs/reports/2026-09-07-retrospective.md` |
| 24 | process | 회고 착수 신호가 항상 로드되는 어떤 표면에도 없다 — 직전 회고 P1-3 미시정, 창이 51 → 55 로 계속 자란다 | `CLAUDE.md` |
| 25 | code | #1638 이 Opus 4.7 을 카탈로그에서 내리며 «내린 모델 요율표» 에 넣지 않아, 대시보드 비용이 2.5× 과소 계상된다 | `src/constants.py` |
| 26 | code | pastel 테마에서 PR 필터 활성 버튼 글자가 3.57:1 — #1643 이 세 형제 중 한 줄만 고쳤다 | `src/templates/repo_detail.html` |
| 27 | code | 새 가드가 `:hover` 를 «순간 상태» 라며 면제했는데, WCAG 1.4.3 에 그런 예외가 없고 면제된 네 자리는 실제로 미달이다 | `tests/unit/ui/test_accent_as_text_closure.py` |
| 28 | code | catppuccin 등급 F 칩이 «행에 마우스를 올리면» 3.41:1 로 떨어진다 — 55 PR 짜리 AA 스윕에 hover 축이 없다 | `src/static/css/components.css` |
| 29 | code | 내린 모델에 고정된 리포는 설정 화면이 «전역 기본값» 으로 그려지고, 다음 저장에서 고정이 조용히 지워진다 | `src/templates/settings.html` |
| 30 | code | `retrospective.mjs` 가 세션 컨텍스트 객체를 문자열로 만들지 않아 «[object Object]» 로 흘리고, #1630 의 범위 교차검증이 영영 일치할 수 없다 | `.claude/workflows/retrospective.mjs` |
| 31 | docs | 항상 로드되는 CLAUDE.md 요약이 #1668 이 폐기한 규칙을 그대로 가르친다 — 자기가 지목한 SSOT 와 정면으로 다르다 | `CLAUDE.md` |
| 32 | decision | 회고 확정 125건이 Issue 원장에 0건 등재 — 직전 회고가 이 기전을 두 번 확정했는데 3회차로 재발했다 | `CLAUDE.md` |
| 33 | decision | 「fix 는 사용자 결정」을 선언한 뒤 우선순위를 Grok 권고로 대체해 자율 집행했고, 그 목록은 어디에도 없으며 PR 본문끼리 순서가 어긋난다 | `.claude/skills/retrospective/SKILL.md` |
| 34 | decision | 직전 회고 확정 P1-4·P1-13 이 «브라우저에 도달한 적 없는» CSS 의 정적 계산 위에 서 있었고, 같은 사이클이 전제를 반증했는데 두 항목도 리포트도 정정되지 않았다 | `docs/reports/2026-09-07-retrospective.md` |
| 35 | decision | 직전 회고 확정 P1-3(회고 착수 신호 부재)이 미이행 — 창이 48 → 55 PR 로 커졌고 「임계 15」는 리포 어디에도 없다 | `docs/reports/2026-09-07-retrospective.md` |
| 36 | tooling | retro_scope 가 `unmeasured: []` 을 내면서 4 커밋(후일 PR #1684)이 PR 정체성 없이 범위를 통과했다 — HEAD 가 main 인지 보는 축이 없다 | `scripts/retro_scope.py` |
| 37 | tooling | 회고 하네스가 호출자 컨텍스트를 `[object Object]` 로 소실 — 그리고 범위 가드가 그 공백 위에서 «적발» 을 만들어 냈다 | `.claude/workflows/retrospective.mjs` |
| 38 | tooling | 가드 품질 floor 2종이 이번 사이클 신규 가드 19/19 를 단 한 건도 보지 않는다 — 가드 인구가 tests/ 로 이주했는데 게이트는 scripts/ 에 남았다 | `scripts/check_witness_set_predicates.py` |
| 39 | process | 회고 워크플로가 세션 컨텍스트를 `[object Object]` 로 직렬화해 전 에이전트에 «맥락 0» 을 배포했고, 로그와 범위 가드가 그 사고를 각각 «컨텍스트 有»·«호출자 범위 불일치» 로 잘못 보고한다 | `.claude/workflows/retrospective.mjs` |
| 40 | process | 직전 회고 확정 125건 중 이 사이클이 닿은 것은 9건이고 나머지 ~116건은 원장이 0건 — 그 회고 스스로 P1-11·P1-20 으로 진단한 «등재 없으면 종결 0%» 기전을 자기 산출물에 그대로 재생산했다 | `docs/reports/2026-09-07-retrospective.md` |
| 41 | process | 이 사이클의 지배 작업(UI 17 PR)이 영역 문서에 0줄을 남겼고, 여기서 발명해 가드 5개에 반복 적용한 «잠긴 3종 세트» 관용구는 docs 에 한 번도 등장하지 않는다 — CLAUDE.md 절차 2번이 가리키는 문서가 빈 채로 다음 세션을 맞는다 | `docs/workflow/ui-i18n.md` |
| 42 | code | 회고 워크플로가 객체 `context` 를 문자열로 강제하지 않아, 세션 맥락이 «[object Object]» 로 날아가고 #1630 범위 대조가 상시-참 경보가 된다 | `.claude/workflows/retrospective.mjs` |
| 43 | code | #1638 이 `claude-opus-4-7` 을 카탈로그에서만 내리고 내린-요율표에 옮기지 않아, 화면 비용이 기록 비용의 40% 로 갈렸다 | `src/constants.py` |
| 44 | code | 설정 화면의 모델 셀렉터가 «카탈로그에서 내려간» 저장값을 표시하지 못해, 다음 저장 한 번에 리포별 모델 선택이 조용히 지워진다 | `src/templates/settings.html` |
| 45 | docs | 직전 회고 확정 125건이 Issue 0건으로 끝났고, 55 PR 뒤 docs 확정 항목이 전건 그대로 살아 있다 — 원장 부재 3회 연속 재발 | `docs/reports/2026-09-07-retrospective.md` |
| 46 | decision | 직전 회고 확정 125건 중 ~10건만 착수됐고, 나머지의 «처분»을 담는 면이 리포에 존재하지 않는다 | `docs/reports/2026-09-07-retrospective.md` |
| 47 | tooling | 회고 워크플로가 `context` 를 문자열로 가정해 `[object Object]` 를 뿌린다 — 이 회고 실행에서 실증됨 | `.claude/workflows/retrospective.mjs` |
| 48 | test-guard-coverage | 닫힌 것은 7개 모양 중 2개 — 닫는 중괄호 한 글자를 지우면 스타일시트 63%가 브라우저에서 죽는데 단위 7,973건이 전건 초록 | `tests/unit/ui/test_css_comment_nesting.py` |
| 49 | instrument-calibration | «실제 파서를 통과시킨다» 는 처방이 실측 2/7 — 정규식과 동률이고, 파일을 통째로 죽이는 네 모양을 전부 놓친다 | `tests/unit/ui/test_css_comment_nesting.py` |
| 50 | recurrence | 같은 부류의 세 번째 발생 — 매번 CSSOM 이 진단했는데 매번 텍스트 가드만 남기고 계기를 버렸다 | `tests/unit/ui/test_csp_external_asset_parity.py` |
| 51 | tooling-asymmetry | 같은 HTML 안에서 `<script>` 는 진짜 파서 + 공허화 가드, `<style>` 은 정규식 — CSS 린트는 0개. 제품은 stylelint 어댑터를 갖고도 어디에도 조달하지 않는다 | `package.json` |
| 52 | 운영 실측 (production telemetry) | 작업 절차가 머지에서 끝난다 — 운영 확인 단계가 계약에 없다 | `docs/workflow/deploy.md` |
| 53 | 운영 실측 (production telemetry) | #1638 이 근거로 든 가드는 죽은 모델 id 를 원리적으로 못 본다 — 뮤테이션으로 실증 | `tests/unit/shared/test_pricing_parity.py` |
| 54 | process | 직전 회고가 이 gap 을 4건으로 이미 확정했는데 55 PR 동안 한 줄도 이행되지 않았고, 그 위에 최대 규모 UI 캠페인이 올라갔다 | `docs/reports/2026-09-07-retrospective.md` |
| 55 | ci-budget/unguarded-growth | E2E 시간 예산에 관측자가 0 — 그리고 증분 비용이 초선형이라 남은 여유는 브리프 추정의 절반(≈+121건 · ≈5일) | `scripts/check_e2e_scope.py` |
| 56 | retro/cross-verify | 직전 회고가 이 축을 이미 제기했고 cross-verify 가 «다른 질문에 답해» 기각했다 — 그 반박은 오늘 Grok 이 그대로 재현한다 | `docs/reports/2026-09-07-retrospective.md` |
| 57 | a11y/media-state | 랜딩은 base.html 을 상속하지 않아 전역 모션 감소 리셋이 닿지 않는다 — 전체화면 고정 그라데이션이 reduce 에서도 계속 확대·회전한다 | `src/templates/landing.html` |
| 58 | test-guard/false-enforcer | 이 축의 유일한 관측이 부분문자열 존재 검사다 — 게다가 여섯 선언 중 가장 안 중요한 하나에 걸려 있다 | `tests/integration/test_repo_insights_css.py` |
| 59 | 키보드 조작성(WCAG 2.1.1) / 쌍대 축 … | 분석 표의 행이 마우스 전용 네비게이션 컨트롤 — 포커스를 받을 수 없어 «포커스 표시» 작업이 원리적으로 도달 못 한 자리 | `src/templates/repo_detail.html` |
| 60 | 키보드 조작성(WCAG 2.1.1) / 쌍대 축 … | 두 keydown 핸들러를 통째로 지워도 단위 스위트 7972건 전건 초록 — 조작 축에 가드가 0 | `src/templates/base.html` |
| 61 | 측정 계기 / 쌍대 축 비대칭 | 포커스 스윕이 포커스를 «옮기지 않는다» — CDP forcePseudoState + 「이미 포커스 가능한 마크업」으로 집합을 뽑는 항진명제 | `e2e/test_theme_mobile_guards.py` |

## P2 (77건)

| # | 관점 | 제목 | 좌표 |
|---|---|---|---|
| 1 | process | 회고 착수 신호가 여전히 항상-로드 표면·훅·CI 어디에도 없다 — 직전 회고 P1-3 미이행, 창은 51 → 55 PR 로 커졌다 | `CLAUDE.md` |
| 2 | process | PR 템플릿 채택률이 56건 중 0건 — 그 체크리스트의 「UI 변경 8조합 시각 확인」이 하필 이 사이클의 지배 작업축이었다 | `.github/PULL_REQUEST_TEMPLATE.md` |
| 3 | process | MEMORY 인덱스의 진입점 좌표가 실제 main 보다 6 PR 뒤처졌다 — 파생 가능한 수치를 문서에 복사한 결과 | `CLAUDE.md` |
| 4 | code | 새 «자기 틴트» 가드에 반례 세 가지가 남아 있다 — 세미콜론 없는 마지막 선언 · 두 번째 `background` · `background-image` | `tests/unit/ui/test_self_tint_text_idiom.py` |
| 5 | code | CSS 판정이 전부 정규식이라 «브라우저가 통째로 버리는 규칙» 을 못 본다 — 새 가드는 그 축 중 주석 하나만 닫았다 | `tests/unit/ui/test_css_comment_nesting.py` |
| 6 | docs | ui-i18n.md 의 토큰 추가 절차가 «줄번호» 좌표이고, 이번 사이클 tokens.css 204줄 변경으로 네 개 전부 틀렸다 | `docs/workflow/ui-i18n.md` |
| 7 | docs | doc_review_gate 의 캐시 근거 수치가 10× 낡았다 — 「여유 있게 상회한다」는 주석과 달리 안정 블록은 최소 캐시 길이에 원리적으로 못 닿는다 | `.claude/hooks/doc_review_gate.py` |
| 8 | docs | check_doc_anchors 가 「모든 코드 좌표가 앵커」라고 초록을 내지만, 백틱 밖 줄번호 좌표는 애초에 보지 않는다 | `scripts/check_doc_anchors.py` |
| 9 | docs | README 히어로 스크린샷이 이번 사이클 팔레트 변경을 반영하지 않는다 — 스크립트 자신이 「문서가 거짓을 그린다」고 경고해 둔 축 | `docs/readme/dashboard.png` |
| 10 | docs | #1648 이 토큰 37개를 지우면서 섹션 주석 3개를 고아로 남겼다 — 없는 분류가 있는 것처럼 읽힌다 | `src/static/css/tokens.css` |
| 11 | decision | 다음 사이클을 끄는 유일한 결정 산출물(회고 리포트)만 심의 게이트와 claim-review 양쪽 밖 — 그 처방 하나가 실제로 틀렸다(정밀도 30%) | `.claude/hooks/doc_review_gate.py` |
| 12 | decision | 운영 기본 모델을 바꾼 #1638 의 잔여 위험 2건·운영 확인 3건이 어떤 추적면에도 착지하지 않았다 | `src/ui/routes/settings.py` |
| 13 | tooling | SessionStart 훅이 매 세션 83줄을 주입하는데 실신호는 1줄 — 70줄이 «미참조 파일» 재고 목록이다 | `.claude/settings.json` |
| 14 | tooling | ci.yml 의 e2e 주석이 #1631 이 삭제한 «통과 건수 하한» 을 아직 «유일한 관측면» 으로 가르친다 | `.github/workflows/ci.yml` |
| 15 | process | gh 교차대조의 `n >= floor` 번호 컷이 #1630 커밋 본문이 «Grok 이 반증했다» 고 적은 바로 그 설계를 되살렸다 | `scripts/retro_scope.py` |
| 16 | process | 경계 갭 시정이 «리포트가 head 를 적었는가» 에 의존하는데, 리포트를 쓰라고 지시하는 표면이 그 필드를 요구하지 않는다 | `.claude/skills/retrospective/SKILL.md` |
| 17 | code | «목록이 아니라 파생» 자격증명 가드가 e2e 하네스 한 축에만 걸려, 단위 하네스는 손으로 적은 목록 그대로다 | `tests/unit/scripts/test_e2e_harness_neutralises_credentials.py` |
| 18 | code | Bash 보호경로 탐지 훅이 경로당 «클론 생애 단 한 번» 만 알린다 — 상태 파일이 영원히 지워지지 않는다 | `.claude/hooks/detect_protected_bash_write.py` |
| 19 | code | «잠긴 3종 세트» 등급 토큰의 AA 여유가 0.00~0.04 이고, 계산 도구는 카드 한 면만 모델링한다 | `src/static/css/tokens.css` |
| 20 | code | 기본 모델 id 를 `CLAUDE_DEFAULT_MODEL_ID` 로 모아 놓고도 코드 4곳이 같은 문자열을 다시 적는다 | `src/services/operations_service.py` |
| 21 | docs | 회고 후속 7건이 전부 code·guard·e2e 로 갔고 docs 확정건은 이행 0 — ui-i18n.md 는 이제 103 PR 째 한 글자도 안 바뀌었다 | `docs/workflow/ui-i18n.md` |
| 22 | docs | 파생 대조 가드가 README.ko 만 보던 비대칭을 바로 윗 함수에서 고쳐 놓고 아랫 함수에 그대로 남겼다 — 뮤테이션으로 실증 | `tests/unit/scripts/test_doc_distinguished_values.py` |
| 23 | docs | 이번 사이클이 만든 메모리 역방향 가드가 리포 루트 파일을 구조적으로 못 본다 — 「삭제금지」라 적힌 AGENTS.md 가 부재인데 ✅ 를 인쇄한다 | `scripts/check_memory_refs.py` |
| 24 | docs | 모든 문서 편집을 심의하는 훅의 «범위» 주석이 존재하지 않는 표면 6개를 현행처럼 열거한다 | `.claude/hooks/doc_review_gate.py` |
| 25 | decision | Grok 반증률 83%(57/69) — 내 첫 판단이 6번 중 5번 뒤집히는데 집계하는 곳이 없어 추세가 보이지 않는다 | `CLAUDE.md` |
| 26 | decision | 「옳은가」를 「도달하는가」보다 먼저 물어, 픽셀에 닿지 않는 CSS 를 고치고 그 수정을 핀으로 잡는 시험까지 만들었다 | `src/static/css/components.css` |
| 27 | tooling | doc_review_gate 프롬프트 캐시가 실측으로 죽어 있다(0/0) — 자기 계기가 이미 잡았는데 55 PR 동안 아무 조치가 없었고, 근거 주석은 7배 stale | `.claude/hooks/doc_review_gate.py` |
| 28 | tooling | 범위 집행식이 부분문자열 판정이다 — CLAUDE.md 가 금지한 바로 그 형태가 정책 8-(5) 집행자 안에 있다 | `.claude/workflows/retrospective.mjs` |
| 29 | tooling | Bash-쓰기 탐지 훅의 억제 상태가 영구다 — 클론 수명 동안 경로당 1회만 알리고 그 뒤로는 침묵한다 | `.claude/hooks/detect_protected_bash_write.py` |
| 30 | tooling | CI 주석이 폐기된 처방을 가르친다 — 바로 아래 줄이 그 처방을 버렸다 | `.github/workflows/ci.yml` |
| 31 | tooling | PostToolUse 스모크가 이 사이클의 주 편집면(템플릿·CSS·워크플로)을 전혀 보지 않는다 — 결함이 가장 많은 곳에 조기탐지 0 | `.claude/hooks/posttool_pytest_smoke.py` |
| 32 | tooling | 새로 만든 메모리 역방향 축은 자기 입력이 바뀔 때 발화하지 않는다 — 결함이 생기는 순간이 유일하게 조용한 순간이다 | `.pre-commit-config.yaml` |
| 33 | process | main 이 8.5시간 red 였는데(#1678 시점, codecov 403) 절차 어디에도 «main 초록» 을 확인하는 단계가 없어 그 위로 5 PR 이 그대로 머지됐다 — `fail_ci_if_error: false` 는 그 red 를 막지 못했다 | `.github/workflows/ci.yml` |
| 34 | code | 자격증명 파생 가드의 단어 목록이 `smtp_pass` 를 못 본다 — 「모든 자격증명을 못박는다」는 단언이 거짓이다 | `tests/unit/scripts/test_e2e_harness_neutralises_credentials.py` |
| 35 | code | `.env` 누출 봉인이 e2e 하네스 한 축에만 걸렸다 — 단위 하네스는 여전히 손으로 적은 목록이고 다섯 자격증명이 빠져 있다 | `tests/conftest.py` |
| 36 | code | Bash 보호경로 «탐지» 훅이 경로당 한 번만 알리고 클론 수명 내내 영구 침묵한다 | `.claude/hooks/detect_protected_bash_write.py` |
| 37 | code | 죽은 토큰 가드의 «소비자» 집합이 `.json` 을 제외하는데, i18n 번역문이 실제로 CSS 변수를 소비한다 | `tests/unit/ui/test_no_dead_design_tokens.py` |
| 38 | code | 모델 카탈로그 재확인(#1638)이 Haiku 항목의 날짜 접미사 id 를 그대로 두어, 앱이 같은 모델을 두 이름으로 부른다 | `src/constants.py` |
| 39 | docs | STATE.md 의 E2E 수치 4사본 중 2곳이 어떤 가드에도 안 걸리고 --fix 도 파생하지 않는다 — 이 창에서 28회 손으로 고쳐졌다 | `docs/STATE.md` |
| 40 | docs | 이 창이 세운 죽은-좌표 가드(#1636)가 «메모리 → 리포» 한 방향뿐 — 리포 안의 죽은 문서 정본 인용 34파일은 밖에 있고, 가드 자신이 없는 파일을 판정 근거로 든다 | `scripts/check_architecture_tree_sync.py` |
| 41 | docs | ui-i18n.md 가 UI 30여 PR 내내 0줄 변경 — tokens.css 좌표는 거짓을 넘어 «더 틀려졌다»(블록 4 → 9), 문서를 따르면 이 창이 고친 결함을 재생산한다 | `docs/workflow/ui-i18n.md` |
| 42 | docs | pipeline.md 의 「분석기 추가」 절차가 존재하지 않는 문자열을 편집 대상으로 처방하고, 같은 절 제목이 분석기 수의 무방비 4번째 사본이다 | `docs/workflow/pipeline.md` |
| 43 | decision | «사용자 결정 = 보류» 로 네 번 기록된 W15 가 재개됐는데, 재개 결정의 주체·근거가 원장에 없다 | `CLAUDE.md` |
| 44 | decision | 실제 과금이 나간 사고(#1662)의 유일한 후속이 머지된 PR 본문에만 남았고, 규모는 측정 가능한데 측정되지 않았다 | `src/services/dashboard_service.py` |
| 45 | decision | #1638 이 승인 경계를 한쪽에만 적용해, 알려진 «조용한 덮어쓰기» 경로를 추적면 없이 열어 뒀다 | `src/constants.py` |
| 46 | tooling | E2E 잡이 한 사이클에 3.6분 → 17.9분(5배)으로 늘어 required check 의 30분 벽 60% 에 도달 — 근거 주석은 122건에서 멈춰 있다 | `.github/workflows/ci.yml` |
| 47 | tooling | pre-push 게이트의 «못 보는 축» 목록에 E2E 잡만 빠져 있다 — 사이클 내 CI-only e2e 실패 3건 | `scripts/pre_push_gate.py` |
| 48 | tooling | 새 Bash-쓰기 탐지 훅이 경로당 1회만 말하고 영구히 침묵한다 — 상태 파일에 만료·해제가 없다 | `.claude/hooks/detect_protected_bash_write.py` |
| 49 | tooling | 어떤 워크플로에도 `concurrency:` 그룹이 없어 덧쓰인 푸시의 18분짜리 E2E 가 끝까지 돈다 | `.github/workflows/ci.yml` |
| 50 | tooling | main 이 SonarCloud 403 으로 red 였는데 다음 머지의 초록이 그 신호를 덮었다 — 관측기가 «최신 1건» 만 본다 | `scripts/check_main_red.py` |
| 51 | derived-falsehood | 텍스트 판정 위에 세운 파생 가드가 함께 거짓말한다 — 「죽은 토큰 0」은 components.css 가 브라우저에 산다는 미검증 전제 위에 있다 | `tests/unit/ui/test_no_dead_design_tokens.py` |
| 52 | observability | e2e 는 스타일시트 무결성을 한 번도 보지 않는다 — 깨져도 증상으로만 간접 관측돼 귀속이 불가능하다(내가 직접 겪었다) | `e2e/test_state_indication.py` |
| 53 | known-wrong-idiom | 「두 번째로 싼, 틀린 과정」이라고 스스로 적은 정규식이 형제 파일에서 그대로 쓰이고 있다(현재 위반 0건 · 잠복) | `tests/unit/ui/_contrast.py` |
| 54 | 운영 실측 (production telemetry) | 운영 KPI 가 «가정» 을 재고, 진실이 담긴 표는 같은 세션을 손에 쥐고도 안 읽는다 | `src/services/operations_service.py` |
| 55 | 운영 실측 (production telemetry) | #1638 이 카탈로그 4종 중 3종만 올렸다 — 남은 Haiku 는 16개월 된 날짜 스냅샷이고 자기 코드베이스와도 어긋난다 | `src/constants.py` |
| 56 | 운영 실측 (production telemetry) | 이 회고가 도는 작업트리를 다른 에이전트가 동시에 오염시키고 있다 — 내 실측의 격리가 깨졌다 | `src/static/css/components.css` |
| 57 | tooling | 포커스 캠페인은 Firefox·WebKit 에 «원리적으로 못 돌린다» — 계기가 Chromium 전용 API 로 짜여 있어 「conftest 에 firefox 를 추가」가 처방이 아니다 | `e2e/test_theme_mobile_guards.py` |
| 58 | code | 같은 창에서 엔진 접두사 비대칭이 4건 «새로» 추가됐다 — `backdrop-filter` 28 사이트 중 23곳이 `-webkit-` 짝 없이 있고, 짝을 쓴 5곳이 저자가 필요성을 알았다는 증거다 | `src/static/css/components.css` |
| 59 | code | #1627 의 짝 가드가 «자기가 만들어진 그 파일 안에서» 이미 회피되고 있다 — 회고 #70 이 지목한 자리가 실물로 살아 있다 | `tests/unit/ui/test_focus_indicator.py` |
| 60 | tooling | 회고 #33 이 「축이 파라미터가 아니라 리터럴」이라 적은 뒤의 사이클이 그 리터럴을 25개 «추가»했다 — 뷰포트 축 분모도 여전히 1 | `e2e/test_theme_mobile_guards.py` |
| 61 | ci-budget/false-basis | 「실측 ~10초/건」은 stale 이 아니라 **출생 시 거짓**(5.4× 오차) — 30분 벽은 그 거짓 수의 1.5배이고, 지금 17.9분이라 눈대중 점검이 거짓 초록을 준다 | `.github/workflows/ci.yml` |
| 62 | instrument/absent | 벽에 닿는 순간 쓸 계기가 0 — `--durations` 가 리포 어디에도 없고, 수집분의 63%가 파일 하나에 몰려 있다 | `.github/workflows/ci.yml` |
| 63 | guards/orphaned-claim | `pre_push_gate.py` 에 사라진 가드의 동작을 현재형으로 서술하는 고아 주석 — 같은 병의 별건 | `scripts/pre_push_gate.py` |
| 64 | a11y/forced-colors | forced-colors 선언 0건 — 리포가 스스로 기록한 «색만으로 나르는 상태» 들이 그 모드에서 아무것도 나르지 않는다 | `tests/unit/ui/test_state_indication.py` |
| 65 | retro/root-cause | 폐쇄 가드를 «앱 안에 정본이 있는 열거» 에만 걸었다 — 계기가 앱에 쓰는 방식이라, 앱에 쓸 수 없는 상태는 원리적으로 프레임 밖이었다 | `tests/unit/ui/test_a11y_route_coverage.py` |
| 66 | dead-code | 모션 감소 방어가 죽은 선택자에 배분됐다 — #1651 의 죽은-CSS 사냥이 템플릿 인라인 `<style>` 을 안 훑었다 | `src/templates/base.html` |
| 67 | ARIA 계약 / 키보드 | `role="menu"` 가 약속한 키보드 계약이 구현돼 있지 않다 — 화살표·Escape·roving tabindex 전무 | `src/templates/base.html` |
| 68 | 포커스 관리 / 쌍대 축 비대칭 | 언어 변경이 포커스를 버린다 — 같은 파일의 테마 팔은 `toggleBtn.focus()` 로 되돌리는데 언어 팔만 열려 있다 | `src/templates/base.html` |
| 69 | 측정 계기 / 셀렉터 정확도 | `[role=menuitem]` 은 `role="menuitemradio"` 를 매치하지 않는다 — 테마·언어 옵션 7개가 24px 타깃 스윕 밖 | `e2e/test_theme_mobile_guards.py` |
| 70 | 쌍대 축 비대칭 / CSS | `:hover` 93 대 `:focus-visible` 13, 짝을 강제하는 가드 0 | `src/templates/repo_detail.html` |
| 71 | guard-false-green | #1636 이 연 «역방향» 축이 정작 이 WBS 가 쓰는 단어를 안 본다 — `진입점` 은 처방이 아니다 | `scripts/check_memory_refs.py` |
| 72 | guard-false-green | 처방 줄 위의 «값» 은 어떤 값이든 무판정 — SHA·PR 번호·테스트 수를 통째로 날조해도 exit 0 | `scripts/check_memory_refs.py` |
| 73 | guard-false-green | 훅은 «기준선을 무효화한 바로 그 5 커밋» 에서 전부 발화했고, 전부 초록이었다 — 두 수치가 한 프로세스 안에 있었는데 잇는 규칙이 없다 | `.pre-commit-config.yaml` |
| 74 | unfalsifiable-metric | 표제 수치 «미관측 팔 129 → 46/410» 은 재측정 불가 — 계기를 커밋하지 않았는데, 커밋된 e2e 두 곳이 그 없는 계기를 심판으로 지목한다 | `e2e/test_theme_mobile_guards.py` |
| 75 | ssot-violation | 근본 원인은 «가드 부재» 가 아니라 SSOT 위반 — 드리프트한 값 4종이 전부 추출 가능하고, 파일 스스로 「Issue 가 정본」이라 적었다 | `scripts/check_memory_refs.py` |
| 76 | honest-coverage | 잔여 blind-spot 원장이 «고른 값 타입 안에서만» 정직하다 — 다음 읽는 사람은 전수 커버로 읽는다 | `tests/unit/scripts/test_check_memory_refs.py` |
| 77 | process-gap | 쓰는 쪽 절차가 아예 없다 — 리포 문서 전체에 메모리 갱신을 지시하는 문장이 0건 | `CLAUDE.md` |

## 오탐 (다음 회고가 다시 판정하지 않도록)

| 관점 | 제목 | 기각 사유 |
|---|---|---|
| tooling | PR 템플릿 채택률이 55건 전부 0% — 반면 가드가 걸린 Grok 흔적은 비봇 52/52. 대조가 «가드 없는 지시 표면» 의 ROI 를 확정한다 | 모든 인용 좌표는 정확하다(PULL_REQUEST_TEMPLATE.md:5 '## 체크리스트' · :14 '## 🔍 사용자 검증 필요' · :22 '## MCP 자율 실행' · check_claim_review_trace.py:1~40 · pre_push_gate.py:86 등재). 원시 카운트 3개(0·0·0)도 55건 재측정으로 그대로 재현된다. 그런… |
| process | 경계 갭 시정(#1630)이 직전 회고 «리포트 자신의 PR» 을 매 사이클 결정적으로 다시 센다 — 이번 창의 #1629 | 인용은 전건 재현됐다. `scripts/retro_scope.py` = `scan_from = boundary` → `if newest and (rh := report_head(newest)): scan_from = rh` (실재). `docs/reports/2026-09-07-retrospective.md` = `· head · ``03855b12`` … |
| docs | verify.md §CI 가 9개 job 중 5개만 열거 — lint-src·lint-js-nonvacuous·dependency-audit 은 추적 문서 어디에도 없다 | 인용 좌표는 실재한다(`docs/workflow/verify.md` = 「### CI (`.github/workflows/ci.yml` …)」, 그 아래 불릿 5개 / `.github/workflows/ci.yml` job 9개: secret-scan:30 · lint-changed-tests:96 · repo-integrity:156 · lint-src… |
| decision | W20 «완료» 근거가 같은 원장 안에서 반증됐는데 닫힘 판정만 정정되지 않았다 | 주장의 두 전제가 실측으로 무너진다. 【전제1「닫힘의 근거 두 축이 무너졌다」 — 반증】 PR #1645(`e70e859d`)가 실제로 옮긴 칩은 5곳이고, 인용된 반증 두 줄은 그중 **`.severity-low` 한 곳**만 가리킨다. 나머지 넷의 현재 상태(HEAD `2613028e` 실측): - `.issue-badge--closed` — `src… |
| build-and-doc-truth | `npm run build` 는 브라우저가 읽는 6,734줄 중 0줄을 읽는다 — 그런데 verify.md 는 e2e 를 「CSS 빌드 후」로 적는다 | 좌표 3건은 전부 실재한다(`src/static/css/main.css` = `@import "tailwindcss";` 단독 · `package.json` 입력 = `main.css` 단독 → `dist/tailwind.css` · `docs/workflow/verify.md` = 「`e2e` — CSS 빌드 후 …」). 구조적 사실(7개 수기 스타일시… |
| 운영 실측 (production telem… | 모델 id 실패는 기본점수 17/17/7 로 흡수되고, 그 차단은 이 리포의 «사람이 머지한다» 규칙 때문에 신호를 못 낸다 | 주장의 중심 추론 — 「fail-closed 는 참이지만, 그것이 사람에게 도달하는 경로가 이 리포에는 없다」 — 이 코드로 반증된다. 주장은 관측 축을 **auto-merge/approve 하나만** 놓고 봤고, 그 축은 확실히 「사람이 머지한다」 워크플로에서 조용하다. 그러나 `api_error` 가 사람에게 닿는 **무조건 경로가 최소 3겹** 더 … |
| 운영 실측 (production telem… | 운영 계기가 전부 꺼져 있다 — 안 쓴 게 아니라 «닿지 않는다», 26일 전엔 닿았다 | 인용은 실재한다 — `src/analyzer/io/ai_review.py` 에 「🔴 **운영 실측으로 정한 값** (2026-08-21, claude_api_calls 847 시도)」 원문 그대로 존재(추가 커밋 `352be054` fix(analyzer) … #1467, 2026-08-22). 그러나 **결론은 직접 측정으로 반증됐다.** 브리프가 요구… |
| tooling | 수집 건수 baseline 과 skip allowlist 가 «엔진 확장의 비용» 을 인위적으로 올린다 — 가드가 확장을 벌하는 구조 | 인용 3종은 전부 EXACT 실재(ci.yml:769 = `python -m playwright install --with-deps chromium` · EXPECTED_COUNT=396 · SKIP_ALLOWLIST 「양방향으로 red」 헤더). 그러나 핵심 기전이 반증된다. (1) 방향 오류 — `scripts/check_e2e_scope.py` 계약… |
| code | 엔진 분기 표면은 52 선언인데 moz 를 인식하는 파일은 하나뿐이고, 그 하나도 슬라이더 손잡이만 본다 | 인용은 실재한다 — HEAD 2613028e 에서 src/templates/settings.html:238 은 `.threshold-ctrl input[type=range] { ...; -webkit-appearance:none; outline:none; cursor:pointer; }` 이고, `grep -rln -- "-moz-" tests/` 는 t… |
| ci-budget/no-lever | 벽에 닿았을 때 당길 레버가 미리 정해져 있지 않다 — 병렬화는 미설치, 샤딩은 required check 이름 계약과 충돌, 남는 건 근거 없는 숫자 상향뿐 | 인용은 전건 일치하나(xdist 리포 전체 0건 · branch-protection.md:20 「이름 변경 = 4곳」 · L17 `E2E (Playwright)` · ci.yml:728 경고 · L737 `timeout-minutes: 30` 유일), 결론을 지탱하는 핵심 전제가 리포 내부 반례로 무너진다. 레버 (2) 샤딩이 「하는 순간 영영 pendi… |
| backstop-honesty | CI 제외는 옳지만, 옆의 «백스톱» 헤더가 제공하지 않는 커버리지를 광고한다 — CI 에 넣으면 공허한 초록이 된다 | 인용 좌표는 전부 실재하나, 주장된 결함이 **인용된 줄 자체에 의해 반증**된다. (1) 「헤더가 광고하고 괄호가 조용히 뺀다」— ci.yml:152 헤더 2행이 승격 대상을 명시 열거하고(docs↔README 배지·cycle-history TOC 앵커·config↔env-vars·RepoConfig 3-layer), check_memory_refs·c… |

## 다음 회고를 위한 경계

- 다음 범위의 하한은 **이 리포트를 추가한 커밋** 이다.
- 🔴 회고를 **`main` 에서** 돌린다. 피처 브랜치 tip 을 head 로 두면 P0 가 그대로 재발한다.
- 🔴 `context` 는 **문자열** 로 넘긴다. `--json` 출력을 파싱해 객체로 주면 프롬프트에서
  `[object Object]` 가 되어 전 에이전트가 세션 맥락을 잃는다.
- 이번 창에 `#1684` 가 포함됐음을 기억한다 — 기계는 `#1683` 까지만 셌다.
