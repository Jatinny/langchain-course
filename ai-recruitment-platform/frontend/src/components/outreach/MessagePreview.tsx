"use client";

import React from "react";
import {
  Mail,
  Linkedin,
  MessageSquare,
  User,
  AtSign,
  Shield,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { OutreachChannel } from "@/types";

interface MessagePreviewProps {
  channel: OutreachChannel;
  subject?: string;
  body: string;
  senderName?: string;
  recipientName?: string;
  recipientCompany?: string;
  antiSpamScore?: number;
  className?: string;
}

const channelConfig = {
  email: {
    label: "Email Preview",
    icon: Mail,
    color: "text-blue-600",
    bg: "bg-blue-50",
  },
  linkedin: {
    label: "LinkedIn Message",
    icon: Linkedin,
    color: "text-sky-600",
    bg: "bg-sky-50",
  },
  whatsapp: {
    label: "WhatsApp Message",
    icon: MessageSquare,
    color: "text-green-600",
    bg: "bg-green-50",
  },
  telegram: {
    label: "Telegram Message",
    icon: MessageSquare,
    color: "text-indigo-600",
    bg: "bg-indigo-50",
  },
};

function interpolate(
  template: string,
  vars: Record<string, string>
): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => vars[key] || `{{${key}}}`);
}

export function MessagePreview({
  channel,
  subject,
  body,
  senderName = "Rahul Sharma",
  recipientName = "Priya Mehta",
  recipientCompany = "Infosys",
  antiSpamScore,
  className,
}: MessagePreviewProps) {
  const config = channelConfig[channel];
  const Icon = config.icon;

  const vars = {
    first_name: recipientName.split(" ")[0],
    full_name: recipientName,
    company: recipientCompany,
    sender_name: senderName,
  };

  const interpolatedSubject = subject ? interpolate(subject, vars) : "";
  const interpolatedBody = interpolate(body, vars);

  const spamColor =
    antiSpamScore === undefined
      ? null
      : antiSpamScore >= 80
      ? "text-success-600"
      : antiSpamScore >= 60
      ? "text-warning-600"
      : "text-danger-600";

  return (
    <div className={cn("space-y-3", className)}>
      {/* Channel header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-md",
              config.bg
            )}
          >
            <Icon className={cn("h-4 w-4", config.color)} />
          </div>
          <span className="text-sm font-medium text-foreground">
            {config.label}
          </span>
        </div>
        {antiSpamScore !== undefined && (
          <div className="flex items-center gap-1.5">
            <Shield className={cn("h-4 w-4", spamColor)} />
            <span className={cn("text-xs font-semibold", spamColor)}>
              Anti-spam: {antiSpamScore}/100
            </span>
            {antiSpamScore >= 80 ? (
              <CheckCircle className="h-3.5 w-3.5 text-success-500" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5 text-warning-500" />
            )}
          </div>
        )}
      </div>

      {/* Email preview */}
      {channel === "email" && (
        <div className="rounded-xl border border-border overflow-hidden bg-white dark:bg-card">
          {/* Email header */}
          <div className="bg-muted/50 px-4 py-3 border-b border-border space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <AtSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground text-xs w-10 flex-shrink-0">
                From
              </span>
              <span className="text-foreground text-xs font-medium">
                {senderName} &lt;recruiter@recruitai.in&gt;
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground text-xs w-10 flex-shrink-0">
                To
              </span>
              <span className="text-foreground text-xs font-medium">
                {recipientName} &lt;hr@{recipientCompany.toLowerCase()}.com&gt;
              </span>
            </div>
            {interpolatedSubject && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground text-xs w-14 flex-shrink-0">
                  Subject
                </span>
                <span className="text-foreground text-xs font-semibold">
                  {interpolatedSubject}
                </span>
              </div>
            )}
          </div>

          {/* Email body */}
          <div className="p-5">
            <div
              className="text-sm text-foreground leading-relaxed whitespace-pre-wrap prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{
                __html: interpolatedBody
                  .replace(/\n\n/g, "<br/><br/>")
                  .replace(/\n/g, "<br/>"),
              }}
            />
          </div>

          {/* Email footer */}
          <div className="px-5 py-3 bg-muted/30 border-t border-border">
            <p className="text-xs text-muted-foreground">
              {senderName} · RecruitAI Platform ·{" "}
              <span className="underline cursor-pointer">Unsubscribe</span>
            </p>
          </div>
        </div>
      )}

      {/* LinkedIn/WhatsApp/Telegram preview */}
      {channel !== "email" && (
        <div className="rounded-xl border border-border overflow-hidden">
          {/* Platform header */}
          <div
            className={cn(
              "px-4 py-2 border-b border-border flex items-center gap-2",
              config.bg
            )}
          >
            <div
              className={cn(
                "h-7 w-7 rounded-full flex items-center justify-center bg-white text-xs font-bold",
                config.color
              )}
            >
              {senderName.charAt(0)}
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">{senderName}</p>
              <p className={cn("text-xs", config.color)}>via RecruitAI</p>
            </div>
          </div>

          {/* Message bubble */}
          <div className="p-4 bg-white dark:bg-card">
            <div
              className={cn(
                "rounded-xl p-3 max-w-sm ml-auto text-sm leading-relaxed whitespace-pre-wrap",
                channel === "linkedin" && "bg-sky-50 text-sky-900",
                channel === "whatsapp" && "bg-green-50 text-green-900",
                channel === "telegram" && "bg-indigo-50 text-indigo-900"
              )}
            >
              {interpolatedBody}
            </div>
            <p className="text-xs text-muted-foreground text-right mt-1">
              Now · {senderName}
            </p>
          </div>
        </div>
      )}

      {/* Variable legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(vars).map(([key, value]) => (
          <div key={key} className="flex items-center gap-1 text-xs">
            <Badge variant="ghost" className="font-mono text-xs py-0">
              {`{{${key}}}`}
            </Badge>
            <span className="text-muted-foreground">→ {value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
