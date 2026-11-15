import argparse
import asyncio
import json
from typing import Any

from ..services.web_search_client import search as _search


async def search_web(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search the web and return normalized result items."""

    return await _search(query=query, limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser(prog="web_search_tools")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(search_web(args.query, limit=args.limit)), indent=2))


if __name__ == "__main__":
    main()
