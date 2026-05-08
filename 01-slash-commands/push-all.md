---
description: 暂存全部改动、提交并推送到远端（高风险操作，谨慎使用）
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git push:*), Bash(git diff:*), Bash(git log:*), Bash(git pull:*)
---

# Commit and Push Everything / 全量提交并推送

⚠️ **CAUTION**：这个命令会把当前工作区里的全部改动一起提交并推送。只有在你确认这些改动应该放在同一个 commit 里时才使用。

## 工作流程

### 1. 先分析改动

并行查看：

- `git status`
- `git diff --stat`
- `git log -1 --oneline`

### 2. 安全检查

如果发现下面这些问题，必须停止并明确警告：

- secrets：`.env*`、`*.key`、`*.pem`、`credentials.json`、`id_rsa`
- 真正的 API key / token
- 大文件（例如 >10MB）
- 构建产物：`node_modules/`、`dist/`、`build/`、`.venv/`
- 临时文件：`.DS_Store`、`*.tmp`、`*.swp`

### 3. 请求确认

在真正执行前，先给出摘要并等待用户明确输入 `yes`。

### 4. 执行

```bash
git add .
git status
```

### 5. 生成提交信息

使用 conventional commits，格式如下：

```text
[type]: Brief summary

- Key change 1
- Key change 2
- Key change 3
```

### 6. 提交并推送

```bash
git commit -m "..."
git push
```

如推送失败，可提示：

- `git pull --rebase && git push`
- `git push -u origin [branch]`

### 7. 确认成功

输出：

- commit hash
- branch
- files changed

## 什么时候使用

✅ 适合：

- 文档大改
- 一次完整功能交付
- 明确属于同一主题的多文件修改

❌ 不适合：

- 改动来源不清
- 有 secrets 风险
- 你其实想要更细粒度 commit
- 当前分支是受保护分支
