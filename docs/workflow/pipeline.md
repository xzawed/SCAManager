## 이벤트 → 점수

진입 = `src/webhook/providers/github.py:426` (BackgroundTask). 이하 좌표는 `src/worker/pipeline.py`.

1. 메타 추출(`:365`). sha 가 비었거나 all-zeros 면 즉시 반환(`:386`).
2. repo 등록 + sha 중복 판정(`:459`). 중복이면 PR 만 gate 재실행. CLI 훅 행(`source=="cli"`)은 중복이 아니라 교체 대상(`:665`).
3. `_begin_attempt`(`:940`) 는 비싼 작업 **앞**. `_finish_attempt` 는 정상 종료 3곳(`:959`·`:1046`·`:1056`)에서만.
4. 파일 수집(`:950`) — 동기 I/O 는 `asyncio.to_thread` offload.
5. 병렬 실행(`:990`) — `_run_static_with_timeout` + `review_code` gather.
   - 정적: 파일별 순차, deadline 60초(`:33`), 도구당 30초(`src/constants.py:107`). 초과 시 완료분 보존 + `incomplete`.
   - AI: `src/analyzer/io/ai_review.py:68`. diff 16000자 절단(`review_prompt.py:31`), 모델 기본 `claude-sonnet-4-6`(`src/config.py:41`).
6. 채점(`:1007`) → 저장·게이트(`:729`, PR 만 `run_gate_check`) → 알림(`:1058`).

## 점수

`src/scorer/calculator.py:30` — 코드품질 25 + 보안 20 + 커밋 15 + 방향성 25 + 테스트 15.
감점(`AnalysisIssue.category` 기준, 도구명 무관): code_quality error −3 / warning −1(상한 25), security error −7 / warning −2. AI raw 20·20·10 → 15·25·15 스케일, 실패 시 기본값 13·21·10 + `ai_defaults_applied`. 등급 A90 B75 C60 D45(`src/constants.py:38`).

## 불완전 마커

미분석이 만점으로 머지되지 않게 `result` 에 실어 게이트로 넘긴다.

- `static_analysis_incomplete`(`:759`) — deadline 초과 · 전량 실패 · 도구 타임아웃 · fetch 실패.
- `ai_review_truncated`(`:80`) — 입출력 절단. 점수는 유지한다.
- `static_uncovered_languages`(`:86`) — 지원 분석기 없음. 차단하지 않고 가시화만.
- 신뢰도 판정 = `src/scorer/reliability.py` — `should_null_persist_score`(AI 실패만 컬럼 NULL) / `score_is_unreliable`(그 외는 집계만 제외).

## 분석기 추가 (25종)

1. `src/analyzer/io/tools/<도구>.py` 작성 — `name`·`category` + `supports(ctx)`·`is_enabled(ctx)`(`shutil.which`)·`run(ctx)`. 본보기 `shellcheck.py`.
2. `run` 은 `subprocess.run(..., timeout=STATIC_ANALYSIS_TIMEOUT, check=False)`. `TimeoutExpired` 는 `ctx.timed_out = True` 후 `[]` 반환(예외 금지). 비-JSON stdout 은 `RuntimeError`.
3. 모듈 하단 `register(...)` + `static.py` 상단 import 1줄(로드 시 자동 등록).
4. 조달한 바이너리는 `static.py:54` `PROVISIONED_ANALYZERS` 에 등재. 등재분 부재 = 배포 회귀 → `incomplete` 차단, 미등재분 부재 = 미제공 → 가시화만.
5. 새 언어면 `src/analyzer/pure/language.py:15` 확장자 맵 + `review_guides/tier{N}/<lang>.py` + `review_guides/__init__.py:34` `_GUIDE_MAP` 1줄.
6. `docs/architecture.md:86` 의 도구 목록 한 줄을 갱신한다.

## 검증

```bash
py -3 -m pytest tests/unit/analyzer tests/unit/scorer tests/unit/worker
py -3 -m pytest tests/unit/analyzer/test_procurement_contract.py tests/integration/test_static_analyzer.py
```

외부 린터는 실바이너리 통합 테스트를 같은 PR 에 넣는다(`test_eslint_analyzer.py`) — mock 은 무분석을 못 잡는다.
