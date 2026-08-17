<div align="center">

# 🛡️ SCAManager

**GitHub push · PR 마다 정적 분석 + Claude AI 리뷰 — 채점하고, 알리고, PR 을 게이트한다.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-7028%2B_total_(6857_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)

[🇺🇸 English](README.md)

</div>

---

셀프 호스팅 FastAPI 서비스. GitHub webhook 이 `push` 와 PR `opened` / `synchronize` / `reopened`
에서 발화하면 파이프라인이 변경을 100점으로 채점해 기록하고, PR 을 게이트하고, 결과를 배달한다.
전부 당신의 인프라에서 돈다 — 밖으로 나가는 것은 Anthropic API 와 당신이 켠 채널뿐이다
([SECURITY.md](SECURITY.md)).

## 변경 하나가 흐르는 길

```
POST /webhooks/github          HMAC-SHA256, 리포별 시크릿
  └─ run_analysis_pipeline()   src/worker/pipeline.py
       ├─ asyncio.gather ─┬─ 정적 분석기 25종 (pylint · bandit · semgrep · eslint · tsc ·
       │                  │   shellcheck · cppcheck · slither · rubocop · golangci-lint · …)
       │                  └─ Claude 리뷰, 49개 언어별 체크리스트
       ├─ calculate_score() → 점수 + 등급 → DB
       ├─ gate  (PR 이벤트)   approve · request changes · Telegram 버튼 · squash merge
       └─ notify              채널은 독립 — 하나가 실패해도 나머지는 나간다
```

## 점수

| 항목 | 배점 | 어떻게 움직이나 |
|---|---|---|
| 코드 품질 | 25 | error −3, warning −1 (warning 상한 25) |
| 보안 | 20 | HIGH −7, LOW/MEDIUM −2 |
| 커밋 메시지 | 15 | Claude 0–20, 스케일링 |
| 구현 방향성 | 25 | Claude 0–20, 스케일링 |
| 테스트 코드 | 15 | Claude 0–10, 스케일링 |

등급 A(90+) · B(75+) · C(60+) · D(45+) · 그 미만 F. `ANTHROPIC_API_KEY` 가 없으면 AI 3항목이
중립 기본값(13 / 21 / 10)으로 채워져 한 번의 실행은 최대 89점이 된다.
정본 [`src/constants.py`](src/constants.py).

## 게이트와 전달

기본값 — 75 이상 approve, 50 미만 request changes, 75 이상 squash merge. `approve_mode=auto` 는
GitHub 에 바로 쓰고 `semi-auto` 는 Telegram 인라인 버튼으로 사람에게 묻는다. 머지 임계 바로 위
경계 밴드의 점수는 2차 모델 검증을 한 번 더 거치고, 그 검증이 돌지 못하면 막힌 채로 둔다.
CI 가 아직 돌고 있어 실패한 머지는 큐에 넣고 재시도한다.

채널(리포별) — Telegram · GitHub PR 댓글 · 커밋 댓글 · Issue · Discord · Slack · Email ·
범용 webhook · n8n. UI · 알림 · 프롬프트는 한국어 / English / 日本語.

## 빠른 시작

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install                        # pip + npm
make css-build                      # Tailwind 번들 — gitignore 대상, 없으면 404
python -m pip install pre-commit && python -m pre_commit install
cp .env.example .env                # 값을 채운다
make run                            # uvicorn :8000, 기동 시 마이그레이션 실행
```

기동을 막는 것은 `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` 3개다.
`GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET` · `SESSION_SECRET`(32자 이상 랜덤)은 placeholder
기본값이 있어 프로세스는 뜨지만 OAuth 로그인이 동작하지 않는다.

GitHub 로 로그인해 **+ 리포 추가** 에서 리포를 고르면 webhook 이 만들어지고 다음 push 부터
분석된다. 서버 없이 로컬에서 보려면:

```bash
python -m src.cli review --base main    # ANTHROPIC_API_KEY 필요
```

## 배포

**Railway** — 리포를 연결하고 PostgreSQL 플러그인을 추가한 뒤 위 변수 + `ANTHROPIC_API_KEY` ·
`APP_BASE_URL` 을 넣는다. `APP_BASE_URL` 은 반드시 `https://` 주소로 — 없으면 OAuth redirect 와
webhook 이 `http://` 로 등록돼 둘 다 실패한다 ([`docs/runbooks/railway.md`](docs/runbooks/railway.md)).

**온프레미스** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
`DATABASE_URL_FALLBACK` 을 주면 보조 DB 로 자동 failover 한다.

## 문서

[`docs/architecture.md`](docs/architecture.md) 모듈 지도와 데이터 흐름 ·
[`docs/workflow/`](docs/workflow/) 영역별 절차 ·
[`docs/reference/env-vars.md`](docs/reference/env-vars.md) 전체 환경변수 ·
[`docs/runbooks/`](docs/runbooks/) 운영 · [`docs/STATE.md`](docs/STATE.md) 현재 수치 ·
[CONTRIBUTING.md](CONTRIBUTING.md)

취약점은 공개 Issue 가 아니라 [비공개 신고](https://github.com/xzawed/SCAManager/security/advisories/new)로. [MIT License](LICENSE) © xzawed
