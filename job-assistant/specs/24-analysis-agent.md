# AnalysisAgent 规范

## 1. 目标
AnalysisAgent 是系统的核心分析 Agent，负责两阶段深度分析：
1. **Job-side analysis**：岗位需要什么（要求、技术栈、面试官视角）
2. **Candidate-side analysis**：候选人差什么、怎么补（风险、准备策略、行动项）

## 2. 职责
- 深度分析 SearchOrchestrator 的检索结果
- 消费 JobAnalyzer + MatchingEngine + ResumeTailor 的工具产物
- 识别候选人风险点（薄弱技能、证据缺口、面试防追问）
- 生成面试官视角判断
- 生成一周结构化行动项
- 输出质量指标和根因提示

## 3. 输入
```json
{
  "background": {
    "request": {},
    "candidate": {}
  },
  "working_set": {
    "retrieval": {
      "evidence_items": [],
      "retrieval_diagnostics": {}
    }
  },
  "artifacts": {
    "job": {
      "job_snapshot": {},
      "archetype_detection": {}
    },
    "matching": {
      "match_assessment": {}
    },
    "resume": {
      "resume_version": {}
    }
  }
}
```

## 4. 输出
```json
{
  "working_set": {
    "analysis": {
      "query_result": {
        "company_signals": [],
        "role_signals": [],
        "core_evaluation_points": [],
        "company_specific_requirements": [],
        "common_requirements": [],
        "technical_stack_requirements": [],
        "salary_signals": [],
        "interview_expectations": [],
        "coverage_gaps": [],
        "context_quality_score": 78
      },
      "insight_result": {
        "candidate_risks": [],
        "interviewer_questions": [],
        "prep_strategy": [],
        "interview_angle": "",
        "evidence_gap_summary": []
      },
      "quality_metrics": {
        "claim_evidence_coverage": 85,
        "action_plan_source_coverage": 72
      }
    }
  },
  "insights": {}
}
```

## 6. 分析流程

### Phase 1: Job-Side Analysis（岗位侧分析）

#### Step 1: company_signals
- 从 evidence_items 中提取公司画像特征（业务方向、团队规模、文化特征）
- 区分"公司特异性"和"行业通用"信号

#### Step 2: role_signals
- 从 JobSnapshot 提取核心角色期待
- 标注面试官最可能关注的 3-5 个核心评价点

#### Step 3: 要求拆解
- company_specific_requirements：该岗位/公司特有的要求
- common_requirements：行业通用要求
- technical_stack_requirements：技术栈硬要求

#### Step 4: 薪资与面试预期
- salary_signals：从 evidence 中提取的薪资/职级线索
- interview_expectations：面试官对候选人的能力预期

#### Step 5: 质量评估
- context_quality_score：当前证据池的质量（0-100）
- coverage_gaps：缺失的证据类型
- claim 生成与证据绑定

### Phase 2: Candidate-Side Analysis（候选人侧分析）

#### Step 6: 风险识别
- candidate_risks：从 match_assessment.gaps 提炼面试中最可能被追问的弱点
- evidence_gap_summary：候选人简历中缺失的证据项

#### Step 7: 面试官视角
- interviewer_questions：面试官基于岗位要求和候选人弱点的具体追问
- interview_angle：面试官的整体定性判断（如"技术基础OK但缺乏系统设计深度"）

#### Step 8: 准备策略
- prep_strategy：针对风险点和追问的具体准备建议

#### Step 9: 一周行动项
- 7天或 5 天的结构化行动计划
- 每天：目标、具体动作、与该岗位的关联、预期产出
- 绑定 evidence_refs

## 7. 输出质量要求
- 每个 claim 必须带 evidence_refs
- claim_evidence_coverage >= 70%
- action_plan_source_coverage >= 60%
- 风险识别必须指出"可在哪里补证据"而不是只指出问题
- 面试官追问必须基于真实 JD/面经中出现的考察点

## 8. 非职责
- 不做搜索编排（SearchOrchestrator 负责）
- 不做关键词匹配（MatchingEngine 负责）
- 不做报告生成（ReportAgent 负责）
- 不做最终事实校验（Gate 负责）

## 9. 禁止事项
- 不得把岗位证据写成候选人事实
- 不得自行推断候选人掌握某项技能
- 不得生成与岗位无关的泛化建议
- 不得在没有 evidence 支持的情况下生成"面试要点"

## 10. 配置
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ANALYSIS_TEMPERATURE` | `0.3` | LLM 温度 |
| `MAX_ACTION_PLAN_DAYS` | `7` | 最大行动项天数 |

## 11. 实现文件
- `api/agents/analysis_agent.py` — AnalysisAgent 主逻辑
- `api/agents/query_agent.py` — 迁移/废弃
- `api/agents/insight_agent.py` — 迁移/废弃

