"use client";
import {
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  FileText,
  MessageSquare,
  TrendingUp,
  Users,
  Video,
  Mic,
  File,
  Image,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

/* ── types ─────────────────────────────────────────────────────────────── */

interface AnalyticsData {
  overview: {
    total_sessions: number;
    unique_learners: number;
    total_messages: number;
    avg_message_length: number;
  };
  quiz_stats: {
    total_quizzes: number;
    avg_score: number;
    completion_rate: number;
    quizzes_by_kind: Record<string, number>;
  };
  activity: { date: string; sessions: number }[];
  content: {
    total_sources: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
  };
  student_levels: { level: string; count: number }[];
  top_concepts: { concept: string; count: number }[];
}

/* ── helpers ───────────────────────────────────────────────────────────── */

const LEVEL_LABELS: Record<string, string> = {
  class_6_8: "Class 6–8",
  class_9_10: "Class 9–10",
  class_11_12: "Class 11–12",
  undergrad: "Undergraduate",
  postgrad: "Postgraduate",
  professional: "Professional",
  intermediate: "Intermediate",
  beginner: "Beginner",
  advanced: "Advanced",
  unknown: "Unknown",
};

const SOURCE_ICONS: Record<string, typeof Video> = {
  youtube_url: Video,
  video_upload: Video,
  audio_upload: Mic,
  pdf_upload: FileText,
  doc_upload: File,
  pptx_upload: File,
  image_upload: Image,
};

function levelLabel(key: string): string {
  return LEVEL_LABELS[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: typeof Users;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <Card className="flex items-start gap-3">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
          color || "bg-indigo/20 text-indigo-light"
        }`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-xs text-muted">{label}</p>
        {sub && <p className="mt-0.5 text-[10px] text-muted/70">{sub}</p>}
      </div>
    </Card>
  );
}

function BarChart({
  data,
  maxVal,
  labelKey,
  valueKey,
  color,
}: {
  data: { label: string; value: number }[];
  maxVal: number;
  labelKey: string;
  valueKey: string;
  color?: string;
}) {
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate text-xs text-muted">{d.label}</span>
          <div className="flex-1 overflow-hidden rounded-full bg-white/5">
            <div
              className={`h-2 rounded-full ${color || "bg-indigo"}`}
              style={{ width: `${maxVal > 0 ? (d.value / maxVal) * 100 : 0}%` }}
            />
          </div>
          <span className="w-10 text-right text-xs font-medium">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

function MiniBarChart({ data }: { data: { date: string; sessions: number }[] }) {
  const maxVal = Math.max(...data.map((d) => d.sessions), 1);
  return (
    <div className="flex items-end gap-1" style={{ height: 80 }}>
      {data.map((d, i) => (
        <div key={i} className="group relative flex flex-1 flex-col items-center">
          <div
            className="w-full rounded-t bg-indigo transition-all hover:bg-indigo-light"
            style={{
              height: `${(d.sessions / maxVal) * 100}%`,
              minHeight: d.sessions > 0 ? 4 : 0,
            }}
          />
          <span className="mt-1 hidden text-[9px] text-muted group-hover:block">
            {d.sessions}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── page ──────────────────────────────────────────────────────────────── */

export default function AnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const d = await api<AnalyticsData>(`/profiles/${id}/analytics`);
      setData(d);
      setError(null);
    } catch (e: any) {
      setError("Failed to load analytics. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <>
        <TopNav />
        <main className="mx-auto max-w-6xl px-6 py-8">
          <Spinner label="Loading analytics…" />
        </main>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopNav />
        <main className="mx-auto max-w-6xl px-6 py-8">
          <Card className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-rose">{error}</p>
            <Button variant="outline" onClick={load}>
              Retry
            </Button>
          </Card>
        </main>
      </>
    );
  }

  if (!data) return null;

  const { overview, quiz_stats, activity, content, student_levels, top_concepts } = data;

  const sourceEntries = Object.entries(content.by_type)
    .map(([type, count]) => ({ label: type.replace(/_/g, " "), value: count }))
    .sort((a, b) => b.value - a.value);

  const statusEntries = Object.entries(content.by_status)
    .map(([status, count]) => ({ label: status, value: count }))
    .sort((a, b) => b.value - a.value);

  const levelEntries = student_levels.map((l) => ({
    label: levelLabel(l.level),
    value: l.count,
  }));

  const conceptEntries = top_concepts.map((c) => ({
    label: c.concept,
    value: c.count,
  }));

  const maxSource = Math.max(...sourceEntries.map((e) => e.value), 1);
  const maxConcept = Math.max(...conceptEntries.map((e) => e.value), 1);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/profiles/${id}`}>
            <Button variant="ghost" className="px-2">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Analytics</h1>
            <p className="text-sm text-muted">Engagement metrics for this teacher profile</p>
          </div>
        </div>

        {/* Overview stat cards */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={Users} label="Unique learners" value={overview.unique_learners} color="bg-cyan/20 text-cyan" />
          <StatCard icon={BarChart3} label="Total sessions" value={overview.total_sessions} color="bg-indigo/20 text-indigo-light" />
          <StatCard icon={MessageSquare} label="Messages sent" value={overview.total_messages.toLocaleString()} sub={overview.avg_message_length > 0 ? `~${Math.round(overview.avg_message_length)} chars avg` : undefined} color="bg-emerald/20 text-emerald" />
          <StatCard icon={BookOpen} label="Quizzes taken" value={quiz_stats.total_quizzes} sub={quiz_stats.avg_score > 0 ? `${quiz_stats.avg_score}% avg score` : undefined} color="bg-amber/20 text-amber" />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Session activity (last 30 days) */}
          {activity.length > 0 && (
            <Card className="lg:col-span-2">
              <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
                <TrendingUp className="h-4 w-4 text-indigo-light" />
                Session activity (last 30 days)
              </h2>
              <p className="mb-4 text-xs text-muted">
                {activity.reduce((sum, a) => sum + a.sessions, 0)} total sessions
              </p>
              <MiniBarChart data={activity} />
              <div className="mt-2 flex justify-between text-[10px] text-muted/60">
                <span>{activity[0]?.date}</span>
                <span>{activity[activity.length - 1]?.date}</span>
              </div>
            </Card>
          )}

          {/* Quiz performance */}
          <Card>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <CheckCircle2 className="h-4 w-4 text-emerald" />
              Quiz performance
            </h2>
            <div className="mb-4 grid grid-cols-2 gap-4">
              <div>
                <p className="text-2xl font-bold">{quiz_stats.avg_score}%</p>
                <p className="text-xs text-muted">Average score</p>
              </div>
              <div>
                <p className="text-2xl font-bold">{quiz_stats.completion_rate}%</p>
                <p className="text-xs text-muted">Completion rate</p>
              </div>
            </div>
            {Object.keys(quiz_stats.quizzes_by_kind).length > 0 && (
              <div>
                <p className="mb-2 text-xs text-muted">By type</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(quiz_stats.quizzes_by_kind).map(([kind, count]) => (
                    <Badge key={kind}>
                      {kind}: {count}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* Content breakdown */}
          <Card>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <FileText className="h-4 w-4 text-cyan" />
              Content sources
            </h2>
            {sourceEntries.length > 0 ? (
              <>
                <div className="mb-4 grid grid-cols-2 gap-3">
                  {Object.entries(content.by_status).map(([status, count]) => (
                    <div key={status} className="flex items-center gap-2">
                      <div
                        className={`h-2 w-2 rounded-full ${
                          status === "completed"
                            ? "bg-emerald"
                            : status === "failed"
                            ? "bg-rose"
                            : "bg-amber"
                        }`}
                      />
                      <span className="text-xs capitalize text-muted">{status}</span>
                      <span className="text-xs font-medium">{count}</span>
                    </div>
                  ))}
                </div>
                <p className="mb-2 text-xs text-muted">By source type</p>
                <BarChart
                  data={sourceEntries}
                  maxVal={maxSource}
                  labelKey="label"
                  valueKey="value"
                  color="bg-cyan"
                />
              </>
            ) : (
              <p className="text-sm text-muted">No content uploaded yet</p>
            )}
          </Card>

          {/* Student level distribution */}
          {levelEntries.length > 0 && (
            <Card>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <Brain className="h-4 w-4 text-amber" />
                Student levels
              </h2>
              <BarChart
                data={levelEntries}
                maxVal={Math.max(...levelEntries.map((e) => e.value), 1)}
                labelKey="label"
                valueKey="value"
                color="bg-amber"
              />
            </Card>
          )}

          {/* Top concepts */}
          {conceptEntries.length > 0 && (
            <Card>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <BarChart3 className="h-4 w-4 text-indigo-light" />
                Top concepts tested
              </h2>
              <BarChart
                data={conceptEntries}
                maxVal={maxConcept}
                labelKey="label"
                valueKey="value"
                color="bg-indigo"
              />
            </Card>
          )}
        </div>
      </main>
    </>
  );
}
