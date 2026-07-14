import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { WorkflowNode, WorkflowTrace, getWorkflowTrace } from "../api";
import GlassCard from "./GlassCard";
import WorkflowExplorer from "./WorkflowExplorer";

const STATUS_STYLE: Record<string, { color: string; label: string }> = {
  ok: { color: "#2dd4bf", label: "done" },
  error: { color: "#fb7185", label: "error" },
  pending: { color: "#64748b", label: "idle" },
  deferred: { color: "#a78bfa", label: "on-ask" },
};

const GROUP_LABEL: Record<string, string> = {
  ingest: "Ingest",
  analyze: "Analyze",
  memory: "Persist",
  chat: "Chat",
};

function NodeChip({ node, index }: { node: WorkflowNode; index: number }) {
  const st = STATUS_STYLE[node.status || "pending"];
  return (
    <motion.div
      initial={{ opacity: 0, y: 14, rotateX: -20 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ delay: index * 0.06, type: "spring", stiffness: 140, damping: 16 }}
      whileHover={{ scale: 1.05, translateZ: 12 }}
      style={{ transformStyle: "preserve-3d" }}
      className="relative flex min-w-[104px] flex-col items-center rounded-xl border p-2.5 text-center"
      title={node.desc}
    >
      <span
        className="absolute inset-0 rounded-xl"
        style={{ boxShadow: `0 0 14px ${st.color}33`, border: `1px solid ${st.color}55` }}
      />
      <span
        className="relative flex h-8 w-8 items-center justify-center rounded-full text-[11px] font-bold"
        style={{ background: `${st.color}22`, color: st.color }}
      >
        {node.status === "ok" ? "✓" : node.status === "error" ? "!" : index + 1}
      </span>
      <p className="relative mt-1.5 text-[11px] font-medium text-slate-100">{node.label}</p>
      <p className="relative text-[9px] uppercase tracking-wider" style={{ color: st.color }}>
        {node.status === "ok" && node.duration_ms
          ? `${Math.round(node.duration_ms)}ms`
          : st.label}
      </p>
      {node.detail && (
        <p className="relative mt-0.5 text-[9px] text-slate-500 line-clamp-1">{node.detail}</p>
      )}
    </motion.div>
  );
}

export default function WorkflowPanel({ delay = 0 }: { delay?: number }) {
  const [data, setData] = useState<WorkflowTrace | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const nodes: WorkflowNode[] = (data?.trace || data?.nodes || []) as WorkflowNode[];
  const hasRun = !!data?.trace;

  useEffect(() => {
    let cancelled = false;
    getWorkflowTrace()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, []);

  const totalMs = data?.total_ms;

  return (
    <GlassCard
      title="Analysis Workflow"
      subtitle="Live LangGraph execution — every upload flows through these nodes"
      delay={delay}
    >
      {error && <p className="text-sm text-rose-300">{error}</p>}

      <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">
          {data?.langgraph ? "⚡ LangGraph" : "sequential"}
        </span>
        {hasRun && totalMs != null && (
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">
            {Math.round(totalMs)}ms total
          </span>
        )}
        {data?.format && (
          <span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-2 py-0.5 text-teal-accent">
            last input: {data.format}
          </span>
        )}
        {!hasRun && (
          <span>Upload any supported file to see it run.</span>
        )}
      </div>

      {/* Animated node flow */}
      <div className="flex flex-wrap items-center gap-2" style={{ perspective: 900 }}>
        {nodes.map((n, i) => (
          <div key={n.id} className="flex items-center">
            <NodeChip node={n} index={i} />
            {i < nodes.length - 1 && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.06 + 0.1 }}
                className="mx-0.5 text-slate-600"
              >
                →
              </motion.span>
            )}
          </div>
        ))}
      </div>

      {/* Supported formats */}
      {data?.supported_formats && data.supported_formats.length > 0 && (
        <p className="mt-3 text-[11px] text-slate-500">
          Accepts:{" "}
          {data.supported_formats.map((f) => `.${f}`).join(", ")} — all routed
          through the same pipeline.
        </p>
      )}

      <div className="mt-4 flex justify-center">
        <button
          onClick={() => setOpen(true)}
          disabled={nodes.length === 0}
          className="rounded-xl bg-gradient-to-r from-teal-accent to-violet-accent px-5 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-40"
        >
          🧊 Immersive 3D
        </button>
      </div>

      <AnimatePresence>
        {open && nodes.length > 0 && (
          <WorkflowExplorer
            nodes={nodes}
            langgraph={!!data?.langgraph}
            onClose={() => setOpen(false)}
          />
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
