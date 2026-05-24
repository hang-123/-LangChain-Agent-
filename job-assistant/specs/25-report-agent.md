# ReportAgent 规范

## 1. 目标
ReportAgent 是系统的最终输出 Agent，内置生成与自审功能。

## 2. 职责
- 消费所有前置产物（JobSnapshot, MatchAssessment, ResumeVersion, PrepPack, OfferComparison）
- 生成结构化 Markdown 报告
- 内置自审（检查 section 完整性、证据引用、字数长度）
- 内部修复轻微问题，只在严重问题时触发外部 Gate
- 流式输出报告内容

## 3. 输入
```json
{
  "background": {
    "request": {},
    "candidate": {},
    "policy": {}
  },
  "working_set": {
    "analysis": {},
    "review": {}
  },
  "artifacts": {
    "job": {},
    "matching": {},
    "resume": {},
    "interview": {},
    "offer": {}
  },
  "control": {}
}
```

## 4. 输出
```json
{
  "artifacts": {
    "report": {
      "report_content": "# 专属求职研究报告\n\n..."
    }
  },
  "working_set": {
    "analysis": {
      "render_metadata": {}
    },
    "review": {
      "review_feedback": {}
    }
  }
}
```

## 5. 报告结构

### 标准报告（wf_match_v2）
```
## 一、岗位与公司概览
## 二、岗位能力要求拆解
## 三、候选人匹配度分析
## 四、真实面经与面试官追问
## 五、候选人风险点与准备建议
## 六、一周行动清单
## 附：证据来源
```

### 简历定制报告（wf_resume_tailor_v2）
```
## 一、岗位画像回顾
## 二、简历优化建议
## 三、关键词覆盖分析
## 四、改写前后对比
## 五、事实校验结果
## 附：证据来源
```

### 面试准备报告（wf_interview_prep_v2）
```
## 一、岗位画像回顾
## 二、高频面试题
## 三、项目深挖准备
## 四、风险问题与准备建议
## 五、模拟练习建议
```

### offer 对比报告（wf_offer_compare）
```
## 一、Offer 概览
## 二、10维加权对比
## 三、各 Offer 详细分析
## 四、建议
```

## 6. 执行流程

### Step 1: 报告生成（LLM 重度调用）
- 根据工作流类型选择报告模板
- System prompt 注入：模板结构 + 质量规则 + 禁止事项
- 输入：从 background / artifacts / analysis 中按需提取，遵循 Prompt 注入规则
- 流式输出 report_content

### Step 2: 内置自审（确定性规则 + LLM 轻度检查）
- 规则检查（确定性，0 LLM）：
  - 必需 section 是否齐全
  - 报告字数 >= min_report_word_estimate
  - evidence 来源链接数量 >= min_source_urls_in_report
  - 公司名出现次数 >= min_company_mentions
- LLM 轻度检查（仅在规则检查有 warning 时触发）：
  - 检查 section 内容是否空洞（如只有标题没有实质内容）
  - 检查是否有矛盾陈述
  - 生成修订建议
- 可修复问题：内部修复后重新输出（不超过 1 次）
- 严重问题：生成 review_feedback，标记需要 Gate 审查

### Step 3: 渲染元数据
- 记录使用的模板版本、policy_version
- 记录 evidence 引用列表
- 记录报告生成耗时

## 7. 输出质量要求
- 每个 section 包含实质内容，不能只有占位符
- 证据引用至少包含 URL 和 source 名称
- 警告/降级模式必须在报告中显著位置说明
- 流式输出支持 SSE chunk

## 8. 自审规则（内置）

| 检查项 | 阈值 | 动作 |
|--------|------|------|
| 必需 section 齐全 | 基于 ReportPolicy.required_sections | 缺 → 内部修复 |
| 报告字数 | >= min_report_word_estimate (320) | 不足 → 内部扩展 |
| 来源链接数 | >= min_source_urls_in_report (2) | 不足 → 内部追加 |
| 公司名出现次数 | >= min_company_mentions (2) | 不足 → 内部修复 |
| Section 内容虚设 | LLM 检测空洞段落 | 有 → 内部修复（最多1次） |
| 严重事实错误 | 矛盾陈述、虚构断言 | 有 → 生成 review_feedback → defer 到 Gate |
| 合法性警告 | Suspicious 岗位 | 追加醒目警告在报告开头 |

## 9. 非职责
- 不做搜索编排（SearchOrchestrator 负责）
- 不做匹配分析（MatchingEngine 负责）
- 不做最终事实校验（Gate 负责，但内置轻度自审可减少 Gate 打回次数）
- 不做修复建议的实际落实（只在报告中说明，不修改 artifact）

## 10. 禁止事项
- 不得在报告中编造 evidence
- 不得把推断描述为事实
- 不得省略"信息不足"的标注
- 不得在降级模式下仍使用自信语气

## 11. 配置
| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `REPORT_TEMPERATURE` | `0.5` | 报告生成温度 |
| `ENABLE_REPORT_SELF_REVIEW` | `1` | 是否启用内置自审 |

## 12. 实现文件
- `api/agents/report_agent.py` — ReportAgent 主逻辑（包含自审逻辑）
- `api/agents/review_agent.py` — 迁移/废弃（自审逻辑移入 report_agent.py）
- `api/core/prompts.py` — ReportAgent 的 prompt 模板

