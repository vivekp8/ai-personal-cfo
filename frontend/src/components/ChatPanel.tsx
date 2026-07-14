import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Capabilities,
  ChatResponse,
  clearChatHistory,
  getChatHistory,
  sendChat,
} from "../api";
import GlassCard from "./GlassCard";

interface Msg {
  role: "user" | "assistant";
  text: string;
  context?: string[];
  llmUsed?: boolean;
}

const SUGGESTIONS = [
  "Why is my score where it is?",
  "How much did I spend on food?",
  "What can I cut back on?",
  "What's my forecast for next month?",
];

export default function ChatPanel({
  capabilities,
  delay = 0,
}: {
  capabilities: Capabilities | null;
  delay?: number;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Load persisted conversation memory so follow-ups have context on reload.
  useEffect(() => {
    let cancelled = false;
    getChatHistory()
      .then(({ history }) => {
        if (cancelled) return;
        setMessages(
          history.map((h) => ({
            role: h.role,
            text: h.content,
            llmUsed: h.llm_used ?? undefined,
          }))
        );
        requestAnimationFrame(() =>
          scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
        );
      })
      .catch(() => {
        /* no history yet — fine */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleClear() {
    try {
      await clearChatHistory();
    } catch {
      /* ignore */
    }
    setMessages([]);
    setExpanded(null);
  }

  function scrollDown() {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  async function ask(query: string) {
    if (!query.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text: query }]);
    setInput("");
    setBusy(true);
    scrollDown();
    try {
      const res: ChatResponse = await sendChat(query);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.response,
          context: res.retrieved_context,
          llmUsed: res.llm_used,
        },
      ]);
      scrollDown();
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: e instanceof Error ? e.message : "Something went wrong.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard title="Ask your CFO" subtitle="Grounded in your data" delay={delay}>
      <div className="flex flex-col" style={{ height: 420 }}>
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl">
                💬
              </div>
              <p className="mt-3 text-sm text-slate-400 max-w-xs">
                Ask about your spending, score, forecast, or savings. Try:
              </p>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/10 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                  m.role === "user"
                    ? "bg-teal-accent/20 text-teal-50"
                    : "bg-white/5 text-slate-200"
                }`}
              >
                <p className="whitespace-pre-wrap">{m.text}</p>
                {m.role === "assistant" && m.context && m.context.length > 0 && (
                  <div className="mt-2">
                    <button
                      onClick={() => setExpanded((p) => (p === i ? null : i))}
                      className="text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                    >
                      {expanded === i ? "▾ Hide reasoning" : "▸ Show reasoning"}
                      {m.llmUsed === false && " (computed, LLM off)"}
                    </button>
                    <AnimatePresence>
                      {expanded === i && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-2 overflow-hidden"
                        >
                          <p className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
                            Retrieved context
                          </p>
                          <ul className="space-y-1">
                            {m.context.map((c, ci) => (
                              <li
                                key={ci}
                                className="rounded-md bg-black/30 px-2 py-1 text-[11px] text-slate-400"
                              >
                                {c}
                              </li>
                            ))}
                          </ul>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-white/5 px-4 py-3">
                <div className="flex gap-1">
                  {[0, 1, 2].map((d) => (
                    <motion.span
                      key={d}
                      className="h-2 w-2 rounded-full bg-slate-400"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1, repeat: Infinity, delay: d * 0.2 }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(input)}
            placeholder="Type your question…"
            className="flex-1 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-teal-accent/50"
          />
          <button
            onClick={() => ask(input)}
            disabled={busy || !input.trim()}
            className="rounded-xl bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-40 transition-opacity"
          >
            Send
          </button>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              disabled={busy}
              title="Clear conversation memory"
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-slate-300 hover:bg-white/10 disabled:opacity-40 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
