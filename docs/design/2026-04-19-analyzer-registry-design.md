# Analyzer Registry 설계 (Phase A, 2026-04-19)

> 새 정적분석 도구 추가 시 이 문서를 참조. 변경 파일: `tools/<tool>.py` 1개로 끝남.

## 아키텍처 개요

```
src/analyzer/
├── registry.py          ← Protocol + REGISTRY + register()
├── static.py            ← AnalysisIssue, analyze_file (REGISTRY 순회)
├── language.py          ← detect_language(), is_test_file()
└── tools/
    ├── python.py        ← pylint, flake8, bandit
    ├── semgrep.py       ← Semgrep (30+ 언어)
    ├── eslint.py        ← ESLint (JS/TS)
    └── shellcheck.py    ← ShellCheck (shell)
```

모듈 로드 순서: `static.py`가 `import src.analyzer.tools.*` → 각 모듈 최하단 `_register_*()` 자동 호출 → `REGISTRY` 구성 완료.

---

## Analyzer Protocol 구현 체크리스트

새 도구 `tools/<tool>.py` 작성 시:

```python
class _MyToolAnalyzer:
    name = "my-tool"            # REGISTRY 내 고유 식별자 (중복 시 무시됨)
    category = "code_quality"   # "code_quality" | "security" 중 택1

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"go", "java"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:
        # 도구 설치 여부 + 기타 조건 (is_test 등)
        return shutil.which("my-tool") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        try:
            r = subprocess.run(["my-tool", ctx.tmp_path], ...)
            # JSON/XML 파싱 → AnalysisIssue 변환
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("my-tool timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("my-tool failed for %s: %s", ctx.tmp_path, exc)
            return []


def _register_mytool_analyzers() -> None:
    from src.analyzer.registry import register  # noqa: PLC0415
    register(_MyToolAnalyzer())


_register_mytool_analyzers()  # ← 모듈 import 시 자동 실행
```

---

## AnalyzeContext 계약

```python
@dataclass
class AnalyzeContext:
    filename: str        # 원본 파일명 (경로 포함)
    content: str         # 파일 내용 (언어 감지 + is_test 판단에 사용)
    language: str        # detect_language() 반환값 ("python", "go", ..., "unknown")
    is_test: bool        # is_test_file(filename, language) 반환값
    tmp_path: str        # 분석 도구에 전달할 임시 파일 경로 (실제 파일 존재)
    repo_config: object | None = None  # Phase D opt-in 제어용 (현재 미사용)
```

`tmp_path`는 `analyze_file()`이 생성한 임시 파일. 분석 도구는 이 경로를 직접 사용.

---

## AnalysisIssue 필수 필드

```python
@dataclass
class AnalysisIssue:
    tool: str            # 도구 이름 (식별 목적)
    severity: str        # "error" | "warning"
    message: str         # 이슈 설명
    line: int            # 발생 라인 (0이면 파일 전체)
    category: str        # "code_quality" | "security"  ← 점수에 영향
    language: str        # ctx.language 전달
```

**`category`가 점수를 결정한다**:
- `"code_quality"` error → `-3점`, warning → `-1점` (CQ_WARNING_CAP=25)
- `"security"` error(HIGH) → `-7점`, warning(LOW/MED) → `-2점` (SECURITY_MAX=20)

---

## register() 동작

```python
def register(analyzer: Analyzer) -> None:
    if any(a.name == analyzer.name for a in REGISTRY):
        return  # 이름 기반 중복 방지 — 테스트 재실행 시 안전
    REGISTRY.append(analyzer)
```

동일 모듈이 두 번 import 되더라도 REGISTRY는 1개 항목만 보유.

---

## 테스트 작성 패턴

```python
# tests/test_<tool>_analyzer.py

import importlib
import src.analyzer.tools.python  # noqa — REGISTRY 초기 상태 확보 필수

@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch):
    """각 테스트마다 REGISTRY를 Python 분석기만 있는 초기 상태로 리셋."""
    import src.analyzer.registry as reg
    original = list(reg.REGISTRY)   # python 분석기 캡처 후
    monkeypatch.setattr(reg, "REGISTRY", list(original))  # 격리
    # 테스트 대상 모듈 재로드
    import src.analyzer.tools.<tool> as m
    importlib.reload(m)
    yield

def test_is_enabled_when_binary_missing(ctx):
    with patch("shutil.which", return_value=None):
        assert not analyzer.is_enabled(ctx)

def test_timeout_returns_empty(ctx):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
        assert analyzer.run(ctx) == []

def test_json_error_returns_empty(ctx):
    with patch("subprocess.run", return_value=MagicMock(stdout="not-json")):
        assert analyzer.run(ctx) == []
```

**중요**: `import src.analyzer.tools.python` 선행 import 없으면 `fresh_registry` fixture가 빈 배열을 `original`로 캡처 → REGISTRY 오염.

---

## 점수 영향 흐름도

```
AnalysisIssue(category="code_quality", severity="warning")
  → calculate_score() cq_warnings 집계
  → code_quality_score = 25 - errors*3 - min(warnings, 25)

AnalysisIssue(category="security", severity="error")
  → calculate_score() security_errors 집계
  → security_score = 20 - errors*7 - warnings*2
```

새 도구가 올바른 category를 지정하면 `calculator.py` 수정 없이 즉시 점수 반영됨.
