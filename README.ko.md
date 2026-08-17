<div align="center">

# 🛡️ SCAManager

**GitHub push · PR 마다 정적 분석 + Claude AI 리뷰 — 채점 · 알림 · PR 게이트.**

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/Tests-7111%2B_total_(6940_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[🇺🇸 English](README.md)

</div>

셀프 호스팅 FastAPI 서비스, Python 3.12. 밖으로 나가는 것은 Anthropic API 호출과
**켠 알림 채널**뿐이다 ([SECURITY.md](SECURITY.md)).

## 파이프라인

```
POST /webhooks/github — HMAC-SHA256 · 리포별 시크릿 · push, PR opened/synchronize/reopened
 └─ run_analysis_pipeline()  src/worker/pipeline.py
    gather   정적 분석기 25종(27개 언어) + Claude 리뷰(49개 언어별 체크리스트)
    score    calculate_score() → DB
    gate     PR approve · request changes · Telegram 버튼 · squash merge
    notify   채널은 서로 독립 — 하나 실패해도 나머지는 나간다
```

배포가 설치하기로 계약한 분석기 바이너리가 없으면 **배포 회귀**로 처리한다 — 분석을
incomplete 로 표시하고 auto-merge 를 막는다. 아무것도 안 돌고 만점을 받는 일이 없도록.

## 점수

100점 만점 — 코드 품질 25 (error −3 · warning −1) · 보안 20 (HIGH −7 · LOW/MEDIUM −2) ·
커밋 메시지 15 · 구현 방향성 25 · 테스트 코드 15. 뒤 3항은 Claude 가 raw 0–20 / 0–20 / 0–10 으로
주고 스케일링한다. 등급 **A** 90+ · **B** 75+ · **C** 60+ · **D** 45+ · 미만 **F**.

`ANTHROPIC_API_KEY` 가 없으면 그 3항이 중립값 13 / 21 / 10 으로 떨어져 **상한이 89점**이다 —
키가 없는데 A 로 보이는 일은 생기지 않는다. 정본은 [`src/constants.py`](src/constants.py).

## 게이트·전달

75+ approve · 50 미만 request changes · 75+ squash merge. `approve_mode=auto` 는 GitHub 에 즉시
반영하고, `semi-auto` 는 Telegram 버튼으로 먼저 묻는다. 머지 임계 바로 위 **경계 밴드**는 2차
모델 검증을 거치며, 그 검증이 돌지 못하면 막는다. CI 대기로 실패한 머지는 큐에 넣어 재시도한다.

채널은 리포별 설정이고 서로 독립이다 — Telegram · GitHub(리뷰·댓글·Issue) · Discord · Slack ·
Email · webhook · n8n. UI·알림·프롬프트는 **ko · en · ja**.

## 빠른 시작

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install         # pip + npm
make css-build       # Tailwind 번들 — gitignore 대상이라 없으면 404
cp .env.example .env
make run             # uvicorn :8000 + 부팅 시 마이그레이션
```

`make` 이 없는 머신이면 타깃은 얇은 래퍼일 뿐이니 [Makefile](Makefile) 을 보거나 직접:
`py -3 -m pip install -r requirements.txt -r requirements-dev.txt` · `npm ci && npm run build` ·
`py -3 -m uvicorn src.main:app --reload`.

기동 필수는 `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` — 기본값이 없는 설정은
이 셋뿐이다. `GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET` · `SESSION_SECRET`(32자 이상 랜덤)은
placeholder 기본값이 있어 프로세스는 뜨지만, 바꾸기 전까지 OAuth 로그인은 되지 않는다.

로그인 후 **+ 리포 추가** 를 고르면 webhook 이 생성되고 다음 push 부터 분석한다.
서버 없이 쓰려면 `python -m src.cli review --base main`.

## 배포

**Railway** — 리포 연결 · PostgreSQL 플러그인 추가 · 위 변수에 `ANTHROPIC_API_KEY` 와
`https://` 로 시작하는 `APP_BASE_URL` 을 더한다. `http://` 면 그 값이 그대로 등록돼 OAuth
redirect 와 webhook 이 **둘 다** 실패한다 ([railway.md](docs/runbooks/railway.md)).

**온프레미스** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
`DATABASE_URL_FALLBACK` 을 주면 보조 DB 로 자동 failover 한다.

## 문서

[architecture](docs/architecture.md) · [env-vars](docs/reference/env-vars.md) ·
[runbooks](docs/runbooks/) · [CONTRIBUTING](CONTRIBUTING.md) · [현재 수치](docs/STATE.md)

취약점은 공개 Issue 가 아니라
[private advisory](https://github.com/xzawed/SCAManager/security/advisories/new) 로 신고한다
([SECURITY.md](SECURITY.md)).

[MIT](LICENSE) © xzawed
