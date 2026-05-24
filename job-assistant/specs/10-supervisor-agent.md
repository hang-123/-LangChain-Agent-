# Supervisor Agent 规范

## 1. 目标
Supervisor 是系统的唯一入口 Agent，一步完成：意图识别 → 缺参检测 → 工作流选择 → 返回路由指令。

## 2. 职责
- 识别用户意图（general / tech_coding / salary_culture / match / resume_tailor / interview_prep / offer_compare / profile_bootstrap）
- 检测缺失的必要输入
- 选择合适工作流
- 对模糊意图做保守路由

## 3. 输入
```json
{
  "query": "帮我分析字节后端实习是否匹配",
  "user_id": "user_001",
  "memory_summary": "",
  "candidate_profile": {},
  "resume_evidence": [],
  "job_posting": {},
  "raw_jd_text": "",
  "offer_list": []
}
```

## 4. 输出
```json
{
  "intent": "match",
  "workflow_id": "wf_match_v2",
  "query_profile": {
    "company": "字节跳动",
    "role": "后端开发实习",
    "team_hint": "",
    "domain_hint": ""
  },
  "missing_artifacts": [],
  "warnings": [],
  "reasoning": "用户询问匹配度，检测到候选人画像和岗位信息充足，进入匹配分析工作流。"
}
```

## 5. 决策规则（确定性 + LLM 回退）

### 5.1 确定性规则（先执行）
```
if 检测到简历文件上传 → intent = "profile_bootstrap", workflow = wf_profile_bootstrap
if query 包含 "对比" | "选 offer" | "两个 offer" → intent = "offer_compare", workflow = wf_offer_compare
if query 包含 "改简历" | "优化简历" | "定制简历" → intent = "resume_tailor", workflow = wf_resume_tailor_v2
if query 包含 "面试" | "会问什么" | "准备包" → intent = "interview_prep", workflow = wf_interview_prep_v2
if query 包含 "匹配" | "适合吗" | "怎么样" | "分析" → intent = "match", workflow = wf_match_v2
```

### 5.2 LLM 路由（确定性无法匹配时）
- 调用 LLM 识别意图，分类到 {general, tech_coding, salary_culture, match, resume_tailor, interview_prep, offer_compare, profile_bootstrap}
- 同时提取 `query_profile`（company, role, team_hint, domain_hint）
- general/tech_coding/salary_culture 默认路由到 wf_match_v2（使用更通用的分析模式）
- 如果 LLM 也失败 → 默认 wf_match_v2，标注"意图模糊，使用通用匹配分析"

### 5.3 缺参检测
- `wf_match_v2` 需要：至少 query 非空
  - 缺 `candidate_profile` → 标注"无候选人画像，分析偏保守"
  - 缺 `resume_evidence` → 标注"无简历证据，匹配分数可能偏低"
- `wf_resume_tailor_v2` 需要：`candidate_profile` + `resume_evidence` + `match_assessment`(可选)
  - 缺候选人材料 → 提示先走 wf_profile_bootstrap
  - 缺 match_assessment → 自动先跑 wf_match_v2
- `wf_interview_prep_v2` 需要：`candidate_profile` + `resume_evidence` + `match_assessment`(可选)
- `wf_profile_bootstrap` 需要：简历文件
- `wf_offer_compare` 需要：至少两个 offer 数据

## 6. 非职责
- 不直接做简历事实抽取
- 不直接执行岗位侧外部检索
- 不直接改写最终简历文案
- 不自己存储投递记录

## 7. 失败处理
- 输入不足时，不猜测缺失信息，直接输出 `missing_artifacts`
- LLM 失败时回退到确定性规则
- 确定性规则也失败时，默认路由到 `wf_match_v2`

## 8. 约束
- 不允许把推断包装成候选人事实
- 不允许在没有 resume_evidence 时默认候选人技能
- 不允许跳过缺参检测直接进入工作流

## 9. 观测指标
- 路由准确率（目标 >= 90%）
- 缺参识别准确率（目标 >= 90%）
- LLM 回退率（越低越好）
- 确定性规则命中率（越高越好）
