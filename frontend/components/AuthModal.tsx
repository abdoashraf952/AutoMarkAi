"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { useAuth } from "@/hooks/useAuth";

type Auth = ReturnType<typeof useAuth>;

export default function AuthModal({
  auth,
  onSuccess,
  onClose,
}: {
  auth: Auth;
  onSuccess: () => void;
  onClose:   () => void;
}) {
  const [mode,     setMode]     = useState<"login" | "register">("login");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [busy,     setBusy]     = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError("Please fill in both fields."); return; }
    setBusy(true);
    setError("");
    try {
      if (mode === "login") await auth.login(email, password);
      else                  await auth.register(email, password);
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    /* backdrop */
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "rgba(10,8,5,0.82)", backdropFilter: "blur(12px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.93, y: 20 }}
        animate={{ opacity: 1, scale: 1,    y: 0  }}
        exit={{   opacity: 0, scale: 0.93,  y: 20 }}
        transition={{ type: "spring", stiffness: 300, damping: 28 }}
        className="glass-strong relative w-full max-w-md rounded-3xl p-8 shadow-card"
        style={{ border: "1px solid rgba(201,168,76,0.2)" }}
      >
        {/* close */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:text-white"
          style={{ background: "rgba(255,255,255,0.06)" }}
        >
          ✕
        </button>

        {/* logo mark */}
        <div className="mb-7 flex flex-col items-center gap-3">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-2xl text-2xl shadow-glow"
            style={{ background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 40%, #E8C97A 70%, #D97706 100%)" }}
          >
            🏢
          </div>
          <div className="text-center">
            <h2 className="font-serif text-xl font-bold accent-gradient-text">AutoMark AI</h2>
            <p className="mt-0.5 text-xs text-white/45">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </p>
          </div>
        </div>

        {/* tab switcher */}
        <div
          className="mb-6 flex rounded-2xl p-1"
          style={{ background: "rgba(255,255,255,0.05)" }}
        >
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(""); }}
              className="flex-1 rounded-xl py-2 text-sm font-semibold transition-all"
              style={
                mode === m
                  ? { background: "linear-gradient(110deg, #C9A84C, #E8C97A)", color: "#1A1205" }
                  : { color: "rgba(255,255,255,0.45)" }
              }
            >
              {m === "login" ? "Sign In" : "Create Account"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4">
          {/* email */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-white/55">Email address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="field"
              autoComplete="email"
            />
          </div>

          {/* password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-white/55">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "Min. 8 characters" : "Your password"}
              className="field"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>

          {/* error */}
          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-xl px-4 py-2.5 text-xs text-red-300"
                style={{ background: "rgba(239,68,68,0.12)" }}
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>

          <button
            type="submit"
            disabled={busy}
            className="btn-primary mt-1 w-full py-3.5 text-sm font-bold"
          >
            {busy ? "Please wait…" : mode === "login" ? "Sign In →" : "Create Account →"}
          </button>
        </form>

        <p className="mt-5 text-center text-[11px] text-white/30">
          Your campaigns and ad data are saved securely to your account.
        </p>
      </motion.div>
    </motion.div>
  );
}
