"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Button, Card, ErrorBanner, Input, Label } from "@/components/ui";
import { ForgeMark } from "@/components/forge-mark";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function RegisterPage() {
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [orgSlug, setOrgSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveSlug = slugTouched ? orgSlug : slugify(orgName);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.registerOrganization(orgName.trim(), effectiveSlug);
      await api.registerUser(effectiveSlug, email.trim(), password, "ADMIN");
      await api.login(effectiveSlug, email.trim(), password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) setError("That organization slug is already taken.");
        else if (err.status === 429) setError("Too many attempts. Wait a moment and try again.");
        else if (err.status === 422)
          setError("Password must be at least 8 characters; slug must be lowercase letters, numbers, and hyphens.");
        else setError(typeof err.detail === "string" ? err.detail : "Could not create your organization.");
      } else {
        setError("Could not reach the server.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-12">
      <div className="w-full max-w-sm animate-fade-in-up">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <ForgeMark />
          <div>
            <h1 className="text-lg font-semibold text-fg">Create your organization</h1>
            <p className="text-sm text-fg-muted">
              You&apos;ll be the first admin — invite teammates afterward.
            </p>
          </div>
        </div>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && <ErrorBanner message={error} />}
            <div>
              <Label>Organization name</Label>
              <Input
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Corp"
                required
              />
            </div>
            <div>
              <Label>Organization URL slug</Label>
              <Input
                value={effectiveSlug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setOrgSlug(slugify(e.target.value));
                }}
                placeholder="acme"
                pattern="[a-z0-9-]+"
                required
              />
            </div>
            <div>
              <Label>Your email</Label>
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
                placeholder="At least 8 characters"
                autoComplete="new-password"
                minLength={8}
                required
              />
            </div>
            <Button type="submit" loading={loading} className="mt-1 w-full">
              Create organization
            </Button>
          </form>
        </Card>
        <p className="mt-6 text-center text-sm text-fg-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:text-accent-hover">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
