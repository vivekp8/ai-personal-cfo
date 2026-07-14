import { Capabilities } from "../api";
import { useReduceMotion } from "../lib/motion";

interface Props {
  capabilities: Capabilities | null;
  onReset?: () => void;
  showReset?: boolean;
}

function Badge({ ok, label, degraded }: { ok: boolean; label: string; degraded?: string }) {
  return (
    <span
      title={ok ? `${label} active` : degraded || `${label} unavailable`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${
        ok
          ? "bg-teal-accent/15 text-teal-accent"
          : "bg-slate-500/15 text-slate-400"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-teal-accent" : "bg-slate-500"}`} />
      {label}
    </span>
  );
}

export default function Header({ capabilities, onReset, showReset }: Props) {
  const { reduceMotion, toggle } = useReduceMotion();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-6 py-4 glass-strong border-b border-white/5">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-accent to-teal-accent text-navy-900 font-extrabold">
          ₹
        </div>
        <div>
          <h1 className="text-base font-bold leading-tight">AI Personal CFO</h1>
          <p className="text-[11px] text-slate-400 leading-tight">
            Your finances, explained.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {capabilities && (
          <div className="hidden md:flex items-center gap-1.5 mr-1">
            <Badge
              ok={capabilities.llm_configured}
              label="LLM"
              degraded="Gemini key not configured — showing computed values only"
            />
            <Badge ok={capabilities.rag_available} label="RAG" />
            <Badge
              ok={(capabilities.voice?.stt_providers?.length ?? 0) > 0}
              label="Voice"
              degraded="No speech-to-text provider — set GROQ_API_KEY or install openai-whisper"
            />
          </div>
        )}

        <button
          onClick={toggle}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 transition-colors"
          title="Disable 3D background and heavy animations"
        >
          {reduceMotion ? "Motion: Off" : "Motion: On"}
        </button>

        {showReset && (
          <button
            onClick={onReset}
            className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/10 transition-colors"
          >
            New Upload
          </button>
        )}
      </div>
    </header>
  );
}
