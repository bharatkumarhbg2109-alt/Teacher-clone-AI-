"use client";
import { clsx } from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LogViewer } from "@/components/dashboard/LogViewer";
import { AdminCard } from "@/components/dashboard/primitives";
import { clearLogs, getLogs, type LogLine } from "@/lib/adminApi";

type Filter = "all" | "dna" | "whisper" | "ollama" | "errors";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "dna", label: "DNA" },
  { key: "whisper", label: "Whisper" },
  { key: "ollama", label: "Ollama" },
  { key: "errors", label: "Errors Only" },
];

const MAX_LINES = 3000;

function matchesFilter(log: LogLine, filter: Filter): boolean {
  const msg = log.message.toLowerCase();
  const lg = log.logger.toLowerCase();
  switch (filter) {
    case "dna":
      return /dna|\[phase|layer \d|🧬/.test(msg) || lg.includes("dna");
    case "whisper":
      return /whisper|transcrib|audio/.test(msg);
    case "ollama":
      return /ollama|model|layer/.test(msg) || lg.includes("ollama");
    case "errors":
      return ["ERROR", "CRITICAL", "WARNING"].includes(log.level.toUpperCase());
    default:
      return true;
  }
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [connected, setConnected] = useState<boolean | null>(null);
  const maxSeq = useRef(0);
  const inFlight = useRef(false);

  const poll = useCallback(async (initial = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const resp = await getLogs(initial ? undefined : maxSeq.current);
      setConnected(true);
      if (resp.logs.length > 0) {
        for (const l of resp.logs) if (l.seq > maxSeq.current) maxSeq.current = l.seq;
        setLogs((prev) => {
          const merged = initial ? resp.logs : [...prev, ...resp.logs];
          return merged.length > MAX_LINES ? merged.slice(-MAX_LINES) : merged;
        });
      }
    } catch {
      setConnected(false);
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    poll(true);
    const id = setInterval(() => poll(false), 2_000);
    return () => clearInterval(id);
  }, [poll]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return logs.filter(
      (l) => matchesFilter(l, filter) && (!q || l.message.toLowerCase().includes(q))
    );
  }, [logs, filter, search]);

  async function handleClear() {
    try {
      await clearLogs();
    } catch {
      /* ignore */
    }
    maxSeq.current = 0;
    setLogs([]);
  }

  function handleDownload() {
    const text = filtered
      .map((l) => `[${new Date(l.ts).toISOString()}] ${l.level} ${l.logger} — ${l.message}`)
      .join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `teachclone-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-admin-txt">📋 Live Logs</h1>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={clsx(
              "inline-block h-2 w-2 rounded-full",
              connected === null
                ? "bg-admin-sub"
                : connected
                ? "animate-pulse-ring bg-admin-success"
                : "bg-admin-error"
            )}
          />
          <span className="text-admin-sub">
            {connected === false ? "Disconnected" : "Streaming · every 2s"}
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <AdminCard padded={false} className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex flex-wrap gap-1 rounded-lg border border-admin-border p-0.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={clsx(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition",
                  filter === f.key
                    ? "bg-admin-primary text-white"
                    : "text-admin-sub hover:text-admin-txt"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>

          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="🔍 Search logs…"
            className="min-w-[10rem] flex-1 rounded-lg border border-admin-border bg-admin-bg px-3 py-1.5 text-sm text-admin-txt outline-none focus:border-admin-primary"
          />

          <label className="flex cursor-pointer items-center gap-2 text-xs text-admin-sub">
            <span>Auto-scroll</span>
            <button
              onClick={() => setAutoScroll((v) => !v)}
              className={clsx(
                "relative h-5 w-9 rounded-full transition",
                autoScroll ? "bg-admin-primary" : "bg-admin-border"
              )}
            >
              <span
                className={clsx(
                  "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                  autoScroll ? "left-4" : "left-0.5"
                )}
              />
            </button>
          </label>

          <div className="flex gap-2">
            <button
              onClick={handleClear}
              className="rounded-lg border border-admin-border px-3 py-1.5 text-xs text-admin-sub hover:text-admin-txt"
            >
              Clear
            </button>
            <button
              onClick={handleDownload}
              disabled={filtered.length === 0}
              className="rounded-lg border border-admin-border px-3 py-1.5 text-xs text-admin-sub hover:text-admin-txt disabled:opacity-40"
            >
              ⬇️ Download
            </button>
          </div>
        </div>
      </AdminCard>

      <div className="flex items-center justify-between text-xs text-admin-sub">
        <span>
          {filtered.length} line{filtered.length === 1 ? "" : "s"}
          {filter !== "all" || search ? ` (of ${logs.length})` : ""}
        </span>
      </div>

      <LogViewer
        logs={filtered}
        autoScroll={autoScroll}
        emptyLabel={
          connected === false
            ? "Cannot reach the API — is the server running?"
            : logs.length === 0
            ? "Waiting for log activity… start a DNA extraction to see the pipeline log."
            : "No lines match the current filter."
        }
      />
    </div>
  );
}
