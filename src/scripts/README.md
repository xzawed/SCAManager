# SCAManager 로컬 도구 스크립트

> **본 디렉토리는 production 의존성 X** — 사용자 로컬에서 1회 실행하는 도구 모음.
> Production code MUST NOT import from `src/scripts/`.

## generate_illustrations.py — UI 일러스트 5장 생성 (사이클 93 Step 2)

OpenAI DALL-E 3 API로 SCAManager UI 일러스트 5장 생성. 결과는 `src/static/illustrations/`에 commit하여 [base.html](../templates/base.html) 등에서 정적 자산으로 참조.

### 사전 준비

1. **OpenAI API 키 발급** — https://platform.openai.com/api-keys
2. **로컬 환경 변수 설정**:
   ```bash
   export OPENAI_API_KEY="sk-..."
   # 또는 .env 파일에 추가 (이미 .env.example 에 항목 존재)
   ```
3. **의존성 설치** (이미 설치되어 있을 수 있음):
   ```bash
   pip install -r requirements-dev.txt
   ```

### 사용법

```bash
# Dry-run (API 호출 없이 5장 prompt 만 출력 — 검토용 default)
python -m src.scripts.generate_illustrations --all --dry-run

# 단일 일러스트 (예: login_hero)
python -m src.scripts.generate_illustrations --name login_hero

# 전체 5장 생성 (~$0.40)
python -m src.scripts.generate_illustrations --all
```

### 5장 prompt 일람

| 이름 | 배치 | 사이즈 | 품질 |
|------|------|--------|------|
| `login_hero` | login.html L40-60 form 상단 hero | 1024×1024 | hd |
| `dashboard_empty` | dashboard.html L210/678/700 empty state | 1024×1024 | standard |
| `overview_onboarding` | overview.html L154-193 3-step tutorial | 1792×1024 | hd |
| `add_repo_hero` | add_repo.html form 상단 hero | 1792×1024 | standard |
| `filter_empty` | repo_detail.html L168 filter-empty | 1024×1024 | standard |

상세 prompt 본문 = [`illustration_prompts.py`](illustration_prompts.py) `PROMPTS` 상수 참조.

### 비용 (2026-05 기준 OpenAI 가격)

| 옵션 | 1장 | 5장 합계 |
|------|------|----------|
| standard 1024×1024 | $0.040 | — |
| hd 1024×1024 | $0.080 | — |
| hd 1792×1024 | $0.120 | — |
| **본 5장 합계** | — | **~$0.40** |

캐싱 X (DALL-E 3 idempotent 아님 — 동일 prompt도 매번 다른 결과). 한 번 만들고 commit 후 재실행 X.

### 결과 적용 (Step 2-B 별도 PR)

본 PR (Step 2-A) = 스크립트 + prompt 만. 사용자 로컬 실행 후:
1. `src/static/illustrations/*.png` 5장 commit
2. 별도 PR (Step 2-B): 5 페이지 (login / dashboard / overview / add_repo / repo_detail)에 `<img src="/static/illustrations/...">` 마크업 추가 + 4-테마 호환 CSS

### 회귀 가드

- [`tests/unit/scripts/test_illustration_prompts.py`](../../tests/unit/scripts/test_illustration_prompts.py): 5장 prompt 정의 누락 차단 + 정책 정합 (텍스트 X / isometric / 4-테마 호환 키워드 보존)
