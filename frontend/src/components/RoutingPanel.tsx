import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  RouterProvider,
  RouterStatus,
  getRouterStatus,
  setPreferredProvider,
} from "../api";
import GlassCard from "./GlassCard";

const STATUS: Record<string, { color: string; label: string }> = {
  healthy: { color: "#2dd4bf", label: "Healthy" },
  unhealthy: { color: "#f59e0b", label: "Unhealthy" },
  not_configured: { color: "#64748b", label: "Not configured" },
};

function dot(status: string) {
  return STATUS[status]?.color || "#64748b";
}

function ProviderCard({
  p,
  active,
  onSelect,
  index,
}: {
  p: RouterProvider;
  active: boolean;
  onSelect: () => void;
  index: number;
}) {
  const maxLatency = 3000;
  const latencyPct = Math.min(100, (p.avg_latency_ms / maxLatency) * 100);
  return (
    <motion.button
      onClick={onSelect}
      initial={{ opacity: 0, y: 16, rotateX: -10 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ delay: index * 0.06, type: "spring", stiffness: 130, damping: 16 }}
      whileHover={{ rotateY: 5, translateZ: 16, scale: 1.02 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className={`relative rounded-xl border p-3.5 text-left transition-colors ${
        active
          ? "border-teal-accent/60 bg-teal-accent/10"
          : "border-white/10 bg-white/5 hover:border-white/25"
      }`}
    >
      {active && (
        <span className="absolute right-2 top-2 rounded-full bg-teal-accent px-2 py-0.5 text-[9px] font-bold text-navy-900">
          ACTIVE
        </span>
      )}
      <div className="flex items-center gap-2">
        <motion.span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: dot(p.status) }}
          animate={p.status === "healthy" ? { scale: [1, 1.4, 1], opacity: [1, 0.6, 1] } : {}}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-100">
            #{p.rank} {p.label}
          </p>
          <p className="truncate text-[10px] text-slate-400">{p.model || "—"}</p>
        </div>
        {p.offline && (
          <span className="rounded bg-white/10 px-1.5 py-0.5 text-[9px] text-slate-300">
            offline
          </span>
        )}
      </div>

      <p className="mt-1.5 text-[10px]" style={{ color: dot(p.status) }}>
        {STATUS[p.status]?.label || p.status}
      </p>

      {/* latency bar */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full"
          style={{ background: p.avg_latency_ms > 1500 ? "#f59e0b" : "#38bdf8" }}
          initial={{ width: 0 }}
          animate={{ width: `${latencyPct}%` }}
          transition={{ duration: 0.6 }}
        />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1 text-center text-[10px] text-slate-400">
        <div>
          <p className="text-slate-200">{p.requests}</p>
          <p>reqs</p>
        </div>
        <div>
          <p className="text-slate-200">{Math.round(p.avg_latency_ms)}ms</p>
          <p>latency</p>
        </div>
        <div>
          <p className="text-slate-200">${p.cost_estimate_usd.toFixed(4)}</p>
          <p>cost</p>
        </div>
      </div>
    </motion.button>
  );
}

export default function RoutingPanel({ delay = 0 }: { delay?: number }) {
  const [status, setStatus] = useState<RouterStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setStatus(await getRouterStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load router status");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function choose(provider: string) {
    try {
      await setPreferredProvider(provider);
      await refresh();
    } catch {
      /* ignore */
    }
  }

  const totals = status?.totals || {};
  const cache = status?.cache || {};

  return (
    <GlassCard
      title="Model Routing"
      subtitle="Multi-provider failover · health · latency · cost"
      delay={delay}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-400">Preferred:</span>
        <button
          onClick={() => choose("auto")}
          className={`rounded-lg px-3 py-1 text-xs transition-colors ${
            status?.preferred === "auto"
              ? "bg-teal-accent font-semibold text-navy-900"
              : "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
          }`}
        >
          ⚡ Auto (failover)
        </button>
        {status?.providers.map((p) => (
          <button
            key={p.name}
            onClick={() => choose(p.name)}
            disabled={!p.available}
            title={p.available ? "" : "Not configured"}
            className={`rounded-lg px-3 py-1 text-xs transition-colors disabled:opacity-40 ${
              status?.preferred === p.name
                ? "bg-teal-accent font-semibold text-navy-900"
                : "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
            }`}
          >
            {p.label.split(" ")[0]}
          </button>
        ))}
        <button
          onClick={refresh}
          disabled={busy}
          className="ml-auto rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 hover:bg-white/10 disabled:opacity-40"
        >
          {busy ? "…" : "↻ Refresh"}
        </button>
      </div>

      {error && <p className="text-sm text-rose-300">{error}</p>}

      <AnimatePresence>
        {status && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ perspective: 1000 }}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {status.providers.map((p, i) => (
                <ProviderCard
                  key={p.name}
                  p={p}
                  index={i}
                  active={status.active_provider === p.name}
                  onSelect={() => choose(p.name)}
                />
              ))}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { label: "Requests", value: totals.requests ?? 0 },
                { label: "Tokens", value: (totals.total_tokens ?? 0).toLocaleString() },
                { label: "Est. cost", value: `$${(totals.cost_estimate_usd ?? 0).toFixed(4)}` },
                {
                  label: "Cache hit",
                  value: `${Math.round((cache.hit_rate ?? 0) * 100)}%`,
                },
              ].map((s) => (
                <div key={s.label} className="rounded-xl border border-white/10 bg-white/5 p-2.5 text-center">
                  <p className="text-sm font-bold text-slate-100">{s.value}</p>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400">{s.label}</p>
                </div>
              ))}
            </div>

            <p className="mt-3 text-center text-[11px] text-slate-500">
              Active: <span className="text-teal-accent">{status.active_provider}</span> · Claude &
              OpenAI reachable via OpenRouter / GitHub Models
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
