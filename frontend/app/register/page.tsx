"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import api, { getApiErrorMessage } from "@/lib/api";
import { setToken, setUser } from "@/lib/auth";
import Navbar from "@/components/layout/Navbar";
import Logo from "@/components/ui/Logo";

interface HospitalOption {
  hospital_id: string;
  name: string;
  region: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"hospital_staff" | "admin">("hospital_staff");
  const [selectedHospital, setSelectedHospital] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [hospitals, setHospitals] = useState<HospitalOption[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch available hospitals for selection
    api
      .get("/hospitals/public?limit=100")
      .then((res) => {
        const list = res.data?.hospitals || [];
        setHospitals(list);
        if (list.length > 0) {
          setSelectedHospital(list[0].hospital_id);
        }
      })
      .catch(() => {
        // Fallback default
        setSelectedHospital("050001");
      });
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (role === "admin" && adminKey.trim() !== "HEALTHFLOW_ADMIN_2026" && adminKey.trim() !== "admin") {
      setError("Invalid Admin Passkey. Use 'HEALTHFLOW_ADMIN_2026' or 'admin'");
      setLoading(false);
      return;
    }

    try {
      const payload: any = {
        name,
        email,
        password,
        role,
      };

      if (role === "hospital_staff" && selectedHospital) {
        payload.hospital_ids = [selectedHospital];
      }

      const res = await api.post("/auth/register", payload);
      setToken(res.data.access_token);
      setUser({
        email: res.data.user.email,
        name: res.data.user.name,
        role: res.data.user.role,
        hospital_ids: res.data.user.hospital_ids || (selectedHospital ? [selectedHospital] : []),
      });

      if (res.data.user.role === "admin") {
        router.push("/admin");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Registration failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const filteredHospitals = hospitals.filter(
    (h) =>
      h.hospital_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      h.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated">
      <Navbar />
      <div className="flex items-center justify-center min-h-screen px-4 py-24">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-gradient-radial from-teal/5 to-transparent blur-3xl pointer-events-none" />

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
            <h1 className="text-2xl font-bold text-center mb-1">Create Account</h1>
            <p className="text-slate-400 text-center text-sm mb-6">
              Sign up for hospital-specific forecasting or system administration
            </p>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            {/* Role Selection Tabs */}
            <div className="grid grid-cols-2 gap-2 p-1 bg-white/5 rounded-xl border border-white/10 mb-5">
              <button
                type="button"
                onClick={() => setRole("hospital_staff")}
                className={`py-2 text-xs font-semibold rounded-lg transition-all ${
                  role === "hospital_staff"
                    ? "bg-cyan text-navy shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Hospital Staff
              </button>
              <button
                type="button"
                onClick={() => setRole("admin")}
                className={`py-2 text-xs font-semibold rounded-lg transition-all ${
                  role === "admin"
                    ? "bg-amber-400 text-navy shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Admin Access
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
                  Full Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="input-field"
                  placeholder="Dr. Jordan Lee"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
                  Work Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="input-field"
                  placeholder={role === "admin" ? "admin@healthflow.ai" : "staff@hospital.org"}
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
                  minLength={6}
                  className="input-field"
                  placeholder="••••••••"
                />
              </div>

              {/* Hospital Staff Specific: Assigned Hospital Picker */}
              {role === "hospital_staff" && (
                <div>
                  <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
                    Select Your Hospital Facility
                  </label>
                  {hospitals.length > 0 ? (
                    <div className="space-y-1.5">
                      <input
                        type="text"
                        placeholder="Search hospital name or CCN..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="input-field !py-1.5 !text-xs !bg-navy-dark/60 mb-1"
                      />
                      <select
                        value={selectedHospital}
                        onChange={(e) => setSelectedHospital(e.target.value)}
                        required
                        className="input-field text-sm cursor-pointer"
                      >
                        {filteredHospitals.slice(0, 50).map((h) => (
                          <option key={h.hospital_id} value={h.hospital_id} className="bg-navy text-white">
                            {h.hospital_id} — {h.name} ({h.region})
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <input
                      type="text"
                      value={selectedHospital}
                      onChange={(e) => setSelectedHospital(e.target.value)}
                      placeholder="e.g. 050001"
                      className="input-field font-mono"
                      required
                    />
                  )}
                  <p className="text-[11px] text-slate-400 mt-1">
                    Your account will be scoped exclusively to this hospital&apos;s admissions and bed forecasts.
                  </p>
                </div>
              )}

              {/* Admin Specific: Passkey */}
              {role === "admin" && (
                <div>
                  <label className="block text-xs uppercase tracking-widest text-amber-400 mb-2 font-medium">
                    Admin Verification Key
                  </label>
                  <input
                    type="password"
                    value={adminKey}
                    onChange={(e) => setAdminKey(e.target.value)}
                    required
                    className="input-field border-amber-400/40 focus:border-amber-400"
                    placeholder="Enter HEALTHFLOW_ADMIN_2026 or admin"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Passkey: <code className="text-amber-400">HEALTHFLOW_ADMIN_2026</code> or <code className="text-amber-400">admin</code>
                  </p>
                </div>
              )}

              <button type="submit" disabled={loading} className="w-full btn-primary mt-2">
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-navy border-t-transparent rounded-full animate-spin" />
                    Creating account...
                  </span>
                ) : (
                  `Register as ${role === "admin" ? "Admin" : "Hospital Staff"}`
                )}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-400">
              Already have an account?{" "}
              <Link href="/login" className="text-cyan hover:text-cyan-light transition-colors font-medium">
                Sign in
              </Link>
            </p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
