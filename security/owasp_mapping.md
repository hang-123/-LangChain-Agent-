# OWASP LLM Top 10 Mapping

| 风险 | 当前系统资产/入口 | 已实现控制项 | Owner | 备注 |
| --- | --- | --- | --- | --- |
| LLM01 Prompt Injection | 用户 query、外部检索内容、报告生成 | `ENABLE_GUARDRAILS` 下的 input/retrieval/output rails；`security_events.jsonl` 审计 | `{{OWNER}}` | 当前默认关闭，建议先 report-only 或灰度开启 |
| LLM02 Insecure Output Handling | `report_content` 流式输出、最终 markdown | 输出脱敏 `sanitize_output_text`，敏感模式命中时记录审计事件 | `{{OWNER}}` | 已支持 redact，但仍需产品侧确认敏感字段范围 |
| LLM03 Training Data Poisoning | 外部公开网页被当作证据 | SearchAgent retrieval rail 过滤指令型污染内容 | `{{OWNER}}` | 当前是最小规则版，不是完整内容信誉系统 |
| LLM04 Model Denial of Service | `/api/research/run`、`/api/research/stream` | `MAX_RETRIES`、质量闸门、缓存、eval/bench 基线 | `{{OWNER}}` | 仍需平台侧限流和网关层控制 |
| LLM05 Supply Chain Vulnerabilities | Tavily、LangChain、OpenTelemetry、Prometheus 依赖 | 最小依赖清单、CI smoke eval、security injection workflow | `{{OWNER}}` | 仍需 Dependabot/SCA 外部接入 |
| LLM06 Sensitive Information Disclosure | 流式 chunk、最终报告、trace/persistence | 安全审计不落原文，只存 hash/summary；输出脱敏 | `{{OWNER}}` | secrets 仍依赖 CI/运行时注入，不写 repo |
| LLM07 Insecure Plugin Design | Search tools、未来 Redis/外部工具 | execution rail allowlist，固定 Search tool 名单 | `{{OWNER}}` | 后续新工具接入必须补 allowlist |
| LLM08 Excessive Agency | Review 回退、报告润色、检索调用 | run_manifest、quality gate、tool allowlist、retry cap | `{{OWNER}}` | 多工具/写操作还未开放 |
| LLM09 Overreliance | renderer-first 报告与建议生成 | rule checker、eval harness、evidence-bound action plan | `{{OWNER}}` | 仍需业务侧抽样 review |
| LLM10 Model Theft | API key、prompt/version、策略信息 | 不打印 secrets，基线文件仅记录 presence/length | `{{OWNER}}` | 仍需平台侧出口控制与密钥轮换 |
