# Multilingual Insight Prompt + Docs Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) `language` 파라미터가 Claude 프롬프트 응답 언어를 실제로 제어하게 수정 — `repo_insight_service.py`와 `dashboard_service.py` 양쪽. (2) `docs/architecture.md` / `docs/STATE.md` / `docs/cycle-history.md` 3종 문서 동기화.

**Architecture:**
- `repo_insight_service.py`: `_LANG_NAMES` dict(ko/en/ja → 언어명)를 추가하고, 프롬프트의 "in Korean" 하드코딩을 `_LANG_NAMES.get(language, "Korean")`으로 교체.
- `dashboard_service.py`: `insight_narrative()` 에 `language: str = "en"` 파라미터 추가 → `_build_insight_user_prompt()` 에 언어 지시 추가 → 시스템 프롬프트의 "Always reply in Korean" 제거 → `get_fresh/upsert/record_error` 호출에 `language=language` 전달 → `dashboard.py` 라우트에서 `language=get_locale(request)` 전달.
- Docs: 브랜치 생성 후 3 파일 직접 편집, PR 생성.

**Tech Stack:** Python 3.12, pytest, anthropic SDK, SQLAlchemy, FastAPI

---

## 파일 변경 목록

| 액션 | 파일 |
|------|------|
| Modify | `src/services/repo_insight_service.py` |
| Modify | `src/services/dashboard_service.py` |
| Modify | `src/ui/routes/dashboard.py` |
| Create | `tests/unit/services/test_insight_language_prompt.py` |
| Modify | `docs/architecture.md` |
| Modify | `docs/STATE.md` |
| Modify | `docs/cycle-history.md` |

---

## Task 1: 테스트 먼저 작성 (TDD Red)

**Files:**
- Create: `tests/unit/services/test_insight_language_prompt.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
"""repo_insight_service + dashboard_service 언어별 프롬프트 생성 검증."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestRepoInsightLanguagePrompt:
    """repo_insight_narrative — language 파라미터가 프롬프트 언어를 제어하는지 검증."""

    @pytest.mark.asyncio
    async def test_prompt_uses_korean_when_language_ko(self, db, repo):
        """language='ko' → 프롬프트에 'Korean' 포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "테스트"}')]
        mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        captured = {}

        async def capture_create(**kwargs):
            captured["messages"] = kwargs.get("messages", [])
            return mock_msg

        mock_client.messages.create = capture_create

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="ko",
            )

        user_prompt = captured["messages"][0]["content"]
        assert "Korean" in user_prompt

    @pytest.mark.asyncio
    async def test_prompt_uses_english_when_language_en(self, db, repo):
        """language='en' → 프롬프트에 'English' 포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "test"}')]
        mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_client = AsyncMock()
        captured = {}

        async def capture_create(**kwargs):
            captured["messages"] = kwargs.get("messages", [])
            return mock_msg

        mock_client.messages.create = capture_create

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="en",
            )

        user_prompt = captured["messages"][0]["content"]
        assert "English" in user_prompt
        assert "Korean" not in user_prompt

    @pytest.mark.asyncio
    async def test_prompt_uses_japanese_when_language_ja(self, db, repo):
        """language='ja' → 프롬프트에 'Japanese' 포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "テスト"}')]
        mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_client = AsyncMock()
        captured = {}

        async def capture_create(**kwargs):
            captured["messages"] = kwargs.get("messages", [])
            return mock_msg

        mock_client.messages.create = capture_create

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="ja",
            )

        user_prompt = captured["messages"][0]["content"]
        assert "Japanese" in user_prompt


class TestDashboardInsightLanguagePrompt:
    """_build_insight_user_prompt — language 파라미터 유무 및 언어 지시 검증."""

    def test_build_prompt_ko_contains_korean_instruction(self):
        """language='ko' → user prompt에 한국어 지시 포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="ko",
        )
        assert "Korean" in prompt

    def test_build_prompt_en_contains_english_instruction(self):
        """language='en' → user prompt에 영어 지시 포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="en",
        )
        assert "English" in prompt
        assert "Korean" not in prompt

    def test_build_prompt_ja_contains_japanese_instruction(self):
        """language='ja' → user prompt에 일본어 지시 포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="ja",
        )
        assert "Japanese" in prompt

    @pytest.mark.asyncio
    async def test_insight_narrative_passes_language_to_cache(self, db):
        """language 파라미터가 get_fresh / upsert 캐시 호출에 전달되는지 검증."""
        from src.services import dashboard_service

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=(
            '{"positive_highlights":["ok"],'
            '"focus_areas":["fix"],'
            '"key_metrics":[{"label":"a","value":"1","delta":"0"},'
            '{"label":"b","value":"2","delta":"0"},'
            '{"label":"c","value":"3","delta":"0"},'
            '{"label":"d","value":"4","delta":"0"}],'
            '"next_actions":["do it"]}'
        ))]
        mock_msg.usage = MagicMock(
            input_tokens=10, output_tokens=20,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        )
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("src.services.dashboard_service.settings") as s, \
             patch("src.services.dashboard_service.anthropic.AsyncAnthropic",
                   return_value=mock_client), \
             patch("src.services.dashboard_service.insight_narrative_cache_repo") as mock_repo:
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            mock_repo.invalidate = MagicMock()
            mock_repo.get_fresh = MagicMock(return_value=None)
            mock_repo.upsert = MagicMock()
            mock_repo.record_error = MagicMock()

            # dashboard_kpi 등 4 헬퍼도 mock
            with patch.object(dashboard_service, "dashboard_kpi",
                               return_value={"analysis_count": {"value": 5}}), \
                 patch.object(dashboard_service, "dashboard_trend", return_value=[]), \
                 patch.object(dashboard_service, "frequent_issues_v2", return_value=[]), \
                 patch.object(dashboard_service, "auto_merge_kpi", return_value={}):
                await dashboard_service.insight_narrative(
                    db, days=7, user_id=1, language="en",
                )

        # get_fresh에 language="en" 전달됐는지 확인
        call_kwargs = mock_repo.get_fresh.call_args[1]
        assert call_kwargs.get("language") == "en"
        # upsert에도 language="en" 전달됐는지 확인
        upsert_kwargs = mock_repo.upsert.call_args[1]
        assert upsert_kwargs.get("language") == "en"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/unit/services/test_insight_language_prompt.py -v 2>&1 | head -40
```

Expected: FAIL (`language="en"` 시 "Korean" 포함 / `_build_insight_user_prompt` signature 에러 / `get_fresh` language 미전달)

---

## Task 2: `repo_insight_service.py` 언어 매핑 + 프롬프트 수정

**Files:**
- Modify: `src/services/repo_insight_service.py`

- [ ] **Step 1: `_LANG_NAMES` dict 추가 + 프롬프트 수정**

`_MAX_ANALYSES = 30` 바로 아래에 추가:
```python
# 지원 언어 코드 → Claude 프롬프트 언어명 매핑
# Mapping from locale code to the language name used in Claude prompts.
_LANG_NAMES: dict[str, str] = {"ko": "Korean", "en": "English", "ja": "Japanese"}
```

`user_prompt` 의 `"in Korean"` 부분을 아래로 교체 (`repo_insight_service.py:369` 근처):
```python
        f"Please provide a 2-3 paragraph diagnostic narrative "
        f"in {_LANG_NAMES.get(language, 'Korean')} summarizing "
```

- [ ] **Step 2: 테스트 확인**

```bash
pytest tests/unit/services/test_insight_language_prompt.py::TestRepoInsightLanguagePrompt -v
```

Expected: 3건 PASS

---

## Task 3: `dashboard_service.py` 언어 지원

**Files:**
- Modify: `src/services/dashboard_service.py`

- [ ] **Step 1: `_INSIGHT_SYSTEM_PROMPT` 에서 "Always reply in Korean" 제거**

`_INSIGHT_SYSTEM_PROMPT` 안의:
```python
    "Always reply in Korean. Output strict JSON only "
```
를 아래로 교체:
```python
    "Output strict JSON only "
```

- [ ] **Step 2: `_build_insight_user_prompt` 에 `language` 파라미터 추가**

함수 시그니처:
```python
def _build_insight_user_prompt(
    *,
    days: int,
    kpi: dict[str, Any],
    trend: list[dict[str, Any]],
    frequent: list[dict[str, Any]],
    auto_merge: dict[str, Any],
    language: str = "en",
) -> str:
```

`_LANG_NAMES` 동일 상수를 재사용하기 위해 파일 상단 상수 섹션에 추가:
```python
# 지원 언어 코드 → Claude 프롬프트 언어명 매핑 (repo_insight_service 와 동일 집합)
# Locale code → language name for Claude prompts (same set as repo_insight_service).
_DASHBOARD_LANG_NAMES: dict[str, str] = {"ko": "Korean", "en": "English", "ja": "Japanese"}
```

`_build_insight_user_prompt` 반환 직전 `payload` dict 직렬화 줄 아래에 언어 지시 추가:
```python
    lang_name = _DASHBOARD_LANG_NAMES.get(language, "Korean")
    return (
        f"다음은 최근 {days}일간의 dashboard 데이터입니다. "
        f"위 4 카드 JSON 형식으로 narrative 를 생성해주세요. "
        f"Please respond in {lang_name}.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, default=str)}\n```"
    )
```

- [ ] **Step 3: `insight_narrative()` 에 `language` 파라미터 추가**

함수 시그니처:
```python
async def insight_narrative(  # pylint: disable=too-many-locals
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
    api_key: str | None = None,
    user_id: int | None = None,
    refresh: bool = False,
    language: str = "en",
) -> dict[str, Any]:
```

docstring 에 `language` 항목 추가:
```python
        language: 응답 언어 코드 ("ko"/"en"/"ja"). Response language code.
```

- [ ] **Step 4: 캐시 호출에 `language` 전달**

`get_fresh` 호출:
```python
            cached = insight_narrative_cache_repo.get_fresh(
                db, user_id=user_id, days=days, language=language, now=_now,
            )
```

`upsert` 호출:
```python
        insight_narrative_cache_repo.upsert(
            db, user_id=user_id, days=days, language=language, response=response, now=_now,
        )
```

`record_error` 호출 3곳 (`no_data` / `api_error` / `parse_error`):
```python
            insight_narrative_cache_repo.record_error(
                db, user_id=user_id, days=days, language=language, error_type="no_data", now=_now,
            )
```
```python
            insight_narrative_cache_repo.record_error(
                db, user_id=user_id, days=days, language=language, error_type="api_error", now=_now,
            )
```
```python
            insight_narrative_cache_repo.record_error(
                db, user_id=user_id, days=days, language=language, error_type="parse_error", now=_now,
            )
```

- [ ] **Step 5: `_build_insight_user_prompt` 호출에 `language` 전달**

```python
    user_prompt = _build_insight_user_prompt(
        days=days, kpi=kpi, trend=trend, frequent=frequent, auto_merge=auto_merge,
        language=language,
    )
```

- [ ] **Step 6: 테스트 확인**

```bash
pytest tests/unit/services/test_insight_language_prompt.py -v
```

Expected: 전체 PASS

---

## Task 4: `dashboard.py` 라우트에 `language` 전달

**Files:**
- Modify: `src/ui/routes/dashboard.py`

- [ ] **Step 1: `insight_narrative` 호출에 `language` 추가**

기존:
```python
            insight = await dashboard_service.insight_narrative(
                db, days=days, user_id=current_user.id, refresh=bool(refresh),
            )
```

교체:
```python
            insight = await dashboard_service.insight_narrative(
                db, days=days, user_id=current_user.id, refresh=bool(refresh),
                language=locale_value,
            )
```

`locale_value` 가 이미 해당 스코프에서 선언되어 있는지 확인 후 없으면 `get_locale(request)` 를 직접 사용:
```python
            insight = await dashboard_service.insight_narrative(
                db, days=days, user_id=current_user.id, refresh=bool(refresh),
                language=get_locale(request),
            )
```

- [ ] **Step 2: 단위 테스트 확인**

```bash
pytest tests/unit/services/test_insight_language_prompt.py tests/unit/services/test_dashboard_service_insight_narrative.py -v
```

Expected: 전체 PASS

---

## Task 5: commit (기능)

- [ ] **Step 1: 테스트 전체 실행 (단위만)**

```bash
pytest tests/unit/ -q --timeout=30 2>&1 | tail -5
```

Expected: 모두 passed (숫자 증가, fail 0)

- [ ] **Step 2: lint 확인**

```bash
python -m pylint src/services/repo_insight_service.py src/services/dashboard_service.py src/ui/routes/dashboard.py --disable=all --enable=E,W 2>&1 | tail -10
```

Expected: 신규 에러 없음

- [ ] **Step 3: 브랜치 생성 + commit**

```bash
git checkout -b feat/insight-multilang-prompt
git add src/services/repo_insight_service.py \
        src/services/dashboard_service.py \
        src/ui/routes/dashboard.py \
        tests/unit/services/test_insight_language_prompt.py
git commit -m "feat(insight): language 파라미터가 Claude 프롬프트 응답 언어를 실제 제어

- repo_insight_service: _LANG_NAMES dict 추가, '항상 Korean' 하드코딩 → language 인자 활용
- dashboard_service: insight_narrative에 language 파라미터 추가, 캐시 3종 호출 전달
  _build_insight_user_prompt language 지시 삽입, 시스템 프롬프트 언어 중립화
- dashboard.py 라우트: get_locale(request) → insight_narrative language 전달
- 테스트 5건 신규 (ko/en/ja 프롬프트 검증 + 캐시 language 전달 검증)"
```

---

## Task 6: docs 동기화

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/STATE.md`
- Modify: `docs/cycle-history.md`

- [ ] **Step 1: `docs/architecture.md` e2e 섹션 갱신**

기존 e2e 섹션을 아래로 교체:
```
e2e/
├── conftest.py                    # live_server / page / seeded_page / browser_instance / seeded_analysis fixtures (session-scope)
├── pytest.ini                     # E2E 전용 pytest 설정 (asyncio_mode 미설정 — src/ 단위 테스트 충돌 방지)
├── _perf_helpers.py               # LCP_INIT_JS + measure_one/page 공통 헬퍼 — test_performance.py + scripts/perf_measure.py 공유 (사이클 111 #536)
├── test_performance.py            # 12개 @pytest.mark.perf 성능 테스트 — TTFB/FCP/LCP/DCL/Load (3회 avg/min/max)
├── test_dashboard.py              # /dashboard 페이지 E2E — 4 모드(overview/insight/usage/security) 전환 흐름
├── test_dashboard_insight.py      # /dashboard?mode=insight E2E — AI narrative 카드 렌더링
├── test_i18n_visual_regression.py # 3-언어 × 4-페이지 i18n 연기 테스트 (Cycle 84 PR-16)
├── test_navigation.py             # hx-boost 네비게이션 + 뒤로가기 흐름 E2E
├── test_repos_mode.py             # /repos/add + /repos/{name} 기능 흐름 E2E (Cycle 94)
├── test_settings.py               # /repos/{name}/settings 저장 흐름 E2E
├── test_theme.py                  # 4-테마 토글 E2E (desktop)
└── test_theme_mobile_guards.py    # 모바일 테마 토글 + 44px 터치 영역 E2E
```

- [ ] **Step 2: `docs/STATE.md` 수치 갱신**

헤더 라인의 수치를 아래로 갱신:
- `#533` → `#536`
- `3027 수집` → `3055 수집`
- `3023 passed, 4 skipped` → `실제 CI 수치로` (PR 머지 후 CI 결과 참조)

단위 테스트 비고 마지막에 추가:
```
+ **사이클 111 #535 P1 3건 + #536 chore(_perf_helpers 추출)**
```

- [ ] **Step 3: `docs/cycle-history.md` 사이클 110·111 이력 추가**

파일 끝에 추가:
```markdown
## 사이클 110~111

- **사이클 110 (2026-05-19 · #530~#532)** — settings.html AI 리뷰 모델 선택기 카드 위치 변경 (#530). InsightNarrativeCache 에러 빈도 추적 — SDK/network/parse 3 컬럼 + 0033 마이그레이션 + 서비스/레포지토리 5+1 에이전트 검증 (#531). docs STATE/architecture 사이클 110 동기화 (#532).
- **사이클 111 (2026-05-20 · #533~#536)** — analysis_detail 차트 검정 배경(accent+'22' → accentRgb 경로) + 피드백 버튼 htmx 핸들러 누적 등록 수정 (remove-before-add 2-레이어) + 회귀가드 13건 (#533). 5+1 리뷰 P1 3건 수정: language 누락 2곳 + ORM 인덱스 누락 + dead assert (#535). e2e/_perf_helpers.py 추출 — _LCP_INIT_JS/measure_one/measure_page 중복 58줄 제거 (#536).
```

- [ ] **Step 4: commit (docs)**

```bash
git add docs/architecture.md docs/STATE.md docs/cycle-history.md
git commit -m "docs: architecture e2e 섹션 8파일 갱신 + STATE.md + cycle-history 110·111 동기화"
```

---

## Task 7: PR 생성

- [ ] **Step 1: push + PR 생성**

```bash
git push -u origin feat/insight-multilang-prompt
gh pr create \
  --title "feat(insight): 다국어 프롬프트 지원 + docs 동기화" \
  --body "..."
```

PR body 포함 항목:
- Summary (기능 변경 + docs 변경)
- 테스트 결과
- 🔍 사용자 검증 필요 (Railway에서 영어/일본어 사용자로 insight 카드 확인)
