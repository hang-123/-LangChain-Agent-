from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


async def _run_json_request(client: httpx.AsyncClient, url: str, query: str) -> dict[str, Any]:
    started = time.perf_counter()
    response = await client.post(url, json={"query": query})
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    payload = {}
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:500]}
    return {
        "status_code": response.status_code,
        "latency_ms": elapsed_ms,
        "ok": response.is_success,
        "run_id": payload.get("run_id", ""),
    }


async def _run_stream_request(client: httpx.AsyncClient, url: str, query: str) -> dict[str, Any]:
    started = time.perf_counter()
    ttft_ms = 0.0
    status_code = 0
    async with client.stream("GET", url, params={"query": query}, headers={"Accept": "text/event-stream"}) as response:
        status_code = response.status_code
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                ttft_ms = round((time.perf_counter() - started) * 1000, 2)
                break
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "status_code": status_code,
        "latency_ms": elapsed_ms,
        "ttft_ms": ttft_ms,
        "ok": 200 <= status_code < 300,
    }


def _summarize(results: list[dict[str, Any]], *, mode: str, concurrency: int) -> dict[str, Any]:
    latencies = [float(item["latency_ms"]) for item in results]
    ttfts = [float(item.get("ttft_ms") or 0.0) for item in results if item.get("ttft_ms")]
    failures = [item for item in results if not item.get("ok")]
    return {
        "mode": mode,
        "concurrency": concurrency,
        "requests": len(results),
        "error_count": len(failures),
        "error_rate": round(len(failures) / len(results), 4) if results else 0.0,
        "latency_avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "latency_p99_ms": _percentile(latencies, 99),
        "ttft_p50_ms": _percentile(ttfts, 50) if ttfts else 0.0,
        "ttft_p95_ms": _percentile(ttfts, 95) if ttfts else 0.0,
        "sample_failures": failures[:5],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight load/soak benchmarks against BettaFish APIs.")
    parser.add_argument("--endpoint", choices=["run", "stream"], default="run")
    parser.add_argument("--base-url", default="http://localhost:9000", help="Base URL for the API server.")
    parser.add_argument("--query", default="字节跳动后端开发实习生面试准备", help="Benchmark query payload.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--output-json", default="bench/results/latest.json")
    parser.add_argument("--output-md", default="bench/results/latest.md")
    args = parser.parse_args()

    path = "/api/research/run" if args.endpoint == "run" else "/api/research/stream"
    request_url = f"{args.base_url.rstrip('/')}{path}"
    timeout = httpx.Timeout(timeout=120.0, connect=10.0)
    runner = _run_json_request if args.endpoint == "run" else _run_stream_request

    async with httpx.AsyncClient(timeout=timeout) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def one_request() -> dict[str, Any]:
            async with semaphore:
                return await runner(client, request_url, args.query)

        results = await asyncio.gather(*[one_request() for _ in range(args.requests)])

    summary = _summarize(list(results), mode=args.endpoint, concurrency=args.concurrency)
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Bench Report",
                "",
                f"- Endpoint: `{args.endpoint}`",
                f"- Concurrency: `{args.concurrency}`",
                f"- Requests: `{args.requests}`",
                f"- Error rate: `{summary['error_rate']}`",
                f"- p50 latency: `{summary['latency_p50_ms']} ms`",
                f"- p95 latency: `{summary['latency_p95_ms']} ms`",
                f"- p99 latency: `{summary['latency_p99_ms']} ms`",
                f"- p95 TTFT: `{summary['ttft_p95_ms']} ms`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
