"use client";
import { GitFork, Play } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";
import { startSession } from "@/lib/actions";
import type { TeacherProfile } from "@/lib/types";

export default function SharedTeacher() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<TeacherProfile>(`/t/${token}`)
      .then(setProfile)
      .catch(() => setError("Share link not found or has expired."));
  }, [token]);

  async function open() {
    setBusy(true);
    try {
      const res = await api<{ teacher_profile_id: string; mode: string; cloning: boolean }>(
        `/t/${token}/start`,
        { method: "POST" }
      );
      const sid = await startSession(res.teacher_profile_id);
      if (sid) router.push(`/chat/${sid}`);
    } catch {
      alert("Failed to start session. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (error)
    return (
      <>
        <TopNav />
        <main className="mx-auto max-w-md px-6 py-20 text-center">
          <p className="text-rose">{error}</p>
        </main>
      </>
    );
  if (!profile) return (<><TopNav /><main className="p-8"><Spinner label="Opening shared teacher…" /></main></>);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-md px-6 py-16">
        <Card className="text-center">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo to-cyan text-2xl">
            🧠
          </div>
          <div className="mb-1 text-xs uppercase tracking-wide text-muted">A friend shared a teacher</div>
          <h1 className="text-xl font-bold">{profile.name}</h1>
          {profile.description && <p className="mt-2 text-sm text-muted">{profile.description}</p>}
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {profile.subject && <Badge>{profile.subject}</Badge>}
            <Badge>{profile.total_sources} sources</Badge>
            <Badge className="border-cyan/30 text-cyan">
              {profile.share_mode === "view" ? "learn together" : "your own copy"}
            </Badge>
          </div>
          <Button onClick={open} loading={busy} className="mt-6 w-full">
            {profile.share_mode === "view" ? <Play className="h-4 w-4" /> : <GitFork className="h-4 w-4" />}
            {profile.share_mode === "view" ? "Start learning" : "Get my copy & learn"}
          </Button>
          <p className="mt-3 text-xs text-muted">This teacher keeps its full memory — knowledge, style and voice.</p>
        </Card>
      </main>
    </>
  );
}
