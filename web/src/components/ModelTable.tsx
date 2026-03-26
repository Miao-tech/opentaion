// web/src/components/ModelTable.tsx
import type { UsageRecord } from "../types/api";
import { groupByModel } from "../utils/usage";

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
          <th scope="col" className="pb-3 font-medium text-gray-500">
            Model
          </th>
          <th scope="col" className="pb-3 font-medium text-gray-500 text-right">
            Tokens
          </th>
          <th scope="col" className="pb-3 font-medium text-gray-500 text-right">
            Cost
          </th>
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
