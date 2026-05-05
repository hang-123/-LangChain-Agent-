# 逻辑层说明：确定性 Tools / Skill 执行机制

这次改造后的逻辑层，不再让大模型自主猜工具，也不走 `bind_tools` 黑盒路由。

系统采用的是“产品层叫 Skill，代码层落成 Tools”的确定性架构：

- 产品视角：可以把每个本地检索能力理解为一个 Skill
- 工程视角：这些能力统一实现为 `api/tools/` 下的纯异步 Python 模块
- 调度视角：只有 `SearchAgent` 有权选择并执行这些 Tools，选择逻辑完全写死在 Python if-else 中

## 一、执行顺序

整个流程固定为：

`IntentRouterNode -> SearchAgent -> QueryAgent -> InsightAgent -> ReportAgent -> ReviewAgent`

每一层的职责如下：

### 1. IntentRouterNode

- 输入：用户原始 `query`
- 输出：
  - `State["intent"]`
  - `State["query_profile"]`
- 可选意图：
  - `general`
  - `tech_coding`
  - `salary_culture`

它做两件事：

- 快速判断这次调研更偏通用面经、技术编码，还是薪资文化
- 抽取 `query_profile`，尽量保住细分岗位信息，不把“推荐后端”“广告后端”“数据平台后端”压扁成普通“后端”

`query_profile` 当前包含：

- `company`
- `role`
- `team_hint`
- `job_level`
- `domain_hint`
- `priority_topics`

### 2. SearchAgent

- 输入：`query + intent + query_profile`
- 行为：根据 `intent` 和 `query_profile` 在代码里直接选择本地 Tools，并发执行
- 输出：
  - `State["context"]`
  - `insights.company`
  - `insights.role`
  - `insights.search_queries`
  - `insights.source_urls`
  - `insights.evidence_count`
  - `insights.search_failures`

这里不会让 LLM 决定“该调哪个工具”，而是直接在 Python 里按意图分流。

并且检索包不再只是“岗位通用 query”，而是固定拆成三路：

- 公司画像：业务线、组织特征、产品场景、技术文化、招聘页
- 岗位画像：JD、职责、任职资格、关键技术栈
- 面试画像：真实面经、高频问题、系统设计、算法/项目追问

当前分流逻辑：

- `general`
  - `company_profile_searcher`
  - `jd_searcher`
  - `interview_searcher`
- `tech_coding`
  - `company_profile_searcher`
  - `jd_searcher`
  - `interview_searcher`
  - `tech_stack_searcher`
- `salary_culture`
  - `company_profile_searcher`
  - `jd_searcher`
  - `interview_searcher`
  - `salary_culture_searcher`

调度方式是 `asyncio.gather(..., return_exceptions=True)`，所以单个工具失败不会拖垮整轮。

SearchAgent 执行完后还会做一轮确定性重排：

- 优先保留命中目标公司 / 团队方向 / 业务域的结果
- 优先保留更近的结果
- 优先保留 JD、招聘页和高质量面经
- 限制泛经验贴占比

最终写进 `context` 的每条证据块，都会附带：

- `SOURCE_CLASS`
- `RELEVANCE_HINT`

并在 `insights` 里额外产出：

- `company_signals`
- `role_signals`
- `business_domain_hints`
- `evidence_map`
- `context_quality_score`
- `company_specific_source_count`
- `generic_source_count`

### 3. QueryAgent / InsightAgent

这两个节点仍然保留原本的 LangGraph 结构化分析职责，但现在都改成了“证据归因优先”，不再围绕泛化关键词直接套模板。

`QueryAgent` 当前会输出：

- `company_specific_requirements`
- `common_requirements`
- `technical_stack_requirements`
- `salary_signals`
- `interview_expectations`
- `evidence_map`
- `coverage_gaps`

也就是说，它不只给结论，还要说明这些结论来自哪些证据类别。

`InsightAgent` 当前会输出：

- `candidate_risks`
- `interviewer_questions`
- `prep_strategy`
- `evidence_gap_summary`
- `action_plan_items`
- `action_plan_source_coverage`

其中 `action_plan_items` 是动态行动项，不再是固定 Day1-Day7 模板。

例如：

- `tech_coding` 会更强调算法、系统设计、编码质量、工程细节
- `salary_culture` 会更强调薪资预期、团队文化、工作节奏、匹配风险

当证据不足时，这两个节点都会进入“保守降级”：

- 明确说缺什么证据
- 明确哪些判断还不能做
- 行动项优先变成“补证据”，而不是继续伪装成高质量定制报告

### 4. ReportAgent

- 使用 `streaming=True`
- 在 LangGraph `astream_events(version="v2")` 下产生 token 级 chunk
- 最终把完整 Markdown 回写到 `report_content`

### 5. ReviewAgent

这一层保留原有重试与熔断语义，但审查维度更严格：

- 结构或排版问题：回退到 `ReportAgent`
- 风险点、追问、行动清单过于模板化：回退到 `InsightAgent`
- 公司差异不足、证据归因不足、技术栈未证据化：回退到 `QueryAgent`
- 超过 `MAX_RETRIES`：熔断，并在报告顶部追加最终调优提示

新增的反模板化检查主要包括：

- 公司名是否只在标题出现一次
- 是否写出了公司独有业务 / 组织 / 产品场景
- 一周行动清单是否仍像固定 Day1-Day7 骨架
- 技术栈是否只是关键词堆砌，而没有对应证据
- 行动项是否真正绑定了 `evidence_refs`

## 二、本地 Tools 是如何加载和执行的

本次不是动态扫描式插件框架，而是“轻插件化”的显式模块组织：

- 所有本地 Tools 都放在 `api/tools/`
- 每个 Tool 都是一个纯异步 Python 函数
- `SearchAgent` 通过普通 import 引入它们
- 调用权集中在 `SearchAgent`

也就是说，这里的“Skill”是产品上的抽象名词，但在代码里没有复杂注册中心，没有模型工具调用协议，没有二次 schema 协商。

这带来的好处是：

- 延迟更低
- 稳定性更强
- 排查更直接
- 不会浪费上下文去注入一堆工具 schema

## 三、当前已有的 Tool / Skill 抽样

### 1. `tavily_searcher.py`

底层公共能力，负责：

- 调 Tavily REST API
- 做超时、异常和 fallback 处理
- 把原始结果归一化成统一结构

统一输出 `NormalizedSource`：

- `query`
- `url`
- `title`
- `snippet`
- `published`
- `score`
- `raw_type`

### 2. `company_profile_searcher.py`

用于抓：

- 公司画像
- 招聘页
- 技术文化
- 组织 / 业务背景
- 面向岗位的产品和场景线索

### 3. `jd_searcher.py`

用于抓：

- 最新 JD
- 岗位职责
- 任职资格
- 真实技术栈要求

### 4. `interview_searcher.py`

用于抓：

- 公开面经
- 高频面试题
- 面试流程
- 追问方向

### 5. `tech_stack_searcher.py`

用于抓：

- 技术栈关键词
- 系统设计相关线索
- 算法 / 编码题方向
- 工程关键词

主要服务于 `tech_coding` 意图。

### 6. `salary_culture_searcher.py`

用于抓：

- 薪资区间
- 职级待遇
- 团队文化
- 工作节奏
- 口碑 / WLB 讨论

主要服务于 `salary_culture` 意图。

## 四、context 为什么仍然保留为多行文本块

虽然底层 Tool 已经统一输出为结构化 `NormalizedSource`，但为了不破坏现有下游节点，我们仍然在 `SearchAgent` 中把它们重新编码为多行证据块写入 `State["context"]`。

这样做的目的有两个：

- 保持 Query / Insight / Report / Review 的下游兼容性
- 保留 URL、标题、摘要等硬证据，减少信息折损

一条 `context` 证据块大致长这样：

```text
[SOURCE 1]
TYPE: jd
SOURCE_CLASS: jd
QUERY: 字节跳动 后端开发 最新 招聘 JD 任职要求 技术栈
URL: https://...
TITLE: ...
PUBLISHED: ...
SCORE: ...
RELEVANCE_HINT: 标题/摘要命中目标公司；属于高价值原始画像证据
SNIPPET: ...
```

## 五、为什么这套方案比“大模型自主调工具”更适合当前项目

因为这个项目是垂类效率工具，不是开放世界 Agent 平台。

我们要的是：

- 确定性
- 低延迟
- 可追踪
- 易维护

而不是：

- 自主规划很强但不稳定
- 每次都把工具 schema 塞给模型
- 工具选择不可控
- 调试困难

所以这次逻辑层升级的核心不是“让模型更像 Agent”，而是“让工程层更像一把稳定的专业工具”。
