"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Container from "@/components/layout/Container";
import HospitalSelector from "@/components/HospitalSelector";
import ContinuousTimelineChart from "@/components/forecast/ContinuousTimelineChart";
import InsightCard from "@/components/agent/InsightCard";
import api, { getApiErrorMessage } from "@/lib/api";
import { getUser, getUserHospitalIds, getUserRole } from "@/lib/auth";

/* ── Types ── */
interface ForecastResult {
  hospital_id: string;
  target: "admissions" | "inpatient_beds_used";
  horizon: number;
  prediction: number;
  prediction_low: number | null;
  prediction_high: number | null;
  resource_gap: number | null;
  capacity_source: string | null;
  forecast_date: string;
}

interface ExternalSignal {
  date: string;
  temperature: number;
  aqi: number;
  outbreak_index: number;
  mobility_index: number;
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const preselected = searchParams.get("hospital");

  const [hospitals, setHospitals] = useState<string[]>([]);
  const [hospitalMap, setHospitalMap] = useState<Record<string, { name: string; region: string }>>({});
  const [selectedHospitals, setSelectedHospitals] = useState<string[]>(
    preselected ? [preselected] : []
  );
  const [forecasts, setForecasts] = useState<ForecastResult[]>([]);
  const [history, setHistory] = useState<{ date: string; admissions: number }[]>([]);
  const [signals, setSignals] = useState<ExternalSignal | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<"admissions" | "inpatient_beds_used">("inpatient_beds_used");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState("");
  const [hospitalsWithoutForecasts, setHospitalsWithoutForecasts] = useState<string[]>([]);
  const [user, setUser] = useState<{ email: string; name?: string; role?: string } | null>(null);
  const [modelVersion, setModelVersion] = useState<string>("v2.0.0");
  const [lastRetrained, setLastRetrained] = useState<string | null>(null);

  useEffect(() => {
    setUser(getUser());
    loadHospitals();
    loadSystemMetadata();
  }, []);

  useEffect(() => {
    if (preselected && hospitals.includes(preselected) && !selectedHospitals.includes(preselected)) {
      setSelectedHospitals([preselected]);
    }
  }, [preselected, hospitals]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSystemMetadata = async () => {
    try {
      const res = await api.get("/system/status");
      if (res.data?.model_version) setModelVersion(res.data.model_version);
      if (res.data?.last_forecast_run) setLastRetrained(res.data.last_forecast_run);
    } catch {
      // silent
    }
  };

  const loadHospitals = async () => {
    try {
      const res = await api.get("/hospitals");
      const list = res.data.hospitals || [];
      const items = res.data.items || [];
      const userRole = getUserRole();
      const assigned = getUserHospitalIds();

      const map: Record<string, { name: string; region: string }> = {};
      items.forEach((item: any) => {
        map[item.hospital_id] = { name: item.name, region: item.region };
      });
      setHospitalMap(map);

      // For hospital staff, strictly filter options if assigned
      let allowed = list;
      if (userRole === "hospital_staff" && assigned.length > 0) {
        allowed = list.filter((h: string) => assigned.includes(h));
      }

      setHospitals(allowed);
      if (allowed.length > 0 && selectedHospitals.length === 0) {
        setSelectedHospitals([allowed[0]]);
      }
    } catch {
      // silent
    }
  };

  const handleGenerate = async () => {
    if (selectedHospitals.length === 0) {
      setError("Please select at least one hospital");
      return;
    }
    setError("");
    setHospitalsWithoutForecasts([]);
    setLoading(true);
    setLoadingHistory(true);

    try {
      // Fetch 4-week forecasts
      const res = await api.post("/predict", {
        hospital_ids: selectedHospitals,
        horizons: [1, 2, 3, 4],
      });
      const fcList: ForecastResult[] = res.data.forecasts || [];
      setForecasts(fcList);

      // Surface hospitals with no model data
      const noData: string[] = res.data.metadata?.hospitals_without_forecasts || [];
      setHospitalsWithoutForecasts(noData);

      // Fetch historical admissions (last 8 weeks / 56 days)
      try {
        const histRes = await api.get(`/forecast/history`, {
          params: { hospitals: selectedHospitals[0], days: 56 },
        });
        const histData = histRes.data?.history || [];
        setHistory(histData);
      } catch {
        setHistory([]);
      }

      // Fetch signals
      try {
        const sysRes = await api.get("/system/status");
        if (sysRes.data?.last_signal_update) {
          setSignals({
            date: sysRes.data.last_signal_update,
            temperature: 0,
            aqi: 0,
            outbreak_index: 0,
            mobility_index: 0,
          });
        }
      } catch {
        // silent
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to generate forecast"));
    } finally {
      setLoading(false);
      setLoadingHistory(false);
    }
  };

  // Auto-generate on first hospital selection
  useEffect(() => {
    if (selectedHospitals.length > 0 && forecasts.length === 0 && !loading) {
      handleGenerate();
    }
  }, [selectedHospitals]); // eslint-disable-line react-hooks/exhaustive-deps

  const exportCSV = () => {
    if (!forecasts.length) return;
    const csv = [
      "Hospital ID,Target,Horizon,Prediction,Prediction Low (10th),Prediction High (90th),Resource Gap,Capacity Source,Forecast Date",
      ...forecasts.map(
        (f) =>
          `${f.hospital_id},${f.target},Week ${f.horizon},${f.prediction.toFixed(2)},${
            f.prediction_low !== null ? f.prediction_low.toFixed(2) : ""
          },${f.prediction_high !== null ? f.prediction_high.toFixed(2) : ""},${
            f.resource_gap !== null ? f.resource_gap.toFixed(2) : ""
          },${f.capacity_source || ""},${f.forecast_date}`
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `forecast_${selectedTarget}_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const primaryHospital = selectedHospitals[0] || "";
  const filteredForecasts = forecasts.filter((f) => f.target === selectedTarget);
  const activeBedForecast = forecasts.find((f) => f.hospital_id === primaryHospital && f.target === "inpatient_beds_used");

  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated">
      <Navbar />

      <div className="pt-20 pb-12">
        <Container>
          {/* Header & Badges */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan/10 text-cyan border border-cyan/20">
                  Model: {modelVersion} (Residual-on-MA4)
                </span>
                {lastRetrained && (
                  <span className="text-xs text-slate-400">
                    Updated: {new Date(lastRetrained).toLocaleDateString()}
                  </span>
                )}
              </div>
              <h1 className="text-3xl font-bold font-display">
                Welcome back, <span className="gradient-text">{user?.name || user?.email}</span>
              </h1>
              <div className="flex flex-wrap items-center gap-2 mt-1.5">
                <p className="text-slate-400 text-sm">
                  4-Week Dual-Target Hospital Forecasting
                </p>
                {getUserRole() === "hospital_staff" && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-400/10 text-emerald-400 border border-emerald-400/30">
                    Hospital: {primaryHospital} {hospitalMap[primaryHospital]?.name ? `(${hospitalMap[primaryHospital].name})` : ""}
                  </span>
                )}
                {getUserRole() === "admin" && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-400/10 text-amber-400 border border-amber-400/30">
                    Admin Network View
                  </span>
                )}
              </div>
            </div>

            {/* Target Toggle */}
            <div className="flex items-center bg-white/5 p-1 rounded-xl border border-white/10">
              <button
                onClick={() => setSelectedTarget("inpatient_beds_used")}
                className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                  selectedTarget === "inpatient_beds_used"
                    ? "bg-cyan text-navy shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Occupancy (Beds Used)
              </button>
              <button
                onClick={() => setSelectedTarget("admissions")}
                className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                  selectedTarget === "admissions"
                    ? "bg-cyan text-navy shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Demand (Admissions)
              </button>
            </div>
          </motion.div>

          {/* Control Panel & Content Grid */}
          <div className="grid lg:grid-cols-4 gap-6">
            {/* Left sidebar */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              className="lg:col-span-1 space-y-4"
            >
              <HospitalSelector
                hospitals={hospitals}
                hospitalMap={hospitalMap}
                selected={selectedHospitals}
                onChange={setSelectedHospitals}
              />

              <button
                onClick={handleGenerate}
                disabled={loading || selectedHospitals.length === 0}
                className="w-full btn-primary"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-navy border-t-transparent rounded-full animate-spin" />
                    Generating 4-Wk Forecast...
                  </span>
                ) : (
                  "Update 4-Week Forecast"
                )}
              </button>

              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              {hospitalsWithoutForecasts.length > 0 && (
                <div className="p-3 rounded-xl bg-amber-400/10 border border-amber-400/25 space-y-2">
                  <div className="flex items-start gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber-400 mt-0.5 flex-shrink-0">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <div>
                      <p className="text-xs font-semibold text-amber-400">No Forecast Data Available</p>
                      <p className="text-xs text-amber-300/70 mt-1">
                        {hospitalsWithoutForecasts.join(", ")} — newly added and not yet in the training dataset. Requires model retraining before forecasts can be generated.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Resource Gap Callout for Primary Hospital */}
              {activeBedForecast && activeBedForecast.resource_gap !== null && (
                <div className="glass-card rounded-xl p-4 border border-white/5 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs uppercase tracking-wider text-slate-400 font-medium">Safe Capacity Gap</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold ${
                        activeBedForecast.resource_gap > 0
                          ? "bg-red-500/20 text-red-400 border border-red-500/30"
                          : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      }`}
                    >
                      {activeBedForecast.resource_gap > 0
                        ? `+${activeBedForecast.resource_gap.toFixed(1)} beds deficit`
                        : `${activeBedForecast.resource_gap.toFixed(1)} beds buffer`}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Threshold: 85% of hospital capacity.
                    {activeBedForecast.capacity_source === "historical_median_fallback" && (
                      <span className="text-amber-400 block mt-1">
                        * Note: Sourced from hospital historical median capacity fallback.
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Summary stats */}
              {filteredForecasts.length > 0 && (
                <div className="glass-card rounded-xl p-4 space-y-3 border border-white/5">
                  <h4 className="text-xs uppercase tracking-widest text-slate-400 font-medium">Forecast Stats</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Target</span>
                      <span className="text-cyan font-medium capitalize">
                        {selectedTarget.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Horizons</span>
                      <span className="text-cyan font-mono">Weeks 1 – 4</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Peak Forecast</span>
                      <span className="text-amber-400 font-mono">
                        {Math.max(...filteredForecasts.map((f) => f.prediction)).toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <button onClick={exportCSV} className="w-full mt-2 btn-secondary !py-2 text-xs">
                    Export Dual-Target CSV
                  </button>
                </div>
              )}
            </motion.div>

            {/* Main content */}
            <div className="lg:col-span-3 space-y-6">
              {/* Continuous Timeline Chart */}
              <div className="glass-card rounded-xl p-6 border border-white/5">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2 mb-4">
                  <div>
                    <h3 className="text-base font-semibold text-white">
                      Continuous Timeline Forecast ({selectedTarget === "inpatient_beds_used" ? "Occupancy / Beds Used" : "Demand / Admissions"})
                    </h3>
                    <p className="text-xs text-slate-400">
                      Historical weeks to the left, 4-week prediction interval to the right of the cutoff
                    </p>
                  </div>
                  <span className="text-xs font-mono px-2.5 py-1 bg-white/5 border border-white/10 rounded text-slate-300">
                    Hospital: {primaryHospital || "None"}
                  </span>
                </div>

                {loading ? (
                  <div className="h-80 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-cyan border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <ContinuousTimelineChart
                    target={selectedTarget}
                    hospitalId={primaryHospital}
                    history={history}
                    forecasts={forecasts}
                    capacity={activeBedForecast?.resource_gap ? 300 : 200}
                    capacitySource={activeBedForecast?.capacity_source}
                  />
                )}
              </div>

              {/* Signals & AI Agent Row */}
              {forecasts.length > 0 && (
                <div className="grid md:grid-cols-2 gap-6">
                  {/* External Signals */}
                  <div className="glass-card rounded-xl p-5 border border-white/5">
                    <h3 className="text-sm uppercase tracking-widest text-cyan mb-4 font-medium flex items-center gap-2">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-cyan">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                      </svg>
                      Exogenous Telemetry
                    </h3>
                    {signals ? (
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Latest Signal Week</span>
                          <span className="font-mono text-slate-200">{signals.date}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Ingestion Status</span>
                          <span className="badge-success">Synchronized</span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">Synchronized with weekly HHS/NHSN reporting cycle.</p>
                    )}
                  </div>

                  {/* AI Agent Insight */}
                  <InsightCard hospitalCode={selectedHospitals[0]} />
                </div>
              )}

              {/* Forecast Table */}
              {filteredForecasts.length > 0 && (
                <div className="glass-card rounded-xl overflow-hidden border border-white/5">
                  <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center">
                    <h3 className="text-sm uppercase tracking-widest text-cyan font-medium">
                      4-Week Horizon Predictions ({selectedTarget})
                    </h3>
                    <span className="text-xs text-slate-400 font-mono">10th – 90th Quantile Bounds</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/5 text-xs text-slate-400 uppercase">
                          <th className="px-6 py-3 text-left">Hospital</th>
                          <th className="px-6 py-3 text-left">Horizon</th>
                          <th className="px-6 py-3 text-left">Target Date</th>
                          <th className="px-6 py-3 text-right">Point Forecast</th>
                          <th className="px-6 py-3 text-right">80% Interval (Low - High)</th>
                          {selectedTarget === "inpatient_beds_used" && (
                            <th className="px-6 py-3 text-right">Resource Gap</th>
                          )}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {filteredForecasts.map((row) => (
                          <tr key={`${row.hospital_id}-${row.horizon}`} className="hover:bg-white/[0.02]">
                            <td className="px-6 py-3 font-medium text-slate-200">{row.hospital_id}</td>
                            <td className="px-6 py-3">
                              <span className="px-2 py-0.5 rounded bg-cyan/10 text-cyan text-xs font-medium">
                                Week {row.horizon}
                              </span>
                            </td>
                            <td className="px-6 py-3 font-mono text-slate-400 text-xs">
                              {row.forecast_date}
                            </td>
                            <td className="px-6 py-3 text-right font-mono text-cyan font-semibold">
                              {row.prediction.toFixed(1)}
                            </td>
                            <td className="px-6 py-3 text-right font-mono text-slate-400 text-xs">
                              {row.prediction_low !== null && row.prediction_high !== null
                                ? `[${row.prediction_low.toFixed(1)} – ${row.prediction_high.toFixed(1)}]`
                                : "N/A"}
                            </td>
                            {selectedTarget === "inpatient_beds_used" && (
                              <td className="px-6 py-3 text-right font-mono text-xs">
                                {row.resource_gap !== null ? (
                                  <span className={row.resource_gap > 0 ? "text-red-400 font-semibold" : "text-emerald-400"}>
                                    {row.resource_gap > 0 ? `+${row.resource_gap.toFixed(1)}` : row.resource_gap.toFixed(1)}
                                  </span>
                                ) : (
                                  "-"
                                )}
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Container>
      </div>

      <Footer />
    </main>
  );
}
