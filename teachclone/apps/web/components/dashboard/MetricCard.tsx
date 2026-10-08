import { clsx } from "clsx";
import type { ReactNode } from "react";
import { AdminCard, Skeleton } from "./primitives";

type Accent = "primary" | "success" | "info" | "warning" | "error";

const ACCENT: Record<
  Accent,
  { text: string; glow: string; ring: string }
> = {
  primary: {
    text: "text-admin-primary",
    glow: "from-admin-primary/15",
    ring: "ring-admin-primary/20",
  },
  success: {
    text: "text-admin-success",
    glow: "from-admin-success/15",
    ring: "ring-admin-success/20",
  },
  info: {
    text: "text-admin-info",
    glow: "from-admin-info/15",
    ring: "ring-admin-info/20",
  },
  warning: {
    text: "text-admin-warning",
    glow: "from-admin-warning/15",
    ring: "ring-admin-warning/20",
  },
  error: {
    text: "text-admin-error",
    glow: "from-admin-error/15",
    ring: "ring-admin-error/20",
  },
};

export function MetricCard({
  icon,
  label,
  value,
  sub,
  accent = "primary",
  loading = false,
}: {
  icon: string;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: Accent;
  loading?: boolean;
}) {
  const a = ACCENT[accent];
  return (
    <AdminCard
      padded={false}
      className={clsx(
        "relative overflow-hidden p-5 ring-1 ring-inset",
        a.ring
      )}
    >
      {/* subtle corner gradient */}
      <div
        className={clsx(
          "pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br to-transparent blur-2xl",
          a.glow
        )}
      />
      <div className="relative flex items-start justify-between">
        <span className="text-sm font-medium text-admin-sub">{label}</span>
        <span className="text-xl">{icon}</span>
      </div>
      <div className="relative mt-3">
        {loading ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <div className={clsx("text-3xl font-bold tracking-tight", a.text)}>
            {value}
          </div>
        )}
        {loading ? (
          <Skeleton className="mt-2 h-3 w-28" />
        ) : (
          sub && <div className="mt-1 text-xs text-admin-sub">{sub}</div>
        )}
      </div>
    </AdminCard>
  );
}
