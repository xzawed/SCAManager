"""TypeScript review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## TypeScript review checklist
- **Type safety**: Minimize `any` → prefer `unknown` + type guards; cautious `as` casts
- **Interfaces**: Consistent `interface` vs `type`; verify union type readability
- **Null safety**: Assume `strictNullChecks` enabled; use optional chaining (`?.`) and nullish coalescing (`??`)
- **Enums**: Prefer `const enum` (bundle optimization); avoid relying on `enum` numeric values
- **Generics**: Explicit generic constraints (`T extends object`); avoid deeply nested generics
- **Async**: Clear return types like `Promise<void>` vs `Promise<unknown>`
- **Modules**: Consistent path aliases (`@/`); watch for circular dependencies in barrel exports (`index.ts`)
- **Compiler**: Enforce `strict: true`; verify `tsconfig.json` `target` compatibility
"""

COMPACT = "## TypeScript: avoid any→unknown, strictNullChecks, const enum, generic constraints, strict:true"

FULL_KO = """\
## TypeScript 검토 기준
- **타입 안전**: `any` 사용 최소화 → `unknown` + 타입 가드, `as` 강제 캐스팅 주의
- **인터페이스**: `interface` vs `type` 일관성 유지, union type 가독성 확인
- **null 안전**: `strictNullChecks` 활성화 전제, optional chaining(`?.`)·nullish coalescing(`??`) 활용
- **enum**: `const enum` 권장(번들 최적화), `enum` 숫자값 의존 금지
- **제네릭**: 제네릭 constraints 명시(`T extends object`), 과도한 중첩 제네릭 경계
- **비동기**: `Promise<void>` vs `Promise<unknown>` 반환 타입 명확화
- **모듈**: 경로 alias(`@/`) 설정 일관성, barrel exports(`index.ts`) 순환 의존성 위험
- **컴파일러**: `strict: true` 옵션 강제, `tsconfig.json` `target` 버전 적합성
"""

COMPACT_KO = "## TypeScript: any 금지→unknown, strictNullChecks, const enum, 제네릭 constraints, strict:true"

FULL_JA = """\
## TypeScript レビュー基準
- **型安全**: `any` 使用を最小化 → `unknown` + 型ガード、`as` 強制キャスト注意
- **インターフェース**: `interface` vs `type` の一貫性、union type の可読性確認
- **null 安全**: `strictNullChecks` 有効を前提、optional chaining (`?.`) · nullish coalescing (`??`) 活用
- **enum**: `const enum` 推奨 (バンドル最適化)、`enum` 数値依存禁止
- **ジェネリクス**: ジェネリクス constraints 明示 (`T extends object`)、過度なネストジェネリクス回避
- **非同期**: `Promise<void>` vs `Promise<unknown>` 戻り値型明確化
- **モジュール**: パス alias (`@/`) の一貫性、barrel exports (`index.ts`) の循環依存リスク
- **コンパイラ**: `strict: true` を強制、`tsconfig.json` `target` バージョン適合性
"""

COMPACT_JA = "## TypeScript: any 禁止→unknown、strictNullChecks、const enum、ジェネリクス constraints、strict:true"
