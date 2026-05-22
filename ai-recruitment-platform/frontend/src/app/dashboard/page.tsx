"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Mail,
  Users,
  DollarSign,
  TrendingUp,
  Sparkles,
  Plus,
  Upload,
  ArrowRight,
  MessageSquare,
  Star,
  Activity,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KPICard } from "@/components/dashboard/KPICard";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import { EmployerFunnelChart } from "@/components/dashboard/EmployerFunnelChart";
import {
  formatCurrency,
  formatRelativeDate,
  formatPercentage,
  cn,
} from "@/lib/utils";
import type { AnalyticsDashboard } from "@/types";

// ─── MOCK DATA ────────────────────────────────────────────────

const mockDashboard: AnalyticsDashboard = {
  period: "MTD",
  kpis: {
    total_employers: 847,
    total_employers_change: 12.4,
    active_campaigns: 18,
    active_campaigns_change: 5.9,
    placements_mtd: 23,
    placements_mtd_change: 21.1,
    revenue_mtd: 1850000,
    revenue_mtd_change: 18.3,
    pipeline_value: 12400000,
    pipeline_value_change: 8.7,
    outreach_sent: 4280,
    open_rate: 34.2,
    reply_rate: 8.9,
    conversion_rate: 2.4,
  },
  revenue_trend: [
    { month: "Dec", revenue: 920000, placements: 11, target: 1000000, currency: "INR" },
    { month: "Jan", revenue: 1100000, placements: 14, target: 1100000, currency: "INR" },
    { month: "Feb", revenue: 980000, placements: 12, target: 1200000, currency: "INR" },
    { month: "Mar", revenue: 1350000, placements: 17, target: 1300000, currency: "INR" },
    { month: "Apr", revenue: 1560000, placements: 19, target: 1400000, currency: "INR" },
    { month: "May", revenue: 1850000, placements: 23, target: 1600000, currency: "INR" },
  ],
  outreach_performance: [
    { channel: "email", sent: 2800, opened: 964, replied: 251, converted: 42 },
    { channel: "linkedin", sent: 980, opened: 627, replied: 138, converted: 28 },
    { channel: "whatsapp", sent: 500, opened: 480, replied: 210, converted: 38 },
  ],
  employer_funnel: [
    { stage: "Prospecting", count: 847, value: 42350000 },
    { stage: "Contacted", count: 512, value: 25600000 },
    { stage: "Interested", count: 248, value: 12400000 },
    { stage: "Registered", count: 124, value: 6200000 },
    { stage: "Active", count: 67, value: 3350000 },
    { stage: "Won", count: 32, value: 1600000 },
  ],
  revenue_by_industry: [
    { industry: "IT Services", revenue: 720000 },
    { industry: "Product", revenue: 450000 },
    { industry: "BFSI", revenue: 310000 },
    { industry: "GCC", revenue: 220000 },
    { industry: "Startup", revenue: 150000 },
  ],
  top_templates: [
    {
      id: "t1",
      name: "Cold Outreach - IT Services",
      subject: "Partnership Opportunity - {{company}}",
      body: "",
      channel: "email",
      industry: "IT Services",
      use_case: "cold_outreach",
      open_rate: 42.3,
      reply_rate: 12.1,
      usage_count: 1240,
      tags: ["cold", "IT"],
      created_at: new Date().toISOString(),
    },
    {
      id: "t2",
      name: "Vendor Registration - BFSI",
      subject: "Vendor Empanelment Inquiry",
      body: "",
      channel: "email",
      industry: "BFSI",
      use_case: "vendor_reg",
      open_rate: 38.7,
      reply_rate: 9.8,
      usage_count: 890,
      tags: ["vendor", "BFSI"],
      created_at: new Date().toISOString(),
    },
    {
      id: "t3",
      name: "Follow-up #2 - GCC",
      subject: "Re: Talent Partnership - {{company}}",
      body: "",
      channel: "email",
      industry: "GCC",
      use_case: "follow_up",
      open_rate: 51.2,
      reply_rate: 15.6,
      usage_count: 640,
      tags: ["follow-up", "GCC"],
      created_at: new Date().toISOString(),
    },
  ],
  recent_activity: [
    {
      id: "a1",
      type: "reply_received",
      title: "Reply from Infosys HR",
      description: "Interested in vendor empanelment. Requested profile deck.",
      timestamp: new Date(Date.now() - 300000).toISOString(),
      user: "System",
    },
    {
      id: "a2",
      type: "placement_made",
      title: "Placement Confirmed",
      description: "Ankit Gupta placed at Wipro as Senior Java Developer",
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      user: "Rahul Sharma",
    },
    {
      id: "a3",
      type: "employer_added",
      title: "New Employer Discovered",
      description: "AI found 12 new GCC employers in Hyderabad matching criteria",
      timestamp: new Date(Date.now() - 10800000).toISOString(),
      user: "AI Agent",
    },
    {
      id: "a4",
      type: "campaign_launched",
      title: "Campaign Launched",
      description: "FinTech Q2 Campaign started — targeting 180 companies",
      timestamp: new Date(Date.now() - 18000000).toISOString(),
      user: "Priya S",
    },
    {
      id: "a5",
      type: "commission_received",
      title: "Commission Received",
      description: "₹85,000 commission from TechMahindra contract placement",
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      user: "Finance",
    },
  ],
  ai_recommendations: [
    {
      id: "r1",
      type: "outreach",
      priority: "high",
      title: "Launch BFSI Follow-up Campaign",
      description:
        "42 BFSI contacts haven't been reached in 30+ days. Historical data shows 18% response rate at this touchpoint.",
      action_label: "Create Campaign",
      action_url: "/outreach/new",
      impact_score: 87,
      created_at: new Date().toISOString(),
    },
    {
      id: "r2",
      type: "employer",
      priority: "high",
      title: "Score 15 New GCC Employers",
      description:
        "AI identified 15 new Global Capability Centers with active hiring. Your success rate with GCCs is 34%.",
      action_label: "View Employers",
      action_url: "/employers?industry=GCC",
      impact_score: 82,
      created_at: new Date().toISOString(),
    },
    {
      id: "r3",
      type: "candidate",
      priority: "medium",
      title: "Match 8 Java Candidates to Active Jobs",
      description:
        "You have 8 Java developers available. 3 of your active employer relationships have open Java roles.",
      action_label: "Run Matching",
      action_url: "/matching",
      impact_score: 74,
      created_at: new Date().toISOString(),
    },
  ],
};

// ─── ACTIVITY ICON HELPER ──────────────────────────────────

const activityIcons: Record<string, { icon: React.ElementType; bg: string; color: string }> = {
  reply_received: { icon: MessageSquare, bg: "bg-blue-100", color: "text-blue-600" },
  placement_made: { icon: Star, bg: "bg-success-100", color: "text-success-600" },
  employer_added: { icon: Building2, bg: "bg-purple-100", color: "text-purple-600" },
  campaign_launched: { icon: Mail, bg: "bg-orange-100", color: "text-orange-600" },
  commission_received: { icon: DollarSign, bg: "bg-emerald-100", color: "text-emerald-600" },
};

// ─── PAGE COMPONENT ────────────────────────────────────────

export default function DashboardPage() {
  const { data: dashboard, isLoading } = useQuery<AnalyticsDashboard>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      // In production: return analyticsApi.getDashboard()
      await new Promise((r) => setTimeout(r, 500));
      return mockDashboard;
    },
  });

  const kpis = dashboard?.kpis;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Good morning, Rahul. Here's what's happening today.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Upload className="h-4 w-4 mr-1.5" />
            Upload Candidate
          </Button>
          <Button size="sm">
            <Plus className="h-4 w-4 mr-1.5" />
            New Campaign
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          loading={isLoading}
          title="Total Employers"
          value={kpis?.total_employers ?? 0}
          change={kpis?.total_employers_change}
          changeLabel="vs last month"
          icon={<Building2 className="h-5 w-5 text-primary-600" />}
          iconBg="bg-primary-100"
        />
        <KPICard
          loading={isLoading}
          title="Active Campaigns"
          value={kpis?.active_campaigns ?? 0}
          change={kpis?.active_campaigns_change}
          changeLabel="vs last month"
          icon={<Mail className="h-5 w-5 text-orange-600" />}
          iconBg="bg-orange-100"
        />
        <KPICard
          loading={isLoading}
          title="Placements (MTD)"
          value={kpis?.placements_mtd ?? 0}
          change={kpis?.placements_mtd_change}
          changeLabel="vs last MTD"
          icon={<Users className="h-5 w-5 text-success-600" />}
          iconBg="bg-success-100"
          variant="success"
        />
        <KPICard
          loading={isLoading}
          title="Revenue (MTD)"
          value={
            kpis?.revenue_mtd
              ? formatCurrency(kpis.revenue_mtd, "INR", true)
              : "₹0"
          }
          change={kpis?.revenue_mtd_change}
          changeLabel="vs last MTD"
          icon={<DollarSign className="h-5 w-5 text-emerald-600" />}
          iconBg="bg-emerald-100"
          variant="success"
        />
        <KPICard
          loading={isLoading}
          title="Pipeline Value"
          value={
            kpis?.pipeline_value
              ? formatCurrency(kpis.pipeline_value, "INR", true)
              : "₹0"
          }
          change={kpis?.pipeline_value_change}
          changeLabel="vs last month"
          icon={<TrendingUp className="h-5 w-5 text-indigo-600" />}
          iconBg="bg-indigo-100"
        />
      </div>

      {/* Quick Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-muted-foreground">Quick actions:</span>
        <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5">
          <Building2 className="h-3.5 w-3.5" />
          Discover Employers
        </Button>
        <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5">
          <Mail className="h-3.5 w-3.5" />
          Start Campaign
        </Button>
        <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5">
          <Upload className="h-3.5 w-3.5" />
          Upload Candidate
        </Button>
        <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5">
          <Sparkles className="h-3.5 w-3.5" />
          AI Match
        </Button>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Revenue Trend</CardTitle>
                <CardDescription>Monthly revenue vs target (INR)</CardDescription>
              </div>
              <Badge variant="success" dot>
                {formatPercentage(kpis?.revenue_mtd_change ?? 0, 1, true)} this month
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-64 bg-muted rounded animate-pulse" />
            ) : (
              <RevenueChart
                data={dashboard?.revenue_trend ?? []}
                currency="INR"
                height={260}
              />
            )}
          </CardContent>
        </Card>

        {/* Outreach Performance */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Outreach Performance</CardTitle>
            <CardDescription>By channel this month</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {dashboard?.outreach_performance.map((channel) => {
                const openRate =
                  channel.sent > 0
                    ? (channel.opened / channel.sent) * 100
                    : 0;
                const replyRate =
                  channel.sent > 0
                    ? (channel.replied / channel.sent) * 100
                    : 0;
                return (
                  <div key={channel.channel} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium capitalize">
                        {channel.channel}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {channel.sent.toLocaleString()} sent
                      </span>
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs w-12 text-muted-foreground">Open</span>
                        <div className="flex-1 h-1.5 bg-muted rounded-full">
                          <div
                            className="h-full bg-primary-500 rounded-full"
                            style={{ width: `${openRate}%` }}
                          />
                        </div>
                        <span className="text-xs w-10 text-right font-medium">
                          {openRate.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs w-12 text-muted-foreground">Reply</span>
                        <div className="flex-1 h-1.5 bg-muted rounded-full">
                          <div
                            className="h-full bg-success-500 rounded-full"
                            style={{ width: `${replyRate}%` }}
                          />
                        </div>
                        <span className="text-xs w-10 text-right font-medium">
                          {replyRate.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Employer Funnel */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Employer Pipeline</CardTitle>
            <CardDescription>Funnel across CRM stages</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-64 bg-muted rounded animate-pulse" />
            ) : (
              <EmployerFunnelChart
                data={dashboard?.employer_funnel ?? []}
                height={260}
              />
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Recent Activity</CardTitle>
              <Button variant="ghost" size="sm" className="text-xs h-7">
                View all
                <ArrowRight className="h-3 w-3 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {dashboard?.recent_activity.slice(0, 5).map((activity) => {
                const config = activityIcons[activity.type] || {
                  icon: Activity,
                  bg: "bg-gray-100",
                  color: "text-gray-600",
                };
                const Icon = config.icon;
                return (
                  <div key={activity.id} className="flex items-start gap-2.5">
                    <div
                      className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-full flex-shrink-0 mt-0.5",
                        config.bg
                      )}
                    >
                      <Icon className={cn("h-3.5 w-3.5", config.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground line-clamp-1">
                        {activity.title}
                      </p>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                        {activity.description}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0 mt-0.5">
                      {formatRelativeDate(activity.timestamp)}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* AI Recommendations */}
        <Card className="border-primary-200 bg-gradient-to-br from-primary-50 to-indigo-50 dark:from-primary-900/10 dark:to-indigo-900/10">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary-600" />
              <CardTitle className="text-base text-primary-900 dark:text-primary-100">
                AI Recommendations
              </CardTitle>
            </div>
            <CardDescription>Actions to maximize revenue</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {dashboard?.ai_recommendations.map((rec) => (
                <div
                  key={rec.id}
                  className="rounded-lg bg-white dark:bg-card border border-border p-3 hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-xs font-semibold text-foreground">
                      {rec.title}
                    </p>
                    <Badge
                      variant={
                        rec.priority === "high"
                          ? "destructive"
                          : rec.priority === "medium"
                          ? "warning"
                          : "secondary"
                      }
                      className="text-xs py-0 flex-shrink-0"
                    >
                      {rec.priority}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
                    {rec.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1 text-xs text-primary-600">
                      <TrendingUp className="h-3 w-3" />
                      Impact: {rec.impact_score}/100
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 text-xs px-2"
                    >
                      {rec.action_label}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Templates */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Top Performing Templates</CardTitle>
              <CardDescription>Highest open & reply rates this month</CardDescription>
            </div>
            <Button variant="outline" size="sm" className="text-xs h-7">
              View all templates
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {dashboard?.top_templates.map((template, idx) => (
              <div
                key={template.id}
                className="rounded-lg border border-border p-3 hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-muted-foreground">
                      #{idx + 1}
                    </span>
                    <p className="text-xs font-semibold text-foreground line-clamp-1">
                      {template.name}
                    </p>
                  </div>
                  {template.industry && (
                    <Badge variant="ghost" className="text-xs py-0 px-1.5 flex-shrink-0">
                      {template.industry}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mb-2 italic line-clamp-1">
                  &ldquo;{template.subject}&rdquo;
                </p>
                <div className="flex items-center gap-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Open: </span>
                    <span className="font-semibold text-success-600">
                      {template.open_rate?.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Reply: </span>
                    <span className="font-semibold text-primary-600">
                      {template.reply_rate?.toFixed(1)}%
                    </span>
                  </div>
                  <div className="ml-auto text-muted-foreground">
                    {template.usage_count.toLocaleString()} uses
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
