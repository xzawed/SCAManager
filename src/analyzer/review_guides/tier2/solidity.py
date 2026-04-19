"""Solidity review guide — Tier 2."""

FULL = """\
## Solidity 검토 기준
- **재진입 공격**: CEI 패턴(Checks-Effects-Interactions), `nonReentrant` modifier, 외부 호출 마지막 배치
- **정수**: 오버플로/언더플로 — Solidity 0.8+ 자동 체크(이전 버전은 SafeMath 필수)
- **접근 제어**: `public`/`external`/`internal`/`private` 가시성 명시, `onlyOwner` 권한
- **가스**: 루프 길이 제한, storage 읽기 캐싱(`memory` 복사), `uint256` vs `uint8` 가스 차이
- **업그레이더블**: proxy 패턴 storage 충돌, `delegatecall` 컨텍스트 주의
- **난수**: `block.timestamp`/`blockhash` 조작 가능 — Chainlink VRF 권장
- **이벤트**: 중요 상태 변경 이벤트 emit, indexed 파라미터 필터링
"""

COMPACT = "## Solidity: CEI 패턴, nonReentrant, SafeMath(0.7-), onlyOwner, 루프 가스, block.timestamp 난수 금지"
