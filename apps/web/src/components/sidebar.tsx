"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ForgeWordmark } from "./forge-mark";
import { Badge } from "./ui";

const NAV = [
  { href: "/", label: "Overview", icon: HomeIcon },
  { href: "/investigations", label: "Investigations", icon: CompassIcon },
  { href: "/decisions", label: "Decisions", icon: SparkIcon },
  { href: "/actions", label: "Actions", icon: BoltIcon },
  { href: "/data", label: "Data explorer", icon: DatabaseIcon },
  { href: "/documents", label: "Documents", icon: FileIcon },
  { href: "/audit", label: "Audit log", icon: ShieldIcon },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-border bg-bg-elevated">
      <div className="flex h-16 items-center px-5">
        <ForgeWordmark />
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-accent-soft text-accent"
                  : "text-fg-muted hover:bg-bg-inset hover:text-fg"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bg-inset text-xs font-semibold text-fg-muted">
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-fg">{user?.email ?? "…"}</p>
            {user && <Badge tone="neutral">{user.role}</Badge>}
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="rounded-md p-1.5 text-fg-subtle hover:bg-bg-inset hover:text-fg"
          >
            <LogoutIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

function iconProps(className?: string) {
  return {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
}

function HomeIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10v10h14V10" />
    </svg>
  );
}
function CompassIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15 9-2 6-6 2 2-6 6-2Z" />
    </svg>
  );
}
function SparkIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
    </svg>
  );
}
function BoltIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </svg>
  );
}
function DatabaseIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
    </svg>
  );
}
function FileIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M6 2h9l5 5v15H6Z" />
      <path d="M15 2v5h5" />
    </svg>
  );
}
function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M12 3 4 6v6c0 5 3.5 7.5 8 9 4.5-1.5 8-4 8-9V6l-8-3Z" />
    </svg>
  );
}
function LogoutIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}
