"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Button, Card, ErrorBanner, Input, Label } from "@/components/ui";
import { ForgeMark } from "@/components/forge-mark";

export default function LoginPage() {
  const router = useRouter();
  const [orgSlug, setOrgSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.login(orgSlug.trim(), email.trim(), password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) setError("Too many attempts. Wait a moment and try again.");
        else setError("Invalid organization, email, or password.");
      } else {
        setError("Could not reach the server.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm animate-fade-in-up">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <ForgeMark />
          <div>
            <h1 className="text-lg font-semibold text-fg">Sign in to Forge</h1>
            <p className="text-sm text-fg-muted">Enterprise AI decision platform</p>
          </div>
        </div>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && <ErrorBanner message={error} />}
            <div>
              <Label>Organization</Label>
              <Input
                value={orgSlug}
                onChange={(e) => setOrgSlug(e.target.value)}
                placeholder="acme"
                autoComplete="organization"
                required
              />
            </div>
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
                required
              />
            </div>
            <div>
              <Label>Password</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" loading={loading} className="mt-1 w-full">
              Sign in
            </Button>
          </form>
        </Card>
        <p className="mt-6 text-center text-sm text-fg-muted">
          New to Forge?{" "}
          <Link href="/register" className="font-medium text-accent hover:text-accent-hover">
            Create an organization
          </Link>
        </p>
      </div>
    </main>
  );
}
