# OfferEvaluator Tool 规范（阶段二）

## 1. 目标
多 offer 对比工具。纯数学加权矩阵计算，0 LLM 调用。输入多个 offer 数据，输出排名和建议。

## 2. 职责
- 对每个 offer 在 10 个维度上评分
- 应用可配置权重计算加权总分
- 生成排名和对比建议

## 3. 输入
```json
{
  "offers": [
    {
      "offer_id": "offer_a",
      "company": "字节跳动",
      "role": "后端开发工程师",
      "north_star_alignment": 85,
      "cv_match": 78,
      "seniority_level": 70,
      "compensation": 65,
      "growth_trajectory": 80,
      "remote_quality": 90,
      "company_reputation": 75,
      "tech_stack_modernity": 85,
      "speed_to_offer": 60,
      "cultural_signals": 70
    }
  ],
  "weights": {}
}
```

## 4. 输出
```json
{
  "offer_comparison": {
    "dimensions": {},
    "scores": {},
    "weighted_totals": {},
    "ranking": [],
    "recommendation": ""
  }
}
```

## 5. 计算流程（0 LLM）

### Step 1: 权重加载
- 使用用户提供的 weights（如有）
- 否则使用默认权重：north_star 0.25, cv_match 0.15, seniority 0.15, compensation 0.10, growth 0.10, remote 0.05, reputation 0.05, tech_stack 0.05, speed 0.05, culture 0.05

### Step 2: 加权计算
- 每个 offer：`weighted_total = sum(dimension_score × weight for each dimension)`
- 所有维度必须计分，不得漏计

### Step 3: 排名与建议
- 按 weighted_total 降序排列
- 如果最高分与次高分差距 < 3 分：标注"差距很小，建议结合主观偏好判断"
- recommendation 包含简明对比理由

## 6. 非职责
- 不调用 LLM 做任何推理
- 不验证维度评分的真实性（由用户或上游提供）
- 不做岗位匹配分析

## 7. 实现文件
- `api/tools/offer_evaluator.py` — OfferEvaluator 主逻辑
- `api/agents/offer_evaluator.py` — 迁移/废弃

## 8. 配置
无需额外配置。默认权重已硬编码，可通过输入中的 `weights` 覆盖。
