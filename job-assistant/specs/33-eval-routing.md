# Eval: Routing 规范

## 1. 目标
评估 Supervisor / Workflow 对用户请求的路由是否正确。

## 2. 样本类型
- 仅简历解析
- 仅 JD 解析
- 岗位匹配
- 简历定制
- 面试准备
- 投递记录更新
- 组合意图，例如“分析匹配后再帮我改简历”

## 3. 评测维度
- `intent_accuracy`: 是否识别正确主意图
- `workflow_accuracy`: 是否选择正确工作流
- `missing_input_detection`: 是否正确识别缺失输入
- `step_completeness`: 是否调用了必要子 Agent

## 4. 通过门槛
- `intent_accuracy >= 0.90`
- `workflow_accuracy >= 0.85`
- `missing_input_detection >= 0.90`

## 5. 失败分级
- P0: 把用户带入完全错误工作流
- P1: 漏掉关键前置步骤，例如没解析 JD 就直接改简历
- P2: 路由正确但缺少关键提醒
- P3: 结果正确但流程冗余

## 6. 特别关注
- 多意图混合输入
- 输入缺失但用户没意识到
- 用户表达模糊，例如“帮我看看这个岗位”
