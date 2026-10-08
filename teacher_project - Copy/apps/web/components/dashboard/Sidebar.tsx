"use client";
import { clsx } from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  getDnaHealth,
  getHealth,
  shortModel,
  usePolling,
  type DnaHealth,
  type SystemHealth,
} from "@/lib/adminApi";
import { StatusDot } from "./primitives";

const NAV = [
  { href: "/admin", label: "Overview", icon: "🏠" },
  { href: "/admin/dna", label: "DNA Extraction", icon: "🧬" },
  { href: "/admin/teachers", label: "Teachers", icon: "👨‍🏫" },
  { href: "/admin/system", label: "System Health", icon: "⚙️" },
  { href: "/admin/logs", label: "Logs", icon: "📋" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname() || "/admin";

  const { data: sys } = usePolling<SystemHealth>(getHealth, 30_000);
  const { data: dnaTimed } = usePolling(getDnaHealth, 30_000);
  const dna: DnaHealth | undefined = dnaTimed?.data;

  const apiUp = !!sys;
  const ollamaUp = !!dna?.reachable;
  // Green when everything is up, amber when the API is up but Ollama is down,
  // red when the API itself is unreachable.
  const overall: "success" | "warning" | "error" = !apiUp
    ? "error"
    : ollamaUp
    ? "success"
    : "warning";
  const overallLabel =
    overall === "success"
      ? "All systems running"
      : overall === "warning"
      ? "Partial — Ollama down"
      : "API unreachable";

  const activeModel =
    dna?.models?.find((m) => m.startsWith(dna.default_model)) ||
    dna?.models?.[0] ||
    dna?.default_model;

  return (
    <>
      {/* Mobile backdrop */}
      <div
        onClick={onClose}
        className={clsx(
          "fixed inset-0 z-30 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      />
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-admin-border bg-admin-surface transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 border-b border-admin-border px-5 py-5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-admin-primary to-admin-info text-xl shadow-lg shadow-admin-primary/20">
            🧬
          </span>
          <div className="leading-tight">
            <div className="font-semibold text-admin-txt">TeachClone DNA</div>
            <div className="text-xs text-admin-sub">Admin Dashboard</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                  active
                    ? "bg-admin-primary/15 text-admin-txt ring-1 ring-inset ring-admin-primary/30"
                    : "text-admin-sub hover:bg-white/5 hover:text-admin-txt"
                )}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
                {active && (
                  <span className="ml-auto h-1.5 w-1.5 rounded-full bg-admin-primary" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Status footer */}
        <div className="space-y-3 border-t border-admin-border px-4 py-4 text-xs">
          <div className="flex items-center gap-2">
            <StatusDot tone={overall} pulse={overall === "success"} />
            <span className="text-admin-sub">{overallLabel}</span>
          </div>
          <div className="rounded-lg border border-admin-border bg-admin-bg/50 px-3 py-2">
            <div className="flex items-center gap-2">
              <span>{ollamaUp ? "🟢" : "🔴"}</span>
              <span className="font-medium text-admin-txt">
                Ollama: {ollamaUp ? "Online" : "Offline"}
              </span>
            </div>
            <div className="mt-0.5 pl-6 text-admin-sub">
              Model: {shortModel(activeModel) || "—"}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
