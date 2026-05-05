# Eval: Matching 规范

## 1. 目标
评估岗位匹配分析是否正确、稳定、可解释。

## 2. 数据集要求
- 每条样本包含：简历、JD、人工标注匹配结论。
- 人工标注至少包含：整体建议、3 个优势、3 个差距。
- 至少覆盖校招、实习、社招初级岗位。

## 3. 评测维度
- `score_alignment`: 模型分数与人工区间的一致性
- `must_have_recall`: 对关键硬要求缺口的识别率
- `evidence_precision`: 优势/差距引用证据的准确率
- `recommendation_accuracy`: 建议投递结论准确率

## 4. 通过门槛
- `recommendation_accuracy >= 0.75`
- `must_have_recall >= 0.80`
- `evidence_precision >= 0.85`

## 5. 失败分级
- P0: 把明显不匹配判断成强匹配
- P1: 漏掉关键 `must_have` 差距
- P2: 解释合理但引用证据不准
- P3: 分数波动偏大但建议结论不变

## 6. 样例关注点
- 关键词命中但实际经验很浅
- 项目经历强，但业务域不匹配
- 地点/工作方式约束冲突
