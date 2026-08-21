"use client";

import { useState, useEffect, useCallback } from "react";
import { AUTH_API } from "@/lib/api";

const TOKEN_KEY = "automark_token";
const USER_KEY  = "automark_user";

export interface AuthUser {
  user_id: string;
  email: string;
}

export function useAuth() {
  const [user,    setUser]    = useState<AuthUser | null>(null);
  const [token,   setToken]   = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    try {
      const t = localStorage.getItem(TOKEN_KEY);
      const u = localStorage.getItem(USER_KEY);
      if (t && u) {
        setToken(t);
        setUser(JSON.parse(u));
      }
    } catch { /* ignore parse errors */ }
    setLoading(false);
  }, []);

  const _persist = useCallback((t: string, u: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${AUTH_API}/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? "Login failed");
    }
    const data = await res.json();
    _persist(data.token, { user_id: data.user_id, email: data.email });
  }, [_persist]);

  const register = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${AUTH_API}/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? "Registration failed");
    }
    const data = await res.json();
    _persist(data.token, { user_id: data.user_id, email: data.email });
  }, [_persist]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return { user, token, loading, login, register, logout };
}
