"use client";
import { clsx } from "clsx";
import {
  fmtEta,
  fmtNumber,
  LAYER_META,
  PHASE_META,
  shortModel,
  timeAgo,
  type DnaJob,
} from "@/lib/adminApi";
import { AdminCard, Badge, ProgressBar } from "./primitives";

type PhaseState = "done" | "active" | "pending";

function phaseState(job: DnaJob, index: number, pct: number): PhaseState {
  if (pct >= 100) return "done";
  if (job.status === "running" && job.current_phase === index + 1) return "active";
  if (job.current_phase > index + 1) return "done";
  return "pending";
}

const STATE_ICON: Record<PhaseState, string> = {
  done: "✅",
  active: "🔄",
  pending: "⏳",
};

function LayerRow({ job, field, label, icon }: {
  job: DnaJob;
  field: string;
  label: string;
  icon: string;
}) {
  const done = job.layers_done.includes(field);
  const active = !done && job.status === "running" && job.current_layer === field;
  const state: PhaseState = done ? "done" : active ? "active" : "pending";
  return (
    <div
      className={clsx(
        "flex items-center gap-2 text-sm",
        state === "pending" ? "text-admin-sub" : "text-admin-txt/90"
      )}
    >
      <span className={clsx(active && "animate-pulse")}>{STATE_ICON[state]}</span>
      <span>{icon}</span>
      <span>{label} DNA</span>
      {active && <span className="text-xs text-admin-primary">(analyzing…)</span>}
    </div>
  );
}

export function ExtractionProgress({
  job,
  onDismiss,
}: {
  job: DnaJob;
  onDismiss?: () => void;
}) {
  const running = job.status === "running";
  const failed = job.status === "failed";
  const complete = job.status === "complete";

  return (
    <AdminCard padded={false} className="overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-admin-border bg-admin-elevated/40 px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 font-semibold text-admin-txt">
            <span>🧬</span>
            <span className="truncate">
              {complete ? "Extracted DNA" : failed ? "Extraction failed" : "Extracting DNA"}:{" "}
              <span className="text-admin-primary">&ldquo;{job.teacher_name}&rdquo;</span>
            </span>
          </div>
          <div className="mt-0.5 text-xs text-admin-sub">
            Model: {shortModel(job.model)} · Whisper: {job.whisper_model} · Started{" "}
            {timeAgo(job.started_at)}
          </div>
        </div>
        <Badge tone={complete ? "success" : failed ? "error" : "primary"}>
          {complete ? "✅ Complete" : failed ? "🔴 Failed" : "🔄 Running"}
        </Badge>
      </div>

      {/* Phases */}
      <div className="space-y-4 px-5 py-5">
        {PHASE_META.map((phase, i) => {
          const pct = job.phase_progress[phase.key] ?? 0;
          const state = phaseState(job, i, pct);
          const isAnalysis = phase.key === "dna_analysis";
          return (
            <div key={phase.key}>
              <div className="flex items-center gap-3">
                <span className="w-5 text-center">{STATE_ICON[state]}</span>
                <span className="w-6 text-center">{phase.icon}</span>
                <span
                  className={clsx(
                    "flex-1 text-sm font-medium",
                    state === "pending" ? "text-admin-sub" : "text-admin-txt"
                  )}
                >
                  Phase {i + 1}: {phase.label}
                </span>
                <span className="w-28">
                  <ProgressBar
                    value={pct}
                    tone={
                      failed && state === "active"
                        ? "error"
                        : pct >= 100
                        ? "success"
                        : "primary"
                    }
                  />
                </span>
                <span className="w-10 text-right text-xs tabular-nums text-admin-sub">
                  {Math.round(pct)}%
                </span>
              </div>

              {/* 7 layers under DNA Analysis */}
              {isAnalysis && (state === "active" || state === "done") && (
                <div className="ml-14 mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  {LAYER_META.map((l) => (
                    <LayerRow
                      key={l.key}
                      job={job}
                      field={l.key}
                      label={l.label}
                      icon={l.icon}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-admin-border px-5 py-4">
        <div className="text-sm">
          {running && (
            <span className="text-admin-sub">
              Words: {fmtNumber(job.stats.words_transcribed)}
              {job.stats.language_detected
                ? ` · Language: ${job.stats.language_detected}`
                : ""}
            </span>
          )}
          {failed && (
            <span className="text-admin-error">⚠️ {job.error || "Unknown error"}</span>
          )}
          {complete && (
            <span className="text-admin-success">
              ✅ {fmtNumber(job.stats.words_transcribed)} words ·{" "}
              {job.stats.videos_downloaded} source(s) analyzed
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {running && (
            <span className="text-sm font-medium text-admin-txt">
              ETA: {fmtEta(job.eta_seconds)}
            </span>
          )}
          {onDismiss && !running && (
            <button
              onClick={onDismiss}
              className="rounded-lg border border-admin-border px-3 py-1.5 text-sm text-admin-sub hover:text-admin-txt"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    </AdminCard>
  );
}
