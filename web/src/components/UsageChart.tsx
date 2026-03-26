// web/src/components/UsageChart.tsx
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { UsageRecord } from "../types/api";
import { groupByDay } from "../utils/usage";

export function UsageChart({ records }: { records: UsageRecord[] }) {
  const chartData = groupByDay(records);

  if (chartData.length === 0) {
    return (
      <p className="text-gray-500 text-sm py-12 text-center">
        No usage yet. Run your first task.
      </p>
    );
  }

  return (
    <div role="img" aria-label="30-day token usage bar chart">
      <ResponsiveContainer width="100%" height={192}>
        <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(date: string) =>
              new Date(date + "T00:00:00").toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })
            }
          />
          <Tooltip
            formatter={(value: number) => [value.toLocaleString(), "Tokens"]}
            labelFormatter={(label: string) =>
              new Date(label + "T00:00:00").toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })
            }
          />
          <Bar dataKey="tokens" fill="#2563eb" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
