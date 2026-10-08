"use client";
import { BarChart3, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, Spinner, TopNav } from "@/components/ui";
import { api } from "@/lib/api";

interface OrgDetail {
  id: string;
  name: string;
  slug: string;
  members: number;
}

export default function OrgDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [org, setOrg] = useState<OrgDetail | null>(null);

  useEffect(() => {
    api<OrgDetail>(`/organizations/${id}`).then(setOrg).catch(() => {});
  }, [id]);

  if (!org) return (<><TopNav /><main className="p-8"><Spinner label="Loading institute…" /></main></>);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6">
          <h1 className="text-xl font-semibold">{org.name}</h1>
          <p className="text-sm text-muted">Institute dashboard · /{org.slug}</p>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Card>
            <Users className="mb-1 h-5 w-5 text-cyan" />
            <div className="text-2xl font-bold">{org.members}</div>
            <div className="text-xs text-muted">Members</div>
          </Card>
          <Card>
            <BarChart3 className="mb-1 h-5 w-5 text-indigo" />
            <div className="text-2xl font-bold">—</div>
            <div className="text-xs text-muted">Activity (7d)</div>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Link href={`/orgs/${id}/members`}>
            <Card className="cursor-pointer transition hover:border-indigo-light">
              <div className="font-medium">👥 Members</div>
              <div className="text-xs text-muted">Manage roles and invitations</div>
            </Card>
          </Link>
          <Link href={`/orgs/${id}/analytics`}>
            <Card className="cursor-pointer transition hover:border-indigo-light">
              <div className="font-medium">📊 Analytics</div>
              <div className="text-xs text-muted">Institute-wide learning data</div>
            </Card>
          </Link>
        </div>
      </main>
    </>
  );
}
