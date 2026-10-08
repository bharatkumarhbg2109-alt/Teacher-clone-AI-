"use client";
import { useEffect, useState } from "react";
import {
  AdminCard,
  Badge,
  ErrorNote,
  ProgressBar,
  SectionTitle,
  Skeleton,
  StatusDot,
} from "@/components/dashboard/primitives";
import {
  clearLogs,
  fmtBytes,
  getSystem,
  shortModel,
  usePolling,
  type DnaSystem,
} from "@/lib/adminApi";

export default function SystemPage() {
  const { data: system, error, loading, refresh } = usePolling<DnaSystem>(
    getSystem,
    30_000
  );
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (system) setLastChecked(new Date());
  }, [system]);

  // Re-render the "last checked" label every second.
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const secsAgo = lastChecked
    ? Math.floor((Date.now() - lastChecked.getTime()) / 1000)
    : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-admin-txt">⚙️ System Health</h1>
        <div className="flex items-center gap-3 text-xs text-admin-sub">
          <span suppressHydrationWarning>
            {secsAgo == null ? "checking…" : `Last checked ${secsAgo}s ago`}
          </span>
          <button
            onClick={refresh}
            className="rounded-lg border border-admin-border px-3 py-1.5 text-admin-txt hover:border-admin-primary/50"
          >
            🔄 Refresh Now
          </button>
        </div>
      </div>

      {error && !system && <ErrorNote message={error} onRetry={refresh} />}

      {loading && !system ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <AdminCard key={i}>
              <Skeleton className="h-6 w-40" />
              <Skeleton className="mt-3 h-20 w-full" />
            </AdminCard>
          ))}
        </div>
      ) : system ? (
        <>
          <SectionTitle>Services</SectionTitle>
          <div className="grid gap-4 md:grid-cols-2">
            <OllamaCard system={system} />
            <WhisperCard system={system} />
            <ToolCard
              icon="🎬"
              name="FFmpeg"
              online={system.tools.ffmpeg.available}
              version={system.tools.ffmpeg.version}
              hint="Audio extraction from video"
            />
            <ToolCard
              icon="⬇️"
              name="yt-dlp"
              online={system.tools.yt_dlp.available}
              version={system.tools.yt_dlp.version}
              hint="YouTube video download"
            />
            <DatabaseCard system={system} />
            <PullModelCard />
          </div>

          <SectionTitle>Resource Usage</SectionTitle>
          <ResourceCard system={system} />

          <SectionTitle>Quick Actions</SectionTitle>
          <QuickActions onRefresh={refresh} />
        </>
      ) : null}
    </div>
  );
}

function ServiceHead({
  icon,
  name,
  online,
}: {
  icon: string;
  name: string;
  online: boolean;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex items-center gap-2 font-semibold text-admin-txt">
        <span>{icon}</span> {name}
      </div>
      <span className="flex items-center gap-2 text-xs">
        <StatusDot tone={online ? "success" : "error"} pulse={online} />
        <span className={online ? "text-admin-success" : "text-admin-error"}>
          {online ? "ONLINE" : "OFFLINE"}
        </span>
      </span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-admin-sub">{label}</span>
      <span className="truncate text-admin-txt/90">{value}</span>
    </div>
  );
}

function OllamaCard({ system }: { system: DnaSystem }) {
  const o = system.ollama;
  return (
    <AdminCard>
      <ServiceHead icon="🧠" name="Ollama" online={o.reachable} />
      <div className="space-y-1.5">
        <Row label="URL" value={o.base_url} />
        <Row label="Default model" value={shortModel(o.default_model)} />
        <Row label="Fallback" value={shortModel(o.fallback_model)} />
      </div>
      <div className="mt-3">
        <div className="mb-1.5 text-xs font-medium text-admin-sub">
          Installed Models ({o.models?.length ?? 0})
        </div>
        {o.reachable ? (
          o.models && o.models.length > 0 ? (
            <div className="space-y-1">
              {o.models.map((m) => {
                const oom = m.toLowerCase().includes("deepseek");
                return (
                  <div
                    key={m}
                    className="flex items-center justify-between rounded-md border border-admin-border bg-admin-bg/40 px-2.5 py-1.5 text-xs"
                  >
                    <span className="truncate text-admin-txt/90">{m}</span>
                    <Badge tone={oom ? "warning" : "success"}>
                      {oom ? "⚠️ may OOM" : "✅ Ready"}
                    </Badge>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-xs text-admin-sub">No models installed.</div>
          )
        ) : (
          <div className="text-xs text-admin-error">
            {o.error || "Ollama is not reachable."}
          </div>
        )}
      </div>
    </AdminCard>
  );
}

function WhisperCard({ system }: { system: DnaSystem }) {
  const w = system.tools.whisper;
  const sizes: Record<string, string> = {
    tiny: "74 MB",
    small: "244 MB",
    medium: "769 MB",
    large: "1.5 GB",
  };
  return (
    <AdminCard>
      <ServiceHead icon="🎙️" name="Whisper STT" online={w.available} />
      <div className="space-y-1.5">
        <Row label="Engine" value={w.engine} />
        <Row label="Type" value="offline (local)" />
      </div>
      <div className="mt-3 space-y-1">
        {Object.entries(sizes).map(([name, size]) => {
          const active = name === w.model;
          return (
            <div
              key={name}
              className="flex items-center justify-between rounded-md border border-admin-border bg-admin-bg/40 px-2.5 py-1.5 text-xs"
            >
              <span className="text-admin-txt/90">
                {name} <span className="text-admin-sub">({size})</span>
              </span>
              {active ? (
                <Badge tone="primary">← Active</Badge>
              ) : (
                <span className="text-admin-sub">available</span>
              )}
            </div>
          );
        })}
      </div>
    </AdminCard>
  );
}

function ToolCard({
  icon,
  name,
  online,
  version,
  hint,
}: {
  icon: string;
  name: string;
  online: boolean;
  version: string | null;
  hint: string;
}) {
  return (
    <AdminCard>
      <ServiceHead icon={icon} name={name} online={online} />
      <div className="space-y-1.5">
        <Row label="Version" value={version || "—"} />
        <Row label="Purpose" value={hint} />
        <Row
          label="Status"
          value={
            online ? (
              <span className="text-admin-success">Available</span>
            ) : (
              <span className="text-admin-error">Not found on PATH</span>
            )
          }
        />
      </div>
    </AdminCard>
  );
}

function DatabaseCard({ system }: { system: DnaSystem }) {
  const db = system.database;
  return (
    <AdminCard>
      <ServiceHead icon="🗄️" name="Database" online={db.size_bytes != null} />
      <div className="space-y-1.5">
        <Row label="Type" value={db.type} />
        <Row label="File" value={db.file || "—"} />
        <Row label="Size" value={fmtBytes(db.size_bytes)} />
      </div>
      <div className="mt-3">
        <div className="mb-1.5 text-xs font-medium text-admin-sub">Table Row Counts</div>
        <div className="space-y-1">
          {Object.entries(db.row_counts).map(([table, count]) => (
            <div key={table} className="flex justify-between text-xs">
              <span className="text-admin-sub">{table}</span>
              <span className="tabular-nums text-admin-txt/90">{count}</span>
            </div>
          ))}
          {Object.keys(db.row_counts).length === 0 && (
            <div className="text-xs text-admin-sub">No table data.</div>
          )}
        </div>
      </div>
    </AdminCard>
  );
}

function PullModelCard() {
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const cmd = `ollama pull ${name.trim() || "<model>"}`;
  return (
    <AdminCard>
      <div className="mb-3 flex items-center gap-2 font-semibold text-admin-txt">
        <span>⬇️</span> Pull New Model
      </div>
      <p className="mb-3 text-xs text-admin-sub">
        Model pulls run on the server host. Enter a name to get the command to run in the
        server terminal.
      </p>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="llama3.1"
        className="w-full rounded-lg border border-admin-border bg-admin-bg px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
      />
      <div className="mt-2 flex items-center gap-2">
        <code className="flex-1 truncate rounded-md bg-black/50 px-2.5 py-1.5 font-mono text-xs text-admin-success">
          {cmd}
        </code>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(cmd).then(
              () => {
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              },
              () => {}
            );
          }}
          className="rounded-lg border border-admin-border px-2.5 py-1.5 text-xs text-admin-sub hover:text-admin-txt"
        >
          {copied ? "✅" : "📋"}
        </button>
      </div>
    </AdminCard>
  );
}

function ResourceCard({ system }: { system: DnaSystem }) {
  const mem = system.memory;
  const disk = system.disk;
  return (
    <AdminCard>
      {mem.available ? (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-admin-sub">RAM Usage</span>
            <span className="text-admin-txt/90">
              {fmtBytes(mem.system_used_bytes)} / {fmtBytes(mem.system_total_bytes)} (
              {Math.round(mem.system_percent)}%)
            </span>
          </div>
          <ProgressBar
            value={mem.system_percent}
            tone={mem.system_percent > 90 ? "error" : mem.system_percent > 75 ? "warning" : "success"}
          />
          <div className="mt-1 text-xs text-admin-sub">
            API process: {fmtBytes(mem.process_rss_bytes)}
          </div>
        </div>
      ) : (
        <div className="mb-4 text-sm text-admin-sub">
          RAM metrics unavailable —{" "}
          <code className="text-admin-txt/80">pip install psutil</code> on the server to
          enable.
        </div>
      )}

      {disk.available ? (
        <div>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-admin-sub">Disk Usage</span>
            <span className="text-admin-txt/90">
              {fmtBytes(disk.used_bytes)} / {fmtBytes(disk.total_bytes)}
            </span>
          </div>
          <ProgressBar
            value={(disk.used_bytes / disk.total_bytes) * 100}
            tone="info"
          />
        </div>
      ) : (
        <div className="text-sm text-admin-sub">Disk metrics unavailable.</div>
      )}
    </AdminCard>
  );
}

function QuickActions({ onRefresh }: { onRefresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function doClearLogs() {
    setBusy(true);
    setMsg(null);
    try {
      await clearLogs();
      setMsg("Log buffer cleared.");
    } catch (e: any) {
      setMsg(`⚠️ ${e?.message || "Failed"}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminCard>
      <div className="flex flex-wrap gap-3">
        <button
          onClick={onRefresh}
          className="rounded-lg border border-admin-border px-4 py-2 text-sm text-admin-txt hover:border-admin-primary/50"
        >
          🔄 Refresh Health
        </button>
        <button
          onClick={doClearLogs}
          disabled={busy}
          className="rounded-lg border border-admin-border px-4 py-2 text-sm text-admin-txt hover:border-admin-primary/50 disabled:opacity-50"
        >
          🧹 Clear Log Buffer
        </button>
      </div>
      <p className="mt-3 text-xs text-admin-sub">
        Note: temp-file cleanup, database backup and API restart are intentionally not
        exposed over HTTP — run them from the server host for safety.
      </p>
      {msg && <div className="mt-2 text-xs text-admin-txt/80">{msg}</div>}
    </AdminCard>
  );
}
