# P-TPL-02 NodePerf

目标：为每个 LangGraph node 注入计时、token、tool、fallback 统计，并落到 perf bill 与 `/metrics`。

约束：

- 只追加诊断字段
- 由 `ENABLE_NODE_PERF` 控制
- 异常不破坏主链路
