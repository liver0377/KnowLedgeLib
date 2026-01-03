// src/api/sse.ts
export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "message"; content: any }
  | { type: "error"; content: string };

export async function streamChat(
  url: string,
  payload: any,
  onEvent: (ev: StreamEvent) => void
) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(`Stream failed: ${res.status} ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE event 以 \n\n 分隔
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((s) => s.trimEnd())
        .find((l) => l.startsWith("data:"));

      if (!line) continue;

      const data = line.replace(/^data:\s*/, "");
      if (data === "[DONE]") return;

      try {
        const obj = JSON.parse(data);
        onEvent(obj as StreamEvent);
      } catch {
        onEvent({ type: "error", content: "Bad SSE payload" });
      }
    }
  }
}
