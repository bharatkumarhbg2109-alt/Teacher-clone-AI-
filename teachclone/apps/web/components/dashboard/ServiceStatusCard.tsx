import type { ReactNode } from "react";
import { AdminCard, Skeleton, StatusDot } from "./primitives";

export interface ServiceStatus {
  name: string;
  /** true = up, false = down, null = unknown/loading */
  online: boolean | null;
  subtitle?: string;
  lines?: { label?: string; value: ReactNode }[];
}

function Row({ svc }: { svc: ServiceStatus }) {
  const tone =
    svc.online == null ? "neutral" : svc.online ? "success" : "error";
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <StatusDot tone={tone} pulse={svc.online === true} className="mt-1.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium text-admin-txt">{svc.name}</span>
          <span
            className={
              svc.online == null
                ? "text-xs text-admin-sub"
                : svc.online
                ? "text-xs font-medium text-admin-success"
                : "text-xs font-medium text-admin-error"
            }
          >
            {svc.online == null ? "…" : svc.online ? "Online" : "Offline"}
          </span>
        </div>
        {svc.subtitle && (
          <div className="truncate text-xs text-admin-sub">{svc.subtitle}</div>
        )}
        {svc.lines && svc.lines.length > 0 && (
          <div className="mt-1.5 space-y-0.5">
            {svc.lines.map((l, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 text-xs"
              >
                {l.label && <span className="text-admin-sub">{l.label}</span>}
                <span className="truncate text-admin-txt/90">{l.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ServiceStatusCard({
  services,
  loading = false,
}: {
  services: ServiceStatus[];
  loading?: boolean;
}) {
  if (loading) {
    return (
      <AdminCard padded={false}>
        <div className="divide-y divide-admin-border">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-4 py-3.5">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="mt-2 h-3 w-24" />
            </div>
          ))}
        </div>
      </AdminCard>
    );
  }
  return (
    <AdminCard padded={false}>
      <div className="divide-y divide-admin-border">
        {services.map((svc) => (
          <Row key={svc.name} svc={svc} />
        ))}
      </div>
    </AdminCard>
  );
}
