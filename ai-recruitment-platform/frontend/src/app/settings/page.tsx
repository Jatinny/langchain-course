"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const INTEGRATIONS = [
  { id: "apollo", name: "Apollo.io", description: "Contact enrichment & email finding", icon: "🚀", category: "enrichment" },
  { id: "hunter", name: "Hunter.io", description: "Email finder & verifier", icon: "🎯", category: "enrichment" },
  { id: "linkedin", name: "LinkedIn", description: "Recruiter outreach & profile search", icon: "💼", category: "social" },
  { id: "gmail", name: "Gmail", description: "Automated email sending", icon: "📧", category: "email" },
  { id: "whatsapp", name: "WhatsApp Business", description: "WhatsApp recruiter outreach", icon: "💬", category: "messaging" },
  { id: "telegram", name: "Telegram Bot", description: "Real-time notifications", icon: "✈️", category: "messaging" },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("integrations");
  const [connectedIntegrations, setConnectedIntegrations] = useState<Set<string>>(new Set());
  const [commissionPct, setCommissionPct] = useState("8.33");
  const [preferredLLM, setPreferredLLM] = useState("gpt-4o");

  const tabs = ["integrations", "commission", "ai-settings", "notifications", "profile"];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>

      <div className="flex gap-2 border-b border-gray-200 pb-0">
        {tabs.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${activeTab === tab ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {tab.replace("-", " ")}
          </button>
        ))}
      </div>

      {activeTab === "integrations" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {INTEGRATIONS.map(integration => (
            <Card key={integration.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex gap-3">
                    <span className="text-2xl">{integration.icon}</span>
                    <div>
                      <h3 className="font-semibold text-gray-900">{integration.name}</h3>
                      <p className="text-sm text-gray-500">{integration.description}</p>
                    </div>
                  </div>
                  <Badge className={connectedIntegrations.has(integration.id) ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}>
                    {connectedIntegrations.has(integration.id) ? "Connected" : "Not Connected"}
                  </Badge>
                </div>
                <div className="mt-4 space-y-2">
                  <Input placeholder={`${integration.name} API Key`} type="password" />
                  <Button size="sm" className="w-full" variant={connectedIntegrations.has(integration.id) ? "outline" : "default"}
                    onClick={() => setConnectedIntegrations(prev => { const next = new Set(prev); next.has(integration.id) ? next.delete(integration.id) : next.add(integration.id); return next; })}>
                    {connectedIntegrations.has(integration.id) ? "Disconnect" : "Connect"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {activeTab === "commission" && (
        <Card><CardHeader><CardTitle>Commission Settings</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Default Permanent Placement Fee (%)</label>
              <p className="text-xs text-gray-400 mb-2">Standard India: 8.33% = 1 month salary</p>
              <Input type="number" value={commissionPct} onChange={e => setCommissionPct(e.target.value)} className="w-40" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Default Contract Margin (%)</label>
              <Input type="number" defaultValue="15" className="w-40" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">C2H Contract Duration (months)</label>
              <Input type="number" defaultValue="6" className="w-40" />
            </div>
            <Button className="bg-blue-600 hover:bg-blue-700">Save Commission Settings</Button>
          </CardContent>
        </Card>
      )}

      {activeTab === "ai-settings" && (
        <Card><CardHeader><CardTitle>AI Configuration</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Preferred LLM</label>
              <select className="mt-1 block w-full rounded-md border border-gray-200 px-3 py-2 text-sm" value={preferredLLM} onChange={e => setPreferredLLM(e.target.value)}>
                <option value="gpt-4o">GPT-4o (Recommended)</option>
                <option value="claude-opus-4-7">Claude Opus</option>
                <option value="gpt-4o-mini">GPT-4o Mini (Faster)</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Outreach Style</label>
              <select className="mt-1 block w-full rounded-md border border-gray-200 px-3 py-2 text-sm">
                <option value="professional">Professional & Formal</option>
                <option value="casual">Casual & Friendly</option>
                <option value="mixed">Mixed (AI decides)</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Auto Follow-up</label>
              <div className="flex items-center gap-3 mt-2">
                <input type="checkbox" defaultChecked className="h-4 w-4" />
                <span className="text-sm text-gray-600">Enable automatic follow-up sequences</span>
              </div>
            </div>
            <Button className="bg-blue-600 hover:bg-blue-700">Save AI Settings</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
