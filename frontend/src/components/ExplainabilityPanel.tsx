import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExplanationCard, explainSubject } from "../api";
import { formatCurrency } from "../lib/format";
import GlassCard from "./GlassCard";

const SUBJECTS: { id: string; label: string; icon: string }[] = [
  { id: "score", label: "Health Score", icon: "❤️" },
  { id: "savings", label: "Savings", icon: "💰" },
  { id: "forecast", label: "Forecast", icon: "🔮" },
  { id: "anomaly", label: "Anomalies", icon: "🚨" },
  { id: "spending", label: "Spending", icon: "📊" },
];

function confColor(c: number): string {
  if (c >= 0.85) return "#2dd4bf";
  if (c >= 0.6) return "#38bdf8";
  return "#f59e0b";
}

function Facet({
  label,
  icon,
  children,
  delay = 0,
}: {
  label: string;
  icon: string;
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className="rounded-xl border border-white/10 bg-white/5 p-3"
    >
      <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        <span>{icon}</span>
        {label}
      </p>
      <div className="text-sm text-slate-200">{children}</div>
    </motion.div>
  );
}

export default function ExplainabilityPanel({ delay = 0 }: { delay?: number }) {
  const [subject, setSubject] = useState("score");
  const [card, setCard] = useState<ExplanationCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError("");
    explainSubject(subject)
      .then((c) => !cancelled && setCard(c))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to explain"))
      .finally(() => !cancelled && setBusy(false));
    return () => {
      cancelled = true;
    };
  }, [subject]);

  return (
    <GlassCard
      title="Explainable AI"
      subtitle="Why · evidence · confidence · formula · model — no black boxes"
      delay={delay}
    >
      {/* Subject selector */}
      <div className="mb-4 flex flex-wrap gap-2">
        {SUBJECTS.map((s) => (
          <button
            key={s.id}
            onClick={() => setSubject(s.id)}
            className={`rounded-lg px-3 py-1.5 text-xs transition-colors ${
              subject === s.id
                ? "bg-teal-accent text-navy-900 font-semibold"
                : "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
            }`}
          >
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-rose-300">{error}</p>}

      <AnimatePresence mode="wait">
        {busy ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center py-10"
          >
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-teal-accent border-t-transparent" />
          </motion.div>
        ) : card ? (
          <motion.div
            key={card.subject}
            initial={{ opacity: 0, rotateX: -8 }}
            animate={{ opacity: 1, rotateX: 0 }}
            exit={{ opacity: 0 }}
            style={{ transformStyle: "preserve-3d", perspective: 1000 }}
          >
            {/* Headline: why + confidence gauge */}
            <div className="mb-4 rounded-2xl border border-teal-accent/25 bg-gradient-to-br from-teal-accent/10 to-violet-accent/10 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-400">
                    {card.title}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-slate-100">{card.why}</p>
                </div>
                <div className="shrink-0 text-center">
                  <div
                    className="flex h-14 w-14 items-center justify-center rounded-full text-sm font-bold"
                    style={{
                      color: confColor(card.confidence),
                      border: `2px solid ${confColor(card.confidence)}`,
                    }}
                  >
                    {Math.round(card.confidence * 100)}%
                  </div>
                  <p className="mt-1 text-[10px] text-slate-500">confidence</p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <Facet label="Evidence" icon="🧾" delay={0.05}>
                <ul className="space-y-1 font-mono text-[12px] text-slate-300">
                  {card.evidence.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </Facet>

              <Facet label="Formula used" icon="📐" delay={0.1}>
                <code className="block rounded bg-black/30 px-2 py-1.5 text-[11px] text-teal-200">
                  {card.formula}
                </code>
                <p className="mt-2 text-[11px] text-slate-400">{card.reasoning_summary}</p>
              </Facet>

              <Facet label="Transactions used" icon="💳" delay={0.15}>
                {card.transactions_used.length === 0 ? (
                  <p className="text-[12px] text-slate-500">None for this figure.</p>
                ) : (
                  <ul className="space-y-1 text-[12px]">
                    {card.transactions_used.slice(0, 6).map((t, i) => (
                      <li key={i} className="flex justify-between gap-2">
                        <span className="truncate text-slate-300">
                          {t.date} · {t.description}
                        </span>
                        <span
                          className={t.amount < 0 ? "text-rose-300" : "text-emerald-300"}
                        >
                          {formatCurrency(t.amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Facet>

              <Facet label="Retrieved documents (RAG)" icon="📚" delay={0.2}>
                {card.retrieved_documents.length === 0 ? (
                  <p className="text-[12px] text-slate-500">No supporting docs retrieved.</p>
                ) : (
                  <ul className="space-y-1 text-[11px] text-slate-400">
                    {card.retrieved_documents.map((d, i) => (
                      <li key={i} className="rounded bg-black/20 px-2 py-1">
                        {d}
                      </li>
                    ))}
                  </ul>
                )}
              </Facet>
            </div>

            <p className="mt-3 text-center text-[11px] text-slate-500">
              🧠 Model: {card.model}
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </GlassCard>
  );
}
