"use client";
import { ArrowDown, ArrowUp, Mic, Paperclip, Send, Sparkles, Volume2, X } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CheckpointCard } from "@/components/CheckpointCard";
import { Badge, Button, Spinner, TopNav } from "@/components/ui";
import { API_URL, api, streamChat } from "@/lib/api";
import { levelLabel } from "@/lib/constants";
import type { ChatMessage, Quiz, Session } from "@/lib/types";

function locator(c: any): string {
  if (c.page != null) return `p.${c.page}`;
  if (c.start_time != null) {
    const m = Math.floor(c.start_time / 60);
    const s = Math.floor(c.start_time % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }
  return "ref";
}

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [wantAudio, setWantAudio] = useState(false);
  const [checkpoint, setCheckpoint] = useState<Quiz | null>(null);
  const [loadingCp, setLoadingCp] = useState(false);
  const [recording, setRecording] = useState(false);
  const [effLevel, setEffLevel] = useState<string | undefined>();
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<Session>(`/sessions/${sessionId}`).then((s) => {
      setSession(s);
      setMessages(s.messages || []);
      setEffLevel(s.current_effective_level || s.student_profile?.level);
    });
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, checkpoint]);

  // P3: Image upload handler
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      alert("Image must be under 10 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      setImagePreview(ev.target?.result as string);
      setImageFile(file);
    };
    reader.readAsDataURL(file);
  };

  const removeImage = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const send = useCallback(
    async (text: string) => {
      if ((!text.trim() && !imagePreview) || streaming) return;
      setInput("");
      setStreaming(true);

      // Strip the data: prefix from the base64 string
      const imageBase64 = imagePreview?.split(",")[1] ?? null;
      const imageMediaType = imageFile?.type ?? null;
      const userLabel = text.trim() || (imagePreview ? "[Image]" : "");
      const userMsg: ChatMessage = { id: `u${Date.now()}`, role: "user", content: userLabel, citations: [] };
      const aMsg: ChatMessage = { id: `a${Date.now()}`, role: "assistant", content: "", citations: [] };
      setMessages((m) => [...m, userMsg, aMsg]);
      removeImage();

      try {
        await streamChat(sessionId, text, wantAudio, {
          onToken: (t) =>
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], content: copy[copy.length - 1].content + t };
              return copy;
            }),
          onDone: (d) =>
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                ...copy[copy.length - 1],
                id: d.message_id,
                citations: d.citations || [],
                audio_url: d.audio_url,
              };
              return copy;
            }),
          onError: (msg) =>
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], content: `⚠️ ${msg}` };
              return copy;
            }),
        }, imageBase64, imageMediaType);
      } catch (error) {
        console.error("Chat stream error:", error);
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant" && !last.content) {
            copy[copy.length - 1] = { ...last, content: "⚠️ Message failed to send. Please try again." };
          }
          return copy;
        });
      } finally {
        setStreaming(false);
      }
    },
    [sessionId, streaming, wantAudio, imagePreview, imageFile]
  );

  async function adjust(direction: "simpler" | "deeper") {
    const r = await api<{ level: string }>(`/sessions/${sessionId}/adjust-level`, {
      method: "POST",
      body: JSON.stringify({ direction }),
    });
    setEffLevel(r.level);
    await send(direction === "simpler" ? "Please re-explain that more simply." : "Go deeper on that, please.");
  }

  async function makeCheckpoint() {
    setLoadingCp(true);
    try {
      const q = await api<Quiz>(`/sessions/${sessionId}/checkpoint`, {
        method: "POST",
        body: JSON.stringify({ num_questions: 2 }),
      });
      setCheckpoint(q);
    } catch {
      alert("Failed to load checkpoint. Please try again.");
    } finally {
      setLoadingCp(false);
    }
  }

  async function onCheckpointResolved(r: any) {
    setEffLevel(r.updated_level);
    setTimeout(() => setCheckpoint(null), 2500);
    if (r.adapt === "reteach") {
      const concept = r.review_concepts?.[0];
      await send(`I got some of that wrong. Please re-teach${concept ? ` ${concept}` : " that"} more simply.`);
    }
  }

  async function listen(msg: ChatMessage) {
    let url = msg.audio_url;
    if (!url) {
      const r = await api<{ audio_url: string }>(`/voice/speak`, {
        method: "POST",
        body: JSON.stringify({ message_id: msg.id }),
      });
      url = r.audio_url;
    }
    if (url) new Audio(url).play().catch(() => {});
  }

  async function toggleMic() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        const fd = new FormData();
        fd.append("file", blob, "voice.webm");
        try {
          const res = await fetch(`${API_URL}/voice/transcribe`, { method: "POST", body: fd });
          const data = await res.json();
          if (data.text) setInput((v) => (v ? v + " " : "") + data.text);
        } catch {}
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
      rec.addEventListener("stop", () => setRecording(false));
    } catch {
      alert("Microphone not available");
    }
  }

  const isValid = (input.trim().length > 0 || imagePreview) && input.length <= 10000;

  if (!session) return (<><TopNav /><main className="p-8"><Spinner label="Loading session…" /></main></>);

  return (
    <>
      <TopNav />
      <main className="mx-auto flex h-[calc(100vh-57px)] max-w-3xl flex-col px-4">
        <div className="flex items-center justify-between border-b border-borderc py-3">
          <div>
            <div className="font-semibold">{session.teacher_profile?.name}</div>
            <div className="text-xs text-muted">
              {session.student_profile?.subject} · level: {levelLabel(effLevel)}
              {session.student_profile?.learn_ahead ? " · ahead 🚀" : ""}
            </div>
          </div>
          <Button variant="outline" onClick={makeCheckpoint} loading={loadingCp}>
            <Sparkles className="h-4 w-4" /> Checkpoint
          </Button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto py-4">
          {messages.length === 0 && (
            <p className="mt-10 text-center text-sm text-muted">
              Ask anything about {session.student_profile?.subject}. The teacher adapts to your level.
            </p>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo px-4 py-2 text-sm text-white">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-borderc bg-card px-4 py-3">
                  <div className="prose-chat text-sm text-slate-200">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || "…"}</ReactMarkdown>
                  </div>
                  {m.citations?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.citations.map((c, j) => (
                        <span key={j} title={c.chunk_text} className="cursor-help">
                          <Badge className="border-cyan/30 text-cyan">[{locator(c)}]</Badge>
                        </span>
                      ))}
                    </div>
                  )}
                  {m.content && !(streaming && i === messages.length - 1) && (
                    <div className="mt-2 flex gap-1">
                      <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => adjust("simpler")}>
                        <ArrowDown className="h-3 w-3" /> Simpler
                      </Button>
                      <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => adjust("deeper")}>
                        <ArrowUp className="h-3 w-3" /> Deeper
                      </Button>
                      <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => listen(m)}>
                        <Volume2 className="h-3 w-3" /> Listen
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            )
          )}
          {checkpoint && <CheckpointCard quiz={checkpoint} onResolved={onCheckpointResolved} />}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-borderc py-3">
          <div className="mb-2 flex items-center gap-2">
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
              <input type="checkbox" checked={wantAudio} onChange={(e) => setWantAudio(e.target.checked)} className="accent-indigo" />
              🔊 Audio answers
            </label>
          </div>

          {/* P3: Image preview */}
          {imagePreview && (
            <div className="mb-2 relative inline-block">
              <img
                src={imagePreview}
                alt="Upload preview"
                className="h-20 rounded-lg border border-borderc object-cover"
              />
              <button
                type="button"
                onClick={removeImage}
                className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white text-xs"
                aria-label="Remove image"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2"
          >
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              className="px-3"
              aria-label="Attach image"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              maxLength={10000}
              placeholder="Ask your teacher…"
              className="max-h-32 flex-1 resize-none rounded-xl border border-borderc bg-surface px-4 py-2.5 text-sm outline-none focus:border-indigo-light"
            />
            <Button type="button" variant={recording ? "danger" : "outline"} onClick={toggleMic} className="px-3">
              <Mic className="h-4 w-4" />
            </Button>
            <Button type="submit" disabled={!isValid || streaming} loading={streaming} className="px-3">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </main>
    </>
  );
}
