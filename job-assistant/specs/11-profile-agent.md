# Profile Pipeline 规范

## 1. 目标
说明：本规范是阶段二目标能力。阶段一允许上游直接提供 `CandidateProfile` 与 `ResumeEvidence`，不强依赖完整 Profile Pipeline 已接入主流程。

在完整版本中，把候选人的原始简历与补充输入整理成稳定、可复用的 `CandidateProfile` 和 `ResumeEvidence`。

## 2. 组成
- `ResumeParser`：抽取简历原文与各 section。
- `ProfileNormalizer`：标准化教育、经历、技能、偏好等结构化字段。
- `ProfileValidator`：校验事实边界、完整度和警告。

## 3. 非目标
- 不做自由推理式职业判断。
- 不根据岗位侧证据补写候选人事实。
- 不直接输出匹配、改简历或面试建议。

## 4. 输入
```json
{
  "resume_asset": {},
  "candidate_profile": {},
  "resume_evidence": [],
  "manual_profile_patch": {
    "target_roles": ["后端开发工程师"]
  }
}
```

说明：
- 阶段一允许跳过 `resume_asset`，直接消费外部已经整理好的 `candidate_profile + resume_evidence`
- 阶段二再把 `ResumeParser + ProfileNormalizer + ProfileValidator` 完整接入

## 5. 输出
```json
{
  "candidate_profile": {},
  "resume_evidence": [],
  "profile_gaps": ["缺少明确的求职城市偏好"],
  "profile_completeness": 0.82,
  "warnings": []
}
```

## 6. 核心规则
- 只抽取简历中明确存在的信息。
- 对技能标准化，但保留原始文本。
- 项目与实习经历都要拆成独立证据项。
- 指标、成果、职责必须分开抽取，避免混写。

## 7. 输出质量要求
- 每条 `ResumeEvidence` 必须带 `section` 与原文片段。
- 若技能只是课程名或工具名，不能自动提升为熟练掌握。
- `years_of_experience` 优先基于时间范围估算，估算失败时允许为空。

## 8. 失败与兜底
- 解析不全时，保留未解析原文片段供人工回看。
- 如果简历内容过短，明确标记 `profile_completeness < 0.5`。
- 如果当前工作流已拿到可信的结构化 `candidate_profile + resume_evidence`，可跳过重复解析。

## 9. 禁止事项
- 不得补充未写明的项目背景。
- 不得把学校课程直接认定为工作经验。
- 不得自行判断“擅长”或“精通”。
