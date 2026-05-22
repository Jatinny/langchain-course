"use client";
import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Upload, Search, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import type { Candidate } from "@/types";

export default function CandidatesPage() {
  const [search, setSearch] = useState("");
  const [workType, setWorkType] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["candidates", search, workType],
    queryFn: () => apiClient.candidates.list({ search, work_type: workType, limit: 20 }),
  });

  const handleFileDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    setUploading(true);
    try {
      await apiClient.candidates.parseResume(file);
      refetch();
    } finally {
      setUploading(false);
    }
  }, [refetch]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Candidates</h1>
          <p className="text-sm text-gray-500">{data?.total || 0} candidates in database</p>
        </div>
        <Button className="bg-blue-600 hover:bg-blue-700">
          <UserPlus className="h-4 w-4 mr-2" />Add Candidate
        </Button>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleFileDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400"}`}
      >
        <Upload className="h-8 w-8 mx-auto mb-3 text-gray-400" />
        <p className="text-sm font-medium text-gray-700">
          {uploading ? "Parsing resume with AI..." : "Drop resume files here (PDF, DOCX) or click to upload"}
        </p>
        <p className="text-xs text-gray-400 mt-1">AI will automatically extract skills, experience, and contact info</p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 flex gap-4 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <Input className="pl-9" placeholder="Search by name, skill, title..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="rounded-md border border-gray-200 px-3 py-2 text-sm" value={workType} onChange={e => setWorkType(e.target.value)}>
            <option value="">Any Work Type</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">Onsite</option>
          </select>
        </CardContent>
      </Card>

      {/* Candidates grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.items?.map((candidate: Candidate) => (
            <Card key={candidate.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => window.location.href = `/candidates/${candidate.id}`}>
              <CardContent className="p-5">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">{candidate.name}</h3>
                    <p className="text-sm text-gray-500">{candidate.current_title}</p>
                  </div>
                  <Badge className={candidate.availability === "immediate" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}>
                    {candidate.availability}
                  </Badge>
                </div>
                <p className="text-xs text-gray-500 mb-3">{candidate.location} • {candidate.years_experience}y exp</p>
                <div className="flex flex-wrap gap-1">
                  {candidate.skills?.slice(0, 5).map(skill => (
                    <span key={skill} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded">{skill}</span>
                  ))}
                  {(candidate.skills?.length || 0) > 5 && <span className="text-xs text-gray-400">+{candidate.skills.length - 5} more</span>}
                </div>
                {candidate.salary_expectation_min && (
                  <p className="text-xs text-gray-500 mt-2">₹{(candidate.salary_expectation_min / 100000).toFixed(1)}L - ₹{(candidate.salary_expectation_max / 100000).toFixed(1)}L</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
