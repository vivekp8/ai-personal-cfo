import { motion } from "framer-motion";

export type VoiceState = "idle" | "listening" | "thinking" | "speaking";

const COLORS: Record<VoiceState, string> = {
  idle: "#64748b",
  listening: "#2dd4bf",
  thinking: "#a78bfa",
  speaking: "#38bdf8",
};

// Lightweight pulsing orb (CSS/framer, not WebGL) used in the voice button.
export default function VoiceOrb({
  state,
  amplitude = 0,
  size = 56,
}: {
  state: VoiceState;
  amplitude?: number;
  size?: number;
}) {
  const color = COLORS[state];
  const active = state !== "idle";
  const scale = 1 + amplitude * 0.4;

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      {active && (
        <motion.span
          className="absolute inset-0 rounded-full"
          style={{ background: color, opacity: 0.25 }}
          animate={{ scale: [1, 1.6, 1], opacity: [0.25, 0, 0.25] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <motion.span
        className="relative rounded-full"
        style={{
          width: size * 0.6,
          height: size * 0.6,
          background: `radial-gradient(circle at 30% 30%, ${color}, ${color}88)`,
          boxShadow: `0 0 ${active ? 24 : 8}px ${color}`,
        }}
        animate={{ scale: active ? scale : 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 15 }}
      >
        {state === "idle" && (
          <span className="absolute inset-0 flex items-center justify-center text-white/90">
            🎤
          </span>
        )}
      </motion.span>
    </div>
  );
}
