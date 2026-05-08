---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*)
argument-hint: [message]
description: 基于当前改动生成并执行一次 git commit
---

# Commit / 提交改动

## 上下文

- 当前 git 状态：!`git status`
- 当前 diff：!`git diff HEAD`
- 当前分支：!`git branch --show-current`
- 最近提交：!`git log --oneline -10`

## 你的任务

请基于以上改动创建一次单独的 git commit。

如果用户通过参数传入了 message，直接使用：`$ARGUMENTS`

否则，请分析改动并生成一条符合 conventional commits 的提交信息：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档改动
- `refactor:` 重构
- `test:` 新增或调整测试
- `chore:` 杂项维护

提交信息要：

- 准确概括这次改动
- 尽量简洁
- 不要编造未发生的内容
