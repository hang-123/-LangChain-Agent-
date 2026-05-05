# 深挖追问版回答

## 一、项目深挖回答模板

### 1. 你先整体介绍一下这个项目

这个项目是一个面向面试准备场景的多 Agent 求职研究系统。用户输入公司、岗位和研究目标后，系统会自动完成意图识别、检索真实 JD / 面经 / 公司信息、做证据归因、生成风险诊断和行动清单，最后输出一份带真实来源链接的研究报告。  
和普通 `LLM + 搜索 + 总结` Demo 不一样的地方在于，我没有把它做成开放式自主 Agent，而是用 LangGraph 搭了一个固定的执行状态机，并在外面补了一层 harness 控制平面。现在这版系统已经把检索阈值、质量门禁、回退矩阵、报告章节规则、评测标准等关键行为从 Prompt 中外移到了 policy 和 contracts 层。

### 2. 这个项目当前的核心架构是什么

当前架构可以分成 6 层：

- API 入口层：负责同步执行、SSE 流式执行、case 列表和 eval 批跑
- Execution Runtime：负责一次 run 的生命周期管理，包括 `run_id`、`run_manifest`、trace 和质量摘要
- Policy Control Plane：负责检索阈值、质量阈值、回退策略、报告章节和评测分数线
- Structured Contracts：负责 `EvidenceItem`、`Claim`、`ActionPlanItem`、`QualitySummary` 等显式对象
- Agent Pipeline：负责 `IntentRouter -> Search -> Query -> Insight -> QualityGate -> Report -> Review`
- Eval / Persistence：负责 case replay、per-node scorecard、运行产物持久化

所以现在这套系统已经不是单纯的 Prompt workflow，而是一个 policy-driven 的 research harness。

### 3. 为什么不用开放式 Agent，而要做确定性工作流

因为这个项目不是开放世界任务规划，而是围绕“公司 + 岗位 + 面试准备”做单次深度研究。  
如果把工具选择、流程规划、重试逻辑都交给模型，短期会更灵活，但会带来几个问题：

- 工具调用不可控，结果波动大
- 失败时难以判断是 retrieval、attribution 还是 synthesis 问题
- Prompt 一改，系统行为容易整体漂移

所以我把系统做成固定链路，再把系统行为外移到 policy 层，让模型主要负责局部归纳和语言生成，而不是主导整个控制流。

### 4. SearchAgent 在这套架构里的职责是什么

SearchAgent 的职责不是“搜信息”，而是生成可审计证据集。  
它会根据 intent 和 query_profile 确定性选择工具，生成 `query_pack`，并发拉取公司画像、JD、面经、技术栈或薪资文化信息，再做结果重排、失败分类、source tier 统计和证据裁剪，最后输出：

- `evidence_items`
- `retrieval_diagnostics`
- `query_pack`
- `source_tier_counts`
- `failure_breakdown`

也就是说，它是整个 harness 里的检索控制点，而不是一个简单的 search wrapper。

### 5. 你是怎么把系统从 Prompt 驱动往 Harness 驱动升级的

我主要做了三件事：

- 把阈值和策略从 Prompt 中外移到 `policy`，比如最小证据数、最小 claim 覆盖率、最大重试次数、issue code 到 retry target 的映射
- 把节点输入输出收敛成结构化 contracts，比如 `EvidenceItem`、`Claim`、`ActionPlanItem`、`QualitySummary`
- 把报告层改成 renderer-first，把 Review 拆成规则检查器 + LLM reviewer

这样一来，Prompt 主要负责“怎么表达”，而 policy、contracts 和状态机负责“系统怎么运行、怎么判断、怎么回退”。

### 6. ReviewAgent 为什么要拆成 rule checker 和 LLM reviewer

因为报告审查里有两类问题：

- 硬约束问题：比如缺章节、URL 不够、技术栈没证据、行动清单模板化，这些适合规则检查器处理
- 软质量问题：比如表达是否自然、风险点像不像真实面试官口吻，这些更适合 LLM reviewer 处理

所以我把 Review 拆成：

- `rule_checker`：规则优先，负责稳定发现硬问题
- `llm_reviewer`：只补软质量问题

这样能避免把所有质量判断都压给 Prompt，也更容易解释某轮回退到底是为什么发生的。

### 7. 报告层为什么改成 renderer-first

因为之前如果让 LLM 自由生成整份报告，质量仍然会强依赖 Prompt，结构和事实边界容易漂。  
现在报告主体由 renderer 负责：

- section 顺序由 policy 控制
- 内容来源优先来自 `claims / action_plan_items / evidence_items`
- evidence section 直接渲染真实链接

LLM 只负责局部润色，比如 overview lead 和 interview angle。这样可以显著降低 Prompt 漂移对最终交付结构的影响。

### 8. 这个项目里 Harness Engineering 的体现具体有哪些

现在这版的 harness 体现主要在：

- 每次 run 都有唯一 `run_id`
- 会生成 `run_manifest`，记录 prompt version、policy version、code version、model、experiment assignment
- 同步接口和流式接口共享统一 trace 和质量摘要
- 有 `root_cause_history`
- 有 `research case`、`case evaluation`、`node scorecard`
- 有持久化仓储保存 run / trace / eval 结果

这意味着系统已经不只是“能跑”，而是具备持续优化、回归评估和问题复现的工程底座。

### 9. 这个项目里你觉得最难的问题是什么

最难的不是把报告写出来，而是避免系统在证据不足时“写得很像，但其实不可信”。  
尤其是求职研究这种场景，最容易出现的假高质量问题是：

- 公司特异性不足
- 技术栈没有证据映射
- 行动清单像固定模板
- 薪资 / 文化判断其实证据很弱

所以我后面重点做了 QualityGate、Review、policy threshold、renderer-first 和 eval suite，让系统在证据不够时宁可保守，也不要伪装成定制化高质量输出。

### 10. 如果继续优化，你下一步会做什么

如果从工程角度继续升级，我会优先做：

- 把 Search 的 tool mapping 和排序策略进一步 policy 化
- 把 persistence 从文件仓储升级成数据库或 queryable store
- 把 eval 真正接进 CI / release gate
- 把 user feedback 接到 case / policy / score weighting 闭环里

如果从产品角度继续升级，我会做：

- 用户画像输入
- run 历史与结果纠偏
- evidence explorer
- 面试答题稿和行动项完成状态管理

## 二、最容易被问的 10 个问题与答法

### 1. 这个项目解决的核心问题是什么？

它解决的是“面试准备信息分散且可信度难判断”的问题。  
求职者通常能搜到很多 JD、面经、公司信息，但很难判断哪些是公司特异性要求、哪些是泛经验贴、下一步到底该先准备什么。这个系统就是把检索、归因、风险分析和行动计划整合成一轮可信的研究输出。

### 2. 为什么选择 LangGraph，而不是直接写链式调用？

因为这个项目不是单轮 Prompt 拼接，它有明确的节点边界、回退路径和熔断语义。  
LangGraph 适合表达状态机式流程，比如 Review 不通过时回退到 Query / Insight / Report，并且能统一维护中间状态。这比手写链式 `if-else` 更稳，也更适合后续做 trace 和 eval。

### 3. 你怎么保证输出不是胡编的？

主要通过四层约束：

- SearchAgent 输出结构化 `evidence_items`
- QueryAgent 要求 claims 尽量绑定 `evidence_refs`
- QualityGate 根据阈值判断是否进入保守模式
- Review 使用 rule checker + llm reviewer 双层审查

如果证据不够，系统会 conservative，而不是继续生成看起来很完整但其实不可信的结论。

### 4. 这个项目为什么说是 harness，而不是普通多 Agent 项目？

因为现在控制权已经不主要在 Prompt，而是在 harness 层：

- policy 控制检索阈值、质量阈值和重试矩阵
- run_manifest 记录版本和实验信息
- contracts 约束节点边界
- eval suite 负责回归
- persistence 负责记录 run / trace / eval

也就是说，模型只负责局部推理和表达，系统行为主要由控制平面和状态机决定。

### 5. SearchAgent 为什么不直接让模型自己选工具？

因为这不是开放任务平台，而是垂类研究系统。  
让模型自主选工具的代价是延迟更高、路径更不可控、失败原因更难定位。我这里把工具组合和检索路径做成确定性调度，再通过 policy 约束检索要求，换来了更好的稳定性和更低的调试成本。

### 6. 你怎么做质量评估？

我现在已经不是只做最终结果打分了，而是做分节点评分。  
Eval 里会分别看：

- retrieval
- attribution
- insight
- report compliance

再结合最终 `quality_mode`、`root_cause` 和 case 规则决定这轮是否通过。这样后续退化时，不只是知道“差了”，还能知道差在 Search、Query/Insight 还是 Report。

### 7. 这个项目里最体现工程性的部分是什么？

我认为最体现工程性的不是模型调用，而是这几个点：

- policy control plane
- structured contracts
- run manifest
- rule checker + LLM reviewer
- renderer-first report
- eval scorecard + persistence

这些设计说明项目已经在往可持续演进的系统走，而不是一次性跑通的 Demo。

### 8. 如果某个检索工具失败了，系统怎么办？

SearchAgent 本身支持并发调度和单点失败容忍。  
某个 Tool 失败后，不会直接让整轮任务崩掉，而是把失败记录写进 `retrieval_diagnostics`，并做 `failure_breakdown`。后续由 QualityGate 和 Review 根据证据缺口决定是否保守降级、是否继续交付、是否回退重写。

所以我的目标不是“所有组件都成功”，而是“部分失败时系统仍然有清晰控制策略”。

### 9. 这个项目为什么值得写到简历里？

因为它已经不是普通的 `LLM + 搜索 + 页面展示` 项目，而是一个有明确架构分层、控制平面、质量门禁、回退策略、报告渲染和评测闭环的完整系统。  
面试时它能覆盖：

- Agent / LLM 应用设计
- 检索增强与证据归因
- 状态机工作流编排
- Policy-driven control plane
- 质量控制与回退机制
- Renderer-first 输出设计
- Eval / 回归 / 持久化

这比普通聊天项目更能体现系统设计和工程化能力。

### 10. 如果面试官问“它能不能真正跑通”，你怎么回答？

我会如实回答：  
这套系统前后端链路、流式输出、case replay、eval 批跑和 run 持久化都已经实现，仓库里也保留了真实运行产物。真正上线运行时，前提是 Python 解释器和依赖环境要正确绑定，比如 FastAPI、LangGraph、LangChain、Tavily 等依赖装在实际启动后端的解释器里。  
也就是说，项目本身是可运行的，但运行成功依赖环境一致性，这也是我后面会继续优化的工程点之一，比如把启动方式、依赖管理和运行检查做得更强约束。

