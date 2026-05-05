# Tool: Application Store 规范

## 1. 目标
说明：该工具属于阶段二规划，不在阶段一 MVP 承诺范围内。

提供投递记录的创建、查询、更新与检索能力。

## 2. 支持操作
- `create_application`
- `update_status`
- `append_note`
- `list_applications`
- `get_application`

## 3. 输入契约
```json
{
  "operation": "create_application",
  "payload": {
    "candidate_id": "cand_001",
    "job_id": "job_001",
    "status": "planned"
  }
}
```

## 4. 输出契约
```json
{
  "ok": true,
  "application_record": {},
  "error_code": ""
}
```

## 5. 规则
- `candidate_id + job_id` 默认视为同一投递上下文。
- 状态更新必须记录 `last_updated_at`。
- 重复创建时，应返回已有记录或显式报冲突。
- 备注追加为 append-only，不覆盖历史。

## 6. 合法状态流转
- `draft -> planned -> applied -> screening -> written_test -> interviewing -> offer`
- 任意状态可转 `rejected` 或 `withdrawn`

## 7. 禁止事项
- 不允许无痕修改历史状态。
- 不允许删除已存在的投递记录，除非明确执行归档策略。
