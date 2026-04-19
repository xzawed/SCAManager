# 운영 검증 가이드 — 분석 도구 배포 후 확인 절차

> Phase B(Semgrep), Phase C(ESLint/ShellCheck) 배포 이후 도구가 정상 동작하는지
> 검증하는 표준 절차. Phase D 도구 추가 시 동일 패턴으로 확장.

## 1. 도구 설치 확인

Railway 컨테이너에서 확인 (Deploy Logs → `railway run bash` 또는 서버 시작 시 로그):

```bash
semgrep --version      # 1.x.x 이상
eslint --version       # 9.x.x
shellcheck --version   # 0.9.x
```

**nixpacks 빌드 로그에서 확인**:
```
✓ npm install -g eslint@9 ...  ← exit code 0
✓ pip install -r requirements.txt  ← semgrep 포함
✓ apt-get install -y shellcheck
```

도구가 없으면 `is_enabled()=False` → 분석 결과에서 해당 도구 이슈가 0건으로 표시됨 (오류 없음).

---

## 2. 런타임 동작 검증

### 2.1 분석 로그 확인

Railway 앱 로그에서 아래 패턴이 **없어야 함**:
```
eslint failed for /tmp/...
semgrep timed out for /tmp/...
shellcheck failed for /tmp/...
```

`is_enabled=False` 건은 로그 없음 — 정상.

### 2.2 언어별 샘플 PR 체크리스트

각 도구를 활성화했다면 아래 샘플 PR로 실제 이슈 감지 여부 확인.

**ESLint (JavaScript)**:
```javascript
// test.js
var x = 1           // no-var warning
eval("alert(1)")    // no-eval error
```
→ `GET /repos/{repo}/analyses/{id}` 또는 대시보드 분석 상세 확인
→ `issues` 배열에 `"tool": "eslint"` 항목 존재 여부

**ShellCheck (Shell)**:
```bash
#!/bin/bash
for f in $(ls)   # SC2045: 공백 포함 파일명 처리 안전하지 않음
do echo $f       # SC2086: 따옴표 없는 변수
done
```
→ `"tool": "shellcheck"`, `"message"` 에 `SC2045`/`SC2086` 포함 여부

**Semgrep (Go, Java 등)**:
```go
// test.go
package main
import "fmt"
func main() {
    fmt.Println("hello")
    _ = map[string]interface{}{}  // Semgrep이 패턴 감지 가능
}
```
→ Semgrep auto rule 적중 여부는 룰셋에 따라 달라질 수 있음 → 이슈 0건도 정상

### 2.3 점수 회귀 검증

Python 파일만 포함된 기존 PR을 재분석 시 점수가 Phase A 이전과 동일해야 함.

**검증 방법**:
```bash
# analysis_detail 페이지에서 동일 commit SHA 분석 2건 비교
# 또는 API로 score 확인
curl /api/analyses/{id} | jq '.score'
```

**예상**: `category` 기반 집계 전환 후에도 Python-only PR 점수 불변 (CQ_WARNING_CAP=25 동치 보장).

---

## 3. 도구 미설치 환경 확인 (로컬 개발)

로컬에 eslint/shellcheck가 없을 때 테스트는 **mock으로 대체**:

```python
# tests/test_eslint_analyzer.py 패턴 참조
with patch("shutil.which", return_value=None):
    assert not analyzer.is_enabled(ctx)
```

실제 바이너리 없어도 단위 테스트 1074개 전부 통과 — `make test`로 확인.

---

## 4. 스코어 계산 단위 검증

`calculate_score(issues, ai_review)` 입력 시 category별 집계 확인:

```python
from src.analyzer.static import AnalysisIssue
from src.scorer.calculator import calculate_score

issues = [
    AnalysisIssue(tool="eslint", severity="warning", message="no-var",
                  line=1, category="code_quality", language="javascript"),
    AnalysisIssue(tool="semgrep", severity="error", message="SQL inject",
                  line=5, category="security", language="python"),
]
result = calculate_score(issues, ai_review=None)
# result.code_quality_score: ESLint warning 감점 확인
# result.security_score: Semgrep HIGH(error) 감점 확인
```

---

## 5. Railway 배포 검증 체크리스트

새 도구 추가(Phase D 등) 후 필수 확인:

- [ ] `git push` → Railway 자동 빌드 시작
- [ ] **Railway 대시보드 빌드 로그 직접 확인** (`push 성공 ≠ 빌드 성공`)
- [ ] 빌드 로그에 도구 설치 단계 exit code 0 확인
- [ ] `GET /health` → `{"status":"ok"}` 응답
- [ ] 샘플 PR 1개로 해당 언어 분석 이슈 실제 수신 확인
- [ ] Railway 앱 로그에 `failed for` / `timed out` 없음 확인

---

## 6. 긴급 롤백 절차

도구 오작동(배포 실패 / 분석 지연 / 스코어 이상) 시:

```bash
# 1. 문제 도구 is_enabled() 항상 False 반환하도록 임시 조치
# src/analyzer/tools/<tool>.py
def is_enabled(self, ctx):
    return False  # 긴급 비활성화

# 2. Railway 재배포
git commit -m "hotfix: disable <tool> temporarily"
git push

# 3. 분석 결과 정상화 확인 후 원인 분석
# 원인 수정 후 is_enabled 복구
```

**기존 분석 결과는 DB에 저장됨** — 롤백 후에도 이전 결과는 대시보드에 그대로 표시.
