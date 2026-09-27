"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/layout/Navbar";
import api, { getApiErrorMessage } from "@/lib/api";
import { getUserHospitalIds, getUserRole } from "@/lib/auth";

interface Message {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  hospital?: string;
  time?: number;
}

interface HospitalItem {
  hospital_id: string;
  name: string;
  region: string;
  capacity?: number;
}

const CLINICAL_SUGGESTIONS = [
  "Why is inpatient bed occupancy rising over the 4-week forecast horizon?",
  "Will our facility exceed the 85% safe capacity threshold in the coming weeks?",
  "Explain the 80% confidence interval bounds and risk of admission surge",
  "Summarize how external signals (flu, COVID, weather) are affecting demand",
];

export default function AgentPage() {
  return (
    <ProtectedRoute>
      <AgentContent />
    </ProtectedRoute>
  );
}

function AgentContent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hospitals, setHospitals] = useState<HospitalItem[]>([]);
  const [selectedHospital, setSelectedHospital] = useState<string>("10001");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadHospitals();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadHospitals = async () => {
    try {
      const res = await api.get("/hospitals");
      let items: HospitalItem[] = res.data.items || [];
      const userRole = getUserRole();
      const assigned = getUserHospitalIds();

      if (userRole === "hospital_staff" && assigned.length > 0) {
        items = items.filter((h) => assigned.includes(h.hospital_id));
      }

      setHospitals(items);
      if (items.length > 0) {
        setSelectedHospital(items[0].hospital_id);
      }
    } catch {
      // silent fallback
    }
  };

  const sendQuery = async (question: string) => {
    if (!question.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.post("/agent/query", {
        question,
        hospital_id: selectedHospital,
      });
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: res.data.analysis,
        hospital: res.data.hospital,
        time: res.data.inference_time_seconds,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "error",
        content: getApiErrorMessage(err, "Failed to get analysis. Please try again."),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendQuery(input);
  };

  const activeHospitalItem = hospitals.find((h) => h.hospital_id === selectedHospital);

  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-4xl w-full mx-auto px-4 md:px-8 pt-24 pb-6 flex flex-col">
        {/* Header with Hospital Focus Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/5"
        >
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan animate-pulse" />
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="gradient-text">AI Forecast Analyst</span>
              </h1>
            </div>
            <p className="text-slate-400 text-xs mt-1">
              Grounded in live 4-week dual-target LightGBM models, 80% CI quantiles, and epidemiological signals.
            </p>
          </div>

          {/* Facility Context Selector */}
          <div className="flex items-center gap-2 bg-navy-light/60 border border-white/10 rounded-xl px-3 py-1.5 self-start sm:self-auto">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Facility:</span>
            <select
              value={selectedHospital}
              onChange={(e) => setSelectedHospital(e.target.value)}
              className="bg-transparent text-xs text-cyan font-mono font-medium focus:outline-none cursor-pointer max-w-[200px] truncate"
            >
              {hospitals.map((h) => (
                <option key={h.hospital_id} value={h.hospital_id} className="bg-navy text-slate-200">
                  {h.hospital_id} — {h.name} ({h.region})
                </option>
              ))}
            </select>
          </div>
        </motion.div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0 pr-1">
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.15 }}
              className="flex flex-col items-center justify-center h-full py-12"
            >
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan/20 to-blue-600/20 border border-cyan/30 flex items-center justify-center mb-4 shadow-lg shadow-cyan/10">
                <svg
                  width="26"
                  height="26"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  className="text-cyan"
                >
                  <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
                  <path d="M10 21h4" />
                  <path d="M9 17v2" />
                  <path d="M15 17v2" />
                </svg>
              </div>

              <h2 className="text-base font-semibold text-slate-200 mb-1">
                Operational Clinical Intelligence
              </h2>
              <p className="text-slate-400 text-xs mb-6 text-center max-w-md">
                Analyzing{" "}
                <span className="text-cyan font-mono font-medium">
                  {activeHospitalItem ? `${activeHospitalItem.name} (${activeHospitalItem.hospital_id})` : selectedHospital}
                </span>
                . Select a clinical scenario below or type a query:
              </p>

              {/* Clinical Prompt Suggestions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl">
                {CLINICAL_SUGGESTIONS.map((promptText, i) => (
                  <button
                    key={i}
                    onClick={() => sendQuery(promptText)}
                    className="text-left text-xs text-slate-300 glass-card rounded-xl p-3 hover:border-cyan/40 hover:text-cyan transition-all group flex flex-col justify-between gap-2 shadow-sm"
                  >
                    <span>{promptText}</span>
                    <span className="text-[10px] text-slate-500 group-hover:text-cyan/70 font-mono">
                      Ask agent &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "user" ? (
                  <div className="max-w-[80%] bg-gradient-to-r from-cyan/20 to-blue-600/20 border border-cyan/30 rounded-2xl rounded-br-sm px-4 py-3 shadow-md">
                    <p className="text-sm text-slate-100">{msg.content}</p>
                  </div>
                ) : msg.role === "error" ? (
                  <div className="max-w-[85%] bg-red-500/10 border border-red-500/20 rounded-2xl rounded-bl-sm px-4 py-3">
                    <p className="text-sm text-red-400">{msg.content}</p>
                  </div>
                ) : (
                  <div className="max-w-[90%] glass-card rounded-2xl rounded-bl-sm px-5 py-4 shadow-lg border border-white/10">
                    <div className="flex items-center justify-between gap-3 mb-3 pb-2 border-b border-white/5">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan/15 text-cyan border border-cyan/20">
                          Hospital {msg.hospital || selectedHospital}
                        </span>
                        <span className="text-[10px] text-slate-400">Groq Production LLM</span>
                      </div>
                      {msg.time !== undefined && (
                        <span className="text-[10px] text-slate-500 font-mono">
                          {msg.time.toFixed(2)}s inference
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap font-sans">
                      {msg.content}
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="glass-card rounded-2xl rounded-bl-sm px-4 py-3 border border-cyan/20">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <span className="w-2 h-2 bg-cyan rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-cyan rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-cyan rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-xs text-slate-400 font-medium">
                    Retrieving forecast quantiles & analyzing risk...
                  </span>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <motion.form
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          onSubmit={handleSubmit}
          className="flex gap-2 items-center"
        >
          <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask about hospital ${selectedHospital} (e.g., Will we exceed 85% capacity in week 3?)...`}
              disabled={loading}
              className="w-full px-4 py-3.5 glass-card rounded-xl text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan/50 disabled:opacity-50 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-5 py-3.5 bg-gradient-to-r from-cyan to-teal text-navy font-semibold rounded-xl hover:shadow-lg hover:shadow-cyan/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0 flex items-center justify-center"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-navy border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            )}
          </button>
        </motion.form>
      </div>
    </main>
  );
}
