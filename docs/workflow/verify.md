## 테스트·검증

- `tests/unit` — `py -3 -m pytest tests/unit -q`
- `tests/integration` — `-m "slow"`(자동 마킹)
- `e2e/` — `py -3 -m pytest e2e/ -p no:asyncio -v`

루트 `pytest.ini`: `testpaths=tests` · `asyncio_mode=auto` · `--timeout=30`.
`e2e/pytest.ini` 에 `asyncio_mode` 없음 — e2e 는 `-p no:asyncio` 로 `tests/` 와
**다른 프로세스**에서 돌린다.

### push 전 절차

1. `py -3 -m pytest tests/unit -q` **전체**. 파이프(`| tail`) 금지 — 종료코드 소실.
   `N passed / M skipped` 보관.
2. `py -3 scripts/pre_push_gate.py`(`--full` = pylint·bandit·unit 추가)
3. 출력 끝 "보지 못하는 축"·인터프리터 줄 확인(로컬 초록 ≠ CI).
4. `git push` → `gh pr create` → **도달 확인**. `git push` 의 exit 만으로는 부족하다:

   ```bash
   git ls-remote origin refs/heads/<branch> | cut -f1        # == git rev-parse HEAD
   gh api repos/xzawed/SCAManager/pulls/<n> -q '.head.sha, .commits'   # 🔴 머지 **직전에도**
   ```

   🔴 **두 확인은 서로를 대신하지 못한다.** `ls-remote` 는 ref 만 본다 — ref 가 갔어도 PR 객체가
   그 커밋을 집지 않으면 CI 는 **옛 커밋**을 초록으로 통과시킨다. 그래서
   `head.sha == git rev-parse HEAD` 를 **머지를 누르기 직전에** 다시 본다.
   ⚠️ `mergeStateStatus=UNKNOWN` 이 지속되면 「계산 중」이 아니라 이 상태를 의심한다.
   🔴 본문 수치가 틀렸으면 본문을 고치고 `gh run rerun --failed` 한다. 본문을 읽는 세 스텝은
   `gh api /pulls/N` 으로 **살아 있는 값**을 조회한다(고정 페이로드 아님). 조회가 실패하면
   fail-closed 로 red 다 — 빈 본문으로 흘러가 조용히 초록이 되지 않는다.

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

   볼드(`**WEAKENED**`)는 미매칭. `pre_push_gate.py` 는 PR 환경변수가 없어 이 축을 건너뛴다.
   왜 그 분기로 갔는지는 `py -3 scripts/check_claim_review_trace.py --explain <base> <head>`.

7. **게이트 분기를 완화했으면** — 조건 제거 · 범위 확대 · `except` 통합 · 면제 추가.
   본문에 `## 새로 도달 가능해진 입력 클래스` 를 두고 **클래스마다 테스트 1건**을 건다.
   그리고 실제 PR SHA 로 스크립트를 태워 나온 EXIT 를 before/after 2줄로 적는다.
   ⚠️ 발화 0건을 「트리거가 죽었다」로 읽지 않는다 — 분모는 「PR N건」이 아니라
   **실제 완화 PR N건**이다. 분모가 다르면 0/N 은 「안 재봤다」다.
   「뮤테이션 red + 전체 green」은 이 항목을 대체하지 못한다 — 그 둘은 저자가 이미 상상한
   실패 모드만 잰다. 회귀는 **테스트에 한 번도 준 적 없는 입력**에서 난다.

### CI (`.github/workflows/ci.yml` — push:main · PR:base 무관)

- `test-and-analyze` — `pytest tests/` 전량 + coverage.xml → Codecov·SonarCloud. PR 은
  역-뮤테이션(되돌리면 red?) + 본문 수치 ↔ `--collect-only` 대조 추가.
- `pg-concurrency` — pg16.4, SKIP LOCKED + 마이그레이션 round-trip.
  **node-id 핀 목록** — 새 PG 테스트를 등재 안 하면 단위 스위트가 red 로 잡는다.
- `e2e` — CSS 빌드 후 `--e2e-min-passed=100`, 수집 건수 ↔ `e2e/EXPECTED_COUNT` 대조.
- `lint-changed-tests` — 변경 test: `flake8 --isolated --select=F401,F841` +
  dual-import · noqa 은닉 import · 미배선 dead code.
- `repo-integrity` — stdlib 가드 전량(정본 = `pre_push_gate.py` `_INTEGRITY`).

🔴 base 가 `main` 이 아닌 PR 은 CI 는 돌지만 **required check 가 적용되지 않는다** — 보호 대상이
`main` 뿐이라 초록도 빨강도 머지를 막지 못한다(`repo-integrity` 가 배너로 알린다). 집행으로
올릴 수 없다: 규칙을 전 브랜치로 넓히면 feature 브랜치 직접 push·삭제·force-push 가 막힌다.
그 변경의 claim-review 는 base 가 `main` 으로 갈 때의 PR 이 통째로 짊어진다.

### 건수를 바꿀 때

- e2e 증감 → 같은 PR 에서 `e2e/EXPECTED_COUNT` 갱신(감소도 필수).
- 단위 증감 → `docs/STATE.md` SSOT 불릿 한 줄만 고치고 `py -3 scripts/check_docs_sync.py --fix`.
  미룰 때만 **커밋 메시지** 열 0 `STATE-sync-deferred: <사유 16자 이상>`.
- 되돌림 판정 불가 → PR 본문 `reverse-mutation-not-applicable: <사유 16자 이상>`.
  두 마커 다 통과하되 계수된다.

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
2. `pre_push_gate.py` 의 `_INTEGRITY`·`_INTEGRITY_WITH_ARGS`·`_DIFF_SCOPED` 중 하나에 등재하고,
   `ci.yml` **과** `claim-review-on-body-edit.yml` 양쪽에 스텝을 넣는다 — 같은 check 이름을
   쓰므로 한쪽만 넣으면 `test_claim_review_body_edit_workflow.py` 가 red.
3. 판정식은 **부분문자열이 상태를 대신하지 않게** — 개수·구조를 읽는다. `" failed" in out` 은
   SUT 가 인쇄한 문자열에도 맞는다(실측). 정본 관용구는 `check_test_count_sync.py` —
   **줄을 고른 뒤** 그 줄에서 센다.
4. 「초록인데 거짓」 1건을 심어 red 를 확인한다. docstring 이 성질을 주장하면 그 성질이
   거짓인데 통과하는 입력을 만든다 — 유일성을 약속했으면 다중 일치를, 존재를 약속했으면 삭제를.
5. 아무것도 못 재면 **초록이 아니라 red** 다(「안 쟀음」과 「통과」를 구별한다).
