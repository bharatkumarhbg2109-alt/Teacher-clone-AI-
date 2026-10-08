"use client";
import { ArrowLeft, Send, UserPlus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, Input, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

interface Member {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

export default function OrgMembersPage() {
  const { id } = useParams<{ id: string }>();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("student");
  const [inviting, setInviting] = useState(false);

  useEffect(() => {
    api<Member[]>(`/organizations/${id}/members`)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoading(false));
  }, [id]);

  async function invite() {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await api(`/organizations/${id}/members/invite`, {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      setInviteEmail("");
    } catch {
      alert("Failed to send invitation.");
    } finally {
      setInviting(false);
    }
  }

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/orgs/${id}`} className="text-muted hover:text-white">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-xl font-semibold">Members</h1>
        </div>

        {/* Invite form */}
        <Card className="mb-6">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <UserPlus className="h-4 w-4" /> Invite Member
          </div>
          <div className="flex gap-3">
            <Input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="email@example.com"
              type="email"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="rounded-lg border border-borderc bg-surface px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
              <option value="admin">Admin</option>
            </select>
            <Button onClick={invite} loading={inviting}>
              <Send className="h-4 w-4" /> Invite
            </Button>
          </div>
        </Card>

        {/* Member list */}
        {loading ? (
          <Spinner label="Loading members…" />
        ) : members.length === 0 ? (
          <Card className="text-center text-muted">
            <p>No members yet. Send an invitation above.</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {members.map((m) => (
              <Card key={m.user_id}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-sm">{m.name || "Unknown"}</div>
                    <div className="text-xs text-muted">{m.email}</div>
                  </div>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
                    {m.role}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
