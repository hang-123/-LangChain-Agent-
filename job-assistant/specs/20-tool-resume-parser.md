# Tool: Resume Parser 规范

## 1. 目标
说明：该工具属于阶段二重点补齐能力。阶段一允许主工作流直接接收外部整理好的 `CandidateProfile` 和 `ResumeEvidence`。

把原始简历文件或文本解析为 `ResumeAsset`、`CandidateProfile` 基础字段和 `ResumeEvidence`。

## 2. 输入契约
```json
{
  "source_type": "pdf|docx|txt|markdown",
  "source_name": "string",
  "content_bytes": "optional",
  "raw_text": "optional"
}
```

## 3. 输出契约
```json
{
  "resume_asset": {},
  "draft_candidate_profile": {},
  "resume_evidence": [],
  "parse_warnings": []
}
```

## 4. 能力边界
- 负责文本抽取与结构初步拆分。
- 可以做技能标准化。
- 不负责匹配评分和简历改写。
- 阶段一不要求它成为所有 workflow 的唯一入口。

## 5. 错误处理
- 文件损坏：返回 `parse_error=file_unreadable`
- 文本过少：返回 `parse_warning=insufficient_text`
- 时间范围冲突：保留原文并标红冲突

## 6. 质量要求
- 解析结果应尽量保留原始段落顺序。
- 对无法确定的字段允许为空，不允许乱填。
- 输出必须包含 `parser_version`。
