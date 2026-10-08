"use client";
import { useEffect, useState } from "react";
import { Badge, Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

const ALL_BADGES: Record<string, { name: string; icon: string; hint: string }> = {
  first_lesson: { name: "First Step", icon: "🎓", hint: "Complete 1 session" },
  curious_mind: { name: "Curious Mind", icon: "🧠", hint: "10 sessions" },
  quiz_ace: { name: "Quiz Ace", icon: "⭐", hint: "3 perfect quizzes" },
  week_warrior: { name: "Week Warrior", icon: "🔥", hint: "7-day streak" },
  month_master: { name: "Month Master", icon: "🏆", hint: "30-day streak" },
  deep_diver: { name: "Deep Diver", icon: "🤿", hint: "50 sessions" },
  knowledge_base: { name: "Knowledge Base", icon: "📚", hint: "10 sources" },
};

export default function Progress() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => {
    api("/users/me/stats").then(setStats).catch(() => setStats({ badges: [] }));
  }, []);

  if (!stats) return (<><TopNav /><main className="p-8"><Spinner label="Loading progress…" /></main></>);

  const earned = new Set((stats.badges || []).map((b: any) => b.badge_id));
  const inLevel = (stats.xp_total || 0) % 1000;

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="mb-6 text-2xl font-bold">Your progress</h1>

        <Card className="mb-6">
          <div className="mb-2 flex justify-between text-sm">
            <span className="font-medium">Level {stats.level}</span>
            <span className="text-muted">{inLevel} / 1000 XP</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface">
            <div className="h-full rounded-full bg-gradient-to-r from-indigo to-cyan" style={{ width: `${(inLevel / 1000) * 100}%` }} />
          </div>
          <div className="mt-2 flex justify-between text-xs text-muted">
            <span>{(stats.xp_total || 0).toLocaleString()} total XP</span>
            <span>🔥 {stats.streak_days || 0}-day streak</span>
          </div>
        </Card>

        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            ["Sessions", stats.sessions_completed],
            ["Quizzes", stats.quizzes_completed],
            ["Perfect", stats.perfect_quizzes],
            ["Sources", stats.sources_processed],
          ].map(([label, val]) => (
            <Card key={label as string} className="text-center">
              <div className="text-2xl font-bold text-indigo-light">{val ?? 0}</div>
              <div className="text-xs text-muted">{label as string}</div>
            </Card>
          ))}
        </div>

        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Badges</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(ALL_BADGES).map(([id, b]) => {
            const has = earned.has(id);
            return (
              <div
                key={id}
                className={`rounded-xl border p-4 text-center ${has ? "border-indigo bg-indigo/10" : "border-borderc opacity-50"}`}
              >
                <div className="text-3xl">{b.icon}</div>
                <div className="mt-1 text-sm font-medium">{b.name}</div>
                <div className="text-[11px] text-muted">{has ? "Earned" : b.hint}</div>
              </div>
            );
          })}
        </div>
      </main>
    </>
  );
}
