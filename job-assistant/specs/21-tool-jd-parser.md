# Tool: JD Parser 规范

## 1. 目标
说明：该工具属于阶段二重点补齐能力。阶段一允许 `JobIntelligenceAgent` 在没有完整 JD Parser 的情况下，基于 `raw_jd_text(optional)` 和岗位侧 research artifacts 生成保守版岗位快照。

把原始岗位描述解析为 `JobPosting` 与 `JobRequirement`。

## 2. 输入契约
```json
{
  "raw_jd_text": "string",
  "source_url": "optional",
  "company_hint": "optional"
}
```

## 3. 输出契约
```json
{
  "job_posting": {},
  "job_requirements": [],
  "parse_warnings": []
}
```

## 4. 能力边界
- 负责抽取岗位基础信息、职责、要求。
- 可以标注要求强弱和权重。
- 不负责匹配候选人。
- 阶段一不要求它成为 `JobIntelligenceAgent` 的唯一上游依赖。

## 5. 质量要求
- 原始 JD 文本必须原样保留。
- 每条要求都需保存 `evidence_text`。
- 出现模糊词时可以降低 `confidence`，不能假装明确。

## 6. 错误处理
- JD 文本为空：直接失败
- 文本过短：返回低置信度并要求人工确认
- 多岗位混合：打 `mixed_role_warning`
