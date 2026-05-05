# 项目简介

`项目二： 基于 LangGraph / Harness 的多 Agent 求职研究系统	个人Demo	2026.03-至今`

`项目概述：`
面向面试准备场景的深度研究系统。用户输入公司、岗位和目标后，系统自动完成意图识别、公司信息检索、风险诊断、行动清单生成与报告流式输出。后端基于 FastAPI、LangGraph、LangChain，前端基于 React + Vite。

- `执行链路设计：`主导将开放式多 Agent 流程收敛为 `IntentRouter -> Search -> Query -> Insight -> QualityGate -> Report -> Review` 固定状态机，补齐节点职责、回退边与熔断逻辑，提升执行稳定性与问题定位效率。  
- `检索层重构：`将公司画像、岗位画像、面经、技术栈等检索能力拆为异步 Tools，由 SearchAgent 统一做确定性调度、结果重排与失败分类；引入 `evidence_items`、`retrieval_diagnostics`、`query_pack` 等结构化契约，推动下游基于显式证据生成结论。  
- `质量控制与报告改造：`设计 `QualityGate + ReviewAgent` 双层质量控制链路，补充规则检查器与 LLM reviewer；将报告生成从大模型自由成稿改造成 renderer-first，降低 Prompt 漂移对报告结构和事实边界的影响。  
- `Harness 工程化落地：`引入 `policy loader + run_manifest`，将阈值、重试策略、章节规则外移到控制平面，并沉淀 `run_id`、`trace`、`quality_summary`、`research case`、eval scorecard 与运行结果持久化能力，支持回归评测与问题复现。  
