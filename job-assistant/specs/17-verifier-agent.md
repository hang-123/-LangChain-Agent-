# Verifier Agent 规范

## 1. 目标
说明：阶段一当前能力以 artifact-scoped fact check 为主；统一的 Verifier Agent 属于阶段二目标态。

在任何用户可见输出交付前，检查事实边界、证据覆盖、冲突与降级条件。

## 2. 职责
- 检查候选人事实、岗位事实、推断和建议之间的边界。
- 检查主要结论是否具备 artifact 级依据。
- 检查证据冲突、时效不足或覆盖不足时是否需要降级。
- 决定放行、打回或保守降级。

阶段一最小职责：
- 对 `resume_version` 做基础 fact check
- 输出 `passed | downgraded | rejected`
- 阻止明显越界内容继续交付

## 3. 输入
```json
{
  "artifact_type": "resume_version",
  "artifact": {},
  "candidate_profile": {},
  "resume_evidence": [],
  "job_snapshot": {}
}
```

## 4. 输出
```json
{
  "verification_report": {},
  "decision": "passed",
  "required_regeneration": []
}
```

## 5. 核心规则
- 不允许把岗位证据写成候选人事实。
- 主要结论必须带 artifact 级依据。
- 证据冲突时必须输出冲突说明。
- 证据弱时允许降级，不允许伪装成高置信度输出。

## 6. 失败处理
- 如果事实边界被破坏，直接打回。
- 如果证据不足，允许转为保守表达并附带缺口说明。
- 如果多个来源冲突，以覆盖更高且更新的证据为主，并保留冲突记录。
