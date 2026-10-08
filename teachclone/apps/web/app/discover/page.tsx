"use client";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { TeacherCard } from "@/components/TeacherCard";
import { Input, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";
import type { TeacherProfile } from "@/lib/types";

export default function Discover() {
  const [teachers, setTeachers] = useState<TeacherProfile[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(query = "") {
    setLoading(true);
    const rows = await api<TeacherProfile[]>(
      `/discover/teachers?sort=most_used&limit=30${query ? `&q=${encodeURIComponent(query)}` : ""}`
    ).catch(() => []);
    setTeachers(rows);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="mb-1 text-2xl font-bold">Popular teachers</h1>
        <p className="mb-6 text-sm text-muted">
          No material of your own? Learn from the most-used teachers on TeachClone.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            load(q);
          }}
          className="mb-6 flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name or subject…"
              className="pl-9"
            />
          </div>
        </form>

        {loading ? (
          <Spinner label="Loading teachers…" />
        ) : teachers.length === 0 ? (
          <p className="text-sm text-muted">No public teachers found.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {teachers.map((p) => (
              <TeacherCard key={p.id} profile={p} />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
