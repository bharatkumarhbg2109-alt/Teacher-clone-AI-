"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Input, Label, Textarea, TopNav } from "@/components/ui";
import { api } from "@/lib/api";
import type { TeacherProfile } from "@/lib/types";

export default function NewProfile() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [voice, setVoice] = useState("nova");
  const [visibility, setVisibility] = useState("private");
  const [saving, setSaving] = useState(false);

  async function create() {
    if (name.trim().length < 2) return alert("Name is too short");
    setSaving(true);
    try {
      const p = await api<TeacherProfile>("/profiles", {
        method: "POST",
        body: JSON.stringify({ name, subject, description, tts_voice: voice, visibility }),
      });
      router.push(`/profiles/${p.id}`);
    } catch {
      alert("Failed to create profile. Please try again.");
      setSaving(false);
    }
  }

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-xl px-6 py-10">
        <h1 className="mb-1 text-2xl font-bold">New teacher</h1>
        <p className="mb-6 text-sm text-muted">
          Give it a name, then add material (video, PDF, link, slides…) on the next page.
        </p>
        <Card className="space-y-4">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Physics with Newton" maxLength={200} />
          </div>
          <div>
            <Label>Subject</Label>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Physics" maxLength={100} />
          </div>
          <div>
            <Label>Description (optional)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={2000} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Voice (audio answers)</Label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="w-full rounded-lg border border-borderc bg-surface px-3 py-2 text-sm"
              >
                {["nova", "onyx", "shimmer", "echo", "fable", "alloy"].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <Label>Visibility</Label>
              <select
                value={visibility}
                onChange={(e) => setVisibility(e.target.value)}
                className="w-full rounded-lg border border-borderc bg-surface px-3 py-2 text-sm"
              >
                <option value="private">Private</option>
                <option value="unlisted">Unlisted (link)</option>
                <option value="public">Public (listed)</option>
              </select>
            </div>
          </div>
          <Button onClick={create} loading={saving} className="w-full">Create teacher</Button>
        </Card>
      </main>
    </>
  );
}
