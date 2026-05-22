"use client";

import React from "react";
import Link from "next/link";
import {
  MapPin,
  Clock,
  Zap,
  DollarSign,
  ExternalLink,
  Calendar,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  cn,
  formatCurrency,
  getInitials,
  truncateText,
} from "@/lib/utils";
import type { Candidate } from "@/types";

interface CandidateCardProps {
  candidate: Candidate;
  onMatch?: (candidate: Candidate) => void;
  onSubmit?: (candidate: Candidate) => void;
  selected?: boolean;
  onSelect?: (candidate: Candidate) => void;
  showMatchScore?: boolean;
}

const availabilityConfig = {
  available: { label: "Available Now", variant: "success" as const },
  actively_looking: { label: "Actively Looking", variant: "default" as const },
  open_to_offers: { label: "Open to Offers", variant: "warning" as const },
  not_available: { label: "Not Available", variant: "secondary" as const },
};

export function CandidateCard({
  candidate,
  onMatch,
  onSubmit,
  selected = false,
  onSelect,
  showMatchScore = false,
}: CandidateCardProps) {
  const avail = availabilityConfig[candidate.availability];
  const topSkills = candidate.skills.slice(0, 4);
  const remainingSkillsCount = Math.max(0, candidate.skills.length - 4);

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-card-hover",
        selected && "ring-2 ring-primary-500"
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {/* Checkbox */}
          {onSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onSelect(candidate)}
              className="mt-1 h-4 w-4 rounded border-input text-primary-600 focus:ring-primary-500"
            />
          )}

          {/* Avatar */}
          <div className="flex-shrink-0">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-sm font-bold">
              {getInitials(candidate.name)}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Link
                  href={`/candidates/${candidate.id}`}
                  className="font-semibold text-sm text-foreground hover:text-primary-600 transition-colors"
                >
                  {candidate.name}
                </Link>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                  {candidate.title}
                </p>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {showMatchScore && candidate.match_score && (
                  <div className="flex items-center gap-1 bg-primary-50 text-primary-700 rounded-full px-2 py-0.5">
                    <Zap className="h-3 w-3" />
                    <span className="text-xs font-bold">
                      {candidate.match_score}%
                    </span>
                  </div>
                )}
                <Badge variant={avail.variant} dot className="text-xs py-0 px-1.5">
                  {avail.label}
                </Badge>
              </div>
            </div>

            <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {candidate.location}
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {candidate.experience_years}y exp
              </div>
              {(candidate.expected_salary_min || candidate.current_salary) && (
                <div className="flex items-center gap-1">
                  <DollarSign className="h-3 w-3" />
                  {candidate.expected_salary_min
                    ? formatCurrency(candidate.expected_salary_min, candidate.currency, true)
                    : formatCurrency(candidate.current_salary!, candidate.currency, true)}
                  {candidate.expected_salary_max && (
                    <span>
                      {" "}-{" "}
                      {formatCurrency(candidate.expected_salary_max, candidate.currency, true)}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Skills */}
            <div className="flex flex-wrap items-center gap-1 mt-2">
              {topSkills.map((skill) => (
                <Badge
                  key={skill.name}
                  variant="ghost"
                  className={cn(
                    "text-xs py-0 px-1.5",
                    skill.level === "expert" && "bg-primary-50 text-primary-700",
                    skill.level === "advanced" && "bg-indigo-50 text-indigo-700"
                  )}
                >
                  {skill.name}
                </Badge>
              ))}
              {remainingSkillsCount > 0 && (
                <Badge variant="outline" className="text-xs py-0 px-1.5">
                  +{remainingSkillsCount}
                </Badge>
              )}
            </div>

            {/* Notice period */}
            {candidate.notice_period_days !== undefined && (
              <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                <Calendar className="h-3 w-3" />
                {candidate.notice_period_days === 0
                  ? "Immediate joiner"
                  : `${candidate.notice_period_days} days notice`}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
          <Button
            size="sm"
            variant="outline"
            className="flex-1 text-xs h-7"
            onClick={() => onMatch?.(candidate)}
          >
            <Zap className="h-3 w-3 mr-1" />
            Quick Match
          </Button>
          <Button
            size="sm"
            className="flex-1 text-xs h-7"
            onClick={() => onSubmit?.(candidate)}
          >
            Submit
          </Button>
          <Link href={`/candidates/${candidate.id}`}>
            <Button size="icon-sm" variant="ghost">
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
