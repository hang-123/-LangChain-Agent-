# Matching Agent 规范

## 1. 目标
基于 `CandidateProfile`、`ResumeEvidence`、`JobSnapshot` 生成可解释的岗位匹配分析。

## 2. 职责
- 计算整体匹配度与分维度得分。
- 识别优势、差距、风险。
- 给出是否建议投递的结论和原因。

## 3. 输入
```json
{
  "candidate_profile": {},
  "resume_evidence": [],
  "job_snapshot": {}
}
```

## 4. 输出
```json
{
  "match_assessment": {},
  "explanations": {
    "strengths": [],
    "gaps": [],
    "risks": []
  },
  "next_actions": [
    "若投递，优先补足 Redis 使用场景表达"
  ]
}
```

## 5. 评分原则
- 优先评价 `must_have` 覆盖情况。
- 技能存在不等于能证明深度，证据弱时只能部分给分。
- 教育、地点、工作方式等约束应单独计分，不掩盖核心能力差距。
- 如果核心硬要求缺失，`overall_score` 不得因软性加分被拉得过高。

## 6. 解释原则
- 每个优势和差距至少引用一个 `ResumeEvidence`、`JobRequirement` 或 `ExternalEvidencePack` 中的岗位证据。
- 建议投递结论必须说明是“强匹配”“可投但有风险”还是“不建议”。
- 对不确定项使用“证据不足以判断”而不是默认不符合。

## 7. 失败处理
- 缺少简历证据时，只输出保守分析。
- 缺少 `JobSnapshot` 或岗位要求结构化结果时，不允许生成正式匹配分。

## 8. 禁止事项
- 不得凭通用常识推断候选人会某项技术。
- 不得用单一关键词命中替代能力判断。
