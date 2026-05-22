# API Contracts — AI Recruitment Platform

Base URL: `https://api.recruitai.io/api/v1`

All endpoints require `Authorization: Bearer <jwt_token>` unless noted.

---

## Authentication

### POST /auth/login
```json
Request:  { "email": "string", "password": "string" }
Response: { "access_token": "string", "refresh_token": "string", "token_type": "bearer", "expires_in": 1800 }
```

### POST /auth/refresh
```json
Request:  { "refresh_token": "string" }
Response: { "access_token": "string", "expires_in": 1800 }
```

---

## Employer Discovery

### POST /employers/discover
Trigger AI discovery job.
```json
Request: {
  "regions": ["India", "USA"],
  "industries": ["IT Services", "GCC", "FinTech"],
  "roles": ["Java Developer", "AI Engineer"],
  "limit": 100
}
Response: { "job_id": "uuid", "status": "queued", "estimated_time_seconds": 120 }
```

### GET /employers
List employers with filters.
```
Query params: industry, region, vendor_friendly, min_score, max_score, page, limit, sort_by
Response: { "items": [Employer], "total": int, "page": int, "limit": int }
```

### GET /employers/{id}
```json
Response: {
  "id": "uuid", "name": "string", "industry": "string", "size": "string",
  "country": "string", "region": "string", "website": "string",
  "linkedin_url": "string", "is_vendor_friendly": bool, "accepts_contract": bool,
  "accepts_c2h": bool, "hiring_volume": int, "score": float,
  "score_breakdown": { "vendor_friendliness": 85, "hiring_frequency": 70, ... },
  "status": "string", "contacts_count": int
}
```

### POST /employers/{id}/score
Trigger AI re-scoring.
```json
Response: { "score": float, "score_breakdown": object, "scored_at": "datetime" }
```

---

## Recruiter Intelligence

### POST /recruiters/enrich
Enrich a contact via Apollo/Hunter/Clearbit.
```json
Request: { "name": "string", "company": "string", "email": "string?" }
Response: {
  "email": "string", "verified": bool, "linkedin_url": "string",
  "phone": "string", "title": "string", "enrichment_source": "apollo|hunter|clearbit"
}
```

### GET /recruiters
List contacts with filters.

### POST /recruiters/{id}/outreach-sequence
Start an outreach sequence.
```json
Request: { "campaign_id": "uuid", "sequence_template": "cold|partnership|submission" }
Response: { "sequence_id": "uuid", "first_message_scheduled": "datetime" }
```

---

## Outreach Engine

### POST /outreach/generate
AI-generate a personalized message.
```json
Request: {
  "contact": { "name": "string", "title": "string", "company": "string" },
  "channel": "email|linkedin|whatsapp",
  "purpose": "cold_outreach|partnership|candidate_submission|followup",
  "context": {
    "job_description": "string?",
    "candidate_summary": "string?",
    "previous_message": "string?"
  }
}
Response: {
  "subject": "string",
  "body": "string",
  "personalization_tokens": ["string"],
  "spam_score": float,
  "estimated_response_rate": float
}
```

### POST /outreach/campaigns
Create outreach campaign.
```json
Request: {
  "name": "string",
  "target_industry": "string",
  "target_region": "string",
  "target_role": "string",
  "sequence_steps": [
    { "day": 0, "channel": "email", "template_id": "uuid" },
    { "day": 3, "channel": "linkedin", "template_id": "uuid" },
    { "day": 7, "channel": "email", "template_id": "uuid" }
  ]
}
Response: { "campaign_id": "uuid", "status": "draft" }
```

---

## Candidate Matching

### POST /candidates/parse-resume
Parse resume and extract structured data.
```json
Request: multipart/form-data with file field "resume"
Response: {
  "candidate_id": "uuid",
  "name": "string", "email": "string", "phone": "string",
  "skills": ["Java", "Spring Boot", "AWS"],
  "years_experience": 5,
  "current_title": "string",
  "education": [{ "degree": "string", "institution": "string", "year": int }],
  "match_ready": true
}
```

### POST /candidates/{id}/match-jobs
Find matching jobs.
```json
Response: {
  "matches": [
    {
      "job_id": "uuid", "employer": "string", "title": "string",
      "overall_score": 87.5,
      "score_breakdown": {
        "skills": 90, "experience": 85, "location": 100, "salary": 75
      },
      "matched_skills": ["Java", "Spring Boot"],
      "missing_skills": ["Kafka"],
      "recruiter_summary": "Strong candidate for this role..."
    }
  ]
}
```

---

## CRM

### GET /crm/pipeline
Get employer pipeline by stage.
```json
Response: {
  "stages": {
    "prospecting": [{ "employer_id": "uuid", "company": "string", ... }],
    "contacted": [...],
    "interested": [...],
    "vendor_registered": [...],
    "active": [...],
    "closed_won": [...]
  },
  "total_pipeline_value": 250000.00
}
```

### POST /crm/submissions
Submit candidate to employer.
```json
Request: {
  "candidate_id": "uuid",
  "job_posting_id": "uuid",
  "employer_id": "uuid",
  "submission_notes": "string"
}
Response: { "submission_id": "uuid", "status": "submitted" }
```

### POST /crm/placements
Record a successful placement.
```json
Request: {
  "candidate_id": "uuid", "employer_id": "uuid", "job_title": "string",
  "start_date": "date", "employment_type": "permanent|contract|c2h",
  "salary": 1800000, "commission_percentage": 8.33
}
Response: {
  "placement_id": "uuid",
  "commission_amount": 149940.00,
  "invoice_status": "pending"
}
```

---

## Analytics

### GET /analytics/dashboard
Main dashboard data.
```json
Response: {
  "kpis": {
    "total_employers": 1250,
    "active_campaigns": 8,
    "placements_mtd": 3,
    "revenue_mtd": 450000.00,
    "pipeline_value": 2500000.00
  },
  "revenue_trend": [{ "month": "2025-01", "revenue": 380000 }],
  "outreach_performance": { "sent": 450, "opened": 180, "replied": 45 },
  "top_templates": [{ "id": "uuid", "name": "string", "reply_rate": 0.18 }],
  "ai_recommendations": [{ "type": "string", "title": "string", "priority": "high" }]
}
```

### GET /analytics/salary-intelligence
```
Query: role=Java+Developer&location=Bangalore&yoe_min=3&yoe_max=6
Response: { "min": 900000, "median": 1400000, "max": 2200000, "currency": "INR", "source_count": 127 }
```

---

## WebSocket Events (Real-time)

Connect: `wss://api.recruitai.io/ws?token=<jwt>`

Events:
```json
{ "type": "employer_discovered", "data": { "employer_id": "uuid", "name": "string" } }
{ "type": "outreach_replied", "data": { "message_id": "uuid", "contact": "string" } }
{ "type": "candidate_matched", "data": { "candidate_id": "uuid", "score": 87 } }
{ "type": "placement_confirmed", "data": { "placement_id": "uuid", "commission": 149940 } }
{ "type": "ai_recommendation", "data": { "type": "string", "message": "string" } }
```
