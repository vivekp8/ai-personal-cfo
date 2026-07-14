// Formatting helpers (Indian rupee / number formatting).

export function inr(value: number, opts: { compact?: boolean } = {}): string {
  if (opts.compact) {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 1,
      notation: "compact",
    }).format(value);
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export function monthLabel(ym: string): string {
  // "2025-04" -> "Apr 2025"
  const [y, m] = ym.split("-");
  const date = new Date(Number(y), Number(m) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export const CATEGORY_COLORS: Record<string, string> = {
  Housing: "#a78bfa",
  Utilities: "#38bdf8",
  Food: "#2dd4bf",
  Shopping: "#f472b6",
  Entertainment: "#fbbf24",
  Travel: "#fb923c",
  Income: "#4ade80",
  Uncategorized: "#94a3b8",
};

export function categoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] ?? "#94a3b8";
}
