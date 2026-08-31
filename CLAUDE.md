# SCAManager

GitHub Push/PR → 정적 분석 + AI 리뷰 → 점수·등급 → 알림(Telegram·GitHub·Discord·Slack·Email·n8n)
→ 점수 기반 PR Gate·웹 대시보드.
구조 = [architecture.md](docs/architecture.md), 수치 = [docs/STATE.md](docs/STATE.md).

## 작업 절차

1. **브랜치** — `git checkout main && git pull && git checkout -b <type>/<scope>`
   접두사: `feat/` `fix/` `chore/` `docs/`. **`main` 에 직접 커밋·push 하지 않는다.**
2. **영역 문서를 연다** — 아래 표에서 건드릴 영역 하나. 세부 절차가 거기 있다.
3. **테스트 먼저** — 행동 변경은 구현 전에 실패하는 테스트를 쓴다(측정-only 는 기록 테스트 초록 허용).
   `in`·`==`·집합 소속으로 **부류를 판정하는 식**을 쓰면 그 자리에서
   **부분문자열≠상태 · 거짓초록 1건 심기 · 못 재면 red**.
   정본은 [verify.md](docs/workflow/verify.md) 「판정식을 쓸 때」 3~5.
4. **구현**
5. **검증** — [verify.md](docs/workflow/verify.md) 의 절차를 그대로 따른다.
6. **PR** — `gh pr create --body-file <임시파일>`. URL 안내 금지.
7. **머지는 사용자가 한다.**

## 영역 문서

| 건드리는 곳 | 문서 |
|---|---|
| `src/worker/pipeline.py` · `src/analyzer/**` · `src/scorer/**` | [pipeline.md](docs/workflow/pipeline.md) |
| `src/gate/**` · `src/notifier/**` · `src/webhook/**` | [gate-notify.md](docs/workflow/gate-notify.md) |
| `src/models/**` · `src/repositories/**` · `alembic/**` | [db.md](docs/workflow/db.md) |
| `railway.toml` · `nixpacks.toml` · `src/config.py` · `.env.example` | [deploy.md](docs/workflow/deploy.md) |
| `tests/**` · `e2e/**` · `scripts/**` · `.github/workflows/**` | [verify.md](docs/workflow/verify.md) |
| `src/templates/**` · `src/static/**` · `src/ui/**` · `src/i18n/**` | [ui-i18n.md](docs/workflow/ui-i18n.md) |
| `src/auth/**` · `src/crypto.py` · `src/shared/**` · `.pre-commit-config.yaml` | [security.md](docs/workflow/security.md) |
| `src/api/**` · `src/config_manager/**` · `src/services/**` | [gate-notify.md](docs/workflow/gate-notify.md) + [db.md](docs/workflow/db.md) |
| `src/main.py` · `src/config.py` · `src/constants.py` · `src/database.py` · `src/scheduler.py` · `src/logging_config.py` · `src/middleware/**` | [deploy.md](docs/workflow/deploy.md) |
| `src/github_client/**` · `src/railway_client/**` · `src/verifier/**` · `src/mcp/**` · `src/cli/**` | [gate-notify.md](docs/workflow/gate-notify.md) |

## 명령

```bash
py -3 -m pytest tests/unit -q       # 단위 전체 (push 전 필수)
py -3 scripts/pre_push_gate.py      # CI 가드를 로컬에서 (--full: pylint·bandit 추가)
py -3 -m pytest e2e/ -p no:asyncio  # E2E (tests/ 와 같이 돌리지 않는다)
```

`make` 이 없는 머신이 있다(이 개발 PC 포함) — `make X` 실패는 환경 문제다. 타깃 정본 = `Makefile`.

최초 설정: `cp .env.example .env` → `py -3 -m pip install -r requirements.txt -r requirements-dev.txt`
→ `npm install && npm run build` → `py -3 -m pre_commit install` → `py -3 -m uvicorn src.main:app --reload`

## 협업 규칙

- 옵션 제시는 장단점 표 + 권장안 1개.
- PR 본문에 사람이 눈으로 확인할 항목 1~3개 — "테스트 통과" 만 적지 않는다.
- 위임 작업 중 스스로 판단한 것은 PR 본문이나 응답 끝에 명시한다.
- 스키마·API·권한·데이터모델 변경은 착수 전 확인받는다. 나머지는 진행하고 보고한다.
- 시각 변경(`templates/`·`static/`)은 사람이 봐야 한다 — 정적 테스트 통과는 근거가 아니다.
- MCP: SELECT 자율, INSERT·UPDATE·DELETE·DDL 과 PII·credential 조회는 사전 승인.
- 문서 수치는 실행 결과를 옮긴다. 코드 좌표는 **줄번호가 아니라 앵커**다 — `path::파일에 실재하는 문자열`(`scripts/check_doc_anchors.py` 가 강제).

## 파일 수정 제한

`alembic/versions/` · `src/templates/*.html` · `railway.toml` · `alembic.ini` 은 테스트 불가
환경에서 훅이 차단한다(로컬 PC·Codespaces 는 허용).

## 코드 주석

한국어를 먼저 쓰고 다음 줄에 영어를 붙인다. `# TODO`·`# type: ignore` 같은 표준 태그는 영어 단독.
관행이지 게이트는 아니다 — `py -3 scripts/i18n_comments/check_bilingual.py src/ --report` 가 비율을 잰다.

## 문서 규칙

🔴 **문서 총량은 늘리지 않는다.**

- 현재 코드 기준만 적는다. 과거 이력·사고 서사·날짜·PR 번호는 git 이 갖고 있다.
- 규칙 나열이 아니라 수행 절차로 적는다 — 금지는 절차 안의 한 줄로 녹인다. 왜 생겼는지는 쓰지 않는다.
- 문서를 고쳐 자수가 늘면 무엇을 뺐는지 PR 본문에 적는다.
- 새 문서 전에 기존 문서에 자리가 없는지 본다.
- 문서 개수·문장 존재를 강제하는 테스트를 만들지 않는다(`len(docs) >= N`, 「이 문장이 살아 있을 것」).
  그런 계약은 축소를 CI red 로 만든다 — 공허화 방어는 「집합이 비었는가」로 충분하다.
- 테스트 수가 바뀌면 `docs/STATE.md` SSOT 불릿 **한 줄만** 고치고 `py -3 scripts/check_docs_sync.py --fix`.
- `src/` 에 파일을 추가·삭제하면 `docs/architecture.md` 트리를 갱신한다.

## 진행 중인 일

GitHub Issues. 여러 세션에 걸치는 작업은 `[WBS]` 추적 Issue 가 진입점이다:
`gh issue list --search "WBS in:title"`
