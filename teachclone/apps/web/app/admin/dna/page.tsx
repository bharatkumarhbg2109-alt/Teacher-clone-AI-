"use client";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { ExtractionProgress } from "@/components/dashboard/ExtractionProgress";
import { ModelSelector, type ModelOption } from "@/components/dashboard/ModelSelector";
import {
  AdminCard,
  Badge,
  ErrorNote,
  SectionTitle,
  Skeleton,
} from "@/components/dashboard/primitives";
import {
  fmtDuration,
  fmtNumber,
  getDnaHealth,
  getJobs,
  getTeachers,
  shortModel,
  startFileExtraction,
  startUrlExtraction,
  timeAgo,
  usePolling,
  type AdminTeacher,
  type DnaJob,
} from "@/lib/adminApi";

const WHISPER_OPTIONS: ModelOption[] = [
  { value: "tiny", label: "tiny", desc: "Fastest, less accurate" },
  { value: "small", label: "small", desc: "Good balance" },
  { value: "medium", label: "medium", desc: "Recommended", badge: "★", badgeTone: "primary" },
  { value: "large", label: "large", desc: "Most accurate, slowest" },
];

function modelMeta(name: string): Omit<ModelOption, "value" | "label"> {
  const n = name.toLowerCase();
  if (n.includes("llama")) return { icon: "🦙", desc: "Meta Llama — strong analysis" };
  if (n.includes("mistral")) return { icon: "🌪️", desc: "Faster — good for quick tests" };
  if (n.includes("qwen")) return { icon: "⚡", desc: "Reasoning model (available here)" };
  if (n.includes("llava")) return { icon: "🖼️", desc: "Vision model" };
  if (n.includes("deepseek"))
    return { icon: "🧩", desc: "May OOM on this machine", badge: "⚠️ OOM", badgeTone: "warning" };
  return { icon: "🤖", desc: "Installed Ollama model" };
}

const ACCEPT = ".mp4,.avi,.mov,.mkv,.webm,.mp3,.wav,.m4a,.aac";

export default function DnaCenterPage() {
  const { data: jobs } = usePolling(getJobs, 3_000);
  const { data: teachers } = usePolling<AdminTeacher[]>(getTeachers, 20_000);
  const { data: healthTimed } = usePolling(getDnaHealth, 30_000);
  const health = healthTimed?.data;

  const [teacherId, setTeacherId] = useState("");
  const [sourceType, setSourceType] = useState<"url" | "file">("url");
  const [urlText, setUrlText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState("");
  const [whisper, setWhisper] = useState("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const modelOptions: ModelOption[] = useMemo(() => {
    const models = health?.models ?? [];
    if (models.length === 0) return [];
    return models.map((m) => ({ value: m, label: shortModel(m), ...modelMeta(m) }));
  }, [health]);

  // Default the model selection once models load.
  const effectiveModel =
    model ||
    health?.models?.find((m) => m.startsWith(health.default_model)) ||
    health?.models?.[0] ||
    "";

  const urlList = urlText
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  const active = jobs?.active ?? [];
  const historyRows = (jobs?.recent ?? []).filter((j) => j.status !== "running");

  const canSubmit =
    !!teacherId &&
    !submitting &&
    (sourceType === "url" ? urlList.length > 0 : !!file) &&
    !!effectiveModel;

  async function handleStart() {
    setError(null);
    setNotice(null);
    if (!teacherId) return setError("Select a teacher first.");
    setSubmitting(true);
    try {
      let res;
      if (sourceType === "url") {
        if (urlList.length === 0) throw new Error("Add at least one YouTube URL.");
        res = await startUrlExtraction({
          teacher_id: teacherId,
          youtube_urls: urlList,
          model: effectiveModel,
        });
      } else {
        if (!file) throw new Error("Choose a file to upload.");
        const form = new FormData();
        form.append("teacher_id", teacherId);
        form.append("model", effectiveModel);
        form.append("file", file);
        res = await startFileExtraction(form);
      }
      setNotice(`Extraction started (job ${res.job_id}). Watch progress below.`);
      setUrlText("");
      setFile(null);
    } catch (e: any) {
      setError(e?.message || "Failed to start extraction.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-admin-txt">🧬 DNA Extraction Center</h1>
        <p className="text-sm text-admin-sub">
          Extract teacher personality DNA from videos — 100% local (Ollama + Whisper).
        </p>
      </div>

      {/* Section A — start new extraction */}
      <AdminCard>
        <SectionTitle>Start New Extraction</SectionTitle>

        <div className="grid gap-5 lg:grid-cols-2">
          {/* Left column */}
          <div className="space-y-4">
            {/* Teacher */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-admin-sub">
                Teacher
              </label>
              {!teachers ? (
                <Skeleton className="h-10 w-full" />
              ) : (
                <select
                  value={teacherId}
                  onChange={(e) => setTeacherId(e.target.value)}
                  className="w-full rounded-lg border border-admin-border bg-admin-bg px-3 py-2.5 text-sm text-admin-txt outline-none focus:border-admin-primary"
                >
                  <option value="">Select a teacher…</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                      {t.has_dna ? "  ✅ has DNA" : "  — no DNA"}
                    </option>
                  ))}
                </select>
              )}
              {teachers && teachers.length === 0 && (
                <p className="mt-1.5 text-xs text-admin-sub">
                  No teachers found.{" "}
                  <Link href="/admin/teachers" className="text-admin-primary hover:underline">
                    Add one first
                  </Link>
                  .
                </p>
              )}
            </div>

            {/* Source toggle */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-admin-sub">
                Video Source
              </label>
              <div className="inline-flex rounded-lg border border-admin-border p-0.5">
                {(["url", "file"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSourceType(s)}
                    className={
                      "rounded-md px-3 py-1.5 text-sm font-medium transition " +
                      (sourceType === s
                        ? "bg-admin-primary text-white"
                        : "text-admin-sub hover:text-admin-txt")
                    }
                  >
                    {s === "url" ? "YouTube URL" : "Upload File"}
                  </button>
                ))}
              </div>

              {sourceType === "url" ? (
                <div className="mt-2">
                  <textarea
                    value={urlText}
                    onChange={(e) => setUrlText(e.target.value)}
                    rows={4}
                    placeholder="https://youtube.com/watch?v=...&#10;One URL per line"
                    className="w-full resize-y rounded-lg border border-admin-border bg-admin-bg px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
                  />
                  <div className="mt-1 text-xs text-admin-sub">
                    {urlList.length} URL{urlList.length === 1 ? "" : "s"} added
                  </div>
                </div>
              ) : (
                <div className="mt-2">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragOver(false);
                      const f = e.dataTransfer.files?.[0];
                      if (f) setFile(f);
                    }}
                    onClick={() => fileInput.current?.click()}
                    className={
                      "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed px-4 py-6 text-center text-sm transition " +
                      (dragOver
                        ? "border-admin-primary bg-admin-primary/10"
                        : "border-admin-border hover:border-admin-primary/50")
                    }
                  >
                    <span className="text-2xl">📁</span>
                    {file ? (
                      <span className="text-admin-txt">{file.name}</span>
                    ) : (
                      <>
                        <span className="text-admin-txt/80">
                          Drag &amp; drop or click to choose
                        </span>
                        <span className="text-xs text-admin-sub">
                          .mp4 .avi .mov .mp3 .wav
                        </span>
                      </>
                    )}
                  </div>
                  <input
                    ref={fileInput}
                    type="file"
                    accept={ACCEPT}
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-admin-sub">
                Ollama Model
              </label>
              {!health ? (
                <Skeleton className="h-24 w-full" />
              ) : modelOptions.length === 0 ? (
                <div className="rounded-lg border border-admin-warning/30 bg-admin-warning/10 px-3 py-2 text-xs text-admin-warning">
                  Ollama is unreachable or has no installed models — start Ollama and pull a
                  model (e.g. <code>ollama pull llama3.1</code>).
                </div>
              ) : (
                <ModelSelector
                  options={modelOptions}
                  value={effectiveModel}
                  onChange={setModel}
                />
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-admin-sub">
                Whisper Model
              </label>
              <ModelSelector
                options={WHISPER_OPTIONS}
                value={whisper}
                onChange={setWhisper}
                columns={2}
              />
              <p className="mt-1 text-xs text-admin-sub">
                Note: the Whisper model is set by the server config (
                <code>DNA_WHISPER_MODEL={health?.whisper_model || "medium"}</code>).
              </p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4">
            <ErrorNote message={error} />
          </div>
        )}
        {notice && (
          <div className="mt-4 rounded-lg border border-admin-success/30 bg-admin-success/10 px-4 py-2.5 text-sm text-admin-success">
            ✅ {notice}
          </div>
        )}

        <button
          onClick={handleStart}
          disabled={!canSubmit}
          className="mt-5 w-full rounded-lg bg-admin-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-admin-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Starting…" : "🧬 Start DNA Extraction"}
        </button>
      </AdminCard>

      {/* Section B — live progress */}
      <div>
        <SectionTitle>Live Extraction Progress</SectionTitle>
        {active.length === 0 ? (
          <AdminCard>
            <div className="py-6 text-center text-sm text-admin-sub">
              No extraction running. Start one above — progress updates every 3 seconds.
            </div>
          </AdminCard>
        ) : (
          <div className="space-y-4">
            {active.map((job) => (
              <ExtractionProgress key={job.job_id} job={job} />
            ))}
          </div>
        )}
      </div>

      {/* Section C — history */}
      <div>
        <SectionTitle>Completed Extractions</SectionTitle>
        <AdminCard padded={false} className="overflow-hidden">
          {!jobs ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ) : historyRows.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-admin-sub">
              No completed extractions yet in this session.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-admin-border text-left text-xs text-admin-sub">
                    <th className="px-4 py-2.5 font-medium">Teacher</th>
                    <th className="px-4 py-2.5 font-medium">Source</th>
                    <th className="px-4 py-2.5 font-medium">Words</th>
                    <th className="px-4 py-2.5 font-medium">Model</th>
                    <th className="px-4 py-2.5 font-medium">Duration</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-admin-border">
                  {historyRows.map((job) => (
                    <HistoryRow key={job.job_id} job={job} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AdminCard>
      </div>
    </div>
  );
}

function HistoryRow({ job }: { job: DnaJob }) {
  const duration =
    job.finished_at && job.started_at
      ? (new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000
      : null;
  return (
    <tr>
      <td className="max-w-[10rem] truncate px-4 py-3 font-medium text-admin-txt">
        {job.teacher_name}
      </td>
      <td className="px-4 py-3 text-admin-sub">{job.source}</td>
      <td className="px-4 py-3 text-admin-sub">{fmtNumber(job.stats.words_transcribed)}</td>
      <td className="px-4 py-3 text-admin-sub">{shortModel(job.model)}</td>
      <td className="px-4 py-3 text-admin-sub">{fmtDuration(duration)}</td>
      <td className="px-4 py-3">
        <Badge tone={job.status === "complete" ? "success" : "error"}>
          {job.status === "complete" ? "✅ Complete" : "🔴 Failed"}
        </Badge>
      </td>
      <td className="px-4 py-3 text-admin-sub">{timeAgo(job.finished_at || job.started_at)}</td>
    </tr>
  );
}
