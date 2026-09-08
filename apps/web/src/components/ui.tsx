"use client";

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-bg-elevated shadow-sm shadow-black/[0.02] ${className}`}
    >
      {children}
    </div>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap";
  const sizes = { sm: "px-2.5 py-1.5 text-xs", md: "px-3.5 py-2 text-sm" };
  const variants = {
    primary: "bg-accent text-accent-fg hover:bg-accent-hover",
    secondary:
      "bg-bg-inset text-fg border border-border-strong hover:border-fg-subtle",
    ghost: "text-fg-muted hover:text-fg hover:bg-bg-inset",
    danger: "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20",
  };
  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-border-strong bg-bg-inset px-3 py-2 text-sm text-fg placeholder:text-fg-subtle outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 ${props.className ?? ""}`}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-border-strong bg-bg-inset px-3 py-2 text-sm text-fg placeholder:text-fg-subtle outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 ${props.className ?? ""}`}
    />
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1.5 block text-xs font-medium text-fg-muted">{children}</label>
  );
}

const badgeTones: Record<string, string> = {
  neutral: "bg-bg-inset text-fg-muted border-border-strong",
  accent: "bg-accent-soft text-accent border-transparent",
  success: "bg-success-soft text-success border-transparent",
  warning: "bg-warning-soft text-warning border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
  info: "bg-info-soft text-info border-transparent",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: keyof typeof badgeTones;
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${badgeTones[tone]}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function statusTone(status: string): keyof typeof badgeTones {
  switch (status) {
    case "completed":
    case "executed":
    case "approved":
    case "ok":
      return "success";
    case "running":
    case "proposed":
    case "draft":
      return "accent";
    case "max_steps_exceeded":
    case "rejected":
      return "warning";
    case "failed":
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <p className="text-sm font-medium text-fg">{title}</p>
      {description && <p className="max-w-sm text-sm text-fg-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent text-fg-subtle ${className}`}
    />
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 text-sm text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
      {message}
    </div>
  );
}
