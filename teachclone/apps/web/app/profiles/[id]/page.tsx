"use client";
import { BarChart3, CheckCircle2, Link2, Loader2, Play, Share2, Upload, XCircle } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, Input, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";
import { startSession } from "@/lib/actions";
import { uploadFile } from "@/lib/upload";
import type { MediaSource, TeacherProfile } from "@/lib/types";

const ACCEPT =
  "video/*,audio/*,application/pdf,.docx,.pptx,.txt,.md,image/*";

function StatusBadge({ s }: { s: string }) {
  if (s === "completed")
    return <Badge className="border-emerald/40 text-emerald"><CheckCircle2 className="mr-1 h-3 w-3" />Ready</Badge>;
  if (s === "failed")
    return <Badge className="border-rose/40 text-rose"><XCircle className="mr-1 h-3 w-3" />Failed</Badge>;
  return <Badge className="text-amber"><Loader2 className="mr-1 h-3 w-3 animate-spin" />Processing</Badge>;
}

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [media, setMedia] = useState<MediaSource[]>([]);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [share, setShare] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [p, m] = await Promise.all([
      api<TeacherProfile>(`/profiles/${id}`),
      api<MediaSource[]>(`/media/profile/${id}`).catch(() => []),
    ]);
    setProfile(p);
    setMedia(m);
    if (p.share_enabled && p.share_token)
      setShare(`${window.location.origin}/t/${p.share_token}`);
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const anyPending = media.some((m) => m.status === "pending" || m.status === "processing");
    if (!anyPending) return;
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [media, refresh]);

  async function addYouTube() {
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api("/media/youtube", {
        method: "POST",
        body: JSON.stringify({ teacher_profile_id: id, youtube_url: url }),
      });
      setUrl("");
      await refresh();
    } catch {
      alert("Failed to ingest YouTube video. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadPct(0);
    try {
      await uploadFile(file, id, setUploadPct);
      await refresh();
    } catch {
      alert("Upload failed. Please try again.");
    } finally {
      setUploadPct(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function makeShare(mode: string) {
    const res = await api<{ share_url: string }>(`/profiles/${id}/share`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    setShare(res.share_url);
    navigator.clipboard?.writeText(res.share_url).catch(() => {});
  }

  async function learn() {
    setBusy(true);
    const sid = await startSession(id).catch(() => {
      alert("Failed to start session. Please try again.");
      return null;
    });
    if (sid) router.push(`/chat/${sid}`);
    setBusy(false);
  }

  if (!profile) return (<><TopNav /><main className="p-8"><Spinner label="Loading…" /></main></>);
  const ready = media.some((m) => m.status === "completed");

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">{profile.name}</h1>
            <p className="text-sm text-muted">
              {profile.subject} · {profile.total_sources} sources · {profile.unique_learners} learners
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.push(`/profiles/${id}/analytics`)}>
              <BarChart3 className="h-4 w-4" /> Analytics
            </Button>
            <Button variant="outline" onClick={() => makeShare(profile.share_mode || "clone")}>
              <Share2 className="h-4 w-4" /> Share
            </Button>
            <Button loading={busy} onClick={learn}>
              <Play className="h-4 w-4" /> Start learning
            </Button>
          </div>
        </div>

        {share && (
          <Card className="mb-6 flex items-center gap-2">
            <Link2 className="h-4 w-4 text-indigo-light" />
            <input readOnly value={share} className="flex-1 bg-transparent text-sm text-slate-300 outline-none" />
            <Badge>{profile.share_mode === "view" ? "view" : "clone"}</Badge>
            <Button variant="ghost" onClick={() => navigator.clipboard?.writeText(share)}>Copy</Button>
          </Card>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <h2 className="mb-3 font-semibold">Add content</h2>
            <p className="mb-2 text-xs text-muted">Paste a YouTube / video link</p>
            <div className="mb-4 flex gap-2">
              <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://youtube.com/watch?v=…" maxLength={500} />
              <Button onClick={addYouTube} loading={busy}>Add</Button>
            </div>
            <p className="mb-2 text-xs text-muted">…or upload a file (video, audio, PDF, slides, docs, images — any size)</p>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploadPct !== null}
              className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-borderc py-8 text-sm text-muted hover:border-indigo-light"
            >
              {uploadPct !== null ? (
                <>
                  <Loader2 className="h-6 w-6 animate-spin" />
                  Uploading… {Math.round(uploadPct)}%
                </>
              ) : (
                <>
                  <Upload className="h-6 w-6" />
                  Click to choose a file
                </>
              )}
            </button>
            <input ref={fileRef} type="file" accept={ACCEPT} className="hidden" onChange={onFile} />
          </Card>

          <Card>
            <h2 className="mb-3 font-semibold">Content library</h2>
            {media.length === 0 ? (
              <p className="text-sm text-muted">No content yet. Add a link or upload a file.</p>
            ) : (
              <ul className="space-y-2">
                {media.map((m) => (
                  <li key={m.id} className="flex items-center justify-between rounded-lg border border-borderc bg-surface px-3 py-2 text-sm">
                    <span className="truncate">{m.file_name || m.original_url || m.source_type}</span>
                    <StatusBadge s={m.status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {profile.style_profile && (
          <Card className="mt-6">
            <h2 className="mb-3 font-semibold">Teaching style</h2>
            <div className="flex flex-wrap gap-2">
              <Badge>Tone: {profile.style_profile.tone_type}</Badge>
              <Badge>Vocabulary: {profile.style_profile.vocabulary_level}</Badge>
              <Badge>Pattern: {profile.style_profile.explanation_pattern}</Badge>
              <Badge>Pacing: {profile.style_profile.pacing}</Badge>
            </div>
            {profile.style_profile.raw_analysis && (
              <p className="mt-3 text-sm text-muted">{profile.style_profile.raw_analysis}</p>
            )}
          </Card>
        )}

        {!ready && media.length > 0 && (
          <p className="mt-6 text-center text-xs text-muted">
            Processing your content… you can start learning once at least one source is ready.
          </p>
        )}
      </main>
    </>
  );
}
