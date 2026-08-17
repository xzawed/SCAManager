## 테스트·검증

### 스위트

| 스위트 | 건수 | 실행 |
|---|---|---|
| `tests/unit` | 7113 | `py -3 -m pytest tests/unit -q` |
| `tests/integration` | 171 | `-m "slow"` (자동 마킹) |
| `e2e/` | 121 | `py -3 -m pytest e2e/ -p no:asyncio -v` |

루트 `pytest.ini`: `testpaths=tests` · `asyncio_mode=auto` · `--timeout=30`.
`e2e/pytest.ini` 는 `asyncio_mode` 를 두지 않는다 — e2e 는 항상 `-p no:asyncio` 로
`tests/` 와 **다른 프로세스**에서 돌린다.

### push 전 절차

1. 영역 실행 — `py -3 -m pytest tests/unit/<영역> -q`
2. 단위 전체 — `py -3 -m pytest tests/unit -q`. 파이프(`| tail`)를 붙이지 않는다(종료코드가 사라진다).
   출력의 `N passed / M skipped` 를 그대로 보관한다.
3. 가드 — `py -3 scripts/pre_push_gate.py` (`--full` 이면 pylint·bandit·`pytest tests/unit` 추가)
4. 출력 끝의 "보지 못하는 축"·인터프리터 줄을 본다 — 여기 초록은 CI 초록이 아니다.
5. `git push` → `gh pr create`
6. PR 본문 **첫 매치 줄**에 2) 실측을 적는다 — `pytest tests/unit → N passed / M skipped`.
   없으면 CI 가 차단한다.

### CI (`.github/workflows/ci.yml` — push:main / PR:main)

- `test-and-analyze` — `pytest tests/` 전량 + coverage.xml → Codecov·SonarCloud.
  PR 에서는 역-뮤테이션(변경을 되돌리면 이 PR 테스트가 red 인가)과
  본문 수치 ↔ `--collect-only` 실측 대조가 이어 붙는다.
- `pg-concurrency` — postgres:16.4, SKIP LOCKED + 마이그레이션 round-trip.
  **node-id 핀 목록**이라 새 PG 테스트는 자동 수집되지 않는다.
- `e2e` — CSS 빌드 후 `--e2e-min-passed=100`, 선행 step 이 수집 건수 ↔ `e2e/EXPECTED_COUNT` 대조.
- `lint-changed-tests` — PR 변경 test 에 `flake8 --isolated --select=F401,F841` +
  dual-import · noqa 은닉 import · 미배선 dead code 차단.
- `repo-integrity` — stdlib 가드 전량(정본=`pre_push_gate.py` `_INTEGRITY`).

### 건수를 바꿀 때

- e2e 증감 → 같은 PR 에서 `e2e/EXPECTED_COUNT` 갱신. 감소는 갱신 없이 통과 못 한다.
- 단위 증감 → `docs/STATE.md` SSOT 불릿 한 줄만 고치고 `py -3 scripts/check_docs_sync.py --fix`.
  미룰 때만 **커밋 메시지** 열 0 에 `STATE-sync-deferred: <사유 16자 이상>`.
- 되돌림 판정 불가 → PR 본문에 `reverse-mutation-not-applicable: <사유 16자 이상>`.
  두 마커 다 통과시키되 계수된다.

### side-effect-only ORM import

`# noqa: F401` 단독은 flake8 전용이라 CodeQL `py/unused-import` 가 계속 발화한다.
튜플 참조로 '사용됨' 을 만들고 소실 시 loud-fail 하게 한다.

```python
_FK_TARGET_MODELS = (User,)
if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")
```

이 이름은 `scripts/check_noqa_sideeffect.py` 가 찾는 대상이라 바꾸지 않는다.
