# 사용자 수행 필요 잔여 작업 종합 가이드

> 2026-04-23 기준 Claude 단독으로 진행할 수 없어 **사용자 개입이 필요한** 4가지 잔여 작업을 정리한 문서. 각 작업의 배경 · 필요성 · 수행 방법 · 성공 기준 · 예상 소요 시간을 포함한다.
>
> 최신 로드맵: [docs/reports/2026-04-23-remaining-roadmap-3agent.md](../reports/2026-04-23-remaining-roadmap-3agent.md)
> 현재 상태: [docs/STATE.md](../STATE.md)

---

## 전체 요약 (한눈에)

| # | 작업 | 종류 | 우선순위 | 사용자 소요 | 선행 조건 |
|---|------|------|---------|-----------|---------|
| 1 | [P4-Gate-2 Railway 실증](#1-p4-gate-2-railway-실증) | 🟢 실행 | **최우선** | 20~30분 | ✅ Railway 빌드 성공 (2026-04-23 확인) |
| 2 | [Phase D.5~D.8 도구 확장 결정](#2-phase-d5d8-정적분석-도구-확장-결정) | 🟡 의사결정 | 선택 | 10분 | — |
| 3 | [P3-후속 스캐폴딩 완성](#3-p3-후속-스캐폴딩-완성-엔진-전환) | 🟡 의사결정 | 선택 | 10분 | — |
| 4 | [P5 pytest-cov devcontainer 캐싱](#4-p5-pytest-cov-devcontainer-캐싱) | 🟢 실행 | 낮음 | 15분 | Docker rebuild 가능 환경 |

**권장 진행 순서**: `1번 먼저 완료` → `2·3번 중 관심 있는 항목 결정` → (필요 시) `4번`

---

## 1. P4-Gate-2 Railway 실증

### 이게 뭔가요?

Phase D.3 (RuboCop — Ruby 정적분석) + D.4 (golangci-lint — Go 정적분석) 을 Railway 프로덕션 환경에서 **실제로 동작하는지** 검증하는 작업입니다. 로컬 devcontainer 에는 rubocop/golangci-lint 바이너리가 없어서 단위 테스트(각 9건)는 mock 으로만 검증되었습니다. 실제 배포 환경에서 `.rb`/`.go` 파일이 분석되는지 눈으로 확인이 필요합니다.

### 왜 지금 필요한가요?

1. ~~**직전 Railway 빌드 실패 이력**~~ ✅ **2026-04-23 해결** — 커밋 [8042f12](../../commit/8042f12) `rubocop-ast 1.36.2` 명시 핀으로 prism 네이티브 확장 의존성 제거. 배포 성공 확인. 상세: [회고 문서](../reports/2026-04-23-railway-rubocop-prism-retrospective.md).
2. **D.5 이후 단계 차단**: 1차 P4-Gate 는 2026-04-23 에 통과(분석 #543)했지만, rubocop/golangci-lint 는 미실증 상태입니다. D.5 (PHPStan) 착수 전 이 2차 게이트 통과가 필요합니다.
3. **사용자가 이미 준비된 재료 사용 가능**: Ruby/Go 샘플 코드와 검증 스크립트가 모두 레포에 포함되어 있습니다.
4. **빌드가 안정되어 바로 진행 가능**: 이전에는 "빌드 성공 여부 확인" 이 1단계였지만, 이제 **바이너리 동작 확인부터 시작** 할 수 있습니다.

### 구체적으로 뭘 하나요?

**상세 절차는 별도 문서로 분리되어 있습니다**:
→ **[docs/guides/p4-gate-2-verification.md](p4-gate-2-verification.md)** 에서 6단계 체크리스트 확인

**간략 요약** (빌드 성공 확인됨 — 2~6단계로 바로 진행):
1. ~~Railway 대시보드에서 최근 빌드 로그 확인~~ ✅ **완료** (커밋 `8042f12` 로 빌드 성공)
2. `railway run bash` 로 컨테이너 접속 → `which rubocop`, `which golangci-lint` 확인 (5분)
3. 외부 리포(`xzawed/SCAManager-test-samples`)에 `unsafe_ruby.rb` PR 제출 (10분)
4. 동일 리포에 `unsafe_go.go` PR 제출 (10분)
5. 두 PR 의 분석 결과를 SCAManager 대시보드에서 확인 (5분)
6. 이슈가 각각 3건 이상 감지 + 점수 감점 반영 확인 (5분)

### 성공 기준

- ✅ Railway 빌드 로그에 `Successfully installed rubocop-1.57.2` + `golangci-lint has been installed` 포함
- ✅ `which rubocop && which golangci-lint` 가 유효한 경로 반환
- ✅ `unsafe_ruby.rb` PR 분석 결과에 `[rubocop/...]` 이슈 3건 이상 (security 1건 이상)
- ✅ `unsafe_go.go` PR 분석 결과에 `[golangci-lint/...]` 이슈 2건 이상 (security 1건 이상)

### 실패하면 어떻게 하나요?

[P4-Gate-2 가이드 § 실패 시 대응 플로우](p4-gate-2-verification.md#실패-시-대응-플로우) 참조.

**공통 원칙**: 실패 시 다음 정보를 Claude 에게 공유하세요:
1. Railway 빌드 로그 (실패 부분 전체)
2. PR URL + 분석 id
3. `which rubocop` / `which golangci-lint` 출력
4. DB 이슈 목록 (verify_tool_hits.sh 출력)

### 예상 소요

- 순조로운 경우: **30분**
- 빌드 실패 1회 + 재시도: **60~90분**

---

## 2. Phase D.5~D.8 정적분석 도구 확장 결정

### 이게 뭔가요?

Tier 1 정적분석 도구를 추가로 4개 더 지원할지 여부를 결정하는 **의사결정** 작업입니다. 지금까지 10종(pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·rubocop·golangci-lint)이 있고, 다음 후보는:

| Phase | 도구 | 언어 | 이미지 증가 | 리스크 | 비고 |
|-------|------|------|------------|-------|------|
| D.5 | PHPStan | PHP | +150MB | 🟠 중간 | Semgrep 과 기능 중복 · PHP 런타임 신규 |
| D.6 | detekt | Kotlin | +350MB | 🟠 높음 | JDK 설치 필요 → Docker 전환 선행 |
| D.7 | PMD | Java | +300MB | 🔴 높음 | JVM cold start 10~15초 → 타임아웃 우려 |
| D.8 | cargo clippy | Rust | +700MB | 🔴 최상위 | crate 단위 분석 → 단일 파일 분석 아키텍처 변경 |

### 왜 지금 결정이 필요한가요?

- **D.5 (PHPStan)**: nixpacks 유지한 채 추가 가능하지만, SCAManager 가 처리하는 PR 중 PHP 비중이 낮으면 ROI 낮음. **사용자의 실제 사용 수요** 에 따라 결정이 바뀝니다.
- **D.6~D.8**: Railway NIXPACKS 환경에서는 이미지 크기 2GB+ 초과 + JVM 콜드 스타트로 현실적으로 불가. **Docker 전환 Phase 를 먼저 수행** 해야 함. Docker 전환 자체가 대규모 작업이므로 명시적 의사결정이 필요합니다.

### 구체적으로 뭘 결정하나요?

아래 4가지 질문에 답하거나, Claude 에게 원하는 방향을 알려주세요:

**Q1. PHP 코드 리뷰 요청이 얼마나 있나요?**
- (A) 없음 / 거의 없음 → D.5 **보류** (Semgrep 으로 충분)
- (B) 월 1건 이상 → D.5 착수 고려
- (C) 확실하지 않음 → 일단 **보류**

**Q2. Kotlin/Java/Rust 코드 리뷰 수요는?**
- (A) 없음 → D.6~D.8 **영구 보류**
- (B) 있음 + Docker 전환 허용 → D.6~D.8 착수 검토
- (C) 있음 + Docker 전환 부담 → 보류 (Semgrep 으로 부분 커버)

**Q3. Docker 전환에 관심이 있나요?**
- Docker 전환의 비용: Railway 빌드 시간 2배 증가, 이미지 관리 복잡도, Dockerfile 작성 + 디버깅 초기 작업 8~16시간
- Docker 전환의 이점: 모든 JVM/Rust 도구 실행 가능, 배포 일관성 향상, 로컬 재현성 향상

**Q4. 현재 10종으로 충분한가요?**
- (A) 충분 → Phase D 종료 선언, 다른 우선순위로 이동
- (B) 부족하지만 사용자 요청이 있을 때만 추가 → 모든 D.5~D.8 보류
- (C) 적극 확장 → Docker 전환 + D.6~D.8 순차 진행

### 결정 후 Claude 에게 할 말

결정이 내려지면 다음 형식으로 알려주시면 됩니다:

> "D.5 (PHPStan) 만 착수해주세요" → Claude 가 TDD 로 D.3/D.4 패턴 재사용해 바로 진행
>
> "D.6~D.8 를 위한 Docker 전환 Phase 를 먼저 설계해주세요" → Claude 가 Docker 전환 계획서 작성 후 승인 대기
>
> "Phase D 는 여기서 종료합니다" → Claude 가 STATE.md 에 "Phase D 종료" 섹션 추가 + 다음 우선순위 제안

### 예상 소요

- 결정만: **10분** (이 문서 읽고 사용자 판단)
- 결정 후 실행 (Claude 작업): D.5 = 2.5h, Docker 전환 = 8~16h, D.6~D.8 각 4~5h

---

## 3. P3-후속 스캐폴딩 완성 (엔진 전환)

### 이게 뭔가요?

2026-04-22 품질 감사에서 식별된 **리팩토링 기반 작업 2건** 을 완결하는 작업입니다. 현재 "스캐폴딩만 존재" 상태 — 실제 엔진 전환은 미완료.

#### #8a: GateAction 엔진 전환
- **현재 상태**: `src/gate/registry.py` 가 2026-04-19 에 한 번 만들어졌다가 [S.1-2](../reports/2026-04-23-structure-audit-3agent.md) 에서 죽은 코드로 삭제됨
- **재추진 방향**: 3-옵션 Gate (`pr_review_comment`/`approve_mode`/`auto_merge`) 를 `src/gate/engine.py` 의 `if/elif` 분기가 아니라 **Action 클래스 + Registry** 패턴으로 전환
- **이점**: 새 Gate 옵션 추가 시 코드 수정 지점이 1곳으로 줄어듦 (현재 3곳)

#### #8b: http_client 싱글톤 15곳 채택
- **현재 상태**: `src/shared/http_client.py` 에 lifespan 기반 `httpx.AsyncClient` 싱글톤이 있지만, 15곳이 아직 `async with httpx.AsyncClient()` 를 직접 생성
- **재추진 방향**: 15곳을 싱글톤 의존성 주입으로 치환
- **이점**: TCP 커넥션 재사용 → 알림 발송 지연 감소 + 테스트 격리 단순화

### 왜 지금 결정이 필요한가요?

두 작업 모두 **기능 추가가 아닌 순수 리팩토링** 입니다. 비즈니스 임팩트가 즉시 없어서 "지금 해야 하나?" 판단이 사용자 몫입니다.

- ✅ **장점**: 코드베이스 일관성 ↑, 향후 유지보수 비용 ↓, SonarCloud Maintainability 추가 개선 가능
- ❌ **단점**: 엔진 전환은 `test_gate_engine.py` 37건 mock 재작성 필요 → 회귀 리스크 있음, 1~2일 소요

### 구체적으로 뭘 결정하나요?

**Q1. 단기 기능 개발이 급한가요?**
- (A) Phase D 또는 새 기능 우선 → P3-후속 **보류**
- (B) 지금 리팩토링 여유가 있음 → 어느 걸 먼저?

**Q2. 먼저 착수한다면 어느 쪽?**
- **#8a (GateAction 엔진 전환)** — 복잡도 높음, 회귀 리스크 중간, 설계 이점 큼
- **#8b (http_client 15곳 치환)** — 복잡도 낮음, 회귀 리스크 낮음, 즉각 효과 작음
- **둘 다** — 2일 이상 소요, pipeline-reviewer 에이전트 승인 2회 필요

### 결정 후 Claude 에게 할 말

> "#8b http_client 먼저 진행해주세요" → Claude 가 15곳 파일 매핑 조사 후 TDD 로 진행
>
> "#8a GateAction 엔진 전환을 설계해주세요" → Claude 가 설계 문서 작성 + pipeline-reviewer 에이전트 리뷰 요청
>
> "P3-후속 은 당분간 보류합니다" → Claude 가 STATE.md 에 "보류 항목" 섹션 명시

### 예상 소요

- 결정만: **10분**
- 결정 후 실행:
  - #8b http_client: 3~4시간 (낮은 리스크)
  - #8a GateAction: 1.5일 + pipeline-reviewer 리뷰 1회

---

## 4. P5 pytest-cov devcontainer 캐싱

### 이게 뭔가요?

로컬 devcontainer 환경에서 `pytest-cov` (커버리지 측정 도구) 가 DNS 제약으로 설치되지 않는 문제를 해결하는 작업입니다. 현재 [품질 감사 R2](../reports/2026-04-21-quality-audit-round5.md) 에서 절차적 페널티 -5점을 받은 항목.

### 왜 지금 필요한가요?

- 현재 [STATE.md](../STATE.md) 의 커버리지 `96.2%` 수치는 로컬/CI 에서 측정한 과거 스냅샷이 반영된 것입니다
- DNS 제약이 있는 devcontainer 환경에서는 `pip install pytest-cov` 실패 → 커버리지 재측정 불가
- 장기적으로 이 환경에서도 커버리지 재현이 되어야 규격 유지가 쉬움

### 구체적으로 뭘 하나요?

**방법 A — devcontainer.json 수정 (권장)**:

1. `.devcontainer/devcontainer.json` (또는 `postCreateCommand`) 에 pytest-cov wheel 사전 다운로드 추가
2. devcontainer 이미지 rebuild: VS Code 에서 `Dev Containers: Rebuild Container` 실행
3. 재빌드 후 `python -m pytest --cov=src` 정상 실행 확인

**방법 B — 로컬 wheel 캐싱**:

1. 네트워크 가능한 환경에서 `pip download pytest-cov coverage -d /wheels` 실행
2. `/wheels` 디렉토리를 devcontainer 이미지에 포함
3. devcontainer 내부에서 `pip install --no-index --find-links=/wheels pytest-cov`

**현재 장애 요소** — Claude 단독 수행 불가 이유:
- `.devcontainer/devcontainer.json` 수정 자체는 가능하지만, **Docker 이미지 rebuild 권한** 이 사용자에게 있음
- Rebuild 후 검증은 새 환경에서 재실행 필요 → 세션 연속성 끊김

### 성공 기준

- ✅ devcontainer rebuild 후 `python -c "import pytest_cov"` 성공
- ✅ `make test-cov` 가 에러 없이 실행
- ✅ 로컬 커버리지 측정 결과가 STATE.md 의 96.2% 와 ±1% 이내 일치

### 결정 후 Claude 에게 할 말

> "방법 A 로 진행해주세요" → Claude 가 devcontainer.json 수정 PR 작성 → 사용자가 rebuild → 결과 공유
>
> "당분간 CI 의 커버리지 측정에 의존합니다" → P5 **영구 보류**, STATE.md 에서 항목 제거

### 예상 소요

- Claude 작업 (devcontainer.json 수정): 30분
- 사용자 작업 (rebuild + 검증): 10~15분
- 전체: **~1시간** (첫 시도 성공 기준)

---

## 어떻게 시작하나요?

### 가장 간단한 시작: P4-Gate-2 만

1. **지금 당장 수행** — Railway 대시보드에 로그인해 빌드 로그 확인 (5분)
2. 빌드 성공이면 [P4-Gate-2 가이드](p4-gate-2-verification.md) 6단계 진행
3. 빌드 실패면 로그 공유 → Claude 에게 수정 요청

### 시간 여유가 있을 때

1. [2번 Phase D.5~D.8 결정](#2-phase-d5d8-정적분석-도구-확장-결정) 읽고 사용자 의견 결정
2. [3번 P3-후속](#3-p3-후속-스캐폴딩-완성-엔진-전환) 읽고 관심 있는 항목 선택
3. Claude 에게 결정 사항 전달 → 해당 작업 진행

### 모두 보류하고 새 기능을 만들고 싶다면

- Claude 에게 "잔여 작업 전부 당분간 보류. 새 기능 X 를 만들고 싶어요" 라고 알려주세요
- STATE.md 의 잔여 작업 섹션에 "보류 중" 배너만 추가하고 다른 작업 시작 가능

---

## 참고 문서

- [docs/STATE.md](../STATE.md) — 현재 프로젝트 상태 (단일 진실 소스)
- [docs/reports/2026-04-23-remaining-roadmap-3agent.md](../reports/2026-04-23-remaining-roadmap-3agent.md) — 3-에이전트 합의 로드맵
- [docs/guides/p4-gate-verification.md](p4-gate-verification.md) — P4-Gate 1차 (cppcheck + slither, **통과 완료**)
- [docs/guides/p4-gate-2-verification.md](p4-gate-2-verification.md) — P4-Gate 2차 (rubocop + golangci-lint, **진행 필요**)
- [docs/reports/2026-04-22-quality-audit-6lens.md](../reports/2026-04-22-quality-audit-6lens.md) — 6렌즈 품질 감사 (P3-후속 원류)
- [docs/reports/2026-04-21-quality-audit-round5.md](../reports/2026-04-21-quality-audit-round5.md) — 5라운드 감사 (P5 원류)

---

**이 문서는 잔여 작업 상태가 바뀔 때마다 갱신됩니다.** 새 작업이 추가되거나 기존 작업이 완료되면 Claude 에게 "user-actions-remaining.md 갱신해주세요" 라고 알려주세요.
