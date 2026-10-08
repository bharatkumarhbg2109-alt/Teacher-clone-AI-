"use client";
import { clsx } from "clsx";
import {
  fmtNumber,
  LAYER_META,
  shortModel,
  timeAgo,
  type AdminTeacher,
  type TeacherStatus,
} from "@/lib/adminApi";
import { AdminCard, Badge } from "./primitives";

const STATUS_META: Record<
  TeacherStatus,
  { label: string; icon: string; tone: "error" | "warning" | "success" | "info" }
> = {
  none: { label: "No DNA", icon: "🔴", tone: "error" },
  partial: { label: "Partial", icon: "🟡", tone: "warning" },
  complete: { label: "Complete", icon: "🟢", tone: "success" },
  processing: { label: "Processing", icon: "🔵", tone: "info" },
};

export function TeacherCard({
  teacher,
  onViewDna,
  onReextract,
  reextracting = false,
}: {
  teacher: AdminTeacher;
  onViewDna: (t: AdminTeacher) => void;
  onReextract: (t: AdminTeacher) => void;
  reextracting?: boolean;
}) {
  const status = STATUS_META[teacher.status];
  const dna = teacher.dna;

  return (
    <AdminCard padded={false} className="flex flex-col">
      {/* Head */}
      <div className="flex items-start justify-between gap-2 border-b border-admin-border p-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 font-semibold text-admin-txt">
            <span>👨‍🏫</span>
            <span className="truncate">{teacher.name}</span>
          </div>
          <div className="mt-0.5 text-xs text-admin-sub">
            {teacher.subject || "No subject"} · created {timeAgo(teacher.created_at)}
          </div>
        </div>
        <Badge tone={status.tone}>
          {status.icon} {status.label}
        </Badge>
      </div>

      {/* DNA stats */}
      <div className="space-y-1.5 p-4 text-xs">
        {dna ? (
          <>
            <Stat label="Videos analyzed" value={fmtNumber(dna.analyzed_videos)} />
            <Stat label="Words transcribed" value={fmtNumber(dna.total_words)} />
            <Stat label="Model used" value={shortModel(dna.model_used)} />
            {dna.language && <Stat label="Language" value={dna.language} />}
          </>
        ) : (
          <div className="text-admin-sub">
            No DNA extracted yet. Run an extraction from the DNA Center.
          </div>
        )}
      </div>

      {/* 7 layers */}
      <div className="border-t border-admin-border p-4">
        <div className="mb-2 text-xs font-medium text-admin-sub">DNA Layers</div>
        <div className="grid grid-cols-2 gap-1.5">
          {LAYER_META.map((l) => {
            const on = !!dna?.layers?.[l.key as keyof typeof dna.layers];
            return (
              <div
                key={l.key}
                className={clsx(
                  "flex items-center gap-1.5 text-xs",
                  on ? "text-admin-txt/90" : "text-admin-sub"
                )}
              >
                <span>{on ? "✅" : "⬜"}</span>
                <span className="truncate">{l.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Signature phrases */}
      {dna && dna.signature_phrases.length > 0 && (
        <div className="border-t border-admin-border p-4">
          <div className="mb-2 text-xs font-medium text-admin-sub">
            Signature phrases
          </div>
          <div className="flex flex-wrap gap-1.5">
            {dna.signature_phrases.slice(0, 4).map((p, i) => (
              <span
                key={i}
                className="truncate rounded-md bg-admin-primary/10 px-2 py-0.5 text-xs text-admin-primary"
                title={p}
              >
                &ldquo;{p}&rdquo;
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-auto flex flex-wrap gap-2 border-t border-admin-border p-4">
        <button
          onClick={() => onViewDna(teacher)}
          disabled={!teacher.has_dna}
          className="inline-flex items-center gap-1.5 rounded-lg bg-admin-primary/90 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-admin-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          🧬 View DNA
        </button>
        <a
          href={`/profiles/${teacher.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-admin-border px-3 py-1.5 text-xs font-medium text-admin-sub transition hover:text-admin-txt"
        >
          💬 Test Chat
        </a>
        <button
          onClick={() => onReextract(teacher)}
          disabled={reextracting || teacher.status === "processing"}
          className="inline-flex items-center gap-1.5 rounded-lg border border-admin-border px-3 py-1.5 text-xs font-medium text-admin-sub transition hover:text-admin-txt disabled:cursor-not-allowed disabled:opacity-40"
        >
          {reextracting ? "…" : teacher.status === "processing" ? "⏳ Running" : "🔄 Re-extract"}
        </button>
      </div>
    </AdminCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-admin-sub">{label}</span>
      <span className="font-medium text-admin-txt/90">{value}</span>
    </div>
  );
}
