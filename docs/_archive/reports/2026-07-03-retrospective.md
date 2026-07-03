# 2026-07-03 회고 — 2026-06-25~07-03 4세션 누적 갭 회복 (5+1 다중에이전트)

**워크플로우**: `wf_ca72074b-4a8` (`.claude/workflows/retrospective.mjs`) | **scope**: 2026-06-25~07-03 4개 세션 (PR #989~#1023, 약 30건)
**ROI**: findings_total 72 · confirmed 66 (P0 1 / P1 12 / P2 53) · FP 차단 6 · SEVERITY_ADJUST 16 · **verdict_coverage 1.0** · unverified 0 · 92 에이전트 · 0 오류 · 3 라운드 · 7.3M 토큰 · ~63분
**계기**: 직전 정식 회고 = `2026-06-23`. 이후 4개 세션(06-25 품질감사 / 06-29 AM B백로그 / 06-29 PM cross-vendor / 07-03 심층감사)이 정식 5+1 회고 없이 종료 (세션1은 "75줄 규모라 자기회고로 갈음"). 본 회고가 그 누적 갭을 회복.

> 본 보고서는 회고 P1 #43/#21(회고 보고서·산출물 미아카이브 반복 = 정책 8/9 카덴스 공백의 근본)을 직접 해소하기 위해 아카이브됨. 6-step 문서 최신화 의무 준수.

---

## 종합 판정

- **verdict_coverage 1.0** — 66 confirmed 전건이 cross-verify verdict 수신 (UNVERIFIED 0). "단일 패스 회고 13/8 한계 해소" 재입증.
- **FP 6건 전부 적대 검증 차단** — 예: CLAUDE.md:1 플레이스홀더 앵커 오인용 / STATE grep 백로그 섹션 부재를 결함으로 오판 / N3 rename 파싱을 staged-분기 결함으로 오판(실제 staged-agnostic 공유코드) / #1021 PR 본문 "N2 fail-fast 미표면화" 주장이 실제 본문과 정반대.
- **회고가 자기 과대주장도 정정** — SEVERITY_ADJUST **#57**: "operations_kpi API↔HTML days-guard parity 테스트 부재" 주장 → 실제 `src/api/admin.py:94`·`src/ui/routes/admin.py:107` 둘 다 `Query(ge=1, le=365)` 존재를 확인하고 FP성 하향/정정. (본 finding은 특정 클러스터 소속이 아닌 회고 자기교정 사례로 분류.)
- **운영 P0 = 0** (코드/보안). 유일 P0(#36)는 **프로세스** 항목(회고 카덴스 갭) — 운영 사고 아님.

---

## 클러스터 (66 confirmed → 8 테마, 중복 제거)

5 관점 × 3 라운드 loop-until-dry 특성상 동일 근본이 여러 렌즈로 반복 보고됨 → 8 테마로 정규화.

### 🔴 C1. 회고 카덴스 갭 (P0 #36 + P1 #1·#13·#21 + P2 #22·#31·#35·#47) — ✅ 본 회고가 해소 + 정책 진화 제안
- **실측**: `docs/_archive/reports/` 최신 회고 = 2026-06-23. `git log --since 2026-06-25` 회고 커밋 0건. 4세션·~30 PR 무회고 확정 (citation_verified=true).
- **재발 비용 실증** (핵심): 회고에서만 잡히던 결함 유형이 갭 창 안에서 실시간 재발 — self-inflicted CodeQL 2회(#996·#1023) + 공유로직 부분수정 2회(#1019·#1021-N1).
- **부수 관측**: #35 = 회고 자동화(`retrospective.mjs`)가 창 동안 미실행(도구는 있으나 트리거 부재) / #22 = 06-29 단일일 18 PR 머지 = 정책 1 진화 트리거(≥10 다중 PR) 충족했으나 검토 깊이 자가 보고 이행 미확인.
- **권장**: 정책 17-5(누적 결함 정기 검증 ≥5 사이클/≥18 PR)에 준하는 **회고 카덴스 트리거**를 정책 5/8에 신설 — 직전 정식 회고 이후 ≥N PR 또는 ≥3 세션 경과 시 5+1 강제, 자기회고 갈음은 **사용자 명시 승인 시에만** 허용. 감사 세션도 "사이클 종료 = 회고 진입" 판정. → **정책 진화 (사용자 결정 영역)**.

### 🔴 C2. self-inflicted CodeQL 재발 방지 가드 커버리지 갭 (P1 #7·#20·#49 + P2 다수 #2·#15·#25·#32·#39·#40·#48·#53·#54·#55) — 사용자 결정 (정책 17 재평가)
- **실측**: `#989`(env.py 11 ORM 전수 import) → `py/unused-import` 9건(#528~536) → `#996` `_REGISTERED_MODELS` 봉인. `#1021` N2 테스트가 `from src.config import` 추가(기존 `import src.config as cfg` 공존) → `py/import-and-import-from` → `#1023` 봉인. **둘 다 기존 가드(`#979` lint-changed-tests = F401/F841 test-only) 커버리지 갭에 정확히 빠짐**.
  - #1023형(dual-import): 두 import 모두 used → F401/F841 원리상 미검출.
  - #996형(env.py): `# noqa`로 flake8 억제 → flake8 확장으로 미검출 (CodeQL 전용 룰).
- **긴장**: 2026-06-23 회고가 dup-import pre-commit 훅(WF-1)을 **idiom churn·정책 16/17 사유로 의도적 DROP**. 재도입 = 정책 17(안정성 우선) 재평가 필요.
- **권장 2-tier**: (1) PR-changed 파일 한정 "동일 모듈 `import X` + `from X import` 공존" 경량 stdlib 가드(신규 write만 → legacy-churn 논거 비적용). (2) env.py형 = PR-scoped CodeQL이 왜 pre-merge 차단 못 하는지(code-scanning required-check 미설정) 규명 후 게이트 승격 여부. → **사용자 결정 영역**.

### 🟠 C3. Claude 가격 N-소스 parity 회귀 가드 부재 (P1 #6·#33·#56 + P2 #17·#24·#50·#58) — 구체 actionable (정책 4 위반)
- **실측**: Claude 가격이 3+곳 중복 — `src/shared/claude_metrics.py:39` `_PRICING_USD_PER_MTOK`(SSOT·비용계산) / `src/constants.py:174` `CLAUDE_MODELS`→`CLAUDE_MODEL_PRICING`(셀렉터) / i18n `model_hint`(en/ja/ko UI 문자열). `#1015`가 (1)만 갱신 → (2)(3) stale → `#1019` split-fix.
- **정책 4 위반**: "단언과 회귀 가드를 같은 PR에" — 현재 "가격 변경 시 3곳 grep 전수 의무" 단언만 있고 **CI 가드 없음**. repo에 `check_config_5way_sync.py`·`check_env_vars_sync.py` 동형 선례 존재.
- **권장**: 3-소스 parity 단위 테스트/pre-commit — family별 `_PRICING_USD_PER_MTOK`(input,output) ↔ `CLAUDE_MODEL_PRICING` 각 모델ID ↔ 각 언어 `model_hint` 정규식 추출값 동등 assert. → **Medium-tier 구체 PR (선례 재사용, 추상화 0)**.

### 🟠 C4. 공유 로직 "한 곳만 수정" 안티패턴 → grep 전수 default (P1 #3·#37 + P2 #14·#23·#30·#46·#52) — 정책 진화
- **실측**: `#1015`(가격 1소스만) + `#1021 N1`(operations_kpi API 라우트만, HTML 라우트 누락→Codex 적발). 동일 세션 창(15:53 → 17:47, ~2h) 동형 재발. **두 번째는 내부 5+1/self-review가 아닌 외부 Codex만 적발** → 정책 18 §5(mutual을 proactive discipline 대체물로 쓰지 말 것) 정면 위반.
- **정정 (SEVERITY_ADJUST #57)**: operations parity 테스트는 #1021 N1에 이미 실재. 일반 grep 규율이 갭.
- **부수 관측 #30**: 자동 분기 루틴(스케줄드 cron 가격 확인 등)이 정책 18 mutual을 설계상 우회 — #1015가 미검증 상태로 main 도달 → #1019 핫픽스 유발. 자동 생성 PR은 Codex 부재가 상시이므로 머지 전 후속 mutual 게이트 필요.
- **권장**: "값/로직 수정 직전 `grep -rn <심볼>` 전 호출처 열거 + diff에 '전수 확인 N곳' 1줄" 을 정책 16/18 페어 default 승격. 공유 서비스가 API+HTML 양 라우트 호출 영역 = High-tier 사전 grep. → **정책 진화**.

### 🟡 C5. docs SSOT drift (P1 #43 + P2 #5·#11·#12·#27·#28·#29·#38·#44·#45·#59·#60) — 구체 docs fix
- `STATE.md:5` 섹션 날짜 헤더 `(2026-06-29 기준)` stale → 본문 전량 2026-07-03(#1015~#1021) 반영본.
- `#1023`(self-inflicted CodeQL 봉인)이 cycle-history/STATE 서사 트레일 **미기재** — 선례 `#996`은 전용 엔트리 보유 = 비대칭. 6-step이 후속 fix에 미적용.
- cycle-history 범위 주석 stale + `env-vars.md` N2 `model_validator` 미반영 + field_validator 카운트.
- `#5`: `STATE.md` 단일 추적셀 비대화(~21KB/1행) — 매 세션 Edit 취약(partial-read 실패 다수 전례)·카운트 감소 추적 복잡. 구조 개선 여지(정책 17 안정성 고려).
- **근본**: `STATE.md:7` "다음 세션 갱신 규칙"이 **날짜 헤더 필드를 절차에서 누락** + `check_docs_sync`가 미검증 → 매 세션 재발 보장.
- **권장**: docs 정합 PR + `check_docs_sync`에 날짜 헤더 검증 추가 여부 검토. → **Low-tier docs (정책 17 안정성 우선)**.

### 🟡 C6. 개별 구체 코드 P2 (#8·#9·#26·#41·#42 + 감사 커버리지 #10) — 백로그/사용자 결정
- `#9` `_required_contexts_cache` 무상한 — 프로젝트 자체 `services.md` "메모리 캐시 상한 의무" 규칙 위반, 다수 감사 사이클 미해소.
- `#8`/`#42` `operations_service.operations_kpi` 공유 sink 자체는 여전히 unbounded (라우트 경계 Query 가드만 — **저위험**: 진입점 봉인됨).
- `#41` webhook 채널이 AI 리뷰 실패 신호 없이 raw `ai_review.summary` 발신 — `#992` "5채널 동일 패턴"의 6번째(webhook JSON) 호출처 누락.
- `#26` N2 locale validator import-time hard-fail 배포 위험 runbook 미반영.
- `#10` (meta): Claude 8-에이전트 보안 감사가 놓친 P1 2건(2026-06-29)이 **모두 silent-degradation 오류 경로**(crypto 평문 fallback·migration fail-open) → 감사 커버리지 편향 = cross-vendor 필수성 재확인.

### 🟡 C7. dependency/supply-chain 렌즈 부재 (P2 #61·#62·#63·#64·#65·#66) — 신규 관점, 사용자 결정
- 회고 5-렌즈에 supply-chain 소유자 부재 — dependabot bump ~40%가 changelog·호환성·회귀 미점검 통과.
- 프로덕션 의존성 floor-pin(`>=`) + lockfile 부재 → **CI 테스트 버전 ≠ Railway 배포 버전** drift 창.
- PR 시점 SCA 게이트(dependency-review/pip-audit) 부재 + codeql.yml 주석 커버리지 오도.
- major bump 2건(checkout v6→v7 #1018·codecov v6→v7 #1017) "CI green"만으로 머지.
- gh 토큰 workflow 스코프 부재 → workflow 수정 dependabot PR 머지 상시 거부(우회로만).
- trufflehog SHA-핀 버전 주석 drift → bump마다 수동 follow-up PR.

### 🟡 C8. tooling ROI / doc↔code drift (P2 #4·#16·#18·#19·#34·#51) — 혼합
- `#16` `integrity-audit.mjs` finder가 무거운 Opus 8도메인을 **un-chunked 단일 wave** 디스패치 → 같은 창(#1012)이 runbook에 명문화한 "≤3 동시 wave" mandate와 doc↔code drift.
- `#18`/`#34` `check_docs_sync`는 doc↔doc 내부정합만 검사, ground-truth(실 pytest collect) 미대조 → 배치 count-sync PR 반복(#1005·#1014·#1022).
- `#19` `doc_review_gate` PreToolUse 훅 — STATE/CLAUDE/README 편집 시도(실패 재시도 포함)마다 Haiku 3콜, 수치-only diff에 과투자.
- `#51` codex-rescue temp-dir 오염을 gitignore workaround로만 대응 — root cause(cwd=repo root) 미해결.
- `#4` 정책 18 Codex 샌드박스 false-NG 반복(pytest/net/json 차단) → "실행증거 전달 후 재-verdict" 왕복 상시화. Codex NG 수신 시 (a) 샌드박스 제약 유래 (b) 실제 결함 2-tier 선분류 정형화 여지.

---

## 조치 분류 (fix = 사용자 결정 — 정책 7/15/18)

| 클러스터 | 성격 | tier | 조치 |
|----------|------|------|------|
| C1 회고 카덴스 | 정책 진화 | Medium | 카덴스 트리거 신설 제안 → 사용자 결정 |
| C2 CodeQL 가드 | CI/pre-commit | **High** | 정책 17 재평가 (2026-06-23 DROP 번복 여부) → 사용자 결정 |
| **C3 가격 parity 가드** | 회귀 테스트 | Medium | **선례 재사용 구체 PR (정책 4 해소) — 권장 우선** |
| C4 grep 전수 default | 정책 진화 | Medium | 정책 16/18 페어 승격 제안 → 사용자 결정 |
| C5 docs SSOT drift | 문서 정합 | Low | 정확성 fix (정책 17 안정성 우선) |
| C6 개별 코드 P2 | 코드 | Mixed | #41 webhook·#9 캐시상한 = 구체 / 나머지 저위험 백로그 |
| C7 supply-chain | 설계/도구 | **High** | 신규 관점 — 설계 트레이드오프, 사용자 결정 |
| C8 tooling ROI | 도구 정합 | Low/Med | #16 doc↔code drift = 구체 / 나머지 ROI 재검토 |

**자동 수정 금지** (retrospective 런북) — 본 보고서 아카이브(C1 근본 #43 해소)만 즉시 수행. 나머지는 사용자 클러스터별 결정 후 정책 18 Codex mutual 거쳐 PR.

---

## verdict_coverage · 워크플로우 건전성

- **verdict_coverage 1.0** (unverified 0) — completeness/gap 라운드 정상 수행, C10 회복력(try/catch) 작동, 92 에이전트 0 오류.
- 2026-06-23 첫 dogfooding 대비: completeness 라운드 API 500 소실(C10-e) → 이번엔 미발생. gap 라운드 정상.
- ⚠️ **자기 관찰 (C8 #16)**: peer 워크플로우 `integrity-audit.mjs`의 finder wave 분할이 runbook ≤3 mandate와 drift — 회고 도구 스택 자체의 개선 여지.

---

## cross-verify ↔ mutual 2-layer

본 5+1 회고 = **Claude 내부 self-verify (관점 다양성)**. 정책 18 Codex mutual (외부 LLM 모델 다양성)과 **독립 2-layer**. 본 회고로 mutual 생략 불가 — 후속 fix PR은 각각 Codex mutual 별도 수행 의무 (C4 #37가 정면 지적: mutual을 proactive discipline 대체물로 쓰지 말 것).
