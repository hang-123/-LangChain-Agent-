# Eval: Interview 规范

## 1. 目标
评估面试准备内容是否相关、真实、能帮助用户练习。

## 2. 评测维度
- `question_relevance`: 问题是否贴合 JD 与候选人背景
- `question_diversity`: 是否覆盖行为题、技术题、项目深挖
- `evidence_grounding`: 是否绑定候选人真实经历
- `actionability`: 回答框架与练习建议是否可执行

## 3. 通过门槛
- `question_relevance >= 0.80`
- `evidence_grounding >= 0.85`
- 每份 `prep_pack` 至少包含 1 条项目深挖题和 1 条风险追问题

## 4. 失败分级
- P0: 生成基于虚构经历的问题或答案
- P1: 问题严重脱离目标岗位
- P2: 全是泛化问题，缺少项目深挖
- P3: 建议可读但不够可执行

## 5. 重点样本
- 候选人项目弱、JD 技术要求强
- 候选人技术强、行为表达弱
- JD 信息稀疏，需要保守生成
