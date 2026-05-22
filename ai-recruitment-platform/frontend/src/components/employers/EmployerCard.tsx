"use client";

import React from "react";
import Link from "next/link";
import {
  Building2,
  MapPin,
  Users,
  Briefcase,
  Clock,
  ExternalLink,
  CheckCircle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  cn,
  getScoreBadgeVariant,
  formatRelativeDate,
  getCompanyLogoUrl,
} from "@/lib/utils";
import type { Employer } from "@/types";

interface EmployerCardProps {
  employer: Employer;
  onStartOutreach?: (employer: Employer) => void;
  onFindCandidates?: (employer: Employer) => void;
  selected?: boolean;
  onSelect?: (employer: Employer) => void;
}

export function EmployerCard({
  employer,
  onStartOutreach,
  onFindCandidates,
  selected = false,
  onSelect,
}: EmployerCardProps) {
  const scoreVariant = getScoreBadgeVariant(employer.score);

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
              onChange={() => onSelect(employer)}
              className="mt-1 h-4 w-4 rounded border-input text-primary-600 focus:ring-primary-500"
            />
          )}

          {/* Logo */}
          <div className="flex-shrink-0">
            <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center overflow-hidden border border-border">
              {employer.domain ? (
                <img
                  src={getCompanyLogoUrl(employer.domain)}
                  alt={employer.name}
                  className="h-8 w-8 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove("hidden");
                  }}
                />
              ) : null}
              <Building2 className="h-5 w-5 text-muted-foreground hidden" />
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Link
                  href={`/employers/${employer.id}`}
                  className="font-semibold text-sm text-foreground hover:text-primary-600 transition-colors line-clamp-1"
                >
                  {employer.name}
                </Link>
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge variant="ghost" className="text-xs py-0 px-1.5">
                    {employer.industry}
                  </Badge>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {employer.city || employer.region}
                  </div>
                </div>
              </div>

              <Badge variant={scoreVariant} className="flex-shrink-0 font-bold text-xs">
                {employer.score}
              </Badge>
            </div>

            <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Users className="h-3 w-3" />
                {employer.contacts_count} contacts
              </div>
              <div className="flex items-center gap-1">
                <Briefcase className="h-3 w-3" />
                {employer.active_jobs_count} jobs
              </div>
              {employer.vendor_friendly && (
                <div className="flex items-center gap-1 text-success-600">
                  <CheckCircle className="h-3 w-3" />
                  Vendor friendly
                </div>
              )}
            </div>

            {employer.contract_types.length > 0 && (
              <div className="flex items-center gap-1.5 mt-2">
                {employer.contract_types.map((type) => (
                  <Badge
                    key={type}
                    variant="outline"
                    className="text-xs py-0 px-1.5 capitalize"
                  >
                    {type.replace("_", " ")}
                  </Badge>
                ))}
              </div>
            )}

            {employer.last_activity && (
              <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatRelativeDate(employer.last_activity)}
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
            onClick={() => onStartOutreach?.(employer)}
          >
            Start Outreach
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="flex-1 text-xs h-7"
            onClick={() => onFindCandidates?.(employer)}
          >
            Find Candidates
          </Button>
          <Link href={`/employers/${employer.id}`}>
            <Button size="icon-sm" variant="ghost">
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
