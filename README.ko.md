<div align="center">

# 🛡️ SCAManager

**GitHub push · PR 마다 정적 분석 + Claude AI 리뷰 — 채점하고, 알리고, PR 을 게이트한다.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-7028%2B_total_(6857_unit_%2B_171_integration)-brightgreen)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_CI-brightgreen)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen)](src/)

[🇺🇸 English](README.md)

</div>

셀프 호스팅 FastAPI 서비스. GitHub webhook(`push` · PR `opened`/`synchronize`/`reopened`)이
발화하면 변경을 100점으로 채점해 기록하고, PR 을 게이트하고, 결과를 배달한다. 밖으로 나가는
것은 Anthropic API 와 켠 채널뿐.

## 파이프라인

```
POST /webhooks/github   HMAC-SHA256 · 리포별 시크릿
 └─ run_analysis_pipeline()   src/worker/pipeline.py
    ├─ asyncio.gather ─┬─ 정적 분석기 25종 (pylint · bandit · semgrep · eslint · …)
    │                  └─ Claude 리뷰, 49개 언어별 체크리스트
    ├─ calculate_score() → 점수 + 등급 → DB
    ├─ gate (PR)   approve · request changes · Telegram 버튼 · squash merge
    └─ notify      채널 독립 — 하나가 실패해도 나머지는 나간다
```

## 점수

| 항목 | 배점 | 산출 |
|---|---|---|
| 코드 품질 | 25 | error −3 · warning −1 (상한 25) |
| 보안 | 20 | HIGH −7 · LOW/MEDIUM −2 |
| 커밋 메시지 | 15 | Claude 0–20 스케일링 |
| 구현 방향성 | 25 | Claude 0–20 스케일링 |
| 테스트 코드 | 15 | Claude 0–10 스케일링 |

등급 A(90+) · B(75+) · C(60+) · D(45+) · 미만 F. `ANTHROPIC_API_KEY` 가 없으면 AI 3항목이
중립값(13/21/10)이라 상한이 89점. 정본 [`src/constants.py`](src/constants.py).

## 게이트·전달

기본값 — 75+ approve · 50 미만 request changes · 75+ squash merge. `approve_mode` 가 `auto` 면
GitHub 에 바로 쓰고 `semi-auto` 면 Telegram 인라인 버튼으로 묻는다. 임계 경계 밴드는 2차 모델
검증을 거치고, 못 돌면 막는다. CI 대기로 실패한 머지는 큐에서 재시도한다.

채널(리포별) — Telegram · GitHub PR/커밋 댓글 · Issue · Discord · Slack · Email · 범용 webhook ·
n8n. UI·알림·프롬프트는 한국어/English/日本語.

## 빠른 시작

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install          # pip + npm
make css-build        # Tailwind 번들 (없으면 404)
python -m pip install pre-commit && python -m pre_commit install
cp .env.example .env  # 값을 채운다
make run              # uvicorn :8000 + 마이그레이션
```

기동 필수 — `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID`. OAuth 3종
(`GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET` · `SESSION_SECRET` 32자 이상 랜덤)은 placeholder
기본값이 있어 프로세스는 떠도 로그인이 안 된다. 로그인 후 **+ 리포 추가** 로 고르면 webhook 이
생기고 다음 push 부터 분석된다. 서버 없이 — `python -m src.cli review --base main`.

## 배포

**Railway** — 리포 연결 + PostgreSQL 플러그인, 위 변수 + `ANTHROPIC_API_KEY` · `APP_BASE_URL`.
`APP_BASE_URL` 은 반드시 `https://` — 아니면 OAuth redirect·webhook 이 `http://` 로 등록돼 둘 다
실패한다 ([railway.md](docs/runbooks/railway.md)).

**온프레미스** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
`DATABASE_URL_FALLBACK` 을 주면 보조 DB 로 자동 failover.

## 문서

[architecture](docs/architecture.md) · [workflow/](docs/workflow/) ·
[env-vars](docs/reference/env-vars.md) · [runbooks/](docs/runbooks/) · [STATE](docs/STATE.md) · [CONTRIBUTING](CONTRIBUTING.md)

취약점은 [비공개 신고](https://github.com/xzawed/SCAManager/security/advisories/new)로. [MIT License](LICENSE) © xzawed
