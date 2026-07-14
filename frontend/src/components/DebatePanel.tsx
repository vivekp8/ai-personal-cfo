import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AgentOpinion, DebateResult, runDebate } from "../api";
import GlassCard from "./GlassCard";

function confColor(c: number): string {
  if (c >= 0.75) return "#2dd4bf";
  if (c >= 0.5) return "#38bdf8";
  return "#f59e0b";
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
      <motion.div
        className="h-full rounded-full"
        style={{ background: confColor(value) }}
        initial={{ width: 0 }}
        animate={{ width: `${Math.round(value * 100)}%` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
    </div>
  );
}

function OpinionCard({ op, index }: { op: AgentOpinion; index: number }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, rotateX: -12 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ delay: index * 0.08, type: "spring", stiffness: 120, damping: 16 }}
      whileHover={{ rotateY: 6, rotateX: -4, translateZ: 20, scale: 1.02 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      onClick={() => setFlipped((f) => !f)}
      className="cursor-pointer rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur transition-colors hover:border-teal-accent/40"
    >
      <div className="flex items-center gap-2">
        <span className="text-xl">{op.icon}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-100">{op.agent}</p>
          <p className="truncate text-[11px] text-slate-400">{op.role}</p>
        </div>
        <span
          className="shrink-0 rounded-md px-2 py-0.5 text-[10px] font-mono"
          style={{ background: `${confColor(op.confidence)}22`, color: confColor(op.confidence) }}
        >
          {Math.round(op.confidence * 100)}%
        </span>
      </div>

      <div
        className="mt-2 inline-block rounded-md bg-navy-900/60 px-2 py-1 text-[11px] font-medium"
        style={{ color: confColor(op.confidence) }}
      >
        {op.stance}
      </div>

      <ConfidenceBar value={op.confidence} />

      <AnimatePresence initial={false}>
        {flipped ? (
          <motion.div
            key="points"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 overflow-hidden"
          >
            <ul className="space-y-1">
              {op.key_points.map((p, i) => (
                <li key={i} className="text-[11px] text-slate-300">
                  • {p}
                </li>
              ))}
            </ul>
          </motion.div>
        ) : (
          <motion.p
            key="summary"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-2 text-[12px] leading-relaxed text-slate-300"
          >
            {op.summary}
          </motion.p>
        )}
      </AnimatePresence>

      <p className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">
        {op.llm_used ? "AI reasoning" : "computed"} · tap to {flipped ? "hide" : "see"} points
      </p>
    </motion.div>
  );
}

function Convening() {
  const avatars = ["🛡️", "💰", "📈", "🎯", "📊", "🧾", "🧭"];
  return (
    <div className="flex flex-col items-center justify-center py-10">
      <div className="relative flex h-28 w-28 items-center justify-center">
        {avatars.map((a, i) => {
          const angle = (i / avatars.length) * Math.PI * 2;
          return (
            <motion.span
              key={i}
              className="absolute text-lg"
              style={{ x: Math.cos(angle) * 46, y: Math.sin(angle) * 46 }}
              animate={{ scale: [1, 1.35, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.15 }}
            >
              {a}
            </motion.span>
          );
        })}
        <motion.span
          className="text-2xl"
          animate={{ rotate: 360 }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        >
          ⚖️
        </motion.span>
      </div>
      <p className="mt-4 text-sm text-teal-accent">The panel is deliberating…</p>
    </div>
  );
}

export default function DebatePanel({ delay = 0 }: { delay?: number }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DebateResult | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");

  async function convene() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await runDebate(question.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The panel could not convene.");
    } finally {
      setBusy(false);
    }
  }

  const decision = result?.decision;

  return (
    <GlassCard
      title="Advisory Panel"
      subtitle="Eight specialists debate your finances, then decide"
      delay={delay}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && convene()}
          placeholder="Optional: ask the panel something (e.g. 'Can I afford a car?')"
          className="flex-1 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
        />
        <button
          onClick={convene}
          disabled={busy}
          className="rounded-xl bg-gradient-to-r from-teal-accent to-violet-accent px-5 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-40 transition-opacity"
        >
          {busy ? "Convening…" : "Convene panel"}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}

      <AnimatePresence mode="wait">
        {busy && !result ? (
          <Convening key="convening" />
        ) : result ? (
          <motion.div
            key="result"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-4"
          >
            {/* Final decision */}
            {decision && (
              <motion.div
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mb-4 rounded-2xl border border-teal-accent/30 bg-gradient-to-br from-teal-accent/10 to-violet-accent/10 p-4"
                style={{ boxShadow: "0 0 24px rgba(45,212,191,0.15)" }}
              >
                <div className="flex items-center justify-between">
                  <p className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                    ⚖️ Final Decision
                  </p>
                  <span className="rounded-md bg-teal-accent/20 px-2 py-0.5 text-xs font-mono text-teal-accent">
                    {Math.round(decision.consensus_confidence * 100)}% consensus
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-200">
                  {decision.summary}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {decision.priorities.slice(0, 4).map((p, i) => (
                    <span
                      key={i}
                      className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300"
                    >
                      {i + 1}. {p.icon} {p.action}
                    </span>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Specialist opinions */}
            <div
              className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
              style={{ perspective: 1000 }}
            >
              {result.opinions.map((op, i) => (
                <OpinionCard key={op.agent} op={op} index={i} />
              ))}
            </div>

            <p className="mt-3 text-center text-[11px] text-slate-500">
              {result.meta.langgraph ? "Orchestrated via LangGraph" : "Concurrent execution"} ·{" "}
              {result.meta.agent_count} agents · {Math.round(result.meta.elapsed_ms)}ms ·{" "}
              {result.meta.llm_used ? "AI-enriched" : "computed from your data"}
            </p>
          </motion.div>
        ) : (
          <motion.p
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-6 text-center text-sm text-slate-400"
          >
            Convene a panel of eight financial specialists — Risk, Savings, Investment,
            Lifestyle, Budget, Tax, and a Planner — who debate your data and reach a
            confidence-weighted decision.
          </motion.p>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
