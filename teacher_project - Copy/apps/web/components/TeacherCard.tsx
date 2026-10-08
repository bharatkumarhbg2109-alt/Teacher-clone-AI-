"use client";
import { ArrowRight, Users, Video } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { startSession } from "@/lib/actions";
import type { TeacherProfile } from "@/lib/types";

export function TeacherCard({ profile, manage }: { profile: TeacherProfile; manage?: boolean }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function learn() {
    setLoading(true);
    try {
      const id = await startSession(profile.id);
      if (id) router.push(`/chat/${id}`);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  }

  const style = profile.style_profile;
  return (
    <Card className="flex flex-col">
      <div className="mb-2 flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-tight">{profile.name}</h3>
        {profile.visibility === "public" && <Badge>Public</Badge>}
      </div>
      {profile.description && <p className="mb-3 line-clamp-2 text-xs text-muted">{profile.description}</p>}
      <div className="mb-3 flex flex-wrap gap-1">
        {profile.subject && <Badge>{profile.subject}</Badge>}
        {style?.tone_type && <Badge>{style.tone_type}</Badge>}
        {style?.vocabulary_level && <Badge>{style.vocabulary_level}</Badge>}
      </div>
      <div className="mb-4 flex gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <Video className="h-3 w-3" /> {profile.total_sources} sources
        </span>
        <span className="flex items-center gap-1">
          <Users className="h-3 w-3" /> {profile.unique_learners} learners
        </span>
      </div>
      <div className="mt-auto flex gap-2">
        {manage && (
          <Button variant="outline" className="flex-1" onClick={() => router.push(`/profiles/${profile.id}`)}>
            Manage
          </Button>
        )}
        <Button className="flex-1" loading={loading} onClick={learn}>
          Learn <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </Card>
  );
}
