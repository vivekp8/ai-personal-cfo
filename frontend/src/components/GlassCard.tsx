import { motion } from "framer-motion";
import { ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
  delay?: number;
  title?: string;
  subtitle?: string;
}

// Staggered fade/slide/scale-in glass card.
export default function GlassCard({ children, className = "", delay = 0, title, subtitle }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className={`glass rounded-2xl p-5 shadow-xl shadow-black/20 ${className}`}
    >
      {title && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            {title}
          </h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
      )}
      {children}
    </motion.div>
  );
}
