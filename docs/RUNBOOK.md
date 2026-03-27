# Career Research Copilot Runbook

## 1. 项目定位

这个项目基于现有多 Agent Demo 改造成 `求职研究助手`，当前保留的是最小可跑通闭环。

当前真实主链路：
- `ForumEngine` 主编排器
- `QueryAgent` 岗位与公司扫描
- `InsightAgent` 候选人洞察
- `ReportAgent` 求职报告生成

输入：
- 岗位名称
- 公司名称
- 面试准备目标

输出：
- 岗位关键信息提炼
- 公司与业务背景概览
- 岗位能力要求拆解
- 潜在面试问题预测
- 回答准备建议
- 候选人行动清单

## 2. 本地启动

### 后端

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-minimal.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 9000 --reload
```

健康检查：

```powershell
curl http://localhost:9000/api/health
```

### 前端

在 `web` 目录执行：

```powershell
npm install
npm run dev
```

默认前端会请求：

```text
http://localhost:9000
```

如果后端地址不同，可配置：

```text
VITE_API_BASE_URL
```

## 3. 演示顺序

推荐按下面顺序演示一次完整流程：

1. 打开首页，说明这是一个最小多 Agent 求职研究助手
2. 输入一个岗位或公司问题
3. 展示右侧 Agent 状态区如何随 SSE 事件变化
4. 切换到报告页，展示结构化求职建议
5. 记录 `session_id`，再次提问，说明系统支持 best-effort 多轮记忆

## 4. 推荐演示问题

- 帮我为字节跳动后端开发暑期实习生成一份求职研究报告
- 我准备投递小红书数据平台后端实习，请整理岗位要求和面试准备方向
- 针对阿里云平台工程实习，给我一份面试前行动清单

## 5. 演示时重点强调

- 系统不是单个 Prompt，而是主编排器驱动的轻量多 Agent 闭环
- 前端状态不是猜测，而是由后端 SSE 事件驱动
- 会话记忆是 best-effort 设计，数据库不可用时主流程仍然可运行
