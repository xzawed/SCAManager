"""JavaScript review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## JavaScript review checklist
- **Variables**: No `var`; use `const` / `let` (`const` when no reassignment)
- **Async**: Prefer `async/await` over Promise chains; prevent unhandled rejections (`.catch()` or `try/catch`)
- **Type safety**: No `==` / `===` mixing; explicit `null` / `undefined` checks
- **Modules**: Prefer ES Module (`import` / `export`); confirm bundler config when mixing CommonJS
- **Security**: No `eval()`; direct `innerHTML` assignment → XSS risk; wrap `JSON.parse` in try/catch
- **Performance**: Minimize DOM manipulation in loops; avoid leaking event listeners
- **Error handling**: Missing try/catch around `await` in async functions, unhandled `Promise.all` reject
- **Code quality**: Function length ≤50 lines recommended; refactor nested callbacks (callback hell)
"""

COMPACT = "## JavaScript: const/let, async/await, ===, no eval, XSS innerHTML caution, Promise error handling"

FULL_KO = """\
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

COMPACT_KO = "## JavaScript: const/let, async/await, ===, eval 금지, XSS innerHTML 주의, Promise 에러 처리"

FULL_JA = """\
## JavaScript レビュー基準
- **変数**: `var` 禁止 → `const` / `let` 使用、再代入なしなら `const`
- **非同期**: `Promise` チェーンより `async/await`、unhandled rejection 防止 (`.catch()` または `try/catch`)
- **型安全**: `===` vs `==` 混用禁止、`null` / `undefined` チェックを明示
- **モジュール**: ES Module (`import` / `export`) 推奨、CommonJS 混用時はバンドラ設定確認
- **セキュリティ**: `eval()` 禁止、`innerHTML` 直接代入 → XSS 危険、`JSON.parse` を try/catch でラップ
- **パフォーマンス**: ループ内の DOM 操作を最小化、イベントリスナー解除漏れ確認
- **エラー処理**: `async` 関数で await 前の try/catch 漏れ、Promise.all の reject 伝播
- **コード品質**: 関数長 50 行以下推奨、ネストコールバック (callback hell) のリファクタリング
"""

COMPACT_JA = "## JavaScript: const/let、async/await、===、eval 禁止、XSS innerHTML 注意、Promise エラー処理"
