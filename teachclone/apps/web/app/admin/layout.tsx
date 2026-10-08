"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { api } from "@/lib/api";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    api<{ is_admin?: boolean }>("/users/me")
      .then((user) => {
        if (user?.is_admin) {
          setAuthorized(true);
        } else {
          router.replace("/dashboard");
        }
      })
      .catch(() => {
        router.replace("/dashboard");
      });
  }, [router]);

  if (authorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-admin-bg text-admin-txt">
        <span className="text-sm text-muted">Checking access…</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-admin-bg text-admin-txt">
      <Sidebar open={open} onClose={() => setOpen(false)} />

      <div className="lg:pl-64">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-admin-border bg-admin-bg/90 px-4 py-3 backdrop-blur lg:hidden">
          <button
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
            className="grid h-9 w-9 place-items-center rounded-lg border border-admin-border text-admin-sub hover:text-admin-txt"
          >
            ☰
          </button>
          <span className="flex items-center gap-2 font-semibold">
            <span>🧬</span> TeachClone DNA
          </span>
        </div>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
