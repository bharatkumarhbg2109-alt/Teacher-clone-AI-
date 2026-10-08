"use client";
import { clsx } from "clsx";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

export function Button({
  children,
  variant = "primary",
  className,
  loading,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger";
  loading?: boolean;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-indigo hover:bg-indigo-light text-white",
    outline: "border border-borderc hover:border-indigo-light text-slate-200",
    ghost: "hover:bg-white/5 text-slate-300",
    danger: "bg-rose/90 hover:bg-rose text-white",
  };
  return (
    <button className={clsx(base, variants[variant], className)} disabled={loading || props.disabled} {...props}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-xl border border-borderc bg-card p-5", className)}>{children}</div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={clsx(
        "w-full rounded-lg border border-borderc bg-surface px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-light",
        props.className
      )}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={clsx(
        "w-full rounded-lg border border-borderc bg-surface px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-light",
        props.className
      )}
    />
  );
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border border-borderc bg-white/5 px-2 py-0.5 text-xs text-slate-300",
        className
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="mb-1.5 block text-xs font-medium text-muted">{children}</label>;
}

export function TopNav() {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-borderc bg-bg/90 px-6 py-3 backdrop-blur">
      <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-indigo to-cyan text-sm">
          🧠
        </span>
        TeachClone
      </Link>
      <nav className="flex items-center gap-4 text-sm text-muted">
        <Link href="/dashboard" className="hover:text-white">Dashboard</Link>
        <Link href="/discover" className="hover:text-white">Discover</Link>
        <Link href="/onboarding" className="hover:text-white">My level</Link>
      </nav>
    </header>
  );
}
