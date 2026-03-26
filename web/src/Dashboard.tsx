// web/src/Dashboard.tsx
import { useUsage } from "./hooks/useUsage";
import { UsageChart } from "./components/UsageChart";
import { ModelTable } from "./components/ModelTable";

export default function Dashboard() {
  const { data, isLoading, error } = useUsage();

  if (isLoading) {
    return <div className="p-8 text-gray-500 text-sm">Loading usage data…</div>;
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
          totalCostUsd={data?.total_cost_usd ?? "0.00000000"}
        />
      </div>
    </div>
  );
}
