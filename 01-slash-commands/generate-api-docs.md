---
description: 从源码生成结构化 API 文档
---

# API Documentation Generator / API 文档生成

请按下面步骤生成 API 文档：

1. 扫描 `/src/api/` 下的相关文件
2. 提取函数签名、路由信息和 JSDoc 注释
3. 按 endpoint / module 分组整理
4. 输出为 Markdown 文档
5. 包含 request / response schema
6. 补充错误返回说明

输出要求：

- 写入 `/docs/api.md`
- 每个 endpoint 尽量提供 `curl` 示例
- 如项目使用 TypeScript，补充相关类型说明
- 文档结构清晰，适合团队直接维护
