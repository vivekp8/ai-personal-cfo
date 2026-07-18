import { motion } from "framer-motion";
import { SavingsSuggestion } from "../api";
import { formatCurrency } from "../lib/format";
import GlassCard from "./GlassCard";

export default function SavingsPanel({
  suggestions,
  delay = 0,
}: {
  suggestions: SavingsSuggestion[];
  delay?: number;
}) {
  const total = suggestions.reduce((s, x) => s + (x.monthly_savings || 0), 0);

  return (
    <GlassCard
      title="Savings Opportunities"
      subtitle={total ? `Up to ${formatCurrency(total)}/mo potential` : "Looking good"}
      delay={delay}
    >
      {suggestions.length === 0 ? (
        <p className="text-sm text-slate-400">
          No obvious savings opportunities right now. Nice work.
        </p>
      ) : (
        <div className="space-y-2">
          {suggestions.map((s, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: delay + i * 0.1 }}
              className="rounded-xl border border-teal-accent/20 bg-teal-accent/5 p-3"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-teal-accent">{s.title}</p>
                {s.monthly_savings > 0 && (
                  <span className="rounded-md bg-teal-accent/15 px-2 py-0.5 text-xs font-semibold text-teal-accent">
                    ~{formatCurrency(s.monthly_savings)}/mo
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-300">{s.detail}</p>
            </motion.div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}
