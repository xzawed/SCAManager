# SCAManager 로컬 도구 스크립트

> **본 디렉토리는 production 의존성 X** — 사용자 로컬에서 1회 실행하는 도구 모음.
> Production code MUST NOT import from `src/scripts/`.

## generate_illustrations.py — UI 일러스트 5장 생성

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
# Dry-run (API 호출 없이 prompt 만 출력). `--dry-run` 은 argparse `store_true` 라
# **기본값이 아니다** — 빼면 곧바로 과금 호출이 나간다.
python -m src.scripts.generate_illustrations --all --dry-run

# 단일 일러스트 (`--name` 은 PROMPTS 5종 이름만 허용)
python -m src.scripts.generate_illustrations --name filter_empty

# 전체 5장 생성 (비용은 아래 §비용)
python -m src.scripts.generate_illustrations --all
```

### 5장 prompt 일람

이름 · 배치 · 사이즈 · 품질의 정본은 [`illustration_prompts.py`](illustration_prompts.py) 의 `PROMPTS` 상수다.
여기 있던 복제 표는 2026-08-17 감사에서 배치 좌표 4건이 **전부** 실측과 어긋나 있었다
(`login.html L40-60` · `dashboard.html L210/678/700` · `overview.html L154-193` · `repo_detail.html L168`)
— 파생 대신 포인터만 남긴다.

**`login_hero` 는 출하되지 않았다** — 대상이던 `login.html` 이 사이클 117(#578)에서 삭제돼
`landing.html` 로 통합됐다. 커밋된 PNG 는 4장(`add_repo_hero` · `dashboard_empty` · `filter_empty`
· `overview_onboarding`)이고 `PROMPTS` 는 5종을 유지한다 — 개수는 아래 §회귀 가드가 고정한다.

### 비용

단가 정본 = [`generate_illustrations.py`](generate_illustrations.py) 모듈 docstring (2026-05 기준).
여기 있던 복제 표에는 `standard 1792×1024` 행이 없어 `add_repo_hero` 가 빠져 있었다 —
그 표만으로는 "~$0.40" 합계를 검산할 수 없다. 실행 전 현재 단가는 OpenAI 가격 페이지에서 재확인할 것.

캐싱 X (DALL-E 3 idempotent 아님 — 동일 prompt도 매번 다른 결과). 한 번 만들고 commit 후 재실행 X.

### 결과 적용 — 완료 (사이클 94 Step 2-B)

이 절차는 이미 끝났다. **재실행하지 말 것.** PNG 4장이 `src/static/illustrations/` 에 커밋됐고
마크업은 `add_repo.html` · `dashboard.html` · `overview.html` · `repo_detail.html` 에 들어갔다
(공통 CSS = `src/static/css/illustrations.css`, `base.html` 에서 로드).
현재 참조 지점은 아래로 재측정한다 — 줄 번호를 여기 적으면 다음 편집에서 곧바로 낡는다.

```bash
grep -rn "static/illustrations/" src/templates/ src/static/css/
```

### 회귀 가드

- [`tests/unit/scripts/test_illustration_prompts.py`](../../tests/unit/scripts/test_illustration_prompts.py): 5장 prompt 정의 누락 차단 + 정책 정합 (텍스트 X / isometric / 4-테마 호환 키워드 보존)
