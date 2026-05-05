# Agent 架构优化 Vibecoding 提示包

## 目标

- 为 BettaFish research harness 建立可观测、可回归、可审计底座
- 通过缓存、query store、experiment assignment 降低调优成本
- 为安全基线提供最小可执行的 guardrails 与注入回归

## 使用顺序

1. 先读取 `vars/baseline.json`
2. 再按 `tasks/task_list.md` 执行未完成项
3. 模板与 schema 位于 `templates/` 和 `schemas/`
4. 运行日志统一写入 `logs/` 或仓库约定目录

## 当前已落地

- T0 baseline
- T2/T4 NodePerf + `/metrics`
- T3 OTel 基线
- T6 bench 脚本
- T7/T8 CI eval + eval diff
- T9 SQLite cache
- T11/T12/T13 安全基线、最小注入 runner、guardrails
- T14 experiment assignment
- T15 SQLite query store 双写 PoC

## 外部依赖项

- Redis 与共享缓存需要 `REDIS_URL`
- GitHub Actions 真正运行依赖仓库 secrets
- 生产 OTel/Prometheus/告警路由需要平台配置
