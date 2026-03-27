# 基于 LangChain 的多 Agent 求职研究助手

副标题：参考 BettaFish 开源架构并完成场景化二次改造

## 1. 简历项目标题

`基于 LangChain 的多 Agent 求职研究助手`

## 2. 项目简介（80-120 字）

基于 LangChain 思路与开源多 Agent 架构完成二次改造，使用 Python FastAPI 和 React 落地求职研究助手。系统围绕 `QueryAgent -> InsightAgent -> ReportAgent` 完成任务编排，并通过 SSE 实时返回 Agent 状态与中间结果；同时引入 progressive memory、本地会话持久化和 LLM/fallback 双模式，兼顾多轮上下文效果、可观测性与演示稳定性。

## 3. 简历 Bullet（固定 3 条）

- 参考 BettaFish 开源多 Agent 架构，结合 LangChain 的节点化 workflow 思路，将通用舆情/研究链路裁剪为面向求职场景的 `QueryAgent -> InsightAgent -> ReportAgent` 三阶段编排流程。
- 设计并联通 FastAPI `POST /api/forum/run` 与 `GET /api/forum/stream` 接口，前端基于 SSE 消费 `meta/status/message/done/error` 事件，实时展示 Agent 状态与结构化中间结果，提升多 Agent 执行过程的可观测性。
- 实现本地 progressive memory 机制，按 `session_summary + turn_capsules + raw_messages` 三层结构保存会话，并结合 `generation_mode=llm/fallback` 与 `template_id` 多档输出控制，平衡上下文质量、系统稳定性与 token 成本。

## 4. 技术栈关键词

`Python, FastAPI, React, TypeScript, LangChain, Multi-Agent, SSE, Prompt Engineering, Session Memory`

## 5. 30 秒介绍版

这个项目最初是基于 LangChain 思路和 BettaFish 开源多 Agent 架构做复现与理解，后面我把它裁剪成了一个面向实习求职场景的轻量 Agent 应用。系统通过 `QueryAgent`、`InsightAgent`、`ReportAgent` 顺序编排完成岗位理解、候选人洞察和报告生成，同时用 SSE 展示 Agent 执行状态，并通过 progressive memory 做多轮上下文召回。

## 6. 1 分钟介绍版

这个项目我没有直接停留在“复现开源框架”这一步，而是基于 LangChain 的 workflow 设计思路，把原本偏通用研究的多 Agent 架构收缩成一个求职研究助手。后端由 `ForumEngine` 作为主编排器，按 `QueryAgent -> InsightAgent -> ReportAgent` 的顺序执行，分别负责岗位与公司信息提炼、候选人准备策略分析和最终 Markdown 报告生成。

工程上我重点做了三件事。第一，保留了 Agent 职责拆分与结构化输出的设计，让每个阶段都有清晰输入输出，而不是一个大 Prompt 直接出最终答案。第二，打通了 FastAPI 和 React 的前后端链路，后端通过 `/api/forum/stream` 输出 SSE 事件，前端实时展示 Agent 状态和中间结果。第三，补了多轮会话能力，memory 采用 `session_summary + turn_capsules + raw_messages` 的渐进式结构，本地持久化后按相关性召回，同时每个 Agent 支持真实 LLM 和 fallback 双模式，保证演示环境下主链路稳定可跑。

## 7. 3 分钟介绍版

这个项目最开始是我基于 LangChain 和 BettaFish 开源多 Agent 架构做的一次复现和拆解。原始方向更偏通用研究与舆情分析，但如果直接拿来做求职简历项目，会面临两个问题：一是场景太泛，不容易形成清晰的用户价值；二是系统较重，面试里很难在几分钟内把重点讲明白。所以我后续做的核心工作，不是继续堆功能，而是做场景化裁剪和工程收口。

我把主链路收缩成三个 Agent。`QueryAgent` 负责从用户输入里抽取目标公司、岗位、候选人目标和关注重点，并以结构化 metadata 输出；`InsightAgent` 基于上游结果继续生成候选人风险点、准备策略和面试官关注点；`ReportAgent` 再把前两个阶段的结果整合成最终的中文 Markdown 报告。这个设计本质上沿用了 LangChain 式的节点化 workflow 思路，但没有把所有逻辑都绑死在复杂框架编排上，而是针对求职场景保留了最有价值、最容易验证的闭环。

在工程落地上，我重点做了四件事。第一是编排器设计，`ForumEngine.run_session` 和 `ForumEngine.stream_session` 负责统一管理顺序执行、消息收集和状态分发。第二是状态流，我把后端 `/api/forum/stream` 设计成 SSE 接口，输出 `meta/status/message/done/error` 五类事件，前端 `useForumChat` 按事件驱动更新 Agent 状态栏、消息区和报告视图，这样多 Agent 不是“黑盒生成”，而是用户可见的执行过程。第三是上下文管理，我实现了本地 progressive memory，把会话拆成 `session_summary`、`turn_capsules`、`raw_messages` 三层结构，再通过 `build_memory_snippet` 按相关性召回历史，而不是把所有聊天记录直接塞回 prompt。第四是稳定性设计，三个 Agent 都优先走真实 LLM，当模型不可用时自动切换到 fallback 规则模式，并通过 `generation_mode` 显式标识当前结果来源，方便前端展示和面试讲述。

这个项目我最想强调的不是“我用了某个 Agent 框架”，而是我能基于 LangChain 和开源架构完成一次有取舍的二次改造，把一个偏 demo 的多 Agent 系统收口成一个可运行、可解释、可演示的 LLM 应用工程项目。它现在还不是生产级平台，但已经把 Agent workflow、状态流、memory、fallback 和前后端联动这些关键点打通了。

## 8. 高频追问与回答

### Q1. 这个项目和 LangChain 的关系是什么？

项目最初基于 LangChain 1.0 的流水线/节点链思路以及 BettaFish 多 Agent 架构做复现与拆解，后续我没有继续往重型框架堆叠，而是保留 Agent 拆分、节点化结构化输出和 workflow 编排这些核心思想，再把通用研究链路裁剪成求职场景的轻量闭环。

### Q2. 为什么用多 Agent，而不是一个大 Prompt？

因为这个项目更强调职责清晰和过程可观测。`QueryAgent` 负责意图和岗位信息提炼，`InsightAgent` 负责候选人视角分析，`ReportAgent` 负责最终整合。拆开后每一步的输入输出都更明确，前端也能展示中间结果和状态变化，出了问题更容易定位。

### Q3. 为什么没有直接上 LangGraph 或更重的 Agent 平台？

当前版本的目标是做一个轻量但完整的 LLM 应用闭环，而不是先做平台化。对求职场景来说，最重要的是编排逻辑清楚、状态流可见、上下文延续自然、接口异常时还能稳定运行。LangGraph 或更重的平台更适合后续把并发、分支控制、复杂 tool calling 做大之后再引入；现在我先把最关键的产品闭环和工程点做扎实。

### Q4. 既然说参考开源项目，你自己的改造点是什么？

我的工作重点不是“照搬”，而是“裁剪 + 收口 + 重构表达”。具体包括：把通用研究系统重新定位成求职研究助手；把主流程收敛为三个核心 Agent；用 FastAPI 提供统一 REST/SSE 接口；前端新增 Agent 状态面板和结构化中间结果展示；补上本地 progressive memory；为每个 Agent 增加 LLM/fallback 双模式和输出档位控制。这些改造决定了它从“架构参考”变成“可讲、可演示、可投递”的项目。

### Q5. 你为什么还保留 fallback？

因为这是一个演示型 LLM 应用。真实模型接口可能受到网络、鉴权、限流或配置影响，如果某一轮直接失败，整个体验就断了。fallback 的作用不是替代 LLM，而是保证主链路不断，并且通过 `generation_mode` 明确告诉前端和使用者当前结果是 `llm` 还是 `fallback`，这也是一种工程上的可观测性。

### Q6. 现在的 memory 是怎么设计的？

我没有把 memory 简单做成聊天记录堆积，而是做成了三层结构：`session_summary` 记录会话级摘要，`turn_capsules` 记录每一轮的压缩结果和结构化标签，`raw_messages` 记录原始消息。下一轮提问时优先读取 summary 和 capsule，再通过相关性选择历史片段拼接到当前 query 后面，避免上下文无限膨胀。

### Q7. 你是怎么控制 token 成本的？

主要有两层。第一层是 `template_id`，支持简洁、标准、详细三档输出，直接影响每个 Agent 的信息粒度。第二层是 memory 注入控制，系统不会把完整历史原文全部回灌给模型，而是优先使用会话摘要和压缩后的 capsule，这样可以减少上下文长度和无关噪音。

### Q8. 项目里哪些地方能体现 Agent 可观测性？

后端 `/api/forum/stream` 会持续发送 `meta/status/message/done/error` 事件，前端 `useForumChat` 消费这些事件后，分别更新 Agent 状态、消息列表和报告内容。这样用户能看到每个 Agent 什么时候开始、什么时候结束、输出了什么结构化结果，也方便调试和面试讲解。

### Q9. 为什么说这是“轻量化”而不是“弱化”？

因为我保留的是 Agent 应用最关键的骨架，而不是把复杂度简单删掉。这个项目依然有多 Agent 编排、结构化输出、上下文管理、SSE 状态流和 fallback，只是没有提前引入重型 RAG、复杂数据库层、并行调度和平台化控制面。这个取舍是为了先形成一个稳定、可解释、可验证的最小闭环。

### Q10. 当前版本离生产化还差什么？

还差更完整的测试、观测、权限与多用户能力，更强的知识库/RAG 体系，以及更细粒度的并发调度与错误恢复机制。当前版本更适合展示 Agent workflow 和 LLM 应用工程能力，而不是直接作为生产级平台。

## 9. 取舍总结

- 保留 `LangChain / Agent workflow` 作为核心技术背景，但不把项目讲成“只会调框架”。
- 保留“基于开源架构改造”的真实性，但强调你的贡献是场景裁剪和工程收口。
- 不夸大为“完整复现 BettaFish 全架构”或“成熟 RAG 平台”。
- 重点突出已经落地并可验证的工程点：编排、状态流、memory、fallback、前后端联动。

## 10. 最推荐的收口句

如果一句话总结这个项目，我会说：

> 我做的是一个基于 LangChain 思路和开源多 Agent 架构二次改造的求职研究助手，重点不在于堆很多框架能力，而在于把 Agent workflow、SSE 状态流、progressive memory、fallback 和前后端联动这些关键工程点真正打通。
