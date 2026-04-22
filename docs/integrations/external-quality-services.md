# 외부 품질 검증 서비스 연동 — SonarCloud · Codecov · CodeQL

저장소 push 시 자동으로 외부 공신력 있는 서비스가 코드 품질·커버리지·보안을 분석하고 결과를 GitHub PR 과 README 배지에 반영한다.

## 개요

| 서비스 | 측정 지표 | 워크플로 | 비용 |
|--------|----------|---------|------|
| **SonarCloud** | Quality Gate · Maintainability · Security · Reliability · Coverage · Duplication | `.github/workflows/ci.yml` (SonarSource/sonarcloud-github-action) | 공개 저장소 무료 |
| **Codecov** | Line coverage · Patch coverage (PR diff) · 추세 | `.github/workflows/ci.yml` (codecov/codecov-action) | 공개 저장소 무료 |
| **CodeQL** | CWE 기반 보안 advisory (Python) | `.github/workflows/codeql.yml` | GitHub 기본 기능, 무료 |

세 서비스 모두 **push to main** 및 **모든 PR** 에서 자동 실행된다.

---

## 1. SonarCloud 초기 설정 (1회)

### 1-1. SonarCloud 프로젝트 생성

1. [sonarcloud.io](https://sonarcloud.io) 접속 → `Sign in with GitHub`
2. **Import an organization from GitHub** → `xzawed` 선택
3. **Analyze new project** → `SCAManager` 선택
4. **With GitHub Actions** 선택 (권장 — 본 저장소의 `ci.yml` 이 이미 구성됨)

### 1-2. SONAR_TOKEN GitHub Secret 등록

SonarCloud 프로젝트 생성 화면에서 표시되는 토큰을 복사한 뒤:

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. Name: `SONAR_TOKEN` / Value: (복사한 토큰)
4. **Add secret**

### 1-3. `sonar-project.properties` 검증

본 저장소에 이미 포함되어 있다. SonarCloud 가 제안한 `projectKey` / `organization` 과 파일 내용이 일치하는지 확인:

```properties
sonar.organization=xzawed
sonar.projectKey=xzawed_SCAManager
```

불일치 시 위 파일을 SonarCloud UI 에 표시된 값으로 수정.

### 1-4. 첫 분석 실행

main 에 push 또는 PR 생성 → `.github/workflows/ci.yml` 의 **SonarCloud scan** step 이 자동 실행. 결과는 SonarCloud 대시보드 + PR 코멘트 + README 배지에 반영.

---

## 2. Codecov 초기 설정 (1회)

### 2-1. Codecov 프로젝트 생성

1. [codecov.io](https://codecov.io) 접속 → `Log in with GitHub`
2. **Setup repo** → `xzawed/SCAManager` 선택
3. Codecov 대시보드에서 **Repository Upload Token** 복사

### 2-2. CODECOV_TOKEN GitHub Secret 등록

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. Name: `CODECOV_TOKEN` / Value: (복사한 토큰)
4. **Add secret**

> 공개 저장소는 토큰 없이도 작동하지만 Codecov v4 action 은 rate limit 회피를 위해 토큰을 권장.

### 2-3. `codecov.yml` 정책 확인

본 저장소에 이미 포함:

- 전체 커버리지 목표 **95%** (현재 96.2%)
- 2% 이상 하락 시 CI 실패
- PR diff 커버리지 목표 80%

필요 시 `codecov.yml` 편집 후 커밋.

---

## 3. CodeQL 활성화 확인 (설정 자동)

CodeQL 은 별도 외부 서비스 연동이 필요 없다 — GitHub 내장 기능이며 `.github/workflows/codeql.yml` 만 있으면 자동 동작.

### 3-1. GitHub Security 탭 확인

1. GitHub 저장소 → **Security** 탭
2. **Code scanning** → CodeQL 결과 표시됨
3. Advisory 가 발견되면 **Security** 탭에 CWE 번호와 함께 issue 가 등록됨

### 3-2. 주기적 스캔

`.github/workflows/codeql.yml` 은 매주 월요일 09:00 UTC 에 의존성 CVE 감지를 위한 주기 스캔을 실행 (`cron: "0 9 * * 1"`).

---

## 4. 결과 확인 방법

### 4-1. README 배지 (실시간)

```markdown
[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)]
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)]
[![codecov](https://codecov.io/gh/xzawed/SCAManager/branch/main/graph/badge.svg)]
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=xzawed_SCAManager&metric=alert_status)]
[![Maintainability Rating](.../metric=sqale_rating)]
[![Security Rating](.../metric=security_rating)]
```

배지 클릭 시 각 서비스 대시보드로 이동.

### 4-2. 각 서비스 대시보드

- SonarCloud: `https://sonarcloud.io/summary/new_code?id=xzawed_SCAManager`
- Codecov: `https://codecov.io/gh/xzawed/SCAManager`
- CodeQL: GitHub 저장소 → **Security** 탭 → **Code scanning**

### 4-3. PR 자동 코멘트

SonarCloud · Codecov 둘 다 PR 에 변경 영향 요약을 자동 코멘트로 남긴다. 병합 전 품질 저하 여부를 즉시 확인 가능.

---

## 5. Quality Gate 임계값 (SonarCloud)

SonarCloud 기본 Quality Gate:

| 조건 | 기준 | 현 프로젝트 상태 |
|------|------|----------------|
| New code coverage | ≥ 80% | ✅ 96.2% 유지 |
| New code duplicated lines | ≤ 3% | 확인 필요 |
| Maintainability Rating on new code | A | pylint 10.00 유지 가정 |
| Reliability Rating on new code | A | bandit HIGH 0 |
| Security Rating on new code | A | bandit HIGH 0 |
| Security Hotspots Reviewed | 100% | SonarCloud UI 에서 검토 필요 |

Quality Gate 실패 시 README 배지가 빨강으로 변경됨 → 즉시 조치.

---

## 6. 트러블슈팅

### Q. SonarCloud 배지가 계속 "no measures" 로 표시됨
A. 첫 분석이 완료될 때까지 ~5분 소요. main 에 push 1회 발생 여부 확인. 배지 URL 의 `projectKey` 오타도 점검.

### Q. Codecov 배지가 "unknown" 으로 표시됨
A. CODECOV_TOKEN secret 등록 여부 확인. CI 로그에서 **Upload coverage to Codecov** step 성공 여부 점검.

### Q. CodeQL 이 "No workflow runs" 로 표시됨
A. `.github/workflows/codeql.yml` 이 main 브랜치에 push 됐는지 확인. GitHub **Actions** 탭에서 CodeQL 워크플로 첫 실행 확인.

### Q. SonarCloud 가 테스트 파일까지 커버리지 계산에 포함시킴
A. `sonar-project.properties` 의 `sonar.exclusions` 와 `sonar.test.inclusions` 가 올바른지 확인. 본 저장소는 `tests/**/*.py` 를 테스트로 지정.

### Q. CI 가 `.env` 부재로 실패
A. CI 환경에는 `.env` 가 없어야 함 (`.gitignore` 로 차단). conftest.py 가 `os.environ.setdefault` 로 테스트 기본값을 주입하지만, 안전을 위해 `ci.yml` 에 env 값을 명시적으로 설정한 상태.

---

## 7. 삭제·교체 시

### SonarCloud 를 제거하려면
1. `.github/workflows/ci.yml` 의 **SonarCloud scan** step 삭제
2. `sonar-project.properties` 삭제
3. SONAR_TOKEN secret 삭제
4. README 에서 SonarCloud 3종 배지 제거

### Codecov 를 제거하려면
1. `.github/workflows/ci.yml` 의 **Upload coverage to Codecov** step 삭제
2. `codecov.yml` 삭제
3. CODECOV_TOKEN secret 삭제
4. README 에서 codecov 배지 제거

### CodeQL 을 제거하려면
1. `.github/workflows/codeql.yml` 삭제
2. README 에서 CodeQL 배지 제거

서비스 제거 시 반드시 README 배지도 함께 정리 (끊어진 배지는 signal noise).
