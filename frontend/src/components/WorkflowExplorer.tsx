import { useState } from "react";
import { motion } from "framer-motion";
import { WorkflowNode } from "../api";
import ErrorBoundary from "./ErrorBoundary";
import WorkflowScene from "../three/WorkflowScene";

const STATUS_LABEL: Record<string, string> = {
  ok: "Completed",
  error: "Failed",
  pending: "Not run",
  deferred: "Runs on each question",
};

export default function WorkflowExplorer({
  nodes,
  langgraph,
  onClose,
}: {
  nodes: WorkflowNode[];
  langgraph: boolean;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const node = selected != null ? nodes[selected] : null;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        background:
          "radial-gradient(circle at 50% 30%, #0b1e3a 0%, #060b1a 55%, #03060f 100%)",
      }}
    >
      <div className="flex items-center justify-between px-5 py-3">
        <div>
          <p className="text-sm font-semibold text-cyan-100">Workflow — Immersive 3D</p>
          <p className="text-[11px] text-slate-400">
            {langgraph ? "Orchestrated via LangGraph" : "Sequential execution"} · drag to
            rotate · scroll to zoom · click a node
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 backdrop-blur hover:bg-white/10"
        >
          ✕ Close
        </button>
      </div>

      <div className="relative flex-1">
        <ErrorBoundary
          fallback={
            <div className="flex h-full items-center justify-center px-6 text-center">
              <p className="max-w-sm text-sm text-slate-400">
                The 3D view couldn't start on this device (WebGL unavailable). The
                pipeline panel still shows every node, status, and timing.
              </p>
            </div>
          }
        >
          <WorkflowScene nodes={nodes} selected={selected} onSelect={setSelected} />
        </ErrorBoundary>

        {node && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="absolute bottom-5 left-1/2 w-[90%] max-w-md -translate-x-1/2 rounded-2xl border border-white/10 bg-black/50 p-4 backdrop-blur"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-100">{node.label}</p>
              <span className="text-[11px] text-slate-400">
                {STATUS_LABEL[node.status || "pending"]}
                {node.status === "ok" && ` · ${Math.round(node.duration_ms || 0)}ms`}
                {node.retries ? ` · ${node.retries} retr${node.retries > 1 ? "ies" : "y"}` : ""}
              </span>
            </div>
            <p className="mt-1 text-[12px] text-slate-400">{node.desc}</p>
            {node.detail && (
              <p className="mt-2 text-[12px] text-teal-200">{node.detail}</p>
            )}
            {node.error && (
              <p className="mt-2 text-[12px] text-rose-300">Error: {node.error}</p>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
