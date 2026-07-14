import { useMemo } from "react";
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceDot,
} from "recharts";
import { Forecast } from "../api";
import { inr, monthLabel } from "../lib/format";
import GlassCard from "./GlassCard";

export default function ForecastChart({
  forecast,
  delay = 0,
}: {
  forecast: Forecast;
  delay?: number;
}) {
  const data = useMemo(() => {
    const rows = forecast.history.months.map((m, i) => ({
      month: monthLabel(m),
      expenses: forecast.history.expenses[i],
      forecast: null as number | null,
    }));
    rows.push({
      month: monthLabel(forecast.next_month),
      expenses: null as unknown as number,
      forecast: forecast.total_expense_forecast,
    });
    // connect the line: last actual also seeds the forecast series
    if (rows.length >= 2) {
      rows[rows.length - 2].forecast = rows[rows.length - 2].expenses;
    }
    return rows;
  }, [forecast]);

  return (
    <GlassCard
      title="Expense Forecast"
      subtitle={`Next month (${monthLabel(forecast.next_month)}) projected at ${inr(
        forecast.total_expense_forecast
      )}`}
      delay={delay}
    >
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
            <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
            <YAxis
              stroke="#94a3b8"
              fontSize={11}
              tickFormatter={(v) => inr(v, { compact: true })}
            />
            <Tooltip
              formatter={(v: number) => inr(v)}
              contentStyle={{
                background: "rgba(15,22,38,0.95)",
                border: "1px solid rgba(148,163,184,0.2)",
                borderRadius: 12,
                color: "#e5e9f0",
              }}
            />
            <Line
              type="monotone"
              dataKey="expenses"
              stroke="#2dd4bf"
              strokeWidth={2.5}
              dot={{ r: 4, fill: "#2dd4bf" }}
              name="Actual"
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="forecast"
              stroke="#a78bfa"
              strokeWidth={2.5}
              strokeDasharray="6 4"
              dot={{ r: 4, fill: "#a78bfa" }}
              name="Forecast"
              connectNulls
            />
            <ReferenceDot
              x={monthLabel(forecast.next_month)}
              y={forecast.total_expense_forecast}
              r={6}
              fill="#a78bfa"
              stroke="#fff"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex gap-4 text-xs text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-4 rounded bg-teal-accent" /> Actual
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-4 rounded bg-violet-accent" /> Forecast
        </span>
      </div>
    </GlassCard>
  );
}
