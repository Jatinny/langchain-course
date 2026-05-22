"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Bell,
  Sparkles,
  Moon,
  Sun,
  Settings,
  LogOut,
  User,
  ChevronDown,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn, getInitials } from "@/lib/utils";

interface Notification {
  id: string;
  title: string;
  description: string;
  time: string;
  read: boolean;
  type: "reply" | "placement" | "discovery" | "alert";
}

const mockNotifications: Notification[] = [
  {
    id: "1",
    title: "New Reply Received",
    description: "Infosys HR responded to your outreach campaign",
    time: "5m ago",
    read: false,
    type: "reply",
  },
  {
    id: "2",
    title: "Placement Confirmed",
    description: "John Doe placed at TCS — ₹45,000 commission earned",
    time: "1h ago",
    read: false,
    type: "placement",
  },
  {
    id: "3",
    title: "AI Discovery Complete",
    description: "Found 24 new vendor-friendly employers in Bangalore",
    time: "3h ago",
    read: true,
    type: "discovery",
  },
];

const mockUser = {
  name: "Rahul Sharma",
  email: "rahul@recruitai.in",
  role: "Senior Recruiter",
};

export function TopNav() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDiscovering, setIsDiscovering] = useState(false);

  const unreadCount = mockNotifications.filter((n) => !n.read).length;

  const handleAIDiscover = async () => {
    setIsDiscovering(true);
    // Simulate AI discovery
    await new Promise((r) => setTimeout(r, 2000));
    setIsDiscovering(false);
    router.push("/employers");
  };

  const notifColors: Record<Notification["type"], string> = {
    reply: "bg-blue-100 text-blue-600",
    placement: "bg-green-100 text-green-600",
    discovery: "bg-purple-100 text-purple-600",
    alert: "bg-red-100 text-red-600",
  };

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-4 border-b border-border bg-background/95 backdrop-blur px-4 shadow-sm">
      {/* Global Search */}
      <div className="flex-1 max-w-md">
        <Input
          placeholder="Search employers, candidates, campaigns..."
          leftIcon={<Search className="h-4 w-4" />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 bg-muted/50"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* AI Discover Button */}
        <Button
          size="sm"
          onClick={handleAIDiscover}
          loading={isDiscovering}
          className="gap-1.5 bg-gradient-to-r from-primary-600 to-indigo-600 hover:from-primary-700 hover:to-indigo-700 shadow-sm"
        >
          <Sparkles className="h-3.5 w-3.5" />
          AI Discover
        </Button>

        {/* Dark Mode Toggle */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowUserMenu(false);
            }}
            className="relative flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-danger-500 ring-2 ring-background" />
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-11 w-80 rounded-xl border border-border bg-background shadow-xl z-50">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <h3 className="text-sm font-semibold">Notifications</h3>
                {unreadCount > 0 && (
                  <Badge variant="destructive" className="text-xs">
                    {unreadCount} new
                  </Badge>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {mockNotifications.map((notif) => (
                  <div
                    key={notif.id}
                    className={cn(
                      "flex items-start gap-3 px-4 py-3 hover:bg-muted/50 cursor-pointer transition-colors",
                      !notif.read && "bg-primary-50/50 dark:bg-primary-900/10"
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold flex-shrink-0",
                        notifColors[notif.type]
                      )}
                    >
                      {notif.type === "reply" && "R"}
                      {notif.type === "placement" && "P"}
                      {notif.type === "discovery" && "D"}
                      {notif.type === "alert" && "!"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className={cn(
                          "text-sm",
                          !notif.read ? "font-semibold" : "font-medium"
                        )}
                      >
                        {notif.title}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {notif.description}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">
                      {notif.time}
                    </span>
                  </div>
                ))}
              </div>
              <div className="border-t border-border px-4 py-2">
                <button className="text-xs text-primary-600 hover:text-primary-700 font-medium w-full text-center py-1">
                  View all notifications
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => {
              setShowUserMenu(!showUserMenu);
              setShowNotifications(false);
            }}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted transition-colors"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-600 text-white text-xs font-semibold">
              {getInitials(mockUser.name)}
            </div>
            <span className="hidden sm:block text-sm font-medium text-foreground">
              {mockUser.name.split(" ")[0]}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </button>

          {showUserMenu && (
            <div className="absolute right-0 top-11 w-56 rounded-xl border border-border bg-background shadow-xl z-50 py-1">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-sm font-semibold">{mockUser.name}</p>
                <p className="text-xs text-muted-foreground">{mockUser.email}</p>
                <Badge variant="ghost" className="mt-1 text-xs">
                  {mockUser.role}
                </Badge>
              </div>
              <div className="py-1">
                <button
                  onClick={() => router.push("/profile")}
                  className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  <User className="h-4 w-4 text-muted-foreground" />
                  My Profile
                </button>
                <button
                  onClick={() => router.push("/settings")}
                  className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  <Settings className="h-4 w-4 text-muted-foreground" />
                  Settings
                </button>
              </div>
              <div className="border-t border-border pt-1 pb-1">
                <button className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-danger-600 hover:bg-danger-50 dark:hover:bg-danger-900/10 transition-colors">
                  <LogOut className="h-4 w-4" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
