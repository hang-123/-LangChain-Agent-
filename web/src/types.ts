export type AgentName = "User" | "QueryAgent" | "InsightAgent" | "ReportAgent" | "System";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  agent?: AgentName;
  content: string;
  metadata?: Record<string, unknown> | null;
  timestamp: string;
  pending?: boolean;
}

export interface AgentStatus {
  agent: AgentName;
  status: "idle" | "running" | "done" | "error";
  detail?: string;
}

export interface ForumBaseEventDTO {
  type: "meta" | "status" | "message" | "done" | "error";
}

export interface ForumMessageDTO extends ForumBaseEventDTO {
  speaker: AgentName;
  content: string;
  metadata?: Record<string, unknown> | null;
  timestamp?: string;
  type: "message";
}

export interface ForumMetaEventDTO extends ForumBaseEventDTO {
  type: "meta";
  session_id?: string;
}

export interface ForumStatusEventDTO extends ForumBaseEventDTO {
  type: "status";
  agent: AgentName;
  phase: "started" | "completed";
  detail: string;
}

export interface ForumDoneEventDTO extends ForumBaseEventDTO {
  type: "done";
  session_id?: string;
}

export interface ForumErrorEventDTO extends ForumBaseEventDTO {
  type: "error";
  detail: string;
  error_type?: string;
}

export type ForumStreamEventDTO =
  | ForumMetaEventDTO
  | ForumStatusEventDTO
  | ForumMessageDTO
  | ForumDoneEventDTO
  | ForumErrorEventDTO;

export interface ForumRunMessageDTO {
  speaker: AgentName;
  content: string;
  metadata?: Record<string, unknown> | null;
  timestamp?: string;
}

export interface ForumRunResponse {
  session_id: string;
  messages: ForumRunMessageDTO[];
  report_markdown?: string | null;
}
