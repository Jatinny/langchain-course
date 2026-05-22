"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, MapPin, Briefcase, DollarSign, Clock, Send } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data: candidate, isLoading } = useQuery({
    queryKey: ["candidate", id],
    queryFn: () => apiClient.candidates.getById(id),
    enabled: !!id,
  });

  const { data: matchData } = useQuery({
    queryKey: ["candidate-matches", id],
    queryFn: () => apiClient.candidates.matchJobs(id),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {[1,2,3].map(i => <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Candidate not found</p>
        <Button className="mt-4" onClick={() => router.push("/candidates")}>Back to Candidates</Button>
      </div>
    );
  }

  const skills = Array.isArray(candidate.skills) ? candidate.skills :
    (typeof candidate.skills === "string" ? JSON.parse(candidate.skills) : []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push("/candidates")}>
          <ArrowLeft className="h-4 w-4 mr-2" />Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{candidate.name}</h1>
          <p className="text-gray-500 text-sm">{candidate.current_title}</p>
        </div>
        <Badge className={candidate.availability === "immediate" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}>
          {candidate.availability}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <MapPin className="h-4 w-4 text-gray-400" />
                <span>{candidate.location}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Briefcase className="h-4 w-4 text-gray-400" />
                <span>{candidate.years_experience} years experience</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <DollarSign className="h-4 w-4 text-gray-400" />
                <span>{formatCurrency(candidate.salary_expectation_min)} – {formatCurrency(candidate.salary_expectation_max)}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Clock className="h-4 w-4 text-gray-400" />
                <span>{candidate.preferred_work_type}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Skills</CardTitle></CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill: string) => (
                  <Badge key={skill} className="bg-blue-100 text-blue-800">{skill}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Top Job Matches</CardTitle></CardHeader>
            <CardContent>
              {!matchData?.matches?.length ? (
                <p className="text-sm text-gray-400 text-center py-4">No matches found yet</p>
              ) : (
                <div className="space-y-3">
                  {matchData.matches.slice(0, 5).map((match: any) => (
                    <div key={match.job_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium text-sm text-gray-900">{match.job_title}</p>
                        <p className="text-xs text-gray-500">{match.company_name}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-blue-600">{(match.overall_score * 100).toFixed(0)}%</p>
                        <p className="text-xs text-gray-400">match</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Actions</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Button className="w-full bg-blue-600 hover:bg-blue-700">
                <Send className="h-4 w-4 mr-2" />Submit to Employer
              </Button>
              <Button variant="outline" className="w-full">Add to CRM</Button>
              <Button variant="outline" className="w-full">Schedule Interview</Button>
              <Button variant="outline" className="w-full">Download Resume</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Commission Estimate</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Min (8.33%)</span>
                <span className="font-semibold">{formatCurrency(candidate.salary_expectation_min * 0.0833)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Max (8.33%)</span>
                <span className="font-semibold text-green-600">{formatCurrency(candidate.salary_expectation_max * 0.0833)}</span>
              </div>
              <p className="text-xs text-gray-400 mt-2">Based on 1-month salary (8.33%) standard fee</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
