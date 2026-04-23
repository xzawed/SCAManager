"""JavaScript review guide — Tier 1 deep checklist."""

FULL = """\
## JavaScript 검토 기준
- **변수**: `var` 금지 → `const`/`let` 사용, 재할당 없으면 `const`
- **비동기**: `Promise` 체인 대신 `async/await`, unhandled rejection 방지 (`.catch()` 또는 `try/catch`)
- **타입 안전**: `===` vs `==` 혼용 금지, `null`/`undefined` 체크 명시
- **모듈**: ES Module(`import`/`export`) 권장, CommonJS 혼용 시 번들러 설정 확인
- **보안**: `eval()` 금지, `innerHTML` 직접 할당 → XSS 위험, `JSON.parse` try/catch 감싸기
- **성능**: 루프 내 DOM 조작 최소화, 이벤트 리스너 해제 누락 확인
- **에러 처리**: `async` 함수에서 await 앞 try/catch 누락, Promise all reject 전파
- **코드 품질**: 함수 길이 50줄 이하 권장, 중첩 콜백(callback hell) 리팩토링
"""

COMPACT = "## JavaScript: const/let, async/await, ===, eval 금지, XSS innerHTML 주의, Promise 에러 처리"
