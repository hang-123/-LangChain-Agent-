import type { AgentName } from "../types";

export const AGENT_FLOW: AgentName[] = [
  "IntentRouterNode",
  "SearchAgent",
  "QueryAgent",
  "InsightAgent",
  "QualityGate",
  "ReportAgent",
  "ReviewAgent",
];

export const AGENT_LABELS: Record<AgentName, string> = {
  User: "候选人输入",
  IntentRouterNode: "IntentRouter · 意图识别",
  SearchAgent: "SearchAgent · 并发检索",
  QueryAgent: "QueryAgent · 岗位要求提炼",
  InsightAgent: "InsightAgent · 风险诊断",
  QualityGate: "QualityGate · 质量闸门",
  ReportAgent: "ReportAgent · 报告生成",
  ReviewAgent: "ReviewAgent · 质量审查",
  System: "系统",
};

export const AGENT_DESCRIPTIONS: Record<AgentName, string> = {
  User: "发起一次新的深度求职研究",
  IntentRouterNode: "用低延迟意图路由决定检索侧重点",
  SearchAgent: "按 intent 并发抓取真实招聘要求、薪资线索与面经证据",
  QueryAgent: "提炼核心考察点、技术栈和面试官画像",
  InsightAgent: "生成风险点、追问和备考动作",
  QualityGate: "在成稿前执行保守降级与质量模式判定",
  ReportAgent: "流式输出 Markdown 研究报告",
  ReviewAgent: "打回重写并在 3 次后熔断",
  System: "承载错误和系统提示",
};
