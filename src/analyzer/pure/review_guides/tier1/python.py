"""Python review guide — Tier 1 deep checklist."""

FULL = """\
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

COMPACT = "## Python: PEP 8, type hints, async 블로킹 I/O 금지, mutable default args, eval/pickle 주의"
