// web/src/types/api.ts

export interface UsageRecord {
  date: string;           // "YYYY-MM-DD" — never a Date object
  model: string;          // e.g. "deepseek/deepseek-r1:free"
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: string;       // "0.00120000" — 8dp decimal string from API
}

export interface UsageResponse {
  records: UsageRecord[];
  total_cost_usd: string; // "0.00120000" — 8dp decimal string
  period_days: number;    // always 30 in V1
}
