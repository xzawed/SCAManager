> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# P4-Gate-2 프로덕션 실증 가이드 (rubocop + golangci-lint)

> Phase D.3 (RuboCop) + D.4 (golangci-lint) 가 Railway 프로덕션 환경에서 실제 동작하는지 확인하기 위한 체크리스트.
>
> 1차 가이드: [P4-Gate 1차 (cppcheck + slither)](p4-gate-verification.md) — 이미 통과.

> ✅ **Railway 빌드 안정화 완료 (2026-04-23)** — 커밋 [`8042f12`](../../commit/8042f12) 로 prism 네이티브 확장 의존성 문제 해소. 아래 **1단계 (빌드 로그 확인)** 는 이미 통과된 상태입니다. **2단계 (바이너리 확인)** 부터 진행하면 됩니다. 배경 설명: [회고 문서](../reports/2026-04-23-railway-rubocop-prism-retrospective.md).

---

## 왜 필요한가

로컬 devcontainer 에는 rubocop/golangci-lint 바이너리가 없어 `is_enabled()=False` 경로만 단위 테스트(9+9 건)로 검증된다. Railway 빌드에서 `gem install rubocop` + `golangci-lint installer` 가 정상 설치되고 런타임에서 실제 분석이 실행되는지 프로덕션 확인이 필요하다.

**특히 주의할 점** — 직전 커밋 [6aaa268](https://github.com/xzawed/SCAManager/commit/6aaa268) 에서 **rubocop prism native ext 빌드 실패**를 `build-essential + libyaml-dev` 추가로 해결 시도했으나 재실패. 커밋 [8042f12](https://github.com/xzawed/SCAManager/commit/8042f12) 에서 **`rubocop-ast 1.36.2` 명시 핀** 으로 transitive prism 의존성 자체를 제거하여 최종 해결. 상세 경위: [회고 문서](../reports/2026-04-23-railway-rubocop-prism-retrospective.md).

---

## 사용자 역할 분담 (예상 소요 20~30분 — 빌드 성공 확인됨)

| # | 항목 | 담당 | 소요 | 선행 조건 | 상태 |
|---|------|------|------|---------|------|
| 1 | Railway 빌드 로그 확인 | 사용자 | 5분 | 없음 | ✅ **완료** (2026-04-23) |
| 2 | rubocop 바이너리 존재 확인 | 사용자 | 3분 | 빌드 성공 | 대기 |
| 3 | golangci-lint 바이너리 존재 확인 | 사용자 | 3분 | 빌드 성공 | 대기 |
| 4 | rubocop 실증 PR 제출 | 사용자 | 10분 | 2번 통과 | 대기 |
| 5 | golangci-lint 실증 PR 제출 | 사용자 | 10분 | 3번 통과 | 대기 |
| 6 | 타임아웃 + 점수 반영 확인 | 사용자 | 5분 | 4/5 완료 | 대기 |

---

## 1. Railway 빌드 로그 확인

### 접속 경로

1. **Railway 대시보드** (`https://railway.app/dashboard`) 로그인
2. SCAManager 프로젝트 → **Deployments** 탭
3. 최근(커밋 `6aaa268` 또는 이후) 배포를 클릭 → **Build Logs** 탭

### 통과 조건 (로그에 아래 문자열 전부 포함)

```
# nixpacks aptPkgs 설치
Setting up build-essential
Setting up libyaml-dev
Setting up ruby-full
Setting up golang-go

# buildCommand 실행
Successfully installed rubocop-1.57.2
golangci-lint has been installed to /usr/local/bin
```

### ❌ 실패 패턴

| 증상 | 원인 | 조치 |
|------|------|------|
| `prism.so: failed` / `mkmf can't find header` | `libyaml-dev` / `build-essential` 누락 | `nixpacks.toml::aptPkgs` 확인 — 이미 추가됨 (`6aaa268`) |
| `gem install rubocop` timeout | Railway 빌드 타임아웃 (15분) | rubocop 버전 핀 1.57.2 유지 (현재 설정) |
| `curl: (6) Could not resolve host` | Railway 빌드 네트워크 제약 | 희귀 — Railway 상태페이지 확인 |

---

## 2. rubocop 바이너리 존재 확인

### 방법 A — Railway Shell (권장)

```bash
# Railway CLI 설치 (최초 1회)
npm i -g @railway/cli
railway login

# 프로젝트 디렉토리에서 실행
railway run bash
# 컨테이너 shell 안에서:
which rubocop && rubocop --version
# 기대 출력:
# /usr/local/bundle/bin/rubocop  (또는 /root/.gem/.../rubocop)
# 1.57.2
```

### 방법 B — 임시 헬스체크 확장 (Railway CLI 불가 시)

일회성 디버그용으로만 사용 — 확인 후 원복:

```python
# src/main.py 의 /health 핸들러에 임시 추가
@app.get("/health/tools")
async def health_tools():
    import shutil
    return {
        "rubocop": shutil.which("rubocop"),
        "golangci-lint": shutil.which("golangci-lint"),
        "cppcheck": shutil.which("cppcheck"),
        "slither": shutil.which("slither"),
    }
```

push 후 `https://<railway-url>/health/tools` 호출 → 각 키가 `null` 이 아닌 경로 반환.

### ❌ `which rubocop` 이 빈 출력인 경우

- Gemfile/bundler 가 PATH 설정을 바꿨을 수 있음
- 대안 경로 확인: `find / -name "rubocop" 2>/dev/null`
- 발견된 경로를 `src/analyzer/io/tools/rubocop.py` 의 `_is_enabled()` 로직에 추가 필요 → Claude 에게 요청

---

## 3. golangci-lint 바이너리 존재 확인

```bash
# Railway Shell 또는 /health/tools 로:
which golangci-lint && golangci-lint --version
# 기대: /usr/local/bin/golangci-lint
# golangci-lint has version 1.55.2 built from ...
```

추가 확인 — Go 런타임:
```bash
which go && go version
# 기대: /usr/bin/go  (nixpacks aptPkgs 에서 golang-go 로 설치)
```

---

## 4. rubocop 실증 PR 제출

### 샘플 파일 위치

이미 준비됨: [docs/samples/p4-gate/unsafe_ruby.rb](../samples/p4-gate/unsafe_ruby.rb)

내용 요약 — 5개 의도적 결함:
- `YAML.load` (Security/YamlLoad)
- `Kernel#open` (Security/Open)
- `eval` (Security/Eval)
- 따옴표 일관성 (Style/StringLiterals)
- 미사용 지역 변수 (Lint/UselessAssignment)

### 제출 절차

1. 외부 테스트 리포(`xzawed/SCAManager-test-samples`)를 로컬에 clone
2. 새 브랜치 생성: `git checkout -b p4-gate-2-rubocop`
3. SCAManager 리포에서 샘플 복사:
   ```bash
   cp /workspaces/SCAManager/docs/samples/p4-gate/unsafe_ruby.rb \
      /path/to/SCAManager-test-samples/unsafe_ruby.rb
   ```
4. 커밋 + push:
   ```bash
   cd /path/to/SCAManager-test-samples
   git add unsafe_ruby.rb
   git commit -m "test: P4-Gate-2 rubocop 샘플 추가"
   git push -u origin p4-gate-2-rubocop
   ```
5. GitHub 웹에서 PR 생성
6. SCAManager 대시보드(`https://<railway-url>/`) 에서 PR 분석이 도착할 때까지 대기 (보통 30~60초)

### 통과 조건

분석 상세 페이지(`/repos/<owner>/SCAManager-test-samples/analyses/<id>`)의 **정적 분석 이슈** 섹션에 다음 중 최소 3건 포함:

- `[rubocop/error]` 또는 `[rubocop/warning]` 태그
- `category='security'` 이슈 최소 1건 (YamlLoad 또는 Eval 또는 Open 중)
- `category='code_quality'` 이슈 최소 1건

### DB 직접 확인 (대안)

```bash
# Railway Variables 에서 DATABASE_URL 복사 후
export DATABASE_URL="postgresql://..."
bash docs/samples/p4-gate/verify_tool_hits.sh <analysis_id> rubocop
# 출력 예시:
# analysis_id=544 tool=rubocop count=5
#   [rubocop/error] line=13 category=security — YAML.load 사용
#   [rubocop/error] line=18 category=security — Kernel#open 사용
#   ...
```

---

## 5. golangci-lint 실증 PR 제출

### 샘플 파일

이미 준비됨: [docs/samples/p4-gate/unsafe_go.go](../samples/p4-gate/unsafe_go.go)

내용 요약 — 4개 의도적 결함:
- `math/rand` 난수 (gosec G404 — security)
- `json.Unmarshal` 에러 무시 (gosec G104 / errcheck)
- `neverCalled()` 미사용 함수 (unused)
- `deadStore` 할당 후 미사용 (staticcheck SA4006)

### 제출 절차

rubocop 과 동일한 방식. 파일명만 `unsafe_go.go` 로 교체.

```bash
cp /workspaces/SCAManager/docs/samples/p4-gate/unsafe_go.go \
   /path/to/SCAManager-test-samples/unsafe_go.go
git checkout -b p4-gate-2-golangci
git add unsafe_go.go && git commit -m "test: P4-Gate-2 golangci-lint 샘플 추가"
git push -u origin p4-gate-2-golangci
# GitHub 에서 PR 생성
```

### 통과 조건

- `[golangci-lint/error]` 또는 `[golangci-lint/warning]` 태그 최소 2건
- **gosec 출신 이슈는 `category='security'`** 로 분류됐는지 확인 (rubocop.py:`_categorize` 와 동일 패턴)
- 단일 `.go` 파일인데도 "no Go files" 오류가 없는지 (go.mod 자동생성 로직 검증)

### go.mod 자동생성 확인

`_GolangciLintAnalyzer.run()` 이 tmp 디렉토리에 `go.mod` 가 없으면 최소 모듈 정의를 자동 생성한다. Railway 로그에 다음 메시지가 없어야 한다:

```
❌ 실패: "no Go files in <tmp_path>"
```

있으면 `_ensure_go_mod()` 경로 확인 필요 → Claude 에게 공유.

---

## 6. 타임아웃 + 점수 반영 확인

### 타임아웃

두 PR 모두:
- PR 이벤트 수신부터 분석 완료까지 **< 90초** (일반 기준)
- Railway 로그에 다음 경고 **부재**:
  ```
  logger.warning("rubocop timed out")
  logger.warning("golangci-lint timed out")
  ```

golangci-lint 는 첫 실행 시 모듈 다운로드가 발생할 수 있어 첫 분석에 60~90초가 걸릴 수 있음 — 두 번째 PR 은 10~30초 내 완료.

### 점수 반영

**RuboCop** (`unsafe_ruby.rb`):
- security 3건 × 감점 = `security -7 (SEC_ERROR)` × N = 최대 `security_score: 0~6/20`
- code_quality 2건 × 감점 = `-3 (CQ_ERROR) × 0 + -1 (CQ_WARNING) × 2 = -2` → `code_quality_score: 23/25`

**golangci-lint** (`unsafe_go.go`):
- security 1~2건 (G404 + G104) = `security_score: 6~13/20`
- code_quality 2건 (unused + SA4006) = `-2` → `code_quality_score: 23/25`

### 최종 예상 등급

- 샘플 1 파일만 있는 PR 이므로 AI 리뷰 점수는 보통 60~80/100
- 합산 총점이 **D (45~59)** 또는 **C (60~74)** 범위에 드는 것을 확인

---

## 게이트 통과 선언

6개 항목 모두 ✅ 확인 시 다음 파일들을 업데이트 (Claude 에게 요청):

1. `docs/STATE.md` → "**P4-Gate-2 통과 (2026-04-23)**" 항목 추가 + `잔여 작업` 표에서 P4-Gate-2 항목 체크
2. `docs/reports/2026-04-23-remaining-roadmap-3agent.md` → `잔여 작업` 목록의 1번 항목 `✅` 표시
3. `docs/guides/p4-gate-2-verification.md` 최상단에 `✅ 통과 완료` 배너 추가

---

## 실패 시 대응 플로우

```
빌드 실패?
  ├─ rubocop prism 에러 → libyaml-dev / build-essential 재확인
  ├─ gem install timeout → rubocop 버전 유지 (1.57.2)
  ├─ golangci-lint 404 → installer URL 유효성 확인 (v1.55.2 태그 존재)
  └─ nixpacks 감지 실패 → providers=["python"] + aptPkgs 구조 재확인

실행 실패?
  ├─ 이슈 0건 반환 → is_enabled() = False 의심 → /health/tools 로 경로 확인
  ├─ "no Go files" → _ensure_go_mod() 디버그 로그 추가 요청
  └─ 타임아웃 → STATIC_ANALYSIS_TIMEOUT 30 → 60 상향 (src/constants.py)

점수 반영 안 됨?
  ├─ category 잘못 분류 → rubocop.py::_is_security_cop / golangci_lint.py::_is_security_linter 확인
  └─ severity 매핑 누락 → tools/*.py 의 severity 분기 확인
```

실패 시 **Claude 에게 다음 정보를 공유**:
1. Railway 빌드 로그 (전체 또는 실패 부분)
2. PR URL + 분석 id
3. `/health/tools` 응답 또는 `which rubocop` 출력
4. DB 이슈 목록 (`verify_tool_hits.sh` 출력)

---

## 참고

- 관련 커밋: [2eb0ef0](../../commit/2eb0ef0) D.3 RuboCop · [d78b449](../../commit/d78b449) D.4 golangci-lint · [6aaa268](../../commit/6aaa268) Railway 빌드 수정
- 분석 코드: [rubocop.py](../../src/analyzer/io/tools/rubocop.py) · [golangci_lint.py](../../src/analyzer/io/tools/golangci_lint.py)
- 점수 계산: [calculator.py](../../src/scorer/calculator.py)
