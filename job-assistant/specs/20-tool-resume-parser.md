# ResumeParser Tool 规范

## 1. 目标
把原始简历文件（PDF/DOCX/TXT/Markdown）或文本解析为 `CandidateProfile` 基础字段和 `ResumeEvidence`。

ResumeParser 将 ProfilePipeline（11-profile-agent.md）的三个子模块——ResumeParser、ProfileNormalizer、ProfileValidator——合并为一个统一的 Tool。单次 LLM 调用完成文本抽取 + 标准化 + 验证。

## 2. 职责
- 解析简历文件 → 提取原始文本
- LLM 抽取：教育、经历、技能、项目、证书
- 标准化：技能名、学历、职业经历
- 验证：完整度检查、警告标注

## 3. 输入
```json
{
  "source_type": "pdf|docx|txt|markdown",
  "source_name": "张三-简历.pdf",
  "content_bytes": "optional (base64)",
  "raw_text": "optional (如果已有文本)"
}
```

## 4. 输出
```json
{
  "resume_asset": {
    "resume_id": "resume_raw_001",
    "candidate_id": "cand_001",
    "source_type": "pdf",
    "source_name": "张三-简历.pdf",
    "raw_text": "string",
    "language": "zh-CN",
    "parsed_at": "2026-05-08T10:00:00Z",
    "parser_version": "resume-parser-v2"
  },
  "candidate_profile": {},
  "resume_evidence": [],
  "profile_completeness": 0.82,
  "profile_gaps": ["缺少明确的求职城市偏好"],
  "warnings": []
}
```

## 5. 执行流程

### Step 1: 文本提取（确定性）
- PDF/DOCX → 提取纯文本（使用 pypdf / python-docx 或已有库）
- TXT/Markdown → 直接读取
- 文本过短（<100字符） → 返回 insufficient_text 警告

### Step 2: LLM 结构化抽取（单次 LLM 调用）
- System prompt：抽取规则 + 质量要求 + 禁止事项
- 输入：原始简历文本
- 输出：结构化 CandidateProfile + ResumeEvidence 列表

### Step 3: 后处理标准化（确定性）
- ProfileNormalizer：技能名标准化（如"java" → "Java"）
- 时间范围检查：start_date <= end_date
- 完整度计算：必填字段（name, skills, education 中的至少一项）的覆盖率

### Step 4: 验证（确定性）
- 完整度 >= 0.5 → 正常输出
- 完整度 < 0.5 → 标记 warnings
- 约束检查：技能名不能从课程名自动提升为"熟练掌握"
- 保留未解析原文片段供人工回看

## 6. 核心规则
- 只抽取简历中明确存在的信息
- 对技能标准化，但保留原始文本
- 项目与实习经历都拆成独立证据项
- 指标、成果、职责分开抽取，避免混写

## 7. 输出质量要求
- 每条 ResumeEvidence 必须带 section 与原文片段
- 若技能只是课程名或工具名，不能自动提升为熟练掌握
- years_of_experience 优先基于时间范围估算，估算失败时允许为空

## 8. 失败与兜底
- 解析不全时，保留未解析原文片段供人工回看
- 如果简历内容过短，明确标记 profile_completeness < 0.5
- 如果当前工作流已拿到可信的结构化 candidate_profile + resume_evidence，可跳过重复解析

## 9. 禁止事项
- 不得补充未写明的项目背景
- 不得把学校课程直接认定为工作经验
- 不得自行判断"擅长"或"精通"

## 10. 实现文件
- `api/tools/resume_parser.py` — ResumeParser 主逻辑（LLM抽取+标准化+验证）

