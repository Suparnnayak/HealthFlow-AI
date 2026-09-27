"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Container from "@/components/layout/Container";
import api from "@/lib/api";

interface HospitalRow {
  hospital_id: string;
  name: string | null;
  region: string | null;
  capacity: number | null;
  icu_capacity?: number | null;
}

const PAGE_SIZE = 25;

export default function HospitalsPage() {
  return (
    <ProtectedRoute>
      <HospitalsContent />
    </ProtectedRoute>
  );
}

function HospitalsContent() {
  const router = useRouter();
  const [hospitals, setHospitals] = useState<HospitalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    loadHospitals();
  }, []);

  const loadHospitals = async () => {
    try {
      const res = await api.get("/hospitals");
      const items: HospitalRow[] = res.data?.items || [];
      if (items.length > 0) {
        setHospitals(items);
      } else {
        const ids: string[] = res.data?.hospitals || [];
        const rows: HospitalRow[] = ids.map((id) => ({
          hospital_id: id,
          name: `Hospital ${id}`,
          region: null,
          capacity: 200,
        }));
        setHospitals(rows);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const filtered = hospitals.filter((h) => {
    const q = search.toLowerCase().trim();
    if (!q) return true;
    return (
      h.hospital_id.toLowerCase().includes(q) ||
      (h.name && h.name.toLowerCase().includes(q)) ||
      (h.region && h.region.toLowerCase().includes(q))
    );
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const paginated = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated">
      <Navbar />

      <div className="pt-20 pb-12">
        <Container>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8 pt-4 flex flex-col sm:flex-row justify-between sm:items-end gap-4"
          >
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan/10 text-cyan border border-cyan/20">
                  Facility Directory
                </span>
                <span className="text-xs text-slate-400">
                  {hospitals.length} healthcare facilities monitored
                </span>
              </div>
              <h1 className="text-3xl font-bold text-white">Hospital Network</h1>
              <p className="text-slate-400 mt-1 text-sm">
                Browse hospital facilities and launch 4-week dual-target capacity forecasts.
              </p>
            </div>

            {/* Search Input */}
            <div className="w-full sm:w-80">
              <input
                type="text"
                placeholder="Search by facility name, CCN, or state..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setCurrentPage(1);
                }}
                className="input-field !py-2 text-sm"
              />
            </div>
          </motion.div>

          {/* Table Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card rounded-xl overflow-hidden border border-white/5"
          >
            {loading ? (
              <div className="p-8 space-y-3">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/5 bg-white/[0.02]">
                      <th className="px-6 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Hospital CCN / ID
                      </th>
                      <th className="px-6 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Facility Name
                      </th>
                      <th className="px-6 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Region
                      </th>
                      <th className="px-6 py-3.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Licensed Beds
                      </th>
                      <th className="px-6 py-3.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {paginated.map((h, i) => (
                      <tr
                        key={h.hospital_id}
                        onClick={() => router.push(`/dashboard?hospital=${h.hospital_id}`)}
                        className="hover:bg-white/[0.03] transition-colors cursor-pointer group"
                      >
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono font-medium text-cyan">
                            {h.hospital_id}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm font-medium text-slate-200">
                          {h.name || `Hospital ${h.hospital_id}`}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300 font-mono text-xs">
                            {h.region || "US"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-right text-emerald-400 font-mono">
                          {h.capacity ? `${h.capacity} beds` : "200 beds"}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/dashboard?hospital=${h.hospital_id}`);
                            }}
                            className="btn-secondary !py-1.5 !px-3 text-xs text-cyan hover:border-cyan transition-all"
                          >
                            View Forecast →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {filtered.length === 0 && (
                  <div className="p-12 text-center text-slate-400 text-sm">
                    No hospitals found matching &quot;{search}&quot;.
                  </div>
                )}
              </div>
            )}

            {/* Pagination Controls */}
            {!loading && totalPages > 1 && (
              <div className="px-6 py-4 border-t border-white/5 flex items-center justify-between text-xs text-slate-400 bg-white/[0.01]">
                <span>
                  Showing {(safePage - 1) * PAGE_SIZE + 1} to{" "}
                  {Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length} hospitals
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={safePage === 1}
                    className="px-3 py-1.5 rounded-lg border border-white/10 hover:bg-white/5 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                  >
                    Previous
                  </button>
                  <span className="font-mono text-slate-300">
                    Page {safePage} of {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={safePage === totalPages}
                    className="px-3 py-1.5 rounded-lg border border-white/10 hover:bg-white/5 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </Container>
      </div>

      <Footer />
    </main>
  );
}

