# SearchOrchestrator Tool 规范（阶段二）

## 1. 目标
SearchOrchestrator 是统一搜索编排 Tool。单次 LLM 生成搜索查询词，随后纯确定性编排：并发调用 Tavily + RAG → 去重合并 → 评分排序。

将阶段一的 SearchAgent 降级为 Tool。

## 2. 职责
- 生成搜索查询词（LLM 单次调用）
- 并发调用 Tavily 搜索工具（company_profile, jd, interview, tech_stack, salary_culture）
- 并发调用 RAG 向量检索（如启用）
- URL 去重合并
- 质量评分排序
- 缓存（基于 query + intent + profile 的 hash）
- 写入 evidence_items 和 retrieval_diagnostics

## 3. 输入
```json
{
  "query": "字节跳动后端开发实习",
  "query_profile": {
    "company": "字节跳动",
    "role": "后端开发实习",
    "priority_topics": ["技术栈", "面经"]
  },
  "intent": "general",
  "policy": {}
}
```

## 4. 输出
```json
{
  "evidence_items": [],
  "query_pack": [],
  "retrieval_diagnostics": {
    "coverage_by_class": {},
    "missing_classes": [],
    "company_specific_ratio": 0.6,
    "failures": [],
    "cached": false,
    "rag_hit_count": 2,
    "rag_failures": []
  },
  "context": [],
  "insights": {
    "evidence_count": 12,
    "company_specific_source_count": 5,
    "search_queries": [],
    "search_failures": []
  }
}
```

## 5. 执行流程

### Step 1: 查询词生成（LLM 单次调用）
- 根据 intent 和 query_profile 生成 4-6 个搜索查询词
- 覆盖策略：至少 1 个 company+role 精准查询，至少 1 个通用岗位查询
- LLM 失败时 → 确定性回退（用 company + role + intent 关键词拼装）

### Step 2: 缓存检查
- cache_key = hash(query + intent + query_profile)
- 命中且未过期 → 返回缓存的 evidence_items

### Step 3: 并发检索
- Tavily 工具集并发调用：company_profile, jd, interview, tech_stack, salary_culture
- RAG 检索并发调用（如 ENABLE_RAG=1）
- 单个工具失败不阻断整体流程

### Step 4: 去重 + 合并
- 合并 Tavily 结果和 RAG 结果
- URL 去重：RAG 命中 URL 若已存在于 Tavily 结果中则跳过
- 每个 source 标注 source_class、freshness_score、quality_score

### Step 5: 评分排序
- 质量评分：quality_score 基于 freshness_score + source_type + company_specificity
- RAG 结果额外考虑时效衰减权重（见 RAG spec）
- 截断至 context_limit（默认 12）

### Step 6: 诊断输出
- 计算 coverage_by_class、missing_classes、company_specific_ratio
- 记录所有 search_failures

## 6. 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `TAVILY_API_KEY` | (空) | Tavily API key |
| `TAVILY_MAX_RESULTS` | `5` | 每个搜索词的最大结果数 |
| `SEARCH_CACHE_TTL` | `600` | 缓存存活秒数 |
| `ENABLE_RAG` | `0` | 是否启用 RAG |
| `RAG_TOP_K` | `4` | RAG 检索 top-k |

## 7. 非职责
- 不做岗位分析（JobAnalyzer 负责）
- 不做候选人匹配（MatchingEngine 负责）
- 不生成最终报告（ReportAgent 负责）
- 不做自主决策（只是执行搜索编排）

## 8. 实现文件
- `api/tools/search_orchestrator.py` — SearchOrchestrator 主逻辑（从 search_agent.py 迁移）
- `api/agents/search_agent.py` — 废弃/迁移
- `api/core/rag_store.py` — RAG 存储和检索（已有）
- `api/core/cache.py` — 搜索缓存（已有）

## 9. 与阶段一的差异
| 维度 | 阶段一 SearchAgent | 阶段二 SearchOrchestrator |
|------|-------------------|--------------------------|
| 类型 | Agent | Tool |
| LLM | 1次（查询词） | 1次（查询词） |
| RAG | 集成在 Agent 内部 | 统一编排层调用 |
| 缓存 | 基于 query+intent+profile | 不变 |
| 写入 | working_set.retrieval | 不变 |
