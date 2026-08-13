# backlog 종결 항목 원문 보존 (2026-08-13 압축)

> 🔴 **이 문서는 실행 대상이 아닙니다** — `docs/backlog.md` 의 ✅ 종결 행 **원문**을 보존한 기록입니다.
> 현재 유효한 일감은 언제나 `docs/backlog.md` 본문이며, 여기는 **왜 그 항목이 그렇게 닫혔는지**를 봅니다.

2026-08-13 압축에서 `docs/backlog.md` 의 ✅ **39행**을 본문에서 stub 으로 줄이고 원문을 여기 옮겼다.

🔴 **본문 stub 은 잔여를 보존한다** — ✅ 40행 중 **21행이 미해결 잔여를 담고** 있었고,
그중 **17행은 어느 열린 행에도 귀속되지 않았다**(실측). 잔여를 지우면 *"완료로 표시된 미결"* 이
통째로 사라진다(제안서 `#1334` §3-A 가 **R41 완전성 축의 재발**로 경고한 형태).
그래서 stub 에 `🔴 잔여:` 한 줄을 남기고 전문만 여기로 옮겼다.

---

<a id="r35"></a>

## R35

| **R35** | ✅ 완료 (`#1275`) | 🔴 **[P0] 문서 심의 게이트가 응답 절단을 '승인'으로 처리 — CRITICAL 문서 편집이 무흔적 통과** | **기전**: `.claude/hooks/doc_review_gate.py` `max_tokens=512`(당시 `:357`, 2026-08-05 실측 `:531`) → `stop_reason` 미독 → `json.loads` 실패 → `decision="approve"` → `sys.exit(0)` **무출력**. 🔴 line 인용은 이후 편집으로 전건 drift 했다 — **완료 행의 line:span 은 당시 값이므로 재작성하지 않고 현재 값을 병기**한다(정책 6). 심각도와 fail-open 확률이 **정비례**한다(리뷰어가 할 말이 많을수록 잘려서 승인). 부수 축 = `:151` `r.get("decision","approve")` 로 **스키마 drift·키 누락·`results=[]` 도 전부 approve**. 🔴 **Grok `019fc81b` HOLDS + 로컬 재현**(`{"decision":"block"…` 으로 *시작한* 절단 JSON 이 approve 로 뒤집힘). 🔴 **`check_guard_fail_open`(B8)은 이 클래스를 원리적으로 못 본다** — 훅이 `re` 를 쓰므로 후보에서 제외되고 B8 은 decision 기본값을 검사하지 않는다. **반증 수단**: 절단 응답 픽스처로 훅 end-to-end 호출 시 stdout 이 비지 않는가(= inoperative 표기 발화). 🔴 **freeze test 가 반대 극성** — `tests/unit/hooks/test_doc_review_gate.py:211` 이 *"JSON 파싱 실패 시 approve로 fallback"* 을 **정상 동작으로 고정**한다. 시정 시 그 테스트가 RED 가 되는 것이 정답이다 |

<a id="r36"></a>

## R36

| **R36** | ✅ 완료 (`#1275` + `#1276` 근본원인) | **심의 게이트 무동작 3형태 중 2형태가 '정상 판정'과 구별 불가 + 예외 원문 폐기** | **기전**: `#1257` 은 **자격증명 부재** 한 형태에만 `_NO_CREDENTIALS_BANNER`(`:280`)를 만들었다. 나머지 둘 — (a) 호출 실패(`:375` `decision="warn"`) (b) 파싱 실패(`:373` approve) — 는 진짜 심의 결과와 같은 모양을 쓴다. 세션14 가 **8회+ 실제로 앉아 있던 상태가 (a)** 이고, 그 `detail`(예외 원문)이 출력에서 통째로 버려져 원인을 아무도 몰랐다. **반증 수단**: 3 에이전트 전건 실패 payload 주입 시 출력이 *"3/3 미심의"* 를 명시하는가(문자열이 아니라 payload 구조 단언). 🔴 R33-a 가 "키 설정 완료 ✅" 로 닫혀 있으나 실패 축은 **호출 축**이었다 — 원장이 잘못된 축을 닫았다  🔴 **해소 + 근본원인 확정(2026-08-04)**: `#1275` 가 예외 원문을 출력에 싣자마자 **다음 편집에서 즉시** `'utf-8' codec can't encode characters … surrogates not allowed` 가 드러났다 — 프롬프트의 lone surrogate 가 httpx 인코딩에서 터져 3 에이전트가 동시에 죽고 있었다. **자격증명 축이 아니었다**(R33-a 의 "키 만료/크레딧 재확인" 은 오진, 철회). `#1276` `_scrub_surrogates()` 봉인 후 **라이브 3-판정 실증**(impact=approve · consistency=warn · quality=approve, RC=0). 이 항목이 R36 의 존재 이유를 그대로 증명했다 — 원인은 내내 **버려지던 예외 문자열 안에** 있었다. |

<a id="r37"></a>

## R37

| **R37** | ✅ 완료 (`#1276` — 잔여 GROK-1 아래 명시) | **심의 게이트가 6-step ⑤ STATE.md 동기화 편집을 block 할 수 있다 — 필수 절차를 가드가 차단** | **기전**: `apply_veto_matrix`(`:135~161`)에 **"확인 불가 ⇒ block 아님"** 규칙이 없고, `critical` 등급에서 `consistency` 의 block 이 그대로 `deny` 로 간다(`:161`). 🔴 **원 finding 의 기전 서술은 반증됐다 — 그대로 쓰지 말 것**: *"종합수치 라인이 char 11132 라 심의자가 못 본다"* 는 **거짓**이다. 실측 = `6607` @ offset **3023** · `6778` @ **3105** 로 4000자 예산 **안**에 있다(예산 밖은 `pylint`/`10.00` @ 11254~11263 뿐 = 부분 실명). Grok `019fc81b` 가 BROKEN 판정, Claude 재측정 일치, 이 회고 cross-verify 도 독립적으로 P0→P1 강등. **반증 수단**: `apply_veto_matrix` 에 강등 규칙 추가 후 같은 payload 가 `warn` 으로 떨어지는가  🔴 **해소(`#1276`)**: STATE 컨텍스트 예산 4000→16000 + `unable_to_verify is True` 인 consistency block 을 `critical` 에서도 warn 으로 강등(impact 은 제외 — 가드 자살 방지) + 에이전트 계약에 필드 등재(불변식 3). Grok `019fc878` 이 초판의 **진리값 fail-open**(문자열 `"false"` 가 실 불일치 차단까지 강등)과 **산문 결합 테스트**(substring 판정으로 바꿔도 green)를 재현 적발 → 같은 PR fix-up. 🔴 **잔여 = GROK-1**: `unable_to_verify` 는 구조적 검증 없이 **모델 신고에 의존**하므로 consistency 의 critical 거부권을 자발적으로 끌 수 있다(impact 이 하드 백스톱으로 남는다). **반증 수단**: 플래그를 항상 true 로 내는 뮤테이션에서 critical consistency deny 가 사라지는지 — 사라진다면 구조적 확인 축(예: 인용 존재 요구)이 필요하다. |

<a id="r38"></a>

## R38

| **R38** | ✅ 완료 (`#1282` — 잔여 3축 아래 명시) | **심의 게이트에 prompt caching 미적용 — 문서 편집 1회당 실측 85,434 입력 토큰** | **기전**: `:355` `client.messages.create` 가 동일 프리픽스(CLAUDE.md 전문 + AGENTS.md 전문 + STATE 머리 + 시스템 프롬프트 ≈28k)를 **3 에이전트에게 캐시 없이 3회 재전송**한다. 같은 리포의 `src/analyzer/io/ai_review.py` 는 이미 `cache_control` 을 쓴다 — 훨씬 자주 발화하는 훅에만 없다. 원장(R33)의 비용 수치와 **7.4배** 어긋난다. **반증 수단**: `cache_control` 적용 후 2회차 편집의 `cache_read_input_tokens` 가 0 이 아닌가 🔴 **해소(2026-08-04)**: 마커가 아니라 **순서** 문제였다 — 가변 부분(diff)이 프리픽스 맨 앞이라 `cache_control` 을 어디에 붙여도 원리적으로 히트 불가였다. 배치를 `system[0]=공유 컨텍스트(breakpoint) / system[1]=에이전트별 지시 / user=diff` 로 바꿨다. 라이브 실측: 1회차 `write=34,748 read=0` ×3 → 2회차 `write=0 read=34,748` ×3. 비용(FPE) 편집당 ≈110,000 → 1회차 ≈136,500(**+24%, 더 비쌈**) → 2회차 이후 ≈14,600(−87%), **손익분기 = 편집 2회**. 🔴 **증명 경계**: `usage` 에 캐시 항목 식별자가 없어 *'3 에이전트가 항목 하나를 공유'* 는 **증명되지 않는다**(설계상 성립일 뿐) — 초판 서술 "쓰기 1세트" 는 같은 로그의 `write×3` 과 자기모순이라 철회(Grok `019fcd10` 적발). 뮤테이션 6종 red(문자열 system 회귀·breakpoint 이동·블록 순서·opt-out 무력화·**호출부에서 `system[0]+=agent_prompt` 우회**·opt-out 호출부 무시). 🔴 **잔여 3축**: (a) `docs/STATE.md` 가 캐시 프리픽스에 있어 trailing sync 가 세션 중간 캐시를 무효화한다(컨텍스트에서 빼면 심의자가 수치 정합을 못 봄 — R37 이 되돌린 축과 충돌) (b) TTL 5분 + 병렬 첫 miss — 편집 간격이 5분 초과면 쓰기 3회 재지불 (c) **훅에 usage 관측면이 0** — 컨텍스트 예산이 4096 토큰 아래로 줄면 캐시가 **오류 없이 조용히** 죽는데 아무도 모른다. **반증 수단**: (c) = 컨텍스트를 4000 토큰 미만으로 줄인 뒤 `cache_creation_input_tokens` 가 0 이 되는데 가드가 red 가 되는가 |

<a id="r49"></a>

## R49

| **R49** | ✅ 완료 (`#1279` — 잔여 3축 아래 명시) | 🔴 **[P0] 심의 게이트가 한글을 mojibake 로 읽고 자기 손상을 근거로 차단** | **기전**: 훅은 payload 를 stdin 으로 받는데 `json.load(sys.stdin)` 는 텍스트 모드라 인터프리터 stdin 인코딩에 의존한다. **실훅 자식 프로세스 계측(2026-08-04)** = `stdin.encoding=cp949` · `errors=surrogateescape` · `utf8_mode=0` · `PYTHONUTF8` 미설정. 결과 (1) mojibake(`'문서 정합 가드'` 8자 → 13자) (2) 🔴 **lone surrogate 발생** — 디코드 불가 바이트가 U+DC80~U+DCFF 로 escape 돼 `.encode("utf-8")` 이 터진다. 즉 `#1276` 이 *"게이트를 2 세션 죽인"* 예외의 **발생원이 이 디코드**였고 `_scrub_surrogates` 는 증상만 지웠다. 실제로 정당한 `.claude/rules/guards.md` 편집을 *"인코딩 오류로 판독 불가"* 사유로 **차단**했다(R37 클래스). **해소**: `read_payload()` 가 바이트를 읽어 UTF-8 로 직접 디코드. 뮤테이션 4종 red(배선 되돌림·**죽은 호출**·`json.loads(sys.stdin.read())` 한 글자 우회·텍스트 모드). end-to-end 실증 = 같은 편집이 픽스 전 3/3 인코딩 차단 → 픽스 후 내용 지적 후 통과. 🔴 **잔여 3축**: (a) 게이트가 **비구체적 사유로 차단**한다 — `guards.md` 2-axis 설명 섹션이 *"모순"·"모호성"* 만 근거로 3회 연속 block 돼 결국 반영 못 했다(무엇을 고쳐야 하는지 알 수 없는 차단) (b) **prepend 편집을 교체로 오독** — 게이트가 `old→new` 쌍만 보여줘 섹션 앞에 끼워넣는 편집을 심의자 2/3 가 *"기존 규칙 삭제"* 로 판정했다(앵커를 앞 섹션 끝으로 옮기면 통과 = 회피 가능하나 표현 결함은 잔존) (c) **R38 비용이 이 결함으로 증폭** — 한 파일 편집에 게이트 5회 호출(편집당 ~85k 입력 토큰, `cache_control` 미적용 실측 = `grep -n cache_control .claude/hooks/doc_review_gate.py` 무결과). **반증 수단**: (a) 차단 사유에 `file:line` 또는 인용이 포함되는가 (b) prepend 편집에서 심의자가 '삭제' 로 판정하지 않는가 |

<a id="r50"></a>

## R50

| **R50** | ✅ 완료 (2026-08-04 — 리포 변경 없음, 로컬 정리) | **`.claude/worktrees/` 에 에이전트 worktree 7개 잔존 — 전 리포 grep 이 8배로 오염** | 🔴 **해소**: 제거 전 7건 전부 `git log <branch> --not main --oneline` 으로 **미머지 커밋 0건**을 확인한 뒤 `git worktree remove --force` + `prune`. 실효 실측 = `grep -rn "from cryptography.fernet" --include=*.py .` 결과 **64 → 8** (8배 감소, 남은 8건이 실제 리포 사용처). 🔴 이 항목은 **로컬 머신 상태**라 리포에 회귀 가드를 둘 수 없다 — 다음 세션에 다시 쌓이면 같은 절차를 반복한다(백그라운드 에이전트 `isolation: worktree` 사용의 정상 부산물). | **기전**: `git worktree list` 실측 7건(`agent-a0d0eb…` 등, 구 커밋 `d58de9f`·`5556601`·`0220bc0`에 고정). `git status` 는 깨끗하지만(무시 대상) **`grep -rn` 이 같은 심볼을 8번 반환**한다 — 이번 세션의 `from cryptography` 전수 조사가 실제로 그랬고, 인용 실측(정책 6)을 매번 수동 필터링해야 한다. 방치 시 디스크·검색 비용이 계속 는다. **반증 수단**: 각 worktree 에 미머지 커밋이 있는지 `git log <branch> --not main --oneline` 로 확인 후 `git worktree remove` — 제거 뒤 `grep -rn` 결과 수가 1/8 로 떨어지는가 |

<a id="r51"></a>

## R51

| **R51** | ✅ 완료 (`#1286` 훅 + `#1289` 서비스 3경로) | **Anthropic 경로가 free-form JSON 을 파싱한다 — 스키마 drift 방어가 영구 필요해진 이유** | **기전**: 2026-08-05 "모델 변경으로 무효가 된 과거 실수 기록 정리" 검토의 결론이다. 기록된 실수 중 **모델 귀속은 극소수**이고, 그 소수마저 지울 수 없는 이유가 이것이다 — 이 리포는 Anthropic 응답을 `json.loads` 로 직접 파싱한다(`src/analyzer/io/ai_review.py:300` null↔`[]`/str↔dict 방어 · `src/services/dashboard_service.py:868` · `src/services/repo_insight_service.py:442` · `.claude/hooks/doc_review_gate.py:178`,`:202` `"maybe"`/키 누락/문자열 `"false"`). 🔴 **비대칭 실측**: 2nd-LLM 검증자는 이미 구조화 출력을 쓴다(`src/verifier/openai_client.py:51`,`:101` `response_format={"type":"json_object"}`) — 즉 같은 리포 안에서 한쪽만 무방비다. Anthropic Messages API 의 `output_config.format`(json_schema) / 도구 `strict: true` 를 쓰면 **드리프트가 원리적으로 불가능**해지고, 그때 비로소 위 방어와 그 사유 기록을 **은퇴시킬 수 있다**(모델 이름이 바뀌었다고 은퇴하는 것이 아니다). 🔴 **주의**: 출력 형식 변경은 AI 리뷰 품질에 직접 닿으므로 정책 16 §명시 제외(사용자 사전 확인) 영역이다. **반증 수단**: 구조화 출력 적용 후 스키마 drift 방어를 제거해도 실 API 응답 100건에서 파싱 실패 0 인가 🔴 **부분 이행(`#1286`, 2026-08-05)**: 훅(`doc_review_gate`)에 `output_config.format`(json_schema) 적용 — 에이전트별 스키마(consistency 만 `unable_to_verify`), `additionalProperties: false` + 전 필드 required. 🔴 **지원 여부는 Models API 실측이 정본**이었다 — 캐시된 문서 표에는 `claude-sonnet-4-6` 이 빠져 있었으나 `capabilities.structured_outputs.supported` 는 haiku-4-5·sonnet-4-6·sonnet-5 **전부 true**. 라이브 실측: 1회차 `stop=end_turn` 전건(절단 0) · 2회차 전건 캐시 read. 🔴 **부수 발견**: 스키마가 캐시 프리픽스에 포함돼 회계가 갈렸다(impact·quality `34,974` / consistency `35,004`) — 엔트리가 늘지만 스키마 통일은 하지 않았다(통일 시 impact·quality 에 프롬프트에 없는 필드를 강제하게 된다). 🔴 **방어는 그대로 둔다** — 구조화 출력이 닫는 것은 스키마 축뿐이고 절단·호출실패·빈 결과는 열려 있다(R35/R36). **잔여**: `ai_review.py`(Sonnet, 제품 점수 직결) · `dashboard_service.py` · `repo_insight_service.py` — 출력 형식 변경이 리뷰 품질에 닿으므로 정책 16 명시 제외 영역, 별도 PR + 라이브 검증 필요 🔴 **완료 (`#1289`, 2026-08-05 — 사용자 사전 확인 후)**: 3경로 전건 `output_config.format` 배선 — `review_prompt.REVIEW_RESPONSE_SCHEMA`(11키, **프롬프트와 같은 모듈**에 둬 계약 drift 가 보이게) · `dashboard_service._INSIGHT_RESPONSE_SCHEMA`(`key_metrics` 원소 `{label,value,delta}`) · `repo_insight_service`(`{text}`). KO/EN/JA 3 프롬프트 변형이 선언하는 키가 **동일**함을 실측한 뒤 닫힌 스키마를 만들었다. **라이브 검증**: 실 API 1회 — `status=success` · 11필드 전건 채워짐 · 한국어 보존. 🔴 **배선 뮤테이션이 처음엔 green 이었다** — `output_config` 를 통째로 지워도 analyzer 단위 **1022건 전건 통과**. 스키마를 *정의만* 하고 실제로 실리는지는 아무도 안 보던 공허한 가드였고 `test_review_request_carries_the_response_schema` 로 닫았다. 🔴 **방어는 예고대로 남겨 뒀다** — 구조화 출력이 닫는 것은 **스키마 축뿐**이고 절단·호출실패·점수 범위 이탈은 `_parse_response`/`_coerce_score`/non-dict 가드가 계속 맡는다(R35/R36). 즉 **"이제 방어를 은퇴시킬 수 있다"는 R51 의 원 전제는 절반만 참이었다**. 🔴 **부수 P0 발견**: 그 라이브 검증이 아니었으면 못 봤을 별개 결함 — `.env` 의 `CLAUDE_REVIEW_MODEL=`(빈 값)이 기본값을 **빈 문자열로 덮어** 모든 AI 리뷰가 `400 model: String should have at least 1 character` → `api_error` 였다(pydantic-settings 는 `""` 를 *제공된 값*으로 본다). 단위 테스트는 env 를 읽지 않아 초록이고 고장은 **실 API 호출에서만** 드러난다. `field_validator` + 회귀 2건으로 봉인 |

<a id="r52"></a>

## R52

| **R52** | ✅ 완료 (30 → **0**) — CSP 앱 버그까지 해소 (`#1294`) | ~~**e2e 30건이 Linux CI 에서 실패한다 — 로컬 Windows 에서만 초록이던 스위트**~~ → **e2e 스위트가 앱과 14개월 drift — 플랫폼 무관하게 30건 실패** | **기전**: R7 배선(`#1288`) 직후 첫 실행이 `30 failed / 91 passed / 1 skipped`. **이 30건은 새로 깨진 것이 아니라 처음 관측된 것**이다 — 배선 전에는 어떤 워크플로도 실행하지 않아 상태를 알 수단이 없었다. 분포: `test_settings` 10 · `test_repos_mode` 10 · `test_overview_score` 10 · `test_theme` 7 · `test_theme_mobile_guards` 6 · `test_i18n_visual_regression` 5 · `test_dashboard` 3 · `test_dashboard_insight` 2 · `test_performance` 1. 오류 종류 `TimeoutError` 24 · `AssertionError` 32(한 테스트가 복수 계상). **가설(미검증)**: (a) 타임아웃 24 = Linux 컨테이너의 콜드스타트/렌더 지연이 Windows 로컬보다 길다 (b) AssertionError 32 = 폰트·테마 렌더 차이 또는 로케일 기본값 차이 — 어느 쪽도 **아직 실측하지 않았다**. 🔴 **초록으로 위장하지 않는 것이 이 항목의 핵심 제약**: deselect·`continue-on-error`·`|| true` 로 job 을 초록으로 만들면 R7 이 정확히 원상복귀한다(실행되지만 아무것도 지키지 않는 job). 줄이려면 **제외 목록을 이 원장에 명시**하고 사유를 함께 적을 것. **반증 수단**: 실패 30건 중 1건을 골라 Linux 컨테이너에서 재현 → 원인이 (a)/(b) 중 무엇인지 확정 🔴 **가설 (a)(b) 는 실측으로 전부 기각됐다 (2026-08-05)**: 같은 커밋을 로컬 Windows(py3.14)에서 완주하니 **31 failed / 90 passed** 였고, 실패 **테스트 이름 집합은 CI 28 ⊂ 로컬 29**(CI 에서만 실패 = **0건**). 비교 가능한 18건 중 **16건은 예외 타입까지 동일**(2건은 로그 절단으로 판정 불가). 즉 원인은 컨테이너 렌더 지연도 폰트·로케일 차이도 아니라 **스위트가 앱과 14개월간 어긋난 drift** 였다. ⚠️ **초판 분포 수치 정정**: 이 행에 적었던 *"Timeout 24"* 는 스택트레이스 중복 계상이었다 — 실제는 `playwright TimeoutError` **12** · `AssertionError` 32. 🔴 **관측기가 두 번 거짓말했다**: (1) 정규식 `test_[a-z0-9_]+` 이 대문자에서 잘려 `test_localStorage_…` 를 `test_local` 로 만들어 "로컬 전용 3건" 이라는 허수를 냈다(실제 1건) — Grok claim-review 가 *"`test_local` 은 존재하지 않는 심볼"* 로 적발 (2) 노드 목록을 Python 이 CRLF 로 써서 재실행이 전건 not-found → 전체 스위트가 대신 돌았다. **측정 도구 자체가 결함원**이라는 점을 기록한다. **근본원인 11개**(상위 2개가 15건): `.theme-option` 속성 `data-theme`→`data-theme-target` 리네임(#639) 미추종 **10** · `/login` 이 301→`/auth/github`→**github.com** 이 돼 테스트가 *우리 페이지가 아니라 GitHub 을* 검증·측정 **8곳** · 저장버튼 클래스 리네임(#631) 3 · preset inert 행 생략(#1041) 3 · i18n 기본 locale en vs 한국어 리터럴 2 · dashboard_insight 모드 JS 삭제(#649) 2 · KPI 5→6(#1037) 1 · OTP 6→8(#895) 1 · 미사용 import 제거 오탐 1 · **앱 버그 2**. **조치 = 아래 잔여를 뺀 전건 수정**(로컬 실측 31 → **1**). 🔴 **잔여 1건 — `test_dashboard_no_js_runtime_errors` = 실제 앱 버그, 테스트를 고치지 않았다**: `src/main.py:90~97` 이 모든 응답에 `style-src 'self' 'unsafe-inline'` + `font-src 'self' data:` 를 주입하는데 `src/templates/base.html:16,22` 가 Pretendard CDN · Google Fonts 스타일시트를 로드한다 → **앱이 자기 폰트를 자기 CSP 로 차단**하고 콘솔 에러를 낸다. 고치는 방향이 **보안 자세 변경(CSP 완화) ↔ 시각 변경(외부 폰트 제거·vendoring)** 으로 갈리므로 정책 15 High tier(사전 확인) + 정책 11(시각 검증 불가)에 해당해 **Claude 가 임의 결정하지 않는다**. 그동안 이 1건은 **빨간 채로 둔다**(deselect·xfail 로 초록을 만들면 R7 의 원죄를 재생산) 🔴 **종결 (`#1294`, 2026-08-06) — 결정 표가 틀렸었다**: 옵션을 제시하기 전에 **실제로 무엇이 일어나는지 재지 않았다**. Playwright 실측 결과 두 외부 스타일시트는 `cssRules` 접근이 **BLOCKED** 이고 `document.fonts.size == 0` — 즉 폰트는 **14개월간 한 번도 적용된 적이 없었고** 페이지는 이미 시스템 폰트로 렌더되고 있었다. 따라서 내가 ㉰(링크 제거)의 단점으로 적은 *"한글 렌더가 눈에 띄게 바뀜"* 은 **거짓**이었다 — 제거해도 시각 변화 0 이다(실측: 제거 전후 `font-family` 동일 · 등록 폰트 0 동일 · 콘솔 에러 2 → 0). 반대로 ㉮(vendoring)는 무해한 복구가 아니라 **14개월 만에 타이포그래피를 처음 바꾸는** 변경이라 시각 검증이 필요한 쪽이다. **조치**: 죽은 링크 5개(스타일시트 2 + preconnect 3) 제거 — `font-family` 스택의 이름은 그대로 둬 나중에 vendoring 하면 코드 변경 0 으로 살아난다. **재발 가드**: `test_csp_external_asset_parity.py` 가 CSP `style-src`/`font-src` 를 `main.py` 에서 읽어 템플릿과 대조한다(모순이 두 파일에 걸쳐 있어 단일 파일 리뷰로는 안 보였다). 뮤테이션 red 확인 |

<a id="r54"></a>

## R54

| **R54** | ✅ 완료 (`#1293` — 문서 감사 P0~P2) | **문서 설계 감사: 총량이 아니라 형상이 문제였다** | **기전**: 사용자 발화(*"자꾸 실수나 번복된 거짓보고가 많습니다"*)에 대한 근본원인 감사 — Claude 11-에이전트 + Grok 독립, **양쪽 총평 4/10**. 🔴 **총량 가설은 기각됐다**: 매 세션 강제 로드는 **17,375 토큰**(창의 8.7%)이고 3개월간 **+8%** 로 안정, 아카이브 79%는 상시 비용 **0**. 실수 10건 중 **총량으로 설명되는 것 0건**(문서구조 3 · 도구사용 4 · 판단오류 3). 진짜 문제 3가지: (1) `docs/STATE.md:36` 이 **한 줄 30,806자** — 머리·꼬리가 30,752자 떨어져 한쪽만 고치는 사고가 실제로 났고 Grep 이 표시를 거부했다 (2) **`docs/**` 에 path-scoped 규칙 0개** — 월 388 touch 로 `src/`(233)보다 많은 최다 편집 표면인데 로드 시점 규칙이 한 번도 없었다 (3) 같은 정수가 **5지점 손유지**. **조치**: 이력을 표 밖 절로 분해(최장 줄 30,806→2,764) · 가드에 꼬리 축 + fail-closed 3층 · `--fix` 파생으로 손유지 5→1 · `.claude/rules/docs.md` 신설 · `check_memory_refs` 범위 3→34파일 · `docs-sync` 스킬의 stale 리터럴(`154`, 실제 171)·틀린 절차 정정. 🔴 **감사가 찾은 진짜 근본 원인은 문서가 아니었다** — 실수 10건 중 **5건이 "1회용 측정 도구가 낸 숫자를 검증 없이 사실로 발행"** 한 클래스이고, 그 클래스는 `.claude/rules` 의 적용 술어가 전부 **경로**라 56 패턴 중 0개에 매칭돼 **규칙이 도달한 적이 없었다**. `AGENTS.md` 에 **측정 규율** 별도 축으로 신설. 🔴 **Grok 이 2라운드에 걸쳐 내 작업을 무너뜨렸다**(`019fcf` WEAKENED → `df5ed11d` BROKEN): 1차는 **가짜 분할 9건**("141개"가 내 splitter 출력이었다)과 **꼬리 축 fail-open 3층**, 2차는 **`--fix` 가 형식만 맞는 틀린 SSOT 를 5곳에 자동 전파**하는 쓰기측 fail-open. 전부 봉인 + 회귀 가드 9건 |

<a id="r56"></a>

## R56

| **R56** | ✅ 완료 (`#1303` Phase 0+1 — 사용자 결정 '설치'. 잔여 = R67) | **pre-commit 계층이 이 머신에 전면 부재 — 시크릿 훅 포함 13 훅이 19 PR 내내 0회 실행** | **기전**: 2026-08-06 5+1 회고(190 에이전트·확정 147) P0. `.pre-commit-config.yaml` 에 13 훅이 배선돼 있으나 이 머신에 pre-commit 이 설치돼 있지 않아 **한 번도 실행되지 않았다**. 그중에는 시크릿 스캔도 있다. 🔴 **원장에 열린 항목이 없다** — 즉 아무도 모르는 상태로 19 PR 이 머지됐다. `check_precommit_installed.py`(SessionStart)가 관측하도록 돼 있으나 그 신호가 조치로 이어지지 않았다. **반증 수단**: 이 머신에서 `pre-commit run --all-files` 가 실행되는가 · 실행 시 red 가 몇 건인가. **결정 필요**: 설치할 것인가(로컬 마찰 ↑, 조기 탐지 ↑) 아니면 CI 단일 집행면으로 명시 종결할 것인가(현재 사실상 그 상태인데 문서는 아닌 척한다) 🔴 **이행 (사용자 결정 = 설치, 2026-08-06)**: 훅 개수는 15도 13도 아닌 **16** 이었다(원장 수치 자체가 drift). **Phase 0(`#1303`)** — 설치 **전에** 죽어 있던 것을 먼저 고쳤다: 문서·가드 훅 7종이 `language: system` + `entry: python …` 이라 이 머신의 Store 스텁으로 해소돼 **exit 9009 로 커밋만 막았을 것**이다(실행 실측: `system`=Failed(9009) / `python`=Passed). **Phase 1** — 관측자 결함 4종 봉인 + 실제 설치. 🔴 관측자는 *침묵한 적이 없었다* — 매 세션 loud 하게 빨간 배너를 냈다. 진짜 기전은 (a) advisory 가 조치로 변환되는 경로 부재 (b) **PATH 바이너리를 AND 조건으로 요구해 설치에 성공해도 계속 빨강**(무조건 빨강 = 정상 빨강과 구별 불가) (c) 배너가 안내한 해결 명령이 이 머신에서 **실패**(`core.hooksPath` 설정 시 pre-commit 이 거부). 셋 다 고쳤다. **설치 실측**: `pre-commit`·`commit-msg` 2 타입 생성 · `.git/hooks/pre-push`(6-step ② 러너) **생존 확인**(`pre-push.legacy` 미생성) · `pre-commit run --all-files` → **시크릿·문서·가드 훅 전건 Passed**, autofixer 10 파일(공백 전용, `git diff -w` 로 확인). 🔴 **집행면은 늘지 않았다** — 로컬 훅은 리포가 강제할 수 없다. 늘어난 것은 *조기 탐지*와 *관측 정확도*뿐이며 그 한계를 배너가 명시한다. |

<a id="r57"></a>

## R57

| **R57** | ✅ 완료 (`#1305` — Grok `019fd786` WEAKENED 지적 3건 이행. 잔여 = 프록시 한계 명시) | **`claim-review-not-required` 자기발급 면제가 최근 11 PR 중 6건 — 정책 19 default 를 가드 트리거로 대체했다** | **기전**: 정책 19 는 *"실질 작업마다 CLAIM-REVIEW 기본 포함"* 이고 사용자 명시 지시다. 그런데 `check_claim_review_trace.py` 는 **seal 어휘가 있을 때만** 흔적을 요구하므로, 어휘가 없으면 면제 문구 없이도 통과한다. Claude 는 그 **가드 트리거를 정책 트리거로 오인**해 seal 어휘가 없는 PR 에 `claim-review-not-required` 를 자기발급했다(11 PR 중 6). 🔴 **가드는 이 남용을 원리적으로 못 잡는다** — 면제는 `::notice` 로 계량만 된다. **반증 수단**: 면제 6건 중 실제로 Grok 검토가 불필요했던 것이 몇 건인가. **처방 후보**: (a) 면제 사유에 '왜 반증 대상이 아닌가' 1줄 강제 (b) 세션당 면제 N건 초과 시 loud 🔴 **이행 (2026-08-06)**: (a)는 이미 있었다(사유 16자 이상). 진짜 갭은 **트리거**라 두 번째 트리거를 신설했다 — **코드·가드 표면을 건드리면 seal 어휘와 무관하게 흔적(또는 사유 있는 면제)을 요구**한다. 표면 목록에 `docs/runbooks/owed-verification.md`(R0-2 이후 **기계 판정 입력**)와 `tests/unit/{scripts,hooks}/`(가드 저술면)를 포함했다. **실측 오탐(최근 30 머지 PR)**: 코드 표면 23 · 문서 전용 7 · 새로 red **3건(10%)** — 진탐이 오탐을 넘는다. 면제는 `::notice` 만이 아니라 **job summary** 에도 누적한다(로그 안쪽은 아무도 안 본다). 🔴 **Grok claim-review `019fd786` = WEAKENED**, 지적 3건 전부 이행: (1) CI 의 `PR_BASE_SHA`/`PR_HEAD_SHA` 가 load-bearing 인데 **무검증** — 두 줄을 지우면 축이 조용히 죽는데 스위트는 초록이었다 (2) `main()` 의 env→인자 사상(base,head) **무검증** — 뒤바꾸면 `head...base` 가 되어 남의 변경을 이 PR 것으로 본다 (3) 판정 불가(`None`)에서 *"코드 표면 변경 없음"* 이라 **단언**해 모르는 것을 안다고 말했다. 셋 다 가드 신설 + 뮤테이션 red. 부수: **`WEAKENED` 를 합법 verdict 로 추가** — Grok 이 실제로 내는 판정이고 `cycle-history.md:223` 이 이미 서사로 쓰는데 가드는 거부했다. 표현 수단이 없으면 저자가 SURVIVES 로 반올림해 **판정이 낙관 쪽으로 왜곡**된다. ⚠️ **정직 기준(Grok 지적 4)**: 경로 접두사 목록은 정책 19 의 *실질 작업* 에 대한 **프록시**다. 양방향으로 갈린다 — 정책은 원하는데 가드가 조용한 경우(`tests/unit/{gate,worker,…}`·의존성 핀·정책 산문)와 그 역(주석만 고친 `src/` 변경·순수 trailing sync). 뮤테이션 8종 red. |

<a id="r58"></a>

## R58

| **R58** | ✅ 완료 (`#1298` — Grok `71bd2d6c` BROKEN 지적 이행) | **e2e 초록이 공허할 수 있다 — `live_server` 실패 시 121건 전건 skip 후 job exit 0** | **기전**: 2026-08-06 회고 확정. `e2e/conftest.py` 의 `live_server` 가 `/health` 폴링에 실패하면 **전 스위트를 skip** 하고, pytest 는 skip 을 성공으로 보므로 **job 이 GREEN** 이다. 즉 앱이 부팅조차 못 해도 배지는 초록이다. 🔴 **같은 창이 다른 3개 표면(lint-js·의존성 핀·이력 절)에는 '검사 범위 비면 fail' 을 적용해 놓고**, 자기가 방금 초록으로 만든 e2e 에만 적용하지 않았다. 부수 확정: `_perf_helpers` 기반 perf 11건 중 **10건은 라우트가 404 여도 통과**(뮤테이션 확정) · README E2E 배지는 CI 와 **기계적 결속 0**. **반증 수단**: `live_server` 를 강제 실패시켰을 때 job 이 red 인가 🔴 **이행 (`#1298`)**: 공허화 경로가 **셋**이었다(내 초판은 둘로 봤다 — Grok 적발). (1) `live_server` 의 `pytest.skip` → `RuntimeError`(뮤테이션: 전 `121 skipped·exit 0` → 후 `120 errors·exit 1`) (2) 검사 범위 축소 → `scripts/check_e2e_scope.py` + `e2e/EXPECTED_COUNT`(CI·러너 양쪽 배선) (3) 🔴 **수집은 유지한 채 전건 skip** — 범위 가드를 통과하고도 exit 0 이다(`pytest.mark.skip` 주입 뮤테이션으로 재현). `--e2e-min-passed=100`(conftest `pytest_sessionfinish`)이 그 유일한 관측면이다. 🔴 **부수 시정 2건**: 파서가 `2 tests collected, 1 error` 에서 **2 를 뽑아** collection error 를 통과시켰고(returncode 도 무시), 배선 테스트가 **substring** 이라 `echo` 로 우회됐다(`guards.md` 금지 패턴) → `_wiring_shape.surface_invokes` 로 전환. **잔여**: e2e job 은 여전히 **required check 가 아니라** red 가 머지를 막지 않는다(R64) |

<a id="r60"></a>

## R60

| **R60** | ✅ 완료 (`#1296` — 이번 창 이행) | **6-step ⑤ 의 '서사 축' 이 4 세션 방치 — 수치는 5회 동기화, 이야기는 0회** | **기전**: ⑤ 는 *"STATE 수치 갱신 **+ cycle-history 사이클 이력 동기화**"* 를 '예외 없음' 으로 못박는데, 이 창에서 수치 축은 5회 동기화된 반면 서사 축은 **0회**다. `cycle-history.md` 의 최신 절은 **세션14**(#1268~#1271)이고 세션15·16 이 통째로 없다. 🔴 **기전은 관측자 비대칭**: 수치 축에는 `check_docs_sync`(#1293 이 꼬리까지 3층 fail-closed)가 있고 **서사 축에는 관측자가 0** 이다(`check_toc_anchors` 는 앵커만·`check_memory_refs` 는 명시 제외). 그래서 STATE 가 **자기모순** 상태다 — 머리는 세션15, 꼬리는 세션16 7차. **반증 수단**: 서사 축 advisory 가드를 붙였을 때 실제로 이행률이 오르는가 🔴 **이행 (`#1296`, 2026-08-06)**: `cycle-history.md` 에 세션15·16 절 2개 신설(TOC 앵커 정합 확인) + `STATE.md` 최신 블록을 세션16 으로 회전 + 날짜 헤더 `2026-08-04` → `2026-08-06` 갱신. **자기모순 해소** — 머리와 꼬리가 같은 세션을 가리킨다. 🔴 **관측자는 여전히 0** — 서사 축 advisory 가드는 미구현이라 **다음 세션에 같은 방식으로 재발할 수 있다**. 그 부분은 R62 로 분리한다 |

<a id="r61"></a>

## R61

| **R61** | ✅ 완료 (`#1297` — Grok `6580850b` BROKEN 지적 이행) | **Anthropic 응답을 4곳 모두 `content[0].text` 로 인덱싱 — 첫 블록이 text 가 아니면 전부 조용한 `api_error`** | **기전**: 2026-08-06 회고 확정. `src/analyzer/io/ai_review.py` 등 4 경로가 응답의 **첫 블록이 항상 text 라고 가정**한다. thinking 블록이나 tool_use 가 앞서는 모델·설정에서는 `IndexError`/타입 오류로 떨어지고, 그 경로는 `api_error` 로 삼켜져 **점수 NULL-persist** 로 이어진다(#1289 가 고친 것과 같은 결말, 다른 원인). 🔴 지금 당장 터지지는 않지만 **모델/설정 변경 한 번이면 전량 사망**하는 클래스다. **반증 수단**: 응답 블록에 thinking 을 섞어 4 경로를 태우면 각각 어떻게 되는가 🔴 **이행 (`#1297`)**: `first_text_block()` 단일 출처(src) + standalone 3곳(훅·scripts ×1)의 의도적 중복 헬퍼. **호출부는 4곳이 아니라 5곳**이었다(`scripts/i18n_comments/translate_comments.py:245` — Grok 이 적발). 🔴 **개선 범위를 정확히 적는다**: 고친 것은 *복구 가능한 인덱스 버그*(text 는 있는데 첫 블록이 아닌 경우)이고, **'예외를 조용히 삼키는 구조' 자체는 한 줄도 안 바꿨다** — text 블록이 아예 없으면 `ValueError` 가 같은 `except Exception` 에 잡혀 **여전히 조용한 api_error** 다(Grok 지적 수용). 회귀 가드는 정규식 → **AST** 로 전환(`.content` 의 모든 첨자 + 지역 변수 별칭 경유) — Grok 이 제시한 우회 5종(직접·`[1]`·`[-1]`·lambda·변수+dead 헬퍼) **전부 red** 확인 |

<a id="r63"></a>

## R63

| **R63** | ✅ 완료 (`#1299` — Grok `32b9a2f9` 2라운드) | **성공 로그가 응답 파싱보다 앞서서, 추출 실패 시 success 와 error 가 둘 다 기록된다** | **기전**: `src/analyzer/io/ai_review.py:166~176` 과 `repo_insight_service.py:447~456` 이 `log_claude_api_call(status="success")` 를 **`first_text_block()` 호출보다 먼저** 부른다. 추출이 실패하면 success 가 이미 DB 에 남고 except 절이 error 를 **또** 남긴다 — 비용/성공률 집계가 왜곡되고, 운영자는 *"성공했다는데 왜 결과가 없지"* 를 보게 된다. 🔴 구 `content[0].text` 시절에도 같은 순서였으므로 **R61 이 만든 것이 아니라 드러낸 것**이다. **반증 수단**: 추출 실패를 강제했을 때 `claude_api_calls` 에 행이 몇 개 생기는가 · 각 status 는 무엇인가. **처방 후보**: 파싱 성공 후 로깅하도록 순서 교체(단 토큰 수는 응답에서 오므로 값 보관 필요) 🔴 **이행 (`#1299`)**: 실측 재현 확인 — 추출 실패 시 status 시퀀스가 `['success','error']`(한 호출 = 2행). `ai_review` 는 홀더 dict + **`finally` 단일 기록**으로, `dashboard`·`repo_insight` 는 **추출·파싱을 로그보다 앞**으로. 🔴 **Grok 2라운드가 잔여 구멍을 찾았다** — 1차 수정은 로그를 `json.loads` 뒤로만 옮겼는데 **유효 JSON 이 dict 가 아니면**(`"문자열"`·`[1,2]`) 그 다음 줄 `data.get` 이 success 로그 **뒤에서** 터져 여전히 2행이었다. 로그를 **결과 조립이 끝난 뒤**로 재이동. 회귀 가드 9건(실행 관측 6 + AST 순서 2 + 단일 호출부 1) — AST 순서만으로는 이 축을 **원리적으로 못 본다**는 것이 Grok 지적의 핵심이라 실행 관측을 함께 뒀다. **잔여 = R65** |

<a id="r64"></a>

## R64

| **R64** | ✅ 완료 (2026-08-06 — 사용자 결정 '승격'. required 9→10 라이브 적용) | **e2e job 이 required check 가 아니라 red 여도 머지를 막지 않는다** | **기전**: `#1288` 이 배선하며 *"실행 이력이 없어 flakiness 를 모른다 — 안정성 데이터를 모은 뒤 승격 판단"* 이라 적고 non-required 로 뒀다. 그 뒤 `#1291`·`#1294` 로 **0 failed** 가 됐고 `#1298` 이 공허화 3경로를 닫았다. 즉 **승격 판단에 필요한 조건이 갖춰졌다**. 🔴 그러나 지금 상태는 *가드는 빨간데 머지는 된다* — R58 이 닫은 것은 **job 내부의 공허**이지 **집행면**이 아니다. **결정 필요**: required 로 승격할 것인가(머지 차단 ↑, 플레이크 1건이 전체를 막을 위험) 아니면 non-required 유지인가(현 상태 — 빨강이 조언에 그친다). **반증 수단**: 승격 전 N 사이클 동안 e2e job 의 플레이크 발생률이 몇 %인가(현재 관측된 것은 perf 1건) 🔴 **이행 (2026-08-06)**: `PATCH .../branches/main/protection/required_status_checks` 로 승격 — required **9 → 10**, `enforce_admins: true`·`strict: false`·app_id 전부 보존(하위 리소스 PATCH 라 `PUT .../protection` 의 전체 덮어쓰기 위험 회피). **승격 근거(실측)**: e2e job 성공률이 `#1294`(CSP 결함 + CI 의 CSS 빌드 누락) **이전 2/17**, **이후 16/16** 이다 — 빨강의 원인은 플레이크가 아니라 **원인이 밝혀진 두 결함**이었고 그것이 닫힌 뒤 한 번도 실패하지 않았다. `#1298` 이 공허화 3경로를 닫아 '초록이 공허할 수 있다' 축도 함께 제거됐다. ⚠️ **정직 기준**: 16/16 은 점추정이다 — rule of three 로 95% 신뢰 상한은 **≤17%** 이지 0% 가 아니다. 회귀 가드 3건(job 이름 리터럴 대조 · 목록 비공허 · 조건부 `if:` 금지) + 뮤테이션 2종 red. 🔴 **라이브 설정은 관측하지 못한다** — GitHub 에서 항목을 빼도 CI 는 전건 초록이다. `Administration: read` 토큰이 필요한데 리포 시크릿에 두면 같은 리포의 어떤 워크플로에서도 읽혀 containment 가 성립하지 않는다(Environment 스코프 필요). 없는 관측을 있는 것처럼 보이게 하는 파일을 두지 않기로 했다. 정본·롤백 절차 = [`docs/runbooks/branch-protection.md`](runbooks/branch-protection.md). **잔여 = R68** |

<a id="r65"></a>

## R65

| **R65** | ✅ 완료 (`#1300` — Grok `019fd6e8` BROKEN 지적 이행. 잔여 = R66·백필 미수행) | **비용 로그의 error 경로가 토큰을 0 으로 덮어 비용이 과소 계상된다 + 과거 이중 행은 그대로 남는다** | **기전**: (a) `dashboard_service`·`repo_insight_service` 의 except 절이 `input_tokens=0, output_tokens=0` 을 기록한다 — API 호출은 실제로 일어나 **토큰을 소비했는데** 실패했다는 이유로 0 으로 남는다. R63 이 이중 행은 없앴지만 **실패 호출의 비용은 여전히 0** 이라 `monthly_cost` KPI 가 과소다. `ai_review` 는 홀더 패턴이라 성공 시 잡은 토큰이 보존되지만 나머지 2경로는 아니다. (b) 🔴 **과거 데이터는 고쳐지지 않는다** — R63 은 *신규 기록 규약*이고 백필 SQL 이 없다. 이미 쌓인 success+error 이중 행이 KPI 에 그대로 남아 있다. **반증 수단**: (a) 실패 호출에서 `extract_anthropic_usage` 를 먼저 잡아 except 로 넘겼을 때 값이 유효한가 (b) `claude_api_calls` 에서 같은 (model, 초 단위 시각) 쌍의 success+error 인접 행이 몇 건인가 🔴 **이행 (`#1300`)**: 3경로 전부 홀더로 전환(`dashboard`·`repo_insight` 신설, `ai_review` 는 R63 홀더가 이미 보존 — 실행으로 확인). `log_claude_api_call` docstring 의 *"에러 시 0"* 처방 삭제 + 실패 로그 줄에 토큰·비용 노출(이전엔 `extra` 에만 있어 raw 로그를 읽는 운영자에게 비가시). 회귀 가드 11건 + 뮤테이션 6종 red. 🔴 **Grok claim-review `019fd6e8` 가 BROKEN** — 핵심 지적: 모든 가드가 `log_claude_api_call` 을 **스파이로 대체**하거나 `_persist_cost` 를 패치해서, *"실패해도 비용이 기록된다"* 는 주장이 **한 번도 관측된 적이 없었다**(호출부 kwargs 만 봤다). 조치 = 호출부 실패 → 실제 `claude_api_calls` 행까지 무패치로 관통하는 테스트 신설 — 영속화 배선을 끊는 뮤테이션에서 **그 테스트만** red 였다(다른 8건 green). 초판 docstring 의 "DB 로 가는 값" 과대 표현도 정정. ⚠️ **Grok 지적 중 반증한 것 1건**: *"AST 가드가 홀더 채우기 삭제를 못 잡으므로 그것이 R65 의 실제 잔여"* — AST 가 못 보는 것은 맞으나 그 뮤테이션은 **실행 가드 6건이 red** 다(실측). 🔴 **잔여 2**: (a) **백필 없음** — 과거 이중 행·0 토큰 행은 그대로다(신규 기록 규약일 뿐) (b) **R66**(SDK 재시도분 비가시) |

<a id="r68"></a>

## R68

| **R68** | ✅ 완료 (`#1314` — 사용자 확인 '**auto-merge 를 실제로 운용한다**' → P1 확정 후 이행) | **required check 미충족(`blocked`)이 auto-merge 에서 종결 실패라, 체크가 도는 동안 시도된 PR 은 영구 포기된다** | **기전**: `mergeable_state="blocked"` → `merge_reasons.BRANCH_PROTECTION_BLOCKED`(`merge_reasons.py:86`) 이고, 그 태그는 `_RETRIABLE_TAGS`(`:60` = `unstable_ci`·`unknown_state_timeout`)에 **없다** → 재시도 큐가 기다리지 못한다. `sensitive_paths.py:18~20` 이 이미 이 성질을 실측으로 기록해 뒀다(*"오히려 자동 머지를 죽인다"*). 🔴 **R64 가 만든 것이 아니다** — 브랜치 보호 자체(2026-08-01 `R2-b`, 사용자 승인)가 켜진 시점부터 있던 성질이고, 체크를 하나 더 넣으면 그 창이 길어질 뿐이다. **왜 High tier 인가**: `blocked` 를 retriable 로 바꾸면 *정말로* 영구 차단된 PR(리뷰 요구 미충족 등)에서도 재시도 큐가 소진될 때까지 돈다 — auto-merge **동작 변경**이라 정책 15 상 사전 확인 대상이다. GitHub 은 '체크 대기 중 blocked' 와 '규칙상 blocked' 를 구별해 주지 않는다. **반증 수단**: (a) required check 가 pending 인 동안 `mergeable_state` 가 실제로 `blocked` 인가(라이브 PR 관측) (b) 그 상태에서 auto-merge 가 시도되는 타이밍이 실재하는가 — 파이프라인이 분석을 마칠 무렵 체크가 이미 끝나 있으면 실해가 0일 수 있다 🔴 **이행 (2026-08-08)**: 사용자가 **auto-merge 를 실제로 운용한다**고 확인해 실해가 확정됐다(반증 수단 (b) 해소). `BRANCH_PROTECTION_BLOCKED` 를 `_RETRIABLE_TAGS` 에 추가하되, **무조건 재시도가 아니다** — `should_retry` 에 분기를 신설해 **CI 가 `running` 일 때만** 재시도로 확정한다. 🔴 `blocked` 은 (a)required check 진행 중 · (b)규칙상 충족 불가를 GitHub 이 뭉뚱그린 값인데, CI 가 끝났는데도 blocked 면 그것이 (b)이므로 `passed`·`failed`·`unknown` 은 전부 종결로 둔다 — (b)가 `max_attempts`(기본 30) 예산을 태우지 않게 하는 것이 이 분기의 핵심이다. `UNSTABLE_CI` 가 `passed` 를 허용하는 것은 merge-API lag 축이고 그 태그가 이미 담당한다. **회귀 가드 9건 + 뮤테이션 3종 red**(종결로 되돌림 · 무조건 재시도 · 과도 완화). 🔴 **계약 변경이라 옛 계약을 못박던 테스트 4건을 갱신**했다 — 지우지 않고, `blocked` 을 *일반 종결 사례*로 쓰던 3곳(engine 2 · merge_retry_service 1)은 여전히 종결인 `dirty_conflict` 로 교체해 **원래 의도를 보존**했고, 계약 자체를 단언하던 2곳은 사유와 함께 뒤집었다. ⚠️ **정직 기준**: 예산 상한(`is_expired` max_age + `max_attempts`)이 무한 재시도를 막는다는 것은 소스 존재로만 확인했다 — 실제 소진 시나리오는 실행 관측하지 않았다. |

<a id="r77"></a>

## R77

| **R77** | ✅ 완료 (2026-08-10 — 🔴 **내가 등재할 때 적은 처방이 틀렸다**) | **import 시점 `ValidationError` 가 자격증명을 그대로 인쇄한다 — 어떤 로그 필터도 원리적으로 닿지 못한다** | **기전**: `src/config.py` 의 `_normalize_pg_url` 이 `urlparse(v)` 를 부르는데 닫히지 않은 `[`(온프레미스 IPv6 지원 대상이라 현실적인 오타)에서 `ValueError: Invalid IPv6 URL` 이 난다. 그러면 pydantic v2 가 `input_value=...` 로 **비밀번호를 인쇄**한다. `SESSION_SECRET` 도 같은 기전. 🔴 **이 축은 계층 2 로 못 막는다** — `settings = Settings()` 가 **모듈 import 시점**이라 `configure_logging()` 보다 먼저이고 애초에 `LogRecord` 가 만들어지지 않는다. R8 이 닫은 alembic 축(excepthook)과 **다른 축**이다. 🔴 **등재 시 내가 적은 처방(*"validator 에서 값 없는 메시지로 재발생"*)은 착수 전 측정에서 거짓으로 드러났다** — pydantic 은 내 메시지와 **무관하게** `input_value` 를 덧붙인다. 통제 지점은 validator 가 아니라 **생성 지점**이었다. **이행**: `build_settings()` 가 `Settings()` 를 감싸 `ValidationError` 를 잡고, 민감 필드는 값을 빼고 무해한 필드는 값을 남긴 메시지로 `RuntimeError` 를 던진다. 🔴 **`from None` 필수** — `from exc` 로 체인하면 원본이 트레이스백에 **다시 인쇄**돼 그대로 유출된다(실측). 🔴 **민감 판정에 타입을 넣었다** — 이름 힌트만 쓰면 `claude_review_max_tokens` 가 `token` 에 걸려 과교정된다(실측 오탐). 자격증명은 `str` 이므로 `int`/`bool` 필드는 판정에서 제외한다. **가드 6건**: 결함 존재 대조군(`str(e)` 절단 축 + `errors()[].input` 무절단 축 **양쪽**) · 민감 필드 은닉 · 무해 필드 값 보존 과교정 대조군 · 트레이스백 전문 검사 · 정상 입력 통과 · `SESSION_SECRET` 축. 뮤테이션 M8(`from None`→`from exc`) 2 red · M9(타입 판정 제거) 1 red | 보안 |

<a id="r16"></a>

## R16

| **R16** | ✅ 완료 (`#1268`) | **B8 fail-open floor 가 자기 스캔 범위를 관측하지 않는다** — `scripts/check_*.py` 만 glob 하므로 **test-as-guard 표면은 원리적으로 미탐**이고, 범위를 비워도 `✅ … bare-substring fail-open 0` **성공 문구를 출력**한다 | **기전**: 뮤테이션 GROK-9 실측 — `tests/unit/scripts/` 에 bare substring 판정 가드를 새로 만들어도 `check_guard_fail_open.py` 는 EXIT=0. AGENTS.md 스스로 최다 재발 사고(`#1136`·`#1156`)가 **test-as-guard 에 있었다**고 기록한다. **반증 수단**: 범위를 `tests/**/test_*.py` 로 넓혔을 때 오탐 < 진탐인지(정책 17 guard-suicide 위험 — `X in text` 는 정당한 presence 검사에도 쓰인다). 🔴 **오탐 위험 0인 최소 조치 = 출력 문구를 실제 스캔 범위로 한정** |

<a id="r17"></a>

## R17

| **R17** | ✅ 완료 (`#1268`) | **lint-js 공허화 차단의 false-justification 우회** — 템플릿 인라인 `<script>` 에 비실행 Jinja 유사 토큰(`// {{`)을 넣으면 "정당한 제외" 로 분류돼, 그 파일을 eslint 무시 목록에 넣어도 가드가 통과 | **기전**: 뮤테이션 GROK-12 실측 — 검사 대상이 **6 파일 → 5 파일**로 줄었는데 EXIT=0(양쪽 다). 🔴 **라벨 정정**: Grok 은 `score-lie` 로 분류했으나 대상이 **자사 템플릿**이라 사용자 리포 점수 인플레가 아니다 → `silent-disable`. 사용자 가시 효과 = *"템플릿 JS 가 영영 미린트돼도 CI 초록"*. **반증 수단**: 검사 대상 **파일 수 감소 자체**를 신호로 삼는 축 추가 시 red 가 되는지 |

<a id="r19"></a>

## R19

| **R19** | ✅ 완료 (세션13) | **`tests/unit/verifier/test_openai_client.py` 5건이 의존성 없는 환경에서 red** — `openai==2.50.0` 은 `requirements.txt` 핀이지만 `importorskip` 가드가 없다 | **기전**: 2026-07-31 실측 — 로컬 `pytest tests/unit` = **6079 passed / 5 failed**(`ModuleNotFoundError`), main 에서도 동일. CI 는 설치하므로 초록이라 **누구도 못 본다**. 🔴 진짜 피해는 6-step ② 가 요구하는 "push 전 전체 통과 실측" 이 이 환경에서 **구조적으로 불가능**해져, 실패를 습관적으로 무시하게 되는 것이다(진짜 회귀도 같이 묻힌다) |

<a id="r20"></a>

## R20

| **R20** | ✅ 완료 (`#1269` — 잔여 1축 아래 명시) | **정책 19 집행면 결함 9건** — 면제 마커가 **계량되지 않는다**(창의 post-guard seal PR 10건 중 **5건이 면제로 통과**, 첫 사용은 가드 생성 **66분 후**) · **HTML 주석 안의 흔적·면제도 인정**(가드는 exit 0 인데 리뷰어에게 비가시) · **session id 재사용 무탐지**(#1245 가 #1244 의 세션 인용) · seal 어휘가 이 리포 관용구 `뮤테이션 N건 red`(단수형)를 못 잡음 · **집행면이 정책 SSOT 4곳 어디에도 없음** | 회고 P1 클러스터 2. 최소 조치 = (a) 면제 사용을 원장에 기록·계량 (b) HTML 주석 제거 후 매칭 (c) 어휘 사전에 단수형 추가 (d) AGENTS.md·CLAUDE.md 정책 19 항에 게이트 존재 명시 🔴 **해소(`#1269`)**: (a) `::notice` annotation 계량 (b) **마크다운 인지 상태기계** 스트리핑(Grok 이 초판 정규식의 가시 텍스트 과제거[펜스 안 `<!--` 이후 seal 은닉 fail-open]를 재현 적발해 재설계) (c) `뮤테이션 N건/N종 red` 추가 (d) 양 SSOT 등재. **잔여 = session id 재사용 무탐지**: cross-PR 상태 조회(gh) 의존이라 CI 가드 결정성을 깨 이번 범위에서 제외(기지 한계 — 다음 회고 재평가) |

<a id="r21"></a>

## R21

| **R21** | ✅ 완료 (`#1261` — 사용자 결정 옵션 C) | **`#1244` 커버리지 승격이 조달 불가 언어의 auto-merge 를 영구 차단** — `unavailable_tools → incomplete` 승격으로 **css/scss·dart·powershell·protobuf** 가 영구 incomplete. `#1245` 가 스스로 *"차단 없이 가시화만"* 이라 적은 것과 정면 모순 | 회고 P1 클러스터 4(7건). 🔴 **결정 필요**: (a) 조달 불가 언어는 incomplete 에서 제외(가시화만) / (b) 현행 유지(보수적 차단) / (c) 언어별 화이트리스트. 부수: 가시화가 **6 알림 채널 중 GitHub PR 코멘트 1곳에만** 구현돼 Telegram·대시보드에는 여전히 만점만 보인다 🔴 **해소(2026-08-01)**: 문제는 원장 기록(4 언어)보다 컸다 — 등록 25 분석기 중 **9종**이 조달 흔적 0 이라 **9개 언어**(rust·dart·C#·php·powershell·css/scss·swift·protobuf·html)가 차단돼 있었다. 조달 계약(`PROVISIONED_ANALYZERS` 16종)으로 갈라쳐 계약 안 부재만 차단(실제 배포 회귀), 밖은 가시화만. 계약↔조달파일 양방향 대조 가드 동반. 뮤테이션 5/5 RED. |

<a id="r22"></a>

## R22

| **R22** | ✅ 완료 (세션13 — 설정 메타 메시지 드롭 + 실바이너리 축) | **eslint fail-closed 오탐 4건** — `ruleId:null` 을 전부 '미린트' 로 오판해 **흔한 `eslint-disable` 주석 하나로 PR 전체가 `static_analysis` 오판**. 또 10-룰 최소 config 때문에 **설정에 없는 룰을 가리키는 `eslint-disable` 주석이 severity=ERROR 오탐으로 집계돼 점수를 깎는다**(실측 재현) | 회고 P1 클러스터 7. 🔴 사용자 리포 점수에 직접 영향 = `score-lie`. **반증 수단**: `eslint-disable-next-line some-external-rule` 만 담은 픽스처를 분석해 이슈 0건·미린트 판정 0 인지 |

<a id="r23"></a>

## R23

| **R23** | ✅ 완료 (세션13 — SessionStart 관측면, advisory) | **pre-commit 미설치를 관측하는 면이 리포 전체에 없다** — 시크릿 훅 5종이 창 **22 커밋 내내 0회 실행**. CI TruffleHog `--only-verified` 는 이 클래스를 대체하지 못한다(검증된 시크릿만 본다) | 회고 P1 클러스터 8. 🔴 보안. **반증 수단**: SessionStart 훅이 `pre-commit --version` + `.git/hooks/pre-commit` 실재를 확인해 부재 시 loud(advisory 유지, 정책 17) |

<a id="r24"></a>

## R24

| **R24** | ✅ 완료 (`#1271` + 본 sync) | **backlog 원장 자체의 정확성 6건** — R9 는 창에서 양 축 모두 해소됐는데 여전히 🟡 · ~~R2-b 의 반증 수단이 원리적으로 측정 불가(지정 API 가 영원히 404)~~ · 요약표 🔴 1건인데 실제 3건 · 회귀 가드가 원장 23행 중 5행만 본다 | 회고 P1 클러스터 6. "지금 뭐가 남았나" 의 SSOT 가 **완료된 일을 다시 시킨다**. 🔴 **본 항목 자신이 그 사례였다(세션13 정정)**: "R2-b 는 원리적으로 측정 불가" 는 **틀렸다** — 404 는 *보호가 없음*을 뜻하지 API 부재가 아니고, 보호를 적용하자 같은 API 가 **200 + `Repo integrity guards (stdlib backstop)`** 를 반환했다(실측). *현재 상태*를 *측정 가능성*으로 오독해 **해소 가능한 일감을 불가능으로 등재**한 것이다. 잔여 = R9 상태 · 요약표 카운트 · 가드 커버리지 3건 🔴 **잔여 해소(2026-08-02)**: R9 ✅ 플립(역사 창) · 요약표 재계산(본 sync — 범위 명시 유지) · 가드 커버리지 = `#1271` 전장(whole-file) R행 legality 백스톱(실측 35행 전수 + 하한 30, 기존 5행→현재 창 18행→전장으로 확장) |

<a id="r25"></a>

## R25

| **R25** | ✅ 완료 (세션13 — `check_test_count_sync` ground-truth 축, PR/main 이원 배선) | **`check_docs_sync` 는 ground truth 를 원리적으로 못 본다** — 문서 사본끼리만 대조하므로 **4지점이 함께 틀리면 항상 GREEN**(뮤테이션 실증). 유일한 수동 backstop 인 `/docs-sync` 스킬은 **통합 카운트를 상수 154 로 하드코딩** | 회고 P1 클러스터 1. 이번 세션이 수치는 정정하지만 **관측 축은 미신설**. 처방 = CI test job 에서 `pytest --collect-only -q` collected 수를 STATE 정규식 값과 대조(로컬 pre-commit 은 속도 때문에 현행 유지) |

<a id="r26"></a>

## R26

| **R26** | ✅ 완료 (세션13) | **`docs/architecture.md` 핵심 데이터 흐름 stale 2건** — 창에서 P0 로 정정한 `claude -p` 서술이 **이 문서에만 생존**(수정이 README 에만 적용됨) · `#1247` 이 STATE 최신 블록·cycle-history 어디에도 없음 | 회고 P1 클러스터 10·12 |

<a id="r27"></a>

## R27

| **R27** | ✅ 완료 (`#1265`·`#1266`) | **CONTRIBUTING(양 언어)이 존재하지 않는 기계 강제를 약속** — "커버리지·pylint 점수 drift 를 pre-commit 훅이 차단" · "src/ 신규 파일 트리 등재를 훅이 강제" 둘 다 실재하지 않는다. 또 path-scoped rules 본문 sync 의무(사이클 86 Q2 **사용자 명시 결정**)가 창의 코드 PR **7건 중 6건에서 미이행** | 회고 P1 클러스터 13. 신규 기여자에게 거짓 보증 🔴 **해소(2026-08-01 문서 전수 감사)**: CONTRIBUTING 의 거짓 기계 강제 약속 정정 + path-scoped rules 본문 sync 이행. 부수로 게이트 주장 9지점 drift · 규칙 도달성 3갭 · 완료 계획 12개 실행형 오독 · 심의 skip 50→4 를 함께 시정했다. |

<a id="r29"></a>

## R29

| **R29** | ✅ 완료 (`#1258`+`#1263`) | 🔴 **`make` 이 이 머신에 없다 — CLAUDE.md 가 처방하는 게이트가 한 번도 실행된 적이 없다** | **실측**(2026-08-01): `make --version` → `command not found`. CLAUDE.md 는 `make test`·`make lint`·**`make gate`**(= "CI 와 동일 기준 로컬 사전 확인" 으로 명시된 유일한 수단)를 처방하지만 **전부 실행 불가**다. 결과: 6-step ② 를 `py -3 -m pytest` 로 대체 수행하게 되고, **`make gate` 가 덮는 pylint `--fail-under` + bandit 축은 push 전에 아무도 안 본다** — CI 도착 후에야 발견된다(창에서 F841 로 실제 발생). 이것이 "가드가 수행되지 않는" 가장 단순한 형태다: 가드가 틀린 게 아니라 **호출 명령이 존재하지 않는다**. **반증 수단**: `make gate` 가 실제로 돌아 exit code 를 내는가. 조치 후보 = (a) Windows 용 make 설치 (b) `scripts/gate.py` 등 make 비의존 진입점 + CLAUDE.md 동시 정정 (c) 문서에 "이 머신에는 make 없음" 을 적고 대체 명령 명시. ✅ **(b)+(c) 이행**(`#1258`): `scripts/pre_push_gate.py` 신설(repo-integrity 9 + PR-diff 4, 못 보는 축 매 실행 인쇄) + CLAUDE.md 의 *"`make gate`(CI 와 동일 기준)"* 주장 정정 — **두 겹으로 거짓**이었다(명령 부재 + 있었어도 13 가드 미실행). 🔴 **잔여 = (a) 사용자 결정**: make 를 설치할지. 미설치 시 표의 `make X` 항목들은 계속 실행 불가다 🔴 **(a) 결말(2026-08-01)**: make 설치 대신 **로컬 `.git/hooks/pre-push`** 로 자동화하고 그 존재를 SessionStart 가 관측한다(`#1263`). `.pre-commit-config.yaml` 에 `stages: [pre-push]` 를 적는 안은 Grok 설계 검토 `019fbc8e` 가 **기각** — pre-commit 이 훅 타입별 설치를 요구해 미설치 머신에서는 한 번도 안 도는 가드가 된다. 로컬 훅은 git 미추적이라 리포는 **관측만** 가능. |

<a id="r30"></a>

## R30

| **R30** | ✅ 완료 (`#1271` — 관측면. 잔여 = 로컬 3.12 정렬 여부 사용자 결정) | **로컬 인터프리터(3.14) ↔ CI(3.12) 이원** — 로컬 전건 통과가 CI 통과를 보장하지 않는다 | **실측**: `py -3` → **3.14.2**, `.github/workflows/ci.yml` 4개 job → **3.12**. `__pycache__` 에 `cpython-312`·`cpython-314` 산출물이 공존한다. 6-step ② 가 요구하는 "push 전 전체 통과 실측" 이 **다른 런타임에서의 통과**라 버전 의존 회귀(문법·표준 라이브러리 deprecation)를 못 잡는다. 실제로 로컬 실행마다 `asyncio.iscoroutinefunction` DeprecationWarning 14건이 뜨는데 CI 에는 없다. **반증 수단**: 로컬을 3.12 로 맞추거나, 최소한 "로컬 통과 ≠ CI 통과" 를 6-step ② 문구에 명시 |

<a id="r31"></a>

## R31

| **R31** | ✅ 완료 (`#1270` — loud fail-open 채택[deny 는 전 편집 차단 = 가드 자살, 정책 17]. 행동 23케이스 + main deny stdout freeze) | **`check_edit_allowed.py`(수정 금지 파일 보호)에 행동 커버리지가 0이고 stdin 실패가 fail-open** | 모바일 환경 보호 훅인데 **차단 동작을 검증하는 테스트가 없다** — 정의만 있고 관측이 없는 전형(불변식 3). stdin 파싱이 실패하면 통과시키므로, 훅 입력 계약이 바뀌면 **조용히 무보호**가 된다. 보안 인접(`alembic/versions/`·템플릿 보호). **반증 수단**: 금지 경로 편집 payload 로 exit≠0 을 관측하는 테스트 + stdin 파손 시 차단(fail-closed) 여부 결정 |

<a id="r32"></a>

## R32

| **R32** | ✅ 완료 (`#1257`) | 🔴 **문서 심의 게이트가 한 번도 심의한 적 없었다** — `ANTHROPIC_API_KEY` 부재로 3 에이전트 전부 실패 → veto `warn` → exit 0 | **배선·실행·출력 다 하면서 아무것도 심의하지 않는다**(`make` 부재와 동형 — 로직이 아니라 실행 전제 부재). 6206건 스위트가 못 잡은 이유 = `tests/conftest.py:17` 이 **가짜 키를 주입**해 운영 실패 조건을 재현 불가로 만듦. Grok `019fbb2d` 가 수정본에서 **C1=BROKEN**(선점검↔클라이언트가 `.env` 에서 갈라짐) 적발 → 시정. 뮤테이션 10/10 RED |

<a id="r33"></a>

## R33

| **R33** | ✅ 완료 (`#1257`·`#1260` + 사용자 키 설정 2026-08-01) | **(a) `ANTHROPIC_API_KEY` 를 설정할지** + ~~(b) 배너가 보이는지 미확인~~ | **(a) 🔴 사용자 결정 잔여**: 키를 설정하면 심의 게이트가 **처음으로 실제 작동**한다(문서 편집마다 Haiku 3회 ≈11.6k 입력 토큰). 안 하면 배너만 뜨고 게이트는 계속 무동작. `DOC_REVIEW_GATE_DISABLED=1` 로 명시 종료도 가능. **(b) ✅ 해소 — 라이브 실증**: 원인은 **공식 계약**이었다 — PreToolUse 의 plain stdout 은 **Claude 에게 전달되지 않는다**(전달되는 이벤트는 `UserPromptSubmit`·`UserPromptExpansion`·`SessionStart` 셋뿐). 🔴 **내 최초 시정안(SessionStart 이관)은 Grok claim-review `019fbb65` 가 기각**했다: SessionStart 는 세션당 1회라 세션 중간 키 만료 시 **stale-green** — 이 리포의 지배적 결함을 재생산한다. 올바른 답 = `hookSpecificOutput.additionalContext`(Claude) + `systemMessage`(사용자), `permissionDecision` **미설정**(`"allow"` 는 권한 확인을 건너뛸 수 있어 안전 결함). **실증**: 수정 전 CRITICAL 문서 3회 편집 = 배너 **0회** 출현 → 수정 후 **첫 편집에 즉시** `PreToolUse:Edit hook additional context:` 로 도착(같은 세션 실측). 뮤테이션 6/6 RED 🔴 **(a) 해소 — 사용자가 `.env` 에 키 설정**: 심의 게이트가 **처음으로 실제 심의**하고 CLAUDE.md 축약 변경을 `deny` 로 차단했다(라이브 실측). **(b) 해소 — 라이브 실증**: `#1260` 이후 훅 출력이 에이전트 컨텍스트에 도착한다. 부수 검증 = 3 에이전트 1회 실패 시 INOPERATIVE 가 **아니라** 개별 실패로 보고됐고 재시도 6.3s 전건 성공 — `#1257` 의 일시/구조 구분이 실전에서 정확히 작동했다. |

<a id="r7"></a>

## R7

| **R7** | ✅ 배선 종결 (`#1288`, 2026-08-05) — 🔴 **후속 R52 신설** | ~~**e2e 122건이 CI 미배선인데 README/STATE 는 "E2E 122 passing" 단언 — 실행되지 않는 초록 배지**~~ → **e2e 122건이 CI 에 배선돼 있지 않다** | 🔴 **2026-08-05 전제 정정 (Grok `019fcd90` 적발 + 실측)**: *"거짓 초록 배지"* 축은 **이미 죽었다** — `README.md:22` 배지는 `E2E-122_tests_(local_only, not_in_CI)` 회색으로 정직화돼 있다(`#1237`, 2026-07-29). 원장이 이미 고쳐진 결함을 **살아 있는 것처럼 서술**하고 있었고, 요약 블록도 스스로 *"R7 의 원 근거는 stale"* 이라 적으면서 행 본문은 그대로였다. **남은 유일한 결정**: e2e 122건을 CI 에 배선할 것인가(현재 어떤 워크플로도 실행하지 않음 — R47-(c) 실측). 배지 문구 결정은 이미 끝났다 🔴 **종결 (`#1288`, 2026-08-05 — 사용자 결정 ㉮ "빨간 채로 머지")**: `ci.yml` 에 `e2e` job(Playwright + chromium, 30분 타임아웃) 배선. 🔴 **배선이 즉시 새 사실을 드러냈다 — 스위트는 (플랫폼 무관하게) 통과하지 않는다**: `30 failed / 91 passed / 1 skipped` (8분 40초). 즉 R7 의 진짜 결함은 *"실행되지 않는 초록"* 이 아니라 **"실행된 적이 없어 아무도 몰랐던 빨강"** 이었다 — 배선 전에는 이 사실을 알 수단 자체가 없었다(R47-(c) 의 '양 열 공백' 이 정확히 이 상태). 실패 분포: `test_settings` 10 · `test_repos_mode` 10 · `test_overview_score` 10 · `test_theme` 7 · `test_theme_mobile_guards` 6 · `test_i18n_visual_regression` 5 · `test_dashboard` 3 · `test_dashboard_insight` 2 · `test_performance` 1 (`TimeoutError` 24 · `AssertionError` 32 — 한 테스트가 복수 계상). 🔴 **배지를 초록으로 바꾸지 않았다** — `README.md:22` 는 `E2E-122_in_CI_(91_pass/30_fail_on_Linux)` 주황이다. 여기서 초록으로 적었으면 R7 의 원죄(검증되지 않은 초록)를 정확히 재생산했을 것이다. **잔여 = R52** 🔴 **후속 확정 (`#1291`, 2026-08-05)**: R52 진단 결과 30건 중 **환경 원인은 0건**이었다 — 로컬 Windows 에서도 같은 이름이 실패했다(CI 28 ⊂ 로컬 29). 여기 적었던 *"Linux 에서"* 는 관측 범위를 원인으로 오독한 서술이라 위와 같이 정정한다. 수정 후 CI 실측 **119 통과 / 1 실패**(잔여 = CSP 앱 버그) |

<a id="r8"></a>

## R8

| **R8** | ✅ 완료 (2026-08-10 — 🔴 **내 1차 반증이 틀렸다. 실제 유출 경로가 있었다**) | **로그·예외 경로의 DB 자격증명 유출** | 🔴 **경위를 그대로 남긴다 — 이 항목은 두 번 틀렸다.** ① 원 서술(*"SQLAlchemy 가 예외 메시지에 URL 전문을 담는다"*)은 검증 없이 들어온 추정이었고 **거짓**이다(실측: `str(URL)`·`repr(engine)`·`OperationalError`·psycopg2 직접 실패·`ArgumentError` 전부 마스킹 또는 DSN 미포함). ② 그래서 나는 *"활성 유출 경로는 존재하지 않는다"* 고 **반증을 발행하려 했고 그것도 거짓이었다** — 적대 검증 2건(Grok `019febc8` · `wf_014af71e-152`)이 독립적으로 **실경로**를 찾아냈다. **도구가 안전한 것과 그 도구를 감싼 배선이 안전한 것은 다른 문제다.** 🔴 **실제 유출 (재현 완료)**: `alembic/env.py` 의 `config.set_main_option("sqlalchemy.url", …)` 는 ConfigParser 저장소를 쓰는데 `BasicInterpolation` 이 `%` 를 보간 문법으로 읽는다 → 비밀번호에 `%` 가 있으면 `ValueError: invalid interpolation syntax in 'postgresql://appuser:p%40ss%2Fword@…' at position 22` 로 **URL 전문이 노출**된다. 특수문자 비밀번호의 percent-encoding(`@`→`%40`)은 **표준 관행**이라 흔한 형태고, `railway.toml` 의 `preDeployCommand = alembic upgrade head` 가 **매 배포마다** 이 경로를 탄다. 그 예외는 `logging` 이 아니라 **excepthook** 으로 나가므로 `_RedactSecretsFilter`(계층 2)가 **구조적으로 볼 수 없다**. 🔴 **부수 정정**: *"logger 호출에 DB URL 이 실리는 지점 0건"* 도 틀렸다 — 내 세는 법이 **호출 인자만** 보고 `exc_info` 적재분을 못 봤다(`src/main.py` `logger.exception("DB migration failed")` 가 트레이스백에 DSN 을 싣는다). #1104 가 값을 치른 바로 그 사각이다. **이행**: (계층 1) `env.py` 에서 `%` → `%%` 이스케이프 — 두 읽기 경로(`get_main_option`·`get_section`→`engine_from_config`) 모두 원본 복원 실측. (계층 2) `_SECRET_URL_PATTERNS` 에 userinfo 패턴. 적대 검증이 찾은 정규식 결함 2종도 수정 — 빈 사용자명(`redis://:pass@host`) 미마스킹 · compact JSON 과교정. **가드**: CLI 축 subprocess 가드(실제 `alembic upgrade head` 출력에 비밀번호 0건) + AST 배선 + 라운드트립 5종 + 리댁션 6종. 뮤테이션(이스케이프 제거) 시 **CLI 축과 배선 축 동시 red**. 🔴 기존 가드가 전부 로깅 축에만 있었다면 CLI 경로가 뚫린 채 초록이었을 것이다([[feedback-false-enforcer-is-worse-than-none]]) | 보안 |

<a id="r9"></a>

## R9

| **R9** | ✅ 완료 (세션12~13 — R24 잔여 정정으로 2026-08-02 플립) | **doc_review_gate 가 cp949(Windows)에서 deny 불가** + 심의 대상 집합이 2026-07-21 재구성 이후 stale(AGENTS.md·rules/**·policies/** 전부 skip) | 차단 게이트가 구조적으로 차단 불가 → cp949 즉사는 `#1243` 노출·시정, 심의 대상 stale 은 `#1265` skip 50→4 로 해소 (양 축 종결 — 이 행만 원장에서 뒤처져 있었다) |

<a id="r15"></a>

## R15

| **R15** | ✅ 완료 (`#1280` — ground-truth 축 신설) | **fastapi 버전 문서 drift** — `.claude/rules/deploy.md:39` 과 `README.md` 배지가 `0.139` 인데 실제 핀은 `0.140.13`(#1233 머지 후) | 🔴 **해소(2026-08-04)**: 핀이 `0.141.1`(#1273)까지 **두 번** 지나가는 동안 3지점이 `0.139` 에 멈춰 있었다. 수치 정정 + `check_docs_sync.check_dependency_pins` 신설 — 기대값을 `requirements.txt` 실핀에서 유도하는 **ground truth 축**이라 문서 사본이 함께 틀려도 red 다(R25 가 지적한 '사본끼리 대조' 한계의 보완축). 인용 0건 = 검사 범위 붕괴로 red. 뮤테이션 6종 red(배지 drift·산문 drift·범위 붕괴·ground truth 소실·`main()` 집계 퇴화·pre-commit `files` 누락). 🔴 뒤 2종은 **Grok claim-review `019fccd5` 가 적발** — 초판은 신규 테스트가 전부 순수함수를 직접 호출해 `main()` 집계를 `if ok:` 로 퇴화시켜도 전건 green 이었고, `.pre-commit-config.yaml` `files` 패턴이 `requirements.txt`·`deploy.md` 를 덮지 않아 **그 파일만 바꾼 커밋에서 훅이 미발화**했다. 🔴 **수용한 한계**: 배지는 `major.minor` 만 비교하므로 패치 bump 는 검사 대상이 아니다(배지 관례 자체가 major.minor). **기전(원문)**: dependabot 은 requirements.txt 만 갱신하고 문서/배지를 동기화하지 않는다(6-step ⑤ 는 사람/Claude 몫). **반증 수단**: `grep -n 'fastapi' .claude/rules/deploy.md README.md README.ko.md` 가 requirements.txt 핀과 일치하는지. 🔴 `check_docs_sync` 는 **테스트 카운트만** 보고 의존성 버전은 안 본다 — 가드 범위 확대 여부도 함께 판단 |

