import { createContext, useContext, useEffect, useState, ReactNode } from "react";

// Global "reduce motion" toggle. When enabled we disable the 3D background and
// heavy animations (accessibility + low-end devices). Persisted to localStorage.
interface MotionCtx {
  reduceMotion: boolean;
  toggle: () => void;
}

const Ctx = createContext<MotionCtx>({ reduceMotion: false, toggle: () => {} });

export function MotionProvider({ children }: { children: ReactNode }) {
  const [reduceMotion, setReduceMotion] = useState<boolean>(() => {
    const stored = localStorage.getItem("reduceMotion");
    if (stored !== null) return stored === "1";
    // Respect the OS-level preference by default.
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });

  useEffect(() => {
    localStorage.setItem("reduceMotion", reduceMotion ? "1" : "0");
    document.body.classList.toggle("reduce-motion", reduceMotion);
  }, [reduceMotion]);

  return (
    <Ctx.Provider value={{ reduceMotion, toggle: () => setReduceMotion((v) => !v) }}>
      {children}
    </Ctx.Provider>
  );
}

export function useReduceMotion(): MotionCtx {
  return useContext(Ctx);
}
