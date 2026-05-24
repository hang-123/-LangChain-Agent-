# BettaFish — AI 求职研究助手

基于 LangGraph 的确定性多 Agent 求职深度研究工具。输入"公司 + 岗位 + 研究目标"，输出一份带证据归因的结构化 Markdown 报告。

## 架构

```
Supervisor → MemoryRetrieval → SearchOrchestrator → JobAnalyzer
                                                      ↓
                                               MatchingEngine
                                                      ↓
                                               ResumeTailor / InterviewCoach / OfferEvaluator
                                                      ↓
                                               AnalysisAgent → ReportAgent → Gate
```

- **Supervisor** — 路由决策，选择工作流
- **MemoryRetrievalNode** — 跨 session 记忆检索 (STM + LTM 混合)
- **SearchOrchestrator** — Tavily + RAG 并行搜索，自动回写
- **AnalysisAgent** — 结构化分析 (风险/机会/行动计划)
- **ReportAgent** — Token 级流式 Markdown 生成
- **Gate** — 12 条规则的质量门禁，含回退和熔断

## 快速开始

### Docker Compose (推荐)

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 2. 启动
docker compose up -d

# 3. 访问
# API:  http://localhost:9000/docs
# 前端: http://localhost:5173
```

### 本地开发

```bash
# 1. 启动依赖服务
docker compose up -d postgres redis

# 2. 安装依赖
pip install -r requirements-minimal.txt

# 3. 配置 .env
cp .env.example .env

# 4. 启动后端
uvicorn api.main:app --reload --host 0.0.0.0 --port 9000

# 5. 启动前端 (可选)
cd web && npm install && npm run dev
```

## 核心特性

### RAG + 网络搜索

- **BGE-M3 嵌入** (SiliconFlow 云端，1024d) — 中文优化
- **Dense + Sparse 混合检索** — 向量相似 + 关键词精确匹配
- **按源类型分块** — JD 按标题、面经按 Q&A、技术栈按句子+overlap
- **自动回写** — 高质量搜索结果自动缓存到 pgvector
- **RAG ↔ LTM 桥接** — 缓存内容同步写入长期记忆

### Memory 系统

三层架构：
- **Session Memory** — 会话元数据，加载历史摘要
- **STM** — 最近 3 轮对话作为检索上下文
- **LTM** — 5 类记忆 (Entity/Pattern/Preference/Semantic/Episodic)，时间驱动衰减 + 软删除

### 确定性工作流

- 工具由 Supervisor 按工作流选择，不是 LLM 自主调用
- 搜索按意图类型固定派发 (company + jd + interview)
- Gate 质量门禁 12 条规则 (证据充分性 / 虚构检测 / 结构合规等)

### Eval 评测体系

- 8 维度评分 (retrieval / attribution / insight / report / matching / resume / interview / routing)
- CI 回归评测 + 基线差异对比
- 离线评测脚本: `python scripts/run_eval_suite.py`

## API

| 端点 | 说明 |
|------|------|
| `POST /api/research/run` | 同步研究 |
| `GET /api/research/stream` | SSE 流式研究 |
| `GET /api/research/cases` | 评测用例列表 |
| `POST /api/research/eval` | 运行评测 |

## 环境变量

关键配置见 `.env.example`。必填项：

| 变量 | 说明 |
|------|------|
| `QUERY_ENGINE_API_KEY` | LLM API Key (DashScope / OpenAI) |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `RAG_DATABASE_URL` | PostgreSQL 连接串 |
| `EMBEDDING_API_KEY` | 嵌入模型 API Key (SiliconFlow) |

## 技术栈

- **后端**: Python 3.12, FastAPI, LangGraph, PostgreSQL + pgvector, Redis
- **前端**: Vue 3 + TypeScript + Vite
- **LLM**: DashScope (qwen-plus) / OpenAI 兼容
- **嵌入**: BGE-M3 (SiliconFlow, 1024d)
- **搜索**: Tavily API + pgvector RAG
- **监控**: Prometheus + OpenTelemetry

## 文档

- 架构与逻辑层: [`docs/LOGIC_LAYER.md`](docs/LOGIC_LAYER.md)
- 规范文件: [`job-assistant/specs/`](job-assistant/specs/)
- 评测基础设施: `api/evals/`
