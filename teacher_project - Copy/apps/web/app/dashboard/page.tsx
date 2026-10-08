"use client";
import { Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { TeacherCard } from "@/components/TeacherCard";
import { Button, Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";
import { levelLabel, loadStudentProfile } from "@/lib/constants";
import type { TeacherProfile } from "@/lib/types";

export default function Dashboard() {
  const [mine, setMine] = useState<TeacherProfile[]>([]);
  const [popular, setPopular] = useState<TeacherProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const profile = typeof window !== "undefined" ? loadStudentProfile() : null;

  useEffect(() => {
    Promise.all([
      api<TeacherProfile[]>("/profiles").catch(() => []),
      api<TeacherProfile[]>("/discover/teachers?limit=6").catch(() => []),
    ]).then(([m, p]) => {
      setMine(m);
      setPopular(p);
      setLoading(false);
    });
  }, []);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            {profile && (
              <p className="text-sm text-muted">
                Learning as <b>{levelLabel(profile.level)}</b>
                {profile.subject ? ` · ${profile.subject}` : ""}
                {profile.learn_ahead ? " · ahead 🚀" : ""} ·{" "}
                <Link href="/onboarding" className="text-indigo-light hover:underline">change</Link>
              </p>
            )}
          </div>
          <Link href="/profiles/new">
            <Button>
              <Plus className="h-4 w-4" /> New teacher
            </Button>
          </Link>
        </div>

        {loading ? (
          <Spinner label="Loading…" />
        ) : (
          <>
            <section className="mb-10">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Your teachers</h2>
              {mine.length === 0 ? (
                <Card className="flex flex-col items-center gap-3 py-10 text-center">
                  <Sparkles className="h-8 w-8 text-indigo-light" />
                  <p className="text-sm text-muted">
                    No teachers yet. Create one from your own material, or learn from a popular teacher below.
                  </p>
                  <Link href="/profiles/new">
                    <Button>Create your first teacher</Button>
                  </Link>
                </Card>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {mine.map((p) => (
                    <TeacherCard key={p.id} profile={p} manage />
                  ))}
                </div>
              )}
            </section>

            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
                  Popular teachers
                </h2>
                <Link href="/discover" className="text-sm text-indigo-light hover:underline">
                  See all
                </Link>
              </div>
              {popular.length === 0 ? (
                <p className="text-sm text-muted">No public teachers yet. Run the seed script to add a demo.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {popular.map((p) => (
                    <TeacherCard key={p.id} profile={p} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </>
  );
}
