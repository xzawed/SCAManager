.PHONY: install test test-v test-cov lint run migrate review install-playwright test-e2e test-e2e-headed

# 의존성 설치 (개발 환경 — 테스트/E2E 포함)
install:
	pip install -r requirements-dev.txt

# 테스트 (빠른 실행)
test:
	python -m pytest tests/ -q

# 테스트 (상세 출력)
test-v:
	python -m pytest tests/ -v

# 테스트 + 커버리지
test-cov:
	python -m pytest tests/ --cov=src --cov-report=term-missing -q

# 특정 파일 테스트 (예: make test-file f=tests/test_pipeline.py)
test-file:
	python -m pytest $(f) -v

# 코드 품질 검사
lint:
	pylint src/ || true
	flake8 src/ || true
	bandit -r src/ -q || true

# DB 마이그레이션
migrate:
	alembic upgrade head

# 로컬 코드리뷰 (CLI)
review:
	python -m src.cli review

# 개발 서버 실행
run:
	uvicorn src.main:app --reload --port 8000

# 새 마이그레이션 생성 (예: make revision m="add column")
revision:
	alembic revision --autogenerate -m "$(m)"

# Playwright 브라우저 설치
install-playwright:
	pip install playwright pytest-playwright
	playwright install chromium

# E2E 테스트 (headless)
test-e2e:
	python -m pytest e2e/ -v -p no:asyncio

# E2E 테스트 (브라우저 표시)
test-e2e-headed:
	python -m pytest e2e/ -v -p no:asyncio --headed
