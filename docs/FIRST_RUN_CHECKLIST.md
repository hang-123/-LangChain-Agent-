# First Run Checklist

这份文档只针对当前仓库的 `最小可跑通闭环`。

当前真实架构：
- `api/main.py`：FastAPI 入口
- `ForumEngine/forum.py`：主编排器
- `ForumEngine/minimal_agents.py`：3 个轻量 Agent，其中 `QueryAgent`、`InsightAgent` 和 `ReportAgent` 都会优先调用真实 LLM
- `web/`：前端页面

目标不是一次性把所有原始模块跑起来，而是先打通：

`前端输入 -> 后端 API -> ForumEngine -> QueryAgent -> InsightAgent -> ReportAgent -> 前端展示`

## 1. 先确认环境

### 必须有

- Node.js 与 npm
- Python 3.11 或 3.12

### 当前这台机器的现状

当前工作区所在机器只找到了 Windows Store 的 `python.exe` 占位入口，没有实际可执行的 Python 解释器。

这意味着：
- 前端可以构建
- 后端代码已经准备好
- 但在这台终端里不能直接启动 `uvicorn`

## 2. 安装 Python 后的最小启动步骤

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-minimal.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 9000 --reload
```

如果 PowerShell 阻止激活脚本，可先执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 3. 启动前端

新开一个终端，在 `web` 目录执行：

```powershell
npm install
npm run dev
```

默认前端请求：

```text
http://localhost:9000
```

## 4. 后端启动成功后的验证顺序

### 步骤 1：健康检查

```powershell
curl http://localhost:9000/api/health
```

预期返回：

```json
{"status":"ok","service":"career-research-assistant"}
```

### 步骤 2：验证普通接口

```powershell
curl -X POST http://localhost:9000/api/forum/run ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"帮我分析字节跳动后端实习的准备方向\",\"template_id\":\"default\"}"
```

预期观察点：
- 返回 `session_id`
- `messages` 至少包含 `QueryAgent`、`InsightAgent`、`ReportAgent`
- `report_markdown` 不为空

### 步骤 3：验证流式接口

浏览器或前端页面发起后，观察是否按顺序收到：
- `meta`
- `status`
- `message`
- `status`
- `message`
- `status`
- `message`
- `done`

注意：
- 后端日志里看到 `GET /api/forum/stream ... 200 OK` 只代表 SSE 连接建立成功
- 不代表业务一定成功
- 如果后端中途报错，前端仍然可能收到 HTTP 200，但流里会返回 `type=error`

## 5. 页面上应该看到什么

输入一个岗位问题后，前端应该出现三类变化：

1. 聊天区出现你的输入
2. 右侧 Agent 状态依次从 `idle -> running -> done`
3. 报告区出现结构化求职报告

## 6. 当前版本的关键注意点

### 这是最小闭环，不是完整版

当前主链路不再依赖原来的重型 `MediaEngine` 和复杂检索模块。

这样做的目的：
- 降低运行复杂度
- 保留 Agent 编排骨架
- 保留前后端联动
- 保留 SSE 状态流
- 保留 best-effort 会话记忆

### 当前已经接入轻量 LLM

不是所有输出都走模板了。

当前行为是：
- `QueryAgent` 优先调用 LLM 做意图解析，提取公司、岗位、目标和准备重点
- `InsightAgent` 优先调用 LLM 生成候选人风险点、准备策略和面试官关注点
- `ReportAgent` 优先调用 LLM 生成最终报告
- 如果 LLM 接口失败，系统会自动降级到本地模板模式

所以你现在能讲成：
- 这是一个轻量多 Agent 编排系统
- 不是纯模板壳子
- 但也不是重型工具调用系统

### 会话记忆是 best-effort

当前版本已经升级成 `本地持久化 memory`，不再依赖数据库。

你需要理解的是：
- `session_id` 仍然会生成
- 会话消息会落到本地 `memory_store/{session_id}/` 目录
- 每个会话会分成三层：
  - `session_summary.json`
  - `turn_capsules.jsonl`
  - `raw_messages.jsonl`
- 新问题进入时，系统不会拼接全部历史，而是优先读取 summary 和相关 turn capsule，再按需参考原始消息
- 即使持久化失败，系统主流程仍然可以继续

### SSE 是这次最值得讲的工程点

不要把它讲成“前端轮询”。

准确说法是：
- 前端调用 `GET /api/forum/stream`
- 后端按步骤发 `meta/status/message/done/error`
- 前端按事件更新 Agent 面板和消息区

### 闲聊和任务查询会分流

像 `你好`、`在吗`、`谢谢` 这种输入，不会再进入求职报告链路。

当前逻辑：
- 闲聊输入：直接由 `System` 返回一句短回复
- 求职相关输入：进入 `QueryAgent -> InsightAgent -> ReportAgent`

### 现在能看到结构化中间结果

当前前端不仅显示最终 markdown，还会在聊天区展示：
- `QueryAgent` 提取出的公司、岗位、目标、关注重点
- `InsightAgent` 提取出的风险点、准备策略、面试官关注点

这部分是你讲“多 Agent 先拆解任务、再生成结果”的核心证据。

### 现在支持多档输出长度

为了控制 token 成本，当前系统不是固定输出长文，而是支持 3 个等级：

- `executive`
  - 简洁输出
  - 适合快速预览，token 成本最低
- `default`
  - 标准输出
  - 适合日常演示和项目展示
- `analysis`
  - 详细输出
  - 信息量更大，token 成本最高

这不是只在最终报告里裁字，而是会影响：
- `QueryAgent` 结构化提取的条目数
- `InsightAgent` 洞察条目数
- `ReportAgent` 最终报告篇幅

所以你可以把它讲成：
- “我在 Agent 编排层加入了篇幅等级控制，用来平衡信息完整度和 token 成本”

### Memory 与 RAG 的当前取舍

当前版本优先做的是：
- 持久化 session memory
- 轻量历史召回

当前没有上的内容：
- 向量库
- embedding 检索
- 完整 RAG 文档切片链路

这样设计的原因是：
- 当前项目主题是求职助手，多轮上下文价值高于复杂知识库
- 先把 memory 做实，比仓促接入重型 RAG 更适合最小可讲项目
- 后续如果接入简历、项目经历、面经题库，再把 RAG 作为二期扩展更合理

## 7. 你第一次演示时的推荐提问

- 帮我分析字节跳动后端开发暑期实习的准备方向
- 我准备投递小红书数据平台后端实习，请给我一份面试前行动清单
- 帮我针对阿里云平台工程实习生成一份求职研究报告

## 8. 最容易卡住的地方

- 没有真实 Python 解释器，只装了 Windows Store 占位入口
- 虚拟环境没激活，导致 `uvicorn` 找不到
- 前端起了但后端没起，页面会直接报网络错误
- SSE 的 `200 OK` 容易让人误以为业务成功，实际要看流里是否出现 `error` 事件
- `.env` 里虽然有旧配置，但当前最小闭环不依赖完整外部能力
- 不要再按旧版“四协作 Agent”去理解当前系统，当前真实主链路只有 3 个轻量 Agent
- 如果后端再次异常，先看终端打印，再看 `logs/forum_error.log`

## 9. 跑通后的学习顺序

跑通后按这个顺序理解代码：

1. `api/main.py`
2. `ForumEngine/forum.py`
3. `ForumEngine/minimal_agents.py`
4. `web/src/hooks/useForumChat.ts`
5. `web/src/lib/api.ts`

这样你会先理解信息流，再看 UI，而不是先陷入旧版复杂 Agent 细节。
