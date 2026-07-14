import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  SavedSimulation,
  ScenarioInput,
  TwinGoal,
  TwinResult,
  deleteSimulation,
  getSimulations,
  simulateTwin,
} from "../api";
import { inr, pct } from "../lib/format";
import GlassCard from "./GlassCard";

type Assumptions = {
  years: number;
  salary_growth: number;
  expense_growth: number;
  inflation: number;
  investment_return: number;
  current_savings: number;
  current_age: number;
  retirement_age: number;
};

const DEFAULTS: Assumptions = {
  years: 20,
  salary_growth: 0.08,
  expense_growth: 0.06,
  inflation: 0.05,
  investment_return: 0.1,
  current_savings: 0,
  current_age: 30,
  retirement_age: 60,
};

function Slider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <div className="flex items-center justify-between text-[11px] text-slate-400">
        <span>{label}</span>
        <span className="font-mono text-teal-accent">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-teal-accent"
      />
    </label>
  );
}

export default function TwinPanel({ delay = 0 }: { delay?: number }) {
  const [a, setA] = useState<Assumptions>(DEFAULTS);
  const [goals, setGoals] = useState<TwinGoal[]>([]);
  const [goalName, setGoalName] = useState("");
  const [goalAmount, setGoalAmount] = useState<number>(1000000);
  const [result, setResult] = useState<TwinResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<SavedSimulation[]>([]);
  const [scenarioName, setScenarioName] = useState("My scenario");

  function set<K extends keyof Assumptions>(k: K, v: Assumptions[K]) {
    setA((prev) => ({ ...prev, [k]: v }));
  }

  async function refreshSaved() {
    try {
      const { scenarios } = await getSimulations();
      setSaved(scenarios);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refreshSaved();
  }, []);

  function buildScenario(): Partial<ScenarioInput> {
    return {
      name: scenarioName || "Scenario",
      years: a.years,
      salary_growth: a.salary_growth,
      expense_growth: a.expense_growth,
      inflation: a.inflation,
      investment_return: a.investment_return,
      current_savings: a.current_savings,
      current_age: a.current_age,
      retirement_age: a.retirement_age,
      goals,
    };
  }

  async function run(save = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const { result: res } = await simulateTwin(buildScenario(), {
        save,
        name: scenarioName,
      });
      setResult(res);
      if (save) refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  function addGoal() {
    if (!goalName.trim() || goalAmount <= 0) return;
    setGoals((g) => [...g, { name: goalName.trim(), target_amount: goalAmount }]);
    setGoalName("");
  }

  async function removeSaved(id: number) {
    try {
      await deleteSimulation(id);
      refreshSaved();
    } catch {
      /* ignore */
    }
  }

  const chartData =
    result?.projection.map((p) => ({
      year: p.year,
      Nominal: p.net_worth,
      "Today's value": p.real_net_worth,
    })) ?? [];

  const ret = result?.retirement;

  return (
    <GlassCard
      title="Digital Financial Twin"
      subtitle="Project your future and simulate scenarios"
      delay={delay}
    >
      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {/* Controls */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Slider label="Horizon" value={a.years} min={5} max={40} step={1}
              format={(v) => `${v} yrs`} onChange={(v) => set("years", v)} />
            <Slider label="Invest return" value={a.investment_return} min={0} max={0.2} step={0.005}
              format={pct} onChange={(v) => set("investment_return", v)} />
            <Slider label="Salary growth" value={a.salary_growth} min={0} max={0.2} step={0.005}
              format={pct} onChange={(v) => set("salary_growth", v)} />
            <Slider label="Expense growth" value={a.expense_growth} min={0} max={0.2} step={0.005}
              format={pct} onChange={(v) => set("expense_growth", v)} />
            <Slider label="Inflation" value={a.inflation} min={0} max={0.15} step={0.005}
              format={pct} onChange={(v) => set("inflation", v)} />
            <Slider label="Current age" value={a.current_age} min={18} max={70} step={1}
              format={(v) => `${v}`} onChange={(v) => set("current_age", v)} />
            <Slider label="Retire age" value={a.retirement_age} min={a.current_age + 1} max={75} step={1}
              format={(v) => `${v}`} onChange={(v) => set("retirement_age", v)} />
            <Slider label="Start savings" value={a.current_savings} min={0} max={2000000} step={10000}
              format={(v) => inr(v, { compact: true })} onChange={(v) => set("current_savings", v)} />
          </div>

          {/* Goals */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
            <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-400">Goals</p>
            <div className="flex gap-2">
              <input
                value={goalName}
                onChange={(e) => setGoalName(e.target.value)}
                placeholder="e.g. House"
                className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/20 px-2.5 py-1.5 text-xs text-slate-100 outline-none"
              />
              <input
                type="number"
                value={goalAmount}
                onChange={(e) => setGoalAmount(Number(e.target.value))}
                className="w-24 rounded-lg border border-white/10 bg-black/20 px-2.5 py-1.5 text-xs text-slate-100 outline-none"
              />
              <button
                onClick={addGoal}
                className="rounded-lg bg-teal-accent/20 px-2.5 py-1.5 text-xs text-teal-accent hover:bg-teal-accent/30"
              >
                +
              </button>
            </div>
            {goals.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {goals.map((g, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1 rounded-full border border-white/10 bg-black/20 px-2 py-0.5 text-[11px] text-slate-300"
                  >
                    {g.name} · {inr(g.target_amount, { compact: true })}
                    <button
                      onClick={() => setGoals((gs) => gs.filter((_, j) => j !== i))}
                      className="text-slate-500 hover:text-rose-300"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <input
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => run(false)}
              disabled={busy}
              className="flex-1 rounded-xl bg-gradient-to-r from-teal-accent to-violet-accent px-4 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-40"
            >
              {busy ? "Simulating…" : "Simulate"}
            </button>
            <button
              onClick={() => run(true)}
              disabled={busy}
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200 hover:bg-white/10 disabled:opacity-40"
            >
              Save
            </button>
          </div>
          {error && <p className="text-sm text-rose-300">{error}</p>}
        </div>

        {/* Results */}
        <div>
          {!result ? (
            <div className="flex h-full min-h-[280px] flex-col items-center justify-center text-center text-sm text-slate-400">
              <motion.div
                animate={{ rotateY: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                style={{ transformStyle: "preserve-3d" }}
                className="mb-3 text-4xl"
              >
                🔮
              </motion.div>
              Adjust the assumptions and run a simulation to see your projected
              financial future.
            </div>
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="mb-3 grid grid-cols-3 gap-2">
                <div className="rounded-xl bg-white/5 p-3">
                  <p className="text-[10px] uppercase text-slate-400">Net worth (yr {a.years})</p>
                  <p className="text-lg font-bold text-teal-accent">
                    {inr(result.final_net_worth, { compact: true })}
                  </p>
                </div>
                <div className="rounded-xl bg-white/5 p-3">
                  <p className="text-[10px] uppercase text-slate-400">In today's value</p>
                  <p className="text-lg font-bold text-sky-300">
                    {inr(result.final_real_net_worth, { compact: true })}
                  </p>
                </div>
                <div className="rounded-xl bg-white/5 p-3">
                  <p className="text-[10px] uppercase text-slate-400">Investment growth</p>
                  <p className="text-lg font-bold text-violet-accent">
                    {inr(result.total_growth, { compact: true })}
                  </p>
                </div>
              </div>

              <div style={{ width: "100%", height: 220 }}>
                <ResponsiveContainer>
                  <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gNom" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.5} />
                        <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gReal" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                    <XAxis dataKey="year" stroke="#94a3b8" fontSize={11}
                      tickFormatter={(v) => `Y${v}`} />
                    <YAxis stroke="#94a3b8" fontSize={11}
                      tickFormatter={(v) => inr(v, { compact: true })} />
                    <Tooltip
                      formatter={(v: number) => inr(v)}
                      labelFormatter={(l) => `Year ${l}`}
                      contentStyle={{
                        background: "rgba(15,22,38,0.95)",
                        border: "1px solid rgba(148,163,184,0.2)",
                        borderRadius: 12,
                        color: "#e5e9f0",
                      }}
                    />
                    <Area type="monotone" dataKey="Nominal" stroke="#2dd4bf" strokeWidth={2}
                      fill="url(#gNom)" />
                    <Area type="monotone" dataKey="Today's value" stroke="#38bdf8" strokeWidth={2}
                      fill="url(#gReal)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Retirement + goals */}
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {ret?.applicable && (
                  <div className="rounded-xl border border-violet-accent/30 bg-violet-accent/5 p-3">
                    <p className="text-xs font-semibold text-violet-accent">
                      Retirement at {ret.retirement_age}
                    </p>
                    <p className="mt-1 text-[12px] text-slate-300">
                      Projected corpus {inr(ret.projected_corpus ?? 0, { compact: true })} →{" "}
                      ~{inr(ret.real_sustainable_monthly_income ?? 0, { compact: true })}/mo in
                      today's money (4% rule).
                    </p>
                  </div>
                )}
                {result.goals.length > 0 && (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <p className="mb-1 text-xs font-semibold text-slate-200">Goal timeline</p>
                    <ul className="space-y-1">
                      {result.goals.map((g, i) => (
                        <li key={i} className="flex justify-between text-[12px]">
                          <span className="text-slate-300">{g.name}</span>
                          <span className={g.reached ? "text-teal-accent" : "text-amber-300"}>
                            {g.reached ? `Year ${g.year_reached}` : "beyond horizon"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Saved scenarios */}
      {saved.length > 0 && (
        <div className="mt-4 border-t border-white/10 pt-3">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-400">
            Saved scenarios
          </p>
          <div className="flex flex-wrap gap-2">
            {saved.map((s) => (
              <span
                key={s.id}
                className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300"
              >
                {s.name} · {inr(s.result.final_net_worth, { compact: true })}
                <button
                  onClick={() => removeSaved(s.id)}
                  className="text-slate-500 hover:text-rose-300"
                  title="Delete"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
