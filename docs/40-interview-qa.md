# 基于当前项目的 Agent 面试题回答

## 使用原则

- 这份回答优先基于当前已经落地的 `BettaFish LangGraph 求职研究助手` 来说。
- 仓库里 `job-assistant/specs/` 的内容我只会当成“下一阶段设计稿”，不会和已实现能力混着讲。
- 遇到 `RAG / MCP / VLM / 移动端 / 微信小程序` 这类当前仓库没有完整落地的题，建议你诚实回答“当前项目没做到生产实现，但我会这样设计”。

---

## 一、先背这条主线

一句话版：

这个项目本质上不是开放式自主 Agent，而是一个基于 LangGraph 的确定性 research harness。主链路是 `IntentRouterNode -> SearchAgent -> QueryAgent -> InsightAgent -> QualityGate -> ReportAgent -> ReviewAgent`，重点在于把检索、证据归因、质量闸门、回退重试和评测闭环工程化。

展开版：

我做的是一个面向求职研究场景的多节点 Agent 系统。用户输入“公司 + 岗位 + 研究目标”后，系统先识别意图和 query_profile，再由 SearchAgent 并发调度多个检索工具，拉回真实 JD、公司画像、面经、技术栈或薪资文化证据；然后 QueryAgent 把结论收敛成带 `claims + evidence_refs` 的结构化结果，InsightAgent 生成风险点、追问和动态行动清单，QualityGate 做成稿前门禁，ReportAgent 用 renderer-first 方式生成 Markdown 报告，最后 ReviewAgent 用 `rule checker + LLM reviewer` 双层审查，必要时回退到 Query / Insight / Report 节点重写。

---

## 二、Agent 项目深挖题

### 1. 介绍一下 Agent 实习的项目架构

我会直接按分层来讲。

- 接口层：`FastAPI` 提供同步接口、SSE 流式接口、case replay 和 eval 接口。
- 编排层：`LangGraph StateGraph` 负责固定状态机和条件回退边。
- Agent 层：`IntentRouterNode / SearchAgent / QueryAgent / InsightAgent / QualityGate / ReportAgent / ReviewAgent`。
- Tool 层：`api/tools/` 下的异步检索工具，负责公司画像、JD、面经、技术栈、薪资文化检索。
- Control Plane：`policy + contracts + run_manifest`，把阈值、章节规则、重试矩阵、评测门槛从 Prompt 里外移。
- Eval / Persistence：保存 `run_trace / quality_summary / perf_bill / eval_result / security_event`，支持回放和回归。

面试里我会强调，这不是“LLM 自己决定一切”的黑盒，而是一个 policy-driven 的确定性工作流。

### 2. 一共用了几个 Agent？每个 Agent 分别负责哪一块？

如果按当前执行节点算，一共是 7 个节点：

- `IntentRouterNode`：识别 `general / tech_coding / salary_culture`，并抽取 `query_profile`
- `SearchAgent`：确定性选择 Tools，并发检索，生成 `evidence_items / retrieval_diagnostics / query_pack`
- `QueryAgent`：把证据收敛成 `claims`、岗位要求、技术栈、面试期待、coverage gaps
- `InsightAgent`：生成风险点、面试官追问、准备策略、动态行动清单
- `QualityGate`：按 policy 判断是否进入 `normal` 或 `conservative` 模式
- `ReportAgent`：renderer-first 生成 Markdown 报告，只让 LLM 做局部润色
- `ReviewAgent`：规则检查 + LLM 软审查，决定通过、回退还是熔断

如果面试官严格问“几个 Agent”，你可以说工程上我把它讲成 5 个核心 Agent，加 1 个 Router 和 1 个 Quality Gate。

### 3. 什么情况下用单 Agent，什么情况下用多 Agent？

单 Agent 适合目标单一、步骤短、结构清晰的任务，比如只做意图分类、只做字段抽取、只做一段文本改写。

多 Agent 或多节点工作流适合：

- 链路长
- 中间产物需要复用
- 有明确的阶段职责
- 失败后希望局部回退，而不是整条链路重跑
- 需要可解释、可评测、可观测

当前项目之所以拆多节点，是因为检索、归因、风险诊断、成稿、审查本身就是不同问题，混成一个大 Agent 会更难控。

### 4. 多 Agent 之间的数据传输或者通信一般怎么做？

当前项目不是让 Agent 之间用自然语言“聊天”，而是统一通过 `state` 里的结构化字段传递：

- `query_profile`
- `context`
- `evidence_items`
- `retrieval_diagnostics`
- `claims`
- `action_plan_items`
- `review_feedback`

也就是说，我更偏向传结构化 artifact，而不是传一大段自由文本，这样更稳，也方便 schema 校验、trace 和 eval。

### 5. 如果多个 Agent 之间有并发的情况，你一般怎么处理？

当前项目真正做并发的地方主要在 `SearchAgent`。它会把多个 Tool 做 fan-out，再在本节点内部 fan-in 汇总：

- 用 `asyncio.gather(..., return_exceptions=True)` 并发调用多个检索工具
- 所有结果回来后统一去重、重排、裁剪和失败归类
- 下游节点只消费合并后的结构化证据

我的原则是：并发只放在互不依赖、可独立失败的阶段；涉及依赖关系的地方，用工作流边界做 barrier。

### 6. 如果多个 Agent 同时去操作数据库或者文件，这种并发你怎么处理？

当前项目主要有 3 类持久化：

- append-only JSONL
- SQLite cache
- SQLite query store

已经做的处理有：

- SQLite 开启 `WAL`
- run trace / security event 用追加写，避免覆盖写冲突
- cache 用主键覆盖更新
- run 产物按 `run_id` 分目录存储，尽量减少资源争用

如果真的扩到多个 worker 同时写同一业务对象，我会再加：

- 幂等键
- 事务
- 乐观锁版本号
- 单 writer 队列

### 7. 如果它们是异步执行的，这边会考虑怎么做？

我一般会关注 5 件事：

- 任务状态：`started / completed / failed`
- 超时和异常分类
- 可重试和不可重试错误分离
- 幂等，避免重试时把写操作重复执行
- 取消和恢复能力

当前项目里，Search 的并发工具失败不会拖垮整轮，因为异常会被收敛进 `failure_breakdown`，后面再由 QualityGate 和 Review 决定是否保守降级。

### 8. RAG 混合检索机制，是怎么实现的？

这题要诚实一点：当前仓库严格说还不是“向量库 + BM25 + reranker”的经典混合 RAG，它更像“实时 Web 检索 + 确定性重排 + 证据归因”。

当前已实现的是：

- 根据 `intent + query_profile` 生成 query pack
- 并发调用不同检索工具
- 对结果按公司命中、团队方向、业务域、发布时间、来源类型做重排
- 限制泛经验贴比例
- 输出 `evidence_items` 给下游

如果面试官继续追问“真正的 hybrid retrieval”，我会补一句：这版还没接向量库，下一步会把历史 JD、历史面经、内部案例接成 `keyword + vector + metadata filter + rerank` 的混合召回。

### 9. 项目里有没有遇到幻觉问题？怎么减少、规避？

有，主要有三类：

- 检索证据不够时，模型容易把泛经验贴包装成公司特异性结论
- 生成行动清单时容易模板化
- 报告成稿时容易把弱证据写成强结论

我的处理方式是：

- Search 阶段强制产出 `evidence_items`
- Query 阶段把结论收敛成 `claims + evidence_refs`
- QualityGate 在证据不足时切 `conservative`
- Report 改成 renderer-first，减少自由生成面积
- Review 阶段检查公司特异性、技术栈证据化、行动项证据绑定

核心思路就是“证据不足时宁可保守，也不要写得像真的”。

### 10. 你之前都开发过哪些工具 / function？

结合当前项目，我会重点讲这些：

- `company_profile_searcher`
- `jd_searcher`
- `interview_searcher`
- `tech_stack_searcher`
- `salary_culture_searcher`
- `tavily_searcher` 这个底层归一化搜索器

再往上是一些支撑函数：

- query profile 提取
- 证据重排和评分
- coverage gap 识别
- rule checker
- quality gate
- renderer

所以我的重点不是只写了几个 function，而是把 Tool、contract、policy 和 review 规则串成完整闭环。

### 11. 你提到 self-refine / 自我修正，你做过哪些修正策略？

当前项目的自我修正是工程化的，不是让模型无限反思。

- `QueryAgent / InsightAgent` 结构化输出失败时，走 heuristic fallback
- `QualityGate` 根据阈值切到 `conservative`
- `ReviewAgent` 发现问题后，按 issue code 回退到 `query / insight / report`
- 超过 `MAX_RETRIES` 直接熔断，不继续无意义重试
- `ReportAgent` 只做 renderer-first，局部润色失败也不影响主体报告

所以我的修正策略更像“定向 repair + 限次 retry + 可降级”。

### 12. 如果 API 返回结果有字段缺失，或者有冗余内容，你会怎么处理？

会，当前代码里已经这么做了。

- 先通过 Pydantic schema 做结构化约束
- 如果 LLM 结构化输出缺字段，就用 `_fill_query_response_defaults` / `_fill_insight_defaults` 回填
- 多余字段不会进入 contract
- 极端情况下直接走 heuristic fallback

我的原则是脏数据不要直接透传给下游，要先在边界层修复、过滤或降级。

### 13. 你对 MCP 了解多吗？有没有写过相关的 MCP？

基于当前仓库，最稳妥的答法是：

我理解 MCP 的核心价值，知道它是把 model 和 tool/resource/prompt 之间的交互做标准化协议；但当前这个项目没有真正实现 MCP Server，它走的是更轻量、确定性的 Python Tool 调度。也就是说，我对 MCP 概念和接入方式了解，但当前项目的重点不在 MCP，而在 harness、policy 和结构化 contracts。

### 14. 假设 Agent 调工具失败了，一般怎么处理？

当前项目的处理方式是：

- Search 并发调用时用 `return_exceptions=True`
- 单个工具失败只记到 `execution_failures`
- 统一归类成 `timeout / api_failure / no_result / too_generic / runtime_failure`
- 写入 `retrieval_diagnostics.failure_breakdown`
- 下游继续执行，但 QualityGate 和 Review 会决定是否保守降级

我特别强调一点：工具失败后不能让模型自己脑补结果。

### 15. 你之前开发过 Agent，怎么管理 context？

当前项目的 context 管理是分层的：

- `query_profile`：保存公司、岗位、团队方向、业务域
- `context`：兼容展示层的多行证据块
- `evidence_items`：真正供下游使用的结构化事实
- `insights`：保存 claims、风险点、行动项等中间分析结果
- `review_feedback`：只给回退节点看的修正意见

另外还有两个控制手段：

- 截断：给 Query / Insight 传上下文时做长度裁剪
- 结构化优先：下游优先读 `evidence_items`，而不是直接吃原始文本

### 16. 你自己在做 AI coding 时，一般怎么用？有没有什么方法论？

我自己的方法论是：

- 先定 contract 和 state，再写 Agent
- 先写 policy 和规则，再放 Prompt
- 先做可回退的节点切分，再做生成
- 先补 eval 和 trace，再谈优化

也就是尽量把模型放在“局部推理和表达”的位置，而不是把整个系统控制权全交给模型。

### 17. 上线前主要通过什么方式保证质量？只是靠 code review 吗？

不是。当前项目已经把质量控制拆成了几层：

- rule checker
- LLM reviewer
- QualityGate
- case replay
- eval suite
- run trace / perf bill / quality summary

所以 code review 只是其中一层，真正更重要的是能不能稳定复现、定位和回归。

### 18. 除了简历上写的这些，你自己还用 AI coding 做过哪些项目？

这题必须按你的真实经历答。结合当前仓库的风格，你可以说：

除了主项目，我还会用 AI coding 做评测脚本、运行时观测、缓存层、规则检查器、文档到 schema 的转换、前后端联调原型这类工程化工作。重点是体现你把 AI 当成稳定的研发助手，而不是偶尔问几个代码片段。

### 19. 你刚才提到的 omo / openspec，是你自己的项目实践，还是从别的地方学来的？

推荐答法：

我自己的实践为主，但方法论吸收了成熟软件工程思路。比如我现在这个项目就是明显的 spec-driven / policy-driven 开发：先有 contracts、policy、eval，再去做 Agent 编排，而不是先堆 Prompt 再慢慢补工程壳。

### 20. 项目里根据评论内容判断帖子的可信度，这个流程怎么做？

当前仓库没有真正实现“评论可信度判定”这条业务线，所以别说成已落地。

你可以这样答：

如果做，我会把它拆成 `claim 抽取 -> 可信度特征提取 -> 规则分 + 模型分融合 -> 输出解释`。特征会看细节密度、时间一致性、一手经验信号、多评论互相印证、营销/灌水模式等。这个思路和我当前项目里做 evidence grounding、source tier 分类是一致的。

### 21. 在实际 AI coding 过程中，除了写 PRD、技术文档，还有什么方法能提升代码质量、降低模型乱写？

我觉得最有效的是把约束前置：

- schema 先行
- state 先行
- policy 先行
- 小步提交
- 每步都可验证

当前项目里，最能降低乱写概率的就是 `contracts + rule checker + renderer-first` 这三件事。

### 22. 你提到了 skill，你自己写过哪些 skill？

结合当前项目，我会把 skill 解释成“产品层能力块”，代码里落成 Tool 或规则模块。

当前项目里比较接近 skill 的有：

- 意图识别
- 公司画像检索
- JD 检索
- 面经检索
- 技术栈检索
- 薪资文化检索
- claim 归因
- 风险诊断
- 报告审查

我会强调：这里的 skill 不是一段 prompt，而是“输入输出明确、可测试、可组合”的能力单元。

### 23. 你自己写 skill 的时候，有没有做评测？

有，当前项目已经有 case replay 和 eval。

- 研究 case 保存在 `api/evals/research_cases.json`
- 评测分 retrieval / attribution / insight / report_compliance 四个维度
- 每次 run 都有 `run_id / manifest / trace / quality_summary`

所以我判断一个 skill 是否达标，不是只看“像不像”，而是看它能不能稳定过门槛。

### 24. 你之前有接触过移动端开发吗？

这题按真实情况答。当前仓库没有移动端代码，不要硬说做过。

如果你经验不深，可以说：

我主战场不是移动端，但对前后端联调、日志定位、接口异常、版本差异这类问题有理解；如果迁移到小程序排障，我会优先把日志、版本、复现路径和工作流编排做好。

### 25. 如果是一个微信小程序排查问题的 Agent，你会怎么做？

我会沿用当前项目这套分层思路：

- `Issue Router`：先判断是白屏、接口报错、性能、兼容性还是版本回滚问题
- `Log Retriever`：抓日志、埋点、网络请求、最近发布记录
- `Code Analyzer`：关联最近改动、报错栈、组件生命周期
- `Evidence Synthesizer`：把错误证据收敛成结构化结论
- `Fix Advisor`：给出最可能原因、验证步骤、修复建议、回滚建议
- `Review`：检查是否越过证据边界

也就是把当前求职研究系统里的“检索-归因-诊断-报告-审查”迁移到排障场景。

### 26. 你刚才提到的是 RAG / 检索，是类似根据关键词看历史有没有问题记录？

如果基于当前项目，我会说不是只靠关键词。

当前实现已经有：

- query profile 提取
- tool-level query rewrite
- 多来源检索
- 基于公司/岗位/业务域/时间/来源的重排

只是它还没接入向量库。如果扩成排障或知识库场景，我会再叠加 `keyword + vector + metadata + rerank`。

### 27. 如果不是业务代码问题，而是 JS 框架本身的 bug，Agent 怎么处理？

我会先做“责任边界识别”，而不是让 Agent 一直在业务层乱试。

- 看问题是否和特定框架版本强相关
- 看是否能脱离业务代码最小复现
- 查 release note、官方 issue、社区 workaround
- 给出结论：业务问题、配置问题、框架版本缺陷，还是该升级/回滚

这和当前项目的思路一致，先做 root cause 分类，再决定回退或修复路径。

---

## 三、第二组深挖题

### 28. 自我介绍

建议你围绕这套项目这样说：

我现在主要在做 AI 应用和 Agent 系统方向，比较关注怎么把大模型能力落成可解释、可评测、可维护的工程系统。最近做的这个项目是一个基于 LangGraph 的求职研究助手，我主要做了确定性工作流、检索层拆分、结构化 contracts、quality gate、review 回退和 eval 闭环。我的强项不是只写 Prompt，而是更习惯先把 state、tool、policy、评测和回退机制搭起来，再让模型去做局部推理和表达。

### 29. 对着一个 Agent 项目详细深挖，问架构、交互、skill、检索机制、和单智能体比好在哪里

你就抓住一条主线：

这个项目不是单 Agent 自主规划，而是确定性多节点编排。节点之间不靠自然语言自由通信，而是通过结构化 state 传 `query_profile / evidence_items / claims / action_plan_items / review_feedback`。skill 在这个项目里不是插件框架，而是产品上的能力抽象，代码上对应 Tool、规则模块和结构化节点。和单智能体相比，我这套方案更稳、更可解释、更容易局部回退和做评测；代价是工程复杂度更高。

### 30. 用的哪个基模，模型大小多少，参数是多少，有对比其他基模吗？

当前仓库默认是：

- 走 OpenAI-compatible 接口
- 默认 `base_url` 指到 DashScope compatible endpoint
- 默认模型名是 `qwen-plus`

更稳妥的答法是：

当前系统是 model-agnostic 的，我在接口层做的是兼容 OpenAI 风格 chat model，默认配置是 `qwen-plus`。这个项目的重点不在特定基模调优，而在 harness 和结构化流程控制。参数量和基模横评，如果你没有实际做，就别编，可以说“我更关注任务效果、稳定性、时延和成本，不会只背参数表”。

### 31. skill 的机制

在当前项目里，skill 更像产品层概念，工程上实际落成两类东西：

- Tool：比如 `jd_searcher / interview_searcher / tech_stack_searcher`
- Structured node：比如 QueryAgent 的 claim 归因、InsightAgent 的风险诊断

它们的共性是输入输出清晰、边界明确、能单测、能评测，不是单独一段 prompt。

### 32. 有没有做过 RAG，RAG 的分块和召回

基于当前项目要诚实说：

我做的是 evidence-grounded retrieval pipeline，但还没把它扩成完整向量 RAG。当前更偏实时 Web 检索，不涉及文档 chunk 存向量库。如果做 RAG，我会按语义单元切块，优先保留标题路径、来源类型、时间、实体信息，再做混合召回和重排。

### 33. 这个 Agent 项目有什么创新点能拿去投稿

如果讲工程创新，我会说有这几个点：

- 把开放式 Agent 收敛成 policy-driven harness
- 明确 `evidence_items / claims / action_plan_items` 这些结构化 contracts
- `QualityGate + ReviewAgent` 双层质量链路
- renderer-first 报告生成，降低 Prompt 漂移
- case replay + per-node eval + run trace

如果讲学术投稿，我会保守一点，说它目前更偏工程实践，还需要更系统的对比实验。

### 34. 问学院主要做什么

按真实情况答，这题和项目关系不大。

### 35. 当场写 prompt 做智能导购 Agent 意图识别

你可以借当前项目的 `IntentRouterNode` 思路回答：

我不会只写一句“请识别用户意图”，而会先定义：

- 意图集合
- 输出 schema
- 置信度或 reason
- 缺信息时的兜底策略
- 负例边界

当前项目里，我就是把意图识别输出成 `intent + reason + query_profile`，而不是一段自由文本。

### 36. 反问

推荐三个方向：

- 你们现在 Agent 系统里最难的点是检索、质量、评测还是工具稳定性？
- 团队现在更偏业务闭环，还是在做平台化 Agent 能力？
- 如果我加入，前两个月最希望我解决哪一类问题？

### 37. 如果面试官连续追问三四十分钟，怎么稳住主线？

你就反复拉回四个词：

- 结构化
- 分层
- 可解释
- 可评测

这是当前项目最强的主线。

---

## 四、概念题和项目映射题

### 38. 深挖实习经历，围绕项目背景与落地细节展开

建议按这个顺序讲：

- 背景：为什么普通 `LLM + 搜索 + 总结` 不够
- 方案：为什么做固定状态机和 harness
- 关键实现：Search 拆 Tool、Query 做 claim、Insight 做动态行动项、Review 做回退
- 工程化：policy、eval、trace、persistence
- 收获：稳定性、定位效率、输出可信度都更高

### 39. MinerU 输出 Markdown 相比纯文本，层级结构对检索有哪些优势？

当前项目没做 MinerU，但这题可以正常答理论：

- 标题层级能帮助切块
- 标题路径可作为 metadata
- chunk 边界更自然
- 重排和答案生成时更容易保持上下文位置感

### 40. VLM 在流程中是参与检索阶段，还是仅在最终生成答案时介入？

当前项目没有 VLM。推荐答法是：

如果原始资料里有图片、表格、截图，我更倾向让 VLM 前置到解析/检索阶段，把图像信息先转成可检索的结构化内容；只在最终回答时介入太晚了。

### 41. Ragas 里 Faithfulness 偏低，代表模型存在什么问题？

说明答案没有被检索证据充分支撑，常见原因有：

- 生成超出证据范围
- 证据归因不够严
- 检索召回本身不完整

这和我当前项目里为什么要做 `claim_evidence_coverage` 是一个思路。

### 42. LangGraph 里 Node 和 Edge 分别对应业务流程中的什么模块？

当前项目可以直接举例：

- Node 就是 `IntentRouter / Search / Query / Insight / QualityGate / Report / Review`
- Edge 就是固定流转关系
- Conditional Edge 是 Review 不通过时回退到 `query / insight / report`

### 43. 长短期记忆在实现方式上有什么差异？短期记忆一般存哪里？

当前项目更偏短期工作流记忆，主要存在 `AgentState` 里；长期记忆没有真正做成用户级 memory。

所以你可以答：

- 短期记忆：当前 run 的 state、context、insights，存在工作流状态对象里
- 长期记忆：如果后续做，会放数据库、对象存储或向量库

### 44. Agent 依据什么识别并选用工具，是工具名还是功能描述？

当前项目其实不是让模型选工具，而是代码里确定性选工具。

如果面试官追问通用设计，我会说应该主要依赖功能描述、输入输出契约和使用边界，而不只是工具名。

### 45. 向量检索与关键词检索的优缺点对比

正常答理论就行：

- 关键词检索精确、快、可解释，对实体名和术语很强
- 向量检索更能覆盖语义相近问题，但更容易召回“像相关但不够准”的内容
- 实战一般做混合召回

### 46. 为什么 RAG 相比直接调用大模型，能降低事实性错误？

因为它把回答建立在外部证据上，而不是只靠参数记忆和语言先验。当前项目虽然不是完整向量 RAG，但也是同样的思想：先检索事实，再做归因和生成。

### 47. 原始文档更新后，如何保证向量数据库索引同步更新？

当前仓库没做这部分，建议答：

我会维护 `document_id + chunk_id + version/hash`，做增量更新、原子切换可见版本、旧版本延后清理，避免检索读到一半旧一半新。

### 48. 什么是 Query Rewrite？可以解决哪些问题？

当前项目里虽然没有单独叫 Query Rewrite，但其实已经做了轻量版本：先抽 `query_profile`，再给不同 Tool 生成针对性的查询语句。

它解决的就是：

- 用户表达口语化
- 公司/岗位/团队方向混在一起
- 问题太泛
- 检索缺少业务域关键词

### 49. Temperature 调大和调小有什么影响？

当前项目关键节点基本都用低温度，因为：

- 路由、结构化输出、审查更需要稳定
- 创意不是第一优先级

### 50. CoT 思维链原理，为什么能提升复杂任务处理能力？

正常答理论即可：把复杂问题拆成中间推理步骤，降低一步到答案的错误率。

### 51. Agent 执行任务时，Thought、Action、Observation 如何循环？

这题可以答通用理论，但也可以补一句：当前项目不是纯 ReAct，而是把 Thought 更大程度外置到了状态机和 policy 里，模型主要负责局部结构化推理。

### 52. 对话长度超出上下文窗口时，有哪些处理方案？

当前项目主场景是单次深度研究，不是长对话聊天，所以主要做的是：

- 结构化状态替代长自由文本
- 证据裁剪
- 截断 context

如果扩成长会话，再加摘要压缩、外部记忆召回和滑动窗口。

### 53. 模型进行工具调用时，输出是直接结果，还是带参数的 JSON？

通用框架里通常是先输出结构化 tool call，再拿 observation 回来后继续推理。

但当前项目里更简单：模型根本不选工具，工具由代码直接调。

### 54. 系统提示词与用户提示词，对 Agent 的约束能力有什么区别？

当前项目里系统提示词主要定义角色、边界、格式和“不得越界”；用户提示词是本轮具体研究目标。

### 55. 什么是 HNSW 索引？为什么比暴力检索快？

正常答理论即可，和当前项目无直接实现关系。

### 56. 围绕 OpenClaw 展开简单讨论

如果你没有深入用过，就别展开过度。可以说自己更熟悉的是 LangGraph、结构化工具调用和 harness 这条线。

### 57. 开发 Agent 应用时，如何判断任务适合用 7B 小模型还是 70B 大模型？

我的判断标准是：

- 分类/抽取/路由/简单格式化：小模型优先
- 长链路分析、复杂归因、高质量生成：大模型更稳

当前项目其实也是这个思路，只是代码里还没有显式分模调度。

### 58. 若 Agent 反复调用同一个错误工具，优先从哪个环节修复？

如果是通用 Agent，我会先查：

- 工具描述是否模糊
- 选择策略是否有歧义
- 失败反馈是否不清晰

但当前项目更简单，因为工具选择在代码里，优先排查的是路由规则、query profile 和 tool mapping，而不是让模型自己瞎选。

### 59. 候选人反问环节

参考第 36 题即可。

---

## 五、几道容易问穿的“诚实回答”

### 1. 这个项目到底算不算多 Agent？

我会说：

严格从实现上看，它更像“多节点确定性工作流”，不是开放式自主多 Agent；但从职责拆分和中间产物协作上，也可以讲成多 Agent pipeline。面试里我会先把这个边界说清楚，避免夸大。

### 2. 这个项目现在有完整 RAG 吗？

没有完整向量 RAG。当前做的是实时 Web 检索、确定性重排、证据归因和保守生成。不要把它说成已经做了向量库、embedding、HNSW 和混合召回。

### 3. 这个项目现在有 MCP 吗？

没有。当前是本地 Python Tool 调度，不是 MCP Server。

### 4. 当前最值得你在面试里讲的亮点是什么？

我建议你重点讲 4 个：

- 固定状态机，而不是开放式黑盒 Agent
- Search 到 Query 的证据归因链路
- QualityGate + Review 的回退与熔断
- Eval / trace / persistence 的工程化闭环

### 5. 如果面试官问“你这项目最大的不足是什么”

可以直接答：

- 还没接完整向量 RAG
- 还没做真正的多模型分层调度
- 还没把 persistence 升级成更标准的服务化存储
- job-assistant 那套多 Agent 求职工作流目前更多还在 spec 阶段

这样会显得你很清楚系统边界，不会乱吹。
