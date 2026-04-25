.PHONY: install test test-v test-fast test-slow test-cov test-file test-isolated lint gate run migrate revision review install-playwright test-e2e test-e2e-headed

# 의존성 설치 (개발 환경 — 테스트/E2E 포함)
# Install dependencies (development environment — includes tests/E2E).
install:
	pip install -r requirements-dev.txt

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
# Code quality checks (pylint + flake8 + bandit).
lint:
	pylint src/ || true
	flake8 src/ || true
	bandit -r src/ -q || true

# Phase 완료 게이트 — 테스트 + 정적 분석 한번에
# Phase completion gate — tests + static analysis in one command.
gate:
	python -m pytest tests/ -q
	pylint src/ || true
	flake8 src/ || true
	bandit -r src/ -q || true

# DB 마이그레이션
# Run database migrations.
migrate:
	alembic upgrade head

# 로컬 코드리뷰 (CLI)
# Local code review via CLI.
review:
	python -m src.cli review

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
