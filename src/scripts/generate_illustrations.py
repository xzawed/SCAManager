"""SCAManager UI 일러스트 5장 OpenAI DALL-E 3 생성 스크립트 (사이클 93 Step 2-A).

OpenAI DALL-E 3 generator for SCAManager UI illustrations (5 pieces).

사용자 결정 1 = 🅑 OpenAI API 직접 호출. 사용자가 OPENAI_API_KEY 발급 후 로컬에서
본 스크립트 실행 → 결과 PNG 를 src/static/illustrations/ 에 commit.

User decision 1 = OpenAI API direct call. User obtains OPENAI_API_KEY and runs this
script locally → commits resulting PNGs to src/static/illustrations/.

비용 (2026-05 기준):
- standard 1024×1024: ~$0.040 / image
- hd 1024×1024:        ~$0.080 / image
- hd 1792×1024:        ~$0.120 / image
- 본 5장 합계 추정: ~$0.40 (1회 실행) — caching 없음 (DALL-E 3 idempotent X).

사용 예시:
    # 단일 일러스트
    python -m src.scripts.generate_illustrations --name login_hero

    # 전체 5장
    python -m src.scripts.generate_illustrations --all

    # dry-run (API 호출 없이 prompt 출력만)
    python -m src.scripts.generate_illustrations --all --dry-run

환경변수:
    OPENAI_API_KEY  필수 (스크립트 실행 시점)
    OPENAI_BASE_URL 선택 (proxy 사용 시)
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

# 본 스크립트는 SCAManager production 의존성 X — 로컬 1회 실행 도구.
# requirements-dev.txt 의 openai 패키지 사용.
# dry-run 시 openai 미설치도 허용 (prompt 검토 흐름 보장).
# This script is NOT a production dependency — local one-shot tool.
# dry-run allowed without openai installed (preserves prompt review flow).
try:
    from openai import OpenAI

    _OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False

from src.scripts.illustration_prompts import PROMPTS, get_prompt


# 출력 디렉토리 (gitignore X — 결과 commit 의무)
# Output directory (NOT gitignored — results are committed)
_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "src" / "static" / "illustrations"


def generate_one(client: "OpenAI | None", name: str, dry_run: bool = False) -> Path | None:
    """단일 일러스트 생성. dry_run=True 시 prompt 만 출력.

    Generate a single illustration; print prompt only if dry_run=True.
    """
    p = get_prompt(name)
    print(f"\n=== {p.name} ({p.size}, {p.quality}) ===")
    print(f"배치 / Placement: {p.placement}")
    print(f"\nPrompt:\n{p.prompt}\n")

    if dry_run:
        print("[dry-run] API 호출 생략 / API call skipped")
        return None

    print("→ DALL-E 3 호출 중... / Calling DALL-E 3...")
    response = client.images.generate(
        model="dall-e-3",
        prompt=p.prompt,
        size=p.size,
        quality=p.quality,
        n=1,
        response_format="b64_json",
    )

    image_b64 = response.data[0].b64_json
    if not image_b64:
        print(f"❌ {name}: API 응답에 이미지 데이터 없음")
        return None

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{name}.png"
    out_path.write_bytes(base64.b64decode(image_b64))
    print(f"✅ 저장 / Saved: {out_path}")
    return out_path


def main() -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="SCAManager UI 일러스트 5장 OpenAI DALL-E 3 생성",
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--name",
        choices=[p.name for p in PROMPTS],
        help="단일 일러스트 생성 (5종 중 1)",
    )
    g.add_argument("--all", action="store_true", help="전체 5장 생성")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 prompt 만 출력 (검토용)",
    )
    args = parser.parse_args()

    if not args.dry_run:
        if not _OPENAI_AVAILABLE:
            print(
                "❌ openai 패키지 미설치. 다음 명령 실행:\n"
                "   pip install openai>=1.50.0\n"
                "   또는: pip install -r requirements-dev.txt\n"
                "   (--dry-run 으로 prompt 검토만 가능)",
                file=sys.stderr,
            )
            return 1
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(
                "❌ OPENAI_API_KEY 환경변수 미설정. .env 파일 또는 export 명령으로 설정.",
                file=sys.stderr,
            )
            return 1
        client = OpenAI(api_key=api_key)
    else:
        client = None

    targets = [p.name for p in PROMPTS] if args.all else [args.name]
    print(f"대상 / Targets: {len(targets)}장")

    for name in targets:
        try:
            generate_one(client, name, dry_run=args.dry_run)  # type: ignore[arg-type]
        except (ValueError, RuntimeError, OSError) as exc:
            # OpenAI API 오류 (rate limit / network / 권한) + 파일 쓰기 오류 한정.
            # 의도된 오류만 catch — 코드 버그는 즉시 노출.
            print(f"❌ {name}: {exc}", file=sys.stderr)
            return 2

    print(f"\n✅ 완료 / Done. 결과 위치 / Output: {_OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
