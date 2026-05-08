# InterviewCoach Tool 规范（阶段二）

## 1. 目标
基于候选人的真实经历和目标岗位要求，生成个性化面试准备材料。阶段二将 InterviewCoachAgent 降级为 Tool：单次 LLM 生成，不做自主决策。

## 2. 职责
- 生成面试问题清单（行为题 + 技术题 + 项目深挖题）
- 生成回答框架（背景-任务-方案-结果-复盘）
- 输出风险问题与补强建议
- 形成结构化 `InterviewPrepPack`

## 3. 输入
```json
{
  "candidate_profile": {},
  "resume_evidence": [],
  "job_snapshot": {},
  "match_assessment": {}
}
```

## 4. 输出
```json
{
  "prep_pack": {},
  "question_groups": {
    "behavioral": [],
    "technical": [],
    "project_deep_dive": []
  },
  "practice_advice": []
}
```

## 5. 执行流程

### Step 1: 输入准备
- 从 match_assessment 提取 strengths, gaps, risks
- 从 job_snapshot 提取 must_have requirements
- 从 resume_evidence 提取可用于深挖的项目

### Step 2: LLM 生成（单次调用）
- System prompt：出题规则 + 回答框架要求 + 禁止事项
- 输入：精简后的候选人画像摘要 + 岗位要求摘要 + 匹配差距
- 输出：结构化 InterviewPrepPack

### Step 3: 输出结构化
- 将 LLM 输出解析为 InterviewPrepPack 模型
- 每条问题绑定 evidence_refs

## 6. 出题规则
- 问题优先覆盖高权重 must_have
- 项目深挖题必须绑定候选人真实项目证据
- 对匹配分析中的高风险项，必须生成至少一个追问题
- 若 JD 技术信息很弱，可降低技术深挖比重，但要明确说明

## 7. 回答框架要求
- 以"背景-任务-方案-结果-复盘"为主骨架
- 可以给答题结构，不替用户虚构答案内容
- 对需要补证据的问题，单独提示准备材料

## 8. 非职责
- 不负责长对话式 mock interview
- 不生成完整标准答案
- 不伪装成真实公司题库
- 不做匹配分析

## 9. 禁止事项
- 不得生成标准答案式虚构经历
- 不得输出带歧视性或不合规的问题
- 不得把面试问题伪装成真实公司题库泄露

## 10. 实现文件
- `api/tools/interview_coach.py` — InterviewCoach 主逻辑
- `api/agents/interview_coach_agent.py` — 迁移/废弃

## 11. 与阶段一的差异
| 维度 | 阶段一 | 阶段二 |
|------|--------|--------|
| 类型 | Agent（阶段二规划） | Tool（单次 LLM） |
| 状态 | 未实现 | 阶段二实现 |
| 调用方式 | 独立图节点 | 仅 wf_interview_prep_v2 中调用 |
