# Bench

使用 `scripts/run_bench.py` 运行轻量压测，默认输出到 `bench/results/`。

示例：

```bash
python scripts/run_bench.py --endpoint run --base-url http://localhost:9000 --concurrency 5 --requests 20
python scripts/run_bench.py --endpoint stream --base-url http://localhost:9000 --concurrency 5 --requests 20
```

输出指标：

- `latency_p50_ms / latency_p95_ms / latency_p99_ms`
- `ttft_p50_ms / ttft_p95_ms`（仅 `stream`）
- `error_rate`
