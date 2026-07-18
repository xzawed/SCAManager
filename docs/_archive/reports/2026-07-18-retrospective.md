# 5+1 회고 — 2026-07-18 (사이클: 2026-07-03 회고 이후 ~46 PR)

> 정책 8 (5+1 다중 에이전트 회고)의 결정론적 실행. 엔진 = `.claude/workflows/retrospective.mjs`.
> read-only 분석 — **fix 는 사용자 결정**(정책 7 PR 단위 / 15 사전 사고). 자동 수정 금지.

## 실행 메타

| 항목 | 값 |
|------|-----|
| Run ID | `wf_331cdddf-519` |
| scope | session (2026-07-03 회고 #1024~1029 이후 ~46 PR: **#1032~#1077**, 5~6 세션) |
| 에이전트 | **87** (finder 15 = 5 관점 × 3 라운드 + gap 4 + cross-verify 전건) · 0 error |
| 토큰 | ~8.65M |
| 라운드 | 3 (신규 20 → 18 → 20) + completeness gap 4 |
| **verdict_coverage** | **1.0 (100%)** — 67 finding 전건 verdict 수신 (UNVERIFIED 0, 단일 패스 13/8 한계 미재발) |

## ROI

| 지표 | 값 |
|------|-----|
| findings_total | 67 |
| **confirmed** | **61** (P0 **3** · P1 **15** · P2 **43**) |
| false-positive 차단 | **6** (적대 cross-verify — 인용 drift·면제 적용·저가치 추측 논파) |
| severity 조정 | 10 |

> P0 3건은 **동일 core issue**(회고 카덴스 트리거 위반)를 3 관점이 독립 발견 — dedup 후 1 근본. P1 15건은 ~6 테마로 수렴.

---

## P0 — 회고 카덴스 강제 트리거 재위반 (근본 1건)

**결함**: 정책 8 진화 (4) 회고 카덴스 강제 트리거(#1028, **2026-07-03 신설**)가 **첫 측정창에서 위반**됐다. 직전 정식 회고(2026-07-03) 이후 이 회고(2026-07-18)까지 **~46 PR / 5~6 세션 무회고** — 트리거 임계(≥3 세션 또는 ≥15 PR)의 **~3배 초과**. 트리거는 07-09 세션 종료(~16 PR·2~3 세션)에 발화했어야 하나 발화하지 않았다.

**재발성**: 이 트리거는 2026-07-03 회고의 C1 finding("직전 회고 이후 4세션·~30 PR 무회고 갭")이 **바로 그 갭을 막으려 신설**한 정책이다. 즉 **직전 시정(문서-only 정책 추가)이 행동을 바꾸지 못하고 더 큰 규모로 재발**했다. P0 정의("정책 위반")에 문자 그대로 해당(운영 사고는 없어 자기교정된 상태이나 강제 정책의 반복 위반).

**인용**: `CLAUDE.md:206` (강제 트리거 본문·"예외 금지") — citation_verified ✅. 아카이브 실측: 2026-07-03 이후 유일 07월 리포트 = `2026-07-17-grok-full-review.md`(회고 아님) → 회고 아카이브 0건.

**조치 방향** (문서-only 2회 연속 실패 → 기계적 집행):
1. **세션 시작 체크리스트 1줄 자가확인** — "직전 정식 회고 커밋 이후 머지 PR/세션 카운트 → ≥15/≥3 시 회고 진입 판정" (`gh pr list` / `docs/_archive/reports/` 최신 날짜 대비).
2. **STATE.md 추적셀** — "직전 정식 회고: YYYY-MM-DD·기준 PR# / 이후 세션 N·머지 PR N (트리거 3/15)" — 매 docs-sync PR 에서 강제 갱신 (정책 4 단언+가드 페어).
3. **(선택) pre-commit/CI 카운터** — last-retro 태그 이후 머지 PR 수 임계 도달 시 loud 경고.

---

## P1 — 6 테마 (15 confirmed)

### 테마 A — 카덴스 집행 자동화 (P1#2·5·11·12, P0와 동일 축)
소프트 자가 점검이 **인지에만 의존** → 신설 2주 만에 자기 위반. 정책 4 정신(단언+가드 동일 PR)대로 기계적 카운터 도입. **P0 조치와 통합.**

### 테마 B — self-inflicted CodeQL `py/unused-import` turn-0 가드 진공 (P1#4·6·8·10)
- **근본**: `lint-changed-tests` CI job 의 flake8 이 `# noqa: F401` 을 **존중** → side-effect ORM import(등록용)를 pre-merge 에 못 잡음. CodeQL 은 별도 룰셋이라 main 전체 스캔에서만 노출 → **본 창에서만 반응형 봉인 PR 3건**(#1040·#1066·#1077).
- **testing.md:28 이 안티패턴을 공식 권장** — `# noqa: F401` 예시가 근본 원인.
- **조치**: `.github/workflows/ci.yml` `lint-changed-tests` 에 `flake8 --disable-noqa --isolated --select=F401 $changed` 스텝 추가(flake8 7.3.0 지원 실측) → side-effect import 를 authoring 시점에 fail → 저자가 삭제하거나 `_FK_TARGET_MODELS`/`_REGISTERED_MODELS` 튜플-참조로 봉인(CodeQL 도 'used' 인식). testing.md:28 을 튜플 패턴으로 교체 + 회귀 가드 동반(정책 4).

### 테마 C — PostToolUse pytest 훅 false-green (P1#7)
- **결함**: `.claude/settings.json:26` 의 PostToolUse pytest 훅이 **전체 5566 테스트를 60s 타임아웃 안에 완주 불가** → 타임아웃 → false-green. 필수 원칙 "Hook 신뢰"의 토대 붕괴.
- **조치**: 훅을 빠른 단위 스코프(`pytest tests/unit -q -p no:cacheprovider`, 이상적으로 편집-경로 선택) + 타임아웃 상향(120~180s), 또는 "완주=green" 문구를 "best-effort 조기실패 탐지"로 하향 정정. 전체 게이트는 push-time(6-step ②)에 이미 위임됨.

### 테마 D — declared-but-unwired / dead-code 완료 게이트 통과 (P1#9·14·15)
- `find_orphaned`(#1060)가 **호출자 0 dead code 로 13 PR 생존** — 전 스위트 green + 5+1 + opus whole-branch 모두 미검출(#1073 가 뒤늦게 배선). service 함수 mutation-green 이 route 배선을 못 잡음.
- **조치**: 경량 AST 가드(`check_dual_import.py` 동형) — src/repositories·src/services 신규(diff-scoped) 공개 함수가 src/ 내 호출자 0 이면 CI fail. 의도적 미배선은 whitelist 주석. route→service parity 가드 병행.

### 테마 E — 비대칭 가드(only-one-side-guarded) turn-0 미차단 (P1#1)
- grep-전수 default(정책 16 진화)가 **심볼**은 전수하나 **취약점 클래스**는 못 잡음 → #1057(auto-merge SHA 결속)이 형제 경로 approve 를 미결속 → 한 세션 뒤 #1072 가 사후 수정.
- **조치**: 신뢰경계(merge↔approve↔review) 결속 시 같은 경계를 넘는 **모든 액션을 같은 PR 에서 열거**하는 규율을 grep-전수에 **의미적 대칭 축**으로 추가.

### 테마 F — 결정 규율: 미검증 전제를 waiver·배제 근거로 단정 (P1#3)
- `src/github_client/repos.py:37` — 게이트 waiver·분석 경로 배제 시 실측 근거(probe·grep 호출부 추적·양방향 재검증) 없이 단정 (3회 재발).
- **조치**: "~일 것이다/~없다" 단언은 호출부/외부계약 확인 후에만 확정 — 특히 보안/데이터-접근 PR High-tier.

### 테마 G — Phase 종료 owed 운영 검증 미취합 (P1#13)
- 8-PR Wave 종료(#1076)에서 **코드-미증명 운영 검증 4건**(#1071 HSTS/쿠키 · #1072 GitHub 422 · #1073 orphan sweep 로그 · #1075 retention DELETE)이 단일 §"🔍 사용자 검증 필요" 표로 취합되지 않음 (정책 2 진화 + 정책 13 누락).
- **조치**: trailing sync PR body 에 STATE/배지 sync 와 페어로 §owed-verification 표 상시 배치 (`| PR | 검증 항목 | 검증 방법 | 정책 | 상태 |`).

---

## P2 — 43 confirmed (클러스터 요약)

| 클러스터 | finding | 핵심 |
|---------|---------|------|
| **CodeQL noqa-blind 가드** | P2#1·3·14·34·39·40 | 테마 B 강화 — pre-merge `--disable-noqa` 가드. #1077 튜플 미read 이탈(P2#4)=**이미 fix-up 완료**. |
| **owed 운영 검증** | P2#31·38 | #1058 SMTP(출시 이래 100% 실패)·#1062 IDOR 과잉차단 = **안전/데이터 등급 → 명시 회신 요청 의무**. |
| **docs drift 배치** | P2#7·8·9·15·19·20·21·22·28·29·30 | README cron 엔드포인트 2종 누락 + EN/KO parity · FastAPI 배지 stale · STATE repo `11→13` · env-vars 누락 키(DOC_REVIEW_GATE_DISABLED·INTERNAL_CRON 영향·상수) · saas RLS matrix `12→13`. |
| **retention sweep 갭** | P2#16·17·43 | claude_api_calls(3번째 무한증가 테이블) 미GC · merge_retry 종결 4/6 경로 미기록 · **PG naive/aware coercion 미실증**(pg-concurrency round-trip 필요). |
| **reliability** | P2#18 | `begin_attempt`(#1073) fail-safe 아님 — 흔적 INSERT 실패 시 정상 분석까지 무음 중단(finish 와 비대칭). |
| **로드맵 tier 오분류** | P2#23·26 | "전부 사용자 결정 선행" 일괄 라벨이 **관측성(코드전용 Medium)**까지 과-게이팅 → 정책 15 3-tier 재분류. |
| **툴링 ROI** | P2#24·37 | `doc_review_gate.py` 매 critical-doc 편집마다 3 Haiku 호출 — STATE 수치 bump 에 과잉. |
| **CI backstop** | P2#12·36 | 6 stdlib 무결성 가드 pre-commit-only(우회 가능) → 서버측 CI job 백스톱. full-suite 없이 import/parametrize 연쇄 봉인. |
| **route→service parity** | P2#41·42 | owner-filter parity 문서 규약뿐 기계 미강제 → 단일 parametrized parity 테스트. "mutation-green ≠ wiring-verified" testing.md 명시. |
| **운영 위생** | P2#2·27 | 머지 로컬 브랜치 미정리(`/clean_gone`) · railway.toml cron `curl -s`(–f 부재)로 5xx 무음. |
| **결정 traceability** | P2#10·13·32·33 | R1 NULL-owner 읽기노출 신선 승인 인용 부재 · probe-before-waive 일반화 · 신뢰경계 결속 완전 열거. |

전체 61 confirmed + recommendation 원문: 워크플로우 반환 JSON(`wf_331cdddf-519`) 참조.

---

## §자성 (정책 9 — 첫 적용 창 자기위반 명시)

- **본 회고 자체가 카덴스 위반 회복 사례다.** 트리거(#1028)를 신설한 바로 그 정책이 첫 측정창에서 위반됐고, 이는 문서-only 시정의 한계를 실증한다. 다음 세션은 **기계적 카운터**(P0 조치 1·2)를 우선 도입해야 한다 — 그러지 않으면 3번째 재발이 보증된다.
- **#1077(내 이번 세션 CodeQL 봉인)이 확립된 #1040 튜플-패턴에서 이탈**했다(P2#4) — 튜플 정의만 하고 loud-fail read 를 생략. 회고가 지목 → 동일 PR fix-up 으로 즉시 정합(loud-fail read 복원). turn-0 에 #1040 을 참조했어야 했다.
- self-inflicted CodeQL 재발(테마 B)은 **예측 가능했고**(2026-07-03 C2 tier-(2)로 이미 유예됨) 3회 실현됐다 — 예방 가드 유예의 누적 비용.

## 회귀 가드 정합

- verdict_coverage **1.0** — completeness try/catch 격리(C10) + UNVERIFIED bounded 재검증(C10-d) 정상 작동, gap 라운드 소실 없음.
- 워크플로우 회귀 가드: `tests/unit/scripts/test_retrospective_resilience.py` · `test_workflow_loop_sync.py` (drift 가드).

## 후속 (fix = 사용자 결정)

confirmed 61건은 **트랙별 옵션 표**로 사용자에게 상정(정책 1) — 자동 수정 금지(정책 7/15). 추천 우선순위: **① 카덴스 기계화(P0) → ② CodeQL turn-0 가드(테마 B) → ③ Hook false-green(테마 C) → ④ dead-code/parity 가드(테마 D) → ⑤ docs drift 배치 → ⑥ owed 검증 회신(안전등급)**.
