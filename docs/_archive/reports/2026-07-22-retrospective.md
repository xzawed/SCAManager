# 5+1 회고 — 2026-07-22 (범위 #1114~#1170, 57 PR·4세션)

> 정책 8 다중 에이전트 회고. 실행 = `.claude/workflows/retrospective.mjs` (run `wf_fad44f59-7cc`).
> 이 파일의 존재가 **회고 카덴스 카운터를 리셋**한다(`check_retro_cadence.py` 는 `_archive/reports/`
> 최신 `*retrospective*.md` 이후 머지 PR 을 셈) — 즉 이 회고가 곧 P0 카덴스 부채의 이행이다.

## 실행 지표

| 지표 | 값 |
|------|-----|
| 범위 | 57 PR (#1114~#1170), 경계 `68dc80e..a8695f9`, 약 4세션 (세션3~6 + 현 세션) |
| 관점 | 5종(process·code·docs·decision·tooling) + completeness critic (+1) |
| 라운드 | 3 (loop-until-dry) |
| 에이전트 | **93** (0 error) · 8.82M 토큰 · 83분 |
| findings_total | 73 |
| **verdict_coverage** | **1.0** (전건 검증 — UNVERIFIED 0) |
| ROI | 확정 **65** (P0 **3** · P1 **18** · P2 **44**) · severity_adjust 11 · **false-positive 차단 8** |

> 🔴 verdict_coverage 1.0 = 73 finding 전부 cross-verify 판정 수신 (단일 패스 "13 중 8만 검증" 한계 해소).
> P0/P1 18건에 카덴스 주제 near-duplicate 다수 — 아래에서 **고유 이슈로 통합**해 서술한다(원 카운트는 관점별 중복).

---

## P0 (3건) — 전부 단일 근본: 회고 카덴스 자기위반 3회차

세 P0 는 관점(decision·process)만 다를 뿐 **동일 결함**이다: 직전 정식 회고(2026-07-19-retrospective-2)
이후 **57 PR·4세션이 회고 없이 머지**됐다(임계 15의 **3.8배**). `check_retro_cadence.py` 는 세션5·6 시작마다
loud 경고를 냈으나 **advisory(exit 0)라 3세션 연속 이월**됐고, 이월에 대한 **사용자 승인 기록이 없다**.

- **[P0-1] (decision, `backlog.md:42`)** — 회고 의무를 #1150 에서 명시 인지하고도 사용자 승인 없이 14+ PR 추가 머지. 정책 8 위반.
- **[P0-2] (process, `check_retro_cadence.py:26`)** — 정식 5+1 회고가 세션5·6 loud 트리거에도 2회 연속 이연, 이연 승인 미기록 (정책 8 진화 (4) 위반).
- **[P0-3] (process, `check_retro_cadence.py:13`)** — 카운터를 기계화(#1077)해 막으려던 자기위반이 **문서-only 시정의 3회차로 재생산**. advisory 배너로는 크로스세션 이연을 못 막음이 3.8x 누적으로 실증됨.

> 🔴 **핵심 통찰**: 이 저장소가 싸워 온 observer-lie(관측자가 거짓말) 클래스가 **프로세스/메타 층에서 재생산**됐다.
> 카운터는 "관측"만 하고 "행동"을 강제하지 못했다 — 정확히 코드 층 fail-open 가드가 실패하는 방식과 동형.

**이행**: 본 회고 실행 + 이 아카이브 파일이 P0 를 종결(카운터 리셋). 재발 방지책은 §사용자 결정 안건 참조.

---

## P1 (18건) — 고유 이슈 5종으로 통합

### ① 카덴스 집행면 부재 + 세션5 회고 미아카이브 (P1-1·2·4·6·7·9·10·11·12·14 — 10건이 이 주제)
- **세션5 회고(wf_317714e4·88 에이전트·확정 61)가 `_archive/reports/` 에 미아카이브** (`cycle-history.md:163` 에만 존재) → 카운터가 실부채를 **~4배로 오보**(57 vs 실 ~14~21) + 본 회고가 세션5 기회고분을 재훑음 + 61 findings 상세 소실(runbook:50 이 경고한 추적성 저하). `runbook retrospective.md:50` 산문 의무가 **3회째 실패**.
- **권장**: (a) 세션5 보고서 소급 아카이브(복원 불가 시 요약이라도 날짜파일로). (b) 아카이브 스텝을 기계 검증 승격 — "회고 fix PR 머지됐는데 같은 창에 신규 retrospective 파일 없음" → SessionStart loud 경고. (c) advisory 이월 시 승인/사유를 owed 원장에 강제 append (§사용자 결정).

### ② architecture-tree 가드(#1160)의 과대주장 (P1-3·5·8·15 — 4건)
- `check_architecture_tree_sync.py` 는 **패키지·최상위 모듈만** 검사 — 기존 패키지 **내부** 신규 파일은 초록불 통과. 그런데 커밋/docstring 은 "신규 파일 미등재 3회 재발 **기계 봉인**"을 주장 → observer 과대주장. 게다가 그 가드를 만든 두 파일(`check_architecture_tree_sync.py`·`check_guard_fail_open.py`)이 **정작 `architecture.md` scripts/ 트리에 미등재**.
- **권장**: (1) architecture.md scripts/ 트리에 두 파일 등재. (2) 가드를 파일 단위로 확장하거나 — 아니면 "봉인" 주장을 "패키지·최상위 모듈 등재 floor"로 **정직하게 하향**(정책 17). (3) 뮤테이션 테스트에 "패키지 내부 신규 파일" 케이스 추가.

### ③ 안전등급 owed #1062 (NULL-owner IDOR) 방치 (P1-16)
- 2026-07-17 이후 **~5일·다중 세션 ⏳**, 유일 근거인 DB 스냅샷이 in-tree 코드와 모순, 기계 트리거 없음. 원장 스스로 "경고 피로가 진짜 안전항목까지 무시하게 함"을 경고(#1129 자기인증 P0 를 낳은 클래스).
- **권장**: 본 회고에서 정책 5 NEW-P0-N 로 **명시 회신 요청**(§회고 질문). 나아가 가변 스냅샷을 **감시 불변식으로 전환**(NULL-owner repo 수 loud-flag).

### ④ npm 공급망 SCA 게이트 비대칭 (P1-17)
- `ci.yml:238` pip `dependency-audit` 有 ↔ npm audit **無**. 동일 프로젝트 표준의 비대칭 — #1169 brace-expansion 같은 반응형 fix 가 재발 예정.
- **권장 (architecture 결정 — 정책 9 완화 미적용, 옵션 표 사전 확인 의무)**: (A) npm SCA fail-closed CI 게이트 신설(pip 대칭) vs (B) dependabot.yml npm ecosystem 추가해 monitor-only(정책 17 — devDeps·빌드 전용이라 런타임 노출 낮음).

### ⑤ 🔴 이번 세션 #1170 이 **문서-only 시정 + 살아있는 위반 인스턴스 존치** (P1-18 — 정책 8-5 직격)
- 이번 세션에 추가한 `testing.md:66` "does not raise" 규칙은 **산문뿐**이고, **AST 로 탐지 가능한 동일 안티패턴의 실 인스턴스가 지금도 살아있다**: `test_failover.py:304-313` 의 `try/except + pytest.fail`. 즉 #1170 은 이 저장소의 반복 실수(문서-only 시정)를 **또 재생산**했다.
- **권장**: fail-closed AST 가드 신설(`ExceptHandler` 본문이 `pytest.fail(...)` 단독인 것 차단, `tests/` 스코프 포함) + pre-commit/CI 배선 + guards.md 불변식 2대로 **실경로 뮤테이션 red 실증**. 같은 PR 에서 `test_failover.py:304-313` 을 직접 호출로 교정(정책 4 단언+가드 동시).

---

## P2 (44건) — 클러스터 요약

### STATE.md 심층 drift (11건 — docs 지배 클러스터)
가장 큰 P2 밀집. `STATE.md` 가 다각도로 어긋남:
- 날짜 헤더(line 5) 2026-07-20 에 동결 — **자기 자신을 "상시 누락 필드"로 명시한 in-file 규칙이 3연속 자기위반**.
- 누적 추적셀 trail 이 세션4(#1126, 5684)에서 멈춤 — 헤더/배지 5850 과 **166건 갭** 미기록.
- line 18 산술 자기모순: "5684→5850(+130)" (실제 +166).
- 세션 자기 산출물 **#1167~#1170 이 SSOT 에서 통째 누락** — "최신" 블록이 #1166 에 동결 (정책 8-5·6-step ⑤).
- SonarCloud 행(27/29/31)이 2026-06-22 green 을 단언 — **#1168 QG 회귀/회복 미반영**(회복은 "다음 스캔" UNVERIFIED).

### B8 fail-open floor(#1165) 커버리지·정확도 (code 3 + tooling 3 = ~5 고유)
- **표면 비대칭**: `check_guard_fail_open.py` 는 `scripts/check_*.py` 만 스캔 — **#1145 false-green 이 실제 발생한 `.claude/hooks/`** 와 workflows·alembic 은 미커버. guards.md 3-불변식이 명시 관할하는 표면과 어긋남.
- **alias 맹점**: `import re as _re`·from-import 를 못 봐 정상 가드를 fail-open 오판 → escape 주석 상습화(floor 의 유일 우회로가 침식됨).

### 문서 정합 단방향 가드 (docs/tooling)
- `check_toc_anchors.py` 는 TOC→헤딩 **단방향** — cycle-history 최신 3개 세션이 목차에 없는데 exit 0(observer-lie).
- `check_docs_sync.py` 는 **mirror-parity 만** 검사, **freshness 못 봄** — 2일/4-PR stale SSOT 에 GREEN.
- `cycle-history.md:173` 이 이미 해소된 /login drift 를 "🟡 미해결"로 표기(같은 블록 180줄과 모순).
- backlog.md 진입점 헤더가 세션4 에 3세션 stale.

### 거버넌스·의사결정 (decision/security)
- **B6-b (AI 자기 머지 거버넌스, High-tier)** 가 opt-out 권장으로 프레이밍되고 세션6 재상정 의무(정책 5/9) 미이행 → 무행동이 Claude 권장안으로 귀결.
- 🔴 **red 신호를 조기에 "외부 원인"으로 귀인하는 결정 패턴 재발** — 이번 세션 SonarCloud "외부 장애뿐" 조기 결론이 바로 그 사례(사용자 대시보드 공유로 정정). 자성 항목.
- 재구성 배치가 "detail 이관/보존" 단언했으나 실제 소실 6건(후행 재감사 적발) — 정책 17-3 단계별 검증이 프로그램 말미로 밀림.
- scan-security cron(#1116) 실동작 검증이 owed 미등재 — "재확인 불필요" 헤더가 미관측 job 을 stale 보호.

### 민감경로 가드 (code)
- SCAManager 고유 파일(main.py·logging_config.py)을 **전역 패턴으로 고객 리포에도 광범위 매칭** + 보류 코멘트 멱등성 없음(중복 post 위험).

---

## False-positive 차단 8건 (ROI — 적대검증이 걸러냄)

cross-verify 가 8건을 FALSE_POSITIVE 로 기각(추측·이미 해소·근거 부족). 11건은 SEVERITY_ADJUST(실재하나 심각도 조정).
verdict_coverage 1.0 이므로 **65 확정 전부가 회의적 +1 검증을 통과**한 것 — 단일 패스 회고 대비 신뢰도 상승.

---

## 메타 통찰 (이 회고가 스스로 발견한 것)

1. **observer-lie 가 메타 층으로 이동**: 코드 fail-open(#1136·#1145·#1156)을 봉인하는 동안, 같은 병이 **회고 카덴스·아카이브·문서 freshness 가드**에서 재생산됐다. 공통 형태 = "관측은 하는데 강제(집행면)가 없다"(advisory·단방향·mirror-only).
2. **이번 세션 자기 산출물이 2회 자기 적발**: (a) #1170 문서-only 시정 + 살아있는 위반(P1-18), (b) SonarCloud "외부 장애" 조기 귀인(P2). 정책 8-5(회고 범위에 세션 자신 포함)가 실제로 작동해 **가장 검증 덜 된 코드가 회고를 피하지 못했다**.
3. **"봉인" 어휘의 남용**: 여러 가드가 실제 커버리지보다 넓게 "봉인/기계 봉인"을 주장. 정직성 우선(정책 17) — 주장을 실제 floor 로 하향하거나 커버리지를 확장할 것.

---

## 조치 원칙

**fix 는 자동 수행하지 않는다**(정책 7 PR 단위 · 15 사전 사고 · 8 회고는 발견까지). 위 권장은 §사용자 결정 안건과
자유 발언에서 옵션으로 상정한다. 이 아카이브 파일 자체는 P0(카덴스) 이행이며, 나머지는 사용자 결정 후 PR 로 진행.
