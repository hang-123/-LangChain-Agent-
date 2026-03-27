# BettaFish LangChain 优化方案（草案存档）

## 1. 当前进度总览

- **QueryEngine**
  - 已有 LangChain 1.0 流水线（结构规划 → 搜索/反思 → 汇总 → 报告格式化）。
  - 统一配置（Pydantic Settings）与 Tavily 工具封装，支持基础 / 深度 / 时间范围 / 图片 / 按日期搜索。
  - 状态对象记录段落搜索历史与事件日志，写入 `logs/query.log`。

- **InsightEngine**
  - 已有基于 LangChain 的节点链：SearchNode（PG 向量或本地文档）→ SentimentNode → SummaryNode → ReportStructureNode → FormattingNode。
  - PGVector + 本地文本 RAG 能力，情感分析使用 LLM prompt，配置集中在 `InsightEngine/utils/config.py`。
  - 输出结构化 `InsightReport` + Markdown 报告，日志写入 `logs/insight.log`。

- **MediaEngine**
  - 新建 LangChain 版 MediaAgent：多模态 Tavily 搜索（文章 + 图片）→ 媒体摘要 → 媒体简报格式化。
  - 复用 QueryEngine 的 Tavily 封装，配置支持独立或沿用 QueryEngine 模型/API 配置。
  - 状态保存媒体素材与可执行摘要，日志写入 `logs/media.log`。

- **ReportEngine**
  - 新建 ReportAgent：收集多 Agent 输出 → 生成报告规划 JSON（章节标题 + 摘要）→ 渲染 Markdown 执行报告。
  - 配置可复用 QueryEngine 模型或独立配置，日志写入 `logs/report.log`。

- **ForumEngine**
  - 由原 monitor + llm_host 思路简化为 orchestrator：顺序调用 Query / Insight / Media / Report，聚合为一个 ForumSession。
  - 所有阶段写入 `logs/forum.log`，返回结构化对话用于前端展示。

- **Web 前端**
  - `web/` 目录下使用 React + Vite + TypeScript + TailwindCSS。
  - ChatGPT 风格 UI：聊天区（多 Agent 消息气泡）、右侧 Agent 进度时间线、最近请求与日志说明。
  - 已与后端 `POST /api/forum/run` 接通，支持真实多 Agent 调用；预留 SSE `/api/forum/stream` 供后续流式化。

- **API 后端**
  - 新增 FastAPI 应用 `api/main.py`，暴露 `/api/forum/run` 和 `/api/forum/stream`。
  - 统一 CORS 设置，错误处理包装 ForumEngine 内部异常。

---

## 2. 与原 BettaFish 架构对比：仍可借鉴/扩展的点

1）**QueryEngine / MediaEngine 工具层丰富度**

- 原项目：
  - Tavily 工具拆分为多种“场景化”工具：按时间、多源、图片、专题，带有更智能的重试与限流策略。
  - MediaEngine 有针对多模态（视频、图文、短视频）的专用检索与聚合逻辑。
- 当前：
  - 我们已具备基础新闻检索和图片检索，但尚未覆盖“按平台”“按专题热度”等高级用法。
- 后续可做：
  - 引入更多“工具函数”并注册为 LangChain `Tool`，例如：
    - `search_breaking_news_24h`、`search_policy_and_regulation`、`search_company_risk_events` 等。
  - 针对多模态增加字段（缩略图、封面 URL、平台 ID），为前端展示做准备。

2）**InsightEngine 的 DB 工具与文本处理**

- 原项目：
  - 有完整的 MySQL 媒体库抽象（MediaCrawlerDB），封装 Topic / Date / Platform / Comments 等表的查询。
  - `text_processing.py` 中包含去重、清洗、分段、聚合等实用文本处理工具。
- 当前：
  - 依赖 PGVector + 本地 txt 文档；SearchNode 已能用向量或 keyword 搜索，但缺少“以 DB 视角的工具层”。
- 后续可做（当前优先方向）：
  - 在 InsightEngine 下提供统一 DB 工具接口（哪怕底层用 PGVector），例如：
    - `search_topic_globally(topic)`：结合向量检索和 keyword 搜索。
    - `get_comments_for_topic(topic)`：预留接口，未来可接真实评论表。
  - 引入轻量版文本处理（参考上游 `text_processing.py`）：
    - 去除重复段落、过短文本。
    - 控制单次摘要的上下文长度。

3）**ReportEngine 的模板/IR 体系**

- 原项目：
  - 有“报告中间表示”（IR）与 Markdown/HTML 模板，支持多种报告风格（执行摘要版、日报版等）。
  - 模板解析、章节存储和渲染逻辑解耦，便于重复生成和导出。
- 当前：
  - ReportAgent 仍然是“LLM 规划 JSON + LLM 渲染全文”的精简版，不区分模板，也缺少 IR 层。
- 后续可做（当前优先方向）：
  - 引入简单 IR：
    - `ReportSection` + `ReportState` 中增加模板 ID、来源标签等。
  - 新增 Markdown 模板文件（例如 `ReportEngine/templates/default.md`），字段包括：
    - `{title}`, `{executive_summary}`, `{sections_markdown}` 等。
  - RenderNode 改为“模板填充”而非再调用 LLM，提升可控性；后续再考虑支持多模板选择。

4）**SentimentAnalysisModel 的本地模型生态**

- 原项目：
  - 拥有多种 Weibo 情感模型（BERT/GPT2/小 Qwen/传统 ML），支持批量预测。
- 当前：
  - InsightEngine 使用 LLM prompt 计算情绪分布，更统一但不如专门模型精细。
- 后续可做：
  - 增加一个统一情感分析接口：
    - 优先调用本地微调模型（若存在），否则 fallback 至 LLM。
  - 对接已有或新训练的中文社交媒体情感模型（待你提供模型路径或 API）。

5）**ForumEngine 的“主持人智能体”**

- 原项目：
  - 有 llm_host 模块，用于生成“主持人评论”，对多个 Agent 的输出做 Meta 分析。
- 当前：
  - ForumEngine 只负责 orchestrator 与日志，缺少一个 HostAgent 的总结与追问。
- 后续可做：
  - 新增 HostAgent：
    - 输入各 Agent 的摘要，输出“主持人总结 + 建议 + 下一步问题”。
    - 前端 UI 中以特殊头像/颜色展示。
  - 未来扩展为多轮对话：根据用户反馈重跑部分 Agent 或深入某个章节。

6）**SingleEngineApp / 前端体验与会话管理**

- 原项目：
  - 有 Flask + Streamlit 应用，支持单 Agent 与多 Agent 模式。
- 当前：
  - 我们已用 FastAPI + React 实现更现代的架构，但还没有：
    - 会话历史持久化 / 切换。
    - 配置切换（选择使用哪些 Agent、模型、输出目录等）。
    - SSE/WS 真正的 token 级 streaming。
- 后续可做：
  - 在 FastAPI 中为 ForumSession 增加 ID + 存储（文件或 SQLite）。
  - 前端左侧增加“历史会话列表”，支持加载旧报告。
  - 利用 `/api/forum/stream` 做 SSE 流式输出，前端按消息逐条更新 Agent 泡泡。

---

## 3. 短期优先路线（当前要落实的两点）

1）**完善 InsightEngine 的 DB 工具**

- 提供一个统一的“DB 工具层”，即便底层使用的是 PGVector，也要对外有「话题查询」「评论收集」等语义清晰的函数/工具：
  - `search_topic_globally(topic: str, k: int)`：通过向量检索+拼接返回结构化结果列表。
  - 预留 `get_comments_for_topic` 等接口，未来可对接真实 MySQL/PG 表。
- 与 SearchNode 集成策略：
  - SearchNode 优先使用 PGVector；若未来有结构化 DB，可在内部按配置切换。
  - 状态中记录 DB 查询的元信息（表/平台/时间范围），供下游 SummaryNode 使用。

2）**ReportEngine 模板化改造**

- 定义报告 IR：
  - `ReportState` 中补充 `title`、`template_id` 等字段。
- 引入默认模板：
  - 新建 `ReportEngine/templates/default.md`，按以下结构：
    - 标题（含查询主题）
    - 执行摘要
    - 详细章节（按 Section 列表渲染）
    - 可预留“后续行动建议”占位。
- 修改 RenderNode：
  - 不再调用 LLM 渲染整篇报告，而是：
    - 将 `executive_summary` 与 `sections` 填充进模板；
    - 生成确定性的 Markdown，减少不必要的风格漂移。

以上就是当前版本的整体优化方案与近期两项重点工作。

