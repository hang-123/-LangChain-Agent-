# ResumeTailor Tool 规范

## 1. 目标
在不虚构事实的前提下，把候选人已有经历重新组织为更贴合目标岗位的简历版本。0 LLM 调用，纯确定性逻辑。

## 2. 职责
- 基于匹配结果制定改写计划
- 输出摘要建议、项目改写建议、关键词覆盖建议
- 生成可审计的岗位定制简历版本
- 内置 fact check（确定性的规则检查，非 LLM）

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
  "tailor_plan": {},
  "resume_version": {},
  "fact_check_report": {
    "status": "passed",
    "blocked_claims": []
  }
}
```

## 5. 执行流程（纯确定性）

### Step 1: 输入验证
- candidate_profile.candidate_id 必须存在
- resume_evidence 每条必须有 evidence_id 和 section
- job_snapshot.job_id 必须存在
- match_assessment 必须存在

### Step 2: 关键词覆盖计算
- 提取 job_requirements 的 name/description/evidence_text
- 与 TAILOR_KEYWORDS 列表匹配。
  TAILOR_KEYWORDS 为硬编码的技术关键词列表，覆盖主流后端/全栈技能：
  `["Java", "Go", "Python", "C++", "Redis", "MySQL", "Kafka", "Spring", "Spring Boot", "HTTP", "RPC", "微服务", "分布式", "高并发", "系统设计"]`
- 与候选人技能集匹配
- 计算 covered / missing / overused

### Step 3: Section Action 生成
- 遍历 projects 和 work_experience 类的 resume_evidence
- 对每个 evidence 生成 rewrite action（指令：保留原始事实，调整表达重心）
- 对技能 section 生成 prioritize action

### Step 4: ResumeVersion 生成
- 生成 headline（基于关键词覆盖）
- 生成 summary_text
- 生成 project_bullets（从 evidence 中提取文本片段）
- 生成 omissions 建议

### Step 5: Fact Check（内置，确定性）
- 检查 blocked_claims：每个 missing 关键词检查是否被写成"已掌握"
- 检查 forbidden_phrases：数字成果是否来自 resume_evidence
- status = passed（无 blocked_claims）或 downgraded（有 blocked_claims但不包含虚构）
- rejected 状态保持可用但不主动触发（虚构检测主要在 Gate 层）

## 6. 改写策略
- 优先强化与高权重 must_have 相关的真实经历
- 允许重排表达顺序，不允许新增未发生的事实
- 允许把原始项目描述改得更聚焦，但必须保留原意
- 对缺失要求输出"补充建议"，而不是偷偷补写

## 7. 非职责
- 不生成最终排版的简历文件
- 不调用 LLM 生成文案
- 不做匹配分析（MatchingEngine 负责）
- 不做全文事实校验（Gate 负责统一校验）

## 8. 禁止事项
- 不得编造数字成果、用户角色、项目规模
- 不得把课程作业改写成实习经历
- 不得把"会"改成"精通"
- 不得承诺"这样改一定过筛"

## 9. 实现文件
- `api/tools/resume_tailor.py` — ResumeTailor 主逻辑
