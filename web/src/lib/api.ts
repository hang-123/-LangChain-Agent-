import type { ForumRunResponse, ForumStreamEventDTO } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:9000";

export async function runForumSession(
  query: string,
  templateId?: string,
  sessionId?: string | null
): Promise<ForumRunResponse> {
  const response = await fetch(`${API_BASE}/api/forum/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      template_id: templateId,
      session_id: sessionId ?? null,
    }),
  });

  if (!response.ok) {
    const detail = await safeParseError(response);
    throw new Error(detail ?? `HTTP ${response.status}`);
  }
  const data = await response.json();
  if (!("messages" in data) || !("session_id" in data)) {
    throw new Error("Invalid API response.");
  }
  return data;
}

export async function streamForumSession(
  query: string,
  templateId: string | undefined,
  sessionId: string | null | undefined,
  onMessage: (message: ForumStreamEventDTO) => void,
  onError: (error: string) => void
): Promise<void> {
  const params = new URLSearchParams({ query });
  if (templateId) params.set("template_id", templateId);
  if (sessionId) params.set("session_id", sessionId);

  const response = await fetch(`${API_BASE}/api/forum/stream?${params.toString()}`);

  if (!response.ok) {
    const detail = await safeParseError(response);
    onError(detail ?? `HTTP ${response.status}`);
    return;
  }

  if (!response.body) {
    onError("Response body is null");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onMessage(data);
          } catch (err) {
            console.error("Failed to parse SSE message:", err);
          }
        }
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err.message : "Stream error");
  }
}

async function safeParseError(response: Response): Promise<string | null> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    return null;
  } catch {
    return null;
  }
}
