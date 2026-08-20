<div align="center">

# 🛡️ SCAManager

**GitHub push · PR 마다 정적 분석 + Claude AI 리뷰 — 채점 · 알림 · PR 게이트.**

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/Tests-7187%2B_total_(7005_unit_%2B_182_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[🇺🇸 English](README.md)

</div>

셀프 호스팅 FastAPI 서비스, Python 3.12 — 셀프 호스팅이지 밀폐는 아니다. GitHub API 와
`DATABASE_URL` 은 파일·점수를 불가피하게 보고, Anthropic 은 diff 를, 켠 채널은 요약을 받고,
일부 분석기는 네트워크를 탄다. 전체 표와 끄는 법: [SECURITY.md](SECURITY.md#data-egress).

## 파이프라인

```
POST /webhooks/github — HMAC-SHA256 · 리포별 시크릿 · push, PR opened/synchronize/reopened
 └─ run_analysis_pipeline()  src/worker/pipeline.py
    gather   정적 분석기 25종(27개 언어) + Claude 리뷰(49개 언어별 체크리스트)
    score    calculate_score() → DB
    gate     PR approve · request changes · Telegram 버튼 · squash merge
    notify   채널은 서로 독립 — 하나 실패해도 나머지는 나간다
```

배포가 설치하기로 계약한 분석기가 없으면 분석을 incomplete 로 표시하고 auto-merge 를 막는다 —
아무것도 안 돌고 만점을 받는 일이 없도록.

## 점수

100점 만점 — 코드 품질 25 (error −3 · warning −1) · 보안 20 (HIGH −7 · LOW/MEDIUM −2) ·
커밋 메시지 15 · 구현 방향성 25 · 테스트 코드 15. 뒤 3항은 Claude 가 raw 0–20 / 0–20 / 0–10 으로
주고 스케일링한다. 등급 **A** 90+ · **B** 75+ · **C** 60+ · **D** 45+ · 미만 **F**.

AI 리뷰가 쓸 수 있는 결과를 못 내면 — 키 부재 · 비활성 · 빈 diff · API/파싱 오류 — 그 3항이
중립값 13 / 21 / 10 으로 떨어져 **상한이 89점**이 된다. 돌지도 않은 리뷰가 A 로 보이는 일은 없다.
정본은 [`src/constants.py`](src/constants.py).

## 게이트·전달

75+ approve · 50 미만 request changes · 75+ squash merge. `approve_mode=auto` 는 GitHub 에 즉시
반영하고, `semi-auto` 는 Telegram 버튼으로 먼저 묻는다. CI 대기로 실패한 머지는 큐에 넣어
재시도한다.

2차 모델 검증자는 **opt-in** 이다 — `OPENAI_API_KEY` 를 넣으면 머지 자격을 갖춘 점수를 **전부**
다시 보고 diff 에 심긴 prompt injection 을 찾는다. 상한은 의도적으로 두지 않는다 — 인젝션은
*높은* 점수를 노리기 때문이다. 키가 없으면 그냥 안 돈다. 없다고 머지를 막지는 않는다.

알림 채널은 리포별 설정이고 서로 독립이다 — Telegram · Discord · Slack · Email · webhook ·
n8n · GitHub 커밋 댓글 · GitHub Issue. (PR 을 approve 하는 것은 게이트가 GitHub 에 직접 하는
행위이지 notifier 가 아니다.) UI·알림·프롬프트는 **ko · en · ja**.

## 빠른 시작

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install         # pip install -r requirements-dev.txt + npm install
make css-build       # Tailwind 번들 — gitignore 대상. 템플릿이 기대는 유틸리티 레이어다
cp .env.example .env
make run             # uvicorn :8000 --reload + 부팅 시 마이그레이션
```

`make` 이 없으면 위 세 타깃은 각각 명령 한두 줄이니 [Makefile](Makefile) 에서 그대로 읽어 쓴다.

기동 필수는 `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` — 기본값 없는 설정은 이
셋뿐이다. `GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET` · `SESSION_SECRET`(32자 이상 랜덤)은
placeholder 가 있어 프로세스는 뜨지만, 바꾸기 전까지 OAuth 로그인은 안 된다.

로그인 후 **+ 리포 추가** — webhook 이 생성되고 다음 push 부터 분석한다.
서버 없이: `python -m src.cli review --base main`.

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
[private advisory](https://github.com/xzawed/SCAManager/security/advisories/new) 로 신고한다.
[MIT](LICENSE) © xzawed
