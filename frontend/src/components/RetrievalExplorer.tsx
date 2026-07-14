import { useState } from "react";
import { motion } from "framer-motion";
import { RagTraceResult } from "../api";
import ErrorBoundary from "./ErrorBoundary";
import RetrievalScene from "../three/RetrievalScene";

const STAGES = [
  "Question",
  "Embedding",
  "Retrieved Chunks",
  "Similarity Score",
  "Ranking",
  "Final Context",
  "LLM Response",
];

function collLabel(c: string): string {
  return c === "user_memory" ? "Your memory" : "Knowledge base";
}

export default function RetrievalExplorer({
  trace,
  onClose,
}: {
  trace: RagTraceResult;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<number | null>(0);
  const chunks = trace.chunks || [];
  const queryPoint = (trace.embedding?.query_point ?? [0, 0, 0]) as [number, number, number];
  const sel = selected != null ? chunks[selected] : null;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        background:
          "radial-gradient(circle at 50% 20%, #0b1e3a 0%, #060b1a 55%, #03060f 100%)",
      }}
    >
      {/* Header: query + pipeline stages */}
      <div className="relative z-10 border-b border-white/10 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              RAG Retrieval Explorer
            </p>
            <p className="truncate text-sm text-slate-100">“{trace.query}”</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 backdrop-blur hover:bg-white/10"
          >
            ✕ Close
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {STAGES.map((s, i) => (
            <motion.span
              key={s}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.12 }}
              className="flex items-center gap-1.5"
            >
              <span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-2.5 py-1 text-[11px] text-teal-100">
                {s}
              </span>
              {i < STAGES.length - 1 && <span className="text-slate-600">→</span>}
            </motion.span>
          ))}
        </div>
      </div>

      {/* Body: 3D scene + details */}
      <div className="relative z-10 flex flex-1 flex-col overflow-hidden lg:flex-row">
        <div className="relative flex-1">
          <ErrorBoundary
            fallback={
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-400">
                3D view unavailable on this device (WebGL). The ranked chunks are
                listed on the right.
              </div>
            }
          >
            <RetrievalScene
              queryPoint={queryPoint}
              chunks={chunks}
              selected={selected}
              onSelect={setSelected}
            />
          </ErrorBoundary>

          {/* Legend */}
          <div className="pointer-events-none absolute bottom-4 left-4 flex flex-col gap-1 text-[11px] text-slate-300">
            <span><span style={{ color: "#f472b6" }}>●</span> Query</span>
            <span><span style={{ color: "#22d3ee" }}>●</span> Knowledge base</span>
            <span><span style={{ color: "#a78bfa" }}>●</span> Your memory</span>
            <span className="mt-1 text-slate-500">Drag to rotate · scroll to zoom · closer = more similar</span>
          </div>
        </div>

        {/* Details panel */}
        <div className="w-full shrink-0 overflow-y-auto border-t border-white/10 bg-black/30 p-4 backdrop-blur lg:w-96 lg:border-l lg:border-t-0">
          <p className="mb-2 text-xs uppercase tracking-wider text-slate-400">
            Retrieved chunks ({chunks.length}) · dim {trace.embedding?.dimension}
          </p>
          <div className="space-y-2">
            {chunks.map((c, i) => (
              <button
                key={i}
                onClick={() => setSelected(i)}
                className={`block w-full rounded-xl border p-2.5 text-left transition-colors ${
                  selected === i
                    ? "border-teal-accent/50 bg-teal-accent/10"
                    : "border-white/10 bg-white/5 hover:bg-white/10"
                }`}
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">
                    #{c.rank} · {collLabel(c.collection)}
                  </span>
                  <span
                    className="font-mono"
                    style={{ color: c.collection === "user_memory" ? "#a78bfa" : "#22d3ee" }}
                  >
                    {Math.round(c.similarity * 100)}%
                  </span>
                </div>
                <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.round(c.similarity * 100)}%`,
                      background: c.collection === "user_memory" ? "#a78bfa" : "#22d3ee",
                    }}
                  />
                </div>
                {selected === i && (
                  <p className="mt-2 text-[12px] leading-relaxed text-slate-200">
                    {c.text}
                  </p>
                )}
              </button>
            ))}
          </div>

          {sel && (
            <div className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3 text-[11px] text-slate-400">
              cosine similarity {sel.similarity.toFixed(3)} · distance{" "}
              {sel.distance.toFixed(3)}
            </div>
          )}

          <p className="mt-4 mb-1 text-xs uppercase tracking-wider text-slate-400">
            Final context → LLM
          </p>
          <pre className="whitespace-pre-wrap rounded-xl bg-black/40 p-3 text-[11px] leading-relaxed text-teal-100">
            {trace.final_context || "(empty)"}
          </pre>
        </div>
      </div>
    </motion.div>
  );
}
