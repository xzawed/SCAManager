# 회고 2026-11-24 — `#1813~#1916`

## 범위

| | 값 |
|---|---|
| head | `5ae8d50b` = `main` (분석 종료 시점 · 분석 시작과 같다) |
| 기계 산출 범위 | `#1813~#1916` — 99 PR (`retro_scope.py --json` · 디스패치 직전 실행) |
| 경계 커밋 | `535cc87` (직전 리포트 `2026-11-06-retrospective.md` 추가 커밋) |
| 실제 기점 | `dfb3115c` — 직전 리포트가 적은 분석 종료 시점(`scan_from_kind: report-head`) |
| 정직성 필드 | `gh_only: []` · `unmeasured: []` · `records_expired_prs: []` |
| 실행 중 범위 이동 | 없음 |

## ROI

| 지표 | 값 |
|---|---|
| 라운드 (loop-until-dry) | 3 (예산 미설정 상한) |
| 총 발견 | 101 |
| 확정 | **100** |
| 오탐 차단 | 1 |
| 심각도 조정 | 6 (P1→P2 5 · P2→P1 1) |
| verdict 커버리지 | 1 |
| 미검증 잔여 | 0 |
| 실행 중 범위 이동 | 없음 |
| P0 / P1 / P2 | 0 / 18 / 82 |
| 창의 claim-review 반증률 | 0.328 — 99 PR 중 86건의 판정 290개에서 BROKEN 88 · WEAKENED 5 · REFUTED 2 (SURVIVES 28 · HOLDS 167) |

에이전트 121 · 오류 0 · 5h10m · 2,280만 토큰 · 도구 호출 5,948(직전 191 · 10h42m · 3,074만).
실행 전 예상(약 170 에이전트 · 약 10시간 · 약 2,800만 토큰)보다 작았다 — 차이는 표적 라운드 크기다(이번 gap 2건 · 11건, 직전 8건 · 44건).
5관점(process·code·docs·decision·tooling) finder 3라운드(39 · 28 · 23건) → 전건 cross-verify →
완전성 비평가 gap 2건 → 표적 라운드(11건) → 검증.

## 실행 안전 — 리포트 작성자 확인(워크플로 교차검증 밖)

직전 회고는 실행 중에 운영 비밀값 노출과 운영 컨테이너 코드 실행을 냈다(원장 #1824 R-1). 이번에는 디스패치 브리프에
운영 접근 · 비밀값 인용 · 쓰기 · 무거운 실행 · 다른 모델 위임 금지를 적었고, 끝난 뒤 에이전트 기록 121개를 값을 열지 않고 다시 쟀다.

| 축 | 결과 |
|---|---|
| 비밀값 꼴 | 9 — 전부 이미 공개된 문자열이다. 리포에 커밋된 자리표시자 DB 접속 주소 6(`.github/workflows/ci.yml` · `scripts/observer_setup.py`) · 공개 GitHub 문서의 예시 3(키 머리 줄뿐). 실제 비밀값 0 |
| 운영 접근 실행 | 0 — 그 낱말이 나온 호출은 검색 · 소스 읽기 · 기록 분석이었다 |
| 하위 에이전트 · 다른 모델 호출 | 0 |
| 시험 실행 | 단일 파일 · `-k` · `--collect-only` 28회 — 전체 단위 시험 0 |
| 쓰기 | 세션 임시 폴더 133회 — 회고 워크트리 · 주 체크아웃은 끝난 뒤 깨끗했다 |
| 외부 웹 | 공개 문서(GitHub · Claude Code) 24회 — 리포 · 사용자 정보 0 |

세 축(운영 · 비밀값 · 쓰기)이 모두 0 이었다. 에이전트가 운영 접근을 시도하지 않았으니 운영 접근 훅은 이번에 시험되지 않았다 —
브리프 금지는 다음 회고에도 그대로 둔다.

## 핵심 — P1 18건의 뿌리 (P0 없음)

### M06 — #1857 의존성 이동의 뒷면: slither pragma 사전 점검 회귀 (P1-13 ~ P1-18)

- 사실: `semantic_version` 은 어떤 requirements 에도 선언된 적이 없고 semgrep 의 전이 의존으로만 앱 venv 에 있었다.
  #1857 이 semgrep 을 별도 venv(`/opt/semgrep`)로 옮기자 앱 venv 와 CI 앱 환경 모두에서 빠졌다. slither 의 pragma
  사전 점검은 import 실패를 폴백으로 받아 설치된 0.8.20 을 고르고, 0.8.20 이 못 맞추는 pragma 에서도 slither 가 돌아
  빈 출력 → `analysis_failed` → `static_analysis_incomplete` 로 auto-merge · approve 가 막힌다. #1571 의 계약(«못 맞추면
  skip + 관측 기록»)이 운영에서 꺼졌다고 판단한다 — 근거는 CI 실측과 코드 경로이고, 운영은 직접 재지 않았다.
- 왜 아무것도 못 잡았나: CI 에서 이 경로의 시험 34건이 영구 skip 이 됐는데 시험 수 게이트는 «본문 + skip == junit» 합만
  대조해 초록이었다. 단위 · 통합 잡에는 skip 집합 회귀 가드가 없고(#1857 뒤 35건이 어느 잡에서도 돌지 않았다), pylint E0401 은
  `except ImportError` 로 감싼 import 를 보지 않으며, 이미지 안 출력 오라클의 Solidity 시료는 맞출 수 있는 pragma 하나뿐이다.
- 이 묶음은 5관점 finder 3라운드가 설치 절차 한 건(P2-41)만 짚었고, 회귀 자체는 완전성 비평가의 gap 2건 → 표적 라운드가 찾았다.
- 처방(검증자들이 모은 것 — 수정은 사용자 결정): `semantic-version` 직접 선언 · 오라클에 못 맞추는 pragma 시료 · skip 집합
  허용 목록 가드 · 선언되지 않은 import 검사(이미지 venv · 단위 잡) · «CI 에서 돈다» 고 적은 skip 은 CI 에서 red.
- 필요한 측정(사람 승인 뒤): 운영 이미지의 `semantic_version` 유무 · #1857 배포 뒤 Solidity 를 포함한 `incomplete` 분석 건수 ·
  운영 로그의 `slither produced no output` 줄 수(배포 전후).

### M01 — 훅 · 설정이 세션에 닿는 길 (P1-1 ~ P1-4)

- 사실: 리포 훅은 주 체크아웃의 파일로 돈다. 주 체크아웃이 11-15 ~ 11-21 기능 브랜치에 머물러, 그 사이 머지된 훅 · 설정 변경
  10 PR(회고 착수 신호 #1856 · 문서 심의 훅 퇴역 #1876 · credential 훅 수정 #1887 · #1890 등)이 4~6일 적용되지 않았다.
  회고 착수 신호는 신호 훅이 `startup|resume` 에만 걸려 /clear · 압축 뒤에는 돌지 않았고, #1856 머지 때 31 PR 이던 창이
  99 PR 이 되어서야(8.5일 뒤) 사용자에게 닿았다. PostToolUse 스모크 훅의 결과(창 746회 · 동기 7.8시간)는 에이전트에게 닿지 않는다.
- 처방: 작업은 워크트리 · 주 체크아웃은 main(CLAUDE.md 작업 절차 1) · SessionStart 에 «지금 도는 훅 ≠ main 의 훅» 한 줄 ·
  신호 훅에 clear · compact · 스모크 훅은 ❌ · ⚠️ 만 에이전트 맥락으로.

### M03 · M04 — 승인과 결정의 기록면 (P1-8 · P1-9 ~ P1-11)

- 승인하지 않은 head 가 «승인한 head» 기록을 달고 머지됐다(#1894 · #1907 — 원장 #1824 L06 P1-27 재발). 시각 관문의
  «화면을 본 발화» 는 대리 근거(PR 본문 글자 · 다른 모델 판독)로 통과했고, Grok 판정이 하나도 성립하지 않은 머지가 9건이다.
- 원장 «고치지 않기» 2건이 에이전트 판단인데 «보류(결정됨)» 으로 보고됐고, 동의를 묻던 #1880 체크박스는 답 없이 위임 머지로
  닫혔다. 공유 표면에 먼저 적용하고 반증은 뒤에 한 사례가 둘이고, 사용자 몫 정리 · 확인은 원장 «다음» 줄에 오르지 않으면
  압축 뒤 사라진다.
- 처방: `merge_approved.py` 에 승인 발화 시각을 받고 그 뒤 push 가 있으면 막는다 · 위임 머지는 따로 표기한다 · 보류는 사용자 결정
  줄이 있어야 성립한다 · 원장 머리에 «사용자 몫» 칸 · 공유 표면(공개 Issue · 전역 규칙)의 보안 · 민감 내용은 반증 뒤에 적용한다.

### M02 — 운영 접근 · 비밀값 차단면 (P1-5 ~ P1-7)

- credential · 운영 접근 훅의 정밀도를 아무도 재지 않는다 — 창의 거부 131건 중 실제 값 덤프 시도는 0 이었고, 오탐 수정(R-5)은
  6건으로 세고 닫혔다. 훅의 예외 처리와 문서 두 곳(운영 DB 확인 · 유출 확인 절차)은 공개 리포라 상세를 작성자 메모로 둔다.
- 처방: 거부마다 값 없는 기록(시각 · 사유 · 명령 해시)으로 정밀도를 잰다 · «통과해야 하는» 오탐 코퍼스를 «막아야 하는» 코퍼스와
  짝으로 · 예외 처리 계약을 시험으로 고정 · 문서 처방은 사용자 `!` 명령과 값 없는 확인으로.

### M05 — 공급망 (P1-12)

- «== 핀이면 CI == Railway» 가 전이 의존에서는 거짓이다 — 같은 `requirements.txt` 가 6일 사이 pydantic · pydantic-core ·
  certifi · regex 를 다른 판으로 깔았고, 의존성 그래프는 전이 패키지를 모른다.
- 처방: 두 venv 모두 해시 lock(`requirements.in` → 해시를 담은 `requirements.txt`) · 설치는 `--require-hashes`.

## P1 (18건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | M01 | process/cycle-close | 회고 착수 신호(L15 · #1856)가 창 내내 사용자에게 닿지 않았다 — 머지 때 31 PR, 첫 전달은 8.5일 뒤 99 PR | `.claude/settings.json` |
| 2 | M01 | process/hook-delivery | 머지된 훅 · 설정 변경 10 PR 이 약 6일간 에이전트 세션에 적용되지 않았다 — 주 체크아웃이 옛 브랜치에 머물렀다(사용자 결정 L11 포함) | `CLAUDE.md` |
| 3 | M01 | hooks | 훅 수정이 머지돼도 «주 체크아웃의 판» 이 돈다 — 11-15~11-21 주 체크아웃이 기능 브랜치에 있어 훅 표면 11커밋이 4~6일 비활성, 그동안 스모크 105회가 워크트리 편집을 옛 트리로 쟀다 | `.claude/settings.json` |
| 4 | M01 | tooling | PostToolUse 스모크 훅의 ✅/❌/⚠️ 결과가 에이전트에게 닿지 않는다. 창 안에서 746회, 동기 7.8시간을 썼지만 결과는 디버그 로그로만 갔다 | `.claude/hooks/posttool_pytest_smoke.py` |
| 5 | M02 | hooks | credential · 운영 접근 훅의 정밀도를 아무도 재지 않는다 — 창 거부 131건 중 정직한 값 덤프 시도 0, R-5 는 6건으로 세고 닫혔고 주된 오탐 꼴은 현 판에서 그대로 재현된다 | `.claude/hooks/block_credential_dump.py` |
| 6 | M02 | docs | `railway.md` §DB 의 운영 DB 확인 처방이 운영 규칙(L02)과 어긋난다 — 사용자 `!` 명령으로 바꾼다(상세는 작성자 메모) | `docs/runbooks/railway.md` |
| 7 | M02 | tooling | 운영 접근 · credential 차단 훅의 예외 처리 계약을 시험으로 고정한다(상세는 작성자 메모) | `.claude/settings.json` |
| 8 | M03 | decision | 사용자가 승인하지 않은 head 가 «승인한 head» 기록을 달고 머지됐다 — #1894 · #1907 (원장 L06 P1-27 ✅ #1843 재발) | `scripts/merge_approved.py` |
| 9 | M04 | decision | 원장 «고치지 않기» 2건(K07 P2-11 · K22 P2-2)은 에이전트 판단인데 «보류(결정됨)» 으로 보고됐다. 동의를 묻는 #1880 체크박스는 위임 머지로 답 없이 닫혔고, 같은 PR 이 바꾼 회고 판정 규칙도 확인 없이 이번 회고를 판정한다 | `.claude/skills/retrospective/SKILL.md` |
| 10 | M04 | process | 공유 표면(공개 Issue · 전역 에이전트 권한 규칙)에 먼저 적용하고 반증은 뒤에 했다 — 두 번 모두 반증이 실제 구멍을 찾았다(사례는 작성자 메모) | `docs/workflow/verify.md` |
| 11 | M04 | process | «사용자 몫» 정리 · 확인은 원장 «다음» 줄에 오르지 않으면 컨텍스트 압축 뒤 사라진다 — 8일째 남은 정리 1건이 있다(내용은 작성자 메모) | `.claude/skills/retrospective/SKILL.md` |
| 12 | M05 | supply-chain | «== 핀이라 CI == Railway» 가 전이 의존에서는 거짓이다 — 같은 requirements.txt 가 6일 사이 pydantic · pydantic-core · certifi · regex 를 다른 판으로 깔았고, 의존성 그래프는 전이 패키지를 하나도 모른다 | `.github/workflows/ci.yml` |
| 13 | M06 | analyzer-runtime · 의존성 선언 | #1857 이후 앱 환경에 semantic_version 이 없다 — 운영 slither pragma 사전 점검이 폴백으로 떨어져 #1568 B · #1571 이 없앤 «벽»이 되살아났을 개연성이 높다 | `src/analyzer/io/tools/slither.py` |
| 14 | M06 | test-observability · CI skip 집합 | 단위·통합 잡(pytest tests/)에 skip 집합 회귀 가드가 없다 — #1857 부터 64 머지 동안 35건이 어느 CI 잡에서도 안 돌았고, 수치 계기는 그 차이를 찍고도 초록이었다 | `.github/workflows/ci.yml` |
| 15 | M06 | dependency declaration guard | 선언되지 않은 import 를 잡는 축이 없다 — pylint E0401 은 `except ImportError` 로 감싼 import 를 보지 않아, #1857 이 쓴 점검(E0401 + 그 패키지를 쓰는 시험)이 이 부류에 구조적으로 맹목 (심각도 조정 P2→P1) | `src/analyzer/io/tools/slither.py` |
| 16 | M06 | 운영 분석 동작 — slither(Solidity) pragma↔solc | #1857 뒤 앱 venv 에 semantic_version 이 없어 slither pragma 사전 점검이 폴백한다 — 0.8.20 이 못 맞추는 Solidity 가 다시 «벽»(incomplete → auto-merge·approve 차단) | `src/analyzer/io/tools/slither.py` |
| 17 | M06 | 검증 양식 — 의존성 이동의 import 폐포 대조 | 의존성을 옮기는 PR 에 «src 가 import 하는 모듈 ⊆ 요구 파일 폐포» 대조가 없다 — 메모리 처방(깨끗한 컨테이너 pylint E0401 + 그 패키지 시험)은 가드된 지연 import 를 원리적으로 못 잡는다 | `requirements.txt` |
| 18 | M06 | 검증 양식 — CI 에서 skip 으로 바뀐 시험 | #1857 이 CI 의 slither pragma 판정 시험 34건을 영구 skip 으로 바꿨는데 어떤 게이트도 잡지 않았다 — 수치 게이트는 «본문 9896+5 == junit 9861+40» 으로 초록 | `tests/unit/analyzer/tools/test_slither.py` |

## P2 (82건)

| # | 묶음 | 관점 | 제목 | 좌표 |
|---|---|---|---|---|
| 1 | M01 | automation | 회고 착수 신호는 배포된 날부터 이미 켜져 있었고 처음 보인 것은 이레 뒤(93 PR)다 — 임계 15 가 직전 원장의 수정 PR 까지 세고, 신호는 세션 시작에서만 나온다 | `scripts/retro_scope.py` |
| 2 | M01 | docs | CLAUDE.md 영역 표에 `.claude/**`(훅 · 설정 · 워크플로 · 스킬 · 에이전트) 행이 없다 — 창 99 PR 중 15건이 이 표면을 고쳤는데 «영역 문서를 연다»(절차 2) 가 가리킬 곳이 없다 | `CLAUDE.md` |
| 3 | M02 | hooks | P0 확정 사흘 뒤 같은 꼴(운영 컨테이너에서 에이전트 코드 · 워커 자격)이 주 세션에서 다시 돌았다 — 기계 차단(#1818)이 오기 전 빈 구간이었고, 남은 기록은 «읽기 전용 확인» 뿐이다 (심각도 조정 P1→P2) | `.claude/hooks/block_credential_dump.py` |
| 4 | M02 | docs | 문서가 처방한 MCP 읽기 두 곳(deploy.md «MCP describe-service» · railway.md «MCP get_project»)을 #1818 운영 접근 훅이 «운영 실행 · 변경» 으로 막는다 | `docs/workflow/deploy.md` |
| 5 | M02 | docs | `secret-prevention.md` «유출 시» 확인 절차를 값을 출력하지 않는 꼴로 바꾼다(상세는 작성자 메모) | `docs/runbooks/secret-prevention.md` |
| 6 | M02 | process/publication-safety | 공개 Issue · PR 본문의 게시 전 비밀값 · 개인정보 검사를 세션과 분리된 고정 절차로 두고, 공개 쓰기마다 적용한다(사례는 작성자 메모) | `.github/workflows/ci.yml` |
| 7 | M02 | tooling | 1층 비밀값 스캐너(gitleaks)와 pre-commit 의존성을 갱신 감시 범위에 두고, 저장소가 쓰는 키 꼴을 검사가 덮게 한다(상세는 작성자 메모) | `.pre-commit-config.yaml` |
| 8 | M02 | tooling | DB 접속 주소 꼴을 push 전 비밀값 검사(GitHub 쪽 · 1층 이름 검사)에 넣는다(상세는 작성자 메모) | `.pre-commit-config.yaml` |
| 9 | M03 | process/visual-gate | 시각 관문의 «화면을 본 발화» 가 두 대리 근거로 통과했다 — PR 본문 글자(#1906) · 다른 모델 판독(#1911) — 규칙 문구는 그대로 | `scripts/merge_approved.py` |
| 10 | M03 | docs | CLAUDE.md 7단계 «화면을 본 발화(--visual) — 위임으로 덮지 않는다»와 실제 머지 근거가 갈라졌다 — #1911 은 «직접 봤다는 발화 없음»을 --visual 로 넣고 통과했다 (심각도 조정 P1→P2) | `CLAUDE.md` |
| 11 | M03 | decision | 시각 변경 PR #1911 이 «화면을 본 발화» 없이 머지됐다 — 관문은 비지 않은 글자만 보고, 원장은 에이전트 판단을 사용자 결정으로 적었다 (L06 P1-10 ✅ #1843 재발) (심각도 조정 P1→P2) | `scripts/merge_approved.py` |
| 12 | M03 | decision | 특정 질문에 한 답과 원장 작업용 머지 위임을 나중 일의 «상시 지시» 로 넓혀 썼다 — #1899 착수 · #1916 머지 (L07 P2-74 ✅ #1877 재발) | `.claude/skills/retrospective/SKILL.md` |
| 13 | M03 | process | P2-111 결정의 «승인 기록에 남김» 이 merge_approved.py 기록 양식에 없다. 스크립트가 유일한 머지 경로가 된 뒤 보완 커밋 PR 11건 중 9건에 «제목 ↔ 최종 diff» 대조 흔적이 없다 | `scripts/merge_approved.py` |
| 14 | M03 | process | 머지 위임 메모리가 아직 날것 `gh pr merge` 와 i18n 이 빠진 시각 범위를 처방하고, MEMORY.md 진입점이 그 파일을 «머지 조건» 으로 가리킨다. 그 경로를 막는 훅은 없다. claim-review 메모리도 원장 P2-26 이 리포에서 고친 거짓을 그대로 갖고 있다 | (메모리) feedback-merge-authority-granted-2026-11-15.md |
| 15 | M03 | decision | Grok 판정이 하나도 성립하지 않은 PR 9건이 머지됐다 — 11-12 사용자 지시 «머지 승인하기 앞서서 Grok의 판정을 확실하게 받아야 합니다» 뒤의 일이고, 머지 기록과 머지 요청 어디에도 이 사실이 없다 | `docs/workflow/verify.md` |
| 16 | M03 | decision | «화면을 봤는가» 라는 사실 확인에 권장 표시를 붙여 물었다 — 권장안 채택률 48/50 인 창에서 #1895 · #1896 · #1899 의 화면 확인 기록은 에이전트가 쓴 «화면 확인 · 머지 승인 (Recommended)» 라벨 그대로다 | `CLAUDE.md` |
| 17 | M03 | tooling | required 검사인 CodeQL 신규 경고 게이트의 dismiss 결정 주체를 정한다(사례는 작성자 메모) | `scripts/check_codeql_alerts.py` |
| 18 | M04 | process/collaboration-handoff | 사용자에게 넘긴 수동 단계가 13일 동안 다섯 번 틀렸다 — 끝난 일 재요구 · 꺾쇠 자리표시자 · 틀린 접속 값 · 옛 화면 경로(2회) | `CLAUDE.md` |
| 19 | M04 | decision | #1824 «결정 기록» 절에 머지 위임 부여 · 위험 수락(#1915) · Grok 규칙 결정이 없다 — 위임을 인용한 머지 57건의 근거를 GitHub 에서 찾을 수 없다 (L07 ✅ #1877 재발) | `CLAUDE.md` |
| 20 | M04 | decision | #1886 이 관리자 JSON API(/api/admin/operations 의 api_cost) 계약을 착수 전 확인 없이 바꾸고, 승인 기록에는 «결정 범위 안» 이라고 적었다 (L07 P2-45 ✅ #1877 재발) | `src/services/operations_service.py` |
| 21 | M04 | process | PR 본문 «사람이 확인할 것» 에 넣은 결정 질문이 답 없이 위임 머지됐다. #1855(대화 기록 보존 기간) · #1874(iOS 글꼴 한계) · #1880(P2-11 보류 사유 동의)은 사용자에게 한 번도 묻지 않았고 기본값이 그대로 결정이 됐다(원장 L07 P2-46 · P2-73 «무응답을 결정으로» 의 부류 재발) | `CLAUDE.md` |
| 22 | M04 | decision | 위임 머지가 PR 본문 «사용자 검증 필요» 의 질문을 답 없이 닫는다. 11-15~16 위임 머지 13건(#1880 외)에 사용자 판단을 묻는 질문 15개가 남았다. 그중에는 공급망 신뢰(#1884) · 한계 수락(#1874) · 결정 기록의 공개 범위(#1877) 가 있다 | `CLAUDE.md` |
| 23 | M04 | decision | 11-13 사용자가 승인한 semgrep 룰 교체 계획(B1)의 셋째 단계가 어디에도 추적되지 않는다. 서비스로 열기 전 다른 분석기 · 의존성 라이선스 점검과 «유료로 열기 전 전문가 확인» 이 원장 · Issue · 문서 검색 0건이고, 그 결정도 결정 기록 절에 없다 | `src/analyzer/io/tools/semgrep.py` |
| 24 | M04 | process | 결정 질문 51개에 장단점 표가 0개다 — 거의 다 «(Recommended)» 한 줄 선택지로 왔고, 사용자는 권장안이 있던 46개 중 44개를 그대로 골랐다 | `CLAUDE.md` |
| 25 | M04 | decision | 머지 뒤 사용자에게 넘긴 확인과 정리가 원장에 오르지 않고 사라졌다 — 원장 L04 는 #1838 을 «사용자 화면 확인 뒤» 로 닫았지만, 그 머지 기록은 «움직임이라 이미지에 안 담김 · 배포 뒤 확인 몫» 이다. 11-16 에 넘긴 정리 1건(내용은 작성자 메모)도 답 없이 남았다 | `CLAUDE.md` |
| 26 | M05 | supply-chain | semgrep 감사 예외의 제거 조건 (1)(«semgrep 이 수정판을 허용하면 즉시 지운다»)을 알리는 계기가 없다 — pip-audit 은 쓰이지 않은 예외를 말하지 않고, 예외는 5 → 8 로 늘기만 했다 | `scripts/semgrep_audit.py` |
| 27 | M05 | supply-chain | Dockerfile 이 받는 분석기 엔진은 어떤 갱신 · 권고 감시에도 걸리지 않는다 — golangci-lint 는 3년 전 v1(상류 v2.15.0), rubocop 1.57.2(상류 1.92.3), solc 0.8.20(상류 0.8.39) | `Dockerfile` |
| 28 | M05 | supply-chain | 서비스 토큰을 받는 서드파티 action 둘이 가변 태그다 — codecov-action@v7(CODECOV_TOKEN) · sonarqube-scan-action@v8(SONAR_TOKEN), 공개 리포라 실행 로그도 공개 | `.github/workflows/ci.yml` |
| 29 | M05 | tooling | Dependabot production-deps 묶음이 semgrep 을 앱 운영 의존성과 한 PR 에 싣는다. semgrep 권고 때문에 앱 갱신 8개가 든 #1912 가 두 번 red 가 되어 약 5시간 막혔다. #1857 이 끊은 결합이 묶음 설정으로 다시 생겼다 | `.github/dependabot.yml` |
| 30 | M05 | tooling | 운영 이미지와 CI 가 수명이 끝난 Node.js 20(EOL 2026-04-30)으로 돈다. 운영 eslint 분석기가 분석 대상 코드를 이 런타임 위에서 처리하는데, Dockerfile 주석이 major 를 CI 와 묶어 두어 둘 다 그대로다 | `Dockerfile` |
| 31 | M05 | tooling | 앱 venv 의 전이 의존 약 99개에 새 CVE 가 나와도 잡는 예약 실행이 없다. Dependabot 의존성 그래프에는 직접 핀 34개만 있고, codeql.yml 은 주간 CodeQL 을 «의존성 CVE 감지 목적» 이라고 적어 두었다 | `.github/workflows/codeql.yml` |
| 32 | M05 | tooling | semgrep 감사 예외 가운데 «semgrep 내부» 전제는 핀을 올려도 다시 재지 않는다. #1860(1.184.0→1.185.0)은 배지 커밋 하나만 붙은 채 머지됐고, 재측정은 6일 뒤 새 권고가 감사를 막은 #1912 때에야 했다 | `scripts/semgrep_audit.py` |
| 33 | M05 | process | 의존성 보류 추적처 #1733 의 표가 실제 감사 예외와 어긋난다 — CVE-2026-126360 행이 11-13 부터 없고, 확인 명령은 옮겨 간 ci.yml 과 이제 예외가 없는 앱 감사를 가리킨다 | `.github/dependabot.yml` |
| 34 | M05 | docs | 보류 · 감사 예외 추적처 #1733 의 표가 #1857/#1863 뒤 코드와 다르다 — 넷은 ci.yml 을 가리키고 확인 명령은 공허하며, CVE-2026-126360 은 행이 없다 | `scripts/semgrep_audit.py` |
| 35 | M05 | tooling | CodeQL이 GitHub가 감지한 언어 가운데 python만 분석한다. 워크플로(actions)와 템플릿 인라인 JS는 어떤 강제 SAST에도 걸리지 않는다 | `.github/workflows/codeql.yml` |
| 36 | M06 | analyzer drift guard · semgrep | R-8 semgrep 출력 스키마 드리프트 가드가 CI 에서 영구 skip — 존재 이유인 판올림 두 번(1.185.0 · 1.186.0)을 한 번도 재지 않았고, 로컬은 남은 1.184.0 을 잰다 | `tests/unit/analyzer/tools/test_semgrep_scan_completeness.py` |
| 37 | M06 | test-design · 부정 통제 공허화 | CI 상태(semantic_version 부재)에서 pragma 부정 통제 5건이 폴백으로 초록 — skip 수로는 보이지 않는 공허화라 뒤집기 쌍이 통째로 사라졌다 | `tests/unit/analyzer/tools/test_slither.py` |
| 38 | M06 | 검증 양식 — semgrep 출력 스키마 계약 | semgrep «규칙이 끝까지 못 돎» 이름을 semgrep 자체 스키마와 대조하는 유일한 시험이 #1857 뒤 CI 에서 영구 skip — semgrep 1.185.0(#1860) · 1.186.0(#1912) 판올림이 대조 없이 머지됨 | `tests/unit/analyzer/tools/test_semgrep_scan_completeness.py` |
| 39 | M06 | 문서 · 주석 · 메모리 drift | slither docstring · 시험 주석 · skip 사유 · 메모리 처방이 #1857 뒤 거짓인데 head 까지 그대로 | `src/analyzer/io/tools/slither.py` |
| 40 | M06 | 검증 양식 — 이미지 안 분석기 오라클(#1832) | 분석기 오라클은 이 회귀를 원리적으로 못 본다 — Solidity 시료가 pragma 0.8.20 이고, 못 맞추는 시료를 넣으면 회귀 전후 모두 «잴 수 없다»(exit 2) | `scripts/analyzer_oracle.py` |
| 41 | M06 | docs | 새 PC 설정 절차가 약속한 환경을 만들지 못한다 — #1857 뒤 semgrep(조달 계약 분석기)이 사람용 설치 절차 어디에도 없고, pre-commit 은 어떤 requirements 에도 없다 | `Makefile` |
| 42 | M07 | process/ledger-hygiene | 원장 #1824 본문이 GitHub 상한의 97.7%(64,027/65,536자) — «▶️ 다음» 줄이 완료 이력 19건(2,793자)을 쌓는 이력 로그가 됐다 (심각도 조정 P1→P2) | `.claude/skills/retrospective/SKILL.md` |
| 43 | M07 | docs | 원장 #1824 의 «▶️ 다음» 줄이 2,797자 완료 기록부가 됐다 — 실제 다음 할 일은 첫 문장뿐이다 | [WBS] #1824 (GitHub Issue 진입점 «다음» 줄) |
| 44 | M07 | docs | 항상 로드되는 메모리 진입점 줄에 이미 풀린 금지(«DB 비밀번호 3개 회전 전에는 보고서 게시 금지»)가 11일째 남아 있다 — 이번 회고 보고서 게시가 다음 일이다 | (메모리) MEMORY.md |
| 45 | M07 | process | 원장 L13 P2-26(✅ #1845)이 걷은 «본문 red → 빈 커밋» 처방이 항상 로드되는 MEMORY.md:30 과 그 메모리 파일에 그대로다 — 근거로 든 verify.md 4번은 반대를 말한다 | (메모리) MEMORY.md |
| 46 | M07 | decision | 정식 회고 워크플로(예상 에이전트 약 170 · 약 10시간 · 약 2,800만 토큰)를 포괄 승인으로 띄웠다 — 스킬이 정한 «실행 전 예상 비용 1줄 보고» 는 디스패치 46초 뒤에 나왔고, 자율 판단 보고는 «규칙대로 보고하고 바로 실행» 이라 적었다 | `.claude/skills/retrospective/SKILL.md` |
| 47 | M08 | process/ssot-policy | README FastAPI 배지가 의존성 판을 복사하고 가드가 그 복사를 강제한다 — Dependabot PR 마다 손 커밋이 필요했다(창 안 2회) | `scripts/check_docs_sync.py` |
| 48 | M08 | automation | README FastAPI 배지(의존성 판 사본)를 CI 가 강제해, FastAPI minor 를 올리는 Dependabot PR 은 혼자 초록이 못 된다 — 창의 두 번 모두 봇 브랜치에 사람 커밋이 필요했다 | `scripts/check_docs_sync.py` |
| 49 | M08 | process/doc-policy | «문서 총량은 늘리지 않는다» 인데 창 안 문서가 +4,731자(+6.7%) — 직전 창(+815)의 5.8배, doc-growth 18건 중 9건이 «뺀 것 없음» | `CLAUDE.md` |
| 50 | M08 | docs | «문서 총량은 늘리지 않는다»를 재기 시작한 뒤 8일 동안 +4,012자 — 늘린 17건 중 12건이 «뺀 것 없음». 규칙 문구와 실측이 갈라졌다 | `CLAUDE.md` |
| 51 | M08 | code | 스케줄러 주석의 cron 경로 수 «7종» 이 #1906 뒤로 8종이 됐는데 고쳐지지 않았다 — 모듈 머리의 «job 5종» 도 07-19 부터 낡아 있다 | `src/scheduler.py` |
| 52 | M08 | docs | architecture.md «인앱 JOBS 7»과 scheduler.py 주석 «cron 경로 7종»이 #1906 뒤로 틀렸다 — 실제로는 8개다 | `docs/architecture.md` |
| 53 | M08 | docs | README · STATE 의 수 사본은 대부분 시험 밖이다 — 언어 수(49 · 25)는 대조 0곳, 분석기 수는 README 마다 3곳 중 1곳만. #1827 이 이 모양으로 «27» 4곳을 남겼다 | `README.md` |
| 54 | M08 | docs | README «25 with a static analyzer» 목록에는 출하 이미지가 분석하지 않는 7언어가 섞여 있다 — #1827 이 php · rust 의 유일한 출하 분석기를 빼 이 무리에 넣었고, #1828 은 수만 고쳤다 | `README.md` |
| 55 | M08 | docs | Makefile 주석에 테스트 수 사본(«slow 154개»)과 틀린 범위(«통합 테스트가 semgrep 을 돌린다»)가 남아 있다 — L20(#1862 «테스트 수를 문서에서 걷는다»)이 놓친 사본이고 지금 수집은 247건이다 | `Makefile` |
| 56 | M09 | process/policy-text | 사용자가 정한 에이전트 자율 재배포 경로(L02 A안 · scripts/railway_redeploy.py)가 항상 읽히는 규칙과 배포 절차 어디에도 없다 — CLAUDE.md 는 «배포는 사용자가 !» 라고만 한다 | `CLAUDE.md` |
| 57 | M09 | docs | L02 «운영은 행위로 가른다»가 문서 표면에 반만 옮겨졌다 — 에이전트의 유일한 자율 배포 경로는 배포 문서에 없고, PR 템플릿은 반증된 «SELECT-only 자율»을 아직 가르친다 | `docs/workflow/deploy.md` |
| 58 | M09 | docs | SECURITY.md 의 Telegram 끄는 법(«unset TELEGRAM_BOT_TOKEN»)을 따르면 앱이 기동하지 않는다 — 같은 필수 설정 사실의 사본은 이 창에서 늘었다 | `SECURITY.md` |
| 59 | M09 | docs | CONTRIBUTING 의 «Pre-commit enforces: new src/ file → architecture.md» 는 기존 패키지 안의 새 파일에 거짓이다 — 창의 새 src 파일 6개가 전부 가드 밖이었고 2개는 architecture.md 에 흔적이 없다(원장 L18 P2-14 ✅ #1849 는 files 정규식만 고쳤다) | `CONTRIBUTING.md` |
| 60 | M09 | docs | CONTRIBUTING «핀 · pylint 값은 커밋 때가 아니라 CI · 로컬 게이트에서 잰다» 는 사실과 반대다 — 커밋 때 pre-commit check-docs-sync 가 같은 검사를 돈다(#1862) | `CONTRIBUTING.md` |
| 61 | M09 | docs | PR 템플릿에 CI 가 요구하는 본문 줄이 없다 — 없으면 비봇 PR 이 red 가 되는 `pytest tests/unit → N passed / M skipped`(#1862 뒤 유일한 자리)와 `doc-growth:`(#1867) | `.github/PULL_REQUEST_TEMPLATE.md` |
| 62 | M09 | docs | db.md «운영 연결의 세션 설정»(#1873 · 11-16)이 나흘 먼저 머지된 DB 하트비트(#1821 · 11-12)를 모른다 — 앱이 1분 안에 스스로 고치는 경우의 수동 RESET 만 적고, 하트비트가 경보로 넘기는 남은 경우에는 절차가 없다 | `docs/workflow/db.md` |
| 63 | M09 | docs | 지워진 규칙 문서를 인용한 근거가 리포 곳곳에 남아 있다 — 원장 K21 P2-40 ✅ #1883 이 지목된 파일(check_architecture_tree_sync.py)의 AGENTS.md 인용을 그대로 두었고, 새 가드는 구조상 루트 파일 · 맨 이름 · 번호 정책 인용을 보지 못한다 | `scripts/check_architecture_tree_sync.py` |
| 64 | M09 | docs | README 배포 절이 «대시보드 설정 둘» 이라고 적는데, #1904 뒤로 셋째(Draining time 120초)가 생겼다 — README · README.ko 어디에도 없다 | `README.md` |
| 65 | M09 | docs | TOKEN_ENCRYPTION_KEY 를 바꾸면 무엇이 깨지는지가 코드 주석 · PR 본문에만 있다 — 이 창에서 실제로 키를 바꿨는데(원장 R-16) 런북에는 «환경변수 교체» 한 줄뿐이다 | `docs/runbooks/secret-prevention.md` |
| 66 | M09 | docs | verify.md 의 push 절차는 단위 전체를 두 번 돌리게 적혀 있고(1단계 + 2단계 --full), CLAUDE.md 는 --full 을 «pylint·bandit 추가» 로만 적는다 — 실제 기록에서 --full 은 224회 중 39회 | `docs/workflow/verify.md` |
| 67 | M09 | docs | 문서 심의 훅을 지우며 대안으로 정한 «문서 심의 에이전트 3종»은 부르는 자리가 없고, 호출은 0번이며, 프롬프트는 없는 CLAUDE.md 절을 기준으로 삼는다 | `.claude/agents/doc-impact-analyzer.md` |
| 68 | M10 | code | boost 이동의 «앱 화면이 아니면 전체 이동»(#1840)이 세션 만료 뒤 로그인 리다이렉트를 덮지 못한다 — 링크를 눌러도 진행 막대만 잠깐 돌고 화면이 그대로다 | `src/templates/base.html` |
| 69 | M10 | code | 이슈 등록 모달: 한 건을 등록하고 나면 «등록» 버튼이 «생성 중…» 인 채 비활성으로 남아, 같은 화면에서 두 번째 등록이 안 된다. 창 안에서 #1841·#1893 이 이 모달을 두 번 고쳤지만 등록 흐름은 시험 밖이다 | `src/templates/analysis_detail.html` |
| 70 | M10 | code | 슬롯 대기 전 흔적(#1871)의 시작 시각이 큐 대기 시간까지 «소실 경과» 로 센다. 30분 넘게 줄 선 파이프라인은 아직 살아 있는데 고아 정리가 «분석 소실 — 재-push 하라» 고 알리고 흔적을 지운다 | `src/worker/pipeline.py` |
| 71 | M10 | code | i18n 문구가 이 창의 화면 · 요율 변경을 따라가지 않았다. 보안 화면 영역 이름은 아직 «Security audit 4 카드» 인데 실제 카드는 3장이고, 운영 화면은 «read = 0.1×» 라고 적지만 캐시 읽기 요율은 이제 판마다 다르다 | `src/i18n/translations/ko.json` |
| 72 | M11 | code | 공용 Claude 호출 도우미가 서버 대체 호출의 400 을 원인과 상관없이 «대체 인자 거부» 로 보고, 그 모델의 서버 대체를 재시작 때까지 끈다 — 지출 한도 400 에도 같은 경고와 같은 비용 행 라벨이 남는다 | `src/shared/claude_call.py` |
| 73 | M11 | code | 인사이트 호출이 리뷰용 effort 기본값(high)을 1500 토큰 출력 상한과 함께 보낸다 — #1908 이 «④ 전에 정한다» 고 미룬 선결 조건이 [WBS] #1905 의 ④ 항목에 없다 | `src/services/dashboard_service.py` |
| 74 | M11 | code | 모델 카탈로그의 재시작 기준(비용 기록 → 검증판)이 첫 목록 동기화 «뒤»에 한 번만 돈다. 기동 때 목록 API 가 실패하면 대체 카탈로그에 없는 검증판은 버려진 채 bootstrapped=True 가 되고, 최대 6시간 auto:<계열> 이 옛 판으로 돈다. 그 뒤 동기화는 같은 판을 다시 시험하고 «promoted» 로 알린다 | `src/services/model_catalog_service.py` |
| 75 | M11 | code | 인사이트 하루 한도 문구는 «AI 인사이트 {cap}회를 모두 썼습니다» 라고 기능별 생성 수처럼 말하지만, 실제로는 대시보드 인사이트와 리포 진단 두 기능의 Claude 호출 «행» 을 함께 센다. #1908 뒤로 한 번의 생성이 2행 이상이 되기도 한다 | `src/services/insight_cost_guard.py` |
| 76 | M11 | code | 비동기 인사이트 자리(#1896 · #1899)의 기록 캐시 동작을 정한다(상세는 작성자 메모) | `src/templates/dashboard.html` |
| 77 | M11 | code | 하루 한도의 «마지막 결과 보여 주기»(#1872)를 매일 20:00 UTC 보존 정리가 지운다. 정리 함수는 «만료 행은 지워도 손실 0» 이라는 #1872 이전 전제를 그대로 따른다 | `src/repositories/insight_narrative_cache_repo.py` |
| 78 | M11 | docs | 진행 중 원장 #1905(진입점)의 설계 §4 가 구현과 어긋난다(CLAUDE_EFFORT · 기본 medium), 요율 갱신 절차(§6)는 리포 문서 어디에도 없다 | [WBS] #1905 (GitHub Issue 본문 §4 · §6) |
| 79 | M11 | docs | gate-notify.md «페이지 Claude 호출 — 다섯 다 넣는다»에 이 창의 유료 호출 계약 넷이 빠져 있다 — 공용 도우미 규칙은 영역 표가 보내지 않는 pipeline.md 에만 있다 (심각도 조정 P1→P2) | `docs/workflow/gate-notify.md` |
| 80 | M12 | code | CodeQL note 가 push 뒤에야 잡혀 고침 커밋이 붙은 PR 이 9건이다 — 메모리에 처방이 있던 규칙과 창 안에서 이미 고친 규칙이 다시 났고, 로컬 · CI 의 diff 린트는 F401/F841 만 본다 | `scripts/pre_push_gate.py` |
| 81 | M12 | tooling | required 잡이 실행마다 Ubuntu apt 미러에서 도구를 받는데 재시도도 캐시도 없다. 11-11 러너 DNS 장애로 main CI 가 4회 연속 red 였고, #1819 배포가 SKIPPED 되고 PR 두 건이 막혔다(원장에 기록 없음) | `.github/workflows/ci.yml` |
| 82 | M12 | tooling | 편집 보호 훅이 «검증 가능한 환경»으로 안내하는 Codespaces 정의가 05-10 그대로다. 그래서 #1848(11-15) 뒤로 그 환경에서는 앱이 뜨지 않는다 | `.devcontainer/devcontainer.json` |

## 오탐 (다음 회고가 다시 판정하지 않도록)

| 관점 | 제목 | 기각 사유 |
|---|---|---|
| process | «사용자에게 쓰는 말은 한국어» 가 11-15 머지 위임 첫날 약 6시간 깨졌다. 턴 끝 보고 20건(위임 머지 계획 · 첫 위임 머지 요약 포함)이 영어였고, 사용자가 «한글로 알려주세요» 로 바로잡았다(05-11 에 이은 두 번째 요청) | 사건은 실제로 있었지만 새 결함이 아니다 — 원장 #1824 P2-58(✅ #1875)과 같은 결함이고 이미 해소됐다 |

## 묶음 — 원장은 `[WBS]` #1917

확정 100건을 원인 12묶음으로 나눴다. 같은 결함을 여러 관점이 따로 확정한 경우가 있다
(예: M01 의 주 체크아웃 문제 · M06 의 slither pragma 회귀 · M08 의 FastAPI 배지).

| 묶음 | P1 · P2 | 주제 |
|---|---|---|
| M01 | 4 · 2 | 훅 · 설정이 세션에 닿는 길 — 주 체크아웃 · 신호 전달 · 훅 출력 |
| M02 | 3 · 6 | 운영 접근 · 비밀값 차단면 — 훅 정밀도 · 예외 처리 · 문서 처방 · 스캐너 |
| M03 | 1 · 9 | 머지 승인 · 관문 — 승인 head · 시각 확인 · 위임 범위 · Grok 판정 · 게이트 해제 |
| M04 | 3 · 8 | 결정 · 사용자 몫의 기록면 — 보류 · 무응답 · 질문 방식 · 넘긴 확인 |
| M05 | 1 · 10 | 공급망 · 의존성 감시 — 전이 핀 · 감사 예외 · 분석기 엔진 · 런타임 |
| M06 | 6 · 6 | #1857 의존성 이동의 뒷면 — slither pragma 회귀 · CI 영구 skip · 선언 안 된 import |
| M07 | 0 · 5 | 원장 · 메모리 · 회고 계기 위생 |
| M08 | 0 · 9 | 문서 수 사본 · 총량 — 배지 · 개수 · 시험 수 |
| M09 | 0 · 12 | 절차 · 규칙 문서의 사실 오류 |
| M10 | 0 · 4 | 앱 동작 — 화면 · 워커 |
| M11 | 0 · 8 | Claude 호출 · 비용 · 모델 카탈로그 |
| M12 | 0 · 3 | CI · 로컬 게이트 계기 |

## 다음 회고를 위한 경계

- 다음 범위의 하한은 **이 리포트를 추가한 커밋** 이다.
- 운영 접근 · 비밀값 인용 · 쓰기 금지는 계속 디스패치 브리프에 적는다 — 이번 실행은 브리프만으로 세 축이 0 이었다.
- 실행 시간 예상은 두 실측에서 출발한다 — 121 에이전트 · 5h10m(이번) · 191 에이전트 · 10h42m(직전). 차이는 표적 라운드 크기다.
- 예상 비용 1줄 보고는 디스패치 **전**에 한다(M07 P2-46).
- 🔴 이 리포트를 추가하면 단위 테스트가 2건 는다 — `tests/unit/scripts/test_gate_claim_consistency.py` 가 문서마다 파라미터화한다.
