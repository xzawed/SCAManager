"""Python review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
Phase 4 PR-13 (Cycle 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Python review checklist
- **Style**: PEP 8 naming (snake_case for functions/variables, PascalCase for classes), line length ≤100
- **Type hints**: Required on public function signatures; consistent `Optional[X]` vs `X | None`
- **Async**: No sync blocking I/O (requests, open) inside `async def` → use httpx, aiofiles
- **Exceptions**: No bare `except:`; use `exc_info=True` or `logger.exception()` when logging
- **Pitfalls**: Mutable default args (`def f(x=[])`), circular imports, heavy imports in `__init__.py`
- **pytest**: `@pytest.fixture` scope (function/module/session) appropriateness, correct `parametrize` and `pytest.raises`
- **Dependencies**: SQLAlchemy N+1 queries, missing `open()` / DB session context manager
- **Security**: `eval` / `exec` / `pickle.loads` on untrusted input, SQL string format → parameterized
"""

COMPACT = "## Python: PEP 8, type hints, no async blocking I/O, mutable default args, eval/pickle caution"

FULL_KO = """\
## Python 검토 기준
- **스타일**: PEP 8 네이밍(snake_case 함수/변수, PascalCase 클래스), 줄 길이 ≤100
- **타입 힌트**: public 함수 시그니처에 annotation 필수, `Optional[X]` vs `X | None` 일관성
- **비동기**: `async def` 내부 동기 블로킹 I/O(requests, open) 금지 → httpx·aiofiles
- **예외**: bare `except:` 금지, 로깅 시 `exc_info=True` 또는 `logger.exception()`
- **함정**: Mutable default args(`def f(x=[])`), 순환 import, `__init__.py` 무거운 import
- **pytest**: `@pytest.fixture` 범위(function/module/session) 적절성, `parametrize`·`pytest.raises` 정확성
- **의존성**: SQLAlchemy N+1 query, `open()`/DB session context manager 누락
- **보안**: `eval`/`exec`/`pickle.loads` 신뢰 입력, SQL string format → parameterized
"""

COMPACT_KO = "## Python: PEP 8, type hints, async 블로킹 I/O 금지, mutable default args, eval/pickle 주의"

FULL_JA = """\
## Python レビュー基準
- **スタイル**: PEP 8 命名 (snake_case 関数/変数、PascalCase クラス)、行長 ≤100
- **型ヒント**: public 関数シグネチャに annotation 必須、`Optional[X]` vs `X | None` の一貫性
- **非同期**: `async def` 内部の同期ブロッキング I/O (requests, open) 禁止 → httpx · aiofiles
- **例外**: bare `except:` 禁止、ロギング時は `exc_info=True` または `logger.exception()`
- **落とし穴**: Mutable default args (`def f(x=[])`)、循環 import、`__init__.py` の重い import
- **pytest**: `@pytest.fixture` スコープ (function/module/session) 適切性、`parametrize` · `pytest.raises` 正確性
- **依存**: SQLAlchemy N+1 query、`open()` / DB session context manager 漏れ
- **セキュリティ**: `eval` / `exec` / `pickle.loads` 信頼入力、SQL string format → parameterized
"""

COMPACT_JA = "## Python: PEP 8、type hints、async ブロッキング I/O 禁止、mutable default args、eval/pickle 注意"
