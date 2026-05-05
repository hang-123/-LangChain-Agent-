# Query Store

`ENABLE_QUERY_STORE=1` 时，`FileHarnessRepository` 会在保留 JSONL 的同时双写一个 SQLite 查询层。

默认路径：

- `logs/harness/query_store.sqlite`

当前表：

- `runs`
- `run_traces`
- `node_perf`
- `eval_results`
- `security_events`

示例：

```bash
python scripts/query_variant_metrics.py --db logs/harness/query_store.sqlite
python scripts/query_variant_metrics.py --db logs/harness/query_store.sqlite --experiment-id report-polish-ab
```
