# MatchingEngine Tool 规范（阶段二）

## 1. 目标
候选人技能 × 岗位要求的纯关键词匹配引擎。0 LLM 调用，将阶段一的 MatchingAgent 降级为确定性 Tool。

## 2. 职责
- 计算整体匹配度与分维度得分（skills / experience / domain_fit / education / location_fit）
- 识别优势（strengths）、差距（gaps）、风险（risks）
- 给出是否建议投递的结论
- 每个结论绑定证据引用

## 3. 输入
```json
{
  "candidate_profile": {},
  "resume_evidence": [],
  "job_snapshot": {},
  "archetype_detection": {}
}
```

## 4. 输出
```json
{
  "match_assessment": {
    "overall_score": 76,
    "recommendation": "recommended_with_risks",
    "strengths": [],
    "gaps": [],
    "risks": [],
    "dimension_scores": {},
    "reasoning_notes": []
  }
}
```

## 5. 匹配算法（确定性，0 LLM）

### Step 1: 构建候选人技能集
- 从 `candidate_profile.skills` 提取
- 从 `resume_evidence[*].normalized_skills` 提取
- 标准化：lowercase + whitespace normalize

### Step 2: 逐条匹配岗位要求
- 对每条 `job_requirement`：提取 name + description + evidence_text
- 与候选人技能集做 keyword 匹配 + 简历文本匹配
- 匹配成功 → 记录 evidence_refs → 归入 strengths
- 匹配失败 → 归入 gaps（severity: hard_blocker if must_have else significant）

### Step 3: 分维度评分
```
skills_score = must_have匹配率 × 80 + 其他匹配率 × 20
experience_score = 72 (years_of_experience >= 1) else 58
education_score = 85 (有学历记录) else 55
domain_fit = 78 (job_title 匹配 target_roles) else 60
location_score = 90 (city匹配) else 65 (无城市信息) else 55
```

### Step 4: 综合评分
```
overall_score = skills × 0.45 + experience × 0.2 + domain × 0.15 + education × 0.1 + location × 0.1
```

### Step 5: 降级规则
- 有 must_have 缺失 → overall_score = min(overall_score, 76)
- 无 resume_evidence → overall_score = min(overall_score, 58)
- 岗位合法性为 Suspicious → risks 中追加醒目警告

### Step 6: 建议映射
- overall_score >= 82 → strong_recommend
- overall_score >= 68 → recommended_with_risks
- overall_score >= 50 → neutral
- else → not_recommended

## 6. 非职责
- 不做岗位分析（JobAnalyzer 负责）
- 不做简历改写（ResumeTailor 负责）
- 不调用 LLM 做任何推理
- 不使用通用常识推断候选人技能

## 7. 输出质量要求
- 每个 strengths 至少绑定一个 evidence_ref
- 每个 gaps 至少绑定一个 requirement_id
- overall_score 范围 0-100
- 推荐结论附带至少一行 reasoning_note

## 8. 配置
无需额外配置。匹配逻辑为纯确定性算法，不依赖外部服务。

## 9. 实现文件
- `api/tools/matching_engine.py` — MatchingEngine 主逻辑（从 matching_agent.py 迁移）
- `api/agents/matching_agent.py` — 废弃/删除

## 10. 与阶段一的差异
| 维度 | 阶段一 MatchingAgent | 阶段二 MatchingEngine |
|------|---------------------|----------------------|
| 类型 | Agent（名不副实） | Tool |
| LLM | 0次 | 0次 |
| 输入 | job_snapshot | job_snapshot + archetype_detection |
| 合法性感知 | 无 | Suspicious 岗位追加风险警告 |
| 位置 | 固定图节点 | 按需被工作流调用 |
