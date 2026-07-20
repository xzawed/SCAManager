# 5+1 회고 (범위 한정) — 2026-07-18 · 복구본

> 🔴 **이 파일은 소실됐다가 복구된 보고서다.** 원 실행(`wf_40082e43-d00`)은 2026-07-18 에
> 완료됐으나 **보고서가 아카이브되지 않았고**, 이후 두 회고가 각각 P1 으로 그 사실을 지목했다
> (`2026-07-19-retrospective.md` P1-3·P1-47). `docs/STATE.md` 한 줄이 유일한 흔적이었다.
>
> **복구 방법**: 워크플로 journal(`journal.jsonl` — 186 에이전트 · 372 레코드)에서 finding
> 본문을 추출하고, cross-verify 에이전트의 **프롬프트에 포함된 주장 제목**으로 verdict 를
> 페어링했다(163/163 매칭).
>
> 🔴 **복구본이 원본과 일치함을 교차 확인**: 복구 집계 **확정 147(P0 2·P1 55·P2 90)** 이
> `docs/STATE.md` 기록과 **완전히 일치**한다.
>
> ⚠️ **원본과 다른 점**: 실행 요약 서사·ROI 정량·§자성 섹션은 journal 에 없어 **복구 불가**다.
> 🔴 verdict 를 페어링하지 못한 항목은 **심각도를 추측해 채우지 않고** 별도 섹션에 둔다 —
> 조용히 P2 로 넣으면 복구본이 원본보다 커 보이는 거짓이 된다.
>
> 📄 **P2 는 표로 압축**했다(원문 715KB → 저장소 대용량 파일 한도 초과). P0·P1 은 원문 전량 보존.

## 실행 요약

| 항목 | 값 |
|------|-----|
| 워크플로 | `wf_40082e43-d00` (`.claude/workflows/retrospective.mjs`) |
| 실행일 | 2026-07-18 |
| 범위 | 세션2 remediation 15 PR (범위 한정 회고) |
| 에이전트 | **186** |
| 확정 | **147** (P0 2 · P1 55 · P2 90) |
| cross-verify 기각 | 16 |
| 미페어링(심각도 미확정) | 7 |
| 핵심 질문 | **"가드의 가드"** — 세션2 신설 가드 4종(#1080~#1083)에 '가드가 무력한데 green' 이 또 있는가 |

---

## 🔴 P0 (2건) — 원문 전량

### P0-1. [process] owed 원장이 write-only — 처방된 상시 배치가 같은 세션 첫 기회에 누락, 안전등급 2건 4세션째 ⏳

- **위치**: `docs/runbooks/owed-verification.md:15`
- **주장**: #1084 가 신설한 owed 원장은 회신을 유도하는 메커니즘이 아니라 기록 장치다. 테마 G 처방("trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치")이 같은 세션의 trailing sync PR 2건에서 즉시 누락됐고, 읽기측 트리거가 어디에도 없다. 이것은 P0 자체의 실패 모드(문서-only 시정이 행동을 못 바꿈)의 세 번째 반복이다.
- **근거**: 처방 = docs/_archive/reports/2026-07-18-retrospective.md:71-75 (테마 G). 실제 = `gh pr view 1087/1093 --json body | grep -c owed` → 둘 다 **0**. #1093 은 이 세션 최종 sync PR 이며 §"🔍 사용자 검증 필요" 에 "문서/배지만 — 코드 영향 0" 만 기재. 원장 파일 참조는 저장소 전체에서 단 1곳(`docs/runbooks/operational-smoke-checks.md:6`) — CLAUDE.md 작업 시작 전 체크리스트(CLAUDE.md:320 블록)에 미등재, 훅·스크립트·CI 배선 0 (`grep -rn owed-verification CLAUDE.md .claude/ scripts/` 무히트). 원장 15~16행 #1058 SMTP·#1062 IDOR = 정책 5 NEW-P0-N(매 사이클 명시 회신 의무) 라벨인데 2026-07-17 등재 이후 4 작업세션 전부 ⏳. #1058 은 "출시 이래 100% 실패" 였던 이메일 발송의 실복구 미확인 건. 메모리 `feedback-stale-blocker-policy.md` = "머지 대기 4사이클 누적 금지".
- **권고**: (a) `check_retro_cadence.py` 와 동형의 `check_owed_verification.py` 신설 — 원장의 ⏳ 행 수와 최고령 행의 경과 세션/PR 수를 실측해 안전등급 ⏳ 존재 시 loud 경고, CLAUDE.md:320 체크리스트에 카덴스 카운터 바로 옆 배치. (b) 원장 상단에 "등재일/경과 세션" 컬럼 추가(고령화 가시화). (c) 이번 세션 종료 회신에서 #1058/#1062 2건을 정책 5 NEW-P0-N 으로 단독 상정.
- **cross-verify**: CONFIRMED — 모든 근거를 독립 실측으로 재확인 — 전건 일치.

[인용 검증] owed-verification.md:15 = #1058 SMTP 행(⏳, 정책 5·13), :16 = #1062 IDOR 행(⏳, 정책 15). retrospective.md:71-75 = 테마 G, 처방 문구 축자 일치("trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치").

[행동 검증 — 핵심] gh pr view 1087/1093/1085 --json body | grep -ci owed → 0 / 0 / 0. 시점 반증 시도 실패: #1084(원장) 머지 05:38Z, #1087 06:15Z(+37분), #1093 09:32Z(+4시간) — 두 sync PR 모두 원장 존재 이후. 즉 "처방이 아직 없었다"는 방어 불가, 같은 세션 첫·둘째 기회 연속 누락이 실증됨.

[배선 검증] grep -rn owed CLAUDE.md .claude/ scripts/ → 실히트 0(check_edit_allowed.py 'allowed' 부분문자열 오탐뿐). 훅·스크립트·CI 배선 0 확인. 저장소 전체 owed-verification 참조 4곳이나 3곳(STATE.md:15·cycle-history.md:156·회고 리포트)은 사후 서술 기록이고, 전향적 포인터는 operational-smoke-checks.md:6 단 1곳 — CLAUDE.md:315-321 작업 시작 전 체크리스트에 미등재(check_retro_cadence.py 는 있으나 owed 항목 없음). 주장의 "단 1곳"은 실효 포인터 기준으로 정확.

[반론 검토 — 4건 모두 기각] (1) "⏳ 는 사용자 미회신이라 Claude 통제 밖" → 증거로 기각. 쟁점은 사용자 침묵이 아니라 처방된 채널에서 표가 제시된 적이 없다는 것(요청 자체가 부재) = Claude 측 실패. (2) "원장은 #1084 이전 대비 개선이니 결함 아님" → 직교. 포착(write)은 개선했으나 행동을 만드는 읽기/촉구(read) 측이 부재 = write-only 진단이 정확. (3) "세 번째 반복은 과장" → CLAUDE.md 본문이 카덴스 트리거를 "문서-only 정책이 두 번 연속 실패"로 자기 기록(2026-07-03 신설 → 2026-07-18 자기위반), owed 원장은 동형 세 번째. 카운트 타당. (4) "'어디에도 없다'는 절대화" → 2-hop 문서 체인(CLAUDE.md→smoke-checks→원장)은 존재하나 0/0 실측이 그 체인의 무효를 경험적으로 입증. 실질 유지.

[심각도 P0 유지] 본 저장소 자체 선례와의 정합 — 회고가 카덴스 트리거 자기위반(문서-only 시정·읽기측 트리거 부재·첫 측정창 자기위반)에 P0 을 부여했고 본 건은 구조적 동형. 여기만 강등하면 판정 비일관. 가중 요인: 원장 안전등급 2행이 정책 5 NEW-P0-N(매 사이클 명시 회신 의무)과 메모리 feedback-stale-blocker-policy.md("머지 대기 4사이클 누적 금지")를 현재 동시 위반 중이며, #1058 은 출시 이래 100% 실패였던 이메일 채널의 실복구 미확인 건.

[시정 방향 — 문서-only 재발 금지] 원장의 실효화는 기계 신호여야 함(#1080 check_retro_cadence.py 패턴): 미결 ⏳ 행 수를 실측해 세션 시작 체크리스트에서 loud 출력하는 스크립트 + CLAUDE.md:315-321 블록 등재. 처방을 다시 문서 문장으로만 두면 네 번째 반복이 예약됨.

### P0-2. [railway cron 관측 신뢰성 ↔ owed 원장] railway.toml cron 5종이 API 키를 single-quote 로 감싸 미확장 → 전건 401, 그런데 `-f` 부재로 curl exit 0 (무음 전면 실패)

- **위치**: `railway.toml:31`
- **주장**: `railway.toml:31,37,45,51,57` 의 cron 5종은 `-H 'X-API-Key: $INTERNAL_CRON_API_KEY'` 로 **작은따옴표** 를 쓴다. POSIX 셸에서 작은따옴표 안 `$VAR` 는 확장되지 않으므로 서버는 리터럴 문자열 `$INTERNAL_CRON_API_KEY` 를 수신 → `_require_cron_key` 의 `secure_str_compare` 불일치 → **401**. 여기에 `curl -s` 가 `-f` 없이 실행되어 401 에도 **exit 0** 을 반환, Railway 는 cron 을 '성공' 으로 기록한다. 즉 P2#27(`-f` 부재)은 단독 결함이 아니라 **선행 결함(따옴표)을 은폐하는 두 번째 층** 이다.
- **근거**: 실서버 재현(로컬 HTTP 서버 + `sh -c`): railway.toml 형태 → `SERVER_SAW_HEADER='$INTERNAL_CRON_API_KEY' -> 401`, `CURL_EXIT=0`. runbook 형태(큰따옴표) → `SERVER_SAW_HEADER='secret123' -> 200`. `-f` 추가 시 → `CURL_EXIT=22`. argv 분해 실측: `printf '[%s]\n'` → `[-H][X-API-Key: $INTERNAL_CRON_API_KEY]` (미확장 확정). 같은 줄의 `$PORT` 는 따옴표 밖이라 8731 로 정상 확장 = 의도는 확장이었음. `docs/runbooks/merge-retry.md:50` 은 동일 헤더를 **큰따옴표** 로 작성 = 저장소 내부 불일치. 인증 로직: `src/api/internal_cron.py:53-57` (401 raise).
- **권고**: 5줄 전부 `-H "X-API-Key: $INTERNAL_CRON_API_KEY"` (큰따옴표) + `curl -sf --max-time N` 로 동시 수정. 🔴 단, Railway 가 셸 경유 실행이 아니라 `$VAR` 를 자체 텍스트 치환하는 경우 본 항목은 무효화되므로, **fix 전 Railway 셸에서 해당 명령 1회 실측** 후 확정할 것(무효화되어도 `-f` 부재와 원장 맹점은 그대로 유효).
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인 + 실서버 재현으로 2층 결함 전부 입증. (1) railway.toml:31,37,45,51,57 5종 전부 작은따옴표 확인 — `sh -c` argv 분해 실측 `[X-API-Key: $INTERNAL_CRON_API_KEY]` 미확장 확정, 반면 같은 줄 `$PORT`는 8731 확장 = 의도는 확장이었음. (2) 로컬 HTTP 서버 종단 재현: railway.toml 형태 → 서버 수신 리터럴 → 401 / CURL_EXIT=0, runbook 형태(큰따옴표) → 'secret123' → 200, `-f` 추가 시 → CURL_EXIT=22. 즉 P2#27(-f 부재)은 선행 결함(따옴표)을 은폐하는 두 번째 층이라는 주장 그대로. (3) src/api/internal_cron.py 401 raise 실재(claim 53-57 vs 실측 54-58 — 주석 경계 off-by-one, 실질 정확). (4) docs/runbooks/merge-retry.md:50 큰따옴표 = 저장소 내부 불일치 확인. (5) 가드 전무: `grep -rn "railway.toml" tests/ scripts/ .github/` 0 hit, 어떤 cron 명령에도 `-f` 없음.

반증 시도 2건 모두 실패: (a) "Railway 가 config 단계에서 $VAR 치환할 수 있다" — 로컬 반증 불가(Railway MCP 미인증)이나, line 6 startCommand 가 bare `$PORT` 셸 확장에 의존해 운영에서 실동작 = 실행 경로가 셸이라는 직접 증거. 설령 그 가설이 맞아도 `-f` 부재 관측성 갭은 그대로이고 수정(큰따옴표)은 양 가설 하에서 무위험. (b) "키가 애초에 미설정이면 503 이라 무의미" — 마스킹일 뿐 반증 아님. 키 설정 순간 발화하는 잠복 결함이며, exit 0 층 때문에 어느 경우든 무음.

심각도 P0 유지: 스케줄 작업 5종(주간 리포트·트렌드 경보·머지 재시도 큐·orphan sweep·retention sweep) 전면 무음 실패 + Railway 는 '성공' 기록. retention sweep 미실행 = DB 무한 증가, orphan sweep 미실행 = 분석 소실 미표면화 = 운영 사고급. 완화 요인(머지 재시도는 check_suite webhook 대체 경로 존재, sweep 2종은 오늘 신설이라 누적 피해 아직 없음)이 있으나 '전면 무음' 성격상 강등 불가.

구조적 관측(회고 질문 직결): git blame = 24ff3b71(2026-04-26) 도입 패턴이 #1073(sweep-orphans)·#1075(retention-sweep)에 그대로 복사 — **본 회고 대상 15 PR 창 안에서 결함을 2회 재전파**. 자초 CodeQL 3회 재발과 동일한 '관용구 복사 드리프트' 근본 원인이며, 하필 turn-0 가드·CI·테스트가 전무한 유일 파일에 착지. 또한 docs/runbooks/owed-verification.md:24 가 사용자에게 orphan sweep 실행을 Railway 로그로 확인하라 요구 중인데, 본 결함 존치 시 그 owed 항목은 통과 불가 = 원장이 '기록만' 하고 회신을 유도 못 하는 구조의 실증 사례.

---

## P1 (55건) — 원문 전량

### P1-1. [tooling] 카덴스 카운터(#1080)의 실행 배선이 여전히 문서-only — P0의 실패 기질이 한 계층 위에서 재생산

- **위치**: `scripts/check_retro_cadence.py:8`
- **주장**: 회고 P0는 '문서-only 트리거가 인지 의존이라 자기위반'이었고, #1080은 이를 '측정 신호로 전환'한다고 선언했다(check_retro_cadence.py:8). 그러나 스크립트를 실행시키는 유일한 지점이 CLAUDE.md:320의 bash 블록 한 줄 — 즉 또 다른 문서다. 훅·CI·SessionStart 어디에도 배선이 없어, 트리거 발화 여부가 여전히 'Claude가 체크리스트를 실행하기로 선택하는가'에 달려 있다. 스크립트 자체는 정상 동작(라이브 실행 시 15건 정확 발화 확인)하므로 결함은 로직이 아니라 배선이다.
- **근거**: grep으로 check_retro_cadence 전 참조 열거 시 *.yml/settings.json 히트 0 — CLAUDE.md:320,326 / docs/STATE.md:11 / cycle-history.md:152 / 스크립트·테스트 자신뿐. .claude/settings.json은 PostToolUse(:26 posttool_pytest_smoke.py)를 실제 등록하고 있어 훅 배선 수단이 존재함에도 카덴스 카운터는 미등록. 결정적으로 tests/unit/scripts/test_check_retro_cadence.py:157의 배선 테스트가 `assert "check_retro_cadence.py" in claude_md` — '문서가 스크립트를 언급하는가'만 단언하며 실행 보장을 검증하지 않는다(테스트가 약한 단언을 제도화). 대조군: test_check_dead_code.py:120/127은 ci.yml을 yaml 파싱해 실제 배선을 단언 — 같은 세션 내 배선 검증 수준이 비대칭. 라이브 실측: `python scripts/check_retro_cadence.py` → '🔴 회고 카덴스 트리거 발화 — 머지 PR 15건 (임계 ≥15)'
- **권고**: .claude/settings.json에 SessionStart 훅으로 등록(PostToolUse와 동일 형식, advisory·exit 0이라 안전). 그 후 test_check_retro_cadence.py:157을 settings.json JSON 파싱 단언으로 교체 — test_check_dead_code.py:120의 yaml 배선 단언 패턴을 그대로 적용. 문서 언급 단언은 배선 단언의 대체물이 아님을 규칙화.
- **cross-verify**: SEVERITY_ADJUST — 결함 자체는 실재하며 모든 인용이 실측 일치. check_retro_cadence 전 참조 열거 결과 실행 배선은 CLAUDE.md:320 bash 블록 한 줄뿐 — *.yml/settings.json 히트 0. 프로젝트 .claude/settings.json(check_edit_allowed·doc_review_gate PreToolUse, posttool_pytest_smoke PostToolUse)과 전역 ~/.claude/settings.json(hooks 블록 자체 부재) 어디에도 미등록, settings.local.json 양 스코프 부재, SessionStart 등록 0건. 배선 수단 부재 반박도 성립 불가 — changelog.md:3117 이 SessionStart 훅 지원을 확인하며, context 주입 semantics 는 advisory(비차단) 신호에 적합해 정책 17 안정성이 회피 사유가 되지 못함. 스크립트 로직은 정상(라이브 '머지 PR 15 건 (임계 ≥15)'·exit 0) → 결함은 배선 맞음.

다만 P0 근거인 '실패 기질 재생산' 은 증거가 부분적으로 반박. #1080 이전 = 정책 회상 + 카덴스 수동 산출 + 판단 / 이후 = 체크리스트 한 줄 실행 → 명확한 판정 출력. 인지 부담이 '회상+계산+판단' 에서 '회상' 으로 실질 감소했으므로 동일 기질의 재생산이 아니라 잔여 리스크. 또한 첫 측정창에서 임계 정확히 15 에 발화해 회고가 실제 진입 — 예측된 재발과 반대 방향의 유일한 실측 데이터. 최악 결과도 회고 지연(프로세스 품질)이며 운영 사고·데이터 손실·보안 노출 경로 없음. 본 저장소 P0 는 측정된 드리프트를 동반한 실증 자기위반(~46 PR·3x 임계)에 유보돼 왔고 본 건은 예측 재발 → P1 이 정합.

심각도와 무관하게 존치돼야 할 핵심 = 테스트 비대칭. test_check_retro_cadence.py:157 은 `assert "check_retro_cadence.py" in claude_md` 로 '문서가 스크립트를 언급하는가' 만 단언하는 반면, 동일 세션 test_check_dead_code.py:120/127 은 ci.yml 을 yaml 파싱해 lint-changed-tests job 의 실제 호출과 base.sha..HEAD 인자 전달까지 단언. 같은 세션이 강한 기준을 이미 시연했음에도 카덴스 가드만 약한 기준으로 green 이 유지되는 구조 — '가드의 가드' 관점 유효 발견이며 권고 조치는 SessionStart 훅 등록 + :157 을 실행 배선 단언으로 승격.

### P1-2. [tooling] posttool 훅이 tests/unit 루트 1717건(스위트 31%)에 구조적으로 눈멀어 있음 — 명분으로 인용한 #1041 케이스가 실제로는 미커버

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:96`
- **주장**: #1082는 false-green을 봉인했으나 그 대가로 큰 사각을 만들었다. derive_test_target은 `tests/unit/{parts[0]}` 서브디렉토리만 반환하므로 tests/unit 루트의 test_*.py는 어떤 편집에서도 실행되지 않는다. collection 스모크 fallback은 `len(parts) < 2`(src 직속 파일)일 때만 진입한다. 결정적으로 훅 docstring이 fallback의 근거로 '#1041 클래스 조기 탐지'를 명시하는데, #1041의 실제 파손은 src/templates/settings.html 편집 → tests/unit/test_i18n_settings.py(루트) 연쇄였다. 이 경로는 target=tests/unit/templates로 매핑되어 fallback에 진입조차 못 하므로, 훅이 명분으로 삼은 바로 그 사고가 지금도 미탐지다.
- **근거**: posttool_pytest_smoke.py:51-62 derive_test_target(서브디렉토리 전용) / :96-98 fallback 주석 '대응 서브영역 없음(직속 파일 등) → collection 스모크(import/parametrize 파손 = #1041 클래스 조기 탐지)'. 실측: `ls tests/unit/*.py` = 33개 파일, `pytest tests/unit/test_*.py --co -q` = 1717 tests collected(전체 5480의 약 31%). 해당 루트 목록에 test_i18n_settings.py·test_config.py·test_main.py·test_migration_completeness.py 등 교차영역 가드가 집중. src 최상위 디렉토리 25개 중 tests/unit 대응이 없는 것은 static(비-Python)뿐이므로 fallback 경로는 사실상 거의 진입하지 않음.
- **권고**: 스코프 실행에 더해 항상 `pytest tests/unit --co -q`(초 단위)를 함께 수행하거나, 스코프 실행 대상에 루트 test_*.py를 무조건 포함. 최소한 docstring의 '#1041 클래스 커버' 주장을 실제 커버 범위에 맞게 정정 — 미커버를 커버로 적은 주석이 다음 세션의 오신뢰를 만든다.
- **cross-verify**: CONFIRMED — 모든 인용·실측이 정확히 재현됨. posttool_pytest_smoke.py:51-62 derive_test_target 은 `tests/unit/{parts[0]}` 서브디렉토리만 반환하고, :96-98 fallback 주석은 실제로 '#1041 클래스 조기 탐지' 를 명분으로 명시한다. 실측: tests/unit 루트 .py 33개, `pytest tests/unit/test_*.py --co` = 1717, 전체 tests/unit = 5480 → 31.3% (주장과 일치). src 최상위 중 tests/unit 대응이 없는 것은 static 뿐(비-Python) 도 확인.

결정적 검증: tests/unit/templates/ 가 실제 디렉토리로 존재하므로 line 93 `.is_dir()` 가드가 참이 되어 src/templates/* 편집은 서브디렉토리 분기로 가고 fallback 에 진입조차 못 한다. 추론이 아니라 훅의 derive_test_target 을 직접 실행해 확인했다.

#1041 실제 diff(bbb9e26)가 주장을 오히려 강화한다. 변경 파일은 src/templates/settings.html **및** src/i18n/translations/{en,ja,ko}.json 이고 파손은 tests/unit/test_i18n_settings.py(루트, _KEYS parametrize)였다. 두 경로 모두 존재하는 서브디렉토리(tests/unit/templates, tests/unit/i18n)로 매핑되어 **어느 편집으로도** fallback 미진입 → docstring 의 명분은 #1041 이 건드린 모든 파일에 대해 거짓이다. 더 나쁜 점: #1046 이 바로 그 루트 파일에 #1041 재발 방지용 test_keys_match_template 양방향 가드를 추가했는데, 그 목적-특화 가드가 훅의 사각에 있다.

심각도 하향(P2)을 적극 검토했으나 반증됨. '훅은 advisory·실 게이트는 push-time 6-step ②' 논리는 기계적 백스톱 부재로 무너진다: pre-push 훅 없음(.git/hooks = commit-msg·pre-commit 뿐), .pre-commit-config.yaml 에 pytest 항목 0건(시크릿·docs-sync·이중언어 주석만). 즉 6-step ② 는 문서-only 규율이고, 본 회고 P0 가 문서-only 정책의 실패(#1028 2회 자기위반 → #1080 기계화)를 이미 입증했다. 방어층 = 눈먼 훅 → pytest 없는 pre-commit → 문서-only 정책 → CI. 유일한 기계적 pre-push 탐지기가 눈먼 상태라 #1041 클래스는 여전히 push 후 CI 실패로 착지 = #1082 가 개선하려던 바로 그 결말.

P1 유지 근거 2가지: (1) 훅이 침묵이 아니라 `✅ 스모크 통과` 배너를 적극 출력 = 능동적 오정보. (2) 눈먼 31% 가 무작위가 아니라 위험과 역상관 — test_config·test_main·test_migration_completeness·test_rls_matrix_completeness·test_i18n_settings 등 서브디렉토리 스코프가 구조적으로 도달 불가한 교차영역 가드가 집중. 회고가 명시적으로 추적 중인 '가드의 가드 / #1094형(가드 무력한데 green)' 클래스에 정확히 해당.

최소 수정: 스코프 실행에 루트 테스트 동반(`[target, *glob('tests/unit/test_*.py')]`) 또는 collection 스모크를 서브영역 실행과 무조건 병행.

### P1-3. [tooling] dead-code 가드의 이름 충돌 false-negative — find_orphaned에서 통한 건 이름이 희귀해서였을 뿐(실측 재현)

- **위치**: `scripts/check_dead_code.py:123`
- **주장**: check_dead_code는 참조를 '이름 문자열'로만 센다(ast.Name.id / ast.Attribute.attr). 모듈·임포트 해석이 없어, 신규 공개 함수 이름이 흔할수록 무관한 속성 접근이 전부 '호출자 있음'으로 집계된다. #1060 find_orphaned가 잡혔던 것은 이름이 독특했기 때문이며, 가드의 정밀도는 구조적 보장이 아니라 이름 우연에 의존한다. repository/service 계층은 짧은 일반명을 실제로 쓰고 있어 이 사각은 가설이 아니라 현행 위험이다.
- **근거**: check_dead_code.py:63-79 count_ast_references(이름 단순 매칭) + :96-102 _total_references(src 전역 합산) + :123 `_total_references(n, src_root) == 0`. 실측(src/ 전역 AST 참조 수): get→561, count→40, delete→17, update→10, create→6 — 모두 무관한 dict.get/func.count/SQLAlchemy .delete()에서 유래. 동시에 `grep '^def |^async def ' src/repositories/*.py` 실측 결과 현행 함수명에 get(1), create(2), record(1), upsert(2)가 이미 존재 — 이 중 어느 것이든 오늘 신규 추가되면 가드는 무조건 '배선됨'으로 통과시킨다.
- **권고**: (a) 정의 파일 외부 참조만 카운트하고 (b) 후보명의 src 전역 매칭이 임계(예: 5) 초과 시 'ambiguous — 수동 확인 필요'로 별도 보고해 무음 통과를 없앨 것. 최소 조치로 docstring에 '희귀명 전제' 한계를 명시 — 지금은 한계 기술이 없어 다음 세션이 만능 가드로 오신뢰할 소지가 크다.
- **cross-verify**: CONFIRMED — 모든 인용·측정·결론이 독립 검증에서 그대로 재현됨. (1) 인용 정확: check_dead_code.py:63-79 count_ast_references 는 ast.Name.id / ast.Attribute.attr 를 이름 문자열로만 매칭(모듈·임포트 해석 없음), :96-102 _total_references 가 src/ 전역 합산, :123 이 `== 0` 단일 술어로 생사 판정 — 3개 모두 EXACT 확인. (2) 측정 재현: get→561, count→40, delete→17, update→10, create→6 (자릿수까지 일치). 전부 무관한 dict.get / func.count / SQLAlchemy .delete() 유래이며 repository 함수 호출이 아님. (3) 트리거가 현행 위험: grep -n 실측으로 merge_retry_repo.py:31 `def get`, issue_registration_repo.py:25 + merge_attempt_repo.py:20 `def create`, gate_decision_repo.py:57 + insight_narrative_cache_repo.py:58 `def upsert`, claude_api_cost_repo.py:24 `def record` 확인 — 짧은 일반명이 scoped 계층의 실제 명명 관용구. (4) 결정적 end-to-end 재현(격리 worktree, 사후 제거·repo clean): user_repo.py 에 호출자 0 함수 2개를 이름 희귀도만 달리해 추가 → 가드가 probe_zqxj_unique_name() 만 차단(EXIT=1)하고 동일하게 dead 인 get() 은 언급조차 안 함. 가드의 판별 기준은 배선 여부가 아니라 이름 희귀도임이 실증됨. (5) 보강 발견(원 finding 미제기): 가드 자체 테스트가 이 사각을 구조적으로 탐지 불가 — test_check_dead_code.py 의 참조-카운팅 단언 17건이 전부 희귀명 find_orphaned 를 사용하고, 충돌이 발생하는 지점인 _total_references 는 tests/ 전체에서 참조 0건. 즉 테스트가 동일한 이름-유일성 가정을 그대로 상속해 자가 교정되지 않음 → 세션이 물은 '가드의 가드'(#1094 형: 가드가 무력한데 green) 두 번째 사례. 심각도: P2 강등을 검토함(가드의 false-negative 이지 운영 결함이 아니고, #1083 이전 상태 대비 회귀는 아님). 그럼에도 P1 유지 — #1083 은 회고 P1#9/14/15 재발의 '구조적' 차단이 존재 이유인데, 실증된 실패 모드가 바로 그 dead-code 클래스가 흔한 이름일 때 무검출로 통과하는 것이고, 그 흔한 이름이 현행 명명 관용구이며, 실패 경로에 테스트 커버리지가 0 이기 때문(= P1 의 부분 조치). 원 주장은 과대평가 아님: find_orphaned 적발을 '틀렸다'가 아니라 '운이었다'로 정확히 규정했고 제시 수치가 전부 재현됨.

### P1-4. [docs] owed 원장(#1084)이 회신 유도 메커니즘이 아니라 기록 장치 — 회고 P0 와 동일한 '문서-only 시정' 패턴 재생산

- **위치**: `docs/runbooks/owed-verification.md:11`
- **주장**: 원장은 안전등급 행에 '다음 세션 진입 전 명시 회신 의무' 를 선언하지만, 그 의무를 세션 시작 시점에 표면화하는 배선이 전무하다. 6행 전부 ⏳ 인 현 상태는 원장의 실효를 반증한다. 이는 회고 자신이 P0 로 지목한 '문서-only 트리거가 첫 측정창에서 자기위반' 과 정확히 같은 구조이며, 같은 세션 안에서 반복됐다.
- **근거**: docs/runbooks/owed-verification.md:11 은 안전등급 표를 '🔴 다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N' 으로 규정(행 = #1058 SMTP, #1062 IDOR). 그러나 저장소 전체 grep 결과 'owed-verification' 참조는 docs/cycle-history.md:156 · docs/STATE.md:15 · docs/runbooks/operational-smoke-checks.md:6 · 자기 자신 뿐 — CLAUDE.md 와 .claude/policies/active.md 에는 0건. CLAUDE.md:315-323 '작업 시작 전 필수 체크리스트' 에 원장 점검 단계 없음. 대조적으로 같은 회고의 카덴스 트리거는 CLAUDE.md:320 `python scripts/check_retro_cadence.py` 로 체크리스트에 기계 배선됐다 — 즉 같은 세션이 한 결함에는 기계 신호를, 다른 결함에는 문서만 적용했다. 실측: 원장 6행 전부 ⏳(:15,:16,:22,:23,:24,:25).
- **권고**: 카덴스 카운터와 동형으로 승격: (a) CLAUDE.md 세션시작 체크리스트에 원장 미결(⏳) 행 카운트 1줄 추가, 또는 (b) `scripts/check_owed_verification.py`(stdlib·advisory) 로 ⏳ 행 수와 최고 등급을 배너 출력. 안전등급 ⏳ 가 1건이라도 있으면 loud — feedback-stale-blocker-policy 의 '4사이클 누적 금지' 를 기계 신호로 전환.
- **cross-verify**: CONFIRMED — CONFIRMED at P1. Core structural claim verified directly and independently. (1) docs/runbooks/owed-verification.md:11 declares the safety-grade table a '🔴 다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N'; rows :15 (#1058 SMTP) and :16 (#1062 IDOR) are both ⏳. (2) Wiring is genuinely absent, stronger than the finder showed: `grep -rln "owed-verification" scripts/ .claude/ .github/` returns NONE, and `.claude/settings.json` defines only PreToolUse/PostToolUse hooks — there is no SessionStart hook at all, so no surface exists on which a session-entry obligation could fire. The finder's `.claude/` grep hit is a substring accident (check_edit_allOWEDpy), so the real count is zero. (3) The same-session asymmetry is exact: CLAUDE.md:320 wires the cadence defect to a machine counter (`python scripts/check_retro_cadence.py`) inside the '작업 시작 전 필수 체크리스트', while the ledger gets no checklist step. (4) NEW EVIDENCE: the ledger's own rule at :5 claims it pairs with 'trailing sync PR body 의 §owed-verification 표', but CLAUDE.md:355 — the authoritative 6-step ⑤ trailing-sync clause — never mentions the ledger. The pairing is asserted unilaterally inside the ledger and absent from the process doc governing it, so even the one declared mechanism is unbacked.

ONE EVIDENCE LINE CORRECTED (does not sink the finding): `git log --follow` shows the ledger was created by e2098d3 (#1084) on 2026-07-18, this same session. No session boundary has elapsed since creation, so the finder's claim that '6행 전부 ⏳ 인 현 상태는 원장의 실효를 반증한다' is over-claimed — ⏳ is the expected initial state, i.e. UNTESTED, not DISPROVEN. The finding survives on the wiring gap alone and should be restated that way.

Severity P1 upheld rather than adjusted. Not P0: the ledger is net-positive over no ledger, and no active operational breakage stems from the gap itself. Not P2: it re-instantiates, in the same session, the exact mechanism class the retrospective judged P0-worthy, applied to safety-grade rows including #1058 (SMTP broken since launch, fix unproven by code); and declaring a 정책 5 NEW-P0-N obligation with zero enforcement is a direct 정책 4 violation (단언과 회귀 가드를 같은 PR 에 묶기). Repo base rate supports the prediction: the cadence trigger failed doc-only twice (2026-07-03 → 2026-07-18, ~46 PRs), and memory feedback-stale-blocker-policy.md records a prior 4-cycle '머지 대기' accumulation. Recommended remediation: add a ledger-check step to the CLAUDE.md session-start checklist, preferably as a machine counter parallel to check_retro_cadence.py that reads the ⏳ rows and warns loudly on safety-grade entries.

### P1-5. [decision] 세션2 가드 3종에 end-to-end 긍정 통제 부재 — 순수 헬퍼만 검증, main()/실 git 경로 0건

- **위치**: `tests/unit/scripts/test_check_dead_code.py:120`
- **주장**: #1081·#1083·#1082 의 테스트는 전부 문자열/AST 순수 함수 + 정적 YAML 배선 단언이고, 실제로 가드를 '돌려서 위반을 잡는지' 확인하는 통제가 하나도 없다. 그래서 위 P1(무음 green)을 잡아낼 테스트가 구조적으로 존재할 수 없다. 아이러니하게도 #1094 에서 뒤늦게 작성된 test_empty_except_guard.py 만 '탐지기 자체 검증(긍정/부정 통제)' 섹션을 갖고 있다 — 규율이 가드 출하 **후에** 학습됐고 기존 3종에 소급 적용되지 않았다.
- **근거**: tests/unit/scripts/test_check_dead_code.py = 14 test, 전부 parse_added_public_defs/parse_unwired_ok_names/count_ast_references 순수 함수 + test_ci_wires_dead_code_guard·test_ci_dead_code_guard_passes_pr_base_sha(YAML 문자열 단언) — `main(` 호출 0건. tests/unit/scripts/test_check_noqa_sideeffect.py = 14 test, 동일하게 `main(` 0건. tests/unit/hooks/test_posttool_pytest_smoke.py = 6 test, 전부 is_src_file/derive_test_target — main()·배너·타임아웃 분기 0건. 대조: tests/unit/scripts/test_empty_except_guard.py:56 '--- 탐지기 자체 검증 (긍정/부정 통제) / detector self-checks ---' + test_detects_bare_pass_handler.
- **권고**: 각 가드에 tmp_path 임시 git repo fixture 기반 end-to-end 테스트 2건 추가: (1) 실제 위반 커밋 → exit 1 + 위반 라인 출력(긍정 통제), (2) 깨끗한 커밋 → exit 0(부정 통제). 추가로 'base 해석 불가 → non-zero 또는 loud skip' 단언을 넣으면 위 P1 이 회귀 봉인된다. 세션2 가드 3종 일괄 소급 적용.
- **cross-verify**: CONFIRMED — 인용 검증: test_check_dead_code.py:120 = `test_ci_wires_dead_code_guard` 실재 확인. `grep -c "main("` 실측 = 3 파일 전부 **0건** (dead_code / noqa_sideeffect / posttool_smoke). `pytest --collect-only` 실측 36 tests = 16 + 14 + 6 (주장의 "14 test"는 dead_code 실측 16 — 사소한 오차, 결론 무관).

핵심 주장(순수 헬퍼만 검증·main()/실 git 경로 0건)은 CONFIRMED. 다만 **회의적 검증 결과 주장보다 더 나쁘다** — 나는 이론적 커버리지 갭이 아니라 **재현 가능한 live 무음 blindness**를 실측했다:

```
$ python scripts/check_dead_code.py "deadbeef...(무효 sha)" HEAD
✅ 신규 dead-code 후보 없음 / no new dead-code candidates   exit=0
$ python scripts/check_dead_code.py "" HEAD          # 비-PR 이벤트 시 빈 표현식
✅ 신규 dead-code 후보 없음                                  exit=0
$ python scripts/check_dead_code.py HEAD~15 HEAD     # 정상 base
✅ 신규 dead-code 후보 없음                                  exit=0
```
noqa 가드도 동일. 근본 = `_git()` 이 `check=False` + `out.stdout or ""` 로 git 실패를 삼킴(dead_code.py:82-86, noqa_sideeffect.py:76-81) → 변경 파일 0 → candidates 공집합 → ✅ exit 0. 🔴 **무효 base 의 출력이 정상 clean 출력과 바이트 단위로 동일** — CI 로그만 보고 "검사했고 깨끗함" 과 "아무것도 검사 안 함" 을 구별할 방법이 없다. 이것이 정확히 #1094 클래스(가드가 눈멀었는데 green)이며, 회고 질문 "가드의 가드"의 답이다.

현재 미발화 사유는 가드 **코드 밖 CI 설정** 뿐: `lint-changed-tests` 의 `if: github.event_name == 'pull_request'` + `actions/checkout@v7 with fetch-depth: 0`. 그런데 `grep -rn "fetch-depth" tests/` = **0건** — 이 단일 결합을 지키는 테스트가 없다. 누가 checkout 을 기본 depth(=1)로 되돌리면 두 가드가 동시에 영구 무음 실패하고 **기존 36 테스트는 전부 green 유지**. 즉 P1 봉인이 조용히 재개방된다.

#1082 는 특히 아이러니: 훅 전체 리스크 로직(`_run` 타임아웃 처리, `rc is None` 3-상태 배너, `-x --timeout=15` 스코프 결정)이 전부 `main()`/`_run()` 에 있는데(posttool_pytest_smoke.py:65-105) 테스트 6건은 `is_src_file`/`derive_test_target` 문자열 매핑만 본다. **false-green 을 고치려 만든 교체품의 false-green 표면이 미검증**.

주장 중 과장 1건 정정(그러나 결론 불변): "가드를 돌려서 위반을 잡는지 확인하는 통제가 하나도 없다" 는 부정확 — test_check_noqa_sideeffect.py:94 `test_find_violations_reports_added_noqa_import` 는 위반 diff → 위반 보고를 단언하는 **탐지기 레벨 긍정 통제**다. 실제 부재는 "긍정 통제 전무" 가 아니라 **합성(composed)·end-to-end 통제 부재** — 특히 check_dead_code 는 whitelist 차감(`candidates -= whitelisted`)·0-참조→dead 분류·exit code 결정이 전부 `main()` 인라인이라 헬퍼 테스트로 도달 불가능한 구간이다. 대조 사례 프레이밍도 일부 오해: test_empty_except_guard.py 역시 `main(` 0건(애초 CLI main 이 없는 pytest-native 가드) — 대조점은 "e2e 검증" 이 아니라 **'탐지기 자체 검증' 섹션을 명시적으로 라벨링한 규율**이며, 그 규율이 가드 3종 출하 후에 학습되어 소급 적용되지 않았다는 구조적 지적은 유효.

P1 유지(강등 거부): (a) 이 가드들은 P1 테마 B/C 의 remediation 자체이므로 무음 실패 = P1 재개방, (b) 실측 재현됨(추측 아님), (c) 성공/맹목 출력 동일이라 운영 중 탐지 불가, (d) 유일한 방어(fetch-depth: 0)에 회귀 가드 0건 = 정책 4(단언과 회귀 가드를 같은 PR 에) 위반 패턴. 프로덕션 코드가 아닌 dev-tooling 이라 P0 는 아님. 권고 fix: ① `_git()` 이 returncode≠0 시 loud-fail(빈 문자열 무음 반환 금지) ② `main()` 긍정/부정 통제 각 1건(위반 포함 diff → exit 1, clean diff → exit 0) ③ ci.yml `fetch-depth: 0` 정적 단언을 기존 CI 배선 메타 가드 옆에 추가 ④ posttool `_run` 타임아웃/배너 3-상태 테스트.

### P1-6. [code] 카덴스 카운터(#1080)의 호출 자체가 여전히 문서-only — P0 시정이 한 계층 못 미침

- **위치**: `.claude/settings.json:3`
- **주장**: 회고 P0 '문서-only 트리거가 행동을 못 바꿈'에 대한 시정으로 신설된 check_retro_cadence.py 가, 정작 **자신의 실행 트리거는 CLAUDE.md 문서 한 줄**이다. .claude/settings.json 은 PreToolUse(3행)·PostToolUse(20행) 두 훅만 등록하며 SessionStart 훅이 없어 카운터를 자동 실행하는 기계 경로가 존재하지 않는다. 더 결정적으로, 회귀 가드 test_checklist_wires_the_counter 는 'CLAUDE.md 본문에 check_retro_cadence.py 문자열이 있는가'만 단언해(157행) **문서-only 배선을 '배선됨'으로 제도화**한다. 즉 '계산은 기계화됐으나 계산을 시작시키는 것은 여전히 인지 의존' — 두 번 실패한 것과 동일한 강제 채널이다. (완화 요인은 인정: 이전엔 Claude 가 임계 도달 여부를 기억으로 추론해야 했고 지금은 명령 1회 실행이면 되므로 인지 부담은 실제로 감소했다. 그러나 실행 누락 시 신호는 0 이며, 그 누락이 정확히 과거 2회의 실패 양식이다.)
- **근거**: scripts/check_retro_cadence.py 전체(자동 호출자 없음) · .claude/settings.json:3(PreToolUse)·:20(PostToolUse) — SessionStart 부재 · CLAUDE.md:320 체크리스트 bash 블록 · tests/unit/scripts/test_check_retro_cadence.py:150-159 `assert "check_retro_cadence.py" in claude_md`
- **권고**: SessionStart 훅(.claude/settings.json)으로 카운터를 배선하거나, 최소한 breached 시 loud 배너가 PreToolUse 첫 편집에서 1회 출력되도록 승격. 회귀 가드는 '문서에 문자열 존재'가 아니라 '설정 파일에 실행 엔트리 존재'를 단언하도록 교체.
- **cross-verify**: SEVERITY_ADJUST — 모든 인용 실측 확인 — 결함 자체는 실재하나 P0 는 과대평가, P1 로 조정.

[검증된 사실]
- `.claude/settings.json` = PreToolUse(:3)·PostToolUse(:20) 2 훅만. SessionStart 부재 확인.
- 자동 호출자 전무: repo 전체 grep + dot-dir 명시 확인(`.github/`·`.claude/`·`Makefile`) + 전역 `~/.claude/settings.json`(hooks 키 자체 없음) 모두 0건. 참조는 CLAUDE.md:320·326, STATE.md:11, cycle-history.md:152, 테스트뿐.
- `tests/unit/scripts/test_check_retro_cadence.py:157` = `assert "check_retro_cadence.py" in claude_md` 단독. 파일 내 다른 테스트 어디에도 기계 호출 경로 단언 없음(전 함수 목록 실측).

[CONFIRMED 인 부분 — 가장 강한 하위 주장]
회귀 가드가 '문서에 문자열이 있는가'를 '배선됨'으로 인증한다. 이는 #1094 와 동일 계열(가드가 약한 속성만 검증)이며 실제 조치 가치가 있다. SessionStart 훅은 기술적으로 가능하므로 FALSE_POSITIVE 아님.

[P0 → P1 강등 근거 3]
1. **두 번 실패한 그 채널이 아니다.** 과거 실패 = 정책 8 진화 각주에 묻힌 산문적 *판단*(규칙 상기 + PR 수 기억 추정 + 임계 적용). #1080 은 이 3 단계를 전부 기계화했고, 남은 인지 의존은 '호출' 한 링크뿐이며 그 위치가 turn-0 체크리스트(gh run list·code-scanning·메모리 grep·git status·브랜치 생성과 동일 블록)다. 산출물 계층이 바뀌었으므로 "동일한 강제 채널"은 두 실패 표면의 혼동.
2. **SessionStart 도 루프를 닫지 못한다.** 스크립트는 설계상 advisory(:129 무조건 exit 0). 자동 호출은 인지 링크 하나를 제거할 뿐 최종 링크(배너 읽고 회고 진입 판정)는 그대로 → 제안된 수정은 개선이지 P0 봉인이 아님.
3. **라이브 실행 1회 기록됨.** STATE.md:11 · cycle-history.md:152 "라이브 48→5 리셋 실측" — "실행 누락 시 신호 0" 이 현재 관측 상태라는 전제와 배치.

[추가 완화] 탐지 로직 자체엔 실효 긍정 통제 존재(`test_retro_date_rejects_non_retrospective_reports` 가 grok-review 오인 리셋 차단 실증·경계 포함 임계·inline #NN 미카운트). 눈이 먼 곳은 호출 계층에 국한되며 측정 계층은 아님 → #1094 급 '가드 전체 무력' 사례 아님. 운영 위험 없고 본 측정창 내 재발 없음.

[권고 조치] SessionStart 훅 등록 + 가드를 `settings.json` 의 실제 호출 경로 단언으로 승격(문서 문자열 단언은 보조로 강등).

### P1-7. [code] dead-code 가드가 리포지토리 공용 동사 이름에 무력화 — 이름 충돌 시 silent false-negative

- **위치**: `scripts/check_dead_code.py:96`
- **주장**: check_dead_code.py 의 `_total_references` 는 함수명을 **src/ 전체에서 bare name 으로** 집계한다(96-102행: `ast.Name(id==name)` 또는 `ast.Attribute(attr==name)`). 그런데 이 코드베이스의 repository 계층은 CRUD 동사를 의도적으로 균일하게 쓴다 — 실측 결과 scoped 공개 함수 100개 중 8개가 이미 2개 이상 파일에 중복 정의돼 있다(create·find_by_id·find_by_full_name·list_by_repo·list_pending·save_new·upsert·user_cost_summary). 따라서 신규 repo 모듈에 `def find_by_id(...)` 를 추가하면, 기존 `analysis_repo.find_by_id()` 등 타 모듈 호출 4건이 참조로 집계되어 **호출자 0 dead code 인데도 '✅ all wired' 통과**한다. #1060 find_orphaned 가 잡힌 것은 이름이 우연히 고유했기 때문이며, 코드베이스의 지배적 명명 관행에서는 가드가 열리는 구조다.
- **근거**: scripts/check_dead_code.py:29 `_SCOPED_DIRS` · :96-102 `_total_references`(파일 무관 이름 집계) · :74-79 `count_ast_references` · AST 실측: scoped 공개 100명 중 중복 8명, `find_by_id` 는 3파일 정의 + 타파일 참조 4건 · 긍정 통제 replay(worktree @050bab6)에서 find_orphaned 는 정상 검출 — 고유명이라 통과한 사례
- **권고**: 참조 집계를 이름 단독이 아니라 (모듈 import 경로 + 이름) 결속으로 좁히거나, 최소한 '후보 이름이 src 내 2곳 이상에 정의됨' 시 판정 불가로 보고 loud-warn 하여 조용한 통과를 막을 것.
- **cross-verify**: CONFIRMED — CONFIRMED by controlled end-to-end experiment; citations exact.

CITATIONS VERIFIED: check_dead_code.py:29 `_SCOPED_DIRS` ✔ · :63-79 `count_ast_references` (walk loop 74-79) ✔ · :96-102 `_total_references` ✔. Line 123 confirms the fatal call site: `_total_references(n, src_root)` with `src_root = Path("src")` — reference counting is global and file-agnostic, exactly as claimed.

DUPLICATE CENSUS REPRODUCED EXACTLY: AST scan of src/repositories + src/services yields 100 public def names, 8 defined in >1 file — name-for-name identical to the finder's list (create, find_by_id, find_by_full_name, list_by_repo, list_pending, save_new, upsert, user_cost_summary).

BASELINE POISONING MEASURED: every colliding verb already returns nonzero from `_total_references` in current src/ — find_by_full_name=20, create=6, find_by_id=4, save_new=3, upsert=3, user_cost_summary=2, list_pending=1, list_by_repo=1. Any newly added def bearing these names is pre-satisfied before it has a single caller.

DECISIVE A/B REPLAY (isolated git worktree, sole variable = the function name, zero callers in both arms):
- ARM A `def find_by_id(...)` in a new repo module, zero callers → "✅ 신규 공개 함수 1개 모두 src 내 호출자 有 / all wired", exit 0. FALSE NEGATIVE.
- ARM B unique name, zero callers → correctly blocked, exit 1.
This isolates name collision as the causal variable. Main tree left clean; worktree removed.

ADDITIONAL DEFECT THE FINDER MISSED (strengthens the case): `grep -rn "_total_references" tests/` returns ZERO hits. tests/unit/scripts/test_check_dead_code.py exercises `count_ast_references` only against single-source strings and never tests `_total_references` or `main()`. The positive control exists for the parsing primitives but NOT for the cross-file aggregation seam where the defect lives — which is exactly why the guard shipped green. This is the #1094 pattern ("guard impotent but green") recurring inside the remediation for it.

SEVERITY SUSTAINED AT P1 (not adjusted). Considered and rejected downgrade to P2 on the argument "defense-in-depth failing open toward the pre-#1083 status quo, no production impact." Rejected because (a) the blind spot is aligned with the DOMINANT naming convention of the exact layer the guard scopes — a new repository module, the highest-risk scenario for unwired dead code, will almost certainly define create/find_by_id/save_new, all already poisoned, so this is the mainline case not a tail case; (b) the failure is affirmatively misleading — printing "all wired" having verified nothing suppresses the human scrutiny that was the only thing that eventually caught #1060. Not P0: no production, data, or security exposure; the guard is a CI layer, not runtime.

NOTE ON #1060 FRAMING: finder is correct — find_orphaned now reads 1 ref only because #1073 wired it. It was caught at retro replay because the name was incidentally unique, not because the guard's logic is sound.

FIX DIRECTION: exclude the defining file from the reference count, and when a candidate name is defined in >1 file, either require a caller in a file that imports the defining module or fail closed demanding an explicit `# unwired-ok:` marker. Pair with a regression test at the `_total_references`/`main()` level (policy 4 — assertion + guard in the same PR), since that seam currently has no coverage at all.

### P1-8. [process] 신규 noqa 가드가 저장소 자신의 지배적 관용구를 탐지 못 함 — #1094형 '가드가 무력한데 green' 재현

- **위치**: `scripts/check_noqa_sideeffect.py:30`
- **주장**: #1081 `check_noqa_sideeffect.py` 의 탐지기가 `# noqa: F401  pylint: disable=unused-import` 형태를 **False(위반 아님)** 로 판정한다. 이 관용구는 저장소에서 가장 많이 쓰이는 형태이며, flake8 은 이를 F401 억제로 정상 해석하므로 CodeQL py/unused-import 가 그대로 재발한다 — 가드가 존재하는 채로 원래 재발 경로가 열려 있다.
- **근거**: `scripts/check_noqa_sideeffect.py:30` `_NOQA = re.compile(r"#\s*noqa(?::\s*([A-Za-z0-9, ]+))?")` — 코드 문자 클래스에 **공백이 포함**되어 `F401  pylint` 까지 한 덩어리로 캡처. `:54` `"F401" in codes.upper().replace(" ","").split(",")` → `["F401PYLINT"]` → False. flake8 은 codes 를 `[,\s]+` 로 분리하므로 F401 을 실제로 억제 → pre-merge 통과 + CodeQL 발화.
실측 재현(end-to-end): `git diff 90d0bd3~1 90d0bd3 -- tests/` 가 추가한 `+import src.models.claude_api_call  # noqa: F401  pylint: disable=unused-import` 를 `python scripts/check_noqa_sideeffect.py 90d0bd3~1 90d0bd3` 이 **미보고**(같은 실행에서 다른 6줄은 정상 보고, exit=1).
직접 호출 실측: `line_hides_f401('import x  # noqa: F401  pylint: disable=unused-import')` → **False**.
동일 관용구 실사용: `src/analyzer/io/static.py:8~27` 약 20줄이 `# noqa: F401 … # pylint: disable=unused-import` 형태.
단위 테스트 사각: `tests/unit/scripts/test_check_noqa_sideeffect.py:32~58` 은 `F401` / bare / `E402,F401` / `E501` 만 커버 — 공백 구분 다중 지시어 케이스 없음.
- **권고**: `_NOQA` 코드 그룹에서 공백을 제거하고 분리자를 flake8 과 동형(`[,\s]+`)으로 맞춘다: codes 캡처를 `([A-Za-z0-9,\s]+?)(?=#|$)` 로 좁히거나 `re.split(r'[,\s]+', codes)` 로 판정. 회귀 가드로 `# noqa: F401  pylint: disable=unused-import` 및 `# noqa: F401 x  # pylint: …` 2 케이스를 탐지기 긍정 통제에 추가(#1094 `test_empty_except_guard.py:60` 패턴 준용).
- **cross-verify**: CONFIRMED — Reproduced end-to-end. Citations exact: check_noqa_sideeffect.py:30 `_NOQA = re.compile(r"#\s*noqa(?::\s*([A-Za-z0-9, ]+))?", re.IGNORECASE)` (space IS in the char class) and :54 `"F401" in codes.upper().replace(" ","").split(",")`. Direct call: line_hides_f401('import x  # noqa: F401  pylint: disable=unused-import') -> False, capture group 'F401  pylint' -> ["F401PYLINT"]. End-to-end: `python scripts/check_noqa_sideeffect.py 90d0bd3~1 90d0bd3` reports 6 violations (exit=1) while silently passing 3 added lines in the SAME diff — tests/unit/migrations/test_orm_alembic_parity.py (`pylint:` suffix) + tests/unit/services/test_dashboard_service.py and test_dashboard_service_user_id_filter.py (`# noqa: F401  C1 Phase 4 —` prose suffix). 3 of 9 added F401 lines evade = 33% miss on real merged history. flake8 premise verified empirically: probe file under `flake8 --isolated --select=F401` reports only the unannotated import; both evading forms are suppressed — so lint stays green while CodeQL py/unused-import can re-fire. Test sac confirmed at tests/unit/scripts/test_check_noqa_sideeffect.py:32~60 (covers F401 / em-dash / bare / E402,F401 / E501 / non-import / no-noqa; no unhashed space-separated trailing prose case).

CORRECTION to the claim's supporting evidence (does not refute the finding): the assertion that this is "the repo's most-used idiom" is FALSE. The actual src/analyzer/io/static.py:8~27 form is `# noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import`; the em-dash terminates the char class so line_hides_f401 returns True on those real lines (verified against the live file). Additionally src/** is outside the guard's scan scope entirely (_changed_test_files restricts to tests/), so src prevalence was never load-bearing. The true trigger is narrower in origin but BROADER in class than claimed: any alphanumeric trailing prose after F401 with no `#` delimiter defeats detection ('F401  C1 Phase 4 note', 'F401 registers model' -> all False), while 'F401,E402 trailing note' -> True.

Severity held at P1, not raised: the defect is real, reproduced on actual merged history, and is precisely the "#1094-form — guard present, CI green, detector inert" class this retro set out to find (answers the 'guard of the guards' question affirmatively for #1081). It is not P0 because the failure mode is a reactive CodeQL lint-alert fix PR with no production, data, or security impact. Suggested fix: exclude space from the codes character class and split on flake8's own `[,\s]+` semantics, plus add a positive-control test for the space-separated trailing-prose form.

### P1-9. [process] 카덴스 카운터가 여전히 '기억해서 실행' — 문서-only 실패의 3번째 반복 형태 + 회고 조치 2 미이행

- **위치**: `CLAUDE.md:320`
- **주장**: #1080 은 카덴스 판정을 측정 가능하게 만들었으나, **자동 발화 경로가 없다**. 어떤 훅·CI·pre-commit 에도 배선되지 않고 CLAUDE.md 산문 체크리스트 1줄에만 존재한다. 즉 '규칙을 기억하기'가 '스크립트 실행을 기억하기'로 바뀌었을 뿐, 트리거가 인지 의존이라는 P0 근본 구조는 그대로다. 회고가 함께 지시한 조치 2(STATE.md 추적셀)는 미이행이라 백업 신호도 없다.
- **근거**: 배선 실측: `grep -rn "check_retro_cadence" .github/ .claude/settings.json` → **0 hit**. `.pre-commit-config.yaml` 등록 6종(`check_docs_sync`·`check_toc_anchors`·`check_memory_refs`·`check_env_vars_sync`·`check_config_5way_sync`·`check_bilingual_comments`)에 미포함.
유일 배선 = `CLAUDE.md:320` 체크리스트 명령줄 + `:326` 설명 블록.
`.claude/settings.json` 은 `PreToolUse`(:3) / `PostToolUse`(:20) 만 정의 — `SessionStart` 훅 부재(`grep -n "SessionStart" .claude/settings.json` → 0 hit). Claude Code 가 SessionStart 훅을 지원하므로 **가용한 자동화가 미사용**.
회고 조치 2 미이행: `docs/_archive/reports/2026-07-18-retrospective.md:40` 이 "STATE.md 추적셀 — 직전 정식 회고: YYYY-MM-DD·기준 PR# / 이후 세션 N·머지 PR N (트리거 3/15) — 매 docs-sync PR 에서 강제 갱신 (정책 4 단언+가드 페어)" 를 지시했으나 `grep -n "직전 정식 회고" docs/STATE.md` → 추적셀 없음(:11 서사 불릿 1건뿐).
- **권고**: `.claude/settings.json` 에 `SessionStart` 훅으로 `python scripts/check_retro_cadence.py` 배선(advisory·exit 0 이므로 세션 차단 위험 0 — 정책 17 안정성 충족). 그래야 '기억' 없이 배너가 뜬다. 병행해 회고 조치 2(STATE.md 추적셀)를 이행하거나, 이행하지 않기로 결정했다면 회고 리포트에 미채택 사유를 명시(정책 3 자율 판단 사후 보고).
- **cross-verify**: CONFIRMED — 모든 인용 재확인 통과. (1) `grep -rn "check_retro_cadence" .github/ .claude/settings.json` → 0 hit. (2) `.claude/settings.json`(692B, 전문 read)은 PreToolUse:3 / PostToolUse:20 만 정의 — `SessionStart` 는 `.claude/` `.github/` 어디에도 부재. (3) `.pre-commit-config.yaml` 등록 프로젝트 스크립트 = 지목된 6종 정확히 일치, 카덴스 카운터 미포함. (4) 유일 배선 = CLAUDE.md:320 + :326. (5) `grep -n "직전 정식 회고" docs/STATE.md` → :11 서사 불릿 1건뿐, 지시된 추적셀 부재. 회고 리포트 조치 2는 조치 3(`(선택) pre-commit/CI 카운터`)과 달리 선택 표기 없음 = 미이행 확정.

추가 확보한 가중 증거 2건: (a) #1080 commit body 자체가 범주 오류를 자백 — "CLAUDE.md 작업 시작 전 필수 체크리스트에 배선 — 문서-only 재발 방지(스크립트만 있고 미배선이면 다시 인지 의존)". 저자가 위험을 정확히 식별한 뒤 'CLAUDE.md 체크리스트 배치'를 그 해법으로 간주했으나, 실패한 #1028 트리거도 동일하게 auto-load 되는 CLAUDE.md 산문이었다 → 실증 실패율 2/2 인 전달 매체를 재사용. (b) 동일 세션 형제 가드는 CI 배선됨 — `check_noqa_sideeffect.py`(ci.yml:102), `check_dead_code.py`(ci.yml:109). P0 파생 가드만 산문에 남음.

반대 가설 검증 결과: 카운터는 diff 없는 세션 스코프라 CI/pre-commit 적합도가 낮고, 정책 17 이 blocking 훅을 의도적으로 배제 — 이 방어는 실재하나 갭을 덮지 못한다. `SessionStart` 는 비차단이며 스크립트 docstring 의 자기 선언("run at session start — pre-work checklist")과 정확히 일치하는 가용 자동화 지점인데 미사용이다.

finder 과대 지점 2건(판정 유지, 기록만): "3번째 반복"은 미측정 재발 예측(#1080 은 오늘 착지, 측정창 미경과)이고, pre-καdence pre-commit/CI 부재 비판은 회고가 스스로 `(선택)` 처리한 항목을 일부 겨냥한다. 실제 하중은 *SessionStart 미사용 + 조치 2 누락* 이지 pre-commit 부재가 아니다. P2 강등하지 않는 이유: 본 건의 대상은 P0 시정의 적절성이며, 다음 실패를 기다려 판정하는 것이 바로 이 체인이 끊으려는 안티패턴이다. 또한 `STATE.md:11` 이 "문서-only→측정 신호 승격"을 완료로 서술하는 동안 조치 2 가 무음 누락된 것은 예측이 아닌 현재형 관측 갭(= cross-verify 가 지목한 'remediation 완결성: 완료 선언됐으나 부분 조치' 클래스에 정확히 해당). 두 시정 레그(자동 발화 / 영속 카운터 셀)가 모두 동일한 실패 매체에 얹혀 독립 신호 경로가 0.

### P1-10. [process] 반복의 구조적 원인 — '자기참조 allowlist/count-lock' 이 이 창에서만 3건, 누락 방향은 원리적으로 탐지 불가

- **위치**: `tests/unit/ui/test_dashboard_owner_filter_parity.py:23`
- **주장**: 자초 CodeQL 3회 재발과 dead-code 13 PR 생존이 반복되는 공통 구조는 '관용구 복사 드리프트' 보다 한 겹 아래에 있다: **가드가 검사 대상 목록을 스스로 들고 있고, 그 목록에 항목을 추가하는 일이 수동**이라는 것. 이런 가드는 rename/제거(변경)는 잡지만 **누락(추가 안 함)** 은 원리적으로 못 잡으며, 전 스위트 green 이 안전 신호로 오독된다. 이 창에서 신설·기존 가드 3건이 같은 형태다.
- **근거**: ① `tests/unit/test_migration_completeness.py:150` `assert len(_REGISTERED_MODELS) == 12` — 튜플 자기 대조. 실제 13종과 드리프트 발생 중(위 finding 참조).
② `tests/unit/ui/test_dashboard_owner_filter_parity.py:25~30` `_OWNER_SCOPED = {10개 이름}` 하드코딩. `:23` 주석이 한계를 자인: "신규 owner-스코프 집계 도입 시 이 집합에 추가(완전성 가드가 rename/제거를 잡는다)" — 즉 **추가 방향 무방비**. #1074(형제 7개 중 feedback_status 하나만 owner 필터 누락)와 동일 클래스의 신규 집계가 들어오면 재발.
③ `alembic/env.py:56~60` `_REGISTERED_MODELS` — env.py 는 갱신됐으나 테스트 사본은 안 됐다는 사실 자체가, 두 수동 목록 사이에 상호 대조가 없음을 증명.
대조군(올바른 형태): `scripts/check_dead_code.py` 는 목록이 아니라 diff+AST 로 대상을 **도출**한다 → 실측 재현에서 #1060 `find_orphaned` 를 정확히 탐지(격리 worktree 에서 `050bab6~1..050bab6` 재생 → exit=1, `find_orphaned()` 보고).
- **권고**: 가드 설계 규약을 `.claude/rules/testing.md` 에 1줄 추가: "검사 대상 목록을 하드코딩하는 가드는 반드시 **외부 기준과의 집합 동등성**을 함께 단언한다(파일 시스템 열거·타 목록·AST 도출 중 택1). 자기 길이 단언(`len(X) == N`)은 가드로 인정하지 않는다." 우선 적용 대상 = 위 ①②.
- **cross-verify**: SEVERITY_ADJUST — CONFIRMED as a real structural defect, severity raised P2→P1.

CITATIONS (all exact): (1) test_dashboard_owner_filter_parity.py:23 = verbatim self-admitting comment "신규 owner-스코프 집계 도입 시 이 집합에 추가"; _OWNER_SCOPED at :25 with 10 hardcoded names. (2) test_migration_completeness.py:150 = `assert len(_REGISTERED_MODELS) == 12` exact. (3) alembic/env.py:57~60 = 13-model tuple (cited 56~60 covers it).

DRIFT IS REAL AND GREEN: Base.metadata has 13 tables (verified by enumeration); env.py lists 13; the test tuple lists 12 — AnalysisAttempt absent. `pytest test_all_registered_models_have_tables` PASSES (1 passed) because the tuple is compared against itself. Two manual lists of the same set with no cross-check — exactly as claimed.

POSITIVE CONTROL (decisive): I injected a synthetic new owner-scoped aggregation called without user_id and unregistered in _OWNER_SCOPED. Result: `collected calls: [('dashboard_kpi', True)]`, `missing: []` → guard GREEN. The `node.attr in names` filter in _is_dashboard_service_attr drops the symbol before evaluation. This is precisely the #1074 class (sibling aggregation missing owner filter → cross-tenant private-repo CTA exposure) that #1086 was built to seal. The guard's own test_helper_ignores_non_owner_scoped codifies this blindness as intended.

NO COMPENSATING GUARD: tests/unit/services/test_dashboard_service_user_id_filter.py is hand-written per-function tests (test_dashboard_kpi_filters_by_user_id, test_dashboard_trend_..., test_frequent_issues_v2_..., etc.) — a THIRD manual enumeration, not a derivation. Reinforces rather than refutes.

CORRECTION TO FINDING: the contrast group is overstated. check_dead_code.py does derive targets (_ADDED_DEF regex over diff ADDED lines + count_ast_references AST walk), but also carries a manual list — _SCOPED_DIRS = ("src/repositories/", "src/services/"). The real distinction is granularity: a coarse, stable scope filter vs. a per-symbol enumeration touched on every feature. Prescription should read "derive within a coarse scope," not "eliminate all lists."

SEVERITY RATIONALE (P2→P1): The session brief explicitly asks "가드의 가드 — 신규 가드 4종에 #1094 형(가드 무력한데 green) 결함이 더 있는가?" This answers affirmatively with reproduction. Not a prediction — one instance is ALREADY silently drifted (12 vs 13), and #1086 is remediation for a tenant-leak incident yet is blind in the recurrence direction (new code). Not P0: nothing regressed, guards are net-additive, all 10 current aggregations do pass user_id (parity test passes on the real route), and exposure requires a future commit.

RECOMMENDED REMEDIATION: (a) test_migration_completeness — replace the self-referential tuple with derivation from Base.metadata.tables (or assert env.py's tuple == the test's, making the two lists cross-check); (b) #1086 parity — derive candidates from dashboard_service's public aggregation surface (AST of the service module) and require each to be either called with user_id or explicitly annotated `# global-metric-ok:`, mirroring check_dead_code.py's `# unwired-ok:` escape hatch; (c) add positive-control tests to each guard proving the detector fires on a synthetic violation of the ADDITION direction, not just rename/removal.

### P1-11. [docs] owed-verification 원장이 어디에도 배선되지 않음 — 정책 통합 주장이 실제 정책 본문과 불일치 (기록만 하는 원장)

- **위치**: `docs/runbooks/owed-verification.md:33`
- **주장**: #1084 가 신설한 `docs/runbooks/owed-verification.md` 는 CLAUDE.md·`.claude/policies/`·`.claude/rules/` 어디에서도 참조되지 않는다. 원장 자신은 line 33 에서 "세션 종료 시 이 원장 갱신이 정책 5 Phase-종료 cross-reference 자가 검토(정책 2/5/8/11)의 하위 체크다" 라고 단언하지만, 그 정책 본문(CLAUDE.md:142, .claude/policies/active.md:432)에는 원장에 대한 언급이 0건이다. 즉 원장은 회신을 유도하는 메커니즘이 아니라 **읽힐 트리거가 없는 순수 기록물**이며, 이는 본 사이클의 P0(문서-only 트리거는 실패한다 — 2회 연속 실증)이 진단한 실패 모드를 그대로 재생산한 것이다.
- **근거**: `grep -rn "owed" CLAUDE.md .claude/` → 실질 hit 0건 (유일 매치 `.claude/settings.json:9` 는 `check_edit_allowed.py` 의 'allowed' 오매치). 저장소 전체에서 원장을 참조하는 곳은 `docs/runbooks/operational-smoke-checks.md:6` 단 1곳 + 이력 문서(cycle-history.md:156 · STATE.md:15 · _archive/reports/2026-07-18-retrospective.md:73) 뿐. 반면 CLAUDE.md:142 = "Phase 종료 시점 의무는 정책 2/5/8/11 4 정책에 분산 … 4 정책 cross-reference 자가 검토 의무" — 원장 미언급. .claude/policies/active.md:432 = "## 정책 5: Phase 종료 cross-reference 4 정책 열거 상세" — 동일하게 미언급. 원장이 담고 있는 6행 중 2행(#1058 SMTP 실발송·#1062 NULL-owner IDOR 오차단)은 원장 스스로 "🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)" 으로 분류했고, CLAUDE.md 정책 5 NEW-P0-N 은 "매 사이클 진행 신호 회신 의무" 를 규정하나 이를 상기시킬 배선이 없다. 6행 전부 ⏳ 미회신 누적 — 메모리 `feedback-stale-blocker-policy.md`("머지 대기 4사이클 누적 금지")가 경고한 정확한 궤적.
- **권고**: (1) CLAUDE.md 정책 5 cross-reference 본문(line 142)과 6-step ⑤ 에 `docs/runbooks/owed-verification.md` 갱신·회신 확인을 명시 항목으로 추가하고, active.md:432 정책 5 상세에도 하위 체크로 등재해 원장의 자기 주장과 정책 본문을 일치시킨다. (2) 더 강하게는 `check_retro_cadence.py` 패턴을 재사용해 `scripts/check_owed_verification.py`(⏳ 행 수 + 최고 등급 + 최고 경과 사이클 수 loud 출력)를 만들고 CLAUDE.md 작업 시작 전 필수 체크리스트에 배선한다 — 안전등급 ⏳ 가 1건이라도 있으면 세션 시작 시 눈에 띄게. (3) 원장 line 33 의 "하위 체크다" 서술은 배선 완료 전까지는 사실이 아니므로, 배선과 같은 PR 에서 함께 참으로 만든다(정책 4 — 단언과 가드를 같은 PR 에).
- **cross-verify**: SEVERITY_ADJUST — 모든 인용 재확인 통과 — 핵심 결함은 실재하나 P0 근거 3건 중 2건이 무너져 P1 로 조정.

**검증된 사실 (전건 일치)**
- `grep -rn "owed" CLAUDE.md .claude/` → 실질 hit 0건. 유일 매치 `.claude/settings.json:9` = `check_edit_allowed.py` 오매치, 주장대로.
- `owed-verification.md:33` 원문 일치: "세션 종료 시 이 원장 갱신이 정책 5 Phase-종료 cross-reference 자가 검토(정책 2/5/8/11)의 하위 체크다".
- `CLAUDE.md:142` = 정책 5 cross-reference 강화(정책 2/5/8/11 열거) — 원장 미언급 확인.
- `.claude/policies/active.md:432` = "## 정책 5: Phase 종료 cross-reference 4 정책 열거 상세" — 4 정책 불릿 열거, 원장 미언급 확인.
- 6행 전부 ⏳, 2행이 🔴 안전/데이터 등급(#1058·#1062) 확인.

**따라서 CONFIRMED 인 부분**: line 33 의 자기주장이 **거짓**이다. 정책 5 의 4-정책 자가 검토를 수행하는 미래 Claude 는 정책 2/5/8/11 을 열거할 뿐 원장에 도달하지 않는다. "커버리지가 존재한다"고 오도하는 문서라 그 자체로 시정 대상 — 이 점은 배선 논쟁과 무관하게 성립한다.

**P0 근거를 무너뜨린 반증 3건**
1. **"읽힐 트리거 0" 은 과장** — finder 가 "단 1곳" 으로 평가절하한 `operational-smoke-checks.md:6` 은 파일 헤더 블록의 📋 배너(10줄 헤더 중 6줄)이며, 그 파일은 **정책 13 런북**이다. 정책 13 = "매 사이클 종료 시(또는 Phase 종료 시)" 발동이고 `CLAUDE.md:335`·`active.md:168,210` 이 이 파일을 지목한다. 즉 Phase 종료 → 정책 13 → 런북 → 배너 → 원장의 2-hop 경로가 실재한다. 원장 6행 중 4행의 정책 컬럼이 "13" 인 것도 이 진입점이 설계 의도임을 뒷받침한다.
2. **"6건 전부 미회신 누적" 은 시간적으로 무효한 증거** — `git log` 실측: 원장은 commit `e2098d3`(#1084), **2026-07-18 = 검토 대상 세션 당일** 생성. 세션 경계가 0회 경과했으므로 "회신을 유도하지 못한다" 를 입증할 수 없다. `feedback-stale-blocker-policy.md`("4사이클 누적") 인용은 관측이 아니라 **예측을 관측으로 제시**한 것 — 이번 사이클 진짜 P0(카덴스 자기위반)가 ~46 PR 무회고라는 **실측**을 가졌던 것과 대비된다.
3. **세션 시작 중복 표면 존재** — 매 세션 자동 로드되는 `MEMORY.md:3` 이 "D owed 원장(**#1058 SMTP·#1062 IDOR 회신대기**)" 로 최고 등급 2행을 명시 보유. finder 가 NEW-P0-N 의무를 근거로 든 바로 그 2행은 원장 파일과 독립적으로 세션 시작 트리거를 갖는다.

**조정 근거**: 안전등급 2건 무음 유실 위험이 (1)(3)으로 실질 완화되고, 실패 관측은 아직 0건(2). 본 프로젝트 P0 기준(운영 사고 차단·데이터 손실·실측된 자기위반)에 미달. 반면 line 33 거짓 자기주장 + 정책 본문 미배선은 검증된 실 결함이므로 P2 강등도 부적절.

**권장 조치(저비용)**: `CLAUDE.md:142` 정책 5 cross-reference 항목 및 `active.md:432` 4-정책 열거에 원장 갱신 1줄 추가 — 그러면 line 33 자기주장이 참이 된다. 대안은 line 33 을 실제 배선(정책 13 런북 경유)에 맞게 정정. 전자가 정책 4(단언과 가드를 같은 PR 에) 부합.

### P1-12. [docs] docs/architecture.md 가 존재한 적 없는 scripts/README.md 를 트리 종단 항목으로 문서화 (유령 항목)

- **위치**: `docs/architecture.md:170`
- **주장**: `docs/architecture.md:170` 이 scripts/ 트리의 마지막 항목으로 `└── README.md  # 사용자 실행 가이드 + 비용 안내` 를 기재하고 있으나, `scripts/README.md` 는 현재 존재하지 않을 뿐 아니라 git 전체 이력에서 한 번도 존재한 적이 없다. 트리 종단(`└──`) 위치라 시각적으로 트리 완결성을 보증하는 것처럼 보여, 실제로는 3종 신규 가드가 빠진 불완전한 트리를 '완결된 것처럼' 보이게 만든다.
- **근거**: `git log --all --oneline -- scripts/README.md` → 출력 0건(추가·삭제 커밋 모두 없음 = 이력상 부재). `test -f scripts/README.md` → NO. `ls -la scripts/` 실측 목록에 README.md 없음(파일 16 + dev/ + i18n_comments/ + __pycache__). `grep -n "README.md                    # 사용자 실행 가이드" docs/architecture.md` → line 170 단일 매치. 참고로 #977 이 과거 "scripts/ 5종 등재" 로 이 트리를 정정한 이력이 있으나(cycle-history TOC), 그때도 이 유령 항목은 살아남았다.
- **권고**: 둘 중 하나로 결착한다 — (a) architecture.md:170 의 README.md 행을 삭제하고 실제 마지막 항목에 `└──` 를 부여, 또는 (b) scripts/ 사용자 실행 가이드가 실제로 필요하다고 판단되면 `scripts/README.md` 를 신설해 문서를 참으로 만든다. 위 P1(3종 미등재)과 같은 PR 에서 처리하면 트리를 한 번에 파일시스템과 일치시킬 수 있다.
- **cross-verify**: CONFIRMED — 모든 검증 가능 항목 실측 일치. (1) 인용 정확: `grep -n "README.md" docs/architecture.md` → line 170 단일 매치, 문구 동일, 최상위 scripts/ 펜스(141~170) 내부. (2) 이력상 부재 확정: `git log --all -- scripts/README.md` 0건, `--diff-filter=A` 0건 (삭제 아님, 애초에 없음). (3) 트리 불완전 확정: 펜스 대 디스크 엄밀 diff → 유령 1건(README.md) + 미등재 3건(check_dead_code.py / check_noqa_sideeffect.py / check_retro_cadence.py) = 각각 #1083/#1081/#1080 본 사이클 산출물.

단, 근본 원인은 finder 설명("존재한 적 없는 항목 창작")보다 구체적임 — **오귀속(misattribution)**. `src/scripts/README.md` 는 실재하며 내용이 DALL-E 3 사용자 실행 가이드 + OpenAI API 비용 안내로, 고아 주석 "사용자 실행 가이드 + 비용 안내" 와 정확히 일치. 즉 이 행은 `src/scripts/` 소속인데 최상위 `scripts/` 펜스에 잘못 배치됨. 교차 확인: architecture.md:27~29 src/ 트리는 illustration_prompts.py + generate_illustrations.py 만 등재(`└──` 가 후자)라 `src/scripts/README.md` 도 미등재 — 한 행이 동명 두 디렉토리 중 틀린 쪽에 놓여 **양쪽 트리 모두** 부정확. 문서 자신이 line 137 에서 경고하는 바로 그 혼동의 재발 사례.

심각도 P1 유지(조정 없음). 단 근거는 finder 논지와 다름 — "`└──` 가 완결성을 보증한다"는 논증은 약함(박스문자는 완결성 계약이 아니고, 3건 누락을 인과적으로 은폐하지도 않음). 유령 행 단독은 P2 수준. P1 무게는 미검증 3 사실에 있음: (a) `git log -- docs/architecture.md` 본 사이클 커밋 0건(최종 터치 #1075, 이전 세션) → #1080/#1081/#1083 이 6-step ⑥ "예외 없음" 규칙을 3회 연속 위반. (b) **#1085 가 바로 그 "문서 drift 일괄 sync" PR 인데 architecture.md 미터치**(repo 카운트/배지/cron/env-vars/RLS 만 수행) = 부분 조치 실증 — 회고의 remediation 완결성 질문에 대한 구체 사례. (c) `grep -rln "architecture.md" scripts/ .github/workflows/` → 0 hit. check_*.py 가드 9종 존재하나 ⑥ 의무만 기계 가드 부재 = 문서-only. 이는 본 사이클 P0(#1028 문서-only 카덴스 트리거 자기위반 → #1080 기계화)와 **동일 실패 양식이, 그것을 진단한 바로 그 사이클 안에서, 인접 의무에 재발**한 것.

구조적 시사점: 한 건의 문서-only 트리거 기계화가 일반화되지 않음 — 깨진 규칙만 국소 경화하고 동일 약점을 가진 형제 "예외 없음" 의무를 일괄 점검하지 않음. check_docs_sync.py 가 이미 선례 패턴 제공(파일시스템↔펜스 parity 체크는 저비용, 긍정 통제 선례 존재).

### P1-13. [decision] 카덴스 카운터가 어떤 자동 트리거에도 미배선 — P0 조치가 자신이 지목한 '문서-only' 실패 모드를 재생산

- **위치**: `.claude/settings.json:20`
- **주장**: #1080 이 신설한 `check_retro_cadence.py` 는 실행을 강제하는 기전이 전무하다. 유일한 호출 경로가 CLAUDE.md 체크리스트 한 줄이므로, 회고 P0 가 '문서-only 시정이 2회 연속 실패했다'며 기계화를 요구한 바로 그 인지 의존이 한 겹 뒤로 물러났을 뿐 해소되지 않았다. 3번째 재발 경로가 그대로 열려 있다.
- **근거**: `.claude/settings.json:3,20` 은 PreToolUse/PostToolUse 만 정의 — SessionStart 훅 없음. `grep -rn "check_retro_cadence" .github/ .claude/settings.json Makefile .pre-commit-config.yaml` = 0 hit(스크립트 자신·테스트 제외). 유일 참조 = `CLAUDE.md:320` 체크리스트 bash 블록. 회고 본문 `docs/_archive/reports/2026-07-18-retrospective.md:99` — "문서-only 시정의 한계를 실증… 기계적 카운터를 우선 도입해야 한다 — 그러지 않으면 3번째 재발이 보증된다". 결정적으로 `tests/unit/scripts/test_check_retro_cadence.py:150-159` 의 `test_checklist_wires_the_counter` 는 `assert "check_retro_cadence.py" in claude_md` 로 **문서 문자열 존재만** 단언하면서 docstring 은 '배선'이라 주장 — #1094형(가드가 green 인데 무력)의 전형.
- **권고**: `.claude/settings.json` 에 SessionStart 훅으로 배선(또는 pre-commit/CI 백스톱 추가). 동시에 `test_checklist_wires_the_counter` 를 'settings.json 에 실행 엔트리가 존재한다' 단언으로 승격 — 문서 존재를 배선 증거로 인정하는 테스트는 P0 를 은폐한다.
- **cross-verify**: SEVERITY_ADJUST — 모든 인용 실측 확인 — 결함 자체는 실재. (1) `.claude/settings.json:3,20` = PreToolUse/PostToolUse 만 정의, SessionStart 훅 없음. 전역 `~/.claude/settings.json` 은 hooks 키 자체가 부재. (2) repo 전수 grep 결과 `.github/`·`Makefile`·`.pre-commit-config.yaml`·양 settings.json 모두 0 hit — 유일 live 참조 = `CLAUDE.md:320` 체크리스트 한 줄. (3) `tests/unit/scripts/test_check_retro_cadence.py:156-159` 는 보고보다 더 약함: `assert "check_retro_cadence.py" in claude_md` 가 파일 전체 대상 unscoped 부분문자열 검사라, "스크립트를 삭제했다"는 산문에 문자열이 있어도 통과. 체크리스트 bash 블록 소속을 전혀 검증하지 않으면서 docstring 은 '배선'을 주장 — #1094형(green 인데 무력) 전형이 맞고, 세션 컨텍스트의 '가드의 가드' 질문에 대한 정확한 답.

단, P0 → P1 하향: (a) 보고의 "한 겹 뒤로 물러났을 뿐 해소되지 않았다"는 과장 — 기존 실패 모드는 '규칙 상기 + ~46 PR 수동 카운트' 이중 인지 의존이었으나 현재는 판정을 출력하는 단일 명령이라 잔여 확률이 동일하지 않음(감소). (b) 탐지 로직은 무력하지 않음 — `docs/STATE.md:11` 의 라이브 48→5 리셋 실측이 계산부 정상 작동을 입증. 결손은 트리거 한정이지 탐지기가 아님. (c) blast radius = 프로세스 전용(운영/데이터/보안 영향 0)이며, 본 repo 의 P0 정의는 운영 사고 차단 영역. 따라서 '실재하는 미완결 remediation'으로 P1 이 정확. 권고 조치 = SessionStart 훅 배선(기전 존재·미사용) + 테스트를 체크리스트 bash 블록 스코프 단언 또는 settings.json 훅 등재 단언으로 교체(긍정 통제 동반).

### P1-14. [decision] owed 원장이 회신 유도 기전 없는 기록 전용 — 같은 세션의 카덴스 P0 대비 처방 강도 불일치

- **위치**: `docs/runbooks/owed-verification.md:1`
- **주장**: #1084 원장은 안전등급 2건에 '다음 세션 진입 전 명시 회신 의무'(정책 5 NEW-P0-N)를 선언하지만, 그 의무를 세션 시작 시점에 노출하는 경로가 없다. 원장은 세션 시작 체크리스트에 등재되지 않았고 훅·스크립트도 없어, 카덴스 P0 가 '문서-only 라 실패했다'고 판정된 것과 정확히 같은 구조다. 같은 세션 안에서 한쪽은 스크립트로 승격하고 다른 쪽은 markdown 표로 남긴 처방 강도 불일치이며, 6행 전부 ⏳ 누적이 그 결과다.
- **근거**: `docs/runbooks/owed-verification.md` 상단 안전등급 표 — #1058(SMTP 실발송, '출시 이래 100% 실패')·#1062(IDOR 과잉차단) 상태 ⏳, 헤더에 '다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N' 명시. 그러나 `grep -n "owed-verification" CLAUDE.md` = **0 hit**(CLAUDE.md 는 320/326 카덴스만 배선). 전 repo 참조 실측 = `docs/runbooks/operational-smoke-checks.md:6`·`docs/STATE.md:15`·`docs/cycle-history.md:156`·회고 보고서 73행 = 전부 산문 언급. 훅/스크립트/CI 0건. #1058 은 2026-07-17 머지라 원장 신설 시점에 이미 세션 경계를 1회 넘긴 상태였다. 메모리 인덱스도 'D owed 원장(#1058 SMTP·#1062 IDOR 회신대기)'로 미결 상태를 확인.
- **권고**: `check_retro_cadence.py` 에 owed 원장 `⏳` 행 카운트 출력을 1줄 추가(둘 다 세션 시작 신호라 통합이 자연스럽다) 하거나 CLAUDE.md 필수 체크리스트에 원장 확인 줄 추가. 정책 5 NEW-P0-N 영역은 '기록'이 아니라 '노출'이 있어야 회신이 발생한다.
- **cross-verify**: CONFIRMED — CONFIRMED at P1 (severity unchanged). All citations verified. docs/runbooks/owed-verification.md exists; header line 11 declares '다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N'; 6 rows all ⏳ (safety: #1058/#1062 at lines 15-16; ops: #1071/#1072/#1073/#1075 at lines 22-25). `grep -n "owed" CLAUDE.md` = exit 1, 0 hits, while the cadence counter IS wired at CLAUDE.md:320 (session-start checklist command) + :326 (loud rationale). All repo references are prose only (operational-smoke-checks.md:6, STATE.md:15, cycle-history.md:156, retrospective:73); hooks/scripts/CI = 0 across .claude/, .github/, scripts/. The asymmetry is not incidental: scripts/ contains 21 scripts including the 3 guards built in this same session, so mechanization was available and cheap.

DECISIVE EVIDENCE — the project's own retrospective settles it. 2026-07-18-retrospective.md:99 states '문서-only 시정의 한계를 실증한다 … 그러지 않으면 3번째 재발이 보증된다', and :38 frames the cadence remediation as '문서-only 2회 연속 실패 → 기계적 집행'. The session formally concluded document-only remediation fails, mechanized the cadence trigger on that basis, then applied document-only remediation to the owed ledger. The prescription inconsistency is not inferred — it contradicts a written finding in the same document.

BOUNDARY CROSSING CONFIRMED: git log shows #1058 (486573d) and #1062 (81eefe1) merged 2026-07-17, one session before the ledger (2026-07-18). The header's own 'before next session entry' obligation has already lapsed once with no surfacing path.

COUNTER-ARGUMENTS TESTED AND REJECTED: (1) MEMORY.md auto-loads and mentions 'D owed 원장(#1058 SMTP·#1062 IDOR 회신대기)' — but this is a parenthetical fragment in a dense index bullet, strictly weaker than the cadence trigger, which was an explicit CLAUDE.md clause with a numeric threshold and still failed twice; this strengthens rather than refutes. (2) The ledger may be session-END by design (line 33) — refuted by its own header asserting a session-ENTRY obligation under 정책 5 NEW-P0-N, and the line-33 path is itself the document-only 정책 5 cross-reference self-review.

FINDER OVERREACH FLAGGED: '6행 전부 ⏳ 누적이 그 결과다' is weak evidence — the ledger was created the same day, so zero replies is expected, not proof of failure. The core claim survives independently on the absent surfacing path plus same-session asymmetry, so this does not change the verdict.

SEVERITY RATIONALE (P1 held, neither raised nor lowered): below the cadence P0, which was a repeat violation of a mandatory policy. P1 is correct rather than P2 because the gap gates unverified safety state with real blast radius — #1058's fix is unverified against a path documented as '출시 이래 100% 실패', so if the fix is wrong, email notification remains fully broken and silent; #1062 risks 403 over-blocking on 7 write routes for legitimate owners. Not a code defect, so not P0; a process gap holding unverified safety state, so not P2. Suggested remediation: add a session-start surfacing path (e.g. scripts/check_owed_verification.py printing unresolved 안전등급 rows, advisory/non-blocking like check_retro_cadence.py) and register it in the CLAUDE.md:320 checklist block.

### P1-15. [tooling] check_dead_code.py (#1083) 는 이름 충돌로 눈이 먼다 — 일반 CRUD 명 신규 함수는 호출자 0 이어도 '✅ all wired'

- **위치**: `scripts/check_dead_code.py:63`
- **주장**: 신규 dead-code 가드가 `ast.Attribute` 를 **수신자 검사 없이 attr 이름만으로** 매칭하고 `_total_references` 가 정의 파일 포함 src/ 전역을 세기 때문에, `count`/`create`/`delete`/`update`/`add` 같은 흔한 repo/service 함수명은 무관한 `.count()` 호출에 흡수돼 호출자 0 dead code 가 그대로 통과한다. #1060 `find_orphaned` 를 잡은 것은 그 이름이 유일했기 때문이며, 가드는 이름 운에 의존한다 — CI 차단 가드에 남은 #1094 형(green 인데 무력) 결함.
- **근거**: scripts/check_dead_code.py:63-79 `count_ast_references` 는 `isinstance(node, ast.Attribute) and node.attr == name` 만 검사(수신자·타입 무관). scripts/check_dead_code.py:96-102 `_total_references` 는 `src_root.rglob('*.py')` 전역 합산(정의 모듈 포함).
실측 `_total_references(name, Path('src'))`: get=561 · first=53 · all=50 · count=40 · refresh=23 · add=21 · delete=17 · update=10 · close=8 · create=6 (list_all=0).
**양방향 실증(worktree 격리)**: (a) 긍정 통제 — 050bab6(#1060) 에 현행 가드 적용 시 `EXIT=1 / 🔴 ... - find_orphaned()` 로 정상 탐지. (b) 반증 — 같은 worktree 의 `src/repositories/analysis_attempt_repo.py` 에 호출자 0 인 `def count(db, *, repo_id)` 추가 후 실행 시 `EXIT=0 / ✅ 신규 공개 함수 1개 모두 src 내 호출자 有 / all wired`.
- **권고**: 참조 카운트를 (1) 정의 파일 제외 + (2) `ast.Attribute` 는 수신자 모듈/객체가 대상 repo·service 모듈로 해석될 때만 계수(또는 `from src.repositories.X import name` / `X.name` qualified 참조만 인정)로 좁힐 것. 최소 조치로 `_total_references` 에서 정의 파일을 빼고, 충돌 위험 이름(참조 수는 ≥1 이나 qualified 참조 0)을 별도 ⚠️ 등급으로 보고. 회귀 가드로 `count` 형 반증 케이스를 테스트에 고정.
- **cross-verify**: CONFIRMED — CONFIRMED — reproduced in full, plus three strengthening findings.

CITATIONS VERIFIED: check_dead_code.py:63-79 `count_ast_references` matches `isinstance(node, ast.Attribute) and node.attr == name` with no receiver/type check. :96-102 `_total_references` sums `src_root.rglob('*.py')` globally including the defining module. Both exact.

REPRODUCTION (exact): all 10 reported counts matched to the digit (get=561, first=53, all=50, count=40, refresh=23, add=21, delete=17, update=10, close=8, create=6, list_all=0). Both control directions reproduced in an isolated git worktree (removed; main tree verified clean, 0 porcelain entries, branch unchanged): (a) positive control — zero-caller `count_zzz_distinctive_probe` -> EXIT=1, correctly flagged; (b) reported failure — zero-caller `def count(db, *, repo_id)` in analysis_attempt_repo.py -> EXIT=0 "✅ 신규 공개 함수 1개 모두 src 내 호출자 有 / all wired".

THREE FINDINGS BEYOND THE ORIGINAL REPORT:
1. Blind spot is LIVE convention, not hypothetical. `create` (2 files), `get` (1), `upsert` (2) are already existing public function names inside src/repositories/. Tested the highest-realism case — zero-caller `def create()` following the repo's own convention — EXIT=0, masked partly by the Anthropic SDK's `messages.create()`, an entirely unrelated receiver.
2. Collision domain is STRUCTURALLY ALIGNED with the guarded scope. Receiver analysis of absorbing refs: SQLAlchemy Session/Query API (func.count()x15, db.add()x20, .all()x42, .first()x41, db.delete()) and dict.get (data.get()x68, result.get()x39). That is the repository layer's own native vocabulary — the guard is blindest exactly where it is aimed. Not random luck; a scope/vocabulary overlap.
3. The guard's own tests ENCODE the luck. Every count_ast_references test in tests/unit/scripts/test_check_dead_code.py uses `find_orphaned` (the unique name); `_total_references` — where the src-wide summation that causes absorption occurs — has ZERO tests (grep -c = 0). Suite is green because it exercises only the lucky case: precisely the #1094-class "green but inert" defect this cycle asked about ("가드의 가드").

SEVERITY P1 RETAINED (not adjusted). Considered downgrade to P2: impact is dead-code hygiene with no production/operational consequence (the original #1060 find_orphaned incident caused no outage), the guard is additive vs. the prior state of nothing, and only ~3/109 existing scoped names are generic — the repo's dominant descriptive multi-word convention (count_by_classification, delete_all_for_repo) would still be caught. Rejected the downgrade because (a) the failure is SILENT — it prints "✅ all wired" with no signal that matching was name-lucky, giving a false all-clear on a CI blocking gate; (b) #1083 was declared as remediation of retro P1#9/14/15, so this is partial remediation presented as closed — the remediation-completeness question this retro must answer; (c) the untested `_total_references` path means no existing test would ever surface the regression. Not P0: no operational/production impact.

FRAMING CORRECTION (honest caveat, does not change verdict): the phrase "눈이 먼다 / is blind" overstates breadth — the guard works for the majority of realistic new functions. The accurate claim is that detection is contingent on name uniqueness and fails silently for the generic-name class, which the repo demonstrably already uses.

### P1-16. [tooling] owed 원장(#1084)이 문서-only 추적기 — 본 사이클 P0 가 '문서-only 시정은 행동을 못 바꾼다'고 결론낸 직후 같은 형태로 신설

- **위치**: `docs/runbooks/owed-verification.md:15`
- **주장**: 본 사이클의 P0 결론은 '문서-only 트리거(#1028)가 2회 연속 실패 → 기계 신호로 승격'이었는데, 같은 사이클의 Track D 는 회신을 유도해야 할 owed 원장을 **기계 표면화 0** 인 문서로 신설했다. 원장은 CLAUDE.md 어디에도 참조되지 않아 세션 시작 체크리스트(카덴스는 방금 기계화된 그 자리)에 뜨지 않는다. 6행 전부 ⏳ 이고, 그중 2행은 원장 스스로 정책 5 NEW-P0-N(매 사이클 회신 의무·정책 9 완화 미적용)로 등급했다 — 메모리 `feedback-stale-blocker-policy.md` 가 금지한 누적 경로. 원장은 회신을 '유도'하는 메커니즘이 아니라 '기록'하는 문서다.
- **근거**: `docs/runbooks/owed-verification.md` 상태 실측 — 6행 전부 ⏳: 안전/데이터 등급 `:15`(#1058 SMTP 실발송) · `:16`(#1062 IDOR 과잉차단), 운영/외부계약 등급 `:22`(#1071 HSTS/쿠키) · `:23`(#1072 approve 422) · `:24`(#1073 orphan sweep cron) · `:25`(#1075 retention sweep cron).
`grep -n "owed" CLAUDE.md` → **0 매치**(세션 시작 체크리스트 `CLAUDE.md:315-322` 에 부재; 같은 블록의 `CLAUDE.md:320` 은 `python scripts/check_retro_cadence.py` 로 기계화됨).
참조는 `docs/runbooks/operational-smoke-checks.md:6` · `docs/STATE.md:15` · `docs/cycle-history.md:156` 뿐 — 전부 사후 기록 문서.
- **권고**: `check_retro_cadence.py` 와 동형의 `check_owed_verification.py`(원장 ⏳ 행 수 + 최고 등급 + 등재 후 경과 사이클 카운트, advisory·exit 0)를 세션 시작 체크리스트(CLAUDE.md:315-322)에 배선. 안전/데이터 등급 ⏳ 가 1 사이클 이상 남으면 loud 경고. 최소 조치로라도 CLAUDE.md 체크리스트에 원장 경로 1줄 추가.
- **cross-verify**: CONFIRMED — All cited evidence verified exactly. docs/runbooks/owed-verification.md:15,16,22,23,24,25 — all 6 rows ⏳. `grep -n "owed" CLAUDE.md` → 0 matches; the session-start checklist (CLAUDE.md:315-322) carries 5 steps including the freshly mechanized `python scripts/check_retro_cadence.py`, and the ledger is absent from that exact block. `grep -rn "owed" scripts/ .claude/ .github/` → zero machine surfacing. All existing references (operational-smoke-checks.md:6, STATE.md:15, cycle-history.md:156) are sunk-record documents.

Decisive evidence beyond the finding's own case: the original P1#13 remediation (2026-07-18-retrospective.md:73) prescribed a concrete induction mechanism — "trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치." I tested whether it fired. PR #1084 (the ledger's own PR) has the section, but PR #1087 (session trailing sync) and PR #1093 (most recent sync, commit b3438c0, merged AFTER the ledger existed) both contain zero owed mentions. The prescribed pairing failed on both of its first two opportunities inside the same session that prescribed it. This converts the claim from analogy to an observed first-measurement-window self-violation — the identical signature to the P0 it is compared against (#1028).

Considered and rejected two downgrade arguments: (a) the ledger is net-positive vs. the prior state (items tracked nowhere → tracked); (b) its consumer is the user, so no script can compel a reply. Neither survives — the finding does not ask to force a user reply, it identifies that nothing surfaces owed rows to either party at any recurring checkpoint, and the Claude-side surfacing that WAS specified is exactly what was missed twice. Net-positive-but-inert is still inert. Two rows self-classify as NEW-P0-N ("매 사이클 회신 의무"), an obligation with no trigger capable of firing it — the precise accumulation path feedback-stale-blocker-policy.md bans. Row :15 (#1058 SMTP) is live exposure: email 100% broken since launch, fix unverified in production.

Minor imprecision not affecting the verdict: "6건 전부 미회신 ⏳ 누적" overstates duration (ledger is hours old, no reply window meaningfully elapsed). The substantive claim — record rather than mechanism — stands independently on the two missed sync PRs.

Severity held at P1 (not adjusted). Cheap fix available on the surface already built: extend scripts/check_retro_cadence.py (133 lines, advisory/exit-0 pattern) to parse the ledger and print ⏳ row counts, and add the corresponding line to the CLAUDE.md session-start checklist alongside the cadence counter.

### P1-17. [code] 카덴스 카운터의 '배선'이 여전히 문서-only — P0 시정이 P0 의 실패 양식을 재생산

- **위치**: `.claude/settings.json:20`
- **주장**: P0 근본은 '정책 8 진화 (4) 트리거가 문서-only 라 인지 의존 → 자기위반'이었다. 시정(#1080)은 스크립트를 만들었으나 그 스크립트의 **호출**은 다시 CLAUDE.md 체크리스트 텍스트 한 줄뿐이다. settings.json 에 SessionStart 훅이 없어, Claude 가 체크리스트를 읽고 실행하기로 마음먹어야만 작동한다 — 즉 '문서-only 정책'에서 '문서-only 호출을 가진 스크립트'로 한 단계 이동했을 뿐 인지 의존은 그대로다. 세 번째 실패가 같은 자리에서 날 수 있다.
- **근거**: .claude/settings.json:2~32 — hooks 에 PreToolUse(check_edit_allowed, doc_review_gate) + PostToolUse(posttool_pytest_smoke) 뿐, SessionStart 항목 없음. 유일한 호출 배선은 CLAUDE.md:320 의 체크리스트 bash 블록. 이를 검증하는 테스트마저 문서 멘션 검사다 — tests/unit/scripts/test_check_retro_cadence.py:157 `assert "check_retro_cadence.py" in claude_md` (실행 배선이 아니라 문자열 존재 단언).
- **권고**: .claude/settings.json 에 SessionStart 훅으로 `python scripts/check_retro_cadence.py` 등록(advisory·exit 0 이라 안전). 그러면 test_checklist_wires_the_counter 도 settings.json 배선 단언으로 승격 가능. 문서 체크리스트는 보조로 존치.
- **cross-verify**: CONFIRMED — Citation verified exactly. .claude/settings.json:2-32 contains only PreToolUse (check_edit_allowed, doc_review_gate) and PostToolUse (posttool_pytest_smoke); repo-wide grep for "SessionStart" returns zero matches. The sole invocation of check_retro_cadence.py is CLAUDE.md:320 (checklist bash block) plus prose/narrative mentions in CLAUDE.md:326, docs/STATE.md:11, docs/cycle-history.md:152 — no hook, no CI job, no pre-commit entry.

DECISIVE EVIDENCE NOT CITED BY REPORTER — same-batch wiring asymmetry: the sibling guards from this identical remediation batch ARE machine-wired and blocking (.github/workflows/ci.yml:102 check_noqa_sideeffect.py; ci.yml:109 check_dead_code.py). Within one batch, the two P1-tier guards received enforced server-side wiring while the guard remediating the batch's only P0 received text wiring alone. This inversion is strong evidence of oversight rather than deliberate design — it is not plausible that the highest-severity item was intentionally given the weakest enforcement.

Test has no positive control: tests/unit/scripts/test_check_retro_cadence.py:157 asserts `"check_retro_cadence.py" in claude_md` — a substring check that passes if the string appears in a comment, a changelog line, or a sentence stating the counter was removed. It cannot distinguish wired from unwired, making it the same #1094-class defect (guard green while blind) this retrospective was convened to find.

STEELMAN CONSIDERED AND REJECTED: the counter did run live (48->5 reset, docs/STATE.md:11) so it is not inert, and even under SessionStart the output is advisory (exit 0, non-blocking) so Claude must still act. But this conflates two distinct dependences. Today the trigger fires only if Claude retrieves and elects to run the checklist — the exact conditional-retrieval failure that broke twice (#1028 doc-only policy, then the first measurement window). A SessionStart hook makes firing UNCONDITIONAL, reducing the dependence to "notice loud output." Materially weaker, so the proposed remedy is substantive and the gap is real. Not already-resolved, not speculative.

SEVERITY HELD AT P1 (as claimed, no adjustment): blast radius is process degradation (missed retrospective cadence), not a production incident, which caps it below P0; but a twice-failed mechanism at the same site, with a cheap fix available in hook infrastructure already present in the same file, exceeds P2.

REMEDY: add a SessionStart hook in .claude/settings.json invoking `python scripts/check_retro_cadence.py`, and replace the CLAUDE.md substring assertion at test line 157 with a settings.json parse asserting the SessionStart entry exists and references the script (positive control on wiring, not on prose).

### P1-18. [code] 신규 가드 4종에 '탐지기가 실제로 위반을 차단한다'는 긍정 통제 부재 — 카덴스 테스트는 공허 단언

- **위치**: `tests/unit/scripts/test_check_retro_cadence.py:146`
- **주장**: #1094 가 드러낸 '가드가 무력한데 green' 결함이 구조적으로 남아 있다. 가드 자체 테스트는 (a) 순수 헬퍼 단위 테스트와 (b) ci.yml YAML 문자열 배선 메타 테스트로만 구성돼 있고, `main()`·`_git()`·`_changed_*_files()` 플러밍을 실행해 위반 입력에 exit 1 이 나오는지 확인하는 통제가 없다. 특히 카덴스 스크립트의 유일한 subprocess 테스트는 `returncode == 0`(advisory 라 항상 참) 과 `"UnicodeEncodeError" not in stderr`(정상 시 항상 참) 만 단언 — 카운팅 로직이 망가져 영구 'skip' 으로 퇴화해도 전 테스트가 green 이다. #1094 의 encoding 결함이 이 테스트를 통과한 이유가 정확히 이 공허성이며, encoding 만 고쳤을 뿐 공허성 자체는 미시정.
- **근거**: tests/unit/scripts/test_check_retro_cadence.py:141~147 — 단언 2개가 `r.returncode == 0` 과 `"UnicodeEncodeError" not in r.stderr`. 판정 문자열(breached/여유/skip) 미검증. scripts/check_retro_cadence.py:118~121 에서 `_boundary_commit` 이 None 이면 skip 출력 후 return 0 → 위 테스트 그대로 통과. tests/unit/scripts/test_check_noqa_sideeffect.py 전 32~140행이 순수함수 + yaml 배선 메타만, tests/unit/scripts/test_check_dead_code.py:30~133 동일. 대조군으로 tests/unit/scripts/test_empty_except_guard.py:60~84 는 긍정/부정 통제 4건 보유(옳은 형태).
- **권고**: 가드별 e2e 통제 1쌍씩 추가: tmp_path 에 git init → 위반 커밋 생성 → `subprocess.run([sys.executable, 'scripts/<guard>.py', base, head])` → `returncode == 1` + 위반 파일명이 stdout 에 포함, 그리고 클린 커밋에 `returncode == 0`. 카덴스는 회고 파일/커밋을 합성해 breached 배너 문자열을 단언(임계 경계 15 포함).
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인. test_check_retro_cadence.py:141~147 의 단언 2개는 정확히 `r.returncode == 0` 과 `"UnicodeEncodeError" not in r.stderr` 뿐이며, check_retro_cadence.py:118~121 의 `_boundary_commit` None → skip → return 0 경로도 확인.

실증: `_git` 을 빈 문자열 반환으로 교체(플러밍 파손 시뮬레이션) 후 `main()` 직접 호출 → rc=0 + `ℹ️ ... skip` 배너 출력. 기존 테스트는 returncode==0 만 보므로 동일하게 통과. `main()` 이 4개 경로(112/116/121/129) 전부 0 을 반환하므로 어떤 로직 퇴화도 현행 테스트로 검출 불가 — '영구 skip 퇴화해도 전 테스트 green' 주장이 실측으로 성립.

지적자가 인용하지 않은 강화 근거 2건(독립 확인):
(1) 4번째 가드 posttool_pytest_smoke(#1082)가 최악 사례인데 미인용. tests/unit/hooks/test_posttool_pytest_smoke.py 는 is_src_file/derive_test_target 순수함수만 커버 — `main()`/`_run()` 미실행이라, 스코프 테스트 실패 시 실제로 `❌ 스모크 실패` 를 내는지 검증하는 통제가 전무. **false-green 을 고치려고 만든 훅에 실패 탐지 통제가 없다** = #1094 패턴 그대로.
(2) 저장소 자체 선례 존재: test_generate_illustrations.py:101~185 와 test_extract_design_tokens.py:135 는 `main()` 을 구동하고 반환값을 단언. 신규 가드 4종이 저장소 기존 표준보다 후퇴한 것이라, 요구가 새롭거나 비싸지 않음. 대조군 test_empty_except_guard.py:60~84(긍정/부정 통제 4건)는 같은 디렉토리·같은 세션 산출물 = 옳은 형태가 이미 알려져 있었음.

스코핑 정정 1건(반증 아님): '긍정 통제 부재' 라는 일괄 표현은 check_noqa_sideeffect/check_dead_code 에는 다소 과장. find_violations(위반 diff → 위반 반환, test:94~98)·count_ast_references 는 실제 탐지기 수준 긍정 통제임. 이 2종에서 결여된 것은 '검증된 탐지기'와 '검증된 CI 배선(R1/R2/R3)' 사이의 seam — 즉 `main()` 이 탐지된 위반을 exit 1 로 변환하는지에 대한 통제. 반면 카덴스 카운터와 스모크 훅은 어떤 종류의 종단 통제도 0 건이라 지적이 전면 성립.

심각도 P1 유지(P2 미강등): 카덴스 카운터는 본 회고 P0(문서-only 트리거가 두 번 조용히 실패)의 직접 시정물. 카운팅 파이프라인이 조용히 skip 으로 퇴화하면 그 P0 가 무증상 재발한다 — '안전망의 무음 소실'은 정확히 이번 세션이 봉인하려던 결함 계열이며, advisory 도구라는 점이 심각도를 낮추지 않음(가드의 가치 = 실패 시 신호를 내는 것 하나뿐이므로 신호 상실 = 전손).

권고 시정: (a) 카덴스 — tmp_path 임시 git repo(회고 리포트 커밋 + 머지 PR 제목 N건)로 main() 구동해 breached/여유/skip 판정 문자열 3종 단언, (b) 스모크 훅 — 실패하는 임시 테스트를 스코프에 두고 main() 실행해 `❌` 배너 출력 단언, (c) noqa/dead_code — 위반 입력으로 main() 이 1 반환·정상 입력에 0 반환하는 seam 통제 각 2건.

### P1-19. [code] check_dead_code 의 참조 카운트가 이름 기반 — 흔한 repository/service 함수명은 무조건 통과

- **위치**: `scripts/check_dead_code.py:96`
- **주장**: 가드가 `src/` 전역에서 동일 **이름**의 ast.Name/ast.Attribute 를 세기 때문에, 신규 미배선 함수라도 이름이 다른 모듈에 이미 존재하면 참조>0 으로 오통과한다. repository/service 계층은 함수명이 고도로 반복적(create/upsert/find_by_id/list_pending)이라 오통과율이 낮지 않다. 아이러니하게 동기 사례였던 `find_orphaned` 조차 #1073 배선 이후 참조 1 이 되어, 지금 같은 이름의 미배선 함수를 새로 추가하면 가드를 통과한다 — 즉 가드가 자기 동기 사례를 더는 재현 차단하지 못한다.
- **근거**: scripts/check_dead_code.py:63~79 `count_ast_references` 는 `node.id == name` / `node.attr == name` 만 비교(정의 모듈·import 결속 무관), :96~102 `_total_references` 가 `Path('src').rglob('*.py')` 전역 합산. 실측 — src/ 전역 AST 참조 수: find_by_id=4, create=6, upsert=3, list_pending=1, find_orphaned=1 → 다섯 이름 모두 신규 미배선이어도 PASS. 추가 실측: src/repositories+src/services 의 공개 def 100개 중 8개(create, find_by_full_name, find_by_id, list_by_repo, list_pending, save_new, upsert, user_cost_summary)가 이미 2개 이상 파일에 중복 정의돼 이름만으로는 원리적 구분 불가.
- **권고**: 이름 매칭을 결속 기반으로 승격: 정의 모듈 경로를 알고 있으므로, 참조로 인정할 조건을 (a) `from src.<pkg>.<mod> import <name>` 이 있는 파일의 Name 참조 또는 (b) `import src.<pkg>.<mod>` 계열이 있는 파일의 `<mod>.<name>` Attribute 참조로 좁힌다. 최소 조치로는 정의 파일 자신을 참조 집계에서 제외 + 동명 함수 다중 정의 시 loud-warn 출력.
- **cross-verify**: CONFIRMED — CONFIRMED at P1 — reproduced end-to-end, and the finding understates the defect.

CITATIONS VERIFIED EXACT: check_dead_code.py:63-79 count_ast_references compares only `node.id == name` / `node.attr == name`, with no binding to defining module or import; :96-102 _total_references sums across `Path("src").rglob("*.py")`; main():123 treats any nonzero total as "wired". All stated line spans match.

EMPIRICAL CLAIMS REPRODUCED via the guard's own functions: find_by_id=4, create=6, upsert=3, list_pending=1, find_orphaned=1 (all >0 → all PASS). Independently confirmed 8 of 100 public defs in src/repositories+src/services are multiply-defined (create, find_by_full_name, find_by_id, list_by_repo, list_pending, save_new, upsert, user_cost_summary).

END-TO-END PROOF (isolated git worktree, since removed; working tree clean): added src/repositories/probe_collide_repo.py with genuinely zero-caller `find_by_id`+`upsert` plus a unique-named control. Guard blocked ONLY `zzz_totally_unique_probe_fn`; both colliding zero-caller functions passed silently. DECISIVE: re-adding an unwired `find_orphaned` — the guard's own motivating case from #1060 — yields "✅ 신규 공개 함수 1개 모두 src 내 호출자 有", exit 0. The guard affirmatively certifies its own motivating incident as wired, i.e. it can no longer reproduce-block the incident it was built for.

TWO REFINEMENTS AGAINST DOWNGRADE:
(1) False-pass surface is far larger than the 8/100 framing — the namespace is every ast.Name/ast.Attribute in src/ = 2,324 distinct names, not just repo/service defs. 26 of 42 plausible generic function names (62%) pass silently. The poisoning names include query, filter, first, all, get, add, count, close, commit, rollback — the SQLAlchemy Session/Query idioms saturating the repository layer, so the guarded layer's own ORM calls blind the guard to the guarded layer's own function names.
(2) This is a false-GREEN, not a mere gap: it prints affirmative "✅ ... all wired" and exits 0 — the exact #1094 class ("guard blind but green") this cycle was chartered to hunt, and a direct affirmative answer to the retro's "가드의 가드" charter question. Root cause of shipping: tests/unit/scripts/test_check_dead_code.py has positive controls for parse helpers and count_ast_references, but NO test exercises _total_references — the cross-module aggregation carrying the defect.

SEVERITY HELD AT P1 (no adjustment): not P0 because worst case is dead code surviving review, not production/user impact, and distinctive names are still caught; not P2 because a gate asserting success while unable to block its own motivating incident manufactures false confidence worse than silence for the ~62% of names it silently skips.

SUGGESTED FIX DIRECTION: resolve references against import binding / defining module (e.g. count only refs in files that import the symbol from the new module, or match qualified module.attr), rather than bare name equality across src/; and add a regression test that a newly-added unwired `find_orphaned` is still blocked (self-motivating-case guard).

### P1-20. [code] owed 원장이 회신 유도 메커니즘 없음 — 자체 페어링 규칙조차 첫 창에서 2/3 위반

- **위치**: `docs/runbooks/owed-verification.md:5`
- **주장**: 원장(#1084)은 기록 전용이며, 회신을 유도하는 경로가 코드·훅·CI·세션 체크리스트 어디에도 없다. 더 결정적으로 원장이 스스로 정한 유도 장치('trailing sync PR body 에 §owed-verification 표 상시 배치')가 신설 직후 창에서 이미 2/3 위반됐다. 카덴스 P0 와 동일한 '문서-only 규칙은 자기 첫 측정창에서 실패한다' 패턴의 재현이며, 원장 6건 전부 ⏳ 인 것은 사용자 무응답이 아니라 애초에 제시된 적이 없기 때문일 가능성이 크다. 추가로 표에 기록일 컬럼이 없어 '몇 세션 묵었는가'를 기계적으로 계산할 수 없다 — 정책 5 NEW-P0-N(안전등급 매 사이클 회신 의무) 대상인 #1058 SMTP 의 지연을 감지할 수단이 없다.
- **근거**: docs/runbooks/owed-verification.md:5 — 'trailing sync PR body 의 §owed-verification 표와 페어' 명문. 실측: `gh pr view <n> --json body | grep -c owed` → #1087(원장 머지 후 첫 trailing sync)=0, #1093(두 번째)=0, #1094=2. 원장 참조처 전수 grep 결과 docs/cycle-history.md:156 · docs/STATE.md:15 · docs/runbooks/operational-smoke-checks.md:6 · 회고 리포트뿐 — CLAUDE.md 체크리스트·scripts/·.github/ 참조 0건. 표 헤더는 `| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |` 로 기록일/경과 컬럼 없음.
- **권고**: (a) 표에 `기록일` 컬럼 추가. (b) `scripts/check_owed_verification.py` 신설 — ⏳ 행 수와 최장 경과일을 세어 배너 출력, check_retro_cadence 와 같은 체크리스트 줄(및 SessionStart 훅)에 배선. (c) 안전등급(#1058·#1062) 행은 경과 임계 초과 시 loud 경고로 정책 5 NEW-P0-N 매 사이클 회신 의무를 기계화.
- **cross-verify**: SEVERITY_ADJUST — All cited evidence independently verified. docs/runbooks/owed-verification.md:5 contains the quoted self-imposed pairing rule verbatim. PR body counts reproduce exactly (#1087=0, #1093=0, #1094=2). Merge timestamps confirm the rule was in force when violated: #1084 (ledger) merged 2026-07-18T05:38:12Z, #1087 merged 06:15:58Z — 38 minutes later — and #1093 at 09:32:05Z. Repo-wide grep confirms zero enforcement path: the only non-doc hits in scripts/ and .claude/ are substring matches on "allowed" (check_edit_allowed.py; "indentation allowed" comment), and CLAUDE.md contains 0 occurrences of both "owed" and "원장". All genuine references are docs-only (cycle-history.md, STATE.md, operational-smoke-checks.md, the 2026-07-18 retrospective report, and the ledger itself) — circular, since nothing in the session checklist or 6-step points to it. Table header confirmed as `| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |` with no date/elapsed column, so staleness cannot be computed mechanically.

CORRECTION strengthening the finding: "2/3 위반" understates it. The rule's target population is trailing sync PRs = {#1087, #1093} only; #1094 is titled "fix(codeql): 자초 py/empty-except #547~#549 봉인" and is not a trailing sync, so its 2 hits are incidental. Actual compliance among rule targets is 0/2.

SEVERITY ESCALATED P2 → P1. This is a remediation-completeness defect, not housekeeping — one of the questions this retrospective is chartered to answer. The same session's headline P0 was that doc-only rules fail in their first measurement window (#1028 cadence trigger → machine-enforced via #1080), yet the remediation for P1#13 shipped 38 minutes later was itself another doc-only rule that self-violated immediately and completely. The project re-committed its own headline P0 within the same session. Compounding factors: (a) the ledger gates #1058 SMTP, an explicit NEW-P0-N item carrying "매 사이클 회신 의무" per policy 5, whose delay is undetectable without a date column; (b) repo memory feedback-stale-blocker-policy.md records 4-cycle stale-blocker accumulation as an already-burned failure mode, making recurrence foreseeable rather than hypothetical; (c) the escalation path is cheap and proven — check_retro_cadence.py exists as a working template for a machine counter.

Not escalated to P0: no operational break exists today. The owed items are verification-owed, not known-failing (the #1058 SMTP fix is believed correct, merely unproven), and the append-only ledger is a genuine net improvement over the prior fully-untracked state. Recommended fix: add a date/elapsed column plus a machine counter modeled on check_retro_cadence.py that loud-warns on safety-tier rows aging past one cycle, and wire a ledger check into the CLAUDE.md session-start checklist so the reference graph is no longer circular.

### P1-21. [process] check_dead_code 의 참조 카운트가 이름-전역·비한정 — 봉인 대상이던 find_orphaned 재발을 영구히 못 잡음 (실증)

- **위치**: `scripts/check_dead_code.py:96`
- **주장**: 가드가 '호출자 유무'를 모듈/클래스 한정 없이 이름 문자열로만 판정한다. 따라서 이미 어딘가에서 참조되는 이름을 재사용한 신규 dead 함수는 무조건 통과한다. #1073 이 find_orphaned 를 배선한 순간 그 이름은 영구 화이트리스트가 됐고, 가드는 자기가 만들어진 이유인 바로 그 시나리오를 다시는 탐지하지 못한다.
- **근거**: `scripts/check_dead_code.py:96-102` `_total_references` 가 src/ 전체 rglob 로 `count_ast_references` 합산, 그 안(`:74-79`)은 `ast.Name.id == name` 또는 `ast.Attribute.attr == name` 만 비교 — 정의 모듈·소유 클래스 무관. 실증 probe(격리 worktree, 각각 단독 커밋 후 `python scripts/check_dead_code.py HEAD~1 HEAD`): (A) 고유 이름 `find_totally_orphaned_xyz()` 를 `src/repositories/analysis_repo.py` 에 추가 → **exit 1, 정상 탐지**(긍정 통제 있음). (B) 이미 배선된 이름 `find_orphaned()` 를 `src/repositories/repo_config_repo.py` 에 호출자 0 으로 추가 → **"✅ 신규 공개 함수 1개 모두 src 내 호출자 有" exit 0**. 회고 처방 근거 = 리포트:59-61 (테마 D, "find_orphaned 가 호출자 0 dead code 로 13 PR 생존").
- **권고**: 참조 판정을 이름 전역 매칭에서 **정의 모듈 기준 한정**으로 승격 — 최소안: `ast.Name` 히트는 해당 심볼을 import 한 파일에서만, `ast.Attribute` 히트는 정의 모듈을 import 한 파일에서만 카운트. 회귀 가드로 위 (B) 시나리오(이미 존재하는 이름 재사용 dead 함수)를 명시 테스트에 고정.
- **cross-verify**: CONFIRMED — Citations exact: check_dead_code.py:96-102 (_total_references rglob-sums across all src/) and :74-79 (matches only ast.Name.id==name / ast.Attribute.attr==name, no module/class qualification). Both probes reproduced end-to-end in an isolated worktree with real commits: (A) unique name find_totally_orphaned_xyz() in analysis_repo.py, zero callers -> exit 1, detected (positive control is genuine); (B) already-wired name find_orphaned() re-added to repo_config_repo.py with zero callers (grep -c repo_config_repo.find_orphaned src/ == 0) -> "✅ 신규 공개 함수 1개 모두 src 내 호출자 有", exit 0. Whitelist is permanent: find_orphaned is now truly wired at src/services/cron_service.py:53, so _total_references == 1 forever.

Blast radius is WIDER than the finding argued. Because ast.Attribute.attr matches unqualified, ordinary SQLAlchemy/dict method noise whitelists common CRUD verbs: measured get=561 (from .get()), query=115, filter=76, commit=68, first=53, all=50, count=40, refresh=23, add=21, delete=17, update=10, create=6 — 17 of 21 common names auto-pass. A new `def create(...)`/`def count(...)` in a repo module with zero callers is invisible. Also 8 of 100 public functions already in the scoped dirs share names across modules (create, find_by_id, upsert, save_new), so name reuse in this layer is the norm, not an edge case. tests/unit/scripts/test_check_dead_code.py contains no module-qualification test, so the gap is undocumented and invisible.

CORRECTION to the finding's framing (confirmed despite it): "가드는 자기가 만들어진 이유인 바로 그 시나리오를 다시는 탐지하지 못한다" is overstated — at #1060 time find_orphaned had 0 refs, so this guard WOULD have caught the original incident. The permanent whitelist is a consequence of remediation, not pre-existing blindness.

Severity held at P1 (not downgraded to P2) because: (1) it is exactly the #1094 "guard green while blind" class the session asked about; (2) unlike a silent gap, the guard prints an affirmative all-clear ("모두 src 내 호출자 有") that is factually false, inducing false confidence; (3) it makes the P1#9/14/15 remediation partial rather than complete. Fix direction: qualify the reference count by resolving the defining module/class (skip references that are the definition site, and prefer attribute-owner or import-graph resolution over bare name equality), plus a regression test asserting a reused-but-unwired name is still detected.

### P1-22. [process] 신규 가드 4종에 end-to-end 긍정 통제 0 — 순수 헬퍼만 검증, git glue 결함 시 영구 green (#1094 형 재발 표면)

- **위치**: `tests/unit/hooks/test_posttool_pytest_smoke.py:26`
- **주장**: #1094 의 교훈은 '가드가 무력한데 테스트는 green' 이었는데, 신규 가드 4종의 테스트는 전부 pure function 단위와 CI yaml 텍스트 단언뿐이고, 가드를 실제 위반 diff 에 실행해 exit 1 을 확인하는 테스트가 하나도 없다. main()·_git()·_changed_*_files() 가 전부 미검증이라 pathspec/인자/인코딩 결함이 생기면 '✅ ... 없음' exit 0 으로 영구 green 이 되고 전 스위트는 통과한다 — #1094 와 동일한 실패 모드가 4곳에 복제됐다.
- **근거**: `tests/unit/scripts/test_check_dead_code.py` 16 테스트 = parse_added_public_defs / parse_unwired_ok_names / count_ast_references(:30~108) + CI yaml 배선 단언(:120·127). `tests/unit/scripts/test_check_noqa_sideeffect.py` 14 테스트 = line_hides_f401 / parse_added_noqa_imports / find_violations(:32~101) + yaml·testing.md 단언(:115·123·135). `tests/unit/hooks/test_posttool_pytest_smoke.py` 6 테스트 전부 is_src_file / derive_test_target(:26~61) — `main()`·`_run()` 미검증, 실패 시 ❌ 배너 산출 검증 0. 어떤 파일에도 `subprocess`/`tmp_path` 기반 실제 diff 실행 케이스 없음. 대조군: 스크립트를 실제 실행하는 유일한 테스트 `tests/unit/scripts/test_check_retro_cadence.py:128 test_script_runs_without_crashing` 이 바로 #1094 에서 encoding 누락으로 눈멀어 있던 그 테스트(e256435 가 사후 보강) — 실행 테스트조차 단언이 약하면 무의미함을 이 세션이 이미 실증했다.
- **권고**: 각 가드에 `tmp_path` 기반 미니 git 리포(또는 고정 diff 픽스처)로 **위반 심기 → exit 1 + 위반 라인 리포트 확인** / **정상 → exit 0** 2-케이스 긍정 통제를 의무화. 본 회고의 probe 3종(noqa 3-디렉토리·dead-code 고유이름·dead-code 이름충돌)이 그대로 픽스처가 된다. '가드 신설 PR 은 긍정 통제 테스트 동반' 을 정책 4(단언+가드 페어)의 하위 규칙으로 명문화.
- **cross-verify**: CONFIRMED — CONFIRMED — 회의적으로 접근해 반증을 시도했으나, 주장된 실패 모드를 **두 경로로 실증 재현**했다.

## 1. 인용 재확인 (전건 일치)
- `tests/unit/hooks/test_posttool_pytest_smoke.py:26` 존재 — 파일 전체 6 테스트가 `is_src_file`(:26,:32) / `derive_test_target`(:42,:49,:55,:61) 뿐. import 는 `from posttool_pytest_smoke import derive_test_target, is_src_file` (:20) 단 2 심볼 — `main()`·`_run()` 미임포트=미검증 확정.
- `test_check_dead_code.py` 16 테스트 = 순수(:30~110) + CI yaml(:120,:127). `test_check_noqa_sideeffect.py` 14 테스트 = 순수(:32~103) + yaml(:115,:123) + testing.md(:135). 3 파일 어디에도 `subprocess`/`tmp_path` 실행 케이스 없음 (검증 완료).
- 대조군 주장도 사실: `git log` 상 `e256435 fix(test): cp949 reader 크래시로 눈먼 카덴스 가드 — subprocess encoding 명시` 가 `e23ca38`(#1080) 직후 사후 보강 — 유일한 실행 테스트조차 이 세션에서 눈이 멀어 있었음이 확인됨.

## 2. 실증 (scratch git repo 긍정/부정 통제 직접 수행)
**긍정 통제 — 가드는 현재 정상 작동**: 위반 diff(`+from src.models.user import User  # noqa: F401`, `+def find_orphaned_zzz(db)` 호출자 0) 에 대해 두 가드 모두 exit 1 + 정확한 위반 지목. → **현행 활성 결함은 아님**(오탐 아님을 확인).

**부정 통제 — 예측된 silent-green 재현됨**:
- 무효 base SHA(`deadbeef...`) → `check_noqa_sideeffect` / `check_dead_code` 양쪽 `✅ ... 없음` + **exit 0**
- 인자 없이 실행(`origin/main` 미해결) → `✅ ... 없음` + **exit 0**
- **pathspec drift**: `git mv src/services src/service_layer` 후 호출자 0 공개 함수 추가 → `✅ 신규 dead-code 후보 없음` + **exit 0** (영구 무력화)

근본 = `_git()` 의 `check=False` + `return out.stdout or ""` (check_dead_code.py:82~86, check_noqa_sideeffect.py:76~81) 가 git 실패를 통째로 삼켜 "변경 파일 0" 과 구분 불가. `#1094`(stderr 빈 문자열 → 무조건 통과)와 **동일 구조**.

## 3. 반증 시도 — 부분 감경되나 판정 유지
finding 이 CI yaml 메타 단언을 과소평가한 면은 있다: `test_ci_dead_code_guard_passes_pr_base_sha`(:127)·`test_ci_noqa_guard_passes_pr_base_sha`(:123)가 주석 decoy 제거 후 `base.sha.*HEAD` 정규식으로 배선을 잠그고, 현행 `ci.yml` 은 `fetch-depth: 0` 이라 base SHA 가 오늘은 해결된다. 그러나 이 단언들은 **문자열 존재**만 검증할 뿐 **호출이 실제로 작동하는지**는 검증하지 않는다 — 위 3 시나리오(fetch-depth 축소 같은 흔한 CI 속도 최적화, scoped 디렉토리 리네임, ref 미해결) 중 어느 것도 30 테스트 중 단 1건도 깨뜨리지 못한다. "가드 배선됨"과 "가드 작동함"의 간극이 정확히 #1094 가 남긴 교훈이다.

## 4. 심각도 P1 유지
- 활성 결함이 아니라 **탐지기 없는 잠복 실명**이므로 P0 아님.
- P2 로 낮추지 않는 이유: (a) 실패 경로가 이론이 아니라 재현됨 (b) 4 가드는 "인지 의존 → 기계 신호 전환"이 존재 이유이므로 무음 실명은 목적 자체를 무효화 (c) 본 세션 메모리가 `advisory=P0 무시 재현`으로 가드 무결성을 고심각도로 취급한 전례 (d) 동일 실패 모드가 3 가드에 복제됨 (e) 수리 비용이 낮음 — `tmp_path` git repo 에 위반 커밋 심고 exit 1 단언하는 테스트 가드당 1건(+ `_git()` 에 rc 검사 loud-fail), `test_check_retro_cadence.py:128` 의 subprocess 선례 재사용 가능.

권장 remediation: 가드당 (1) 위반 diff → exit 1 긍정 통제 (2) 정상 diff → exit 0 부정 통제 (3) `_git()` rc≠0 시 무음 통과 금지(loud-fail). posttool 훅은 stdin JSON → 배너 산출 계약 테스트(`main()` 호출).

### P1-23. [process] PostToolUse 스모크 훅의 ❌ 신호가 Claude 에게 도달하지 않는 경로 — false-green 을 false-invisible 로 이동시켰을 가능성

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:101`
- **주장**: #1082 는 훅이 완주하도록 스코프를 줄여 false-green 을 봉인했지만, 실패 신호 전달 경로는 bare print + exit 0 그대로다. PostToolUse 훅은 exit 0 일 때 stdout 이 transcript 전용이라 모델 컨텍스트에 들어가지 않는다. 그러면 CLAUDE.md 필수 원칙의 "❌ 배너 시 즉시 조사" 가 성립하지 않는다 — 완주는 하지만 소비자가 못 읽는 신호가 된다.
- **근거**: `.claude/hooks/posttool_pytest_smoke.py:101-105` = `banner = "✅ ..." if rc == 0 else (...)` → `print(f"{banner} ...")` → `return 0` (:105 주석 "비차단 advisory"). 같은 저장소의 다른 훅은 구조화 출력을 씀: `.claude/hooks/doc_review_gate.py:311-318` `{"hookSpecificOutput": {"hookEventName": ..., "permissionDecision": "deny", "permissionDecisionReason": ...}}` — 저장소가 모델 도달용 채널을 이미 알고 사용 중이다. 배너 도달을 검증하는 테스트 0(위 P1 항목 참조). 소비 측 문언 = CLAUDE.md 필수 원칙 "❌ 배너 시 즉시 조사".
- **권고**: 실패 시에만 `hookSpecificOutput.additionalContext`(또는 exit 2 + stderr)로 승격해 모델 컨텍스트 도달을 보장하고, ✅ 는 현행 조용한 print 유지(소음 0). 도달 경로를 실측 확인한 뒤 CLAUDE.md 필수 원칙 문언을 실제 동작에 맞춰 확정 — 실측 없이 문언만 유지하면 '가드 신뢰' 단언이 다시 근거 없는 상태가 된다(테마 F 와 동형).
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인. posttool_pytest_smoke.py:101-105 = `banner = "✅..." if rc == 0 else (... "❌ 스모크 실패")` → `print(f"{banner} ...")` → `return 0` (:105 "비차단 advisory"). doc_review_gate.py:311-318 구조화 출력 실재. 소비 측 문언 = CLAUDE.md:352 "❌ 배너 시 즉시 조사".

기술 전제 성립: Claude Code 에서 exit-0 stdout 이 모델 컨텍스트에 들어가는 이벤트는 UserPromptSubmit / SessionStart 2종뿐. PostToolUse 는 미포함 — exit 0 시 stdout 은 transcript 전용(Ctrl-R). PostToolUse 의 모델 도달 채널은 exit 2(stderr) 또는 JSON `hookSpecificOutput.additionalContext` 인데 훅은 둘 다 미사용. settings.json 확인 결과 output 라우팅 없는 bare command 로 배선. 배너 문자열 grep 전수 = 발화 1곳뿐, 소비처 0(로그/래퍼/테스트 전무).

테스트 갭은 주장보다 큼: test_posttool_pytest_smoke.py 는 is_src_file / derive_test_target 순수함수만 검증 — main() 전체가 미커버(배너 도달은 물론 배너 생성조차 미검증).

반증 3건 시도·기각: (1) "advisory 설계라 비가시성 의도" — 기각. advisory = 비차단이며 additionalContext 도 비차단. CLAUDE.md:352 가 행동 주체를 Claude 로 명시하므로 Claude-소비가 설계 의도. 코드와 계약이 모순. (2) "transcript 로 사용자가 봄" — 기각. Ctrl-R opt-in 이라 편집마다 관찰 안 함, 문서상 행위자는 Claude. (3) "push-time 전체 게이트 백스톱" — 심각도 완화 요인이나 반증 아님. 결함 유출은 막지만 조기탐지 가치는 0.

정정 1건: doc_review_gate.py:314 `permissionDecision` 은 PreToolUse 전용 필드라 그대로 복사 불가 — 올바른 수정은 `hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ...}` 또는 exit 2 + stderr. 핵심 논지(저장소가 구조화 채널을 이미 인지·사용) 는 유지.

심각도 P1 유지(P2 강등 기각): 본 세션 중심 테마(#1094 형 — 가드가 설치·실행·green 이나 구조적으로 눈이 멂)가 #1082 신작에서 재현. #1082 는 false-green 의 '완주' 절반만 봉인하고 '소비자 도달' 절반을 남겨 remediation 부분조치이며, CLAUDE.md:352 는 현재 실행 불가능한 운영 절차를 단언 중 — 본 세션 P0(#1080)를 낳은 "문서-only 정책이 기계에 미배선" 패턴과 동형. push-time 백스톱에도 불구, 훅의 선언된 가치(조기 실패 탐지) 가 현재 사실상 0 이면서 정상 작동으로 보이므로 P1.

구체적 실패 시나리오: Claude 가 src/gate/engine.py 편집 → 스코프 스모크 rc=1 → "❌ 스모크 실패" + tail 출력 → exit 0 이라 transcript 에만 적재 → Claude 미인지 → 깨진 기반 위에서 N 턴 추가 편집 → push-time 전체 게이트에서야 발현, 수 턴 분량 작업 되감기.

### P1-24. [process] 카덴스 카운터가 SessionStart 훅 미배선 — 기계 신호를 다시 doc-only 지시로 호출

- **위치**: `.claude/settings.json:20`
- **주장**: P0 의 근본은 '인지 의존' 이었는데, 그 해법인 기계 카운터의 **실행 자체**가 여전히 CLAUDE.md 체크리스트를 Claude 가 읽고 기억해 수동 실행하는 데 의존한다. 계측은 기계화됐지만 트리거는 문서-only 그대로라 한 단계 못 갔다.
- **근거**: `CLAUDE.md:320` = 체크리스트 코드블록 내 `python scripts/check_retro_cadence.py  # 🔴 회고 카덴스 기계 카운터` — 실행 주체는 Claude. `.claude/settings.json` 전문에 훅 이벤트는 `PreToolUse`(:3)·`PostToolUse`(:20) 뿐, **SessionStart 없음**. 즉 세션 시작 시 자동 발화 경로 0. (본 세션에서 수동 실행 시 정상 발화 확인: "🔴 ... 머지 PR 15 건 (임계 ≥15)" — 계측 로직 자체는 건전.)
- **권고**: `SessionStart` 훅으로 `python scripts/check_retro_cadence.py` 배선(advisory·exit 0 이라 차단 위험 0, 정책 17 안정성 충족). 같은 훅에 P0 항목의 owed-원장 카운터를 함께 태우면 세션 시작 시 카덴스+미결검증 2 신호가 자동 노출된다.
- **cross-verify**: SEVERITY_ADJUST — 사실관계 전량 확인. `.claude/settings.json` 전문 33줄에 훅 이벤트는 `PreToolUse`(:3)·`PostToolUse`(:20, 인용 line 정확) 뿐 — `SessionStart` 없음. 전역 `~/.claude/settings.json` 은 `hooks` 키 자체가 부재라 상속 경로도 0. `CLAUDE.md:320` 호출 확인. 비-문서 호출 경로 전수 조사(.github/, Makefile, .pre-commit-config.yaml, .git/hooks/) 결과 **전무** — CLAUDE.md 체크리스트 bash 블록이 유일 진입점. 즉 계측은 기계화됐으나 트리거는 Claude 의 문서 독해·기억 의존 그대로라는 주장은 정확하다. 제안 해법도 가상이 아니다: `SessionStart` 는 지원 이벤트(plugin-dev README 전체 이벤트 목록에 명시)이며 본 머신에 설치된 awesome-statusline 플러그인이 이미 SessionStart 훅을 사용 중.

🔴 finder 가 인용하지 않은 가중 증거 발견 — `tests/unit/scripts/test_check_retro_cadence.py:150-159` `test_checklist_wires_the_counter` 는 `"check_retro_cadence.py" in claude_md` 문자열 존재만 단언한다. docstring 은 "문서-only 재발 방지" 를 표방하나 이 테스트의 '배선' 정의가 곧 '마크다운에 문자열이 있음' 이다. 두 번 실패한 바로 그 메커니즘을 green 으로 인증하는 가드 = 본 회고가 지목한 "#1094 형(가드가 무력한데 green)" 패턴의 정확한 재현. 단순 갭이 아니라 갭 + 허위 양성 신호.

심각도 상향 근거: 본 저장소 자체 선례가 P2 를 배제한다 — 동일 실패의 직전 인스턴스를 2026-07-18 회고가 **P0**("회고 카덴스 강제 트리거 첫 측정창 자기위반")로 등급했다. 그 P0 의 시정이 동일한 인지-의존 차원을 남긴 부분 조치라면 P2 로 내려앉을 수 없다. P0 은 아님 — 계측은 실제로 기계화됐고 체크리스트 bash 블록은 #1028 의 매몰된 정책 8 진화 산문보다 현저히 높은 salience 라 잔여 위험이 실질 감소했다. 본 저장소 문서-only 시정의 실증 실패율은 2/2 이며, 이번 세션 1회 정상 발화는 사고 직후 salience 최대 시점의 n=1 이라 지속성 증거로는 최약. → P1.

### P1-25. [decision] owed 원장이 '기록만' 하는 장치로 확정 — 테마 G 조치의 전달 절반이 미구현, 안전등급 2건이 원장 자체 규칙(정책 5 NEW-P0-N)을 위반한 채 세션 종료

- **위치**: `docs/runbooks/owed-verification.md:11`
- **주장**: 회고 테마 G의 조치는 두 부분이었다 — (a) 원장 파일 신설 (b) **trailing sync PR body 에 §owed-verification 표 상시 배치**. (a)만 #1084로 이행되고 (b)는 이행되지 않았다. 세션의 두 trailing sync PR 본문 어디에도 owed 표가 없다. 그 결과 머지 완료된 6건의 운영 검증이 사용자 눈에 한 번도 제시되지 않은 채 세션이 종료됐고, 원장 스스로 '다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N' 로 분류한 #1058·#1062 가 미회신 상태로 다음 세션(현재)에 진입했다. 즉 원장은 회신을 유도하는 메커니즘이 아니라 Claude 만 읽는 기록부다.
- **근거**: docs/runbooks/owed-verification.md:11 헤더가 '🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)' 명시, :15(#1058)·:16(#1062) 상태 ⏳. :5 작성 규칙이 'trailing sync PR body 의 §owed-verification 표와 페어' 를 명문화. 그러나 `gh pr view 1093 --json body` = 세션 최종 sync PR 본문의 §'🔍 사용자 검증 필요' 전문이 '문서/배지만 — 코드 영향 0. 이 세션 최종 sync (17 PR #1077~#1092 반영).' 뿐 — owed 표 부재. `gh pr view 1087` 도 동일('문서/배지만 — 코드 동작 영향 0. README EN/KO parity + STATE 수치 정합 확인.'). 6건 전부 머지 완료 실측: #1058 MERGED 2026-07-17T05:42Z · #1062 2026-07-17T14:36Z · #1071 18:12Z · #1072 18:15Z · #1073 19:41Z · #1075 2026-07-18T02:08Z. #1058 은 '출시 이래 100% 실패' 하던 SMTP 경로 수정이 운영 배포된 상태로 실발송 미확인. 메모리 feedback-stale-blocker-policy.md('머지 대기 4사이클 누적 금지, Policy 5 예외')와 정면 충돌.
- **권고**: (a) 원장을 세션시작 체크리스트에 배선 — `check_retro_cadence.py` 옆에 ⏳ 행 카운트를 출력하는 기계 신호 추가(안전등급 ⏳ 존재 시 loud). 문서-only 의무가 2회 실패한 클래스를 원장이 3번째로 반복하고 있음. (b) trailing sync PR 템플릿에 §owed-verification 표를 강제 — 원장 파일이 ⏳ 행을 가지면 sync PR body 생성 시 표 삽입을 필수화. (c) 이번 세션 최우선으로 #1058·#1062 회신 요청을 사용자에게 명시 제시(정책 5 NEW-P0-N 은 정책 9 완화 미적용 영역).
- **cross-verify**: SEVERITY_ADJUST — 핵심 사실은 전부 실측 확인됨 — 그러나 P0 등급을 떠받치는 결과 서술 2건이 반증되어 P1 로 조정.

**검증된 부분 (인용 전건 일치)**
- `docs/runbooks/owed-verification.md:5` = "trailing sync PR body 의 §owed-verification 표와 페어" 명문 · `:11` = "🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)" · `:15`(#1058)·`:16`(#1062) 상태 `⏳` — 전부 축자 일치.
- 🔴 **claimant 보다 강한 증거 발견**: 회고 보고서 `docs/_archive/reports/2026-07-18-retrospective.md:73` 테마 G 의 **조치 원문 = "trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치"** — 즉 (b) 는 claimant 의 해석이 아니라 **처방된 조치 그 자체**이고, 원장 파일(#1084) 은 처방에 없던 **대체물**이다. 처방 미이행 + 대체물을 fix 로 선언 = remediation 완결성 결함 성립.
- PR body 실측: #1093 §"🔍 사용자 검증 필요" 전문 = "문서/배지만 — 코드 영향 0. 이 세션 최종 sync (17 PR #1077~#1092 반영)." / #1087 = "문서/배지만 — 코드 동작 영향 0. README EN/KO parity + STATE 수치 정합 확인." — **양쪽 모두 owed 표 부재**. #1084(05:38) 머지 후 #1087(06:15)·#1093(09:32) 이 이어졌으므로 페어 규칙은 두 건 모두에 발효 중이었다.
- 6건 머지 시각 전건 일치(#1058 07-17T05:42 … #1075 07-18T02:08).
- **기계 강제 0 확인**: `grep -rn "owed-verification" --include=*.py --include=*.mjs --include=*.yml --include=*.json .` = **0 hit**. 원장은 스크립트·훅·CI 어디에도 배선되지 않은 순수 문서. "회신을 유도하는 메커니즘이 아니라 기록부" 라는 결론은 **정확**하다.

**P0 를 못 받는 이유 (반증 2건)**
1. "머지 완료된 6건이 사용자 눈에 한 번도 제시되지 않은 채 세션 종료" = **반증**. (a) #1088 body §"🔍 사용자 검증 필요" 가 "#1058 검증 시 위 detail 대로 리포 Email 설정 + SMTP env 확인 후 발송 테스트" 로 #1058 을 절차까지 제시(사용자 질문에 대한 응답으로 생성, 최종 sync 이전 08:11 머지). (b) `docs/cycle-history.md:160` 이 "**보류(사용자 결정)**: owed 회신(#1058 SMTP/#1062 IDOR)" 로 미결 상태를 사용자 가시 문서에 기록. (c) #1071~#1075 는 각 origin PR body 에 자기 검증 항목을 이미 실었다 — 테마 G 의 원 불만은 "최초 미공개" 가 아니라 "**wave 종료 시 단일 표로 미취합**" 이다. 결손된 것은 최초 전달이 아니라 **취합·회신 유도**이며, 이는 P0 가 아니라 P1 규모다.
2. "메모리 `feedback-stale-blocker-policy.md`(머지 대기 4사이클 누적 금지)와 정면 충돌" = **과장**. 원장 생성(07-18 05:38) 후 경과는 **1 사이클**(당일 다음 세션). 해당 메모리 자체의 임계가 4사이클인데 1사이클 경과를 임계 위반으로 제시한 것은 근거 초과.

**추가 감쇠 근거**: 회고 자신이 `:110` 에서 "⑥ owed 검증 회신(안전등급)" 을 6개 트랙 중 **최하위 우선순위**로 배정했다. 원 finding 은 **P1#13**. 새 운영 피해 증거 없이 "P1 의 부분 조치" 를 P0 로 승격하는 것은 등급 인플레다. 실제 운영 리스크도 6건 균질하지 않다 — #1058 은 최악값이 "수정 전과 동일한 실패"(회귀 없음), 실질 리스크는 **#1062 과잉차단 1건**에 집중된다.

**P1 로 존치하는 실질**: 처방된 조치 (b) 미이행 + 기계 배선 0 = 이 세션이 P0(카덴스 문서-only 자기위반)를 기계화하면서 **동시에 또 하나의 문서-only 의무를 신설하고 첫 측정창에서 자기위반**했다는 구조가 성립한다. 조치 방향은 원장 파일 보강이 아니라 **sync PR body 표 생성의 기계화**(예: `check_owed_ledger.py` — 미결 ⏳ 행 존재 시 trailing sync PR body 에 §owed-verification 표 부재를 loud-fail, #1080 카덴스 카운터와 동형)여야 한다. 문서 규칙을 한 번 더 쓰는 처방은 이미 2회 실패한 패턴이다.

### P1-26. [decision] P1 테마 E·F 가 조치 문안까지 확정된 채 무기록 소멸 — 같은 회고의 P2 한 건은 명시 보류 기록됨(traceability 비대칭)

- **위치**: `docs/_archive/reports/2026-07-18-retrospective.md:63`
- **주장**: 회고가 확정한 7개 P1 테마 중 A/B/C/D/G 5개는 PR 로 이행됐으나, **테마 E(비대칭 가드 의미적 대칭 축)와 테마 F(미검증 전제 waiver 금지)는 PR·정책 문서·보류 기록 어디에도 흔적이 없다.** 두 테마 모두 회고에 '조치' 문안이 구체적으로 확정돼 있었고 둘 다 정책 문서 1줄 수정이면 끝나는 항목이다. 반면 우선순위가 낮은 P2#16 은 STATE.md 에 '보류' 로 명시 기록됐다. 즉 기록 규율이 심각도와 역상관 — 사용자가 트랙을 선택해 제외한 것인지, Claude 가 누락한 것인지 **사후 판별이 불가능**하다. 이것이 정책 3(자율 판단 사후 보고)이 막으려던 상태 그 자체다. 테마 F 가 '결정 규율' 테마라는 점에서 자기지시적 실패다.
- **근거**: docs/_archive/reports/2026-07-18-retrospective.md:63-65 테마 E 조치='신뢰경계(merge↔approve↔review) 결속 시 같은 경계를 넘는 모든 액션을 같은 PR 에서 열거하는 규율을 grep-전수에 의미적 대칭 축으로 추가'. :67-69 테마 F 조치='"~일 것이다/~없다" 단언은 호출부/외부계약 확인 후에만 확정 — 보안/데이터-접근 PR High-tier'. 실측: `grep -n "신뢰경계|의미적 대칭|probe-before-waive|미검증 전제" CLAUDE.md .claude/policies/active.md .claude/policies/history.md .claude/rules/*.md` → **0 hit**. `git log --since=2026-07-17 -- .claude/policies/ CLAUDE.md` → #1080·#1082·#1088 뿐(A·C·자성 후속만). 대조군: docs/STATE.md:17 '🔴 owed 회신(#1058 SMTP·#1062 IDOR) · **보류(P2#16 claude_api_calls GC 보존기간 결정)**' — P2 는 보류 기록, P1 2건은 무기록. 회고 :110 이 'fix = 사용자 결정 / 트랙별 옵션 표로 상정' 이라 선택 자체는 정당하나, 선택 결과의 기록이 없어 검증 불가.
- **권고**: 회고 finding → 이행/보류 매핑을 STATE.md 에 전건 원장화(테마 단위 ✅/보류+사유 1줄). 미이행 P0/P1 은 owed 원장과 동일 append-only 취급. 테마 E·F 는 정책 문서 1줄 수정 비용이므로 이번 세션에서 즉시 이행하거나 명시 보류 사유를 기록할 것. 회고 워크플로우 산출물에 'finding 미배정' 검출을 넣는 방안 검토(2026-07-03 세션에서 이미 '회고 finding 미배정 6건' 이 외부 검증으로 적발된 전례 있음 — 동일 결함 재발).
- **cross-verify**: CONFIRMED — 인용 정확 + 반대가설 반증 + 손실 메커니즘 특정. 회의적 재검증 결과 주장이 전부 성립하며, 오히려 근거가 원 주장보다 강해졌다.

**1) 인용 실측 일치** — :63 `### 테마 E — 비대칭 가드(only-one-side-guarded) turn-0 미차단 (P1#1)`, :65 조치='신뢰경계(merge↔approve↔review)…의미적 대칭 축으로 추가', :67 `### 테마 F — 결정 규율: 미검증 전제를 waiver·배제 근거로 단정 (P1#3)`, :69 조치='"~일 것이다/~없다" 단언은 호출부/외부계약 확인 후에만 확정'. 주장의 :63-65/:67-69 와 정확히 일치.

**2) 무기록 재확인** — `grep -rn "신뢰경계|의미적 대칭|미검증 전제|probe-before-waive" CLAUDE.md .claude/policies/ .claude/rules/ docs/cycle-history.md docs/runbooks/owed-verification.md` → **0 hit**. `git log --since=2026-07-17 -- .claude/policies/ CLAUDE.md .claude/rules/` → #1080·#1081·#1082·#1085·#1088 뿐이며 diff 에 E/F 문안 없음. STATE.md:10~18 세션 블록은 A1/A2/B1/B2/C/D/P2#41/후속 5건을 개별 열거하면서 E·F 는 언급 0.

**3) 대조군 성립** — docs/STATE.md:17 `🔴 owed 회신(#1058 SMTP·#1062 IDOR) · 보류(P2#16 claude_api_calls GC 보존기간 결정)`. P2 는 보류 명시, P1 2건은 무기록 — 기록 규율의 심각도 역상관 확인.

**4) 🔴 신규 — "사용자가 트랙 미선택" 방어 반증 + 손실 지점 특정.** 최유력 반대가설(사용자가 옵션 표에서 E/F 를 제외 → 정당한 선택)은 성립하지 않는다. 회고 :110 후속 문단이 fix 처분을 '트랙별 옵션 표로 사용자에게 상정'으로 라우팅하는데, **그 추천 우선순위 목록 자체가 6개(① 카덴스/A → ② CodeQL/B → ③ Hook/C → ④ dead-code·parity/D → ⑤ docs drift → ⑥ owed 검증/G)이고 E·F 가 없다.** 즉 사용자는 E/F 를 제시받은 적이 없어 **제외할 수조차 없었다.** 소실은 사후 미기록 결정이 아니라 **회고 문서 내부의 handoff 경계(body→후속 요약)에서 발생**했다 — 재현 가능한 구조적 결함.

**5) 🔴 신규 — 독립 2차 drift 아티팩트.** :45 헤더 `## P1 — 6 테마 (15 confirmed)` 인데 본문은 A~G **7 테마**. 15 confirmed 는 7 테마 전부 필요(A=P1#2·5·11·12, B=#4·6·8·10, C=#7, D=#9·14·15, G=#13 → 13건 / +E=#1 +F=#3 → 15). 헤더가 정확히 1 테마 과소 카운트 = 요약 계층이 이미 축소된 테마 집합으로 작동 중이었다는 두 번째 독립 증거. :110 의 6-트랙 목록과 정확히 동일한 축소폭.

**6) '이미 해소' 반증** — 실질 커버 없음. 테마 E: CLAUDE.md:275 정책 16 진화는 '같은 값/로직이 2+곳' 에 대한 **심볼 기반** `grep -rn <심볼>` 로, E 가 명시적으로 "심볼은 전수하나 취약점 클래스는 못 잡는다"며 요구한 **의미적/신뢰경계 축**은 미도입. 테마 F: 유일 근접 문안이 active.md:203-204(정책 14 CodeQL alert dismiss 한정)로 보안/데이터-접근 PR waiver·배제 단정 규율은 미커버.

**심각도 P1 유지(하향 부적절)**: (a) P1 remediation 7 테마 중 2건(29%) 소실, (b) 테마 E 는 실제 보안 결함 이력에서 도출 — #1057 auto-merge SHA 결속이 형제 approve 경로 미결속 → 한 세션 뒤 #1072 사후 수정 — 미도입 시 동일 클래스 재발이 보증되며 본 세션 #1094(관용구 복사 드리프트)가 같은 형태로 재현, (c) 자기지시적 실패 — '결정 규율' 테마 F 자체가 무기록 소멸. 런타임 무영향이나 재발 보증성과 자기지시성이 P2 로 하향할 근거를 상쇄한다.

### P1-27. [process] 회고 카덴스 P0 시정이 **측정만** 기계화 — 호출은 여전히 문서-only, 훅 미배선(가드의 수용 기준이 'CLAUDE.md 에 문자열 존재')

- **위치**: `.claude/settings.json:20`
- **주장**: P0 근본은 '문서-only 트리거가 인지 의존이라 두 번 실패' 였는데, #1080 의 시정은 카운터 로직만 기계화하고 **카운터를 실행시키는 계층은 그대로 문서**로 남겼다. `.claude/settings.json` 에 SessionStart 훅이 없고, 유일한 배선점은 CLAUDE.md 체크리스트 한 줄이다. 즉 '회고를 기억해야 함' 이 '카운터 실행을 기억해야 함' 으로 한 단계 이동했을 뿐 실패 계열이 동일하다.
- **근거**: .claude/settings.json:2-32 — 훅은 PreToolUse(check_edit_allowed·doc_review_gate) + PostToolUse(posttool_pytest_smoke) **2종뿐**, SessionStart 없음. `grep -rn "SessionStart|check_retro_cadence" .claude/ CLAUDE.md` → 매치는 CLAUDE.md:320·326 **문서 2곳뿐**, 훅/CI 배선 0. 가드 자신의 테스트가 이 한계를 명문화한다: tests/unit/scripts/test_check_retro_cadence.py:150 `test_checklist_wires_the_counter()` 의 단언이 `assert "check_retro_cadence.py" in claude_md` — 즉 **수용 기준 = 마크다운에 문자열이 있는가**. 같은 테스트 docstring 이 '스크립트만 있고 체크리스트 미배선이면 다시 인지 의존' 이라고 스스로 진단하면서도, 배선의 종착점을 문서로 삼았다.
- **권고**: `.claude/settings.json` 에 SessionStart 훅으로 `python scripts/check_retro_cadence.py` 등록(비차단 advisory 유지 — 정책 17 안정성 부합). 그러면 CLAUDE.md 체크리스트는 백업 설명이 되고 배너가 무조건 세션 로그에 남는다. test_checklist_wires_the_counter 단언도 settings.json 배선 검사로 승격.
- **cross-verify**: CONFIRMED — All cited evidence verified exactly. (1) .claude/settings.json:2-32 contains only PreToolUse (check_edit_allowed, doc_review_gate) + PostToolUse (posttool_pytest_smoke) — no SessionStart. (2) Repo-wide grep for "SessionStart|check_retro_cadence" yields CLAUDE.md:320/326, docs/STATE.md, docs/cycle-history.md, the test file, and the script itself — zero hook wiring. (3) .github/ wiring count = 0; .pre-commit-config.yaml wiring count = 0. (4) tests/unit/scripts/test_check_retro_cadence.py:157 asserts `"check_retro_cadence.py" in claude_md` verbatim.

TWO ADDITIONAL EVIDENCE ITEMS THAT STRENGTHEN THE FINDING BEYOND ITS ORIGINAL FORM:

(A) Batch asymmetry — .github/workflows/ci.yml:102 wires check_noqa_sideeffect.py and ci.yml:109 wires check_dead_code.py. The #1081/#1083 siblings from the SAME remediation batch both received machine enforcement; only #1080 terminates in prose. It is the outlier within its own cohort, which defeats any "cadence is inherently unwireable" defense.

(B) The guard is blind in the #1094 class the retrospective is hunting — test_checklist_wires_the_counter's docstring claims it verifies the call exists "체크리스트 bash 블록에", but the assertion is an UNSCOPED whole-file substring match. CLAUDE.md:320 is the real bash-block invocation; CLAUDE.md:326 is a separate prose paragraph naming the same file. Deleting line 320 (the actual wiring) leaves the guard GREEN via line 326. The guard does not protect what it claims to protect — a concrete positive-control gap, not a theoretical one.

TEMPERING (severity held, not raised): the finding's claim that the failure class is IDENTICAL ("실패 계열이 동일") is overstated. Relocating the trigger into the already-ritualized turn-0 30-second checklist collapses "remember policy exists → manually count merged PRs since date → compare to threshold" into a single command in an established list — a genuine reduction in recall burden, not a pure lateral move. However this mitigates severity rather than refuting the defect: STATE.md's "라이브 48→5 리셋 실측" evidences one execution, in the authoring session itself, which is not evidence of durable habitual invocation.

Held at P1 rather than downgraded to P2: the remediation sits one deleted line away from silent regression with a fully green suite, the failure class has already recurred twice (2026-07-03 신설 → 2026-07-18 ~46 PR 자기위반), and SessionStart is an available Claude Code hook event — the correct enforcement venue exists and is simply unused. Not a duplicate of pre-identified learning #1, which covers the ORIGINAL document-only failure; this is the next-order claim that the remediation for it is itself incomplete, squarely within the session's "가드의 가드" and "remediation 완결성" questions.

Suggested fix: wire scripts/check_retro_cadence.py to a SessionStart hook in .claude/settings.json, and tighten the test to assert the invocation appears inside the checklist bash fence (parse between the ```bash fence markers) rather than anywhere in the document.

### P1-28. [docs] owed-verification.md 원장이 CLAUDE.md 집행면(세션시작 체크리스트·완료 6-step) 어디에도 배선되지 않음 — 기록 전용

- **위치**: `CLAUDE.md:354`
- **주장**: #1084 원장은 '세션/Phase 종료 시 추가한다'를 문서 본문에만 규정하고, 실제로 매 사이클 읽히는 두 집행면(CLAUDE.md 작업시작 체크리스트, 완료 6-step ①~⑥) 어느 쪽에도 등장하지 않는다. 원장은 회신을 '유도'하지 않고 기록만 한다 — 6행 전부 ⏳ 로 누적됐고 그중 2건은 정책 5 NEW-P0-N '매 사이클 회신 의무' 등급인데도 2세션 이상 무회신으로 생존 중이다. 이는 #1080 이 봉인하려던 문서-only 트리거 실패 모드의 동형 재생산이다.
- **근거**: `grep -n "owed" CLAUDE.md` → rc=1 (0 hit). CLAUDE.md:310~325 체크리스트 = gh run list / code-scanning / 메모리 grep / check_retro_cadence.py / git status / checkout -b (원장 없음). CLAUDE.md:354 완료 6-step = ⑤ STATE.md+cycle-history, ⑥ architecture.md (원장 없음). 원장의 자기 규정은 docs/runbooks/owed-verification.md:5 '세션/Phase 종료 시 … 이 표에 추가한다'. 외부 참조는 docs/runbooks/operational-smoke-checks.md:6 단 1곳(의무 열람 대상 아님). 현재 상태 = 안전등급 2행(#1058 SMTP·#1062 IDOR) + 운영등급 4행(#1071·#1072·#1073·#1075) 전부 ⏳.
- **권고**: CLAUDE.md 작업시작 체크리스트에 1줄 추가(`grep -c '⏳' docs/runbooks/owed-verification.md` → >0 시 안전등급 행 회신 요청 의무) + 6-step ⑤ 를 'STATE.md 수치 + cycle-history + owed 원장 갱신'으로 확장. 안전등급(NEW-P0-N) 행은 check_retro_cadence.py 처럼 세션시작 loud 배너로 승격하면 정책 5 페어가 기계 신호가 된다.
- **cross-verify**: CONFIRMED — 모든 인용 실측 재확인. `grep -n "owed" CLAUDE.md` → rc=1 (0 hit); 한국어 용어 스윕(`원장|미결|verification.md`) 도 rc=1 — 어떤 명칭으로도 0 참조. CLAUDE.md:354 = 6-step (⑤ STATE+cycle-history, ⑥ architecture.md — 원장 없음), CLAUDE.md:310~325 체크리스트 = gh run list/code-scanning/메모리 grep/check_retro_cadence.py/git status/checkout -b (원장 없음). 원장 자기규정 owed-verification.md:5, 유일 외부참조 operational-smoke-checks.md:6 모두 확인.

반증 시도 2건 모두 실패: (1) 기계 집행 존재 여부 — `.claude/settings.json`·`scripts/` 의 "owed" 히트는 전부 **all-owed 부분문자열 오탐**(check_edit_allowed.py, 영문 주석 "indentation allowed"). 원장을 읽는 스크립트·훅 0건. `git show` 결과 #1084 는 docs 2파일(+35줄)만 변경. (2) operational-smoke-checks.md 가 의무 열람면인가 — 아님. CLAUDE.md:335 는 "§9 (정책 14)" 로 **조건부·섹션 한정** 포인터이고, 원장 cross-ref 는 line 6(헤더)로 그 경로 밖.

finding 이 제시하지 않은 더 강한 증거 발견 — 이는 단순 미배선이 아니라 **부분 조치**다. 회고 P1#13 의 처방(2026-07-18-retrospective.md:73)은 "trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 **상시 배치**" 로, 6-step ⑤ 산출물을 겨냥했다. #1084 는 원장 파일만 만들고 trailing-sync-PR 관행에 표를 배선하지 않았다. 그리고 이 페어링은 **첫 적용 기회에서 이미 실패**했다 — `gh pr view` 결과 원장 신설 이후 머지된 trailing sync PR #1093 에 owed 섹션 없음(#1087·#1085 도 동일). 즉 원장이 일방 선언한 페어링을 집행면이 모른다.

과대 표현 1건 지적(등급 미조정): "6행 전부 ⏳ 로 누적" 은 원장이 1일차라 decay 증거로 약하다. 다만 구조적 주장(0 배선)은 경과일과 무관하게 성립하고 #1093 실증 실패만으로 결론이 선다.

P1 유지(조정 없음). P0 아님 — 원장 실재·내용 건전·운영 파손 없음. P2 초과 — 추적 행에 정책 5 NEW-P0-N 매 사이클 회신 의무 등급 2건 포함, 특히 #1058 은 출시 이래 100% 실패한 이메일 채널의 복구가 미증명 상태. 결정적으로 본 프로젝트는 문서-only 트리거 실패 전례가 확립돼 있다(카덴스 트리거 2026-07-03 → 2026-07-18 2회 실패, 2회차는 직전 회고 P0). 그 패턴을 봉인한 직후 동형 재생산이므로 P1 타당.

권고 조치: CLAUDE.md 6-step ⑤ 본문에 "trailing sync PR body §owed-verification 표 첨부" 1줄 추가(회고 처방 완결) + 안전등급 행 잔존 시 세션시작 체크리스트에 loud 카운터(check_retro_cadence.py 선례대로 기계 신호 승격) 검토.

### P1-29. [docs] 회고 P2#42 문서 산출물이 무음 누락 — 미조치 finding 을 추적하는 원장이 없음

- **위치**: `.claude/rules/testing.md:30`
- **주장**: 회고 P2#41·42 클러스터는 산출물 2개(파생 parity 테스트 + testing.md 에 'mutation-green ≠ wiring-verified' 명시)를 지목했는데, #1086 이 앞의 것만 구현하고 뒤의 문서 산출물은 어디에도 착지하지 않았다. 더 중요한 구조 문제는 이것이 '선언 후 부분 조치'로 감지되지 않았다는 점이다 — 61 confirmed 중 약 12건만 PR 로 조치됐고, 미조치 항목을 열거하는 원장은 존재하지 않는다(STATE 에 기록된 유일한 보류는 P2#16 1건).
- **근거**: docs/_archive/reports/2026-07-18-retrospective.md:89 = '| **route→service parity** | P2#41·42 | … 단일 parametrized parity 테스트. "mutation-green ≠ wiring-verified" testing.md 명시. |'. 실측: `grep -n "mutation-green|wiring-verified|배선 검증|mutation" .claude/rules/testing.md` → rc=1 (0 hit). 저장소 전역 `grep -rn "mutation-green" --include=*.md` → 회고 보고서 자신(:60, :89) 2곳뿐. 조치 선언측 docs/cycle-history.md:156 은 'P2#41(#1086)' 만 명명 — #42 는 언급조차 없음(허위 선언은 아니나 소실). 미조치 추적: docs/STATE.md:17 에 '보류(P2#16 claude_api_calls GC 보존기간 결정)' 1건만 기재.
- **권고**: owed-verification.md 와 같은 형식으로 '미조치 회고 finding 원장'(finding ID | 클러스터 | 조치 PR 또는 보류 사유 | 상태)을 회고 보고서 말미 또는 별도 runbook 에 두고, 회고 종료 PR 에서 confirmed 전건을 조치/보류/기각 중 하나로 반드시 분류한다. 우선 .claude/rules/testing.md 에 'service mutation-green ≠ route 배선 검증' 1줄을 추가해 P2#42 를 종결한다.
- **cross-verify**: CONFIRMED — 전 인용 실측 확인. retrospective.md:89 원문 일치(산출물 2종 선언) · .claude/rules/testing.md(74줄) `grep -nEi "mutation-green|wiring-verified|배선"` rc=1 0 hit · 저장소 전역 `mutation-green` = 회고 보고서 자신 :60/:89 뿐 · `git show --stat 720759b`(#1086) = **테스트 파일 1개 113 insertions, testing.md 미포함**(testing.md 최종 편집=#1081, #1086 이전) · cycle-history.md:156 은 `P2#41(#1086)` 만 명명 · STATE 보류=P2#16 1건.

구조 주장은 신고보다 광범위함을 독립 검증. 타 클러스터 선언 산출물 실측: (1) **P2#27 railway.toml cron `-f` 부재** → :31·37·45·51·57 전부 `curl -s` 그대로 = **미조치 + 미추적, 5xx 무음이라는 라이브 운영 가시성 결함**. (2) P2#24·37 doc_review_gate ROI → 최종 커밋 #1036(회고 이전) 미착수. (3) P2#23·26 tier 재분류 · P2#10·32·33 traceability → downstream 추적 0 hit. (4) 선언된 "pre-merge `--disable-noqa` 가드" → `--disable-noqa` 전역 0 hit(#1081 은 diff-scoped AST = 대체로는 타당하나 선언 산출물 불일치). 즉 '선언 후 부분 조치'는 P2#42 단발이 아니라 반복 패턴.

반증 시도 결과 기각: #1084 `owed-verification.md` 원장이 존재하나 명시 스코프(line 3)가 "코드로 증명 불가한 **운영/외부 검증**"(사용자 회신 대기 항목) — '조치되지 않은 confirmed finding' 행 유형이 없음. 미조치 finding 탐지 원장 부재 주장 성립.

심각도 P1 유지: 본 세션 P0(문서-only 카덴스 트리거가 첫 측정창 자기위반)와 **동형**(선언에 기계 탐지 미배선)이나 라이브 안전 회귀 아니고 P2#27 자체 등급이 낮아 P0 미승격. 반대로 P2 미강등 — 핵심 결함은 누락된 문서 1줄이 아니라 미조치 추적 부재(≥4 클러스터, 그중 1건 라이브 운영)이며, 본 회고 charter 의 'remediation 완결성' 질문 직격.

⚠️ 전파 금지 수치: 근거의 "61 confirmed 중 약 12건만 조치"는 과소집계 — #1085 단독으로 11 finding(P2#7·8·9·15·19·20·21·22·28·29·30) 커버, 실제 ~25~30건. 주장 성립에는 무영향이나 해당 통계는 재사용 말 것.

### P1-30. [tooling] 카덴스 P0 시정이 '규칙 기억' → '스크립트 실행 기억' 으로 이동만 — SessionStart 훅 0, 동일 인지 의존 클래스

- **위치**: `.claude/settings.json:1`
- **주장**: #1080 은 회고 P0(문서-only 트리거 자기위반)의 시정으로 `check_retro_cadence.py` 를 만들었으나, 그 **호출**은 CLAUDE.md:320 의 bash 코드블록 한 줄에만 존재한다. `.claude/settings.json` 에 배선된 훅 이벤트는 `PreToolUse`·`PostToolUse` 두 개뿐이며 `SessionStart`/`UserPromptSubmit` 훅은 0건이다. 즉 '카덴스 규칙을 기억한다' 가 '체크리스트를 읽고 스크립트를 실행할 것을 기억한다' 로 바뀌었을 뿐, 실패 모드(Claude 의 자발적 준수 의존)는 동일하다. 문서-only 트리거는 이미 2회(2026-07-03 신설 → 2026-07-18 ~46 PR 자기위반) 실패했는데, 3번째 시도도 같은 계층(문서에 적힌 실행 지시)에 놓였다. `test_check_retro_cadence.py:150 test_checklist_wires_the_counter` 는 'CLAUDE.md 에 문자열이 존재하는가' 만 단언하므로 이 갭을 구조적으로 못 잡는다 — 문서-only 재발 방지 테스트가 정작 문서-only 임을 승인한다.
- **근거**: `python -c "json.load(open('.claude/settings.json'))"` → hook events wired: ['PreToolUse', 'PostToolUse'] / `grep -rn 'SessionStart|UserPromptSubmit' .claude/settings.json` → 0건 / CLAUDE.md:320 `python scripts/check_retro_cadence.py` (bash 블록 내 산문) / tests/unit/scripts/test_check_retro_cadence.py:156-159 `assert "check_retro_cadence.py" in claude_md`
- **권고**: `.claude/settings.json` 에 `SessionStart` 훅으로 `python scripts/check_retro_cadence.py` 배선(advisory·exit 0 이라 차단 위험 0 — 스크립트가 이미 그 계약으로 설계됨). 그리고 `test_checklist_wires_the_counter` 를 'settings.json 의 SessionStart 훅에 배선됨' 단언으로 승격 — 문자열 존재 단언은 문서-only 를 봉인하지 못한다.
- **cross-verify**: SEVERITY_ADJUST — 실재하는 갭 — 인용 4건 전부 실측 일치. (1) `.claude/settings.json` 배선 훅 = PreToolUse(check_edit_allowed·doc_review_gate) + PostToolUse(posttool_pytest_smoke) 2개뿐. (2) 글로벌 `~/.claude/settings.json` → `hooks: []` (빈 객체) — 상위 계층 백스톱 없음. `.claude/settings.local.json` 부재. (3) `grep -rn "SessionStart|UserPromptSubmit"` 을 `.claude/`·`.github/`·`scripts/`·`docs/` 전역 → **0건**. 배선 안 됐을 뿐 아니라 **검토·기각 흔적조차 없음** = 설계 판단이 아닌 누락. (4) 비-문서 참조는 `scripts/check_retro_cadence.py:17` 자체 usage docstring 뿐이며 CI(`ci.yml`·`codeql.yml`) 미호출 → 유일 호출 경로 = CLAUDE.md:320 산문. (5) `test_check_retro_cadence.py:156-159` 는 `assert "check_retro_cadence.py" in claude_md` 만 단언 — docstring 이 "문서-only 재발 방지" 를 표방하면서 정작 문서 문자열 존재를 '배선' 으로 인증. 동일 파일 :146-147 이 #1094 가 적발한 무의미 단언(Windows stderr 공백)이라 **이 테스트 파일의 공허 단언 패턴이 2건째** — '가드의 가드' 관점에서 유효한 발견. 시정 비용도 낮음: 스크립트가 이미 항상 exit 0 + `_make_stdout_safe()` + self-contained 라 SessionStart 배선이 정책 17 안정성을 해치지 않음.

P0→P1 하향 사유 (주장 중 과대 부분): (a) "이동만·동일 클래스" 는 과장 — 2026-07-03→07-18 에 실제로 실패한 단계는 **암산 카운팅**(~46 PR 이 조작자에게 비가시)이었고 그 단계는 결정론화 + 라이브 검증(STATE.md:11 48→5 리셋)됨. 게재 위치도 §정책 8 진화 (4) 산문 → "매 작업마다" 필수 체크리스트로 salience 상승. 잔여 실패면이 "규칙 기억+암산+판정" 3단계 → "나열된 명령 1회 실행" 1단계로 축소. (b) 제안된 시정(SessionStart) 자체도 부분적 — invoke 단계만 제거하고 **배너를 읽고 회고 진입을 판정하는 단계는 advisory 설계상(breached 여도 `return 0`, 정책 17) 인지 의존으로 잔존** → 발견이 명명한 '클래스' 를 그 발견의 해법도 닫지 못함. (c) 영향 = 회고 지연(프로세스 latency)이며 본 저장소 P0 taxonomy 의 정확성·보안·데이터 손실 계열 아님.

권고: SessionStart 훅에 `check_retro_cadence.py` 배선(additionalContext 주입)으로 invoke 단계 제거 + `test_checklist_wires_the_counter` 를 문자열 존재 단언에서 **settings.json 훅 이벤트 실측 단언**으로 교체(문서-only 를 '배선' 으로 인증하는 자기모순 해소).

### P1-31. [tooling] owed 원장(#1084)이 무배선 문서-only — 같은 회고가 P0 로 규정한 안티패턴의 즉시 재생산

- **위치**: `docs/runbooks/owed-verification.md:1`
- **주장**: 회고 2026-07-18 의 P0 결론은 '문서-only 정책이 두 번 연속 실패했으므로 기계 신호로 승격' 이었다. 그런데 같은 회고의 P1#13 조치로 신설된 `docs/runbooks/owed-verification.md` 는 스크립트 0건·CI step 0건·훅 0건·CLAUDE.md 세션시작 체크리스트 미등재로, 정확히 그 P0 안티패턴이다. 원장이 스스로 '#1058·#1062 = 안전/데이터 등급, 다음 세션 진입 전 명시 회신 의무(정책 5 NEW-P0-N)' 라고 선언하는데, 세션 시작 시 이 행들을 표면화하는 기계 장치가 전무하므로 그 의무는 구조적으로 집행 불가다. 결과적으로 6행 전부 ⏳ 로 누적됐고, `feedback-stale-blocker-policy.md`(머지 대기 4사이클 누적 금지) 위반 궤도에 올라 있다. 즉 원장은 '회신을 유도하는 메커니즘' 이 아니라 '기록만 하는 장부' 다 — 미결이 몇 세션 묵었는지 세는 주체가 없다.
- **근거**: `grep -rn 'owed-verification' --include=*.md --include=*.py --include=*.yml .` → 참조 4건 전부 산문(cycle-history.md:156·STATE.md:15·operational-smoke-checks.md:6·retrospective.md:73), 실행 배선 0 / CLAUDE.md:315-320 세션시작 체크리스트에 owed 원장 미등재(`gh run list`·code-scanning·메모리 grep·check_retro_cadence 4개만) / docs/runbooks/owed-verification.md 안전등급 표 #1058·#1062 = ⏳, 운영등급 #1071·#1072·#1073·#1075 = ⏳ (6/6 미회신)
- **권고**: `scripts/check_owed_verification.py` 신설 — 원장 ⏳ 행 수 + 각 행의 등재 후 경과 세션/PR 수를 카운트해 안전등급 ⏳ 존재 시 loud 배너(카덴스 카운터와 동일 advisory 계약). 세션시작 체크리스트 + SessionStart 훅에 카덴스 카운터와 함께 배선. 원장 행에 '등재 커밋 SHA' 컬럼을 추가해야 경과 측정이 가능하다.
- **cross-verify**: CONFIRMED — 인용 전건 실측 재확인. (1) `docs/runbooks/owed-verification.md` 존재(4067B, e2098d3 #1084). (2) `grep -rn 'owed-verification'` → 참조 4건 전부 산문(cycle-history.md:156·STATE.md:15·operational-smoke-checks.md:6·docs/_archive/reports/2026-07-18-retrospective.md:73 — 보고서가 `retrospective.md:73` 로 축약했으나 동일 파일, 실질 오류 아님). (3) 실행 배선 0 을 독립 확인 — `grep -rni 'owed'` 를 *.py/*.yml/*.mjs/*.sh/Makefile 전수 실행 결과 히트 전부 `allowed` 부분문자열(RLS·auth·gate 등), 진성 참조 0건. scripts/ 20개 중 owed 관련 0. `.claude/settings.json` 훅 3종(check_edit_allowed·doc_review_gate·posttool_pytest_smoke) 무관. CI 워크플로 2종(ci.yml·codeql.yml) runbook 참조 0. (4) CLAUDE.md:315-320 체크리스트 4항목(gh run list·code-scanning·메모리 grep·check_retro_cadence) 중 원장 미등재 — line 320 이 `check_retro_cadence.py` 임을 실측. (5) 원장 6행(#1058·#1062 안전등급 + #1071~#1075 운영등급) 전부 ⏳.

핵심 논거 성립: 같은 회고가 P0 로 "문서-only 정책 2회 연속 실패 → 기계 신호 승격" 을 결론내고 실제로 #1080 을 스크립트+체크리스트 line 320+해설 블록 3중 배선했는데, 같은 회고 P1#13 산출물은 대응물 0. 동일 세션 내 비대칭이라 '아직 학습 전' 변명 불가.

적대 검증 3건 수행: (a) 다른 이름의 배선 존재 가능성 → `owed` 전수 grep 으로 반증. (b) "원장은 본질적으로 기계화 불가" 방어 → 성립 안 함. ⏳ 행 카운트 + git blame 기반 경과 세션 산정은 `check_retro_cadence.py` 와 동형 구현 가능(같은 저장소에 선례 존재)이므로 doc-only 는 제약이 아니라 선택. (c) 원장 line 5 의 "trailing sync PR body §owed 표와 페어" 가 대체 메커니즘인가 → 아님. 그 페어 의무 자체가 산문이라, 두 번 실패한 바로 그 인간/에이전트 기억에 의존 — 반증이 아니라 논거 보강.

심각도 P1 유지(하향 검토 후 기각). 하향 근거로 검토한 것: 원장이 당일 생성(2026-07-18)이라 6/6 ⏳ 는 회신 창 미경과의 자명한 결과이며, `feedback-stale-blocker-policy` 4사이클 임계 미도달 → 실현 손해 0. 그러나 P1 유지 결정: (i) 본 저장소는 이 메커니즘 클래스에 대해 **측정된 2/2 실패율**을 보유하고, 그 측정치를 확립한 주체가 바로 같은 회고다. 추측이 아닌 실측 기저율 적용이므로 "아직 손해 없음" 은 카덴스 트리거가 1일차에 멀쩡해 보였던 것과 정확히 동일한 반론 — 두 번 틀린 반론이다. (ii) 대상이 정책 5 NEW-P0-N(연기 default 미적용 영역) 급 항목 — #1058 은 출시 이래 100% 실패했던 이메일 발송 복구 확인이라 미검증 방치 시 채널 무음 파손 지속. (iii) 결정적으로, 원장이 스스로 "다음 세션 진입 전 명시 회신 의무" 를 선언하면서 그것을 촉발할 주체가 없다 — **자기반증적 보증**은 무보증보다 나쁘다(추적·표면화되고 있다는 허위 안심 생성). 조치 방향: ⏳ 행 수 + 최초 등재 이후 경과 세션/PR 을 실측해 loud 경고하는 `check_owed_verification.py`(advisory·비차단) + CLAUDE.md 세션시작 체크리스트 5번째 항목 등재 — #1080 과 동형, 정책 4(단언+가드 페어) 준수.

### P1-32. [tooling] 자초 CodeQL 3회 재발의 구조적 원인 — PR-time CodeQL 이 이미 돌지만 무게이트, 대신 룰별 stdlib 복제본 4종을 사후 증축

- **위치**: `.github/workflows/codeql.yml:6`
- **주장**: '관용구 복사 드리프트' 는 증상이고 근본은 **탐지 시점**이다. `codeql.yml:6-7` 은 이미 `pull_request: branches:[main]` 로 PR 마다 CodeQL 을 돌리고 `security-and-quality` 스위트(= py/unused-import·py/empty-except·py/import-and-import-from 포함)를 켠다. 그러나 이 룰들은 warning/recommendation 등급이라 PR 체크를 실패시키지 않고, 저장소에는 code-scanning 결과를 소비해 게이트하는 CI step 이 **0건**이다(.github/ 전체 grep 결과 codeql.yml 외 참조 없음). 그 결과 매 파동마다 '해당 룰 하나만 흉내내는 stdlib 가드' 를 사후 추가하는 N+1 트레드밀이 형성됐다 — 현재 4종: flake8 --select=F401,F841(ci.yml:88), check_dual_import.py(ci.yml:95, py/import-and-import-from), check_noqa_sideeffect.py(ci.yml:102, py/unused-import), test_empty_except_guard.py(py/empty-except). 4종 모두 **alert 가 터진 뒤에** 만들어졌고, 각각 스코프·휴리스틱이 제각각이라(위 P1 2건 참조) 원본 룰과 커버리지가 어긋난다. 룰 계열은 앞으로도 남아 있다(py/unused-local-variable·py/similar-function·py/unnecessary-pass 등 동일 스위트) → 5번째·6번째 트레드밀이 예약돼 있다.
- **근거**: .github/workflows/codeql.yml:3-11 (`push`·`pull_request`·주간 cron 3 트리거) / codeql.yml:35 `queries: +security-extended,security-and-quality` / `grep -rn 'code-scanning|codeql' .github/workflows/ci.yml` → 0건(결과 소비 step 없음) / 룰별 복제 가드 4종 = ci.yml:88·95·102 + tests/unit/scripts/test_empty_except_guard.py / 실측 alert 이력: #513~#526·#528~#545 py/unused-import, #517~#520·#538~#539 py/import-and-import-from, #547~#549 py/empty-except (3 계열·다파동)
- **권고**: 룰별 복제 증축을 멈추고 일반해 1건 평가: PR job 에서 `gh api repos/:owner/:repo/code-scanning/alerts?ref=refs/pull/N/merge` 로 **PR 이 신규 도입한 alert 만** 조회해 존재 시 fail(기존 baseline 무영향 = 정책 17 안정성 + 기존 diff-scoped 철학 유지). 채택 시 check_dual_import·check_noqa_sideeffect·empty_except 가드는 중복이 되므로 유지 부담이 순감한다. 미채택이면 최소한 '어떤 CodeQL 룰이 복제 가드로 커버되고 어떤 룰이 미커버인가' 를 명시한 매트릭스를 rules 문서에 두어 다음 파동을 예측 가능하게 할 것.
- **cross-verify**: CONFIRMED — CONFIRMED — evidence is stronger than the finding asserted. All citations verified exactly: codeql.yml:6-7 (`pull_request: branches:[main]`), codeql.yml:35 (`security-and-quality`), and the four replica guards at the precise cited lines ci.yml:88 (flake8 --isolated --select=F401,F841), ci.yml:95 (check_dual_import.py), ci.yml:102 (check_noqa_sideeffect.py) + tests/unit/scripts/test_empty_except_guard.py (a 5th now exists at ci.yml:109, check_dead_code.py). `grep -rn 'code-scanning|codeql|sarif|security-events' .github/` returns 0 result-consuming steps — every ci.yml hit is a comment describing the replicas.

I attempted to refute the premise and failed. The repo's own recorded belief (memory: "자초CodeQL = main full-scan만 노출") implies PR-time CodeQL never surfaces these, which would make PR gating a useless remediation. The instances API disproves it: alert 545 → refs/pull/1070/merge (state=open), 540 → refs/pull/1037/merge, 549 → refs/pull/1083/merge. Detection demonstrably existed pre-merge; only the gate was missing. Decisive timeline: alert 549 (py/empty-except in scripts/check_dead_code.py) created 2026-07-18T05:18:44Z, PR #1083 merged 05:28:08Z — CodeQL flagged it ~10 min before merge, it merged anyway, and #1094 fixed it 5.5h later. The treadmill recurred inside the very session under review, on the PR that added guard #4.

Gate absence confirmed at all three enforcement layers: (1) no CI step consumes code-scanning results; (2) `branches/main/protection` → 404 "Branch not protected"; (3) sole active ruleset PRIMARY (id 17144307, enforcement=active) contains only deletion / non_fast_forward / pull_request(required_approving_review_count=0) — no `code_scanning` rule type. Severity is `note` with security_severity_level=null, below any default check-failure threshold; the finding's "warning/recommendation" wording actually understates its own case.

Qualifier that does not refute: alert 539 (py/import-and-import-from) has a main-only instance with no PR ref, so a code_scanning ruleset gate would catch most but not all of this class (cross-file orphaning still needs main full-scan). The replica guards are therefore not fully redundant — but the finding claims a missing detection-time gate, not that the guards should be deleted, so this narrows the remediation's coverage without undermining the root-cause claim.

Severity held at P1, not raised: real structural cause with demonstrated 3-wave recurrence, in-session reproduction, and a cheap fix (add `code_scanning` rule to the existing PRIMARY ruleset with alerts_threshold, and/or a CI step consuming the SARIF). Not P0 — process/tooling debt with no operational, security, or data-integrity impact.

### P1-33. [tooling] dead-code 가드가 이름 문자열 매칭 — 범용 이름 함수는 무관한 속성 접근에 자동 화이트리스트

- **위치**: `scripts/check_dead_code.py:74`
- **주장**: `check_dead_code.py` 의 `count_ast_references` 는 `ast.Name(id==name)` / `ast.Attribute(attr==name)` 를 **이름 문자열로만** 세고 바인딩을 해석하지 않는다. 따라서 신규 공개 함수 이름이 범용어면 src/ 전역의 무관한 속성 접근이 곧바로 '호출자 있음' 으로 집계돼 가드가 무력해진다. 실측: `get`→561, `commit`→68, `all`→50, `count`→40, `run`→35, `add`→21, `execute`→22, `delete`→17, `update`→10, `create`→6 (전부 SQLAlchemy `db.commit()`·`query.all()`·`dict.get()` 등 무관 참조). 이것이 가설적 위험이 아닌 이유: 현재 `src/repositories/`·`src/services/` 에 실제로 `create`·`get`·`record`·`upsert`·`find_all` 같은 짧은 이름 함수가 존재해, 이 계층의 명명 관습 자체가 충돌 구간에 있다. 즉 `find_orphaned`(긴 고유명)라서 잡힌 것이고, 같은 사고가 `def create()` 로 났다면 가드는 green 이었다. 단위 테스트는 순수 함수 4건(`test_counts_bare_call`·`test_counts_attribute_call`·`test_def_only_is_zero_references` 등)만 검증해 이 오탐 방향(false-negative)을 전혀 통제하지 않는다.
- **근거**: scripts/check_dead_code.py:74-79 (`isinstance(node, ast.Name) and node.id == name` / `ast.Attribute) and node.attr == name`) / 실측 `_total_references(n, Path('src'))`: get=561, commit=68, all=50, count=40, run=35, execute=22, add=21, delete=17, update=10, close=8, send=7, create=6 / 현존 함수명 실측 `grep -rh '^def [a-z]' src/repositories/ src/services/` → create·get·record·upsert·find_all 포함 / (긍정 통제는 정상: worktree@050bab6 에서 `check_dead_code.py 050bab6^ 050bab6` → find_orphaned 적발·EXIT=1)
- **권고**: 정의 파일 자신을 참조 집계에서 제외하고, `ast.Attribute` 매칭은 모듈 별칭이 실제로 해당 repo/service 모듈로 해석될 때만 인정(또는 최소한 `from X import name`/`import X as m` 바인딩이 있는 파일로 한정). 최소 조치로도 충분히 유효: 후보 이름이 짧거나(≤8자) 파이썬/SQLAlchemy 공용어 화이트리스트에 있으면 '참조 있음' 을 신뢰하지 말고 **loud 경고 + 수동 확인 요구**로 격상. 회귀 가드로 `count_ast_references('get', 'db.get(1)')` 가 오검출됨을 명시하는 negative-control 테스트 추가.
- **cross-verify**: CONFIRMED — CONFIRMED — empirically proven, not inferential. (1) Citation verified verbatim: check_dead_code.py:75 `isinstance(node, ast.Name) and node.id == name` / :77 `isinstance(node, ast.Attribute) and node.attr == name` — pure name-string matching, no binding resolution. (2) All 12 claimed counts reproduced exactly via the guard's own `_total_references`(Path('src')): get=561, commit=68, all=50, count=40, run=35, execute=22, add=21, delete=17, update=10, close=8, send=7, create=6. (3) Generic-named public functions confirmed in the guarded layers: create (issue_registration_repo.py:25, merge_attempt_repo.py:20), get (merge_retry_repo.py:31), record (claude_api_cost_repo.py:24), upsert (gate_decision_repo.py:57, insight_narrative_cache_repo.py:58), find_all (repository_repo.py:11), save_new (analysis_repo.py:20, repository_repo.py:73) — so the collision is the mainline naming convention of exactly the guarded layers, not an edge case. (4) DECISIVE end-to-end control I ran in an isolated worktree @1019472 (the finding did not run this): same-diff differential added `def create()` + `def find_stale_orphans_xyz()` to repository_repo.py, BOTH zero-caller — guard flagged ONLY find_stale_orphans_xyz (EXIT=1) and silently passed create; name genericness was the sole differing variable. Isolated re-run with `create` as the sole added function printed `✅ 신규 공개 함수 1개 모두 src 내 호출자 有 / all wired` with EXIT=0 — an affirmative false-green about a function with zero callers. (5) The 6 `create` refs granting the whitelist are 4 unrelated SDK calls (client.messages.create x3 in ai_review.py:144/dashboard_service.py:820/repo_insight_service.py:420, client.chat.completions.create in verifier/openai_client.py:45) plus 2 calls to OTHER repos' create — none reachable to the new function. (6) Test gap confirmed: tests/unit/scripts/test_check_dead_code.py has 14 tests, all on isolated in-memory source strings or CI wiring meta; none exercise _total_references against real src/, so the false-negative direction is entirely uncontrolled. This is exactly the #1094-class defect the session asked to hunt (guard powerless yet green) and implicates remediation completeness: #1083 was declared the seal for P1#9/14/15, but find_orphaned was caught only because it happened to carry a long unique name — had the original incident been `def create()`, the guard would have been green. Severity held at P1 (finding's own): failure is demonstrated with a concrete reproduction rather than 'a feature is missing', but it is tooling defense-in-depth, so worst case is reverting to the pre-#1083 status quo plus false confidence, with no direct production/data impact — hence not P0. Suggested fix direction: resolve the definition site (module-qualified match, or exclude references whose enclosing Attribute value is not the owning repo/service module), or at minimum fail-loud when a candidate name's total reference count is implausibly high relative to its module (heuristic ambiguity warning), plus a regression test asserting a generic-named zero-caller function is still caught. Main repo left clean (worktree removed, git status empty).

### P1-34. [code] owed 원장(#1084)이 어떤 진입점에도 배선되지 않음 — 문서-only 처방의 3회차 반복

- **위치**: `docs/runbooks/owed-verification.md:1`
- **주장**: 회고 P0 의 근본은 '문서-only 시정은 행동을 바꾸지 못한다'였는데, 그 회고가 낳은 #1084 원장 자체가 배선 0인 문서다. 원장은 회신을 유도하는 메커니즘이 아니라 기록 장치이며, 안전등급 행(#1058 SMTP)이 정책 5 NEW-P0-N '매 사이클 회신 의무' 대상인데도 이를 강제하는 신호가 존재하지 않는다.
- **근거**: `grep -rn "owed-verification" CLAUDE.md .claude/policies/ .claude/rules/ scripts/ .github/` → 히트 0 (exit 0). 즉 작업 시작 전 필수 체크리스트(CLAUDE.md:320 부근), 6-step ⑤(STATE·cycle-history 만 명시), 정책 본문, CI 어디에도 원장 참조가 없다. 대조군: check_retro_cadence.py 는 CLAUDE.md:320 체크리스트 라인 + 배선 단언 테스트를 함께 받았으나 원장은 둘 다 없다. 파일 이력도 생성(#1084 e2098d3)·1회 수정(#1088 7608656) 뿐 — 이후 머지된 #1086·#1089~#1093 은 원장에 반영되지 않았고 6행 전부 ⏳ 유지. docs/runbooks/owed-verification.md 헤더는 스스로 '정책 5 NEW-P0-N(안전등급은 매 사이클 회신 의무) 페어'라 선언한다.
- **권고**: check_retro_cadence.py 와 동일 등급으로 승격: (a) 원장의 ⏳ 행 수를 세는 stdlib 카운터(`scripts/check_owed_verification.py`)를 작업 시작 전 체크리스트에 추가하고, 안전등급 ⏳ 가 1건이라도 있으면 loud 배너 (b) 그 배선을 단언하는 테스트 추가 (c) 6-step ⑤ 를 'STATE·cycle-history·**owed 원장**' 3종 동기화로 확장. 메모리 feedback-stale-blocker-policy.md(머지 대기 4사이클 누적 금지)와 페어.
- **cross-verify**: SEVERITY_ADJUST — CONFIRMED as a real, now-empirically-demonstrated defect, but downgraded P0→P1.

VERIFIED (reproduced independently): `grep -rn "owed-verification" CLAUDE.md .claude/ scripts/ .github/` → 0 hits. The only repo references are docs-to-docs (operational-smoke-checks.md:6 header note, STATE.md:15, cycle-history.md:156) — none is an entry point. CLAUDE.md:354 6-step ⑤ names only STATE.md + cycle-history.md. No hook/CI wiring (`.claude/settings*.json`, `.claude/hooks/` → 0). Cited file exists; header at line 5 verbatim self-declares "정책 5 NEW-P0-N(안전등급은 매 사이클 회신 의무) 페어". Control-group asymmetry confirmed exactly as claimed: check_retro_cadence.py has BOTH CLAUDE.md:320 checklist line AND a wiring-assertion test (tests/unit/scripts/test_check_retro_cadence.py:157, comment "배선 안 되면 문서-only 재발"); the ledger has neither. Git history = 2 commits only (e2098d3 #1084, 7608656 #1088); #1089~#1093 merged after with zero ledger updates, 6/6 rows still ⏳.

STRENGTHENED beyond the finder's evidence — decisive test the finder did not run: the ledger's own authoring rule claims pairing with "trailing sync PR body 의 §owed-verification 표". I checked the actual bodies via `gh pr view`. #1093 — merged AFTER both ledger creation (#1084) and its edit (#1088) — contains no §owed-verification section; neither do #1087 or #1085. The self-declared pairing already failed in its first available measurement window. This moves the claim from predicted-to-fail to observed-failing.

WHY P1 NOT P0 (two finder overstatements): (1) "3회차 반복" misattributes history — the cadence trigger #1028 earned P0 on TWO documented failure cycles; this ledger has ONE failed window (#1093). The finder borrowed a different artifact's recurrence count. (2) The finder's assertion "이를 강제하는 신호가 존재하지 않는다" is too strong: MEMORY.md carries "D owed 원장(#1058 SMTP·#1062 IDOR 회신대기)" in the 2026-07-18 세션2 index entry and auto-loads every session, so the two safety-grade rows DO surface — a partial compensating control the finder missed. Accurate framing is "zero ENFORCED signal in the repo's own checklist/CI." Additionally the ledger's non-wiring causes no operational defect by itself; the owed verifications exist independently of it. P0 in this repo's convention requires operational-risk-blocking or demonstrated multi-cycle recurrence — neither is met yet, though one more unenforced session would satisfy the latter.

REMEDIATION (mirror the control group): CLAUDE.md 세션시작 체크리스트 line + wiring-assertion test, plus fold §owed-verification into 6-step ⑤ next to STATE/cycle-history so the trailing sync PR carries it structurally rather than by prose convention.

### P1-35. [code] PostToolUse 스모크 훅의 ❌ 신호가 Claude 컨텍스트에 도달하지 않음 — false-green 을 silent-red 로 교체

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:105`
- **주장**: #1082 는 완주 불가(타임아웃 삼킴) 문제를 고쳤지만 전달 경로는 그대로다. 훅은 항상 exit 0 이고 배너를 stdout 에 쓴다. PostToolUse 훅의 exit-0 stdout 은 사용자 transcript 모드(Ctrl-R)에만 노출되고 Claude 컨텍스트에는 주입되지 않으므로, CLAUDE.md 가 명령하는 '❌ 배너 시 즉시 조사'를 수행할 주체가 배너를 볼 수 없다.
- **근거**: .claude/hooks/posttool_pytest_smoke.py:101-105 — `banner = "✅ 스모크 통과" if rc == 0 else (..."❌ 스모크 실패")` → `print(...)` → `return 0  # 비차단 advisory / non-blocking advisory`. CLAUDE.md:352 "❌ 배너 시 즉시 조사". Claude Code 훅 계약상 Claude 에게 텍스트를 전달하는 경로는 exit 2(stderr) 또는 JSON `hookSpecificOutput.additionalContext` 인데 둘 다 미사용. 구 훅(git show 6153fed^:.claude/settings.json)도 `| tail -8 || true` 로 동일하게 stdout·exit 0 이었으므로 이 결함은 #1082 가 상속한 채 남았다. 실행 실측: `echo '{"tool_input":{"file_path":"src/scorer/engine.py"}}' | python .claude/hooks/posttool_pytest_smoke.py` → `✅ 스모크 통과 [tests/unit/scorer]`, EXIT=0.
- **권고**: 실패(rc != 0)와 미완(rc is None)일 때만 배너를 stderr 로 내보내고 exit 2 반환(정상 통과는 현행 exit 0 유지). 차단이 부담이면 JSON `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}` 로 비차단 주입. 어느 쪽이든 '실패가 Claude 에게 전달됨'을 단언하는 테스트 동반.
- **cross-verify**: CONFIRMED — CONFIRMED at P1. All citations verified: posttool_pytest_smoke.py:101-105 matches exactly (banner ternary -> print -> `return 0  # 비차단 advisory`); CLAUDE.md:352 contains "❌ 배너 시 즉시 조사"; `git show 6153fed^:.claude/settings.json` confirms the old hook was `python -m pytest tests/ -x -q 2>&1 | tail -8 || true` — same stdout + exit-0 channel, so the delivery defect is genuinely INHERITED, not introduced by #1082. Empirical rerun reproduced `✅ 스모크 통과 [tests/unit/scorer]` / EXIT=0 verbatim.

Contract analysis holds: PostToolUse with exit 0 and plain-text stdout surfaces only in opt-in transcript mode (Ctrl-R) and is not injected into Claude's context. The Claude-visible channels are exit 2 (stderr) or JSON `hookSpecificOutput` — neither is used. Settings inspection confirms a single PostToolUse entry (`Write|Edit`, timeout 90) with no output routing, and no settings.local.json override exists.

I attempted three refutations, all of which failed: (1) "it's intentional advisory design" — refuted, because non-blocking and Claude-visible are orthogonal; `hookSpecificOutput.additionalContext` delivers to Claude WITHOUT blocking the edit, so the current design purchases no tradeoff, it is a pure gap; (2) "the banner is for the user, not Claude" — refuted, because the instruction sits in CLAUDE.md 필수 원칙, Claude's own operating manual, and "즉시 조사" is an in-loop action only Claude performs, while transcript mode is opt-in so in practice neither party reliably sees it; (3) "no better mechanism available" — refuted decisively, because both sibling hooks in the same directory already use it (check_edit_allowed.py:102, doc_review_gate.py:312 both emit `hookSpecificOutput`). This hook is an outlier, not a considered choice.

Two findings strengthen the original beyond what was reported. First, tests/unit/hooks/test_posttool_pytest_smoke.py (64 lines) covers ONLY the pure functions is_src_file and derive_test_target — there is ZERO coverage of main(), the delivery path. No positive control exists that a ❌ ever reaches any consumer. This is exactly the #1094 class the retro's "가드의 가드" question targets: the guard runs, computes correctly, is structurally incapable of informing its addressee, and the suite stays green. Second, doc_review_gate.py:319-320 carries the identical defect on its `warn` branch (bare print + sys.exit(0)) while its `block` branch uses structured output — a small recurring pattern, not a one-off.

Severity retained at P1 rather than adjusted to P2. I weighed the mitigation seriously: this hook is explicitly not the gate, and push-time `pytest tests/unit` (6-step ②) remains an enforced blocking backstop, so blast radius is lost early-warning latency rather than an escaped regression reaching main. P1 nonetheless stands because the claim concerns guard integrity, and CLAUDE.md's "Hook 신뢰" 필수 원칙 depends on this signal arriving at its consumer. #1082 made the computation honest (fixing false-green) but left delivery broken — a half remediation, i.e. a remediation-completeness defect. Suggested fix: emit `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": banner + tail}}` on the rc != 0 path (and consider the rc is None timeout path), keeping exit 0 so the hook stays non-blocking; add a main() test asserting the ❌ path actually emits a Claude-visible payload, since no such positive control currently exists.

### P1-36. [code] 회고 카덴스 카운터가 훅 미배선 — 실행 주체가 여전히 인지 의존이고, '배선' 테스트는 문서 문자열만 단언

- **위치**: `.claude/settings.json:1`
- **주장**: P0 시정의 요지는 '인지 의존을 측정 신호로 전환'인데, 카운터는 CLAUDE.md 체크리스트 문장으로만 호출된다. 즉 '문서가 시키는 대로 Claude 가 기억해서 실행'하는 구조로, 실패한 원래 메커니즘과 동일 계층이다. 배선을 지킨다는 테스트조차 CLAUDE.md 에 파일명 문자열이 있는지만 본다.
- **근거**: CLAUDE.md:320 `python scripts/check_retro_cadence.py  # 🔴 회고 카덴스 기계 카운터 (정책 8 진화 (4))` — bash 체크리스트 블록 내 텍스트. .claude/settings.json 은 PreToolUse 2종 + PostToolUse 1종만 등록하며 SessionStart 훅 항목이 없다(파일 전문 확인). tests/unit/scripts/test_check_retro_cadence.py:150-159 `test_checklist_wires_the_counter` 는 `assert "check_retro_cadence.py" in claude_md` — 문자열 존재만 확인하므로, 체크리스트가 무시돼도 green. 같은 파일 docstring 10-11 은 '현재 repo 카덴스 상태는 시점 의존이라 단언 금지'라 실측 상태 단언도 배제돼 있다.
- **권고**: settings.json 에 SessionStart 훅으로 `python scripts/check_retro_cadence.py` 등록 — SessionStart 는 exit-0 stdout 이 Claude 컨텍스트에 주입되는 이벤트라 advisory 성격(exit 0)을 유지하면서도 신호가 실제 도달한다(위 PostToolUse 전달 결함과 정반대 특성). test_checklist_wires_the_counter 를 settings.json 배선 단언으로 승격.
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인. (1) CLAUDE.md:320 = bash 체크리스트 블록 내 텍스트 호출(주석 포함 정확 일치). (2) .claude/settings.json 전문 = PreToolUse 2종(check_edit_allowed, doc_review_gate) + PostToolUse 1종(posttool_pytest_smoke)만 — SessionStart 항목 없음. settings.local.json 부재. repo 전역 grep "SessionStart" = 0 hit. (3) test_check_retro_cadence.py:150-159 = `assert "check_retro_cadence.py" in claude_md` 문자열 존재만. (4) docstring:10-11 = 실측 상태 단언 배제 확인.

반증 시도(CI/pre-commit/Makefile/statusline 배선 탐색)가 오히려 finding 을 강화함 — 동일 시정 배치 4 가드 중 3종은 실제 집행 기질에 배선됨: check_noqa_sideeffect.py→ci.yml:102, check_dead_code.py→ci.yml:109, posttool_pytest_smoke.py→settings.json:26. check_retro_cadence.py 만 유일하게 실행 경로 0 (전역 grep = CLAUDE.md 산문 2줄 + STATE/cycle-history 서사 + 자기 테스트뿐). 게다가 pre-commit 은 이미 6개 check_*.py 를 CI 와 이중 배선 중 — 즉 배선 표준이 repo 에 존재했고 형제 3종이 충족했는데 본건만 누락. 이는 프로젝트가 반복 겪은 "only-one-side-guarded 비대칭 결함" 패턴(#1068~#1075)의 재현.

반론 검토: (a) "48→5 리셋 실측" 은 계산 정확성 증거이지 호출 보장 증거가 아님(시정 세션에서 수동 실행). (b) 판정(judgment) 기계화는 실제 부분 개선 — 그래서 P0 아님. (c) "advisory 라 게이트 불가" 는 논점 이탈 — invoked-vs-not 과 blocking-vs-advisory 는 직교하며 SessionStart 훅도 비차단 배너 방출 가능. 메모리의 "advisory=P0 무시 재현" 학습은 오히려 우려를 가중.

P1 유지 근거: 문서-only 메커니즘이 2회 연속 실패(2026-07-03 신설→2026-07-18 ~46 PR 무회고)한 P0 의 시정이 다시 산문 호출 계층에 착지 = 3회차 동형 실패가 구체적 위험. 또한 테스트 이름 test_checklist_wires_the_counter 가 실제 단언(문서 문자열 존재)보다 과대 주장 = 본 회고가 추적 중인 #1094 형 false-green 계열이며, "가드의 가드" 질문에 대한 직접 답. P0 미승격 사유 = 운영/보안 영향 없고 순수 함수 로직은 정확.

구조적 원인(재발 이유): 이 repo 는 집행 기질이 3종(pre-commit / CI / .claude/settings.json 훅) + 유사 기질 1종(CLAUDE.md 산문)으로 분산돼 있으나, "신규 가드 스크립트는 실 기질 3종 중 하나에 반드시 착지" 규칙이 부재. 그 결과 산문 착지 가드가 리뷰·테스트를 통과 — 테스트 작성자가 '집행 요건' 이 아니라 '만들어진 것' 에 맞춰 단언을 쓰기 때문. 권고: (1) SessionStart 훅 등록으로 호출 기계화, (2) 테스트를 settings.json 파싱 기반 배선 단언으로 교체(문자열 단언 폐기), (3) 신규 check_*.py 는 pre-commit/CI/settings.json 중 1곳 배선을 강제하는 메타 가드 신설(정책 4 단언+가드 페어).

### P1-37. [code] owner-filter parity 가드의 _OWNER_SCOPED 가 손유지 목록 — '신규 집계 추가 시 CI fail' 주장이 성립하지 않음

- **위치**: `tests/unit/ui/test_dashboard_owner_filter_parity.py:26`
- **주장**: 가드는 docstring 에서 '신규 집계가 owner 스코프 없이 추가되면 CI fail' 이라 단언하지만, 판정 대상 집합이 손으로 유지되므로 저자가 집합에 이름을 추가하지 않으면 신규 집계는 검사 자체를 받지 않는다. 완전성 테스트는 rename/제거만 잡고 '추가 누락' 방향은 열려 있다 — testing.md 가 #1041 교훈으로 경고하는 손유지 목록 안티패턴과 동형이다.
- **근거**: tests/unit/ui/test_dashboard_owner_filter_parity.py:26-31 `_OWNER_SCOPED = {...}`(10개 하드코딩) · 79-87 `test_all_owner_scoped_aggregations_are_wired` 는 `_OWNER_SCOPED - called` 만 검사(반대 방향 없음) · 51-52 helper 는 `owner_scoped` 집합 밖 함수를 명시적으로 무시(`test_helper_ignores_non_owner_scoped`). 대조: .claude/rules/testing.md 의 '손유지 i18n 키 목록 ↔ 템플릿 양방향 가드' 절이 정확히 이 실패를 다루며 해법으로 SSOT 파생(`test_keys_match_template`)을 제시한다. 현재 drift 는 0 — AST 실측 결과 src/services/dashboard_service.py 의 user_id 수용 공개 함수 10개가 _OWNER_SCOPED 10개와 정확히 일치하므로, 집합은 **기계적으로 파생 가능**하다.
- **권고**: _OWNER_SCOPED 를 dashboard_service.py 에서 파생 — `{공개 함수 중 user_id 파라미터 수용}` 를 AST 로 계산하고, 하드코딩 집합과의 집합 동등성을 단언(양방향). 그러면 신규 owner-스코프 집계 추가 시 집합 갱신을 잊어도 자동 편입되어 docstring 의 단언이 실제로 성립한다.
- **cross-verify**: SEVERITY_ADJUST — 모든 인용 실측 확인 + 주장 재현 성공. 반증 시도는 실패했고, 오히려 심각도를 올려야 할 결정적 사실이 나왔다.

**인용 검증 (전건 일치)**
- `test_dashboard_owner_filter_parity.py:25-29` — `_OWNER_SCOPED` 10개 하드코딩 ✅
- `:84` — `missing = _OWNER_SCOPED - called` 단방향만 ✅ (반대 방향 없음)
- `:110-113` — `test_helper_ignores_non_owner_scoped` 가 집합 밖 함수 명시적 무시 ✅
- `:7`/`:10` docstring — "신규 집계가 owner 스코프 없이 추가되면 CI fail" / "a new aggregation added without owner scope fails CI" ✅ (과대 단언 실재)
- `.claude/rules/testing.md` §"손유지 i18n 키 목록 ↔ 템플릿 양방향 가드" 가 동형 실패(#1041 6-fail)를 다루며 SSOT 파생(`test_keys_match_template`)을 해법으로 제시 ✅

**기계적 파생 가능성 실측** — AST 로 `dashboard_service.py` 공개 함수 추출: 총 10개, 전부 `user_id` 수용, `_OWNER_SCOPED` 10개와 **정확히 일치**(차집합 양방향 공집합). 파생을 막는 설계 트레이드오프 없음 = 수정 비용 기계적.

**긍정 통제 재현 (반증 실패)** — 실제 route 소스에 `dashboard_service.dashboard_newagg(db)` (신규·user_id 없음) 주입 후 가드 로직 실행:
- `test_every_dashboard_aggregation_passes_user_id` → `missing = []` → **PASS(놓침)**
- `test_all_owner_scoped_aggregations_are_wired` → `missing = set()` → **PASS(놓침)**
- 대조군(기존 `feedback_status` 에서 `user_id` 제거) → `missing = ['feedback_status']` → 정상 검출

즉 가드는 **회귀 방향(기존 항목 user_id 소실)만** 작동하고 **추가 방향은 완전히 맹목**이다. 다른 백스톱 부재도 확인 — `grep -rln "owner_scoped|owner-filter"` 결과 이 파일 외 route-배선 완전성 가드 없음(`test_dashboard_service_user_id_filter.py` 는 서비스 계층 필터 동작 테스트지 배선 완전성 아님).

**P2 → P1 상향 근거 (finder 미기술 · 결정적)**
가드가 봉인하려던 **#1074 자체가 "추가 방향" 사고**다. 파일 docstring:4-5 — "overview 7 형제 집계 중 `feedback_status` 하나만 owner 필터를 **안 받아**" = 신규 형제가 owner 스코프 없이 추가된 경우이지 기존 호출이 user_id 를 잃은 경우가 아니다. **원 사고가 온 방향을, 그 사고를 막으려 만든 가드가 커버하지 않는다** — remediation 이 선언은 됐으나 실제로는 부분 조치(세션 질문 §remediation 완결성에 정확히 해당).

여기에 3 요소가 겹친다: (a) **단일 방어선** — 메모리 실측상 RLS 0026 이 `user_id IS NULL` 을 whitelist 해 DB 백스톱 부재, 앱 계층이 유일 (b) **지배적 방향에 맹목** — 신규 집계 추가는 rename/제거보다 훨씬 빈발 (c) **false-confidence** — `:23` 주석이 "집합에 추가하라"고 안내하지만 신규 집계를 dashboard.py 에 추가하는 개발자는 이 테스트 파일을 열 이유가 없고 CI 는 조용히 green. 노출 결과는 타 테넌트 private repo 정보 = 보안 인접.

현 drift 0(당장 노출 없음)이라 P0 은 아니나, "가드가 무력한데 green"(#1094 형) + 원 사고 방향 미커버 + 단일 방어선 조합은 하드닝 nit(P2) 를 넘는다.

**권고 조치** — `_OWNER_SCOPED` 를 `dashboard_service.py` AST 파싱으로 파생(공개 함수 중 `user_id` 수용). 부수 효과로 "서비스가 user_id 를 아예 안 받는 신규 집계" 는 여전히 미검출이므로, 파생 집합을 **공개 함수 전체**로 잡고 `user_id` 미수용 함수를 명시적 화이트리스트(`# global-metric-ok:`)로 예외 처리하는 편이 `check_dead_code.py` 의 `# unwired-ok:` 선례와 일관되고 두 방향을 모두 봉인한다. docstring:7/10 의 "모든"·"신규 집계 추가 시 CI fail" 단언은 수정 전까지 실제 커버리지에 맞게 정정 필요(정책 4 — 단언과 가드를 같은 PR 에).

### P1-38. [P0 카덴스 가드 — 배선 vs 집행 비대칭] 동일 회고 배치 4 가드 중 P0 가드만 재량 계층에 잔존 — 나머지 3종은 기계 집행 배선 획득

- **위치**: `CLAUDE.md:320`
- **주장**: #1080~#1083 신규 가드 4종 중 3종은 기계가 강제하는 실행 경로를 얻었으나, 근본 원인이 정확히 '문서-only 트리거를 2회 연속 미준수'였던 P0 가드(#1080)만 유일하게 산문 체크리스트에 남았다. 즉 두 번 실패한 바로 그 재량 계층이 3번째 재발 경로로 그대로 보존됐다. 더 결정적인 것은, 같은 세션 #1089 가 '우회 가능한 계층에 있는 가드는 서버측 백스톱으로 승격한다'는 원칙을 명시적으로 언어화하고 P2#36 4 가드에 적용했다는 점이다 — 원칙을 손에 쥔 채 최고 심각도 항목에는 적용하지 않았다. 심각도 역전(P2 는 기계화, P0 는 산문)이 배치 내부에 존재한다.
- **근거**: 배선 실측 대조: #1081 check_noqa_sideeffect → `.github/workflows/ci.yml:102` (PR 차단) / #1083 check_dead_code → `ci.yml:109` (PR 차단) / #1082 posttool_pytest_smoke → `.claude/settings.json:26` (PostToolUse 훅) / #1080 check_retro_cadence → `CLAUDE.md:320` 산문 1곳뿐. `grep -rn check_retro_cadence` 전수 결과 실행 배선은 CLAUDE.md 외 0곳(나머지 히트는 전부 docs 서술·테스트·docstring). `.claude/settings.json` 훅 이벤트는 PreToolUse/PostToolUse 2종만 — `grep -rn "SessionStart|UserPromptSubmit|SessionEnd" ~/.claude/*.json .claude/` 히트 0으로, 세션 시작 시점에 자동 실행할 기제가 존재하는데 미채택. 동일 세션의 반대 원칙: `ci.yml:113` "pre-commit-only 라 우회 가능했다 → … 서버측 백스톱으로 승격" (job `ci.yml:116-117`).
- **권고**: 카운터 호출을 재량에서 기계 계층으로 이동: (a) `.claude/settings.json` 에 `SessionStart` 훅 추가해 `python scripts/check_retro_cadence.py` 자동 실행(advisory·비차단 유지 — 정책 17 안정성 보존, 커밋/PR 미간섭 성질은 그대로) 또는 (b) 차선으로 `UserPromptSubmit` 1회성 실행. 동시에 `test_ci_repo_integrity_backstop.py:38-45` 의 검증된 패턴을 그대로 이식해 '카운터가 훅 이벤트에 배선돼 있는가'를 단언하는 회귀 가드를 동반한다(정책 4 단언+가드 페어). 배선 이동 없이 CLAUDE.md 문구만 강화하는 시정은 이미 2회 실패한 계층의 3번째 시도이므로 금지.
- **cross-verify**: SEVERITY_ADJUST — 실체 확인 — 배선 비대칭은 실재. 전 인용 line 실측 일치: check_noqa_sideeffect → ci.yml:102(차단), check_dead_code → ci.yml:109(차단), posttool_pytest_smoke → .claude/settings.json:26(PostToolUse 자동발화), check_retro_cadence → CLAUDE.md:320 산문 1곳뿐. `grep -rn check_retro_cadence` 전수 + .pre-commit-config.yaml / Makefile / .git/hooks / ci.yml / 양 settings.json 확인 결과 실행 배선 0곳(나머지 히트=docs 서술·docstring·테스트). 훅 이벤트는 PreToolUse/PostToolUse 2종뿐 — SessionStart/UserPromptSubmit 히트 0으로 자동 실행 기제 미채택 확인. ci.yml:113 승격 원칙("pre-commit-only 라 우회 가능했다 → 서버측 백스톱으로 승격") 및 job ci.yml:116 도 확인. 반증 시도 3건 모두 실패: (a) "advisory 설계라 기계화 부적합" — advisory 와 자동실행은 직교(SessionStart 는 비차단+자동 동시 충족)이므로 방어 실패. (b) "테스트가 배선을 고정" — test_check_retro_cadence.py:157 은 CLAUDE.md 내 **문자열 존재**만 단언, 실행을 고정하지 않음. 실제 실패 양태(Claude 가 체크리스트를 건너뜀)를 원리적으로 탐지 불가 = 두 번 실패한 재량 계층 그대로 보존. (c) "이미 해소" — HEAD 에서 훅 배선 0 확인.

P0→P1 하향 사유 2건. (1) 주장의 '심각도 역전(P2 는 기계화·P0 는 산문)' 프레이밍이 동종 비교를 과장 — P2#36 가드는 임의 커밋에서 평가 가능한 whole-repo 상태 검사라 CI 가 자연스러운 venue 였으나, 카덴스 카운터는 PR 단위로 평가할 트리거가 없어 CI 백스톱이 구조적으로 부적합. 실제 미채택 기제는 SessionStart(근거에 정확히 적시됨)이며, 이 지점에서 finding 의 실질은 유지되나 '역전' 수사는 과함. (2) #1080 은 no-op 이 아님 — 측정 불가한 인지 판단을 정확한 카운트+loud 배너의 측정 신호로 전환했고 라이브 48→5 리셋이 실측됨. 2회 실패 당시(측정 자체 부재) 대비 실질 개선이며 잔여 갭은 '자동 호출' 단일 항목. 노출 범위도 회고 지연이라는 프로세스 위생이지 운영/보안/데이터 손실이 아님. 다만 배치 자신의 P0 잔여이고 같은 세션이 승격 원칙을 명문화해 놓고 미적용한 불일치라 backlog(P2) 가 아닌 실착수 대상 — P1 이 적정. 권고 조치: `.claude/settings.json` 에 SessionStart 훅으로 `python scripts/check_retro_cadence.py` 배선(비차단 유지) + 테스트를 '문자열 존재'에서 '훅 배선 존재' 단언으로 승격.

### P1-39. [P0 카덴스 가드 — 회귀 가드 실효성(긍정 통제 부재)] 배선 단언이 '텍스트 존재' 수준 — main() 3 skip 경로 무커버, 동일 디렉토리에 더 강한 검증된 패턴 존재

- **위치**: `tests/unit/scripts/test_check_retro_cadence.py:150`
- **주장**: 카덴스 가드의 회귀 테스트는 두 겹에서 긍정 통제가 비어 있다. (1) 배선 단언이 `"check_retro_cadence.py" in claude_md` — CLAUDE.md 에 그 문자열이 있는가만 확인하며, 실행 여부는 물론 그 줄이 체크리스트 안에 있는지·주석 처리됐는지조차 구분하지 못한다(본 회고 서술 문단에도 같은 문자열이 있어 체크리스트 호출을 통째로 삭제해도 테스트는 통과한다). (2) `main()` 통합 경로에 긍정 통제가 없다 — 순수 함수 `evaluate` 는 breached True 를 제대로 단언하지만, 스크립트 전체 실행 테스트는 exit 0 과 UnicodeEncodeError 부재만 볼 뿐 **출력이 옳은지**를 보지 않는다. 그 결과 무음 skip 3 경로가 전부 미커버로 남아 P1 결함이 생존했다. 같은 디렉토리에 이미 더 강한 패턴이 있다는 점이 구조적 원인을 드러낸다 — 검증된 배선-단언 패턴을 보유한 세션이 최고 심각도 가드에는 가장 약한 형태를 적용했다.
- **근거**: 약한 배선 단언: `tests/unit/scripts/test_check_retro_cadence.py:150-158` (`assert "check_retro_cadence.py" in claude_md`). 문자열 중복 출처: `CLAUDE.md:320` 체크리스트 호출 + `CLAUDE.md:326` 서술 문단 — 320 삭제 시에도 326 이 단언을 만족. 통합 긍정 통제 부재: 같은 파일 `:141-147` 이 `returncode == 0` 과 `"UnicodeEncodeError" not in r.stderr` 만 단언(출력 내용 무검사). 미커버 무음 경로: `scripts/check_retro_cadence.py:111-112`(리포트 디렉토리 부재) · `:115-116`(정식 회고 부재) · `:120-121`(경계 커밋 미발견) 3곳 모두 exit 0. 검증된 대안 패턴: `tests/unit/scripts/test_ci_repo_integrity_backstop.py:38-45` `test_repo_integrity_runs_all_four_guards` 가 ci.yml job 의 실제 run 스텝을 파싱해 4 가드 각각의 배선을 단언.
- **권고**: 두 겹 모두에 긍정 통제를 넣는다. (1) 배선 단언을 `test_ci_repo_integrity_backstop.py:38-45` 형태로 승격 — 산문 검색이 아니라 실제 실행 기제(`.claude/settings.json` 훅 command 또는 CLAUDE.md 체크리스트 bash 블록 범위 한정 파싱)에서 호출을 찾도록 한다(F1 의 SessionStart 배선과 동시 적용 시 자연히 훅 단언으로 통일). (2) `main()` 통합 테스트에 탐지기 긍정 통제 추가 — 임시 git repo 픽스처에 정식 회고 리포트 + 임계 초과 머지 커밋을 심고 stdout 에 '트리거 발화'가 실제로 나오는지, 그리고 임계 미만에서는 안 나오는지 양방향 단언. 무음 skip 3 경로도 각각 의도된 조건에서만 나오는지 커버해 blind-and-green 을 봉인한다.
- **cross-verify**: SEVERITY_ADJUST — substance CONFIRMED, severity raised P2 -> P1. All six citations verified EXACT: test_check_retro_cadence.py:150-158 wiring assert is a whole-file substring check; CLAUDE.md:320 (checklist call) + :326 (prose) both contain the literal; :141-147 asserts only returncode==0 and absence of UnicodeEncodeError with zero stdout assertions; check_retro_cadence.py:111-112/:115-116/:120-121 are three silent `return 0` skips; test_ci_repo_integrity_backstop.py:38-45 is the stronger in-repo pattern (parses ci.yml run steps per guard).

Empirically reproduced the reporter's central claim: removing line 320 leaves line 326, and the assertion still evaluates True -- the checklist call can be deleted wholesale with the suite green.

NEW EVIDENCE the reporter lacked, which is why I raise severity: _REPORTS_DIR = Path("docs/_archive/reports") is RELATIVE, so main() is CWD-dependent. Run from repo root it prints "trigger FIRED -- 15 merged PRs (>= 15)"; run from scripts/ it prints "reports dir absent -- skip". Both exit 0 with empty stderr, so the integration test cannot distinguish a working counter from a fully blind one. That is exactly the #1094 class (guard neutered but green) the session named as its priority question, present inside the guard that seals the retrospective's own P0.

PARTIAL PUSHBACK on the reporter's reasoning: their claim that the missing positive control "let a P1 defect survive" overreaches -- the #1094 defect was subprocess encoding in the test harness, a distinct failure mode from the uncovered main() skip paths, and it is already fixed at :144. The finding did not need that causal chain. The sound case is the two compounding blind spots (wiring assert cannot see de-wiring; runtime assert cannot see no-op) on a control whose doc-only predecessor already failed twice (#1028 -> ~46-PR gap -> #1080).

Concrete failure scenario: a routine CLAUDE.md checklist reorganization drops line 320 while prose at 326 survives -> full suite green -> counter never runs again -> the sealed P0 reopens silently and is next detected only by another multi-session no-retro gap. Live output shows the trigger firing at exactly the 15/15 boundary now, so the counter is load-bearing today and a regression would be invisible.

Not P0: wiring is currently intact and the tool is advisory/non-blocking by design, so nothing is operationally broken. But P2 understates a guard that cannot detect its own defeat while protecting a P0-classified control. Remediation: scope the wiring assert to the checklist fenced code block (match the `python scripts/check_retro_cadence.py` invocation form, not the bare filename), and add a positive control on main() asserting stdout contains the "last formal retro" line plus tests for the three skip branches via tmp_path/monkeypatch -- ideally anchoring _REPORTS_DIR to the script's repo root rather than CWD.

### P1-40. [railway cron 관측 신뢰성 ↔ owed 원장] owed 원장 #1073·#1075 의 검증 수단이 곧 맹점 — 게다가 두 기능은 cron 이 유일 호출자라 미실행 가능성이 높음

- **위치**: `docs/runbooks/owed-verification.md:24`
- **주장**: 원장 `owed-verification.md:24,25` 는 #1073·#1075 의 검증 방법을 둘 다 'Railway cron 로그에서 실행/purged 관측' 으로 지정한다. 그런데 (a) 그 관측 채널이 F1 로 인해 실패를 은폐하고, (b) `sweep_analysis_attempts`·`run_retention_sweep` 은 **`src/api/internal_cron.py` 외 호출자가 저장소 전체에 0건** — cron 이 유일 트리거다. 따라서 사용자가 ✅ 를 찍어도 무의미한 정도가 아니라, **두 기능이 실제로는 한 번도 실행되지 않았을 가능성이 높은 상태에서 ✅ 가 찍힐 수 있다**. 회고가 owed 등록(P1#13)과 cron 무음 5xx(P2#27)를 별개 클러스터로 처리해 이 의존이 검토되지 않았다.
- **근거**: `grep -rn "sweep_analysis_attempts\|run_retention_sweep" --include=*.py src/` → `internal_cron.py:18,21,148,160` (정의부 제외 시 호출자 = internal_cron 단독). 대조군: `process_pending_retries` 는 `src/webhook/providers/github.py:492,497` 에도 배선되어 있어 cron 이 죽어도 webhook 경로로 동작 → 운영 머지 938건(메모리 #985)이 cron 정상성의 증거가 **되지 못함**(F1 을 반증하지 않음).
- **권고**: 원장 검증 방법을 **cron 로그 관측 → DB 상태 직접 조회** 로 교체(예: #1075 = `expired_cache` 만료 행 잔존 수 SELECT, #1073 = `analysis_attempts` orphan 잔존 수 SELECT). 코드-미증명 항목의 검증 수단은 **결함과 독립인 채널** 이어야 한다. 추가로 원장에 `검증 수단의 신뢰성 전제` 컬럼 1개를 신설해, 미수정 P0/P1/P2 가 검증 채널을 무력화하는지 행 등록 시 자가 대조하도록 강제.
- **cross-verify**: SEVERITY_ADJUST — CITATION VERIFIED (exact). `docs/runbooks/owed-verification.md:24` = "Railway cron 로그에서 orphan sweep 실행 + `INTERNAL_CRON_API_KEY` 설정 확인(미설정 시 무음 중단)"; `:25` = "Railway cron 로그 `retention sweep — purged expired_cache=N terminal_queue=N` 관측". Both prescribe the same channel, as claimed.

GREP VERIFIED. `sweep_analysis_attempts` / `run_retention_sweep`: definitions at `src/services/cron_service.py:42,89`, references only at `src/api/internal_cron.py:18,21,148,160` — call sites = internal_cron alone. Contrast holds: `process_pending_retries` is additionally wired at `src/webhook/providers/github.py:492,497`. The finder's neutralization of the 938-merge counter-evidence (memory #985) is therefore correct — merge volume evidences the *webhook* path and says nothing about cron liveness.

F1 MECHANISM INDEPENDENTLY CONFIRMED (finder asserted it; I verified it). All five `[[deploy.cronJobs]]` in `railway.toml` invoke `curl -s` with **no `-f`/`--fail`** (railway.toml:31,37,45,51,57). curl exits 0 on HTTP 401/503/5xx, so Railway's cron reports SUCCESS while the request failed. The 503 branch at `internal_cron.py:47-51` (unset `INTERNAL_CRON_API_KEY`) is precisely the condition ledger:24 asks the user to rule out — and it is structurally invisible through the prescribed channel. The ledger's own parenthetical "(미설정 시 무음 중단)" names the failure it cannot detect.

NEW — FINDER UNDERSTATED ITS OWN CASE. `cron_service.py:103` gates the retention log behind `if expired_cache or terminal_queue:`. The exact string ledger:25 tells the user to look for is **not emitted on a healthy run with nothing to purge**. So absence of that log cannot distinguish "ran clean" from "never ran" — the verification instruction is non-discriminating even when cron is fully healthy and authenticated. (An unconditional `logger.info("retention_sweep: counts=%s")` does exist at `internal_cron.py:161`, but the ledger does not point the user at it. Same shape for orphans: `cron_service.py:56-57` returns 0 with no service log.) Recommended fix targets this: point the ledger at the unconditional endpoint-level log, or better, replace log-grep with a DB-observable assertion, and add `--fail-with-body` to the cron curls.

FLAGGED FOR SEPARATE CHECK (not asserted — outside this finding, and I cannot verify Railway's exec semantics from here): each cron command single-quotes `'X-API-Key: $INTERNAL_CRON_API_KEY'` while `$PORT` in the same string is unquoted. Under POSIX `sh -c`, single quotes suppress expansion — the header would ship the literal `$INTERNAL_CRON_API_KEY` → 401 on every cron, silently, for all five jobs. The intra-command asymmetry warrants a live probe.

WHY NOT P0. Two overreaches in the grading:
(1) "두 기능이 한 번도 실행되지 않았을 가능성이 높다" is inference from unobservability, not measurement. Both cron jobs ARE declared (railway.toml:49-51 `*/10 * * * *` sweep-orphans; :55-57 `0 20 * * *` retention-sweep). Unobservable ≠ not running. The defensible claim is "cron liveness is unevidenced and the prescribed check cannot establish it" — which is P1.
(2) Blast radius is janitorial. Non-execution causes unbounded growth of `analysis_attempts` / `insight_narrative_cache` / `merge_retry_queue` plus undetected analysis loss — degradation over weeks. Critically, not running means no DELETE executes, so there is **no data-loss path**; no security exposure, no user-facing correctness break. Contrast genuine P0s in this repo (#1058 SMTP 100% failure, #1062 IDOR).

Real, structural, worth fixing this cycle — the cross-cluster dependency (P1#13 owed ledger × P2#27 cron silent 5xx) genuinely went unexamined, and the remediation-completeness angle is sound. P1, not P0.

### P1-41. [railway cron 관측 신뢰성 ↔ owed 원장] `-f` 부재는 이미 코드 주석에 명시적으로 인지돼 있었고, 선택된 완화(startup 경고)가 실제 발생 중인 실패 모드를 덮지 못함

- **위치**: `src/main.py:192`
- **주장**: `src/main.py:192` 주석은 'railway.toml cron 의 curl 은 -f 없이 성공 종료해 운영자가 인지하기 어렵다 → startup 경고(#15)' 라고 **결함을 정확히 서술** 한다. 그러나 그 경고는 `main.py:189` 의 `not (settings.internal_cron_api_key or "").strip()` 조건 — 즉 **키 미설정(503)** 일 때만 발화한다. F1 시나리오는 키가 **설정되어 있으나 확장 실패로 불일치(401)** 이므로 경고는 침묵한다. '왜 반복되는가' 의 구조적 원인: remediation 이 finding 에 적힌 실패 모드(미설정)에만 스코프되고, **관측 가능성 자체(curl exit code)** 라는 근본 원인은 인지된 채로 미수정 잔존했다.
- **근거**: `grep -n` 실측 — `src/main.py:189` 조건절, `:192` 주석(`-f` 부재 명시), `:197` 경고 문구 'will return 503 and never run'(503 단일 모드만 언급). 401·5xx·타임아웃 경로 커버 0. `tests/unit/test_main.py:247,267,302` 도 설정/미설정 2 분기만 단언.
- **권고**: 근본 수정(`-f`)을 완화(startup 경고)의 **대체재로 쓰지 말 것**. 회고 remediation 등록 시 '인지된 결함을 완화로 종결' 항목은 별도 태그로 표시하고, 완화가 커버하는 실패 모드를 명시(여기서는 '503 only')해 잔여 모드가 보이게 할 것.
- **cross-verify**: CONFIRMED — All cited locations verified by grep with exact content match. src/main.py:189 gates the warning on `not (settings.internal_cron_api_key or "").strip()` — i.e. key-unset only. src/main.py:192 comment explicitly names the root cause ("railway.toml cron 의 curl 은 -f 없이 성공 종료해 운영자가 인지하기 어렵다"). src/main.py:197 warning text says only "will return 503 and never run". src/api/internal_cron.py confirms two distinct failure modes: 503 at :46 (unset) vs 401 at :54 (mismatch, secure_str_compare) — the warning covers exactly one. tests/unit/test_main.py:247/267/302 assert only unset/set/dev branches; no 401, 5xx, or timeout coverage.

Attempted and failed to refute via compensating controls: grep for last_run|heartbeat|cron_run across src/ returns zero (no last-run tracking); `curl -f`/`--fail` appears nowhere in railway.toml (all 5 cronJobs use bare `curl -s`); docs/runbooks/operational-smoke-checks.md policy-13 smoke check covers /health, /auth/github, /login, /webhooks/github but omits /api/internal/cron/*. No detection path exists at any layer, so the finding survives.

Independent corroboration that F1 is live rather than hypothetical (noted, not asserted as proven): all 5 cron commands single-quote the header as -H 'X-API-Key: $INTERNAL_CRON_API_KEY'. POSIX sh suppresses expansion inside single quotes, which would send the literal string and yield a permanent 401. Whether Railway interpolates before exec is undeterminable from the repo — and that undeterminability is precisely the defect: nothing distinguishes "cron healthy" from "cron 401-ing every 60s".

Blast radius: retry-pending-merges runs * * * * *, and per the R13 finding native auto-merge has enabled 0 times in operational history, making the retry queue the sole production merge path.

Severity held at P1, neither raised nor lowered. Not P0: no data loss, no security exposure, no confirmed active outage, and merge stalls eventually surface as user-visible un-merged PRs. Not P2: silent failure across five jobs including the only production merge path, with the root cause documented in-code and left unfixed.

Structural cause (answers "why does this recur"): remediation was scoped to the failure mode named in the finding text (unset key) rather than the root cause named in the adjacent comment (unobservable curl exit code). A `-f` flag or last_run_at heartbeat covers 503/401/5xx/timeout in one change; the startup warning covers 1 of 4 and cannot cover the rest by construction.

### P1-42. [railway cron 관측 신뢰성 ↔ owed 원장] `scan-security` 는 문서상 'cron 6종' 이지만 railway.toml 에 스케줄 항목 자체가 없음 — 배선 없는 cron

- **위치**: `docs/reference/env-vars.md:40`
- **주장**: `docs/reference/env-vars.md:40` 과 `docs/architecture.md:118` 은 cron 을 **6종** 으로 기술하고 `scan-security` 를 'Code/Secret Scanning 폴링' 으로 명시한다. 라우트도 `src/api/internal_cron.py:103` 에 실재한다. 그러나 `railway.toml` 의 `[[deploy.cronJobs]]` 는 **5개뿐** 이고 `scan-security` 항목이 없어 **한 번도 스케줄된 적이 없다**. #1083 dead-code 가드가 잡는 '호출자 0' 과 동일 계열 결함이지만, 트리거가 인프라 설정에 있어 가드 사각지대(F4)에 정확히 해당한다.
- **근거**: `grep -o "cron/[a-z-]*" railway.toml | sort -u` → retention-sweep·retry-pending-merges·sweep-orphans·trend·weekly (5종, scan-security 부재). `grep -n "@router.post" src/api/internal_cron.py` → `:69 weekly :86 trend :103 scan-security :120 retry-pending-merges :139 sweep-orphans :153 retention-sweep` (6종). `grep -rn "scan-security"` 전체 → 문서 언급만, 스케줄 정의 0건.
- **권고**: 의도 확인 후 택1 — (a) 운영 필요 시 `[[deploy.cronJobs]]` 항목 추가 (b) 불필요 시 env-vars.md:40 의 'cron 6종' → 5종 정정 + architecture.md:118 에 '수동 트리거 전용' 표기. F4 의 양방향 일치 가드가 재발을 봉인.
- **cross-verify**: CONFIRMED — CONFIRMED at P1 — citations exact, and independent verification strengthens the finding beyond the original claim.

CITATIONS VERIFIED: env-vars.md:40 literally reads "cron 6종 ... `scan-security`=Code/Secret Scanning 폴링"; architecture.md:118 lists scan-security among six routes; internal_cron.py:103 route exists; railway.toml has exactly 5 [[deploy.cronJobs]] (weekly, trend, retry-pending-merges, sweep-orphans, retention-sweep) with scan-security absent.

ALTERNATIVE TRIGGERS EXHAUSTED (finder did not do this): (1) railway.toml:59+ "Fallback B" comment lists only weekly+trend — does not rescue it; (2) no GitHub Actions scheduler — `grep -rn "internal/cron" .github/` returns empty; (3) no webhook ingestion — zero code_scanning/secret_scanning/security_alert handlers in src/webhook/ or src/api/hook.py.

CLOSED UNREACHABLE CHAIN: upsert_alert_log (sole ingestion writer, security_alert_log_repo.py:32) <- security_scan_service.py:163 (only caller) ; scan_all_repos <- internal_cron.py:115 (only caller) <- ZERO schedulers. The ingestion path has never executed in production.

CONSEQUENCE IS WORSE THAN "DEAD CODE": dashboard_service.py:1009-1017 READS this never-populated table (list_pending, count_by_classification, total_alerts). The security panel does not fail visibly — it renders a confident "0 alerts / nothing pending" to the operator. That is false reassurance on a security surface and silently undercuts policy 14 (standing per-cycle Code Scanning check mandate). Four docs assert the feature is live (env-vars.md:40, architecture.md:118, README.md:502, README.ko.md:560).

COUNTER-ARGUMENTS CONSIDERED AND REJECTED: (a) "intentionally manual/on-demand" — no runbook documents manual invocation, and env-vars.md:40 asserts all six are key-gated crons; (b) "just docs drift, fix docs to say 5종" — wrong remediation direction, the dashboard read path proves the feature was intended live, so the gap is infra not docs; (c) "P2, nothing crashes" — silent-zero on security is the fail-open pattern this repo has repeatedly sealed (cf. #804 fail-CLOSED precedent).

SEVERITY HELD AT P1, NOT INFLATED TO P0: GHAS has 403/404 graceful degradation so real alert volume may be zero on the user's repos, and the user manually checks the Security tab per policy 14 — a human backstop exists. No data loss or outage.

GUARD-GAP CONFIRMED (answers the retro's "guard of guards" question): tests/unit/api/test_internal_cron_security.py only asserts 401-without-key — it tests the route, never that anything invokes it. check_dead_code.py (#1083) walks Python AST, so a caller residing in railway.toml is structurally invisible. This is precisely the F4 blind spot and it GENERALIZES: any route whose sole trigger is infra config. Suggested remediation is two-part — (1) add the missing [[deploy.cronJobs]] entry (not a docs edit), (2) add a cross-artifact parity guard asserting every @router.post in internal_cron.py has a matching cron/<name> in railway.toml, which would have caught this at turn 0 and closes the class.

### P1-43. [remediation 완결성 / 재발방지 도구 자기유지] P1#13 조치가 원장 파일(artifact)만 만들고 retro 가 명시한 구동 메커니즘(trailing sync PR body §owed-verification 표)을 한 번도 배선하지 않음 — 0/2

- **위치**: `docs/_archive/reports/2026-07-18-retrospective.md:73`
- **주장**: 회고가 지정한 조치는 '원장 파일 신설'이 아니라 'trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치'였다. 원장 신설(#1084, 14:38) 이후 머지된 trailing sync PR 2건(#1087 15:15, #1093 18:32) 어느 쪽 본문에도 owed/verification/검증 원장 언급이 0건이다. 즉 원장은 만들어졌으나 원장을 채우는 메커니즘은 단 한 번도 실행되지 않았다. 이것이 '행 추가 0건'의 직접 원인이며, 원장 stale 은 증상이고 메커니즘 미배선이 근본이다. 구조적 원인은 remediation 완료 판정 기준이 '산출물 존재'(파일이 생겼는가)이지 '메커니즘 실행'(다음 사이클에 실제로 작동했는가)이 아니라는 점이다 — 이번 세션이 P0 로 진단해 #1080 으로 기계화한 카덴스 트리거(#1028 문서-only 자기위반)와 완전히 동일한 실패 형태가, 같은 회고의 형제 조치에서 그대로 반복됐다.
- **근거**: docs/_archive/reports/2026-07-18-retrospective.md:73 — '**조치**: trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치 (`| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |`)'. `gh pr view 1087 --json body` / `gh pr view 1093 --json body` grep -i 'owed|검증 원장|verification' → 양쪽 모두 '## 검증 / Verification'(무관한 자체 검증 섹션) 1행만 매치, §owed-verification 표 0건. docs/runbooks/owed-verification.md:5 작성 규칙도 '(trailing sync PR body 의 §owed-verification 표와 페어)'로 페어 관계를 명문화하고 있으나 페어 반대편이 부재.
- **권고**: 원장 갱신을 PR 본문 규율이 아니라 trailing sync PR 의 기계 체크로 승격. `check_docs_sync.py` 가 이미 CI+pre-commit 이중 배선된 자리에 owed 행 currency 검사를 얹거나(권장), 최소한 STATE.md 를 건드리는 커밋에서 owed-verification.md 미동반 시 loud advisory. 아울러 remediation 완료 판정 기준을 '산출물 존재'에서 '다음 사이클 1회 실행 실측'으로 바꿔 회고 조치 항목마다 '무엇이 실행되면 이 조치가 살아있다고 볼 수 있는가' 1줄을 강제.
- **cross-verify**: CONFIRMED — 인용 정확 + 핵심 주장 실측 확인. docs/_archive/reports/2026-07-18-retrospective.md:73 이 지정한 조치는 축자적으로 "trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치" (line 71 = 테마 G P1#13). 지정된 vehicle 전수 검사 결과 미배선 확정.

[실측 1 — 구동 메커니즘 0회] 원장 신설 #1084(05:38Z) 이후 머지된 trailing sync PR 은 #1087(06:15Z)·#1093(09:32Z) 2건. 양쪽 body 섹션 = 요약/갱신/검증/🔍사용자 검증 필요 4종뿐이고, owed|verification|검증 원장|미결 grep 매치는 무관한 자체 검증 섹션 헤더 "## 검증 / Verification" 1행뿐. 두 PR 의 §"🔍 사용자 검증 필요" 실내용은 각각 "문서/배지만 — 코드 동작 영향 0" 한 줄 = 표 0건. 특히 #1093 은 본문에 "이 세션 최종 sync (17 PR #1077~#1092 반영)" 로 자기 규정한 세션 종결 sync — 원장 자신의 작성 규칙(owed-verification.md:5 "세션/Phase 종료 시 … trailing sync PR body 의 §owed-verification 표와 페어")이 지목한 바로 그 시점에 페어 반대편 부재. 원장이 선언한 페어 관계가 직후 종결 sync 에서 그대로 불발.

[실측 2 — 행 추가 0건] git log --follow docs/runbooks/owed-verification.md = 커밋 2개뿐: e2098d3(#1084 신설), 7608656(#1088). #1088 diff 실측 = 1 insertion/1 deletion, 기존 #1058 행의 검증 방법 셀만 상세화 — 신규 행 0. 세션 후속 5 PR(#1089~#1092) 어느 것도 원장 미갱신. "원장은 만들어졌으나 채우는 메커니즘 미실행" 확인.

[반증 시도 — 부분 반례 있으나 판정 불변] 회의적으로 반대 증거를 찾은 결과 2건: (a) #1094(미머지) §"🔍 사용자 검증 필요" 항목 2 가 "owed 원장 6건 회신 대기 중" + 안전등급 2건(#1058·#1062) 정책 5 NEW-P0-N 매 사이클 회신 의무 명시 + 런북 경로 안내 — 표면화가 1회 발생. (b) #1088 body "사용자 지적: #1058 '어떤 메일' 미상세" = 원장에 대한 사용자 round-trip 실재 → 원장이 완전 inert 하다는 강한 형태는 성립 안 함. 그러나 둘 다 지정 vehicle(trailing sync PR)이 아니고 #1094 는 미머지 상태 ad-hoc 표면화 — 회고가 요구한 것은 저자 기억 의존 없는 "상시 배치" 규약이므로 관례 미확립 판정 유지. 따라서 finding 의 "한 번도 배선 안 됨"은 지정 메커니즘 기준 정확하나, "원장이 기록만 한다"는 함의는 위 (a)(b) 만큼 과대 — 이 정정만 부기.

[P1 유지 근거] 강등 검토했으나 유지. (i) 미표면화 6건 중 2건이 안전/데이터 등급(#1058 = 출시 이래 SMTP 100% 실패 복구 미실증, #1062 = IDOR 과잉차단)으로 정책 5 NEW-P0-N 매 사이클 회신 의무 영역이며 메모리 feedback-stale-blocker-policy("머지 대기 누적 금지")가 이미 경고한 패턴. (ii) 구조적 진단이 타당 — remediation 완료 판정 기준이 '산출물 존재'이지 '메커니즘 실행'이 아니라는 점이, 같은 세션이 P0 로 진단해 #1080 으로 기계화한 카덴스 트리거(#1028 문서-only 자기위반)와 동일 실패 형태로 형제 조치에서 반복됨. 문서-only 조치의 3번째 사례. 단 경과 시간이 ~4시간으로 짧아 "6건 전부 ⏳" 자체는 실패의 약한 증거이므로, 판정 근거는 ⏳ 누적이 아니라 지정 vehicle 2/2 미배선 + 행 추가 0건에 둔다. 시사 조치 = 표 배치를 문서 규약이 아닌 기계 가드로 승격(예: trailing sync PR 판정 시 원장 미결 행 존재하면 body 표 부재를 CI/훅에서 fail) — 그렇지 않으면 #1028 과 동일 경로로 다음 측정창에서 재위반 예상.

### P1-44. [기계 가드 부재 / 가드의 가드] 원장 currency 는 가드 0인데 저위험 형제(STATE/배지)는 pre-commit + CI 이중 강제 — 강제력이 위험도와 역상관

- **위치**: `.github/workflows/ci.yml:128`
- **주장**: `check_docs_sync.py` 는 pre-commit(.pre-commit-config.yaml:69)과 CI(ci.yml:128)에 이중 배선돼 STATE 수치·README 배지 drift 를 차단한다. 반면 owed-verification.md 를 참조하는 .py/.yml/hook 은 전 저장소에 0건이며(grep 결과 매치는 전부 산문 문서: operational-smoke-checks.md:6, STATE.md:15, cycle-history.md:156, 회고 보고서), 원장 currency 를 검사하는 기계 신호가 전무하다. 강제력 배분이 위험도와 역상관이다 — STATE 배지 drift 는 자기교정적이고 가시적이며 최악이 숫자 오표기인 반면, 원장 stale 은 비가시적이고 '출시 이래 100% 실패였던 SMTP(#1058)가 실제로 복구됐는지'와 'IDOR 차단이 정상 사용자를 오차단하는지(#1062)'라는 안전/데이터 등급 신호를 소리 없이 썩힌다. 이 세션이 문서-only 정책의 무력함을 P0 로 진단하고 기계화(#1080)한 직후에, 같은 세션에서 만든 원장을 문서-only 로 남긴 것이 자기위반이다.
- **근거**: .pre-commit-config.yaml:69 `entry: python scripts/check_docs_sync.py`; .github/workflows/ci.yml:128-129 'STATE↔README 배지 수치 정합 (check_docs_sync)' / `run: python scripts/check_docs_sync.py`. `grep -rn 'owed-verification' --include=*.py --include=*.yml --include=*.json --include=*.mjs .` → 0건(산문 .md 만 매치). docs/runbooks/owed-verification.md:15 #1058 = '출시 이래 100% 실패', :16 #1062 = IDOR 과잉차단, 둘 다 '🔴 안전/데이터 등급 (다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N)'(:11) 섹션인데 9회 머지 동안 ⏳ 고정.
- **권고**: `scripts/check_owed_currency.py` 신설 — 원장의 안전/데이터 등급 행이 ⏳ 인 채로 머지 N건 경과 시 loud advisory(check_retro_cadence 와 동일 advisory·비차단 패턴). 정책 5 NEW-P0-N 이 '매 사이클 회신 의무'를 이미 규정하므로 기계 신호는 그 정책의 집행부일 뿐 신규 정책이 아니다.
- **cross-verify**: CONFIRMED — All cited lines verified verbatim. .pre-commit-config.yaml:69 = `entry: python scripts/check_docs_sync.py`; .github/workflows/ci.yml:128-129 = `STATE↔README 배지 수치 정합 (check_docs_sync)` / `run: python scripts/check_docs_sync.py` — dual pre-commit + CI enforcement confirmed. `grep -rn 'owed-verification'` across .py/.yml/.yaml/.json/.mjs/.js/.sh/.toml returns 0 hits; all 5 repo matches are prose .md (operational-smoke-checks.md:6, STATE.md:15, cycle-history.md:156, owed-verification.md:5, 2026-07-18-retrospective.md:73). Ledger content confirmed: :11 = 🔴 안전/데이터 등급 header, :15 #1058 SMTP '출시 이래 100% 실패', :16 #1062 IDOR 과잉차단, all 6 rows ⏳. The enforcement-vs-risk inversion is real as stated.

Two sub-claims I probed independently. (a) OVERSTATED — '9회 머지 동안 ⏳ 고정' implies observed decay, but #1085~#1093 all merged the same day as the ledger's creation (#1084), before any user reply window opened. Nothing has rotted yet; harm is prospective. (b) A stronger objection I raised and then rejected: check_docs_sync guards a machine-checkable internal invariant (STATE number == README badge number), whereas ⏳→✅ requires human operational observation no script can perform, so 'equal enforcement' is impossible in kind. This objection fails because the correct remedy is not 'machine verifies SMTP works' but 'machine surfaces that open safety-grade rows exist' — precisely the check_retro_cadence.py (#1080) pattern built in this same session (advisory, non-blocking, counts and warns). The remedy is precedented, ~30 lines, and has a working template in scripts/.

P1 sustained rather than adjusted down, on evidence the finding did not cite: this repo has a materialized prior incident of exactly this failure mode. 정책 5 NEW-P0-N exists because of 사이클 78, where a safety-grade item awaiting user action accumulated 4 cycles unnoticed → 운영 사고 위험 누적 (memory: feedback-stale-blocker-policy.md, '머지 대기 4사이클 누적 금지'). The ledger's two 🔴 rows are explicitly tagged 정책 5 NEW-P0-N — a per-cycle mandatory-reply obligation with zero mechanical trigger, structurally identical to #1028 whose doc-only trigger self-violated within one measurement window (repo base rate for doc-only obligations: 2 documented failures). Creating a new doc-only mechanism in the same session that diagnosed doc-only enforcement as P0 is a valid self-violation finding. Not P0 (no runtime/user-facing defect; ledger rot delays confirmation of shipped fixes rather than causing them). Not P2 (documented prior incident + safety-grade scope exceeds hygiene). Recommended action: advisory script mirroring check_retro_cadence.py that fails loud when 🔴-section rows remain ⏳, wired into the 작업 시작 전 필수 체크리스트 alongside the existing cadence counter.

### P1-45. [disposition traceability] 회고 정본(confirmed[] 61건)이 저장소 밖 ephemeral 산출물에만 존재 — 워크플로우·런북 계약이 구조적 원인

- **위치**: `.claude/workflows/retrospective.mjs:307`
- **주장**: 5+1 회고의 유일한 건별 기록(file/line/claim/evidence/recommendation 원문)인 `confirmed[]` 배열이 저장소에 아카이브되지 않는다. 두 워크플로우 모두 리포트 파일 작성을 호출자에게 위임하고, 호출자 스펙(런북·스킬)은 '클러스터 요약'만 요구하므로 건별 정본이 리포트 작성 경계에서 체계적으로 폐기된다. 이는 인스턴스 실수가 아니라 계약 결함이다.
- **근거**: `.claude/workflows/retrospective.mjs:307` = `// Report (returns structured data — writing the report file is the caller/skill's job)`. 동형 결함이 peer 워크플로우에도 존재: `.claude/workflows/integrity-audit.mjs:327` = `// ── Report (구조화 데이터 반환 — 리포트 파일 작성은 호출자 책임) ──`. 호출자 스펙은 요약만 요구: `docs/runbooks/retrospective.md:33` = '보고서 작성: docs/_archive/reports/YYYY-MM-DD-retrospective.md (ROI + verdict_coverage + 클러스터)', `.claude/skills/retrospective.md:20` = '(P0/P1/P2 + ROI + verdict_coverage 표)'. 결과: `docs/_archive/reports/2026-07-18-retrospective.md:93` 이 '전체 61 confirmed + recommendation 원문: 워크플로우 반환 JSON(wf_331cdddf-519) 참조' 라고 지시하나 `find . -name '*331cdddf*' -not -path './.git/*'` → 0건, `.gitignore` 에 wf_/workflow/journal 규칙도 0건(애초에 write 된 적 없음). 저장소 잔존물 = 11행 클러스터 표뿐.
- **권고**: 런북·스킬의 리포트 작성 의무에 `docs/_archive/reports/YYYY-MM-DD-retrospective-findings.json`(confirmed[] 원문 dump) 동반 아카이브를 추가하고, 리포트 본문은 wf ID 대신 그 상대경로를 인용한다. 정책 4(단언+가드 페어)에 따라 `scripts/check_retro_findings_archive.py` stdlib 가드 동반 — `*-retrospective.md` 존재 시 동일 날짜 `-findings.json` 부재면 fail. integrity-audit.mjs 에도 동일 적용(동형 결함).
- **cross-verify**: SEVERITY_ADJUST — REAL AND STRUCTURAL — all citations verified verbatim. retrospective.mjs:307 and integrity-audit.mjs:327 are exactly as quoted (both delegate report-writing to the caller); runbooks/retrospective.md:33 and skills/retrospective.md:20 request only ROI + verdict_coverage + cluster, never per-finding archival; reports/2026-07-18-retrospective.md:93 points at wf_331cdddf-519 which find(0 hits) shows does not exist, with no .gitignore wf_/journal rule.

EVIDENCE STRONGER THAN CLAIMED: grep -nE "writeFile|journal|wf_|appendFile|mkdir" on retrospective.mjs returns ZERO hits — the workflow has no persistence path at all. The confirmed[] payload is in-memory only; it was never written-then-excluded, it was never writable. Contract defect confirmed at the source, not just the caller.

SYSTEMATIC, NOT INSTANCE: across all three workflow-driven retros — 2026-06-23 (30 confirmed / 55 lines / 0 finding IDs), 2026-07-03 (66 confirmed / 108 lines / 0 IDs), 2026-07-18 (61 confirmed / 110 lines / 19 IDs) — ~157 confirmed findings left no per-finding record (file/line/claim/evidence/recommendation). Three consecutive occurrences with no counterexample rules out instance error and confirms the caller-boundary contract as cause. Self-demonstrating: this cycle's mandated question ("조치 선언됐으나 실제 부분 조치인 항목?") is unanswerable for the ~53/61 findings with no surviving record.

WHY P1, NOT P0: (a) No runtime, security, operational, or production-data impact — this is an audit-trail gap. This project reserves P0 for 운영 사고 차단 영역 (정책 5 NEW-P0-N), which carries a 매 사이클 진행 신호 회신 의무 escalation; routing a bookkeeping defect there dilutes the lane. (b) Partial secondary traceability survives: 8 finding IDs are cited in commit subjects (회고 P1#9/13, P2#4/17/18/36/41/43), the 27-row cluster table preserves themes, and actioned findings are permanently encoded in code/tests/rules docs — the fix IS the disposition record. Loss concentrates in the unactioned long tail, not the high-value P0/P1s. (c) Internal consistency: the same report flags "로드맵 tier 오분류 — 일괄 라벨이 관측성까지 과-게이팅" (P2#23·26) as a defect; grading this P0 would reproduce that exact over-classification.

WHY NOT P2: the repo actively asserts retrievability that does not exist (report:93 dangling pointer). A false assurance is worse than silence and is the same failure class this cycle just sealed in #1082/#1094 (guard green while blind). That aggravator holds it at P1.

REMEDIATION SHAPE: fix at the contract, not the instance — have the caller spec (runbook:33 + skill:20) require persisting confirmed[] verbatim to docs/_archive/reports/YYYY-MM-DD-retrospective-findings.json, or have the workflow write it directly (closing the same gap in integrity-audit.mjs:327, which is identically exposed). Pair with a guard asserting no report references a wf_ id absent from the repo (정책 4: 단언과 회귀 가드 동시 머지) — otherwise the dangling-pointer pattern recurs by construction.

### P1-46. [recurrence mechanism] 2026-07-03 이 도입한 '커버리지 카운트' 회계 라인이 2026-07-18 에서 소실 — 시정을 인스턴스에만 적용해 1 사이클 만에 증발

- **위치**: `docs/_archive/reports/2026-07-03-retrospective.md:23`
- **주장**: 동일 양식(회고 finding 미배정)이 2026-07-03 에 적발됐을 때의 시정은 그 리포트 본문에 커버리지 회계 1줄을 넣은 것이었다. 그 시정이 런북 템플릿으로 승격되지 않았기 때문에 다음 회고 작성 시 자연 소실됐고, 결과가 이번의 5건 완전 소실이다. '왜 반복되는가'의 직접적 기전은 산출물-수준 시정과 프로세스-수준 시정의 혼동이다.
- **근거**: `docs/_archive/reports/2026-07-03-retrospective.md:23` = '**커버리지 카운트**: 65건이 C1~C8 클러스터에 배정 + **#57(SEVERITY_ADJUST 자기교정)은 클러스터 비배정** → 문서 내 전건 참조 66/66, 클러스터 heading 커버리지 65/66' — 미배정 건을 명시적으로 회계 처리. 2026-07-18 리포트 대조: `grep -n -E "커버리지 카운트|배정" docs/_archive/reports/2026-07-18-retrospective.md` → **0건**. 그 사이 런북에도 반영 없음: `docs/runbooks/retrospective.md:33` 의 리포트 요구사항은 여전히 'ROI + verdict_coverage + 클러스터' 3항목뿐.
- **권고**: 커버리지 회계를 런북 리포트 필수 필드로 승격(`docs/runbooks/retrospective.md:33` 항목에 추가). 일반화 규칙: 회고 산출물 품질 결함의 시정은 **해당 리포트가 아니라 리포트를 만드는 스펙**에 가해야 한다 — 산출물 편집은 다음 산출물에 상속되지 않는다.
- **cross-verify**: CONFIRMED — 모든 인용 실측 검증 통과 + 인과 서사가 git provenance 로 오히려 보강됨.

**1. 인용 정확 (citation_verified=true)**
- `docs/_archive/reports/2026-07-03-retrospective.md:23` = `grep -n "커버리지 카운트"` → line 23 EXACT 일치. 본문도 주장대로 "65건 배정 + #57 비배정 → 문서 참조 66/66, heading 커버리지 65/66".
- 2026-07-18 리포트: `grep -n -E "커버리지 카운트|비배정|배정"` → **exit 1, 0건**. 소실 확인.
- `docs/runbooks/retrospective.md:33` = "보고서 작성: ... (ROI + verdict_coverage + 클러스터)" — 3항목뿐, 커버리지 회계 요구 없음. 승격 부재 확인.

**2. 인과 서사 = 주장보다 강하게 입증 (finder 가 제시 못한 증거)**
`git log -S "커버리지 카운트"` → PR #1025 커밋 a9338cf 내 **2번째 커밋 메시지가 문자 그대로**: `docs(retro): #57 커버리지 카운트 정밀화 — Codex mutual (d) 반영` / 본문 "**Codex mutual (a)(b)(c) PASS·(d) 표현 정밀도 반영**". 즉 이 1줄은 자발적 기록이 아니라 **외부 리뷰 지적에 대한 fix-up 시정**이 맞다. 내가 회의적으로 검증한 지점(=07-03 리포트 본문에 '미배정' 관련 finding 이 없어서 "시정" 프레이밍이 조작일 가능성)이 git 이력으로 해소됨 — 지적은 리포트 내부가 아니라 Codex mutual 에서 왔고, 시정은 **그 리포트 파일 1줄 편집으로만** 끝나 런북 템플릿에 미승격. 산출물-수준 vs 프로세스-수준 시정 혼동이라는 기전 진단 정확.

**3. 결과(“5건 완전 소실”) = 산술 실측 확인**
07-18 P2 표의 finding ID 전수 파싱(`P2#1·3·14` 형식 = 첫 항목만 prefix 라 순진한 regex 는 오파싱 — 교정 후 재측정): **참조 38 / 선언 43**, 미참조 = **P2 #5·#6·#11·#25·#35 정확히 5건**. 주장 수치와 일치. P1 은 반대로 전건 배정(테마 A~G 15/15) 이라 손실은 P2 국한.

**심각도 P1 유지 (조정 없음)**
- 상향(P0) 근거 아님: 운영 사고 0. 5건이 파괴된 것은 아니고 워크플로우 JSON(`wf_331cdddf-519`)에 잔존(리포트 line 93 이 fallback 으로 지목) — 복원 가능.
- 하향(P2) 거부: 07-18 세션의 fix 트랙은 **클러스터에서** 구성됐으므로 heading 미배정 5건은 트리아지 자체를 못 받음(=조치 검토 0). 아카이브 리포트가 durable 산출물이고 JSON 은 외부/휘발성. 07-18 자체 분류에서 동류(추적성·owed 미취합 테마 G)를 P1 로 둔 것과 정합.
- 부수 관측(과대주장 아님을 명시): 07-18 이 "전체 61 confirmed" 라 쓰면서 본문은 56건만 참조. 단 **verdict_coverage 1.0 은 반증되지 않음** — 그것은 워크플로우 verdict 수신률이지 리포트 heading 커버리지가 아니며, 07-03:23 이 바로 그 둘을 구분하려고 존재했던 라인이다. 그 구분 장치가 사라진 것이 본 finding 의 핵심.

**중복성 검토(세션 "재보고 말 것" 지시 대조)**: 이미 식별된 학습 #1(카덴스 트리거 문서-only 자기위반)과 "문서-only 시정 한계"라는 상위 패턴은 공유하나, 산출물(리포트 본문 vs 정책 문서)·기전(템플릿 미승격 vs 기계 강제 부재)·결과(finding 5건 트리아지 누락 vs 카덴스 위반)가 모두 달라 별건. 세션이 요구한 "왜 반복되는가의 구조적 원인"에 직접 응답.

**시정 벡터**: `docs/runbooks/retrospective.md:33` 요구항목을 4항목으로 확장 — "ROI + verdict_coverage + 클러스터 + **클러스터 heading 커버리지 N/M + 미배정 finding ID 명시 열거**". 정책 4(단언+가드 동일 PR) 정신대로 리포트 생성 시 미배정 ID 를 산술 검출하는 가드 동반 권장(본 검증에 쓴 파싱 로직이 그대로 가드가 됨).

### P1-47. [자초 CodeQL 재발 — 구조적 원인] check_noqa_sideeffect.py 의 자체 처방이 다음 alert 를 재생산 — 튜플 패턴을 loud-fail read 없이 안내(alert #546 와 동형)

- **주장**: 자초 CodeQL 3회 재발의 구조적 원인은 "관용구 복사" 보다 한 단계 깊다 — **처방 자체가 검증된 정본보다 잘린 사본**이라는 점이다. `check_noqa_sideeffect.py` 는 py/unused-import 를 차단한 뒤 개발자에게 `_FK_TARGET_MODELS = (Model,)` 를 쓰라고 안내하는데(line 110), 이 bare 형태가 정확히 alert **#546 `py/unused-global-variable` (tests/unit/ui/test_repo_detail_query.py:42)** 를 자초해 이 창 안에서 #1079 로 별도 수습된 형태다. 즉 turn-0 가드가 성공적으로 차단한 개발자가 가드의 안내를 그대로 따르면 alert 계열만 py/unused-import → py/unused-global-variable 로 바뀐 채 재발한다. `.claude/rules/testing.md` 에는 `if any(...): raise RuntimeError(...)` loud-fail read 를 포함한 완전한 정본이 있으나, 개발자가 실제로 마주치는 turn-0 출력에는 없다. "CodeQL 룰 계열이 아직 남아 있는가" 라는 질문의 답은 예이며, 그 유입 경로는 신규 룰이 아니라 **가드 자신의 처방 문구**다.
- **근거**: scripts/check_noqa_sideeffect.py:110 = `print("  _FK_TARGET_MODELS = (Model,)  # CodeQL 도 'used' 로 인식 + import 소실 시 loud-fail")` (loud-fail 을 문구로만 언급, read 코드 미제시). 같은 파일 line 8 docstring 도 동일하게 절단. 실측 alert 이력: `gh api code-scanning/alerts` → `546 fixed py/unused-global-variable tests/unit/ui/test_repo_detail_query.py:42` (#1077 튜플 도입 → #1079 `dd8d87e fix(test): _FK_TARGET_MODELS loud-fail read` 로 해소). 정본은 .claude/rules/testing.md 의 `_FK_TARGET_MODELS = (User,)` + `if any(m.__tablename__ not in Base.metadata.tables ...): raise RuntimeError(...)` 3줄 블록.
- **권고**: 가드 출력의 처방을 정본과 동일한 3줄 블록으로 교체하고(`_FK_TARGET_MODELS = (Model,)` + loud-fail read + 사유 주석), 처방 문자열이 testing.md 정본과 drift 하지 않도록 parity 테스트를 건다(정책 4 단언+가드 페어, 정책 16 공유 로직 grep 전수와 동형). 일반화: **재발 방지 가드는 차단만이 아니라 처방을 배포한다 — 처방도 SSOT 대조 대상**이라는 원칙을 rules 에 명문화.
- **cross-verify**: CONFIRMED — All cited evidence verified exactly, and the underlying mechanism is demonstrated (not hypothetical) twice over.

VERIFIED CITATIONS: (1) scripts/check_noqa_sideeffect.py:110 is verbatim `print("  _FK_TARGET_MODELS = (Model,)  # CodeQL 도 'used' 로 인식 + import 소실 시 loud-fail")` — the bare tuple with no read; docstring line 8 is identically truncated. (2) `gh api code-scanning/alerts` returns `546 fixed py/unused-global-variable tests/unit/ui/test_repo_detail_query.py:42`. (3) .claude/rules/testing.md:35-37 holds the complete canonical block including `if any(m.__tablename__ not in Base.metadata.tables ...): raise RuntimeError(...)`. (4) Git confirms the causal chain: dc14e18 (#1077) added the bare tuple with no read; #546 fired; dd8d87e (#1079) added the loud-fail read and cleared it.

EVIDENCE STRONGER THAN CLAIMED — two additional findings:
(a) The identical failure has fired TWICE, not once. Full py/unused-global-variable history: `515 fixed tests/unit/test_migration_completeness.py:50` (the pattern's original precedent) and `546` (its latest copy). alembic/env.py:50-51 explicitly documents the read as the fix for that class — "이어지는 단언이 튜플을 실제로 읽어 py/unused-global-variable(상수 고아화, #515 류)도 함께 회피". The read is known to be load-bearing.
(b) Every canonical instance in the repo carries the read — alembic/env.py:56-67, test_dashboard_service.py:34-36, test_dashboard_service_user_id_filter.py:70-72, test_repo_detail_query.py:45-47, testing.md:35-37. The single bare prescription in the entire repo is the guard's own turn-0 output, i.e. exactly the surface a blocked developer reads.

AGGRAVATING (answers the session's "guard of the guard" question): tests/unit/scripts/test_check_noqa_sideeffect.py has NO assertion on fix-message content (grep for Fix|해결|loud-fail|message|capsys returns nothing). Its only pattern check (line 138) asserts that testing.md documents the tuple — never that the guard's own prescription matches the canonical form. The remediation text is wholly untested, so this is a #1094-class defect: the guard passes green while its prescription is wrong.

SKEPTICAL COUNTERS WEIGHED AND REJECTED: line 111 points to test_repo_detail_query.py, which post-#1079 is correct — but that is recovery, not prevention, and the inline snippet is what gets copied (the very idiom-drift mechanism at issue). Worse, the line-110 comment ASSERTS `import 소실 시 loud-fail`, a property the shown code lacks; that is not mere omission but a false claim that would reasonably stop a developer from reading further. Also considered whether the bare tuple only sometimes alerts — refuted: it alerted at both #515 and #546, and no pre-merge linter catches unused module-level globals (flake8 ignores them; pylint's unused-variable is function-scoped), so it surfaces only on main full scan, matching #546's actual history.

SEVERITY HELD AT P1: no runtime/security/data impact and the fix is ~3 lines, but #1081 was built specifically to end reactive CodeQL fix PRs, and this is the mechanism by which that P1 theme survives its own remediation. P2 would frame it as cosmetic when it is a defect in the remediation itself — precisely the "partial remediation" category under review. Fix: replace lines 110 and 8 with the full 3-line testing.md block, and add a positive-control test asserting the guard's fix message contains the `raise RuntimeError` read.

### P1-48. [remediation 완결성 — owed 원장 운영] owed 원장(#1084)이 강제력 0 의 문서-only 산출물 — 회고 P0 근본(문서-only 시정 2회 실패)을 같은 세션의 자기 처방에 미적용

- **주장**: 이 회고의 P0 는 "회고 카덴스 트리거가 문서-only 라 첫 측정창에서 자기위반" 이었고 시정은 기계 카운터 신설이었다. 그런데 같은 세션의 Track D 산출물인 owed 원장은 **정확히 같은 형식(문서-only)** 으로 만들어졌다. `owed-verification.md` 는 CLAUDE.md 체크리스트·스크립트·CI·훅·테스트 어디에서도 참조되지 않는다 — `grep -rn "owed-verification" CLAUDE.md scripts/ .github/ .claude/ tests/` 결과 **0건**. 대조적으로 카덴스 카운터는 CLAUDE.md:320 세션시작 체크리스트에 배선돼 있다. 원장은 회신을 유도하는 메커니즘이 아니라 기록 장치이며, 이미 증상이 나타났다: 6행 전부 ⏳ 이고 그중 2행(#1058 SMTP·#1062 IDOR)은 정책 5 NEW-P0-N "매 사이클 회신 의무" 등급이다. 메모리 `feedback-stale-blocker-policy.md`(스테일 블로커 4사이클 누적 금지)가 경고한 패턴의 재유입 경로다.
- **근거**: `grep -rn "owed-verification" CLAUDE.md scripts/ .github/ .claude/ tests/` → 매치 0 (참조는 docs/STATE.md:15 와 메모리 본문뿐 — 둘 다 수동 서사). CLAUDE.md:320 `python scripts/check_retro_cadence.py  # 🔴 회고 카덴스 기계 카운터` (대조군: 배선됨). docs/runbooks/owed-verification.md:15,16 (안전등급 #1058·#1062 모두 상태 `⏳`), :22-25 (운영등급 #1071·#1072·#1073·#1075 모두 `⏳`) = 6/6 미회신. 같은 파일 line 5 가 "세션/Phase 종료 시 ... 추가한다" 로 인지 의존을 명시.
- **권고**: 카덴스 카운터와 동형의 최소 기계화: `scripts/check_owed_verification.py` — owed-verification.md 의 ⏳ 행 수와 최고 등급(안전/운영)을 파싱해 세션시작 체크리스트에서 loud 출력(advisory·exit 0, 정책 17 안정성). 안전등급 ⏳ 가 1건이라도 있으면 배너에 정책 5 NEW-P0-N 회신 의무를 명시. 원장 신설 PR 이 이 배선을 동반하지 않은 것은 정책 4(단언과 회귀 가드를 같은 PR 에) 자기위반이며, 이 진단 자체를 메모리에 남겨야 다음 세션이 세 번째 문서-only 시정을 반복하지 않는다.
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인. (1) `grep -rn "owed-verification" CLAUDE.md scripts/ .github/ .claude/ tests/` → 매치 0건(exit 1) — 원장은 어떤 강제 경로에도 미배선. (2) CLAUDE.md:320 `python scripts/check_retro_cadence.py` 배선 확인(대조군). (3) docs/runbooks/owed-verification.md:15,16 = #1058·#1062 모두 `⏳`, line 11 헤더가 "다음 세션 진입 전 명시 회신 의무 — 정책 5 NEW-P0-N" 등급 선언. (4) :22-25 = #1071·#1072·#1073·#1075 모두 `⏳` → 6/6 미회신. (5) line 5 "세션/Phase 종료 시 … 추가한다" = 인지 의존 명시.

보고자가 제시하지 않은 결정적 증거를 추가 발견: `tests/unit/scripts/test_check_retro_cadence.py:150-159` 가 CLAUDE.md 배선 존재를 단언하며 docstring 에 "스크립트만 있고 체크리스트 미배선이면 다시 인지 의존이 된다" 를 명시. 즉 **같은 세션이 "미배선 = 인지 의존 = 문서-only 재발" 원칙을 명시적으로 언어화하고 한 산출물에는 회귀 가드까지 붙인 뒤, 같은 세션의 다른 산출물(원장)에는 미적용**. 인지 못 한 누락이 아니라 보유한 원칙의 비적용 — 지적의 핵심 주장이 원 보고보다 강하게 성립.

단, 보고 근거 중 1건은 부당하므로 상위 전파 금지: "이미 증상이 나타났다: 6행 전부 ⏳" — 파일 mtime 07-18 17:51 로 생성 ~1일·경과 세션 0. day-0 시점의 6/6 ⏳ 는 기대되는 초기 상태이지 실패 증상이 아님. 심각도는 구조적 논거만으로 판단해야 하며, 그것만으로 성립.

P1 유지 근거(반론 검토 후): 반론 (a) "사용자 물리 행위(수신함 확인·Railway 로그)는 기계화 불가" 는 지적을 무력화하지 못함 — Claude 측 실패 모드는 "사용자 미회신" 이 아니라 "Claude 가 세션 진입 시 재부상시키지 않음" 이고, 원장은 PR 번호·상태 컬럼을 가진 구조화 표라 ⏳ 행 수·경과를 파싱해 세션 시작에 loud-warn 하는 것은 카덴스 카운터와 동형으로 명백히 가능. 반론 (b) "신설 추적물에 강제력까지 요구는 가혹" 도 약함 — 원장 자신의 line 11 이 "다음 세션 진입 전" 을 기한으로 못박았는데 세션 진입 시점에 이를 발화시키는 장치가 전무하고, `.claude/hooks/` 에 SessionStart 훅이 없어 CLAUDE.md 체크리스트가 유일한 세션 진입 표면 → 수정 비용은 같은 체크리스트 1줄. 실패 모드는 메모리 `feedback-stale-blocker-policy.md`(4사이클 스테일 누적 금지)로 선례화됨. #1058 은 출시 이래 100% 실패였던 이메일 발송의 복구 미증명이라 운영 실질 위험(부기 사안 아님).

### P1-49. [self-inflicted CodeQL — 클래스 차단 부재] CodeQL 은 이미 PR 마다 돌고 있다 — note 심각도라 SUCCESS 로 통과할 뿐. 클래스 게이트는 '부재'가 아니라 '임계값 미설정'

- **위치**: `.github/workflows/codeql.yml:6`
- **주장**: 4회 반복된 bespoke 가드 트레드밀 전체가, GitHub 가 이미 모든 PR 에서 실행 중인 검사를 stdlib Python 으로 룰 하나씩 재구현한 것이다. `.github/workflows/codeql.yml:6-7` 은 `pull_request: branches: [main]` 트리거를 갖고 `:35` 에서 `security-and-quality` 룰셋(py/unused-import·py/empty-except 포함)을 로드한다. 즉 자초 alert 는 **머지 전에 이미 탐지되고 있었다**. 차단되지 않는 이유는 단 하나 — 이 룰들이 전부 `note` 심각도이고, code scanning PR 체크의 기본 실패 임계값이 `error` 이기 때문이다. 따라서 클래스 차원 차단은 새 도구를 만드는 문제가 아니라 임계값 한 줄의 문제다.
- **근거**: (1) 자초 alert 12건(#538~#549) 전부 `most_recent_instance.ref = refs/heads/main` — PR ref 에서 생성된 alert 는 0건. (2) `gh pr view 1081/1082 --json statusCheckRollup` → `CodeQL SUCCESS` + `Analyze (python) SUCCESS`. 그런데 바로 이 두 PR 이 #547(check_noqa_sideeffect.py:118)·#548(posttool_pytest_smoke.py:111)을 만들었고 머지 몇 시간 뒤 main 스캔에서 표면화됐다. (3) `gh api .../branches/main/protection` → 404 Branch not protected — required check 도 없어 이중으로 무해화. (4) 전 alert 의 `rule.severity = note`, `security_severity_level = null`.
- **권고**: 룰별 가드 추가를 중단하고 임계값을 올린다. 이식성 있는 방법: `codeql-action/analyze` 에 `output: sarif-results` 를 주고 후속 step 에서 `python -c` 로 SARIF `runs[].results` 를 파싱해 PR diff 파일에 결과가 하나라도 있으면 exit 1. 대안: repo Settings → Code security → Code scanning → check failure severity 를 note 포함으로 상향. 어느 쪽이든 **모든 CodeQL 룰**을 한 번에 덮으므로 check_dual_import·check_noqa_sideeffect·check_empty_except 세 bespoke 가드가 불필요해지고, 아직 터지지 않은 룰(py/mixed-returns·py/ineffectual-statement 등 이미 전례 있음)도 선제 차단된다.
- **cross-verify**: SEVERITY_ADJUST — CORE DIAGNOSIS CONFIRMED — and proven harder than the finding argued. Citation verified: codeql.yml:6-7 = `pull_request: branches:[main]`, :35 = `+security-extended,security-and-quality`. Verified independently: (a) all 25 self-inflicted alerts #525~#549 are `severity=note` / `security_severity_level=null`, zero exceptions; (b) PR #1081/#1082 rollup shows `CodeQL | success | app=github-advanced-security` — the GHAS alert-gating check, not merely the workflow job; (c) DECISIVE — `code-scanning/analyses?ref=refs/pull/1081/merge` returns `results=1` and alert #547 IS queryable at `refs/pull/1081/merge`. CodeQL detected the exact alert pre-merge, uploaded it, and passed. (d) `scripts/check_dual_import.py:2` self-documents as "CodeQL py/import-and-import-from self-inflict 차단" — an admitted stdlib reimplementation. (e) branch protection 404 confirmed.

NOTE: the finding's own evidence item (1) ("PR ref 에서 생성된 alert 는 0건") is FALSE — an artifact of the default-branch-scoped alerts API. The correction strengthens the conclusion, so the thesis survives despite its supporting evidence being partly wrong.

THREE DEFECTS requiring downgrade from P0:

1. SCOPE OVERREACH. "4회 반복된 bespoke 가드 트레드밀 전체" is false for #1080~#1083: #1080 (check_retro_cadence — retrospective cadence) and #1082 (posttool_pytest_smoke — pytest hook) have ZERO CodeQL relation; #1083 (check_dead_code — AST caller analysis on public repository/service functions) has no `security-and-quality` equivalent (CodeQL does not flag zero-caller module-level public functions). Only #1081 overlaps. The charitable reading — the CodeQL-targeting guards only (check_dual_import, check_noqa_sideeffect, #1094 empty-except guard) — holds at 3, not "전체".

2. PRESCRIPTION NOT EXECUTABLE AGAINST THE CITED FILE. `gh api .../code-scanning/default-setup` → `state: not-configured`: this repo uses advanced setup, so the check-failure severity threshold is a repo-level Code security UI setting. There is no such field in codeql.yml and no documented public REST API. "임계값 한 줄" cannot be applied to codeql.yml:6, the line it cites.

3. UNACCOUNTED BLAST RADIUS. `src/gate/github_review.py:18` `_MERGEABLE_BLOCK = frozenset({"dirty","blocked","behind","draft","unstable"})` means a failing check WOULD block merges through SCAManager's own gate even absent branch protection — so the remedy is more viable than the finding claims. But `src/services/dashboard_service.py:350` records `unstable_ci` at 79% of merge failures ALREADY. Lowering the threshold to `note` across 172 rules turns every new note alert repo-wide into a merge blocker, whereas all three bespoke guards are deliberately diff-scoped AND tests/-scoped per an explicitly recorded 2026-06-23 decision to DROP a blanket hook for idiom churn. The remedy silently re-litigates that decision without costing it out.

SEVERITY: P0 -> P1. Every affected alert is `note` with `security_severity_level=null` — no security or operational exposure; the status-quo cost is wasted effort on reactive fix PRs, not an incident. This project reserves P0 for operational-incident-blocking or hard-policy self-violation (e.g. the cadence breach). Not FALSE_POSITIVE: the structural insight — stop hand-rolling rule-by-rule stdlib reimplementations of a scanner already running on every PR — is correct, well-evidenced, and actionable. Recommended reframing: "configure the existing detector's PR gate (repo Code security setting, scoped ruleset) instead of extending the bespoke guard treadmill" with an explicit churn/unstable_ci cost analysis — not "one threshold line in codeql.yml".

### P1-50. [가드의 가드] CI 배선된 가드 3종 전부 git 실패 시 fail-OPEN — `_git` 이 returncode/stderr 를 버리고 `""` 반환 → '✅ 위반 없음' + exit 0

- **위치**: `scripts/check_noqa_sideeffect.py:76`
- **주장**: #1094 가 발견한 결함(가드가 무력한데 green)이 특정 사례가 아니라 **가드 계층 공통 관용구**다. `check_dead_code.py:82-86`·`check_noqa_sideeffect.py:76-81`·`check_dual_import.py:62-67` 의 `_git` 은 모두 `check=False` 로 실행한 뒤 `return out.stdout or ""` 만 한다 — returncode 미검사, stderr 폐기. `git diff` 가 실패하면(base sha 미도달·shallow clone·force-push 후 rebase·fork PR) 변경 파일 목록이 빈 리스트가 되고, 세 가드 모두 `if not violations: print("✅ …"); return 0` 경로로 빠져 CI 가 green 이 된다. 위반이 없어서 통과한 것과 아무것도 못 본 채 통과한 것이 출력·종료코드상 구분 불가능하다.
- **근거**: `scripts/check_noqa_sideeffect.py:76-81` — docstring 이 명시적으로 "실패 시 빈 문자열" 이라고 적어 fail-open 이 의도된 설계임을 자백한다. 동일 패턴 `scripts/check_dual_import.py:63` ("'' on failure"), `scripts/check_dead_code.py:86`. 소비 지점: `check_noqa_sideeffect.py:87` → `main:95-102`, `check_dead_code.py:92` → `main:113-122`. 세 가드 어느 것도 `_git` 실패 경로 테스트가 없다 — `tests/unit/scripts/test_check_noqa_sideeffect.py`·`test_check_dead_code.py`·`test_dual_import_guard.py` 어디에도 git 오류 주입 케이스 부재.
- **권고**: `_git` 을 loud-fail 로 전환: `if out.returncode != 0: raise SystemExit(f"가드 무력화 — git 실패: {out.stderr[:300]}")`. 이것이 카덴스 가드 `encoding=` 누락 fix(#1094)와 **정확히 같은 수정**이므로, 개별 fix 가 아니라 4 스크립트 공용 `scripts/_guard_git.py` 헬퍼로 통합해야 4번째 사본 드리프트를 끊는다. 추가로 각 가드에 '변경 파일 0건이면 그 사실을 명시 출력' 을 넣어 '검사함/못봄' 을 구분 가능하게 한다.
- **cross-verify**: SEVERITY_ADJUST — 기술적 사실은 전건 확인 + 실행 증거로 재현됨. 심각도만 P0→P1 조정.

## 인용 검증 (전부 EXACT 일치)
- `scripts/check_noqa_sideeffect.py:76-81` — `_git`: `check=False` 후 `return out.stdout or ""`. docstring "실패 시 빈 문자열" = fail-open 자백 (주장대로).
- `scripts/check_dead_code.py:82-86` — 동일 관용구.
- `scripts/check_dual_import.py:62-67` — 동일 관용구, docstring "'' on failure".
- 소비 지점 확인: noqa `:87`→`main:95-102`, dead_code `:92`→`main:113-122`, dual_import `:73,76,77`→`main:88-98`.
- CI 배선 확인: `.github/workflows/ci.yml:95`(dual_import) `:102`(noqa) `:109`(dead_code) — 3종 전부 `github.event.pull_request.base.sha` 인자로 실배선.
- 테스트 부재 확인: `tests/unit/scripts/` 3 테스트 파일에 `returncode|stderr|CalledProcess|_git` grep 0건 — git 실패 주입 케이스 전무.

## 실행 증거 (추측 아님 — 직접 재현)
도달 불가 base sha 주입 결과:
- `check_noqa_sideeffect.py` → `✅ 신규 noqa-은닉 import 없음` **EXIT=0**
- `check_dead_code.py` → `✅ 신규 dead-code 후보 없음` **EXIT=0**
- `check_dual_import.py` (PYTHONUTF8=1, CI 동등 조건) → `신규 이중 import 없음 — OK` **EXIT=0**
→ "위반 없어서 통과"와 "아무것도 못 본 채 통과"가 출력·exit code 상 **구분 불가능**이라는 핵심 주장이 실측으로 입증됨.

## 주장의 도달 경로 중 2건은 반증됨 (심각도 하향 근거)
- ❌ "shallow clone" — `ci.yml:63-65` `fetch-depth: 0` (전체 히스토리) 로 차단.
- ❌ "base sha 미도달(빈 인자)" — `lint-changed-tests` job 에 `if: github.event_name == 'pull_request'` (`ci.yml:56`) → push 이벤트로 빈 base.sha 유입 경로 없음. 빈 인자 실측 시 fail-open 재현되나 **CI 도달 불가**.
- ✅ 잔존 실경로: base 브랜치 force-push 로 base.sha 고아화 / fork PR / git 자체 오류(디스크·객체 손상). 비-일상적 이상 상황 한정.

## P0→P1 조정 사유
#1094(카덴스 가드)는 Windows 에서 **모든 실행이 100% 무력** = 상시 실명이라 P0 타당. 본 건은 **git 이상 발생 시에만** 조건부 실명이며, 보호 대상이 런타임 정합성이 아니라 self-inflicted CodeQL 알림·dead code 라는 **위생 계층**이고, main 전체 CodeQL 스캔이라는 사후 백스톱이 실존(그 백스톱이 바로 #540~545 를 계속 잡아온 경로). 본 저장소 P0 전례(Telegram 봇 차단 silent skip, NULL-owner IDOR)의 운영 사고 기준과 등급 불일치. 결함·수정 필요성은 인정하되 P1 이 정직한 슬롯.

## 추가 발견 (주장이 놓친 동형 결함 — 본 finding 보강)
`check_dual_import.py` 에는 다른 2종이 가진 `sys.stdout.reconfigure(encoding="utf-8")` 블록(noqa `:116-119`, dead_code `:139-143`)이 **없음**. Windows cp949 에서 **성공 경로 출력 자체가 `UnicodeEncodeError` 크래시 → exit 1**(실측). 세션 컨텍스트 학습 5(#1094 subprocess encoding 실명)와 동일 관용구 드리프트 계열 — 3종 가드가 같은 조상에서 복사되며 방어 코드만 선택적으로 누락된 증거.

## 권고 수정 (3줄, 정책 16 부합)
`_git` 에서 `out.returncode != 0` 시 stderr 를 stdout 에 출력하고 `sys.exit(2)` (loud-fail). 세 스크립트 공통 적용 + git 실패 주입 테스트 3건 추가(정책 4 단언+가드 페어). 부수로 dual_import 에 reconfigure 블록 동기화.

### P1-51. [remediation 완결성] 회고 P0(문서-only 트리거 자기위반)의 조치가 부분 조치 — #1080 은 '측정'만 기계화하고 '호출'은 여전히 문서-only, 회귀 가드가 그 문서-only 를 정답으로 고정한다

- **위치**: `tests/unit/scripts/test_check_retro_cadence.py:150`
- **주장**: P0 의 실패 메커니즘은 '문서에 적힌 단계를 Claude 가 건너뛴다' 였다. #1080 은 카운트 로직을 스크립트로 만들었지만 그 스크립트를 **실행시키는 유일한 트리거가 여전히 CLAUDE.md 체크리스트 한 줄**이다. `.claude/settings.json` 에 배선된 훅은 PreToolUse 2종·PostToolUse 1종뿐이고 SessionStart 훅은 없다. 즉 Claude 가 체크리스트를 건너뛰면 카운터는 P0 이전과 동일하게 영원히 실행되지 않는다. 더 나쁜 것은 회귀 가드가 이 상태를 승인한다는 점이다.
- **근거**: `grep -rn check_retro_cadence` 실측 — 호출 경로는 `CLAUDE.md:320` 한 곳뿐(나머지는 docs 서술·자기 테스트). `.claude/settings.json` hooks 키 = PreToolUse(check_edit_allowed·doc_review_gate) + PostToolUse(posttool_pytest_smoke) — SessionStart 없음. `tests/unit/scripts/test_check_retro_cadence.py:150` `test_checklist_wires_the_counter` 는 `assert "check_retro_cadence.py" in claude_md` 로 **CLAUDE.md 에 문자열이 있는지만** 단언하며, 실패 메시지가 "체크리스트 미배선이면 다시 인지 의존이 된다" 라고 적혀 있다 — 체크리스트 배선 자체가 인지 의존이라는 점을 놓친 것이다. 2회 실패한 메커니즘 클래스를 회귀 가드가 성공 기준으로 제도화했다.
- **권고**: `.claude/settings.json` 에 SessionStart 훅으로 `python scripts/check_retro_cadence.py` 를 배선하고(exit 0 advisory 유지, breached 시 additionalContext 로 Claude 에 주입), `test_checklist_wires_the_counter` 의 단언 대상을 CLAUDE.md 문자열이 아니라 settings.json 의 SessionStart 엔트리로 교체한다. 문서 라인은 보조로 유지.
- **cross-verify**: CONFIRMED — 모든 사실 근거를 실측 재확인 — 결함 실재. (1) 인용 정확: test_check_retro_cadence.py:150 = `def test_checklist_wires_the_counter():`, 유일 단언(157행) = `assert "check_retro_cadence.py" in claude_md` (CLAUDE.md 문자열 존재 여부만). (2) 호출 경로 단일·인지의존: `grep -rn check_retro_cadence` (py/md/json/yml/toml/mjs/sh) 결과 실호출은 `CLAUDE.md:320` 체크리스트 bash 블록 1곳뿐 — 나머지는 docs 서술(cycle-history/STATE)·스크립트 자체 usage docstring·자기 테스트. (3) 기계 백스톱 부재 확인: `.claude/settings.json` hooks = PreToolUse(check_edit_allowed·doc_review_gate) + PostToolUse(posttool_pytest_smoke), SessionStart 없음 / settings.local.json 비어 있음 / ci.yml 카덴스 job 없음 / .pre-commit-config.yaml 은 커스텀 스크립트 8종(check_docs_sync·check_toc_anchors·check_memory_refs·check_env_vars_sync·check_config_5way_sync·check_bilingual_comments 등)을 배선하면서 check_retro_cadence.py 만 누락 — 즉 기계 배선 관용구가 이미 확립돼 있는데 본 가드에만 미적용.

적대 검증 2건 모두 finding 이 생존: (a) "#1080 이 무가치한가?" — 아니고 finding 도 그렇게 주장하지 않음(부분 조치로 정확히 규정). #1080 이전엔 "직전 회고 이후 ≥15 PR?" 판정 자체가 수동 카운트였고 지금은 단일 명령+loud 배너(48→5 리셋 실측) → 실질 마찰 감소. 다만 근거문 중 "P0 이전과 동일하게"는 소폭 과장(카운트 노동은 해소, 미해소는 **트리거**). (b) 가드 비판의 타당성 — 가장 예리한 지점. 테스트 docstring 이 "스크립트만 있고 체크리스트 미배선이면 다시 인지 의존이 된다"고 추론하는데, 체크리스트 배선 자체가 인지 의존이다. 개념 오류가 가드의 성공 기준에 각인돼 green 이 곧 기계화를 의미하지 않음.

심각도 P1 유지(승급·강등 모두 기각): 운영 영향 없음 + #1080 의 실질 진전은 P0 반대 근거이나, 잔여 실패 모드가 2/2 재발률을 가진 데다 가드가 그에 대해 **거짓 확신**을 방출 — #1094(가드가 무력한데 green)와 동일 클래스이며 본 회고의 최우선 질문("가드의 가드")에 정확히 해당하므로 P2 강등도 기각. SessionStart 는 Claude Code 표준 훅 이벤트라 시정 가능(불가능한 요구 아님) — 권고 시정 = SessionStart 훅 배선 + 가드를 "CLAUDE.md 문자열 존재" 대신 "settings.json 에 카운터를 실행하는 훅이 배선됨" 단언으로 교체(+ 탐지기 긍정 통제).

### P1-52. [가드의 가드] PostToolUse 스모크 훅의 ❌ 배너가 Claude 에게 도달하지 않는다 — exit 0 + stdout 은 transcript 전용. CLAUDE.md 는 Claude 에게 '❌ 배너 시 즉시 조사' 를 지시하고 있다

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:101`
- **주장**: #1082 는 훅의 false-green(전체 5566 을 60s 타임아웃에 돌려 `|| true` 로 삼킴)을 봉인했지만, 결과를 **읽는 주체에게 전달하는 경로**는 손대지 않았다. 훅은 `print(banner)` 후 `return 0` 한다. Claude Code 의 PostToolUse 훅은 exit 0 일 때 stdout 을 transcript 모드(Ctrl-R)에만 표시하고 모델 컨텍스트에는 주입하지 않는다 — Claude 에게 알리려면 exit 2(stderr) 또는 `hookSpecificOutput.additionalContext` JSON 이 필요하다. 결과적으로 CLAUDE.md 가 Claude 에게 부과한 의무('❌ 배너 시 즉시 조사')는 Claude 가 물리적으로 관측할 수 없는 신호에 걸려 있다. 스코프는 고쳤으나 신호는 여전히 무음이다.
- **근거**: `.claude/hooks/posttool_pytest_smoke.py:101-105` — `banner = "✅ …" if rc == 0 else … "❌ 스모크 실패"` → `print(f"{banner} …")` → `return 0  # 비차단 advisory`. 파일 헤더 `:14` 도 "Non-blocking (always exit 0); the result is shown via a ✅/❌ banner" 로 exit 0 을 명시. 지시 측: `CLAUDE.md:352` "❌ 배너 시 즉시 조사". 테스트 측: `tests/unit/hooks/test_posttool_pytest_smoke.py` 6개 전부 순수 함수(`is_src_file`·`derive_test_target`)만 검증 — `main()` 호출·배너 출력·전달 채널에 대한 긍정 통제 0건.
- **권고**: rc != 0 일 때 `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"<배너+tail>"}}` 를 stdout 에 JSON 으로 내보내거나 stderr + exit 2 로 전환한다(비차단 유지가 목표면 additionalContext 쪽). 그리고 `main()` 을 실패하는 가짜 pytest 로 구동해 ❌ 경로가 실제로 실패 신호를 산출하는지 검증하는 긍정 통제 테스트를 추가한다.
- **cross-verify**: CONFIRMED — 모든 인용 실측 일치 — 위양성 아님. 오히려 근거가 미인용 증거로 보강됨.

**1. 인용 재확인 (전건 EXACT)**
- `.claude/hooks/posttool_pytest_smoke.py:101-105` — `banner = "✅ 스모크 통과" if rc == 0 else (... "❌ 스모크 실패")` → `print(f"{banner} [{scope}] …")` → `return 0  # 비차단 advisory`. 정확히 인용대로.
- 동 파일 `:14` — "Non-blocking (always exit 0); the result is shown via a ✅/❌ banner." 헤더가 exit 0 명시.
- `CLAUDE.md:352` — "❌ 배너 시 즉시 조사." 실재 (sed 350,354p 로 라인 오프셋까지 대조).
- `tests/unit/hooks/test_posttool_pytest_smoke.py` — 6 테스트 전부 `is_src_file`·`derive_test_target` 순수 함수. `main()` 호출 0건·배너 문자열 단언 0건·전달 채널 단언 0건. 긍정 통제 부재 주장 정확.

**2. 미인용 결정적 보강 — 같은 디렉토리가 정답 채널을 이미 쓰고 있다**
`.claude/hooks/check_edit_allowed.py:102` 와 `doc_review_gate.py:312` 는 `hookSpecificOutput` JSON(`permissionDecision`/`permissionDecisionReason`)으로 신호를 보낸다. 즉 **프로젝트는 구조화 채널을 이미 알고 사용 중**이며, 스모크 훅만 bare `print()` + exit 0 이다 — "몰라서"가 아니라 **드리프트**. 추가로 `doc_review_gate.py:318` 의 `warn` 분기(`print(_format_warn(...))` + exit 0)도 **동일 결함 2번째 인스턴스** (본 finding 미포착 — 회고 반영 권장).
`.claude/settings.json` 확인 결과 훅은 `PostToolUse` / `matcher: "Write|Edit"` / timeout 90 으로 배선 — 전달 의미론을 바꾸는 래퍼 없음. 훅 계약상 exit 0 stdout 은 transcript(Ctrl-R) 전용이고 모델 컨텍스트 주입은 `UserPromptSubmit`/`SessionStart` 예외에 한정 — PostToolUse 에서 Claude 에게 알리려면 exit 2(stderr) 또는 `hookSpecificOutput.additionalContext` 가 필요하다는 주장은 계약과 일치.

**3. P1 유지 근거 (강등 검토 후 기각)**
강등 논거는 있었다 — 훅이 스스로 advisory 로 명시하고, 진짜 게이트는 push-time `pytest tests/unit`(6-step ②, "예외 없음")라 **미관측 스모크 실패가 main 으로 결함을 탈출시키지는 않는다**(피해=탐지 지연). 그럼에도 P1 유지:
(a) 본 항목은 회고가 **P1 테마 C 로 분류한 바로 그 결함의 미조치 잔여분**이다. #1082 는 신호가 유실되는 *이유*를 timeout-삼킴 → 채널-불일치로 바꿨을 뿐, *유실된다*는 사실은 불변. 동일 피해의 잔여분을 P1 아래로 내리면 원 분류와 모순.
(b) 결과적으로 편집 시점 조기 탐지 기여도 = **0%**. 훅의 유일한 소비자(Claude)에게 값이 전달되지 않으므로 #1082 는 **부분 조치** — 세션 질문 "remediation 완결성"의 실사례.
(c) `CLAUDE.md:352` 가 관측 불가 신호에 Claude 의 행동 의무를 걸어둔 상태 = "가드의 가드" 공백, #1094(인코딩 누락으로 가드가 눈멀었는데 green)와 **동일 클래스**.

**4. 두 다리로 서는 finding**
전달 의미론에 잔여 불확실성을 가정하더라도(계약 변경 등) 결함은 유지된다 — 테스트가 전달 채널을 전혀 단언하지 않으므로 **회귀를 탐지할 수 없다**는 점은 독립적으로 성립. 조치 권고: `main()` 을 실제 호출해 실패 rc 에서 Claude-도달 채널(exit 2 stderr 또는 `additionalContext`)이 산출되는지 단언하는 긍정 통제 추가 + `doc_review_gate.py` warn 분기 동시 정정(정책 16 공유 관용구 grep 전수 페어).

### P1-53. [가드의 가드 (신규 가드 자체의 테스트 신뢰성)] #1082 false-green 봉인 PR 이 스스로 false-green — 봉인 대상 결함을 재주입해도 6/6 통과 (뮤테이션 실증)

- **위치**: `.claude/hooks/posttool_pytest_smoke.py:101`
- **주장**: P1 테마 C(#1082)의 존재 이유는 '훅이 실패를 삼키고 green 보고'를 봉인하는 것이었다. 그러나 테스트는 순수 경로매핑 함수 2종(is_src_file·derive_test_target)만 커버하고, false-green 이 실제로 발생하는 seam(main() 101줄 배너 판정 + _run() 65~78줄 rc 전파)에는 단언이 0건이다. 즉 '검증자 검증 부재'가 회고 테마 자기 산출물에 그대로 재현됐다.
- **근거**: 뮤테이션 실증: main() 배너 판정 직전에 `rc = 0` 을 삽입해 #1082 이 봉인한 바로 그 삼킴 결함을 재주입 → `python -m pytest tests/unit/hooks/test_posttool_pytest_smoke.py -q` = **6 passed**. 테스트 파일 전체(65줄)에 main·_run·subprocess·stdin 참조 0건(grep 확인). 대조로 실제 stdin 주입 실행은 정상 동작함을 확인: `echo '{"tool_input":{"file_path":"src/gate/engine.py"}}' | python .claude/hooks/posttool_pytest_smoke.py` → `✅ 스모크 통과 [tests/unit/gate]`, exit 0 — 즉 실행 가능한 seam 인데도 테스트가 없다.
- **권고**: main() 통합 테스트 3건 추가: (a) 실패하는 tmp 테스트 디렉토리를 target 으로 주입 → stdout 에 '❌' 포함 단언(부정 통제, 이번 뮤턴트를 죽임) (b) 통과 케이스 → '✅' 단언(긍정 통제) (c) 타임아웃 경로 → '⚠️' 단언. subprocess 로 훅을 실제 실행하고 stdin JSON 을 주입하는 방식(위 실증 커맨드와 동일)이면 seam 전체가 덮인다.
- **cross-verify**: SEVERITY_ADJUST — 근거 재현 성공 — 단, P0 는 과대. 실제 결함이므로 FALSE_POSITIVE 아님. // Evidence reproduced, but P0 overstates it.

[검증된 사실 / Verified]
1. 인용 정확: posttool_pytest_smoke.py:101 = 배너 판정 라인 (`banner = "✅ 스모크 통과" if rc == 0 else ...`). sed -n '101p' 실측 일치.
2. 커버리지 갭 실재: 테스트 파일 64줄, import 는 `derive_test_target`·`is_src_file` 2종뿐. grep 결과 main·_run·subprocess·stdin 참조 0건.
3. 뮤테이션 재현 + 확대(격리 사본, 저장소 무변경 — git status --porcelain empty 확인): M1 배너 직전 `rc = 0` 삼킴 재주입 → 6 passed / M2 `main()` 전체를 `return 0` 으로 무력화 → 6 passed / M3 `_run` 이 pytest 미실행 후 (0, "") 반환 → 6 passed. 즉 폭발 반경은 주장(배너 seam)보다 넓다 — 실행 가능 표면 전체가 미검증.
4. 형제 가드 비대칭 확인: #1080/#1081/#1083 는 긍정 통제·배선 테스트 보유(test_ci_wires_dead_code_guard:120 / test_ci_wires_noqa_guard_in_lint_job:115 / test_script_runs_without_crashing:128 / test_checklist_wires_the_counter:150). #1082 는 긍정 통제도 settings.json 배선 테스트도 0건 — 4 가드 중 유일한 예외.

[P0 → P1 하향 사유 / Why downgraded]
a. 살아있는 결함 없음 — 긍정 통제 직접 수행: 가짜 repo 루트(.claude/hooks + tests/unit/foo/test_fail.py 실패 테스트) 구성 후 stdin 주입 → `❌ 스모크 실패 [tests/unit/foo]` + 실패 tail 출력. 실제 탐지 정상. 운영 2 분기(src/gate/engine.py → tests/unit/gate, src/main.py → collection fallback) 모두 정상 동작. 훅은 '눈이 먼' 게 아니라 '미검증'.
b. 계층이 설계상 advisory — 항상 exit 0(105줄), CLAUDE.md 가 'best-effort 조기 실패 탐지(전체 게이트 아님)' 명시. 전체 게이트는 push-time 6-step ②. 훅 전면 회귀 시 비용 = 탐지 지연이지 정합성/보안 손실 아님.
c. 본 회고의 실제 P0(카덴스 트리거 자기위반 — 트리거가 실제로 미발화) 및 #1094형(Windows encoding 누락으로 가드가 live-blind)과 등급 대비 시 본 건은 한 단계 아래. 전자는 실발생, 본 건은 잠재.

[P2 아닌 사유 / Why not P2]
#1094 선례가 이 잠재 실명 클래스의 현실화를 이미 입증했고(가드가 green 인데 무력), main()/_run 수정 시 CI 가 무조건 통과하는 은닉 회귀 경로가 열려 있다. 형제 3종 대비 비대칭이라 수정 비용도 낮다(긍정 통제 1건 + settings.json 배선 단언 1건). 본 회고의 '가드의 가드 — 각 가드에 긍정 통제가 있는가' 질문에 뮤테이션으로 답한 항목이므로 P1 유지.

[권고 조치] (1) 가짜 repo 루트 + 실패 테스트로 main() 종단 긍정 통제 1건(❌ 배너 + exit 0 동시 단언) (2) rc=None 타임아웃 → '⚠️ 미완' 분기 단언 (3) .claude/settings.json PostToolUse 배선 단언(형제 test_ci_wires_* 패턴).

### P1-54. [가드의 가드 (신규 가드 자체의 테스트 신뢰성)] #1080 카덴스 가드를 완전 무력화해도 13/13 통과 — #1094 는 encoding 증상만 고치고 '긍정 통제 부재' 근본은 미해결

- **위치**: `tests/unit/scripts/test_check_retro_cadence.py:146`
- **주장**: #1094 가 subprocess `encoding=` 누락을 고쳤으나, 그 테스트가 애초에 눈이 멀었던 진짜 이유는 encoding 이 아니라 **'가드가 판정을 산출했는가'를 아무도 단언하지 않는다**는 점이다. 146~147줄은 returncode 와 stderr 만 검사하고 stdout(=가드의 유일한 산출물인 카덴스 판정 배너)에 대한 단언이 0건이다. 따라서 가드가 통째로 무음 no-op 가 되어도 스위트는 green 이다 — #1094 형 결함이 같은 파일에 그대로 남아 있다.
- **근거**: 뮤테이션 실증: `main()` 본문 최상단(check_retro_cadence.py:109 직전)에 `return 0` 을 삽입해 가드를 완전 무력화 → 실행 출력 0줄(판정 완전 소실) → `pytest tests/unit/scripts/test_check_retro_cadence.py -q` = **13 passed**. 추가로 stderr 단언(147줄)은 returncode 단언(146줄)에 이미 포섭되는 잉여 단언이다(UnicodeEncodeError 발생 시 returncode≠0). 실제 정상 실행 시 출력: `🔴 회고 카덴스 트리거 발화 — … 머지 PR 15 건 (임계 ≥15)` — 이 문자열류를 아무도 검사하지 않는다.
- **권고**: `test_script_runs_without_crashing` 에 stdout 긍정 통제 추가: `assert re.search(r'(회고 카덴스|last formal retro)', r.stdout)` + 판정 라인 존재 단언. 나아가 skip 4 경로(110·114·119줄)와 판정 경로를 구분하는 단언(예: skip 문구가 아닌 verdict 문구여야 함)을 넣어 '무음 skip = green' 을 죽인다.
- **cross-verify**: SEVERITY_ADJUST — 결함 자체는 실재 — 뮤테이션 재현 성공. `main()` 본문 최상단(_make_stdout_safe() 직전)에 `return 0` 삽입 → 가드 출력 0줄(판정 완전 소실) → `pytest tests/unit/scripts/test_check_retro_cadence.py -q` = **13 passed** (주장과 정확히 일치). 인용 검증: 146~147줄이 유일한 종단 단언이며 returncode/stderr 만 검사, stdout 단언 0건. 테스트 파일 내 `stdout`/`main` grep 결과는 docstring 과 커밋제목 fixture 문자열(:80)뿐 — `main()` 은 import 도 호출도 되지 않음. 작업트리는 mutation 후 `git checkout` 복원 + `git status --porcelain` 공백 확인, 스크립트 정상 동작 재확인.

추가 실증(주장에 없던 보강): `_REPORTS_DIR = Path("docs/_archive/reports")` (check_retro_cadence.py:28) 가 **cwd 상대경로** — `scripts/` 에서 실행 시 `ℹ️ 회고 리포트 디렉토리 없음 — 카덴스 점검 skip` + exit 0 로 **무음 자기무력화**. #1080 이 봉인하려던 바로 그 실패 모드가 재현되나, 유일한 종단 테스트가 `cwd=_ROOT` 고정 + stdout 무단언이라 탐지 불가. 가설이 아닌 실측 degradation.

단, 주장 헤드라인('긍정 통제 부재 근본 미해결')은 과대. 형제 가드 대조 확인 — `test_check_noqa_sideeffect.py:94-98`(`find_violations` → `len(violations)==1`) · `test_check_dead_code.py:79-105`(`count_ast_references`) 는 긍정 통제 보유, 그리고 **본 파일도 보유**: `test_evaluate_breached_at_or_above_threshold`(:99-104) 가 46/경계 15 에서 `breached is True` 단언, `count_merge_prs` 도 위반 입력 단언. 즉 판정 로직은 긍정 통제됨. 미커버 영역은 더 좁다 — `main()` 오케스트레이션 seam(디렉토리 해석·glob·boundary commit 조회·git 호출·출력)에 한정.

심각도 P0→P1 조정 사유: (1) 가드는 advisory 설계(항상 exit 0, 커밋/PR 미차단) 이며 현재 정상 동작(15 PR 에서 FIRED 배너 실측 출력). (2) 판정 로직 긍정 통제 존재 → 'guard 통째 무력' 은 뮤테이션 상 참이나 회귀 blast radius 는 main() 글루 한정. (3) 실현된 장애가 아닌 잠재 탐지 갭 — 본 프로젝트 P0 은 실제 발생한 위반(~46 PR 무회고 창)에 부여돼 왔고, 동작하는 advisory 스크립트의 테스트 커버리지 갭은 '가드의 가드' P1 계열. 부차 주장(147줄 stderr 단언이 146줄에 포섭되는 잉여)도 타당 — UnicodeEncodeError 는 non-zero exit(shutdown flush 실패 시 120 포함)로 귀결.

수정 방향: stdout 비어있지 않음 + 카덴스 판정 형태 매칭 단언 추가 · cwd 독립성 테스트 추가 · `_REPORTS_DIR` 을 cwd 대신 스크립트 기준 repo root 앵커링.

### P1-55. [remediation 완결성 (기계화 한 단계 미달)] P0 시정이 '정책 문서 의존'을 '체크리스트 문서 의존'으로 바꿨을 뿐 — 카운터는 여전히 인지 의존이고, 배선 테스트가 그 사실을 은폐

- **위치**: `tests/unit/scripts/test_check_retro_cadence.py:150`
- **주장**: P0 의 교훈은 '문서-only 시정은 두 번 실패했다'였다. 그런데 시정 결과물인 카운터의 발화 경로는 CLAUDE.md 체크리스트의 bash 라인 한 줄 — 즉 Claude 가 세션 시작에 그것을 읽고 실행하기로 기억해야 발화한다. 여전히 인지 의존이다. 더 나쁜 것은 `test_checklist_wires_the_counter`(150줄)가 CLAUDE.md 에 문자열이 존재하는지만 검사하면서 이름은 'wires'라, **문서 의존을 배선인 것처럼 부호화**해 거짓 안심을 준다. 같은 저장소가 settings.json 으로 진짜 훅 배선(PostToolUse)을 할 줄 알면서 카덴스에는 적용하지 않았다.
- **근거**: .claude/settings.json 는 PreToolUse·PostToolUse 두 이벤트만 등록(전문 확인) — SessionStart 항목 없음. CLAUDE.md 의 카운터 호출은 체크리스트 bash 블록 텍스트일 뿐이며, test_checklist_wires_the_counter 는 `assert "check_retro_cadence.py" in claude_md` 문자열 포함 검사 1건이 전부(156~159줄). 대조: posttool 훅은 settings.json PostToolUse 에 실제 등록되어 stdin 주입만으로 발화 실증됨.
- **권고**: 카운터를 SessionStart 훅으로 승격해 settings.json 에 등록(advisory·exit 0 유지 → 정책 17 안정성 무손상). 그 후 test_checklist_wires_the_counter 를 settings.json 파싱 단언으로 교체하거나, 최소한 함수명을 `test_checklist_documents_the_counter` 로 정정해 '문서 언급 ≠ 배선'을 테스트 이름이 거짓말하지 않게 한다.
- **cross-verify**: CONFIRMED — 모든 인용 실측 확인 + 주장보다 **더 강한** 결함을 재현했다.

**인용 검증 (전건 일치)**
- `tests/unit/scripts/test_check_retro_cadence.py:150` = `def test_checklist_wires_the_counter()` 정확 일치. 본문 단언은 156~159줄 `assert "check_retro_cadence.py" in claude_md` 1건이 전부.
- `.claude/settings.json` 전문 33줄 read — 등록 이벤트는 `PreToolUse`(check_edit_allowed·doc_review_gate) + `PostToolUse`(posttool_pytest_smoke) **2종뿐, SessionStart 없음**. 사용자 레벨 `~/.claude/settings.json` 에도 hooks 키 자체가 없음(permissions/plugins만).
- CLAUDE.md:320 = 체크리스트 bash 블록 내 `python scripts/check_retro_cadence.py` — 카운터의 **유일한 발화 경로**. 전 저장소 grep 결과 CI(`ci.yml`)·`.pre-commit-config.yaml` 어디에도 배선 없음.

**주장보다 강한 실증 — 테스트가 지목한 배선의 제거를 탐지조차 못 한다**
`check_retro_cadence.py` 는 CLAUDE.md 에 **2회** 등장(320줄 = 실행 bash 라인, 326줄 = 산문 설명 노트). 실행 라인 320만 삭제하는 시뮬레이션 결과 `"check_retro_cadence.py" in claude_md` → **True(테스트 green 유지)**. 즉 `test_checklist_wires_the_counter` 는 이름이 지목한 **배선 소실을 물리적으로 검출 불가**하며, 파일 전체 substring 검사라 체크리스트 블록으로 스코프조차 되지 않았다. 이는 이번 회고가 사냥 중인 "#1094형(가드가 무력한데 green)" 클래스의 교과서 사례 — 거짓 안심 생성이 추정이 아니라 재현된 사실이다.

**적대 반증 시도 3건 전부 실패**
(a) "advisory 설계라 배선 불요" → 쟁점은 blocking 여부가 아니라 **발화 경로**. PostToolUse 훅처럼 advisory 출력도 기계 발화가 가능하며 동일 저장소가 그 패턴을 이미 운용 중(대조군 성립).
(b) "CLAUDE.md 는 자동 로드라 기계적" → 자동 로드는 텍스트를 컨텍스트에 넣을 뿐 스크립트를 실행하지 않는다. 결정적으로 **#1028 자체가 자동 로드 CLAUDE.md 에 있었는데 ~46 PR 무회고로 자기위반**했다 — 방금 실패가 실증된 그 매체를 한 겹 우회해 재사용한 것이므로 P0 교훈이 정면 적용된다.
(c) 형제 가드 대조 → #1081 `check_noqa_sideeffect.py`·#1083 `check_dead_code.py` 는 `ci.yml:102/109` 에 실제 배선(pre-merge). 카덴스만 문서 텍스트 — "이벤트가 없어서"라는 변명도 SessionStart/CI 스케줄 대안 존재로 성립 안 함.

**심각도 = P1 유지 (조정 없음)**
상향 안 하는 근거: 측정 자체는 진짜 기계화됐고(수기 PR 카운팅 제거·라이브 48→5 리셋 실측) advisory·비운영 영역이라 부분 개선은 실재 — "문서 의존을 문서 의존으로 바꿨을 뿐"은 다소 과장. 하향 안 하는 근거: 두 번 실패한 **개시(initiation) 단계**가 그대로 인지 의존으로 남았고, 위 재현된 테스트 무력화가 그 사실을 능동적으로 은폐한다. 회고 헌장의 "remediation 완결성" 질문에 대한 정확한 답이므로 P1 적정.

**최소 시정 방향**: (1) 단언을 체크리스트 bash 블록 스코프 + 실행 라인 형태(`python scripts/check_retro_cadence.py`)로 좁혀 산문 occurrence 로 통과 불가하게 할 것, (2) 문서 의존 자체를 `.claude/settings.json` SessionStart(advisory·exit 0) 로 승격하고 테스트를 settings.json 등록 검증으로 전환할 것 — 그때만 이름 `wires` 가 사실이 된다.

---

## P2 (90건) — 압축 표

| # | 관점 | 위치 | 요지 | 권고 |
|---|------|------|------|------|
| 1 | tooling | `.github/workflows/codeql.yml:35` | 자초 CodeQL 3회 재발의 구조적 원인 = PR CodeQL이 이미 도는데 게이팅하지 않음 → 룰당 수제 가드 두더지잡기 | 저장소 Code scanning 설정의 'Alert severities that cause a pull request check failure'에 Warning/Note를 포함시키거나 `.githu… |
| 2 | tooling | `docs/runbooks/owed-verification.md:11` | owed 원장(#1084)은 surfacing 메커니즘이 없어 기록만 함 — 세션시작 체크리스트 미배선(카덴스 카운터와 비대칭) | CLAUDE.md 세션시작 체크리스트에 원장 점검 1줄 추가 + 안전/데이터 섹션의 ⏳ 행 수를 세어 loud 출력하는 stdlib 스크립트(~30 LOC)를 check_retro_cadence.p… |
| 3 | tooling | `tests/unit/scripts/test_check_noqa_sideeffec…` | 신규 가드 3종의 main() 배관이 프로세스 경계에서 미검증 — #1094가 준 교훈(순수함수는 옳고 배관이 눈멀었다)의 미적용 | 가드당 tmp git repo(init→commit→위반 라인 추가→커밋)를 만들어 스크립트를 subprocess로 실행하고 exit 1 + 위반 경로 출력까지 단언하는 테스트 1건씩 추가. 순수 … |
| 4 | docs | `docs/architecture.md:141` | #1085 '문서 drift 일괄 sync' 가 같은 창에서 신설된 가드 3종을 architecture.md scripts/ 트리에 미등재 — 부분 조치 | (a) 3 스크립트를 architecture.md scripts/ 트리에 1줄씩 추가. (b) 구조 봉인: CLAUDE.md 6-step ⑥ 문구를 'src/ 트리' → 'architecture.m… |
| 5 | docs | `.claude/rules/testing.md:30` | testing.md 가 check_noqa_sideeffect 가드 범위를 무제한으로 오기술 — 정작 alembic/env.py(최초 자초 발생지)는 가드 사각 | (a) 문서 즉시 정정: testing.md:30 에 '(현재 tests/ 하위 diff 한정)' 명시. (b) 가드 범위를 `tests/` → `tests/ alembic/` 로 확장(src/ 는… |
| 6 | docs | `docs/STATE.md:20` | 가드 계층(scripts/·.claude/hooks/)이 모든 lint 게이트 밖 — 자초 CodeQL 반복의 구조적 원인 | `make lint-guards` 또는 CI 스텝으로 `pylint --fail-under=<보수적 floor> scripts/ .claude/hooks/` 추가. 가드 계층은 파일 수가 적고 의존… |
| 7 | docs | `docs/architecture.md:170` | architecture.md scripts/ 트리에 git 이력상 존재한 적 없는 scripts/README.md 유령 항목 | 유령 항목 삭제 + 누락 3건 추가를 한 PR 로 처리. 근본 봉인은 위 P1 권고의 트리↔실파일 대조 자동화와 동일 조치로 커버된다. |
| 8 | decision | `docs/runbooks/owed-verification.md:11` | owed 원장(#1084)이 회고 P0 교훈을 같은 세션에서 자기 위반 — 문서-only 기록장, 첫 측정창에서 NEW-P0-N 회신 의무 미이행 | 카덴스와 동일하게 기계 신호로 승격: (a) `scripts/check_owed_verification.py` 신설 — 원장의 🔴 안전등급 표에 ⏳ 행이 있으면 세션 시작 시 loud 배너(advi… |
| 9 | decision | `scripts/check_dead_code.py:82` | 신규 가드 #1081·#1083 이 git plumbing 실패 시 무음 green — #1094 형(가드가 무력한데 통과) 재발 | 두 스크립트에 (a) 시작 시 `git rev-parse --verify <base>^{commit}` 선행 검증 — 실패 시 exit 1(fail-closed, CI 가드로서 정당) 또는 최소한 … |
| 10 | decision | `.claude/settings.json:26` | #1082 훅 배선·타임아웃 부등식이 미검증 — 형제 가드는 배선 단언이 있는데 훅만 비대칭 | test_posttool_pytest_smoke.py 에 (a) settings.json PostToolUse 항목이 posttool_pytest_smoke.py 를 가리키는지, (b) 해당 tim… |
| 11 | decision | `scripts/check_noqa_sideeffect.py:87` | #1081 가드의 경로 범위 축소(tests/ 한정)가 재발 클래스보다 좁고, 그 결정이 PR 본문에 미보고 (정책 3) | (a) 가드 docstring 과 PR/커밋 본문에 '경로 범위 = tests/ 한정, src/·alembic/ 은 제외(사유: …)' 를 결정으로 명시 — 고려했으나 제시 안 한 안 1줄(정책 1… |
| 12 | decision | `scripts/check_dual_import.py:98` | #1094 커밋 본문의 '정책 16 grep 전수' 단언이 관용구의 절반만 훑음 — 나머지 절반은 지금도 드리프트 | (a) 7개 스크립트에 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 관용구 일괄 적용, (b) 재발 방지로 test_empty_exc… |
| 13 | decision | `scripts/check_dead_code.py:122` | check_dead_code 의 이중 진실원(diff 범위 vs 워킹트리) 미고지 — 가드 수동 검증이 거짓 green 을 반환 | main() 시작부에 head 와 워킹트리 일치 검증 추가 — `git rev-parse HEAD` != 전달된 head 이면 '🔴 워킹트리≠head — 참조 카운트 무효' 경고 후 exit 1. … |
| 14 | code | `scripts/check_noqa_sideeffect.py:87` | 자초 CodeQL turn-0 가드 계층 전체가 tests/ 한정 — 최대 재발 클러스터(alembic/env.py 9건)가 사각 | check_noqa_sideeffect 의 diff pathspec 을 `tests/` → `tests/ alembic/ src/` 로 확장(신규 diff 한정 원칙은 유지되므로 legacy chu… |
| 15 | code | `docs/runbooks/owed-verification.md:11` | owed 원장(#1084)에 회신 유도 메커니즘 부재 — 생성 세션 내에서 이미 자기 규칙 미달 | CLAUDE.md 작업 시작 전 필수 체크리스트에 원장 미결 행 카운트 출력을 추가(카덴스 카운터와 동일 위치·동일 advisory 형식). 안전등급 행이 1건이라도 ⏳ 이면 세션 종료 보고에 강제… |
| 16 | code | `tests/unit/scripts/test_empty_except_guard.p…` | empty-except 가드의 'CodeQL 동등 판정' parity 주장이 실측과 불일치 — 안전한 scope 확장을 막음 | parity 주장을 '휴리스틱(CodeQL 보다 보수적, 미검증)' 으로 정정하거나, src/gate/github_review.py:115 를 반례 fixture 로 삼아 실제 CodeQL 발화 조… |
| 17 | code | `tests/unit/scripts/test_check_dead_code.py:1…` | 신규 가드 4종 어느 것도 main() 통합 경로를 테스트하지 않음 — #1094형 무음 실명의 남은 표면 | 각 가드에 tmp git repo(또는 고정 fixture diff)를 만들어 main() 이 exit 1 을 반환하는 **통합 긍정 통제** 1건씩 추가. #1060 커밋 replay 를 그대로 … |
| 18 | process | `tests/unit/test_migration_completeness.py:15…` | ORM 등록 튜플 12 vs 13 드리프트 — count-lock 이 자기참조라 누락을 구조적으로 탐지 불가 | (a) `AnalysisAttempt` 를 명시 import + 튜플에 등재하고 `== 13` 으로 갱신. (b) 근본 봉인: count-lock 을 자기참조에서 **외부 기준 대조**로 교체 — … |
| 19 | process | `docs/runbooks/owed-verification.md:1` | owed 원장이 회신을 유도하지 못함 — 처방된 강제 장치가 같은 세션 trailing sync PR 2건에서 즉시 누락 | 원장을 읽는 최소 카운터를 추가(`check_retro_cadence.py` 와 동형 advisory: ⏳ 행 수 + 안전등급 ⏳ 존재 시 loud 경고)하고 SessionStart 훅에 함께 배선… |
| 20 | process | `tests/unit/scripts/test_check_noqa_sideeffec…` | 가드 테스트가 순수 함수층만 검증 — #1094 결함이 살았던 git/subprocess 이음매는 전 가드 미검증 | 가드마다 end-to-end 통제 1건 추가 — 임시 git 저장소(또는 알려진 과거 커밋 범위)에 위반을 심고 `main()` 이 1을 반환하는지 단언. 최소 비용 형태 = 본 회고가 쓴 방식 그… |
| 21 | docs | `docs/architecture.md:164` | 6-step ⑥ 자기위반 — 신규 가드 3종이 docs/architecture.md scripts/ 트리에 전혀 미등재 (직전 사이클 동종 가드는 등재됨) | architecture.md:141~170 트리에 3종을 `check_dual_import.py:164` 와 동일 포맷(한국어+영어 2줄 + 배선 위치 명시: check_noqa_sideeffect… |
| 22 | docs | `docs/cycle-history.md:9` | cycle-history.md TOC 항목이 자기 본문과 모순 — 5467 vs 5475, "11 PR (#1077~#1086)" vs 본문 #1077~#1092 | cycle-history.md:9 TOC 요약을 본문과 일치시킨다(PR 범위 #1077~#1094, 단위 5412→5480, 통합 154→158). 앵커 문자열 `](#세션2-회고--회고-fix-4… |
| 23 | docs | `docs/cycle-history.md:145` | #1094 sync 커밋이 "6-step ⑤" 를 선언하면서 cycle-history.md 를 누락 — #1093·#1094 는 사이클 이력에 기록 자체가 없음 | cycle-history.md line 145 섹션 본문에 #1093·#1094 문단을 추가하고(특히 encoding 맹점 학습은 재사용 가치 높음) TOC line 9 요약을 동시 갱신한다. 또한… |
| 24 | docs | `scripts/check_docs_sync.py:11` | check_docs_sync.py 커버리지 갭 — cycle-history.md 미검사 + pytest 실측 대조 없음 → 드리프트가 있어도 구조적으로 green | check_docs_sync.py 에 (a) cycle-history.md 최신 TOC 항목·헤딩 섹션의 `단위 N` 값을 5번째 비교 지점으로 추가하고, (b) 선택적 `--verify-live`… |
| 25 | docs | `CLAUDE.md:320` | P0 대응 가드(check_retro_cadence.py)만 기계 배선 없음 — 나머지 3종은 CI 차단, 이것만 문서 지시 + advisory | advisory 성격(회고 진입은 사람 판단) 자체는 타당하므로 차단으로 바꿀 필요는 없으나, **호출을 문서에서 떼어낸다** — SessionStart 훅(.claude/settings.json,… |
| 26 | docs | `docs/STATE.md:8` | STATE.md "최신" 블록 제목의 PR 범위가 자기 본문보다 좁음 (총 17 PR #1077~#1092 vs 실제 #1094 까지) | STATE.md:8 제목을 "총 19 PR #1077~#1094" 로 정정한다. 나아가 STATE.md:6 갱신 규칙 (1) 항에 "**최신 블록 제목의 PR 범위·건수도 함께 갱신**" 을 (0)… |
| 27 | decision | `scripts/check_noqa_sideeffect.py:30` | 회고가 실측까지 마친 처방 기전(flake8 --disable-noqa)이 자작 정규식으로 교체됐으나 대체 사유 미기록 (정책 3) + 탐지 범위 축소 | 정책 3(자율 판단 사후 보고) 적용 — 회고 처방과 다른 기전을 채택할 때는 PR 본문에 '처방 X → 채택 Y, 사유' 1줄 의무화. 본 건은 후속 PR 에서 `--disable-noqa` 스텝… |
| 28 | decision | `scripts/check_noqa_sideeffect.py:87` | 신규 CodeQL 가드 3종의 scope 가 '위험 클래스'가 아니라 '직전 알림이 난 디렉토리'로 그어짐 — 3회 재발의 구조적 원인이 미해소 | 가드 scope 결정 규칙을 '알림 발생 위치' → '해당 CodeQL 룰이 스캔하는 전 경로'로 전환. 즉시 조치는 `check_noqa_sideeffect.py` 의 diff 필터를 `tests… |
| 29 | decision | `docs/_archive/reports/2026-07-18-retrospecti…` | P1 테마 2건(E·F)과 P2 '결정 traceability' 클러스터 4건이 조치도 유예 기록도 없이 소실 — 회고 보고서 단계에서 탈락 | 회고 보고서에 finding→disposition(조치 PR / 유예+사유 / 기각+사유) 전수 매핑 표를 필수 섹션으로 추가하고, cycle-history '보류' 줄이 그 표에서 파생되도록 강제… |
| 30 | decision | `tests/unit/hooks/test_posttool_pytest_smoke.…` | PostToolUse 훅의 유일한 가치 경로(main·❌ 배너·타임아웃 분기)에 테스트 0 — false-green 을 봉인한 PR 이 신호 생성 경로엔 positive control 없음 | 실패하는 임시 테스트를 스코프 영역에 넣고 `main()` 이 ❌ 배너를 출력하는지 확인하는 통합-lite 테스트 1건 추가(가드의 가드). 스코프 매핑은 `src/<area>` 편집 시 `test… |
| 31 | tooling | `.claude/hooks/posttool_pytest_smoke.py:101` | posttool_pytest_smoke.py (#1082) 의 ❌ 배너는 Claude 에게 전달되지 않는다 — false-green 의 '전달 채널' 절반이 미봉인 | 실패(rc != 0) 시에만 `hookSpecificOutput.additionalContext` JSON 으로 배너+tail 을 주입(doc_review_gate 선례 재사용)하거나 exit 2 … |
| 32 | tooling | `scripts/check_noqa_sideeffect.py:87` | 자초 CodeQL 재발의 구조적 원인 = 모든 turn-0 가드가 '직전 사고가 난 디렉토리'로만 스코프된다 (CodeQL 은 repo 전역 스캔) | 디렉토리별 개별 스크립트를 룰별 탐지기 1개 × repo 전역 스코프로 재편(제외 목록 방식). 최소 조치 2건: `check_noqa_sideeffect.py` 의 pathspec 을 `tests… |
| 33 | tooling | `docs/STATE.md:12` | STATE.md 의 가드 커버리지 서술 과대 — '3회 재발 turn-0 봉인' / '전역 AST 가드' 가 실스코프와 불일치 | STATE.md:12/18 문구를 실스코프로 정정("tests/ PR diff 한정", "scripts + .claude/hooks 한정") 하거나, 스코프를 서술에 맞춰 확대. 이후 가드 서술에는… |
| 34 | tooling | `tests/unit/scripts/test_check_dead_code.py:1…` | CI 차단 가드 2종의 단위 테스트가 순수 함수만 검증 — #1094 가 결함을 찾아낸 plumbing 계층은 무커버리지 | 가드별 tmp git repo fixture(init → 커밋 2개 → 위반 도입) 기반 `main()` end-to-end 테스트 각 2건(위반 감지 exit 1 / 클린 exit 0) 추가. 본… |
| 35 | tooling | `scripts/check_noqa_sideeffect.py:70` | check_noqa_sideeffect.py `find_violations(path, diff_text)` 의 path 파라미터가 미사용 — dead parameter | `path` 를 제거해 `parse_added_noqa_imports` 를 직접 호출하거나, 스코프 확대(전역 pathspec) 시 제외 목록 판정을 실제로 `path` 로 수행하도록 구현. 어느 … |
| 36 | code | `.github/workflows/ci.yml:109` | main 브랜치에 required status checks 부재 — 이번 창의 신규 가드 4종이 머지 전제조건이 아님 | PRIMARY ruleset 에 `required_status_checks` 룰 추가 — 최소 `lint-changed-tests`, `repo-integrity`, 단위 테스트 job 을 requ… |
| 37 | code | `scripts/check_noqa_sideeffect.py:87` | check_noqa_sideeffect 가 alembic/ 을 보지 못함 — 역사적 py/unused-import 18건 중 9건이 alembic/env.py | `_changed_test_files` → `_changed_scanned_files` 로 일반화하고 pathspec 을 `tests/`, `alembic/`, `src/`, `scripts/` 로… |
| 38 | code | `.claude/hooks/posttool_pytest_smoke.py:105` | PostToolUse 스모크 훅의 ❌ 배너가 Claude 컨텍스트에 도달하지 않음 — 완주는 회복됐으나 가시성은 미회복 | 실패(rc not in (0, None))일 때만 배너를 stderr 로 출력하고 exit 2 반환(편집은 이미 완료된 뒤라 차단 부작용 없음, 신호만 Claude 에 주입). 또는 JSON 출력으… |
| 39 | code | `tests/unit/scripts/test_empty_except_guard.p…` | py/empty-except 동일 shape 에 상반된 disposition 이 미조정 — 가드 스코프가 그 모순을 회피하는 형태로 좁혀짐 | 둘 중 하나로 통일: (a) github_review.py:115 에도 사유 주석을 달고 `_SCOPED_DIRS` 를 `src` 포함으로 확장(#231 dismiss 를 해제) 또는 (b) src… |
| 40 | process | `scripts/check_noqa_sideeffect.py:87` | 자초 CodeQL 3회 재발의 구조적 원인 = 가드 스코프가 매번 '직전 사고가 난 디렉토리'에만 붙음 (실증: src/·alembic/ 무음 통과) | 3 가드의 스코프를 디렉토리가 아니라 **CodeQL 이 스캔하는 전 파이썬 영역(src/·tests/·scripts/·alembic/·.claude/)** 으로 통일하되 diff-scoped(AD… |
| 41 | process | `docs/_archive/reports/2026-07-18-retrospecti…` | 회고 P1 7 테마 중 E·F 2건 무조치·무기록 — 리포트 헤더가 '6 테마'로 오기재된 것과 상관 | (a) 리포트 헤더 :45 를 "7 테마" 로 정정(append-only 정신상 정정 사유 각주). (b) 테마 E(신뢰경계 액션 전수 열거)를 정책 16 진화 §공유 로직 grep 전수에 '의미적… |
| 42 | process | `scripts/check_retro_cadence.py:26` | 카덴스 기계화가 정책의 OR 2조건 중 1개만 구현 — 세션 축 미충족 시 '✅ 여유' 오신호 | (a) 즉시(저비용): 미돌파 메시지를 "✅ PR 축 여유 (N/15) — ⚠️ 세션 축(≥3 세션)은 미측정, Claude 판정 필요" 로 정정해 오신호 제거. (b) 세션 축 측정: 회고 경계 … |
| 43 | decision | `scripts/check_retro_cadence.py:93` | 카덴스 카운터가 자기 회고의 remediation PR 을 다음 회고 임계에 계상 — 매 회고 직후 100% 발화하는 구조(경보 피로 → 인지의존 재이전) | 경계를 '회고 리포트 커밋' 이 아니라 '회고 remediation 종료' 로 이동하거나, 계상에서 회고 파생 PR 을 제외한다. 실행 가능한 최소안: 커밋 제목에 '회고' / 'retro' 가 포… |
| 44 | decision | `scripts/check_dead_code.py:118` | 신규 CI 가드 2종(#1081·#1083)에 긍정 통제 부재 — git 실패와 '위반 없음'이 구분 불가하게 ✅ exit 0 (#1094 와 동일 결함 클래스, 백필 안 됨) | 두 가드에 end-to-end 긍정/부정 통제 각 1건씩 추가 — tmp_path 에 git init → 위반 커밋 생성 → `main(["", base, head])` 가 **1** 반환 단언(긍… |
| 45 | decision | `scripts/check_retro_cadence.py:26` | 카덴스 기계화가 정책 트리거 2축 중 1축만 구현 — 문서는 '기계 신호로 승격' 으로 기술해 커버리지 과대표현 | 둘 중 하나를 택할 것 — (a) 세션 축 구현: 회고 boundary 이후 고유 커밋 author-date 일자 수를 세션 프록시로 카운트해 ≥3 이면 동일 발화(git 만으로 측정 가능, 의존성… |
| 46 | process | `scripts/check_dead_code.py:123` | #1083 dead-code 가드가 head_sha 가 아닌 **워킹트리**를 참조 스캔 — 자기 동기 사례(#1060) 리플레이가 green 통과 | `_total_references` 를 `git show <head>:<path>` 또는 `git ls-tree -r <head>` 기반으로 바꿔 head 트리를 읽게 하거나, head 인자를 제거… |
| 47 | process | `scripts/check_noqa_sideeffect.py:87` | turn-0 CodeQL 가드가 `tests/` 로만 스코프 — py/unused-import 이력의 30%(65/213)가 구조적 사각, alembic/env.py 는 모델 추가마다 재발 예약 | check_noqa_sideeffect.py 스코프를 `tests/` → `tests/ alembic/ src/ scripts/`(정책 17 안정성 유지 위해 여전히 ADDED 라인 한정)로 확장.… |
| 48 | process | `docs/runbooks/owed-verification.md:13` | owed 원장(#1084)은 회신 유도 메커니즘이 아니라 **기록 파일** — 신설 세션 내 10 PR 동안 갱신 0, 체크리스트 미배선, 안전등급 #1058 노화 | check_retro_cadence.py 와 같은 SessionStart 훅에서 원장의 ⏳ 행 수(특히 🔴 안전등급 섹션)를 파싱해 배너 출력 — '측정 신호' 로 승격. 최소한 CLAUDE.md … |
| 49 | process | `tests/unit/scripts/test_empty_except_guard.p…` | 동일 CodeQL 룰(py/empty-except)에 과거 7회 **dismiss** vs 이번 fix+가드 — dismiss 판단이 규칙으로 인코딩되지 않아 매 재발이 새로 재판됨 | (a) dismiss 결정을 `.claude/rules/<area>.md` 에 '이 룰의 허용 형태' 로 1줄씩 인코딩해 다음 발생 시 재판 비용을 0 으로 만들고, (b) _SCOPED_DIRS … |
| 50 | process | `tests/unit/scripts/test_check_dead_code.py:1…` | 신규 CI 가드 2종에 end-to-end 긍정통제 부재 — #1094 가 준 교훈(가드가 눈멀어도 green)이 형제 가드에 미적용 | 각 가드에 '알려진-불량 커밋 리플레이' 테스트 1개씩 추가 — check_dead_code 는 050bab63(#1060 find_orphaned) 로 exit 1 + 함수명 출력 단언, chec… |
| 51 | process | `scripts/check_dead_code.py:82` | diff-scoped 가드 3종이 git 실패를 '깨끗함' 으로 취급 — 잘못된 base SHA 에 확신에 찬 green(fail-open) | `_git` 에서 returncode != 0 이면 stderr 와 함께 exit 2(=가드 오류, green 아님)로 loud-fail. 최소한 `git rev-parse --verify <bas… |
| 52 | docs | `docs/STATE.md:20` | 회고 카덴스 P0 시정의 '필수' 절반(STATE.md 추적셀)이 누락되고 '(선택)' 절반만 구현 — 여전히 능동 호출 의존 | STATE.md 종합 수치 표에 '회고 카덴스' 행 1개 추가(직전 정식 회고 날짜·기준 PR#·이후 머지 PR N / 임계 15) 하고, check_docs_sync.py 에 이 셀 ↔ check… |
| 53 | docs | `docs/architecture.md:164` | architecture.md scripts/ 트리가 이번 사이클 신설 가드 3종 + 기존 하위 디렉토리 2개 누락 — 6-step ⑥ 의무 문구가 src/ 로만 좁혀진 구조적 원인 | 6-step ⑥ 문구를 '`src/`·`scripts/`·`e2e/` 트리'로 확장하고, scripts/ 트리 누락 3종 + 하위 디렉토리 2개를 등재한다. 나아가 architecture.md 의 … |
| 54 | docs | `scripts/check_docs_sync.py:29` | check_docs_sync.py 가 배지의 integration 세그먼트를 캡처하지 않고 total = unit + integration 산술 불변식도 검사하지 않음 — 부정 통제 테스트도 같은 … | 두 정규식에 integration 그룹을 캡처 추가해 4지점 대조에 포함시키고, `int(total) == int(unit) + int(integration)` 산술 단언을 추가한다. 부정 통제 테… |
| 55 | docs | `.claude/hooks/doc_review_gate.py:23` | doc_review_gate 등급 매트릭스가 README.md 만 심의하고 쌍둥이 README.ko.md·architecture.md·cycle-history.md·runbooks 는 전부 skip | _IMPORTANT 에 `^README\.ko\.md$`·`^docs/architecture\.md$`·`^docs/runbooks/.+\.md$` 를 추가한다. cycle-history.md 는 … |
| 56 | docs | `docs/cycle-history.md:160` | 진행 중인 #1094 브랜치가 STATE.md·배지만 갱신하고 cycle-history.md 는 미갱신 — 두 서사 문서가 세션 범위에서 불일치 | #1094 브랜치에 cycle-history.md 후속 2 항목을 함께 추가하거나(6-step ⑤ 원자 준수), 인라인 STATE 갱신을 되돌리고 세션 종료 trailing sync PR 로 3종을… |
| 57 | tooling | `scripts/check_noqa_sideeffect.py:87` | noqa 가드 스코프가 tests/ 한정 — 역대 py/unused-import 최대 파동(alembic/env.py 9건)을 실측상 통과 | pathspec 을 `tests/` → `tests/ alembic/ src/` 로 확장(신규 ADDED 라인 한정이라 기존 30건 legacy 는 무영향 — 정책 17 안정성 보존). ci.yml… |
| 58 | tooling | `tests/unit/scripts/test_empty_except_guard.p…` | empty-except 가드의 CodeQL parity 휴리스틱이 저장소 내 반례로 반증됨 (src/gate/github_review.py:115) | parity 근거를 1 관측 귀납에서 실제 룰 정의 대조로 교체하거나, 휴리스틱임을 docstring 에 명시하고 불변식 스코프를 현행(가드/훅 계층)으로 못박아 '일반 봉인' 으로 오독되지 않게 … |
| 59 | tooling | `.claude/hooks/posttool_pytest_smoke.py:60` | PostToolUse 스모크 훅 커버리지가 blast radius 와 역상관 — 최고 위험 6파일만 collection-only 로 강등 | src 직속 파일에 대한 명시 매핑 테이블 추가(예: config.py→`tests/unit/test_config.py`, crypto.py→`tests/unit/test_crypto*`, data… |
| 60 | tooling | `scripts/check_dead_code.py:29` | dead-code 가드 스코프가 repositories/services 한정 — 문서화된 동형 선례(src/gate)는 스코프 밖 | 위 P1(이름 충돌 오탐)을 먼저 해소한 뒤 스코프를 `src/gate/`·`src/worker/` 로 확장. 순서가 중요하다 — 이름 매칭 상태로 스코프만 넓히면 오탐(false-negative)… |
| 61 | code | `scripts/check_noqa_sideeffect.py:87` | 신규 import 가드 2종이 tests/ 전용 — src·alembic 은 실제로 12건 py/unused-import 를 낸 영역인데 무방비 | diff 스코프를 `tests/` → `tests/ src/ alembic/` 로 확장(신규 ADDED 라인 한정이므로 legacy 30건은 여전히 무관 = idiom churn 0). src 영역… |
| 62 | code | `scripts/check_noqa_sideeffect.py:110` | check_noqa_sideeffect 가 출력하는 시정 처방이 alert #546 을 자초한 미완성 패턴 그대로 | 출력 문구를 testing.md:33-38 의 3줄 완전 형태(할당 + `if any(...)` + `raise RuntimeError`)로 교체하고, 'CodeQL py/unused-global-… |
| 63 | code | `tests/unit/hooks/test_posttool_pytest_smoke.…` | 스모크 훅만 4 신규 가드 중 유일하게 red-path 긍정 통제가 없음 (#1094 형 실명 재현 가능) | tmp_path 에 일부러 실패하는 테스트 파일을 둔 미니 트리를 만들고 main() 을 stdin JSON 으로 구동해 (a) 배너가 ❌ 를 포함 (b) rc 해석이 0/None/비0 3분기 모두… |
| 64 | code | `.claude/hooks/posttool_pytest_smoke.py:62` | 스모크 훅 영역 매핑이 루트 단위 테스트 1717건(31%)을 구조적으로 제외 — 스스로 지목한 #1041 클래스를 못 잡음 | 타깃을 디렉토리 단독 대신 `tests/unit/<area>` + 루트 파일 이름 매칭(`tests/unit/test_<area>*.py`) 합집합으로 확장. 실측상 tests/unit/ui 338… |
| 65 | code | `scripts/check_dead_code.py:74` | check_dead_code 참조 카운트가 속성명 충돌에 무방비 — 저장소 계층 관용 명명에서 대량 false-pass | (a) 정의 파일을 참조 집계에서 제외하고 (b) Attribute 매칭 시 `node.value` 가 해당 모듈 별칭인지 확인(`repo.find_orphaned` 형), 또는 (c) 최소한 이름… |
| 66 | code | `tests/unit/scripts/test_empty_except_guard.p…` | 빈 except 불변식이 가드 계층에만 적용 — src/tests/e2e 의 10건은 사각지대 (사고 발생 지점만 방어) | _SCOPED_DIRS 를 src/tests/e2e/alembic 으로 확장하고, 기존 10건에 사유 주석 1줄씩 부여(정책 17 안정성: 동작 변경 0, 주석만). 확장이 부담이면 최소한 src/… |
| 67 | P0 카덴스 가드 — 미검증 양식(가드가 무력한데 green) | `scripts/check_retro_cadence.py:28` | cwd 상대경로로 인해 repo 루트 밖 실행 시 무음 skip — 테스트가 cwd 를 고정해 구조적으로 탐지 불가 | `_ROOT = Path(__file__).resolve().parents[1]` 앵커 도입 후 `_REPORTS_DIR = _ROOT / "docs/_archive/reports"` 로 교체하고,… |
| 68 | railway cron 관측 신뢰성 ↔ owed 원장 | `railway.toml:45` | 신규 가드 4종(#1080~#1083)은 전부 Python AST/diff 스코프 — 인프라 설정 계층(railway.toml)에 turn-0 가드 0건 | `tests/unit/scripts/test_railway_cron_shape.py` 신설 — railway.toml 의 각 `[[deploy.cronJobs]]` command 에 대해 (1) `… |
| 69 | 툴링 재사용 / 자기 세션 내 패턴 미적용 | `scripts/check_retro_cadence.py:59` | 동일 세션이 46분 전에 만든 재사용 가능한 aging 평가기(check_retro_cadence)를 원장에 적용하지 않음 — 원장에 소유자·기한·에스컬레이션 필드 전무 | 원장 표에 '등재 사이클' 컬럼 1개 추가 후 check_retro_cadence 의 evaluate 를 재사용해 '등재 이후 머지 N건 초과 ⏳' 행을 loud 로 표면화. 회고 조치 설계 시 '… |
| 70 | 원장 운영 / 부분 방면 미반영 | `docs/runbooks/owed-verification.md:25` | #1092 가 #1075 행의 'pending 행 보존' 검증을 PostgreSQL 에서 코드 증명했으나 cross-reference 없이 행은 원래 범위 그대로 ⏳ | #1075 행 검증 방법을 'cron 실제 발화 + 로그 라인 관측'으로 축소하고 'DELETE 집합 정확성·pending 보존 = #1092 로 PG 코드 증명 완료' 각주 추가. 일반화: owe… |
| 71 | disposition traceability | `docs/_archive/reports/2026-07-18-retrospecti…` | P2#5·6·11·25·35 — confirmed 5건이 저장소 어디에도 없음(복구 불가 소실) | 리포트 템플릿에 'finding ID 커버리지 N/N + 미배정 ID 목록' 필수 필드를 넣고, 리포트의 ID 집합이 findings.json 의 ID 집합과 일치하는지 검증하는 파싱 가드를 CI … |
| 72 | guard efficacy | `scripts/check_retro_cadence.py:46` | 카덴스 가드(#1080)가 '회고 실행 여부'만 측정 — finding 처리 여부는 무측정이라 green 신호가 소실을 은폐 | 가드 판정에 disposition 축을 추가한다 — owed-verification.md 동형의 append-only `docs/runbooks/retro-disposition.md` 원장을 신설하… |
| 73 | ledger operation | `docs/runbooks/owed-verification.md:15` | owed 원장(#1084)이 기록 전용 — 6행 전부 ⏳ 누적, 안전등급 2건은 정책 5 NEW-P0-N 회신 의무 미이행 | check_retro_cadence.py 동형의 stdlib advisory 카운터(`scripts/check_owed_verification.py`)를 세션 시작 체크리스트에 배선 — ⏳ 행 존재… |
| 74 | guard efficacy | `CLAUDE.md:320` | 카덴스 가드의 실행 트리거 자체가 여전히 문서-only — '기계화' 선언의 절반만 이행 | SessionStart 훅 또는 최소한 pre-push 훅에 advisory 실행을 배선한다. 비차단 성격은 유지하되 실행 자체는 문서 준수에 의존하지 않아야 '기계화'가 성립한다. 메모리에 기록된… |
| 75 | disposition traceability | `docs/cycle-history.md:160` | 보류(defer) 기록이 미처리 ~30건 중 1건뿐 — 나머지는 adopt/defer/reject 어느 것도 아닌 무상태 | 완료 6-step ⑤(STATE/cycle-history 동기화)에 'finding 원장 갱신'을 하위 항목으로 추가하고, 원장 스키마를 `· finding ID · 요약 · disposition(… |
| 76 | remediation completeness | `docs/STATE.md:11` | P0 조치 3건 중 2번(STATE.md 회고 추적셀) 미구현이며 대체·보류 기록도 없음 | A1 카운터가 추적셀을 기능적으로 대체한다면 그 판단을 원장에 'superseded by #1080' 로 1줄 기재하고 종결한다. 대체가 아니라면 추적셀을 추가하되, 갱신 강제 수단 없는 셀은 st… |
| 77 | memory/docs drift — 창 종료 시점 미반영 | `` | MEMORY.md 인덱스·메모리 헤더가 #1085 에서 동결 — 창 마지막 2 PR(#1093·#1094)의 최고가치 gotcha 2건 전량 유실 | 메모리 본문에 §후속 3(#1093·#1094) 추가 + 인덱스/frontmatter 를 `#1077~#1094 (15 PR)` 로 갱신하고, line 45 잔여 항목에서 STATE sync 를 제… |
| 78 | 가드의 가드 — 신규 가드 4종 긍정 통제 부재 | `` | #1080~#1083 신규 가드 4종 전부 end-to-end 종료코드 긍정 통제 없음 — #1094 형(가드가 무력한데 green) 결함이 조합 계층에 그대로 남음 | 가드마다 tmp_path 픽스처 기반 종료코드 쌍 테스트를 추가한다 — 위반 fixture → `main() == 1`, 청정 fixture → `main() == 0`. 카덴스 카운터는 flaky… |
| 79 | 가드의 가드 — 스코프 정합 | `` | 가드 3종의 검사 스코프가 대응 CodeQL 룰의 스캔 스코프보다 좁음 — 과거 재발 지점 일부가 커버 밖 | 각 가드 docstring 과 rules 에 "커버리지 = 룰 표면의 부분집합, 잔여 = <디렉토리 목록>" 1줄을 명시한다(정책 3 자율 판단 사후 보고). 최소 확장으로 `check_noqa_s… |
| 80 | 정책 준수 — 6-step ⑤ 부분 이행 | `` | #1093·#1094 가 docs/cycle-history.md 에 미반영 — STATE 는 갱신됐으나 사이클 이력은 #1092 에서 끊김 | cycle-history 에 #1093·#1094 1줄 추가. 기계화는 `check_docs_sync.py` 확장이 저비용이다 — STATE.md 가 언급한 최대 PR 번호 ≤ cycle-histo… |
| 81 | 가드의 가드 — 관용구 드리프트 잔존 | `` | #1094 가 고친 encoding 관용구가 가드 스크립트 자신에는 미전파 — 4곳이 errors= 없이 strict decode | 4곳에 `errors="replace"` 를 추가해 6 사본을 단일 형태로 통일하고, `test_empty_except_guard.py` 와 동형의 AST 불변식 테스트를 하나 더 건다 — scri… |
| 82 | self-inflicted CodeQL — 관용구 드리프트 | `scripts/check_noqa_sideeffect.py:110` | 창 안의 remediation-자초 사건은 1건이 아니라 2건 — #1077(자초 CodeQL 수정 PR)이 #546 을 자초했고, 그 원인 패턴을 #1081 가드가 지금도 '해결책' 으로 출력한다 | `check_noqa_sideeffect.py:109-111` 의 출력 스니펫을 #1079 가 최종 확정한 loud-fail read 를 포함한 2줄 형태로 교체하고, `.claude/rules/t… |
| 83 | note-alert 분류 정책 부재 | `tests/unit/scripts/test_empty_except_guard.p…` | py/empty-except 는 신규 룰이 아니라 3라운드째다 — 과거 12건 중 5건은 '수용(dismissed)' 처리됐고, 동일 구문이 src/ 에서는 허용·scripts/ 에서는 가드 차단이… | CLAUDE.md 정책 14 에 note 등급 3-분기 결정 규칙을 명문화한다 — (a) diff 내 신규 = 차단(P0-1 SARIF 게이트가 자동 수행) / (b) legacy 존치 = 일괄 d… |
| 84 | 가드의 가드 | `tests/unit/scripts/test_empty_except_guard.p…` | #1094 가드가 주장하는 'CodeQL parity' 는 측정되지 않았고 실제로 CodeQL 보다 엄격하다 — 스코프를 넓히는 순간 오탐한다 | parity 주장을 코드로 바꾸거나 문구를 낮춘다. 실측 방법: 현재 dismissed/fixed alert 위치 집합을 골든 fixture 로 두고 탐지기 출력이 그 집합의 부분집합인지 단언하면 … |
| 85 | owed 원장 운영 | `docs/runbooks/owed-verification.md:13` | owed 원장(#1084)은 회신을 유도하는 메커니즘이 아니라 기록물이다 — 같은 세션이 P0 로 진단한 '문서-only 트리거' 클래스를 그대로 재생산했다 | `scripts/check_owed_verification.py` 를 추가해 원장 표를 파싱하고 안전 등급 행에 ⏳ 가 있으면 loud 배너를 출력, P1-3 에서 제안한 SessionStart 훅… |
| 86 | 가드의 가드 (구조적 근본 원인) | `tests/unit/scripts/test_check_dead_code.py:1…` | 긍정 통제가 '위험'이 아니라 '테스트 용이성 형태'에 따라 배분됨 — 4 가드 중 순수 술어형 2종만 통제 有, main() 부수효과형 2종은 통제 全無 | 가드/탐지기 신설 시 저작 시점 3-단언 체크리스트를 `.claude/rules/testing.md` 에 명문화: ① 긍정 통제(탐지기를 무력화하면 최소 1건 fail) ② 부정 통제(정상 입력에 … |
| 87 | remediation 완결성 (owed 원장 운영) | `docs/runbooks/owed-verification.md:1` | #1084 owed 원장이 P0 가 단죄한 '문서-only 시정' 패턴을 같은 창 안에서 재현 — 6/6 행 미회신 ⏳, 발화 기전 0 | 카덴스 카운터와 동일 취급: `scripts/check_owed_verification.py`(stdlib·advisory) 신설 — ⏳ 행 수 + 안전등급 행의 체류 사이클 수를 세션 시작에 lo… |
| 88 | 가드의 가드 (silent-pass 실패 모드) | `scripts/check_dead_code.py:82` | diff 기반 가드 2종이 git 실패 시 '✅ 위반 없음' 을 출력하고 exit 0 — 진짜 통과와 구분 불가 | `_git()` 에서 returncode≠0 이면 stderr 를 출력하고 exit 2(가드 실행 실패)로 fail-loud 처리. 최소한 `_changed_*_files` 단계의 diff 실패와 … |
| 89 | 자초 CodeQL 재발 (관용구 복사 드리프트) | `scripts/check_dual_import.py:102` | cp949 stdout 시정이 신규 4파일에만 적용되고 같은 CI job 의 형제 가드는 미소탕 — check_dual_import.py 는 Windows 통과 경로에서 크래시 | stdout 안전 재구성을 공용 헬퍼 1곳으로 추출(사용처 ≥3 이므로 정책 16 최소 추상화 기준 충족)하고 10종 스크립트에 일괄 적용. 회귀 가드는 test_empty_except_guard.… |
| 90 | remediation 완결성 (가드 범위 vs 사고 표면) | `scripts/check_noqa_sideeffect.py:87` | #1081 noqa 가드 범위가 tests/ 한정 — 정작 동일 룰 재발을 일으켰던 alembic/env.py(13건) 등 tests/ 밖 62건은 미커버 | 검사 범위를 `tests/`, `alembic/`, `src/` 로 확대(신규 diff 한정 원칙은 유지 — 기존 62건 legacy 무churn 은 그대로 보존되므로 정책 17 안정성 무손상). … |

---

## ⚠️ 미페어링 — 심각도 미확정 (7건)

cross-verify verdict 를 찾지 못한 항목이다. **원 심각도만 표기**하고 확정 집계에 넣지 않는다.

| # | 관점 | 원 심각도 | 요지 |
|---|------|-----------|------|
| 1 | P0 카덴스 가드 — 배선(wiring) vs 집행(execution) 비대칭 | ? |  |
| 2 | owed 운영 검증 원장 (#1084) 의 창 내 자기 stale | ? |  |
| 3 | 61 confirmed finding 의 건별 disposition 추적성 | ? |  |
| 4 | railway cron 관측 신뢰성 (P2#27) ↔ owed 원장 검증 방법 | ? |  |
| 5 | self-inflicted CodeQL — rule 클래스 vs 개별 rule 가드 | ? |  |
| 6 | 신규 가드 자체의 테스트 신뢰성 (false-green 자가 적용) | ? |  |
| 7 | 메모리 sync — 창 종료 시점 drift | ? |  |

---

## cross-verify 기각 (false-positive · 16건)

| 관점 | 제목 | 기각 사유 |
|------|------|-----------|
| tooling | noqa 가드 스코프가 tests/ 한정 — 과거 9건 alert의 발원지 alembic/env.py와 src/ 전체가 사각 | 인용 자체는 정확하나, 추론된 결함이 별도 가드로 반증됨.  **검증된 부분**: `scripts/check_noqa_sideeffect.py:87` 은 인용대로 `"--", "tests/"` 로 스코프를 한정한다(verbatim 일치). alembic/env.py 가… |
| docs | 카덴스 카운터가 squash-merge 제목 형태에 단일 결합 — merge-commit 전략에서 무음 과소집계(#1094형 … | 인용은 전건 정확하나, 주장된 실패 양태(무음 과소집계)가 실측으로 반증됨 — 방향이 정반대.  [검증된 사실] check_retro_cadence.py:36 = `_MERGE_PR = re.compile(r"\(#\d+\)\s*$")` EXACT 일치. `git lo… |
| docs | empty-except 가드의 CodeQL parity 가 단일 관측 기반 가정 — 범위는 src/ 제외, src/ 에 동형 … | 인용은 전부 실재하나, 결론을 떠받치는 핵심 사실 주장이 Code Scanning 이력으로 반증됨.  ■ 검증된 부분 - `tests/unit/scripts/test_empty_except_guard.py:23` = `_SCOPED_DIRS = ("scripts", "… |
| process | noqa 가드 범위가 tests/ 한정 — 스스로 정본으로 인용하는 alembic/env.py·src/ 는 사각 | 근거 사슬의 핵심 주장이 반증됨 — 보완 통제 미확인(파일 고립 독해) 전형.  [인용 검증: 전부 실재] check_noqa_sideeffect.py:87 `--", "tests/"` 범위 제한 ✓ / :111 안내문이 `alembic/env.py _REGISTERE… |
| tooling | 카덴스 카운터의 trailing `(#N)` 정규식이 프로젝트 자신의 sync-PR 제목 형태를 놓친다 — 과소 카운트 편향 | Citation verified: scripts/check_retro_cadence.py:36 is exactly `_MERGE_PR = re.compile(r"\(#\d+\)\s*$")`. But the claimed undercount does not occur i… |
| process | check_noqa_sideeffect 가 '미사용' 을 판정하지 않음 — 회고 처방(--disable-noqa)에서 이탈, … | 인용은 전부 실재 확인 (check_noqa_sideeffect.py:36-54 정규식-only, :109-111 안내문, retrospective.md:53 처방, ci.yml:102 hard-fail 배선). 그러나 결함 주장은 3중으로 반증됨.  **(1) 스크립… |
| process | 드리프트가 alert 원인이라 자기진단하고도 4 사본 통합 없이 주석만 4곳 패치 — 5번째 사본 재발 여지 | 인용은 전부 실재 확인(4 사본 line 정확·자기진단 원문 test_empty_except_guard.py:4-7 일치·b3c3ac2 stat 4파일×2줄+테스트1·_git 3사본 중 check_retro_cadence.py:85 만 OSError). 그러나 핵심 주… |
| decision | noqa 가드의 검사 범위가 사고 증거가 아니라 자매 가드(#979)의 범위에서 상속됨 — 3회 재발 중 최대 배치(alemb… | 인용 위치는 모두 실재하나(scripts/check_noqa_sideeffect.py:87 `-- tests/` 하드코딩, :19 docstring '#979 페어'), 핵심 주장 3 프롱이 실측으로 전부 반증됨.  (1) 범위-사고 불일치 주장 반증 — 가드의 선언 … |
| 원장 correctness / 시간차 결함 | #1090 이 #1073 owed 행의 검증 대상(analysis_attempts 흔적)을 best-effort 로 바꿨으나 … | 코드 관찰 자체는 사실이나(#1090 이 흔적 write 실패를 삼키고, sweep 은 cron_service.py:53 find_orphaned 를 통해 전적으로 흔적 의존), 주장된 결함 — "#1073 행 문안이 부정확해져 잘못된 안심을 유도" — 은 행의 실제 … |
| 메커니즘 검증 / 미배선 산출물 | 원장의 의도된 라이브 경로(머지 시 행 추가)가 단 한 번도 실행되지 않음 — 수록 6행 전부 신설 이전 backfill, 이… | 모든 사실 근거는 실측 재확인됨 — 그러나 추론이 성립하지 않는다.  【검증된 사실 (전부 정확)】 - `git log -- docs/runbooks/owed-verification.md` → 정확히 2 커밋(e2098d3 14:38 #1084 신설, 7608656 1… |
| 자율 판단 보고 경로 / 공시 유실 | commit body 에 공시된 미검증 운영 항목(#1090 idle-in-tx 2 커넥션 창)이 원장으로 흘러들지 않음 — … | 두 축 모두 반증됨.  **1. 핵심 전제("공시 → 원장 연결이 없다")가 사실과 다름.** 원장 현행 6행 중 #1071·#1072·#1073·#1075 4행이 직전 웨이브(#1068~#1075) PR 본문 공시에서 그대로 유입된 항목이다. 실측: `git log … |
| disposition traceability | P2#24/37(doc_review_gate ROI) 무처리·무기록 — 창 내 6 docs 커밋 × 3 Haiku ≈ 18 호… | file:line 인용 3건 전부 정확 실증 — doc_review_gate.py:15-21 _CRITICAL(^CLAUDE\.md$·^docs/STATE\.md$), :142 _HAIKU_MODEL, :201 call_agents_parallel(3 에이전트), gi… |
| disposition traceability | P2#23/26(로드맵 tier 재분류) 무처리 — 일괄 High-tier 라벨 잔존, 같은 줄 내 자기모순 | 인용 실측 OK: `docs/cycle-history.md:174` 에 '전부 사용자 결정 선행(정책 15 High-tier)' 과 '관측성(… → 코드전용 착수 후보)' 가 동일 문장에 공존하며, 창 내 이 줄을 수정한 커밋 없음도 사실(`git log -L 170,… |
| 가드 범위 미달 | 가드 스코프가 '룰이 적용되는 표면' 이 아니라 '직전 사고가 난 디렉토리' 에 맞춰져 있다 — 자초 alert 12건 중 9… | 인용 3건은 실측 정확(check_dead_code.py:29 `_SCOPED_DIRS=("src/repositories/","src/services/")`, check_noqa_sideeffect.py:87 및 check_dual_import.py:73 의 `-- t… |
| 자초 CodeQL 재발 (룰 계열 커버리지) | py/empty-except 가드 범위가 사고 발생 레이어에만 한정 + 'CodeQL parity' 주장 미검증 (로컬 탐지기… | 근거의 핵심 판별 증거가 실측으로 반증됨. (1) "py/empty-except 알림은 #547~#549 3건뿐, 위 8곳은 CodeQL 미발화" = 오측. `gh api ... -f state=all --jq 'select(.rule.id=="py/empty-exce… |
| 가드의 가드 (배선 커버리지 갭) | PostToolUse 매처가 MultiEdit 미포함 — PreToolUse 는 포함하는데 스모크만 누락, 배선 단언도 0건 | 모든 인용 문자열은 정확하나 영향 추론이 반증됨 — MultiEdit 는 현 하네스의 live tool 이 아니다.  **인용 재확인 (전건 일치)**: settings.json:5 PreToolUse=`"Write·Edit·MultiEdit"`, :22 PostToo… |
