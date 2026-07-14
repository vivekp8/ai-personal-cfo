import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { DashboardData, uploadCsv } from "../api";
import { useReduceMotion } from "../lib/motion";
import ErrorBoundary from "./ErrorBoundary";

const ANALYZE_STAGES = [
  "Reading transactions…",
  "Categorizing your spending…",
  "Detecting anomalies…",
  "Forecasting next month…",
  "Scoring your financial health…",
];

const ACCEPTED =
  ".csv,.tsv,.txt,.xlsx,.xlsm,.xls,.ods,.json,.pdf";

const HeroScene = lazy(() => import("../three/HeroScene"));

interface Props {
  onLoaded: (data: DashboardData) => void;
}

export default function Landing({ onLoaded }: Props) {
  const { reduceMotion } = useReduceMotion();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Drive an animated progress bar + rotating stage labels while uploading.
  useEffect(() => {
    if (!busy) {
      setProgress(0);
      setStage(0);
      return;
    }
    setProgress(6);
    // Ease toward ~92% so it feels alive but never "finishes" before the API does.
    const barTimer = setInterval(() => {
      setProgress((p) => (p < 92 ? p + Math.max(0.6, (92 - p) * 0.05) : p));
    }, 120);
    const stageTimer = setInterval(() => {
      setStage((s) => Math.min(s + 1, ANALYZE_STAGES.length - 1));
    }, 1200);
    return () => {
      clearInterval(barTimer);
      clearInterval(stageTimer);
    };
  }, [busy]);

  async function handleFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      const data = await uploadCsv(file);
      // Snap to completion so the bar visibly finishes before the view swaps.
      setStage(ANALYZE_STAGES.length - 1);
      setProgress(100);
      await new Promise((r) => setTimeout(r, 350));
      onLoaded(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden ambient-bg">
      {/* 3D hero background (code-split, disabled under reduce-motion) */}
      {!reduceMotion && (
        <div className="absolute inset-0 z-0 opacity-80">
          <ErrorBoundary fallback={null}>
            <Suspense fallback={null}>
              <HeroScene />
            </Suspense>
          </ErrorBoundary>
        </div>
      )}

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="text-center mb-8"
        >
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-teal-accent via-white to-violet-accent bg-clip-text text-transparent">
              AI Personal CFO
            </span>
          </h1>
          <p className="mt-3 max-w-xl mx-auto text-slate-300 text-sm md:text-base">
            Upload a bank statement and get instant categorization, anomaly
            detection, forecasts, a financial health score, and an AI advisor you
            can talk to.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="w-full max-w-lg"
        >
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) handleFile(f);
            }}
            onClick={() => inputRef.current?.click()}
            className={`glass-strong cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all ${
              dragOver
                ? "border-teal-accent bg-teal-accent/5 scale-[1.02]"
                : "border-white/15 hover:border-white/30"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            {busy ? (
              <div className="flex w-full flex-col items-center gap-4 py-2">
                <div className="flex items-center justify-between w-full text-sm">
                  <motion.p
                    key={stage}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-slate-200"
                  >
                    {ANALYZE_STAGES[stage]}
                  </motion.p>
                  <span className="font-mono text-teal-accent">
                    {Math.round(progress)}%
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-teal-accent to-violet-accent"
                    style={{ boxShadow: "0 0 12px rgba(45,212,191,0.6)" }}
                    animate={{ width: `${progress}%` }}
                    transition={{ ease: "easeOut", duration: 0.3 }}
                  />
                </div>
                <p className="text-xs text-slate-400">Analyzing your statement…</p>
              </div>
            ) : (
              <>
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-2xl">
                  📄
                </div>
                <p className="font-semibold text-slate-100">
                  Drop your statement here or click to browse
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  CSV, Excel, TSV, JSON or PDF — with date, description and amount
                </p>
              </>
            )}
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-3 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-300"
            >
              {error}
            </motion.p>
          )}

          <p className="mt-6 text-center text-xs text-slate-500">
            Your file is processed in real time and never leaves your machine.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
