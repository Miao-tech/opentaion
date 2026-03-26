# Acceptance Auditor Review - Story 4.2

## Instructions

You are the **Acceptance Auditor** - verify implementation against the spec. Review the diff against the Story 4.2 spec and check for:

- Violations of acceptance criteria (AC1-AC7)
- Deviations from spec intent
- Missing implementation of specified behavior
- Contradictions between spec constraints and actual code

## Story 4.2 Spec Summary

**Story**: Web Dashboard View — Usage Chart and Model Table

### Acceptance Criteria:

**AC1 — Single fetch on mount:**
- Single `useEffect` fires `GET /api/usage` request with Supabase JWT
- No polling, no refetch on focus

**AC2 — Bar chart renders with Recharts:**
- `<UsageChart>` displays Recharts `<BarChart>` in `<ResponsiveContainer height={192}>`
- One bar per day, bar fill `#2563eb`, no Y-axis label
- Tooltip showing exact token count on hover

**AC3 — Chart accessibility:**
- Chart wrapper has `role="img" aria-label="30-day token usage bar chart"`

**AC4 — Model table renders correctly:**
- `<ModelTable>` displays `<table>` with `<thead>` columns (Model, Tokens, Cost)
- `<tbody>` rows for each model with tokens formatted via `.toLocaleString()`
- Cost as `$${cost.toFixed(4)}`
- `<tfoot>` total row with `bg-gray-50 font-medium`
- All `<th>` elements have `scope` attributes

**AC5 — Empty state:**
- Chart shows "No usage yet. Run your first task." when no data
- Model table shows no rows when empty

**AC6 — Visual layout matches spec:**
- Heading: `text-xl font-semibold text-gray-900` for "Usage — Last 30 Days"
- `space-y-6` between sections
- `bg-white rounded-lg border border-gray-200 p-6` for card containers

**AC7 — Tests pass:**
- `npm run test` passes for: data loads and chart renders, empty state, model table rows, formatting, total row, loading state, error state

### TypeScript Types (from spec):

```typescript
interface UsageRecord {
  date: string;           // "YYYY-MM-DD"
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: string;       // 8dp decimal string
}

interface UsageResponse {
  records: UsageRecord[];
  total_cost_usd: string;
  period_days: number;
}
```

## Files to Review

- web/src/Dashboard.tsx
- web/src/components/UsageChart.tsx
- web/src/components/ModelTable.tsx
- web/src/hooks/useUsage.ts
- web/src/utils/usage.ts
- web/src/types/api.ts
- web/src/tests/Dashboard.test.tsx
- web/src/tests/usage.test.ts

## Output Format

Provide findings as a markdown list. Each finding should include:
- **AC Violated**: Which acceptance criterion is not met
- **Evidence**: Specific code that contradicts the spec
- **Spec Requirement**: What the spec says
- **Actual Implementation**: What the code does

If all ACs are satisfied, state "All acceptance criteria met."
