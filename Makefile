.PHONY: install test test-v test-fast test-slow test-cov test-file test-isolated test-local lint lint-strict lint-js gate run migrate revision review check-memory-refs install-playwright test-e2e test-e2e-headed test-perf perf-report css-install css-build css-dev

# 의존성 설치 (개발 환경 — 테스트/E2E + CSS 빌드 포함)
# Install dependencies (development environment — includes tests/E2E + CSS build).
install:
	pip install -r requirements-dev.txt
	npm install

# CSS 빌드 (Tailwind v4 — 프로덕션 minified)
# Build Tailwind v4 CSS (production minified).
css-build:
	npm run build

# CSS 감시 빌드 (Tailwind v4 — 개발 watch 모드)
# Watch and rebuild Tailwind v4 CSS (development watch mode).
css-dev:
	npm run dev:css

# Node.js 의존성만 설치
# Install Node.js dependencies only.
css-install:
	npm install

# 테스트 (빠른 실행, 전체)
# Run all tests (quick output).
test:
	python -m pytest tests/ -q

# 테스트 (상세 출력)
# Run all tests (verbose output).
test-v:
	python -m pytest tests/ -v

# 빠른 단위 테스트만 (tests/integration/ 의 실 subprocess 테스트 제외)
# Unit tests only — excludes real subprocess tests in tests/integration/.
test-fast:
	python -m pytest tests/ -m "not slow" -q

# 통합 테스트만 (tests/integration/ — pylint/flake8/bandit/semgrep 실제 실행)
# Integration tests only — runs real pylint/flake8/bandit/semgrep subprocesses.
test-slow:
	python -m pytest tests/ -m "slow" -q

# Windows 로컬 환경용 — subprocess(slow) 154개 제외, 짧은 traceback, 헤더 없음
# Local Windows run — excludes 154 slow subprocess tests, short tracebacks, no header.
test-local:
	python -m pytest tests/ -m "not slow" --tb=short -q --no-header

# 테스트 + 커버리지
# Run tests and generate coverage report.
test-cov:
	python -m pytest tests/ --cov=src --cov-report=term-missing -q

# 특정 파일 테스트 (예: make test-file f=tests/test_pipeline.py)
# Run a specific test file (e.g. make test-file f=tests/test_pipeline.py).
test-file:
	python -m pytest $(f) -v

# 환경변수 격리 테스트 — .env stash + 관련 env vars unset 후 실행 (로컬 devcontainer 용)
# Isolated test run — stashes .env and unsets credentials (for local devcontainer).
# 프로덕션 자격증명이 있는 .env 가 conftest 기본값을 덮어써 7~10개 테스트 실패하는 경우 해결.
# Fixes 7–10 test failures caused by a production .env overriding conftest defaults.
test-isolated:
	@( trap 'mv -f .env.test-stash .env 2>/dev/null' EXIT; \
	   mv .env .env.test-stash 2>/dev/null; \
	   unset GITHUB_TOKEN TELEGRAM_BOT_TOKEN GITHUB_WEBHOOK_SECRET DATABASE_URL \
	         ANTHROPIC_API_KEY TELEGRAM_CHAT_ID API_KEY GITHUB_CLIENT_ID \
	         GITHUB_CLIENT_SECRET SESSION_SECRET APP_BASE_URL \
	         DATABASE_URL_FALLBACK N8N_WEBHOOK_SECRET; \
	   python -m pytest tests/ -q )

# 코드 품질 검사
# 정적 분석 **점검**(inspection) — 전부 advisory 다. 게이트가 아니다.
# 🔴 게이트는 `make gate` 와 CI `lint-src` job 이다. 이 타깃은 위반을 **보여주는** 용도이므로
# `|| true` 가 의도적이다 — 세 도구의 출력을 한 번에 보려면 앞 도구가 죽으면 안 된다.
# Inspection only (advisory by design); the gate is `make gate` / CI `lint-src`.
# Code quality checks (pylint + flake8 + bandit).
lint:
	pylint src/ || true
	flake8 src/ || true
	bandit -r src/ -q || true

# pylint 회귀 가드 — score < 9.90 시 fail (사이클 87 Tier B-1, baseline 9.94 보수적 floor)
# pylint regression guard — fail when score < 9.90 (cycle 87 Tier B-1, 9.94 baseline conservative floor)
# 사이클 86 회고 관점 4 P0 — pylint drift 자동 감지 부재 회복. flake8/bandit 은 기존 `make lint` 보존
# Cycle 86 retro perspective 4 P0 — recover from pylint drift detection gap. flake8/bandit kept in `make lint`
lint-strict:
	pylint --fail-under=9.90 src/

# JS 린트 — eslint-plugin-html 로 src/templates/*.html 인라인 스크립트 검사
# JS lint — checks inline scripts in src/templates/*.html via eslint-plugin-html
# Jinja2 {{ }} 인터폴레이션 포함 5개 파일은 .eslintignore 로 제외 (파서 오류 방지)
# 5 files with Jinja2 {{ }} interpolations excluded via .eslintignore (prevents parse errors)
lint-js:
	npx eslint "src/templates/**/*.html" --quiet || true

# Phase 완료 게이트 — 테스트 + 정적 분석. 🔴 이름대로 **실패할 수 있어야** 한다.
# 이전 판은 세 린터를 전부 `|| true` 로 삼켜 **구조적으로 실패 불가**였다(회고 D13):
# "게이트 통과" 라는 보고가 아무것도 보장하지 않았다.
# Phase completion gate — must actually be able to fail; the old version swallowed every linter.
#
# 🔴 **최종 강제면은 CI 의 `lint-src` job 이다** — 로컬 fail-closed 는 강제력이 아니라 마찰이고,
# 여기서만 막으면 사람이 이 타깃을 안 쓰게 된다(Grok 적대 검토 2026-07-20). 이 타깃은
# CI 와 **같은 기준**을 로컬에서 미리 보는 용도다.
# The authoritative gate is CI's `lint-src` job; this mirrors it locally for early feedback.
gate:
	python -m pytest tests/ -q
	pylint --fail-under=9.90 src/
	bandit -r src/ -q
# 🔴 flake8 은 이 게이트에 넣지 않는다 — src/ 에 실측 14 E501 + 1 E131 = 15건이 있어 강제하면
# 12개 파일을 미용 목적으로 고쳐야 한다(정책 17 안정성 > 권장 규격). 실질 결함인 F401/F841 은
# CI `lint-changed-tests` job 이 담당한다. 전체 위반 열람은 `make lint`.
# flake8 is intentionally excluded here; see CI lint-changed-tests for the meaningful subset.

# DB 마이그레이션
# Run database migrations.
migrate:
	alembic upgrade head

# 로컬 코드리뷰 (CLI)
# Local code review via CLI.
review:
	python -m src.cli review

# 메모리 슬러그 교차 점검 — 문서 참조 vs 실제 파일 비교, 스테일 어노테이션 탐지
# Memory slug cross-check — compare doc references vs actual files, detect stale annotations.
check-memory-refs:
	python scripts/check_memory_refs.py

# 개발 서버 실행
# Start the development server (port 8000).
run:
	uvicorn src.main:app --reload --port 8000

# 새 마이그레이션 생성 (예: make revision m="add column")
# Generate a new migration (e.g. make revision m="add column").
revision:
	alembic revision --autogenerate -m "$(m)"

# Playwright 브라우저 설치
# Install Playwright and Chromium browser.
install-playwright:
	pip install playwright pytest-playwright
	playwright install chromium

# E2E 테스트 (headless)
# Run E2E tests in headless mode.
test-e2e:
	python -m pytest e2e/ -v -p no:asyncio

# E2E 테스트 (브라우저 표시)
# Run E2E tests with browser visible.
test-e2e-headed:
	python -m pytest e2e/ -v -p no:asyncio --headed

# 성능 테스트 (pytest 기반, 로컬 E2E 서버)
# Run performance tests (pytest-based, local E2E server).
test-perf:
	python -m pytest e2e/ -m perf -v --timeout=120 -p no:asyncio

# 성능 리포트 생성 (로컬 + 운영) — PYTHONIOENCODING=utf-8 로 Windows UnicodeEncodeError 방지
# Generate performance report (local + production) — PYTHONIOENCODING=utf-8 prevents Windows UnicodeEncodeError.
perf-report:
	PYTHONIOENCODING=utf-8 python scripts/perf_measure.py
