"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("monthly");

  const { data: dashboard } = useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: () => apiClient.analytics.getDashboard(),
  });

  const { data: marketDemand } = useQuery({
    queryKey: ["market-demand"],
    queryFn: () => apiClient.analytics.getMarketDemand("Java Developer", "India"),
  });

  const outreachData = [
    { name: "Email", sent: dashboard?.outreach_performance?.sent || 0, replied: dashboard?.outreach_performance?.replied || 0 },
    { name: "LinkedIn", sent: 45, replied: 12 },
    { name: "WhatsApp", sent: 30, replied: 18 },
  ];

  const industryRevenue = [
    { name: "IT Services", value: 40 }, { name: "GCC", value: 25 },
    { name: "FinTech", value: 15 }, { name: "Product", value: 12 }, { name: "Others", value: 8 },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics</h1>
        <div className="flex gap-2">
          {["weekly", "monthly", "quarterly"].map(p => (
            <Button key={p} variant={period === p ? "default" : "outline"} size="sm" onClick={() => setPeriod(p)}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </Button>
          ))}
          <Button variant="outline" size="sm">Export Report</Button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Open Rate", value: `${((dashboard?.outreach_performance?.open_rate || 0) * 100).toFixed(1)}%`, color: "text-blue-600" },
          { label: "Reply Rate", value: `${((dashboard?.outreach_performance?.reply_rate || 0) * 100).toFixed(1)}%`, color: "text-green-600" },
          { label: "Conversion Rate", value: `${((dashboard?.outreach_performance?.conversion_rate || 0) * 100).toFixed(1)}%`, color: "text-purple-600" },
          { label: "Revenue MTD", value: `₹${((dashboard?.kpis?.revenue_mtd || 0)/100000).toFixed(1)}L`, color: "text-orange-600" },
        ].map(kpi => (
          <Card key={kpi.label}><CardContent className="pt-4 text-center">
            <p className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</p>
            <p className="text-sm text-gray-500 mt-1">{kpi.label}</p>
          </CardContent></Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <Card>
          <CardHeader><CardTitle>Revenue Trend</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={dashboard?.revenue_trend || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={v => `₹${(v/100000).toFixed(0)}L`} />
                <Tooltip formatter={(v: number) => [`₹${(v/100000).toFixed(2)}L`, "Revenue"]} />
                <Area type="monotone" dataKey="revenue" stroke="#3b82f6" fill="#dbeafe" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Outreach by Channel */}
        <Card>
          <CardHeader><CardTitle>Outreach by Channel</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={outreachData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="sent" fill="#3b82f6" name="Sent" />
                <Bar dataKey="replied" fill="#10b981" name="Replied" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Revenue by Industry */}
        <Card>
          <CardHeader><CardTitle>Revenue by Industry</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={industryRevenue} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}%`}>
                  {industryRevenue.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* AI Recommendations */}
        <Card>
          <CardHeader><CardTitle>AI Recommendations</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {dashboard?.ai_recommendations?.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No recommendations available</p>
              ) : dashboard?.ai_recommendations?.map((rec: any) => (
                <div key={rec.id} className="p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={rec.priority === "high" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}>{rec.priority}</Badge>
                    <span className="text-sm font-medium">{rec.title}</span>
                  </div>
                  <p className="text-xs text-gray-600">{rec.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
