"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Container from "@/components/layout/Container";
import api from "@/lib/api";
import ContinuousTimelineChart from "@/components/forecast/ContinuousTimelineChart";

interface AccessLogItem {
  id: string;
  user_id: string | null;
  user_email: string | null;
  hospital_id: string | null;
  endpoint: string;
  timestamp: string;
  query_params: string | null;
}

interface SystemStatus {
  model_version: string | null;
  last_forecast_run: string | null;
  last_signal_update: string | null;
  hospitals_count: number;
}

interface ModelInfo {
  version: string;
  trained_at: string | null;
  feature_count: number;
  feature_columns: string[];
}

interface HospitalItem {
  hospital_id: string;
  name: string;
  region: string;
  capacity: number;
}

export default function AdminPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <AdminContent />
    </ProtectedRoute>
  );
}

function AdminContent() {
  const [logs, setLogs] = useState<AccessLogItem[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [hospitalsList, setHospitalsList] = useState<HospitalItem[]>([]);
  const [selectedHospital, setSelectedHospital] = useState<string>("050001");
  const [chartForecasts, setChartForecasts] = useState<any[]>([]);
  const [chartHistory, setChartHistory] = useState<any[]>([]);
  const [chartTarget, setChartTarget] = useState<"inpatient_beds_used" | "admissions">("inpatient_beds_used");
  const [chartLoading, setChartLoading] = useState(false);

  // Add Hospital Form State
  const [newHospId, setNewHospId] = useState("");
  const [newHospName, setNewHospName] = useState("");
  const [newHospRegion, setNewHospRegion] = useState("CA");
  const [newHospCapacity, setNewHospCapacity] = useState("250");
  const [newHospIcu, setNewHospIcu] = useState("30");
  const [addSuccess, setAddSuccess] = useState("");
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"analytics" | "hospitals" | "audit" | "system" | "model">("analytics");

  useEffect(() => {
    fetchAdminData();
    loadHospitalsList();
  }, []);

  useEffect(() => {
    if (selectedHospital) {
      loadHospitalForecasts(selectedHospital);
    }
  }, [selectedHospital]);

  const loadHospitalsList = async () => {
    try {
      const res = await api.get("/hospitals/public?limit=300");
      const list = res.data?.hospitals || [];
      setHospitalsList(list);
      if (list.length > 0 && !selectedHospital) {
        setSelectedHospital(list[0].hospital_id);
      }
    } catch {
      // silent
    }
  };

  const loadHospitalForecasts = async (hid: string) => {
    setChartLoading(true);
    try {
      const [fcRes, histRes] = await Promise.all([
        api.post("/predict", { hospital_ids: [hid], horizons: [1, 2, 3, 4] }),
        api.get("/forecast/history", { params: { hospitals: hid, days: 56 } }).catch(() => ({ data: { history: [] } })),
      ]);
      setChartForecasts(fcRes.data?.forecasts || []);
      setChartHistory(histRes.data?.history || []);
    } catch (err) {
      console.error("Failed to load forecast for admin chart", err);
    } finally {
      setChartLoading(false);
    }
  };

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [logsRes, statusRes, modelRes] = await Promise.all([
        api.get("/admin/access-logs", { params: { limit: 100 } }),
        api.get("/system/status"),
        api.get("/model-info").catch(() => ({ data: null })),
      ]);
      setLogs(logsRes.data?.access_logs || []);
      setStatus(statusRes.data || null);
      if (modelRes.data) setModelInfo(modelRes.data);
    } catch (err) {
      console.error("Failed to load admin data", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddHospital = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError("");
    setAddSuccess("");
    setAddLoading(true);

    try {
      const res = await api.post("/admin/hospitals", {
        hospital_id: newHospId.trim(),
        name: newHospName.trim(),
        region: newHospRegion.trim(),
        capacity: parseInt(newHospCapacity) || 200,
        icu_capacity: parseInt(newHospIcu) || 20,
      });

      setAddSuccess(`Hospital ${res.data.hospital.hospital_id} (${res.data.hospital.name}) added successfully!`);
      setNewHospId("");
      setNewHospName("");
      // Refresh list
      loadHospitalsList();
      fetchAdminData();
    } catch (err: any) {
      setAddError(err.response?.data?.detail || "Failed to add hospital. Check ID formatting.");
    } finally {
      setAddLoading(false);
    }
  };

  const activeBedFc = chartForecasts.find(
    (f: any) => f.target === "inpatient_beds_used" && f.hospital_id === selectedHospital
  );

  return (
    <div className="min-h-screen bg-navy text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 pt-24 pb-16">
        <Container>
          {/* Header */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-amber-400/20 text-amber-300 border border-amber-400/30">
                  Super Admin
                </span>
                <span className="text-xs text-slate-400">System Monitoring & Hospital Network</span>
              </div>
              <h1 className="text-3xl font-bold text-white">Central Operations Center</h1>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  fetchAdminData();
                  loadHospitalsList();
                }}
                disabled={loading}
                className="btn-secondary !py-2 !px-3 text-xs flex items-center gap-2"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className={loading ? "animate-spin" : ""}
                >
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
                Sync Data
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="glass-card p-5 rounded-xl border border-white/5">
              <span className="text-xs uppercase text-slate-400 tracking-wider">Total Hospitals</span>
              <div className="text-2xl font-bold font-mono text-cyan mt-1">
                {status?.hospitals_count || hospitalsList.length || 1500}
              </div>
              <span className="text-xs text-slate-400 mt-1 block">Nationwide facilities in network</span>
            </div>

            <div className="glass-card p-5 rounded-xl border border-white/5">
              <span className="text-xs uppercase text-slate-400 tracking-wider">Model Serving Version</span>
              <div className="text-2xl font-bold font-mono text-teal mt-1">
                {status?.model_version || "2.0.0"}
              </div>
              <span className="text-xs text-slate-400 mt-1 block">Dual-target Weekly Forecasting</span>
            </div>

            <div className="glass-card p-5 rounded-xl border border-white/5">
              <span className="text-xs uppercase text-slate-400 tracking-wider">Audit Log Records</span>
              <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                {logs.length}
              </div>
              <span className="text-xs text-slate-400 mt-1 block">Tracked data reads across network</span>
            </div>

            <div className="glass-card p-5 rounded-xl border border-white/5">
              <span className="text-xs uppercase text-slate-400 tracking-wider">Forecast Cadence</span>
              <div className="text-2xl font-bold font-mono text-purple-400 mt-1">
                1 - 4 Weeks
              </div>
              <span className="text-xs text-slate-400 mt-1 block">Point + 10th/90th intervals</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex flex-wrap gap-2 border-b border-white/10 mb-6">
            <button
              onClick={() => setActiveTab("analytics")}
              className={`pb-3 px-4 text-sm font-medium transition-colors relative ${
                activeTab === "analytics" ? "text-cyan font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Network Forecast Analytics
              {activeTab === "analytics" && (
                <motion.div layoutId="adm-tab" className="absolute bottom-0 inset-x-0 h-0.5 bg-cyan" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("hospitals")}
              className={`pb-3 px-4 text-sm font-medium transition-colors relative ${
                activeTab === "hospitals" ? "text-cyan font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Manage & Add Hospitals
              {activeTab === "hospitals" && (
                <motion.div layoutId="adm-tab" className="absolute bottom-0 inset-x-0 h-0.5 bg-cyan" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              className={`pb-3 px-4 text-sm font-medium transition-colors relative ${
                activeTab === "audit" ? "text-cyan font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Access Audit Trail
              {activeTab === "audit" && (
                <motion.div layoutId="adm-tab" className="absolute bottom-0 inset-x-0 h-0.5 bg-cyan" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("model")}
              className={`pb-3 px-4 text-sm font-medium transition-colors relative ${
                activeTab === "model" ? "text-cyan font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Model Architecture
              {activeTab === "model" && (
                <motion.div layoutId="adm-tab" className="absolute bottom-0 inset-x-0 h-0.5 bg-cyan" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("system")}
              className={`pb-3 px-4 text-sm font-medium transition-colors relative ${
                activeTab === "system" ? "text-cyan font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Pipeline Health
              {activeTab === "system" && (
                <motion.div layoutId="adm-tab" className="absolute bottom-0 inset-x-0 h-0.5 bg-cyan" />
              )}
            </button>
          </div>

          {/* Tab: Network Analytics (Full Access to all hospital graphs) */}
          {activeTab === "analytics" && (
            <div className="space-y-6">
              <div className="glass-card p-6 rounded-xl border border-white/5">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      Cross-Network Hospital Forecaster
                    </h3>
                    <p className="text-xs text-slate-400">
                      Select any hospital across the nationwide dataset to evaluate predicted occupancy and admissions.
                    </p>
                  </div>

                  {/* Target Toggle */}
                  <div className="flex items-center gap-2 p-1 bg-white/5 rounded-lg border border-white/10">
                    <button
                      type="button"
                      onClick={() => setChartTarget("inpatient_beds_used")}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                        chartTarget === "inpatient_beds_used"
                          ? "bg-cyan text-navy shadow"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Occupancy (Beds)
                    </button>
                    <button
                      type="button"
                      onClick={() => setChartTarget("admissions")}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                        chartTarget === "admissions"
                          ? "bg-cyan text-navy shadow"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Demand (Admissions)
                    </button>
                  </div>
                </div>

                {/* Hospital Selector Dropdown */}
                <div className="max-w-md mb-6">
                  <label className="block text-xs uppercase tracking-widest text-cyan font-medium mb-2">
                    Active Hospital Facility
                  </label>
                  <select
                    value={selectedHospital}
                    onChange={(e) => setSelectedHospital(e.target.value)}
                    className="input-field text-sm cursor-pointer"
                  >
                    {hospitalsList.map((h) => (
                      <option key={h.hospital_id} value={h.hospital_id} className="bg-navy text-white">
                        {h.hospital_id} — {h.name} ({h.region})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Forecast Chart */}
                {chartLoading ? (
                  <div className="h-80 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-cyan border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <ContinuousTimelineChart
                    target={chartTarget}
                    hospitalId={selectedHospital}
                    history={chartHistory}
                    forecasts={chartForecasts}
                    capacity={activeBedFc?.resource_gap ? 300 : 200}
                    capacitySource={activeBedFc?.capacity_source}
                  />
                )}
              </div>
            </div>
          )}

          {/* Tab: Manage & Add Hospitals */}
          {activeTab === "hospitals" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 1 Col: Add Hospital Form */}
              <div className="glass-card p-6 rounded-xl border border-white/5 lg:col-span-1 h-fit">
                <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  Add New Hospital
                </h3>
                <p className="text-xs text-slate-400 mb-6">
                  Register a new healthcare facility in the forecasting database.
                </p>

                {addSuccess && (
                  <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
                    {addSuccess}
                  </div>
                )}
                {addError && (
                  <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
                    {addError}
                  </div>
                )}

                <form onSubmit={handleAddHospital} className="space-y-4">
                  <div>
                    <label className="block text-xs uppercase tracking-widest text-cyan mb-1.5 font-medium">
                      Hospital CCN / ID *
                    </label>
                    <input
                      type="text"
                      value={newHospId}
                      onChange={(e) => setNewHospId(e.target.value)}
                      required
                      placeholder="e.g. 990001"
                      className="input-field font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs uppercase tracking-widest text-cyan mb-1.5 font-medium">
                      Facility Name *
                    </label>
                    <input
                      type="text"
                      value={newHospName}
                      onChange={(e) => setNewHospName(e.target.value)}
                      required
                      placeholder="e.g. St. Jude Memorial Hospital"
                      className="input-field"
                    />
                  </div>

                  <div>
                    <label className="block text-xs uppercase tracking-widest text-cyan mb-1.5 font-medium">
                      State / Region
                    </label>
                    <input
                      type="text"
                      value={newHospRegion}
                      onChange={(e) => setNewHospRegion(e.target.value)}
                      placeholder="e.g. CA or NY"
                      className="input-field"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs uppercase tracking-widest text-cyan mb-1.5 font-medium">
                        Bed Capacity
                      </label>
                      <input
                        type="number"
                        value={newHospCapacity}
                        onChange={(e) => setNewHospCapacity(e.target.value)}
                        min={10}
                        max={5000}
                        className="input-field font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs uppercase tracking-widest text-cyan mb-1.5 font-medium">
                        ICU Beds
                      </label>
                      <input
                        type="number"
                        value={newHospIcu}
                        onChange={(e) => setNewHospIcu(e.target.value)}
                        min={0}
                        max={1000}
                        className="input-field font-mono"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={addLoading}
                    className="w-full btn-primary !py-2.5 text-xs font-semibold mt-2"
                  >
                    {addLoading ? "Creating..." : "Register Hospital"}
                  </button>
                </form>
              </div>

              {/* Right 2 Cols: Hospital Directory */}
              <div className="glass-card p-6 rounded-xl border border-white/5 lg:col-span-2">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">Active Hospital Directory</h3>
                    <p className="text-xs text-slate-400">
                      Listing first {hospitalsList.length} network facilities
                    </p>
                  </div>
                  <span className="px-2.5 py-1 bg-white/5 border border-white/10 rounded font-mono text-xs text-cyan">
                    Total: {status?.hospitals_count || 1500}
                  </span>
                </div>

                <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-white/5 text-slate-300 uppercase tracking-wider font-semibold sticky top-0">
                      <tr>
                        <th className="py-2.5 px-3">CCN / ID</th>
                        <th className="py-2.5 px-3">Facility Name</th>
                        <th className="py-2.5 px-3">Region</th>
                        <th className="py-2.5 px-3">Capacity</th>
                        <th className="py-2.5 px-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 font-mono">
                      {hospitalsList.slice(0, 100).map((h) => (
                        <tr key={h.hospital_id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="py-2.5 px-3 text-cyan">{h.hospital_id}</td>
                          <td className="py-2.5 px-3 font-sans text-slate-200">{h.name}</td>
                          <td className="py-2.5 px-3 text-slate-400">{h.region}</td>
                          <td className="py-2.5 px-3 text-emerald-400">{h.capacity} beds</td>
                          <td className="py-2.5 px-3">
                            <button
                              onClick={() => {
                                setSelectedHospital(h.hospital_id);
                                setActiveTab("analytics");
                              }}
                              className="px-2 py-0.5 rounded bg-cyan/10 text-cyan hover:bg-cyan/20 border border-cyan/30 text-[10px] font-sans transition-colors"
                            >
                              Inspect Graph
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab 1: Access Audit Trail */}
          {activeTab === "audit" && (
            <div className="glass-card rounded-xl border border-white/5 overflow-hidden">
              <div className="p-4 border-b border-white/5 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Real-Time Audit Records ({logs.length})
                </span>
                <span className="text-xs text-slate-400">Captures every hospital data read</span>
              </div>
              <div className="overflow-x-auto max-h-[550px] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white/5 text-slate-300 uppercase tracking-wider font-semibold sticky top-0">
                    <tr>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4">User Email</th>
                      <th className="py-3 px-4">Hospital Scoped</th>
                      <th className="py-3 px-4">Endpoint</th>
                      <th className="py-3 px-4">Parameters</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {logs.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-slate-400">
                          No access log records found yet.
                        </td>
                      </tr>
                    ) : (
                      logs.map((l) => (
                        <tr key={l.id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                            {new Date(l.timestamp).toLocaleString()}
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-200">
                            {l.user_email || "Anonymous"}
                          </td>
                          <td className="py-3 px-4">
                            <span className="px-2 py-0.5 rounded bg-cyan/10 text-cyan border border-cyan/20 font-mono text-[11px]">
                              {l.hospital_id || "ALL"}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono text-emerald-400">
                            {l.endpoint}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-400 truncate max-w-xs">
                            {l.query_params || "None"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 2: Model Info */}
          {activeTab === "model" && (
            <div className="glass-card p-6 rounded-xl border border-white/5">
              <h3 className="text-lg font-semibold text-white mb-4">Model Bundle V2 Architecture</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-xs uppercase tracking-wider text-cyan mb-2">Specifications</h4>
                  <ul className="space-y-2 text-sm text-slate-300">
                    <li><strong className="text-white">Version:</strong> {modelInfo?.version || "2.0.0"}</li>
                    <li><strong className="text-white">Horizons:</strong> 1, 2, 3, 4 Weeks</li>
                    <li><strong className="text-white">Targets:</strong> Dual (<code>admissions</code> + <code>inpatient_beds_used</code>)</li>
                    <li><strong className="text-white">Quantiles:</strong> 10th (Low), 50th (Point), 90th (High)</li>
                    <li><strong className="text-white">Methodology:</strong> Residual on 4-Week Moving Average (MA4)</li>
                    <li><strong className="text-white">Resource Guard:</strong> 85% Safe Capacity with Historical Median Fallback</li>
                  </ul>
                </div>
                <div>
                  <h4 className="text-xs uppercase tracking-wider text-cyan mb-2">Feature Set ({modelInfo?.feature_count || 19})</h4>
                  <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
                    {(modelInfo?.feature_columns || []).map((col) => (
                      <span key={col} className="px-2 py-1 bg-white/5 border border-white/10 rounded font-mono text-xs text-slate-300">
                        {col}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 3: System Status */}
          {activeTab === "system" && (
            <div className="glass-card p-6 rounded-xl border border-white/5">
              <h3 className="text-lg font-semibold text-white mb-4">Pipeline Status</h3>
              <div className="space-y-3 text-sm text-slate-300">
                <div className="flex justify-between py-2 border-b border-white/5">
                  <span>Last Forecast Run:</span>
                  <span className="font-mono text-cyan">{status?.last_forecast_run ? new Date(status.last_forecast_run).toLocaleString() : "Active"}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-white/5">
                  <span>Last Base Signal Date:</span>
                  <span className="font-mono text-slate-200">{status?.last_signal_update || "2024-04-21"}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-white/5">
                  <span>Active Database Hospitals:</span>
                  <span className="font-mono text-emerald-400">{status?.hospitals_count || 1489}</span>
                </div>
              </div>
            </div>
          )}
        </Container>
      </main>

      <Footer />
    </div>
  );
}
