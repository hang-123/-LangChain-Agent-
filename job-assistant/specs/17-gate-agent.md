# Gate System 规范

## 1. 目标
Gate 是系统级、纯规则、0 LLM 的质量守门组件，统一承担输入质量检查和输出真实性验证的全部职责。

在任何用户可见输出交付前，统一检查所有 artifact 的输入质量和输出真实性。

## 2. 职责
- 检查检索证据充足性
- 检查公司特异性覆盖率
- 检查事实边界
- 检查证据引用完整性
- 检查虚构/越界断言
- 决定：passed | downgraded | rejected

## 3. 检查维度

### 3.1 输入质量维度

| 检查项 | 阈值来源 | 若失败 |
|--------|---------|--------|
| evidence_count >= min_evidence_count | RetrievalPolicy | 追加 warning |
| company_specific_source_count >= min_company_specific_sources | RetrievalPolicy | 追加 warning, root_cause="retrieval" |
| claim_evidence_coverage >= min_claim_evidence_coverage | QualityPolicy | 追加 warning, root_cause="attribution" |
| action_plan_source_coverage >= min_action_plan_source_coverage | QualityPolicy | 追加 warning |
| missing_classes 非空 | RetrievalPolicy | 追加 warning, root_cause="retrieval" |

### 3.2 输出真实性维度

| 检查项 | 规则 | 若失败 |
|--------|------|--------|
| 事实边界 | forbidden_phrases 匹配：断言词（精通、擅长、一定过筛）是否由 ResumeEvidence 支撑 | rejected |
| 虚构检测 | 数字成果、项目规模、角色是否来自简历原始文本 | rejected |
| 证据引用 | 每个 strengths/gaps 是否都有 evidence_refs 或 requirement_id | downgraded |
| 岗位证据越界 | ExternalEvidencePack 中的信息是否被写成了候选人事实 | rejected |
| 候选人事实改写 | CandidateProfile 是否被下游节点更改 | rejected |

### 3.3 综合决策

```
if any rejected → status = "rejected"
elif any downgraded conditions → status = "downgraded"
else → status = "passed"
```

- `passed`: 直接交付
- `downgraded`: 保守降级输出，附 warning 标注。ReportAgent 内置自审的结果如需 Gate 最终确认也走此路径
- `rejected`: 打回，不交付。调用方收到 rejected 后可选择回退到上游节点重跑
- ReportAgent 延迟到 Gate 的严重问题：ReportAgent 在自审中发现严重问题时生成 `review_feedback`（含 issue_code 和 severity），Gate 读取 review_feedback 并执行对应的规则检查。若 Gate 无法处理（如需要 LLM 重新推理），将 rejected 连同 root_cause 返回给 WorkflowAgent 触发节点级回退

## 4. 输入
```json
{
  "artifacts": {
    "job_snapshot": {},
    "match_assessment": {},
    "resume_version": {},
    "prep_pack": {},
    "offer_comparison": {}
  },
  "working_set": {
    "retrieval_diagnostics": {},
    "analysis": {
      "quality_metrics": {}
    }
  },
  "background": {
    "policy": {},
    "candidate": {
      "candidate_profile": {},
      "resume_evidence": []
    }
  }
}
```

## 5. 输出
```json
{
  "verification_report": {
    "status": "passed",
    "issues": [],
    "checked_rules": [
      "evidence_sufficiency",
      "company_specificity",
      "candidate_fact_boundary",
      "evidence_coverage",
      "forbidden_phrases"
    ]
  },
  "control": {
    "quality_mode": "normal",
    "warning_message": "",
    "root_cause": ""
  }
}
```

## 6. 配置

| 常量/配置 | 说明 |
|-----------|------|
| `forbidden_phrases` | 硬编码的禁止断言词列表（如"精通""擅长""一定过筛""保证录取"等） |
| `retrieval.min_evidence_count` | 默认 4 |
| `retrieval.min_company_specific_sources` | 默认 2 |
| `quality.min_claim_evidence_coverage` | 默认 70 |
| `quality.min_action_plan_source_coverage` | 默认 60 |

## 7. 非职责
- 不调用 LLM 做任何判断
- 不做语义层面的真实性验证（如 LLM 判断陈述是否虚构）——这委托给 AnalysisAgent 的 confidence 标注
- 不修改 artifact 内容
- 不自动修复发现的问题

## 8. 实现文件
- `api/core/gate.py` — Gate 主逻辑
- `api/review/issue_catalog.py` — Gate 问题编码定义

