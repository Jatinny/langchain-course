"use client";

import React from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { ScoreBreakdown as ScoreBreakdownType } from "@/types";
import { cn } from "@/lib/utils";

interface ScoreBreakdownProps {
  breakdown: ScoreBreakdownType;
  height?: number;
  showLegend?: boolean;
}

const dimensionLabels: Record<keyof ScoreBreakdownType, string> = {
  hiring_velocity: "Hiring Velocity",
  vendor_friendliness: "Vendor Friendly",
  payment_reliability: "Payment",
  job_quality: "Job Quality",
  response_rate: "Response Rate",
  placement_success: "Placement Rate",
};

const CustomTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { subject: string; value: number } }>;
}) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white dark:bg-card border border-border rounded-lg shadow p-2.5">
        <p className="text-xs font-semibold text-foreground">{data.subject}</p>
        <p className="text-sm font-bold text-primary-600">{data.value}/100</p>
      </div>
    );
  }
  return null;
};

export function ScoreBreakdown({
  breakdown,
  height = 280,
  showLegend = true,
}: ScoreBreakdownProps) {
  const radarData = (
    Object.keys(breakdown) as Array<keyof ScoreBreakdownType>
  ).map((key) => ({
    subject: dimensionLabels[key],
    value: breakdown[key],
    fullMark: 100,
  }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "#cbd5e1" }}
            tickCount={5}
          />
          <Tooltip content={<CustomTooltip />} />
          <Radar
            name="Score"
            dataKey="value"
            stroke="#2563eb"
            fill="#2563eb"
            fillOpacity={0.15}
            strokeWidth={2}
            dot={{ fill: "#2563eb", strokeWidth: 0, r: 3 }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {showLegend && (
        <div className="grid grid-cols-2 gap-2 mt-2">
          {radarData.map((item) => (
            <div key={item.subject} className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">{item.subject}</span>
              <div className="flex items-center gap-1">
                <div
                  className={cn(
                    "h-1.5 rounded-full",
                    item.value >= 80
                      ? "bg-success-500"
                      : item.value >= 50
                      ? "bg-warning-500"
                      : "bg-danger-500"
                  )}
                  style={{ width: `${(item.value / 100) * 48}px` }}
                />
                <span
                  className={cn(
                    "text-xs font-semibold",
                    item.value >= 80
                      ? "text-success-600"
                      : item.value >= 50
                      ? "text-warning-600"
                      : "text-danger-600"
                  )}
                >
                  {item.value}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
