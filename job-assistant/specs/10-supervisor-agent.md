# Supervisor Agent 规范

## 1. 目标
说明：本规范描述的是阶段二目标态能力，不代表阶段一已经完整落地。

阶段一中，系统更接近“单入口 + 确定性工作流编排”，Supervisor 的部分职责由入口路由和固定 workflow 承担。

阶段二中，Supervisor 作为系统总控能力，负责识别用户当前任务、选择合适的工作流、协调下游能力，并把最终结果组织成可交付响应。

## 2. 职责
- 识别用户意图并选择工作流。
- 判断哪些 artifact 缺失。
- 编排 `ProfilePipeline`、`JobIntelligenceAgent`、`MatchingAgent`、`ResumeTailorAgent`、`InterviewCoachAgent`、`VerifierAgent`。
- 汇总结构化产物并组织最终响应。
- 控制“事实、推断、建议”边界。

阶段一最小职责可退化为：
- 在 `wf_match_v2` 与 `wf_resume_tailor_v2` 之间做确定性分流
- 汇总结构化产物
- 返回缺失 artifact 提示

## 3. 非职责
- 不直接做简历事实抽取。
- 不直接执行岗位侧外部检索。
- 不直接改写最终简历文案。
- 不自己存储投递记录。

## 4. 输入
```json
{
  "user_query": "帮我分析这份简历和这个后端岗位的匹配度",
  "resume_asset": {},
  "resume_evidence": [],
  "job_snapshot": {},
  "candidate_profile": {},
  "application_record": {}
}
```

## 5. 输出
```json
{
  "intent": "match_resume_to_job",
  "workflow_id": "wf_match_v2",
  "required_capabilities": [
    "ProfilePipeline",
    "JobIntelligenceAgent",
    "MatchingAgent",
    "VerifierAgent"
  ],
  "missing_artifacts": [],
  "response_contract": {
    "facts": [],
    "inferences": [],
    "actions": []
  }
}
```

## 6. 决策规则
- 只有简历资产，没有结构化候选人信息：进入 `ProfilePipeline`，然后给出待补岗位信息提示。
- 已有 `candidate_profile + resume_evidence`，但缺岗位材料：进入 `JobIntelligenceAgent`，然后给出待补岗位信息提示。
- 只有岗位材料，没有候选人材料：优先进入 `JobIntelligenceAgent`，然后给出待补候选人材料提示。
- 同时有简历和岗位材料，且用户问“匹配度/适合吗”：进入 `MatchingAgent`，输出前必须经过 `VerifierAgent`。
- 用户要求“改简历”：先跑 `MatchingAgent`，再跑 `ResumeTailorAgent`，最后经过 `VerifierAgent`。
- 用户要求“准备面试”：先跑 `MatchingAgent`，再跑 `InterviewCoachAgent`，最后经过 `VerifierAgent`。
- 用户要求“记录投递/更新状态”：进入 `WorkflowAgent` + `ApplicationWorkflowService` + `ApplicationStore`。

阶段一约束：
- 默认只承诺 `match` 和 `resume_tailor` 两条主流程
- 若缺少 `candidate_profile` 或 `resume_evidence`，允许返回缺参提示，而不是强行进入完整解析流程

## 7. 失败处理
- 输入不足时，不猜测缺失信息，直接输出 `missing_artifacts`。
- 下游能力失败时，返回可恢复错误，不中断整个会话。
- 当多个来源结论冲突时，以证据覆盖更高且更新的一方为主，并写明冲突点。

## 8. 约束
- 不允许把推断包装成候选人事实。
- 不允许在没有 `ResumeEvidence` 的前提下生成项目成绩。
- 不允许把岗位侧外部证据写回候选人事实。
- 不允许跳过事实校验直接给投递建议。

## 9. 观测指标
- 路由准确率
- 缺参识别准确率
- 工作流成功率
- 子能力结果冲突率
