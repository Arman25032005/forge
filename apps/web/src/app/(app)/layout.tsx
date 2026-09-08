"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "@/components/sidebar";
import { Spinner } from "@/components/ui";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  if (loading || !isAuthenticated || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
