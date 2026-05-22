"use client";

import React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  iconBg?: string;
  loading?: boolean;
  prefix?: string;
  suffix?: string;
  description?: string;
  variant?: "default" | "success" | "warning" | "danger";
}

function KPICardSkeleton() {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1">
            <div className="h-4 w-32 bg-muted rounded animate-pulse" />
            <div className="h-8 w-24 bg-muted rounded animate-pulse" />
            <div className="h-3 w-20 bg-muted rounded animate-pulse" />
          </div>
          <div className="h-12 w-12 bg-muted rounded-lg animate-pulse" />
        </div>
      </CardContent>
    </Card>
  );
}

export function KPICard({
  title,
  value,
  change,
  changeLabel,
  icon,
  iconBg = "bg-primary-100",
  loading = false,
  prefix,
  suffix,
  description,
  variant = "default",
}: KPICardProps) {
  if (loading) return <KPICardSkeleton />;

  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;
  const isNeutral = change === 0;

  const variantBg = {
    default: "bg-white dark:bg-card",
    success: "bg-success-50 dark:bg-success-900/10 border-success-200",
    warning: "bg-warning-50 dark:bg-warning-900/10 border-warning-200",
    danger: "bg-danger-50 dark:bg-danger-900/10 border-danger-200",
  };

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-card-hover",
        variantBg[variant]
      )}
    >
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-muted-foreground mb-1 truncate">
              {title}
            </p>
            <div className="flex items-baseline gap-1">
              {prefix && (
                <span className="text-sm font-medium text-muted-foreground">
                  {prefix}
                </span>
              )}
              <p className="text-2xl font-bold text-foreground tracking-tight">
                {typeof value === "number" ? value.toLocaleString("en-IN") : value}
              </p>
              {suffix && (
                <span className="text-sm font-medium text-muted-foreground">
                  {suffix}
                </span>
              )}
            </div>

            {change !== undefined && (
              <div className="flex items-center gap-1 mt-2">
                {isPositive && (
                  <TrendingUp className="h-3.5 w-3.5 text-success-600" />
                )}
                {isNegative && (
                  <TrendingDown className="h-3.5 w-3.5 text-danger-600" />
                )}
                {isNeutral && <Minus className="h-3.5 w-3.5 text-muted-foreground" />}
                <span
                  className={cn(
                    "text-xs font-medium",
                    isPositive && "text-success-600",
                    isNegative && "text-danger-600",
                    isNeutral && "text-muted-foreground"
                  )}
                >
                  {isPositive && "+"}
                  {change?.toFixed(1)}%
                </span>
                {changeLabel && (
                  <span className="text-xs text-muted-foreground">
                    {changeLabel}
                  </span>
                )}
              </div>
            )}

            {description && !change && (
              <p className="text-xs text-muted-foreground mt-2">{description}</p>
            )}
          </div>

          {icon && (
            <div
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-xl flex-shrink-0",
                iconBg
              )}
            >
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
