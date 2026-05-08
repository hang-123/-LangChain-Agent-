---
name: Expand Unit Tests
description: 针对未覆盖分支、边界情况和错误路径补全测试
tags: testing, coverage, unit-tests
---

# Expand Unit Tests / 扩展单元测试

请根据项目现有测试框架扩展单元测试覆盖：

1. **先分析覆盖率**：识别未覆盖分支、边界情况和低覆盖区域
2. **找出缺口**：
   - 逻辑分支
   - 错误路径
   - 边界值
   - 空值 / 空集合 / null 输入
3. **按项目现有框架补测试**：
   - Jest / Vitest / Mocha
   - pytest / unittest
   - Go testing / testify
   - Rust test framework
4. **重点覆盖**：
   - 错误处理
   - 边界值
   - corner cases
   - 状态变化和副作用
5. **再次验证**：重新跑覆盖率并确认提升

输出要求：

- 只输出新增测试代码块或明确的测试文件改动
- 遵循项目现有测试风格和命名习惯
