// web/src/tests/Dashboard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Dashboard from "../Dashboard";
import type { UseUsageResult } from "../hooks/useUsage";

// Mock the useUsage hook — isolates Dashboard component tests from fetch/supabase
vi.mock("../hooks/useUsage");
import { useUsage } from "../hooks/useUsage";
const mockUseUsage = vi.mocked(useUsage);

// Mock Recharts — ResponsiveContainer needs real dimensions to render
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
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
    total_cost_usd: "0.00120000",
    records: [
      {
        date: "2026-03-20",
        model: "deepseek/deepseek-r1:free",
        prompt_tokens: 1000,
        completion_tokens: 500,
        cost_usd: "0.00000000",
      },
      {
        date: "2026-03-21",
        model: "meta-llama/llama-3.3-70b-instruct:free",
        prompt_tokens: 800,
        completion_tokens: 400,
        cost_usd: "0.00120000",
      },
    ],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Loading state ─────────────────────────────────────────────────────────────

describe("loading state", () => {
  it("shows loading message while fetching", () => {
    mockUseUsage.mockReturnValue({ isLoading: true, error: null, data: null });
    render(<Dashboard />);
    expect(screen.getByText(/loading usage data/i)).toBeInTheDocument();
  });
});

// ── Error state ───────────────────────────────────────────────────────────────

describe("error state", () => {
  it("shows error message on failure", () => {
    mockUseUsage.mockReturnValue({ isLoading: false, error: "HTTP 503", data: null });
    render(<Dashboard />);
    expect(screen.getByText(/failed to load usage/i)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument();
  });
});

// ── Page structure ────────────────────────────────────────────────────────────

describe("page structure", () => {
  it('renders heading "Usage — Last 30 Days"', () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(
      screen.getByRole("heading", { name: /usage — last 30 days/i })
    ).toBeInTheDocument();
  });
});

// ── Chart (non-empty data) ────────────────────────────────────────────────────

describe("UsageChart with data", () => {
  it("renders chart wrapper with correct aria attributes", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    const chartWrapper = screen.getByRole("img", {
      name: /30-day token usage bar chart/i,
    });
    expect(chartWrapper).toBeInTheDocument();
  });

  it("does not show empty-state message when records exist", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.queryByText(/no usage yet/i)).not.toBeInTheDocument();
  });
});

// ── Chart (empty data) ────────────────────────────────────────────────────────

describe("UsageChart empty state", () => {
  it("shows empty state message when no records", () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: { records: [], total_cost_usd: "0.00000000", period_days: 30 },
    });
    render(<Dashboard />);
    expect(
      screen.getByText(/no usage yet\. run your first task\./i)
    ).toBeInTheDocument();
  });
});

// ── Model table ───────────────────────────────────────────────────────────────

describe("ModelTable with data", () => {
  it("renders table with thead columns", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(
      screen.getByRole("columnheader", { name: /model/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: /tokens/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: /cost/i })
    ).toBeInTheDocument();
  });

  it("renders a row for each unique model", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.getByText("deepseek/deepseek-r1:free")).toBeInTheDocument();
    expect(
      screen.getByText("meta-llama/llama-3.3-70b-instruct:free")
    ).toBeInTheDocument();
  });

  it("formats tokens with toLocaleString", () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        period_days: 30,
        total_cost_usd: "0.00000000",
        records: [
          {
            date: "2026-03-20",
            model: "deepseek/deepseek-r1:free",
            prompt_tokens: 10000,
            completion_tokens: 5000,
            cost_usd: "0.00000000",
          },
        ],
      },
    });
    render(<Dashboard />);
    // 15,000 tokens formatted with toLocaleString — "15,000" in en-US
    // getAllByText: value appears in both the tbody row and the tfoot total row
    expect(screen.getAllByText("15,000").length).toBeGreaterThanOrEqual(1);
  });

  it("formats cost as $X.XXXX", () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        period_days: 30,
        total_cost_usd: "0.00120000",
        records: [
          {
            date: "2026-03-20",
            model: "meta-llama/llama-3.3-70b-instruct:free",
            prompt_tokens: 1000,
            completion_tokens: 200,
            cost_usd: "0.00120000",
          },
        ],
      },
    });
    render(<Dashboard />);
    // Cost displayed as $0.0012
    // getAllByText: value appears in both the tbody row and the tfoot total row
    expect(screen.getAllByText("$0.0012").length).toBeGreaterThanOrEqual(1);
  });

  it("renders tfoot total row", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("th elements have scope attributes", () => {
    mockUseUsage.mockReturnValue(LOADED_STATE);
    render(<Dashboard />);
    const ths = screen.getAllByRole("columnheader");
    ths.forEach((th) => {
      expect(th).toHaveAttribute("scope", "col");
    });
  });
});

// ── Model table empty state ───────────────────────────────────────────────────

describe("ModelTable empty state", () => {
  it("renders no tbody rows when records is empty", () => {
    mockUseUsage.mockReturnValue({
      isLoading: false,
      error: null,
      data: { records: [], total_cost_usd: "0.00000000", period_days: 30 },
    });
    render(<Dashboard />);
    expect(
      screen.queryByText("deepseek/deepseek-r1:free")
    ).not.toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });
});
