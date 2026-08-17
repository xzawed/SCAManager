# 운영 검증 가이드 — 분석 도구 배포 후 확인 절차

> Semgrep·ESLint/ShellCheck 등 분석 도구 배포 이후 정상 동작하는지
> 검증하는 표준 절차. 새 도구 추가 시 동일 패턴으로 확장.

## 1. 도구 설치 확인

Railway 컨테이너에서 확인 (Deploy Logs → `railway run bash` 또는 서버 시작 시 로그):

```bash
semgrep --version      # 1.x.x 이상
eslint --version       # 9.x.x
shellcheck --version   # 0.9.x
```

**Railway 빌드 로그에서 확인** — 조달 출처가 파일마다 다르다(고칠 곳을 틀리지 않도록):
```
✓ npm install -g eslint@9 ...      ← railway.toml buildCommand (nixpacks 아님)
✓ pip install -r requirements.txt  ← semgrep 은 requirements.txt 고정 핀
✓ apt-get install -y shellcheck    ← nixpacks.toml aptPkgs
```

> 🔴 **eslint 를 `nixpacks.toml` 에서 찾으면 못 찾는다** — 그 파일의 `[phases.build]` 는 제거돼 있고
> `railway.toml` 의 `buildCommand` 가 상위 오버라이드다. 우선순위 정본 =
> [`.claude/rules/deploy.md`](../../.claude/rules/deploy.md). `package.json` 의 eslint 는 로컬
> `npm run lint:js` 용 devDependency 로, 런타임 `shutil.which("eslint")` 가 보는 전역 설치본과 다른 물건이다.

🔴 **「도구가 없으면 이슈 0건, 오류 없음」이라고 적혀 있었다 — `#1410`(2026-08-16) 이후 거짓이다.**
바이너리 부재의 결과는 `src/analyzer/io/static.py` 의 **조달 계약**으로 갈린다:

- `PROVISIONED_ANALYZERS`(`static.py:54-63`) 안 도구 — **eslint·semgrep·shellcheck 전부 포함** — 이 없으면
  → `StaticAnalysisResult.incomplete = True`(`static.py:269`) → **auto-merge/approve 차단** +
  `provisioned analyzer missing for …` WARNING(`static.py:271`).
- 계약 밖 도구(clippy·swiftlint 등)가 없으면 → `uncovered_language` 로 가시화만, 차단 없음.

즉 **이 세 도구의 부재는 「정상」이 아니라 배포 회귀 신호다.** 계약 정본 =
[`.claude/rules/pipeline.md`](../../.claude/rules/pipeline.md) · 가드 =
`tests/unit/analyzer/test_procurement_contract.py` · `tests/unit/analyzer/test_static_incomplete.py`.

---

## 2. 런타임 동작 검증

### 2.1 분석 로그 확인

Railway 앱 로그에서 아래 패턴이 **없어야 함** (문자열은 `src/analyzer/io/` 실측):
```
semgrep timed out for /tmp/...                  ← tools/semgrep.py:77
shellcheck failed for /tmp/...                  ← tools/shellcheck.py:61
eslint timed out for /tmp/...                   ← tools/eslint.py:161
eslint unavailable for /tmp/...                 ← tools/eslint.py:164
analyzer eslint failed for <파일명>: ...         ← static.py:164 (도구가 못 잡은 crash → incomplete 승격)
provisioned analyzer missing for <파일명> (...)  ← static.py:271 🔴 조달 회귀 = auto-merge 차단
```

🔴 **`eslint failed for …` 라고 적혀 있었으나 그런 문자열은 코드에 없다** —
`grep -rn "eslint failed for" src/` = 0건. eslint 실패는 위 `analyzer %s failed for %s` 경로로 나오고
`%s` 는 `ctx.filename` 이라 `/tmp/…` 도 아니다. 옛 문자열로 감시하면 **영원히 안 잡힌다**.

`is_enabled=False` 는 **더 이상 무로그·정상이 아니다** — 조달 계약 안 도구면 마지막 줄 WARNING 이 뜬다(§1).

### 2.2 언어별 샘플 PR 체크리스트

각 도구를 활성화했다면 아래 샘플 PR로 실제 이슈 감지 여부 확인.

**ESLint (JavaScript)**:
```javascript
// test.js
var x = 1           // no-var warning
eval("alert(1)")    // no-eval error
```
→ `GET /api/analyses/{id}` (단건, `src/api/stats.py:17`) 또는
  `GET /api/repos/{repo}/analyses` (목록, `src/api/repos.py:131`) 또는 대시보드 분석 상세 확인
→ 응답 **`result.issues`** 배열에 `"tool": "eslint"` 항목 존재 여부 (`src/worker/pipeline.py:98-110`)

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
→ 룰셋은 `--config=p/default` **고정**이다(`src/analyzer/io/tools/semgrep.py:48`) — `auto` 가 아니다.
  적중 여부가 룰셋에 달려 있어 **이슈 0건도 정상**이므로, 이 항의 판정 기준은 이슈 수가 아니라
  **§2.1 로그에 `semgrep …` 경고가 없고 `incomplete` 가 서지 않는 것**이다.

### 2.3 점수 회귀 검증

Python 파일만 포함된 기존 PR을 재분석 시 점수가 도구 추가 전과 동일해야 함.

**검증 방법**:
```bash
# analysis_detail 페이지에서 동일 commit SHA 분석 2건 비교
# 또는 API 로 score 확인 — /api/** 는 X-API-Key 필수 (src/api/auth.py:39 require_api_key)
curl -s -H "X-API-Key: $API_KEY" "$APP_URL/api/analyses/{id}" | jq '.score'
# 헤더 없이 호출하면 401, 서버에 API_KEY 미설정이면 503 — 점수 대신 오류가 온다 (auth.py:32,36)
```

**예상**: `category` 기반 집계 전환 후에도 Python-only PR 점수 불변 (CQ_WARNING_CAP=25 동치 보장).

---

## 3. 도구 미설치 환경 확인 (로컬 개발)

로컬에 eslint/shellcheck가 없을 때 테스트는 **mock으로 대체**:

```python
# tests/unit/analyzer/tools/test_eslint.py:215-220 패턴 참조
# (`tests/test_eslint_analyzer.py` 라고 적혀 있었으나 그 경로는 없다. 실바이너리 통합 테스트인
#  tests/integration/test_eslint_analyzer.py 는 mock 이 아니라 skipif 를 쓰므로 이 패턴이 아니다.)
from src.analyzer.io.tools.eslint import _ESLintAnalyzer

with patch("shutil.which", return_value=None):
    assert _ESLintAnalyzer().is_enabled(ctx) is False
```

실제 바이너리 없어도 단위 테스트 전부 통과 — 최신 수치는 [docs/STATE.md](../STATE.md) 헤더 참조.
`make test-isolated` 로 .env 격리 환경 확인 권장.

🔴 **`make` 이 없는 머신이 있다**(이 개발 PC 포함 — `make: command not found`). 그 경우 타깃이 하는 일을
직접 한다(`Makefile:63-70` 이 정본): `.env` 를 임시로 치우고 `GITHUB_TOKEN`·`DATABASE_URL`·`API_KEY` 등
자격증명 환경변수를 unset 한 뒤 pytest 를 돌린다. 이 타깃은 `pytest tests/` **전체**를 돌리므로,
분석 도구 검증만 필요하면 `py -3 -m pytest tests/unit/analyzer` 로 좁힌다.

---

## 4. 스코어 계산 단위 검증

`calculate_score()` 는 **`AnalysisIssue` 리스트가 아니라 `StaticAnalysisResult` 리스트**를 받는다
(`src/scorer/calculator.py:30-33`). 이전 예제는 `src/analyzer/static` 에서 import 하고 이슈를 그대로
넘겼는데, 그 모듈은 존재하지 않고(`ModuleNotFoundError`) 우회하더라도
`AttributeError: 'AnalysisIssue' object has no attribute 'issues'` 로 죽는다(실측 재현).

```python
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.pure.registry import AnalysisIssue, Category, Severity
from src.scorer.calculator import calculate_score

result = StaticAnalysisResult(filename="test.js", issues=[
    AnalysisIssue(tool="eslint", severity=Severity.WARNING, message="no-var",
                  line=1, category=Category.CODE_QUALITY, language="javascript"),
    AnalysisIssue(tool="semgrep", severity=Severity.ERROR, message="SQL inject",
                  line=5, category=Category.SECURITY, language="python"),
])
score = calculate_score([result], ai_review=None)
# score.code_quality_score = CODE_QUALITY_MAX - PYLINT_WARNING_PENALTY  (cq warning 1건)
# score.security_score     = SECURITY_MAX     - BANDIT_HIGH_PENALTY     (security error 1건)
# 감점 상수 정본 = src/constants.py — 여기 숫자를 복제하지 않는다.
```

---

## 5. Railway 배포 검증 체크리스트

새 도구 추가 후 필수 확인:

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
# src/analyzer/io/tools/<tool>.py
def is_enabled(self, ctx):
    return False  # 긴급 비활성화

# 2. Railway 재배포
git commit -m "hotfix: disable <tool> temporarily"
git push

# 3. 분석 결과 정상화 확인 후 원인 분석
# 원인 수정 후 is_enabled 복구
```

**재배포 없이 끄는 경로**: 리포 설정 `disabled_tools` 에 도구 이름을 넣는다
(`src/models/repo_config.py:56` · API `src/api/repos.py:61`). 이 경로는 `opted_out` 으로 세어져
§1 의 조달 회귀 승격(`incomplete`)을 억제한다 — 단 `is_enabled()` 검사가 **먼저**라
바이너리가 살아 있을 때만 그렇다(`src/analyzer/io/static.py:140-151`).

**기존 분석 결과는 DB에 저장됨** — 롤백 후에도 이전 결과는 대시보드에 그대로 표시.
