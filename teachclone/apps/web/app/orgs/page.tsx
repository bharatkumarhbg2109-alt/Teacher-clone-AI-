"use client";
import { Building2, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

interface Org {
  id: string;
  name: string;
  slug: string;
  members: number;
}

export default function OrgsPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");

  useEffect(() => {
    api<Org[]>("/organizations")
      .then(setOrgs)
      .catch(() => setOrgs([]))
      .finally(() => setLoading(false));
  }, []);

  async function createOrg() {
    if (!newName.trim() || !newSlug.trim()) return;
    try {
      const result = await api<{ id: string; slug: string; name: string }>(
        "/organizations",
        { method: "POST", body: JSON.stringify({ name: newName, slug: newSlug }) }
      );
      setOrgs((prev) => [...prev, { ...result, members: 1 }]);
      setShowCreate(false);
      setNewName("");
      setNewSlug("");
    } catch (err) {
      alert("Failed to create organization.");
    }
  }

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">My Institutes</h1>
            <p className="text-sm text-muted">
              Manage coaching institutes and member access.
            </p>
          </div>
          <Button onClick={() => setShowCreate(!showCreate)}>
            <Plus className="h-4 w-4" /> New Institute
          </Button>
        </div>

        {showCreate && (
          <Card className="mb-6">
            <h3 className="mb-3 text-sm font-medium">Create Institute</h3>
            <div className="flex gap-3">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Institute name"
                className="flex-1 rounded-lg border border-borderc bg-surface px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-light"
              />
              <input
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="slug"
                className="w-40 rounded-lg border border-borderc bg-surface px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-light"
              />
              <Button onClick={createOrg}>Create</Button>
            </div>
          </Card>
        )}

        {loading ? (
          <Spinner label="Loading institutes…" />
        ) : orgs.length === 0 ? (
          <Card className="text-center text-muted">
            <Building2 className="mx-auto mb-2 h-8 w-8 opacity-40" />
            <p>No institutes yet. Create one to get started.</p>
          </Card>
        ) : (
          <div className="space-y-3">
            {orgs.map((org) => (
              <Link key={org.id} href={`/orgs/${org.id}`}>
                <Card className="cursor-pointer transition hover:border-indigo-light">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{org.name}</div>
                      <div className="text-xs text-muted">/{org.slug} · {org.members} member{org.members !== 1 ? "s" : ""}</div>
                    </div>
                    <span className="text-xs text-muted">→</span>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
