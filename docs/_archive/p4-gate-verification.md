> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# P4-Gate 프로덕션 실증 가이드 (1차 — cppcheck + slither)

> ✅ **상태**: 2026-04-23 `xzawed/SCAManager-test-samples` 분석 #543 으로 **통과 완료**. Phase D.3 (RuboCop) 해금됨.
>
> 후속 도구 (rubocop / golangci-lint) 실증은 **[P4-Gate-2 가이드](p4-gate-2-verification.md)** 참조.

> Phase D.1 (cppcheck) + D.2 (slither) 가 Railway 프로덕션 환경에서 실제 동작하는지 확인하기 위한 6항목 체크리스트와 재료. Phase D.3 (RuboCop) 착수 전에 통과해야 한다.

---

## 배경

로컬 devcontainer 에는 cppcheck/slither 바이너리가 없어 `is_enabled()=False` 경로만 단위 테스트로 검증된다. Railway 빌드에서 `aptPkgs` + `slither-analyzer` + `solc-select` 가 정상 설치되고 런타임에서 분석이 실행되는지 확인되지 않은 상태로 D.3 를 쌓으면, 실패 표면이 중첩되어 원인 추적이 어렵다.

---

## 사용자 역할 분담

| # | 항목 | 담당 | 소요 |
|---|------|------|------|
| 1 | Railway 빌드 로그 확인 | 사용자 | 5분 |
| 2 | 컨테이너 solc 설치 검증 | 사용자 | 5분 |
| 3 | cppcheck 실증 PR 제출 | 사용자 | 15분 |
| 4 | slither 실증 PR 제출 | 사용자 | 15분 |
| 5 | 타임아웃 확인 | 사용자 | 2분 |
| 6 | 점수 반영 확인 | 사용자 | 5분 |

**총 사용자 소요**: ~45분.

---

## 1. Railway 빌드 로그 확인

**접속**: Railway 대시보드 → 프로젝트 → Deployments → 최근 빌드 → **Build Logs** 탭.

**통과 조건** (로그에 아래 문자열 전부 포함):

```
Successfully installed slither-analyzer-
cppcheck
Preparing version 0.8.20 for installation...
Deploying solidity compiler version '0.8.20'
```

❌ 실패 시: `railway.toml::buildCommand` 와 `nixpacks.toml::aptPkgs` 확인. `buildCommand` 중 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인이 유지됐는지 점검.

---

## 2. solc 사전 설치 검증

Railway 서비스 로그에 접근해 한 번이라도 컨테이너 shell 접근 (Railway CLI `railway run bash`) 또는 헬스체크 엔드포인트에 진단 명령을 추가해 확인:

```bash
which solc && solc --version
# 기대: /root/.solc-select/bin/solc
# solc, the solidity compiler commandline interface
# Version: 0.8.20+commit.a1b79de6.Linux.g++
```

❌ 실패 시: `buildCommand` 의 solc-select 체인 재점검 + Railway Deploy Logs 의 `solc-select use 0.8.20` 단계 성공 확인.

---

## 3. cppcheck 실증 PR

### 사용할 샘플 C 파일 — `samples/buffer_overflow.c`

아래 파일을 외부 테스트 리포 (예: 신규 `xzawed/SCAManager-test-samples`) 의 기본 브랜치에 두고, 새 브랜치에서 의도적 결함을 덮어쓴 뒤 PR 을 열어라.

```c
#include <string.h>
#include <stdio.h>

// 의도적 결함:
// 1) buf[10] 에 크기 미확인 strcpy — cppcheck error "bufferAccessOutOfBounds"
// 2) scanf %s 포맷 — cppcheck warning "invalidscanf"
// 3) 초기화 안 된 지역 변수 — cppcheck warning "uninitvar"
int vulnerable_copy(const char *long_str) {
    char buf[10];
    strcpy(buf, long_str);   // ← 결함 1
    return 0;
}

int unsafe_input(void) {
    char name[32];
    scanf("%s", name);       // ← 결함 2
    return 0;
}

int uninitialized(void) {
    int x;
    return x + 1;            // ← 결함 3
}

int main(void) {
    vulnerable_copy("AAAAAAAAAAAAAAAAAAAAA");
    unsafe_input();
    return uninitialized();
}
```

### 통과 조건

PR 분석 완료 후 대시보드 `/repos/<owner>/<repo>/analyses/<id>` → **정적 분석 이슈** 섹션에 최소 1건 `[cppcheck/...]` tag 가 포함될 것.

또는 DB 직접 확인:

```sql
SELECT result->'issues' FROM analyses WHERE id = <pr-analysis-id>;
-- 결과에 tool='cppcheck' 이슈 포함 확인
```

---

## 4. slither 실증 PR

### 사용할 샘플 Solidity 파일 — `samples/reentrancy.sol`

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

// 의도적 결함:
// 1) 외부 호출 후 상태 변경 — slither "reentrancy-eth" (HIGH)
// 2) tx.origin 인증 — slither "tx-origin" (MEDIUM)
// 3) weak PRNG — slither "weak-prng" (MEDIUM)
contract Vulnerable {
    mapping(address => uint) public balances;

    function withdraw(uint amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        (bool ok, ) = msg.sender.call{value: amount}("");  // ← 결함 1 (외부 호출)
        require(ok, "send failed");
        balances[msg.sender] -= amount;                    // ← 상태 변경 (재진입 후 발생)
    }

    function isOwner(address owner) external view returns (bool) {
        return tx.origin == owner;                         // ← 결함 2
    }

    function rand() external view returns (uint) {
        return uint(keccak256(abi.encodePacked(block.timestamp, block.difficulty))); // ← 결함 3
    }

    receive() external payable {
        balances[msg.sender] += msg.value;
    }
}
```

### 통과 조건

분석 완료 후 이슈 목록에 최소 1건:
- `tool='slither'` + `check='reentrancy-eth'` + `category='security'`
- 또는 `check='tx-origin'` / `weak-prng`

**pragma `^0.8.0`** 는 Railway 에 사전 설치한 `solc 0.8.20` 과 호환되므로 자동 다운로드 없이 첫 분석에서도 성공해야 한다.

---

## 5. 첫 분석 타임아웃 확인

두 PR 모두 다음 조건을 동시에 만족해야 한다:

- 분석 완료까지 경과 시간 < `STATIC_ANALYSIS_TIMEOUT=30` (초)
- `logger.warning("slither timed out")` / `logger.warning("cppcheck failed")` 메시지 **부재**

**측정 방법**: Railway 로그에서 `"analysis completed"` (pipeline.py 종료 로그) 와 PR 이벤트 수신 시각 차이를 측정.

❌ 타임아웃 시 선택지:
- (a) `railway.toml::buildCommand` 의 solc 버전을 PR 의 pragma 에 더 가깝게 조정
- (b) `src/constants.py::STATIC_ANALYSIS_TIMEOUT` 을 45 또는 60 으로 상향

---

## 6. 점수 반영 확인

PR 최종 점수에서 해당 도구 이슈가 `code_quality` 또는 `security` 감점으로 반영됐는지 확인.

- cppcheck error → code_quality -3 (scorer.calculator: `CQ_ERROR=-3`)
- cppcheck warning → code_quality -1
- slither reentrancy-eth (HIGH) → security -7 (SEC_ERROR=-7)
- slither tx-origin (MEDIUM) → security -7
- slither weak-prng (MEDIUM) → security -7

예: 샘플 .sol 의 reentrancy + tx-origin + weak-prng = -21 security 감점 → security 점수 0/20 근접.

---

## 게이트 통과 선언

6개 항목 모두 ✅ 확인 시 [`docs/STATE.md`](../STATE.md) 의 **D.3 차단 게이트** 섹션 체크박스에 v 표시 + 본 세션에서 `"P4-Gate 통과 — D.3 해금"` 선언. 이후 Phase D.3 RuboCop 착수 가능.

---

## 실패 시 대응

| 실패 항목 | 대응 |
|---------|------|
| 1 (빌드 로그) | buildCommand/aptPkgs 재점검 → 수정 PR → Railway 재배포 |
| 2 (solc 검증) | buildCommand 의 solc-select 체인 복구 |
| 3/4 (실증 PR) | `is_enabled()` 가 False 일 가능성 — Railway 컨테이너에서 `which cppcheck`/`which slither` 확인 |
| 5 (타임아웃) | STATIC_ANALYSIS_TIMEOUT 상향 또는 solc 버전 조정 |
| 6 (점수 반영) | `src/analyzer/io/tools/{cppcheck,slither}.py` 의 `category` / `severity` 매핑 확인 |

---

## 참고 자료

- [Phase D.1 추가 커밋](../../src/analyzer/io/tools/cppcheck.py) — 그룹 10 (2026-04-21)
- [Phase D.2 추가 커밋](../../src/analyzer/io/tools/slither.py) — 그룹 13 (2026-04-22)
- [Railway 빌드 설정](../../railway.toml)
- [점수 계산 로직](../../src/scorer/calculator.py)
