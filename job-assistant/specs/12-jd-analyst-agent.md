# Job Intelligence Agent 规范

## 1. 目标
说明：这是阶段一当前主链中的核心能力之一，但当前实现不要求“纯 JD Parser 先行”。它可以基于 `query_profile`、岗位侧 research artifacts 和可选的 `raw_jd_text` 生成岗位快照。

把原始 JD 与外部岗位证据融合为可供匹配、简历优化、面试准备共用的岗位快照。

## 2. 职责
- 解析原始 JD，或消费上游 research artifacts，生成 `JobPosting` 与 `JobRequirement`。
- 调用外部证据增强能力生成 `ExternalEvidencePack`。
- 输出 `JobSnapshot`。
- 标注证据时效、覆盖度与歧义风险。

## 3. 输入
```json
{
  "query_profile": {},
  "evidence_items": [],
  "raw_jd_text": "string",
  "source_url": "optional",
  "target_company": "optional",
  "target_role": "optional"
}
```

说明：
- 阶段一里 `raw_jd_text` 可以为空
- 若已有足够的岗位侧证据，允许先生成保守版 `JobSnapshot`

## 4. 输出
```json
{
  "external_evidence_pack": {},
  "job_snapshot": {
    "job_posting": {},
    "job_requirements": [],
    "external_evidence_pack_id": "jep_xxx"
  },
  "risks": ["JD 没写清楚团队方向，领域判断置信度有限"]
}
```

## 5. 识别规则
- 出现“熟悉/掌握/精通/有经验”时，结合上下文判断为要求项。
- 出现“优先/加分/有相关经验者优先”时，判为 `nice_to_have`。
- 出现薪资、地点、工作制时，写入 `JobPosting`，不混到技能要求。
- 若 JD 同时包含多个方向，保留多标签并提示“方向混合”。
- 外部证据只能增强岗位理解，不能覆盖掉用户明确提供的 JD 事实。
- 阶段一允许通过 `query_profile + evidence_items` 先生成近似岗位要求，再随着 `raw_jd_text` 补齐而增强。

## 6. 输出质量要求
- 每条 `JobRequirement` 必须包含 `description` 和原始 `evidence_text`。
- `ExternalEvidencePack` 中的来源必须保留时效或置信度信息。
- `JobSnapshot` 必须保留证据质量和歧义说明。

## 7. 禁止事项
- 不得把企业文化描述直接等同于岗位硬要求。
- 不得自行脑补该团队技术栈。
- 不得根据公司名猜测薪资范围。
