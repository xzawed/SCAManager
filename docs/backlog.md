# 미해결 일감 원장 (Engineering Backlog)

> **목적**: 회고·감사·운영 관측에서 **확인됐으나 아직 처리하지 않은** 일감을 한 곳에서 추적한다.
> 회고 보고서는 시점 스냅샷(append-only 아카이브)이라 "지금 뭐가 남았나" 를 답하지 못한다 — 이 파일이 그 질문의 단일 출처다.
>
> **owed 원장과의 차이**: [`runbooks/owed-verification.md`](runbooks/owed-verification.md) = **사용자만 할 수 있는 운영 검증**(SessionStart 훅이 기계 집행). 이 파일 = **코드로 처리 가능한 엔지니어링 일감**(집행 없음 — 우선순위 참조용).
>
> **상태 범례**: 🔴 결정 대기(사용자) · 🟡 착수 가능(Claude 자율) · ⏸️ 보류 · ✅ 완료(다음 정리 시 제거)

---

## ▶️ 다음 세션 시작점 (2026-07-31 세션13 인수인계)

**이 파일부터 읽으면 된다.**

🔴 **2026-07-31 세션13 = 5+1 회고(run `wf_d58ff24d-f4d`·188 에이전트·확정 156·verdict_coverage 1.0)
+ 병행 Grok claim-review(session `019fb7fd`) + 뮤테이션 검증(`wf_30d60394-312`·24 에이전트).**
사용자 결정 = **P0 4뿌리 전량 이행 + P1/P2 는 등재만**. 상세·근거는
[`_archive/reports/2026-07-31-retrospective.md`](_archive/reports/2026-07-31-retrospective.md).

**이번 세션이 처리한 P0** (아래 표에 없는 이유): A(CLI supersede `populate_existing`) ·
B(훅 실행 가드) · C(메모리 경로) · D(STATE 수치 4지점). 배선 판정 substring fail-open 은 `#1248`.

| ID | 상태 | 항목 | 근거 요약 |
|----|------|------|-----------|
| **R16** | 🟡 착수 가능 | **B8 fail-open floor 가 자기 스캔 범위를 관측하지 않는다** — `scripts/check_*.py` 만 glob 하므로 **test-as-guard 표면은 원리적으로 미탐**이고, 범위를 비워도 `✅ … bare-substring fail-open 0` **성공 문구를 출력**한다 | **기전**: 뮤테이션 GROK-9 실측 — `tests/unit/scripts/` 에 bare substring 판정 가드를 새로 만들어도 `check_guard_fail_open.py` 는 EXIT=0. AGENTS.md 스스로 최다 재발 사고(`#1136`·`#1156`)가 **test-as-guard 에 있었다**고 기록한다. **반증 수단**: 범위를 `tests/**/test_*.py` 로 넓혔을 때 오탐 < 진탐인지(정책 17 guard-suicide 위험 — `X in text` 는 정당한 presence 검사에도 쓰인다). 🔴 **오탐 위험 0인 최소 조치 = 출력 문구를 실제 스캔 범위로 한정** |
| **R17** | 🟡 착수 가능 | **lint-js 공허화 차단의 false-justification 우회** — 템플릿 인라인 `<script>` 에 비실행 Jinja 유사 토큰(`// {{`)을 넣으면 "정당한 제외" 로 분류돼, 그 파일을 eslint 무시 목록에 넣어도 가드가 통과 | **기전**: 뮤테이션 GROK-12 실측 — 검사 대상이 **6 파일 → 5 파일**로 줄었는데 EXIT=0(양쪽 다). 🔴 **라벨 정정**: Grok 은 `score-lie` 로 분류했으나 대상이 **자사 템플릿**이라 사용자 리포 점수 인플레가 아니다 → `silent-disable`. 사용자 가시 효과 = *"템플릿 JS 가 영영 미린트돼도 CI 초록"*. **반증 수단**: 검사 대상 **파일 수 감소 자체**를 신호로 삼는 축 추가 시 red 가 되는지 |
| **R18** | ⏸️ 보류 (기지 한계) | **claim-review 게이트의 위조·어휘 우회** — (a) Grok 을 돌리지 않고 손으로 채운 흔적으로 통과 (b) 트리거 어휘를 피한 seal 주장("강화했다·틈을 막았다")은 요구가 발동조차 안 함 | 둘 다 `check_claim_review_trace.py` docstring **§한계 1·3 에 이미 명시된 설계 천장**이고, AGENTS.md 가 *"fail-open 은 semantic 이라 정적 판정 불가 — 남은 방어선은 review-time claim-review"* 를 확정했다. 뮤테이션 GROK-10/11 은 그 천장의 **재확인**이지 신규 결함이 아니다. 🔴 **그래도 등재하는 이유**: "알려진 한계" 가 문서에만 있고 원장에 없으면 다음 세션이 신규 발견으로 착각해 같은 검증을 반복한다 |
| **R19** | ✅ 완료 (세션13) | **`tests/unit/verifier/test_openai_client.py` 5건이 의존성 없는 환경에서 red** — `openai==2.50.0` 은 `requirements.txt` 핀이지만 `importorskip` 가드가 없다 | **기전**: 2026-07-31 실측 — 로컬 `pytest tests/unit` = **6079 passed / 5 failed**(`ModuleNotFoundError`), main 에서도 동일. CI 는 설치하므로 초록이라 **누구도 못 본다**. 🔴 진짜 피해는 6-step ② 가 요구하는 "push 전 전체 통과 실측" 이 이 환경에서 **구조적으로 불가능**해져, 실패를 습관적으로 무시하게 되는 것이다(진짜 회귀도 같이 묻힌다) |
| **R20** | 🟡 착수 가능 | **정책 19 집행면 결함 9건** — 면제 마커가 **계량되지 않는다**(창의 post-guard seal PR 10건 중 **5건이 면제로 통과**, 첫 사용은 가드 생성 **66분 후**) · **HTML 주석 안의 흔적·면제도 인정**(가드는 exit 0 인데 리뷰어에게 비가시) · **session id 재사용 무탐지**(#1245 가 #1244 의 세션 인용) · seal 어휘가 이 리포 관용구 `뮤테이션 N건 red`(단수형)를 못 잡음 · **집행면이 정책 SSOT 4곳 어디에도 없음** | 회고 P1 클러스터 2. 최소 조치 = (a) 면제 사용을 원장에 기록·계량 (b) HTML 주석 제거 후 매칭 (c) 어휘 사전에 단수형 추가 (d) AGENTS.md·CLAUDE.md 정책 19 항에 게이트 존재 명시 |
| **R21** | 🔴 결정 대기 | **`#1244` 커버리지 승격이 조달 불가 언어의 auto-merge 를 영구 차단** — `unavailable_tools → incomplete` 승격으로 **css/scss·dart·powershell·protobuf** 가 영구 incomplete. `#1245` 가 스스로 *"차단 없이 가시화만"* 이라 적은 것과 정면 모순 | 회고 P1 클러스터 4(7건). 🔴 **결정 필요**: (a) 조달 불가 언어는 incomplete 에서 제외(가시화만) / (b) 현행 유지(보수적 차단) / (c) 언어별 화이트리스트. 부수: 가시화가 **6 알림 채널 중 GitHub PR 코멘트 1곳에만** 구현돼 Telegram·대시보드에는 여전히 만점만 보인다 |
| **R22** | ✅ 완료 (세션13 — 설정 메타 메시지 드롭 + 실바이너리 축) | **eslint fail-closed 오탐 4건** — `ruleId:null` 을 전부 '미린트' 로 오판해 **흔한 `eslint-disable` 주석 하나로 PR 전체가 `static_analysis` 오판**. 또 10-룰 최소 config 때문에 **설정에 없는 룰을 가리키는 `eslint-disable` 주석이 severity=ERROR 오탐으로 집계돼 점수를 깎는다**(실측 재현) | 회고 P1 클러스터 7. 🔴 사용자 리포 점수에 직접 영향 = `score-lie`. **반증 수단**: `eslint-disable-next-line some-external-rule` 만 담은 픽스처를 분석해 이슈 0건·미린트 판정 0 인지 |
| **R23** | ✅ 완료 (세션13 — SessionStart 관측면, advisory) | **pre-commit 미설치를 관측하는 면이 리포 전체에 없다** — 시크릿 훅 5종이 창 **22 커밋 내내 0회 실행**. CI TruffleHog `--only-verified` 는 이 클래스를 대체하지 못한다(검증된 시크릿만 본다) | 회고 P1 클러스터 8. 🔴 보안. **반증 수단**: SessionStart 훅이 `pre-commit --version` + `.git/hooks/pre-commit` 실재를 확인해 부재 시 loud(advisory 유지, 정책 17) |
| **R24** | 🟡 착수 가능 | **backlog 원장 자체의 정확성 6건** — R9 는 창에서 양 축 모두 해소됐는데 여전히 🟡 · **R2-b 의 반증 수단이 원리적으로 측정 불가**(지정 API 가 영원히 404) · 요약표 🔴 1건인데 실제 3건 · 회귀 가드가 원장 23행 중 5행만 본다 | 회고 P1 클러스터 6. "지금 뭐가 남았나" 의 SSOT 가 **완료된 일을 다시 시킨다** |
| **R25** | ✅ 완료 (세션13 — `check_test_count_sync` ground-truth 축, PR/main 이원 배선) | **`check_docs_sync` 는 ground truth 를 원리적으로 못 본다** — 문서 사본끼리만 대조하므로 **4지점이 함께 틀리면 항상 GREEN**(뮤테이션 실증). 유일한 수동 backstop 인 `/docs-sync` 스킬은 **통합 카운트를 상수 154 로 하드코딩** | 회고 P1 클러스터 1. 이번 세션이 수치는 정정하지만 **관측 축은 미신설**. 처방 = CI test job 에서 `pytest --collect-only -q` collected 수를 STATE 정규식 값과 대조(로컬 pre-commit 은 속도 때문에 현행 유지) |
| **R26** | ✅ 완료 (세션13) | **`docs/architecture.md` 핵심 데이터 흐름 stale 2건** — 창에서 P0 로 정정한 `claude -p` 서술이 **이 문서에만 생존**(수정이 README 에만 적용됨) · `#1247` 이 STATE 최신 블록·cycle-history 어디에도 없음 | 회고 P1 클러스터 10·12 |
| **R27** | 🟡 착수 가능 | **CONTRIBUTING(양 언어)이 존재하지 않는 기계 강제를 약속** — "커버리지·pylint 점수 drift 를 pre-commit 훅이 차단" · "src/ 신규 파일 트리 등재를 훅이 강제" 둘 다 실재하지 않는다. 또 path-scoped rules 본문 sync 의무(사이클 86 Q2 **사용자 명시 결정**)가 창의 코드 PR **7건 중 6건에서 미이행** | 회고 P1 클러스터 13. 신규 기여자에게 거짓 보증 |
| **R28** | 🟡 착수 가능 | **owed 운영검증 원장이 22 PR·2 세션 종료 동안 0행** — 창의 헤드라인 봉인들(eslint/tsc/분석기 커버리지)의 **라이브 검증이 추적면 밖으로 소실**. 직전 회고 R0-2(빈 원장을 green 으로 읽음)가 **더 나쁜 형태로 재발** | 회고 P1 클러스터 12. R0-2 와 같은 뿌리이나 창이 실증을 추가했다 |

> P2 76건(관점 중복 포함)은 보고서 본문 참조. 위 R16~R28 에 흡수되지 않는 잔여는 다음 회고에서 재평가.
> 🔴 **직전 창(2026-07-26)의 R0-2·R7 은 여전히 미해결**이며 아래 역사 섹션에 남아 있다. **R2-b 는 2026-08-01 사용자 승인으로 해소**(브랜치 보호 + required check).

---

## ▶️ (역사) 다음 세션 시작점 (2026-07-26 세션9 인수인계)

**이 파일부터 읽으면 된다.**

🔴 **2026-07-26 세션9 = GitHub 정리 + owed #1072 외부계약 반증(#1218) + 5+1 회고(run `wf_47083cad-e71`·197 에이전트·확정 161).** 회고 P0-1 은 #1219 로 봉인, **P0-2 는 미처리**. P1 59건은 관점 중복 포함이라 **루트 ~15 클러스터**로 묶었다. 상세·근거는 [`_archive/reports/2026-07-26-retrospective.md`](_archive/reports/2026-07-26-retrospective.md).

| ID | 상태 | 항목 | 근거 요약 |
|----|------|------|-----------|
| **R0-2** | 🔴 결정 대기 | **owed 원장 완전성 축 부재 (P0)** — 훅이 **빈 원장을 green 으로** 읽어, 부채를 등재하지 않는 것이 가장 싼 통과 경로. 창 42 PR 중 **22건이 미체크 `- [ ]` 를 단 채 머지**됐고 세는 관측자가 없다 | 지배 주제("옳은 일 하면 red")의 **쌍대**. 처방: `check_owed_verification.py` 에 완전성 축(원장 최종 커밋 이후 머지 PR 중 미체크 항목 보유분 열거 → loud, gh 부재 시 무음). 🔴 `gh` 의존·advisory 유지 설계 결정 필요 |
| **R1** | 🟡 착수 가능 | **회고 보고서 아카이브 기계화** — 워크플로가 보고서를 쓰지 않아(`grep -rn '_archive/reports' .claude/workflows/*.mjs` 무결과) 카덴스 기계의 **입력이 인간 기억 의존**. 미아카이브 **3회차** | (a) `retrospective.mjs` 종료 단계가 보고서 직접 기록 (b) STATE·cycle-history 가 회고로 인용한 `wf_[0-9a-f]{8}` 은 전부 아카이브에 존재해야 한다는 가드 |
| **R2** | 🟡 부분 이행 | **정책 19 Grok CLAIM-REVIEW 집행면** — 창 42 커밋 중 **26건이 "봉인/fail-closed" 주장**인데 Grok 흔적 0. 2026-07-29 세션이 **또 재발**(Claude 가 자기 가드를 "봉인/양방향 강제" 로 단언 → Grok 이 BROKEN 판정) | ✅ **CI 게이트 신설**(`scripts/check_claim_review_trace.py` + `ci.yml` `repo-integrity`, 사용자 결정 2026-07-29): seal 어휘 감지 → 구조화된 claim-review 흔적(session/claim/verdict 값) 요구. 자기 적용 검증 = 이번 세션 PR #1228·#1229 **양쪽 차단됨**. 잔여는 아래 R2-b |
| **R2-b** | ✅ 완료 (2026-08-01 사용자 승인 —  required check + enforce_admins) | **정책 19 게이트가 아직 머지를 막지 못한다** — `main` 브랜치 보호 **없음**(API 실측 `Branch not protected` 404) → required status check 부재 → CI 가 red 여도 머지 가능 | **기전**: 게이트는 status check 로만 보이고 집행력이 없다(Grok claim-review 적발 — "guard is advisory theater"). **반증 수단**: `gh api repos/xzawed/SCAManager/branches/main/protection` 가 200 + `required_status_checks` 에 `Repo integrity guards` 포함이면 해소. 🔴 **GitHub Settings UI = 사용자 영역**(정책 12) — Claude 가 설정 불가. 부수 항목: `on.pull_request.types` 에 `edited` 미포함이라 **CI 초록 후 본문을 seal 주장으로 고쳐도 재검사 안 됨**(추가 시 본문 편집마다 전체 CI 재실행 = 비용 트레이드오프, 사용자 판단 필요 — **잔여**). 🔴 **2026-08-01 사용자 승인으로 해소**: `required_status_checks.checks = [{context: "Repo integrity guards (stdlib backstop)", app_id: 15368}]` + `enforce_admins: true` + `strict: false` 적용. 반증 수단 실측 = `gh api …/branches/main/protection` **200**. Grok claim-review `019fb94d` 로 payload 사전 검증(context 이름 = check-run name 실측 대조 · 항상 실행 job 이라 docs-only PR 도 보고 · DELETE 롤백 경로 확인). 🔴 첫 실전: #1253 이 required check 초록 후 머지. **`enforce_admins: true` 라 소유자 토큰 머지도 green 을 기다린다** — 그것이 이 설정의 요점이다. |
| **R3** | 🟡 착수 가능 | **정책 13 smoke 0/42 발화** — 관측면 0. 🔴 실행 비용 실측 = **~5초·무자격증명**(비싸서가 아니라 아무도 안 봐서 빠졌다) | 6-step ⑤ 또는 SessionStart 에 배선 |
| **R4** | 🟡 착수 가능 | **형제 유추 외부 계약 2건 미실측 잔존** — `#1208` 의 `@` escape 는 **GitHub 에서 완전 no-op**(라이브 프로빙 반증, 멘션 인젝션 봉인은 **존재하지 않는다**) · GraphQL `expectedHeadOid` 를 `PUT /merge` `sha` 와 "동일 의미"로 단정(비동기 머지라 원리적으로 다름) | 🔴 `@` escape 는 **실사용 영향 재평가** 필요. 세션이 발명한 "가정된 계약 → 라이브 프로빙" 을 **클래스로 확장** |
| **R5** | 🟡 착수 가능 | **3-불변식에 "시점 의존 상태를 불변식으로 고정" 클래스 없음** — 한 세션에 3건 발생했는데 규칙도 탐지기도 없다 | `AGENTS.md`·`guards.md`(write-time 자동 로드 표면)에 규칙 등재. 2차 주제는 등재됐는데 지배 주제는 안 됨(비대칭) |
| **R6** | 🟡 착수 가능 | **가드 fail-open 뮤테이션 실증 6건** — repo_detail 차트/bulk i18n 가드 2건(자기 설명 주석이 단언을 만족) · arch-tree-sync · B8 이 `.claude/hooks/**` 미검 · `test_current_tree_is_in_sync` 가 실제 out-of-sync 에서 green 등 | 전부 회고가 뮤테이션으로 red 실증 |
| **R7** | 🔴 결정 대기 | **e2e 122건이 CI 미배선인데 README/STATE 는 "E2E 122 passing" 단언** — 178 커밋째 미변경. **실행되지 않는 초록 배지** | 배선할지, 배지 문구를 정직하게 바꿀지 결정 필요 |
| **R8** | 🟡 착수 가능 | **로그 리댁션에 DB URL·userinfo 자격증명 패턴 전무** — SQLAlchemy 가 예외 메시지에 URL 전문(비밀번호 포함)을 담는데 `_SECRET_URL_PATTERNS` 가 통과시킨다 | 보안 |
| **R9** | 🟡 착수 가능 | **doc_review_gate 가 cp949(Windows)에서 deny 불가** + 심의 대상 집합이 2026-07-21 재구성 이후 stale(AGENTS.md·rules/**·policies/** 전부 skip) | 차단 게이트가 구조적으로 차단 불가 |
| **R10** | 🟡 착수 가능 | **backlog/원장 정합 4건** — H2 종결 항목이 ⏸️ 로 생존 · 원장 갱신이 delta-scoped · ⏸️ 행에 반증수단 의무 미적용 · owed 파서가 첫 셀 drift 행을 조용히 버림 | |
| **R11** | 🟡 착수 가능 | **반자동 승인 경로 잔여 2건** — 결정을 GitHub 리뷰보다 **먼저** commit 해 "approve 기록됐는데 승인은 없는" 상태 고착(insert-only claim 이라 재시도 영구 차단) · telegram `HeadMovedError` 분기 **배선 테스트 0건**(삭제해도 499 테스트 green — 뮤테이션 실증) | #1218 신규 회귀 |
| **R12** | 🟡 착수 가능 | **파괴적 작업 복구 매니페스트가 세션 임시 디렉토리에만 존재** — 브랜치 49건 삭제분. 휘발성·위치 미고지 | |
| **R13** | 🟡 착수 가능 | **slither 분석기에 실바이너리 테스트 0건** — 단위 18건이 subprocess/`shutil.which` 전량 mock + 정적 JSON 픽스처. CI green 이 slither 실동작을 전혀 증명하지 않는다 | **기전**: #1226(eslint) 과 동일 클래스 — "설치는 됐는데 아무것도 분석 안 함" 이 관측 불가. eslint 에는 `tests/integration/test_eslint_analyzer.py` 실바이너리 테스트가 있으나 slither 대응물 부재. **반증 수단**: 실 slither 바이너리로 Solidity 픽스처를 분석해 ruleId 있는 진짜 이슈가 나오는지. 관련 이슈 #1238(tsc 동일 축) |
| **R14** | 🟡 착수 가능 | **`_PIP_DISTRIBUTION` 조달 가드가 문자열 존재만 확인** — `test_build_command_deps.py` 의 `{'solc-select':'slither-analyzer'}` 가 requirements.txt 에 문자열이 있는지만 보고, slither-analyzer 가 **실제로** solc-select 를 조달하는지는 검증 안 함 | **기전**: crytic-compile 이 solc-select 의존을 버리면 가드는 green 유지 → `railway.toml:3` 의 `\|\| echo WARNING` 이 실패 흡수 → `slither.py:47` `shutil.which('slither')` 는 True → solc 없이 실행 → `slither.py:101-102` 가 `[]` → Solidity 이슈 0건 무음 = 점수 인플레. 2026-07-30 실측 시점엔 crytic-compile 0.4.2 가 `solc-select>=1.0.4` 를 유지해 미발동. **반증 수단**: crytic-compile 의 solc-select 의존을 제거한 상태에서 가드가 red 가 되는지 |
| **R15** | 🟡 착수 가능 | **fastapi 버전 문서 drift** — `.claude/rules/deploy.md:39` 과 `README.md` 배지가 `0.139` 인데 실제 핀은 `0.140.13`(#1233 머지 후) | **기전**: dependabot 은 requirements.txt 만 갱신하고 문서/배지를 동기화하지 않는다(6-step ⑤ 는 사람/Claude 몫). **반증 수단**: `grep -n 'fastapi' .claude/rules/deploy.md README.md README.ko.md` 가 requirements.txt 핀과 일치하는지. 🔴 `check_docs_sync` 는 **테스트 카운트만** 보고 의존성 버전은 안 본다 — 가드 범위 확대 여부도 함께 판단 |

> P2 100건(관점 중복 포함)은 보고서 본문 참조. 위 R1~R15 에 흡수되지 않는 잔여는 다음 회고에서 재평가.
> 🔴 **R13~R15 는 2026-07-30 dependabot 검증 워크플로(12 에이전트) 부수 발견** — GitHub 이슈로 승격한 2건은 #1238(tsc 무핀 전역설치)·#1239(trufflehog SHA 핀 실효성).

---

### (역사) 2026-07-24 세션8 인수인계

🔴 **2026-07-24 세션8 = 종합감사(#1186~1194) + P2 5클러스터(#1195~1199) + 5+1 회고(80 confirmed) + 회고 P1 이행(#1200~1201).** 상세 세션 메모리: `project-retro-2026-07-24`. **미이행 잔여**:
- **[감사 P2 — 2026-07-24 라운드 처리]**: 명확버그 6(#1204~#1208) + High-tier 설계결정 5 완료. **2026-07-24 후속**(#1210·#1211): pagination(#1210) + webhook issue-close BackgroundTask(#1211) 완료 · approve 민감경로 가드 = **오탐 정정**(대칭·개념 부재) · cron-conn = defer(서비스품질). **후속2**(#1213~#1215): 가드 self-defect 3/4 완료(B8 escape/alias·arch-tree cross-dir·wiring-coverage path-comment/tautological). **잔여 ~6** = 아래 "🟡 2026-07-23 종합감사 잔여 P2" 섹션 (스냅샷 = [`docs/_archive/reports/2026-07-23-comprehensive-review.md`](_archive/reports/2026-07-23-comprehensive-review.md)): 명확버그 1(cron double-send[dedup schema]) · SQL 집계 4 · 가드 self-defect 1(security.md 로깅 coverage — 모호, 재검증) · UI 5(정책 11 시각검증) — 남은 건 전부 schema/perf/모호가드/시각검증.
- **[회고 P1-G ✅]** = Grok claim-review 완료(#1203) — CAS 주장 REFUTED → "이중 처리 차단" overclaim 을 낙관적 동시성으로 정확화.

---

### (역사) 2026-07-19 세션4 인수인계 처방 오류 3건

🔴 **2026-07-19 세션4 전수 점검 결과 — 이 파일의 처방문 3건이 틀려 있었다.** Grok 교차 검증 완료.
처방문은 산문이 아니라 **실행될 코드**이므로, 틀린 처방은 틀린 코드와 같은 피해를 낸다:

| 항목 | 무엇이 틀렸나 |
|------|---------------|
| **B2** | 처방(`[deploy] numReplicas = 1`)이 **무효 Railway 키** — 그대로 했으면 cron P0 재현 |
| **B2-b** | 블로커 "CLI 로 확인 불가" 가 거짓 — **안 본 곳이 불가능으로 기록**됨 |
| **B6** | 근거의 **귀속이 틀림** — 자동 머지가 아니라 Claude 가 소유자 토큰으로 머지 |

**따라서 갱신 규칙에 (기전·반증수단) 의무를 추가**했다(맨 아래).

| 상태 | 건수 | 성격 |
|------|------|------|
| 🔴 결정 대기 | **1** (B6-b) | AI 자기 머지 거버넌스 (감사 High-tier 6건은 2026-07-24 서비스품질 결정 완료) |
| 🟡 착수 가능 | **1** (B7) + 감사 자율 **~6** | 명확버그 1(cron dedup) + SQL 집계 4 + 가드 self-defect 1(security.md 모호) (pagination #1210·동작1 #1211·가드 3건 #1213~#1215 완료) |
| ⏸️ 보류 | **3** (H2·H3·H4) + 감사 UI **5** | note 등급 + 상류 대기 2종(semgrep×sqlfluff click · typescript×@typescript-eslint/parser peer) + UI 템플릿(정책 11 사용자 시각검증) |

> ✅ **2026-07-24 라운드**: 감사 P2 명확버그 6 + High-tier 설계결정 5(서비스품질 위주) 처리 완료(#1204~#1208). 회고 P1-G(Grok claim-review) 이행(#1203, REFUTED→CAS 정확화). **후속(#1210·#1211)**: security_scan pagination + webhook issue-close BackgroundTask 완료 · approve 민감경로 = 오탐 정정 · cron-conn = defer. 잔여 = SQL 집계·가드 self-defect·UI(정책 11)·cron dedup(schema) — 남은 건 전부 schema/perf/meta-guard/시각검증이라 세션말미 착수 회피(회고 교훈), 다음 세션.

> 🔴 **이 표는 본문 섹션의 행 수와 일치해야 한다** — 회귀 가드
> `tests/unit/scripts/test_backlog_shape.py` 가 CI 에서 강제한다.
> 근거: 요약표 "🔴 1건" 과 본문 "_현재 없음._" 이 **정면 모순**인 채 방치됐고,
> 완료된 항목이 착수 순서 1·2위로 남아 다음 세션을 오도했다(회고 P1 12건).
> 🔴 산문은 검사하지 않는다 — **카운트 대응만** 본다(산문 린터는 그 자체가 observer-lie).

**권장 착수 순서**: **B7**(heartbeat DB, 긴급도 하향) 단독.

✅ **2026-07-20 결정 이행** — B5(회고 보고서 **복구**, 소실 선언 X) · **B6-a**(민감 경로 자동 머지 보류 가드 = 인증/마이그레이션/CI 워크플로 변경 무검토 머지 차단. 🔴 권장안이던 **브랜치 보호는 Grok 적대 검토로 반증**돼 미채택 — 사람 검토를 추가하지 않으면서 `blocked`→비재시도 태그로 자동 머지를 종결 실패시킨다).
🔴 **B6-b 는 부분 해소 — 아래 🔴 결정 대기로 재개방** (세션5 회고 P1): 민감 경로 가드는 B6-a(민감 변경의 무검토 머지)를 막지만, **비민감 PR 은 여전히 점수 60 만으로 `reviews=0` 자동 머지**된다. 'AI 가 소유자 토큰으로 자기 머지를 하는가' 라는 넓은 거버넌스 질문은 미결이다.

✅ **2026-07-19 세션4 완료분** (다음 정리 시 이 줄 제거): B1(#1114) · B2/B2-b(#1121·#1125) ·
B3(#1131) · B4(#1130) · D1(#1116) · D3(#1117) · H1(n8n 정리) ·
회고 P1 클러스터 C(#1140) · B(#1141). · **B8**(write-time fail-open floor 게이트 #1165 + **정적 탐지 천장 확정**: 강한 구문 탐지기는 Grok 2회 검증으로 오탐>진탐·실패표면 미스로 폐기, floor+guards.md write-time+review claim-review 3층이 완성. AGENTS.md 명시).

🔴 **owed 원장은 별도다** — [`runbooks/owed-verification.md`](runbooks/owed-verification.md)
안전등급 **미결 0건** — `#1062`(NULL-owner IDOR 오차단)는 **2026-07-22 회고에서 사용자 명시 결정으로
⏭️ 위험 수용 전환**(노출면[NULL-owner repo·다중 사용자]이 현재 비어 있음 + 앱계층 가드 3곳 + RLS
Phase4 검증. 재개 조건은 원장 참조). 운영등급 `#1072` 1건 (`#1075` 는 2026-07-19 20:00 UTC 실측 종결).

---

## 🟡 2026-07-23 종합감사 잔여 P2 (32건 — 스냅샷 = [아카이브 보고서](_archive/reports/2026-07-23-comprehensive-review.md))

> 회고 P1-C(2026-07-24): 감사 잔여를 메모리-only 에서 정본 원장으로 이관(observer-lie 시정). 각 행 상세·정확 line 은 아카이브 참조. 사용자 "전부 진행" 승인 하 — tier 별 처리 방식 명시.

| tier | 영역 | 항목 (요약) |
|------|------|------------|
| ✅ 완료 (2026-07-24) | **명확 버그 6/8** | ~~security_scan 403 오분류~~(#1204) · ~~secret 캐시 poison~~(#1204) · ~~telegram per-repo chat_id dead~~(#1205) · ~~issue_reg 중복 이슈 무음 폐기~~(#1207) · ~~pre-push max_tokens 절단~~(#1208) · ~~escape_markdown @-멘션~~(#1208) |
| 🟡 자율 (잔여) | **명확 버그 1** | ~~security_scan per_page=100 무페이지네이션~~(#1210 — 마지막 페이지까지 순회 + 상한 WARNING) · **cron weekly/trend 'already-sent' 미기록 double-send** (🔴 manual+scheduler 중복 발송 — dedup 기록[schema/column] 설계 필요, 단순 상수 아님. 세션말미 schema 변경 회피 — 다음 세션) |
| 🟡 자율 | **SQL 집계** (중간 위험) | cost/security-alert/trend/frequent_issues 전량 Python 로드(SQL SUM/AVG/GROUP BY 부재) + claude_api_calls·security_alert_process_logs retention GC 부재 |
| ✅ 3/4 완료 (2026-07-24) / 🟡 잔여 1 | **가드 self-defect** | ~~check_guard_fail_open B8 면제 bare-substring·aliased import 미탐~~(#1213 tokenize+import해소) · ~~check_architecture_tree_sync cross-dir substring fail-open~~(#1214 트리엔트리 경계) · ~~test_guard_wiring_coverage tautological/path-comment 오판~~(#1215 comment-strip+dead-hook 탐지) · 🟡 **잔여**: security.md 로깅 리댁션 coverage guard(`test_logging_config` 가 root/uvicorn/uvicorn.access **하드코딩 3 로거만** 검사 — 신규 propagate=False 로거 자체 핸들러가 필터 우회해도 미탐 가능성. 🔴 **모호·실재성 재검증 필요**[approve 오탐 전례], enumerate-all-propagate-false 강화 검토, 다음 세션) |
| ⏹️ 오탐 정정 / 🟡 defer | **misc** | ~~gate/actions/approve auto-approve 민감경로 가드 누락~~ = **오탐 재검증(2026-07-24)**: `approve.py`/`auto_merge.py` **양쪽 모두 동일 3가드**(static_incomplete·ai_truncated·ai_failed) 보유, **민감경로 가드 개념 자체가 두 액션 어디에도 없음** → 비대칭 아님, 수정 대상 없음(감사 오귀속). · cron notify DB 커넥션 per-repo I/O 보유 = **defer 결정(서비스품질)**: 직렬 background cron·≤6 repo·커넥션 수초 보유라 실영향 미미, 세션 lifetime refactor 는 중간위험(rollback 인터리브) — 세션말미 복잡변경 회피(회고 교훈). 다음 세션 |
| ✅/⏹️ 결정 완료 (2026-07-24, 서비스품질 위주) | **설계/동작 5** | ~~verifier band(고득점 인젝션 우회)~~=**밴드 상한 제거·보안>비용**(#1207) · ~~enqueue find-then-INSERT~~=**first-writer-wins**(#1206) · ~~webhook Closes#N base~~=**default 브랜치만 close**(#1205) · retry `attempts_count` 소진=**바운드 유지**(무한루프 위험>30회 후 abandon, 변경 안 함) · abandon_stale lost-update=**P1-5 CAS 가 이미 커버**(변경 불필요) |
| ✅ 완료 (2026-07-24) | **동작 1** | ~~webhook issue-close 동기 인라인~~(#1211 — `_close_referenced_issues` BackgroundTask 위임, N개 GitHub 왕복이 ~10s webhook 타임아웃 유발하던 것 봉인) |
| ⏸️ 정책 11 (사용자 시각검증) | **UI 템플릿** | analysis_detail·add_repo historyRestore 미배선(뒤로가기 후 버튼 죽음) · overview avg_score 0 Jinja truthiness 숨김 · dashboard chart label `\| e`→`\| tojson` · tweaks.js html data-theme desync |

## 🔴 사용자 결정 대기

| **B6-b** | **AI 자기 머지 거버넌스 (넓은 범위)** (세션5 회고 P1). B6-a(민감 경로)는 #1147 로 봉인된 반면 이 넓은 범위는 미결이다. B6-a(민감 경로)는 #1147 로 봉인됐으나, **비민감 PR 의 점수 기반 무검토 자동 머지**(6 리포 전부 `merge_threshold=60`·`reviews=0`)는 그대로다. 남은 결정 = Claude 소유자 토큰 자기 머지를 (a) 비민감도 사람 검토 요구 / (b) 현행(민감만 차단) 유지 / (c) auto-merge 임계 상향. 권장 = **(b) 현행 유지** — 민감 변경은 봉인됐고 비민감 무검토 머지는 속도 이득이 위험을 상회(사용자가 구축한 워크플로). 이견 시 회신 | 세션5 회고가 오기록(전건 이행 주장) 적발 | 🔴 사용자 결정 |

## 🟡 착수 가능 (Claude 자율)

결정 없이 진행 가능. 우선순위 순.

| # | 일감 | 근거 | 출처 |
|---|------|------|------|
| **B7** | **스케줄러 실행 기록 DB 영속화** (D4 결정) — 🔴 **긴급도 재평가 필요**: 원 근거 "로그로는 스케줄러 생존을 판정 못 한다" 는 `#1102`(로깅 복구) 이후 **약화됐다** — 실제로 `scheduler started — 6 jobs` + 60초 주기 tick 이 로그로 관측된다. DB 는 여전히 내구성·다중 인스턴스·소진성 신호 회피에 유용하나 **P0 가 아니라 durability 편의**다. D4 우선순위 재확인 권장 — job 별 `last_run_at`·`last_status` 1행 upsert 테이블 + 마이그레이션. 스케줄러 생존이 **SELECT 1회**로 판정되고, owed 원장의 소진성 신호(만료 캐시 8행 보존 제약) 없이 상시 검증 가능 | 회고1에서 **3 에이전트 독립 권고**. 로그 의존 검증 → DB 의존 검증이 이번 사고의 진짜 일반화된 교훈 | D4 결정 |

---

## ⏸️ 보류 (의도적)

| # | 일감 | 보류 사유 |
|---|------|----------|
| **H2** | **Code Scanning open alert 2건** — `py/unnecessary-lambda`(note), `tests/unit/scripts/test_guard_git_failclosed.py:26,27` | note 등급·테스트 코드. `#1096` 이 `#1097`(note 게이트)보다 먼저 머지돼 시점상 미포착 |
| **H4** | **typescript `>=6.1.0` dependabot ignore (#1232 실측)** — `package.json` 은 `^5.9.3` 핀, `.github/dependabot.yml` 이 재제안을 억제 | **기전**: `@typescript-eslint/parser` 8.x peer = `typescript >=4.8.4 <6.1.0` → typescript 7 로 올리면 `npm ci` 가 **ERESOLVE 로 실패**(빌드 자체가 깨짐). 이 파서는 런타임 eslint 분석기가 .ts/.tsx 를 파싱하는 수단이라 버리면 **TS 정적분석이 #1226 상태로 회귀**한다. 🔴 dependabot PR #1232 가 실제로 올라와 `lint-js 공허화 차단` job 이 red 로 잡았다(가드 첫 실전 적발). 🔴 **2026-07-30 실측 — 잔여 헤드룸 0**: `6.0.3` 은 통과하나 `6.1.0` 도 이미 peer 범위 밖이라(satisfies=false) #1236 머지 후 dependabot 이 제안 가능한 typescript 업데이트는 **6.0.x 패치뿐**이다. **반증 수단**: `npm view @typescript-eslint/parser peerDependencies.typescript` 가 7 을 포함하면 해제 가능 = 이 행 제거 + ignore 삭제 + `pytest tests/integration/test_eslint_analyzer.py`(.ts/.tsx 축) 통과 확인 |
| **H3** | **semgrep `>=1.171.0` dependabot ignore (#1227 항목 2)** — `requirements.txt` 는 `semgrep==1.170.1` 핀, `.github/dependabot.yml` 이 재제안을 억제 | **기전**: semgrep 1.171.0 → `click~=8.4.2` vs sqlfluff 4.2.2(최신) → `click<8.4.0` = ResolutionImpossible. SQL 정적분석 유지를 우선해 semgrep 을 보류(2026-07-29 사용자 결정). 🔴 **ignore 는 해제 조건 충족을 알려주지 않는다**(silent-disable) — 그래서 여기 등재. **반증 수단**: `pip index versions sqlfluff` 로 신버전 확인 후 `pip install --dry-run -r requirements.txt -r requirements-dev.txt` 가 성공하면 보류 해제 가능 = 이 행 제거 + dependabot ignore 삭제 |

---

## 갱신 규칙

- 일감 완료 시 ✅ 로 표시하고 **다음 정리 시 제거**(이 파일은 append-only 아님 — 현재 상태를 반영한다).
- 신규 회고·감사 종료 시 **잔여 findings 를 여기로 이관**한다. 보고서는 시점 스냅샷으로 아카이브에 남기고, "지금 뭐가 남았나" 는 이 파일이 답한다.
- 🔴 **결정 대기 항목은 다음 사이클 진입 시 사용자 회신 요청 의무**(정책 5/9 페어).
- 🔴 **모든 🟡 행은 (기전 · 반증 수단)을 함께 적는다** (2026-07-19 전수 점검 신설).
  처방문은 **실행될 코드**다 — B2 의 처방은 무효 키였고, B2-b 의 블로커는 거짓이었으며,
  B6 의 근거는 귀속이 틀렸다. 셋 다 *그럴듯한 산문*이라 검토를 통과했다.
  - **기전** = 어느 코드/설정면이 이 문제를 만드는가 (예: `src/gate/engine.py::_run_auto_merge`)
  - **반증 수단** = 이 주장이 틀렸다면 무엇을 측정하면 드러나는가
    (예: *"`mergedBy` 가 봇이 아니라 토큰 소유자면 gate auto-merge 가 아니다"*)
  - 🔴 **"봉인/불가능/전량" 류 단정은 착수 전 반증 측정 1회 의무** — 위 3건 모두 이 한 번을
    안 해서 원장에 거짓이 남았다.
  - ❌ **기계 린터는 만들지 않는다** (Grok 협의 결론) — 자유 산문의 진위는 정적 검사로 판정할
    수 없고, 구조만 검사하는 린터는 통과가 아무것도 보장하지 않아 **이 세션이 계속 다룬
    observer-lie 를 하나 더 만드는 일**이 된다. 진위 판정은 사람/Grok 의 몫으로 둔다.
