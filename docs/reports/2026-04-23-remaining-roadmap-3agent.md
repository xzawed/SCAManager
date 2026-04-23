# 2026-04-23 잔여 과제 3-에이전트 논의 보고서

> Phase S.1~S.3 완료 후 남은 4개 잔여 과제 (Phase Q.7 · Phase S.4 · P4-Gate · Phase D.3~D.8) 의 구체 계획을 3개 Explore 에이전트가 분담 논의하고 결과를 종합해 권장 실행 경로를 도출.
>
> 기준 커밋: `964e981` (S.3-E 완료, origin/main).

---

## 1. 에이전트 분담

| Agent | 담당 영역 | 산출물 |
|-------|----------|--------|
| **A** | Phase Q.7 (Cognitive Complexity 5건) + Phase S.4 (pipeline test mock 재설계) | 분할 설계 + mock 전략 Option A/B 비교 |
| **B** | Phase D.3~D.8 외부 정적분석 도구 확장 로드맵 | 도구별 ROI + Docker 전환 경계 |
| **C** | P4-Gate 프로덕션 실증 프로세스 + 전체 시나리오 3가지 | 시나리오별 ROI·리스크·역할 분담 |

---

## 2. Agent A — Phase Q.7 + Phase S.4

### Phase Q.7 — Cognitive Complexity 5건

| 대상 | 현재 CC | 분할 방안 | 예상 감소 | 리스크 |
|------|---------|----------|----------|--------|
| `gate/engine.py::run_gate_check` | 31 (+16) | `_run_review_comment` · `_run_approve_decision` · `_run_auto_merge` 3개 헬퍼 분리 | -10~12 | 🟡 pipeline-reviewer 필수 |
| `analyzer/io/tools/slither.py::_parse_slither_json` | 20 (+5) | `_extract_line_number` · `_map_severity` · `_map_category` 순수 함수 추출 | -5 | 🟢 |
| `notifier/github_comment.py::_build_comment_from_result` | 19 (+4) | `_add_ai_summary` · `_add_feedback` 등 5개 섹션별 헬퍼 | -5~7 | 🟢 |
| `cli/formatter.py` (CC 16) | 16 (+1) | 구조 양호 — 1~2줄 간소화 | -1 | 🟢 극저 |
| `cli/git_diff.py` (CC 16) | 16 (+1) | 선형 로직 — 1~2줄 간소화 | -1 | 🟢 극저 |

**총 소요**: 3 Phase × 1~1.5일 = **3일**
**효과**: Quality Gate 영향 **없음** (이미 OK), CRITICAL 5 → 0

### Phase S.4 — pipeline test mock 재설계

**근본 원인**: `tests/unit/worker/test_pipeline.py` 13곳이 단일 `filter_by.return_value.first.side_effect` 체인으로 **repo 조회 + analysis 조회 2번** 묶어서 mock → `repository_repo.find_by_full_name` 내부를 `filter` 로 바꾸면 체인 분리되어 회귀.

**Option A (추천)** — 직접 함수 mock:
```python
with (
    patch("src.repositories.repository_repo.find_by_full_name", return_value=mock_repo),
    patch("src.repositories.analysis_repo.find_by_sha", return_value=None),
):
    await run_analysis_pipeline("push", PUSH_DATA)
```
- 수정 범위: test_pipeline.py 13곳 (60~80줄 추가)
- 외부 영향: 없음 (테스트 파일만)
- 해결 후 S.3-D (`get_repo_or_404` UI/webhook 확산) 자동 가능

**Option B** — Fake Repository 구현: 80~120줄 + 의존성 주입 구조 변경 필요. 과도.

**총 소요**: S.4 **1.5일** (Option A) + S.3-D **0.5일** = **2일**

### Agent A 총 예상
- Q.7 + S.4 = 4.5일 + pipeline-reviewer 리뷰 1.5일 = **6일 작업**

---

## 3. Agent B — Phase D.3~D.8 로드맵

### 도구별 ROI 평가

| Phase | 도구 | 언어 | 소요 | ROI | 실행 판단 |
|-------|------|------|------|-----|---------|
| **D.3** | RuboCop | Ruby | 2h | 🟢 높음 | ✅ P4-Gate 통과 후 **즉시** |
| **D.4** | golangci-lint | Go | 3.5h | 🟢 높음 | ✅ D.3 후 (`go.mod` 자동생성 필요) |
| **D.5** | PHPStan | PHP | 2.5h | 🟡 중간 | ⏸️ **수요 확인 후** (Semgrep 이미 지원) |
| **D.6** | detekt | Kotlin | 4h | 🟠 중간 | 🚫 **Docker 전환 필수** |
| **D.7** | PMD | Java | 4h | 🟠 중간 | 🚫 **Docker 전환 필수** (JVM cold start 10-15s) |
| **D.8** | cargo clippy | Rust | 5h | 🔴 낮음 | 🚫 최후순위 (crate 단위 분석) |

### 아키텍처 경계선

- **D.3~D.4** (nixpacks 유지 가능): Ruby gem + Go binary. 현재 빌드 구조 그대로.
- **D.5** (경계): PHP 런타임 +150MB 추가. 수요 불명확 → 보류.
- **D.6~D.8** (Docker 전환 필수): JVM 600MB + Rust 700MB → 이미지 2GB+. `STATIC_ANALYSIS_TIMEOUT=30` 초 내 JVM cold start 미완. **별도 Phase 분리 권장**.

### 재사용 가능한 기존 패턴
- Analyzer Protocol (`supports/is_enabled/run`) — D.1/D.2 선례 그대로
- `_parse_{tool}_{format}()` 분리 (subprocess mock 없이 검증)
- `src/analyzer/io/static.py` import 1줄 추가로 자동 등록
- nixpacks aptPkgs 추가 + buildCommand 확장

---

## 4. Agent C — P4-Gate 실증 + 우선순위

### P4-Gate 6항목 체크리스트 (D.3 착수 차단 조건)

| # | 항목 | Claude 역할 | 사용자 역할 | 시간 |
|---|------|------------|-----------|------|
| 1 | Railway 빌드 로그 확인 | 검증 프롬프트 작성 | Railway 대시보드 → Deployments 로그 확인 | 5분 |
| 2 | solc 사전 설치 검증 | 검증 명령 제공 | 컨테이너에서 `which solc && solc --version` | 5분 |
| 3 | cppcheck 실증 PR | 샘플 C 코드 제공 | **외부 테스트 리포 필요** — 의도적 결함 `.c` → PR → 결과 확인 | 15분 |
| 4 | slither 실증 PR | reentrancy `.sol` 샘플 제공 | 동일 리포 → `.sol` PR → 결과 확인 | 15분 |
| 5 | 타임아웃 확인 | 측정 규약 제공 | 분석 완료 시간 기록 (<30s 목표) | 2분 |
| 6 | 점수 반영 확인 | 점수 규칙 제공 | PR 최종 점수에서 감점 확인 | 5분 |

**사용자 의존도**: 매우 높음 (Railway 접근 + 외부 리포 관리 + PR 승격). Claude 자동화는 샘플 코드·검증 스크립트 제공에 국한.

### 샘플 테스트 리포 제안
- 신규 리포 `xzawed/SCAManager-test-samples` 생성
- `samples/buffer_overflow.c` — `strcpy` 취약점
- `samples/reentrancy.sol` — 상태 변경 전 재진입
- README 에 의도 설명 + SCAManager 리포 링크

### 3가지 시나리오 비교

| 시나리오 | 범위 | 소요 | ROI | 리스크 |
|---------|------|------|-----|--------|
| **A 보수적** | Q.7 → S.4, D.3 미착수 | 5h | 낮음 (사용자 가치 0) | 🟢 낮음 |
| **B 균형 (권장)** | P4-Gate + Q.7 + S.4 + D.3 | 12h + 사용자 45분 | 매우 높음 | 🟡 중간 (사용자 의존) |
| **C 확장 지향** | D.3 선착수 (게이트 skip) + D.4~D.5 병렬 | 20h+ | 매우 높음 | 🔴 높음 (동시성 혼란) |

Agent C 추천: **시나리오 B**.

---

## 5. 3-에이전트 합의 — 최종 권장 로드맵

### 🟢 즉시 실행 가능 (이번 세션 또는 다음 세션, 사용자 개입 최소)

1. **Q.7-2/3/4/5 선제 수행 — Cognitive Complexity 4건** (`slither`, `github_comment`, `formatter`, `git_diff`)
   - pipeline-reviewer 불필요
   - 총 ~2시간, 회귀 리스크 🟢 낮음
   - Agent A 의 3 Phase 중 하나의 절반

2. **S.4 pipeline test mock 재설계 (Option A)** (~1.5일)
   - test_pipeline.py 13곳 `repository_repo.find_by_full_name` + `analysis_repo.find_by_sha` 직접 patch
   - 완료 시 S.3-D 자동 해결 (`get_repo_or_404` UI/webhook 확산)
   - pipeline-reviewer 권장

### 🟡 사용자 개입 필요 (P4-Gate 통과 후 D.3 해금)

3. **P4-Gate 프로덕션 실증** (Claude 1h + 사용자 45분)
   - Claude: 샘플 C/Solidity 코드 + 검증 스크립트 제공
   - 사용자: 외부 테스트 리포 생성 + PR 제출 + 결과 확인
   - 완료 조건: 6항목 모두 ✅

4. **Q.7-1 `run_gate_check` 분할** (~1.5일, pipeline-reviewer 필수)
   - 3개 헬퍼 함수로 분리 (CC 31 → ≤15)
   - 3개 독립 옵션이라 분할 안전

### 🟢 Phase D 확장 (P4-Gate 통과 + Q.7/S.4 완료 후)

5. **Phase D.3 RuboCop** (~2h)
6. **Phase D.4 golangci-lint** (~3.5h, go.mod 자동생성 로직 포함)

### ⏸️ 보류 (수요 발생 또는 Docker 전환 후)

- **Phase D.5 PHPStan** — Semgrep 중복 + PHP 런타임 비용. 사용자 요청 시만.
- **Phase D.6~D.8** — JVM/Rust 계열. Docker 전환 별도 Phase 선행 필요.
- **P5** pytest-cov devcontainer 이미지 캐싱 — DNS 제약 환경용.

---

## 6. 권장 실행 순서 (시나리오 B 기반 세분화)

| # | 단계 | 작업 | Claude 시간 | 사용자 시간 | 차단 요소 |
|---|------|------|-----------|-----------|---------|
| 1 | S.4-1 | pipeline test mock Option A 적용 (13곳) | 1.5h | 0 | 없음 |
| 2 | S.3-D (자동) | UI/webhook 에 `repository_repo.find_by_full_name` 확산 | 30분 | 0 | S.4 |
| 3 | Q.7-2 | slither `_parse_slither_json` 분할 | 45분 | 0 | 없음 |
| 4 | Q.7-3 | github_comment `_build_comment_from_result` 분할 | 1h | 0 | 없음 |
| 5 | Q.7-4/5 | formatter/git_diff 미세 조정 | 30분 | 0 | 없음 |
| 6 | P4-Gate 준비 | 샘플 C/Solidity + 검증 스크립트 작성 | 1h | 0 | 없음 |
| 7 | P4-Gate 실증 | 외부 리포 + PR + Railway 로그 | 0.5h | 45분 | 사용자 개입 |
| 8 | Q.7-1 | `run_gate_check` 분할 (3 헬퍼) | 1.5h | 0 | pipeline-reviewer 승인 |
| 9 | D.3 RuboCop | nixpacks + tools/rubocop.py + 테스트 | 2h | 15분 (Railway) | P4-Gate ✅ |
| 10 | D.4 golangci-lint | tools/golangci_lint.py + go.mod 로직 | 3.5h | 15분 (Railway) | D.3 완료 |

**Claude 누적**: ~12시간
**사용자 누적**: 1.25시간
**차기 마일스톤**: D.4 완료 후 — SonarCloud Rating A 유지 + 8개 정적분석 도구 (pylint/flake8/bandit/semgrep/eslint/shellcheck/cppcheck/slither/rubocop/golangci-lint) 지원

---

## 7. 리스크·주의사항 (3 에이전트 합의)

| 리스크 | 완화책 | 담당 |
|--------|--------|------|
| **S.4 회귀 (S.1-4, S.3-D 2회 실패 이력)** | Option A 로 테스트만 수정 (프로덕션 코드 불변) | Agent A |
| **Q.7-1 `run_gate_check` 분할 회귀** | pipeline-reviewer 승인 + 3 헬퍼가 기존 로직 순서 보존 | Agent A |
| **P4-Gate 사용자 의존** | 샘플 코드·검증 자동화를 Claude 가 먼저 준비 | Agent C |
| **D.3/D.4 Railway 빌드 실패** | 로컬 nixpacks 시뮬레이션 우선 + 실패 시 buildCommand 즉시 원복 | Agent B |
| **D.6~D.8 Docker 전환 시기** | Phase D.5 착수 여부 판정 후 별도 Phase 로 분리 | Agent B |

---

## 8. 결론

3 에이전트 모두 **시나리오 B (균형)** 권장. 즉시 실행 가능한 낮은 리스크 항목 (S.4 → Q.7-2/3/4/5) 은 Claude 단독 수행, Q.7-1 및 D.3 이후는 pipeline-reviewer 또는 사용자 개입 구간. Docker 전환 없는 한계에서 D.6~D.8 는 별도 대형 Phase 로 분리.

**다음 단계 결정 요청**:
1. 🟢 즉시 착수: S.4 + Q.7-2/3/4/5 (낮은 리스크, 3~4시간)
2. 🟡 사용자 준비 필요: P4-Gate 실증 (외부 리포 + Railway 접근)
3. 🟢 D.3~D.4 (P4-Gate 통과 후)

---

## 9. 실행 결과 (2026-04-23 세션 — 최종 갱신)

사용자 승인 후 시나리오 B 10-step 전체 수행 완료. 커밋 순서는 계획과 일치.

| # | Step | 커밋 | 상태 |
|---|------|------|------|
| 1+2 | S.4 + S.3-D | `f678222` | ✅ |
| 3~5 | Q.7-2~5 Cognitive 4건 | `e551839` | ✅ |
| 6 | P4-Gate 재료 | `6ec93f4` | ✅ |
| 8 | Q.7-1 run_gate_check 분할 (pipeline-reviewer 승인) | `842ea1d` | ✅ |
| STATE 중간 | 그룹 22 반영 | `8880df3` | ✅ |
| 7 | P4-Gate 실증 통과 (분석 #543, xzawed/SCAManager-test-samples) | `39b0583` | ✅ |
| 9 | D.3 RuboCop 추가 | `2eb0ef0` | ✅ |
| 10 | D.4 golangci-lint 추가 | `d78b449` | ✅ |
| 최종 | STATE/CLAUDE/README 동기화 | `430b2da` | ✅ |

**최종 수치**: 1170 → **1188 passed** (+18) · pylint 10.00 · CRITICAL 0 · Quality Gate OK · Tier1 정적분석 **10종** (pylint/flake8/bandit/semgrep/eslint/shellcheck/cppcheck/slither/**rubocop**/**golangci-lint**).

**P4-Gate 실증 결과 요약**:
- cppcheck 4건 감지 (L12 buffer · L18 scanf · L23/24 uninitvar)
- slither 3건 감지 — L13 **reentrancy-eth (security)** · L8 solc-version · L13 low-level-calls
- 점수 반영 확인: 코드품질 25→15 (-10), 보안 20→13 (-7)

**잔여 작업 (별도 세션)**:
1. **Railway 2차 실증 (P4-Gate-2)** — rubocop/golangci-lint 가 배포 이미지에서 동작하는지 `.rb`·`.go` 샘플 PR 로 확인
2. ~~**AI 리뷰 파싱 실패**~~ ✅ **해소 (2026-04-23)** — `_extract_json_payload()` 분리 + preamble/uppercase/trailing text 3가지 실패 모드 해소. +4 tests. `re.IGNORECASE` + 첫 `{` ~ 마지막 `}` fallback.
3. **Phase D.5~D.8** (PHPStan/detekt/PMD/clippy) — 수요 확인 또는 Docker 전환 선행 필요
4. **P3-후속** — #8a GateAction 엔진 전환 + #8b http_client 15곳 채택 (별도 Phase)
