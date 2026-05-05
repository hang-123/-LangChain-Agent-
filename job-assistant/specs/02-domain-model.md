# 领域模型

## 1. 设计目标
- 为所有 Agent、Tool、Eval 提供统一数据语言。
- 保证系统始终区分事实、推断、建议。
- 让任何结论都能追溯到简历、JD 或用户显式输入。

## 2. 核心实体

### 2.1 CandidateProfile
候选人的长期稳定画像，由简历解析结果和用户补充信息组成。

```json
{
  "candidate_id": "cand_001",
  "name": "张三",
  "email": "zhangsan@example.com",
  "phone": "13800000000",
  "target_roles": ["后端开发工程师", "服务端开发工程师"],
  "years_of_experience": 1.5,
  "location_preferences": ["上海", "杭州"],
  "salary_expectation": {
    "min": 20,
    "max": 30,
    "currency": "CNY",
    "period": "monthly"
  },
  "education": [
    {
      "school": "某大学",
      "degree": "本科",
      "major": "计算机科学与技术",
      "start_date": "2021-09",
      "end_date": "2025-06"
    }
  ],
  "work_experience": [
    {
      "company": "某科技公司",
      "role": "后端实习生",
      "start_date": "2024-07",
      "end_date": "2024-12",
      "responsibilities": ["负责订单服务接口开发"],
      "achievements": ["接口平均响应时间降低 20%"],
      "skills_used": ["Java", "Spring Boot", "MySQL", "Redis"]
    }
  ],
  "projects": [
    {
      "project_id": "proj_001",
      "name": "电商订单系统",
      "summary": "负责订单查询与库存联动模块",
      "role": "后端开发",
      "skills_used": ["Java", "Redis", "MySQL"],
      "outcomes": ["支持高峰期 2k QPS"]
    }
  ],
  "skills": ["Java", "Spring Boot", "MySQL", "Redis"],
  "languages": ["中文", "英文"],
  "certificates": [],
  "constraints": {
    "work_type": ["onsite", "hybrid"],
    "cities": ["上海", "杭州"],
    "industry_blacklist": [],
    "must_have": ["后端开发"],
    "cannot_accept": ["长期出差"]
  },
  "profile_completeness": 0.82
}
```

### 2.2 ResumeAsset
候选人上传或维护的一份原始简历资产。

```json
{
  "resume_id": "resume_raw_001",
  "candidate_id": "cand_001",
  "source_type": "pdf",
  "source_name": "张三-简历.pdf",
  "raw_text": "string",
  "language": "zh-CN",
  "parsed_at": "2026-04-15T11:00:00Z",
  "parser_version": "resume-parser-v1"
}
```

### 2.3 ResumeEvidence
从简历中抽取出的原始证据片段，供匹配、改写、面试分析引用。

```json
{
  "evidence_id": "evi_resume_001",
  "resume_id": "resume_raw_001",
  "evidence_type": "project",
  "section": "projects",
  "text": "负责订单查询接口优化，接口平均响应时间降低 20%",
  "normalized_skills": ["Java", "Redis"],
  "span": {
    "start": 120,
    "end": 156
  },
  "confidence": 0.93
}
```

### 2.4 JobPosting
目标岗位的标准化对象，可由 JD 文本、招聘页面复制内容或手动录入生成。

```json
{
  "job_id": "job_001",
  "company_name": "某互联网公司",
  "job_title": "后端开发工程师",
  "job_level": "campus",
  "city": "上海",
  "employment_type": "full_time",
  "source_type": "manual_paste",
  "source_url": "",
  "raw_jd_text": "string",
  "business_domain": "电商",
  "team_hint": "交易中台",
  "salary_range": {
    "min": 25,
    "max": 35,
    "currency": "CNY",
    "period": "monthly"
  },
  "normalized_requirements": ["Java 基础扎实", "熟悉 MySQL 和 Redis"],
  "parsed_at": "2026-04-15T11:05:00Z",
  "parser_version": "jd-parser-v1"
}
```

### 2.5 JobRequirement
从 JD 中抽取出的结构化要求，是匹配分析的最小比较单元。

```json
{
  "requirement_id": "req_001",
  "job_id": "job_001",
  "category": "skill",
  "name": "Redis",
  "requirement_level": "must_have",
  "importance_weight": 0.9,
  "description": "熟悉缓存设计与常见使用场景",
  "evidence_text": "熟悉 MySQL、Redis 等常用中间件",
  "confidence": 0.88
}
```

### 2.6 MatchAssessment
候选人与岗位的一次结构化匹配分析结果。

```json
{
  "assessment_id": "match_001",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "overall_score": 76,
  "recommendation": "recommended_with_risks",
  "strengths": [
    {
      "title": "具备 Java + Redis 项目经验",
      "evidence_refs": ["evi_resume_001", "req_001"]
    }
  ],
  "gaps": [
    {
      "title": "缺少分布式系统设计深度证据",
      "severity": "medium",
      "evidence_refs": ["req_003"]
    }
  ],
  "risks": [
    {
      "title": "项目指标数量偏少，面试中不易支撑追问",
      "severity": "medium"
    }
  ],
  "dimension_scores": {
    "skills": 80,
    "experience": 70,
    "domain_fit": 72,
    "education": 85,
    "location_fit": 90
  },
  "reasoning_notes": [
    "匹配结论仅基于简历显式信息，不推测未写明经历"
  ],
  "created_at": "2026-04-15T11:10:00Z"
}
```

### 2.7 ResumeTailoringPlan
针对单个岗位生成的简历优化计划，不直接等同于最终简历文案。

```json
{
  "tailor_plan_id": "rtp_001",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "target_role": "后端开发工程师",
  "headline_suggestion": "具备 Java / Redis / MySQL 项目经验的后端候选人",
  "keyword_coverage": {
    "covered": ["Java", "MySQL", "Redis"],
    "missing": ["分布式系统设计", "高并发"],
    "overused": []
  },
  "section_actions": [
    {
      "section": "projects",
      "action": "rewrite",
      "instruction": "把订单系统项目改写为更贴近交易中台场景的表达",
      "allowed_evidence_refs": ["evi_resume_001"]
    }
  ],
  "risk_notes": [
    "不得补写未在原始简历出现的量化指标"
  ]
}
```

### 2.8 ResumeVersion
一份面向特定岗位的简历输出版本。

```json
{
  "resume_version_id": "resume_v_001",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "source_resume_id": "resume_raw_001",
  "version_label": "backend-trading-v1",
  "summary_text": "string",
  "project_bullets": ["string"],
  "keyword_insertions": ["Redis", "MySQL"],
  "omissions": ["与目标岗位弱相关的前端经历"],
  "fact_check_status": "passed",
  "created_at": "2026-04-15T11:20:00Z"
}
```

### 2.9 InterviewPrepPack
围绕某个岗位生成的一组面试准备材料。

```json
{
  "prep_pack_id": "prep_001",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "focus_areas": ["项目深挖", "Redis 使用场景", "MySQL 索引"],
  "questions": [
    {
      "question_id": "q_001",
      "type": "project_deep_dive",
      "question": "订单系统里 Redis 缓存为什么这样设计？",
      "why_asked": "验证缓存设计理解是否真实",
      "answer_outline": ["背景", "方案", "取舍", "指标"],
      "evidence_refs": ["evi_resume_001", "req_001"]
    }
  ],
  "red_flags": [
    "如果只能说用了 Redis，而说不清 key 设计和失效策略，可信度会下降"
  ],
  "mock_plan": [
    "先讲一个最强项目",
    "再准备 3 个技术追问"
  ]
}
```

### 2.10 ApplicationRecord
单条投递记录，面向投递流程管理。

```json
{
  "application_id": "app_001",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "channel": "boss",
  "status": "applied",
  "applied_at": "2026-04-15T11:30:00Z",
  "last_updated_at": "2026-04-15T11:30:00Z",
  "contact_person": "",
  "notes": ["已投递，等待初筛"],
  "next_action": "3 天后若无反馈则跟进一次",
  "artifacts": {
    "resume_version_id": "resume_v_001",
    "prep_pack_id": "prep_001"
  }
}
```

### 2.11 ExternalEvidencePack
岗位侧外部证据集合，用于承接真实 JD、公司画像、团队线索与面经证据。

```json
{
  "evidence_pack_id": "jep_001",
  "job_id": "job_001",
  "sources": [
    {
      "source_id": "src_001",
      "source_type": "job_board",
      "title": "后端开发实习生",
      "url": "https://example.com/job/1",
      "snippet": "熟悉 MySQL、Redis、消息队列",
      "freshness_score": 92,
      "confidence": 0.88,
      "evidence_class": "real_jd"
    }
  ],
  "company_signals": ["交易中台", "高并发服务"],
  "interview_signals": ["项目深挖", "缓存设计"],
  "risk_flags": ["团队方向存在多来源混合，需要保守判断"]
}
```

### 2.12 JobSnapshot
面向下游匹配和生成任务的岗位快照，由手动 JD 解析结果和外部证据包共同组成。

```json
{
  "job_snapshot_id": "js_001",
  "job_id": "job_001",
  "job_posting": {},
  "job_requirements": [],
  "external_evidence_pack_id": "jep_001",
  "evidence_quality": {
    "freshness": 88,
    "coverage": 0.81,
    "ambiguity_notes": ["团队归属仍有轻微歧义"]
  }
}
```

### 2.13 VerificationReport
交付前验证结果，记录是否放行、降级或打回。

```json
{
  "verification_id": "ver_001",
  "artifact_type": "resume_version",
  "artifact_id": "resume_v_001",
  "status": "passed",
  "issues": [],
  "checked_rules": [
    "candidate_fact_boundary",
    "evidence_coverage",
    "recommendation_clarity"
  ],
  "created_at": "2026-04-19T10:00:00Z"
}
```

## 3. 枚举定义

### 3.1 requirement_level
- `must_have`
- `nice_to_have`
- `bonus`

### 3.2 evidence_type
- `education`
- `work_experience`
- `project`
- `skill`
- `certificate`
- `user_input`

### 3.3 recommendation
- `strong_recommend`
- `recommended_with_risks`
- `neutral`
- `not_recommended`

### 3.4 application_status
- `draft`
- `planned`
- `applied`
- `screening`
- `written_test`
- `interviewing`
- `offer`
- `rejected`
- `withdrawn`

## 4. 实体关系
- 一个 `CandidateProfile` 可以关联多份 `ResumeAsset`。
- 一份 `ResumeAsset` 可以抽取多条 `ResumeEvidence`。
- 一个 `JobPosting` 可以拆解为多条 `JobRequirement`，并可关联一个 `ExternalEvidencePack`。
- 一个 `JobSnapshot` 聚合一个 `JobPosting`、多条 `JobRequirement` 与一个 `ExternalEvidencePack`。
- 一次 `MatchAssessment` 绑定一个候选人和一个 `JobSnapshot`。
- 一个 `ResumeTailoringPlan` 绑定一个候选人和一个岗位。
- 一个 `ResumeVersion` 来源于一份原始简历，并面向一个岗位。
- 一个 `InterviewPrepPack` 绑定一个候选人和一个岗位。
- 一个 `ApplicationRecord` 必须绑定一个候选人和一个岗位，可选绑定一份 `ResumeVersion` 和一份 `InterviewPrepPack`。
- 一个 `VerificationReport` 绑定一个待交付 artifact，并记录放行或打回结果。

## 5. 领域不变量
- 系统不得生成无法指向 `ResumeEvidence` 或用户显式输入的候选人事实。
- 系统不得把 `ExternalEvidencePack` 中的岗位线索写回候选人事实。
- `MatchAssessment.overall_score` 范围必须是 `0-100`。
- `JobSnapshot` 必须保留岗位侧证据质量或歧义说明。
- `ResumeVersion.fact_check_status` 未通过时，不允许进入投递建议流程。
- `VerificationReport.status` 为 `rejected` 时，对应 artifact 不得直接交付用户。
- `ApplicationRecord.status` 只能沿合法状态流转，不能从 `draft` 直接跳到 `offer` 而没有中间记录说明。
- `JobRequirement.requirement_level` 为 `must_have` 时，匹配分析必须单独展示其满足情况。

## 6. 通用输出原则
- 事实字段：来自简历、JD、用户输入。
- 推断字段：来自 Agent 分析，必须附说明。
- 建议字段：必须以动作化表达输出，不冒充事实。
- 任何“分数”都必须附带至少一句简短解释。
