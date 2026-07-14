import { Suspense, lazy } from "react";
import { HealthScore } from "../api";
import { pct } from "../lib/format";
import { useReduceMotion } from "../lib/motion";
import AnimatedNumber from "./AnimatedNumber";
import GlassCard from "./GlassCard";

const ScoreOrb = lazy(() => import("../three/ScoreOrb"));

function ratingColor(score: number): string {
  if (score >= 70) return "#22c55e";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

export default function HealthScorePanel({
  hs,
  delay = 0,
}: {
  hs: HealthScore;
  delay?: number;
}) {
  const { reduceMotion } = useReduceMotion();
  const color = ratingColor(hs.score);

  return (
    <GlassCard title="Financial Health Score" delay={delay} className="flex flex-col">
      <div className="relative flex items-center justify-center" style={{ height: 200 }}>
        {!reduceMotion ? (
          <Suspense
            fallback={
              <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs">
                loading…
              </div>
            }
          >
            <ScoreOrb score={hs.score} />
          </Suspense>
        ) : (
          <div
            className="flex h-40 w-40 items-center justify-center rounded-full"
            style={{ boxShadow: `0 0 60px ${color}55`, border: `3px solid ${color}` }}
          />
        )}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <AnimatedNumber
            value={hs.score}
            className="text-5xl font-extrabold"
          />
          <span
            className="mt-1 text-xs font-semibold uppercase tracking-widest"
            style={{ color }}
          >
            {hs.rating}
          </span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <Stat label="Savings rate" value={pct(hs.savings_rate)} />
        <Stat label="Emergency fund" value={`${hs.emergency_fund_months.toFixed(1)} mo`} />
        <Stat label="Anomalies" value={String(hs.anomalies_count)} />
        <Stat label="Active EMIs" value={String(hs.active_emis)} />
      </div>
    </GlassCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/5 px-3 py-2">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="font-semibold text-slate-100">{value}</p>
    </div>
  );
}
