"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  ServiceStatusCard,
  type ServiceStatus,
} from "@/components/dashboard/ServiceStatusCard";
import {
  AdminCard,
  Badge,
  ErrorNote,
  jobPhaseKey,
  PhaseBadge,
  ProgressBar,
  SectionTitle,
  Skeleton,
} from "@/components/dashboard/primitives";
import {
  fmtCompact,
  fmtEta,
  getJobs,
  getLogs,
  getSystem,
  shortModel,
  timeAgo,
  usePolling,
  type DnaJob,
  type DnaSystem,
} from "@/lib/adminApi";

function overallProgress(job: DnaJob): number {
  const vals = Object.values(job.phase_progress);
  if (vals.length === 0) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function LiveClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!now) return <span className="text-admin-sub">—</span>;
  return (
    <span className="tabular-nums text-admin-sub">
      {now.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      })}{" "}
      · {now.toLocaleTimeString(undefined, { hour12: false })}
    </span>
  );
}

export default function OverviewPage() {
  const { data: system, error: sysErr } = usePolling<DnaSystem>(getSystem, 15_000);
  const { data: jobs } = usePolling(getJobs, 3_000);
  const { data: logsResp } = usePolling(() => getLogs(), 5_000);

  const stats = system?.stats;
  const active = jobs?.active ?? [];
  const loading = !system;

  const ollamaUp = !!system?.ollama?.reachable;
  const healthLabel = !system ? "…" : ollamaUp ? "Healthy" : "Degraded";
  const healthIcon = !system ? "⏳" : ollamaUp ? "💚" : "⚠️";
  const healthAccent = ollamaUp ? "success" : "warning";

  const services: ServiceStatus[] = system
    ? [
        {
          name: "🟢 Ollama API",
          online: system.ollama.reachable,
          subtitle: system.ollama.base_url,
          lines: [
            { label: "Models", value: fmtCompact(system.ollama.models?.length) },
            { label: "Default", value: shortModel(system.ollama.default_model) },
          ],
        },
        {
          name: "🎙️ Whisper STT",
          online: system.tools.whisper.available,
          subtitle: system.tools.whisper.engine,
          lines: [{ label: "Model", value: system.tools.whisper.model }],
        },
        {
          name: "🎬 FFmpeg",
          online: system.tools.ffmpeg.available,
          lines: [{ label: "Version", value: system.tools.ffmpeg.version || "—" }],
        },
        {
          name: "⬇️ yt-dlp",
          online: system.tools.yt_dlp.available,
          lines: [{ label: "Version", value: system.tools.yt_dlp.version || "—" }],
        },
        {
          name: "🗄️ Database",
          online: system.database.size_bytes != null,
          subtitle: system.database.type,
          lines: [{ label: "Tables", value: fmtCompact(system.database.tables) }],
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-admin-txt">System Overview</h1>
        <LiveClock />
      </div>

      {sysErr && !system && (
        <ErrorNote
          message={`Cannot reach the API at ${
            process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
          } — is it running? (${sysErr})`}
        />
      )}

      {/* Row 1 — metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon="👨‍🏫"
          label="Total Teachers"
          accent="primary"
          loading={loading}
          value={fmtCompact(stats?.total_teachers)}
          sub={`${fmtCompact(stats?.teachers_with_dna)} with DNA extracted`}
        />
        <MetricCard
          icon="🧬"
          label="DNA Extractions Today"
          accent="success"
          loading={loading}
          value={fmtCompact(stats?.dna_reports_today)}
          sub={`${active.length} in progress`}
        />
        <MetricCard
          icon="🎥"
          label="Videos Processed"
          accent="info"
          loading={loading}
          value={fmtCompact(stats?.media_sources_total)}
          sub="Total transcribed"
        />
        <MetricCard
          icon={healthIcon}
          label="System Health"
          accent={healthAccent}
          loading={loading}
          value={<span className="text-2xl">{healthLabel}</span>}
          sub={ollamaUp ? "All services running" : "Ollama offline"}
        />
      </div>

      {/* Row 2 — active extractions + service status */}
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <SectionTitle
            right={
              <Link href="/admin/dna" className="text-xs text-admin-primary hover:underline">
                DNA Center →
              </Link>
            }
          >
            Active DNA Extractions
          </SectionTitle>
          <AdminCard padded={false} className="overflow-hidden">
            {active.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-admin-sub">
                No active extractions — start one in the{" "}
                <Link href="/admin/dna" className="text-admin-primary hover:underline">
                  DNA Center
                </Link>
                .
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-admin-border text-left text-xs text-admin-sub">
                      <th className="px-4 py-2.5 font-medium">Teacher</th>
                      <th className="px-4 py-2.5 font-medium">Phase</th>
                      <th className="px-4 py-2.5 font-medium">Progress</th>
                      <th className="px-4 py-2.5 font-medium">Model</th>
                      <th className="px-4 py-2.5 font-medium">Started</th>
                      <th className="px-4 py-2.5 font-medium">ETA</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-admin-border">
                    {active.map((job) => {
                      const pct = overallProgress(job);
                      return (
                        <tr key={job.job_id}>
                          <td className="max-w-[10rem] truncate px-4 py-3 font-medium text-admin-txt">
                            {job.teacher_name}
                          </td>
                          <td className="px-4 py-3">
                            <PhaseBadge phaseKey={jobPhaseKey(job)} />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <ProgressBar value={pct} className="w-20" />
                              <span className="tabular-nums text-xs text-admin-sub">
                                {Math.round(pct)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-admin-sub">
                            {shortModel(job.model)}
                          </td>
                          <td className="px-4 py-3 text-admin-sub">
                            {timeAgo(job.started_at)}
                          </td>
                          <td className="px-4 py-3 text-admin-sub">
                            {fmtEta(job.eta_seconds)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </AdminCard>
        </div>

        <div className="lg:col-span-2">
          <SectionTitle>Service Status</SectionTitle>
          <ServiceStatusCard services={services} loading={loading} />
        </div>
      </div>

      {/* Row 3 — recent activity */}
      <div>
        <SectionTitle
          right={
            <Link href="/admin/logs" className="text-xs text-admin-primary hover:underline">
              View all logs →
            </Link>
          }
        >
          Recent Activity
        </SectionTitle>
        <AdminCard padded={false}>
          {!logsResp ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ) : logsResp.logs.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-admin-sub">
              No activity yet. Pipeline events will appear here.
            </div>
          ) : (
            <ul className="divide-y divide-admin-border">
              {logsResp.logs
                .slice(-10)
                .reverse()
                .map((log) => (
                  <li
                    key={log.seq}
                    className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm"
                  >
                    <span className="min-w-0 truncate text-admin-txt/90">
                      {log.message}
                    </span>
                    <span className="shrink-0 text-xs text-admin-sub">
                      {timeAgo(log.ts)}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </AdminCard>
      </div>
    </div>
  );
}
