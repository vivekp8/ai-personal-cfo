import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RagTraceResult, ragTrace } from "../api";
import GlassCard from "./GlassCard";
import RetrievalExplorer from "./RetrievalExplorer";

const STAGES = [
  "Question",
  "Embedding",
  "Retrieved Chunks",
  "Similarity Score",
  "Ranking",
  "Final Context",
  "LLM Response",
];

const EXAMPLES = [
  "How much emergency fund should I keep?",
  "Ways to increase my savings rate",
  "Are my subscriptions worth it?",
];

export default function RetrievalPanel({ delay = 0 }: { delay?: number }) {
  const [query, setQuery] = useState("");
  const [trace, setTrace] = useState<RagTraceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [explorer, setExplorer] = useState(false);

  async function runTrace(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    setError("");
    try {
      const t = await ragTrace(question, 5);
      if (!t.available) {
        setError(t.reason || "Retrieval is unavailable (RAG not configured).");
        setTrace(null);
      } else {
        setTrace(t);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Trace failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard
      title="RAG Retrieval Explorer"
      subtitle="See exactly how your question finds its answer"
      delay={delay}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runTrace(query)}
          placeholder="Ask anything — watch retrieval work…"
          className="flex-1 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
        />
        <button
          onClick={() => runTrace(query)}
          disabled={busy}
          className="rounded-xl bg-gradient-to-r from-teal-accent to-violet-accent px-5 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-40"
        >
          {busy ? "Tracing…" : "Trace"}
        </button>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => {
              setQuery(ex);
              runTrace(ex);
            }}
            className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-white/10"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}

      {/* Pipeline stages */}
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {STAGES.map((s, i) => (
          <span key={s} className="flex items-center gap-1.5">
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                trace
                  ? "border border-teal-accent/40 bg-teal-accent/10 text-teal-100"
                  : "border border-white/10 bg-white/5 text-slate-400"
              }`}
            >
              {s}
            </span>
            {i < STAGES.length - 1 && <span className="text-slate-600">→</span>}
          </span>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {trace && (
          <motion.div
            key={trace.query}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs text-slate-400">
                {trace.chunks.length} chunks · {trace.embedding?.dimension}-dim embedding
              </p>
              <button
                onClick={() => setExplorer(true)}
                className="rounded-lg border border-teal-accent/40 bg-teal-accent/10 px-3 py-1.5 text-xs font-semibold text-teal-100 hover:bg-teal-accent/20"
              >
                🌐 Immersive 3D
              </button>
            </div>

            <div className="space-y-2">
              {trace.chunks.slice(0, 5).map((c, i) => {
                const isMem = c.collection === "user_memory";
                const col = isMem ? "#a78bfa" : "#22d3ee";
                return (
                  <div key={i} className="rounded-xl border border-white/10 bg-white/5 p-2.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400">
                        #{c.rank} · {isMem ? "Your memory" : "Knowledge base"}
                      </span>
                      <span className="font-mono" style={{ color: col }}>
                        {Math.round(c.similarity * 100)}%
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ background: col }}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.round(c.similarity * 100)}%` }}
                        transition={{ duration: 0.6, delay: i * 0.08 }}
                      />
                    </div>
                    <p className="mt-1.5 text-[12px] text-slate-300">{c.text}</p>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {explorer && trace && (
          <RetrievalExplorer trace={trace} onClose={() => setExplorer(false)} />
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
