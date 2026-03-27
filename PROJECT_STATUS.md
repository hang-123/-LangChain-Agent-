# 基于 LangChain 的多 Agent 求职研究助手

副标题：参考 BettaFish 开源架构并完成场景化二次改造

## 1. 项目定位

本项目当前的对外定位不再是“通用 BettaFish 复现”，而是一个：

`基于 LangChain workflow 思路与开源多 Agent 架构二次改造的求职场景 LLM 应用工程项目`

核心卖点统一为：

`LangChain/Agent workflow + FastAPI + React + SSE + progressive memory + fallback`

这个定位强调三点：

- 项目与 LangChain 和 Agent 开发有明确关系。
- 核心贡献是场景裁剪、工程收口和前后端落地。
- 对外表述严格锚定现有实现，不把二期规划讲成已完成事实。

## 2. 当前状态总览

### 已完成

#### 1）主编排链路

- 已实现 `ForumEngine.run_session` 与 `ForumEngine.stream_session` 两条主链路。
- 已形成 `QueryAgent -> InsightAgent -> ReportAgent` 的顺序编排流程。
- 已支持闲聊/任务分流，简短寒暄不会进入报告生成链路。
- 已完成结构化消息收集与最终报告聚合。

#### 2）LangChain 相关基础

- 原始复现阶段已基于 LangChain 1.0 搭建过 QueryEngine、InsightEngine 等节点化流水线。
- 当前对外主链路虽采用轻量编排实现，但保留了 LangChain 风格的 workflow 思路：
  - 按职责拆分 Agent
  - 用结构化 metadata 传递中间结果
  - 将 prompt 驱动输出收口为可消费的阶段性结果
- 当前项目更适合表述为“基于 LangChain 思路完成场景化收口”，而不是“深度绑定某个重型框架”。

#### 3）后端接口

- 已实现 `POST /api/forum/run`，用于同步执行多 Agent 主流程。
- 已实现 `GET /api/forum/stream`，通过 Server-Sent Events 输出实时状态与消息事件。
- 已实现 `GET /api/health` 健康检查接口。
- 已具备统一错误处理和请求参数校验。

#### 4）Agent 执行与输出

- 已实现 `MinimalQueryAgent`：提取目标公司、岗位、候选人目标、关注重点和准备动作。
- 已实现 `MinimalInsightAgent`：输出候选人风险点、准备策略、项目表达建议和面试官关注点。
- 已实现 `MinimalReportAgent`：汇总上游结果并生成最终 Markdown 报告。
- 已通过 `template_id` 支持简洁、标准、详细三档输出长度控制。
- 已通过 `generation_mode` 标识当前输出来自 `llm` 还是 `fallback`。

#### 5）会话记忆与上下文管理

- 已实现本地会话创建：`create_session`。
- 已实现会话追加存储：`append_session_message`。
- 已实现轻量历史召回：`build_memory_snippet`。
- 已落地 `session_summary + turn_capsules + raw_messages` 三层 progressive memory 结构。
- 已支持基于 `session_id` 的多轮上下文延续。

#### 6）前端交互与可观测性

- 已实现 React + TypeScript 前端界面。
- 已通过 `useForumChat` 消费后端 SSE 事件。
- 已展示 `meta/status/message/done/error` 类型事件对应的状态变化。
- 已实现 Agent 状态面板、中间结果面板和报告视图切换。
- 已展示当前 `session_id` 和 memory 模式说明，便于演示多轮会话能力。

### 已验证

以下能力已可通过现有代码、接口或本地运行产物进行说明：

- `api/main.py` 中可验证 REST 和 SSE 接口定义。
- `ForumEngine/forum.py` 中可验证 Agent 顺序编排、事件发送和会话增强逻辑。
- `ForumEngine/minimal_agents.py` 中可验证三类 Agent 的结构化输出、`template_id` 多档控制和 `generation_mode` 双模式。
- `utils/session_memory.py` 中可验证本地 persistent memory 的三层结构和相关性召回。
- `web/src/hooks/useForumChat.ts` 中可验证前端对 SSE 事件的消费与状态更新。
- `api/memory_store/` 目录中已有真实会话文件，可作为 memory 生效的运行证据。

### 待增强

以下内容可以讲成后续增强方向，但不能表述为当前已完成：

- 更复杂的 LangGraph/分支工作流控制
- 更重型的 RAG / 向量数据库主链路接入
- 多用户与权限体系
- 更完整的自动化测试与监控
- 并行调度、更细粒度 streaming 和生产级重试策略

## 3. 当前主叙事

### 项目是做什么的

这是一个面向实习/求职准备场景的多 Agent 研究助手。用户输入目标岗位、公司或面试准备问题后，系统依次完成岗位信息提炼、候选人视角分析和结构化求职报告生成。

### 为什么和 LangChain 有关系

项目并不是“完全手写的聊天壳子”。它的起点来自 LangChain 1.0 的节点链和工作流思路，以及 BettaFish 开源多 Agent 架构。当前版本没有继续强调重型框架堆叠，而是把 LangChain 的核心价值保留下来：

- 节点化拆分任务
- 中间结果结构化传递
- Prompt 驱动的多阶段 workflow
- 对外暴露可观察的 Agent 执行链路

### 你实际做了什么改造

- 把通用研究链路重新定位为求职研究助手。
- 将主流程收敛为 3 个核心 Agent，降低讲述复杂度。
- 用 FastAPI 暴露统一 REST/SSE 接口。
- 用 React 前端展示 Agent 状态、中间结果和报告输出。
- 新增本地 progressive memory 和相关性召回。
- 为每个 Agent 增加 `llm/fallback` 双模式和输出档位控制。

## 4. 对外可引用说法

下面这些表述可直接用于简历、项目介绍和面试：

- 基于 LangChain workflow 思路和开源多 Agent 架构完成求职场景二次改造。
- 通过 `QueryAgent -> InsightAgent -> ReportAgent` 实现轻量多 Agent 顺序编排。
- 后端以 SSE 返回 Agent 状态与结构化中间结果，前端实时消费并展示执行过程。
- 通过 progressive memory 实现多轮上下文延续，并结合 fallback 提升演示稳定性。

下面这些说法当前不建议使用：

- 深度使用 LangGraph 完成复杂图编排
- 完整复现 BettaFish 全架构
- 已建成成熟 RAG 平台或企业级知识库
- 已具备生产级可观测体系和多租户能力

## 5. 二期规划

如果后续继续增强项目，优先方向建议如下：

1. 增强 LangChain/Agent 证据链
- 补更清晰的 workflow 图和节点说明。
- 将部分轻量 Agent 逻辑进一步映射回显式的链式节点表达。

2. 增强工程可验证性
- 增加单元测试和端到端测试。
- 增加更完整的日志、错误分类和回放样例。

3. 增强应用能力
- 引入更真实的岗位知识库或简历知识库。
- 增加更细粒度的流式输出和更丰富的模板系统。

4. 增强产品化能力
- 增加会话管理、用户体系和持久化查询历史。
- 增加报告导出、演示数据面板和更多场景模板。

## 6. 当前结论

当前版本已经足以支撑一个面向 `大模型应用 / AI 工程` 暑期实习的项目叙事：

- 有 LangChain/Agent workflow 背景
- 有明确的场景化改造目标
- 有真实的多 Agent 编排主链路
- 有 SSE 状态流和前后端联动
- 有 progressive memory 与 fallback 机制

因此，现阶段最稳的讲法不是“完整复现了原项目”，而是：

> 我基于 LangChain 思路和 BettaFish 开源多 Agent 架构完成了求职场景的二次改造，把一个偏通用研究的系统收口成了可运行、可解释、可演示的 LLM 应用工程项目。
