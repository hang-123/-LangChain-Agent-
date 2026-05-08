---
name: Documentation Refactor
description: 按项目类型重组文档结构，提高可读性和可维护性
tags: documentation, refactoring, organization
---

# Documentation Refactor / 文档重构

请根据项目实际类型对文档做结构化重构：

1. **先分析项目**：判断它是 library、API、web app、CLI 还是微服务，并识别主要读者是谁
2. **集中整理文档**：把技术性文档归拢到 `docs/`，并补齐交叉引用
3. **整理根目录 `README.md`**：让它只承担入口职责，包含 overview、quickstart、模块摘要、license、联系方式
4. **补齐组件级文档**：为模块、包或服务增加 README，并写清 setup / testing / usage
5. **按主题组织 `docs/`**：
   - Architecture
   - API Reference
   - Database
   - Design
   - Troubleshooting
   - Deployment
   - Contributing / 参与贡献
6. **按需生成指南**：
   - User Guide
   - API Documentation
   - Development Guide
   - Deployment Guide
7. **图示统一用 Mermaid**

要求：

- 文档要短、清晰、可扫描
- 先从项目入口和高频模块开始
- 不要为了“看起来完整”而增加无意义章节
