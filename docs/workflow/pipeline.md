## 이벤트 → 점수

진입 = `src/webhook/providers/github.py::add_task(run_analysis_pipeline` (BackgroundTask). 이하 좌표는 `src/worker/pipeline.py`.

1. 메타 추출(`::def _extract_event_metadata`). sha 가 비었거나 all-zeros 면 즉시 반환(`::def _is_blank_sha`).
2. repo 등록 + sha 중복 판정(`::def _ensure_repo`). 중복이면 PR 만 gate 재실행. CLI 훅 행(`source=="cli"`)은 중복이 아니라 교체 대상(`::def _is_cli_only`).
3. `_begin_attempt`(`::_begin_attempt(_review_repo_id`) 는 비싼 작업 **앞**. `_finish_attempt`(`::def _finish_attempt`) 는 정상 종료 3곳에서만.
4. 파일 수집(`::def _collect_files`) — 동기 I/O 는 `asyncio.to_thread` offload.
5. 병렬 실행(`::asyncio.gather(*`) — `_run_static_with_timeout` + `review_code` gather.
   - 정적: 파일별 순차, deadline 60초(`::PIPELINE_ANALYSIS_TIMEOUT =`), 도구당 30초(`src/constants.py::STATIC_ANALYSIS_TIMEOUT`). 초과 시 완료분 보존 + `incomplete`.
   - AI: `src/analyzer/io/ai_review.py::async def review_code`. diff 16000자 절단(`src/analyzer/pure/review_prompt.py::MAX_DIFF_CHARS =`), 모델 기본 `claude-sonnet-4-6`(`src/config.py::claude_review_model:`).
6. 채점(`::calculate_score(a`) → 저장·게이트(`::         await run_gate_check(`, PR 만 `run_gate_check`) → 알림(`::_send_notifications(notify_tasks:`).

## 점수

`src/scorer/calculator.py::def calculate_score` — 코드품질 25 + 보안 20 + 커밋 15 + 방향성 25 + 테스트 15.
감점(`AnalysisIssue.category` 기준, 도구명 무관): code_quality error −3 / warning −1(상한 25), security error −7 / warning −2. AI raw 20·20·10 → 15·25·15 스케일, 실패 시 기본값 13·21·10 + `ai_defaults_applied`. 등급 A90 B75 C60 D45(`src/constants.py::GRADE_THRESHOLDS:`).

## 불완전 마커

미분석이 만점으로 머지되지 않게 `result` 에 실어 게이트로 넘긴다.

- `static_analysis_incomplete`(`::result_dict["static_analysis_incomplete"] = True`) — deadline 초과 · 전량 실패 · 도구 타임아웃 · fetch 실패.
- `ai_review_truncated`(`::ai_review_truncated"`) — 입출력 절단. 점수는 유지한다.
- `static_uncovered_languages`(`::"static_uncovered_languages": sorted({`) — 지원 분석기 없음. 차단하지 않고 가시화만.
- `static_no_dedicated_observers`(`::def _aggregate_no_dedicated_observers`) — 지원은 되나 전담 분석기가
  하나도 안 돎(범용 semgrep 만). 같은 계약 — 차단하지 않고 가시화만. 새 분석기가 범용이면
  클래스에 선언한다(`src/analyzer/io/tools/semgrep.py::is_generic = True`). 프로토콜 속성으로는
  선언하지 않는다 — `runtime_checkable` 이 인스턴스에 요구해 미선언 어댑터가 전부 떨어진다(실측 3건 red).
- 신뢰도 판정 = `src/scorer/reliability.py` — `should_null_persist_score`(AI 실패만 컬럼 NULL) / `score_is_unreliable`(그 외는 집계만 제외).

## 분석기 추가 (25종)

1. `src/analyzer/io/tools/<도구>.py` 작성 — `name`·`category` + `supports(ctx)`·`is_enabled(ctx)`(`shutil.which`)·`run(ctx)`. 본보기 `src/analyzer/io/tools/eslint.py::did not produce JSON`(`shellcheck.py` 는 `[]` 를 반환하는 구식이라 따르지 않는다).
2. `run` 은 `subprocess.run(..., timeout=STATIC_ANALYSIS_TIMEOUT, check=False)`. `TimeoutExpired` 는 `ctx.timed_out = True` 후 `[]` 반환(예외 금지). 비-JSON stdout 은 `RuntimeError`.
3. 모듈 하단 `register(...)` + `static.py` 상단 import 1줄(로드 시 자동 등록).
4. 조달한 바이너리는 `src/analyzer/io/static.py::PROVISIONED_ANALYZERS:` `PROVISIONED_ANALYZERS` 에 등재. 등재분 부재 = 배포 회귀 → `incomplete` 차단, 미등재분 부재 = 미제공 → 가시화만.
5. 새 언어면 `src/analyzer/pure/language.py::_EXTENSION_MAP:` 확장자 맵 + `review_guides/tier{N}/<lang>.py` + `src/analyzer/pure/review_guides/__init__.py::_GUIDE_MAP:` `_GUIDE_MAP` 1줄.
6. `docs/architecture.md::tools/` 의 `tools/(N 어댑터)` 개수를 갱신한다.
7. `tests/unit/scripts/test_analyzer_provenance.py` 의 `tests/unit/scripts/test_analyzer_provenance.py::_PROVENANCE = ` 에 `(바이너리, 조달모드, optional 사유)` 를 등재한다 — 미등재는 CI FAIL. 조달하지 않으면 `optional_absent_ok` + 사유. 바이너리 이름이 도구명과 다르면
   `src/analyzer/io/static.py::_BINARY_OVERRIDES:` `_BINARY_OVERRIDES` 에 매핑한다 — 없으면 조달했는데 부재로 판정된다.

## 검증

```bash
py -3 -m pytest tests/unit/analyzer tests/unit/scorer tests/unit/worker
py -3 -m pytest tests/unit/analyzer/test_procurement_contract.py tests/integration/test_static_analyzer.py
```

외부 린터는 실바이너리 통합 테스트를 같은 PR 에 넣는다(`test_eslint_analyzer.py`) — mock 은 무분석을 못 잡는다.
