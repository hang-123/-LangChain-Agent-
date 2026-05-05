import type { ResearchRunResponse, ResearchSessionInput, ResearchStreamEvent } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:9000";


export async function runResearchSession(input: ResearchSessionInput): Promise<ResearchRunResponse> {
  const response = await fetch(`${API_BASE}/api/research/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error((await safeParseError(response)) ?? `HTTP ${response.status}`);
  }

  return response.json();
}


export async function streamResearchSession(
  input: ResearchSessionInput,
  onEvent: (event: ResearchStreamEvent) => void,
  onError: (message: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/research/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
    signal,
  });

  if (!response.ok) {
    onError((await safeParseError(response)) ?? `HTTP ${response.status}`);
    return;
  }

  if (!response.body) {
    onError("SSE 连接建立失败：响应体为空。");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const payload = parseSseChunk(chunk);
        if (!payload) {
          continue;
        }

        try {
          onEvent(JSON.parse(payload) as ResearchStreamEvent);
        } catch (error) {
          console.error("Failed to parse SSE payload", error, payload);
        }
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    onError(error instanceof Error ? error.message : "SSE 流读取失败。");
  } finally {
    reader.releaseLock();
  }
}


function parseSseChunk(chunk: string): string | null {
  const dataLines = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());

  if (dataLines.length === 0) {
    return null;
  }

  return dataLines.join("\n");
}


async function safeParseError(response: Response): Promise<string | null> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : null;
  } catch {
    return null;
  }
}
