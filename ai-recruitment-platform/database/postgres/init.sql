-- =============================================================================
-- AI Recruitment Platform — PostgreSQL Initialization Script
-- =============================================================================
-- Run with: psql -U postgres -f init.sql
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM types
-- =============================================================================
CREATE TYPE user_role AS ENUM ('admin', 'recruiter', 'viewer');
CREATE TYPE employer_status AS ENUM ('active', 'inactive', 'blacklisted', 'pending_review');
CREATE TYPE employer_size AS ENUM ('1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001-10000', '10000+');
CREATE TYPE job_status AS ENUM ('draft', 'active', 'paused', 'closed', 'filled');
CREATE TYPE job_type AS ENUM ('full_time', 'part_time', 'contract', 'c2h', 'freelance', 'internship');
CREATE TYPE work_mode AS ENUM ('remote', 'onsite', 'hybrid');
CREATE TYPE candidate_status AS ENUM ('active', 'passive', 'not_looking', 'placed', 'blacklisted');
CREATE TYPE outreach_status AS ENUM ('draft', 'scheduled', 'sent', 'failed', 'bounced');
CREATE TYPE campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'archived');
CREATE TYPE placement_status AS ENUM ('in_progress', 'offered', 'accepted', 'joined', 'fallen_through', 'cancelled');
CREATE TYPE pipeline_stage AS ENUM ('lead', 'contacted', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost');
CREATE TYPE activity_type AS ENUM ('call', 'email', 'meeting', 'note', 'task', 'linkedin', 'whatsapp', 'sms');
CREATE TYPE channel AS ENUM ('email', 'linkedin', 'whatsapp', 'sms', 'telegram', 'phone');
CREATE TYPE match_status AS ENUM ('pending', 'shortlisted', 'submitted', 'rejected', 'interviewing', 'offered', 'placed');

-- =============================================================================
-- USERS & AUTH
-- =============================================================================
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email             VARCHAR(255) UNIQUE NOT NULL,
    hashed_password   VARCHAR(255) NOT NULL,
    role              user_role NOT NULL DEFAULT 'recruiter',
    full_name         VARCHAR(255) NOT NULL,
    phone             VARCHAR(20),
    avatar_url        TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified       BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at     TIMESTAMP WITH TIME ZONE,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP WITH TIME ZONE,
    email_verify_token VARCHAR(255),
    preferences       JSONB DEFAULT '{}',
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- =============================================================================
-- SKILLS TAXONOMY
-- =============================================================================
CREATE TABLE skill_categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE skills (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) UNIQUE NOT NULL,
    slug        VARCHAR(150) UNIQUE NOT NULL,
    category_id INTEGER REFERENCES skill_categories(id) ON DELETE SET NULL,
    aliases     TEXT[],
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_skills_name ON skills USING gin(name gin_trgm_ops);
CREATE INDEX idx_skills_category ON skills(category_id);

-- =============================================================================
-- EMPLOYERS
-- =============================================================================
CREATE TABLE employers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    legal_name          VARCHAR(255),
    industry            VARCHAR(100),
    sub_industry        VARCHAR(100),
    size                employer_size,
    country             VARCHAR(100) DEFAULT 'India',
    region              VARCHAR(100),
    city                VARCHAR(100),
    address             TEXT,
    website             VARCHAR(500),
    linkedin_url        VARCHAR(500),
    glassdoor_url       VARCHAR(500),
    crunchbase_url      VARCHAR(500),
    description         TEXT,
    tech_stack          TEXT[],
    is_vendor_friendly  BOOLEAN DEFAULT FALSE,
    accepts_contract    BOOLEAN DEFAULT FALSE,
    accepts_c2h         BOOLEAN DEFAULT FALSE,
    accepts_freelance   BOOLEAN DEFAULT FALSE,
    hiring_volume       INTEGER DEFAULT 0,  -- estimated annual hires
    avg_time_to_hire    INTEGER,             -- days
    score               FLOAT DEFAULT 0.0,  -- AI-computed relationship score
    status              employer_status NOT NULL DEFAULT 'active',
    source              VARCHAR(100),        -- apollo, clearbit, manual, linkedin
    external_id         VARCHAR(255),        -- ID in source system
    tags                TEXT[],
    notes               TEXT,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employers_name ON employers USING gin(name gin_trgm_ops);
CREATE INDEX idx_employers_industry ON employers(industry);
CREATE INDEX idx_employers_country_region ON employers(country, region);
CREATE INDEX idx_employers_status ON employers(status);
CREATE INDEX idx_employers_is_vendor_friendly ON employers(is_vendor_friendly);
CREATE INDEX idx_employers_accepts_contract ON employers(accepts_contract);
CREATE INDEX idx_employers_score ON employers(score DESC);
CREATE INDEX idx_employers_tech_stack ON employers USING gin(tech_stack);
CREATE INDEX idx_employers_created_at ON employers(created_at DESC);

-- =============================================================================
-- HIRING CONTACTS (Contacts at employer companies)
-- =============================================================================
CREATE TABLE hiring_contacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id     UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    full_name       VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    title           VARCHAR(255),
    department      VARCHAR(100),
    email           VARCHAR(255),
    work_email      VARCHAR(255),
    phone           VARCHAR(30),
    linkedin_url    VARCHAR(500),
    location        VARCHAR(150),
    seniority       VARCHAR(50),    -- C-Level, VP, Director, Manager
    is_decision_maker BOOLEAN DEFAULT FALSE,
    is_verified     BOOLEAN DEFAULT FALSE,
    last_contacted_at TIMESTAMP WITH TIME ZONE,
    contact_count   INTEGER DEFAULT 0,
    response_rate   FLOAT DEFAULT 0.0,
    source          VARCHAR(100),
    external_id     VARCHAR(255),
    tags            TEXT[],
    notes           TEXT,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hiring_contacts_employer ON hiring_contacts(employer_id);
CREATE INDEX idx_hiring_contacts_email ON hiring_contacts(email);
CREATE INDEX idx_hiring_contacts_is_decision_maker ON hiring_contacts(is_decision_maker);
CREATE INDEX idx_hiring_contacts_name ON hiring_contacts USING gin(full_name gin_trgm_ops);

-- =============================================================================
-- RECRUITER CONTACTS (Vendors / Agency recruiters we work with)
-- =============================================================================
CREATE TABLE recruiter_contacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agency_name     VARCHAR(255),
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    phone           VARCHAR(30),
    linkedin_url    VARCHAR(500),
    whatsapp        VARCHAR(30),
    specializations TEXT[],
    regions         TEXT[],
    tier            INTEGER DEFAULT 3 CHECK (tier BETWEEN 1 AND 5),  -- 1=top, 5=lowest
    score           FLOAT DEFAULT 0.0,
    placements_count INTEGER DEFAULT 0,
    submission_count INTEGER DEFAULT 0,
    avg_quality_score FLOAT DEFAULT 0.0,
    is_active       BOOLEAN DEFAULT TRUE,
    notes           TEXT,
    tags            TEXT[],
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recruiter_contacts_agency ON recruiter_contacts(agency_name);
CREATE INDEX idx_recruiter_contacts_tier ON recruiter_contacts(tier);
CREATE INDEX idx_recruiter_contacts_specializations ON recruiter_contacts USING gin(specializations);

-- =============================================================================
-- JOB POSTINGS
-- =============================================================================
CREATE TABLE job_postings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id         UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    hiring_contact_id   UUID REFERENCES hiring_contacts(id) ON DELETE SET NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    requirements        TEXT,
    responsibilities    TEXT,
    required_skills     TEXT[],
    nice_to_have_skills TEXT[],
    experience_min      INTEGER,    -- years
    experience_max      INTEGER,
    salary_min          NUMERIC(12,2),
    salary_max          NUMERIC(12,2),
    salary_currency     VARCHAR(10) DEFAULT 'INR',
    job_type            job_type NOT NULL DEFAULT 'full_time',
    work_mode           work_mode NOT NULL DEFAULT 'hybrid',
    location            VARCHAR(255),
    openings            INTEGER DEFAULT 1,
    status              job_status NOT NULL DEFAULT 'active',
    external_job_id     VARCHAR(255),
    source_url          TEXT,
    budget_per_placement NUMERIC(12,2),
    commission_rate     FLOAT,
    priority            INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    deadline            DATE,
    tags                TEXT[],
    ai_summary          TEXT,
    embedding_id        VARCHAR(255),
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_postings_employer ON job_postings(employer_id);
CREATE INDEX idx_job_postings_status ON job_postings(status);
CREATE INDEX idx_job_postings_required_skills ON job_postings USING gin(required_skills);
CREATE INDEX idx_job_postings_work_mode ON job_postings(work_mode);
CREATE INDEX idx_job_postings_job_type ON job_postings(job_type);
CREATE INDEX idx_job_postings_created_at ON job_postings(created_at DESC);
CREATE INDEX idx_job_postings_title ON job_postings USING gin(title gin_trgm_ops);

-- =============================================================================
-- CANDIDATES
-- =============================================================================
CREATE TABLE candidates (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name           VARCHAR(255) NOT NULL,
    email               VARCHAR(255),
    phone               VARCHAR(30),
    whatsapp            VARCHAR(30),
    linkedin_url        VARCHAR(500),
    github_url          VARCHAR(500),
    portfolio_url       VARCHAR(500),
    location            VARCHAR(150),
    current_company     VARCHAR(255),
    current_title       VARCHAR(255),
    notice_period_days  INTEGER,
    total_experience    FLOAT,      -- years
    skills              TEXT[],
    tech_stack          TEXT[],
    preferred_roles     TEXT[],
    preferred_locations TEXT[],
    preferred_work_mode work_mode,
    expected_salary_min NUMERIC(12,2),
    expected_salary_max NUMERIC(12,2),
    salary_currency     VARCHAR(10) DEFAULT 'INR',
    status              candidate_status NOT NULL DEFAULT 'active',
    source              VARCHAR(100),
    external_id         VARCHAR(255),
    resume_mongo_id     VARCHAR(100),  -- MongoDB ObjectId
    embedding_id        VARCHAR(255),
    score               FLOAT DEFAULT 0.0,
    tags                TEXT[],
    notes               TEXT,
    is_do_not_contact   BOOLEAN DEFAULT FALSE,
    gdpr_consent        BOOLEAN DEFAULT FALSE,
    gdpr_consent_date   TIMESTAMP WITH TIME ZONE,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_candidates_skills ON candidates USING gin(skills);
CREATE INDEX idx_candidates_tech_stack ON candidates USING gin(tech_stack);
CREATE INDEX idx_candidates_status ON candidates(status);
CREATE INDEX idx_candidates_location ON candidates(location);
CREATE INDEX idx_candidates_total_experience ON candidates(total_experience);
CREATE INDEX idx_candidates_name ON candidates USING gin(full_name gin_trgm_ops);
CREATE INDEX idx_candidates_created_at ON candidates(created_at DESC);

-- =============================================================================
-- JOB MATCHES
-- =============================================================================
CREATE TABLE job_matches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id              UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    candidate_id        UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    assigned_recruiter  UUID REFERENCES users(id) ON DELETE SET NULL,
    status              match_status NOT NULL DEFAULT 'pending',
    ai_score            FLOAT,          -- 0.0-1.0 AI match score
    skills_match_score  FLOAT,
    experience_match    FLOAT,
    manual_score        INTEGER,
    rejection_reason    TEXT,
    interview_rounds    INTEGER DEFAULT 0,
    interview_notes     TEXT,
    offer_amount        NUMERIC(12,2),
    offer_currency      VARCHAR(10) DEFAULT 'INR',
    joined_at           DATE,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(job_id, candidate_id)
);

CREATE INDEX idx_job_matches_job ON job_matches(job_id);
CREATE INDEX idx_job_matches_candidate ON job_matches(candidate_id);
CREATE INDEX idx_job_matches_status ON job_matches(status);
CREATE INDEX idx_job_matches_ai_score ON job_matches(ai_score DESC);
CREATE INDEX idx_job_matches_recruiter ON job_matches(assigned_recruiter);

-- =============================================================================
-- OUTREACH CAMPAIGNS
-- =============================================================================
CREATE TABLE outreach_campaigns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    target_type     VARCHAR(50) NOT NULL, -- 'employers', 'candidates', 'recruiters'
    channel         channel NOT NULL DEFAULT 'email',
    status          campaign_status NOT NULL DEFAULT 'draft',
    template_id     UUID,
    job_id          UUID REFERENCES job_postings(id) ON DELETE SET NULL,
    employer_id     UUID REFERENCES employers(id) ON DELETE SET NULL,
    ai_personalized BOOLEAN DEFAULT TRUE,
    total_targets   INTEGER DEFAULT 0,
    sent_count      INTEGER DEFAULT 0,
    open_count      INTEGER DEFAULT 0,
    reply_count     INTEGER DEFAULT 0,
    bounce_count    INTEGER DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    open_rate       FLOAT GENERATED ALWAYS AS (
        CASE WHEN sent_count > 0 THEN open_count::FLOAT / sent_count ELSE 0 END
    ) STORED,
    reply_rate      FLOAT GENERATED ALWAYS AS (
        CASE WHEN sent_count > 0 THEN reply_count::FLOAT / sent_count ELSE 0 END
    ) STORED,
    scheduled_at    TIMESTAMP WITH TIME ZONE,
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_campaigns_status ON outreach_campaigns(status);
CREATE INDEX idx_campaigns_target_type ON outreach_campaigns(target_type);
CREATE INDEX idx_campaigns_channel ON outreach_campaigns(channel);
CREATE INDEX idx_campaigns_created_by ON outreach_campaigns(created_by);
CREATE INDEX idx_campaigns_created_at ON outreach_campaigns(created_at DESC);

-- =============================================================================
-- OUTREACH MESSAGES (Individual messages in a campaign)
-- =============================================================================
CREATE TABLE outreach_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id     UUID NOT NULL REFERENCES outreach_campaigns(id) ON DELETE CASCADE,
    channel         channel NOT NULL,
    recipient_type  VARCHAR(50) NOT NULL, -- 'employer_contact', 'candidate', 'recruiter'
    recipient_id    UUID NOT NULL,
    recipient_email VARCHAR(255),
    recipient_phone VARCHAR(30),
    subject         VARCHAR(500),
    body            TEXT NOT NULL,
    status          outreach_status NOT NULL DEFAULT 'draft',
    sent_at         TIMESTAMP WITH TIME ZONE,
    opened_at       TIMESTAMP WITH TIME ZONE,
    replied_at      TIMESTAMP WITH TIME ZONE,
    bounced_at      TIMESTAMP WITH TIME ZONE,
    error_message   TEXT,
    external_id     VARCHAR(255),  -- provider message ID
    thread_id       VARCHAR(255),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_campaign ON outreach_messages(campaign_id);
CREATE INDEX idx_messages_recipient ON outreach_messages(recipient_id);
CREATE INDEX idx_messages_status ON outreach_messages(status);
CREATE INDEX idx_messages_sent_at ON outreach_messages(sent_at DESC);

-- =============================================================================
-- EMAIL TEMPLATES
-- =============================================================================
CREATE TABLE email_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) UNIQUE NOT NULL,
    category        VARCHAR(100) NOT NULL, -- 'cold_outreach', 'follow_up', 'submission', 'partnership', 'placement_update'
    channel         channel NOT NULL DEFAULT 'email',
    subject         VARCHAR(500),
    body_html       TEXT,
    body_text       TEXT,
    variables       TEXT[],  -- variable names used in template
    language        VARCHAR(10) DEFAULT 'en',
    is_ai_template  BOOLEAN DEFAULT FALSE,
    version         INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    open_rate_avg   FLOAT DEFAULT 0.0,
    reply_rate_avg  FLOAT DEFAULT 0.0,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_templates_category ON email_templates(category);
CREATE INDEX idx_templates_channel ON email_templates(channel);
CREATE INDEX idx_templates_slug ON email_templates(slug);

-- =============================================================================
-- PLACEMENTS
-- =============================================================================
CREATE TABLE placements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_match_id        UUID NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    job_id              UUID NOT NULL REFERENCES job_postings(id),
    candidate_id        UUID NOT NULL REFERENCES candidates(id),
    employer_id         UUID NOT NULL REFERENCES employers(id),
    recruiter_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    vendor_id           UUID REFERENCES recruiter_contacts(id) ON DELETE SET NULL,
    status              placement_status NOT NULL DEFAULT 'in_progress',
    offered_on          DATE,
    accepted_on         DATE,
    joining_date        DATE,
    ctc_offered         NUMERIC(12,2),
    ctc_currency        VARCHAR(10) DEFAULT 'INR',
    notice_period_days  INTEGER,
    rejection_reason    TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_placements_job ON placements(job_id);
CREATE INDEX idx_placements_candidate ON placements(candidate_id);
CREATE INDEX idx_placements_employer ON placements(employer_id);
CREATE INDEX idx_placements_recruiter ON placements(recruiter_id);
CREATE INDEX idx_placements_status ON placements(status);
CREATE INDEX idx_placements_joining_date ON placements(joining_date);

-- =============================================================================
-- COMMISSIONS
-- =============================================================================
CREATE TABLE commissions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    placement_id        UUID NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
    recruiter_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    employer_id         UUID NOT NULL REFERENCES employers(id),
    invoice_number      VARCHAR(100) UNIQUE,
    gross_amount        NUMERIC(14,2) NOT NULL,
    tax_amount          NUMERIC(14,2) DEFAULT 0,
    net_amount          NUMERIC(14,2) NOT NULL,
    currency            VARCHAR(10) DEFAULT 'INR',
    payment_terms       VARCHAR(50),  -- '30_days', '45_days', '60_days'
    due_date            DATE,
    paid_date           DATE,
    payment_status      VARCHAR(50) DEFAULT 'pending',  -- pending, invoiced, paid, overdue, waived
    payment_reference   VARCHAR(255),
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commissions_placement ON commissions(placement_id);
CREATE INDEX idx_commissions_recruiter ON commissions(recruiter_id);
CREATE INDEX idx_commissions_payment_status ON commissions(payment_status);
CREATE INDEX idx_commissions_due_date ON commissions(due_date);

-- =============================================================================
-- CRM PIPELINE
-- =============================================================================
CREATE TABLE crm_deals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id     UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    contact_id      UUID REFERENCES hiring_contacts(id) ON DELETE SET NULL,
    owner_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    stage           pipeline_stage NOT NULL DEFAULT 'lead',
    deal_value      NUMERIC(14,2),
    currency        VARCHAR(10) DEFAULT 'INR',
    expected_close  DATE,
    probability     INTEGER DEFAULT 0 CHECK (probability BETWEEN 0 AND 100),
    lost_reason     TEXT,
    tags            TEXT[],
    closed_at       TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crm_deals_employer ON crm_deals(employer_id);
CREATE INDEX idx_crm_deals_owner ON crm_deals(owner_id);
CREATE INDEX idx_crm_deals_stage ON crm_deals(stage);
CREATE INDEX idx_crm_deals_expected_close ON crm_deals(expected_close);

-- =============================================================================
-- CRM ACTIVITIES
-- =============================================================================
CREATE TABLE crm_activities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deal_id         UUID REFERENCES crm_deals(id) ON DELETE CASCADE,
    employer_id     UUID REFERENCES employers(id) ON DELETE CASCADE,
    contact_id      UUID REFERENCES hiring_contacts(id) ON DELETE SET NULL,
    candidate_id    UUID REFERENCES candidates(id) ON DELETE SET NULL,
    recruiter_id    UUID REFERENCES recruiter_contacts(id) ON DELETE SET NULL,
    performed_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    activity_type   activity_type NOT NULL,
    subject         VARCHAR(500),
    description     TEXT,
    outcome         VARCHAR(255),
    duration_minutes INTEGER,
    scheduled_at    TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    is_completed    BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activities_deal ON crm_activities(deal_id);
CREATE INDEX idx_activities_employer ON crm_activities(employer_id);
CREATE INDEX idx_activities_contact ON crm_activities(contact_id);
CREATE INDEX idx_activities_performed_by ON crm_activities(performed_by);
CREATE INDEX idx_activities_type ON crm_activities(activity_type);
CREATE INDEX idx_activities_scheduled_at ON crm_activities(scheduled_at);
CREATE INDEX idx_activities_created_at ON crm_activities(created_at DESC);

-- =============================================================================
-- ANALYTICS EVENTS
-- =============================================================================
CREATE TABLE analytics_events (
    id              BIGSERIAL PRIMARY KEY,
    event_type      VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100),
    entity_id       UUID,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    properties      JSONB DEFAULT '{}',
    timestamp       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions for current + next 3 months
CREATE TABLE analytics_events_2025_01 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE analytics_events_2025_q2 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE analytics_events_2025_q3 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE analytics_events_2025_q4 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE analytics_events_2026_q1 PARTITION OF analytics_events
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE analytics_events_2026_q2 PARTITION OF analytics_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE INDEX idx_analytics_event_type ON analytics_events(event_type, timestamp DESC);
CREATE INDEX idx_analytics_user ON analytics_events(user_id, timestamp DESC);
CREATE INDEX idx_analytics_entity ON analytics_events(entity_type, entity_id, timestamp DESC);

-- =============================================================================
-- JOB BOARDS CONFIGURATION
-- =============================================================================
CREATE TABLE job_board_configs (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    slug            VARCHAR(100) UNIQUE NOT NULL,
    base_url        VARCHAR(500),
    api_endpoint    VARCHAR(500),
    scraper_class   VARCHAR(200),
    is_active       BOOLEAN DEFAULT TRUE,
    region          VARCHAR(100) DEFAULT 'India',
    requires_auth   BOOLEAN DEFAULT FALSE,
    rate_limit_rpm  INTEGER DEFAULT 30,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- TRIGGERS: updated_at auto-update
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_employers_updated_at
    BEFORE UPDATE ON employers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_hiring_contacts_updated_at
    BEFORE UPDATE ON hiring_contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_recruiter_contacts_updated_at
    BEFORE UPDATE ON recruiter_contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_job_matches_updated_at
    BEFORE UPDATE ON job_matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON outreach_campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_messages_updated_at
    BEFORE UPDATE ON outreach_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_templates_updated_at
    BEFORE UPDATE ON email_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_placements_updated_at
    BEFORE UPDATE ON placements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_commissions_updated_at
    BEFORE UPDATE ON commissions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_crm_deals_updated_at
    BEFORE UPDATE ON crm_deals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_crm_activities_updated_at
    BEFORE UPDATE ON crm_activities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SEED DATA: Skill categories and skills
-- =============================================================================
INSERT INTO skill_categories (name, slug) VALUES
    ('Programming Languages', 'programming-languages'),
    ('Frontend Frameworks', 'frontend-frameworks'),
    ('Backend Frameworks', 'backend-frameworks'),
    ('Databases', 'databases'),
    ('Cloud & DevOps', 'cloud-devops'),
    ('Data Science & ML', 'data-science-ml'),
    ('Mobile Development', 'mobile-development'),
    ('Testing & QA', 'testing-qa'),
    ('Project Management', 'project-management'),
    ('Soft Skills', 'soft-skills');

INSERT INTO skills (name, slug, category_id, aliases) VALUES
    ('Python', 'python', 1, ARRAY['python3', 'py']),
    ('Java', 'java', 1, ARRAY['java8', 'java11', 'java17']),
    ('JavaScript', 'javascript', 1, ARRAY['js', 'es6', 'es2015']),
    ('TypeScript', 'typescript', 1, ARRAY['ts']),
    ('Go', 'golang', 1, ARRAY['golang']),
    ('Rust', 'rust', 1, NULL),
    ('C++', 'cpp', 1, ARRAY['c++', 'cplusplus']),
    ('C#', 'csharp', 1, ARRAY['dotnet', '.net']),
    ('Kotlin', 'kotlin', 1, NULL),
    ('Swift', 'swift', 1, NULL),
    ('React', 'react', 2, ARRAY['reactjs', 'react.js']),
    ('Angular', 'angular', 2, ARRAY['angularjs', 'angular2+']),
    ('Vue.js', 'vuejs', 2, ARRAY['vue', 'vuejs']),
    ('Next.js', 'nextjs', 2, ARRAY['nextjs', 'next']),
    ('Svelte', 'svelte', 2, NULL),
    ('FastAPI', 'fastapi', 3, NULL),
    ('Django', 'django', 3, NULL),
    ('Flask', 'flask', 3, NULL),
    ('Spring Boot', 'spring-boot', 3, ARRAY['spring', 'springboot']),
    ('Node.js', 'nodejs', 3, ARRAY['node', 'express']),
    ('PostgreSQL', 'postgresql', 4, ARRAY['postgres', 'psql']),
    ('MySQL', 'mysql', 4, NULL),
    ('MongoDB', 'mongodb', 4, ARRAY['mongo']),
    ('Redis', 'redis', 4, NULL),
    ('Elasticsearch', 'elasticsearch', 4, ARRAY['elastic', 'elk']),
    ('Cassandra', 'cassandra', 4, NULL),
    ('AWS', 'aws', 5, ARRAY['amazon-web-services']),
    ('GCP', 'gcp', 5, ARRAY['google-cloud']),
    ('Azure', 'azure', 5, ARRAY['microsoft-azure']),
    ('Docker', 'docker', 5, NULL),
    ('Kubernetes', 'kubernetes', 5, ARRAY['k8s']),
    ('Terraform', 'terraform', 5, NULL),
    ('CI/CD', 'cicd', 5, ARRAY['jenkins', 'github-actions', 'gitlab-ci']),
    ('Machine Learning', 'machine-learning', 6, ARRAY['ml']),
    ('Deep Learning', 'deep-learning', 6, ARRAY['dl', 'neural-networks']),
    ('LangChain', 'langchain', 6, NULL),
    ('PyTorch', 'pytorch', 6, NULL),
    ('TensorFlow', 'tensorflow', 6, NULL),
    ('React Native', 'react-native', 7, NULL),
    ('Flutter', 'flutter', 7, NULL),
    ('Pytest', 'pytest', 8, NULL),
    ('Jest', 'jest', 8, NULL),
    ('Selenium', 'selenium', 8, NULL),
    ('Agile', 'agile', 9, ARRAY['scrum', 'kanban']),
    ('Communication', 'communication', 10, NULL);

-- =============================================================================
-- SEED DATA: Email templates
-- =============================================================================
INSERT INTO email_templates (name, slug, category, channel, subject, body_text, body_html, variables, is_active)
VALUES
(
    'Cold Outreach - Vendor Partnership',
    'cold-outreach-vendor',
    'cold_outreach',
    'email',
    'Partnering on {{job_title}} requirement at {{company_name}}',
    E'Hi {{first_name}},\n\nI came across {{company_name}} and was impressed by your work in {{industry}}. We specialize in sourcing top {{skill}} talent and have successfully placed 200+ professionals at similar organizations.\n\nWe currently have an open {{job_title}} position and would love to explore a vendor partnership.\n\nCould we schedule a quick 15-minute call this week?\n\nBest regards,\n{{sender_name}}\n{{sender_title}}',
    '<p>Hi {{first_name}},</p><p>I came across <strong>{{company_name}}</strong> and was impressed by your work in {{industry}}. We specialize in sourcing top {{skill}} talent and have successfully placed 200+ professionals at similar organizations.</p><p>We currently have an open <strong>{{job_title}}</strong> position and would love to explore a vendor partnership.</p><p>Could we schedule a quick 15-minute call this week?</p><p>Best regards,<br/>{{sender_name}}<br/>{{sender_title}}</p>',
    ARRAY['first_name', 'company_name', 'industry', 'skill', 'job_title', 'sender_name', 'sender_title'],
    TRUE
),
(
    'Follow-up - No Response',
    'follow-up-no-response',
    'follow_up',
    'email',
    'Re: {{job_title}} - Following up',
    E'Hi {{first_name}},\n\nJust following up on my previous email about the {{job_title}} opening at {{company_name}}.\n\nWe have 3 pre-screened candidates ready to submit who match your requirements. Would you be open to a quick 10-minute conversation?\n\nBest,\n{{sender_name}}',
    '<p>Hi {{first_name}},</p><p>Just following up on my previous email about the <strong>{{job_title}}</strong> opening at <strong>{{company_name}}</strong>.</p><p>We have 3 pre-screened candidates ready to submit who match your requirements. Would you be open to a quick 10-minute conversation?</p><p>Best,<br/>{{sender_name}}</p>',
    ARRAY['first_name', 'job_title', 'company_name', 'sender_name'],
    TRUE
),
(
    'Candidate Submission',
    'candidate-submission',
    'submission',
    'email',
    'Profile Submission: {{candidate_name}} for {{job_title}} at {{company_name}}',
    E'Hi {{first_name}},\n\nPlease find attached the profile of {{candidate_name}} for the {{job_title}} position.\n\nHighlights:\n- {{years_experience}} years of experience in {{primary_skill}}\n- Currently at {{current_company}}, notice period: {{notice_period}} days\n- Expected CTC: {{expected_ctc}}\n\nI believe {{candidate_name}} is an excellent fit for your requirement. Would you like to schedule an interview?\n\nBest regards,\n{{sender_name}}',
    '<p>Hi {{first_name}},</p><p>Please find attached the profile of <strong>{{candidate_name}}</strong> for the <strong>{{job_title}}</strong> position.</p><ul><li>{{years_experience}} years of experience in {{primary_skill}}</li><li>Currently at {{current_company}}, notice period: {{notice_period}} days</li><li>Expected CTC: {{expected_ctc}}</li></ul><p>I believe {{candidate_name}} is an excellent fit for your requirement. Would you like to schedule an interview?</p><p>Best regards,<br/>{{sender_name}}</p>',
    ARRAY['first_name', 'candidate_name', 'job_title', 'company_name', 'years_experience', 'primary_skill', 'current_company', 'notice_period', 'expected_ctc', 'sender_name'],
    TRUE
),
(
    'Placement Confirmation',
    'placement-confirmation',
    'placement_update',
    'email',
    'Placement Confirmation - {{candidate_name}} joining {{company_name}}',
    E'Hi {{first_name}},\n\nGreat news! We are pleased to confirm that {{candidate_name}} has accepted the offer and will be joining {{company_name}} on {{joining_date}} as {{job_title}}.\n\nPlease find the invoice for our placement fees attached (Invoice #{{invoice_number}}).\n\nThank you for the opportunity. We look forward to working with you on future requirements.\n\nBest regards,\n{{sender_name}}',
    '<p>Hi {{first_name}},</p><p>Great news! We are pleased to confirm that <strong>{{candidate_name}}</strong> has accepted the offer and will be joining <strong>{{company_name}}</strong> on <strong>{{joining_date}}</strong> as <strong>{{job_title}}</strong>.</p><p>Please find the invoice for our placement fees attached (Invoice #{{invoice_number}}).</p><p>Thank you for the opportunity. We look forward to working with you on future requirements.</p><p>Best regards,<br/>{{sender_name}}</p>',
    ARRAY['first_name', 'candidate_name', 'company_name', 'joining_date', 'job_title', 'invoice_number', 'sender_name'],
    TRUE
);

-- =============================================================================
-- SEED DATA: Job board configurations (Indian job boards)
-- =============================================================================
INSERT INTO job_board_configs (name, slug, base_url, is_active, region, rate_limit_rpm, config)
VALUES
    ('Naukri', 'naukri', 'https://www.naukri.com', TRUE, 'India', 20, '{"requires_login": true, "job_search_url": "/jobsearch/v2/jobs"}'),
    ('LinkedIn Jobs India', 'linkedin-india', 'https://www.linkedin.com', TRUE, 'India', 10, '{"api_version": "v2", "geo_id": "102713980"}'),
    ('Instahyre', 'instahyre', 'https://www.instahyre.com', TRUE, 'India', 30, '{"api_key_required": true}'),
    ('Cutshort', 'cutshort', 'https://cutshort.io', TRUE, 'India', 20, '{"focus": "tech_startups"}'),
    ('AngelList/Wellfound India', 'wellfound-india', 'https://wellfound.com', TRUE, 'India', 15, '{"focus": "startups"}'),
    ('Indeed India', 'indeed-india', 'https://www.indeed.co.in', TRUE, 'India', 20, '{"publisher_id_required": true}'),
    ('Shine.com', 'shine', 'https://www.shine.com', TRUE, 'India', 20, '{}'),
    ('Foundit (Monster)', 'foundit', 'https://www.foundit.in', TRUE, 'India', 15, '{}'),
    ('IIM Jobs', 'iimjobs', 'https://www.iimjobs.com', TRUE, 'India', 20, '{"focus": "senior_management"}'),
    ('Hirist.tech', 'hirist', 'https://www.hirist.tech', TRUE, 'India', 30, '{"focus": "tech_professionals"}');

-- =============================================================================
-- SEED DATA: Default admin user (password: Admin@1234 - change immediately)
-- =============================================================================
INSERT INTO users (email, hashed_password, role, full_name, is_active, is_verified)
VALUES (
    'admin@recruitai.io',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBpj2lSB4Z0Sm.',  -- bcrypt hash of 'Admin@1234'
    'admin',
    'Platform Admin',
    TRUE,
    TRUE
);
