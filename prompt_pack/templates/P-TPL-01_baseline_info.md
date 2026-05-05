# P-TPL-01 Baseline Info

目标：扫描仓库、环境与依赖，生成 `baseline.json`、`ARCH_BASELINE.md` 与缺口清单。

约束：

- 禁止打印 secrets 原文
- 所有未指定项保留 `{{VAR}}`
- 日志写 `logs/baseline_scan.jsonl`
