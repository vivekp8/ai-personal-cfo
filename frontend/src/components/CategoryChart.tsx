import { useMemo, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { AnimatePresence, motion } from "framer-motion";
import { MonthlySummary, Transaction } from "../api";
import { categoryColor, inr } from "../lib/format";
import GlassCard from "./GlassCard";

interface Props {
  summary: MonthlySummary;
  transactions: Transaction[];
  delay?: number;
}

export default function CategoryChart({ summary, transactions, delay = 0 }: Props) {
  const [active, setActive] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const data = useMemo(() => {
    return Object.entries(summary.category_totals)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [summary]);

  const total = useMemo(
    () => data.reduce((s, d) => s + d.value, 0),
    [data]
  );

  const drill = useMemo(() => {
    if (!active) return [];
    return transactions
      .filter((t) => t.category === active && t.amount < 0)
      .sort((a, b) => b.date.localeCompare(a.date));
  }, [active, transactions]);

  return (
    <GlassCard title="Total Spending by Category" subtitle="Click a slice to drill in" delay={delay}>
      <div className="flex flex-col md:flex-row gap-4">
        <div style={{ width: "100%", height: 240 }} className="md:w-1/2">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={55}
                outerRadius={90}
                paddingAngle={2}
                onClick={(d: any) => setActive((prev) => (prev === d.name ? null : d.name))}
                onMouseEnter={(d: any) => setHovered(d.name)}
                onMouseLeave={() => setHovered(null)}
              >
                {data.map((entry) => {
                  const isActive = active === entry.name || hovered === entry.name;
                  return (
                    <Cell
                      key={entry.name}
                      fill={categoryColor(entry.name)}
                      stroke={isActive ? "#fff" : "transparent"}
                      strokeWidth={isActive ? 2 : 0}
                      style={{
                        cursor: "pointer",
                        filter: isActive
                          ? `drop-shadow(0 0 8px ${categoryColor(entry.name)})`
                          : "none",
                        transform: isActive ? "scale(1.04)" : "scale(1)",
                        transformOrigin: "center",
                        transition: "all 0.2s ease",
                      }}
                    />
                  );
                })}
              </Pie>
              <Tooltip
                formatter={(v: number) => inr(v)}
                contentStyle={{
                  background: "rgba(15,22,38,0.95)",
                  border: "1px solid rgba(148,163,184,0.2)",
                  borderRadius: 12,
                  color: "#e5e9f0",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="md:w-1/2 space-y-1.5">
          {data.map((d) => (
            <button
              key={d.name}
              onClick={() => setActive((prev) => (prev === d.name ? null : d.name))}
              onMouseEnter={() => setHovered(d.name)}
              onMouseLeave={() => setHovered(null)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-sm transition-colors ${
                active === d.name ? "bg-white/10" : "hover:bg-white/5"
              }`}
            >
              <span className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: categoryColor(d.name) }}
                />
                <span className="text-slate-200">{d.name}</span>
              </span>
              <span className="text-slate-300 tabular-nums">
                {inr(d.value)}{" "}
                <span className="text-slate-500">
                  ({((d.value / total) * 100).toFixed(0)}%)
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>

      <AnimatePresence>
        {active && (
          <motion.div
            key={active}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-4 overflow-hidden"
          >
            <div className="rounded-xl border border-white/10 bg-black/20 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                {active} — {drill.length} transactions
              </p>
              <div className="max-h-52 space-y-1 overflow-y-auto pr-1">
                {drill.map((t, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md px-2 py-1 text-sm hover:bg-white/5"
                  >
                    <span className="text-slate-300">
                      <span className="text-slate-500 mr-2 tabular-nums">{t.date}</span>
                      {t.description}
                    </span>
                    <span className="tabular-nums text-slate-200">
                      {inr(Math.abs(t.amount))}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
