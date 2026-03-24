# Story 4.2: Web Dashboard View — Usage Chart and Model Table

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want the Dashboard view implemented with a 30-day bar chart and per-model cost summary table,
So that I can see my spending patterns and identify cost spikes at a glance within 3 seconds of page load.

## Acceptance Criteria

**AC1 — Single fetch on mount:**
Given the user navigates to the Dashboard view
When the view mounts
Then a single `useEffect` fires a `GET /api/usage` request with the Supabase session JWT in the `Authorization` header — no polling, no refetch on focus (satisfies FR22)

**AC2 — Bar chart renders with Recharts:**
Given the API response arrives
When the data renders
Then the `<UsageChart>` component displays a Recharts `<BarChart>` inside `<ResponsiveContainer height={192}>` with one bar per day, bar fill `#2563eb` (Tailwind blue-600), no Y-axis label, and a tooltip showing exact token count on hover (satisfies FR20, UX-DR3)

**AC3 — Chart accessibility:**
Given the chart renders
When inspected for accessibility
Then the chart wrapper has `role="img" aria-label="30-day token usage bar chart"` (satisfies UX-DR3)

**AC4 — Model table renders correctly:**
Given the API response arrives
When the data renders
Then the `<ModelTable>` displays a `<table>` with `<thead>` columns (Model, Tokens, Cost), `<tbody>` rows for each model with tokens formatted via `.toLocaleString()` and cost as `$${cost.toFixed(4)}`, and a `<tfoot>` total row with `bg-gray-50 font-medium` — all `<th>` elements have `scope` attributes (satisfies FR21, UX-DR4, UX-DR11)

**AC5 — Empty state:**
Given the user has no usage data
When the Dashboard view renders
Then the chart shows the message "No usage yet. Run your first task." and the model table shows no rows

**AC6 — Visual layout matches spec:**
Given the page heading and section structure
When examined
Then the view uses `text-xl font-semibold text-gray-900` for the "Usage — Last 30 Days" heading, `space-y-6` between sections, and `bg-white rounded-lg border border-gray-200 p-6` for card containers (satisfies UX-DR9)

**AC7 — Tests pass:**
Given tests are run
When `npm run test` is executed from `web/`
Then tests pass for: data loads and chart renders, empty state message, model table rows with correct formatting, total row correctness, loading state, error state

## Tasks / Subtasks

- [ ] Task 1: Add TypeScript types in `web/src/types/api.ts` (AC: 1, 2, 4)
  - [ ] `UsageRecord` interface (snake_case, `cost_usd: string`)
  - [ ] `UsageResponse` interface

- [ ] Task 2: Write tests FIRST in `web/src/tests/Dashboard.test.tsx` — confirm they fail (TDD)
  - [ ] Tests for AC2–AC7 all fail before implementation

- [ ] Task 3: Create `web/src/hooks/useUsage.ts` (AC: 1)
  - [ ] `useEffect` on mount — no deps array re-trigger
  - [ ] Fetch `GET /api/usage` with JWT from `supabase.auth.getSession()`
  - [ ] Return `{ data, isLoading, error }`

- [ ] Task 4: Create `web/src/components/UsageChart.tsx` (AC: 2, 3, 5)
  - [ ] Group records by day (sum prompt + completion tokens)
  - [ ] Recharts `<BarChart>` in `<ResponsiveContainer height={192}>`
  - [ ] Empty state message when no data

- [ ] Task 5: Create `web/src/components/ModelTable.tsx` (AC: 4, 5)
  - [ ] Group records by model
  - [ ] `toLocaleString()` for tokens, `$${cost.toFixed(4)}` for cost
  - [ ] `<tfoot>` total row

- [ ] Task 6: Assemble `web/src/Dashboard.tsx` (AC: 1, 6)
  - [ ] Wire `useUsage` hook
  - [ ] Loading and error states
  - [ ] Layout with heading + two card containers

- [ ] Task 7: Verify `App.tsx` renders `<Dashboard />` for authenticated users (no change expected — just confirm)

- [ ] Task 8: Run tests green (AC: 7)
  - [ ] `npm run test` — all tests pass

## Dev Notes

### Prerequisites: Stories 1.3, 2.3, 2.4, 4.1 Must Be Complete

- `web/src/supabaseClient.ts` (or `lib/supabase.ts`) must exist (Story 2.3) — exports `supabase` Supabase client
- `web/src/App.tsx` must conditionally render `<Dashboard />` for authenticated users (Story 2.3 / 2.4)
- `web/.env` must have `VITE_API_BASE_URL` set to the deployed API URL (Story 1.5/1.6)
- `GET /api/usage` endpoint must be live (Story 4.1)
- Recharts must already be installed (Story 1.3: `npm install recharts`)

### TypeScript Types — `web/src/types/api.ts`

Add `UsageRecord` and `UsageResponse` alongside any existing API types:

```typescript
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
```

**Why `cost_usd: string` not `number`?** The API sends `"0.00120000"` as a string (8 decimal places). Typing it as `number` would require `parseFloat()` at the boundary. Keeping it as `string` in the type and parsing at the display layer (with `.toFixed(4)`) is explicit about when precision matters.

**Why snake_case not camelCase?** Architecture rule: FastAPI sends snake_case; the frontend must accept it. No aliasing. No transformation at the fetch boundary.

### `useUsage` Hook — `web/src/hooks/useUsage.ts`

```typescript
// web/src/hooks/useUsage.ts
import { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';   // adjust path if Story 2.3 placed it elsewhere
import type { UsageResponse } from '../types/api';

export interface UseUsageResult {
  data: UsageResponse | null;
  isLoading: boolean;
  error: string | null;
}

export function useUsage(): UseUsageResult {
  const [data, setData] = useState<UsageResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchUsage() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          setError('Not authenticated');
          setIsLoading(false);
          return;
        }
        const response = await fetch(
          `${import.meta.env.VITE_API_BASE_URL}/api/usage`,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const json: UsageResponse = await response.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }
    fetchUsage();
  }, []); // empty deps = fire once on mount, never again

  return { data, isLoading, error };
}
```

**Why no polling?** Architecture: "No polling, no WebSocket — manual browser refresh to see new data (by design, per PRD)." The empty deps `[]` enforces this — no accidental re-triggers.

**Why `supabase.auth.getSession()` not `useSession()`?** The hook is called inside `<Dashboard />` which only renders when the user is already authenticated (App.tsx conditional rendering). `getSession()` is a direct async call; no subscription needed here.

**`VITE_API_BASE_URL` usage:** `import.meta.env.VITE_API_BASE_URL` is Vite's env var syntax. Value comes from `web/.env` (local) or Vercel environment variables (production). Example: `VITE_API_BASE_URL=https://opentaion-api.up.railway.app`.

### Data Grouping Helpers (put in `Dashboard.tsx` or a `utils/usage.ts` file)

The API returns individual `usage_logs` records. The frontend groups them for the chart (by day) and the table (by model):

```typescript
// Group by day for bar chart — sum prompt + completion tokens per calendar date
export function groupByDay(records: UsageRecord[]): { date: string; tokens: number }[] {
  const map = new Map<string, number>();
  for (const r of records) {
    const tokens = r.prompt_tokens + r.completion_tokens;
    map.set(r.date, (map.get(r.date) ?? 0) + tokens);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))  // ascending date order for chart
    .map(([date, tokens]) => ({ date, tokens }));
}

// Group by model for table — sum tokens and cost per model string
export function groupByModel(records: UsageRecord[]): { model: string; tokens: number; cost: number }[] {
  const map = new Map<string, { tokens: number; cost: number }>();
  for (const r of records) {
    const tokens = r.prompt_tokens + r.completion_tokens;
    const cost = parseFloat(r.cost_usd);  // parse ONLY here, display only — never for arithmetic
    const existing = map.get(r.model) ?? { tokens: 0, cost: 0 };
    map.set(r.model, { tokens: existing.tokens + tokens, cost: existing.cost + cost });
  }
  return Array.from(map.entries()).map(([model, { tokens, cost }]) => ({ model, tokens, cost }));
}
```

**Why `parseFloat(r.cost_usd)` here?** The cost is a string from the API (`"0.00120000"`). For display purposes only (`.toFixed(4)`), parsing to float is fine. The AC says display as `$${cost.toFixed(4)}` — this is a UI display, not monetary arithmetic. Summing in float across ~30 records with 8dp precision is safe for display.

### `UsageChart` Component — `web/src/components/UsageChart.tsx`

```tsx
// web/src/components/UsageChart.tsx
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { UsageRecord } from '../types/api';
import { groupByDay } from '../utils/usage';  // or inline if utils not created separately

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
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(date: string) =>
              new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })
            }
          />
          <Tooltip
            formatter={(value: number) => [value.toLocaleString(), 'Tokens']}
            labelFormatter={(label: string) =>
              new Date(label + 'T00:00:00').toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })
            }
          />
          <Bar dataKey="tokens" fill="#2563eb" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Why `date + 'T00:00:00'`?** The API returns date strings like `"2026-03-24"`. `new Date("2026-03-24")` in JavaScript parses as UTC midnight, which can display as March 23 in negative-UTC timezones. Appending `T00:00:00` (no timezone suffix) forces local-time parsing, so the label always shows the correct calendar date.

**Why `fill="#2563eb"` not `fill="bg-blue-600"`?** Recharts `fill` prop takes a CSS color value, not a Tailwind class. Tailwind's `blue-600` hex is `#2563eb`. Always use the hex value in Recharts props.

**Why no `<YAxis>` component?** The AC specifies "no Y-axis label." Omitting `<YAxis>` entirely removes both the axis line and labels, keeping the chart clean per the UX spec.

### `ModelTable` Component — `web/src/components/ModelTable.tsx`

```tsx
// web/src/components/ModelTable.tsx
import type { UsageRecord } from '../types/api';
import { groupByModel } from '../utils/usage';

interface ModelTableProps {
  records: UsageRecord[];
  totalCostUsd: string;
}

export function ModelTable({ records, totalCostUsd }: ModelTableProps) {
  const rows = groupByModel(records);
  const totalTokens = rows.reduce((sum, r) => sum + r.tokens, 0);
  const totalCost = parseFloat(totalCostUsd);

  return (
    <table className="w-full text-sm text-left">
      <thead>
        <tr className="border-b border-gray-200">
          <th scope="col" className="pb-3 font-medium text-gray-500">Model</th>
          <th scope="col" className="pb-3 font-medium text-gray-500 text-right">Tokens</th>
          <th scope="col" className="pb-3 font-medium text-gray-500 text-right">Cost</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.model} className="border-b border-gray-100">
            <td className="py-2 text-gray-900 font-mono text-xs">{row.model}</td>
            <td className="py-2 text-gray-700 text-right">{row.tokens.toLocaleString()}</td>
            <td className="py-2 text-gray-700 text-right">${row.cost.toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="bg-gray-50 font-medium">
          <td className="py-2 pl-0 text-gray-900">Total</td>
          <td className="py-2 text-gray-900 text-right">{totalTokens.toLocaleString()}</td>
          <td className="py-2 text-gray-900 text-right">${totalCost.toFixed(4)}</td>
        </tr>
      </tfoot>
    </table>
  );
}
```

**Why `<th scope="col">`?** Accessibility requirement (UX-DR11). `scope="col"` tells screen readers the `<th>` describes a column. This is the standard for data tables with header rows.

**Why `parseFloat(totalCostUsd)` in the footer?** `totalCostUsd` comes from the API as `"0.00120000"`. The tfoot total uses the pre-summed API value (not recalculated from `rows`) to avoid floating-point accumulation diverging from the API's Decimal-precise sum.

**Empty table when no records:** When `records` is empty, `rows` is `[]`, so `<tbody>` renders no rows. The `<tfoot>` still renders with `$0.0000` and `0` tokens — this is intentional (shows the totals row even for empty state, making the table structure clear).

### `Dashboard.tsx` — Full Assembly

```tsx
// web/src/Dashboard.tsx
import { useUsage } from './hooks/useUsage';
import { UsageChart } from './components/UsageChart';
import { ModelTable } from './components/ModelTable';

export default function Dashboard() {
  const { data, isLoading, error } = useUsage();

  if (isLoading) {
    return (
      <div className="p-8 text-gray-500 text-sm">Loading usage data…</div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-red-600 text-sm">
        Failed to load usage: {error}
      </div>
    );
  }

  const records = data?.records ?? [];

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Usage — Last 30 Days</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <UsageChart records={records} />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <ModelTable
          records={records}
          totalCostUsd={data?.total_cost_usd ?? '0.00000000'}
        />
      </div>
    </div>
  );
}
```

### Testing Setup — Vitest + React Testing Library

If Story 1.3 did not set up web tests, install testing deps first:

```bash
cd web
npm install -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Update `vite.config.ts` to add test configuration:

```typescript
// web/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
  },
})
```

Create `web/src/tests/setup.ts`:

```typescript
// web/src/tests/setup.ts
import '@testing-library/jest-dom';

// Recharts uses ResizeObserver — mock it for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
```

Add to `package.json` scripts:
```json
"test": "vitest run",
"test:watch": "vitest"
```

### Tests — `web/src/tests/Dashboard.test.tsx`

```tsx
// web/src/tests/Dashboard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Dashboard from '../Dashboard';
import type { UseUsageResult } from '../hooks/useUsage';

// Mock the useUsage hook — isolates Dashboard component tests from fetch/supabase
vi.mock('../hooks/useUsage');
import { useUsage } from '../hooks/useUsage';
const mockUseUsage = vi.mocked(useUsage);

// Mock Recharts — ResponsiveContainer needs real dimensions to render
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="recharts-container">{children}</div>
    ),
  };
});

const LOADED_STATE: UseUsageResult = {
  isLoading: false,
  error: null,
  data: {
    period_days: 30,
    total_cost_usd: '0.00120000',
    records: [
      {
        date: '2026-03-20',
        model: 'deepseek/deepseek-r1:free',
        prompt_tokens: 1000,
        completion_tokens: 500,
        cost_usd: '0.00000000',
      },
      {
        date: '2026-03-21',
        model: 'meta-llama/llama-3.3-70b-instruct:free',
        prompt_tokens: 800,
        completion_tokens: 400,
        cost_usd: '0.00120000',
      },
    ],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Loading state ─────────────────────────────────────────────────────────────

describe('loading state', () => {
  it('shows loading message while fetching', () => {
    mockUseUsage.mockReturnValue({ isLoading: true, error: null, data: null });
    render(<Dashboard />);
    expect(screen.getByText(/loading usage data/i)).toBeInTheDocument();
  });
});

// ── Error state ───────────────────────────────────────────────────────────────

describe('error state', () => {
  it('shows error message on failure', () => {
    mockUseUsage.mockReturnValue({ isLoading: false, error: 'HTTP 503', data: null });
    render(<Dashboard />);
    expect(screen.getByText(/failed to load usage/i)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument();
  });
});

// ── Page structure ────────────────────────────────────────────────────────────

describe('page structure', () => {
  it('renders heading "Usage — Last 30 Days"', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.getByRole('heading', { name: /usage — last 30 days/i })).toBeInTheDocument();
  });
});

// ── Chart (non-empty data) ────────────────────────────────────────────────────

describe('UsageChart with data', () => {
  it('renders chart wrapper with correct aria attributes', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    const chartWrapper = screen.getByRole('img', { name: /30-day token usage bar chart/i });
    expect(chartWrapper).toBeInTheDocument();
  });

  it('does not show empty-state message when records exist', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.queryByText(/no usage yet/i)).not.toBeInTheDocument();
  });
});

// ── Chart (empty data) ────────────────────────────────────────────────────────

describe('UsageChart empty state', () => {
  it('shows empty state message when no records', () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: { records: [], total_cost_usd: '0.00000000', period_days: 30 },
    });
    render(<Dashboard />);
    expect(screen.getByText(/no usage yet\. run your first task\./i)).toBeInTheDocument();
  });
});

// ── Model table ───────────────────────────────────────────────────────────────

describe('ModelTable with data', () => {
  it('renders table with thead columns', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.getByRole('columnheader', { name: /model/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /tokens/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /cost/i })).toBeInTheDocument();
  });

  it('renders a row for each unique model', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.getByText('deepseek/deepseek-r1:free')).toBeInTheDocument();
    expect(screen.getByText('meta-llama/llama-3.3-70b-instruct:free')).toBeInTheDocument();
  });

  it('formats tokens with toLocaleString', () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        period_days: 30,
        total_cost_usd: '0.00000000',
        records: [
          {
            date: '2026-03-20',
            model: 'deepseek/deepseek-r1:free',
            prompt_tokens: 10000,
            completion_tokens: 5000,
            cost_usd: '0.00000000',
          },
        ],
      },
    });
    render(<Dashboard />);
    // 15,000 tokens formatted with toLocaleString — "15,000" in en-US
    expect(screen.getByText('15,000')).toBeInTheDocument();
  });

  it('formats cost as $X.XXXX', () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        period_days: 30,
        total_cost_usd: '0.00120000',
        records: [
          {
            date: '2026-03-20',
            model: 'meta-llama/llama-3.3-70b-instruct:free',
            prompt_tokens: 1000,
            completion_tokens: 200,
            cost_usd: '0.00120000',
          },
        ],
      },
    });
    render(<Dashboard />);
    // Cost displayed as $0.0012
    expect(screen.getByText('$0.0012')).toBeInTheDocument();
  });

  it('renders tfoot total row', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    // "Total" label in the footer
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  it('th elements have scope attributes', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    const ths = screen.getAllByRole('columnheader');
    ths.forEach((th) => {
      expect(th).toHaveAttribute('scope', 'col');
    });
  });
});

// ── Model table empty state ───────────────────────────────────────────────────

describe('ModelTable empty state', () => {
  it('renders no tbody rows when records is empty', () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: { records: [], total_cost_usd: '0.00000000', period_days: 30 },
    });
    render(<Dashboard />);
    // Table should still render (with tfoot), but no model rows
    expect(screen.queryByText('deepseek/deepseek-r1:free')).not.toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
  });
});
```

### `groupByDay` / `groupByModel` Unit Tests — `web/src/tests/usage.test.ts`

```typescript
// web/src/tests/usage.test.ts
import { describe, it, expect } from 'vitest';
import { groupByDay, groupByModel } from '../utils/usage';
import type { UsageRecord } from '../types/api';

const makeRecord = (overrides: Partial<UsageRecord> = {}): UsageRecord => ({
  date: '2026-03-20',
  model: 'deepseek/deepseek-r1:free',
  prompt_tokens: 100,
  completion_tokens: 50,
  cost_usd: '0.00000000',
  ...overrides,
});

describe('groupByDay', () => {
  it('returns empty array for empty records', () => {
    expect(groupByDay([])).toEqual([]);
  });

  it('sums prompt + completion tokens per day', () => {
    const records = [makeRecord({ prompt_tokens: 100, completion_tokens: 50 })];
    const result = groupByDay(records);
    expect(result[0].tokens).toBe(150);
  });

  it('aggregates multiple records on the same day', () => {
    const records = [
      makeRecord({ date: '2026-03-20', prompt_tokens: 100, completion_tokens: 50 }),
      makeRecord({ date: '2026-03-20', prompt_tokens: 200, completion_tokens: 100 }),
    ];
    const result = groupByDay(records);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toBe(450);
  });

  it('keeps separate entries for different days', () => {
    const records = [
      makeRecord({ date: '2026-03-20', prompt_tokens: 100, completion_tokens: 50 }),
      makeRecord({ date: '2026-03-21', prompt_tokens: 200, completion_tokens: 100 }),
    ];
    const result = groupByDay(records);
    expect(result).toHaveLength(2);
  });

  it('sorts results by date ascending', () => {
    const records = [
      makeRecord({ date: '2026-03-22' }),
      makeRecord({ date: '2026-03-20' }),
      makeRecord({ date: '2026-03-21' }),
    ];
    const result = groupByDay(records);
    expect(result[0].date).toBe('2026-03-20');
    expect(result[1].date).toBe('2026-03-21');
    expect(result[2].date).toBe('2026-03-22');
  });
});

describe('groupByModel', () => {
  it('returns empty array for empty records', () => {
    expect(groupByModel([])).toEqual([]);
  });

  it('sums tokens and cost per model', () => {
    const records = [
      makeRecord({ model: 'model-a', prompt_tokens: 100, completion_tokens: 50, cost_usd: '0.00100000' }),
      makeRecord({ model: 'model-a', prompt_tokens: 200, completion_tokens: 100, cost_usd: '0.00200000' }),
    ];
    const result = groupByModel(records);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toBe(450);
    expect(result[0].cost).toBeCloseTo(0.003, 6);
  });

  it('keeps separate entries for different models', () => {
    const records = [
      makeRecord({ model: 'model-a' }),
      makeRecord({ model: 'model-b' }),
    ];
    const result = groupByModel(records);
    expect(result).toHaveLength(2);
  });
});
```

### Architecture Cross-References

From `architecture.md`:
- No router — two-view conditional render on Supabase auth state [Source: architecture.md#Web]
- No shadcn/ui — raw Tailwind utility classes only [Source: architecture.md#Web]
- Single `useEffect` on `<Dashboard />` mount, no polling [Source: architecture.md#Data Fetching]
- snake_case JSON from API; TypeScript uses camelCase for vars (e.g. `isLoading`), PascalCase for components [Source: architecture.md#Naming]
- `VITE_API_BASE_URL` env var for API base URL [Source: architecture.md#Web file structure]
- `cost_usd` is a decimal string from API — `parseFloat()` only at display layer [Source: architecture.md#Cost Format]
- `web/src/types/api.ts` — TypeScript types for API responses [Source: architecture.md#File Structure]
- `web/src/hooks/useUsage.ts` — `GET /api/usage` data fetching hook [Source: architecture.md#File Structure]

From `ux-design-specification.md`:
- Dashboard wireframe: sidebar (220px) + main content [Source: ux-design.md#Flow 5]
- Bar chart: single color, no legend, no date picker [Source: ux-design.md#Chart]
- `h-48` (192px) fixed chart height [Source: ux-design.md#Chart Container]
- `role="img" aria-label` on chart wrapper [Source: ux-design.md#Accessibility]
- `<th scope="col">` on all column headers [Source: ux-design.md#Accessibility]
- `text-gray-900 on bg-white`: 16:1 — AAA contrast [Source: ux-design.md#Accessibility]

From `epics.md`:
- FR20: "30-day bar chart of token usage, grouped by day and broken down by model" [Source: epics.md#FR20]
- FR21: "Per-model cost summary table for last 30 days" [Source: epics.md#FR21]
- FR22: "Single fetch on mount, no polling" [Source: epics.md#FR22]
- NFR3: "Chart and table rendered within 3 seconds" [Source: epics.md#NFR3]

### What This Story Does NOT Include

- The sidebar navigation component — that's Story 2.4 (`<Sidebar>` with Dashboard / API Keys nav)
- The API Keys view — Story 2.5
- Real-time updates or WebSocket — explicitly out of V1 scope
- Pagination or date-range filtering — out of V1 scope
- Stacked bars (multi-model per day) — V1 uses single-color total tokens per day only

### Final Modified/Created Files

```
web/
├── src/
│   ├── Dashboard.tsx                ← MODIFIED — wire useUsage hook, assemble chart + table
│   ├── types/
│   │   └── api.ts                   ← NEW — UsageRecord, UsageResponse TS interfaces
│   ├── hooks/
│   │   └── useUsage.ts              ← NEW — fetch GET /api/usage on mount
│   ├── components/
│   │   ├── UsageChart.tsx           ← NEW — Recharts BarChart with groupByDay
│   │   └── ModelTable.tsx           ← NEW — grouped model table with tfoot totals
│   ├── utils/
│   │   └── usage.ts                 ← NEW — groupByDay, groupByModel helpers
│   └── tests/
│       ├── setup.ts                 ← NEW — testing-library + ResizeObserver mock (if not exists)
│       ├── Dashboard.test.tsx       ← NEW — component tests (useUsage mocked)
│       └── usage.test.ts            ← NEW — groupByDay, groupByModel unit tests
└── vite.config.ts                   ← MODIFIED — add test configuration (if not exists)
```

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_none_

### Completion Notes List

_to be filled by dev agent_

### File List

_to be filled by dev agent_
