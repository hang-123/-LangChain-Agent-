---
name: Setup CI/CD Pipeline
description: 为项目建立 pre-commit hooks 和 GitHub Actions 质量门禁
tags: ci-cd, devops, automation
---

# Setup CI/CD Pipeline / 配置 CI/CD 流水线

请为项目建立一套务实的 DevOps 质量门禁：

1. **分析项目**：识别语言、框架、构建系统和现有工具链
2. **配置 pre-commit hooks**：
   - 格式化：Prettier / Black / gofmt / rustfmt 等
   - lint：ESLint / Ruff / golangci-lint / Clippy 等
   - 安全：Bandit / gosec / cargo-audit / npm audit 等
   - 类型检查：TypeScript / mypy / flow
   - 测试：执行核心 test suite
3. **建立 GitHub Actions**：
   - push / PR 时镜像执行本地检查
   - 必要时做多版本或多平台矩阵
   - 包含 build 与 test 验证
   - 如果需要，加入部署步骤
4. **验证整条流水线**：
   - 本地先跑通
   - 创建测试 PR
   - 确认所有检查绿灯

要求：

- 优先使用开源免费工具
- 尊重项目已有配置
- 保持执行速度，不要一开始就堆太重的检查
