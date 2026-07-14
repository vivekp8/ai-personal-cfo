import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { DashboardData, Simulation, runWhatIf } from "../api";
import { inr, pct } from "../lib/format";
import GlassCard from "./GlassCard";

function scoreColor(score: number): string {
  if (score >= 70) return "#22c55e";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

function ScenarioBar({
  label,
  score,
  outflow,
  ef,
  savingsRate,
  extra,
  recommended,
}: {
  label: string;
  score: number;
  outflow: number;
  ef: number;
  savingsRate: number;
  extra?: string;
  recommended: boolean;
}) {
  const color = scoreColor(score);
  return (
    <div
      className={`flex-1 rounded-xl border p-4 ${
        recommended ? "border-teal-accent/50 bg-teal-accent/5" : "border-white/10 bg-white/5"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-200">{label}</p>
        {recommended && (
          <span className="rounded-md bg-teal-accent/20 px-2 py-0.5 text-[10px] font-bold uppercase text-teal-accent">
            Recommended
          </span>
        )}
      </div>

      {/* Animated score bar */}
      <div className="mt-3">
        <div className="flex items-end justify-between">
          <span className="text-[11px] text-slate-400">Health score</span>
          <span className="text-2xl font-extrabold" style={{ color }}>
            {score}
          </span>
        </div>
        <div className="mt-1 h-3 w-full overflow-hidden rounded-full bg-black/30">
          <motion.div
            className="h-full rounded-full"
            style={{ background: color }}
            initial={{ width: 0 }}
            animate={{ width: `${score}%` }}
            transition={{ type: "spring", stiffness: 120, damping: 18 }}
          />
        </div>
      </div>

      <div className="mt-3 space-y-1 text-xs text-slate-300">
        <Row label="Monthly outflow" value={inr(outflow)} />
        <Row label="Emergency fund" value={`${ef.toFixed(1)} mo`} />
        <Row label="Savings rate" value={pct(savingsRate)} />
        {extra && <Row label="Extra" value={extra} />}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="tabular-nums text-slate-200">{value}</span>
    </div>
  );
}

export default function WhatIfPanel({
  data,
  delay = 0,
}: {
  data: DashboardData;
  delay?: number;
}) {
  const [amount, setAmount] = useState(50000);
  const [tenure, setTenure] = useState(12);
  const [sim, setSim] = useState<Simulation | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const debounceRef = useRef<number>(0);

  const baseSavings = (() => {
    const s = data.monthly_summary;
    const inc = Object.values(s.monthly_income).reduce((a, b) => a + b, 0);
    const exp = Object.values(s.monthly_expenses).reduce((a, b) => a + b, 0);
    return Math.max(0, inc - exp);
  })();

  // Live (fast) recompute of the draining bar without hitting the LLM.
  useEffect(() => {
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      setBusy(true);
      try {
        const res = await runWhatIf({
          purchase_amount: amount,
          tenure_months: tenure,
          explain: false,
        });
        setSim(res.simulation);
      } catch {
        /* ignore transient */
      } finally {
        setBusy(false);
      }
    }, 350);
    return () => window.clearTimeout(debounceRef.current);
  }, [amount, tenure]);

  async function explainNow() {
    setBusy(true);
    setExplanation(null);
    try {
      const res = await runWhatIf({
        purchase_amount: amount,
        tenure_months: tenure,
        explain: true,
      });
      setSim(res.simulation);
      setExplanation(res.explanation?.response ?? null);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  const savingsAfter = sim ? sim.pay_full.new_savings : baseSavings - amount;
  const drainPct = baseSavings > 0 ? Math.max(0, (savingsAfter / baseSavings) * 100) : 0;

  return (
    <GlassCard
      title="What-If Simulator"
      subtitle="Model a purchase: pay in full vs EMI"
      delay={delay}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className="text-xs text-slate-400">Purchase amount</label>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-slate-400">₹</span>
            <input
              type="number"
              value={amount}
              min={0}
              step={1000}
              onChange={(e) => setAmount(Math.max(0, Number(e.target.value)))}
              className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none focus:border-teal-accent/50"
            />
          </div>
          <input
            type="range"
            min={5000}
            max={Math.max(200000, baseSavings * 1.5)}
            step={5000}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="mt-3 w-full accent-teal-accent"
          />
        </div>

        <div>
          <label className="text-xs text-slate-400">EMI tenure: {tenure} months</label>
          <input
            type="range"
            min={3}
            max={36}
            step={1}
            value={tenure}
            onChange={(e) => setTenure(Number(e.target.value))}
            className="mt-3 w-full accent-violet-accent"
          />
          <div className="mt-3">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Savings after paying in full</span>
              <span
                className={`tabular-nums font-semibold ${
                  savingsAfter < 0 ? "text-red-400" : "text-slate-200"
                }`}
              >
                {inr(savingsAfter)}
              </span>
            </div>
            <div className="mt-1 h-4 w-full overflow-hidden rounded-full bg-black/30">
              <motion.div
                className="h-full rounded-full"
                style={{
                  background:
                    drainPct < 25
                      ? "linear-gradient(90deg,#ef4444,#f59e0b)"
                      : "linear-gradient(90deg,#2dd4bf,#38bdf8)",
                }}
                animate={{ width: `${Math.min(100, drainPct)}%` }}
                transition={{ type: "spring", stiffness: 120, damping: 20 }}
              />
            </div>
            {savingsAfter < 0 && (
              <p className="mt-1 text-xs text-red-400">
                This exceeds your estimated savings of {inr(baseSavings)}.
              </p>
            )}
          </div>
        </div>
      </div>

      {sim && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-5 flex flex-col gap-3 md:flex-row"
        >
          <ScenarioBar
            label={sim.pay_full.label}
            score={sim.pay_full.health_score}
            outflow={sim.pay_full.monthly_outflow}
            ef={sim.pay_full.emergency_fund_months}
            savingsRate={sim.pay_full.savings_rate}
            recommended={sim.recommendation === "pay_full"}
          />
          <ScenarioBar
            label={sim.emi.label}
            score={sim.emi.health_score}
            outflow={sim.emi.monthly_outflow}
            ef={sim.emi.emergency_fund_months}
            savingsRate={sim.emi.savings_rate}
            extra={`${inr(sim.emi.emi_monthly)}/mo · ${inr(sim.emi.interest_paid)} interest`}
            recommended={sim.recommendation === "emi"}
          />
        </motion.div>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={explainNow}
          disabled={busy}
          className="rounded-xl bg-violet-accent px-4 py-2 text-sm font-semibold text-navy-900 disabled:opacity-40 transition-opacity"
        >
          {busy ? "Thinking…" : "Explain this"}
        </button>
        {sim && (
          <p className="text-xs text-slate-400">
            Recommendation:{" "}
            <span className="font-semibold text-teal-accent">
              {sim.recommendation === "pay_full" ? "Pay in full" : "Use EMI"}
            </span>
          </p>
        )}
      </div>

      {explanation && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 rounded-xl border border-violet-accent/20 bg-violet-accent/5 p-3 text-sm text-slate-200"
        >
          {explanation}
        </motion.div>
      )}
    </GlassCard>
  );
}
