"use client";

import React from "react";
import {
  FunnelChart,
  Funnel,
  LabelList,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { FunnelData } from "@/types";

interface EmployerFunnelChartProps {
  data: FunnelData[];
  height?: number;
}

const COLORS = [
  "#64748b",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#10b981",
  "#22c55e",
];

const CustomTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: FunnelData }>;
}) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white dark:bg-card border border-border rounded-lg shadow-lg p-3">
        <p className="text-sm font-semibold text-foreground">{data.stage}</p>
        <p className="text-sm text-muted-foreground">
          Count:{" "}
          <span className="font-medium text-foreground">{data.count}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Value:{" "}
          <span className="font-medium text-foreground">
            ₹{data.value.toLocaleString("en-IN")}
          </span>
        </p>
      </div>
    );
  }
  return null;
};

export function EmployerFunnelChart({
  data,
  height = 320,
}: EmployerFunnelChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <FunnelChart>
        <Tooltip content={<CustomTooltip />} />
        <Funnel
          dataKey="count"
          data={data}
          isAnimationActive
          animationDuration={800}
        >
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={COLORS[index % COLORS.length]}
              opacity={0.85}
            />
          ))}
          <LabelList
            position="right"
            content={({ value, x, y, width, height }) => {
              const item = data.find((d) => d.count === value);
              return (
                <text
                  x={Number(x) + Number(width) + 8}
                  y={Number(y) + Number(height) / 2}
                  fill="#64748b"
                  fontSize={12}
                  dominantBaseline="middle"
                >
                  {item?.stage} ({value})
                </text>
              );
            }}
          />
        </Funnel>
      </FunnelChart>
    </ResponsiveContainer>
  );
}
