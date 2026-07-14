import { useEffect } from "react";
import { animate, useMotionValue, useTransform, motion } from "framer-motion";
import { useReduceMotion } from "../lib/motion";

interface Props {
  value: number;
  format?: (n: number) => string;
  duration?: number;
  className?: string;
}

// Counts up from 0 (or current) to value. Respects reduce-motion.
export default function AnimatedNumber({
  value,
  format = (n) => Math.round(n).toString(),
  duration = 1.2,
  className,
}: Props) {
  const { reduceMotion } = useReduceMotion();
  const mv = useMotionValue(reduceMotion ? value : 0);
  const text = useTransform(mv, (v) => format(v));

  useEffect(() => {
    if (reduceMotion) {
      mv.set(value);
      return;
    }
    const controls = animate(mv, value, { duration, ease: "easeOut" });
    return () => controls.stop();
  }, [value, duration, reduceMotion, mv]);

  return <motion.span className={className}>{text}</motion.span>;
}
