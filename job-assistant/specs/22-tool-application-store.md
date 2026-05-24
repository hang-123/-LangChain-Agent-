# Tool: Application Store 规范

## 1. 目标

提供投递记录的创建、查询、更新、检索与模糊查找能力。纯确定性 Tool，0 LLM，SQLite 持久化。

## 2. 支持操作

### 2.1 面向用户的操作（通过 Supervisor 路由）

| operation | 说明 | Supervisor 关键词示例 |
|-----------|------|----------------------|
| `create_application` | 创建一条投递记录 | "记录投递""我投了XX" |
| `update_status` | 更新投递状态 | "更新状态""改成面试中" |
| `append_note` | 追加备注（append-only） | "添加备注""补充一下" |
| `list_applications` | 按候选人列出投递记录 | "我的投递列表""查看申请" |
| `get_application` | 查询单条投递详情 | "查看详情" |

### 2.2 内部操作（供 Supervisor / 其他组件调用）

| 方法 | 说明 |
|------|------|
| `find_applications` | 按 candidate_id + 公司名/岗位名模糊匹配 |
| `lookup_applications` | 模块级辅助函数，一次性连接，供 Supervisor auto-fill 使用 |

## 3. Supervisor 集成

Supervisor 的确定性路由匹配到投递管理关键词后，分三步产出 `ApplicationStoreRequest`：

1. **Regex 确定 operation**：`_detect_application_operation()` 用 5 组正则匹配操作类型
2. **LLM 提取实体**：`_extract_application_entities()` 用单次 LLM 提取 company / role / new_status / note_content 等语义字段
3. **ID 自动补全**：从 state 中取 `candidate_id`；对 update_status / append_note / get_application，通过 `lookup_applications()` 反查 `application_id`（单条命中自动填充，多条命中列选项让用户选择，零命中标 missing_artifacts）

## 4. 数据库 Schema

SQLite，表名 `applications`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `application_id` | TEXT PK | 投递记录 ID，格式 `app_{uuid[:12]}` |
| `candidate_id` | TEXT NOT NULL | 候选人 ID |
| `job_id` | TEXT NOT NULL | 岗位 ID |
| `company` | TEXT | 公司名 |
| `role` | TEXT | 岗位名 |
| `status` | TEXT | 投递状态（默认 draft） |
| `notes_json` | TEXT | 备注数组（JSON），append-only |
| `created_at` | TEXT | 创建时间 ISO-8601 |
| `last_updated_at` | TEXT | 最后更新时间 ISO-8601 |

索引：
- `idx_app_candidate` on `candidate_id`
- `idx_app_candidate_job` UNIQUE on `(candidate_id, job_id)` — 防止重复投递

## 5. 合法状态流转

```
draft ──────→ planned ──→ applied ──→ screening ──→ written_test ──→ interviewing ──→ offer
  │               │           │            │              │                │            │
  └───────────────┴───────────┴────────────┴──────────────┴────────────────┴────────────┘
                                     rejected  /  withdrawn（任意状态可达）
```

具体规则（`LEGAL_TRANSITIONS`）：

| 当前状态 | 允许流转到 |
|---------|-----------|
| draft | planned, rejected, withdrawn |
| planned | applied, rejected, withdrawn |
| applied | screening, rejected, withdrawn |
| screening | written_test, rejected, withdrawn |
| written_test | interviewing, rejected, withdrawn |
| interviewing | offer, rejected, withdrawn |
| offer | rejected, withdrawn |
| rejected | (终态，不可再流转) |
| withdrawn | (终态，不可再流转) |

## 6. 输入契约

```json
{
  "operation": "create_application",
  "payload": {
    "candidate_id": "cand_001",
    "job_id": "job_001",
    "company": "字节跳动",
    "role": "后端开发实习",
    "status": "planned"
  }
}
```

各操作 payload 字段：

| operation | 必填 | 可选 |
|-----------|------|------|
| `create_application` | candidate_id, job_id | company, role, status |
| `update_status` | application_id, status | - |
| `append_note` | application_id, content | - |
| `list_applications` | - | candidate_id, status |
| `get_application` | application_id | - |

## 7. 输出契约

```json
{
  "application_store_response": {
    "ok": true,
    "application_record": {},
    "previous_status": "planned"
  }
}
```

- `application_record`：操作后的投递记录
- `previous_status`：仅在 `update_status` 操作时返回，供 Gate 做流转合法性二次校验
- `application_records`：仅在 `list_applications` 操作时返回（列表）
- `error_code`：失败时的错误码（`duplicate` / `not_found` / `illegal_transition` / `invalid_request` / `unknown_operation`）

## 8. 规则

- `candidate_id + job_id` 唯一约束，重复创建返回 `duplicate`
- 状态更新必须通过 `LEGAL_TRANSITIONS` 校验
- 状态更新后返回 `previous_status`，供 Gate 验证
- 备注为 append-only，不覆盖历史。每条备注带 `note_id` + `created_at`
- `find_applications` 使用 LIKE 做模糊匹配（`%company%` / `%role%`）
- `lookup_applications` 创建独立的一次性连接，用后即关

## 9. Gate 集成

`wf_application_followup_v1` 通过 Gate 时，跳过检索相关检查，执行 application 专有规则：

| 检查项 | 规则 | 失败结果 |
|--------|------|---------|
| `application_status_valid` | status 必须是 9 个合法枚举值之一 | rejected |
| `application_required_fields` | candidate_id, job_id 非空 | rejected |
| `application_transition` | 状态流转符合 LEGAL_TRANSITIONS（如有 previous_status） | rejected |

## 10. 禁止事项

- 不允许无痕修改历史状态
- 不允许删除已存在的投递记录（除非明确归档策略）
- 不允许覆盖备注历史

## 11. 实现文件

- `api/tools/application_store.py` — ApplicationStore 主逻辑 + `lookup_applications` + `run_application_store`
- `api/core/gate.py` — Gate application-specific 检查规则
- `api/agents/supervisor.py` — NL→ApplicationStoreRequest 提取 + ID auto-fill
- `api/core/graph.py` — `wf_application_followup_v1` 工作流定义与路由
- `api/core/contracts.py` — `ApplicationStoreRequest` / `ApplicationRecord` / `SupervisorResponse.application_store_request`
