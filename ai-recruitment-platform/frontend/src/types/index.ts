// ============================================================
// EMPLOYER TYPES
// ============================================================

export type Industry =
  | "IT Services"
  | "BFSI"
  | "Product"
  | "GCC"
  | "Startup"
  | "HealthIT"
  | "EdTech"
  | "FinTech"
  | "Ecommerce"
  | "Telecom"
  | "AIML"
  | "Manufacturing"
  | "Consulting"
  | "Other";

export type Region =
  | "India"
  | "USA"
  | "Canada"
  | "UK"
  | "Europe"
  | "Singapore"
  | "Australia"
  | "UAE"
  | "APAC"
  | "LATAM";

export type CompanySize =
  | "1-50"
  | "51-200"
  | "201-500"
  | "501-1000"
  | "1001-5000"
  | "5000+";

export type EmployerStatus =
  | "prospecting"
  | "contacted"
  | "interested"
  | "vendor_registered"
  | "active"
  | "closed_won"
  | "closed_lost"
  | "dormant";

export interface ScoreBreakdown {
  hiring_velocity: number;
  vendor_friendliness: number;
  payment_reliability: number;
  job_quality: number;
  response_rate: number;
  placement_success: number;
}

export interface Employer {
  id: string;
  name: string;
  domain: string;
  logo_url?: string;
  industry: Industry;
  sub_industry?: string;
  region: Region;
  country: string;
  city?: string;
  company_size: CompanySize;
  website?: string;
  linkedin_url?: string;
  description?: string;
  score: number;
  score_breakdown: ScoreBreakdown;
  vendor_friendly: boolean;
  contract_types: ("contract" | "c2h" | "permanent")[];
  active_jobs_count: number;
  contacts_count: number;
  status: EmployerStatus;
  last_activity?: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  notes?: string;
  expected_monthly_revenue?: number;
  probability?: number;
  assigned_recruiter?: string;
}

export interface HiringContact {
  id: string;
  employer_id: string;
  name: string;
  title: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  is_decision_maker: boolean;
  last_contacted?: string;
  response_rate?: number;
  notes?: string;
  created_at: string;
}

export interface JobPosting {
  id: string;
  employer_id: string;
  employer_name: string;
  title: string;
  description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  experience_min: number;
  experience_max: number;
  location: string;
  work_type: "remote" | "hybrid" | "onsite";
  salary_min?: number;
  salary_max?: number;
  currency: "INR" | "USD" | "GBP" | "EUR" | "SGD" | "AUD";
  contract_type: "contract" | "c2h" | "permanent";
  status: "active" | "filled" | "closed" | "on_hold";
  posted_date: string;
  deadline?: string;
  matched_candidates_count: number;
  commission_percentage?: number;
}

// ============================================================
// CANDIDATE TYPES
// ============================================================

export type SkillLevel = "beginner" | "intermediate" | "advanced" | "expert";
export type AvailabilityStatus =
  | "available"
  | "actively_looking"
  | "open_to_offers"
  | "not_available";
export type WorkPreference = "remote" | "hybrid" | "onsite" | "any";

export interface Skill {
  name: string;
  level: SkillLevel;
  years: number;
  verified: boolean;
}

export interface WorkExperience {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date?: string;
  is_current: boolean;
  description?: string;
  skills_used: string[];
  location: string;
}

export interface Education {
  id: string;
  institution: string;
  degree: string;
  field: string;
  start_year: number;
  end_year?: number;
  grade?: string;
}

export interface JobMatch {
  job_id: string;
  job_title: string;
  employer_name: string;
  employer_id: string;
  match_score: number;
  skill_match_pct: number;
  experience_match: boolean;
  location_match: boolean;
  salary_match: boolean;
  matched_skills: string[];
  missing_skills: string[];
}

export interface SkillTaxonomy {
  category: string;
  skills: string[];
}

export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone?: string;
  location: string;
  title: string;
  summary?: string;
  skills: Skill[];
  experience_years: number;
  work_history: WorkExperience[];
  education: Education[];
  availability: AvailabilityStatus;
  work_preference: WorkPreference;
  notice_period_days?: number;
  expected_salary_min?: number;
  expected_salary_max?: number;
  current_salary?: number;
  currency: "INR" | "USD" | "GBP" | "EUR";
  linkedin_url?: string;
  github_url?: string;
  portfolio_url?: string;
  resume_url?: string;
  resume_parsed_at?: string;
  top_job_matches?: JobMatch[];
  match_score?: number;
  created_at: string;
  updated_at: string;
  tags: string[];
  notes?: string;
}

// ============================================================
// OUTREACH TYPES
// ============================================================

export type CampaignStatus =
  | "draft"
  | "active"
  | "paused"
  | "completed"
  | "failed";
export type OutreachChannel = "email" | "linkedin" | "whatsapp" | "telegram";
export type MessageStatus =
  | "pending"
  | "sent"
  | "delivered"
  | "opened"
  | "clicked"
  | "replied"
  | "bounced"
  | "unsubscribed";

export interface CampaignTargetAudience {
  industries: Industry[];
  regions: Region[];
  company_sizes: CompanySize[];
  roles: string[];
  min_score?: number;
  vendor_friendly_only: boolean;
  tags: string[];
}

export interface FollowUpSequence {
  delay_days: number;
  message_template: string;
  subject?: string;
}

export interface OutreachCampaign {
  id: string;
  name: string;
  description?: string;
  status: CampaignStatus;
  channel: OutreachChannel;
  target_audience: CampaignTargetAudience;
  subject?: string;
  message_template: string;
  follow_ups: FollowUpSequence[];
  send_schedule?: {
    start_date: string;
    end_date?: string;
    send_time: string;
    timezone: string;
    days_of_week: number[];
  };
  stats: {
    total_targets: number;
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
    replied: number;
    bounced: number;
    unsubscribed: number;
  };
  open_rate: number;
  reply_rate: number;
  conversion_rate: number;
  anti_spam_score?: number;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface OutreachMessage {
  id: string;
  campaign_id: string;
  employer_id: string;
  contact_id: string;
  channel: OutreachChannel;
  subject?: string;
  body: string;
  status: MessageStatus;
  sent_at?: string;
  opened_at?: string;
  replied_at?: string;
  reply_content?: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  channel: OutreachChannel;
  industry?: Industry;
  use_case: string;
  open_rate?: number;
  reply_rate?: number;
  usage_count: number;
  tags: string[];
  created_at: string;
}

// ============================================================
// CRM TYPES
// ============================================================

export type PipelineStage =
  | "prospecting"
  | "contacted"
  | "interested"
  | "vendor_registered"
  | "active"
  | "closed_won";

export interface CRMPipeline {
  stages: {
    stage: PipelineStage;
    label: string;
    employers: CRMDeal[];
    total_value: number;
  }[];
  total_pipeline_value: number;
  weighted_pipeline_value: number;
}

export interface CRMDeal {
  id: string;
  employer_id: string;
  employer_name: string;
  company_logo?: string;
  industry: Industry;
  stage: PipelineStage;
  expected_monthly_revenue: number;
  probability: number;
  assigned_recruiter: string;
  last_activity: string;
  next_action?: string;
  next_action_date?: string;
  created_at: string;
  days_in_stage: number;
}

export interface CandidateSubmission {
  id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_title: string;
  job_id: string;
  job_title: string;
  employer_id: string;
  employer_name: string;
  status:
    | "submitted"
    | "under_review"
    | "interview_scheduled"
    | "interview_done"
    | "selected"
    | "rejected"
    | "on_hold";
  submitted_at: string;
  last_updated: string;
  match_score: number;
  feedback?: string;
  interview_date?: string;
  offer_amount?: number;
  notes?: string;
}

export interface Placement {
  id: string;
  submission_id: string;
  candidate_id: string;
  candidate_name: string;
  job_id: string;
  job_title: string;
  employer_id: string;
  employer_name: string;
  start_date: string;
  end_date?: string;
  contract_type: "contract" | "c2h" | "permanent";
  billing_rate?: number;
  salary?: number;
  currency: string;
  commission_percentage: number;
  commission_amount: number;
  commission_status: "pending" | "invoiced" | "partial" | "paid";
  placed_by: string;
  created_at: string;
}

// ============================================================
// ANALYTICS TYPES
// ============================================================

export interface RevenueData {
  month: string;
  revenue: number;
  placements: number;
  target: number;
  currency: string;
}

export interface OutreachPerformanceData {
  channel: OutreachChannel;
  sent: number;
  opened: number;
  replied: number;
  converted: number;
}

export interface FunnelData {
  stage: string;
  count: number;
  value: number;
}

export interface AIRecommendation {
  id: string;
  type:
    | "outreach"
    | "employer"
    | "candidate"
    | "campaign"
    | "template"
    | "timing";
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  action_label: string;
  action_url?: string;
  impact_score: number;
  created_at: string;
}

export interface AnalyticsDashboard {
  period: string;
  kpis: {
    total_employers: number;
    total_employers_change: number;
    active_campaigns: number;
    active_campaigns_change: number;
    placements_mtd: number;
    placements_mtd_change: number;
    revenue_mtd: number;
    revenue_mtd_change: number;
    pipeline_value: number;
    pipeline_value_change: number;
    outreach_sent: number;
    open_rate: number;
    reply_rate: number;
    conversion_rate: number;
  };
  revenue_trend: RevenueData[];
  outreach_performance: OutreachPerformanceData[];
  employer_funnel: FunnelData[];
  revenue_by_industry: { industry: Industry; revenue: number }[];
  top_templates: EmailTemplate[];
  recent_activity: ActivityItem[];
  ai_recommendations: AIRecommendation[];
}

export interface ActivityItem {
  id: string;
  type:
    | "employer_added"
    | "campaign_launched"
    | "reply_received"
    | "candidate_matched"
    | "placement_made"
    | "commission_received"
    | "note_added";
  title: string;
  description: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
  user?: string;
}

// ============================================================
// AUTH / USER TYPES
// ============================================================

export type UserRole = "admin" | "recruiter" | "manager" | "viewer";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatar_url?: string;
  team?: string;
  phone?: string;
  timezone: string;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// ============================================================
// SETTINGS TYPES
// ============================================================

export interface Integration {
  id: string;
  name: string;
  provider:
    | "apollo"
    | "hunter"
    | "linkedin"
    | "gmail"
    | "whatsapp"
    | "telegram";
  enabled: boolean;
  api_key?: string;
  connected_at?: string;
  last_sync?: string;
  status: "connected" | "disconnected" | "error" | "pending";
}

export interface AISettings {
  preferred_llm: "gpt-4o" | "claude-3-5-sonnet" | "gemini-pro";
  outreach_style: "formal" | "casual" | "mixed";
  target_regions: Region[];
  target_industries: Industry[];
  auto_discover: boolean;
  auto_score: boolean;
  message_tone: string;
}

export interface CommissionSettings {
  default_percentage: number;
  payment_terms_days: number;
  currency: string;
  tax_rate?: number;
}

export interface NotificationSettings {
  email_on_reply: boolean;
  email_on_placement: boolean;
  email_weekly_report: boolean;
  telegram_on_reply: boolean;
  telegram_on_placement: boolean;
  telegram_daily_summary: boolean;
}

export interface UserSettings {
  profile: User;
  integrations: Integration[];
  ai_settings: AISettings;
  commission: CommissionSettings;
  notifications: NotificationSettings;
}

// ============================================================
// PAGINATION
// ============================================================

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface FilterParams {
  page?: number;
  per_page?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  [key: string]: unknown;
}
