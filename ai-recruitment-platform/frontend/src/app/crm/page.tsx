"use client";
import { useQuery } from "@tanstack/react-query";
import { DollarSign, TrendingUp, Users, Briefcase } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";

const STAGES = ["prospecting", "contacted", "interested", "vendor_registered", "active", "closed_won"];
const STAGE_COLORS: Record<string, string> = {
  prospecting: "bg-gray-100",
  contacted: "bg-blue-50",
  interested: "bg-yellow-50",
  vendor_registered: "bg-orange-50",
  active: "bg-green-50",
  closed_won: "bg-emerald-50",
};

export default function CRMPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["crm-pipeline"],
    queryFn: () => apiClient.crm.getPipeline(),
  });

  const { data: revenueData } = useQuery({
    queryKey: ["crm-revenue"],
    queryFn: () => apiClient.crm.getRevenue(),
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">CRM Pipeline</h1>
        <Button className="bg-blue-600 hover:bg-blue-700">+ Add Employer</Button>
      </div>

      {/* Revenue summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <DollarSign className="h-8 w-8 text-green-500" />
            <div><p className="text-sm text-gray-500">Pipeline Value</p><p className="text-xl font-bold">₹{((data?.total_pipeline_value || 0)/100000).toFixed(1)}L</p></div>
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <TrendingUp className="h-8 w-8 text-blue-500" />
            <div><p className="text-sm text-gray-500">Revenue MTD</p><p className="text-xl font-bold">₹{((revenueData?.revenue_mtd || 0)/100000).toFixed(1)}L</p></div>
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <Users className="h-8 w-8 text-purple-500" />
            <div><p className="text-sm text-gray-500">Active Employers</p><p className="text-xl font-bold">{data?.stages?.active?.length || 0}</p></div>
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <Briefcase className="h-8 w-8 text-orange-500" />
            <div><p className="text-sm text-gray-500">Placements MTD</p><p className="text-xl font-bold">{revenueData?.placements_mtd || 0}</p></div>
          </div>
        </CardContent></Card>
      </div>

      {/* Kanban board */}
      <div className="overflow-x-auto">
        <div className="flex gap-4 pb-4" style={{ minWidth: "1200px" }}>
          {STAGES.map(stage => {
            const stageItems = data?.stages?.[stage] || [];
            return (
              <div key={stage} className="flex-1 min-w-[200px]">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-700 capitalize">{stage.replace("_", " ")}</h3>
                  <span className="text-xs bg-gray-200 text-gray-600 rounded-full px-2 py-0.5">{stageItems.length}</span>
                </div>
                <div className="space-y-3">
                  {isLoading ? (
                    [1,2].map(i => <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />)
                  ) : stageItems.map((item: any) => (
                    <div key={item.employer_id} className={`${STAGE_COLORS[stage]} rounded-lg p-3 border border-gray-200 cursor-pointer hover:shadow-sm`}>
                      <p className="font-medium text-sm text-gray-900">{item.company || "Unknown Company"}</p>
                      {item.expected_monthly_revenue > 0 && (
                        <p className="text-xs text-green-700 mt-1">₹{(item.expected_monthly_revenue/1000).toFixed(0)}K/mo</p>
                      )}
                      <div className="flex items-center justify-between mt-2">
                        <Badge variant="outline" className="text-xs">{item.probability || 0}%</Badge>
                        <Button variant="ghost" size="sm" className="h-6 text-xs px-2">Move</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
