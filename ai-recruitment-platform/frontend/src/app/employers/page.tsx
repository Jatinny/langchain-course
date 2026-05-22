"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Plus, Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiClient } from "@/lib/api";
import { getScoreColor, formatDate } from "@/lib/utils";
import type { Employer } from "@/types";

export default function EmployersPage() {
  const [search, setSearch] = useState("");
  const [industry, setIndustry] = useState("");
  const [region, setRegion] = useState("");
  const [vendorFriendly, setVendorFriendly] = useState<boolean | undefined>();
  const [page, setPage] = useState(1);
  const [isDiscovering, setIsDiscovering] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["employers", search, industry, region, vendorFriendly, page],
    queryFn: () =>
      apiClient.employers.list({ search, industry, region, vendor_friendly: vendorFriendly, page, limit: 20 }),
  });

  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      await apiClient.employers.discover({
        regions: region ? [region] : ["India"],
        industries: industry ? [industry] : ["IT Services"],
        roles: ["Java Developer", "AI Engineer", "Cloud Engineer"],
        limit: 100,
      });
      setTimeout(() => { refetch(); setIsDiscovering(false); }, 3000);
    } catch {
      setIsDiscovering(false);
    }
  };

  const industries = ["IT Services", "BFSI", "Product", "GCC", "Startup", "FinTech", "E-commerce", "Healthcare IT", "EdTech", "Telecom", "AI/ML"];
  const regions = ["India", "USA", "Canada", "UK", "Europe", "Singapore", "Australia", "UAE"];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Employers</h1>
          <p className="text-sm text-gray-500">{data?.total || 0} companies in database</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" size="sm" onClick={() => refetch()}><RefreshCw className="h-4 w-4 mr-2" />Refresh</Button>
          <Button variant="outline" size="sm"><Download className="h-4 w-4 mr-2" />Export CSV</Button>
          <Button onClick={handleDiscover} disabled={isDiscovering} className="bg-blue-600 hover:bg-blue-700">
            {isDiscovering ? <><RefreshCw className="h-4 w-4 mr-2 animate-spin" />Discovering...</> : <><Plus className="h-4 w-4 mr-2" />AI Discover</>}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <Input className="pl-9" placeholder="Search companies..." value={search} onChange={e => setSearch(e.target.value)} />
            </div>
            <select className="rounded-md border border-gray-200 px-3 py-2 text-sm bg-white dark:bg-gray-800" value={industry} onChange={e => setIndustry(e.target.value)}>
              <option value="">All Industries</option>
              {industries.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
            <select className="rounded-md border border-gray-200 px-3 py-2 text-sm bg-white dark:bg-gray-800" value={region} onChange={e => setRegion(e.target.value)}>
              <option value="">All Regions</option>
              {regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <select className="rounded-md border border-gray-200 px-3 py-2 text-sm bg-white dark:bg-gray-800" value={String(vendorFriendly ?? "")} onChange={e => setVendorFriendly(e.target.value === "" ? undefined : e.target.value === "true")}>
              <option value="">Any Vendor Status</option>
              <option value="true">Vendor Friendly ✓</option>
              <option value="false">Not Vendor Friendly</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Industry</TableHead>
              <TableHead>Region</TableHead>
              <TableHead>Score</TableHead>
              <TableHead>Vendor Friendly</TableHead>
              <TableHead>Contract/C2H</TableHead>
              <TableHead>Hiring Vol.</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={8} className="text-center py-8 text-gray-400">Loading employers...</TableCell></TableRow>
            ) : data?.items?.length === 0 ? (
              <TableRow><TableCell colSpan={8} className="text-center py-8 text-gray-400">No employers found. Try AI Discovery!</TableCell></TableRow>
            ) : data?.items?.map((employer: Employer) => (
              <TableRow key={employer.id} className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800" onClick={() => window.location.href = `/employers/${employer.id}`}>
                <TableCell>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">{employer.name}</div>
                    <div className="text-xs text-gray-500">{employer.website}</div>
                  </div>
                </TableCell>
                <TableCell><Badge variant="secondary">{employer.industry}</Badge></TableCell>
                <TableCell><span className="text-sm text-gray-600">{employer.region}</span></TableCell>
                <TableCell>
                  <span className={`font-bold text-sm ${getScoreColor(employer.score)}`}>{employer.score?.toFixed(0)}</span>
                </TableCell>
                <TableCell>{employer.is_vendor_friendly ? <Badge className="bg-green-100 text-green-800">Yes</Badge> : <Badge variant="outline">No</Badge>}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {employer.accepts_contract && <Badge variant="outline" className="text-xs">Contract</Badge>}
                    {employer.accepts_c2h && <Badge variant="outline" className="text-xs">C2H</Badge>}
                  </div>
                </TableCell>
                <TableCell><span className="text-sm">{employer.hiring_volume || 0}/mo</span></TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); window.location.href = `/employers/${employer.id}`; }}>View</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data && data.pages > 1 && (
          <div className="flex justify-center gap-2 p-4">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <span className="px-4 py-2 text-sm text-gray-600">Page {page} of {data.pages}</span>
            <Button variant="outline" size="sm" disabled={page === data.pages} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        )}
      </Card>
    </div>
  );
}
