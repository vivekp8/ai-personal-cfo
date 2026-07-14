import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Capabilities, sendChat, speak, transcribeAudio } from "../api";
import { useVoiceRecorder } from "../lib/useVoice";
import ErrorBoundary from "./ErrorBoundary";
import VoiceWaveCanvas from "./VoiceWaveCanvas";

type Status = "idle" | "listening" | "thinking" | "speaking";

const STATUS_LABEL: Record<Status, string> = {
  idle: "Tap the mic and ask your question",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

// Neon glowing microphone icon (matches the reference look).
function NeonMic({ active }: { active: boolean }) {
  const glow = active ? "#38bdf8" : "#22d3ee";
  return (
    <motion.svg
      width="72"
      height="72"
      viewBox="0 0 24 24"
      fill="none"
      stroke={glow}
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      animate={active ? { scale: [1, 1.06, 1] } : { scale: 1 }}
      transition={{ duration: 1.4, repeat: active ? Infinity : 0, ease: "easeInOut" }}
      style={{ filter: `drop-shadow(0 0 10px ${glow}) drop-shadow(0 0 22px ${glow})` }}
    >
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="17" x2="12" y2="21" />
      <line x1="8" y1="21" x2="16" y2="21" />
    </motion.svg>
  );
}

export default function VoiceAssistant({
  capabilities,
  onClose,
}: {
  capabilities: Capabilities | null;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [question, setQuestion] = useState<string>("");
  const [answer, setAnswer] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [meta, setMeta] = useState<{
    provider?: string;
    confidence?: number;
    latency?: number;
    lowConfidence?: boolean;
  } | null>(null);
  const voice = useVoiceRecorder();
  // A single, reusable <audio> element we "unlock" on the user gesture so the
  // browser's autoplay policy doesn't block playback after async awaits.
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      // Stop any ongoing speech when the overlay closes/unmounts.
      try {
        window.speechSynthesis?.cancel();
      } catch {
        /* ignore */
      }
      audioRef.current?.pause();
    };
  }, []);

  const active = status === "listening";

  // Unlock audio playback within a user gesture (muted play is always allowed).
  function unlockAudio() {
    if (!audioRef.current) audioRef.current = new Audio();
    const a = audioRef.current;
    a.muted = true;
    a.play().catch(() => {});
    a.pause();
    a.currentTime = 0;
    a.muted = false;
  }

  // Speak text: prefer natural server TTS (gTTS); fall back to the browser's
  // built-in speech synthesis so the assistant always talks back.
  async function speakResponse(text: string): Promise<void> {
    setStatus("speaking");
    const finish = () => setStatus("idle");

    if (capabilities?.gtts) {
      try {
        const audioBlob = await speak(text);
        const url = URL.createObjectURL(audioBlob);
        const a = audioRef.current ?? new Audio();
        audioRef.current = a;
        a.src = url;
        a.onended = () => {
          URL.revokeObjectURL(url);
          finish();
        };
        await a.play();
        return; // playing successfully
      } catch {
        // Autoplay blocked or TTS failed — fall through to speechSynthesis.
      }
    }

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.rate = 1.0;
        utter.pitch = 1.0;
        utter.onend = finish;
        utter.onerror = finish;
        window.speechSynthesis.speak(utter);
        return;
      } catch {
        /* ignore */
      }
    }
    finish(); // no TTS available — answer is still shown on screen
  }

  async function handleMic() {
    setError("");
    if (voice.recording) {
      // Unlock audio now, while we still have the user's tap gesture.
      unlockAudio();
      setStatus("thinking");
      const blob = await voice.stop();
      if (!blob || blob.size < 1200) {
        setStatus("idle");
        setError("That was too short. Tap the mic, wait a beat, then speak.");
        return;
      }
      try {
        let query = "";
        try {
          const res = await transcribeAudio(blob);
          query = (res.text || "").trim();
          setMeta({
            provider: res.provider,
            confidence: res.confidence,
            latency: res.latency_ms,
            lowConfidence: res.low_confidence,
          });
        } catch {
          // Server transcription unavailable — use the live browser transcript.
          query = (voice.liveTranscript || "").trim();
          setMeta(null);
        }
        if (!query) query = (voice.liveTranscript || "").trim();
        if (!query) {
          setStatus("idle");
          setError(
            "I couldn't make out any speech clearly. Please try again, a little louder and closer to the mic."
          );
          return;
        }
        setQuestion(query);
        setAnswer("");
        const res = await sendChat(query);
        setAnswer(res.response);
        await speakResponse(res.response);
      } catch (e) {
        setStatus("idle");
        setError(
          e instanceof Error
            ? e.message
            : "Something went wrong processing your question."
        );
      }
    } else {
      setError("");
      setQuestion("");
      setAnswer("");
      setMeta(null);
      setStatus("listening");
      const startError = await voice.start();
      if (startError) {
        setStatus("idle");
        setError(startError);
      }
    }
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        background:
          "radial-gradient(circle at 50% 30%, #0b1e3a 0%, #060b1a 55%, #03060f 100%)",
      }}
    >
      {/* Animated sound-wave field fills the screen (2D canvas, crash-isolated) */}
      <div className="pointer-events-none absolute inset-0">
        <ErrorBoundary fallback={null}>
          <VoiceWaveCanvas amplitude={voice.amplitude} active={active} />
        </ErrorBoundary>
      </div>

      {/* Close button */}
      <button
        onClick={() => {
          if (voice.recording) voice.stop();
          try {
            window.speechSynthesis?.cancel();
          } catch {
            /* ignore */
          }
          audioRef.current?.pause();
          onClose();
        }}
        className="absolute right-5 top-5 z-10 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 backdrop-blur hover:bg-white/10 transition-colors"
      >
        ✕ Close
      </button>

      {/* Center content */}
      <div className="relative z-10 -mt-24 flex flex-col items-center px-6 text-center">
        {/* Pulsing halo behind the mic */}
        <div className="relative flex h-40 w-40 items-center justify-center">
          {active && (
            <>
              <motion.span
                className="absolute rounded-full border border-cyan-400/40"
                style={{ width: 120, height: 120 }}
                animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              />
              <motion.span
                className="absolute rounded-full border border-sky-400/30"
                style={{ width: 120, height: 120 }}
                animate={{ scale: [1, 2.4], opacity: [0.4, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut", delay: 0.6 }}
              />
            </>
          )}
          <button
            onClick={handleMic}
            className="relative flex h-28 w-28 items-center justify-center rounded-full border border-cyan-400/30 bg-white/5 backdrop-blur transition-transform hover:scale-105"
            title={active ? "Tap to send" : "Tap to speak"}
          >
            <NeonMic active={active} />
          </button>
        </div>

        <p className="mt-8 text-lg font-medium text-cyan-100">
          {STATUS_LABEL[status]}
        </p>

        {/* Live indicators: provider · confidence · latency */}
        {meta && !voice.recording && (
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2 text-[11px]">
            {meta.provider && (
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-slate-300">
                🎙 {meta.provider}
              </span>
            )}
            {typeof meta.confidence === "number" && (
              <span
                className="rounded-full px-2 py-0.5"
                style={{
                  background: meta.lowConfidence ? "#f59e0b22" : "#2dd4bf22",
                  color: meta.lowConfidence ? "#f59e0b" : "#2dd4bf",
                }}
              >
                {Math.round(meta.confidence * 100)}% confidence
              </span>
            )}
            {typeof meta.latency === "number" && meta.latency > 0 && (
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-slate-400">
                {Math.round(meta.latency)}ms
              </span>
            )}
          </div>
        )}
        {meta?.lowConfidence && !voice.recording && (
          <p className="mt-1 text-[11px] text-amber-300/80">
            Low confidence — tap the mic to repeat if this looks wrong.
          </p>
        )}

        {/* Live transcript while speaking */}
        <div className="mt-3 min-h-[2.5rem] max-w-xl">
          <AnimatePresence mode="wait">
            {voice.recording && voice.liveTranscript && (
              <motion.p
                key="live"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-xl italic text-white"
              >
                “{voice.liveTranscript}”
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        {/* Recognized question */}
        <AnimatePresence>
          {question && !voice.recording && (
            <motion.p
              key="question"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-2 max-w-xl text-lg italic text-white/90"
            >
              “{question}”
            </motion.p>
          )}
        </AnimatePresence>

        {/* Assistant answer */}
        <AnimatePresence>
          {answer && !voice.recording && (
            <motion.div
              key="answer"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-4 max-w-xl rounded-2xl border border-white/10 bg-black/30 px-5 py-4 text-left text-sm leading-relaxed text-slate-100 backdrop-blur"
            >
              {answer}
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <p className="mt-4 max-w-md text-sm text-rose-300">{error}</p>
        )}

        {!(capabilities?.voice?.stt_providers?.length) && (
          <p className="mt-6 text-xs text-amber-300/80">
            No speech-to-text provider is available on the server — the live
            preview still works, but final answers may not. Set GROQ_API_KEY or
            install openai-whisper to enable transcription.
          </p>
        )}
      </div>
    </motion.div>
  );
}
