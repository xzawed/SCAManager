# 🛡️ SCAManager

**GitHub push · PR 마다 정적 분석 + Claude AI 리뷰 — 채점 · 알림 · PR 게이트.** 셀프 호스팅.
나가는 것은 Anthropic API 와 켠 채널뿐. [🇺🇸 English](README.md)

![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688)
![Tests](https://img.shields.io/badge/Tests-7038%2B_total_(6867_unit_%2B_171_integration)-green)
![E2E](https://img.shields.io/badge/E2E-121_CI-green)
![pylint](https://img.shields.io/badge/pylint-9.99%2F10-green)

## 파이프라인

```
POST /webhooks/github — HMAC-SHA256 · 리포별 시크릿 · push, PR opened/synchronize/reopened
 └─ run_analysis_pipeline() src/worker/pipeline.py
    gather 정적 분석기 25종 + Claude 리뷰(49개 언어별 체크리스트) → calculate_score() → DB
    → gate(PR) approve · request changes · Telegram 버튼 · squash merge
    → notify 채널 독립 — 하나 실패해도 나머지는 나간다
```

## 점수

코드 품질 25 (error −3 · warning −1) · 보안 20 (HIGH −7 · LOW/MEDIUM −2) · 커밋 메시지 15 ·
구현 방향성 25 · 테스트 코드 15 (뒤 3항 Claude 0–20 · 0–20 · 0–10 스케일링) = 100.
A(90+) · B(75+) · C(60+) · D(45+) · 미만 F — 정본 [`src/constants.py`](src/constants.py).
`ANTHROPIC_API_KEY` 없으면 AI 3항목이 중립값(13/21/10) — 상한 89점.

## 게이트·전달

기본 75+ approve · 50 미만 request changes · 75+ squash merge. `approve_mode=auto` 는 GitHub 즉시
반영, `semi-auto` 는 Telegram 버튼 확인. 경계 밴드는 2차 모델 검증 — 못 돌면 막는다. CI 대기
실패 머지는 큐 재시도. 채널(리포별) — Telegram · GitHub 댓글/Issue · Discord · Slack · Email ·
webhook · n8n. UI·알림·프롬프트 ko/en/ja.

## 빠른 시작

```bash
make install     # pip + npm
make css-build   # Tailwind 번들 — 없으면 404
python -m pip install pre-commit && python -m pre_commit install
cp .env.example .env
make run         # uvicorn :8000 + 마이그레이션
```

기동 필수 — `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID`. OAuth 3종
(`GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET` · `SESSION_SECRET` 32자+ 랜덤)은 placeholder
기본값이라 프로세스는 떠도 로그인 불가. **+ 리포 추가** → webhook 생성 · 다음 push 부터 분석.
서버 없이 — `python -m src.cli review --base main`.

## 배포

**Railway** — 리포 연결 + PostgreSQL 플러그인 + 위 변수 · `ANTHROPIC_API_KEY` · `APP_BASE_URL`.
`APP_BASE_URL` 은 `https://` 필수 — `http://` 면 OAuth redirect·webhook 이 그대로 등록돼 둘 다
실패([railway.md](docs/runbooks/railway.md)).
**온프레미스** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers` ·
`DATABASE_URL_FALLBACK` → 보조 DB 자동 failover.

[architecture](docs/architecture.md) · [env-vars](docs/reference/env-vars.md) ·
[runbooks/](docs/runbooks/) ·
[취약점 신고](https://github.com/xzawed/SCAManager/security/advisories/new) · [MIT](LICENSE) © xzawed
