"use client";
import { clsx } from "clsx";
import { useEffect, useRef } from "react";
import type { LogLine } from "@/lib/adminApi";

function lineColor(log: LogLine): string {
  const level = log.level.toUpperCase();
  const msg = log.message;
  if (level === "ERROR" || level === "CRITICAL") return "text-admin-error";
  if (level === "WARNING") return "text-admin-warning";
  if (level === "DEBUG") return "text-admin-info";
  // DNA pipeline events get their own colour.
  if (/\[Phase|DNA|🧬|Layer \d/.test(msg)) return "text-admin-primary";
  return "text-admin-success";
}

function hhmmss(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

export function LogViewer({
  logs,
  autoScroll,
  emptyLabel = "No log lines yet.",
}: {
  logs: LogLine[];
  autoScroll: boolean;
  emptyLabel?: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  return (
    <div
      ref={boxRef}
      className="h-[62vh] overflow-y-auto rounded-xl border border-admin-border bg-black/60 p-4 font-mono text-xs leading-relaxed"
    >
      {logs.length === 0 ? (
        <div className="py-10 text-center text-admin-sub">{emptyLabel}</div>
      ) : (
        logs.map((log) => (
          <div key={log.seq} className="flex gap-2 whitespace-pre-wrap break-words py-0.5">
            <span className="shrink-0 text-admin-sub">[{hhmmss(log.ts)}]</span>
            <span className={clsx("min-w-0", lineColor(log))}>{log.message}</span>
          </div>
        ))
      )}
    </div>
  );
}
