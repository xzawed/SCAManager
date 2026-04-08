"""SCAManager CLI — local code review from the terminal.

Usage:
    python -m src.cli review [--base HEAD~1] [--staged] [--no-ai] [--json] [--no-color]
"""
import argparse
import asyncio
import os
import sys

from src.analyzer.static import analyze_file
from src.analyzer.ai_review import review_code
from src.scorer.calculator import calculate_score
from src.cli.git_diff import get_diff_files, get_commit_message, GitError
from src.cli.formatter import format_result, format_json


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scamanager",
        description="SCAManager — AI-powered local code review",
    )
    sub = parser.add_subparsers(dest="command")
    review = sub.add_parser("review", help="Review code changes")

    group = review.add_mutually_exclusive_group()
    group.add_argument("--base", default="HEAD~1", help="Base ref for diff (default: HEAD~1)")
    group.add_argument("--staged", action="store_true", help="Review staged changes only")

    review.add_argument("--no-ai", action="store_true", help="Skip AI review")
    review.add_argument("--json", action="store_true", help="Output JSON format")
    review.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    try:
        files = get_diff_files(base=args.base, staged=args.staged)
    except GitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not files:
        print("변경된 파일이 없습니다.")
        sys.exit(0)

    commit_message = get_commit_message(args.base)

    # static analysis (Python files only)
    python_files = [f for f in files if f.filename.endswith(".py")]
    analysis_results = [analyze_file(f.filename, f.content) for f in python_files]

    # AI review
    api_key = "" if args.no_ai else os.environ.get("ANTHROPIC_API_KEY", "")
    patches = [(f.filename, f.patch) for f in files if f.patch]
    ai_review = asyncio.run(review_code(api_key, commit_message, patches))

    # score
    score_result = calculate_score(analysis_results, ai_review=ai_review)

    # output
    if args.json:
        print(format_json(score_result, analysis_results, ai_review))
    else:
        use_color = sys.stdout.isatty() and not args.no_color
        print(format_result(score_result, analysis_results, ai_review, use_color=use_color))

    sys.exit(2 if score_result.grade == "F" else 0)


if __name__ == "__main__":
    main()
