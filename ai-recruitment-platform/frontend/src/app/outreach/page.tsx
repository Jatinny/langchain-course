"use client";
import { useQuery } from "@tanstack/react-query";
import { Plus, Send, Pause, Play, BarChart2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  paused: "bg-yellow-100 text-yellow-800",
  completed: "bg-blue-100 text-blue-800",
  draft: "bg-gray-100 text-gray-800",
};

export default function OutreachPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiClient.outreach.listCampaigns(),
  });

  const campaigns = data?.items || [];
  const totalSent = campaigns.reduce((s: number, c: any) => s + (c.sent_count || 0), 0);
  const avgOpenRate = campaigns.length > 0 ? campaigns.reduce((s: number, c: any) => s + (c.open_rate || 0), 0) / campaigns.length : 0;
  const avgReplyRate = campaigns.length > 0 ? campaigns.reduce((s: number, c: any) => s + (c.reply_rate || 0), 0) / campaigns.length : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Outreach Campaigns</h1>
          <p className="text-sm text-gray-500">{campaigns.length} campaigns</p>
        </div>
        <Button onClick={() => window.location.href = "/outreach/new"} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="h-4 w-4 mr-2" />New Campaign
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-blue-600">{totalSent}</p><p className="text-sm text-gray-500">Total Sent</p></CardContent></Card>
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-green-600">{(avgOpenRate * 100).toFixed(1)}%</p><p className="text-sm text-gray-500">Avg Open Rate</p></CardContent></Card>
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-purple-600">{(avgReplyRate * 100).toFixed(1)}%</p><p className="text-sm text-gray-500">Avg Reply Rate</p></CardContent></Card>
      </div>

      {/* Campaigns list */}
      <div className="space-y-4">
        {isLoading ? (
          [1,2,3].map(i => <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />)
        ) : campaigns.length === 0 ? (
          <Card><CardContent className="py-12 text-center">
            <Send className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No campaigns yet</p>
            <Button className="mt-4" onClick={() => window.location.href = "/outreach/new"}>Create your first campaign</Button>
          </CardContent></Card>
        ) : campaigns.map((campaign: any) => (
          <Card key={campaign.id} className="hover:shadow-md transition-shadow">
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-gray-900">{campaign.name}</h3>
                    <Badge className={STATUS_COLORS[campaign.status] || STATUS_COLORS.draft}>{campaign.status}</Badge>
                  </div>
                  <p className="text-sm text-gray-500 mb-3">{campaign.target_industry} • {campaign.target_region} • {campaign.target_role}</p>
                  <div className="flex gap-6">
                    <div className="text-center">
                      <p className="text-lg font-bold text-gray-900">{campaign.sent_count || 0}</p>
                      <p className="text-xs text-gray-400">Sent</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-blue-600">{((campaign.open_rate || 0) * 100).toFixed(0)}%</p>
                      <p className="text-xs text-gray-400">Opened</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-green-600">{((campaign.reply_rate || 0) * 100).toFixed(0)}%</p>
                      <p className="text-xs text-gray-400">Replied</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-purple-600">{((campaign.conversion_rate || 0) * 100).toFixed(0)}%</p>
                      <p className="text-xs text-gray-400">Converted</p>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 ml-4">
                  <Button variant="outline" size="sm"><BarChart2 className="h-4 w-4" /></Button>
                  {campaign.status === "active" ? (
                    <Button variant="outline" size="sm"><Pause className="h-4 w-4" /></Button>
                  ) : (
                    <Button variant="outline" size="sm"><Play className="h-4 w-4" /></Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
