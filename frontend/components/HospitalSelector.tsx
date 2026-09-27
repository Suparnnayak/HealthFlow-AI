"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";

export interface HospitalInfo {
  name: string;
  region: string;
  capacity?: number;
}

interface Props {
  hospitals: string[];
  hospitalMap?: Record<string, HospitalInfo>;
  selected: string[];
  onChange: (ids: string[]) => void;
}

export default function HospitalSelector({ hospitals, hospitalMap, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [filterText, setFilterText] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setFilterText("");
    }
  }, [open]);

  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  };

  const filteredHospitals = useMemo(() => {
    const q = filterText.trim().toLowerCase();
    if (!q) return hospitals.slice(0, 100);

    return hospitals
      .filter((id) => {
        const info = hospitalMap?.[id];
        return (
          id.toLowerCase().includes(q) ||
          (info?.name && info.name.toLowerCase().includes(q)) ||
          (info?.region && info.region.toLowerCase().includes(q))
        );
      })
      .slice(0, 100);
  }, [hospitals, hospitalMap, filterText]);

  return (
    <div ref={ref} className="relative w-full">
      <label className="block text-xs uppercase tracking-widest text-cyan mb-2 font-medium">
        Select Hospitals
      </label>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full glass-card px-4 py-3 text-left flex items-center justify-between rounded-lg hover:border-cyan/30 transition-all cursor-pointer"
      >
        <span className="text-sm text-slate-200">
          {selected.length === 0
            ? "Choose hospitals to forecast..."
            : `${selected.length} hospital${selected.length > 1 ? "s" : ""} selected`}
        </span>
        <motion.svg
          animate={{ rotate: open ? 180 : 0 }}
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-slate-400"
        >
          <polyline points="6 9 12 15 18 9" />
        </motion.svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute z-30 mt-2 w-full glass-card p-3 max-h-80 flex flex-col rounded-xl shadow-2xl border border-white/10 backdrop-blur-xl"
          >
            {/* Quick search input */}
            <div className="mb-2 relative">
              <input
                ref={searchInputRef}
                type="text"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Search by ID, name or state..."
                className="w-full px-3 py-2 text-xs bg-navy-dark/80 border border-white/10 rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan/40"
              />
              {filterText && (
                <button
                  type="button"
                  onClick={() => setFilterText("")}
                  className="absolute right-2.5 top-2 text-slate-500 hover:text-slate-300 text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            {/* List */}
            <div className="overflow-y-auto flex-1 space-y-1 pr-1">
              {filteredHospitals.length === 0 ? (
                <div className="py-4 text-center text-xs text-slate-500">
                  No matching hospitals found
                </div>
              ) : (
                filteredHospitals.map((h) => {
                  const info = hospitalMap?.[h];
                  const isSelected = selected.includes(h);
                  return (
                    <button
                      key={h}
                      type="button"
                      onClick={() => toggle(h)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left text-xs transition-all ${
                        isSelected
                          ? "bg-cyan/15 text-cyan border border-cyan/25"
                          : "text-slate-300 hover:bg-white/5 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        <div
                          className={`w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                            isSelected ? "border-cyan bg-cyan text-navy" : "border-slate-500"
                          }`}
                        >
                          {isSelected && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </div>
                        <span className="font-mono font-semibold text-cyan/90">{h}</span>
                        {info && (
                          <span className="text-slate-300 truncate">
                            — {info.name}
                          </span>
                        )}
                      </div>
                      {info?.region && (
                        <span className="text-[10px] font-mono text-slate-500 px-1.5 py-0.5 rounded bg-white/5 flex-shrink-0">
                          {info.region}
                        </span>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {selected.map((h) => {
            const info = hospitalMap?.[h];
            return (
              <motion.span
                key={h}
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-cyan/10 text-cyan border border-cyan/25 rounded-lg max-w-[280px]"
              >
                <span className="font-mono font-semibold">{h}</span>
                {info && <span className="truncate text-slate-300 text-[11px]">— {info.name}</span>}
                <button
                  type="button"
                  onClick={() => toggle(h)}
                  className="hover:text-white transition-colors text-slate-400 ml-1 text-sm font-bold"
                >
                  ×
                </button>
              </motion.span>
            );
          })}
        </div>
      )}
    </div>
  );
}
