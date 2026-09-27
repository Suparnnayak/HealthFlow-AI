"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import api, { getApiErrorMessage } from "@/lib/api";
import { setToken, setUser } from "@/lib/auth";
import Navbar from "@/components/layout/Navbar";
import Logo from "@/components/ui/Logo";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/login", { email, password });
      setToken(res.data.access_token);
      setUser({
        email: res.data.user.email,
        name: res.data.user.name,
        role: res.data.user.role,
        hospital_ids: res.data.user.hospital_ids || [],
      });
      if (res.data.user.role === "admin") {
        router.push("/admin");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Login failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError("");
  };

  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated">
      <Navbar />
      <div className="flex items-center justify-center min-h-screen px-4 py-24">
        {/* Background glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-gradient-radial from-cyan/5 to-transparent blur-3xl pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md relative"
        >
          <div className="glass-card rounded-2xl p-8">
            <div className="flex justify-center mb-6">
              <Logo size="md" />
            </div>
            <h1 className="text-2xl font-bold text-center mb-1">Welcome Back</h1>
            <p className="text-slate-400 text-center text-sm mb-6">
              Sign in to access your forecasting dashboard
            </p>

            {/* Quick Demo Fill Buttons */}
            <div className="mb-6 p-3 bg-white/5 rounded-xl border border-white/10 space-y-2">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Quick Demo Credentials:
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleQuickLogin("test_admin_v2@healthflow.ai", "AdminPass123!")}
                  className="px-2.5 py-1.5 text-xs font-medium rounded bg-amber-400/10 hover:bg-amber-400/20 text-amber-400 border border-amber-400/30 transition-colors text-center"
                >
                  Admin Demo
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickLogin("staff@healthflow.ai", "StaffPass123!")}
                  className="px-2.5 py-1.5 text-xs font-medium rounded bg-cyan/10 hover:bg-cyan/20 text-cyan border border-cyan/30 transition-colors text-center"
                >
                  Staff Demo
                </button>
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="input-field"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="input-field"
                  placeholder="••••••••"
                />
              </div>

              <button type="submit" disabled={loading} className="w-full btn-primary">
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-navy border-t-transparent rounded-full animate-spin" />
                    Signing in...
                  </span>
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-400">
              Don&apos;t have an account?{" "}
              <Link href="/register" className="text-cyan hover:text-cyan-light transition-colors font-medium">
                Create one
              </Link>
            </p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
