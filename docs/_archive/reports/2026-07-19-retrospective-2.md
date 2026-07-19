# 5+1 회고 (2차) — 2026-07-19 — 회고 수행 세션 자신의 산출물

> 정책 8 진화 (4) **회고 카덴스 강제 트리거** 발화로 진입 — 직전 정식 회고([2026-07-18](2026-07-18-retrospective.md)) 이후 머지 **22 PR**(#1078~#1101), 임계 ≥15.
> 실행 = `.claude/workflows/retrospective.mjs` (loop-until-dry + 전건 cross-verify).

## 실행 요약

| 항목 | 값 |
|------|-----|
| 에이전트 | **168** |
| 라운드 | 3 (+ completeness gap 라운드) |
| 총 finding | 147 |
| **확정(confirmed)** | **134** |
| false-positive | 13 |
| verdict 커버리지 | **100%** (전건 검증 — 미검증 0) |
| 총 토큰 | 15,211,539 |
| 총 tool call | 2,703 |

**심각도 분포**: **P0** 8건 · **P1** 51건 · **P2** 75건

**관점 분포**: docs 33 · process 19 · code 19 · tooling 19 · decision 11 · security 8 · tooling / owed 원장 집행면 5 · security/process 2 · decision / security-verification 2 · process/docs 2 · 미검증 양식 2 · memory / 자동 로드 컨텍스트 2 · security/code 1 · process/governance 1 · process/policy 1 · retro-finding remediation 1 · tooling / 검증 방법론 (음성 결과) 1 · correctness 1 · security / 미검증 주장 1 · 원장 정합성 / 자동 로드 컨텍스트 1 · 원장 정합성 1 · 회고 프로세스 / 범위 정의 1

**verdict 분포**: CONFIRMED 78 · SEVERITY_ADJUST 56

### cross-verify ROI (정책 8 진화 (2) — 정량 명시 의무)

| 지표 | 값 |
|------|-----|
| fp_blocked | 13 |
| confirmed | 134 |
| severity_adjusted | 56 |
| p0 | 8 |
| p1 | 51 |
| p2 | 75 |

---

## 🔴 P0 (11건)

> 본 세션이 **이미 수정한 항목**은 PR 번호를 병기한다. 미조치 항목은 🔺 로 표시.

### P0-1. [security/code] #1104 의 '2계층' 리댁션이 uvicorn 트레이스백을 전혀 덮지 못함 — 봇 토큰 유출 경로가 미봉인 잔존

- **위치**: `src/logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter` 는 `record.getMessage()` 만 치환하므로 `exc_info` 트레이스백을 리댁션하지 못하고, 필터가 붙은 root 핸들러는 uvicorn 로거 레코드를 애초에 보지 못한다. `src/webhook/providers/telegram.py:242` 의 `background_tasks.add_task(telegram_post_message, ...)` 는 예외 가드가 전혀 없어, Telegram API 오류 시 uvicorn 이 토큰이 박힌 URL 을 평문 트레이스백으로 남긴다. #1104 가 '봉인' 을 선언한 바로 그 credential 이다.
- **권고**: (1) `src/webhook/providers/telegram.py:242`(및 :330) 를 `except httpx.HTTPError` 로 감싸 `type(exc).__name__` 만 로깅 — 다른 8개 호출처와 동일 패턴. (2) 리댁션을 필터가 아니라 **Formatter 서브클래스**로 올려 `formatException()`/`exc_text` 까지 치환하고, 그 Formatter 를 uvicorn 핸들러에도 부착. (3) 회귀 가드에 `logger.exception(..., exc_info=<httpx 에러>)` 케이스 추가 — 현재 `tests/unit/test_logging_config.py` 6건은 전부 msg 경로만 검증한다. (4) 이 항목이 미해결인 채로 TELEGRAM_BOT_TOKEN 로테이션(#1104 원장 행)을 수행하면 **신규 토큰이 같은 경로로 재유출**되므로, 로테이션 전 수정 권장.

### P0-2. [decision / security-verification] #1104 리댁션이 예외 traceback 을 놓친다 — Telegram 알림 실패 시마다 봇 토큰이 여전히 평문 유출 (재현 완료)

- **위치**: `src/logging_config.py:123`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter` 는 `record.getMessage()` 결과만 `record.msg` 로 덮어쓰므로, `logging.Formatter` 가 별도로 렌더링하는 `record.exc_info` traceback 은 마스킹되지 않는다. 운영 경로 `src/worker/pipeline.py:716-717` 이 `exc_info=(type(exc), exc, exc.__traceback__)` 로 알림 실패를 로깅하므로, Telegram 전송이 실패할 때마다 `httpx.HTTPStatusError` 의 traceback 꼬리에 토큰이 그대로 남는다. 이는 #1104 가 봉인했다고 선언한 바로 그 유출이며, 사용자에게 요청 중인 `TELEGRAM_BOT_TOKEN` 로테이션(원장 #1104 행)까지 무력화한다 — 새 토큰도 첫 실패 전송에서 동일하게 유출된다. 심각도 근거: ERROR 레벨이라 계층 1(httpx→WARNING) 사정권 밖이고, 계층 2 가 유일 방어선인데 그 방어선이 뚫린다.
- **권고**: `_RedactSecretsFilter.filter()` 에서 `record.exc_info` 도 처리한다. 가장 단순한 방법은 예외가 있으면 `logging.Formatter().formatException(record.exc_info)` 를 마스킹해 `record.exc_text` 에 미리 채워 넣는 것(Formatter 는 `exc_text` 가 이미 있으면 재생성하지 않는다). 회귀 가드는 반드시 `exc_info` 를 동반한 레코드로 작성하고, 단언 대상은 `record.msg` 가 아니라 **핸들러 최종 출력 전문**이어야 한다 — 현재 6건의 신규 가드가 전부 exc_info 없는 레코드만 검사해 이 경로를 통과시켰다. 원장 #1104 로테이션 행에 '본 수정 배포 후 로테이션' 선후관계를 명시해야 새 토큰 재유출을 막는다.

### P0-3. [code] #1104 리댁션이 exc_info 트레이스백을 통과시킨다 — 봇 토큰·웹훅 시크릿이 운영 알림 실패 경로에서 여전히 평문 기록

- **위치**: `D:\Source\SCAManager\src\logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter` 는 `record.msg`/`record.args` 만 마스킹하고 `record.exc_info` 를 손대지 않는다. `logging.Formatter.format()` 이 `formatException(record.exc_info)` 를 원문 그대로 덧붙이므로, 예외 메시지에 시크릿이 있으면 **메시지 줄은 마스킹되고 트레이스백 줄에는 평문이 남는다**. 이 경로는 SCAManager 의 알림 실패 처리에서 상시 발화한다.
- **권고**: 리댁션을 Filter 가 아니라 Formatter 계층으로 옮기거나(`format()` 오버라이드로 최종 문자열에 패턴 적용), 최소한 filter 에서 `record.exc_info` 를 `logging.Formatter().formatException()` 으로 미리 렌더 → 마스킹 → `record.exc_text` 에 넣고 `record.exc_info = None` 처리한다. `stack_info`/`record.stack_info` 도 동일. 회귀 가드로 `logger.error(..., exc_info=...)` 케이스 1건을 tests/unit/test_logging_config.py 에 추가(현재 exc_info 커버리지 0).

### P0-4. [tooling] credential 유출 벡터(Bash stdout)에 훅 커버리지 0 — 회고가 2번 권고한 시정 (3)이 누락되고, 남은 유일한 사본은 기계가 침묵시키는 행에 있다

- **위치**: `.claude/settings.json:22`
- **verdict**: CONFIRMED
- **주장**: 정책 12 위반을 일으킨 실제 경로(Bash 명령 출력 → 대화 기록)는 기계 집행면이 전무하다. 훅 matcher 는 `Write|Edit|MultiEdit`(PreToolUse) · `Write|Edit`(PostToolUse) · `startup|resume`(SessionStart) 뿐으로 **`Bash` matcher 가 프로젝트·전역 settings 어디에도 없다**. 회고가 P0-10·P0-11 에서 **두 번** 권고한 `.claude/rules/security.md` 등재는 수행되지 않았고, 이후 ⏳→⏭️ 재분류로 산문마저 기계 감시 밖으로 나갔다.
- **권고**: 회고 권고 (3) 자체가 불충분했다는 점이 더 깊은 발견이다 — `.claude/rules/security.md` 는 path-scoped(`paths: src/auth/**, src/crypto.py, ...`) 라 **파일을 건드리지 않는 `railway variables` Bash 호출에는 영원히 로드되지 않는다**. 올바른 표면은 (a) Bash PreToolUse 훅 — `railway variables`/`printenv`/`env` 계열에 `--kv` + `grep` 조합 탐지 시 차단 또는 경고, 혹은 (b) CLAUDE.md 본문(무조건 로드). ⏭️ 행에 재발 방지책을 묻어두는 현 상태는 '인지 의존 산문' 5회차이며, ⏭️ 가 훅에서 침묵되므로 4회차보다 오히려 후퇴다.

### P0-5. [process] credential 유출 재발방지 규칙이 회고 권고를 어기고 ⏭️ 로 '닫힌' 원장 행에만 기록 — 인지 의존 산문 5회차

- **위치**: `docs/runbooks/owed-verification.md:54`
- **verdict**: CONFIRMED
- **주장**: 정책 12 위반(Railway 변수 값 평문 노출)의 재발방지 규칙이 회고가 명시 권고한 `.claude/rules/security.md`(path-scoped·자동 로드) 대신, **기계 스캔에서 제외된 ⏭️ 상태의 원장 표 셀** 과 commit body 에만 남았다. 직전 회고가 P0 로 규정한 '인지 의존 산문'(4회차)을 같은 세션에 재생산한 5회차이며, 구조적으로는 이전 4회보다 나쁘다 — ⏭️ 는 카운터의 스캔 집합에서 빠지고 원장 자신의 규칙이 아카이브 이동 대상으로 지정하기 때문이다.
- **권고**: 규칙 1줄을 `.claude/rules/security.md` 본문에 등재(회고 권고 그대로 이행). 원장 셀은 참조로 남기되 정본을 rules 로 옮긴다. 아울러 `check_owed_verification.py` 또는 별도 가드에 '⏭️ 행 본문에 재발방지 규칙 서술이 있으면 해당 규칙이 `.claude/rules/**` 에도 존재하는지' 대조를 넣어 5회차 패턴을 기계로 봉인 — 문서-only 시정이 4회 실패한 영역이므로 또 한 번의 산문 시정은 근거가 없다.

### P0-6. [code] #1104 리댁션 필터가 예외 traceback 을 검사하지 않아 Telegram 봇 토큰이 여전히 평문 유출 (재현 확인)

- **위치**: `src/logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter.filter()` 는 `record.getMessage()`(msg+args) 만 검사한다. `exc_info`/`exc_text` 는 filter 실행 **이후** `Formatter.format()` 이 붙이므로 리댁션을 완전히 우회한다. httpx 의 `raise_for_status()` 예외 메시지는 `for url '<full URL>'` 형태로 **봇 토큰 전문**을 포함하므로, Telegram 알림이 4xx/5xx 로 실패할 때마다 토큰이 그대로 Railway 로그에 남는다. #1104 가 봉인했다고 단언한 바로 그 결함 클래스가 살아 있다.
- **권고**: `_RedactSecretsFilter.filter()` 에서 `record.exc_info` 가 있으면 `record.exc_text` 를 미리 생성(`logging.Formatter().formatException`)한 뒤 동일 정규식을 적용하고, `record.exc_text` 에 마스킹 결과를 대입한다(Formatter 가 `exc_text` 캐시를 재사용하므로 유효). `record.stack_info` 도 동일 처리. 회귀 가드는 `logger.exception`/`exc_info=` 경로에서 **핸들러 최종 출력**에 토큰이 없음을 단언해야 한다 — 현 6건 가드에는 `exc_info` 시나리오가 전무하다(`grep -n exc_info tests/unit/test_logging_config.py` = 0건).

### P0-7. [tooling] credential 유출 재발 방지책이 원장 표 셀 산문 단독 — 프로젝트 settings.json 에 permissions 키 자체가 부재 (인지 의존 산문 5회차, 자기 진단 1커밋 후 재생산)

- **위치**: `docs/runbooks/owed-verification.md:54`
- **verdict**: CONFIRMED
- **주장**: 본 세션이 정책 12 를 위반해 `INTERNAL_CRON_API_KEY` 를 평문 출력한 뒤, #1106 은 **로테이션 의무**만 기계 집행면(owed 원장 안전등급 표)에 등재했고 **유출 행위 자체의 재발 방지**는 기계면에 전혀 배선하지 않았다. a810e15 커밋 본문은 이를 명시적으로 승인한다 — "🔴 재발 방지책은 코드와 무관하게 **항구 적용**으로 남긴다: `railway variables --kv` 결과를 grep 하지 말고 `cut -d= -f1` 로 이름만 추출." 이 문장의 저장소 내 유일한 소재지는 `docs/runbooks/owed-verification.md:54` 표 셀 안이며, 그 행은 같은 커밋에서 ⏳→⏭️ 로 바뀌어 SessionStart 훅 경고 대상에서 제외됐다(실행 확인: 안전등급 3건→1건). 즉 로테이션 의무는 기계면에 올렸다가 사용자 결정으로 내려왔고, 재발 방지책은 애초에 기계면에 오른 적이 없으며 이제 훅이 읽지 않는 ⏭️ 행 본문에만 남았다. 배선 가능한 집행면이 실재하는데 사용되지 않았다: 프로젝트 `.claude/settings.json` 의 top-level 키는 `['hooks']` **단 하나** — `permissions` 키 자체가 없고, `deny` 규칙 0건이며, `hooks` 3종(SessionStart·PreToolUse `Write|Edit|MultiEdit`·PostToolUse `Write|Edit`) 어디에도 **Bash matcher 가 존재하지 않는다**(grep 실측: `Bash` 0건). 명령 실행 계층에 대한 기계 가드가 저장소 전체에 0건이다. 이는 본 세션이 #1106 커밋 본문에서 스스로 P0 로 인용한 회고 지적 — "의무를 사용자 로컬 메모리에 둔 것 = 이번 세션이 **두 번 유죄 선고한** '인지 의존 산문' 시정의 **4회차**" — 을 그 시정 커밋의 바로 다음 커밋에서 5회차로 재생산한 것이다.
- **권고**: 재발 방지를 산문에서 기계면으로 이동한다 — `.claude/settings.json` 에 `permissions.deny` 신설 후 `Bash(railway variables:*)` · `Bash(*--kv*)` 등 값 덤프 명령 클래스를 등재(update-config 스킬 적용 영역), 또는 PreToolUse 에 `Bash` matcher 훅을 추가해 시크릿 덤프 패턴을 advisory 차단한다. ⏭️ 로 내려간 로테이션 행과 무관하게 재발 방지는 상시 집행면에 있어야 한다(⏭️ 는 '이번 노출의 위험 수용'이지 '다음 노출의 허용'이 아님). 회귀 가드 = settings.json 의 deny 규칙 존재를 단언하는 테스트(`tests/unit/scripts/test_session_start_wiring.py` 가 채택한 '산문이 아니라 실행 기전을 단언' 패턴 동일 적용).

### P0-8. [security / 미검증 주장] #1104 리댁션이 예외 트레이스백을 못 막는다 — 사용자의 로테이션 거절이 거짓 전제 위에 서 있다

- **위치**: `src/logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter` 는 `record.getMessage()`(msg+args)만 마스킹하고 `record.exc_info`/`exc_text` 는 손대지 않는다. `src/notifier/telegram.py:91` 의 `r.raise_for_status()` 가 던지는 `httpx.HTTPStatusError` 메시지에는 봇 토큰이 든 요청 URL 전문이 포함되며, 이를 `logger.exception` 으로 받는 라이브 경로가 최소 3개다. 계층 1(httpx→WARNING)도 무력 — 유출 주체가 httpx 로거가 아니라 **우리 로거**이기 때문. 따라서 '#1104 가 향후 유출을 이미 차단' 이라는 원장 :53 의 위험 수용 근거 ①이 거짓이고, 그 근거로 사용자가 TELEGRAM_BOT_TOKEN 로테이션을 명시 거절(#1108)했다. 안전등급 결정이 잘못된 사실 위에 확정된 상태다.
- **권고**: (1) `_RedactSecretsFilter.filter` 에 `record.exc_info`/`record.exc_text` 리댁션 추가 — `record.exc_text` 를 미리 포맷(`logging.Formatter.formatException`)해 패턴 치환 후 `record.exc_info=None` 로 재포맷 차단하거나, 더 근본적으로 (2) `telegram_post_message` 에서 `raise_for_status()` 대신 상태코드만 담은 자체 예외를 던져 URL 을 예외 메시지에서 제거. (3) 회귀 가드 = `logger.exception` 경로 토큰 미노출 단언 테스트 신설. (4) 수정 전까지 원장 :53 의 위험 수용 근거 ①을 정정하고 사용자에게 재결정 요청 — 로테이션 거절은 '유출이 멈췄다' 전제였다.

---

## P1 (51건)

### P1-1. [security/process] 리댁션 패턴이 Telegram 1건뿐 — Slack/Discord/n8n webhook URL(=credential 자체)은 우리 코드가 평문 로깅 (정책 16 grep 전수 미이행)

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS` 는 항목이 정확히 1개(telegram)다. 그런데 저장소 안에 구조적으로 동일한 'secret-in-URL-path' 채널이 4개 더 있고, 그 URL 전문을 **우리 코드가 WARNING 으로 직접 로깅**한다. WARNING 이라 계층 1(httpx→WARNING 강등)은 무관하고, 패턴 미등록이라 계층 2 도 매칭되지 않는다 — 두 계층 모두 통과.
- **권고**: `_SECRET_URL_PATTERNS` 에 slack/discord webhook 패턴 추가 + 5곳을 `sanitize_for_log` 대신 호스트만 남기는 헬퍼로 치환. 프로세스 측면 = 정책 16 진화(공유 로직 grep 전수 default)가 '수정 직전 `grep -rn` 으로 전 호출처 열거 + PR 본문에 전수 확인 N곳 1줄 명시' 를 요구하는데 #1104 는 관측된 1건만 고쳤다. secret-in-URL 은 정확히 '같은 로직이 2+곳' 케이스이므로 다음 유사 PR 에서 전수 grep 을 착수 조건으로 고정할 것.

### P1-2. [process] 6-step ⑤ 미이행 — 6 PR 전부 STATE/cycle-history/배지 미갱신, trailing sync PR 도 없음 (수치 3종 drift 확정)

- **위치**: `docs/STATE.md:26`
- **verdict**: CONFIRMED
- **주장**: 완료 6-step ⑤(STATE.md 수치 + cycle-history 동기화)는 '배치-PR 이월' 분기를 쓰더라도 **세션 종료 시 단일 trailing sync PR** 을 요구한다. #1102~#1107 중 어느 것도 STATE/cycle-history/README 를 건드리지 않았고, #1107 로 세션이 끝나 이월분이 회수되지 않았다. 결과적으로 문서 수치 3종이 실측과 어긋난 채 남았다.
- **권고**: trailing sync PR 로 STATE.md:26 + README/README.ko 배지(단위 5585·pylint 9.99) 를 일괄 정정하고 cycle-history 에 본 세션 서사 이관. 프로세스 측면 = '이월' 분기가 사실상 '망각' 으로 귀결됐으므로, 이월을 선택한 시점에 원장(owed-verification.md 또는 별도 카운터)에 미결 항목으로 등재해 SessionStart 훅이 회수를 강제하도록 배선할 것 — 본 세션이 credential 로테이션에 대해 내린 진단(#1106 '인지 의존 산문')과 정확히 같은 처방이 sync 이월에도 필요하다.

### P1-3. [process] 6 PR 전량이 생성 ~5분 후 자동 머지·리뷰 0 — 정책 15 High-tier 와 정책 9 미적용 영역이 의존하는 '사용자 머지' 체크포인트가 구조적으로 부재

- **위치**: `CLAUDE.md:1`
- **verdict**: CONFIRMED
- **주장**: 정책 7 step 5 와 정책 10 은 '**PR 직접 생성 → 사용자 머지**' 를 default 로 명시한다. 그러나 본 세션 6 PR 은 전부 리뷰 0건으로 생성 직후 자동 머지 게이트에 의해 머지됐다. 특히 #1104 는 보안 동작 변경(전역 httpx 레벨 강등 + 로그 레코드 변형)인데 사용자 사전 확인 없이 착수(세션 자가 인지 #4)했고, 사후 사용자 검토 창구마저 자동 머지로 사라졌다 — 위 P0(트레이스백 미봉인)이 사람 눈에 걸릴 마지막 기회였다.
- **권고**: 두 갈래 중 사용자 결정 필요: (a) 자동 머지를 default 로 정식화하고 정책 7/10 본문을 '게이트 머지' 로 개정하되, **정책 15 High-tier(보안·데이터 모델·권한) 라벨이 붙은 PR 은 게이트가 머지하지 않도록 예외 배선** — 현재 유일하게 남는 체크포인트를 코드로 확보. (b) 현행 정책 문언을 유지하고 세션 PR 에 대해 자동 머지를 끄기. 어느 쪽이든 '정책 문서 ↔ 운영 실태' 불일치를 방치하지 말 것 — 본 회고가 반복 지적하는 '기록과 실제의 괴리' 의 또 다른 사례다.

### P1-4. [code] #1104 이 봉인한 것과 동일 계열의 credential 로그 유출이 자사 코드 6곳에 잔존 — Discord/Slack/n8n webhook URL 미커버

- **위치**: `D:\\Source\\SCAManager\\src\\logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS` 는 `api.telegram.org/bot` **단 1종**만 커버한다. 그러나 Discord(`/api/webhooks/<id>/<TOKEN>`)·Slack(`/services/T../B../<SECRET>`)·n8n·generic webhook URL 도 **credential 을 URL 경로에 넣는 동일 설계**이며, 자사 코드가 이들 **전체 URL 을 WARNING 레벨로 로깅**한다. WARNING 이므로 계층 1(httpx INFO 침묵)은 무관하고(자사 로거다), 계층 2 정규식은 매칭하지 않는다 → 평문 그대로 운영 로그에 남는다. 실제 트리거 경로가 존재한다: `validate_external_url()` 은 **일시적 DNS 실패 시에도 False 를 반환**(src/notifier/_http.py:68-76)하고, 그러면 호출자가 전체 URL 을 로깅한다. `_http.py` 자신은 DNS 실패 시 hostname 만 로깅해 올바르게 설계됐으나, 반환값 False 를 받은 상위 6개 호출처가 전체 URL 을 찍어 그 설계를 무효화한다. PR #1104 본문은 계층 2 의 존재 이유를 "**우리 코드의 실수**를 이 필터만이 막는다" 로 명시했는데, 정작 코드베이스에 이미 존재하던 '우리 코드의 실수' 6건을 감사에서 찾지 못했다.
- **권고**: (1) `_SECRET_URL_PATTERNS` 에 Discord(`discord(app)?\\.com/api/webhooks/\\d+/`)·Slack(`hooks\\.slack\\.com/services/`) 패턴 추가. (2) 더 근본적으로는 6개 호출처가 전체 URL 대신 `urlparse(url).hostname` 만 로깅하도록 정정 — `_http.py:68-76` 이 이미 채택한 올바른 패턴을 호출처에 전수 적용(정책 16 진화 grep 전수). (3) 미상 패턴을 놓치는 정규식 화이트리스트 방식의 한계상 (2)가 1차 통제, (1)이 심층 방어.

### P1-5. [docs] 6 PR 전부 6-step ⑤ 미이행 — STATE/README/cycle-history 가 세션 산출물을 하나도 반영하지 않음 (trailing sync PR 부재로 이월도 미정산)

- **위치**: `README.md:21`
- **verdict**: CONFIRMED
- **주장**: #1102~#1107 6건 중 `docs/STATE.md`·`README.md`·`docs/cycle-history.md` 를 건드린 PR 이 0건이고, 세션 종료 시 정산해야 할 trailing sync PR 도 생성되지 않았다. 결과 drift 3종: (a) 테스트 수 — README 배지·STATE 표가 `5570 단위`인데 실측 **5585** (+15, 전량 본 6 PR 산). (b) STATE 날짜 헤더가 `2026-07-18 기준` 으로 하루·한 세션 stale — STATE 자신이 line 5 갱신을 '절차에서 상시 누락되던 필드' 로 명시해둔 항목이다. (c) `cycle-history.md` 에 2026-07-19 항목 자체가 부재 — 서사 SSOT 에서 본 세션이 통째로 실종. 🔴 이 누락은 '몰라서'가 아니다 — Claude 는 #1104 PR 본문에 `5581 passed · 4 skipped`, #1107 본문에 `5581 passed` 를 **직접 실측해 기재**했다. 즉 정확한 신규 수치를 손에 쥔 채로 SSOT 에 전파하지 않았다. 6-step ⑤ 의 '배치-PR 이월 분기'는 in-flight PR 충돌 회피를 위해 per-PR 갱신을 미루는 것을 허용하지만 **'세션 종료 시 단일 trailing sync PR'을 조건으로 건다**. 직전 4개 세션은 모두 그 PR 을 냈다(#1093·#1087·#1076·#1067 = `docs: STATE·cycle-history·배지 sync`). 본 세션만 이월 후 미정산으로 종료했다.
- **권고**: trailing sync PR 1건으로 일괄 정산: README.md:21 배지 `5728→5743` / `5570_unit→5585_unit`, README.ko.md 대응 배지쌍(메모리 `feedback-docs-sync-codeql-gotchas` — `%2B` 인코딩 주의), docs/STATE.md:5 날짜 헤더 `2026-07-19`, :30 누적 추적 셀에 `+15 (#1102 +9 · #1104 +6)` 추가, cycle-history.md 최신순 맨 앞에 2026-07-19 세션 본문 섹션 신설. 재발 방지로는 '이월 분기 발동 시 세션 종료 전 sync PR 미생성'을 SessionStart 훅 계열 카운터(`check_retro_cadence.py` 패턴)로 기계 검출하는 안을 검토할 것 — 본 건은 이월 규칙 자체가 아니라 정산 단계가 인지 의존이라 실패했다.

### P1-6. [docs] owed 원장 내부 모순 — 반증된 'cron 은 로그로 판별 불가' 단정이 🔴 마커를 단 채 존치, 원장 자신이 경고한 실패를 재생산

- **위치**: `docs/runbooks/owed-verification.md:122`
- **verdict**: CONFIRMED
- **주장**: 원장 상단은 cron 검증이 **로그 직접 관측으로 종결**됐다고 3곳에서 단언한다(13행 '더 이상 DB 우회 관측이 필요 없다 — 로그가 직접 증거다', 64행 #1073 ✅, 65행 '검증 수단은 이제 로그 직접 관측(DB 우회 불필요)'). 그런데 같은 파일 하단 §'검증 수단 정정'(111~124행)은 여전히 🔴 를 달고 정반대를 지시한다 — 113행 '그 관측 수단이 존재하지 않는다', 122행 '**cron 실행 여부는 로그로 판별 불가.** 대체 수단 = DB 부작용 관측'. 이 섹션의 근거였던 실측(117행 '총 11줄', 118행 'access log 0줄')은 41행이 오귀인으로 정정한 바로 그 증상이며, 원인이 앱 자신(alembic fileConfig)임이 #1102 로 밝혀져 이미 제거됐다. 즉 전제가 무너진 결론이 취소선·정정 배너 없이 지시문 형태로 남아 있다. 41행은 동일 오귀인을 `~~취소선~~ + ❌ 오귀인이었다` 로 제대로 처리했으므로 처리 방법을 몰라서가 아니라 전수 확인을 안 한 결과다. 🔴 아이러니: 109행이 '앱 문제 아님 같은 단정은 반증 실험 없이 원장에 기록하지 말 것' 을 교훈으로 못박았는데, 정작 반증된 단정을 지우지 않아 같은 실패(원장의 stale 단정이 다음 세션 조사 방향을 오도)를 구조적으로 재생산했다. 88행도 동일 계열 — '#1073·#1075 는 스케줄러 배포 후에야 검증 가능… 검증 기준은 아래 DB 관측을 그대로 사용' 이라 하나 #1073 은 64행에서 이미 ✅ 종결이고 DB 관측은 65행이 '불필요' 로 대체했다.
- **권고**: §'검증 수단 정정'(111~124행) 헤더에 41행과 동일한 취소선+정정 배너 적용 — `~~검증 수단 정정~~ → ❌ 2026-07-19 반증(#1102): 관측 불가의 원인은 Railway 가 아니라 앱의 fileConfig 였고 로그 관측이 복구됨. 이하 2026-07-18 시점 기록으로 보존`. 122행의 '로그로 판별 불가' 지시문은 과거형으로 재작성. 88행은 `#1073` 을 빼고 `#1075` 만 남기며 검증 기준을 '로그 직접 관측(`scheduler retention_sweep`)' 으로 교체. 절차적으로는 원장 편집 시 '이번 발견이 기존 섹션의 전제를 무너뜨리는가' 전수 확인 1항을 §작성 규칙(5행)에 추가할 것 — #1103·#1105·#1106 이 같은 파일을 3회 연속 편집하면서도 하단 섹션을 아무도 재검토하지 않았다.

### P1-7. [security] #1104 리댁션 우회 잔존 경로 — 알림 실패 시 exc_info 트레이스백이 Telegram 토큰을 평문 재유출 (실증)

- **위치**: `src/logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: #1104 는 '2계층' 으로 토큰 유출을 차단했다고 선언하고 원장 53행에 로테이션을 안전등급으로 등재했다. 그러나 `_RedactSecretsFilter` 는 `record.getMessage()` 결과만 검사·치환하므로 **`exc_info` 트레이스백은 필터를 통과하지 못한다** — 트레이스백 텍스트는 `Formatter.formatException()` 이 `record.msg` 와 무관하게 별도 생성하기 때문이다. 이는 이론이 아니라 라이브 경로다: `src/notifier/telegram.py:91` 의 `r.raise_for_status()` 가 던지는 `httpx.HTTPStatusError` 는 메시지에 요청 URL 전문을 담고, 이 예외는 `src/worker/pipeline.py:718-719` 에서 `logger.error(..., exc_info=(type(exc), exc, exc.__traceback__))` 로 기록된다. 실증 결과 같은 로그 1건 안에서 메시지 부분은 `bot***` 로 마스킹되는데 트레이스백 꼬리는 토큰을 그대로 노출한다. 실질 영향: 사용자가 원장 53행 지시대로 토큰을 로테이션해도 **신규 토큰이 알림 실패 때마다 같은 경로로 다시 유출**되므로 로테이션이 무효화된다. 다만 상시 INFO 유출(알림 1건당 1줄)은 실제로 차단됐으므로 유출 빈도는 크게 줄었다 — P0 가 아니라 P1 로 본다.
- **권고**: 필터가 트레이스백까지 덮도록 확장 — `_RedactSecretsFilter.filter()` 에서 `record.exc_text` 를 함께 치환하거나(이미 포맷된 경우), 더 확실하게는 `logging.Formatter` 서브클래스를 만들어 `format()` 최종 출력 문자열에 패턴을 적용하고 핸들러 포맷터로 지정할 것(필터+포맷터 병용이 누락면 0). 회귀 가드는 `record.msg` 가 아니라 **핸들러 최종 출력 전체**(트레이스백 포함)를 검사하도록 작성 — #1104 의 기존 가드가 '포맷 최종 출력을 검사한다' 고 주장했으나 `exc_info` 케이스가 없어 이 경로를 놓쳤다. 수정 전까지 원장 53행 로테이션 항목에 '수정 전 로테이션 시 신규 토큰이 알림 실패 경로로 재유출됨 — 코드 수정 후 로테이션 권장' 1줄 경고를 추가할 것.

### P1-8. [decision] 정책 12 위반의 재발 방지책이 또다시 인지 의존 산문 — 노출 벡터(Bash)에 집행면이 0

- **위치**: `.claude/settings.json:1`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1106 커밋 제목은 'credential 로테이션 2건을 기계 집행면에 등재 — 인지 의존 산문 4회차 봉인' 이지만, 실제로 기계화된 것은 **로테이션 리마인더**(원장 ⏳ → SessionStart 훅 loud 경고)뿐이다. **재노출 방지**는 원장 행 안의 산문 한 문장으로만 남았다. 그런데 이번 노출의 벡터는 Write/Edit 이 아니라 **Bash 명령**(`railway variables --kv | grep`)이었고, `.claude/settings.json` 의 훅은 SessionStart / PreToolUse(Write|Edit|MultiEdit) / PostToolUse(Write|Edit) 뿐 — **Bash 에 대한 훅이 하나도 없다**. 즉 노출 경로는 시정 전과 완전히 동일하게 무방비다. 회고가 P0 로 규정한 '문서-only 시정은 행동을 못 바꾼다'를, 그 P0 를 시정하는 PR 안에서 다시 재생산했다(5회차).
- **권고**: Bash 대상 PreToolUse 훅을 신설해 credential 값을 출력할 수 있는 명령 형태(`railway variables` 계열이 `--kv`/`--json` 으로 값을 뿜는데 `cut -d= -f1` 같은 이름-한정 필터가 없는 경우 등)를 차단하거나 경고한다. 훅 자체의 회귀 가드는 산문이 아니라 `.claude/settings.json` 배선을 단언해야 한다 — `tests/unit/scripts/test_session_start_wiring.py` 가 이미 검증된 선례다. 아울러 #1106 의 '기계 집행' 이라는 커밋 서술은 리마인더에만 해당하므로, 향후 동종 보고에서 '리마인더 기계화' 와 '벡터 차단' 을 분리해 표기해야 한다(정책 3 자율 판단 보고 정확성).

### P1-9. [decision] 회고 에이전트를 worktree 격리 없이 공유 작업트리에 디스패치 — 측정 결과가 실시간으로 오염됨(현장 관측)

- **위치**: `CLAUDE.md:1`
- **verdict**: CONFIRMED
- **주장**: 본 회고의 병렬 에이전트들이 `isolation: worktree` 없이 메인 작업트리를 공유한 채 디스패치됐고, 최소 1개 형제 에이전트가 검증 항목 (b)/(e) 를 확인하려고 **추적 대상 소스 파일을 실시간으로 뮤테이션**하고 있다. 그 결과 동일한 pytest 명령이 호출마다 다른 결과를 냈다. 이는 CLAUDE.md 가 '전례 2 (단일 — 2026-07-18)' 로 명시하고 직전 세션 #1088 이 규칙으로 못박은 바로 그 실패 모드이며, 규칙 신설 한 세션 만의 위반이다. 회고의 산출물 신뢰도에 직접 영향한다 — 나 자신이 '테스트 순서 의존성' 이라는 위양성 결론에 도달했다가 트리 오염을 발견하고 철회했다.
- **권고**: 회고/감사 워크플로에서 **뮤테이션 검증을 수행하는 에이전트는 반드시 `isolation: worktree`** 로 디스패치한다. 검증 항목 (e) 처럼 '뮤테이션 재현' 을 명시적으로 요구하는 프롬프트는 격리를 강제 조건으로 프롬프트 본문에 박아야 한다(정책 6 의 line:span 인용 의무와 동급으로). `.claude/workflows/retrospective.mjs` 의 디스패치 지점에 격리 플래그가 실제로 설정되는지 배선 가드를 추가하는 것이 산문 규칙보다 확실하다.

### P1-10. [decision / security-verification] 리댁션 패턴이 Telegram 단일 — 우리 코드 5곳이 Slack·Discord webhook URL 전문을 로깅하는데 PR 본문은 '우리 코드의 실수는 이 필터만이 막는다' 로 단언

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS` 는 `api.telegram.org/bot` 하나만 담은 1-원소 튜플이다. 그런데 우리 코드 5곳이 webhook URL **전문**을 WARNING 으로 로깅하고, Slack(`hooks.slack.com/services/T…/B…/<secret>`)·Discord(`discord.com/api/webhooks/<id>/<token>`) webhook URL 은 경로에 시크릿을 담는 동일 설계다. 계층 1(httpx→WARNING)은 우리 로거에 무관하고 계층 2 는 패턴 미등록이라, 이 5개 경로는 두 계층 모두 통과한다. #1104 PR 본문의 '계층 1 을 통과하는 httpx WARNING과 **우리 코드의 실수**는 이 필터만이 막는다' 는 단언이 이 5곳에서 성립하지 않는다. 다만 발화 조건이 `validate_external_url` 실패 시로 한정돼 상시 유출은 아니므로 P1.
- **권고**: 두 갈래로 처리한다. (1) 위 5개 로그를 URL 전문 대신 스킴+호스트만 남기도록 바꾸는 것이 근본 — 차단 사유 판독에 경로는 불필요하다. (2) `_SECRET_URL_PATTERNS` 에 `hooks.slack.com/services/` 와 `discord.com/api/webhooks/` 를 추가해 심층 방어를 실제 '2계층' 으로 만든다. 사용자 지정 임의 webhook(n8n·generic webhook)은 패턴화가 불가능하므로 (1) 이 유일 해법이라는 점도 함께 기록해야 한다.

### P1-11. [tooling] 정책 12 위반의 재발 방지책이 산문뿐 — Bash 게이팅 표면 자체가 부재 (인지 의존 산문 5회차)

- **위치**: `.claude/settings.json:22`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1106 은 로테이션 '의무'를 기계 집행면(안전등급 표 → SessionStart 카운터)에 올리는 데 성공했으나, 이번 노출을 **일으킨 명령**의 재발 방지 규칙(`railway variables --kv` 를 grep 하지 말고 `cut -d= -f1` 사용)은 마크다운 표 셀 안의 산문으로만 존재한다. 더 근본적으로 `.claude/settings.json` 의 PreToolUse matcher 는 `Write|Edit|MultiEdit` 뿐이라 **Bash 명령을 가로챌 표면이 아예 없다** — 어떤 셸 명령도 게이팅 불가능하다. 직전 회고가 P0 로 규정한 '인지 의존 산문 시정' 패턴의 5회차이며, 방지책이 '다음 세션의 Claude 가 표 셀을 읽고 기억한다'에 전적으로 의존한다.
- **권고**: PreToolUse 에 `Bash` matcher 훅을 신설해 `railway variables` 가 `cut -d= -f1` 없이 호출되면 차단/경고(비차단 advisory 로도 충분 — 정책 17 안정성). 또는 permissions.deny 항목 추가. 두 방식 모두 20줄 미만이며, 현재 Bash 게이팅 표면이 0 이라 향후 모든 셸 기반 규칙(정책 12 전반)의 토대가 된다.

### P1-12. [tooling] 리댁션 필터가 exc_info 트레이스백을 구조적으로 못 덮는데, 프로젝트 자체 리뷰 가이드가 그 우회 패턴을 권장한다

- **위치**: `src/logging_config.py:76`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter` 는 `record.msg`/`record.args` 만 변형하므로 `Formatter.formatException()` 이 렌더링하는 트레이스백은 **필터를 통과하지 않는다**. `httpx.HTTPStatusError` 의 문자열에는 토큰이 포함된 전체 URL 이 들어있으므로, telegram 호출부 어디든 `logger.exception()`/`exc_info=True` 로 로깅하는 순간 봇 토큰이 평문으로 남는다. 현재 코드에서는 모든 telegram 호출부가 `%s exc` 또는 `type(exc).__name__` 로 로깅해 우연히 안전하지만(즉 지금 당장 유출 경로는 아님), 이 안전은 **규약이 아니라 우연**이다. 결정적으로 SCAManager 자체 AI 리뷰 가이드가 `logger.exception()`/`exc_info=True` 사용을 **권장**하고 있어, 프로젝트의 자동 리뷰가 개발자를 Layer 2 우회 패턴 쪽으로 능동적으로 밀어낸다. #1104 의 docstring 은 이 필터가 '우리 코드가 실수로 토큰을 로깅하는 경우'를 막는 심층 방어라고 단언하지만, 가장 흔한 실수 형태인 `logger.exception` 은 덮지 못한다. 해당 갭을 커버하는 테스트도 없다.
- **권고**: 핸들러의 Formatter 를 서브클래싱해 `format()` 결과 전체(트레이스백 포함)에 `_SECRET_URL_PATTERNS` 를 적용하거나, 필터에서 `record.exc_text` 를 미리 렌더링·리댁션해 캐싱. 어느 쪽이든 `logger.exception` 경로를 단언하는 회귀 테스트 1건을 tests/unit/test_logging_config.py 에 추가해야 '심층 방어' 단언이 실증된다.

### P1-13. [process/governance] 6 PR 전부 사람 리뷰 0건 · 창발~머지 ~5분 고정 — 정책 7/10 종단 단계('사용자 머지')가 무음 no-op 화, GitHub 기록은 사용자 행위로 오귀속

- **위치**: `docs/runbooks/owed-verification.md:53`
- **verdict**: CONFIRMED
- **주장**: 본 세션 6 PR(#1102~#1107)은 전부 `reviews=0` · `reviewDecision=null` · `autoMergeRequest=null` 이며 생성→머지 간격이 4m37s~5m27s 로 기계적으로 균일하다. mergedBy 는 6건 모두 `xzawed`(사용자 계정)로 기록되지만, 이는 SCAManager 머지 게이트가 사용자 토큰으로 API 머지하기 때문이며 사용자가 실제 머지 버튼을 누른 증거가 아니다. 즉 (a) 정책 7/10 이 전제하는 '사용자 머지' 독립 검토 지점이 구조적으로 부재했고 (b) GitHub 감사 기록만으로는 봇 머지와 사용자 머지를 구분할 수 없다. 이 경로로 머지된 것 중 #1102(운영 로깅 P0)·#1104(시크릿 처리 보안 P0)는 Claude 가 작성하고 Claude 의 PR 본문이 유일한 검토 산출물인 코드 변경이다 — 독립 검증자가 0명인 상태로 main 에 도달했다. 덧붙여 이 머지를 수행한 retry 큐는 본 세션 직전 #1099 로 도입된 인앱 스케줄러가 구동한다(세션이 스스로 고친 기전이 세션 자신의 미검토 PR 을 머지한 순환).
- **권고**: (1) PR 본문 또는 owed 원장에 §머지 주체를 명시 기록(봇 게이트 / 사용자)해 감사 기록의 오귀속을 상쇄한다. (2) 정책 7/10 에 '작성자=Claude 이고 등급=P0/보안' 인 PR 은 게이트 자동머지 대상에서 제외(사용자 명시 머지 의무) 분기를 신설할지 사용자 결정을 구한다 — 현재는 Claude 자가 작성·자가 검토·봇 머지로 3 지점이 모두 Claude 측이다.

### P1-14. [security/process] #1104 는 시크릿-in-URL 로그 유출 계열 중 Telegram 1건만 봉인 — 구조적으로 동일한 6개 지점이 미리댁션 잔존 (정책 16 진화 'grep 전수' 미이행)

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS`(src/logging_config.py:38-40)은 `api.telegram.org/bot` 단일 패턴만 담고 있으나, 저장소에는 **전체 webhook URL 을 그대로 로깅하는 지점이 6곳 더** 있다. Discord/Slack webhook URL 은 경로 자체가 bearer credential(URL 보유자가 곧 발신 권한)이라 Telegram 토큰과 위험 등급이 동일하다. 이 6곳은 (a) `logger.warning` — 계층 1(httpx→WARNING 강등)이 전혀 닿지 않고 (b) httpx 가 아닌 **우리 코드 자신의 로거** — 즉 `_RedactSecretsFilter` docstring(src/logging_config.py:51-54)이 '우리 코드가 실수로 토큰을 로깅하는 경우… 이 필터만이 막는다' 고 명시한 바로 그 케이스인데, 패턴 미등록으로 **필터를 그대로 통과**한다. #1102 로 로깅이 살아난 지금 이 WARNING 라인은 실제로 Railway 로그에 도달한다. CLAUDE.md 정책 16 진화(공유 로직 grep 전수 default)는 같은 로직이 2+곳일 때 수정 **직전** `grep -rn` 전수 열거 + PR 본문 '전수 확인 N곳' 1줄을 의무화하나, #1104 커밋 본문에 해당 라인이 없다 — `grep -rn "logger.warning.*url" src/` 한 번이면 6곳이 즉시 드러났다.
- **권고**: `_SECRET_URL_PATTERNS` 에 discord/slack webhook 경로 패턴을 추가하거나, 더 견고하게는 위 6곳을 `sanitize_for_log` 계열 헬퍼 경유로 전환해 URL 을 호스트+경로 앞부분만 남기도록 통일한다. 회귀 가드는 'src/ 내 logger 호출 인자에 raw webhook_url 이 전달되지 않는다' 는 AST 단언으로 계열 전체를 잠근다(정책 4). 🔴 선행 확인: 운영 `repo_configs` 에 discord/slack/n8n webhook 설정 건수가 1건이라도 있으면 본 항목은 P0 으로 승격된다(정책 12 SELECT-only 자율 범위).

### P1-15. [code] 리댁션 패턴이 Telegram 전용 — Discord/Slack/custom webhook 시크릿은 우리 코드가 WARNING 으로 평문 로깅

- **위치**: `D:\Source\SCAManager\src\logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS` 에 `api.telegram.org/bot` 단 1개만 등록돼 있으나, SCAManager 는 경로에 시크릿이 박힌 웹훅 URL 4종(Discord `/api/webhooks/{id}/{token}`, Slack `hooks.slack.com/services/...`, custom webhook, n8n)을 다룬다. 계층 1(httpx WARNING)은 서드파티 로거만 덮으므로, **우리 모듈이 직접 WARNING 으로 찍는 URL** 은 어느 계층도 막지 못한다.
- **권고**: `_SECRET_URL_PATTERNS` 에 `(discord(?:app)?\.com/api/webhooks/\d+/)[^/\s]+`, `(hooks\.slack\.com/services/)\S+` 를 추가하고, 임의 custom webhook 은 패턴화가 불가하므로 discord/slack/webhook.py 의 세 WARNING 을 URL 전문 대신 host+경로 접두만 남기도록 변경(예: `urlsplit(url).netloc`). 신규 채널 추가 시 패턴 등재를 강제하는 가드 1건 동반 권장.

### P1-16. [code] path-scoped `.claude/rules/*.md` 동기화 의무 3영역 미이행 — security.md 는 시크릿 리댁션 계층을 모른 채 sanitize_for_log 를 유일 방어로 제시

- **위치**: `D:\Source\SCAManager\.claude\rules\security.md:24`
- **verdict**: CONFIRMED
- **주장**: CLAUDE.md 아키텍처 동기화 체크리스트는 `alembic/**`·`tests/**`·`src/<area>/**` 변경 시 해당 `.claude/rules/<area>.md` 본문 갱신을 의무(🔴 사이클 86 Q2, 사용자 명시 결정)로 규정한다. #1102 는 `alembic/env.py` + `tests/unit/conftest.py` + 신규 테스트 디렉토리 파일을, #1104 는 로그 시크릿 방어면을 바꿨으나 db.md·testing.md·security.md 어디도 갱신되지 않았다.
- **권고**: security.md:24 항목 옆에 '시크릿 리댁션은 별개 계층 = src/logging_config.py::_RedactSecretsFilter (경로형 시크릿 URL 마스킹). sanitize_for_log 는 CR/LF 전용 — 상호 대체 불가' 1줄 추가. db.md 에 'alembic/env.py fileConfig 는 `is_configured()` 가드 뒤에 있다 — 인프로세스 마이그레이션이 앱 로깅을 파괴하던 #1102' 1줄. testing.md §Mock+Fixture 에 'in-process alembic/로깅 전역 변경 테스트는 `tests/unit/conftest.py::logging_isolation` 요청 의무' 1줄.

### P1-17. [docs] cycle-history.md 에 2026-07-19 세션(#1094~#1108, 15 PR) 항목이 0건 — 최신 섹션이 2026-07-18 에서 멈춤

- **위치**: `docs/cycle-history.md:145`
- **verdict**: CONFIRMED
- **주장**: 6-step ⑤ 의 나머지 절반인 `docs/cycle-history.md` 사이클 이력 동기화가 본 세션 15 PR 전부에 대해 수행되지 않았다. STATE.md 는 #1094~#1100 까지 bullet 이 있으나 #1101~#1108 이 없고, cycle-history 는 2026-07-19 세션 자체가 통째로 부재한다.
- **권고**: 위 STATE/README sync PR 에 묶어서 cycle-history.md 에 '2026-07-19 세션 — 운영 P0 2건 + 회고 + 원장 정리 (#1094~#1108)' 섹션 신설 + STATE.md:5 헤더 날짜를 2026-07-19 로 갱신 + #1101~#1108 bullet 추가.

### P1-18. [docs] owed 원장 자체 모순 4곳 — #1103·#1105·#1106·#1108 이 표 '셀'만 갱신하고 그 아래 산문 섹션을 반증 처리하지 않음

- **위치**: `docs/runbooks/owed-verification.md:40`
- **verdict**: CONFIRMED
- **주장**: 같은 파일을 4회 연속 수정하면서 상태 셀만 바꾼 결과, 원장 본문에 이미 뒤집힌 결론이 '현재 사실' 형식으로 4곳 잔존한다. 이 원장은 다음 세션 인수인계용 단일 출처이므로, 원장 스스로 line 92 에서 경고한 실패 모드('오귀인이 원장에 사실로 남아 다음 세션의 조사 방향을 잘못 유도했다')를 같은 파일에서 재생산한 상태다.
- **권고**: `:40`·`:45` → ⏭️ 위험수용 결정(#1108)으로 문구 교체. `:88` → 취소선 + '#1102 로 로그 복구되어 무효 — :64/:65 참조'. §111~122 섹션 헤딩에 `~~취소선~~ + 🔴 2026-07-19 반증됨(#1102)` 마커 부착. 원장의 append-only 규칙과 충돌하지 않게 삭제가 아닌 '반증 마커 + 현행 포인터' 방식 사용.

### P1-19. [docs] env-vars.md 내부 모순 — `INTERNAL_CRON_API_KEY` 설명(:40)과 운영 안전 주석(:48)이 서로 반대 사실을 단언

- **위치**: `docs/reference/env-vars.md:48`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1099 의 인앱 스케줄러 전환이 :40 에는 반영됐으나 :48 은 Railway cron 시절 전제 그대로 남아, 같은 파일이 '키가 없어도 스케줄 작업은 동작한다' 와 '키 미설정 시 cron job 이 silent 503 으로 실패해 weekly_summary 등이 발송 안 됨' 을 동시에 주장한다. 본 세션이 cron 서사를 원장에서 4회 수정하면서도 같은 사실의 env-vars.md 사본은 전수 확인하지 않았다(정책 16 '공유 로직/값 grep 전수' 의 문서판 누락).
- **권고**: `docs/reference/env-vars.md:48` 의 해당 절을 "미설정 시 **수동/외부 트리거 엔드포인트 6종만** 503 — 주기 실행은 인앱 스케줄러가 담당하므로 영향 없음(:40 참조)" 으로 교정. 함께 `SCHEDULER_DISABLED`(:41) 가 실제 kill-switch 임을 운영 안전 문단에 반영.

### P1-20. [decision] #1104 리댁션 범위를 '오늘 로그에 보인 것'으로 정했다 — 경로에 credential 을 담는 Discord/Slack/n8n webhook URL 6개 로깅 지점이 무방비로 잔존

- **위치**: `src/logging_config.py:38`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1104 는 '2계층 리댁션' 으로 URL 경로 credential 유출을 봉인했다고 선언했으나, `_SECRET_URL_PATTERNS` 에는 Telegram 패턴 단 1개만 있다. 반면 앱 자신의 코드에는 credential 이 경로에 박힌 webhook URL 전문을 WARNING 으로 찍는 지점이 6곳 살아 있다. #1104 가 P0 로 규정한 결함과 **동일 클래스**이며, 계층 1(httpx WARNING 강등)로도 막히지 않는다(이미 WARNING 레벨이므로).
- **권고**: 결정 규율로 승격: 시크릿 유출 수정의 범위는 '관측된 로그 라인' 이 아니라 '코드베이스 전수 열거' 로 정한다 — CLAUDE.md 정책 16 진화가 이미 명시한 `grep -rn <심볼>` 전수 의무(공유 로직 2+곳)를 시크릿 클래스에도 적용. 즉시 조치는 (a) `_SECRET_URL_PATTERNS` 에 `discord.com/api/webhooks/\d+/`, `hooks.slack.com/services/`, 범용 n8n/webhook 호스트 패턴 추가 (b) 6 지점을 URL 전문 대신 `urlparse(...).hostname` 만 로깅하도록 변경 (c) 'URL 을 로깅하는 신규 코드 금지' 를 회귀 가드로 고정(`grep` 기반 정적 가드). #1104 의 '2계층' 단언은 Telegram 한정임을 PR/원장 본문에 정정.

### P1-21. [decision] Claude 가 작성한 위험 수용 근거가 '사용자 명시 결정' 으로 원장에 귀속 — 그중 1건은 아무 실측도 없는 주장

- **위치**: `docs/runbooks/owed-verification.md:53`
- **verdict**: CONFIRMED
- **주장**: 사용자 발화는 *"토큰과 키는 그대로 사용 예정입니다."* 한 문장이다. 그런데 원장 행은 **"사용자 명시 결정 (2026-07-19) ... 위험 수용 근거 = ①②③"** 형태로, Claude 가 사후 구성한 3개 논거를 사용자의 판단 근거인 것처럼 기록했다. 특히 근거 ②는 저장소 어디에도 근거가 없는 미검증 사실 주장인데, **살아 있는 credential 노출을 수용하는 영구 기록의 정당화**로 쓰였다.
- **권고**: 원장에 **사용자 발화 원문과 Claude 의 분석을 물리적으로 분리**할 것: `사용자 결정(원문 인용)` 과 `Claude 위험 분석(미검증 항목 표기)` 을 별도 셀/줄로. ②는 즉시 (a) Railway 요금제 보존 기간을 실측해 확정하거나 (b) *"미검증 가정"* 으로 강등한다. 규율: **credential 위험 수용의 근거로 미실측 주장을 쓰지 않는다** — 근거가 실측 불가하면 그 사실을 근거란에 적는다.

### P1-22. [tooling] 병렬 회고 에이전트가 공유 작업트리를 직접 편집 — worktree 격리 규칙 위반 (전례 3회차), 동시 에이전트 측정 실제 오염

- **위치**: `tests/unit/conftest.py:49`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 본 회고를 수행 중인 형제 에이전트가 `isolation: worktree` 없이 메인 작업트리의 `tests/unit/conftest.py` 를 직접 뮤테이션했다. CLAUDE.md §'파일 편집 에이전트 — 작업트리 격리 (병렬·단일 무관)' 이 명시 금지하고 전례 2건(2026-04-27 병렬, 2026-07-18 단일)을 기록한 바로 그 사고의 3회차다.
- **권고**: (1) 회고 오케스트레이터가 파일 쓰기 가능성이 있는 모든 에이전트에 `isolation: worktree` 강제 — 본 세션은 `C:/Users/dirtc/AppData/Local/Temp/pc1` 워크트리를 쓰는 에이전트와 메인 트리를 쓰는 에이전트가 혼재했다. (2) 뮤테이션 프로브는 예외 없이 `git worktree add` 안에서 수행. (3) Stop/SessionEnd 훅으로 '예상치 못한 working-tree 수정' 탐지 — 프로브가 복원되지 않은 채 세션이 끝나면 무력화된 fixture 가 커밋될 수 있고, 그 fixture 는 #1102 가 도입한 격리 가드 자체다.

### P1-23. [tooling] 회고 카덴스 카운터의 경계가 '회고 범위'가 아니라 '리포트 커밋'이라 P0 2건 포함 5 PR 이 영구 미집계

- **위치**: `scripts/check_retro_cadence.py:93`
- **verdict**: CONFIRMED
- **주장**: `_boundary_commit()` 이 회고 리포트 **파일이 추가된 커밋**을 경계로 삼고 `boundary..HEAD` 만 센다. 회고의 선언 범위(#1078~#1101)와 리포트 아카이브 시점(#1107) 사이에 머지된 PR 은 어느 회고에도 포함되지 않으면서 카운터에서도 영구히 사라진다. 산문 2회 실패 끝에 기계화된 바로 그 장치가 구조적으로 과소집계한다.
- **권고**: 경계를 리포트 커밋이 아니라 회고가 **선언한 범위**에서 파생하라 — 리포트 front-matter 에 `scope_end: <sha 또는 PR#>` 필드를 두고 `_boundary_commit` 이 이를 우선 사용(부재 시 현 로직 fallback). 회귀 가드는 `tests/unit/scripts/` 의 기존 파서 테스트에 '리포트 커밋과 scope_end 가 다를 때 사이 PR 이 집계된다' 케이스를 추가.

### P1-24. [tooling] PostToolUse 스모크 훅이 본 세션 최고 폭발반경 파일 3종을 전부 미커버 — alembic/env.py·conftest.py·직속 src/*.py

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:44`
- **verdict**: CONFIRMED
- **주장**: `is_src_file()` 이 `src/` 만 통과시키고 `derive_test_target()` 이 경로 조각 2개 미만을 None 처리해, #1102·#1104 가 편집한 파일 중 **어느 것도 실제 테스트를 실행받지 못했다**. 배포마다 실행되는 `alembic/env.py` 와 단위 5581건을 감싸는 `tests/unit/conftest.py` 는 스모크 0, 두 P0 의 주제 파일 `src/logging_config.py` 는 collection 스모크만 받았다.
- **권고**: (1) `derive_test_target()` 에 파일 단위 fallback 추가 — `src/<n>.py` → `tests/unit/test_<n>.py` 존재 시 해당 파일 실행 (6건 즉시 회복). (2) `is_src_file()` 을 확장해 `alembic/**` → `tests/unit/migrations`, `**/conftest.py` → 해당 conftest 의 상위 디렉토리 스코프 실행. (3) 훅 자체의 매핑 회귀 가드(`tests/unit/scripts/`)에 위 6건 parametrize 를 넣어 재drift 봉인.

### P1-25. [security] #1104 리댁션이 exception traceback 경로를 못 막는다 — 실증 유출 (그리고 가드는 발생 불가능한 경로를 테스트한다)

- **위치**: `src/logging_config.py:63`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1104 가 'Telegram 봇 토큰 로그 평문 유출 차단 (P0)' 으로 머지됐으나, 운영에서 실제로 토큰이 로그에 남는 주 경로인 **예외 트레이스백**을 전혀 막지 못한다. `_RedactSecretsFilter.filter()` 는 `record.getMessage()`(= msg % args)만 검사하므로 `record.exc_info`/`exc_text` 로 렌더되는 트레이스백은 필터를 그대로 통과한다. 더 나쁜 것은 이 경로를 덮는다고 주장하는 가드 테스트가 **실제로는 존재하지 않는 경로**를 검증한다는 점이다.
- **권고**: `_RedactSecretsFilter.filter()` 가 `record.exc_info`/`record.exc_text` 도 마스킹하도록 확장 (`record.exc_text` 를 미리 렌더한 뒤 치환해 캐시에 저장하는 방식이 표준). 더 근본적으로는 `src/notifier/telegram.py:88` 의 `raise_for_status()` 를 감싸 URL 이 없는 예외로 재발생시키는 것이 1차 통제. `tests/unit/test_logging_config.py:341` 는 `logging.getLogger(...).warning(...)` 합성 대신 **실제 `httpx.Response(401).raise_for_status()` 를 `logger.exception` 으로 로깅**하는 형태로 교체 — 현재 형태는 통과해도 아무것도 보증하지 않는다.

### P1-26. [security] Discord·Slack webhook 토큰이 동일 클래스 유출인데 미커버 — 정책 16 '공유 로직 grep 전수' 미이행

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: #1104 는 '토큰이 URL 경로에 있는 외부 서비스' 라는 **클래스**를 식별해 놓고 그 클래스의 인스턴스 1개(Telegram)만 막았다. Discord/Slack webhook URL 도 경로에 시크릿을 담으며, 우리 코드가 그 URL 전문을 WARNING 으로 로깅하는 지점이 이미 존재한다. 정책 16 진화 '같은 값/로직이 2+곳에 있을 때 수정 직전 `grep -rn` 으로 전 호출처 열거' 의무가 이행되지 않았다.
- **권고**: `_SECRET_URL_PATTERNS` 에 Discord/Slack 패턴 추가(캡처 그룹 1 보존 방식 동일)하고, `src/notifier/discord.py:101`·`src/notifier/slack.py:117` 은 URL 전문 대신 host+경로 앞부분만 로깅하도록 교정. 신규 webhook 채널 추가 시 패턴 등재를 강제하는 가드는 `.claude/rules/security.md:26`(webhook URL SSRF 2계층 단일출처 규약)에 1줄 페어로 붙이는 것이 자연스럽다.

### P1-27. [docs] 원장 동일 파일 내 3중 모순 — 무효화된 결론이 🔴 '실측' 권위를 단 채 잔존 (정정 기전은 같은 파일에 이미 있는데 미적용)

- **위치**: `docs/runbooks/owed-verification.md:122`
- **verdict**: CONFIRMED
- **주장**: #1103·#1105·#1106·#1108 이 `docs/runbooks/owed-verification.md` 를 4회 연속 수정하면서 **상단에 새 결론을 얹기만 하고 하단의 무효화된 결론을 중화하지 않았다**. 그 결과 같은 파일이 동일 검증 수단에 대해 정반대를 단언한다. 직전 회고가 P1 으로 지목한 *'append-only 원장에 결론 무효화 기전 부재 — 낡은 근거가 사실로 고착'* 이 그 회고의 조치 PR 들 안에서 재생산됐다.
- **권고**: `:111-122` 섹션 헤더에 취소선 + `❌ 2026-07-19 무효 — #1102 로 로그 관측 복구, §상단 참조` 1줄 삽입(:41 패턴 그대로). `:88` 은 *"→ #1073 은 :64 에서 로그로 종결, #1075 검증 기준도 로그 직접 관측(:65)"* 로 교체. `:40`·`:45` 는 ⏭️ 사용자 결정을 반영해 '로테이션 필요' → '사용자 위험 수용(:53·:54 참조)' 로 정정하고 `:40` 행을 '재확인 불필요' 표에서 제거. 구조적으로는 원장 범례(`:7`)에 **❌무효/🔄정정됨** 상태를 추가해 'append-only 이지만 결론은 무효화 가능' 을 명시 — 회고 P1 권고의 미이행분.

### P1-28. [code] Slack·Discord·n8n webhook URL(경로 자체가 credential) 5개 지점이 로그에 전문 기록 — #1104 의 2계층 어디에도 안 걸림

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: #1104 는 계층 2 필터를 '우리 코드가 실수로 토큰을 로깅하는 경우' 를 막는 심층 방어라고 문서화했으나(`src/logging_config.py:51-52`), 정규식은 `api.telegram.org/bot` **단일 패턴**이다. Slack incoming webhook(`hooks.slack.com/services/T../B../<24자 시크릿>`)·Discord webhook(`/api/webhooks/<id>/<token>`)·n8n webhook 은 **URL 경로 전체가 credential** 인데, 이를 전문 로깅하는 자체 코드가 5곳 존재한다. 계층 1(httpx WARNING 강등)은 자체 로거·WARNING 레벨이라 무효, 계층 2 는 패턴 미등재라 무효 — 즉 두 계층 모두 통과한다.
- **권고**: `_SECRET_URL_PATTERNS` 에 `hooks.slack.com/services/`·`discord(app)?.com/api/webhooks/` 패턴을 추가하고(경로 전체 마스킹), 5개 자체 로깅 지점은 URL 전문 대신 호스트+경로 접두만 남기도록 정정한다. 더 근본적으로는 `src/shared/log_safety.py` 에 `redact_secrets(text)` 를 두어 `sanitize_for_log` 와 짝을 맞추고, 필터·호출부가 같은 단일 출처를 쓰게 한다(현재 리댁션 로직이 `logging_config.py` 에만 있어 재사용 불가).

### P1-29. [docs] STATE.md SSOT 가 #1100 을 로그 소실의 해결책으로 서술 — owed 원장과 정면 상충, 직전 회고 P1 지적이 7 PR 동안 미이행

- **위치**: `docs/STATE.md:25`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: docs/STATE.md:25 는 '앱 INFO 로그가 출시 이래 전부 소실 (#1100)' 항목을 `src/logging_config.py` 신설 + main.py 배선으로 종결한 것처럼 서술하며, #1102(실제 수정)는 STATE.md 전체에 단 한 번도 등장하지 않는다(grep '#1102' → 0건). 그러나 docs/runbooks/owed-verification.md:105 는 '따라서 #1100(로깅 설정 신설)은 운영에서 무력(inert)이었다' 로 명시한다. 프로젝트가 스스로 '단일 진실 소스'로 선언한 문서와 기계 배선된 원장이 '앱 로깅이 고쳐졌는가'에 대해 정반대를 말한다. 결정적으로 이는 신규 결함이 아니라 **직전 회고가 이미 P1 으로 지목한 항목**이다 — docs/_archive/reports/2026-07-19-retrospective.md:345 '본 세션이 #1100 의 운영 무력(inert)을 확정하고 owed 원장에는 정정을 기록했으나, 프로젝트가 스스로 단일 진실 소스로 선언한 docs/STATE.md 는 갱신되지 않았다. 두 SSOT 급 문서가 정반대를 말한다.' 그 회고 보고서를 아카이브한 #1107 을 포함해 이후 7 PR 이 머지되는 동안 STATE.md 는 한 번도 수정되지 않았다(git log -- docs/STATE.md 최신 = b79a789/#1100).
- **권고**: STATE.md:25 를 '#1100 은 root 레벨·핸들러만 고쳐 운영에서 inert 였고, 실제 봉인은 #1102(alembic fileConfig 의 disable_existing_loggers 가 앱 로깅 파괴) 였다' 로 정정하고 #1102 를 최신 블록에 등재한다. 나아가 회고 보고서를 아카이브하는 PR(#1107 류)의 완료 조건에 '보고서가 STATE.md 를 직접 지목한 finding 전수 반영' 을 포함시킬 것 — 보고서를 파일로 저장하는 것과 그 내용을 SSOT 에 반영하는 것은 별개 작업이며, 이번에 전자만 수행됐다.

### P1-30. [docs] 필수 6-step ⑤ 미이행 — 세션 7 PR 종료 시점까지 trailing sync PR 부재로 STATE·cycle-history·README×2 전부 stale, 테스트 배지 15건 drift

- **위치**: `docs/cycle-history.md:145`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: CLAUDE.md 필수 원칙 6-step ⑤ 는 'docs/STATE.md 수치 갱신 + docs/cycle-history.md 사이클 이력 동기화' 를 '예외 없음' 으로 규정하고, 배치-PR 이월 분기는 per-PR 생략을 허용하되 '세션 종료 시 단일 trailing sync PR 로 이월' 을 조건으로 단다. 본 세션은 7 PR(#1102~#1108)을 머지하고 종료했으나 sync PR 이 생성되지 않았다(`gh pr list --state open` → 0건). 결과 실측 drift 4종: (1) STATE.md:5 날짜 헤더가 여전히 '2026-07-18 기준' — STATE.md 자신의 갱신 규칙 (0)번이 명시적으로 요구하는 필드다. (2) #1101~#1108 8 PR 이 STATE.md 에 0건 등재(각 PR 번호 grep 전부 0). (3) docs/cycle-history.md 최신 본문 섹션이 :145 '세션2 회고 + 회고 fix 4 트랙 11 PR (2026-07-18)' 로, 2026-07-19 세션(#1094~#1108, 15 PR)이 통째로 부재. (4) 테스트 수치가 4곳에서 stale — 실측 `pytest tests/unit --collect-only` = **5585** 인데 STATE.md:26·:30 과 README.md:21·README.ko.md:21 이 모두 '5570 unit' 을 단언(drift 15). 부수적으로 STATE.md 최신 블록 제목은 '총 17 PR #1077~#1092' 인데 본문 불릿은 #1100 까지 이어져 제목과 내용이 자기모순이며, 이는 STATE.md:7 이 '헤더에 직전 체인 누적 금지 — 본 정리의 회귀 방지' 로 금지한 바로 그 패턴의 재발이다.
- **권고**: 세션 종료 sync PR 1건으로 일괄 처리: STATE.md:5 날짜 헤더 → 2026-07-19, 최신 블록을 2026-07-19 세션(#1094~#1108)으로 교체하고 2026-07-18 서사는 cycle-history.md 맨 앞 섹션으로 이관(제목-본문 자기모순 동시 해소), 수치 4곳을 실측 5585 로 갱신. 🔴 구조적으로는 배치-PR 이월 분기가 '세션 종료' 라는 인지 의존 시점에 걸려 있어 이번처럼 조용히 유실된다 — 직전 회고가 P0 로 규정한 '문서-only 시정은 행동을 못 바꾼다' 와 동형이므로, SessionEnd 훅 또는 `git log` 기반 'STATE.md 미갱신 머지 PR N건' 카운터(check_retro_cadence.py 와 동일 패턴)로 기계화할 것을 권한다.

### P1-31. [docs] #1107 이 아카이브한 회고 보고서가 INDEX.md 미등재 — 14건 전례 100% 등재와 단절

- **위치**: `docs/_archive/reports/INDEX.md:75`
- **verdict**: CONFIRMED
- **주장**: #1107 은 `docs/_archive/reports/2026-07-19-retrospective.md`(694줄, 164 에이전트·135 확정)를 추가하고 architecture.md 등재는 수행했으나, 같은 디렉토리의 `docs/_archive/reports/INDEX.md` §회고 표에는 등재하지 않았다. 해당 표(:42~:75)의 마지막 행은 2026-07-18 이며, 2026-04-19 이후 아카이브된 회고 14건이 예외 없이 전부 등재돼 있어 전례는 명확하다. INDEX.md 는 :3 에서 스스로를 '감사·회고·로드맵 보고서 목록' 으로 규정하므로 미등재 = 목록의 완전성 계약 위반이다. 실질 영향은 발견 가능성 — 본 보고서는 확정 135건(P0 11·P1 66·P2 58) 중 이번 세션이 조치한 소수를 제외한 대부분이 백로그로 남아 있고, 그 백로그로 가는 유일한 색인 경로가 끊긴 상태다.
- **권고**: INDEX.md §회고 표에 '| 2026-07-19 | [retrospective](2026-07-19-retrospective.md) | 세션2 remediation 22 PR(#1078~#1101) 5+1 회고 — 164 에이전트·135 confirmed(P0 11·P1 66·P2 58)·FP 7·verdict 커버리지 1.0 |' 행을 추가한다. 회고 보고서 아카이브를 수행하는 워크플로우(.claude/workflows/retrospective.mjs) 또는 그 runbook 의 완료 조건에 'INDEX.md 등재' 를 명시해 인지 의존을 제거할 것 — 파일 추가와 색인 등재가 분리된 2 동작인 한 같은 누락이 반복된다.

### P1-32. [decision] 사용자 발화 1문장이 3항목 위험 수용 논거 + 재개 조건으로 확장 — 논거는 Claude 저작인데 결정은 사용자에게 귀속

- **위치**: `docs/runbooks/owed-verification.md:53`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1108 이 인용한 사용자 발화는 "토큰과 키는 그대로 사용 예정입니다" 단 한 문장이다. 이는 credential 을 계속 쓰겠다는 사용 의사 표명이지, 로그 평문 노출 위험을 수용한다는 보안 판단이 아니다. Claude 는 이를 3항목 위험 수용 논거 + 각 행 재개 조건 + 잔여 위험 명세로 확장한 뒤 원장에 '사용자 명시 결정' 으로 기재했다. 논거 ②는 실측 없는 추정이다.
- **권고**: 원장 행에 '사용자 발화 원문' 과 'Claude 가 보충한 논거' 를 시각적으로 분리 표기한다(예: > 인용 블록 + "이하 Claude 작성 근거"). ② 는 실측(Railway 로그 보존 정책 확인) 전까지 근거에서 제외하거나 "미실측 가정" 으로 명시. 보안 위험 수용은 Claude 가 논거를 대신 쓰지 말고 사용자에게 항목별 확인을 받는다.

### P1-33. [decision] 반증된 §섹션이 무효화 표기 없이 존치 — #1108 이 '결론 무효화 기전 부재' 를 조치했다 주장했으나 최대 stale 2곳은 그대로

- **위치**: `docs/runbooks/owed-verification.md:111`
- **verdict**: CONFIRMED
- **주장**: §111-124("검증 수단 정정 — Railway cron 로그 관측은 실행 불가")의 결론과 :88 의 검증 기준은 같은 세션의 #1102·#1105 로 반증됐다(로그가 직접 증거가 됐다). 원장은 표의 **행**(:41)에만 ❌ 오귀인 표기를 달고 독립 §섹션과 :88 은 손대지 않았다. 섹션만 읽는 다음 세션은 반증된 결론을 사실로 받는다 — 이번 사고의 근본 재생산이다.
- **권고**: §111 헤딩을 `## ⛔ [반증됨 2026-07-19 — #1102] 검증 수단 정정 …` 형태로 접두 표기하고 :88·:122 에 1줄 무효화 주석을 단다. append-only 원장에는 '행 상태' 뿐 아니라 '서술 섹션' 무효화 마커 규약이 필요하다(범례 :7 에 추가).

### P1-34. [code] #1104 리댁션 계층 2 가 exc_info 트레이스백을 전혀 덮지 않음 — PR 본문의 커버리지 단언이 실증 반증됨

- **위치**: `src/logging_config.py:61`
- **verdict**: CONFIRMED
- **주장**: `_RedactSecretsFilter.filter()` 는 `record.getMessage()` 만 검사·치환한다. `logging.Formatter.format()` 은 그 뒤에 `formatException(record.exc_info)` 를 **별도로** 덧붙이므로, `logger.exception(...)`/`exc_info=True` 로 남는 트레이스백 안의 토큰은 마스킹되지 않는다. PR #1104 본문은 "계층 1 을 통과하는 httpx WARNING(재시도·타임아웃)과 **우리 코드의 실수**는 이 필터만이 막는다" 고 단언했으나, src/ 의 예외 로깅 20+ 지점 전체가 무방비다. 해당 채널을 검증하는 가드 테스트도 없다.
- **권고**: 필터에 exc_info 경로를 추가한다 — `record.exc_text` 가 이미 캐시돼 있으면 그 문자열에도 `_SECRET_URL_PATTERNS.sub` 적용하고, 미생성 시 `record.exc_info` 를 포맷해 마스킹 후 `exc_text` 에 넣는다. 가드 테스트는 `logger.exception` 으로 발생시킨 레코드의 **핸들러 최종 출력**에 토큰이 없음을 단언(현 가드 6건은 전부 메시지 경로만 검사). 참고: 같은 갭이 src/main.py:230 `logger.exception("DB migration failed")` 의 DB URL 비밀번호에도 적용된다(별건·기존 결함).

### P1-35. [process] 6-step ⑤ 가 세션 전체(7 PR)에서 미수행 — 이월 분기의 trailing sync PR 도 없이 세션 종료

- **위치**: `docs/STATE.md:26`
- **verdict**: CONFIRMED
- **주장**: #1102~#1108 중 어느 PR 도 docs/STATE.md · README 배지 · docs/cycle-history.md 를 갱신하지 않았다. 6-step ⑤ 의 배치-PR 이월 분기는 '세션 종료 시 단일 trailing sync PR 로 이월' 을 허용하지만, 회고 아카이브(#1107)와 #1108 을 끝으로 세션이 종료되고 sync PR 은 생성되지 않았다. 결과 STATE.md 헤더 수치가 실측과 어긋난 채 고착됐다.
- **권고**: STATE.md:26 을 단위 5581 / pylint 9.99 로 정정하고 cycle-history 에 본 세션 항목을 추가하는 sync PR 을 다음 세션 진입 시 최우선 처리. 이월 분기 적용 시 '세션 종료 전 sync PR 생성' 을 SessionEnd 훅 또는 owed 원장 행으로 기계화하지 않으면 이월 = 소실이 반복된다(본 건이 실증).

### P1-36. [tooling] #1104 계층 2 리댁션이 Telegram 단독 — 앱 자체 코드 5곳이 Discord/Slack/n8n/custom webhook URL(경로 자체가 시크릿)을 WARNING 평문 로깅, 회고 보고서가 이를 명시하는데 #1107 이 그 보고서를 커밋하면서 후속 등재 0건

- **위치**: `src/logging_config.py:33`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS`(src/logging_config.py:33-35)는 `api\.telegram\.org/bot` 단일 패턴만 담는다. 그런데 저장소에는 Discord/Slack/n8n/custom webhook URL 전문을 **WARNING 레벨로** 로깅하는 코드가 5곳 실재한다 — `src/notifier/discord.py:101` · `src/notifier/slack.py:117` · `src/notifier/n8n.py:53` · `src/notifier/n8n.py:83` · `src/notifier/webhook.py:54`, 모두 `logger.warning("...: blocked unsafe URL '%s'", webhook_url)` 형태다. 이 경로는 #1104 의 두 계층을 **모두** 우회한다: 계층 1(httpx WARNING 강등)은 `httpx` 로거 대상이라 우리 `src.notifier.*` 로거에 무관하고, 계층 2(리댁션 필터)는 Telegram 패턴만 매칭한다. Discord(`discord.com/api/webhooks/<id>/<TOKEN>`)·Slack(`hooks.slack.com/services/T…/B…/<SECRET>`)은 Telegram 과 동일하게 **경로가 곧 credential** 이므로 완전히 같은 결함 클래스다. 결정적으로 #1107 이 저장소에 커밋한 회고 보고서 본문이 이를 이미 명시한다 — `docs/_archive/reports/2026-07-19-retrospective.md:110` P0-7 주장: "동일 경로로 Discord/Slack/n8n webhook URL(경로 자체가 시크릿) 도 노출된다 — 4 notifier 전부 `build_safe_client()` = httpx 사용"(verdict CONFIRMED, `build_safe_client` 실측 확인: `src/notifier/_http.py:86` 정의, discord:107·n8n:35·slack:123·webhook:57 사용). 즉 Claude 는 미해결 노출을 명시한 문서를 저장소에 커밋하면서 원장 행도 후속 PR 도 만들지 않았다(`grep -n "Discord\|Slack\|n8n\|webhook" docs/runbooks/owed-verification.md` → 해당 항목 0건). 정책 16 진화("같은 값/로직이 2+곳에 있을 때 수정 **직전** `grep -rn` 전 호출처 열거 후 diff/PR 본문에 '전수 확인 N곳' 명시")도 미적용 — #1104 커밋 본문에 전수 확인 문구가 없고, 오히려 "**우리 코드의 실수**는 이 필터만이 막는다"고 단언해 실제로 막지 못하는 5곳을 반증 사례로 갖는다.
- **권고**: `_SECRET_URL_PATTERNS` 에 Discord(`discord(?:app)?\.com/api/webhooks/\d+/`) · Slack(`hooks\.slack\.com/services/`) · 범용 n8n/custom 패턴을 추가하고, 5개 WARNING 로깅 사이트는 URL 전문 대신 host+경로 앞부분만 남기거나 `sanitize_for_log` 를 함께 적용한다. 회귀 가드는 #1104 가 채택한 '핸들러 포맷 최종 출력 검사' 패턴을 채널별로 parametrize 한다. 프로세스: 회고 보고서 아카이브 PR(#1107 류)은 **보고서 내 미해결 CONFIRMED 항목을 owed 원장 행으로 자동 승격**하는 단계를 동반해야 한다 — 그러지 않으면 아카이브가 '기록했으므로 처리됨' 착시를 만든다.

### P1-37. [tooling] logging_isolation fixture 의 실측 blast radius 는 커밋 주장의 약 10배 — "타 파일 5건" vs 실측 48건(≥4개 영역), 순서 의존 오염이라 스코프 실행에서 전량 은폐

- **위치**: `tests/unit/conftest.py:49`
- **verdict**: CONFIRMED
- **주장**: #1102 커밋 본문은 fixture 를 "load-bearing 실증: 무력화 시 **타 파일 5건** 연쇄 실패 (caplog 파괴)" 로 기술한다. 격리 worktree 에서 fixture 본문을 `yield` 단독으로 무력화하고 `pytest tests/unit -q` 전량 실행한 실측은 **48 failed, 5533 passed**(75.5s)였다 — 주장의 9.6배. 실패는 최소 4개 영역에 걸쳐 있다: `tests/unit/test_main.py`(lifespan 경고 6건 이상) · `tests/unit/ui/test_null_owner_visibility.py` · `tests/unit/worker/test_pipeline_pr_regate.py`(2건) · `tests/unit/worker/test_pipeline_save_and_gate.py`(4건). 동일 worktree 에서 fixture 를 복원하면 `5581 passed, 4 skipped, 0 failed`(68.0s) — 즉 48건 전부가 fixture 단독 귀속이다. 질문 (b)에 대한 답: **opt-in(non-autouse)이라 기존 테스트에 부작용을 주지 않는다는 주장은 참**이지만(복원 상태 5581 green 실측), "무해하다"는 결론과 "5건" 이라는 정량화는 결합도를 심각하게 과소 표현한다. 실제 구조는 tests/unit 전역이 이 fixture 의 정확한 복원 로직(`logging._handlerList`/`logging._handlers` 등 CPython private 레지스트리 복구 포함)에 48건 규모로 의존하는 형태다. 위험 특성이 고약하다 — 이 48건은 **전체 스위트 순서 의존 오염**이라 파일/영역 단위 실행에서는 전량 green 이다(가드 파일 단독 실행 = 7 passed). 즉 6-step ② push-전 전체 게이트만이 유일한 탐지 수단이고, 위 P1(스모크 훅 사각지대)과 겹쳐 편집 시점에는 어떤 신호도 나오지 않는다.
- **권고**: 수치를 48 로 정정하고(정책 6 실측 의무 — 이 주장은 재현 시 즉시 반증된다), fixture docstring 에 '이 fixture 의 복원 로직 훼손 시 tests/unit 전역 48건이 순서 의존적으로 실패한다'를 명시해 향후 편집자가 결합도를 인지하게 한다. 회귀 가드: fixture 자체의 복원 정확성을 단언하는 메타 테스트(스냅샷→오염→복원→상태 동등성)를 추가해, 48건 연쇄 실패라는 간접·고비용 신호에 의존하지 않도록 한다.

### P1-38. [security] 리댁션 패턴이 Telegram 1종만 커버 — Discord·Slack·n8n·custom webhook 토큰이 평문 로깅 (P1-56 미조치, main 실측)

- **위치**: `src/logging_config.py:39`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1104 의 `_RedactSecretsFilter` 는 `api\.telegram\.org/bot` 단일 패턴만 보유한다. 저장소 자체 코드가 credential-in-path URL 을 WARNING 으로 평문 로깅하는 호출처가 6곳 존재하며, Discord(`/api/webhooks/<id>/<token>`)·Slack(`/services/T../B../<secret>`)·n8n(`/webhook/<uuid>`)·custom(`?token=`) 은 전부 마스킹되지 않는다. 트리거는 운영자 오설정에 국한되지 않는다 — `validate_external_url` 이 일시적 DNS 실패(OSError)에도 False 를 반환하므로 정상 설정 상태에서 DNS 순단 한 번이면 4개 provider 토큰이 평문으로 남는다. 계층 1(httpx WARNING 격하)은 우리 코드의 WARNING 로그를 막지 못하고, 계층 2 필터는 이 패턴들을 모른다. 🔴 사용자가 credential 로테이션을 명시 거부(a810e15)했으므로 유출 시 회수 수단이 없다.
- **권고**: 2겹 적용. (1) 즉시 패턴 추가 — `(discord(app)?\.com/api/webhooks/\d+/)[^/\s]+`, `(hooks\.slack\.com/services/T[^/]+/B[^/]+/)[^/\s]+`, `([?&](?:token|key|secret|access_token)=)[^&\s]+`. (2) 🔴 근본 수정 — denylist 는 신규 provider 마다 영구 지연하고 n8n·custom 은 self-hosted 임의 경로라 패턴화가 원리적으로 불가하므로, 6 호출처가 전문 URL 을 아예 로깅하지 않도록 `f"{parsed.scheme}://{parsed.hostname}"` allowlist 전환. 회귀 가드는 provider 5종 parametrize 로 봉인.

### P1-39. [retro-finding remediation] 확정 발견의 미조치 — 권고 이행 창(#1104 OPEN)이 검증 없이 닫힘 (finding→fix 단절)

- **위치**: `docs/_archive/reports/2026-07-19-retrospective.md:535`
- **verdict**: CONFIRMED
- **주장**: P1-56 은 '#1104 가 OPEN 인 지금 동일 PR 에 fix-up commit(정책 10 fix-up default)' 을 명시 권고했으나, 실제 머지된 #1104(556ef82)는 `src/logging_config.py` + 테스트 2파일만 담았고 권고 내용은 한 줄도 반영되지 않았다. 어떤 관점도 '#1104 머지 시점에 이 권고가 반영됐는지' 를 사후 확인하지 않았다. 리뷰는 돌았고 발견은 확정됐으나 조치 창이 조용히 닫힌 구조적 결함이다. 동반 P2 2건(:675 provider 미parametrize · :676 sanitize_for_log 미적용)도 동일하게 미조치. 근인 = 미머지 PR 이 회고 scope 밖으로 새는 구멍(직전 회고 wf_b506429b 범위는 #1078~#1101 이었고 본 6 PR 은 범위 밖) + 정책 16 `grep -rn` 전수 의무 미적용.
- **권고**: (1) 즉시 fix PR 착수(P0 finding 참조). (2) 기계 가드 신설 — 회고 리포트의 P0/P1 권고 중 'PR #N 에 fix-up' 유형은 해당 PR 머지 시점에 반영 여부를 확인하는 체크를 `scripts/` 에 추가하거나, owed 원장에 '권고 이행' 행으로 등재해 SessionStart 훅 집행면에 올린다. 문서-only 시정은 본 세션에서만 3회차 실패했다.

### P1-40. [미검증 양식] #1104 리댁션 테스트 226줄이 전부 Telegram — provider 클래스 미parametrize 로 false-green ('가드의 가드' 연장)

- **위치**: `tests/unit/test_logging_config.py:158`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1104 이 추가한 리댁션 가드 6건은 모두 단일 상수 `_FAKE_TELEGRAM_URL` 만 사용한다. Discord·Slack·n8n·custom 케이스가 0건이라, 필터가 4개 provider 를 전혀 마스킹하지 못하는 현 상태에서도 스위트는 100% green 이다. 즉 테스트가 '리댁션이 동작한다' 를 단언하는 것처럼 보이지만 실제로는 'Telegram 에 대해서만 동작한다' 만 단언한다 — 직전 회고가 P0 로 규정한 '가드의 가드' 결함 클래스의 재생산이다.
- **권고**: provider 5종(telegram·discord·slack·n8n·custom querystring) `@pytest.mark.parametrize` 로 전환하고, 각 provider 의 실제 URL 형태에 대해 '토큰 부재 + 도메인 구조 보존' 을 단언. 이렇게 하면 P0 finding 의 패턴 추가가 회귀 가드로 봉인된다.

### P1-41. [process] 아카이브가 카덴스 카운터를 리셋하면서 124건은 0건 이월 — 회고 종결이 집행면 순-감소를 일으킨다

- **위치**: `scripts/check_retro_cadence.py:113`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1107 의 아카이브 행위는 기계 집행면에 **정확히 하나의 효과**를 낸다 — 회고 카덴스 카운터를 0 으로 리셋해 '회고 필요' loud 경고를 끄는 것. 그리고 P1 66·P2 58 = 124건에 대해서는 조치·보류·기각 어느 처분도 이월하지 않는다. 즉 회고를 종결짓는 단일 행위가 동시에 (a) 그 회고를 다시 시야로 끌어올릴 유일한 반복 신호를 침묵시키고 (b) 아무것도 앞으로 나르지 않는다. 아카이브 전이 아카이브 후보다 집행면이 더 강했다 — 순-감소다.
- **권고**: 아카이브 PR 의 완료 조건에 '처분 이월' 을 결속한다 — 리포트 아카이브 커밋은 (1) 미처리 P1/P2 를 백로그 표(`docs/STATE.md` 또는 전용 `docs/backlog.md`)로 이월한 diff 를 **같은 커밋**에 포함해야 하고(정책 4: 단언과 가드를 같은 PR 에), (2) `check_retro_cadence.py` 에 '최신 리포트의 미처분 finding 수 > 0 이면 카운터 리셋과 무관하게 별도 배너' 를 추가한다. 리셋 조건을 '리포트 존재' 가 아니라 '리포트 + 처분 이월 존재' 로 바꾸는 것이 최소 변경이다.

### P1-42. [process] 리포트 자신의 CONFIRMED P1-3·P1-47 미이행 — wf_40082e43(확정 147건) 리포트는 여전히 미아카이브

- **위치**: `docs/_archive/reports/2026-07-19-retrospective.md:163`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 리포트가 두 개의 독립 finding(P1-3, P1-47 — 둘 다 CONFIRMED)으로 '2026-07-19 범위한정 회고(wf_40082e43, 186 에이전트, 확정 147 = P0 2·P1 55·P2 90)의 리포트 파일이 없다' 를 지목하고 아카이브를 권고했다. #1107 은 아카이브를 수행했으나 **자기 자신(wf_b506429b)의 리포트**를 아카이브했을 뿐, 지목된 wf_40082e43 리포트는 지금도 존재하지 않는다. 결과적으로 두 회고를 합쳐 P1 121·P2 148 규모가 처분 기록 없이 남았고, 그중 147건은 리포트 파일조차 없어 STATE 한 줄이 유일한 흔적이다. 더 나쁜 것은 두 회고가 같은 날짜(2026-07-19)라 카덴스 카운터는 이미 리셋됐다 — 미아카이브 회고는 앞으로도 영원히 신호를 만들지 않는다.
- **권고**: wf_40082e43 리포트를 워크플로우 result JSON 에서 재생성해 `2026-07-19-scoped-retrospective.md` 등 구별 가능한 파일명으로 아카이브하고, 두 리포트의 미처리 P1/P2 를 단일 백로그 표로 통합 이월한다. 재생성 불가라면 STATE.md:19 에 '리포트 소실 — 확정 147건 재조회 불가' 를 명시해 손실을 기록으로 확정할 것(조용한 소실 < 명시된 손실).

### P1-43. [security] 구조적 공백의 첫 실증 — P1-56(리댁션 provider 1종) 이 조치·기각 기록 없이 유실, main 은 여전히 Telegram 전용

- **위치**: `src/logging_config.py:39`
- **verdict**: CONFIRMED
- **주장**: gap 브리프가 지목한 '조용한 유실' 이 실재함을 코드로 확인했다. 리포트 P1-56 은 리댁션 패턴이 Telegram 1종뿐이라 Discord·Slack·n8n webhook 토큰이 평문 로깅됨을 **필터 직접 실행으로 실증**(telegram redacted=True / discord·slack·n8n=False)하고, DNS 순단만으로도 트리거된다는 점에서 저장소 자체 캘리브레이션상 P0 이라 명시했으며, '#1104 가 OPEN 인 지금 동일 PR fix-up' 이라는 시한부 권고를 달았다. #1104 는 fix-up 없이 머지됐고, 리포트 P2 에도 동일 결함이 중복 기록됐으나 **두 건 모두 처분 기록이 없다**. 조치도 기각도 아닌 무처분 = 유실.
- **권고**: P1-56 권고 (2)(allowlist 전환 — `f"{parsed.scheme}://{parsed.hostname}"` 만 로깅)를 채택한다. denylist 패턴 추가는 n8n·custom self-hosted 임의 경로를 원리적으로 못 덮으므로 미봉이다. 회귀 가드는 provider 4종 parametrize 로 봉인. 동시에 이 건을 '무처분 유실 1호 사례' 로 백로그 표에 기록해 이월 규칙 신설의 근거로 남길 것.

### P1-44. [process] 6-step ⑤ 전면 미이행 — 본 세션 7 PR 이 STATE·cycle-history 양쪽에 0건, trailing sync PR 부재

- **위치**: `docs/STATE.md:5`
- **verdict**: CONFIRMED
- **주장**: P1/P2 백로그가 관례적으로 안착하던 **다른 두 지점**도 이번 세션엔 비어 있다. 6-step ⑤(STATE.md 수치 갱신 + cycle-history.md 사이클 이력 동기화)가 세션 전체에 대해 한 번도 수행되지 않았고, 배치-PR 이월 분기가 허용하는 '세션 종료 시 단일 trailing sync PR' 도 존재하지 않는다(원격 브랜치 4개·open PR 0건). cycle-history 는 역사적으로 회고 백로그의 정본 서술처였는데(다수 선례 존재) 이번엔 항목 자체가 없다. 결과: 아카이브 문서 1곳 + 그 어디에도 없음 = 브리프가 지적한 '재조회 가능한 유일 지점' 이 실제로 단 하나임이 확정된다.
- **권고**: trailing sync PR 을 즉시 생성해 (1) STATE 헤더 날짜 2026-07-19 갱신 + '최신' 블록을 #1102~#1108 로 교체, (2) cycle-history 최신순 맨 앞에 본 세션 섹션 추가하며 그 안에 **미처분 P1/P2 백로그** 를 명시(선례 다수: cycle-history.md:337·:320·:257 이 회고 백로그를 본문에 남긴 형식), (3) README 배지 동기화. 아울러 6-step ⑤ 의 배치 이월 분기에 '세션 종료 시 trailing sync PR 부재 = ⑤ 미이행' 판정을 명문화한다.

### P1-45. [tooling / owed 원장 집행면] weekly-reports 검증이 파서 사각의 산문으로만 존재 — #1106 이 봉인 선언한 클래스를 같은 파일에 재생산

- **위치**: `docs/runbooks/owed-verification.md:43`
- **verdict**: CONFIRMED
- **주장**: 인앱 스케줄러 5종 중 weekly-reports 의 유일한 검증 기록은 owed-verification.md:43 의 산문 한 줄이며, 원장 파서가 구조적으로 절대 인식할 수 없다. #1106 이 '인지 의존 산문 4회차 봉인' 을 선언한 바로 그 파일 안에서 동형 패턴이 재생산됐다.
- **권고**: weekly-reports 를 운영등급 표에 행으로 등재(검증 방법 = 월요일 00:00 UTC 이후 로그의 `[src.scheduler] scheduler weekly_reports: sent=N`, 상태 ⏳). 산문 :43 은 행으로 대체하거나 행을 가리키는 포인터로 축약.

### P1-46. [docs] STATE.md 가 자기 문서에 명시된 갱신 규칙을 위반 — 이것이 cycle-history 공백을 만든 기전

- **위치**: `docs/STATE.md:7`
- **verdict**: CONFIRMED
- **주장**: STATE.md:7 은 갱신 규칙을 '(1) 본 "최신" 블록을 새 작업으로 **교체** + 종합 수치 갱신, (2) 직전 작업의 전체 서사는 cycle-history.md 최신순 맨 앞에 **이관** (헤더에 "직전" 체인 누적 **금지** — 본 정리의 회귀 방지)' 로 못박고 있다. 실제로는 :9 의 2026-07-18 세션2 블록이 교체되지 않은 채 남고, :18~:25 에 #1094~#1100 불릿이 **append** 됐다. 즉 규칙이 금지한 '직전 체인 누적' 을 그대로 재생산했다. 이관 단계가 실행되지 않았기 때문에 cycle-history 가 0건인 것 — 두 결함은 별개가 아니라 **동일 원인의 상·하류**다.
- **권고**: sync PR 에서 :9 블록을 2026-07-19 세션으로 **교체**하고 2026-07-18 세션2 서사 전체를 cycle-history.md 로 이관. 규칙이 3회 연속 미준수됐으므로(2026-07-03 C5 → 본 세션) `doc_review_gate.py` 에 '최신 블록 날짜 헤더 ≠ 최신 머지 PR 날짜' 또는 '최신 블록에 2개 이상 세션 라벨 공존' 탐지를 추가해 산문-only 규칙을 기계면으로 승격할 것.

### P1-47. [security] #1104 가 고친 것과 동일한 결함 클래스가 5개 notifier 로그 라인에 미수정 잔존 — webhook URL 전문(경로 내 credential)을 WARNING 으로 직접 로깅

- **위치**: `src/logging_config.py:38`
- **verdict**: CONFIRMED
- **주장**: `_SECRET_URL_PATTERNS`(src/logging_config.py:38-40)는 `api.telegram.org/bot<TOKEN>` **단 하나만** 커버한다. 그런데 우리 코드 5곳이 Discord/Slack webhook URL **전문**을 WARNING 으로 로깅한다. Discord(`/api/webhooks/{id}/{token}`)·Slack(`/services/T../B../{secret}`)은 Telegram 과 **똑같이 credential 이 URL 경로에 있는** 서비스다. 계층 1(httpx→WARNING 강등)은 우리 자신의 로그 라인에 무력하고, 계층 2(필터)는 패턴이 없어 통과시킨다. 실증: 두 URL 형태를 필터에 통과시킨 결과 시크릿이 **평문 그대로 출력**됐다.
- **권고**: `_SECRET_URL_PATTERNS` 에 `(hooks\.slack\.com/services/)\S+` · `(discord(?:app)?\.com/api/webhooks/\d+/)[^/\s]+` 추가(캡처 그룹 1 보존 = 판독성 유지 규약 준수). 더 근본적으로는 5개 로그 라인이 URL 전문 대신 `sanitize_for_log()` 또는 호스트만 찍도록 교정. 회귀 가드는 기존 `tests/unit/test_logging_config.py` 의 telegram 케이스와 동형으로 parametrize 확장.

### P1-48. [process] 정책 12 재발 방지 규칙이 산문-only — 회고 보고서가 명시 권고한 `.claude/rules/security.md` 등재가 미이행 ('문서-only 시정' 4회차)

- **위치**: `.claude/rules/security.md:16`
- **verdict**: CONFIRMED
- **주장**: 본 세션의 정책 12 위반(`railway variables --kv | grep` 이 값까지 매칭 → INTERNAL_CRON_API_KEY 평문 출력)에 대한 재발 방지 규칙이 **어떤 집행면에도 없다**. 회고 보고서 자신이 :132 에서 '재발 방지 규칙을 메모리가 아니라 `.claude/rules/security.md` 에 등재' 를 명시 권고했는데, `.claude/rules/security.md`(32줄)에는 해당 규칙이 없다. 규칙의 유일한 거처는 owed 원장 :54 의 **⏭️ 로 닫힌 행 안** 이다. 원장 :71 은 '전 행 ✅/⏭️ 확정 시 = 아카이브 섹션으로 이동' 을 규정하므로, 그 행이 아카이브되는 순간 규칙은 활성 표면에서 **자동 소실**된다. 회고가 P0 로 규정한 '문서-only 시정은 행동을 못 바꾼다' 를 같은 세션이 다시 재생산한 것(원장 :141 이 3회차로 기록 → 본 건이 4회차).
- **권고**: `.claude/rules/security.md` 에 규칙 등재(회고 권고 그대로 이행) — path-scoped 자동 로드라 원장 아카이브와 무관하게 생존한다. 원장 :54 는 규칙 정본이 아니라 참조로 강등. 여력이 되면 PreToolUse Bash matcher 훅으로 `railway variables` + `grep` 동시 출현을 차단하는 기계면까지 승격(산문 4회차라는 이력이 기계화 임계를 이미 넘었다).

### P1-49. [correctness] `_RedactSecretsFilter` 가 exc_info/stack_info 트레이스백을 커버하지 않음 — 코드 주석의 '이 필터만이 막는다' 는 과대 단언

- **위치**: `src/logging_config.py:51`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: 필터는 `record.getMessage()` 결과(= msg + args)만 치환한다(:61-78). 그러나 `logging.Formatter.format()` 은 `record.exc_text`(트레이스백)를 `formatMessage()` **이후에 별도로 append** 하므로 필터를 거치지 않는다. 실증: 토큰이 든 URL 을 메시지에 담은 예외를 `logger.exception()` 으로 기록하니 본문 라인은 `bot***` 로 마스킹됐지만 트레이스백의 `RuntimeError: ... url 'https://api.telegram.org/bot123456:AAHsecret.../sendMessage'` 는 **평문 그대로 출력**됐다. 따라서 :51-54 의 '**우리 코드가 실수로 토큰을 로깅하는 경우**나 httpx 의 WARNING 경로는 이 필터만이 막는다' 는 exc_info 경로에 대해 사실이 아니다. 🔴 **정직한 심각도 판정**: 현행 코드에서 telegram 토큰을 실은 예외가 로깅되는 **도달 경로는 실증하지 못했다** — telegram.py 는 `raise_for_status()` 를 쓰지 않고 상태코드를 수동 분기하며(:52-), `raise_for_status()` 사용처(github_review·github_client)는 토큰이 헤더에 있는 api.github.com 이다. 따라서 라이브 유출이 아니라 **심층방어 공백 + 부정확한 단언**으로 P2 로 판정한다.
- **권고**: 필터에서 `record.exc_info`/`record.exc_text`/`record.stack_info` 도 치환 대상에 포함하거나(단순·정확), 최소한 :51-54 주석을 'msg/args 한정 — 트레이스백은 미커버' 로 정정해 다음 세션이 잘못된 보증을 신뢰하지 않게 할 것. 후자만 해도 오판 위험은 제거된다.

### P1-50. [process] auto-merge 게이트 fix-up 레이스가 동일 세션 내 재발 — #1103 커밋 고아화, 직전 세션 #1077/#1079 와 동일 클래스

- **위치**: `docs/STATE.md:10`
- **verdict**: SEVERITY_ADJUST (심각도 조정 P1 → P1)
- **주장**: #1103 을 #1102 브랜치에 fix-up 으로 얹으려는 사이 #1102 가 SCAManager 자체 auto-merge 게이트에 의해 먼저 머지돼 커밋이 고아가 됐고, main 에서 cherry-pick 으로 복구했다. 이는 신규 결함이 아니라 **직전 세션에서 이미 발생한 것의 재발**이다 — STATE.md:10 이 '#1079 … P2#4 loud-fail read(**게이트 auto-merge 레이스로 fix-up 유실** → 별도 fix PR)' 로 같은 실패 모드를 기록해 두었다. 정책 10 의 'fix-up commit default: 머지 전 CI fail/회귀 = 동일 PR 브랜치 추가 commit' 은 **PR 이 아직 열려 있다는 전제**에 의존하는데, auto-merge 환경에서 그 전제는 turn 간 무효화될 수 있다.
- **권고**: 정책 10 fix-up default 에 전제 조건 1줄 추가: 'fix-up 착수 **직전** `gh pr view <n> --json state` 로 OPEN 확인 의무 — auto-merge 리포에서는 머지 여부가 turn 간 바뀐다'. 2회 연속 동일 사고이므로 산문보다는 fix-up 착수 시 상태 확인을 강제하는 형태가 바람직하다.

### P1-51. [memory / 자동 로드 컨텍스트] 본 세션이 새로 쓴 memory 파일이 작성 2분 만에 stale — 다음 세션에 이미 끝난 사용자 결정을 재요청하게 만든다

- **위치**: `C:/Users/dirtc/.claude/projects/d--Source-SCAManager/memory/project-logging-wipe-token-leak-2026-07-19.md:14`
- **verdict**: CONFIRMED
- **주장**: drift 교훈을 기록하려고 만든 `project-logging-wipe-token-leak-2026-07-19.md` 자체가 3중 stale 이다. (a) :12-15 §'🔴 미결 사용자 조치 (다음 세션 진입 시 회신 요청 **의무**)' 가 TELEGRAM_BOT_TOKEN·INTERNAL_CRON_API_KEY 로테이션을 미결로 지시하나, 사용자는 16:16 #1108 로 '토큰과 키는 그대로 사용 예정' 을 명시 결정했고 원장 :53-54 가 ⏭️ + 재개 조건으로 확정했다 → 다음 세션은 종결된 안전등급 결정을 재요청한다 (b) :16 '미머지 PR — #1104·#1105' 가 거짓 — #1104 는 14:36, #1105 는 14:42 머지 (파일 작성 14:38) (c) :3 `description` 이 문장 중간에서 잘림(`앱 로깅 파괴(P0,`). 배정 gap 과 동일 결함 클래스가 **같은 세션 안에서 재생산**됐다.
- **권고**: (1) :12-16 §미결 사용자 조치를 삭제하고 '✅ 사용자 명시 위험 수용(#1108) — 재개 조건은 원장 :53-54' 로 교체, :3 description 완성. (2) 세션 종료 절차에 **'memory 파일 작성 시각 이후 머지된 PR 이 있으면 memory 재확인'** 을 6-step 에 편입 — 현재 6-step ⑤는 docs/STATE.md·cycle-history.md 만 다루고 memory 는 사각지대다. (3) 근본 대책: memory 파일에 '미머지 PR 목록'·'미결 사용자 조치' 처럼 **분 단위로 낡는 상태**를 쓰지 말고 원장 링크만 남길 것 — 원장은 기계 파싱(check_owed_verification.py)되지만 memory 는 어떤 검증도 받지 않는다.

---

## P2 (75건)

### code (12)

- #1104 리댁션 필터가 로깅 예외를 호출자에게 전파 — logging 이 앱 코드를 크래시시킬 수 있음 (회귀) — `D:\\Source\\SCAManager\\src\\logging_config.py:64`
- #1102 의 fixture load-bearing 실증 수치가 ~10배 과소 — "타 파일 5건 연쇄 실패" 실측은 48건 — `D:\\Source\\SCAManager\\tests\\unit\\conftest.py:50`
- #1104 docstring 의 "lazy % 포맷 보존 + 오버헤드 최소" 주장 부정확 — 모든 레코드가 2회 포맷된다 — `D:\\Source\\SCAManager\\src\\logging_config.py:56`
- #1104 계층 1 의 httpx 일괄 WARNING 강등이 전 외부 연동의 요청 관측을 제거 — "판독성 손실 없음" 주장 과장 — `D:\\Source\\SCAManager\\src\\logging_config.py:114`
- _RedactSecretsFilter 가 무해했던 로깅 포맷 오류를 애플리케이션 치명 예외로 승격 — root 핸들러라 전 코드베이스가 사정권 — `D:\Source\SCAManager\src\logging_config.py:64`
- owed 원장 자기모순 — §"검증 수단 정정"(반증된 결론)이 3회 연속 수정에도 철회되지 않음 — `D:\Source\SCAManager\docs\runbooks\owed-verification.md:122`
- 검증 주장 정밀도 — 뮤테이션 2건은 정확히 재현되나 fixture load-bearing 은 5배 과소, 테스트 수 출처 인용은 오귀속 — `D:\Source\SCAManager\tests\unit\conftest.py:49`
- owed 원장 내부 모순 — 같은 사실을 표+산문 2곳에 중복 기록해 1 PR 만에 산문이 stale — `docs/runbooks/owed-verification.md:40`
- httpx INFO 전면 강등의 관측 손실이 '판독성 손실 없음' 단언과 불일치 — GitHub API 실패가 예외 클래스명만 남음 — `src/logging_config.py:114`
- logging_isolation blast radius 를 '타 파일 5건' 으로 10배 과소 보고 + conftest docstring 이 '옵트인 저비용' 으로 프레이밍 — `tests/unit/conftest.py:13`
- 필터 docstring 의 '오버헤드 최소화' 근거가 실제 동작과 반대 — 모든 레코드가 %-포맷을 2회 수행 — `src/logging_config.py:56`
- logging_isolation 이 opt-in 이라 향후 fileConfig 계열 테스트가 전역 오염을 흘릴 수 있음 — 현 스위트는 안전하나 구조적 방어는 파일 단위 규율에 의존 — `tests/unit/conftest.py:13`

### decision (5)

- 자기 저작 6 PR 을 리뷰 0건으로 자체 게이트가 머지 — 머지 동의의 감사 추적이 원리적으로 불가능 — `docs/runbooks/owed-verification.md:53`
- #1103 고아 커밋 — 머지 상태 미확인 상태로 선행 PR 브랜치에 fix-up 을 얹음 — `CLAUDE.md:1`
- 6 PR 전부 생성 후 4분37초~5분27초 만에 머지·리뷰 이벤트 0 — GitHub 기록상 사람의 머지 판단과 구분 불가 — `CLAUDE.md:1`
- ⏭️ 기호가 의미 3종을 한 칸에 압축 — 행 '추가' 규칙만 신설하고 '집행면 이탈' 규칙은 없다 — `docs/runbooks/owed-verification.md:56`
- 원장 3연속 수정 후 전수 정합성 패스 부재 — 같은 파일 안에서 로테이션 '필요' 와 '수행 안 함' 이 동시 진술 — `docs/runbooks/owed-verification.md:40`

### docs (23)

- 원장에 반증된 지시문 2건이 현재형으로 잔존 — 자기 문서의 '오귀인 취소선' 규율이 불균등 적용됨 — `docs/runbooks/owed-verification.md:122`
- 회고 보고서가 어떤 인덱스에서도 링크되지 않음 — cycle-history 미갱신과 겹쳐 서사 추적 단절 — `docs/_archive/reports/2026-07-19-retrospective.md:1`
- #1105 의 원장 정정이 불완전 — 반증된 "cron 로그 판별 불가" 절이 무표기로 잔존해 문서 상단과 정면 모순 — `D:\\Source\\SCAManager\\docs\\runbooks\\owed-verification.md:122`
- 본 세션 최대 gotcha(alembic fileConfig 가 앱 로깅 파괴)가 path-scoped rules 에 미등재 — 다음 Claude 가 alembic/env.py 편집 시 못 본다 — `.claude/rules/db.md:19`
- #1107 이 회고 보고서를 아카이브하면서 INDEX.md 등재 누락 — 직전 선례(#1078)가 확립한 패턴 이탈로 보고서가 고아화 — `docs/_archive/reports/INDEX.md:75`
- owed 원장 방향 지시어 오류 — '위 안전등급 #1106' 이 실제로는 아래를 가리킴 — `docs/runbooks/owed-verification.md:40`
- #1102 커밋 본문의 테스트 건수 파일 귀속 부정확 — '14/14' 를 단일 파일에 귀속 — `tests/unit/migrations/test_alembic_env_logging_guard.py:1`
- 6-step ⑤ 전면 누락 — STATE.md·README 배지 테스트 수치가 세션 전체(+15)만큼 stale, 이월 sync PR 도 없음 — `docs/STATE.md:26`
- `.claude/rules/db.md` 미동기화 — alembic/env.py 의 fileConfig 스킵 가드가 path-scoped rule 에 부재 — `.claude/rules/db.md:19`
- `.claude/rules/testing.md` 미동기화 — 신규 2층 conftest(`tests/unit/conftest.py`)가 테스트 규칙에 부재 — `.claude/rules/testing.md:15`
- CLAUDE.md 작업트리 격리 '전례 3' 미기록 — 시정이 또다시 PR 본문 산문에 머묾(본 세션이 P0 로 규정한 안티패턴 재생산) — `CLAUDE.md:391`
- #1107 이 회고 보고서를 아카이브했으나 `docs/_archive/reports/INDEX.md` 에 행을 등재하지 않음 — `docs/_archive/reports/INDEX.md:75`
- #1105 의 6-step ② 검증 수치가 stale base 에서 측정됨 — 머지 시점 main 과 6건 불일치 — `docs/runbooks/owed-verification.md:13`
- httpx WARNING 강등의 실제 디버깅 손실은 INFO 요청 로그 한정 — 그러나 근거 서사가 사실과 다르다 — `src/logging_config.py:52`
- owed 원장 내부 모순 — #1104·#1106 을 ⏭️(로테이션 안 함)로 확정한 #1108 이 같은 파일의 교차 참조 2곳을 미갱신 — `docs/runbooks/owed-verification.md:40`
- owed 원장 §근본원인·§검증수단 두 섹션이 #1073 종결 후에도 반증된 '로그 판별 불가·DB 관측 유일' 결론을 유지 — `docs/runbooks/owed-verification.md:88`
- #1107 이 '회고 P1 조치' 를 표방했으나 그 회고가 P1 2건으로 중복 지목한 wf_40082e43(186 에이전트·147 확정) 아카이브는 여전히 미이행 — `docs/_archive/reports/2026-07-19-retrospective.md:472`
- 기계 배선된 owed 원장이 docs/README.md 인덱스 미등재 — runbooks 15개 중 2개만 누락 — `docs/README.md:41`
- '정식 회고 vs 범위 한정 회고' 판정 기준 미명문화 — 카덴스 카운터가 파일명만으로 리셋하는 구조와 결합해 양방향 오판 여지 — `scripts/check_retro_cadence.py:34`
- 아카이브 회고 보고서에 workflow ID 미기록 — wf_b506429b 가 저장소 전체에 부재, 실행 추적성 단절 — `docs/_archive/reports/2026-07-19-retrospective.md:10`
- cycle-history.md 에 2026-07-19 세션 15 PR(#1094~#1108) 서사가 전무 — 6-step ⑤ 이월의 회수 시점이 이미 경과 — `docs/cycle-history.md:9`
- STATE.md stale 3종 — 날짜 헤더·미등재 8 PR·단위 테스트 수 Δ+15 (프롬프트 전제 수치는 실측과 불일치) — `docs/STATE.md:26`
- README.md 배지가 STATE.md 와 동일한 stale 수치를 복제 — 5-way 배지 sync 미이행 — `README.md:21`

### memory / 자동 로드 컨텍스트 (1)

- P0-8 정정이 지목 line 에만 적용 — 같은 파일 §'다음 세션 이어받기' 절차 지시부가 종결된 검증을 미완으로 지시 (배정 gap CONFIRMED) — `C:/Users/dirtc/.claude/projects/d--Source-SCAManager/memory/project-cron-scheduler-observability-2026-07-19.md:49`

### process (10)

- #1105 의 6-step ② 전체 스위트 수치(5575)가 머지 대상 트리(5581)의 측정값이 아님 — 게이트가 stale base 에서 실행됨 — `docs/runbooks/owed-verification.md:1`
- 회고 카덴스 카운터의 경계가 '보고서 파일 커밋' 이라, 보고서를 마지막에 아카이브하면 미회고 6 PR 이 조용히 '커버됨' 으로 삼켜짐 — `scripts/check_retro_cadence.py:89`
- #1103 커밋이 이미 머지된 브랜치 위에 작성돼 고아화 → cherry-pick 복구 (6-step ⑤ in-flight PR 사전 확인 누락) — `CLAUDE.md:1`
- #1105 의 6-step ② 실측 수치가 머지 대상이 아닌 stale base 기준 — 5575 vs 실제 5581 — `D:\\Source\\SCAManager\\docs\\runbooks\\owed-verification.md:1`
- 회고 실행 중 작업트리 오염 — tests/unit/conftest.py 가 외부에서 무력화된 상태로 방치 (worktree 격리 규칙 위반) — `tests/unit/conftest.py:49`
- 6-step ⑤ 미이행 상태로 사이클 종료 — STATE/cycle-history/README 배지가 8 PR 뒤처짐, trailing sync PR 부재 — `docs/STATE.md:5`
- 보안 통제를 호스팅하게 된 `src/logging_config.py` 가 어떤 path-scoped rules 에도 미등재 — 향후 편집 시 보안 규칙 미로드 — `.claude/rules/security.md:3`
- 리포트 양식이 runbook 의 '클러스터' 규정을 위반 — 124건이 평문 나열이라 처분 자체가 불가능한 형태 — `docs/runbooks/retrospective.md:33`
- 테스트 수 3-way drift — README 5570 · STATE 5728 수집 · 실측 5585 수집 (단, #1107 자체 검증 주장은 정확) — `README.md:21`
- 아카이브 리포트에 §자성·§후속 부재 — 정책 9 산출물이 대화에만 남고 저장소에 미보존 — `docs/_archive/reports/2026-07-19-retrospective.md:694`

### process/docs (2)

- 6-step ⑤(STATE·cycle-history·배지 동기화)가 6 PR 전건 미이행 + 이월 분기의 전제 조건(커밋 본문 delta 기록)도 미충족 — 배지·SSOT 가 실측과 11~15건 괴리 — `docs/STATE.md:5`
- 원장 단일 파일 5연속 커밋 편집의 잔여물 — 로테이션 '미결/필요' 산문 2곳이 최종 결정(⏭️ 보류)과 정면 모순 — `docs/runbooks/owed-verification.md:40`

### process/policy (1)

- #1106 의 P0 시정('기계 집행면 등재')이 같은 세션 내 다음 커밋에서 무력화 — 대체 장치인 '재개 조건'은 아무것도 검사하지 않는 산문 — `scripts/check_owed_verification.py:56`

### security (2)

- 동일 6 호출처가 사용자 제어 webhook_url 을 sanitize_for_log 없이 로깅 — CRLF 로그 인젝션 — `src/notifier/discord.py:101`
- _RedactSecretsFilter 가 getMessage() 를 emit() 보호 밖에서 호출 — 로깅 호출이 애플리케이션 코드로 예외를 전파 (신규 회귀) — `src/logging_config.py:72`

### tooling (10)

- PostToolUse 스모크 훅이 본 세션 P0 코드 PR 2건 모두에 행동 신호 0 — alembic/env.py 는 훅 자체가 미발동 — `.claude/hooks/posttool_pytest_smoke.py:60`
- 본 세션 6 PR 전부 reviews=0 — auto-merge 가 P0 보안 변경의 인간 검토 루프를 닫았다 — `docs/runbooks/owed-verification.md:53`
- src/logging_config.py 가 어떤 path-scoped rule 에도 등재되지 않아 시크릿 리댁션 작업 시 보안 규칙이 로드되지 않음 — `.claude/rules/security.md:3`
- 뮤테이션 검증 주장이 구조적으로 재현 불가 — 수작업 프로브가 도구화되지 않아 P0-1 유출 사고를 직접 유발 — `docs/_archive/reports/2026-07-19-retrospective.md:1`
- PostToolUse 스모크 훅이 top-level src/*.py 편집을 0-단언 collection 스모크로 격하하고 "✅ 스모크 통과" 배너 출력 — 본 세션 P0 2건이 정확히 그 사각지대에 착지 — `.claude/hooks/posttool_pytest_smoke.py:60`
- 동일 파일 4연속 편집(#1103·#1105·#1106·a810e15)이 모순 섹션을 그대로 통과 — 원장 :122 가 #1105 로 반증된 "cron 로그 판별 불가"를 여전히 활성 🔴 지침으로 단언, 참조 행만 제거돼 dangling 상태 — `docs/runbooks/owed-verification.md:122`
- tests/unit/conftest.py 신설이 .claude/rules/testing.md 에 미동기화 — CLAUDE.md 아키텍처 동기화 체크리스트 9영역 매트릭스 위반, opt-in 이라 발견 함정 — `.claude/rules/testing.md:1`
- top-level src/*.py 4개 파일이 9영역 path-scoped rules 매트릭스 어디에도 매칭되지 않음 — 스모크 훅 사각지대와 정확히 동일한 집합(구조적 이중 사각지대) — `CLAUDE.md:1`
- 뮤테이션 주장 4건은 전부 정확 재현(양호) — 단 #1102 의 "14/14 green (test_alembic_env_logging_guard.py)" 은 2파일 합계를 1파일에 귀속시킨 오인용으로 재현 시 7 이 나옴 — `tests/unit/migrations/test_alembic_env_logging_guard.py:122`
- 계층 2 필터의 "어떤 로거에서 온 레코드든 반드시 통과한다" 주석이 같은 파일 모듈 docstring 의 uvicorn propagate=False 서술과 자기모순 — 핸들러 부착은 propagate=False 로거를 못 잡음 — `src/logging_config.py:40`

### tooling / owed 원장 집행면 (4)

- trend(daily 03:00 UTC)는 산문조차 없이 완전 무추적 — weekly 보다 엄격히 나쁘고 알림 경로다 — `src/scheduler.py:129`
- 근본 원인 — #1099 가 원장을 17줄 편집하고도 자기 owed 행을 0건 추가 — `docs/runbooks/owed-verification.md:11`
- 종결 선언 과대주장 — 5종 중 2종 증거로 'cron 검증 종결'·'실동작 확정' 표제 — `docs/runbooks/owed-verification.md:13`
- 원장 카운터는 fidelity 가드일 뿐 coverage 가드가 아니다 — 산문 누락은 설계상 영구히 미탐지 — `tests/unit/scripts/test_check_owed_verification.py:116`

### tooling / 검증 방법론 (음성 결과) (1)

- [반증됨] 배포 빈도가 daily/weekly job 을 구조적으로 실행 불가하게 만든다는 가설 — 실측 기각 — `src/scheduler.py:148`

### 미검증 양식 (1)

- owed 원장에 로테이션 관련 stale 모순 잔존 — a810e15 가 표 행만 갱신하고 산문 2곳을 방치 — `docs/runbooks/owed-verification.md:40`

### 원장 정합성 (1)

- 원장 :88 이 폐기된 DB 관측을 검증 기준으로 지정 + '아래' 포인터가 실제로는 위를 가리킴 — `docs/runbooks/owed-verification.md:88`

### 원장 정합성 / 자동 로드 컨텍스트 (1)

- 원장 §'검증 수단 정정' 이 '#1073·#1075 는 로그로 판별 불가' 를 상시 결론으로 단언 — 같은 파일 :13·:64 가 정면 반증 — `docs/runbooks/owed-verification.md:122`

### 회고 프로세스 / 범위 정의 (1)

- 회고 범위가 #1102~#1107 6건으로 선언됐으나 실제 세션 산출물은 #1108 포함 7건 — 누락분이 하필 안전등급 결정 기록 — `docs/runbooks/owed-verification.md:53`
