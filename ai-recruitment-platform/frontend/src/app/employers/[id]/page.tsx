"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Globe, MapPin, Users, Star, Mail, Phone, Linkedin } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { getScoreColor } from "@/lib/utils";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from "recharts";

export default function EmployerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data: employer, isLoading } = useQuery({
    queryKey: ["employer", id],
    queryFn: () => apiClient.employers.getById(id),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {[1,2,3].map(i => <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (!employer) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Employer not found</p>
        <Button className="mt-4" onClick={() => router.push("/employers")}>Back to Employers</Button>
      </div>
    );
  }

  const radarData = [
    { subject: "Vendor Friendly", value: employer.is_vendor_friendly ? 90 : 20 },
    { subject: "Contract", value: employer.accepts_contract ? 85 : 30 },
    { subject: "C2H", value: employer.accepts_c2h ? 80 : 25 },
    { subject: "Score", value: employer.score || 0 },
    { subject: "Volume", value: Math.min(100, (employer.hiring_volume || 0) / 5) },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push("/employers")}>
          <ArrowLeft className="h-4 w-4 mr-2" />Back
        </Button>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{employer.name}</h1>
        <Badge className="bg-blue-100 text-blue-800">{employer.industry}</Badge>
        <span className={`text-2xl font-bold ${getScoreColor(employer.score)}`}>{employer.score}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle>Company Overview</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <MapPin className="h-4 w-4 text-gray-400" />
                <span>{employer.region}, {employer.country}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Users className="h-4 w-4 text-gray-400" />
                <span>{employer.size} employees</span>
              </div>
              {employer.website && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Globe className="h-4 w-4 text-gray-400" />
                  <a href={`https://${employer.website}`} target="_blank" rel="noopener noreferrer"
                    className="text-blue-600 hover:underline">{employer.website}</a>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Star className="h-4 w-4 text-gray-400" />
                <span>{employer.hiring_volume || 0} hires/year</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Engagement Flags</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Badge className={employer.is_vendor_friendly ? "bg-green-100 text-green-800" : "bg-red-100 text-red-700"}>
                {employer.is_vendor_friendly ? "Vendor Friendly" : "Not Vendor Friendly"}
              </Badge>
              <Badge className={employer.accepts_contract ? "bg-blue-100 text-blue-800" : "bg-gray-100 text-gray-600"}>
                {employer.accepts_contract ? "Accepts Contract" : "No Contract"}
              </Badge>
              <Badge className={employer.accepts_c2h ? "bg-purple-100 text-purple-800" : "bg-gray-100 text-gray-600"}>
                {employer.accepts_c2h ? "C2H Available" : "No C2H"}
              </Badge>
              <Badge className="bg-gray-100 text-gray-700">{employer.status}</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Actions</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button className="bg-blue-600 hover:bg-blue-700">
                <Mail className="h-4 w-4 mr-2" />Send Outreach Email
              </Button>
              <Button variant="outline">
                <Linkedin className="h-4 w-4 mr-2" />LinkedIn Connect
              </Button>
              <Button variant="outline" onClick={() => router.push(`/crm?employer=${id}`)}>
                Add to Pipeline
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Score Breakdown</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                  <Radar name="Score" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Key Metrics</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {[
                { label: "Overall Score", value: `${employer.score}/100`, color: getScoreColor(employer.score) },
                { label: "Industry", value: employer.industry, color: "text-gray-700" },
                { label: "Region", value: employer.region, color: "text-gray-700" },
                { label: "Hiring Volume", value: `${employer.hiring_volume || 0}/yr`, color: "text-gray-700" },
              ].map(item => (
                <div key={item.label} className="flex justify-between items-center py-1 border-b border-gray-100 last:border-0">
                  <span className="text-sm text-gray-500">{item.label}</span>
                  <span className={`text-sm font-semibold ${item.color}`}>{item.value}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
