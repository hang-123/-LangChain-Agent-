import { useCallback, useMemo, useState } from "react";
import { nanoid } from "../lib/nanoid";
import { AGENT_FLOW } from "../lib/agentMeta";
import { runForumSession, streamForumSession } from "../lib/api";
import type { AgentName, AgentStatus, ChatMessage, ForumStreamEventDTO } from "../types";

const initialStatuses: AgentStatus[] = AGENT_FLOW.map((agent) => ({
  agent,
  status: "idle",
  detail: "等待执行",
}));

export function useForumChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(initialStatuses);
  const [isLoading, setIsLoading] = useState(false);
  const [templateId, setTemplateId] = useState<string>("default");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setMessages([]);
    setAgentStatuses(initialStatuses);
    setSessionId(null);
    setReportMarkdown(null);
    setError(null);
  }, []);

  const updateStatus = useCallback(
    (agent: AgentName, status: AgentStatus["status"], detail?: string) => {
      setAgentStatuses((prev) =>
        prev.map((item) => (item.agent === agent ? { ...item, status, detail: detail ?? item.detail } : item))
      );
    },
    []
  );

  const appendMessage = useCallback((message: Omit<ChatMessage, "id" | "timestamp">) => {
    setMessages((prev) => [
      ...prev,
      {
        ...message,
        id: nanoid(),
        timestamp: new Date().toISOString(),
      },
    ]);
  }, []);

  const sendQuery = useCallback(
    async (query: string, useStreaming: boolean = true) => {
      if (!query.trim()) return;
      
      appendMessage({ role: "user", content: query });
      setIsLoading(true);
      setError(null);
      setAgentStatuses(initialStatuses);

      try {
        if (useStreaming) {
          // 使用流式API
          let currentSessionId = sessionId;
          await streamForumSession(
            query,
            templateId,
            sessionId,
            (event: ForumStreamEventDTO) => {
              if (event.type === "meta" && event.session_id) {
                currentSessionId = event.session_id;
                setSessionId(event.session_id);
                return;
              }

              if (event.type === "status") {
                updateStatus(
                  event.agent,
                  event.phase === "completed" ? "done" : "running",
                  event.detail
                );
                return;
              }

              if (event.type === "error") {
                setError(event.detail);
                appendMessage({
                  role: "agent",
                  agent: "System",
                  content: `运行失败：${event.detail}`,
                });
                setAgentStatuses((prev) =>
                  prev.map((item) =>
                    item.status === "running"
                      ? { ...item, status: "error", detail: "执行中断" }
                      : item
                  )
                );
                return;
              }

              if (event.type === "done") {
                if (event.session_id && !currentSessionId) {
                  setSessionId(event.session_id);
                }
                return;
              }

              if (event.type !== "message") {
                return;
              }

              const agent = (event.speaker ?? "System") as AgentName;
              appendMessage({
                role: agent === "User" ? "user" : "agent",
                agent: agent === "User" ? "User" : agent,
                content: event.content,
                metadata: event.metadata ?? null,
              });
              if (agent === "ReportAgent") {
                setReportMarkdown(event.content);
              }
            },
            (error) => {
              setError(error);
              appendMessage({
                role: "agent",
                agent: "System",
                content: `错误: ${error}`,
              });
            }
          );
        } else {
          // 使用普通API
          const response = await runForumSession(query, templateId, sessionId);
          setSessionId(response.session_id);

          // 模拟逐步显示消息，提供更好的用户体验
          for (const message of response.messages) {
            const agent = (message.speaker ?? "System") as AgentName;
            if (AGENT_FLOW.includes(agent)) {
              updateStatus(agent, "running", "正在生成阶段输出");
            }
            await new Promise((resolve) => setTimeout(resolve, 300));
            appendMessage({
              role: agent === "User" ? "user" : "agent",
              agent: agent === "User" ? "User" : agent,
              content: message.content,
              metadata: message.metadata ?? null,
            });
            if (AGENT_FLOW.includes(agent)) {
              updateStatus(agent, "done", "已完成");
            }
          }
          setReportMarkdown(response.report_markdown ?? null);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "未知错误";
        setError(errorMessage);
        appendMessage({
          role: "agent",
          agent: "System",
          content: `运行失败：${errorMessage}`,
        });
      } finally {
        setIsLoading(false);
      }
    },
    [appendMessage, updateStatus, templateId, sessionId]
  );

  const state = useMemo(
    () => ({
      messages,
      agentStatuses,
      isLoading,
      sendQuery,
      templateId,
      setTemplateId,
      reportMarkdown,
      sessionId,
      error,
      reset,
    }),
    [messages, agentStatuses, isLoading, sendQuery, templateId, reportMarkdown, sessionId, error, reset]
  );

  return state;
}
