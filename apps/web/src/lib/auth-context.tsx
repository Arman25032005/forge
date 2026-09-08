"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  refreshUser: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authed, setAuthed] = useState(api.isAuthenticated);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    if (!api.isAuthenticated) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.resolve().then(async () => {
      if (!api.isAuthenticated) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        setUser(await api.me());
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    });
  }, []);

  useEffect(() => {
    return api.subscribe(() => {
      setAuthed(api.isAuthenticated);
      if (!api.isAuthenticated) {
        setUser(null);
        router.replace("/login");
      }
    });
  }, [router]);

  const logout = useCallback(() => {
    api.logout();
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ user, loading, isAuthenticated: authed, refreshUser, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
