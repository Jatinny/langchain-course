"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  LayoutDashboard,
  Building2,
  Briefcase,
  Users,
  Zap,
  Mail,
  FileText,
  GitMerge,
  Upload,
  Award,
  BarChart3,
  DollarSign,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { cn, getInitials } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: number;
  badgeVariant?: "default" | "success" | "warning" | "destructive";
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    title: "Sourcing",
    items: [
      { label: "Employers", href: "/employers", icon: Building2 },
      { label: "Job Postings", href: "/jobs", icon: Briefcase },
    ],
  },
  {
    title: "Talent",
    items: [
      { label: "Candidates", href: "/candidates", icon: Users },
      { label: "Matching", href: "/matching", icon: Zap },
    ],
  },
  {
    title: "Outreach",
    items: [
      {
        label: "Campaigns",
        href: "/outreach",
        icon: Mail,
        badge: 3,
        badgeVariant: "success",
      },
      { label: "Templates", href: "/templates", icon: FileText },
    ],
  },
  {
    title: "CRM",
    items: [
      { label: "Pipeline", href: "/crm", icon: GitMerge },
      { label: "Submissions", href: "/submissions", icon: Upload },
      { label: "Placements", href: "/placements", icon: Award },
    ],
  },
  {
    title: "Revenue",
    items: [
      { label: "Commissions", href: "/commissions", icon: DollarSign },
      { label: "Analytics", href: "/analytics", icon: BarChart3 },
    ],
  },
  {
    title: "System",
    items: [
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

const mockUser = {
  name: "Rahul Sharma",
  email: "rahul@recruitai.in",
  role: "Senior Recruiter",
  avatar: null,
};

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<string[]>(
    navGroups.map((g) => g.title)
  );

  const toggleGroup = (title: string) => {
    setExpandedGroups((prev) =>
      prev.includes(title)
        ? prev.filter((g) => g !== title)
        : [...prev, title]
    );
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === href || pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={cn(
        "flex flex-col h-screen bg-brand-navy text-white transition-all duration-300 relative flex-shrink-0",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 flex-shrink-0">
          <Bot className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <div>
            <span className="text-base font-bold text-white">RecruitAI</span>
            <span className="ml-1 text-xs text-primary-300 font-medium">Pro</span>
          </div>
        )}
      </div>

      {/* Toggle button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-16 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-white shadow-md hover:bg-primary-700 transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="h-3.5 w-3.5" />
        ) : (
          <ChevronLeft className="h-3.5 w-3.5" />
        )}
      </button>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
        {navGroups.map((group) => (
          <div key={group.title} className="mb-1">
            {!collapsed && (
              <button
                onClick={() => toggleGroup(group.title)}
                className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-white/40 hover:text-white/60 transition-colors"
              >
                {group.title}
                <ChevronDown
                  className={cn(
                    "h-3 w-3 transition-transform",
                    expandedGroups.includes(group.title) ? "rotate-0" : "-rotate-90"
                  )}
                />
              </button>
            )}

            {(collapsed || expandedGroups.includes(group.title)) && (
              <div className="space-y-0.5 mt-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-2 py-2 text-sm transition-all duration-150",
                        active
                          ? "bg-primary-600/80 text-white font-medium"
                          : "text-white/70 hover:bg-white/10 hover:text-white"
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 flex-shrink-0",
                          active ? "text-white" : "text-white/60"
                        )}
                      />
                      {!collapsed && (
                        <>
                          <span className="flex-1 truncate">{item.label}</span>
                          {item.badge && (
                            <Badge
                              variant={item.badgeVariant || "default"}
                              className="text-xs py-0 px-1.5 h-4 min-w-[1rem]"
                            >
                              {item.badge}
                            </Badge>
                          )}
                        </>
                      )}
                      {collapsed && item.badge && (
                        <span className="absolute left-8 top-0 h-2 w-2 rounded-full bg-success-400" />
                      )}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* User Profile */}
      <div className="border-t border-white/10 p-3">
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg p-2 hover:bg-white/10 transition-colors cursor-pointer",
            collapsed && "justify-center"
          )}
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-500 text-white text-xs font-semibold flex-shrink-0">
            {getInitials(mockUser.name)}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {mockUser.name}
              </p>
              <p className="text-xs text-white/50 truncate">{mockUser.role}</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
