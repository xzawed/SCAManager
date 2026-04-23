# Phase E 전환 결정 — Path A (서비스화) 로드맵 (2026-04-23)

> ✅ **2026-04-23 전체 완결** — E.1~E.5 5단계 모두 동일 일자에 완료. 총 +40 테스트, pylint 10.00 / flake8 0 유지. 상세: [STATE.md 그룹 25~28](../STATE.md#그룹-28--phase-e5-onboarding-튜토리얼-2026-04-23).

> SCAManager 방향 분기점에서 **Path A (서비스화)** 를 공식 선택. Phase D (Tier1 정적분석 도구 확장) 를 잠정 종료하고 Phase E (서비스 성숙화) 로 전환.

## 배경

2026-04-23 세션에서 Claude 가 실무자 관점의 프로젝트 진단을 공유 — 기능 breadth 의 한계 효용 감소, observability 공백, AI 점수 칼리브레이션 부재, onboarding friction 등의 우려. 사용자는 진단을 승인하고 **Path A (서비스화)** 방향을 공식 선택.

## 방향 결정

| 항목 | 이전 (Phase D 확장) | 이후 (Phase E 서비스화) |
|------|--------------------|------------------------|
| 초점 | 지원 언어 breadth 확장 | 운영 성숙도 + 신뢰도 + onboarding |
| 새 기능 | Tier1 도구 10 → 14 (PHPStan/detekt/PMD/clippy) | 관측·피드백·간소화 |
| 신규 사용자 | 자력 설정 (6채널 + 토큰 다수) | Minimal mode + 단계별 튜토리얼 |
| Gate 신뢰 기반 | 구현 완료, 검증 없음 | thumbs up/down 수집 → 정합도 지표 |
| 성공 지표 | 테스트·lint 수치 | + SaaS 건전성 지표 (에러율·지연·비용) |

## Phase D.5~D.8 공식 중단

### 보류 사유 (도구별)

| Phase | 도구 | 언어 | 중단 사유 |
|-------|------|------|----------|
| D.5 | PHPStan | PHP | Semgrep 이 이미 PHP 보안 규칙 커버. PHP 런타임 +150MB 추가 비용 대비 PR 수요 미확인 |
| D.6 | detekt | Kotlin | JDK 필수 → Docker 전환 선행 필요. 현재 Kotlin PR 수요 없음 |
| D.7 | PMD | Java | JVM cold start 10~15초 vs. `STATIC_ANALYSIS_TIMEOUT=30` → 타임아웃 위험. Docker 전환 선행 필수 |
| D.8 | cargo clippy | Rust | crate 단위 분석으로 현재 단일 파일 분석 아키텍처와 불일치 → 구조 변경 필요 |

### 재개 기준 (명시적)

아래 **모든** 조건을 충족할 때만 해당 Phase 재개 검토:

1. 해당 언어의 PR 이 **월 5건 이상** SCAManager 에 수신됨 (로그로 측정)
2. Phase E.2 (Observability) 완료 — 언어별 수신량 측정 가능해진 상태
3. Docker 전환 (D.6~D.8 의 경우) 또는 아키텍처 변경 (D.8) 에 대한 별도 의사결정 완료

조건 미충족 시 **재개 검토하지 않음**. STATE.md 잔여 과제 표에서도 제거.

### 유지되는 것

- Phase D.1 (cppcheck), D.2 (slither), D.3 (rubocop), D.4 (golangci-lint) — 이미 완료, 유지
- nixpacks 의 ruby/go 런타임, build-essential, libyaml-dev — 향후 다른 gem/go 도구 추가 시 대비로 유지
- 관련 코드 (`src/analyzer/io/tools/`) — 변경 없음

## Phase E 로드맵

### E.1 — Phase D 공식 중단 ✅ **완료** (커밋 `bc6f32b`)

### E.2 — Observability 기반 구축 ✅ **완료** (커밋 `91abcba` · `ad951d0` · `b5ea179`)

**목적**: 운영 가시성 확보. Phase E 나머지의 효과 측정 전제 조건.

**핵심 작업**:
- Sentry SDK 통합 (`sentry-sdk[fastapi]`) — 예외 자동 수집
- Structured logging 도입 (loguru 또는 structlog) — 기존 logger 병존 또는 교체
- Claude API 호출 계측 — latency, token usage, cost estimation
- 언어별·도구별 메트릭 — 어느 언어·어느 도구가 얼마나 호출되는지
- Gate 결정 메트릭 — auto-approve / auto-merge / reject 분포

**환경변수**: `SENTRY_DSN` (optional), `LOG_FORMAT=json|text`

**성공 기준**: production 에서 에러 발생 시 Sentry 이벤트 확인 가능 + 분석당 Claude API cost 집계 확인 가능.

### E.3 — AI 점수 피드백 루프 ✅ **완료** (커밋 `f20f331` · `c70f2fa`)

**목적**: auto-merge 의 신뢰 기반 구축. Claude 점수가 사람 판단과 일치하는지 측정.

**핵심 작업**:
- 분석 상세 페이지에 thumbs up/down 버튼 추가
- `AnalysisFeedback` ORM 신설 (analysis_id, user_id, thumbs, comment, created_at)
- 대시보드에 정합도 지표 — Claude 점수 분포 vs. thumbs up 비율
- 점수별 thumbs up 비율이 낮은 구간 식별 → 프롬프트 개선 재료

### E.4 — Minimal Mode (사용자 onboarding 간소화) ✅ **완료** (커밋 `a32a040`)

**목적**: 신규 사용자의 첫 repo 등록까지 friction 최소화.

**핵심 작업**:
- Settings UI 에 Simple / Advanced 토글 (기본값 Simple)
- Simple 모드: Python 정적분석 + Telegram 알림 + PR 코멘트만 노출
- Advanced 모드: 기존 6채널 + 10언어 + Gate 3옵션 전부 노출
- Simple → Advanced 전환 시 기존 설정 보존

### E.5 — Onboarding 튜토리얼 ✅ **완료** (커밋 `f502bb9`)

**목적**: 첫 repo 등록까지의 경로 최적화.

**핵심 작업**:
- "/" 페이지에 "Get Started in 3 steps" 가이드
- GitHub OAuth → repo 선택 → 기본값으로 즉시 완료 (Telegram/기타는 선택)
- `.env.example` 파일을 OAuth 시 자동 생성 (옵션)
- 각 설정 필드에 단계별 설명 툴팁

## 타임라인 (목표)

| Phase | 시작 | 완료 목표 | 비고 |
|-------|------|---------|------|
| E.1 | 2026-04-23 | 2026-04-23 | 본 문서 + STATE.md 정리 |
| E.2 | E.1 직후 | 2026-04-25 | Sentry 무료 플랜으로 시작 |
| E.3 | E.2 완료 후 | 2026-04-27 | 3개월 데이터 수집 후 진짜 지표 나옴 |
| E.4 | E.3 시작 병행 | 2026-04-29 | UI 작업 |
| E.5 | E.4 직후 | 2026-04-30 | 튜토리얼 + 문서 |

## 승인

- 방향 결정: 2026-04-23 사용자 승인
- 기획 검토: 본 문서로 갈음
- 실행 권한: 사용자 일괄 승인 (같은 세션)

## 관련 문서

- [사용자 수행 필요 잔여 작업](../guides/user-actions-remaining.md) — E.4/E.5 완료 후 재검토
- [STATE.md](../STATE.md) — 잔여 과제 섹션 정리 대상
- [3-에이전트 로드맵](./2026-04-23-remaining-roadmap-3agent.md) — Phase D 시점 계획 (역사 문서로 보존)
