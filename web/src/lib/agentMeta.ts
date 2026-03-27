import type { AgentName } from "../types";

export const AGENT_FLOW: AgentName[] = [
  "QueryAgent",
  "InsightAgent",
  "ReportAgent",
];

export const AGENT_LABELS: Record<AgentName, string> = {
  User: "候选人",
  QueryAgent: "岗位与公司扫描",
  InsightAgent: "候选人洞察",
  ReportAgent: "求职报告生成",
  System: "系统",
};

export const AGENT_SHORT_DESCRIPTIONS: Record<AgentName, string> = {
  User: "提交求职目标",
  QueryAgent: "提取岗位、公司和关键准备方向",
  InsightAgent: "梳理岗位要求与候选人准备重点",
  ReportAgent: "生成结构化求职研究报告",
  System: "输出系统状态和错误",
};
