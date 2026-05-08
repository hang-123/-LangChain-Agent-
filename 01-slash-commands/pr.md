---
description: 整理代码、暂存改动并准备 pull request
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(npm test:*), Bash(npm run lint:*)
---

# Pull Request Preparation Checklist / PR 准备清单

在创建 PR 之前，请按下面步骤执行：

1. 跑 lint：`prettier --write .`
2. 跑测试：`npm test`
3. 检查 diff：`git diff HEAD`
4. 暂存改动：`git add .`
5. 生成符合 conventional commits 的提交信息：
   - `fix:` bug 修复
   - `feat:` 新功能
   - `docs:` 文档变更
   - `refactor:` 代码重构
   - `test:` 测试补充
   - `chore:` 维护项
6. 输出 PR 摘要，至少包括：
   - 改了什么
   - 为什么改
   - 做了哪些测试
   - 可能影响到什么

要求：

- 先检查是否有明显不该提交的内容
- 优先让用户看到摘要和风险点
