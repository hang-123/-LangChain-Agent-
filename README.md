# 基于 LangChain 的多 Agent 求职研究助手

副标题：参考 BettaFish 开源架构并完成场景化二次改造

## 项目简介

这是一个面向实习/求职准备场景的轻量多 Agent LLM 应用。项目最初基于 LangChain 1.0 的 workflow 思路和 BettaFish 开源多 Agent 架构做复现与理解，后续围绕真实求职问答场景完成了场景裁剪、工程收口和前后端落地。

当前系统以 `QueryAgent -> InsightAgent -> ReportAgent` 为主链路，用户输入岗位、公司或面试准备目标后，后端按阶段完成岗位信息提炼、候选人准备策略分析和最终 Markdown 报告生成；前端通过 SSE 实时展示 Agent 状态与结构化中间结果，并结合本地 progressive memory 支持多轮上下文延续。

本项目的重点不是把所有能力都塞进重型框架，而是把与 Agent 开发最相关的关键工程点真正打通：

- LangChain/Agent workflow 思路下的职责拆分与顺序编排
- Prompt 驱动的结构化输出与中间结果传递
- FastAPI + React 的前后端联动
- SSE 驱动的 Agent 可观测状态流
- `session_summary + turn_capsules + raw_messages` 的 progressive memory
- `llm/fallback` 双模式运行与输出档位控制

## 为什么这个项目和 LangChain 相关

这个项目不是“纯手写聊天页面”，也不是“完整照搬开源项目”。它和 LangChain 的关系主要体现在三个层面：

1. 工作流来源
- 早期复现阶段基于 LangChain 1.0 的流水线/节点链搭建 QueryEngine、InsightEngine 等能力。

2. 设计思路延续
- 当前主链路仍然沿用 LangChain 风格的 workflow 思路，把任务拆成职责清晰的 Agent，并通过结构化 metadata 传递中间结果。

3. 工程化收口
- 相比继续堆叠更重的图编排平台，当前版本更强调可运行、可解释、可演示的最小闭环，优先落地 Agent 编排、状态流、memory 和 fallback。

## 你改造了什么

相对于开源参考架构，当前项目的核心改造点是：

- 把通用研究/舆情分析方向重新定位成求职研究助手
- 将主链路收敛成 `QueryAgent -> InsightAgent -> ReportAgent`
- 用 `ForumEngine` 统一管理同步执行与 SSE 流式执行
- 用 FastAPI 暴露统一 REST/SSE 接口
- 用 React 前端展示 Agent 状态、中间结果和最终报告
- 新增本地 progressive memory 与相关性召回
- 为每个 Agent 增加 `generation_mode=llm/fallback` 显式标识
- 用 `template_id` 支持简洁、标准、详细三档输出

## 系统流程

```text
用户输入岗位/公司/面试目标
  -> ForumEngine 判断是否为闲聊或求职任务
  -> QueryAgent 提取公司、岗位、候选人目标、关注重点
  -> InsightAgent 输出风险点、准备策略、面试官关注点
  -> ReportAgent 汇总生成 Markdown 求职研究报告
  -> /api/forum/stream 通过 SSE 输出 meta/status/message/done/error
  -> 前端 useForumChat 消费事件并更新状态面板、消息区、报告视图
  -> session_id 对应的本地 memory_store 持久化本轮结果
  -> 下一轮提问通过 build_memory_snippet 做轻量相关性召回
```

## 当前实现锚点

以下能力已经落在当前代码中，可作为简历和面试时的证据锚点：

- 主编排：
  - `ForumEngine.run_session`
  - `ForumEngine.stream_session`
- 三个核心 Agent：
  - `MinimalQueryAgent`
  - `MinimalInsightAgent`
  - `MinimalReportAgent`
- API：
  - `POST /api/forum/run`
  - `GET /api/forum/stream`
  - `GET /api/health`
- Memory：
  - `create_session`
  - `append_session_message`
  - `build_memory_snippet`
- 前端：
  - `useForumChat` 对 SSE 事件的消费逻辑
  - Agent 状态面板和中间结果面板
- 输出控制：
  - `template_id` 控制简洁/标准/详细输出
  - `generation_mode` 标识 `llm` / `fallback`

## 一次真实场景示例

### 输入

```text
帮我为字节跳动后端开发暑期实习生成一份求职研究报告，重点分析岗位要求、核心技术栈和面试准备方向。
```

### QueryAgent 输出重点

- 公司线索：字节
- 岗位线索：后端
- 关注重点：工程基础、项目表达、岗位匹配动机、Python 或 Java 基础

### InsightAgent 输出重点

- 风险点：如果项目成果不可量化、岗位动机不具体、缺少取舍复盘，容易被继续深挖
- 准备策略：准备 60 秒回答、3 分钟项目展开稿、岗位关键词问答索引

### ReportAgent 输出重点

- 岗位与公司概览
- 岗位能力要求拆解
- 潜在面试问题预测
- 回答准备建议
- 候选人行动清单

### 多轮能力

系统会为本次请求生成 `session_id`，并在本地保存：

- `session_summary.json`
- `turn_capsules.jsonl`
- `raw_messages.jsonl`

后续继续使用同一个 `session_id` 提问时，系统会优先召回相关摘要和历史胶囊，而不是把所有历史原文直接注入 prompt。

## 技术栈

- 后端：Python, FastAPI, Pydantic
- 前端：React, TypeScript, Vite
- LLM 应用：LangChain workflow 思路, Multi-Agent, Prompt Engineering
- 交互：SSE
- 上下文：Session Memory, Progressive Memory

## 启动方式

### 启动后端

```bash
cd api
python -m uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

### 启动前端

```bash
cd web
npm install
npm run dev
```

### 访问地址

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:9000/docs`

## 当前边界

这个版本更适合被表述为“可运行、可解释、可演示的 LLM 应用工程项目”，而不是生产级 Agent 平台。以下能力仍属于后续增强方向：

- 更复杂的图编排或 LangGraph 工作流
- 更重型的 RAG / 向量数据库主链路
- 多用户和权限体系
- 更完整的测试、监控和生产级容错

## 一句话总结

> 这是一个基于 LangChain workflow 思路和开源多 Agent 架构二次改造的求职研究助手，核心价值不在于堆框架名词，而在于把 Agent 编排、SSE 状态流、progressive memory、fallback 和前后端联动真正落地成一个可讲、可演示的 LLM 应用。
