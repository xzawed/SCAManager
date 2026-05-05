"""Haskell review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Haskell review checklist
- **Types**: Explicit type signatures (required for public functions); `Maybe` / `Either` error handling
- **Purity**: Minimize IO side effects — separate pure functions from IO; no `unsafePerformIO`
- **Lazy evaluation**: Watch for space leaks; use `seq` / `deepseq` / `!` for strict evaluation
- **Monads**: Readable `do` blocks; cap monad stack complexity; correct `liftIO`
- **Imports**: Prefer qualified imports (`import qualified Data.Map as Map`); avoid wildcard imports
- **GHC extensions**: Only enable what's needed (`{-# LANGUAGE ... #-}`); `OverloadedStrings` is common
"""

COMPACT = "## Haskell: type signatures, Maybe/Either, separate IO, lazy space leaks, qualified imports"

FULL_KO = """\
## Haskell 검토 기준
- **타입**: 명시적 타입 시그니처(공개 함수 필수), `Maybe`/`Either` 에러 처리
- **순수성**: IO 부작용 최소화 — 순수 함수와 IO 분리, `unsafePerformIO` 금지
- **lazy 평가**: 공간 누수(space leak) 주의, `seq`/`deepseq`/`!` 엄격 평가
- **모나드**: `do` 블록 가독성, 모나드 스택 복잡도 경계, `liftIO` 적절성
- **임포트**: qualified import 권장(`import qualified Data.Map as Map`), 와일드카드 import 주의
- **GHC 확장**: 필요한 확장만 명시(`{-# LANGUAGE ... #-}`), `OverloadedStrings` 기본
"""

COMPACT_KO = "## Haskell: 타입 시그니처 필수, Maybe/Either, IO 분리, lazy space leak, qualified import"

FULL_JA = """\
## Haskell レビュー基準
- **型**: 明示的型シグネチャ (公開関数で必須)、`Maybe` / `Either` でエラー処理
- **純粋性**: IO 副作用を最小化 — 純粋関数と IO を分離、`unsafePerformIO` 禁止
- **遅延評価**: 空間漏れ (space leak) に注意、`seq` / `deepseq` / `!` で正格評価
- **モナド**: `do` ブロックの可読性、モナドスタックの複雑度を制限、`liftIO` の適切性
- **インポート**: qualified import 推奨 (`import qualified Data.Map as Map`)、ワイルドカード import 注意
- **GHC 拡張**: 必要な拡張のみ明示 (`{-# LANGUAGE ... #-}`)、`OverloadedStrings` が一般的
"""

COMPACT_JA = "## Haskell: 型シグネチャ必須、Maybe/Either、IO 分離、lazy space leak、qualified import"
