import { motion } from "framer-motion";
import { Anomaly } from "../api";
import { formatCurrency } from "../lib/format";
import GlassCard from "./GlassCard";

export default function AnomaliesPanel({
  anomalies,
  delay = 0,
}: {
  anomalies: Anomaly[];
  delay?: number;
}) {
  return (
    <GlassCard
      title="Anomaly Alerts"
      subtitle={anomalies.length ? `${anomalies.length} flagged` : "Nothing unusual"}
      delay={delay}
    >
      {anomalies.length === 0 ? (
        <p className="text-sm text-slate-400">
          No spending anomalies detected — your patterns look consistent.
        </p>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {anomalies.map((a, i) => {
            const high = a.severity === "high";
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: delay + i * 0.08 }}
                className={`relative rounded-xl border p-3 ${
                  high
                    ? "border-red-500/40 bg-red-500/5"
                    : "border-amber-500/40 bg-amber-500/5"
                }`}
              >
                <span
                  className={`absolute left-0 top-0 h-full w-1 rounded-l-xl ${
                    high ? "bg-red-500 animate-pulseGlow" : "bg-amber-500"
                  }`}
                />
                <div className="flex items-start justify-between gap-3 pl-2">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      {a.type === "category_spike" ? "Category Spike" : "Large Transaction"}
                      {" · "}
                      {a.category}
                    </p>
                    <p className="mt-0.5 text-sm text-slate-200">{a.message}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold ${
                      high ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300"
                    }`}
                  >
                    {formatCurrency(a.amount)}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </GlassCard>
  );
}
