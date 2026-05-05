# Workflow Agent 规范

## 1. 目标
管理跨任务流程，把单点能力串成 artifact 驱动、可恢复、可审计的求职工作流。

说明：阶段一只承诺少量主工作流；完整 Workflow Agent 作为阶段二目标态存在。

## 2. 典型工作流
### 阶段一当前主工作流
- `wf_match_v2`: 结构化候选人输入 -> `JobIntelligenceAgent` -> `MatchingAgent` -> artifact-scoped fact check
- `wf_resume_tailor_v2`: 匹配分析 -> 简历改写计划 -> 简历版本生成 -> artifact-scoped fact check

### 阶段二规划工作流
- `wf_profile_bootstrap`: 简历上传 -> 画像抽取 -> 缺失项提示
- `wf_interview_prep_v2`: 匹配分析 -> 面试问题生成 -> 准备包生成 -> `VerifierAgent`
- `wf_application_followup_v1`: 写入投递记录 -> 状态更新 -> 下一步提醒

## 3. 输入
```json
{
  "workflow_id": "wf_match_v2",
  "artifacts": {
    "candidate_profile": {},
    "resume_asset": {},
    "job_snapshot": {},
    "application_record": {}
  }
}
```

## 4. 输出
```json
{
  "workflow_status": "completed",
  "completed_steps": ["JobIntelligenceAgent", "MatchingAgent", "VerifierAgent"],
  "pending_steps": [],
  "artifacts": {},
  "next_recommended_action": "继续生成简历定制建议"
}
```

## 5. 编排原则
- 先事实抽取，再分析，再生成建议。
- 任何生成型步骤都依赖前置结构化结果和 artifact 契约。
- 状态写入类操作必须幂等。
- 如果某一步关键输入缺失，流程停在可恢复状态。
- 用户可见输出在交付前必须经过 `VerifierAgent`。

阶段一补充：
- `VerifierAgent` 允许先以 artifact-scoped fact check 形式存在
- `workflow_status` 可以先由后端 artifact 与前端状态推导共同组成，阶段二再收敛为后端权威产物

## 6. 恢复策略
- 支持从最近一个成功步骤恢复。
- 支持按 artifact 粒度恢复，只重跑失败节点，不重复解析已确认资产。
- 每次流程都记录输入摘要、版本和时间戳。

## 7. 禁止事项
- 不得跳过 `fact_check` 进入投递建议。
- 不得在一个工作流里悄悄修改候选人长期画像。
