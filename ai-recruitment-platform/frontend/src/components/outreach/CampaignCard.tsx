"use client";

import React from "react";
import {
  Mail,
  Linkedin,
  MessageSquare,
  Send,
  Eye,
  Reply,
  Pause,
  Play,
  Trash2,
  MoreVertical,
  Calendar,
  Target,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate, formatPercentage } from "@/lib/utils";
import type { OutreachCampaign } from "@/types";

interface CampaignCardProps {
  campaign: OutreachCampaign;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onDelete?: (id: string) => void;
  onClick?: (campaign: OutreachCampaign) => void;
}

const channelIcons = {
  email: Mail,
  linkedin: Linkedin,
  whatsapp: MessageSquare,
  telegram: MessageSquare,
};

const statusConfig = {
  active: { label: "Active", variant: "success" as const, dot: true },
  paused: { label: "Paused", variant: "warning" as const, dot: true },
  completed: { label: "Completed", variant: "secondary" as const },
  draft: { label: "Draft", variant: "ghost" as const },
  failed: { label: "Failed", variant: "destructive" as const },
};

export function CampaignCard({
  campaign,
  onPause,
  onResume,
  onDelete,
  onClick,
}: CampaignCardProps) {
  const [showMenu, setShowMenu] = React.useState(false);
  const status = statusConfig[campaign.status];
  const ChannelIcon = channelIcons[campaign.channel];
  const sentPct =
    campaign.stats.total_targets > 0
      ? (campaign.stats.sent / campaign.stats.total_targets) * 100
      : 0;

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-card-hover",
        onClick && "cursor-pointer"
      )}
      onClick={() => onClick?.(campaign)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-start gap-2.5 min-w-0">
            <div
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-lg flex-shrink-0",
                campaign.channel === "email" && "bg-blue-100 text-blue-600",
                campaign.channel === "linkedin" && "bg-sky-100 text-sky-600",
                campaign.channel === "whatsapp" && "bg-green-100 text-green-600",
                campaign.channel === "telegram" && "bg-indigo-100 text-indigo-600"
              )}
            >
              <ChannelIcon className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-foreground line-clamp-1">
                {campaign.name}
              </h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Target className="h-3 w-3 text-muted-foreground" />
                <span className="text-xs text-muted-foreground line-clamp-1">
                  {campaign.target_audience.industries.slice(0, 2).join(", ")}
                  {campaign.target_audience.industries.length > 2 && " +more"}
                  {" · "}
                  {campaign.target_audience.regions.slice(0, 2).join(", ")}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Badge variant={status.variant} dot={status.dot} className="text-xs">
              {status.label}
            </Badge>
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu(!showMenu);
                }}
                className="text-muted-foreground hover:text-foreground p-1 rounded"
              >
                <MoreVertical className="h-4 w-4" />
              </button>
              {showMenu && (
                <div className="absolute right-0 top-7 w-40 rounded-lg border border-border bg-background shadow-lg z-10 py-1">
                  {campaign.status === "active" && onPause && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onPause(campaign.id);
                        setShowMenu(false);
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-xs text-foreground hover:bg-muted"
                    >
                      <Pause className="h-3.5 w-3.5" />
                      Pause Campaign
                    </button>
                  )}
                  {campaign.status === "paused" && onResume && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onResume(campaign.id);
                        setShowMenu(false);
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-xs text-foreground hover:bg-muted"
                    >
                      <Play className="h-3.5 w-3.5" />
                      Resume Campaign
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(campaign.id);
                        setShowMenu(false);
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-xs text-danger-600 hover:bg-danger-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>Progress</span>
            <span>
              {campaign.stats.sent}/{campaign.stats.total_targets} sent
            </span>
          </div>
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                campaign.status === "active" ? "bg-primary-500" : "bg-muted-foreground/50"
              )}
              style={{ width: `${sentPct}%` }}
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="text-center p-2 rounded-lg bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
              <Send className="h-3 w-3" />
              <span className="text-xs">Sent</span>
            </div>
            <p className="text-sm font-bold text-foreground">
              {campaign.stats.sent.toLocaleString()}
            </p>
          </div>
          <div className="text-center p-2 rounded-lg bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
              <Eye className="h-3 w-3" />
              <span className="text-xs">Opened</span>
            </div>
            <p className="text-sm font-bold text-foreground">
              {formatPercentage(campaign.open_rate)}
            </p>
          </div>
          <div className="text-center p-2 rounded-lg bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
              <Reply className="h-3 w-3" />
              <span className="text-xs">Replied</span>
            </div>
            <p className="text-sm font-bold text-foreground">
              {formatPercentage(campaign.reply_rate)}
            </p>
          </div>
        </div>

        {/* Date */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3" />
          Created {formatDate(campaign.created_at, "MMM d, yyyy")}
        </div>
      </CardContent>
    </Card>
  );
}
