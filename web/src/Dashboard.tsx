import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface UsageDay {
  date: string;
  tokens: number;
}

interface DashboardProps {
  email: string;
  usageData: UsageDay[];
  onLogout: () => void;
}

export default function Dashboard({ email, usageData, onLogout }: DashboardProps) {
  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">OpenTalon</h1>
            <p className="text-gray-400 text-sm mt-1">{email}</p>
          </div>
          <button
            onClick={onLogout}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>

        <div className="bg-gray-900 rounded-2xl p-6">
          <h2 className="text-sm font-medium text-gray-400 mb-4">Token usage (last 7 days)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={usageData}>
              <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "none", borderRadius: "8px" }}
                labelStyle={{ color: "#e5e7eb" }}
              />
              <Bar dataKey="tokens" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
