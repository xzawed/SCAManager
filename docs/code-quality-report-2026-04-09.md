# SCAManager 코드품질 강화 보고서

**날짜:** 2026-04-09  
**작업자:** Claude Sonnet 4.6  
**대상 브랜치:** main

---

## 1. 진단 요약

Phase 1~8B까지 기능 중심으로 빠르게 성장하면서 코드 품질 지표가 누적된 상태였다.  
`make lint` 실행 결과 **pylint 0.00/10**, flake8 경고 16건, 7개 중복 코드 패턴, 1개 실제 버그가 발견됐다.

### 발견된 이슈 목록

| 유형 | 건수 | 심각도 | 파일 |
|------|------|--------|------|
| **버그**: `PUT /api/repos/{repo}/config` 4개 필드 누락 | 1 | Critical | `src/api/repos.py` |
| **중복**: `ChangedFile` dataclass 2곳 정의 | 1 | High | `src/github_client/diff.py`, `src/cli/git_diff.py` |
| **중복**: GitHub API 인증 헤더 dict 2곳 | 1 | Medium | `src/gate/github_review.py`, `src/notifier/github_comment.py` |
| **중복**: 분석 결과 JSON 빌더 2곳 | 1 | Medium | `src/api/hook.py`, `src/worker/pipeline.py` |
| **누락**: 모듈/클래스/공개 함수 docstring | ~80건 | Medium | 전체 src/ |
| **스타일**: f-string without placeholder (F541) | 1 | Low | `src/ui/router.py:59` |
| **스타일**: box-drawing 긴 줄 (C0301) | 3 | Low | `src/cli/formatter.py` |
| **스타일**: `import json as _json` 불필요 alias | 1 | Low | `src/cli/formatter.py` |
| **스타일**: import 순서 오류 (C0411) | 1 | Low | `src/main.py` |
| **스타일**: `lifespan(app)` outer-scope 재정의 (W0621) | 1 | Low | `src/main.py` |
| **설정**: models 컬럼 정렬 E221 무시 누락 | 1 | Low | `setup.cfg` |

---

## 2. 버그 상세: PUT /api/repos/{repo}/config 누락 필드

`src/api/repos.py`의 `RepoConfigUpdate` 모델과 `update_repo_config()` 핸들러에  
**discord_webhook_url, slack_webhook_url, custom_webhook_url, email_recipients** 4개 필드가 없었다.

이로 인해 REST API로 알림 채널을 업데이트하면 해당 필드가 항상 `None`으로 덮어써지는 데이터 손실 버그가 있었다.  
(Web UI `/repos/{repo}/settings` 폼은 별도 라우터를 사용하므로 영향 없었음)

**수정 내용:**
- `RepoConfigUpdate` 모델에 4개 필드 추가 (기본값 `None`)
- `update_repo_config()` 핸들러에서 `RepoConfigData` 생성 시 4개 필드 전달

---

## 3. 적용된 개선 사항

### 3-1. 신규 파일 2개

| 파일 | 역할 |
|------|------|
| `src/github_client/models.py` | `ChangedFile` dataclass 단일 출처 정의 |
| `src/github_client/helpers.py` | `github_api_headers()` 공용 헬퍼 |

### 3-2. 중복 제거 (Deduplication)

| 패턴 | 변경 전 | 변경 후 |
|------|---------|---------|
| `ChangedFile` dataclass | `diff.py` + `git_diff.py` 각자 정의 | `models.py`에서 import |
| GitHub API headers | `github_review.py` + `github_comment.py` 각자 4줄 | `github_api_headers()` 1회 호출 |
| 분석 결과 JSON | `pipeline.py` + `hook.py` 각자 ~15줄 | `_build_result_dict()` 추출 후 공유 |

### 3-3. Docstring 추가 (전체 src/)

모듈 docstring 25개 파일, 클래스 docstring 4개, 공개 함수 docstring 15+ 개 추가.

### 3-4. 스타일 수정

- `src/ui/router.py:59` — 불필요한 `f""` 접두사 제거 (F541 수정)
- `src/cli/formatter.py` — box-drawing 긴 줄을 `_H*N` 패턴으로 단축, `import json as _json` → `import json`
- `src/main.py` — import 순서 정렬, `lifespan(_app)` 파라미터 이름 변경 (W0621 수정)
- `src/analyzer/ai_review.py` — `AiReviewResult` 에 `# pylint: disable=too-many-instance-attributes` 추가 (의도적 11속성)
- `src/worker/pipeline.py` — `_build_notify_tasks`, `run_analysis_pipeline`에 복잡도 suppress 주석 추가 (의도적 복잡성)
- `setup.cfg` — `src/models/*.py:E221`, `src/github_client/repos.py:E501`, `src/notifier/email.py:E501` per-file-ignores 추가

---

## 4. 미적용 항목 및 이유

| 항목 | 이유 |
|------|------|
| `_build_notify_tasks()` 구조 변경 | 7개 채널 블록을 registry 패턴으로 리팩터 시 기존 테스트 mock 패턴 전면 수정 필요 — 리스크 대비 효과 낮음 |
| `AiReviewResult` 속성 분리 | 11개 속성을 `CategoryFeedback` 서브클래스로 분리하면 notifier 10개 파일 전면 수정 필요 — 현재 기능 무결성 우선 |
| notifier 간 score breakdown 중복 | 각 notifier가 서로 다른 포맷(Telegram HTML, Slack attachment, Discord embed, Email HTML)이라 공용 추출 시 유연성 감소 |
| Telegram URL 헬퍼 추출 | `telegram_gate.py`와 `telegram.py`의 Telegram API 호출은 파라미터 구조가 달라 단순 추출 불가 |

---

## 5. 전후 지표 비교

| 지표 | 개선 전 | 개선 후 |
|------|---------|---------|
| **pylint 점수** | 0.00 / 10 | **9.29 / 10** |
| **flake8 경고** | 16건 | **0건** |
| **bandit HIGH** | 0건 | **0건** (유지) |
| **단위 테스트** | 292개 통과 | **296개 통과** (+4 버그 테스트) |
| 모듈 docstring | ~5개 | **30개** |
| 중복 코드 패턴 | 7개 | **4개** (3개 제거) |

---

## 6. 회고 (Retrospective)

### 어떤 패턴이 누적됐나

**빠른 기능 추가의 부채:**  
Phase 1~8B에서 기능을 빠르게 추가하면서 `ChangedFile`을 CLI 전용 파일에 별도 정의하거나, GitHub API 헤더를 매 파일마다 복사하는 패턴이 자연스럽게 생겼다.  
이는 "지금 동작하는 코드"를 우선하는 개발 흐름에서 흔히 발생한다.

**문서화 부채:**  
TDD로 테스트는 잘 작성됐지만, docstring은 "동작 확인 후 추가" 방식으로 후순위가 됐다.  
그 결과 pylint가 C 레벨 경고로 점수를 0점으로 내렸다.

**API 확장 시 필드 동기화 누락:**  
알림 채널을 Phase별로 추가하면서 `RepoConfig` DB 모델, UI 폼, config_manager는 업데이트됐지만 REST API `RepoConfigUpdate` 모델과 매핑 코드는 동기화를 놓쳤다.  
이는 단위 테스트가 API 필드 전달을 충분히 검증하지 않았기 때문이다.

### 다음 Phase에서 지켜야 할 규칙

1. **새 알림 채널 추가 시**: `RepoConfig` 모델 → `RepoConfigData` → `RepoConfigUpdate`(API) → UI 폼 4곳을 체크리스트로 함께 업데이트
2. **새 dataclass 정의 시**: 2곳에서 필요하면 즉시 공용 모듈로 추출
3. **GitHub API 호출 시**: `github_api_headers()` 헬퍼 반드시 사용
4. **모듈 생성 시**: 첫 줄에 1줄 docstring 작성 (TDD와 동시에)
5. **복잡한 오케스트레이션 함수**: 의도적 복잡성이면 `# pylint: disable=...` 명시

---

## 7. 검증 명령

```bash
make test   # 296 passed
make lint   # pylint 9.29/10, flake8 0, bandit HIGH 0
```
