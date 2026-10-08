"use client";
/**
 * Admin dashboard API client + shared types.
 *
 * Talks to the local TeachClone API (default http://localhost:8000). In
 * DEV_MODE the backend bypasses auth, so no token is sent. Every fetcher
 * throws on a non-2xx response with a readable message; callers render an
 * error state rather than crashing.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
//  Types
// ---------------------------------------------------------------------------
export interface SystemHealth {
  status: string;
  version: string;
  timestamp: string;
  dev_mode: boolean;
}

export interface DnaHealth {
  reachable: boolean;
  models: string[];
  base_url: string;
  error?: string;
  default_model: string;
  fallback_model: string;
  whisper_model: string;
}

export interface DnaJob {
  job_id: string;
  teacher_id: string;
  teacher_name: string;
  model: string;
  whisper_model: string;
  source: "url" | "file" | "regenerate";
  status: "running" | "complete" | "failed";
  current_phase: number;
  current_layer: string | null;
  phase_progress: Record<string, number>;
  layers_done: string[];
  layers_total: number;
  stats: {
    videos_downloaded: number;
    videos_total: number;
    words_transcribed: number;
    language_detected: string;
  };
  started_at: string;
  finished_at: string | null;
  eta_seconds: number | null;
  error: string | null;
}

export interface JobsResponse {
  active: DnaJob[];
  recent: DnaJob[];
}

export interface LogLine {
  seq: number;
  ts: string;
  level: string;
  logger: string;
  message: string;
}

export interface DnaLayerFlags {
  vocabulary_dna: boolean;
  explanation_dna: boolean;
  example_dna: boolean;
  question_dna: boolean;
  correction_dna: boolean;
  transition_dna: boolean;
  emotion_dna: boolean;
}

export type TeacherStatus = "none" | "partial" | "complete" | "processing";

export interface AdminTeacher {
  id: string;
  name: string;
  subject: string | null;
  description: string | null;
  created_at: string | null;
  total_sources: number;
  has_dna: boolean;
  status: TeacherStatus;
  dna: {
    analyzed_videos: number;
    total_words: number;
    language: string | null;
    model_used: string | null;
    extraction_date: string | null;
    updated_at: string | null;
    layers: DnaLayerFlags;
    layers_filled: number;
    signature_phrases: string[];
    teaching_fingerprint: string;
  } | null;
}

export interface DnaSystem {
  ollama: DnaHealth & { models: string[] };
  whisper_model: string;
  database: {
    type: string;
    file: string | null;
    size_bytes: number | null;
    tables: number | null;
    row_counts: Record<string, number>;
  };
  tools: {
    ffmpeg: { available: boolean; version: string | null };
    yt_dlp: { available: boolean; version: string | null };
    whisper: { available: boolean; model: string; engine: string };
  };
  memory:
    | { available: false }
    | {
        available: true;
        process_rss_bytes: number;
        system_total_bytes: number;
        system_used_bytes: number;
        system_percent: number;
      };
  disk:
    | { available: false }
    | { available: true; total_bytes: number; used_bytes: number; free_bytes: number };
  stats: {
    total_teachers: number;
    teachers_with_dna: number;
    dna_reports_total: number;
    dna_reports_today: number;
    media_sources_total: number;
    words_transcribed_total: number;
  };
  server_time: string;
}

/** The 7-layer DNA report (loosely typed — layer contents vary by model). */
export interface DnaReport {
  teacher_name?: string;
  analyzed_videos?: number;
  total_transcript_words?: number;
  language?: string;
  model_used?: string;
  extraction_date?: string;
  teaching_fingerprint?: string;
  signature_phrases?: string[];
  vocabulary_dna?: Record<string, any>;
  explanation_dna?: Record<string, any>;
  example_dna?: Record<string, any>;
  question_dna?: Record<string, any>;
  correction_dna?: Record<string, any>;
  transition_dna?: Record<string, any>;
  emotion_dna?: Record<string, any>;
  [k: string]: any;
}

export interface TeacherProfile {
  id: string;
  name: string;
  subject?: string | null;
  description?: string | null;
  total_sources: number;
  created_at: string;
  [k: string]: any;
}

// ---------------------------------------------------------------------------
//  Pipeline / layer metadata (shared by the progress + modal UIs)
// ---------------------------------------------------------------------------
export const PHASE_META = [
  { key: "download", label: "Video Download", icon: "📥" },
  { key: "audio_extract", label: "Audio Extraction", icon: "🎵" },
  { key: "transcription", label: "Transcription", icon: "🎙️" },
  { key: "dna_analysis", label: "DNA Analysis", icon: "🧬" },
  { key: "dna_report", label: "DNA Report", icon: "📊" },
  { key: "system_prompt", label: "System Prompt", icon: "📝" },
] as const;

export const LAYER_META = [
  { key: "vocabulary_dna", label: "Vocabulary", icon: "🔤" },
  { key: "explanation_dna", label: "Explanation", icon: "💡" },
  { key: "example_dna", label: "Examples", icon: "🧩" },
  { key: "question_dna", label: "Questions", icon: "❓" },
  { key: "correction_dna", label: "Correction", icon: "✏️" },
  { key: "transition_dna", label: "Transition", icon: "🔀" },
  { key: "emotion_dna", label: "Emotion", icon: "❤️" },
] as const;

// ---------------------------------------------------------------------------
//  Low-level fetch
// ---------------------------------------------------------------------------
async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      Accept: "application/json",
      ...(opts.body && !(opts.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    let detail: any = null;
    try {
      detail = await res.json();
    } catch {
      /* non-JSON body */
    }
    const msg =
      (detail && (detail.detail?.reason || detail.detail || detail.message)) ||
      `Request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

/** Fetch JSON and also report round-trip latency (for service pings). */
export async function requestTimed<T>(
  path: string
): Promise<{ data: T; latencyMs: number }> {
  const t0 = performance.now();
  const data = await request<T>(path);
  return { data, latencyMs: Math.round(performance.now() - t0) };
}

// ---------------------------------------------------------------------------
//  Endpoint helpers
// ---------------------------------------------------------------------------
export const getHealth = () => request<SystemHealth>("/health");
export const getDnaHealth = () => requestTimed<DnaHealth>("/dna/health");
export const getSystem = () => request<DnaSystem>("/dna/system");
export const getJobs = () => request<JobsResponse>("/dna/jobs");
export const getStatus = (jobId: string) => request<DnaJob>(`/dna/status/${jobId}`);
export const getLogs = (since?: number) =>
  request<{ logs: LogLine[] }>(
    `/dna/logs?limit=400${since != null ? `&since=${since}` : ""}`
  );
export const clearLogs = () => request<{ status: string }>("/dna/logs", { method: "DELETE" });
export const getTeachers = () => request<AdminTeacher[]>("/dna/teachers");
export const getProfiles = () => request<TeacherProfile[]>("/profiles");
export const getReport = (teacherId: string) => request<DnaReport>(`/dna/report/${teacherId}`);
export const getSystemPrompt = (teacherId: string) =>
  request<string>(`/dna/system-prompt/${teacherId}`);

export const startUrlExtraction = (body: {
  teacher_id: string;
  youtube_urls: string[];
  model?: string;
}) =>
  request<{ job_id: string; status: string; teacher_id: string }>("/dna/extract-from-url", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const startFileExtraction = (form: FormData) =>
  request<{ job_id: string; status: string; teacher_id: string }>("/dna/extract-from-file", {
    method: "POST",
    body: form,
  });

export const regenerate = (teacherId: string, model?: string) =>
  request<{ job_id: string; status: string; teacher_id: string }>(
    `/dna/regenerate/${teacherId}${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    { method: "POST" }
  );

export const createTeacher = (body: {
  name: string;
  subject?: string;
  description?: string;
}) =>
  request<TeacherProfile>("/profiles", {
    method: "POST",
    body: JSON.stringify(body),
  });

// ---------------------------------------------------------------------------
//  Polling hook — calls `fn` immediately, then every `intervalMs` while
//  `enabled`. Skips overlapping calls and updates only while mounted.
// ---------------------------------------------------------------------------
export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs: number,
  enabled = true
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const inFlight = useRef(false);

  const tick = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const result = await fnRef.current();
      setData(result);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Request failed");
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    setLoading(true);
    tick();
    const id = setInterval(() => {
      if (alive) tick();
    }, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, tick]);

  return { data, error, loading, refresh: tick };
}

// ---------------------------------------------------------------------------
//  Formatters
// ---------------------------------------------------------------------------
export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

export function fmtNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1000) return n.toLocaleString("en-US");
  return String(n);
}

export function fmtCompact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds <= 0) return "0s";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m <= 0) return `${s}s`;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function fmtEta(seconds: number | null | undefined): string {
  if (seconds == null) return "estimating…";
  if (seconds <= 0) return "almost done";
  const m = Math.round(seconds / 60);
  if (m < 1) return "< 1 min";
  return `~${m} min`;
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return secs <= 3 ? "just now" : `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

/** Short model label, e.g. "qwen3.5:latest" -> "qwen3.5". */
export function shortModel(model: string | null | undefined): string {
  if (!model) return "—";
  return model.replace(/:latest$/, "");
}
