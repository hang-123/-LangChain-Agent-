# Architecture Baseline

生成时间：`2026-04-05T11:18:04.5187695+08:00`

## 总览
当前仓库已经是一个 `FastAPI + LangGraph + policy-driven harness + renderer-first report` 的多 Agent 求职研究系统，前端使用 `React + Vite`。  
这次基线补齐的目标，是把后续路线图里需要的关键信息分成三类：

- 已确认：可以直接驱动后续自动化任务。
- 推断项：从代码和默认配置能推断，但仍建议人工确认。
- 未指定：必须保留占位符，等待外部信息或后续任务补齐。

## 已确认项

| 维度 | 当前值 | 证据 | 备注 |
| --- | --- | --- | --- |
| Python 运行时 | `3.11.14` | `D:\software\Develop\anaconda3\envs\bettafish\python.exe -V` | 已切换到项目实际 conda 环境 |
| 后端框架 | `FastAPI` | [api/main.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/main.py) | API 入口已完成 |
| Agent Runtime | `LangGraph StateGraph + ResearchExecutionSession` | [api/core/graph.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/graph.py), [api/core/executor.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/executor.py) | 运行生命周期已集中 |
| 流式协议 | `SSE` | [api/main.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/main.py), [web/src/lib/api.ts](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/web/src/lib/api.ts) | `text/event-stream` 已接通 |
| 主输出形态 | `Markdown research report` | [api/main.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/main.py), [api/reporting/renderer.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/reporting/renderer.py) | renderer-first |
| 持久化目录 | `logs/harness` | [api/policies/defaults.json](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/policies/defaults.json), [api/core/persistence.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/persistence.py) | JSONL 落盘 |
| Eval 入口 | `api/evals/harness.py + scripts/run_eval_suite.py` | [api/evals/harness.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/evals/harness.py), [scripts/run_eval_suite.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/scripts/run_eval_suite.py) | 已支持 case replay |
| CI workflow | `ci-eval` | [.github/workflows/ci-eval.yml](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/.github/workflows/ci-eval.yml) | 已接入 smoke eval gate |
| Metrics 入口 | `/metrics` | [api/main.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/main.py), [api/core/metrics.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/metrics.py) | 已接入 Prometheus client，受 feature flag 控制 |
| OTel Trace | `API -> session -> node spans` | [api/core/otel.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/otel.py), [api/core/executor.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/executor.py), [api/main.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/main.py) | exporter 仍由运行时配置决定 |
| Query Store | `SQLite dual-write` | [api/core/query_store.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/query_store.py), [api/core/persistence.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/persistence.py) | 由 `ENABLE_QUERY_STORE` 控制 |
| Guardrails | `minimal_blocking rails + audit` | [api/core/guardrails.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/guardrails.py), [guardrails/config.yml](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/guardrails/config.yml), [.github/workflows/security-injection.yml](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/.github/workflows/security-injection.yml) | 已有最小注入回归 |
| 前端栈 | `React 18 + Vite 7 + TypeScript 5.9 + Tailwind 3` | [web/package.json](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/web/package.json) | 单独 web 子项目 |
| 搜索供应商 | `Tavily + 多个定向 searcher` | [api/tools/__init__.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/tools/__init__.py) | 已封装岗位/面经/技术栈搜索 |

## 推断项

| 维度 | 推断结果 | 依据 | 风险 |
| --- | --- | --- | --- |
| LLM 供应商 | `DashScope / OpenAI-compatible` | `.env.example` 和 [api/core/settings.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/settings.py) 指向 `https://dashscope.aliyuncs.com/compatible-mode/v1`，模型默认 `qwen-plus` | 代码未显式声明 provider 名称，后续账单/策略层最好补成显式字段 |
| 部署倾向 | `本地开发可用` | `.env.example` 默认前端 API 指向 `http://localhost:9000`，主入口为 `uvicorn.run(...)` | 不能据此推出生产部署方式 |
| 主模型 | `qwen-plus` | `.env.example`、`.env` 安全检查、[api/core/settings.py](/f:/300_studyspace/300_学习空间/bettafish/bettafish_langchain/api/core/settings.py) | review/embed 模型仍未拆分 |

## 未指定项

| 维度 | 占位符 | 如何获取 | 为什么重要 |
| --- | --- | --- | --- |
| 部署环境 | `{{DEPLOYMENT_ENV}}` | 向 DevOps 获取部署拓扑，或补充 Docker/K8s/IaC | 决定 T3/T4/T10/T15 的落地方式 |
| 是否使用 K8s | `{{K8S_OR_NOT}}` | 查看集群、helm chart 或 IaC | 决定 metrics、trace 和缓存部署方式 |
| GPU 类型 | `{{GPU_TYPE}}` | 查看推理硬件或云主机规格 | 影响模型调用方式与预算 |
| LLM Provider 显式字段 | `{{LLM_PROVIDER}}` | 在配置层显式声明 provider | 后续成本与限流治理需要 |
| Review 模型 | `{{REVIEW_MODEL}}` | 决定是否独立拆 ReviewAgent 模型 | 影响成本与审查风格 |
| Embedding 模型 | `{{EMBED_MODEL}}` | 如引入向量检索后补充 | 影响检索路线图 |
| Redis 地址 | `{{REDIS_URL}}` | 提供实例地址与凭据 | T10 共享缓存前置条件 |
| 鉴权方式 | `{{AUTHN}}` | 决定 API key/JWT/OAuth/网关 | 安全基线前置条件 |
| 授权模型 | `{{AUTHZ_MODEL}}` | 明确 RBAC/ABAC/多租户策略 | T11-T13 风险边界需要 |
| OTel Exporter | `{{OTEL_EXPORTER}}` | 指定 collector/vendor APM | T3 需要 |
| Prometheus 抓取路径 | `{{PROM_ENDPOINT}}` | 与平台约定 job/path/alert route | T4 需要 |
| 月预算 | `{{MONTHLY_BUDGET}}` | 向产品/财务确认 | 决定 P1/P2 优化目标 |
| 单次 run 成本上限 | `{{COST_PER_RUN_CAP}}` | 产品或平台设定阈值 | Eval gate 和缓存收益判断需要 |
| 团队规模 | `{{TEAM_SIZE}}` | 项目负责人提供 | 影响任务 owner 规划 |
| 角色分工 | `{{ROLES}}` | 列出后端/前端/平台/SRE/安全负责人 | 影响任务清单执行 |
| 项目 Owner | `{{OWNER}}` | 指定单一负责人 | 避免后续工单无 owner |

## 风险清单

| 风险 | 当前观察 | 影响 |
| --- | --- | --- |
| OTel 仅完成应用侧接入 | exporter/collector 终点仍依赖运行时配置 | 当前可本地/console 追踪，但平台级 trace 还未闭环 |
| Prometheus 仅完成应用侧暴露 | `/metrics` 已存在，但 scrape/alert 规则未配置 | 指标已可产出，但平台闭环未完成 |
| GitHub Actions 真正执行依赖 secrets | smoke eval / baseline workflow 需要模型与搜索 key | 仓库侧 workflow 已写好，但线上是否跑通还取决于 secrets |
| Redis 共享缓存未接入 | 当前只有 SQLite cache | T10 仍需外部 Redis 信息 |
| 鉴权边界仍未显式定义 | guardrails 与注入回归已接入，但 API 鉴权模型仍未指定 | 后续上线前仍需补 `AUTHN/AUTHZ_MODEL` |
| 预算与 owner 缺失 | 仓库没有对应信息 | 后续路线图无法量化优先级和验收门槛 |

## 下一步建议

1. 先让你补 4 类人工信息：`DEPLOYMENT_ENV / LLM_PROVIDER / MONTHLY_BUDGET / OWNER`。这会直接影响后续阈值、告警和成本策略。
2. 代码侧已经完成 `T0-T9` 中所有不依赖外部缓存服务的部分，并补上了 `T11-T15` 的最小可执行实现。
3. 若继续做 `T10`，需要你提供 `REDIS_URL`；若继续验证 GitHub Actions，需要把 `QUERY_ENGINE_*` 和 `TAVILY_API_KEY` 配到仓库 secrets。
