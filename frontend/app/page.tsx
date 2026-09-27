"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Container from "@/components/layout/Container";

/* ───────── Animation helpers ───────── */
const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  }),
};

/* ───────── Feature cards data ───────── */
const FEATURES = [
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 3v18h18" />
        <path d="M7 16l4-8 4 4 4-10" />
      </svg>
    ),
    title: "Precomputed Forecasting",
    desc: "4-week dual-target predictions (demand & occupancy) powered by LightGBM, precomputed weekly with 10th-90th quantile intervals. Sub-second API response times.",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    title: "External Signal Intelligence",
    desc: "Live weather, AQI, outbreak indices, and mobility data from Open-Meteo — automatically correlated with admission patterns.",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
        <path d="M10 21h4" />
      </svg>
    ),
    title: "AI Agent Insights",
    desc: "Groq-powered LLM analyst explains trends, identifies drivers, and provides actionable staffing recommendations using real DB data.",
  },
];

/* ───────── Architecture steps ───────── */
const ARCH_STEPS = [
  { label: "GitHub Actions", sub: "Daily cron jobs" },
  { label: "Neon PostgreSQL", sub: "Source of truth" },
  { label: "FastAPI on Vercel", sub: "Serverless API" },
  { label: "Next.js Frontend", sub: "React SPA" },
  { label: "Groq Agent", sub: "LLM reasoning" },
];

/* ───────── Tech highlights ───────── */
const TECH_POINTS = [
  "Serverless FastAPI deployed on Vercel",
  "Neon PostgreSQL with UPSERT-based idempotent writes",
  "Automated weekly model retraining pipeline",
  "Groq LLM integration for forecast explanations",
  "JWT-secured API with role-based access",
  "Open-Meteo for free weather & AQI signals",
  "LightGBM ensemble model with cross-validation",
  "Zero-CSV production architecture",
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-navy grid-overlay bg-gradient-animated">
      <Navbar />

      {/* ═══════ HERO ═══════ */}
      <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-28 overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-gradient-radial from-cyan/5 to-transparent blur-3xl pointer-events-none" />

        <Container className="relative">
          <div className="text-center max-w-4xl mx-auto">
            <motion.div
              initial="hidden"
              animate="visible"
              variants={fadeUp}
              custom={0}
            >
              <span className="badge-info mb-4 inline-block">
                Open-Source Healthcare AI Platform
              </span>
            </motion.div>

            <motion.h1
              initial="hidden"
              animate="visible"
              variants={fadeUp}
              custom={1}
              className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tight"
            >
              AI-Driven Hospital
              <br />
              <span className="gradient-text">Operations Intelligence</span>
            </motion.h1>

            <motion.p
              initial="hidden"
              animate="visible"
              variants={fadeUp}
              custom={2}
              className="mt-6 text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed"
            >
              Forecast admissions and inpatient occupancy 4 weeks ahead with ML-powered quantiles,
              capacity-guarded safety thresholds, and hospital-scoped role governance.
            </motion.p>

            <motion.div
              initial="hidden"
              animate="visible"
              variants={fadeUp}
              custom={3}
              className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3"
            >
              <Link href="/register" className="btn-primary text-base">
                Get Started Free
              </Link>
              <Link href="/about" className="btn-secondary text-base">
                Learn More
              </Link>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* ═══════ FEATURES ═══════ */}
      <section className="py-20">
        <Container>
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            className="text-center mb-12"
          >
            <motion.h2 variants={fadeUp} custom={0} className="text-3xl font-bold">
              Core <span className="gradient-text">Capabilities</span>
            </motion.h2>
            <motion.p variants={fadeUp} custom={1} className="mt-3 text-slate-400 max-w-xl mx-auto">
              Three pillars powering smarter hospital decisions
            </motion.p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fadeUp}
                custom={i + 1}
                className="glass-card-hover rounded-2xl p-6"
              >
                <div className="w-12 h-12 rounded-xl bg-cyan/10 border border-cyan/20 flex items-center justify-center text-cyan mb-4">
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </Container>
      </section>

      {/* ═══════ ARCHITECTURE ═══════ */}
      <section className="py-20 border-t border-white/5">
        <Container>
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            className="text-center mb-12"
          >
            <motion.h2 variants={fadeUp} custom={0} className="text-3xl font-bold">
              System <span className="gradient-text">Architecture</span>
            </motion.h2>
            <motion.p variants={fadeUp} custom={1} className="mt-3 text-slate-400 max-w-xl mx-auto">
              End-to-end pipeline from data ingestion to AI-powered insights
            </motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="flex flex-col md:flex-row items-center justify-center gap-3 md:gap-0"
          >
            {ARCH_STEPS.map((step, i) => (
              <motion.div key={step.label} variants={fadeUp} custom={i + 1} className="flex items-center">
                <div className="glass-card rounded-xl px-5 py-4 text-center min-w-[150px]">
                  <div className="text-sm font-semibold text-slate-200">{step.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{step.sub}</div>
                </div>
                {i < ARCH_STEPS.length - 1 && (
                  <svg width="32" height="16" viewBox="0 0 32 16" className="text-cyan/40 mx-1 hidden md:block flex-shrink-0">
                    <path d="M0 8h28M24 3l6 5-6 5" stroke="currentColor" strokeWidth="1.5" fill="none" />
                  </svg>
                )}
              </motion.div>
            ))}
          </motion.div>
        </Container>
      </section>

      {/* ═══════ TECHNICAL HIGHLIGHTS ═══════ */}
      <section className="py-20 border-t border-white/5">
        <Container>
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.3 }}
            >
              <motion.h2 variants={fadeUp} custom={0} className="text-3xl font-bold">
                Technical <span className="gradient-text">Highlights</span>
              </motion.h2>
              <motion.p variants={fadeUp} custom={1} className="mt-3 text-slate-400">
                Production-grade infrastructure designed for reliability and scale.
              </motion.p>
            </motion.div>

            <motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              className="grid grid-cols-1 sm:grid-cols-2 gap-3"
            >
              {TECH_POINTS.map((point, i) => (
                <motion.div
                  key={i}
                  variants={fadeUp}
                  custom={i * 0.5}
                  className="flex items-start gap-2.5 p-3 rounded-lg hover:bg-white/[0.02] transition-colors"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-cyan flex-shrink-0 mt-0.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span className="text-sm text-slate-300">{point}</span>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </Container>
      </section>

      {/* ═══════ CTA ═══════ */}
      <section className="py-20 border-t border-white/5">
        <Container>
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            className="glass-card rounded-2xl p-8 sm:p-12 text-center relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-cyan/5 to-teal/5 pointer-events-none" />
            <motion.h2 variants={fadeUp} custom={0} className="relative text-3xl font-bold">
              Ready to Transform Hospital Operations?
            </motion.h2>
            <motion.p variants={fadeUp} custom={1} className="relative mt-4 text-slate-400 max-w-lg mx-auto">
              Start using AI-powered admission forecasting and operational intelligence today.
            </motion.p>
            <motion.div variants={fadeUp} custom={2} className="relative mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/register" className="btn-primary text-base">
                Create Free Account
              </Link>
              <Link href="/dashboard" className="btn-secondary text-base">
                View Demo Dashboard
              </Link>
            </motion.div>
          </motion.div>
        </Container>
      </section>

      <Footer />
    </main>
  );
}
