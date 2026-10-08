import { clsx } from "clsx";
import type { ReactNode } from "react";

/** Surface card matching the admin dark theme (radius 12px). */
export function AdminCard({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-admin-border bg-admin-surface",
        padded && "p-5",
        className
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  right,
}: {
  children: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-admin-sub">
        {children}
      </h2>
      {right}
    </div>
  );
}

type Tone = "success" | "warning" | "error" | "info" | "primary" | "neutral";

const TONE_TEXT: Record<Tone, string> = {
  success: "text-admin-success",
  warning: "text-admin-warning",
  error: "text-admin-error",
  info: "text-admin-info",
  primary: "text-admin-primary",
  neutral: "text-admin-sub",
};

const TONE_BG: Record<Tone, string> = {
  success: "bg-admin-success",
  warning: "bg-admin-warning",
  error: "bg-admin-error",
  info: "bg-admin-info",
  primary: "bg-admin-primary",
  neutral: "bg-admin-sub",
};

/** A small status dot; `pulse` adds an animated ring (for "live" states). */
export function StatusDot({
  tone,
  pulse = false,
  className,
}: {
  tone: Tone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-block h-2.5 w-2.5 shrink-0 rounded-full",
        TONE_BG[tone],
        pulse && "animate-pulse-ring",
        className
      )}
    />
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  const ring: Record<Tone, string> = {
    success: "border-admin-success/30 bg-admin-success/10",
    warning: "border-admin-warning/30 bg-admin-warning/10",
    error: "border-admin-error/30 bg-admin-error/10",
    info: "border-admin-info/30 bg-admin-info/10",
    primary: "border-admin-primary/30 bg-admin-primary/10",
    neutral: "border-admin-border bg-white/5",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        ring[tone],
        TONE_TEXT[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

/** Animated horizontal progress bar (0–100). */
export function ProgressBar({
  value,
  tone = "primary",
  className,
  striped = false,
}: {
  value: number;
  tone?: Tone;
  className?: string;
  striped?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      className={clsx(
        "h-2 w-full overflow-hidden rounded-full bg-admin-border",
        className
      )}
    >
      <div
        className={clsx(
          "h-full rounded-full transition-all duration-500 ease-out",
          TONE_BG[tone],
          striped && "animate-pulse"
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/** Shimmer loading skeleton block. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-md bg-admin-border/60",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer",
        "after:bg-gradient-to-r after:from-transparent after:via-white/5 after:to-transparent",
        className
      )}
    />
  );
}

/** Inline error note (red) — never crash, always show this instead. */
export function ErrorNote({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-admin-error/30 bg-admin-error/10 px-4 py-3 text-sm text-admin-error">
      <span className="flex items-center gap-2">
        <span>⚠️</span>
        <span className="text-admin-txt/90">{message}</span>
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded-md border border-admin-error/40 px-2 py-0.5 text-xs text-admin-error hover:bg-admin-error/20"
        >
          Retry
        </button>
      )}
    </div>
  );
}

const PHASE_TONE: Record<string, { tone: Tone; icon: string; label: string }> = {
  download: { tone: "info", icon: "🔵", label: "Downloading" },
  audio_extract: { tone: "warning", icon: "🟡", label: "Extracting Audio" },
  transcription: { tone: "warning", icon: "🟠", label: "Transcribing" },
  dna_analysis: { tone: "primary", icon: "🟣", label: "Analyzing DNA" },
  dna_report: { tone: "primary", icon: "🟣", label: "Building Report" },
  system_prompt: { tone: "success", icon: "🟢", label: "Generating Prompt" },
  complete: { tone: "success", icon: "✅", label: "Complete" },
  failed: { tone: "error", icon: "🔴", label: "Failed" },
};

/** Phase badge for the Overview active-extractions table. */
export function PhaseBadge({ phaseKey }: { phaseKey: string }) {
  const meta = PHASE_TONE[phaseKey] || {
    tone: "neutral" as Tone,
    icon: "⏳",
    label: phaseKey,
  };
  return (
    <Badge tone={meta.tone}>
      <span>{meta.icon}</span>
      {meta.label}
    </Badge>
  );
}

/** Map a running job's `current_phase` index (1–6) + status to a phase key. */
export function jobPhaseKey(job: {
  status: string;
  current_phase: number;
}): string {
  if (job.status === "complete") return "complete";
  if (job.status === "failed") return "failed";
  const keys = [
    "download",
    "audio_extract",
    "transcription",
    "dna_analysis",
    "dna_report",
    "system_prompt",
  ];
  return keys[Math.max(0, Math.min(keys.length - 1, job.current_phase - 1))];
}
