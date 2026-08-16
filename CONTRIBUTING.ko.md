# SCAManager 기여 가이드

이 프로젝트를 봐주셔서 감사합니다. SCAManager는 셀프 호스팅 코드 품질 서비스입니다 —
이슈, 버그 리포트, Pull Request 모두 환영합니다.

🇺🇸 [English](CONTRIBUTING.md)

> **보안 취약점은 여기가 아닙니다.** 공개 Issue나 PR로 올리지 마시고
> [SECURITY.ko.md](SECURITY.ko.md)의 비공개 신고 절차를 따라주세요.

---

## 목차

- [기여하는 방법](#기여하는-방법)
- [로컬 셋업](#로컬-셋업)
- [테스트 실행](#테스트-실행)
- [린트와 Phase 게이트](#린트와-phase-게이트)
- [브랜치 명명](#브랜치-명명)
- [커밋 메시지](#커밋-메시지)
- [코드 주석 (이중 언어)](#코드-주석-이중-언어)
- [Pull Request 체크리스트](#pull-request-체크리스트)
- [누구나 한 번은 밟는 지뢰 2개](#누구나-한-번은-밟는-지뢰-2개)
- [문서 위치](#문서-위치)

---

## 기여하는 방법

| 종류 | 먼저 할 일 |
|------|-----------|
| **버그 리포트** | 재현 절차 · SCAManager 버전(커밋 SHA) · 관련 로그를 담아 Issue 등록. 토큰은 반드시 가려주세요. |
| **기능 제안** | 코드를 쓰기 전에 문제를 설명하는 Issue를 먼저 열어주세요. 큰 기능은 형태를 먼저 합의해야 머지가 쉽습니다. |
| **작은 수정** (오타 · 깨진 링크 · 명백히 틀린 문서) | Issue 없이 바로 PR 보내주세요. |
| **신규 정적 분석기 / 언어 지원** | Issue를 먼저 열어주세요. 분석기는 공용 프로토콜로 등록되고 점수 산출 경로를 건드립니다. |
| **번역** | UI · 알림 · AI 리뷰 가이드가 영어/한국어/일본어를 지원합니다. [`src/i18n/`](src/i18n/) 참조. |

---

## 로컬 셋업

**Python 3.12+**, **Node.js**(Tailwind 빌드용)가 필요하고, 테스트 이외의 실행에는 **PostgreSQL**이
필요합니다. 테스트 자체는 인메모리 SQLite로 돌기 때문에 DB가 없어도 됩니다.

```bash
git clone https://github.com/xzawed/SCAManager.git
cd SCAManager

cp .env.example .env        # 테스트만 돌릴 거라면 실제 값이 없어도 됩니다

make install                # pip + npm 한 번에
make css-build              # 🔴 필수 — 아래 설명 참조
python -m pip install pre-commit
python -m pre_commit install --hook-type pre-commit --hook-type commit-msg   # 🔴 필수 — 2종 모두
```

마지막 두 단계가 사람들이 건너뛰는 지점이고, 둘 다 **조용히** 실패합니다:

- **`make css-build`** — `src/static/css/dist/tailwind.css` 번들은 빌드 산출물이라 gitignore 대상입니다.
  `base.html`이 이 파일을 무조건 참조하므로, 이 단계를 건너뛰면 모든 페이지가 스타일시트에 대해 404를
  받습니다. 앱이 깨진 것처럼 보이는 게 아니라 그냥 스타일이 없는 상태로 뜹니다.
- **`pre-commit install` 훅 2종** — [`.pre-commit-config.yaml`](.pre-commit-config.yaml)의 모든 로컬
  가드(시크릿 스캔 · docs 수치 정합 · 아키텍처 트리 동기화 · config 레이어 동기화)는 *오직* pre-commit을
  통해서만 실행됩니다. `commit-msg`는 `pre-commit`과 **별개 stage**라 하나만 설치하면 다른 하나는
  설치되지 않습니다. 건너뛰어도 커밋은 성공하므로 — **조용히 무방비** 상태가 됩니다.

앱을 실제로 띄우려면 `DATABASE_URL` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` 가 필요하고
나머지는 기본값이 있습니다. [README.ko.md](README.ko.md) 의 *환경변수 설정* 절과
[`docs/reference/env-vars.md`](docs/reference/env-vars.md) 참조.

---

## 테스트 실행

```bash
make test-fast    # 단위 테스트, 느린 subprocess 스위트 제외 — 개발 중에는 이걸 쓰세요
make test         # 전체
make test-slow    # `slow` 마커만 — 실제 pylint/flake8/bandit/semgrep 프로세스를 띄웁니다.
                  # tests/integration/ 는 conftest 가 이 마커를 자동 부여합니다.
make test-file f=tests/unit/scorer/test_calculator.py
make test-cov     # 커버리지 포함
```

알아두면 좋은 관례 2가지:

- **`make` 타깃이나 명시적 경로를 쓰세요.** 예전에는 경로 없는 `python -m pytest` 가 Playwright E2E
  스위트를 끌어와 의미 없는 실패 수백 건을 뱉었습니다. 지금은 [`pytest.ini`](pytest.ini) 의
  `testpaths = tests` 가 이를 막습니다(`e2e/` 는 `tests/` 밖에 있음). 이 설정을 지우지 마세요.
- **테스트가 먼저입니다.** 새 동작은 그 동작을 서술하는 테스트와 함께 와야 합니다. 스위트가 큰
  (현재 수치는 [`docs/STATE.md`](docs/STATE.md)) 이유는 정확히, 여기서 놓친 회귀를 운영에서 찾는
  비용이 크기 때문입니다.

E2E는 Playwright 기반이고 **로컬 전용** — CI에 포함되지 않습니다:

```bash
make install-playwright
make test-e2e            # headless
make test-e2e-headed     # 브라우저 표시
```

---

## 린트와 Phase 게이트

```bash
py -3 scripts/pre_push_gate.py --full    # ← push 전에 이걸 (가드 + pylint + bandit + 단위 테스트)
py -3 scripts/pre_push_gate.py           # ← 가드만 빠르게 볼 때
```

`pre_push_gate.py` 는 CI 가 실제로 강제하는 가드를 `make` 없이 실행합니다.
목록 정본 = 그 파일의 `_INTEGRITY` · `_INTEGRITY_WITH_ARGS` · `_DIFF_SCOPED`.
그리고 **자기가 보지 못하는 축**(CodeQL · SonarCloud · Codecov ·
TruffleHog · pip-audit · lint-js · Postgres job · 통합 테스트)을 매 실행 인쇄하므로, 여기서
초록이 나와도 CI 초록으로 오해하지 않습니다.

`--full` 은 여기에 `pylint --fail-under=9.90 src/` · `bandit -r src/` · `pytest tests/unit` 를 더합니다.
🔴 **두 형태 모두 `tests/integration` 은 돌지 않습니다.** 파이프라인·분석기·subprocess 를 건드렸다면
`py -3 -m pytest tests/integration` 도 돌리세요 — CI 는 돕니다.

> ⚠️ **`make gate` 는 CI 와 동일 기준이 아닙니다**, 그리고 머신에 `make` 자체가 없을 수 있습니다
> (주 개발 PC 에는 없습니다). 그 타깃은 테스트 + `pylint --fail-under=9.90 src/` + `bandit -r src/`
> 뿐이라 위 가드를 **하나도** 돌리지 않습니다. 편의 도구로 쓰되 **근거로 쓰지 마세요**.

> ⚠️ **`make lint` 도 게이트가 아닙니다.** pylint · flake8 · bandit 를 `|| true` 를 붙여 실행하므로
> 위반을 출력하고도 **항상 `0`으로 종료**합니다. 위반을 *읽는* 용도로는 유용하지만 아무것도 증명하지
> 못합니다. 검증 가능한 유일한 기준은 CI job 결과입니다.

`flake8` 은 의도적으로 `make gate` 에서 제외돼 있습니다 — `src/` 에 장문 라인 위반이 몇 건 있는데
이를 강제하면 십여 개 파일을 미용 목적으로 고쳐야 합니다. 실질 결함에 해당하는 부분(미사용 import·변수)은
CI `lint-changed-tests` job 이 강제합니다. 전체 목록은 `make lint` 로 확인하세요.

---

## 브랜치 명명

문서만 바꾸는 변경을 포함해 **모든 작업은 브랜치 + Pull Request** 로 진행합니다.

| 접두사 | 용도 |
|--------|------|
| `feat/` | 새 기능 |
| `fix/` | 버그 수정 |
| `chore/` | 설정 · 툴링 · 의존성 |
| `docs/` | 문서 전용 |

```bash
git checkout main && git pull
git checkout -b fix/telegram-otp-expiry
```

---

## 커밋 메시지

Conventional Commits 를 따릅니다: `type(scope): 요약`.

```
fix(gate): auto-merge 를 live head 대신 분석된 SHA 에 결속
docs(readme): CLI Hook 요구사항 정정
test(scorer): AI 없이 89점 상한 커버
```

요약은 명령형으로 쓰고 ~72자 이내로 유지하세요. 한국어 요약도 괜찮습니다 — 이 프로젝트의 히스토리는
원래 이중 언어입니다.

**실제 토큰 · 키 · chat ID를 커밋 메시지에 절대 넣지 마세요.** `commit-msg` 훅이 Telegram 봇 토큰
패턴을 차단하고 gitleaks 가 diff 와 메시지를 모두 스캔하지만, 둘 다 완전하지 않습니다. `<REDACTED>` 를
쓰세요.

---

## 코드 주석 (이중 언어)

새 코드 주석은 **한국어를 먼저 쓰고, 바로 다음 줄에 영어**를 씁니다:

```python
# 레이트 리밋 초과 시 재시도
# Retry on rate limit exceeded

# 같은 SHA가 이미 분석된 경우 건너뜀 (멱등성 보장)
# Skip if the same SHA was already analyzed (idempotency guard)
```

이유는 실용적입니다 — 메인테이너는 한국어로 작업하고, 이 코드베이스를 영어로 읽는 기여자와 AI
에이전트의 비중이 늘고 있습니다. 소스에 둘 다 있으면 어느 쪽도 추측할 필요가 없습니다.

영어 문장에 자신이 없다면 **한국어 줄만 쓰고 PR에 그렇게 적어주세요** — 메인테이너가 영어를 채웁니다.
검증할 수 없는 주석을 기계번역해서 넣지는 마세요.

`# TODO` · `# FIXME` · `# type: ignore` 같은 한 단어짜리 표준 태그는 영어 단독을 허용합니다. 기존
파일은 기회가 될 때 갱신합니다 — 파일을 건드리게 되면 **본인이 수정한 주석만** 이중 언어 형태로
맞추면 되고, 지나가는 파일 전체를 변환할 의무는 없습니다.

🔴 **이건 규약이지 강제 게이트가 아닙니다.** 예전에는 pre-commit 훅이 이걸로 커밋을 막았지만
의도적으로 해제됐습니다 — 커밋을 실패시킬 수 있는 유일한 **스타일** 규칙이었고 마찰
대비 기여가 불분명하다는 판단이었습니다. 검사 스크립트 자체는 남아 있으니 원하면 직접 돌리면 됩니다:

```bash
python scripts/check_bilingual_comments.py
```

---

## Pull Request 체크리스트

PR을 열면 [템플릿](.github/PULL_REQUEST_TEMPLATE.md)이 자동으로 채워집니다. ready 로 표시하기 전에:

- [ ] 로컬에서 `py -3 scripts/pre_push_gate.py --full` 통과 (가드 + pylint + bandit + 단위 테스트)
- [ ] 파이프라인·분석기 변경이면 `py -3 -m pytest tests/integration` 도 — 두 게이트 형태 모두 이건 안 돕니다
- [ ] 새 동작에 대해, 변경 없이는 실패하는 테스트가 있음
- [ ] PR 본문에 **리뷰어가 손으로 확인해야 할 것**을 적었음 — "테스트 통과"만 적지 마세요. 시각적인
      것, 배포에 의존하는 것, 외부 서비스가 얽힌 것은 테스트 스위트가 검증할 수 없습니다.
- [ ] **UI 변경**(`src/templates/**`, `src/static/**`): 시각 검증이 미완임을 명시하고 조합을 나열 —
      4테마(dark / light / pastel / catppuccin) × 데스크탑/모바일. 정적 테스트는 깨진 테마 토큰을
      잡지 못합니다.
- [ ] **`src/` 신규 파일**: [`docs/architecture.md`](docs/architecture.md) 의 트리에 추가하고, 요청
      경로에 놓이는 파일이면 데이터 흐름 절에도 반영. 트리는 pre-commit 훅이 강제합니다.
- [ ] **신규 환경변수**: [`docs/reference/env-vars.md`](docs/reference/env-vars.md) 에 등재
- [ ] **테스트 수 · 커버리지 · pylint 점수 변경**: 단일 진실 소스인 [`docs/STATE.md`](docs/STATE.md) 를
      먼저 갱신하고 그다음 README 배지. pre-commit 훅이 둘을 비교해 어긋나면 커밋을 차단합니다.

작은 리뷰 코멘트는 왕복하는 대신 메인테이너가 브랜치에 fix-up 커밋을 얹을 수 있습니다.

---

## 누구나 한 번은 밟는 지뢰 2개

**마이그레이션 없이 ORM 컬럼 추가.** 모델에 컬럼을 추가하는 것만으로는 스키마 변경이 아닙니다.
Alembic 리비전이 없으면 새로 만들어지는 로컬 SQLite에서는 잘 동작하다가, 운영의 실제 테이블에 닿는
순간 500을 냅니다.

```bash
make revision m="add merge_attempts.failure_reason"
make migrate
# 왕복 검증: alembic downgrade -1 && alembic upgrade head
```

`nullable=False` 로 선언한 컬럼은 `server_default` 가 필요합니다. 없으면 이미 행이 있는 테이블에서
마이그레이션이 실패합니다.

**설정 필드를 한 곳에서만 변경.** 리포 설정 필드 하나는 **5곳**에 존재합니다 — SQLAlchemy 모델 ·
dataclass · API 업데이트 body · 설정 폼 · 프리셋. 5곳을 다 고치지 않으면 다음 저장 때 REST API가
그 필드를 조용히 `NULL` 로 덮어씁니다.

🔴 **자동 가드는 5곳 중 3곳만 커버합니다.**
[`scripts/check_config_5way_sync.py`](scripts/check_config_5way_sync.py) 는 Python 3 레이어를 AST 로
비교합니다. 설정 폼과 프리셋은 HTML/JS 라 필드명 파싱이 fragile 해서 강제 대상이 아니며 —
**이 2곳은 수동 확인**입니다. push 전에 필드명을 grep 해서 5곳을 직접 확인하세요. (다만 폼 컨트롤이
`<form>` 밖으로 빠져 조용히 제출되지 않는 특정 사고 유형은 별도 테스트가 잡습니다.)

---

## 문서 위치

| 하고 싶은 것 | 읽을 문서 |
|-------------|----------|
| 모듈 구조와 요청 흐름 파악 | [`docs/architecture.md`](docs/architecture.md) |
| 점수 산출 방식 이해 | [`docs/reference/scoring.md`](docs/reference/scoring.md) |
| 환경변수 조회 | [`docs/reference/env-vars.md`](docs/reference/env-vars.md) |
| 분석기별 지원 언어 확인 | [`docs/reference/language-coverage.md`](docs/reference/language-coverage.md) |
| 배포 · 운영 | [`docs/runbooks/`](docs/runbooks/) |
| 현재 테스트 수 · 품질 수치 | [`docs/STATE.md`](docs/STATE.md) |
| 미해결 일감 찾기 | [GitHub Issues](https://github.com/xzawed/SCAManager/issues) |

리포 루트의 `CLAUDE.md` 와 `AGENTS.md` 는 이 프로젝트에 기여하는 AI 에이전트를 위한 작업 규약입니다.
기여하려고 읽을 필요는 없지만, 여기 규약 일부가 유난히 엄격한 이유를 설명해 줍니다.

---

## 라이선스

기여하시면 그 기여물이 프로젝트 나머지와 동일한 [MIT License](LICENSE) 로 배포되는 데 동의하는 것으로
간주합니다.
