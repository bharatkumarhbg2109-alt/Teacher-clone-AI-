"use client";
import { clsx } from "clsx";
import { Badge } from "./primitives";

export interface ModelOption {
  value: string;
  label: string;
  icon?: string;
  desc?: string;
  badge?: string;
  badgeTone?: "success" | "warning" | "error" | "info" | "primary" | "neutral";
  disabled?: boolean;
}

export function ModelSelector({
  options,
  value,
  onChange,
  columns = 1,
}: {
  options: ModelOption[];
  value: string;
  onChange: (value: string) => void;
  columns?: 1 | 2;
}) {
  return (
    <div
      className={clsx(
        "grid gap-2",
        columns === 2 ? "sm:grid-cols-2" : "grid-cols-1"
      )}
    >
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            disabled={opt.disabled}
            onClick={() => !opt.disabled && onChange(opt.value)}
            className={clsx(
              "flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition",
              opt.disabled && "cursor-not-allowed opacity-50",
              selected
                ? "border-admin-primary bg-admin-primary/10 ring-1 ring-inset ring-admin-primary/40"
                : "border-admin-border hover:border-admin-primary/40 hover:bg-white/5"
            )}
          >
            <span
              className={clsx(
                "grid h-4 w-4 shrink-0 place-items-center rounded-full border",
                selected ? "border-admin-primary" : "border-admin-sub"
              )}
            >
              {selected && (
                <span className="h-2 w-2 rounded-full bg-admin-primary" />
              )}
            </span>
            {opt.icon && <span className="text-base">{opt.icon}</span>}
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-admin-txt">
                  {opt.label}
                </span>
                {opt.badge && (
                  <Badge tone={opt.badgeTone || "neutral"}>{opt.badge}</Badge>
                )}
              </span>
              {opt.desc && (
                <span className="block truncate text-xs text-admin-sub">
                  {opt.desc}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
