"use client";
import { useEffect, useState } from "react";
import {
  getReport,
  getSystemPrompt,
  LAYER_META,
  shortModel,
  type DnaReport,
} from "@/lib/adminApi";
import { Badge, ErrorNote, Skeleton } from "./primitives";

function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\bdna\b/gi, "")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Recursively render an arbitrary DNA value in a readable way. */
function Value({ value }: { value: any }) {
  if (value == null || value === "") return <span className="text-admin-sub">—</span>;
  if (typeof value === "boolean")
    return (
      <span className={value ? "text-admin-success" : "text-admin-sub"}>
        {value ? "✅ Yes" : "❌ No"}
      </span>
    );
  if (typeof value === "number" || typeof value === "string")
    return <span className="text-admin-txt/90">{String(value)}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-admin-sub">—</span>;
    const allScalar = value.every(
      (v) => typeof v === "string" || typeof v === "number"
    );
    if (allScalar)
      return (
        <div className="flex flex-wrap gap-1.5">
          {value.map((v, i) => (
            <span
              key={i}
              className="rounded-md bg-admin-primary/10 px-2 py-0.5 text-xs text-admin-primary"
            >
              {String(v)}
            </span>
          ))}
        </div>
      );
    return (
      <ul className="list-disc space-y-1 pl-4">
        {value.map((v, i) => (
          <li key={i} className="text-admin-txt/90">
            <Value value={v} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object")
    return (
      <div className="space-y-1.5">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            <span className="text-xs font-medium text-admin-sub">{humanize(k)}: </span>
            <Value value={v} />
          </div>
        ))}
      </div>
    );
  return <span className="text-admin-txt/90">{String(value)}</span>;
}

function LayerPanel({ layer }: { layer: Record<string, any> | undefined }) {
  if (!layer || Object.keys(layer).length === 0)
    return (
      <div className="py-8 text-center text-sm text-admin-sub">
        No data captured for this layer.
      </div>
    );
  return (
    <div className="space-y-4">
      {Object.entries(layer).map(([key, val]) => (
        <div key={key} className="rounded-lg border border-admin-border bg-admin-bg/40 p-3">
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-admin-primary">
            {humanize(key)}
          </div>
          <div className="text-sm">
            <Value value={val} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DnaLayerModal({
  teacherId,
  teacherName,
  onClose,
}: {
  teacherId: string;
  teacherName: string;
  onClose: () => void;
}) {
  const [report, setReport] = useState<DnaReport | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([
      getReport(teacherId),
      getSystemPrompt(teacherId).catch(() => ""),
    ])
      .then(([rep, pr]) => {
        if (!alive) return;
        setReport(rep);
        setPrompt(pr || "");
      })
      .catch((e) => alive && setError(e?.message || "Failed to load DNA report"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [teacherId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copyPrompt = async () => {
    if (!prompt) return;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  };

  const activeLayerKey = LAYER_META[tab].key;
  const layer = report?.[activeLayerKey] as Record<string, any> | undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl rounded-2xl border border-admin-border bg-admin-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-admin-border p-5">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold text-admin-txt">
              <span>🧬</span> DNA — {teacherName}
            </div>
            {report && (
              <div className="mt-1 flex flex-wrap gap-2 text-xs text-admin-sub">
                <Badge tone="neutral">📹 {report.analyzed_videos ?? 0} videos</Badge>
                <Badge tone="neutral">
                  📝 {(report.total_transcript_words ?? 0).toLocaleString()} words
                </Badge>
                <Badge tone="neutral">🤖 {shortModel(report.model_used)}</Badge>
                {report.language && <Badge tone="neutral">🌐 {report.language}</Badge>}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-lg border border-admin-border text-admin-sub hover:text-admin-txt"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : error ? (
          <div className="p-5">
            <ErrorNote message={error} />
          </div>
        ) : (
          <>
            {/* Fingerprint */}
            {report?.teaching_fingerprint && (
              <div className="border-b border-admin-border bg-admin-primary/5 px-5 py-3 text-sm italic text-admin-txt/80">
                “{report.teaching_fingerprint}”
              </div>
            )}

            {/* Tabs */}
            <div className="flex gap-1 overflow-x-auto border-b border-admin-border px-3 py-2">
              {LAYER_META.map((l, i) => (
                <button
                  key={l.key}
                  onClick={() => setTab(i)}
                  className={
                    "whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition " +
                    (i === tab
                      ? "bg-admin-primary/15 text-admin-txt ring-1 ring-inset ring-admin-primary/30"
                      : "text-admin-sub hover:text-admin-txt")
                  }
                >
                  {l.icon} {l.label}
                </button>
              ))}
            </div>

            {/* Layer content */}
            <div className="max-h-[45vh] overflow-y-auto p-5">
              <LayerPanel layer={layer} />
            </div>

            {/* System prompt */}
            <div className="border-t border-admin-border p-5">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-admin-txt">
                  Generated System Prompt
                </span>
                <button
                  onClick={copyPrompt}
                  disabled={!prompt}
                  className="rounded-lg border border-admin-border px-2.5 py-1 text-xs text-admin-sub hover:text-admin-txt disabled:opacity-40"
                >
                  {copied ? "✅ Copied" : "📋 Copy Prompt"}
                </button>
              </div>
              {prompt ? (
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-admin-border bg-admin-bg/60 p-3 font-mono text-xs leading-relaxed text-admin-txt/80">
                  {expanded ? prompt : prompt.slice(0, 300) + (prompt.length > 300 ? "…" : "")}
                </pre>
              ) : (
                <div className="text-sm text-admin-sub">No system prompt stored.</div>
              )}
              {prompt && prompt.length > 300 && (
                <button
                  onClick={() => setExpanded((v) => !v)}
                  className="mt-2 text-xs text-admin-primary hover:underline"
                >
                  {expanded ? "Show less" : "Show full prompt"}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
