"""Simple load test script using asyncio + httpx.
Usage:
python scripts/load_test.py --base-url http://localhost:8000 --token <jwt> --session-id <id>
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def worker(client: httpx.AsyncClient, session_id: str, rounds: int) -> None:
    for i in range(rounds):
        await client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"text": f"压测消息 {i}", "stream": False},
        )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=20)
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"}
    start = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.base_url, headers=headers, timeout=30) as client:
        await asyncio.gather(
            *[worker(client, args.session_id, args.rounds) for _ in range(args.users)]
        )
    elapsed = time.perf_counter() - start
    print(f"load test finished in {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
