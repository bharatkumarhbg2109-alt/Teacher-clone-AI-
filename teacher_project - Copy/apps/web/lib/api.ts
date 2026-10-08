export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    let detail: any = null;
    try {
      detail = await res.json();
    } catch {}
    // For validation errors (422), show field-level messages (safe and helpful).
    // For other errors, show a generic message — never leak raw API internals.
    let userMessage = `Request failed (${res.status})`;
    if (res.status === 422 && detail?.errors) {
      userMessage = detail.errors.map((e: any) => e.message).join("; ");
    } else if (detail?.detail) {
      // detail.detail is safe — it's a user-facing string we set on the backend
      userMessage = typeof detail.detail === "string" ? detail.detail : userMessage;
    }
    throw new Error(userMessage);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/** POST a chat message and stream the SSE response. */
export async function streamChat(
  sessionId: string,
  content: string,
  wantAudio: boolean,
  handlers: {
    onToken: (t: string) => void;
    onDone: (d: { message_id: string; citations: any[]; audio_url?: string | null }) => void;
    onError?: (m: string) => void;
  },
  imageBase64?: string | null,
  imageMediaType?: string | null,
): Promise<void> {
  const payload: Record<string, unknown> = { content, want_audio: wantAudio };
  if (imageBase64) {
    payload.image_base64 = imageBase64;
    payload.image_media_type = imageMediaType;
  }
  const res = await fetch(`${API_URL}/chat/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    handlers.onError?.(`Chat error (${res.status}). Please try again.`);
    return;
  }
  if (!res.body) {
    handlers.onError?.("No response stream");
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      let event = "message";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      currentEvent = event;
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        if (currentEvent === "token") handlers.onToken(parsed.token);
        else if (currentEvent === "done") handlers.onDone(parsed);
        else if (currentEvent === "error") handlers.onError?.(parsed.message);
      } catch {}
    }
  }
}
