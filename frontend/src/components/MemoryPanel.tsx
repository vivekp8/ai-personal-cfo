import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MemoryByKind, addGoal, addPreference, getMemory } from "../api";
import GlassCard from "./GlassCard";

const KIND_META: Record<string, { label: string; icon: string; color: string }> = {
  habit: { label: "Habits", icon: "🔁", color: "#2dd4bf" },
  recurring: { label: "Recurring", icon: "📅", color: "#38bdf8" },
  subscription: { label: "Subscriptions", icon: "📺", color: "#a78bfa" },
  salary: { label: "Salary history", icon: "💵", color: "#4ade80" },
  goal: { label: "Goals", icon: "🎯", color: "#fbbf24" },
  preference: { label: "Preferences", icon: "⚙️", color: "#f472b6" },
  conversation_summary: { label: "Remembered topics", icon: "💬", color: "#94a3b8" },
};

const ORDER = [
  "goal",
  "preference",
  "subscription",
  "recurring",
  "habit",
  "salary",
  "conversation_summary",
];

function MemoryChip({ text, color, index }: { text: string; color: string; index: number }) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 10, rotateX: -10 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ delay: index * 0.03, type: "spring", stiffness: 140, damping: 16 }}
      whileHover={{ scale: 1.02, rotateY: 3, translateZ: 12 }}
      style={{ transformStyle: "preserve-3d", borderLeft: `2px solid ${color}` }}
      className="rounded-md bg-white/5 px-3 py-1.5 text-[12px] text-slate-200"
    >
      {text}
    </motion.li>
  );
}

export default function MemoryPanel({ delay = 0 }: { delay?: number }) {
  const [memory, setMemory] = useState<MemoryByKind>({});
  const [busy, setBusy] = useState(false);
  const [goalName, setGoalName] = useState("");
  const [goalAmount, setGoalAmount] = useState("");
  const [prefKey, setPrefKey] = useState("");
  const [prefValue, setPrefValue] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const { memory: m } = await getMemory();
      setMemory(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load memory");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function saveGoal() {
    if (!goalName.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await addGoal(goalName.trim(), goalAmount ? Number(goalAmount) : null);
      setGoalName("");
      setGoalAmount("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save goal");
    } finally {
      setBusy(false);
    }
  }

  async function savePref() {
    if (!prefKey.trim() || !prefValue.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await addPreference(prefKey.trim(), prefValue.trim());
      setPrefKey("");
      setPrefValue("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save preference");
    } finally {
      setBusy(false);
    }
  }

  const kinds = ORDER.filter((k) => (memory[k] || []).length > 0);
  const total = Object.values(memory).reduce((n, arr) => n + arr.length, 0);

  return (
    <GlassCard
      title="Long-Term Memory"
      subtitle={`What your CFO remembers about you · ${total} items`}
      delay={delay}
    >
      {/* Quick add: goal + preference */}
      <div className="mb-4 grid gap-2 md:grid-cols-2">
        <div className="flex gap-2">
          <input
            value={goalName}
            onChange={(e) => setGoalName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveGoal()}
            placeholder="Add a goal (e.g. Emergency fund)"
            className="flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
          />
          <input
            value={goalAmount}
            onChange={(e) => setGoalAmount(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="₹"
            className="w-20 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
          />
          <button
            onClick={saveGoal}
            disabled={busy || !goalName.trim()}
            className="rounded-lg bg-teal-accent px-3 py-2 text-sm font-semibold text-navy-900 disabled:opacity-40"
          >
            +
          </button>
        </div>
        <div className="flex gap-2">
          <input
            value={prefKey}
            onChange={(e) => setPrefKey(e.target.value)}
            placeholder="Preference"
            className="w-1/3 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
          />
          <input
            value={prefValue}
            onChange={(e) => setPrefValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && savePref()}
            placeholder="Value"
            className="flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
          />
          <button
            onClick={savePref}
            disabled={busy || !prefKey.trim() || !prefValue.trim()}
            className="rounded-lg bg-violet-accent px-3 py-2 text-sm font-semibold text-navy-900 disabled:opacity-40"
          >
            +
          </button>
        </div>
      </div>

      {error && <p className="mb-2 text-sm text-rose-300">{error}</p>}

      {total === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">
          Nothing remembered yet. Upload a statement and chat — your CFO will
          learn your habits, subscriptions, salary, and goals.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2" style={{ perspective: 1000 }}>
          {kinds.map((k) => {
            const meta = KIND_META[k] || { label: k, icon: "•", color: "#94a3b8" };
            const items = memory[k] || [];
            return (
              <motion.div
                key={k}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-white/10 bg-white/5 p-3"
              >
                <p
                  className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: meta.color }}
                >
                  <span>{meta.icon}</span>
                  {meta.label}
                  <span className="text-slate-500">({items.length})</span>
                </p>
                <ul className="space-y-1">
                  <AnimatePresence>
                    {items.slice(0, 6).map((m, i) => (
                      <MemoryChip
                        key={m.mem_key}
                        text={m.content}
                        color={meta.color}
                        index={i}
                      />
                    ))}
                  </AnimatePresence>
                </ul>
                {items.length > 6 && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    +{items.length - 6} more
                  </p>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </GlassCard>
  );
}
