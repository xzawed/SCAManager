## 테스트·검증

- `tests/unit` — `py -3 -m pytest tests/unit -q`
- `tests/integration` — `-m "slow"`(자동 마킹)
- `e2e/` — `py -3 -m pytest e2e/ -p no:asyncio -v`. playwright 핀이 바뀌면 먼저
  `py -3 -m playwright install chromium`

`e2e/pytest.ini` 는 루트와 달리 `asyncio_mode` 가 없어 `tests/` 와 **다른 프로세스**에서 돌린다.

화면 폭 · 줄바꿈 e2e 는 Windows 초록이 CI 초록이 아니다(웹 글꼴이 없어 CI 는 Linux 글꼴로 그린다). 재현 =
`mcr.microsoft.com/playwright/python:v<playwright 핀>-noble` 에 `fonts-dejavu-core` 를 더한 컨테이너 — 빼면 `system-ui` 가 WenQuanYi 라 CI(DejaVu Sans)와 다르다.

### push 전 절차

1. `py -3 -m pytest tests/unit -q` **전체**. 파이프(`| tail`) 금지 — 종료코드 소실.
2. `py -3 scripts/pre_push_gate.py --full --pr-body <본문 파일>`(`--full` = pylint·bandit·unit 추가). 본문 없이는
   본문 · base/head 를 읽는 가드가 `SKIP` 이다.
3. 출력 끝 "보지 못하는 축"·인터프리터 줄 확인(로컬 초록 ≠ CI).
4. `git push` → `gh pr create` → **도달 확인**. `git push` 의 exit 만으로는 부족하다:

   ```bash
   git ls-remote origin refs/heads/<branch> | cut -f1        # == git rev-parse HEAD
   gh api repos/xzawed/SCAManager/pulls/<n> -q '.head.sha, .commits'   # 🔴 머지 **직전에도**
   ```

   🔴 **두 확인은 서로를 대신하지 못한다**(`ls-remote` 는 ref 만 본다) — `head.sha == git rev-parse HEAD` 를
   **머지를 누르기 직전에** 다시 본다. ⚠️ `mergeStateStatus=UNKNOWN` 이 지속되면 「계산 중」이 아니라 이 상태를 의심한다.
   🔴 머지 직전 main 최신 CI 가 초록인지(`py -3 scripts/check_main_red.py`) · PR base 가 main 끝인지 본다 — 아니면 rebase 뒤 다시 잰다.
   🔴 보완 커밋을 더했으면 머지 직전 PR 제목(= squash 커밋 제목)이 최종 diff 를 말하는지도 본다 — 아니면 `gh pr edit --title`.
   🔴 본문 수치가 틀렸으면 본문을 고치고 `gh run rerun --failed` 한다. 본문을 읽는 스텝은
   `gh api /pulls/N` 으로 **살아 있는 값**을 조회한다(고정 페이로드 아님).

5. PR 본문 **첫 매치 줄**에 `pytest tests/unit → N passed / M skipped`. 없으면 CI 차단.
6. 아래 표면은 본문에 claim-review 흔적 필수 — 없으면 `repo-integrity` 차단.
   - 면제 가능: `src/` · `alembic/` · `e2e/` → `claim-review-not-required: <사유 16자 이상>`
   - **면제 불가**: `scripts/` · `.github/workflows/` · `.claude/{hooks,workflows,settings.json}` ·
     `.pre-commit-config.yaml` · `tests/unit/{scripts,hooks}` · 위치 무관 `check_*.py`·`test_*guard*.py`

   ```
   ## Grok claim-review
   - session: <sessionId 또는 워크플로 run id>
   - claim: <검증한 주장, 16자 이상>
   - verdict: SURVIVES | WEAKENED | BROKEN | CONFIRMED | REFUTED | HOLDS
   ```

   볼드(`**WEAKENED**`)는 미매칭. 라운드마다 한 묶음 — BROKEN 으로 고친 라운드도 지우지 않는다.
   왜 그 분기로 갔는지는 `py -3 scripts/check_claim_review_trace.py --explain <base> <head>`.
   Grok 은 `grok_build_plan`(셸 · 편집 · MCP 를 Grok 쪽에서 거부), AntiGravity 는 `agyMode: "plan"` 으로만 부른다 — cwd 는 .env 가 없는 워크트리, 프롬프트
   첫 줄에 «.env · 자격 파일을 열지 않는다». 탐침은 Grok 이 명령으로 적고 Claude 가 셸에서 돌린다(훅이 본다).

7. **게이트 분기를 완화했으면** — 조건 제거 · 범위 확대 · `except` 통합 · 면제 추가.
   본문에 `## 새로 도달 가능해진 입력 클래스` 를 두고 **클래스마다 테스트 1건**을 건다.
   그리고 실제 PR SHA 로 스크립트를 태워 나온 EXIT 를 before/after 2줄로 적는다.
   ⚠️ 발화 0건을 「트리거가 죽었다」로 읽지 않는다 — 분모는 「PR N건」이 아니라
   **실제 완화 PR N건**이다. 분모가 다르면 0/N 은 「안 재봤다」다.
   「뮤테이션 red + 전체 green」은 이 항목을 대체하지 못한다 — 그 둘은 저자가 이미 상상한
   실패 모드만 잰다. 회귀는 **테스트에 한 번도 준 적 없는 입력**에서 난다.

### CI (`.github/workflows/ci.yml` — push:main · PR:base 무관)

- `test-and-analyze` — `pytest tests/` 전량 + coverage.xml → Codecov·SonarCloud. PR 은
  역-뮤테이션(되돌리면 red? · e2e 시험이 바뀐 PR 은 `e2e` 잡 끝에서) + 본문 수치 ↔ junit.
- `pg-concurrency` — SKIP LOCKED + 마이그레이션 round-trip.
  **node-id 핀 목록** — 새 PG 테스트를 등재 안 하면 단위 스위트가 red 로 잡는다.
- `e2e` — CSS 빌드 후 `--e2e-strict-skips`(skip 집합 ↔ `e2e/SKIP_ALLOWLIST`, 양방향 red),
  수집 건수 ↔ `e2e/EXPECTED_COUNT` 대조 · 스위트 시간 ↔ 스텝 벽(85% 초과 red, `scripts/e2e_budget.py`).
- `lint-changed-tests` — 변경 test: `flake8 --isolated --select=F401,F841` +
  dual-import · noqa 은닉 import · 미배선 dead code · 이 PR 이 쓴 «원문 글자 포함» 단언.
- `repo-integrity` — stdlib 가드 전량(정본 = `pre_push_gate.py` `_INTEGRITY`).
- `docker-image` — 운영 이미지 빌드 + 런타임 사용자로 분석기 핀·`$PORT` 의 `/health`.

🔴 base 가 `main` 이 아닌 PR 은 CI 는 돌지만 **required check 가 적용되지 않는다** — 보호 대상이
`main` 뿐이라 초록도 빨강도 머지를 막지 못한다(`repo-integrity` 가 배너로 알린다). 집행으로
올릴 수 없다: 규칙을 전 브랜치로 넓히면 feature 브랜치 직접 push·삭제·force-push 가 막힌다.
그 변경의 claim-review 는 base 가 `main` 으로 갈 때의 PR 이 통째로 짊어진다.

### 건수를 바꿀 때

- e2e 증감 → 같은 PR 에서 `e2e/EXPECTED_COUNT` 를 수집 수로 맞춘다. 가드는 바닥(미만 red)이라 늘린 뒤 안 올리면 그만큼 지워도 조용하다.
- 추적 `.md` 하나 = 단위 +2(`tests/unit/scripts/test_gate_claim_consistency.py` 가 문서마다 돈다).
- 단위 수는 문서에 적지 않는다 — PR 본문 첫 줄(`pytest tests/unit → N passed / M skipped`)만 고친다.
- 되돌림 판정 불가 → PR 본문 `reverse-mutation-not-applicable: <사유 16자 이상>`. 통과하되 계수된다.

### 훅 · 설정 · 스킬 (`.claude/**`)

1. 위협 모형은 «실수하는 정직한 세션» 이다 — 그런 세션이 칠 만한 꼴을 막고, 임의 코드 실행은 범위 밖이다
   (`.claude/hooks/block_credential_dump.py` 머리 docstring). 막는 훅은 `deny` 만 낸다 — bypass 모드에서는 `ask` 가 창 없이 통과한다.
   막는 훅 항목에는 `"onFailure": "block"` 을 둔다 — 훅이 시작하지 못하거나 죽거나 시간을 넘기면 그 호출을 막는다.
   그래서 시간 제한은 30초 이상으로 둔다 — PC 가 바쁘면 훅 시작만으로 10초를 넘겨 모든 셸 호출이 막힌다.
2. 에이전트에게 알릴 것은 stdout 전체를 JSON 한 개로 낸다 — `hookSpecificOutput.additionalContext`(에이전트) ·
   `systemMessage`(사람). PreToolUse · PostToolUse 의 plain stdout 은 디버그 로그로만 간다. 시험(`tests/unit/hooks/`)은
   출력을 JSON 으로 파싱해 채널까지 단언한다.
3. 운영 MCP 허용 목록(`.claude/hooks/block_credential_dump.py::_PROD_RAILWAY_MCP_READS = frozenset` · 그 Supabase 짝)을 바꾸면
   문서가 처방한 MCP 도구 이름을 `git grep -n "MCP" -- docs/` 로 모아 목록과 대조한다.
4. 공개 쓰기(gh 의 Issue · PR 본문 · 댓글 · 릴리스 노트)는 `scripts/scan_publish.py` 가 훅으로 먼저 잰다 — 비밀값 · 개인정보 꼴이
   있으면 막고 종류 · 개수만 알린다. 본문 파일 경로는 그대로 적는다(명령 치환 · 정의 안 된 변수는 못 재서 막는다).
5. 훅 밖의 길은 `.claude/settings.json` `permissions.deny` 가 막는다 — 파일 도구의 .env 꼴(작업 폴더 아래 `.env.*` 전체 ·
   템플릿만 `!` 예외, 그 밖은 `//**/` 이름 목록)과 Grok 의 셸 도구. Read 거부는 Grep · Glob 과 이름을 적은 셸의 cat · grep · ls
   에도 걸려, 남는 값 없는 확인은 `test -f .env` 다(이름 · 개수는 사용자 `!`). .env 꼴 이름을 넓히면 훅 `_is_dotenv_name` 과
   거부 목록을 같이 고친다 — 시험이 둘을 대조한다. Monitor 는 Bash 와 같은 판정을, AntiGravity 위임은 계획 모드 인자만
   통과를 받는다(credential 훅 · 모르는 AntiGravity 도구는 막는 쪽).

### side-effect-only ORM import

`# noqa: F401` 단독은 flake8 전용 — CodeQL `py/unused-import` 가 발화한다.
튜플 참조로 '사용됨' 을 만들고 소실 시 loud-fail.

```python
_FK_TARGET_MODELS = (User,)
if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")
```

`scripts/check_noqa_sideeffect.py` 가 막는 것은 `tests/` 에 **새로 추가된 noqa-은닉 import** 다
(`# noqa` 단독 포함). 튜플 이름은 그 스크립트가 출력하는 처방 예시일 뿐 — 강제하는 가드는 없다.

### 판정식을 쓸 때 — 3~5 는 **모든 파일**에 적용(1~2 는 새 `scripts/check_*.py` 한정)

1. 진입에 `_make_stdout_safe()` — 없으면 `test_stdout_encoding_guard.py` 가 red(면제 없음).
2. `pre_push_gate.py` 의 `_INTEGRITY`·`_DIFF_SCOPED` 중 하나에 등재하고,
   `ci.yml` **과** `claim-review-on-body-edit.yml` 양쪽에 스텝을 넣는다 — 같은 check 이름을
   쓰므로 한쪽만 넣으면 `test_claim_review_body_edit_workflow.py` 가 red.
3. 판정식은 **부분문자열이 상태를 대신하지 않게** — 개수·구조를 읽는다. `" failed" in out` 은
   SUT 가 인쇄한 문자열에도 맞는다(실측). 정본 관용구는 `check_test_count_sync.py` —
   **줄을 고른 뒤** 그 줄에서 센다. CSS·`<style>` 은 `tests/unit/ui/_css_structure.py` 로
   읽는다 — 정규식은 브라우저가 버린 규칙도 «있다» 로 읽는다.
4. **믿기 전에 계기를 «뒤집어» 본다 — 두 목록을 적은 뒤에만 심는다. 목록 없이 심은 둘은
   뒤집기가 아니다.** `claimed` 는 계기의 «이름» 이 포함한다고 **적은** 항목 목록,
   `cheap` 는 첫 출력만 보고(소스를 열지 말고) 적은 «그 출력을 낼 가장 싼 과정» 이 포함하게
   될 항목 목록이다. 두 차집합에서 하나씩 심는다 — `claimed\cheap` 은 **반드시 잡혀야** 하고
   `cheap\claimed` 는 **반드시 무시돼야** 한다. 심을 것을 만들려고 소스를 봐야 했다면 그것은
   이미 계기가 믿는 것이다. docstring 이 주장하는 성질은 `claimed` 목록에 넣는다.
   예(죽은 클래스 스캐너): 옳은 쌍 = 실제 요소의 `plant-live`(잡혀야) + **주석에만** 있는
   `plant-dead`(무시돼야). 「살아있는 이름 + 아무 데도 없는 이름」 쌍은 주석 오탐을 통과시킨다.
   차집합이 비거나 소스 없이는 못 심겠으면 **지어내지 말고 5번(red)** 으로 간다.
   🔴 옳은 쌍을 심어도 **두 번째 싼 과정**이 둘 다 맞히면 여전히 초록이다 — 그때는 같은 두
   심음을 **손대지 않은 운영 파일**에 끼워 넣고 같은 뒤집힘을 요구한다.
   이것은 아래 7번(게이트 완화)을 대체하지 못한다.
5. 아무것도 못 재면 **초록이 아니라 red** 다(「안 쟀음」과 「통과」를 구별한다).
