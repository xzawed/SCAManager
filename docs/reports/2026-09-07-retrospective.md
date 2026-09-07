# 회고 2026-09-07 — `#1569~#1627`

## 범위 — 기계 산출과 실제가 다르다 (P0 참조)

| | 값 |
|---|---|
| 기계 산출 범위 | `#1569~#1627 (48 PR, boundary 543ceda .. head 03855b12)` |
| 경계 커밋 | `543ceda` (직전 리포트 `2026-08-29-retrospective.md` 추가 커밋) |
| head | `03855b12` |
| 기계가 센 PR | **48건** |
| 🔴 실제 머지 PR | **51건** — `#1600`·`#1602`·`#1603` 은 base 가 main 이 아니라 열거에서 사라졌다(P0) |
| 🔴 경계 갭 | `#1564`·`#1567` 은 직전 범위(상한 #1563)에도 이 범위에도 없다(P1-1) |

재현:

```bash
py -3 scripts/retro_scope.py --json          # 기계 산출 48건
gh pr list --state merged --limit 100 --json number,baseRefName \
  --jq '[.[]|select(.number>=1569 and .number<=1627)]|length'   # 실제 51건
```

## ROI

| 지표 | 값 |
|---|---|
| 라운드 (loop-until-dry) | 3 |
| 총 발견 | 147 |
| 확정 | **125** |
| 오탐 차단 | 22 |
| 심각도 조정 | 31 |
| verdict 커버리지 | 1 |
| 미검증 잔여 | 0 |
| 실행 중 범위 이동 | 없음 |
| P0 / P1 / P2 | 1 / 44 / 80 |

에이전트 173 · 오류 0 · 2h01m. 5관점(process·code·docs·decision·tooling) 비중복 finder → 확정 전건 cross-verify.

## P0 (1건)

### 스택 PR 3건이 기계 산출 범위를 통째로 빠져나갔다 — 정책 8-(5) 가 막으려던 바로 그 사건이 다른 기전으로 재발

- 좌표: `scripts/retro_scope.py` — 줄번호가 아니라 아래 근거의 인용 문자열이 앵커다
- 주장: 이 사이클에 머지된 PR 은 48건이 아니라 51건이다. #1600·#1602·#1603 은 base 가 main 이 아니라 `fix/doc-distinguished-values`(#1599) 여서 main 의 squash 제목에 `(#N)` 을 남기지 않았고, `scripts/retro_scope.py` 의 열거에서 사라졌다. 그 셋은 +722/-49 줄이며, 그 안에 이번 사이클 `.claude/hooks/doc_review_gate.py` 의 **유일한** 변경(#1602 — 「지시 표면 하나가 미심의였고, 프롬프트 유실이 조용한 검토자 교체였다」)이 들어 있다. 즉 심의 게이트를 고친 PR 이 회고 심의를 빠져나갔다.
- 근거: scripts/retro_scope.py `out = _git(["log", "--format=%s", f"{boundary}..HEAD"])` +  `tail.isdigit()` — main 제목의 말미 `(#N)` 만 센다. `gh pr view` 실측: #1600/#1602/#1603 모두 state=MERGED, baseRefName=`fix/doc-distinguished-values`, mergeCommit OID(8325b05d·a00a604d·00dbc5bc)는 `git cat-file -t` 에서 `fatal: bad object` — main 에 그 SHA 가 없고 내용은 d6bdde1f(#1599) 한 커밋에 접혀 있다. `git log --oneline 543ceda..03855b12 -- .claude/hooks/doc_review_gate.py` → d6bdde1f 단 1건. tests/unit/scripts/test_retro_scope.py 의 18개 테스트 중 base≠main 케이스는 0건. 파일 자신의 docstring:4-16 이 「가장 검증이 덜 된 코드가 회고를 피해간다」를 막으려 만들어졌다고 적는다.
- 처방: `merged_prs` 를 로그 파싱 단독으로 두지 말고 GitHub 쪽 집합과 **대조**해 차집합을 보고하게 한다 — `gh pr list --state merged --json number,mergeCommit,baseRefName,mergedAt` 로 창을 받아 (a) mergeCommit 이 boundary..HEAD 조상인 것 (b) base 가 이 창의 head 브랜치인 것 을 합집합하고, 로그 산출과 다르면 `ok:false` 가 아니라 **양쪽을 다 실어** 회고가 판단하게 한다. 회귀 테스트로 「base 가 main 이 아닌 머지 PR 이 열거에 남는가」를 추가한다.

## P1 (44건)

| # | 관점 | 제목 | 좌표 |
|---|---|---|---|
| 1 | process | 회고 경계 갭 — 직전 회고의 «처방 PR» 이 모든 회고 범위에서 구조적으로 빠진다 | `scripts/retro_scope.py` |
| 2 | process | 충돌 해소의 `git checkout origin/main -- <경로들>` 이 이미 머지된 자기 수정을 조용히 되돌렸다 — 전 가드 초록 상태로 15시간 | `docs/workflow/pipeline.md` |
| 3 | process | 회고 착수 신호가 «항상 로드되는 어떤 표면에도» 없다 — 카덴스 집행은 삭제됐고 대체가 없다 | `CLAUDE.md` |
| 4 | code | 이슈 심각도 칩이 밝은 테마에서 1.51~2.46 — #1614 가드가 같은 파일을 읽으면서 `[abcdf]` 로 좁혀 지나쳤다 | `src/templates/analysis_detail.html` |
| 5 | docs | 직전 회고 리포트의 범위 헤더가 거짓이고, 적힌 재현 명령이 그 값을 재현하지 못한다 | `docs/reports/2026-08-29-retrospective.md` |
| 6 | docs | CLAUDE.md 가 「강제한다」고 적은 앵커 가드가 architecture.md 의 줄번호 좌표 2건을 보지 못한다 | `docs/architecture.md` |
| 7 | decision | 회고 범위 기계가 커밋 «제목» 만 읽어 스택 PR 3건이 원리적으로 회고를 빠져나간다 | `scripts/retro_scope.py` |
| 8 | decision | 유일한 결정 원장 [WBS] #1621 이 생성 후 한 번도 갱신되지 않아 양방향으로 거짓이다 | `CLAUDE.md` |
| 9 | tooling | 훅 3종이 전부 `Write\|Edit\|MultiEdit` 매처 — Bash 로 파일을 고치면 심의·차단·스모크가 통째로 우회된다 | `.claude/settings.json` |
| 10 | tooling | 정책 8-(5) 집행부가 «부분문자열 포함» 으로 범위 소속을 판정한다 — 그리고 그 판정식 가드는 `.claude/**` 를 아예 안 본다 | `.claude/workflows/retrospective.mjs` |
| 11 | process | 회고 후속의 종결률이 «Issue 등재 여부» 하나로 100% 대 0% 로 갈렸다 | `docs/reports/2026-08-29-retrospective.md` |
| 12 | process | 스택 PR 3건이 main 커밋 제목에 남지 않아 회고 범위에서 통째로 사라졌다 — retro_scope 가 존재 이유로 삼은 시나리오 | `scripts/retro_scope.py` |
| 13 | code | 심각도 뱃지 6종이 light·pastel 에서 AA 1.51~2.46 — 가드가 `[abcdf]` 로 좁혀 «심각도» 를 못 본다 | `src/templates/analysis_detail.html` |
| 14 | code | `--danger/--warning/--success` 를 «글자» 로 쓰는 45곳에 짝 토큰이 없다 — 12조합 중 8건 AA 미달 | `src/templates/analysis_detail.html` |
| 15 | code | E2E 대량-skip 하한이 래칫되지 않았다 — 수집 122→200(+64%) 인데 `--e2e-min-passed=100` 그대로(관측 범위 82%→50%) | `.github/workflows/ci.yml` |
| 16 | code | #1626 이 닫은 「열거 가드」 형태를 38분 뒤 #1627 이 그대로 다시 만들었다 — range 슬라이더 템플릿 목록·테마 목록에 폐쇄 가드 없음 | `tests/unit/ui/test_focus_indicator.py` |
| 17 | docs | ui-i18n.md 의 tokens.css 줄번호 좌표가 이번 사이클에 조용히 거짓이 됐다 — 앵커 가드는 콜론이 없어 못 본다 | `docs/workflow/ui-i18n.md` |
| 18 | decision | 사용자에게 올린 판단을 사용자 응답 기록 없이 스스로 집행했고, 그 진입점 Issue 는 한 번도 갱신되지 않았다 | `CLAUDE.md` |
| 19 | decision | WBS #1557 이 살아 있는 잔여 3건을 이름까지 적고 닫혔는데 후속 Issue 가 0건 — CLAUDE.md 가 지정한 진입점에서 사라졌다 | `tests/unit/analyzer/test_adapter_fail_open_inventory.py` |
| 20 | decision | 직전 회고가 확정 103건 중 13건만 문서에 남겨 놓고 「착수 순서는 사용자 판단」을 요청했다 — P2 69건은 어디에도 없다 | `docs/reports/2026-08-29-retrospective.md` |
| 21 | tooling | 증거집합 술어 가드가 src/scripts 만 보고, 이번 사이클의 실제 미탐은 전부 tests/e2e 의 열거에서 났다 | `scripts/check_witness_set_predicates.py` |
| 22 | tooling | e2e 측정축마다 경로 목록이 따로 손으로 유지돼, HTML 라우트 10개 중 2개가 어떤 대비·포커스 축에도 없다 | `e2e/test_theme_mobile_guards.py` |
| 23 | tooling | check-memory-refs 훅이 전체상태·산문 민감·pre-commit 전용 — 리포의 모든 커밋을 막았고, 무관한 PR 에 동반 변경을 강제했다 | `.pre-commit-config.yaml` |
| 24 | process | retro_scope 가 스택 PR 을 구조적으로 못 본다 — 이번 창에서 3건(#1600·#1602·#1603)이 회고 범위를 통과했고 그중 하나가 심의 훅 자신이다 | `scripts/retro_scope.py` |
| 25 | process | 「다른 세션·PC 진입점」으로 만든 WBS #1621 이 생성 이래 한 글자도 갱신되지 않았다 — 그 사이 3 PR 이 열린 축을 닫았고, 후속 PR 이 본문 전제를 거짓으로 실측했다 | `CLAUDE.md` |
| 26 | code | 신뢰도 판정에 절이 추가됐는데 그것을 강제하는 캐시 계약 가드가 초록으로 통과했다 — 표본이 새 키를 담지 않는다 | `tests/unit/scorer/test_reliability_cache_contract.py` |
| 27 | code | E2E 전건-skip 방어선이 사이클 중 65% 늘어난 스위트를 따라가지 않아 절반이 조용히 사라질 수 있다 | `.github/workflows/ci.yml` |
| 28 | docs | #1606 이 참인 문장을 지우고 거짓 문장을 새로 심었다 — 「개발용 기본값으로 넘어가는 경로는 없습니다」는 실측 반증됨 | `README.md` |
| 29 | docs | pipeline.md 「분석기 추가」가 이 사이클이 24개 어댑터에서 폐기한 관용구를 아직 처방한다 — 직전 회고가 지목했고, 같은 파일을 두 번 고치면서 건너뛰었다 | `docs/workflow/pipeline.md` |
| 30 | docs | UI 21건이 남긴 지식이 영역 문서에 0줄 — ui-i18n.md 는 이 사이클 이전(#1545)에서 멈춰 있고, 반복된 근본원인(가드 열거 밖 표면)에 대응하는 절차가 없다 | `docs/workflow/ui-i18n.md` |
| 31 | decision | 직전 회고의 범위 헤더가 거짓이고 재현 불가 — `merged_prs` 가 `origin/main` 이 아니라 리터럴 `HEAD` 를 읽는다 | `docs/reports/2026-08-29-retrospective.md` |
| 32 | tooling | e2e 전건-skip 하한이 스위트 65% 성장 동안 상수로 남아 «유일한 관측면» 이 5배 약해졌다 | `.github/workflows/ci.yml` |
| 33 | tooling | 회고 산출물이 지시 표면 중 유일하게 심의 게이트 밖이고, 그 결과 기전이 틀린 처방이 다음 사이클을 끌었다 | `.claude/hooks/doc_review_gate.py` |
| 34 | tooling | 손으로 적는 열거형 UI 가드 — #1626 이 대가를 치르고 배운 폐쇄 단언을 같은 사이클의 형제 가드 3개에 적용하지 않았다 | `tests/unit/ui/test_chart_grid_color.py` |
| 35 | process | 회고 5관점에도 db.md 절차에도 «운영 행을 세는» 단계가 없다 — 사전승인된 무료 관측을 제도가 요구하지 않는다 | `docs/workflow/db.md` |
| 36 | ui-a11y-guard-enumerat | `outline:none` 가드가 «이미 아는 파일 3개» 만 읽는다 — 주석은 「새 자리가 생기면 red」라고 거짓을 말한다 | `tests/unit/ui/test_focus_indicator.py` |
| 37 | ui-a11y-guard-enumerat | e2e 접근성 스윕이 HTML 라우트 10개 중 8개만 연다 — 라우트 표와 대조하는 검사가 없다 | `e2e/test_theme_mobile_guards.py` |
| 38 | ui-a11y-guard-enumerat | «값으로 대상을 고르는» e2e 감사와 «선택자를 손으로 핀» 구조 가드의 교집합에 구멍 — `--accent-text` 소비처 14곳 중 6곳만 잠겨 있다 | `tests/unit/ui/test_accent_text_contrast.py` |
| 39 | retro-process | 처방은 이 창 안에서 이미 발명됐는데 38분 뒤 PR 이 다시 손 목록을 만들었다 — 교훈이 한 PR 도 전파되지 않았다 | `tests/unit/ui/test_focus_indicator.py` |
| 40 | ci-guard/threshold-dri | e2e 통과 하한 100 이 baseline 200 에서 파생되지 않아 «절반이 skip 돼도 초록» — 이 창에서 분해능 82.6%→50% 로 붕괴 | `.github/workflows/ci.yml` |
| 41 | test-guard/vacuous-ass | 하한 가드의 유일한 단언이 부분문자열이라 `--e2e-min-passed=0`(게이트 완전 비활성)이 초록으로 통과한다 | `tests/unit/scripts/test_e2e_scope_guard.py` |
| 42 | process/memory | «다음 시작점» 3건이 전부 죽은 좌표 — 하나는 삭제된 파일을 가리킨다 | `C:\Users\dirtc\.claude\projects\d--Source-SCAManager\memory\MEMORY.md` |
| 43 | process/memory | 메모리→리포 문서 포인터 27건 중 22건(81%)이 dangling — 메모리의 지배 전략이 무너졌다 | `C:\Users\dirtc\.claude\projects\d--Source-SCAManager\memory\project-retro-2026-07-26.md` |
| 44 | process/protocol | 회고 프로토콜이 «다음 회고»의 앵커만 fail-closed 로 지키고 «다음 세션»의 앵커는 지키지 않는다 | `D:\Source\SCAManager\.claude\skills\retrospective\SKILL.md` |

## P2 (80건)

| # | 관점 | 제목 | 좌표 |
|---|---|---|---|
| 1 | process | stacked PR 자식은 회고 범위에서 원리적으로 안 보인다 — 실제 51건 중 48건만 계수 | `scripts/retro_scope.py` |
| 2 | process | 6일·21 PR 짜리 UI 감사가 «진입점 없이» 진행되고, WBS 추적 Issue 는 마지막 날에 생겼다 | `CLAUDE.md` |
| 3 | code | `score_is_unreliable` 판정이 바뀌었는데 캐시-드리프트 가드가 초록 — 새 마커가 표본에 원리적으로 들어갈 수 없다 | `tests/unit/scorer/test_reliability_cache_contract.py` |
| 4 | code | 운영자 opt-out 이 `no_dedicated_observer` 로 오분류 — 집계에서 조용히 빠지고 알림 문구가 사실과 다르다 | `src/analyzer/io/static.py` |
| 5 | code | `--accent-text`·`--focus-ring` 이 signature 변종에서 짝을 잃는다 — 대비 계기가 그 블록을 구조적으로 안 본다 | `src/static/css/tokens.css` |
| 6 | code | 회고 브리프 범위가 기계 산출과 어긋나 48건 중 46건이 검토를 빠져나갈 뻔했다 | `docs/reports/2026-08-29-retrospective.md` |
| 7 | docs | #1599 가 세운 「분석기 수 파생 대조」 가드가 같은 값의 4번째 사본(pipeline.md)을 빼놓았다 | `docs/workflow/pipeline.md` |
| 8 | docs | E2E 하한이 121→200 성장 동안 100 에 고정 — 가드 주석의 파생 수치가 거짓이 됐고 README 배지가 그 위에 선다 | `tests/unit/scripts/test_e2e_scope_guard.py` |
| 9 | docs | CLAUDE.md 3번의 새 예외 「측정-only」가 저장소 어디에도 정의돼 있지 않다 | `CLAUDE.md` |
| 10 | docs | README 의 정적분석 언어 목록·조달 계약이 kotlin 에 대해 선언만 참이다 (#1592 가 뽑아낸 「선언≠도달 가능」) | `README.md` |
| 11 | docs | src/scripts/ 만 CLAUDE.md 영역 문서 표에 행이 없다 — 이 사이클에 그 안의 지시 표면이 심의 대상이 됐는데도 | `CLAUDE.md` |
| 12 | docs | 로컬 전용 PROJECT_OVERVIEW.md 가 STATE 와 정면으로 모순되는 수치를 든 채 어떤 가드도 닿지 않는다 | `docs/superpowers/PROJECT_OVERVIEW.md` |
| 13 | decision | 스스로 「사람에게 남기는 유일한 판단」이라 선언한 항목을 스스로 권장안대로 이행했고, 그 근거가 어떤 산출물에도 없다 | `CLAUDE.md` |
| 14 | decision | 10개 PR 이 연속으로 「사용자 결정」이라 올린 브랜드 면색 건이 인계 원장에 한 글자도 없다 | `CLAUDE.md` |
| 15 | decision | #1599 squash 가 심의 게이트와 템플릿 변경을 `fix(docs):` 한 줄로 덮어 main 이력의 변경 성격이 거짓이다 | `CLAUDE.md` |
| 16 | tooling | e2e 「최소 통과 건수」 하한이 100 에 얼어붙은 채 스위트는 200 으로 자랐다 — 절반이 조용히 skip 돼도 CI 초록 | `.github/workflows/ci.yml` |
| 17 | tooling | CI 주석에 박힌 파생 수치가 거짓 — 이번 사이클이 analyzer·문서에서 정확히 이 클래스를 걷어낸 그 창에서 ci.yml 만 남았다 | `.github/workflows/ci.yml` |
| 18 | tooling | UI 가드의 손유지 열거 상수들 — #1626 이 증명한 «파생-대조» 패턴이 형제 가드에 이식되지 않았다 | `tests/unit/ui/test_chart_grid_color.py` |
| 19 | process | 다중 세션 UI 트랙이 15 PR 중 12건을 머지한 뒤에야 [WBS] 진입점 Issue 를 얻었다 | `CLAUDE.md` |
| 20 | process | 충돌 해소 명령이 자기 수정을 통째로 되돌렸고, 탐지는 우연이었다 | `docs/reports/2026-08-29-retrospective.md` |
| 21 | process | 사이클 자신의 산출물을 되고치는 PR 이 최소 4건 — 계기를 먼저 검증하지 않고 트랙을 시작했다 | `docs/reports/2026-08-29-retrospective.md` |
| 22 | process | MEMORY.md 의 프로젝트 항목이 2026-07-26 에서 멈췄다 — 최근 두 사이클의 서사가 세션 진입점에 없다 | `docs/reports/2026-08-29-retrospective.md` |
| 23 | code | 운영자가 «전담 도구만» 껐을 때 `no_dedicated_observer` 가 발화 — 모듈 자신의 opt-out 규칙과 모순(점수 신뢰불가 + 거짓 PR 경고) | `src/analyzer/io/static.py` |
| 24 | code | #1609 이 tweaks.js 를 「죽은 배선」으로 지우면서 짝인 CSS ~90줄은 남겼다 — 절반만 닫힌 제거 | `src/static/css/pages.css` |
| 25 | code | `--bg-nav` 는 알파 0.72~0.82 인데 대비 «바탕» 으로 쓰인다 — 같은 PR 의 불투명 가드는 nav 를 제외해 두 가드가 서로 모순 | `tests/unit/ui/test_secondary_text_contrast.py` |
| 26 | docs | #1599 가 세운 「구별값 파생 대조」가 같은 값의 사본 3곳을 빠뜨렸다 — 뮤테이션으로 전부 silent green 실증 | `tests/unit/scripts/test_doc_distinguished_values.py` |
| 27 | docs | STATE.md 첫 불릿의 「손으로 고치는 곳은 한 줄뿐」이 거짓이고, 그 문장이 #1599 사고의 직접 원인인데 값만 고치고 문장은 남았다 | `docs/STATE.md` |
| 28 | docs | STATE.md 가 문서 규칙이 금지한 PR 번호를 들고 있고, 그 번호에 가드 정규식이 문구-고정돼 규칙 준수가 CI red 를 부른다 | `docs/STATE.md` |
| 29 | docs | base.html 헤더 주석이 「themes.css = 4 테마 정의」라고 적는데 그 파일은 7줄짜리 빈 stub 이다 — #1601 의 문서-진실 청소가 .md 밖이라 못 봤다 | `src/templates/base.html` |
| 30 | docs | UI 20여 건 중 최소 4건이 동일 근본원인(「가드 열거 밖이라 한 번도 안 쟀다」)인데 영역 문서 ui-i18n.md 는 48 PR 내내 한 글자도 안 바뀌었다 | `docs/workflow/ui-i18n.md` |
| 31 | decision | 스택 PR 3건이 회고 범위 오라클에 원리적으로 안 보인다 — 그중 하나가 심의 게이트(거버넌스) 변경이다 | `scripts/retro_scope.py` |
| 32 | decision | 회고 범위 라벨이 min~max 라 연속처럼 읽히지만 그 안에 회고 대상이 아닌 번호가 섞인다 | `scripts/retro_scope.py` |
| 33 | tooling | 시각 하네스의 축이 파라미터가 아니라 리터럴 — 엔진 1종·뷰포트 1종으로 고정돼 두 확정 결함이 원리적으로 안 보였다 | `e2e/test_theme_mobile_guards.py` |
| 34 | tooling | 46건을 찾아낸 픽셀 프로브를 «일회용» 으로 버렸고, 남은 25건에는 래칫이 없다 — 같은 사이클의 analyzer 트랙은 정확히 반대로 했다 | `tests/unit/ui/test_tinted_ground_is_determinate.py` |
| 35 | tooling | PR 템플릿 채택률 0% (표본 17/17) — 그런데 이번 사이클에 그 죽은 표면을 손봤고, 하필 그 안의 모바일 항목이 실제로 터진 축이다 | `.github/PULL_REQUEST_TEMPLATE.md` |
| 36 | process | 범위 대조 가드가 부분문자열로 판정해, retro_scope 자신의 `range` 요약을 「46건 누락」으로 오경보한다 — 정책 8-(5) 의 유일한 집행 신호가 늑대소년이 됐다 | `.claude/workflows/retrospective.mjs` |
| 37 | process | 직전 회고가 「이전부터 있던 P1」 8건을 나열했으나 그중 Issue 가 된 것은 0건 — 원장을 Issue 로 단일화한 뒤 회고 리포트가 미등재 부채의 종착지가 됐다 | `scripts/check_env_vars_sync.py` |
| 38 | code | 포커스 가드의 검사 범위가 3파일 손목록인데 주석은 「새 자리가 생기면 red」라고 적는다 — 실제로 밖에 두 자리가 있다 | `tests/unit/ui/test_focus_indicator.py` |
| 39 | code | 도달 불가능한 `[data-variant="signature"]` 팔레트가 살아 있고, 이 사이클이 세운 accent 대비 불변식을 깨는 모양이다 | `src/static/css/tokens.css` |
| 40 | code | fail-open 탐지기의 주 스코프 함수가 `async def` 를 못 본다 — 형제 헬퍼는 보는데 비대칭이다 | `tests/unit/analyzer/test_adapter_fail_open_inventory.py` |
| 41 | code | 이 사이클의 시각 가드 전량이 Chromium 한 엔진만 잰다 — #1627 이 그 사각에서 나온 실물 결함이다 | `e2e/conftest.py` |
| 42 | docs | #1606 이 README 두 본만 고쳤다 — 같은 거짓 설치 절차가 CLAUDE.md·CONTRIBUTING.md 에 그대로 남았다 | `CLAUDE.md` |
| 43 | docs | #1599 가 만든 파생 대조 가드가 3개 파일만 열거 — 같은 값을 든 pipeline.md·architecture.md 는 밖에 있다(뮤테이션으로 실증) | `tests/unit/scripts/test_doc_distinguished_values.py` |
| 44 | docs | 민감 경로 목록의 주석이 「아무것도 red 가 되지 않는다」고 적지만 CI·pre-push 가 강제한다 — 가장 안전에 민감한 파일의 지시가 거짓 | `src/gate/sensitive_paths.py` |
| 45 | docs | #1597 이 C# 전담 분석기를 지웠는데 README 언어 표는 그대로 — 총계 27 이 우연히 유지돼 구성 변화가 안 보인다 | `README.md` |
| 46 | docs | 「죽은 문서 경로」 가드가 번역 JSON 만 본다 — src/ 주석의 같은 결함은 열거 밖이고 실물 1건이 남아 있다 | `src/shared/anthropic_caching.py` |
| 47 | decision | 사용자에게 올린 보류 판단이 ~185배 과대한 수치 위에 있었고, 정정이 한 방향으로만 걸려 있다 | `docs/reports/2026-08-29-retrospective.md` |
| 48 | tooling | `check-memory-refs` 훅의 폭발 반경이 의도를 초과한다 — 문서 위생 1건이 저장소 전체 커밋을 얼렸고, 시정판도 같은 결함이었다 | `.pre-commit-config.yaml` |
| 49 | tooling | 로컬 pre-push 게이트와 CI 가 서로 못 보는 축을 갖는다 — 양방향 발산이 같은 사이클에 두 번 실현됐다 | `scripts/pre_push_gate.py` |
| 50 | tooling | 가드 저작이 CodeQL 을 자초하는 클래스가 반복된다 — 이번엔 «테스트 헬퍼» 에서, 로컬에 대리 검사가 없어 push→CI 왕복으로만 발견됐다 | `tests/unit/ui/test_placeholder_and_chevron.py` |
| 51 | 운영 실측 | 수동 게이트는 운영에서 단 한 번도 실행된 적이 없다 — #1598 R2 전체가 공집합 위의 설계 | `alembic/versions/0047_gate_decision_post_state.py` |
| 52 | 게이트·auto-merge 정책 ↔ 관측 | 판정 변경을 잡는다는 behaviour-hash 가드가 #1570 의 실제 판정 변경을 통과시켰다 — 뮤테이션으로 실증(축을 통째로 지워도 12/12 초록) | `tests/unit/scorer/test_reliability_cache_contract.py` |
| 53 | 게이트·auto-merge 정책 ↔ 관측 | 관측면 부재가 «점수» 를 전혀 낮추지 않는다 — 게이트가 읽는 유일한 통화에 이 사실이 없어서 가시화가 원리적으로 머지에 닿지 못한다 | `src/scorer/calculator.py` |
| 54 | 게이트·auto-merge 정책 ↔ 관측 | 머지 차단 마커 3종만 단일출처화되지 않았다 — 자매 가드 2종은 parity 사고 뒤 engine 진입부로 모았는데 이것만 두 곳에 복사돼 있다 | `src/webhook/providers/telegram.py` |
| 55 | 미검증 양식: 정책 cross-refer | 이 창의 회고 근거로 인용된 pipeline.py 주석의 「6개」가 HEAD 에서 거짓이다 — 실측 9개, 그리고 #1605 의 파생수치 소탕이 자매 사본을 또 놓쳤다 | `src/worker/pipeline.py` |
| 56 | 배포 조달 ↔ 가드 | 조달 계약 가드가 «echo 경고 산문» 으로 충족된다 — 계약 16종 중 8종이 실제 설치를 지워도 초록 | `tests/unit/analyzer/test_procurement_contract.py` |
| 57 | 배포 조달 ↔ 분석기 인벤토리 | JVM 을 넣을지 ktlint 조달을 뺄지의 결정이 없다 — 매 빌드가 영구히 실행 불가한 바이너리를 내려받는다 | `railway.toml` |
| 58 | 가드 정합성 | `_REACHABLE_CEILING = 2` 가 실행 불가능한 ktlint 를 «배포본에서 도는» 것으로 세어 래칫에 빈 슬롯 하나를 남겼다 | `tests/unit/analyzer/test_adapter_fail_open_inventory.py` |
| 59 | 파생값 정합성 | `static.py` 의 「배포 이미지에서 9개 언어」 실측 목록이 같은 창의 #1579 로 거짓이 됐다 — kotlin 이 빠져 있다 | `src/analyzer/io/static.py` |
| 60 | 사용자 대상 문서 | README 의 «16종이 모든 배포에 실린다» 가 이름 소속에서 파생돼 능력을 과대 진술한다 — 실행 가능은 15종 | `README.md` |
| 61 | 가드 부재 | 어댑터의 «런타임 의존» 을 조달과 대조하는 축이 어디에도 없다 — 계약은 분석기 이름 하나만 본다 | `tests/unit/analyzer/test_procurement_contract.py` |
| 62 | 가드 커버리지 / docs drift | 이 창은 «경로 축» 가드를 실제로 만들었다 — 그리고 결함이 난 디렉토리 하나로 스코프를 잘랐다. 그 docstring이 일반 클래스를 이름까지 붙여 놓고서. | `None` |
| 63 | 가드 자기기술 | 메모리 참조 가드의 module docstring 이 자기 스캔 범위를 거짓으로 적는다 — 커버리지를 감사하는 사람이 코드가 아닌 이 문장을 읽는다 | `None` |
| 64 | docs drift / 시정의 부분성 | #1602 는 dangling 경로 주석 2건을 지우고 같은 파일에 5건을 남겼다 — 그 삭제조차 경로 축이 아니라 패턴 삭제의 부산물이었다 | `None` |
| 65 | 브리프 검증 / 오탐 | 브리프 예시 5건 중 2건은 오탐(예정 경로)이고, doc_review_gate 「빈 분모」 축은 이미 이 창이 닫았다 | `None` |
| 66 | docs drift / 죽은 SSOT | 삭제된 `.claude/rules/**` 를 «정본» 으로 지목하는 살아 있는 계약 인용이 8파일에 남아 있다 | `None` |
| 67 | 가드 스코프 / 반복 | «문서 = .md» 라는 스코프 가정이 서로 다른 가드 3곳에 독립적으로 하드코딩돼 있다 | `None` |
| 68 | ui-a11y-guard-enumerat | 상호작용 뒤에만 존재하는 서피스는 경로 열거로 원리적으로 못 닿는다 — 모달은 전 e2e 에서 관측 0건이고, 그 사실이 Issue 에 «기록만» 돼 있다 | `src/templates/analysis_detail.html` |
| 69 | ui-a11y-guard-enumerat | 뷰포트·엔진 두 축의 분모가 각각 1 — 이 창의 마지막 결함(#1627)이 정확히 그 교집합에서만 보였다 | `e2e/conftest.py` |
| 70 | ui-a11y-guard-enumerat | #1627 의 엔진 짝 가드가 «크기» 속성만 본다 — background/box-shadow 만 주는 webkit 규칙은 moz 짝 없이 통과한다 | `tests/unit/ui/test_focus_indicator.py` |
| 71 | ui-a11y-guard-enumerat | 공허 방지 하한이 실측의 3분의 1 — 스캔이 62% 죽어도 초록이다 | `tests/unit/ui/test_focus_indicator.py` |
| 72 | docs-ssot/constant-cop | 같은 상수 `100` 이 docs/workflow/verify.md 에 두 번째 사본으로 박혀 있고 결속 가드가 없다 | `docs/workflow/verify.md` |
| 73 | docs-ssot/stale-commen | 가드 주석의 산술이 baseline 122 시점에 얼어붙어 오답을 가르친다 — 「122-1=121 이라 하한에 안 걸린다」 | `tests/unit/scripts/test_e2e_scope_guard.py` |
| 74 | ci-guard/asymmetry | 통과 하한이 e2e job 에만 있고 단위 job(7856건)에는 없다 — #1298 이 실증한 공허화 클래스가 큰 쪽에 미적용 | `.github/workflows/ci.yml` |
| 75 | security | 회고 렌즈에 보안 축이 없고, 그 부재가 «5종» 개수 보존 논리로 방어된다 | `.claude/workflows/retrospective.mjs` |
| 76 | security | 민감경로 가드의 정의 파일 자신이 hold 밖이다 — 가드가 자기를 지키지 않는다 | `src/gate/sensitive_paths.py` |
| 77 | security | #1060 NULL-owner IDOR P0 의 불변식이 docs 에 전혀 없고, 커버리지는 손 열거다 | `docs/workflow/security.md` |
| 78 | security | 브리프의 #1598 위협모델 전제 반증 — 유출·전달·퇴사자 버튼은 이미 두 겹으로 막혀 있다 | `src/webhook/providers/telegram.py` |
| 79 | process/guards | «dangling 0» 을 표방한 정리 PR(#1387)이 메모리 쪽 dangling 8건을 만들었다 — 가드가 그 방향을 못 본다 | `D:\Source\SCAManager\scripts\check_memory_refs.py` |
| 80 | process/memory | 메모리 본문이 머신 절대경로를 인용한다 | `C:\Users\dirtc\.claude\projects\d--Source-SCAManager\memory\project-retro-2026-07-26.md` |

## 오탐 (다음 회고가 다시 판정하지 않도록)

| 관점 | 제목 | 기각 사유(요지) |
|---|---|---|
| process | 영역 문서가 명시한 검증 축(모바일)을 UI 20 PR 이 연속으로 건너뛰었고, 그 누락이 실제 결함을 출하시켰다 | 인용은 정확하다(`docs/workflow/ui-i18n.md` = 「4테마(dark·light·pastel·catppuccin) × 모바일/데스크탑 확인.」, #1627 본문 인용도 축자 일치). 결함 자체도 실재하며 창(window) 안 자초다 — `git log -S "webkit-slider-thumb"` 결과 «::-moz-range-thumb» 기본 규칙은 **#1618(3ca6d |
| process | 시각 변경 21건에 «사람이 봤다»는 흔적이 하나도 없다 — 규칙이 관측 불가능한 상태 | 인용 좌표는 실재한다 — `CLAUDE.md` = 「시각 변경(`templates/`·`static/`)은 사람이 봐야 한다 — 정적 테스트 통과는 근거가 아니다」(grep 재확인). 그러나 「흔적이 하나도 없다」는 핵심 사실 주장이 반증된다.  전수 확인(호출자 12건 + 기계 범위 확장분 #1603·#1608·#1610·#1614 포함, UI 접촉 PR 17건 전건): `gh pr vie |
| process | 이번 회고의 디스패치 브리프가 손 조립돼 48건 중 46건을 잃었다 — 스킬 1단계가 금지한 바로 그 행위 | 인용(SKILL.md 「범위는 기계에서 얻는다 — 디스패치 직전 실행, 손 조립 금지」)은 실재 확인. 그러나 주장의 사실 골자 3개가 모두 반증된다. (1) 「손 조립」 아님 — 전달된 세션 컨텍스트가 retro_scope.py 출력 스키마와 필드 단위로 일치한다(ok·anchor·prev_retro·boundary·head=03855b12·pr_count=48·range=#1569~#16 |
| code | #1570 이 호스트 의존 단위 2건을 새로 심었고, 같은 범위의 #1622 스윕이 증상별이라 그것을 지나쳤다 | 인용 좌표는 정확하나(`tests/unit/analyzer/test_no_dedicated_observer.py = test_generic_only_run_sets_the_axis`, ` = test_csharp_has_no_dedicated_observer` — grep 로 줄번호까지 일치), 근본 원인 진단이 반증됐다.  【반증 실측 — 이 PC, HEAD 03855b12】 1. 재현:  |
| decision | 「스스로 판단한 것」 절 누락이 사이클 말미 에이전트 PR 3연속에 몰려 있다 | 인용은 정확하다 — CLAUDE.md = 「위임 작업 중 스스로 판단한 것은 PR 본문이나 응답 끝에 명시한다.」 이고, 가드 부재도 재확인했다(grep -rln "사람이 봐야\|스스로 판단" scripts/ .claude/ .github/ → 0건). 수치도 재현된다: 병합된 에이전트 PR 45건(dependabot 6건 제외)에서 `스스로 판단` 미검출 = [1572, 1622, 1626 |
| process | 회고 브리프의 scope 가 기계 산출과 48건 중 46건 어긋났다 — 가드 하나만이 96% 실종을 막았다 | 인용 2건은 원문 정확 일치(SKILL.md 「범위는 기계에서 얻는다 … 손 조립 금지」, retro_scope.py 「손으로 적는 한 항상 '진입 직전 머지분'이 빠진다」). 그러나 주장의 핵심 사실(브리프가 손 조립돼 46건이 빠졌다 / 96%가 회고를 피할 뻔했다)은 반증된다.  가드 본체는 retrospective.mjs `machineScope.prs.filter(n => !Stri |
| process | 회고 카덴스가 무집행이라 창 크기가 6 PR ↔ 48 PR 로 8배 흔들린다 | 사실 확인은 전부 통과했으나, 그 사실을 「결함」으로 묶는 추론이 무너진다.  검증된 사실 (전건 재실측): - `scripts/retro_scope.py` 실재, 224줄이므로  유효. 다만 181행 내용은 `"range": f"#{prs[0]}~#{prs[-1]}" if prs else "(없음)",` — 범위 산출식이지 카덴스 로직이 아니다(주장은 「부재」라 어느 줄도 근거가 될 수 없 |
| decision | 「스스로 판단한 것」이 빠진 4건이 하필 자율도가 가장 높은 PR 들이고, 사이클 말미 4건 중 3건에 몰렸다 | 인용·수치는 전건 재현됨(CLAUDE.md = 규칙 원문 정확 일치, 52줄이 「사람이 눈으로 확인」; 48건 중 dependabot 6건 제외 42건 자기작성; '스스로 판단' 미포함 = #1572·#1622·#1626·#1627 4건; '사람이 봐야 할 것' 42/42; mergedAt 4건 전부 일치). 그러나 「규칙 미준수」 판정 자체가 반증됨. CLAUDE.md 은 「스스로 판단한  |
| code | hx-boost 재실행마다 IntersectionObserver 가 새로 생기고 옛 것은 끊기지 않는다 — 같은 블록의 MutationObserver 만 remove-before-add 를 지킨다 | 인용은 전부 실재 확인(base.html hx-boost body · 스크립트 751~1215 = body 내부(</body>=1216) · 1003 `var _revealIO` 저장·disconnect 0건 · 대조군 1057 MO disconnect). 그러나 「누적된다」는 해악 주장이 성립하지 않는다. 두 관찰자는 대상 수명이 다르다: `_revealMO` 는 `document.body |
| decision | `range` 문자열이 성긴 집합의 min~max 인데 연속 구간처럼 읽혀, 빠진 PR 을 적극적으로 은폐한다 | 인용은 실재한다 — scripts/retro_scope.py `"range": f"#{prs[0]}~#{prs[-1]}" if prs else "(없음)"` 문자 그대로 일치. 그러나 「은폐」주장의 하중을 지는 근거가 오독이다.  (1) 핵심 근거 붕괴 — #1600·#1602·#1603 은 «미열거 머지 PR» 이 아니라 stacked PR 이다. `gh pr view` 실측: 세 건 모두 |
| 운영 실측 | issue_registrations 는 운영에 0행 · create_issue 가 7개 리포 전부 false — sync_error 는 행이 존재한 적 없는 테이블에 붙었고 3일 뒤 그 UI 는 «미사용» 으로 삭제됐다 | 인용 좌표 3건 전부 실재 확인(0047:43 sync_error add_column · issue_registration.py sync_error Column · issue_registration_service.py record_sync_error). 운영 SELECT 2건도 정확히 재현(issue_registrations 0/0/0, created_at min/max NULL; repo_ |
| 운영 실측 | 2026-08-20~25 사이 AI 리뷰 400 BadRequestError 31건이 점수 NULL 로 남았는데 아무도 관측하지 않았다 | 근거 수치는 운영 DB 로 정확히 재현됨(08-25:11·08-24:16·08-20:4=31건, 전부 BadRequestError/400/score NULL, 08-25 이후 0건). 그러나 핵심 주장인 「관측 부재」와 「재발하면 다시 아무도 모른다」가 모두 반증된다. (1) Issue #1506(CLOSED·COMPLETED·2026-08-27) 이 정확히 이 사건이다 — 제목 "계정 지출 |
| 운영 실측 | 운영 점수의 77%가 score_unreliable · 분석의 72%가 ai_review disabled — 파이프라인의 실제 지배 경로가 설계 서술과 다르다 | 숫자는 전건 일치, 그러나 「결함」 주장 두 축이 모두 무너진다.  ■ 근거 재현 (운영 DB qaoirpyhldlkeoyppfwq 직접 SELECT, 전부 EXACT 일치) - 최근 30일 analyses: total 2100 · score_unreliable 1616(76.95%) · ai_review_status disabled 1522(72.5%) · success 546 · api_ |
| 게이트·auto-merge 정책 ↔  | 신뢰도 축 7종 중 머지를 막는 것은 2종뿐 — 새 축이 «형제 유추» 주석 한 줄로 머지 경로를 통과했고 그 분류를 강제하는 것이 없다 | 인용 좌표는 전건 정확하다(engine.py = `if not (config.auto_merge and score >= config.merge_threshold): return` · reliability.py 7사유 · auto_merge.py/45/55 차단마커 3종 · pipeline.py "Informational, never gates" · test_score_reliability.p |
| CI ↔ 운영 비대칭 | CI 는 러너에 미리 깔린 JVM 덕에 ktlint 실바이너리 테스트가 초록이다 — 그 초록은 운영에 대해 아무 말도 하지 않는다 | 인용 좌표·증거는 전부 실재한다(ci.yml ktlint 설치 ·  `command -v` 루프 · test_contracted_analyzers_real_binary.py,216 실 ktlint 실행 · workflows 내 java/jdk/jre/jvm/openjdk grep 0건 · railway.toml·nixpacks.toml aptPkgs 에도 java 조달 0건). 그러나 주장된 |
| 가드 커버리지 / 재사용 | 같은 스코프 확대를 이 리포가 이미 한 번 했다(#1519) — 그 결과물을 재사용하지 않고 세 번째 좁은 가드를 지었다 | 인용은 실재한다(check_memory_refs.py 감사 B7 주석 · _DOC_GLOBS 는 , 주장의  는 2줄 어긋남). #1519 B7 = 커밋 68229f24 도 실재. 그러나 **인용에서 끌어낸 추론이 셋 다 반증된다.**  (A) 재사용할 «분모» 가 존재하지 않는다. check_memory_refs.py 는 «메모리 슬러그»(`feedback\|project\|user` 접두 |
| ci-guard/observe-wit | `check_e2e_scope.py` 의 baseline 초과 경고는 print-only 비차단 — 관측면은 있으나 집행이 없다 | 인용 좌표는 실재한다( `if actual > expected:` /  print /  `return 0`, 대조군  `return 1`, docstring ). 그러나 «초과 축에 집행이 없다» 는 추론이 반증된다. main() 은  에 닿기 전  에서 `_check_documented_split(actual)` 를 돌리고, 이 함수는 docs/STATE.md 의 문서 총계 ≠ 실측이면 → |
| security | 게이트 리플레이 불변식을 쥔 파일이 민감경로 hold 밖이고, drift 오라클이 원리적으로 볼 수 없다 | 인용은 전부 실재하고 재현된다. `src/repositories/gate_decision_repo.py def claim_post_attempt(`, `src/webhook/providers/telegram.py`, `scripts/check_sensitive_path_drift.py _STRONG_MODULES` / ` if module.split(".")[0] in _STRONG_MODU |
| security | upsert 의 UPDATE 분기가 pending_post 를 조용히 posted 로 덮어 재시도 갈래를 닫는다 | 인용 좌표는 전건 정확하나(gate_decision_repo.py `record.state = POSTED` 무조건 UPDATE 분기 · 호출처 approve.py/ 두 곳뿐 · release_post_claim:190 대칭 방어 부재), **주장된 실패 창이 도달 불가**다.  반증 근거 3겹: ① `pending_post` 쓰기 지점은 전 트리에서 `claim_decision:65` 단  |
| process/memory | 메모리의 «상태» 축이 405 PR·6주 stale — 교훈 축은 최신이라 드리프트가 은폐된다 | 인용은 전건 확인됨(MEMORY.md = 최신 project 엔트리 2026-07-26, 최대 PR #1220; ls -t 로도 최신 project 파일 확인; 2026-09-06 착지분 feedback 3건에 `grep -nE "#1[0-9]{3}\|시작점"` → 0 hit; 08-29 회고 리포트 메모리 흔적 0). 그러나 «상태 축이 빠졌다 → 드리프트 은폐»라는 피해 메커니즘이 실측으 |
| process/guards | 메모리 가드는 CI 백스톱이 원리적으로 불가 — 로컬 pre-commit 단일 지점이다 | 인용 2건은 정확하나(ci.yml 주석 문자열 축자 일치, .pre-commit-config.yaml `- id: check-memory-refs` + `stages: [pre-commit]`), 그 위에 세운 추론이 실측으로 반증된다.  **1) 「집행 지점은 개발 PC 훅 하나뿐」·「훅 미설치 머신에서는 아무 검사도 없다」 = 거짓.** CI 는 `python -m pytest tests |
| process/memory | 신규 엔트리가 인덱스 꼬리에 붙어 최신 상태가 가장 늦게 읽힌다 | 인용 좌표는 실재하나(MEMORY.md = 2026-09-06 실측 문구 정확 일치, 69~71행 mtime Sep 6 확인) 그로부터의 추론이 세 겹으로 반증된다. (1) 「꼬리에 붙었다·9월이 마지막」이 사실과 다르다 — 신규 3건 뒤에 더 오래된 72행(2026-06-15 connectivity-probe)·73행(2026-07-09 docs-sync)·74행(2026-07-10 pr- |

## 다음 회고를 위한 경계

- 이 리포트의 범위 상한 = **#1627**. 다음 회고는 **#1628 부터** 이어야 한다.
- 🔴 경계를 「이 리포트를 추가한 커밋」으로 잡으면 그 커밋 이전에 머지된 PR 이 또 사라진다(P1-1).
  이 리포트를 머지하는 PR 번호도 다음 범위에 포함시켜야 한다.

fix 는 사용자 결정 — 이 리포트는 자동 수정을 포함하지 않는다.
