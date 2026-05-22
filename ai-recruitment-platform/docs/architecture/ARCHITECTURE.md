# AI Recruitment Sourcing Platform — Architecture

## Overview

A production-ready, cloud-native, event-driven AI recruitment business development platform
targeting Indian and global hiring markets.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL CLIENTS                                   │
│   Browser (Next.js)  │  Mobile App  │  Telegram Bot  │  WhatsApp Business   │
└──────────────────────┴──────────────┴────────────────┴──────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │   Nginx / ALB    │
                              │  (TLS, Rate Lim) │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │   API Gateway    │
                              │  JWT Auth, RBAC  │
                              │   :8000          │
                              └────────┬────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │              │               │              │                │
   ┌────┴────┐  ┌──────┴─────┐  ┌─────┴──────┐ ┌───┴──────┐  ┌─────┴────┐
   │Employer │  │ Recruiter  │  │ Outreach   │ │Candidate │  │  CRM     │
   │Discovery│  │Intelligence│  │  Engine    │ │Matching  │  │ Service  │
   │ :8001   │  │  :8002     │  │  :8003     │ │ :8004    │  │ :8005    │
   └────┬────┘  └──────┬─────┘  └─────┬──────┘ └───┬──────┘  └─────┬────┘
        │              │               │              │                │
        └──────────────┴───────────────┴──────────────┴────────────────┘
                                       │
                         ┌─────────────┴──────────────┐
                         │       Analytics Service      │
                         │           :8006              │
                         └─────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │              │               │              │                │
  ┌─────┴────┐  ┌──────┴─────┐  ┌─────┴──────┐ ┌───┴──────┐  ┌─────┴────┐
  │PostgreSQL│  │  MongoDB   │  │   Redis    │ │  Kafka   │  │Elastic-  │
  │(Relational│  │(Documents) │  │(Cache/PubS)│ │(Events)  │  │ search   │
  └─────┬────┘  └────────────┘  └────────────┘ └─────┬────┘  └──────────┘
        │                                              │
  ┌─────┴────┐                                  ┌─────┴────┐
  │ Pinecone │                                  │  Kafka   │
  │(Vectors) │                                  │  Topics  │
  └──────────┘                                  └──────────┘
```

## Microservices

| Service | Port | Responsibility |
|---------|------|----------------|
| API Gateway | 8000 | Auth, rate limiting, routing |
| Employer Discovery | 8001 | Scraping, company classification, scoring |
| Recruiter Intelligence | 8002 | Contact enrichment, Apollo/Hunter/LinkedIn |
| Outreach Engine | 8003 | AI email/LinkedIn/WhatsApp generation, campaigns |
| Candidate Matching | 8004 | Resume parsing, vector matching, scoring |
| CRM Service | 8005 | Pipeline, submissions, placements, commissions |
| Analytics Service | 8006 | Metrics, reports, AI recommendations |

## AI Agents (LangGraph)

```
                    ┌─────────────────────┐
                    │   Orchestrator       │
                    │   (LangGraph Master) │
                    └──────────┬──────────┘
                               │
     ┌─────────────────────────┼─────────────────────────┐
     │          │              │              │            │
┌────┴────┐ ┌───┴───┐  ┌──────┴──────┐ ┌────┴────┐ ┌────┴────┐
│Employer │ │Recruiter│ │  Candidate  │ │  Lead   │ │  Email  │
│Discovery│ │Outreach │ │  Matching   │ │ Qualify │ │ Automate│
│  Agent  │ │  Agent  │ │   Agent     │ │  Agent  │ │  Agent  │
└────┬────┘ └───┬───┘  └──────┬──────┘ └────┬────┘ └────┬────┘
     │          │              │              │            │
┌────┴────┐ ┌───┴───┐  ┌──────┴──────┐ ┌────┴────┐
│Relation.│ │Analyt.│  │  Commission │ │         │
│ Mgmt    │ │ Agent │  │  Tracking   │ │         │
│  Agent  │ │       │  │   Agent     │ │         │
└─────────┘ └───────┘  └─────────────┘ └─────────┘
```

## Kafka Event Architecture

```
Producer Services → Kafka Topics → Consumer Services

employer-discovery  → employer.discovered   → lead-qualification-agent
                    → employer.qualified    → crm-service, outreach-engine

recruiter-intel    → recruiter.found       → outreach-engine, crm-service

outreach-engine    → outreach.sent         → analytics-service
                   → outreach.replied      → crm-service, relationship-agent

candidate-matching → candidate.matched     → crm-service, analytics-service
                   → candidate.submitted   → crm-service

crm-service        → placement.confirmed  → commission-agent, analytics
                   → commission.earned    → analytics-service
```

## Database Schema Overview

### PostgreSQL (Relational)
- `users` — Auth and RBAC
- `employers` — Company profiles with vendor-friendliness scores
- `job_postings` — Job openings from all sources
- `hiring_contacts` — HR/recruiter contacts
- `recruiter_contacts` — Enriched contacts (Apollo/Hunter)
- `candidates` — Candidate profiles
- `job_matches` — Candidate-job matching scores
- `outreach_campaigns` — Campaign management
- `outreach_messages` — Individual messages sent
- `email_templates` — Reusable templates
- `employer_pipeline` — CRM stage tracking
- `candidate_submissions` — Submission records
- `placements` — Successful placements
- `activities` — Audit trail

### MongoDB (Documents)
- `resumes` — Raw resume text + parsed structured data
- `email_logs` — Full email bodies and responses
- `web_scrape_cache` — Cached scraping results
- `ai_conversation_logs` — Agent reasoning logs

### Redis (Cache / Real-time)
- Session tokens
- Rate limiting counters
- API response cache (TTL: 5-60 min)
- Real-time metrics
- Pub/Sub for live notifications

## India-Specific Features

### Supported Job Boards
- Naukri.com — Primary India job board
- Foundit (Monster India)
- Shine.com
- Cutshort.io — Tech-focused
- Instahyre — AI-powered hiring
- Hirist.tech — IT jobs
- TimesJobs
- Freshersworld — Entry level
- Apna — Blue & grey collar
- Wellfound — Startups
- IIMJobs — Management roles

### India Market Intelligence
- GCC (Global Capability Center) detection
- C2H (Contract-to-Hire) opportunity identification
- Bench sales company detection
- Staffing aggregator mapping
- Regional tech hub mapping (Bangalore, Hyderabad, Pune, Chennai, NCR, Mumbai)

## Security Architecture

```
┌─────────────────────────────────────────────────┐
│                  Security Layers                  │
├─────────────────────────────────────────────────┤
│ L1: Network    │ VPC, Security Groups, WAF, DDoS │
│ L2: Transport  │ TLS 1.3, HSTS, Certificate Mgmt │
│ L3: API        │ JWT Auth, RBAC, Rate Limiting    │
│ L4: Application│ Input Validation, SQL Injection  │
│                │ CSRF Protection, XSS Prevention  │
│ L5: Data       │ Encryption at rest (AES-256)     │
│                │ PII masking, GDPR compliance     │
│ L6: Audit      │ All actions logged, 90-day ret.  │
└─────────────────────────────────────────────────┘
```

## Scalability Strategy

### Horizontal Scaling
- All services stateless → scale independently
- K8s HPA based on CPU/memory/custom metrics
- Kafka partitioning for parallel processing
- Redis Cluster for distributed caching

### Performance Targets
- API Gateway: < 50ms p95
- Search queries: < 200ms p95
- AI generation: < 5s p95
- Batch discovery: 1000 companies/hour

## Cost Optimization

| Resource | Strategy | Savings |
|----------|-----------|---------|
| EKS Nodes | Spot instances (70%) + On-demand (30%) | ~65% |
| RDS | Multi-AZ Reserved Instance | ~40% |
| AI API | Prompt caching, response caching | ~50% |
| S3 | Intelligent tiering for old resumes | ~30% |
| Data Transfer | VPC endpoints, CDN for static | ~20% |
