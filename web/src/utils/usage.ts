// web/src/utils/usage.ts
import type { UsageRecord } from "../types/api";

// Group by day for bar chart — sum prompt + completion tokens per calendar date
export function groupByDay(records: UsageRecord[]): { date: string; tokens: number }[] {
  const map = new Map<string, number>();
  for (const r of records) {
    const tokens = r.prompt_tokens + r.completion_tokens;
    map.set(r.date, (map.get(r.date) ?? 0) + tokens);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b)) // ascending date order for chart
    .map(([date, tokens]) => ({ date, tokens }));
}

// Group by model for table — sum tokens and cost per model string
export function groupByModel(
  records: UsageRecord[]
): { model: string; tokens: number; cost: number }[] {
  const map = new Map<string, { tokens: number; cost: number }>();
  for (const r of records) {
    const tokens = r.prompt_tokens + r.completion_tokens;
    const cost = parseFloat(r.cost_usd) || 0; // NaN-safe — malformed strings fall back to 0
    const existing = map.get(r.model) ?? { tokens: 0, cost: 0 };
    map.set(r.model, { tokens: existing.tokens + tokens, cost: existing.cost + cost });
  }
  return Array.from(map.entries()).map(([model, { tokens, cost }]) => ({
    model,
    tokens,
    cost,
  }));
}
