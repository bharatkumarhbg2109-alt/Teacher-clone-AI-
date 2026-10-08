"use client";
import { ArrowLeft, BarChart3 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

interface LeaderboardEntry {
  name: string;
  xp: number;
  level: number;
  streak: number;
}

export default function OrgAnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<LeaderboardEntry[]>(`/organizations/${id}/leaderboard`)
      .then(setLeaderboard)
      .catch(() => setLeaderboard([]))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/orgs/${id}`} className="text-muted hover:text-white">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-xl font-semibold">Analytics</h1>
        </div>

        {loading ? (
          <Spinner label="Loading analytics…" />
        ) : (
          <>
            <Card className="mb-6">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <BarChart3 className="h-4 w-4 text-indigo" /> Top Performers
              </div>
              {leaderboard.length === 0 ? (
                <p className="text-sm text-muted">No activity data yet.</p>
              ) : (
                <div className="space-y-2">
                  {leaderboard.map((entry, i) => (
                    <div key={i} className="flex items-center justify-between rounded-lg bg-surface px-3 py-2">
                      <div className="flex items-center gap-3">
                        <span className="w-6 text-center text-xs font-bold text-muted">
                          {i + 1}
                        </span>
                        <div>
                          <div className="text-sm font-medium">{entry.name}</div>
                          <div className="text-xs text-muted">
                            Level {entry.level} · 🔥 {entry.streak} day streak
                          </div>
                        </div>
                      </div>
                      <div className="text-sm font-semibold text-cyan">
                        {entry.xp.toLocaleString()} XP
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card>
              <div className="mb-3 text-sm font-medium">📈 Aggregate Stats</div>
              <p className="text-sm text-muted">
                Detailed per-subject and per-level breakdowns will appear here as the
                institute accumulates learning data.
              </p>
            </Card>
          </>
        )}
      </main>
    </>
  );
}
