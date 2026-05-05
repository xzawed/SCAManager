"""Solidity review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Solidity review checklist
- **Reentrancy**: CEI pattern (Checks-Effects-Interactions); `nonReentrant` modifier; place external calls last
- **Integers**: Overflow/underflow — Solidity 0.8+ auto-checks (older needs SafeMath)
- **Access control**: Explicit `public` / `external` / `internal` / `private` visibility; `onlyOwner` permissions
- **Gas**: Cap loop length; cache storage reads (copy to `memory`); `uint256` vs `uint8` gas differences
- **Upgradeable**: Proxy pattern storage collisions; careful `delegatecall` context
- **Randomness**: `block.timestamp` / `blockhash` are manipulable — prefer Chainlink VRF
- **Events**: Emit events for important state changes; use indexed parameters for filtering
"""

COMPACT = "## Solidity: CEI pattern, nonReentrant, SafeMath(0.7-), onlyOwner, loop gas, no block.timestamp RNG"

FULL_KO = """\
## Solidity 검토 기준
- **재진입 공격**: CEI 패턴(Checks-Effects-Interactions), `nonReentrant` modifier, 외부 호출 마지막 배치
- **정수**: 오버플로/언더플로 — Solidity 0.8+ 자동 체크(이전 버전은 SafeMath 필수)
- **접근 제어**: `public`/`external`/`internal`/`private` 가시성 명시, `onlyOwner` 권한
- **가스**: 루프 길이 제한, storage 읽기 캐싱(`memory` 복사), `uint256` vs `uint8` 가스 차이
- **업그레이더블**: proxy 패턴 storage 충돌, `delegatecall` 컨텍스트 주의
- **난수**: `block.timestamp`/`blockhash` 조작 가능 — Chainlink VRF 권장
- **이벤트**: 중요 상태 변경 이벤트 emit, indexed 파라미터 필터링
"""

COMPACT_KO = "## Solidity: CEI 패턴, nonReentrant, SafeMath(0.7-), onlyOwner, 루프 가스, block.timestamp 난수 금지"

FULL_JA = """\
## Solidity レビュー基準
- **リエントランシー**: CEI パターン (Checks-Effects-Interactions)、`nonReentrant` modifier、外部呼び出しは最後に配置
- **整数**: オーバーフロー/アンダーフロー — Solidity 0.8+ 自動チェック (それ以前は SafeMath 必須)
- **アクセス制御**: `public` / `external` / `internal` / `private` 可視性を明示、`onlyOwner` 権限
- **ガス**: ループ長を制限、storage 読み取りをキャッシュ (`memory` コピー)、`uint256` vs `uint8` のガス差
- **アップグレード可能**: プロキシパターンの storage 衝突、`delegatecall` コンテキスト注意
- **乱数**: `block.timestamp` / `blockhash` は操作可能 — Chainlink VRF 推奨
- **イベント**: 重要な状態変更でイベント emit、indexed パラメータでフィルタリング
"""

COMPACT_JA = "## Solidity: CEI パターン、nonReentrant、SafeMath(0.7-)、onlyOwner、ループガス、block.timestamp 乱数禁止"
