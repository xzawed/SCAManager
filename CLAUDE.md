# SCAManager

GitHub Push/PR 이벤트 → 정적 분석 + AI 리뷰 → 점수·등급 → 알림(Telegram·GitHub·Discord·Slack·Email·n8n)
→ 점수 기반 PR Gate(Approve·자동 Merge). 웹 대시보드 포함.

구조는 [`docs/architecture.md`](docs/architecture.md), 현재 수치는 [`docs/STATE.md`](docs/STATE.md).

---

## 작업 절차

어떤 작업이든 이 순서다.

1. **브랜치** — `git checkout main && git pull && git checkout -b <type>/<scope>`
   접두사: `feat/` `fix/` `chore/` `docs/`. **`main` 에 직접 커밋·push 하지 않는다.**
2. **영역 워크플로를 연다** — 아래 표에서 건드릴 영역의 문서 하나. 거기에 그 영역의 순서가 있다.
3. **테스트 먼저** — 구현 전에 실패하는 테스트를 쓴다.
4. **구현**
5. **검증** — [`docs/workflow/verify.md`](docs/workflow/verify.md) 의 절차를 그대로 따른다.
6. **PR** — `gh pr create --body-file <임시파일>`. URL 안내 대신 직접 만든다.
7. **머지는 사용자가 한다.**

## 영역별 수행 문서

| 건드리는 곳 | 문서 |
|---|---|
| `src/worker/pipeline.py` · `src/analyzer/**` · `src/scorer/**` | [pipeline.md](docs/workflow/pipeline.md) |
| `src/gate/**` · `src/notifier/**` · `src/webhook/**` | [gate-notify.md](docs/workflow/gate-notify.md) |
| `src/models/**` · `src/repositories/**` · `alembic/**` | [db.md](docs/workflow/db.md) |
| `railway.toml` · `nixpacks.toml` · `src/config.py` · `.env.example` | [deploy.md](docs/workflow/deploy.md) |
| `tests/**` · `e2e/**` · `.github/workflows/ci.yml` | [verify.md](docs/workflow/verify.md) |
| `src/templates/**` · `src/static/**` · `src/ui/**` · `src/i18n/**` | [ui-i18n.md](docs/workflow/ui-i18n.md) |
| `src/auth/**` · `src/crypto.py` · `src/shared/ssrf.py` · `.pre-commit-config.yaml` | [security.md](docs/workflow/security.md) |

---

## 명령

```bash
py -3 -m pytest tests/unit -q          # 단위 전체 (push 전 필수)
py -3 scripts/pre_push_gate.py         # CI 가드를 로컬에서 (--full 이면 pylint·bandit 추가)
py -3 -m pytest e2e/ -p no:asyncio     # E2E (tests/ 와 같이 돌리지 않는다)
```

`make` 이 없는 머신이 있다(이 개발 PC 포함). `make X` 실패는 환경 문제이지 리포 문제가 아니다.
전체 타깃은 `Makefile` 이 정본이다.

최초 설정: `cp .env.example .env` → `py -3 -m pip install -r requirements.txt requirements-dev.txt`
→ `npm install && npm run build` → `py -3 -m pre_commit install` → `py -3 -m uvicorn src.main:app --reload`

---

## 협업 규칙

- **옵션을 제시할 때** 장단점 표 + 권장안 1개를 함께 낸다.
- **PR 본문에** 사용자가 눈으로 확인할 항목 1~3개를 적는다. "테스트 통과" 만 적지 않는다.
- **위임받은 작업 중 스스로 판단한 것**은 PR 본문이나 응답 끝에 명시한다.
- **스키마·API·권한·데이터모델 변경**은 착수 전에 확인받는다. 나머지는 진행하고 보고한다.
- **시각 변경**(`templates/` · `static/`)은 사람이 봐야 한다 — 정적 테스트 통과가 근거가 아니다.
- **MCP**: SELECT 는 자율, INSERT·UPDATE·DELETE·DDL 과 PII·credential 조회는 사전 승인.
- **수치를 문서에 적을 때** 실행 결과를 그대로 옮긴다. 추정값·기억값을 쓰지 않는다.
- **`file:line` 인용은 `grep -n` 실측값**이어야 한다.

## 파일 수정 제한

`alembic/versions/` · `src/templates/*.html` · `railway.toml` · `alembic.ini` 은
테스트를 돌릴 수 없는 환경에서 훅이 차단한다. 로컬 PC·Codespaces 에서는 허용된다.

## 문서 규칙

🔴 **문서 총량은 늘리지 않는다.** 이 리포는 문서가 472,746자까지 부풀어 한 번 전면 개편했다.
부풀린 것은 규칙 자체가 아니라 **규칙마다 붙은 근거·전례·예외 설명**이었다.

- **현재 코드 기준만 적는다.** 과거 이력·사고 서사·날짜·PR 번호·세션 ID 는 적지 않는다 — git 이 갖고 있다.
- **규칙 나열이 아니라 수행 절차로 적는다.** 「X 하지 마라(왜냐하면…)」 대신 「① A ② B ③ C」.
  금지는 절차 안의 한 줄로 녹인다.
- **왜 이 규칙이 생겼는지 쓰지 않는다.** 무엇을 하는지만 쓴다.
- **줄이면서 늘리지 않는다** — 문서를 고칠 때 그 파일의 자수가 늘면 무엇을 뺐는지 PR 본문에 적는다.
- **문서 개수·문장 존재를 강제하는 테스트를 만들지 않는다**(`len(docs) >= N`, 「이 문장이 살아 있을 것」).
  그런 계약은 문서를 줄이면 CI 가 red 가 되게 만들어 축소 자체를 막는다. 공허화 방어는
  「집합이 비었는가」로 충분하다.
- 문서를 새로 만들기 전에 기존 문서에 들어갈 자리가 없는지 본다.
- 테스트 수가 바뀌면 `docs/STATE.md` 의 SSOT 불릿 **한 줄만** 고치고
  `py -3 scripts/check_docs_sync.py --fix` 를 돌린다.
- `src/` 에 파일을 추가·삭제하면 `docs/architecture.md` 트리를 갱신한다.

## 진행 중인 일

GitHub Issues. 여러 세션에 걸치는 작업은 `[WBS]` 추적 Issue 가 진입점이다:
`gh issue list --search "WBS in:title"`
