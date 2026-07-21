import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Capabilities, DashboardData } from "../api";
import { formatCurrency, monthLabel } from "../lib/format";
import AnimatedNumber from "./AnimatedNumber";
import AnomaliesPanel from "./AnomaliesPanel";
import CategoryChart from "./CategoryChart";
import ChatPanel from "./ChatPanel";
import DebatePanel from "./DebatePanel";
import ErrorBoundary from "./ErrorBoundary";
import ExplainabilityPanel from "./ExplainabilityPanel";
import GoalPlannerPanel from "./GoalPlannerPanel";
import MemoryPanel from "./MemoryPanel";
import ForecastChart from "./ForecastChart";
import HealthScorePanel from "./HealthScorePanel";
import RetrievalPanel from "./RetrievalPanel";
import RoutingPanel from "./RoutingPanel";
import WorkflowPanel from "./WorkflowPanel";
import SavingsPanel from "./SavingsPanel";
import TwinPanel from "./TwinPanel";
import VoiceAssistant from "./VoiceAssistant";
import WhatIfPanel from "./WhatIfPanel";

function StatCard({
  label,
  value,
  accent,
  delay,
  currency,
}: {
  label: string;
  value: number;
  accent: string;
  delay: number;
  currency: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass rounded-2xl p-4 relative overflow-hidden group hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
    >
      <div 
        className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-300 pointer-events-none"
        style={{ background: `radial-gradient(circle at top right, ${accent}, transparent 70%)` }}
      />
      <p className="text-[11px] uppercase tracking-wider text-slate-400 relative z-10">{label}</p>
      <p className="mt-1 text-2xl font-extrabold relative z-10 font-display tracking-tight" style={{ color: accent }}>
        <AnimatedNumber value={value} format={(n) => formatCurrency(n, { currency })} />
      </p>
    </motion.div>
  );
}

type Tab = "overview" | "planning" | "copilot" | "diagnostics";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "planning", label: "Planning" },
  { id: "copilot", label: "AI Copilot" },
  { id: "diagnostics", label: "Diagnostics" },
];

export default function Dashboard({
  data,
  capabilities,
}: {
  data: DashboardData;
  capabilities: Capabilities | null;
}) {
  const hs = data.health_score;
  const ref = hs.reference_month;
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  return (
    <div className="ambient-bg min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-6">
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mb-4 text-sm text-slate-400"
        >
          {data.monthly_summary.timeline ? (
            <>Statement Period: {data.monthly_summary.timeline.start_date} to {data.monthly_summary.timeline.end_date} ({data.monthly_summary.timeline.duration_days} days)</>
          ) : (
            <>Analysis based on {data.monthly_summary.months.length} months</>
          )}
          {ref && ` · latest: ${monthLabel(ref)}`}
        </motion.p>

        {/* Tabs */}
        <div className="mb-6 flex space-x-2 overflow-x-auto rounded-xl bg-navy-800/60 p-1.5 backdrop-blur-md sm:w-fit border border-white/5 shadow-inner">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id ? "text-navy-900" : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              {activeTab === tab.id && (
                <motion.div
                  layoutId="active-tab"
                  className="absolute inset-0 rounded-lg bg-gradient-to-r from-teal-400 to-teal-300 shadow-sm"
                  initial={false}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span className="relative z-10">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Top stat strip - only visible on Overview */}
        <AnimatePresence mode="popLayout">
          {activeTab === "overview" && (
            <motion.div 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4"
            >
              <StatCard label="Avg Monthly Income" value={hs.income} accent="#4ade80" delay={0.05} currency={data.monthly_summary.dominant_currency} />
              <StatCard label="Avg Monthly Expenses" value={hs.expenses} accent="#fb923c" delay={0.1} currency={data.monthly_summary.dominant_currency} />
              <StatCard
                label="Avg Monthly Surplus"
                value={hs.income - hs.expenses}
                accent="#2dd4bf"
                delay={0.15}
                currency={data.monthly_summary.dominant_currency}
              />
              <StatCard
                label="Next month forecast"
                value={data.forecast.total_expense_forecast}
                accent="#a78bfa"
                delay={0.2}
                currency={data.monthly_summary.dominant_currency}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main grid */}
        <div className="grid gap-4 lg:grid-cols-3">
          {activeTab === "overview" && (
            <>
              <HealthScorePanel hs={hs} delay={0.25} />
              <div className="lg:col-span-2">
                <CategoryChart
                  summary={data.monthly_summary}
                  transactions={data.transactions}
                  delay={0.3}
                />
              </div>

              <div className="lg:col-span-2">
                <ForecastChart forecast={data.forecast} delay={0.35} />
              </div>
              <AnomaliesPanel anomalies={data.anomalies} delay={0.4} />

              <SavingsPanel suggestions={data.savings_suggestions} delay={0.45} />
            </>
          )}

          {activeTab === "planning" && (
            <>
              <div className="lg:col-span-3">
                <GoalPlannerPanel delay={0.1} />
              </div>

              <div className="lg:col-span-3">
                <WhatIfPanel data={data} delay={0.2} />
              </div>

              <div className="lg:col-span-3">
                <TwinPanel delay={0.3} />
              </div>
            </>
          )}

          {activeTab === "copilot" && (
            <>
              <div className="lg:col-span-3">
                <ChatPanel capabilities={capabilities} delay={0.1} />
              </div>
            </>
          )}

          {activeTab === "diagnostics" && (
            <>
              <div className="lg:col-span-3">
                <ExplainabilityPanel delay={0.1} />
              </div>

              <div className="lg:col-span-3">
                <WorkflowPanel delay={0.2} />
              </div>

              <div className="lg:col-span-3">
                <RoutingPanel delay={0.3} />
              </div>

              <div className="lg:col-span-3">
                <RetrievalPanel delay={0.4} />
              </div>

              <div className="lg:col-span-3">
                <MemoryPanel delay={0.5} />
              </div>

              <div className="lg:col-span-3">
                <DebatePanel delay={0.6} />
              </div>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          All figures are computed deterministically from your statement. The AI
          assistant explains them — it never invents numbers.
        </p>
      </div>

      {/* Floating voice-assistant launcher */}
      <motion.button
        onClick={() => setVoiceOpen(true)}
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.6 }}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        title="Talk to your CFO"
        className="fixed bottom-6 right-6 z-40 flex h-16 w-16 items-center justify-center rounded-full border border-teal-400/40 bg-navy-900/80 text-2xl backdrop-blur shadow-glow animate-pulseGlow"
      >
        <span
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "radial-gradient(circle at 50% 50%, rgba(56,189,248,0.25), transparent 70%)",
          }}
        />
        <span className="relative">🎙️</span>
      </motion.button>

      <AnimatePresence>
        {voiceOpen && (
          <ErrorBoundary
            fallback={
              <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-navy-900/95 px-6 text-center">
                <p className="text-lg text-slate-100">
                  The voice assistant couldn't start on this device.
                </p>
                <p className="mt-2 max-w-md text-sm text-slate-400">
                  Your browser may not support WebGL/microphone access. You can
                  still ask questions using the chat box below.
                </p>
                <button
                  onClick={() => setVoiceOpen(false)}
                  className="mt-5 rounded-xl bg-teal-accent px-5 py-2.5 text-sm font-semibold text-navy-900"
                >
                  Close
                </button>
              </div>
            }
          >
            <VoiceAssistant
              capabilities={capabilities}
              onClose={() => setVoiceOpen(false)}
            />
          </ErrorBoundary>
        )}
      </AnimatePresence>
    </div>
  );
}
