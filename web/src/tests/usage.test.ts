// web/src/tests/usage.test.ts
import { describe, it, expect } from "vitest";
import { groupByDay, groupByModel } from "../utils/usage";
import type { UsageRecord } from "../types/api";

const makeRecord = (overrides: Partial<UsageRecord> = {}): UsageRecord => ({
  date: "2026-03-20",
  model: "deepseek/deepseek-r1:free",
  prompt_tokens: 100,
  completion_tokens: 50,
  cost_usd: "0.00000000",
  ...overrides,
});

describe("groupByDay", () => {
  it("returns empty array for empty records", () => {
    expect(groupByDay([])).toEqual([]);
  });

  it("sums prompt + completion tokens per day", () => {
    const records = [makeRecord({ prompt_tokens: 100, completion_tokens: 50 })];
    const result = groupByDay(records);
    expect(result[0].tokens).toBe(150);
  });

  it("aggregates multiple records on the same day", () => {
    const records = [
      makeRecord({ date: "2026-03-20", prompt_tokens: 100, completion_tokens: 50 }),
      makeRecord({ date: "2026-03-20", prompt_tokens: 200, completion_tokens: 100 }),
    ];
    const result = groupByDay(records);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toBe(450);
  });

  it("keeps separate entries for different days", () => {
    const records = [
      makeRecord({ date: "2026-03-20", prompt_tokens: 100, completion_tokens: 50 }),
      makeRecord({ date: "2026-03-21", prompt_tokens: 200, completion_tokens: 100 }),
    ];
    const result = groupByDay(records);
    expect(result).toHaveLength(2);
  });

  it("sorts results by date ascending", () => {
    const records = [
      makeRecord({ date: "2026-03-22" }),
      makeRecord({ date: "2026-03-20" }),
      makeRecord({ date: "2026-03-21" }),
    ];
    const result = groupByDay(records);
    expect(result[0].date).toBe("2026-03-20");
    expect(result[1].date).toBe("2026-03-21");
    expect(result[2].date).toBe("2026-03-22");
  });
});

describe("groupByModel", () => {
  it("returns empty array for empty records", () => {
    expect(groupByModel([])).toEqual([]);
  });

  it("sums tokens and cost per model", () => {
    const records = [
      makeRecord({
        model: "model-a",
        prompt_tokens: 100,
        completion_tokens: 50,
        cost_usd: "0.00100000",
      }),
      makeRecord({
        model: "model-a",
        prompt_tokens: 200,
        completion_tokens: 100,
        cost_usd: "0.00200000",
      }),
    ];
    const result = groupByModel(records);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toBe(450);
    expect(result[0].cost).toBeCloseTo(0.003, 6);
  });

  it("keeps separate entries for different models", () => {
    const records = [makeRecord({ model: "model-a" }), makeRecord({ model: "model-b" })];
    const result = groupByModel(records);
    expect(result).toHaveLength(2);
  });
});
