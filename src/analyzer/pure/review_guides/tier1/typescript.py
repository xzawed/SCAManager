"""TypeScript review guide — Tier 1 deep checklist."""

FULL = """\
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

COMPACT = "## TypeScript: any 금지→unknown, strictNullChecks, const enum, 제네릭 constraints, strict:true"
