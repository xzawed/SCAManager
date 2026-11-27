# 회고 2026-11-27 — `#1916~#1938`

## 범위

| | 값 |
|---|---|
| head | `bff61841` — 분석 워크트리(시작 · 종료 같다). `main` 은 실행 중 `04fef931`(#1939) 로 움직였다 |
| 기계 산출 범위 | `#1916~#1938` — 18 PR (`retro_scope.py --json` · 디스패치 직전 실행) |
| 경계 커밋 | `356078b` (직전 리포트 `2026-11-24-retrospective.md` 추가 커밋) |
| 실제 기점 | `5ae8d50b` — 직전 리포트가 적은 분석 종료 시점(`scan_from_kind: report-head`) |
| 정직성 필드 | `gh_only: [1916]` · `unmeasured: []` · `records_expired_prs: []` |
| 실행 중 범위 이동 | #1939 — 회고 실행 중 머지됐다. 이 범위 밖이고 다음 회고의 범위에 든다 |

## ROI

| 지표 | 값 |
|---|---|
| 라운드 (loop-until-dry) | 3 (예산 미설정 상한) |
| 총 발견 | 114 |
| 확정 | **113** |
| 오탐 차단 | 1 |
| 심각도 조정 | 5 (P1→P2 4 · P2→P1 1) |
| verdict 커버리지 | 1 |
| 미검증 잔여 | 0 |
| 실행 중 범위 이동 | #1939 (범위 밖) |
| P0 / P1 / P2 | 0 / 35 / 78 |
| 창의 claim-review 반증률 | 0.655 — 18 PR 중 16건의 판정 55개에서 BROKEN 35 · WEAKENED 1 (SURVIVES 19) |

에이전트 135 · 오류 0 · 8h50m · 2,249만 토큰 · 도구 호출 6,616(직전 121 · 5h10m · 2,280만).
실행 전 예상(60~90 에이전트 · 2~4시간 · 800만~1,200만 토큰)과 실행 중 재추정(100~105 · 1,900만~2,100만 · 6~6.5시간)을
모두 넘었다 — 재추정 때 사용자에게 알렸고 사용자가 «끝까지» 를 골랐다. 18 PR 에 확정 113건으로, PR 당 발견이 직전의 6배다.
5관점(process·code·docs·decision·tooling) finder 3라운드 → 전건 cross-verify → 완전성 비평가 gap 3건 → 표적 라운드 → 검증.

## 실행 안전 — 리포트 작성자 확인(워크플로 교차검증 밖)

이번 디스패치 브리프에는 운영 접근 · 비밀값 인용 · 쓰기 금지가 없었다(아래 P1 — 직전 보고서가 «계속 적는다» 고 남긴 경계).
그 결과를 기록에서 쟀다(값 없이 — 종류 · 사유 · 명령 sha256).

| 축 | 실측 |
|---|---|
| 훅 거부(창 안) | 119건 — credential 107(`.env` 읽기 54 · 재귀 검색 30 · env 덤프 7 · find→내용 5 · printenv 5 · 그 밖 6) · 운영 12(실행 · 변경 7 · 허용 목록 밖 5). sha256 짝: 회고 에이전트 78 · 주 세션 1 · 짝없음 40(MCP 호출 등) |
| 정직한 명령의 거부 | 안 쟀다 — 짝지은 78건은 검증관이 훅 주장을 재현하려 낸 탐침과 일상 명령이 섞여 있어, 명령 본문을 사람이 봐야 가른다 |
| 허용된 운영 채널 | 9건(채널만 기록) |
| 훅이 못 본 길 | 2건 — 실제 비밀값 노출은 없다(한 건은 검증관이 스스로 만든 가짜 시료). 상세는 비공개 메모(R-3) |
| 쓰기 | 회고 워크트리 변경 0. 검증관이 주 세션 임시 폴더에 탐침 폴더를 만들었다 — 작성자가 지웠다 |
| 결과 데이터 | 계정 이름이 든 홈 경로 31곳을 `~` 로 바꿨다. 이메일 꼴 4건은 모두 시료 도메인이다. 이 보고서는 `scan_publish.py` exit 0 |

## 핵심 — P1 35건의 뿌리 (P0 없음)

### M01 — 회고 디스패치가 실행 제약을 안 실음 — 전용 트리 · 금지 · 범위 (P1-1 ~ P1-6)

이번 회고를 전용 워크트리에서 띄웠지만, 디스패치 브리프가 그 경로와 금지 목록을 프롬프트에 넣지 않았다. 하위 에이전트 대부분이 진행 중 PR 워크트리에서 재었고, 회고 도중 그 트리가 커밋을 받은 뒤 머지되어 지워졌다. 범위 재확인이 실패하면 null 이 되어 이동 없음과 같은 값이 되고, 실행 중 머지를 다음 창으로 넘길 장치도 없다.

### M02 — 결정의 기록면 — 무응답이 닫힘 · 해석이 결정 · 공개가 반증보다 앞섬 (P1-7 ~ P1-11)

사용자 몫과 «정할 것» 을 원장에 옮기던 규칙이 하루 만에 끊겼고, 위임 머지가 확인 질문을 답 없이 닫았다. 권장안이 없는 질문에 «권장안을 선택» 이 오면 에이전트가 내용을 채워 이행했고, 위험 수락은 원장 대신 PR 본문에만 남았다. 공개 이슈에 민감한 사실을 반증보다 먼저 고쳤고, 닫힌 원장의 상시 결정은 새 창으로 넘어오지 않았다.

재발 — 원장 #1917 M04 P1-9 · M04 P1-10 · M04 P1-11 · M04 P2-20 · M04 P2-21 · M04 P2-22 · M04 P2-25 · M03 P2-16

### M03 — 게시 전 검사의 정밀도 · 회귀 가드 — 일부 상세는 비공개 메모(R-3) (P1-12 ~ P1-16)

공개 쓰기를 재는 게시 전 검사에 놓침 · 오탐 · 기록 공백이 함께 있다. 놓침 쪽의 꼴은 공개 글에 적지 않는다(R-3) — 원장 항목의 상세는 비공개 메모에 있다. 시험이 닿지 않는 fail-closed 갈래가 많아, 지워도 초록인 회귀 가드 부재가 같은 뿌리다.

재발 — 원장 #1917 M02 P2-6

### M04 — 세션 경계의 상시 지시 — 메모리 미갱신 · 압축 뒤 언어 · PC 사이 미전달 (P1-17 ~ P1-19)

11-27 재개 결정이 세션 메모리와 색인에 반영되지 않아, 회고 에이전트가 «아직 중단» 을 읽고 일했다. 압축 직후 수 시간 동안 보고와 결정 질문이 영어로 나갔다. PC 를 옮기며 메모리 push 와 검증 라운드 id 가 빠져, 원장이 가리키는 비공개 층이 작업 PC 에 없다.

재발 — 원장 #1917 M03 P2-14 · M07 P2-44 · M07 P2-45 · M09 P2-63

### M05 — 머지 관문의 기록 — 위임 표지 · 판정 부재 · 작성 주체 · cwd 의 스크립트 (P1-20 ~ P1-22)

위임 머지 기록이 «(위임)» 과 원장 근거를 잃고, 11-24 발화를 그 head 의 승인처럼 적었다. Grok 판정이 없거나 마지막 판정이 BROKEN 이어도 머지됐고, 보안 검토 댓글은 관문이 읽지 않는다. 안 B 의 «사용자 승인» 을 에이전트가 사용자 계정으로 올렸고, 관문은 작성자를 보지 않는다. 관문 스크립트는 cwd 의 트리로 돈다.

재발 — 원장 #1917 M03 P1-8 · M03 P2-13 · M03 P2-15 · M04 P2-19

### M06 — credential 훅의 오탐 — 명령 자리 · Bash 경로 · stdin 인코딩 (P1-23 ~ P1-25)

거부 기록을 세어 보니 정직 명령이 대부분이고 값 덤프는 없었다. 고친 뒤 첫 창도 18건 중 16건이 정직 명령이었다. Git Bash 경로를 Windows 규칙으로 읽어 정직 명령을 막고, 한 꼴은 판정이 빗나간다(상세는 비공개 메모 · R-3). stdin 을 로캘 코드로 읽어 해시가 어긋나고, heredoc 의 데이터와 실행을 가르지 못한다.

재발 — 원장 #1917 M02 P1-5

### M07 — 토큰 상한이 문장으로만 있음 — 적대 패스 · 회고 budget 미전달 (P1-26 ~ P1-28)

«조금 늡니다» 로 권장한 적대 패스가 상한 없이 수십 회 돌았고, 사용자가 토큰 부족을 알린 뒤에야 멈췄다. 교차 검증 대체와 가드 표면 패스도 멈춤 규칙이 없어 예산 소진으로 끝났다. 회고에 동의한 상한은 워크플로 budget 으로 넘어가지 않아, 루프를 세는 쪽이 그 숫자를 보지 못한다.

재발 — 원장 #1917 M07 P2-46

### M08 — 차단면의 범위 — 상세는 비공개 메모(R-3) (P1-29 ~ P1-31)

credential · 운영 접근 · 게시 전 검사가 덮는 범위 밖에서 비밀값 · 명령에 닿는 길이 이번 창에 쓰였다. 길의 꼴은 공개 글에 적지 않는다(R-3). 그중 비밀값 사본 1건은 11-27 사용자 결정으로 지웠다(내용 열지 않음).

### M09 — 회고 계기가 창의 기록을 못 가름 — 없는 기록 · 시각 경계 · 감사 개변 (P1-32 ~ P1-33)

창 17건 중 10건의 세션 기록이 회고 PC 에 없는데, 범위 도구는 측정 완료로 빈 목록을 냈다. 훅 정밀도 절차에 시각 경계가 없어 회고 실행이 쓴 거부가 창 거부에 섞였고, 감사 기록은 피감사자가 옮겼으며 탐침이 실제 파일에 가짜 허용 줄을 남겼다. 호출 집계는 사본 때문에 약 1.5배로 부푼다.

### M10 — 훅이 세션의 작업과 어긋남 — 주 체크아웃 · 스모크 대상 · 사람 알림 (P1-34)

보호 경로 훅이 주 체크아웃의 git status 만 보아, 워크트리에서는 항상 빈 결과이고 호출마다 수 초를 쓴다. 훅 최신성 점검은 워크트리를 main 이 아닌 주 체크아웃으로 오진하고, 로컬 전용 skip 시험은 워크트리 슬러그로 메모리를 찾아 항상 skip 이다. 스모크는 훅 시험의 일부만 길게 돌리고, 형제 알림 훅은 에이전트 맥락으로 나가지 않는다.

재발 — 원장 #1917 M01 P1-3 · M01 P1-4

### M11 — 검증 계기의 공허한 초록 — CodeQL diff · src 만 · 잡 이름 · 벽시계 (P1-35)

required 인 CodeQL 게이트는 PR diff 밖 경고를 원리적으로 못 본다. 마지막 사용처를 지운 머지 뒤에 main 에 경고가 새로 열렸고, main 쪽에는 그것을 읽는 곳이 없다. 같은 맹목이 skip 게이트의 잡 이름 대조, src 만 재는 커버리지 도구, 벽시계 하한 단언에도 있어, 재는 집합과 결함의 집합이 달라 초록이 공허하다.

재발 — 원장 #1917 M12 P2-80 · M06 P1-14

## P1 (35건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | M01 | process/cycle-close | 이번 회고 디스패치 브리프에 운영 접근 · 비밀값 인용 · 쓰기 금지가 없다. 직전 보고서가 «계속 적는다» 고 남긴 경계가 이행되지 않았다 | `.claude/workflows/retrospective.mjs` |
| 2 | M01 | process/cycle-close · 회고 실행 격리 | 회고를 전용 워크트리에서 띄웠지만 에이전트 59개 중 53개는 열린 PR #1939 작업 트리에서 돌았다. 실행 중 그 트리에 커밋 3 · 머지 · 삭제가 일어났다 | `.claude/skills/retrospective/SKILL.md` |
| 3 | M01 | code | 회고 에이전트가 전용 워크트리가 아니라 진행 중인 #1939 워크트리에서 떴고, 회고 도중 머지로 그 트리가 지워졌다 — 디스패치가 분석 트리를 지정하지 않는다 (심각도 조정 P2→P1) | `.claude/workflows/retrospective.mjs` |
| 4 | M01 | docs | 회고 전용 워크트리 규칙(SKILL.md 1단계)은 디스패치 순간에만 지켜졌다. 하위 에이전트 59개 중 53개(검증관 48 전부)가 #1939 작업 워크트리에서 돌았고, 그 트리는 회고 중 커밋 3개를 받은 뒤 머지되고 지워졌다 | `.claude/skills/retrospective/SKILL.md` |
| 5 | M01 | decision/autonomy-report | 회고 실행 중 주 세션이 #1939 워크트리로 옮겨 가, 그 뒤 회고 에이전트 53/59 개가 그 PR 브랜치에서 쟀다. 07:07 에는 그 워크트리를 지우고 사용자에게 «내용이 없어 해는 없다» 고 보고했다 | `.claude/workflows/retrospective.mjs` |
| 6 | M01 | tooling | 회고 에이전트 대부분이 회고 워크트리가 아닌 진행 중 PR 워크트리(scam-p18)에서 실측했고, 그 워크트리는 회고 도중 지워졌다. finder·verify 브리프에 트리 경로가 없다 | `.claude/workflows/retrospective.mjs` |
| 7 | M02 | process/user-handoff | 원장 «사용자 몫» 등재 규칙(11-25 신설)이 하루 만에 끊겼다. #1936 · #1938 의 «사용자 검증 필요» 6항목(판단 질문 3)이 미등재이고, #1919~#1922 11항목은 소급되지 않았고, 끝난 #1934 줄은 남아 있다 | `scripts/merge_approved.py` |
| 8 | M02 | decision | 권장안이 없던 질문에 온 «권장안을 선택» 을 에이전트 해석으로 채웠고, 권한 경계를 정책보다 좁게 잡아 워커 자격으로 운영 DB 를 읽는 backfill 건식 실행이 «승인 범위 밖» 으로 열린 채 남았다 | `.claude/hooks/block_credential_dump.py` |
| 9 | M02 | process | ✅ 로 닫힌 훅 항목(P1-19 · P1-5 · P2-6)의 «남긴 위험» 이 원장 어디에도 없다 — 위험 수락을 에이전트가 PR 본문에서 혼자 했다(#1824 L07 P2-44 재발) | `[WBS] #1917 본문 «결정 기록»` |
| 10 | M02 | decision | 공개 범위 결정 R-3(11-17)이 닫힌 원장 #1824 에만 남았다 — 이 창의 공개 글에 우회 꼴이 적혔고 일부는 HEAD 에서도 통과한다 — 상세는 비공개 메모(R-3) |  |
| 11 | M02 | decision | 열린 P1-10(공유 표면에 먼저 적용하고 반증은 뒤에)이 이 창에서 세 번째로 났다 — #1929 가 공개 Issue #1824 의 결정 줄(L02)을 Grok 민감도 반증 전에 고쳤고(판정 BROKEN), 그 첫 판을 공개 편집 이력에 남길지는 에이전트가 혼자 정했다 | `docs/workflow/verify.md` |
| 12 | M03 | code/time-of-check | 게시 전 검사가 본문을 재는 시점에 틈이 있다 — 상세는 비공개 메모(R-3) |  |
| 13 | M03 | code | #1935 가 #1928 교차 검토(Grok 3·4차)로 닫았던 부류를 다른 입력 경로에서 되살렸다 — 상세는 비공개 메모(R-3) |  |
| 14 | M03 | code | 게시 전 검사의 비밀값 꼴이 이 리포의 비밀 일부를 못 보고, 양성 시험이 빈 꼴이 많다 — 상세는 비공개 메모(R-3) |  |
| 15 | M03 | code · 회귀 가드 | 분기 커버리지로 드러나는 진짜 회귀 가드 부재: 시험이 닿지 않는 fail-closed 갈래는 지워도 시험이 전부 초록이고, 확정 결함 부류 입력에서 deny가 ALLOW로 바뀐다 | `scripts/scan_publish.py` |
| 16 | M03 | security · 게시 전 검사 | 게시 전 검사가 한국어 글의 흔한 꼴에서 비밀값을 놓친다 — 상세는 비공개 메모(R-3) |  |
| 17 | M04 | docs | 메모리 진입점이 11-27 «Grok 재개» 결정과 반대로 «중단, 아직 풀리지 않음» 을 지시한다 | `(메모리) MEMORY.md` |
| 18 | M04 | decision | 11-27 교차 검증 재개 결정이 메모리에 없다 — 세션마다 로드되는 색인이 아직 «다시 요청할 때까지 중단» 이다 | `~\.claude\projects\f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager\memory\feedback-grok-collaboration-default.md` |
| 19 | M04 | decision | PC 이전 뒤 결정 기록의 비공개 층이 작업 PC 에 없다 — 09-06 이후 메모리와 «작성자 메모» 가 원격에 없어, 원장의 열린 8항목이 가리키는 곳이 비었다 | `~\.claude\projects\f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager\memory\MEMORY.md` |
| 20 | M05 | decision | 위임 머지 기록이 «(위임)» 표지를 잃었다 — #1936 · #1937 · #1938 이 11-24 발화를 그 head 의 «승인» 으로 적었다 | `scripts/merge_approved.py` |
| 21 | M05 | decision | Grok 실패를 사용자에게 묻지 않고 자체 시험으로 갈음한 채 위임 머지했다 — #1925 는 성립한 판정 0건으로 머지됐고 머지 뒤 결함이 났다 | `docs/workflow/verify.md` |
| 22 | M05 | tooling/security-review-service | #1938 머지 15분 전 Cursor 보안 검토가 HIGH 2 · MEDIUM 2 를 달았다. 머지 경로가 리뷰 댓글을 읽지 않아 아무도 보지 않았고, 지적한 5꼴은 HEAD 에서 모두 통과한다 | `scripts/merge_approved.py` |
| 23 | M06 | code/hook-precision | credential 훅 거부 기록을 처음 재 보니 대부분 정직한 명령이었고, HEAD 훅도 그대로 막는다 (P1-5 ✅ #1936 이후) | `.claude/hooks/block_credential_dump.py` |
| 24 | M06 | code/platform-path-semantics | 두 훅이 Git Bash 경로를 Windows Python 규칙으로 읽는다 — 정직한 명령을 막고, 한 꼴은 판정이 빗나간다 — 상세는 비공개 메모(R-3) |  |
| 25 | M06 | tooling/hook-precision | P1-5 정밀도 수정(#1936) 뒤 첫 측정 창: 귀속된 거부 18건 중 16건이 정직한 명령이었고 값 덤프 시도는 0이다. 같은 오탐 꼴이 되풀이되고 HEAD 에서 재현된다 | `.claude/hooks/block_credential_dump.py` |
| 26 | M07 | process/cost-consent | «Claude 사용량이 조금 늡니다» 라고 권장한 워크플로 적대 패스가 21시간 동안 20회(에이전트 98개 · 약 3,085만 토큰) 돌았다. #1938 의 16회 동안 중간 확인은 0회였고, 사용자가 Claude 토큰 부족을 알린 뒤에야 멈췄다 | `.claude/skills/retrospective/SKILL.md` |
| 27 | M07 | decision | 교차 검증 대체 선택이 상한 없이 실행돼 2 PR 에 19패스 · 약 1,733만 토큰이 들었고, 16번째 패스는 사용자가 원격으로 멈췄다 | `~\.claude\projects\f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager\memory\feedback-grok-collaboration-default.md` |
| 28 | M07 | tooling/verification-cost | 가드 표면 교차 검증에 멈춤 규칙이 없다. #1937 · #1938 적대 패스 20회(에이전트 98 · 1,777만 토큰)를 돌렸고, 15회 연속 BROKEN 끝에 수렴이 아니라 예산 소진으로 멈췄다 | `docs/workflow/verify.md` |
| 29 | M08 | tooling/hooks-coverage | credential 보호가 닿지 않는 도구 경로가 있다 — 상세는 비공개 메모(R-3) |  |
| 30 | M08 | decision | SESSION_SECRET 교체 승인(11-25)을 넘는 비밀값 사본이 만들어져 남아 있었다 — 사본은 11-27 사용자 결정으로 지웠다(내용 열지 않음) · 상세는 비공개 메모(R-3) |  |
| 31 | M08 | tooling | 차단면 3종이 덮지 않는 실행 경로가 있다 — 상세는 비공개 메모(R-3) |  |
| 32 | M09 | process/cycle-close | 창 17 PR 중 10건(#1918~#1927)의 세션 기록이 회고 PC 에 없는데 retro_scope 는 records_expired_prs: [] · unmeasured: [] 를 냈다. 기록 축이 보존 일수만 본다 | `scripts/retro_scope.py` |
| 33 | M09 | docs | 훅 정밀도 절차(SKILL.md 3단계)에 창의 시간 경계와 오염원 제외가 없다. 거부 기록 58줄 중 41줄이 창 밖(이 회고 실행 중)에 쓰였고, 앞 라운드의 «귀속 18 · 미귀속 1/4» 도 그중 7줄을 품는다 | `.claude/skills/retrospective/SKILL.md` |
| 34 | M10 | tooling | Bash 보호 경로 탐지 훅은 주 체크아웃의 git status 만 본다. 워크트리 절차(#1923) 아래에서는 늘 빈 결과이고, 이 PC 에서는 출력이 원리적으로 0 인데 Bash 호출마다 1.3~3.8 s 를 쓴다 | `.claude/hooks/detect_protected_bash_write.py` |
| 35 | M11 | tooling/codeql-gate | required CodeQL 신규 경고 게이트는 PR diff 밖의 경고를 원리적으로 못 본다. #1938 이 마지막 사용처를 지워 main 에 #657 이 새로 열렸고, main 쪽에는 그것을 읽는 곳이 없다 | `scripts/check_codeql_alerts.py` |

## P2 (78건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | M01 | process/cycle-close · 범위 이월 | 회고 중 머지(#1939)를 «다음 회고 하한으로 이월» 하라는 지시와 SKILL 3단계 «분석 종료 head(main SHA)» 가 맞서고 이월 장치는 없다. 적힌 대로면 #1939 는 1초 시차로만 다음 창에 든다 | `.claude/skills/retrospective/SKILL.md` |
| 2 | M01 | tooling/retro-scope | 종료 범위 재확인이 실패(ok:false)하면 아무 기록 없이 null 이 되어 «실행 중 범위 이동 없음» 과 같은 값이 된다. 이번 실행은 #1939 가 07:04 에 머지됐고 주 세션 cwd 가 리포 밖이라 발동 조건이 갖춰져 있다 | `.claude/workflows/retrospective.mjs` |
| 3 | M02 | process/decision-question | 결정 질문이 원장 밖(채팅)에서만 오갔다. 11-26 3번 질문은 권장안 없이 물었는데, «권장안을 선택» 이라는 답에 에이전트가 권장안을 지어 이행했다(#1938 차단 규칙). 11-27 P1-8 «안 B» 답은 원장에 없다 | `.claude/skills/retrospective/SKILL.md` |
| 4 | M02 | process/cycle-close | «정할 것» 4~9 가 이틀째 결정 질문으로 오르지 않은 채 회고가 떴다. 4(회고 임계) · 9(훅 정밀도 목표)는 이 회고의 입력이고, 6(커넥터 읽기)도 답이 없어 7 머지의 배포 로그 확인이 한 번도 안 됐다 | `docs/workflow/deploy.md` |
| 5 | M02 | docs | 원장 #1917 «사용자 몫» 이 PR 본문과 어긋난다 — 이미 끝난 #1934 머지 승인은 남아 있고, 위임 머지 6건의 열린 확인 13개(#1938 의 정책 판단 둘 포함)는 빠졌다 | `[WBS] #1917 본문 «사용자 몫»` |
| 6 | M02 | decision | «사용자 몫» 위임 머지 확인 목록이 만든 지 하루 만에 멈췄다 — 판단 · 확인 질문 11개가 답 없이 닫혔고, 끝난 승인 요청은 그대로 남았다 | `.claude/skills/retrospective/SKILL.md` |
| 7 | M02 | decision | «정할 것» 4~9 가 이틀째 답 대기인데 사용자가 답하는 형식으로 다시 묻지 않았다 — 그 공백이 이번 회고의 착수 · 배포 로그 · 정밀도 판정을 좌우했다 | `scripts/retro_scope.py` |
| 8 | M02 | decision/record-fidelity | 원장 결정 줄과 PR 본문이 선택지 답의 «(Recommended)» 를 지워, 에이전트 권장 라벨을 사용자 원문처럼 남겼다 — 11-26 «워크플로 적대 패스 · 재개 전까지 계속» | `.claude/skills/retrospective/SKILL.md` |
| 9 | M02 | process | 에이전트를 막는 권한 층(훅의 permissionDecision deny)을 착수 전 확인 없이 넓히고 바꿔 위임 머지했다 — 같은 에이전트가 11-27 에는 머지 관문을 «권한 성격» 이라며 먼저 물었다 | `CLAUDE.md` |
| 10 | M02 | decision | 원장 #1917 이 사용자 답을 기다리는 4항목을 ✅ 로 닫았다 — P1-5 · P2-4 · P2-5 · P2-8 의 남은 몫(«정할 것» 9 · 6 · 7 · 8)이 체크박스 밖으로 빠졌다. 같은 처지의 P2-1 · P2-40 은 [ ] 로 남아 기준이 갈렸다 | `.claude/skills/retrospective/SKILL.md` |
| 11 | M02 | decision | 스스로 «P0 채널과 같은 부류» 라고 적은 운영 판정 구멍(P2-83)의 결정 질문에 임시 deny 선택지가 없었다 — 전날 #1929 가 SKILL.md 에 넣은 «본 수정이 올 때까지 채널을 열어 두지 않는다» 와 어긋나고, 구멍은 약 19시간 열려 있었다 | `.claude/skills/retrospective/SKILL.md` |
| 12 | M03 | code/false-positive | 게시 전 검사가 아무것도 게시하지 않는 명령을 막고, 그 막힘은 어디에도 기록되지 않는다 | `scripts/scan_publish.py` |
| 13 | M03 | tooling/hooks | 게시 전 검사 훅이 gh 가 없는 heredoc 명령에서도 돈다. heredoc 본문을 «게시될 글» 로 세어 로컬 스크립트를 막으니 «gh 명령에만 뜬다» 는 문서와 다르다 | `scripts/scan_publish.py` |
| 14 | M03 | tooling/hook-instrument | 게시 전 검사 훅의 거부는 어디에도 기록되지 않는다. 회고의 훅 정밀도 계기가 막는 훅 둘 중 하나를 못 본다 | `scripts/scan_publish.py` |
| 15 | M03 | code | 게시 전 검사가 gh 호출의 끝을 잘못 잡는다 — `$(gh …)` 의 닫는 괄호가 마지막 낱말에 붙고, 큰따옴표 안 `$(gh …)` 에서는 따옴표 상태가 뒤집혀 정직한 게시와 읽기가 모두 막힌다 | `scripts/scan_publish.py` |
| 16 | M03 | tooling | 게시 전 검사가 닿지 않는 공개 쓰기 경로가 있다 — 상세는 비공개 메모(R-3) |  |
| 17 | M03 | docs | 공개 리포에 커밋된 회고 보고서가 사용자 계정 이름이 든 Windows 홈 경로를 싣고 있다. #1928 이 공개 쓰기에서 막기로 한 꼴인데 커밋 쪽에는 재는 곳이 없고, 이번 회고 후보 좌표 3건도 같은 꼴이다 | `docs/reports/2026-09-07-retrospective.md` |
| 18 | M03 | code · 측정 설계 | 측정 축을 hooks · scripts로 넓혀도 창의 확정 결함은 거의 드러나지 않는다: 결함 자리는 당시 이미 실행된 줄이었다(고침 커밋 18개 반사실 측정) (심각도 조정 P1→P2) | `.github/workflows/ci.yml` |
| 19 | M04 | process/communication | 11-26 압축 뒤 약 5.5시간 동안 사용자에게 영어로 썼다(텍스트 64개 중 60개 · 턴 끝 보고 포함). 사용자의 «한글로 알려주세요» 는 세 번째다 — 직전 회고가 «이미 해소» 로 오탐 처리한 결함의 재발 | `CLAUDE.md` |
| 20 | M04 | process/memory | 항상 로드되는 메모리가 사용자가 11-27 에 푼 «Grok 교차 검증 중단» 을 «아직 풀리지 않음» 으로 들고 있다. 이 회고의 모든 에이전트가 그 줄을 읽었다 | `(메모리) MEMORY.md` |
| 21 | M04 | docs | 원장 P2-39 ✅ #1919 는 제목에 있던 «메모리 처방» 을 고치지 않고 닫혔다 — «계기 3.12» 메모리는 #1919 뒤로 두 겹으로 틀렸다 | `(메모리) feedback-analyzer-measurement-needs-py312.md` |
| 22 | M04 | decision | 압축 뒤 4시간 반 동안 보고가 영어로 나갔고, 결정 질문 셋도 영어로 물어 사용자가 «한글로 알려주세요» 로 되물었다 | `CLAUDE.md` |
| 23 | M04 | process | PC 이동 인계가 검증 라운드 id 를 옮기지 않아 #1936 의 claim-review 흔적에서 Grok 반례 라운드(26271dd5)가 빠졌다 — «BROKEN 으로 고친 라운드도 지우지 않는다» 위반 | `docs/workflow/verify.md` |
| 24 | M04 | memory | 메모리 진입점은 Grok 을 «아직 중단» 으로 적고, 그 SSOT 로 삭제된 문서를 가리킨다. 원장은 11-27 재개를 기록했다 | `~/.claude/projects/F--DEVELOPMENT-SOURCE-CLAUDE-SCAManager/memory/MEMORY.md` |
| 25 | M05 | process/approval-record | 위임 머지 #1936 · #1937 · #1938 의 승인 기록이 11-24 위임 발화를 «(위임)» · 날짜 · 원장 근거 없이 맨 승인처럼 적었다. 같은 창 #1919~#1935 의 표기에서 압축 뒤 퇴행 (심각도 조정 P1→P2) | `scripts/merge_approved.py` |
| 26 | M05 | process/verification-gate | 마지막 적대 판정이 BROKEN 인 채 위임 머지된 PR 이 셋이다(#1925 · #1927 · #1937). 머지 조건이 없어서 같은 날 #1937 은 BROKEN 4/4 로 머지했고, #1938 은 SURVIVES 를 받고서야 머지했다 | `docs/workflow/verify.md` |
| 27 | M05 | decision/approval-record | 안 B 의 «사용자 승인» 기록을 에이전트가 사용자 계정으로 쓴다. 첫 적용인 #1939 에서 클릭 44초 뒤 에이전트가 올렸고, 관문은 작성자를 보지 않아 실효가 사용자가 «실효가 낮다» 고 들은 안 A 와 같다 (심각도 조정 P1→P2) | `scripts/merge_approved.py` |
| 28 | M05 | decision/approval-gate | #1939 는 «이 PR 자체의 머지는 main 의 옛 스크립트로 돈다» 고 적고 사용자에게도 «다음 PR 부터 새 관문» 이라 했지만, 실제로는 PR 워크트리의 새 관문이 자기 머지를 판정했다 — 머지 관문은 cwd 의 트리로 돈다 | `CLAUDE.md` |
| 29 | M05 | decision/traceability | 위임 머지 기록 7건(#1924~#1929 · #1935)이 «원장 #1917 결정 기록 … 11-25 «네 완료되면 후속작업 진행해주세요» · «작업을 이어서 수행해주세요»» 를 근거로 인용하지만, 원장은 편집 24판 어디에도 그 줄을 가진 적이 없고 이 PC 의 세션 기록에도 없다 (원장 M04 P2-19 재발) | `CLAUDE.md` |
| 30 | M06 | code | credential 판정에는 heredoc «데이터» 개념이 없다 — 같은 파일의 운영 판정이 이미 고친 R-5 부류(본문 글자가 PR 작성을 막음)가 credential 쪽에는 그대로 남아 있다 | `.claude/hooks/block_credential_dump.py` |
| 31 | M06 | code | credential · 운영 훅이 stdin 을 로캘 코덱(cp949)으로 읽어, 비ASCII 명령의 거부 · 감사 기록 sha256 · len 이 실제 명령과 다르다 — 창 거부 84건 중 22건(26%). «1/4 귀속 불가» 의 실제 원인이다 | `.claude/hooks/block_credential_dump.py` |
| 32 | M06 | code · 인코딩 | 훅 다섯이 stdin을 로캘(cp949)로 읽는다: 형제 하나만 고쳐졌고, Linux CI에서는 원리적으로 안 드러난다 | `scripts/scan_publish.py` |
| 33 | M07 | process/cost-consent · 회고 착수 | 토큰이 모자라다고 한 사용자에게 낸 회고 비용 추정은 PR 수로 줄인 값이었고 집행되지 않는다. 1라운드만으로 추정 하한 800만을 넘었다(약 831만) | `.claude/skills/retrospective/SKILL.md` |
| 34 | M07 | decision/cost-consent | «이 비용으로» 동의받은 회고 상한(에이전트 60~90 · 2~4시간 · 800만~1,200만)을 워크플로 budget 으로 넘기지 않아 아무것도 그 상한을 보지 않는다 — 07:32 r2 진행 중에 이미 59개 · 3시간 8분 · 1,167만 | `.claude/workflows/retrospective.mjs` |
| 35 | M09 | process/cycle-close | 회고 범위가 직전 회고가 이미 본 #1916 을 다시 센다. GitHub mergedAt 이 scan_from 커밋보다 1초 늦어 gh_only 로 들어왔고, 사용자에게는 «머지 18건» 으로 보고됐다(실제 17) | `scripts/retro_scope.py` |
| 36 | M09 | docs | 회고 ROI 의 «창의 claim-review 반증률» 이 11-26 뒤로 두 검증 부류를 섞는다 — 0.655 는 직전 0.328 과 같은 축의 숫자가 아니다 | `.claude/skills/retrospective/SKILL.md` |
| 37 | M09 | tooling/hook-instrument | 거부 기록과 세션 기록을 sha256 으로 대 보면 창 거부의 1/4 을 귀속하지 못한다. PreToolUse 입력의 tool_use_id 를 남기지 않기 때문이다 | `.claude/skills/retrospective/SKILL.md` |
| 38 | M09 | process/measurement-integrity · 회고 계기 | 훅 거부 · 운영 감사 기록은 하네스 밖 호출도 실제 기록에 쓴다. 회고 검증자 탐침이 가짜 «Railway MCP get_logs» 허용 줄(감사 기록 3줄 중 1줄)과 거부 줄을 남겼다 (심각도 조정 P1→P2) | `.claude/hooks/block_credential_dump.py` |
| 39 | M09 | tooling | 회고 실행 자체가 훅 거부 기록에 창의 2.8배를 쌓는다. 기록에 실행·세션 구분이 없고, SKILL.md 는 창을 자르는 시각을 정하지 않는다 | `.claude/skills/retrospective/SKILL.md` |
| 40 | M09 | process | 감사받는 쪽(에이전트)이 운영 채널 감사 기록을 자기 판단으로 옮겨 정리했다 — 정리 절차도 파일 안의 흔적도 없고, 회고는 본 파일만 읽는다 | `.claude/skills/retrospective/SKILL.md` |
| 41 | M09 | decision | 운영 감사 기록의 처분을 피감사자가 정한다 — #1937 머지 직후 에이전트가 허용 기록 12줄(그중 6줄이 «railway variables» 채널)을 혼자 판단해 옆 파일로 옮겼고, 근거는 남기지 않았다 | `.claude/hooks/block_credential_dump.py` |
| 42 | M09 | measurement | 세션 기록의 tool_use 원시 집계는 api-request-blob 사본 때문에 약 1.5배 부푼다. 이 gap 의 60 · 58 · 7 · 4 · 11 은 고유 id 로 40 · 39 · 4 · 2 · 6 이다 | `.claude/skills/retrospective/SKILL.md` |
| 43 | M10 | tooling/hook-roi | PostToolUse 스모크 훅이 창의 주 세션에서 211회 돌았다. 통과 138회만으로 동기 대기가 1.94시간(중앙 55초)이고, ❌ 61회는 거의 다 개발 중인 훅 시험 두 파일에서 났다 | `.claude/settings.json` |
| 44 | M10 | code | 스모크 훅이 credential 훅을 편집할 때 시험 7파일 중 1파일만 돌린다 — #1937 · #1938 의 운영 판정 수정은 스모크에서 한 번도 재지 않았다 | `.claude/hooks/posttool_pytest_smoke.py` |
| 45 | M10 | docs | Bash 로 바뀐 보호 경로 탐지 훅은 사람(systemMessage)에게만 알린다. #1924 가 verify.md 에 적은 채널 규칙이 형제 PostToolUse 훅에는 적용되지 않았고, CLAUDE.md «PostToolUse 는 알리기만» 은 에이전트에게는 사실이 아니다 | `.claude/hooks/detect_protected_bash_write.py` |
| 46 | M10 | code | 훅 최신성 점검(#1923)이 워크트리에서 시작한 세션을 «주 체크아웃이 main 이 아니다» 로 오진하고, 워크트리에서는 실패하는 `git switch main` 을 처방한다 | `scripts/check_hook_surface_fresh.py` |
| 47 | M10 | code | SKIP_ALLOWLIST 의 유일한 «로컬 전용» 항목이 #1923 워크트리 절차 뒤로 어디서도 돌지 않는다 — 메모리 경로를 워크트리 슬러그로 찾아 늘 skip 한다(시간차) | `tests/unit/scripts/test_lint_gate_wiring.py` |
| 48 | M10 | tooling | «로컬 전용» skip 허용 시험이 워크트리 절차 뒤 어디서도 돌지 않는다. 메모리 디렉토리를 워크트리 경로에서 찾는다 | `tests/unit/scripts/test_lint_gate_wiring.py` |
| 49 | M11 | test/time-lag | 부하에 따라 red 가 되는 시간 하한 단언 — #1936 실행에서 38.3 < 40ms 로 깨졌는데 «건드리지 않는 영역» 으로 넘겼고 추적처가 없다 | `tests/unit/services/test_insight_refusal.py` |
| 50 | M11 | test/skip-gate | skip 집합 게이트의 «pg 잡» 꼬리표는 이름만 대조한다 — PG 잡에는 skip 게이트가 없어, 거기서도 skip 되면 35건이 다시 어디서도 안 돌고 두 잡 모두 초록 | `tests/unit/scripts/test_unit_skip_gate.py` |
| 51 | M11 | tooling/ci-reliability | 벽시계 간격을 재는 단위 시험 하나가 main CI 를 red 로 만들어 #1937 배포가 건너뛰어졌다. 같은 임계를 쓰는 형제 시험이 있고 추적 항목은 없다 | `tests/unit/ui/test_insight_pages_off_loop.py` |
| 52 | M11 | ci · CodeQL | CodeQL PR 게이트는 PR이 바꾼 줄 밖을 보지 않는다: 같은 트리가 PR 분석에서는 0건, main 분석에서는 116건이고, #657은 머지 뒤에야 났다 | `scripts/check_codeql_alerts.py` |
| 53 | M11 | ci · 측정 범위 | Codecov · SonarCloud · pylint · bandit은 src만 재는데 그 결정은 어디에도 없다: hooks · scripts를 더한 PR 8건이 모두 codecov/patch «Coverage not affected»로 초록이고, STATE.md는 «Python 97%»라고 적는다 | `docs/STATE.md` |
| 54 | M12 | code/comment-drift | slither `_matching_solc` docstring 이 #1919 뒤 코드와 반대를 말한다 — P2-39 ✅ #1919 가 남긴 문단 | `src/analyzer/io/tools/slither.py` |
| 55 | M12 | docs | 유출 확인 처방 두 곳이 아직 비밀값 원문을 찍는 도구를 부른다 — #1926 은 «유출 시» 2 만 값 없이 바꿨다(원장 P2-5 ✅ 의 잔여) | `docs/workflow/security.md` |
| 56 | M12 | docs | 새 PC 설치 절차(#1922)는 Windows 에서 «그대로 칠» 수 없고 한 번도 실행되지 않았는데, 원장 P2-41 은 ✅ 다 | `Makefile` |
| 57 | M12 | docs | verify.md 가 #1921 의 단위 잡 skip 게이트(--strict-skips ↔ tests/SKIP_ALLOWLIST)를 모른다 — 새 PG 시험은 등재가 두 곳인데 영역 문서는 한 곳만 적는다 | `docs/workflow/verify.md` |
| 58 | M12 | docs | 새 PC 체크리스트에 railway CLI(설치 · 로그인 · 링크)가 없다 — 11-25 PC 이동 뒤 머지 7건 모두 배포 로그 확인(deploy.md 머지 뒤 2)을 하지 못했다 | `docs/runbooks/new-machine-setup.md` |
| 59 | M12 | docs | 문서의 단위 실행 명령(py -3 -m pytest tests/unit -q)은 이 창 PR 17건 어디에도 쓰이지 않았다 — 실제 절차(핀 venv · 3.12 · --timeout=600)는 비공개 메모리에만 있다 | `CLAUDE.md` |
| 60 | M12 | docs | «문서 총량은 늘리지 않는다» 아래에서 이 창 문서가 +2,019자 늘었다 — 7 PR 모두 순증 · 줄인 PR 0, 원장 P2-49 · P2-50 은 결정 없이 열려 있고 PR 당 증가는 직전 창의 2.3배다 | `CLAUDE.md` |
| 61 | M12 | code | slither pragma skip 을 no_dedicated_observer 가 기록한다는 주석이 #1827 이후 거짓이다 — skip 은 «분석 0» 이 됐는데, P2-39 를 닫은 #1919 가 그 주장을 한 곳 더 적었다 | `src/analyzer/io/tools/slither.py` |
| 62 | M12 | docs | #1938 이 observer_setup · backfill --apply 를 막는 규칙을 넣었는데, 같은 파일의 #1937 주석은 그 둘을 «사용자 몫인데 훅이 막지 않는 것» 으로 둔 채 남았다. 런북도 사용자 `!` 몫이라고 적지 않는다 | `.claude/hooks/block_credential_dump.py` |
| 63 | M12 | docs | verify.md 의 «막는 훅 = onFailure block · 시간 제한 30초 이상» 에 편집 훅 예외가 없다. #1925 시험은 그 예외를 «사용자 결정 R31» 로 적는데, R31(#1270)은 에이전트 자율 판단이고 다룬 고장도 다르다 | `docs/workflow/verify.md` |
| 64 | M12 | docs | 새 PC 설치 절차의 사본 동기화 규칙(deploy.md §의존성)이 사본을 셋만 적는다. CLAUDE.md 최초 설정과 보안 사본 둘이 빠졌고, 그중 보안 런북 사본은 #1922 의 pre-commit 핀과 이미 어긋나 있다 | `docs/workflow/deploy.md` |
| 65 | M12 | docs | 로컬 게이트가 push 전에 인쇄하는 «보지 못하는 축» 가운데 test-and-analyze 설명이, #1921 이 그 잡에 더한 새 red 조건 둘(skip 집합 게이트 · semgrep 스키마 덤프)을 모른다 | `scripts/pre_push_gate.py` |
| 66 | M12 | tooling | #1922 가 리포 루트에 만드는 `.venv-semgrep/` 를 .gitignore 에만 넣고 .dockerignore 에는 넣지 않았다. README 대로 `make install` 한 뒤 deploy.md 의 로컬 재현 `docker build` 를 돌리면 semgrep venv 전체가 빌드 컨텍스트와 이미지 /app 에 실린다 | `.dockerignore` |
| 67 | M12 | tooling | 다른 PC 의 커밋 신원이 가짜 시료 신원이었다. 창 범위 커밋 17개 중 13개에 가짜 공동 저자가 공개 이력으로 남았고, 이를 보는 점검이 없다 |  |
| 68 | M13 | tooling | 무변경 운영 재시작 15/16 — 거르는 장치가 없고, 바깥에서 잴 수 있는 채널의 실측 비용은 0 (DB·로그 채널은 못 잼) | `docs/workflow/deploy.md` |
| 69 | M13 | tooling | «위임 머지 = 운영 배포» 가 위임 조건에도 운영 규칙에도 없다 — 배포는 사용자 `!` 몫인데 위임 머지가 운영을 14번 교체했다 | `CLAUDE.md` |
| 70 | M13 | tooling | «머지 뒤 배포 확인» 이 PC 이전 뒤 GitHub 배포 상태(헬스체크)만으로 돌았다 — 로그 단계가 교체 7회 연속 빠졌고, 런북에 «로그를 못 읽을 때» 갈래가 없다 | `docs/workflow/deploy.md` |
| 71 | M13 | tooling | 표적 점검의 계기가 이 PC 에 없고, 있더라도 DB 는 과거 분석 소실을 원리적으로 못 본다 — 내구 기록은 약 7일 보존되는 Railway 로그뿐(11-24 교체분은 12-01 무렵 만료) | `src/services/cron_service.py` |
| 72 | M13 | tooling | 교체마다 두 스케줄러가 겹치는데 문서는 «단일 인스턴스 전제» 로만 적는다 — 무변경 재시작 #1938 의 겹침 창이 비멱등 trend(03:00 UTC) 1초 전에 닫혔다 | `src/scheduler.py` |
| 73 | M13 | tooling | «배포마다 한 번» 을 전제로 둔 프로세스 상태가 위임 머지 빈도에서는 뜻이 바뀐다 — 고정 판 알림 재발송 · 목록 실패 알림 도달 불가 · 기동마다 P2-74 노출 | `src/services/model_catalog_service.py` |
| 74 | M13 | tooling | #1937 의 «실패» 배포는 CI 실패에 따른 SKIP 이었고, main CI 재실행이 초록이 돼도 배포는 다시 생기지 않았다 — 런북에 SKIPPED 복구 갈래가 없다 | `docs/workflow/deploy.md` |
| 75 | M13 | tooling | 회고 도구의 다섯 관점에도 범위 산출에도 운영 배포가 없다 — «재시작 수 × 기동 경로 결함» 같은 시간차 누적이 관점 사이로 빠진다 | `.claude/workflows/retrospective.mjs` |
| 76 | M14 | tooling/supply-chain-automation | #1927 이 더한 Dependabot pre-commit 생태계의 PR 은 required 검사를 구조적으로 못 넘는다. #1930 이 11-25 부터 red 다 | `scripts/check_claim_review_trace.py` |
| 77 | M14 | process | 초록인 Dependabot PR 셋(#1931 · #1932 · #1933)이 회고 착수까지 약 41시간 누구에게도 올라가지 않았다 — #1927 이 연 «갱신 감시» 의 출력을 받을 주인이 없다 | `.github/dependabot.yml` |
| 78 | M14 | supply-chain | Dependabot PR 에는 처리 절차도 추적 자리도 없다. #1927 의 설정 변경으로 열린 4건이 이틀째 누구의 할 일로도 오르지 않았다 | `.github/dependabot.yml` |

## 오탐 (다음 회고가 다시 판정하지 않도록)

| 관점 | 제목 | 기각 사유 |
|---|---|---|
| tooling | Monitor 는 Bash 와 같은 셸을 매처 밖에서 돌린다. PowerShell 이 받은 배선 시험이 Monitor 에는 없다 | 인용은 전부 실재한다. settings.json:47 매처는 `Bash\|PowerShell\|mcp__.*[Rr]ailway.*\|mcp__.*[Ss]upabase.*` 이고, :57 은 `if: Bash(gh *)`, :64 는 `if: PowerShell(gh *)` 이다. test_block_credential_dump.py:941·:951·:961 은 Bash·PowerShell·Railway MCP list 배선 시험이고, 메모리 :25 에는 «Monitor = 별도 셸·PreToolUse 훅 미적용» 이 적혀 있다. 다만 «세 가지뿐» 은 그 파일 안에서만 맞다. test_block_production_access.py 와 test_credential_hook_failure_contract.py 에도 |

## 묶음 — 원장은 `[WBS]` #1940

확정 113건을 원인 14묶음으로 나눴다(묶음 초안 = Grok · 모든 번호가 정확히 한 번 — 생성기가 검사).

| 묶음 | P1 · P2 | 주제 |
|---|---|---|
| M01 | 6 · 2 | 회고 디스패치가 실행 제약을 안 실음 — 전용 트리 · 금지 · 범위 |
| M02 | 5 · 9 | 결정의 기록면 — 무응답이 닫힘 · 해석이 결정 · 공개가 반증보다 앞섬 |
| M03 | 5 · 7 | 게시 전 검사의 정밀도 · 회귀 가드 — 일부 상세는 비공개 메모(R-3) |
| M04 | 3 · 6 | 세션 경계의 상시 지시 — 메모리 미갱신 · 압축 뒤 언어 · PC 사이 미전달 |
| M05 | 3 · 5 | 머지 관문의 기록 — 위임 표지 · 판정 부재 · 작성 주체 · cwd 의 스크립트 |
| M06 | 3 · 3 | credential 훅의 오탐 — 명령 자리 · Bash 경로 · stdin 인코딩 |
| M07 | 3 · 2 | 토큰 상한이 문장으로만 있음 — 적대 패스 · 회고 budget 미전달 |
| M08 | 3 · 0 | 차단면의 범위 — 상세는 비공개 메모(R-3) |
| M09 | 2 · 8 | 회고 계기가 창의 기록을 못 가름 — 없는 기록 · 시각 경계 · 감사 개변 |
| M10 | 1 · 6 | 훅이 세션의 작업과 어긋남 — 주 체크아웃 · 스모크 대상 · 사람 알림 |
| M11 | 1 · 5 | 검증 계기의 공허한 초록 — CodeQL diff · src 만 · 잡 이름 · 벽시계 |
| M12 | 0 · 14 | 절차 · 주석 · 설치 사본이 코드보다 낡음 |
| M13 | 0 · 8 | 위임 머지가 곧 운영 교체 — 무변경 재시작 · 로그 확인 · 겹침 창 |
| M14 | 0 · 3 | Dependabot PR 에 주인이 없음 — required 통과 구조 · 추적 자리 |

## 다음 회고를 위한 경계

- 다음 범위의 하한은 **이 리포트를 추가한 커밋** 이다. 실행 중 머지된 #1939 는 다음 범위에 든다.
- 운영 접근 · 비밀값 인용 · 쓰기 금지는 프롬프트 빌더가 넣기 전까지 디스패치 `context` 에 직접 적는다 — 이번에 빠졌고 훅 거부 119건이 났다.
- 실행 비용은 세 실측에서 출발한다 — 135 에이전트 · 8h50m · 2,249만(이번, 18 PR) · 121 · 5h10m · 2,280만 · 191 · 10h42m · 3,074만. PR 수보다 발견 수가 비용을 정한다.
- 예상 비용 1줄 보고는 디스패치 **전**에 하고, 넘으면 실행 중에 다시 묻는다.
- 🔴 이 리포트를 추가하면 단위 테스트가 2건 는다 — `tests/unit/scripts/test_gate_claim_consistency.py` 가 문서마다 파라미터화한다.
