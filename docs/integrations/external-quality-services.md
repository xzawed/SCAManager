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

## 1. SonarCloud 초기 설정 (1회 · 약 8분)

### 1-1. GitHub 로그인

1. 브라우저에서 [sonarcloud.io](https://sonarcloud.io) 접속
2. 우상단 **Log in** → **With GitHub** 클릭
3. GitHub OAuth 팝업에서 **Authorize SonarCloud** 클릭 (권한: `read:user`, `read:org`, `repo`, `admin:repo_hook`)

### 1-2. Organization 생성·선택

SonarCloud 는 "Organization" 단위로 프로젝트를 관리하며 GitHub 계정 = 1 Organization 매핑이다.

1. 우상단 **+** 버튼 → **Create new Organization**
2. **Import an organization from GitHub** 선택
3. 조직 목록에서 **xzawed** 선택
4. **Free plan** 선택 (Public 저장소 무제한 무료)
5. Organization key 는 기본값 `xzawed` 유지 (본 저장소 `sonar-project.properties` 의 `sonar.organization=xzawed` 와 일치 필수)
6. **Create Organization**

### 1-3. 프로젝트 Import

1. Organization 대시보드 → **+ Analyze new project**
2. **SCAManager** 토글 ON → **Set Up**
3. **Project Key** 기본값 `xzawed_SCAManager` 유지 (sonar-project.properties 의 `sonar.projectKey` 와 일치 필수)
4. Display Name 은 `SCAManager` 권장
5. **Set Up**

### 1-4. 분석 방식 선택 — ⚠️ 함정 주의

프로젝트 생성 직후 두 가지 옵션이 나오는데 **반드시 "With GitHub Actions"** 를 선택한다.

| 옵션 | 선택 | 이유 |
|------|------|------|
| Automatic Analysis | ❌ 금지 | SonarCloud 자체 스캔이 CI 의 `SonarSource/sonarcloud-github-action` 과 충돌 — 커버리지 리포트 누락 발생 |
| **With GitHub Actions** | ✅ | 본 저장소 `ci.yml` 과 호환 |

만약 Automatic Analysis 가 켜진 상태라면: Project → **Administration** → **Analysis Method** → **Automatic Analysis OFF**.

### 1-5. SONAR_TOKEN 발급

1. "With GitHub Actions" 선택 화면에서 **Generate a token** 클릭
2. Token name 예: `scamanager-ci`
3. **Generate** → 표시된 토큰을 **즉시 메모장에 복사** (화면 떠나면 재표시 불가)
   - 형식: `sqp_abcdef1234...` (40~48자)

> 놓쳤다면 우상단 프로필 → **My Account** → **Security** → **Generate Tokens** 재발급

### 1-6. SONAR_TOKEN GitHub Secret 등록

1. [GitHub 저장소 Secrets 페이지](https://github.com/xzawed/SCAManager/settings/secrets/actions) 접속
2. **New repository secret**
3. Name: `SONAR_TOKEN` (정확히 이 문자열 — 오타 시 작동 안 함)
4. Secret: 방금 복사한 토큰
5. **Add secret**

### 1-7. SonarCloud 의 나머지 YAML 스니펫 안내는 무시

SonarCloud 가 "워크플로 파일을 추가하세요" 라며 코드 블록을 보여주는데, `.github/workflows/ci.yml` 에 이미 포함되어 있으므로 Skip.

---

## 2. Codecov 초기 설정 (1회 · 약 3분)

### 2-1. GitHub 로그인

1. [codecov.io](https://codecov.io) 접속
2. 우상단 **Log in** → **Log in with GitHub**
3. OAuth 권한 승인

### 2-2. 저장소 Import

1. 좌상단 조직 드롭다운에서 **xzawed** 선택
2. 저장소 목록에서 **SCAManager** 찾기
   - 안 보이면 상단 **Not yet setup** 탭 클릭
   - 그래도 안 보이면 우상단 **Sync** 버튼 클릭 (GitHub 재동기화)
3. **Setup repo** 또는 **Configure** 클릭

### 2-3. Upload Token 복사

1. Setup 화면 중앙에 **Repository Upload Token** 표시
   - 형식: UUID `abcd1234-...-...`
2. **Copy** 버튼 → 메모장에 복사

### 2-4. CODECOV_TOKEN GitHub Secret 등록

1. [GitHub 저장소 Secrets 페이지](https://github.com/xzawed/SCAManager/settings/secrets/actions)
2. **New repository secret**
3. Name: `CODECOV_TOKEN` (정확히 이 문자열)
4. Secret: 방금 복사한 토큰
5. **Add secret**

> 공개 저장소는 토큰 없이도 작동하지만 Codecov v4 action 은 rate limit 회피를 위해 토큰을 권장.

### 2-5. Codecov 안내 YAML 스니펫은 무시

`.github/workflows/ci.yml` 에 이미 `codecov/codecov-action@v4` 가 포함되어 있다.

### 2-6. `codecov.yml` 정책 확인

본 저장소에 이미 포함:

- 전체 커버리지 목표 **95%** (현재 96.2%)
- 2% 이상 하락 시 CI 실패
- PR diff 커버리지 목표 80%

필요 시 `codecov.yml` 편집 후 커밋.

---

## 2-7. 토큰 등록 후 CI 재실행 (방법 3가지 — 택 1)

토큰 등록만으로는 아직 분석이 돌지 않는다. CI 를 재트리거해야 한다.

### 방법 A — 워크플로 수동 재실행 (1초)
1. [Actions 페이지](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
2. 가장 최근 실행 클릭
3. 우상단 **Re-run all jobs**

### 방법 B — 빈 커밋 push
```bash
git commit --allow-empty -m "ci: trigger external services after secret registration"
git push origin main
```

### 방법 C — 더미 변경 + push
README 에 공백 1 줄 추가 후 커밋·푸시.

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

## 6. 트러블슈팅 FAQ

### Q1. Secret 이름을 `SONARQUBE_TOKEN` 으로 등록했어요
A. `SONAR_TOKEN` 이어야 한다 (정확히). 삭제 후 재생성.

### Q2. SonarCloud "You have no permission to access this project"
A. Organization 생성 시 GitHub 조직이 제대로 연결되지 않음. Organization → **Administration** → **Members** 에서 본인이 admin 인지 확인.

### Q3. SonarCloud 배지가 계속 "no measures"
A. 세 가지 원인:
- 첫 분석 완료까지 5~10분 대기
- `sonar-project.properties` 의 `projectKey` 와 SonarCloud UI 의 값 불일치
- CI 로그에서 `SonarCloud scan` step 성공 여부 확인 (실패 시 SONAR_TOKEN 이름 재확인)

### Q4. Codecov 배지에 "unknown" 그대로
A. 원인 3가지:
- CI 에서 `coverage.xml` 생성 실패 (Actions 로그 확인)
- `CODECOV_TOKEN` secret 미등록/오타
- Public 저장소라 token 없이 시도했지만 rate limit 걸림 → token 등록으로 해결

### Q5. CodeQL 이 "No workflow runs"
A. `.github/workflows/codeql.yml` 이 main 에 있는 상태에서 최소 1회 push 필요. Actions 탭에서 CodeQL 워크플로 성공 확인. Security 탭 접근 권한도 확인.

### Q6. SonarCloud Quality Gate 가 FAILED
A. 대시보드에서 원인 확인. 가장 흔한 원인:
- New code coverage < 80% → 추가된 코드에 테스트 부족
- Security Hotspots 미검토 → UI 에서 "Review" 버튼으로 수동 승인
- Duplicated lines > 3%

Quality Gate 는 **new code (신규/변경 코드)** 에만 적용되므로 기존 코드는 무시된다.

### Q7. SonarCloud 가 테스트 파일까지 커버리지 계산
A. `sonar-project.properties` 의 `sonar.exclusions` 와 `sonar.test.inclusions` 확인. 본 저장소는 `tests/**/*.py` 를 테스트로 지정.

### Q8. CI 가 `.env` 부재로 실패
A. CI 환경에는 `.env` 가 없어야 함. conftest.py 의 `os.environ.setdefault` 가 테스트 기본값 주입 + `ci.yml` 에 env 값 명시.

### Q9. Token 이 노출됐어요
A. 즉시 폐기:
- SonarCloud: My Account → Security → **Revoke** → 새 토큰 → GitHub Secret 교체
- Codecov: Settings → 저장소 → **Regenerate** → GitHub Secret 교체

### Q10. Private 저장소로 전환하면?
A. 세 서비스 모두 유료 전환:
- SonarCloud: $10/월~
- Codecov: $10/월~
- CodeQL: GitHub Advanced Security ($21/활성 사용자/월)

---

## 7. 결과 확인 체크리스트

토큰 등록 + CI 재실행 후 5~10분 내에 아래가 모두 성공해야 한다.

- [ ] [Actions CI 워크플로](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml) 초록색 체크 표시
- [ ] CI 로그의 **Upload coverage to Codecov** step: `Uploading reports` 메시지
- [ ] CI 로그의 **SonarCloud scan** step: `ANALYSIS SUCCESSFUL` 메시지
- [ ] [SonarCloud 대시보드](https://sonarcloud.io/summary/new_code?id=xzawed_SCAManager) 에 Quality Gate/Coverage/Rating 표시
- [ ] [Codecov 대시보드](https://codecov.io/gh/xzawed/SCAManager) 에 커버리지 % 표시
- [ ] GitHub 저장소 **Security** 탭 → Code scanning → CodeQL 결과 (첫 실행 후 advisory 있을 수도/없을 수도)
- [ ] README 배지 6종이 "unknown" 이 아닌 실제 값으로 표시

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
