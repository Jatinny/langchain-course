"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { RevenueData } from "@/types";

interface RevenueChartProps {
  data: RevenueData[];
  currency?: "INR" | "USD";
  height?: number;
}

const CustomTooltip = ({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
  currency: "INR" | "USD";
}) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white dark:bg-card border border-border rounded-lg shadow-lg p-3 min-w-[160px]">
        <p className="text-sm font-semibold text-foreground mb-2">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-xs text-muted-foreground capitalize">
                {entry.name}
              </span>
            </div>
            <span className="text-xs font-medium text-foreground">
              {entry.name === "placements"
                ? entry.value
                : formatCurrency(entry.value, currency, true)}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export function RevenueChart({
  data,
  currency = "INR",
  height = 300,
}: RevenueChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart
        data={data}
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2563eb" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="targetGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
        <XAxis
          dataKey="month"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 12, fill: "#94a3b8" }}
          dy={8}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 12, fill: "#94a3b8" }}
          tickFormatter={(value) => formatCurrency(value, currency, true)}
          dx={-8}
        />
        <Tooltip
          content={<CustomTooltip currency={currency} />}
          cursor={{ stroke: "#e2e8f0", strokeWidth: 1 }}
        />
        <Legend
          wrapperStyle={{ paddingTop: "16px", fontSize: "12px" }}
          formatter={(value) =>
            value === "revenue"
              ? "Actual Revenue"
              : value === "target"
              ? "Target"
              : "Placements"
          }
        />
        <Area
          type="monotone"
          dataKey="target"
          stroke="#10b981"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          fill="url(#targetGradient)"
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="#2563eb"
          strokeWidth={2.5}
          fill="url(#revenueGradient)"
          dot={false}
          activeDot={{ r: 5, fill: "#2563eb", strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
