"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api";

const INDUSTRIES = ["IT Services", "FinTech", "BFSI", "GCC", "Product", "E-commerce", "EdTech", "Healthcare IT"];
const REGIONS = ["Bangalore", "Hyderabad", "Pune", "Mumbai", "Delhi NCR", "Chennai", "India", "USA", "UK"];
const CHANNELS = ["email", "linkedin", "whatsapp"];

export default function NewCampaignPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    target_role: "",
    target_industry: "",
    target_region: "",
    channel: "email",
    max_contacts: 50,
    message_template: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.outreach.createCampaign(form);
      router.push("/outreach");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push("/outreach")}>
          <ArrowLeft className="h-4 w-4 mr-2" />Back
        </Button>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">New Campaign</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader><CardTitle>Campaign Details</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Campaign Name</label>
              <Input
                className="mt-1"
                placeholder="e.g. Java Developer Q1 2025"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Target Role</label>
              <Input
                className="mt-1"
                placeholder="e.g. Java Developer"
                value={form.target_role}
                onChange={e => setForm({ ...form, target_role: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Target Industry</label>
                <select
                  className="mt-1 block w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                  value={form.target_industry}
                  onChange={e => setForm({ ...form, target_industry: e.target.value })}
                >
                  <option value="">All Industries</option>
                  {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Target Region</label>
                <select
                  className="mt-1 block w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                  value={form.target_region}
                  onChange={e => setForm({ ...form, target_region: e.target.value })}
                >
                  <option value="">All Regions</option>
                  {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Outreach Configuration</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Channel</label>
              <div className="flex gap-3 mt-2">
                {CHANNELS.map(ch => (
                  <button key={ch} type="button"
                    onClick={() => setForm({ ...form, channel: ch })}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors capitalize
                      ${form.channel === ch ? "border-blue-600 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-600 hover:border-gray-300"}`}>
                    {ch}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Max Contacts</label>
              <Input
                type="number"
                className="mt-1 w-32"
                value={form.max_contacts}
                onChange={e => setForm({ ...form, max_contacts: parseInt(e.target.value) || 50 })}
                min={1}
                max={500}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Message Template (optional override)</label>
              <textarea
                className="mt-1 block w-full rounded-md border border-gray-200 px-3 py-2 text-sm h-32 resize-none"
                placeholder="Leave blank to auto-generate with AI..."
                value={form.message_template}
                onChange={e => setForm({ ...form, message_template: e.target.value })}
              />
              <p className="text-xs text-gray-400 mt-1">Use {"{"}{"{"} candidate_name {"}"}{"}"},  {"{"}{"{"} company_name {"}"}{"}"} as placeholders</p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => router.push("/outreach")}>Cancel</Button>
          <Button type="submit" className="bg-blue-600 hover:bg-blue-700" disabled={loading}>
            {loading ? "Creating..." : "Create Campaign"}
          </Button>
        </div>
      </form>
    </div>
  );
}
