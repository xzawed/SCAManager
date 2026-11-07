# 회고 2026-11-06 — `#1684~#1812`

## 범위

| | 값 |
|---|---|
| 기계 산출 범위 | `#1684~#1812 (109 PR, boundary dfc6423 .. head dfb3115c)` |
| 경계 커밋 | `dfc6423` (직전 리포트 `2026-09-16-retrospective.md` 추가 커밋) |
| head | `dfb3115c` = `main` (분석 종료 시점) |
| 정직성 필드 | `gh_only: []` · `unmeasured: []` |
| 🔴 실제 기점 | 출력의 boundary 가 아니라 직전 리포트의 «분석 종료 head» `2613028e`(main 밖)에서 셌다 — `#1684` 가 두 회고에 겹친다(L14) |
| 🔴 기록 보존 | 창 52일 > 대화 기록 보존 30일 — 109 PR 중 34건의 세션 기록이 이미 없다(L14 P1) |
| 실행 중 범위 이동 | 없음 |

## ROI

| 지표 | 값 |
|---|---|
| 라운드 (loop-until-dry) | 3 |
| 총 발견 | 165 |
| 확정 | **162** |
| 오탐 차단 | 3 |
| 심각도 조정 | 21 |
| verdict 커버리지 | 1 |
| 미검증 잔여 | 0 |
| 실행 중 범위 이동 | 없음 |
| P0 / P1 / P2 | 7 / 42 / 113 |

에이전트 191 · 오류 0 · 10h42m · 3,074만 토큰(직전 176 · 3h29m · 1,604만).
🔴 실행 전 예상(1~3시간)의 3.5배였다. 다음 예상은 이 실측에서 출발한다.
5관점(process·code·docs·decision·tooling) finder 3라운드(41 · 42 · 38건) → 전건 cross-verify →
완전성 비평가 gap 8건 → 표적 라운드(44건) → 검증.

## 🔴 이 회고가 실행 중에 낸 사고 — 리포트 작성자 확인(워크플로 교차검증 밖)

1. **운영 비밀값 노출.** docs 관점 1라운드 에이전트가 deploy.md 사본값을 대조하려고 문서의
   «읽기» 명령을 그대로 실행했고, 운영 서비스 변수 19개(비밀 13 · 개인정보 2)가 출력됐다.
   표적 라운드의 docs 에이전트도 그중 하나를 다시 출력했다. 값이 남은 곳은 이 PC 의 에이전트
   기록 2개와 그 에이전트들의 모델 API 요청이다. 리포 · Issue · 오케스트레이터 대화에는 없다
   (값을 열지 않고 개수만 센 기록 252개 + 회고 시작 뒤 바뀐 파일 31,771개).
   처리(사용자 결정): 기록의 값 가림 · 비밀값 12개 회전 · 토큰 암호화 키 교체와 GitHub 로그인 토큰
   일괄 폐기(키와 DB 접속 주소가 함께 노출돼, 재암호화로는 이미 읽혔을 수 있는 토큰을 못 막는다) ·
   경로 차단 PR #1813 · 이 보고서는 회전 뒤 게시.
2. **운영 컨테이너 코드 실행.** 표적 라운드의 code 에이전트가 측정 스크립트 3개를 `railway ssh` 로
   운영 컨테이너에 실어 앱 워커 자격으로 실행했다(11-06 20:49~20:56Z). 트랜잭션 단위
   `BEGIN READ ONLY` 였고, 실행 뒤 새 연결의 `default_transaction_read_only` 는 `off/default`,
   현재 배포 로그의 read-only 오류는 0 — 피해는 없었다. 그러나 아래 뿌리 A 의 바로 그 꼴
   (사전 승인 없는 운영 런타임 코드 실행 · 앱 쓰기 자격)을 회고 계기가 되풀이했다.
3. **공통 원인.** 이 실행 때 회고 워크플로 에이전트에는 운영 접근을 막는 장치가 없었고, 오케스트레이터도
   디스패치할 때 운영 접근을 금지하지 않았다. → `[WBS]` 원장 L14 에 추가 등재(R-1). 교차검증은 다음 회고가 한다.

## P0 (7건 — 뿌리 둘)

### 뿌리 A — 운영 측정 사고(25시간 장애)의 재발 방지가 산문 한 줄이다 (P0-1 · P0-3 · P0-4 · P0-5 · P0-6)

- 좌표: `CLAUDE.md` 협업 규칙의 «운영 DB(MCP · `railway ssh`)» 줄 · `.claude/settings.json` ·
  `.claude/hooks/` — 줄번호가 아니라 인용 문구가 앵커다.
- 사실: 2026-10-25 13:03Z ~ 10-26 14:00Z(약 25시간). `#1764` B안 운영 측정 계기가 `railway ssh` 로
  운영 컨테이너에 브랜치 코드를 실어 앱 워커 역할(BYPASSRLS · Supavisor 트랜잭션 풀러 6543)로
  실행했고, 연결마다 autocommit 으로 `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` 를
  보냈다. 그 설정이 풀러의 서버 연결에 남아 분석 저장 · GitHub 로그인 · 머지 재시도 · 스케줄러가
  전부 실패했다. 발견은 사용자 신고(«로그인이 안 된다»)였다. 피해는 웹훅 427건 · 분석 이벤트
  약 70건이고, 사용자 결정은 재전송 안 함이다.
- 다섯 관점이 서로 다른 증거로 확인한 결함:
  1. 시정 `#1775` 는 CLAUDE.md 한 줄뿐이다. 근거로 든 «리포 가드는 리포 밖을 못 본다» 는
     07-19 의 `block_credential_dump.py`(명령 글자를 보는 훅)와 11-05 의 메모리 쓰기 훅이 반증한다.
  2. 위임 경계가 SQL 문장 종류(SELECT)로 그어져 있다. 실제 행위는 «쓰기 가능한 앱 자격으로 운영
     컨테이너에서 에이전트 코드 실행» 이었고, `#1775` 는 그 경로를 «SELECT 자율» 칸에 넣었다.
  3. 장애 중 두 번째 측정 · `#1773` 머지 · 배포 SUCCESS · «배포 후 읽기 전용 확인» 이 모두
     지나갔지만 에이전트 쪽 확인은 하나도 잡지 못했다. 읽기 전용 확인은 원리적으로 쓰기 실패를
     보지 못한다.
  4. 피해와 «재전송 안 함» 결정은 개인 메모리에만 있고, `#1773` · `#1774` 본문의 «읽기 전용
     실행» 은 정정되지 않았다.
- 처방(검증자들이 모은 것 — 수정은 사용자 결정):
  1. 측정 전용 읽기 역할 — 역할 수준 read only · 쓰기 권한 0 · 앱과 다른 풀(권한 변경 → 착수 전 확인).
  2. 운영 접속을 커밋된 헬퍼 하나로 — 트랜잭션 단위 `BEGIN READ ONLY` · 세션 SET 거부 · 끝나면 새
     연결에서 `pg_settings.source='session'` 0건 확인.
  3. PreToolUse 훅 — Bash · PowerShell · Write 내용 · MCP `execute_sql` 에서 세션 SET 을 거부하고,
     `railway ssh` 로 코드를 실어 보내는 실행은 사전 승인 표지를 요구한다.
  4. 위임 경계를 행위 범주로 — «운영 런타임에서 에이전트 코드 실행 · 앱 자격 사용» 은 사전 승인.
  5. 머지 · 운영 접촉 뒤 쓰기 경로 신호 하나(최근 분석 저장 시각 · 스케줄러 오류 0).
  6. 사고를 Issue 로 남기고 `#1773` · `#1774` 에 정정 댓글.
- 처리(사용자 결정 «3층 안»): 위임 경계를 행위로 — 배포 · 로그 · 상태 읽기와 관측 역할의 DB 읽기만 자율,
  운영 실행 · 배포 · 변수 · 그 밖의 DB SQL 은 사용자가 직접(훅 차단 #1818) · 관측 전용 DB 역할과 조회 도구
  (허용 컬럼만 · 읽기 전용 · 앱과 다른 풀 #1820) · DB 하트비트(풀 연결에 남은 세션 READ ONLY 를 1분 안에
  되돌리고, 3분 이어지면 알림 #1821) · 실패한 배포를 조건을 확인하고 다시 거는 스크립트(#1819 · #1822) ·
  `#1773` · `#1774` 정정 댓글. 피해와 «재전송 안 함» 결정은 이 보고서가 리포에 남긴다.

### 뿌리 B — deploy.md 의 «읽기» 처방이 운영 비밀값을 평문으로 낸다 (P0-2 · P0-7)

- 좌표: `docs/workflow/deploy.md` 첫 단락의 «읽기:» · `.claude/hooks/block_credential_dump.py`
- 주장: `#1723`(09-29)이 `railway.toml` 을 지우며 배포 설정 «읽기» 로 `railway environment config --json`
  을 적었다. CLI 는 변수를 복호화해 조회하고 `--json` 은 서비스 · 공유 변수 값을 그대로 싣는다
  (CLI 도움말 «JSON and KV output include raw variable values»). 차단 훅은 `railway variables` ·
  `printenv` · `cat/type .env` 만 알았고, Bash 에만 걸려 PowerShell 도구로는 `railway variables`
  도 통과했다.
- 근거: 이 회고의 에이전트가 실제로 그 명령을 실행했다(위 «실행 중 사고» 1).
- 처리: 경로 차단 PR #1813 — deploy.md 를 변수 절을 뺀 읽기(`scripts/railway_config.py`)로
  바꾸고, 훅이 CLI 별칭 · PowerShell · Railway MCP `list_variables` · `railway ssh|run env` 를 막는다.
  Grok 반증 검토가 원래 훅부터 있던 «이름만 자르기» 예외의 구멍을 여러 개 찾아 함께 막았다.
  재귀 검색이 `.env` 를 읽는 꼴은 후속 #1814.

## P1 (42건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | L02 | process | 25시간 장애를 에이전트 쪽 확인이 하나도 못 봤다. 장애 중 운영 측정(10-26 12:04Z)과 #1773 머지·배포(SUCCESS 13:34:40Z)가 지나갔고, 발견은 사용자 로그인 실패였다. 그 공백(#1746 K22 P1-52 «절차가 머지에서 끝난다»)은 사고 뒤에도 원장에서 움직이지 않았다 | `CLAUDE.md` |
| 2 | L15 | process | 회고 착수 신호가 세 회고 연속 «부재» 로 확정됐는데 아직도 그 신호를 내는 곳이 하나도 없다 — 창이 55 → 109 PR(«임계 15» 의 7.3배)로 두 배가 됐다 | `.claude/settings.json` |
| 3 | L10 | process | CLAUDE.md:87 은 «메모리 진입점엔 수치·SHA 를 적지 않는다» 를 check_memory_refs.py 가 집행한다고 적었지만, 그 스크립트는 SHA 를 금지하지 않고 «실재하는지» 만 확인한다. 규칙을 넣은 다음 날 MEMORY.md 진입점 줄에 SHA 10개가 적혔는데 집행자와 쓰기 훅 모두 초록이다 | `CLAUDE.md` |
| 4 | L04 | code | #1809 이후 설정 «저장됨·저장 실패» 토스트가 sticky nav 밑에 깔려 보이지 않는다. 쌓임 맥락(.container z-index:1 < nav 100)은 바뀌지 않았다 | `src/templates/base.html` |
| 5 | L10 | docs | CLAUDE.md:87 은 «메모리 진입점에 수치·SHA 를 적지 않는다» 를 `check_memory_refs.py` 가 지킨다고 적는다. 그런데 그 스크립트와 시험은 진입점 줄의 SHA 를 «실재하면 통과» 로 판정하고, 규칙을 넣은 #1805 뒤에도 진입점 줄의 SHA 10개가 초록이다 | `CLAUDE.md` |
| 6 | L08 | tooling | required 체크 11개 중 9개에 timeout-minutes 가 없다. #1808 의 required pytest 잡은 apt 단계에서 5시간 35분 멈췄고, 같은 사이클 E2E 설치 단계도 4회 11~17분 정체했다 | `.github/workflows/ci.yml` |
| 7 | L09 | tooling | subprocess 로만 부르는 semgrep 을 앱과 한 venv 에 설치해, 그 정확 핀이 이 사이클 required pip-audit 를 네 번 막았다(PR red 11 · main red 1 · 해제 PR 4). fastapi 도 0.141 에 묶였다 | `requirements.txt` |
| 8 | L14 | tooling | 회고 범위 출력의 boundary 는 실제 스캔 기점이 아니다. boundary..head 로 diff 를 재면 109 PR 중 #1684·#1685·#1686 이 빠지고, #1684 는 직전 회고 P0 의 바로 그 PR 이다 | `scripts/retro_scope.py` |
| 9 | L08 | tooling | E2E 스위트가 이 사이클 16.7→24.4분(중앙값 +46%)으로 자랐는데 관측자는 여전히 0이다. #1766 은 준비 단계 정체만 근거로 벽을 45분으로 올렸고, 10-22 급 정체가 지금 크기 스위트와 겹치면 약 44.8분이다(추정) | `.github/workflows/ci.yml` |
| 10 | L06 | process/visual-gate | «시각 변경은 사람이 봐야 한다»가 머지에 묶여 있지 않다. #1791 은 사람 확인 3항목을 남긴 채 머지·배포됐고, 머지 뒤 처음 본 그 항목(375px 줄바꿈)이 실패해 #1792 가 필요했다 | `CLAUDE.md` |
| 11 | L16 | process/ledger-priority | 원장 정렬 «… → 개발 도구 → 문서·절차» 때문에 절차 묶음 4개(21건)가 하나도 해소되지 않았고, 그 사이 이 묶음들이 예고한 실패가 창 안에서 실제로 일어났다 | `.claude/skills/retrospective/SKILL.md` |
| 12 | L10 | process/memory-rule | CLAUDE.md:87 은 «메모리 진입점은 수치·SHA 를 적지 않는다(check_memory_refs.py)»라고 하지만, 인용된 집행자는 SHA 를 «있으면 통과»로 판정한다. 규칙이 생긴 다음 날 MEMORY.md 진입점 줄에 SHA 10개·PR 14개가 쌓였는데 가드는 exit 0 이다 | `CLAUDE.md` |
| 13 | L18 | docs | README «Deploying(Railway)» 절차를 그대로 따르면 앱이 안 뜬다 — 필수 TELEGRAM_* 가 빠져 있고, #1723 이후 저장소가 실어 주던 pre-deploy·헬스체크도 사라졌다 | `README.md` |
| 14 | L10 | docs | CLAUDE.md 가 «메모리 진입점은 Issue 를 가리키고 수치·SHA 를 적지 않는다(check_memory_refs.py)» 고 가르치지만, 그 스크립트는 SHA 를 허용하도록 설계·시험돼 있고 실제 MEMORY.md 진입점 줄에는 SHA 가 10개 있다 | `CLAUDE.md` |
| 15 | L02 | decision | #1775 시정이 문서 한 줄로 끝났다 — «리포 가드가 볼 수 없다» 는 판단 근거가 틀렸고, 새 규칙은 railway ssh 를 오히려 «SELECT 자율» 쪽에 명시적으로 넣었다 | `.claude/settings.json` |
| 16 | L02 | decision | 장애 기전이었던 «읽기 전용 실행 · 쓰기 거부» 자기 보고가 #1773·#1774 에 정정 없이 남았고, 피해 규모와 «재전송 안 함» 결정은 개인 메모리에만 있다 | `CLAUDE.md` |
| 17 | L06 | decision | 머지 대부분을 에이전트가 구두 승인을 받아 하는데, 승인 범위 규칙은 리포에 없고 GitHub 에서는 승인 주체를 되짚을 수 없다 — #1771 은 승인 뒤 대상이 2.1.0→2.3.0 으로 바뀐 채 머지됐다 | `CLAUDE.md` |
| 18 | L07 | decision | 운영 DB 리전 이전의 «결정» 이 사용자가 결정하기 전에 런북에 먼저 적혔고, 실제 승인 시점과 주체는 GitHub 어디에도 없다 | — |
| 19 | L14 | decision | 회고 워크플로가 «이전 라운드 항목 제외» 를 목록도 주지 않고 지시하고 제목 일치로만 중복을 거른다 — 직전 회고 확정 140건은 라운드마다 같은 결함을 다시 셌고, «loop-until-dry» 는 구조상 일찍 멈출 수 없다 | `.claude/workflows/retrospective.mjs` |
| 20 | L14 | tooling | The retro loop-until-dry can never run dry: from round 2 the prompt says 'exclude earlier items' but never supplies the list, and dedupe keys on exact title, so the same defect is confirmed again every round | `.claude/workflows/retrospective.mjs` |
| 21 | L02 | process | 장애 계기의 안전장치 세 겹이 모두 위험 축 밖이었다 — 출처는 리뷰 없는 메모리 «참조 절차», 보정 DB 에는 풀러가 없었고, 자기검사는 방금 켠 값을 다시 읽었다(장애 중 같은 계기를 5번 더 돌렸고 매번 «read_only=on» 통과) | `CLAUDE.md` |
| 22 | L02 | process | 운영 행위의 안전성은 교차 벤더 검토의 «반증 대상» 이 된 적이 없다 — Grok CLAIM-REVIEW 240회(10-11~11-07) 중 계기 연결 코드를 실은 것 0, «read-only» 는 매번 CONTEXT 전제였고, 시정 #1775 는 «claim-review 대상 표면 없음» 으로 빠졌다 | `scripts/check_claim_review_trace.py` |
| 23 | L11 | process | 문서 심의 게이트의 warn 19 · block 6 이 이 창에서 한 건도 전달되지 않았다(25/25) — 5개 세션에 걸친 하네스 오류 25회를 아무도 보고·원장에 올리지 않았고, 유일하게 전달된 «캐시 미동작» 고지(바로 그 원인)는 «관계없는 훅 상태 경고» 로 넘겼다 | `.claude/hooks/doc_review_gate.py` |
| 24 | L14 | process | 회고 창(52일)이 대화 기록 보존 기본값(30일)보다 길다 — 이번 창 109 PR 중 34건(사람 27건, 09-16~09-29 머지)의 세션 기록이 이미 없어 그 구간의 사용자 발화·승인·운영 행위를 원본으로 대조할 수 없는데, 범위 산출은 unmeasured 를 빈 목록으로 낸다 | `scripts/retro_scope.py` |
| 25 | L04 | code | #1789 forced-colors 감사가 ARIA 로 선언된 상태 쌍만 뽑아서, 앱이 가장 많이 쓰는 «.active 클래스만» 상태가 감사 범위 밖이다 — 감사 대상 화면인 리포 상세의 필터 3그룹은 forced-colors 에서 켜짐과 꺼짐의 계산값이 같다(실측) | `e2e/test_state_indication.py` |
| 26 | L10 | docs | CLAUDE.md «메모리 진입점은 수치·SHA 를 적지 않는다» 의 집행자 check_memory_refs.py 는 SHA 를 금지하지 않고 «실재» 만 본다 — 규칙 다음 날 갱신된 진입점 줄이 머지 SHA 10개를 실은 채 ✅ | `CLAUDE.md` |
| 27 | L06 | decision | 머지 승인이 «PR 번호» 에만 묶여 승인 뒤 바뀐 내용이 재확인 없이 머지된다 — #1795(시각 변경, 사용자 화면 검토 전) · #1797(«#1798 머지 승인» 12분 뒤) · #1771(2.1.0→2.3.0) | `CLAUDE.md` |
| 28 | L02 | decision | 자기가 낸 25시간 운영 장애 동안 자율 보고는 «읽기 전용 · 배포 후 확인 끝» 이라고 썼고, 원인을 알리기 6분 전에 #1774 를 머지·배포했다 — #1773·#1774 본문은 지금도 정정되지 않았다 | `CLAUDE.md` |
| 29 | L02 | decision | 운영 접근의 위임 경계를 «채널 이름 + SQL 문장 종류» 로만 그어서, 운영 컨테이너 안 에이전트 Python 실행 40회가 «SELECT 자율» 로 돌았다 — 25시간 장애 뒤 #1775 도 그 분류 축은 그대로 뒀다 (심각도 조정) | `CLAUDE.md` |
| 30 | L11 | tooling | 훅 2종이 «편집된 파일이 속한 체크아웃» 이 아니라 «훅 파일 위치» 로 리포를 정한다 — 워크트리 편집에서 스모크는 거짓 초록을 내고, 문서 심의는 조용히 꺼진다 | `.claude/hooks/posttool_pytest_smoke.py` |
| 31 | L08 | ci-budget | #1766 의 45분 산식이 지금 기록에서 깨졌다. 같은 표본(main+PR)으로 넣으면 27m43s + 18m04s = 45m47s > 45m | `.github/workflows/ci.yml` |
| 32 | L08 | ci-budget | E2E 시간 예산 관측자가 여전히 0이다. 유일한 계기는 건수를 재는데, 건수로는 시간을 설명할 수 없다 | `scripts/check_e2e_scope.py` |
| 33 | L09 | security | 의존성을 올린 뒤 «도달 불가» 전제를 다시 잰 기록이 없다 — #1733 의 사람 확인은 해제 조건 (1)(semgrep 핀)만 본다 | `.github/workflows/ci.yml` |
| 34 | L09 | security | semgrep 을 앱 venv 에서 떼는 구조 대안이 «#1733 에 적었다» 고 했지만 어느 판에도 없다 — 그 뒤 예외 결정 3번이 이 대안을 비교하지 않았다 | `Dockerfile` |
| 35 | L05 | security | 보안 알림이 GitHub 에서 닫혀도 «신규 pending» 에서 영영 빠지지 않는다 — 폴링은 open 만 받고, 닫힘을 반영하는 writer 가 없다(프로브 실측) | `src/services/security_scan_service.py` |
| 36 | L10 | docs/memory | CLAUDE.md:87 이 괄호로 지목한 check_memory_refs.py 는 SHA 절을 반대 술어로 판정한다. 금지된 SHA 10개가 든 진입점 줄에 «✅ 전건 유효» 가 나온다 | `CLAUDE.md` |
| 37 | L13 | process | K22 악화: 창 안 main push CI 107회 중 비초록이 5건이다(실패 2 · 연속 취소 1 · 재실행으로 가려진 red 2). check_main_red.py 는 창 안 커밋이 0이고 여전히 최신 1건만 판정한다. 재실행이 가린 red 는 «최신 N건» 으로 넓혀도 보이지 않는다 | `scripts/check_main_red.py` |
| 38 | L08 | tooling | K20 악화: 관측자 없이 E2E 시간 예산이 줄고 있다. 스위트 p50 16.8 → 23.3분(+39%)이고, 성공 잡 하나가 옛 30분 벽과 같은 1800초를 찍었다. 원장 증거(p50 18.0분 · 30분 벽의 62% · 덧쓰인 푸시 3건)는 전부 낡았다 | `.github/workflows/ci.yml` |
| 39 | L03 | code/analyzer | semgrep 레지스트리가 룰셋을 HTTP 오류로 거절하면(rc=7) «이슈 0건 · 완전 분석» 으로 기록된다. 어댑터가 실물 바이너리의 실패 모양을 보지 못한다 | `src/analyzer/io/tools/semgrep.py` |
| 40 | L03 | code/analyzer | semgrep 룰셋은 버전 없이 파일마다 실행 시점에 받아 온다. `semgrep==` 핀은 엔진만 고정하고, 게이트를 가장 많이 움직이는 입력은 기록도 diff 도 없이 바뀔 수 있다(이번 창은 잠재 위험이고 drift 는 관측되지 않았다) | `src/analyzer/io/tools/semgrep.py` |
| 41 | L06 | process | 시각 변경 PR 의 «사람이 확인할 것» 에 머지 시점 상태가 없다 — 확인이 머지 뒤로 밀려도 기록되지 않고, #1791 은 그 항목이 실패한 채 배포됐다 | `CLAUDE.md` |
| 42 | L14 | tooling | +1 완전성 비평가는 검증 항목의 «개수» 와 호출자 scope 문자열만 받는다. 그래서 이번 실행의 gap 8개 중 5개가 verified[] 에 이미 2~6벌 있는 주제를 같은 수치로 다시 골랐다 | `.claude/workflows/retrospective.mjs` |

## P2 (113건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | L19 | process | 이 창의 함정·절차 교훈 넷이 리포가 아니라 이 PC 의 메모리에만 남았다 — 마이그레이션 잠금 상한 · 시각 변경 «머지 전» · SET SESSION 진단·복구 · 보완 커밋 뒤 PR 제목 (심각도 조정) | `docs/workflow/db.md` |
| 2 | L10 | process | 항상 로드되는 MEMORY.md 가 문서화된 로드 상한(25KB)의 97.6% 에 와 있다. 남은 595 B 는 진입점 줄이 한 세션에 늘어난 양(+233 B)으로 두세 세션이면 바닥나고, 넘치면 파일 끝의 행동 규칙부터 조용히 로드되지 않는다 (심각도 조정) | (메모리) MEMORY.md |
| 3 | L16 | process | 원장 #1746 은 #1766 이 이미 닫은 P2-61 을 14일째 «근거가 여전히 거짓» 으로 적어 두고 있다. PR 이 «원장 체크는 머지 뒤 결정에 맡긴다» 고 넘겼는데 아무도 결정하지 않았다. 회고 다음 묶음이 바로 K20 이다 | `.github/workflows/ci.yml` |
| 4 | L18 | process | 🔴 «문서 총량은 늘리지 않는다» 는 아무도 재지 않는 규칙이다. 창 전체에서 +814자가 늘었고, «뺀 것 없음» 3회와 «0 이하를 못 맞췄다» 1회로 넘어갔다. 같은 규칙이 db.md 에 함정 한 줄을 넣지 않는 근거로는 쓰였다 | `CLAUDE.md` |
| 5 | L20 | process | 테스트 수 사본 줄이 PR 흐름에서 늘 충돌하는 지점이다. 106 커밋 중 61개가 STATE.md · README 배지를 고쳤고, PR 9건이 «수치 줄 충돌 → 재계산» 을 적었다. 창 첫머리의 main red 도 바로 이 줄 때문이었다(브랜치 보호 strict=false) | `docs/STATE.md` |
| 6 | L17 | code | 대시보드 repos 모드의 리포 레포트는 동기 DB 9문장을 여전히 이벤트 루프에서 돌린다. #1720 이 범위 밖으로 남긴 자리에 #1791 이 문장을 하나 더했다 | `src/ui/routes/dashboard.py` |
| 7 | L17 | code | 유료 Claude 호출을 되풀이하지 않게 한 방어(#1716 · #1718)의 설계를 다시 볼 것 — 상세는 작성자 메모 | `src/ui/routes/dashboard.py` |
| 8 | L17 | code | 이슈 집계 상한 «30» 이 사본 셋(인사이트 상수 · 대시보드 카드 지역 리터럴 · MCP 도구 설명)으로 갈라져 있고, 상수를 바꿔도 카드와 MCP 는 red 가 나지 않는다 | `src/services/dashboard_service.py` |
| 9 | L12 | code | e2e «이번 달 비용» 팔이 달 경계(UTC 자정)를 넘는 세션에서 red 가 된다. 세션 픽스처는 시드 시각 기준이고 화면은 요청 시각 기준이다. 이 창에서 고친 #1764/#1765 와 같은 부류다 | `e2e/conftest.py` |
| 10 | L17 | code | #1718 PRG 뒤 서비스의 `refresh` 인자는 운영 호출자가 0 인데, «무효화 → 부정 캐시 건너뛰고 바로 유료 호출» 분기가 시험 4건으로만 살아 있다 | `src/services/dashboard_service.py` |
| 11 | L18 | docs | E2E 수가 바뀔 때 문서가 가르치는 절차를 그대로 따르면 CI 가 red 다. `--fix` 는 README 배지만 파생하고 STATE 의 E2E 세 지점은 손으로 고쳐야 하는데, 다섯 곳의 절차 문구는 «그 밖은 직접 편집하지 않는다» 고 가르친다(이 창 26 PR 이 손으로 고쳤다) (심각도 조정) | `docs/STATE.md` |
| 12 | L18 | docs | `check_doc_anchors.py` 가 «✅ 모든 코드 좌표가 앵커» 를 인쇄하지만 architecture.md 의 백틱 밖 줄번호 좌표 2개를 보지 못한다. 같은 파일을 고친 #1742 뒤에도 원장 P2-8 그대로다 | `docs/architecture.md` |
| 13 | L18 | docs | STATE.md E2E 줄의 «(`#1291` 기준)» 은 E2E 가 121건이던 시절의 꼬리표다. 시험 정규식이 그 글자를 붙잡고 있어 554건이 된 지금도 남아 있고, 재측정 명령은 이 PC 에 없는 `make test-e2e` 다 | `docs/STATE.md` |
| 14 | L18 | docs | CONTRIBUTING.md 가 «pre-commit 이 강제한다» 고 적은 두 축(새 src 파일 → architecture.md, 테스트 수 → STATE)이 pre-commit 단계에서는 실제로 돌지 않는다. 트리 훅의 files 정규식 첫 가지는 죽어 있다 | `CONTRIBUTING.md` |
| 15 | L18 | docs | CLAUDE.md 영역 표는 `src/shared/**` 를 security.md 로 보낸다. 그런데 이 창에서 src/shared 를 고친 커밋 8개의 계약은 전부 gate-notify.md · deploy.md 에 적혔고, security.md 에는 그 모듈이 한 번도 안 나온다 | `CLAUDE.md` |
| 16 | L18 | docs | 🔴 «문서 총량은 늘리지 않는다» 인데 이 창에서 +815자(69,748 → 70,563)가 늘었다. 실제로는 «늘면 뺀 것을 적는다» 만 집행됐고, 4 PR 은 상쇄 없이 늘렸다고 본문에 스스로 적었다 | `CLAUDE.md` |
| 17 | L18 | docs | new-machine-setup.md 가 리포 안 절차를 `README.md#quick-start` 로 가리키는데 README 에는 그 절이 없다. 추적 문서 전체의 상대 링크 중 끊긴 것은 이 하나뿐이다 | `docs/runbooks/new-machine-setup.md` |
| 18 | L18 | docs | 추적 `.md` 1개를 더하면 단위 테스트가 2건 는다는 결합이 verify.md «건수를 바꿀 때» 에 없다. 이 결합은 이 창 첫 main red 의 한 축이었고, 이번 회고 리포트 PR 이 다시 밟는다 | `docs/workflow/verify.md` |
| 19 | L06 | decision | 시각 변경 PR 이 사람 확인 없이 머지됐다. #1755 는 승인 문구를 넓게 읽었고, #1795 는 승인 뒤에 더한 시각 변경을 사용자 회신 전에 머지했다. 승인 뒤 재설계한 #1797 은 다른 PR(#1798)의 승인으로 머지했다 (심각도 조정) | `CLAUDE.md` |
| 20 | L02 | decision | 장애 피해(웹훅 427건 · 분석 이벤트 약 70건)와 사용자의 데이터 결정(«A. 재전송 안 함» — 25시간 분석 공백을 그대로 둠)이 Issue 와 리포 어디에도 없고 개인 메모리에만 있다. 원인이 된 측정을 «읽기 전용 실행»이라고 적은 #1774 는 원인을 확인한 뒤에도 그 문구 그대로 머지됐다 (심각도 조정) | `CLAUDE.md` |
| 21 | L06 | decision | CLAUDE.md:19 «머지는 사용자가 한다»가 실측과 다르다. 10-12 이후 창 안 PR 75건은 전부 에이전트가 `gh pr merge` 로 머지했다. 실제 위임 규약(무엇이 승인인가 · 승인 범위 · 승인 뒤 변경 · 시각 PR 예외)은 리포에 없고 메모리와 압축 요약에만 있다 | `CLAUDE.md` |
| 22 | L16 | decision | 직전 회고에서 decision 관점으로 확정된 15건 중 해소는 4건(27%, 전부 10-12 #1744)뿐이다. 전체 해소율 87/140(62%)의 절반이 안 된다. 원장 순서 규칙이 «문서·절차»를 맨 뒤로 보냈고, 그 부류(K08 «후속·결정의 추적면 부재»)가 이번 창에서 P0 장애의 후속으로 다시 나왔다 | `docs/reports/2026-09-16-retrospective.md` |
| 23 | L12 | tooling | required 역-뮤테이션 게이트가 tests/ 만 돌린다. 사람 PR 86건 중 e2e 로 관측한 25건을 재지 못했고(10건은 «안 잼»), 게이트를 통과하려고 텍스트 대리 단위 시험이 붙었다 (심각도 조정) | `scripts/check_reverse_mutation.py` |
| 24 | L13 | tooling | 로컬 게이트의 «보지 못하는 축» 목록에 새 required 체크 Dockerfile build + analyzer contract 가 없다. #1717 이 E2E 를 넣은 바로 다음 날 #1722·#1724 가 required 잡을 추가했다 | `scripts/pre_push_gate.py` |
| 25 | L11 | tooling | 판정이 필요 없는 편집·Bash 호출도 훅 비용을 낸다. doc_review_gate 는 비-문서 편집에도 anthropic SDK 를 먼저 import 하고(실측 2.4~3.2초), Bash 탐지 훅은 결과가 늘 0 인 PC 에서 인터프리터 probe(0.9초)를 먼저 돈다 | `.claude/hooks/doc_review_gate.py` |
| 26 | L13 | tooling | PR 본문 red 의 복구 절차가 리포 안에서 서로 모순된다. body-edit 워크플로 주석은 «rerun 은 옛 본문을 재생 → 새 SHA» 라고 하지만 #1464 이후 거짓이고, verify.md 는 «본문 수정 + rerun --failed» 다. 이 창에서는 빈 커밋 3건이 매번 CI 전체를 다시 돌렸다 | `.github/workflows/claim-review-on-body-edit.yml` |
| 27 | L10 | tooling | SessionStart 가 매 세션 112줄을 주입하고 그중 92줄이 «미참조 메모리 파일» 재고 목록이다. 직전 회고 P2-13(83줄/70줄) 뒤 같은 스크립트를 두 번 고치면서도 줄은 더 늘었다 | `scripts/check_memory_refs.py` |
| 28 | L10 | tooling | CLAUDE.md:87 «메모리 진입점 절은 … 수치·SHA 는 적지 않는다» 가 가리키는 가드는 SHA 를 금지하지 않고 «리포에 있는가» 만 본다. 같은 K18 묶음(#1804·#1805)이 반대 규칙을 동시에 만들었고, 인덱스 진입점 줄의 SHA 10개 위에서 ✅ 를 낸다 | `CLAUDE.md` |
| 29 | L15 | process/cycle-close | 회고 착수 신호가 네 번 확정된 뒤에도 없다. 10-12 원장이 «실행은 사용자가 띄운다»로 넘겼지만 사용자에게 닿는 표면은 개인 메모리 인계뿐이었고, 창이 45 → 88(첫 제안) → 109 PR 로 자랐다 (심각도 조정) | `.claude/skills/retrospective/SKILL.md` |
| 30 | L14 | process/retro-scope | 회고 범위가 직전 리포트에서 «main 아님» 경고가 붙은 head(2613028e)를 기점으로 써서 #1684 가 두 창에 겹친다. 출력의 boundary(dfc6423)는 실제 기점이 아니다 | `scripts/retro_scope.py` |
| 31 | L20 | process/merge-serialization | 테스트 수 줄이 머지 직렬화 지점이다. 사람 PR 83건 중 61건이 같은 세 파일(STATE·README·README.ko)을 고쳐서 일괄 승인이 매번 rebase 연쇄가 되고, 그 우회 절차는 리포에 없다 | `CLAUDE.md` |
| 32 | L17 | time-lag / data-integrity (pipeline) | #1721 이 연 «흔적 없는 소실 창»(슬롯 대기 중 파이프라인)이 재검토되지 않았다 — 수용 근거는 같은 사이클의 #1727·#1719 가 없앴고, #1741 은 그 주석을 다시 쓰면서도 소실 문장을 그대로 옮겼다 (심각도 조정) | `src/worker/pipeline.py` |
| 33 | L17 | regression / off-loop contract (UI route) | repos 모드 선택 리포 레포트가 집계 7개(SQL 14문장 중 10)를 이벤트 루프 스레드에서 돈다 — #1720 이 같은 파일에 루프 밖 원칙을 세운 뒤 #1774·#1791 이 그 분기를 고치며 동기 호출을 더했다 | `src/ui/routes/dashboard.py` |
| 34 | L17 | asymmetric twin / off-loop (cron HTTP entry) | #1727 은 스케줄러 job 진입만 루프 밖으로 옮겼다 — 같은 job 의 HTTP 쌍둥이(/api/internal/cron/*)는 세션 열기·닫기를 루프에서 하고, retention-sweep 은 job 전체를 루프에서 돈다 | `src/api/internal_cron.py` |
| 35 | L08 | time-lag / CI budget (E2E) | #1766 이 E2E 벽을 30→45분으로 올리며 계산한 여유 3.6분을 같은 사이클의 E2E 증가(+123건, +29%)가 약 0.2분까지 먹었다 — 같은 미러 정체가 다시 오면 그 PR 이 막으려던 «취소» 가 재발한다 | `.github/workflows/ci.yml` |
| 36 | L17 | SSOT / drift (code constant) | «카드 = 인사이트 페이지 KPI» 의 이슈 상한 30 이 세 벌로 따로 적혀 있다 — 상수 · 지역 리터럴 · MCP 도구 설명 — 그리고 셋을 묶는 시험이 0 | `src/services/dashboard_service.py` |
| 37 | L11 | docs | 문서 심의 게이트가 worktree 에서 한 문서 편집을 전부 «심의 대상 아님» 으로 조용히 넘긴다 — 이 창의 배포 문서 재작성(#1722·#1723)을 포함한 15 PR 이 심의 원장에 한 줄도 없다 (심각도 조정) | `.claude/hooks/doc_review_gate.py` |
| 38 | L18 | docs | README 가 SESSION_SECRET 에 «개발용 폴백은 없다» 고 단언하지만, 변수가 아예 없으면 앱은 공개 기본 시크릿으로 뜬다 — 이 창의 #1707 이 security.md 에는 반대 사실을 다시 적었다 | `README.md` |
| 39 | L19 | docs | 0048 이 운영에서 실측한 마이그레이션 함정(세션 lock_timeout=0·statement_timeout=2min · ACCESS EXCLUSIVE 는 COMMIT 까지 · count(id) 는 Index Only Scan 차단)이 그 리비전 docstring 과 전용 시험에만 있다 — alembic/** 를 받는 db.md 절차에는 0줄 | `docs/workflow/db.md` |
| 40 | L18 | docs | STATE.md 의 «E2E 554 (`#1291` 기준)» 은 거짓 출처 표지다 — #1291 시점 E2E 는 122 였고, 현재 상태 문서에 남은 유일한 PR 번호인데 가드 정규식이 그 리터럴을 강제해 지울 수도 없다 | `docs/STATE.md` |
| 41 | L14 | docs | 회고 리포트의 «확정 N» 이 같은 관점 안 중복까지 센다 — 2라운드부터 finder 는 «이전 라운드 항목 제외» 지시만 받고 그 목록은 받지 못하며, 중복 키는 제목 완전일치다 | `.claude/workflows/retrospective.mjs` |
| 42 | L18 | docs | CLAUDE.md 의 make 줄이 자수 절약 압축 두 번(#1775·#1805)을 거쳐 «일반 사실» 에서 «이 PC 엔 make 이 없다» 는 기기 한정 주장으로 바뀌었다 — Codespaces·CI·클라우드 세션에서는 거짓 | `CLAUDE.md` |
| 43 | L18 | docs | new-machine-setup 런북의 첫 줄이 README 에 없는 절(#quick-start)을 가리킨다 — 10주 넘게 죽어 있고, 문서→문서 링크·앵커를 재는 가드는 리포에 없다 | `docs/runbooks/new-machine-setup.md` |
| 44 | L07 | decision | 운영 DB 백업에 관한 결정을 «PII 처리» 질문으로만 올렸고, 그 위험 수락은 개인 메모리에만 있다 (심각도 조정) | `docs/workflow/db.md` |
| 45 | L07 | decision | 사용자의 선택(A/B안)과 운영 설정 변경 승인이 PR 마다 기록되기도 하고 빠지기도 한다 — CLAUDE.md:54 가 요구한 API 변경 사전 확인(#1774)은 GitHub 에서 검증할 수 없다 | `CLAUDE.md` |
| 46 | L07 | decision | «진행하고 보고» 범주의 문서 한 줄을 승인 질문으로 올렸다가 두 번 무응답을 «안 넣음» 으로 읽었다 — 운영 마이그레이션 잠금 함정이 db.md 에 없다 | `docs/workflow/db.md` |
| 47 | L11 | tooling | Two hooks go blind on worktree edits: doc_review_gate skips with no review, ledger row or banner, and the pytest smoke hook prints ✅ after testing the main checkout (심각도 조정) | `.claude/hooks/doc_review_gate.py` |
| 48 | L08 | tooling | 8 of the 10 CI jobs have no time wall: on 11-05 an apt stall held the pytest job for 5h35m, and #1766 had fixed the same failure class only in the E2E job (심각도 조정) | `.github/workflows/ci.yml` |
| 49 | L08 | tooling | The basis for #1766's 45-minute E2E wall was used up in two weeks: max suite 26.7 min plus the 18.1-minute stall #1766 measured is 44.8 min, a 0.2-minute margin | `.github/workflows/ci.yml` |
| 50 | L14 | tooling | retro_scope never checks that the report's 'analysis end head' is on main, so this range re-counts #1684, which the previous retro already covered, and the same main can yield a different range per clone | `scripts/retro_scope.py` |
| 51 | L12 | tooling | The witness-set predicate guard pools corpus values from every changed test file, so an existing corpus passes a new, unrelated predicate; #1812 noted this itself, yet the ledger closed K19 | `scripts/check_witness_set_predicates.py` |
| 52 | L12 | tooling | The B8 fail-open floor now covers tests/·e2e/, but it judges per file, so all 206 file-reading tests pass, including 116 files holding 814 bare `'literal' in text` assertions | `scripts/check_guard_fail_open.py` |
| 53 | L12 | tooling | The reverse-mutation gate cannot see e2e observers by design: in an e2e-dominated window it gave 3 false reds, and the exemption text reads 'outside this gate' | `scripts/check_reverse_mutation.py` |
| 54 | L09 | tooling | Required pip-audit pushes upstream advisories onto unrelated PRs and main deploys: 3 advisories in the window → 6 unrelated PR reds, 1 main red, 3 exception PRs and no upgrades | `.github/workflows/ci.yml` |
| 55 | L11 | tooling | The doc_review_gate ledger cannot answer the ROI question: of 29 reviews (87 calls) in the window, consistency declared itself 'unable to verify' 15 times (52%), the 6 blocks left only hashed reasons, and `src` has been None for 84 days | `.claude/hooks/doc_review_gate.py` |
| 56 | L19 | tooling | The procedure for reproducing CI fonts exists only in personal memory: #1811, reported green on Windows, failed on CI (English 360px table 14px too wide) | `docs/workflow/verify.md` |
| 57 | L16 | process | [WBS] 진입점 계약이 뒤집혀 있다 — #1639 본문 «다음 시작점» 은 09-10 에 끝난 W3·W10 을, 마지막 «🔖 핸드오프» 는 09-14 를 가리키고, #1746 의 마지막 핸드오프(11-03)는 이미 닫힌 K14 를 가리킨다. 지금 순서는 개인 메모리 한 줄에만 있다 | `CLAUDE.md` |
| 58 | L10 | process | «한국어 응답» 이 항상 로드되는 규칙 어디에도 없어 11-04~05 에 영어 단독 메시지가 29%(74/254)로 번졌고, 사용자가 같은 요청을 두 번째로 했다(05-11 → 11-05) | (메모리) MEMORY.md |
| 59 | L09 | process | pip-audit 예외 5건의 «즉시 삭제» 조건 중 절반은 우리 코드의 변화인데 그것을 재는 시험이 0 — 앱이 OpenTelemetry 서버 계측이나 MCP 클라이언트·HTTP 서버를 켜도 예외는 남고 감사는 초록이다 | `.github/workflows/ci.yml` |
| 60 | L04 | code | #1754 오류 화면의 «개요로 가기» 를 로그인 안 한 방문자가 누르면, hx-boost 가 독립 head 를 가진 랜딩의 body 만 끼워 넣어 랜딩이 자기 CSS 없이 그려진다(실측). 앱 안 boost 링크가 4xx 를 받으면 진행 막대가 끝없이 돈다 | `src/templates/error.html` |
| 61 | L04 | code | 분석 이력 페이지 버튼을 키보드로 누르면 포커스가 <body> 로 떨어진다 — #1776 의 «이력 표 키보드 조작» 이 정렬과 행 링크만 다뤘다(실측) | `src/templates/repo_detail.html` |
| 62 | L04 | code | 대시보드 KPI 카운트업(base.html countUp)은 «동작 줄이기» 를 보지 않는다. #1779 의 계기(getAnimations)는 rAF·canvas 움직임을 원리적으로 못 봐서 /dashboard 가 초록이다(실측: reduce 에서 약 1.4초 동안 값 22개) | `src/templates/base.html` |
| 63 | L04 | code | 카운트업 끝값이 정수 1000 이상에서 서버 글자와 달라진다. toLocaleString() 이 브라우저 기본 로케일로 묶어 1234 가 «1,234»(de 계열은 «1.234»)가 되는데, #1754·#1768 의 «끝값 = 서버 글자» e2e 는 시드 최대값이 27 이라 이 분기를 못 연다 | `src/static/js/effects.js` |
| 64 | L18 | docs | STATE.md 종합 수치의 «E2E N (`#1291` 기준)» 은 거짓 출처인데 시험 정규식이 그 PR 번호를 강제한다 — 이 창에서 숫자만 26번 바뀌었다 | `docs/STATE.md` |
| 65 | L18 | docs | ci.yml e2e 잡 주석의 `e2e/conftest.py` 줄번호 좌표(135-159행)를 #1712 가 무효화 — 앵커 가드는 .md 만 읽어 워크플로 주석의 줄번호는 계속 썩는다 | `.github/workflows/ci.yml` |
| 66 | L18 | docs | new-machine-setup.md 의 README 링크 `#quick-start` 는 #1480(08-24) 이후 죽은 앵커 — 문서 가드 어디에도 마크다운 상대 링크·제목 앵커 검사가 없다 | `docs/runbooks/new-machine-setup.md` |
| 67 | L18 | docs | CLAUDE.md «최초 설정»·CONTRIBUTING 설정 절차가 SESSION_SECRET 을 빠뜨려, 그대로 따르면 import 시점에 기동이 막힌다 — README 는 필수라고 적는다 | `CLAUDE.md` |
| 68 | L18 | docs | README §Deploying(Railway) 이 이 창의 배포 개편(#1722·#1723·#1726)을 반영하지 않았다 — railway.toml 이 주던 pre-deploy·healthcheck 는 이제 대시보드 수동 설정인데 언급이 없고, 필수 TELEGRAM_* 도 빠져 있다 | `README.md` |
| 69 | L19 | docs | deploy.md·db.md 의 «이전 배포 재배포» 복구 절차가 이 창의 DB 이전(#1719) 제약을 모른다 — 전환 이전 배포는 기동하지 못한다는 사실이 사설 메모리에만 있다 | `docs/workflow/deploy.md` |
| 70 | L14 | docs | 회고 SKILL.md 의 «직후 정책 9 자유 발언 4 섹션» 은 리포 어디에도 정의가 없다 — 번호 정책 본문은 #1427 에서 지워졌고 번호 인용만 95파일 191곳 남았다 | `.claude/skills/retrospective/SKILL.md` |
| 71 | L18 | docs | 운영 DB 는 PG 17.6 인데 PG 판정 CI 잡·그 근거 주석·verify.md 는 16.4 를 기준으로 삼고 «최신 16.x 로 bump» 를 권한다 — 운영 major 를 적은 리포 문서가 없다 | `.github/workflows/ci.yml` |
| 72 | L07 | decision | 운영 데이터의 영구 상태를 정한 사용자 결정 2건(장애 구간 미재전송 · 운영 DB 백업 정책)이 비공개 메모리의 «다시 권하지 않는다» 로만 남았다 — 열린 원장 K08 과 같은 부류가 더 큰 판으로 재발 (심각도 조정) | `CLAUDE.md` |
| 73 | L07 | decision | 두 번 답이 없던 «db.md 잠금 규칙 한 줄» 제안을 에이전트가 «안 넣음» 으로 닫았다 — 사용자 전역 규칙(새 함정 → 항상 읽히는 곳에 한 줄)과 반대 방향의 기본값이고, 9일 뒤 #1775 는 같은 총량 규칙 아래에서 한 줄을 넣었다 | `docs/workflow/db.md` |
| 74 | L07 | decision | «09-16 회고 140건은 권장안대로» 라는 지시가 가리킨 권장안은 없었다 — 에이전트가 계획을 만들어 #1744 머지까지 마친 뒤에야 알렸고, 기록(#1706 진행 11 · 메모리)은 지금도 «권장안대로» 라서 결정의 출처가 거꾸로 남아 있다 | `.claude/skills/retrospective/SKILL.md` |
| 75 | L13 | tooling | 로컬 pre-push 게이트가 아무것도 재지 못하는 두 가드에 OK 를 찍는다 — 창 안 비봇 PR 빨강 18회 중 8회가 바로 그 두 스텝 (심각도 조정) | `scripts/pre_push_gate.py` |
| 76 | L10 | tooling | 메모리 슬러그 pre-commit 가드가 워크트리 커밋마다 거짓 «slug drift» 로 막는다 — 3 세션이 같은 함정을 기록했지만 코드는 그대로 | `scripts/check_memory_refs.py` |
| 77 | L09 | tooling | semgrep 이 앱과 같은 파이썬 환경에 깔려 있어, 그 전이 «정확 핀» 이 required pip-audit·Dependabot·fastapi 판올림을 좌우한다 | `requirements.txt` |
| 78 | L14 | tooling | 회고 범위 계기가 리포트에 적힌 head 를 «해석되기만 하면» 믿는다 — 로컬 reflog 에만 남은 squash 된 브랜치 끝에서 세어 #1684 를 두 회고에 넣고도 unmeasured: [] 를 낸다 | `scripts/retro_scope.py` |
| 79 | L14 | tooling | 회고 워크플로의 중복 제거 키가 «관점 + 정확한 제목» 이라 관점만 달라도 같은 결함이 따로 확정된다 — 09-16 «확정 140» 은 원인 22묶음이었다 | `.claude/workflows/retrospective.mjs` |
| 80 | L11 | tooling | Grok 위임 ROI 를 재는 계기가 없다 — 10-18 «300 s 넘으면 쪼갠다» 규칙 뒤 첫 시도 시간 초과율이 23% → 36% 로 올랐고, 공유 구독 소진(11-04)이 필수 게이트 경로를 막았다 | (메모리) feedback-grok-collaboration-default.md |
| 81 | L20 | tooling | 커밋된 «정확 일치» 테스트 수치 때문에 비봇 PR 73%(61/83)가 같은 줄을 고친다 — strict=false 와 겹쳐 직렬 머지·재계산이 상시 비용이 됐다 | `scripts/check_e2e_scope.py` |
| 82 | L08 | tooling | #1766 이 E2E 벽을 45분으로 올린 근거(23:23 + 정체 18:04 = 41:27)가 15일 만에 소진됐다 — 정체는 드문 원인이고 스위트 증가가 상시 원인이다 | `.github/workflows/ci.yml` |
| 83 | L11 | tooling | 편집 훅의 고정 비용이 신호보다 크다 — 문서 심의는 skip 파일에도 anthropic 을 import 하고(편집마다 ~2~3 s), 스모크는 가드 스크립트 12개에서 시험 이름 규칙이 어긋나 75 s 타임아웃만 낸다 | `.claude/hooks/doc_review_gate.py` |
| 84 | L08 | ci-budget | 정체 항은 «관측 최대» 일 뿐 상한이 없다. #1766 뒤에도 설치 단계 정체가 4번 있었고(2번은 11분대), 옛 벽이었다면 PR 2건이 취소됐다 | `.github/workflows/ci.yml` |
| 85 | L16 | ci-budget | 원장 #1746 K20 의 재확인 값이 10-12 생성 때 그대로 15판을 지났다. #1766 이 고친 2건은 표시되지 않았고, 남은 위험은 작게 적혀 있다 | — |
| 86 | L09 | security | pip-audit 예외 5건의 «도달 불가» 전제를 지키는 회귀 가드가 0 — 재검토 조건 (2) «즉시 삭제» 를 알릴 계기가 없다 (심각도 조정) | `.github/workflows/ci.yml` |
| 87 | L05 | security | 분류·사용자 결정을 쓰는 writer 가 0 — «처리됨 · 사용자 confirm 완료» 카드와 AI 분류 4칸은 운영에서 늘 0 인데 화면·docstring 이 남았다(#1810 은 약속 한 줄만 지웠다) | `src/repositories/security_alert_log_repo.py` |
| 88 | L14 | security | 회고 5관점과 integrity-audit 보안 렌즈 어느 쪽도 공급망 예외와 보안 기능 서비스를 보지 않는다 (심각도 조정) | `.claude/workflows/integrity-audit.mjs` |
| 89 | L09 | security | 감사 예외의 같은 사실이 네 곳에 복사돼 있고 셋이 낡았다(«최신 1.182.1» · ID 2/5) | `.github/workflows/ci.yml` |
| 90 | L10 | docs/memory | 메모리 처방 표면에는 CLAUDE.md:58 «줄번호가 아니라 앵커» 를 집행하는 곳이 없다. 진입점 절의 줄번호 좌표 6개 중 3개가 썩었는데 «✅ 처방적 좌표 전건 유효» 가 나온다 | `scripts/check_memory_refs.py` |
| 91 | L10 | docs/memory | K18 을 «해소» 로 닫을 때 규칙↔집행자 축을 재지 않았다. P2-3·P2-75 의 SHA drift 부류가 열려 있고, P2-76 의 실패가 CLAUDE.md 층에서 되풀이된다 | `tests/unit/hooks/test_check_memory_after_write.py` |
| 92 | L10 | docs/memory | 역방향 축의 맨 파일 이름 판정은 `:줄` 꼬리 하나로 통째로 꺼진다. 계약은 «`path:줄` 은 경로만 본다» 인데, 실제로는 경로조차 보지 않는다 | `scripts/check_memory_refs.py` |
| 93 | L18 | docs/memory | CLAUDE.md:58 의 «(`scripts/check_doc_anchors.py` 가 강제)» 는 백틱 밖 줄번호 좌표를 보지 못한다(원장 P2-8 미해소). 살아 있는 설계 문서 docs/architecture.md:53 에 2건이 있다 | `scripts/check_doc_anchors.py` |
| 94 | L10 | docs/memory | 같은 앵커 규약을 두 집행자가 서로 다른 술어로 잰다. CLAUDE.md:58 의 문구(«실재»)를 따른 메모리 축은 check_doc_anchors 가 «거짓 집행자» 라 부른 «있기만 하면 통과» 판정이다 | `scripts/check_memory_refs.py` |
| 95 | L16 | decision | #1766 이 해소를 스스로 적은 K20 P2-61(+P1-16·P2-46 의 근거 주석 부분)이 원장에 반영되지 않았다. «해소 87 · 남음 49» 와 K20 증거 3줄이 지금 거짓이다 (심각도 조정) | `.github/workflows/ci.yml` |
| 96 | L16 | tooling | 커밋·PR 본문의 «#원장 P#-##» 참조를 원장 체크 상태와 대조하는 단계·도구가 없다. 기계로 대조했다면 커밋 본문 기준 오탐 0으로 P2-61 하나만 떴다 (심각도 조정) | `.claude/skills/retrospective/SKILL.md` |
| 97 | L15 | process | K06 악화: 회고 창이 55 → 109 PR 로 늘었다(임계 15 의 3.7배 → 7.3배). 착수 신호를 띄우는 곳은 여전히 0이고, 원장 안의 유일한 운반체(«다음 회고» 절)는 45건에서 멈춰 있다 (심각도 조정) | `CLAUDE.md` |
| 98 | L16 | docs | 원장이 추출 가능한 값을 복사해 둔다. «다음 회고» 의 «45건(#1684~#1743)» 은 15판 내내 바뀌지 않았고(기계 산출 109), 손으로 고치는 머리 «해소/남음» 은 11-05~06 세 판 동안 체크 상태와 어긋났다 | `scripts/retro_scope.py` |
| 99 | L10 | tooling | CLAUDE.md 는 «메모리 진입점에 수치·SHA 를 적지 않는다» 의 집행자로 check_memory_refs.py 를 가리킨다. 하지만 그 가드는 원장 수치를 판정하지 않아, MEMORY.md:19 의 낡은 #1746 수치와 «다음 = K15» 위에서 ✅ 를 인쇄한다 | `scripts/check_memory_refs.py` |
| 100 | L16 | process | K20 영역의 새 발견(10개 잡 중 시간 제한이 2개뿐 · PR CI pytest 잡 5시간 35분 끝 취소)이 개인 메모리에만 «K20 후보» 로 남아 있고 #1746 에는 없다 | `.github/workflows/ci.yml` |
| 101 | L16 | decision | #1706 의 사건 트리거 «#1701 착수 때 함께» 는 #1720(09-28) 머지로 지나갔는데, 항목은 미체크에 문구도 그대로다. 트리거를 «인사이트 트래픽» 으로 바꾼 결정은 기록이 없다 | — |
| 102 | L16 | docs | 미해결 50건(보류 포함) 중 26건은 원장 생성(10-12) 뒤 인용 파일이 바뀌었는데, 재확인 스탬프는 전부 10-12 그대로다. P2-61 은 그중 실제로 거짓이 된 경우다 | `docs/workflow/ui-i18n.md` |
| 103 | L03 | ci/verify | 분석기 bump 에 출력 오라클이 없다. 이 창의 분석기 go-live 9회가 점수 영향 증거 0인 채 «CI 초록» 만으로 운영에 들어갔다 (심각도 조정) | `tests/integration/test_static_analyzer.py` |
| 104 | L03 | data/provenance | 분석 행에 분석기 버전과 룰셋 출처가 없어서, 요청된 검증 양식(운영 분포를 배포일 전후로 대조)은 원리적으로 답을 낼 힘이 없다 | `src/worker/pipeline.py` |
| 105 | L03 | deploy/provisioning | 운영 eslint 분석기는 핀 없는 전역 `eslint@9`(실측 9.39.5)다. package.json 의 eslint bump(10.10→10.13)는 운영 분석에 닿지 않고, Dockerfile 의 «전부 버전 핀» 주석은 사실이 아니다 | `Dockerfile` |
| 106 | L03 | measurement | 측정 결과: 이 창의 pylint·flake8·semgrep 엔진 bump 는 고정 코퍼스에서 출력을 바꾸지 않았다. 운영 점수·게이트 분포의 변화는 워크로드(JS/TS)가 설명한다 | — |
| 107 | L21 | code (UX 측정 계기 보정) | «CI 글꼴이 가장 넓다» 가 폰 글꼴로 재지 않은 채 주석·시험·WBS 에 사실로 남았다. 이번 회고의 첫 실측: 안드로이드 꼴에서는 성립, iOS 는 아직 안 쟀다 | `src/templates/repo_detail.html` |
| 108 | L21 | code (UX 측정 계기 보정) | «Windows 글꼴(Segoe UI · 맑은 고딕)» 대조군은 실제로는 맑은 고딕 하나였다. 어떤 글꼴인지 렌더러에서 읽지 않고 CSS 스택에서 짐작했다 | `src/templates/repo_detail.html` |
| 109 | L21 | code (UX 측정 계기 보정) | 판정 글꼴(DejaVu Sans)을 CI 가 설치하지도 확인하지도 않는다. 러너 이미지가 더 좁은 글꼴로 바뀌면 폭 시험은 초록인 채 «넓은 글꼴로 쟀다» 가 조용히 거짓이 된다 | `.github/workflows/ci.yml` |
| 110 | L21 | docs-process | 세션이 뽑은 규칙이 «화면 폭은 CI 글꼴로 잰다» 로 굳었다. 폰 단서는 빠졌고, 화면 영역 문서에는 글꼴 축이 아예 없다 | `docs/workflow/ui-i18n.md` |
| 111 | L18 | process | 다중 커밋 squash 의 제목(= git 정본 이력의 제목)을 보완 커밋 뒤 아무도 다시 대조하지 않는다 — #1811 main 제목이 최종 diff 와 모순되고, 같은 부류(09-07 P2-15)가 처방 없이 재발했다 | `docs/workflow/verify.md` |
| 112 | L14 | tooling | finding 의 domain 은 에이전트가 쓴 자유 문자열 그대로다. 이번 발견 라운드에서만 비정규 domain 13종이 나왔고, gap 결과는 비평가가 지은 이름을 물려받는다. 그래서 :371 의 seen 필터가 검증 항목을 원리적으로 못 거른다 | `.claude/workflows/retrospective.mjs` |
| 113 | L14 | tooling | loop-until-dry 동기화 가드는 「(1) dedup」 불변식을 `seen.has(key(` 글자가 있는지로만 본다. 정본 템플릿엔 key 정의가 없고 두 소비자의 키는 이미 갈렸다. 이번 실행에서 키가 합친 것은 121건 중 0건인데 가드는 초록이다 | `tests/unit/scripts/test_workflow_loop_sync.py` |

## 오탐 (다음 회고가 다시 판정하지 않도록)

| 관점 | 제목 | 기각 사유 |
|---|---|---|
| process/knowledge-locality | «문서 총량 불변» 규칙 때문에 함정과 운영 절차가 개인 메모리로 밀려난다. 배포 확인, 머지 프로토콜, 잠금 함정의 정본이 리포 밖에 있다 | 인용은 전부 실재하고 문구도 일치한다. CLAUDE.md:73·:19, 전역 ~/.claude/CLAUDE.md §3(30행)·§4(39행), 메모리 overview-unverified-card:22 · railway-deploy-verify:11 · retro-2026-09-16:71 · k15:56 · no-session-set:16-17, docs/runbooks/railway.md:9… |
| ci-budget | 벽에 걸려 취소된 경로는 문서화된 배포 진단으로 보이지 않는다. b53c1755 는 SKIPPED 기록조차 없다 | 인용은 실재한다. deploy.md:3 은 «실패 체크 스위트가 하나라도 있으면 … SKIPPED 다», :37 은 «railway deployment list --json 으로 상태부터(SKIPPED 면 meta.skippedReason)» 라고 적는다. 원자료도 맞다. `railway deployment list --json --limit 400`(08-07~11-06) 에 b53c175… |
| security | #1778 의 MCP «클라이언트» 전제는 semgrep sdist 만 뒤졌다 — 설치본의 anthropic 이 MCP 클라이언트 헬퍼를 싣고 있다 | 인용과 사실 부분은 모두 맞다. 그러나 결함이라는 주장은 성립하지 않는다. [인용 재확인 — 실재] - ci.yml:399-401 «116685 · 116686 … MCP «클라이언트» … semgrep 1.181.0 소스에 그 API 가 0건이고, 앱은 `mcp` 패키지를 import 하지 않는다» 와 417-418 «(absent from semgrep and from the app)» … |

## 묶음 — 원장은 `[WBS]` #1824

확정 162건을 원인 21묶음으로 나눴다. 같은 결함을 여러 관점이 따로 확정한 경우가 많다
(예: L10 의 «메모리 진입점 SHA 규칙 ↔ 집행자» 는 6관점 · 15건이 한 뿌리다).

| 묶음 | P0 · P1 · P2 | 주제 |
|---|---|---|
| L01 | 2 · 0 · 0 | 운영 비밀값 덤프 경로 — 문서 처방 · 훅 공백 |
| L02 | 5 · 7 · 1 | 운영 측정 사고(25시간 장애)의 재발 방지 — 위임 축 · 기계 집행면 · 사고 기록 |
| L03 | 0 · 2 · 4 | 분석기 정확성·출처 — 실패 모양 · 룰셋 버전 · 핀 · 출력 오라클 |
| L04 | 0 · 2 · 4 | 화면 결함 — 토스트 · forced-colors · 오류 화면 · 포커스 · 카운트업 |
| L05 | 0 · 1 · 1 | 보안 알림 상태 — 닫힘 반영 · 분류 writer |
| L06 | 0 · 4 · 2 | 머지 승인 · 시각 확인 규약 |
| L07 | 0 · 1 · 6 | 결정 · 위험 수락의 기록면 |
| L08 | 0 · 5 · 5 | CI 시간 벽 · 관측자 (#1746 K20 악화) |
| L09 | 0 · 3 · 5 | 공급망 — semgrep 정확 핀 · pip-audit 예외 |
| L10 | 0 · 6 · 10 | 메모리 규칙 ↔ 집행자 · 로드 상한 |
| L11 | 0 · 2 · 6 | 훅 · 위임 도구의 계기 — 워크트리 · 비용 · 전달 · ROI |
| L12 | 0 · 0 · 5 | 시험 게이트의 사각 — e2e 역-뮤테이션 · B8 · 증거집합 코퍼스 · 달 경계 |
| L13 | 0 · 1 · 3 | 로컬 게이트 · main red 관측 · 본문 red 복구 (#1746 K22 악화) |
| L14 | 0 · 5 · 9 | 회고 계기 — 중복 제거 · 범위 기점 · 기록 보존 · 비평가 입력 |
| L15 | 0 · 1 · 2 | 회고 착수 신호 (#1746 K06 악화) |
| L16 | 0 · 1 · 10 | 원장 위생 — 우선순위 · 상태 · 복사된 값 · 진입점 |
| L17 | 0 · 0 · 8 | 서버 루프 · 유료 호출 방어 · 소실 창 |
| L18 | 0 · 1 · 21 | 문서 사실 오류 — README · CONTRIBUTING · STATE · 링크 · 좌표 · 총량 |
| L19 | 0 · 0 · 4 | 함정 · 절차가 리포 밖(메모리)에만 |
| L20 | 0 · 0 · 3 | 테스트 수 사본 줄의 직렬화 |
| L21 | 0 · 0 · 4 | 폭 시험의 글꼴 계기 |

## 다음 회고를 위한 경계

- 다음 범위의 하한은 **이 리포트를 추가한 커밋** 이다.
- 🔴 회고 에이전트는 운영(`railway` CLI · 운영 DB · MCP `execute_sql`)에 닿지 않는다 — 디스패치 브리프에
  금지를 적고, 훅이 막는 것만 믿지 않는다. 측정이 필요하면 사람 승인 뒤 오케스트레이터가 한다.
- 🔴 실행 시간 예상은 이번 실측(10h42m · 191 에이전트)에서 출발한다.
- 🔴 창이 대화 기록 보존 기간(30일)을 넘기 전에 착수한다 — 넘긴 구간은 원본 대조가 안 된다.
- 🔴 **이 리포트를 추가하면 단위 테스트가 2건 는다** — `tests/unit/scripts/test_gate_claim_consistency.py`
  가 문서마다 파라미터화한다. 리포트 PR 의 `docs/STATE.md` 와 본문 수치는 그 2건을 **포함한** 값이다.
