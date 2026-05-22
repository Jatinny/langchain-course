-- =============================================================================
-- Migration: 001_initial
-- Description: Initial schema creation for AI Recruitment Platform
-- Author: Platform Team
-- Date: 2025-01-01
-- =============================================================================

BEGIN;

-- Record migration
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(50) PRIMARY KEY,
    description TEXT,
    applied_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Guard: skip if already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001') THEN
        RAISE NOTICE 'Migration 001 already applied, skipping.';
        RETURN;
    END IF;
END $$;

-- =============================================================================
-- Extensions
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM types
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'recruiter', 'viewer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE employer_status AS ENUM ('active', 'inactive', 'blacklisted', 'pending_review');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE employer_size AS ENUM ('1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001-10000', '10000+');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE job_status AS ENUM ('draft', 'active', 'paused', 'closed', 'filled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE job_type AS ENUM ('full_time', 'part_time', 'contract', 'c2h', 'freelance', 'internship');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE work_mode AS ENUM ('remote', 'onsite', 'hybrid');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE candidate_status AS ENUM ('active', 'passive', 'not_looking', 'placed', 'blacklisted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE outreach_status AS ENUM ('draft', 'scheduled', 'sent', 'failed', 'bounced');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE placement_status AS ENUM ('in_progress', 'offered', 'accepted', 'joined', 'fallen_through', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE pipeline_stage AS ENUM ('lead', 'contacted', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE activity_type AS ENUM ('call', 'email', 'meeting', 'note', 'task', 'linkedin', 'whatsapp', 'sms');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE channel AS ENUM ('email', 'linkedin', 'whatsapp', 'sms', 'telegram', 'phone');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE match_status AS ENUM ('pending', 'shortlisted', 'submitted', 'rejected', 'interviewing', 'offered', 'placed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =============================================================================
-- TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
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

CREATE TABLE IF NOT EXISTS skill_categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) UNIQUE NOT NULL,
    slug        VARCHAR(150) UNIQUE NOT NULL,
    category_id INTEGER REFERENCES skill_categories(id) ON DELETE SET NULL,
    aliases     TEXT[],
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employers (
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
    hiring_volume       INTEGER DEFAULT 0,
    avg_time_to_hire    INTEGER,
    score               FLOAT DEFAULT 0.0,
    status              employer_status NOT NULL DEFAULT 'active',
    source              VARCHAR(100),
    external_id         VARCHAR(255),
    tags                TEXT[],
    notes               TEXT,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hiring_contacts (
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
    seniority       VARCHAR(50),
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

CREATE TABLE IF NOT EXISTS recruiter_contacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agency_name     VARCHAR(255),
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    phone           VARCHAR(30),
    linkedin_url    VARCHAR(500),
    whatsapp        VARCHAR(30),
    specializations TEXT[],
    regions         TEXT[],
    tier            INTEGER DEFAULT 3 CHECK (tier BETWEEN 1 AND 5),
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

CREATE TABLE IF NOT EXISTS job_postings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id         UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    hiring_contact_id   UUID REFERENCES hiring_contacts(id) ON DELETE SET NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    requirements        TEXT,
    responsibilities    TEXT,
    required_skills     TEXT[],
    nice_to_have_skills TEXT[],
    experience_min      INTEGER,
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

CREATE TABLE IF NOT EXISTS candidates (
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
    total_experience    FLOAT,
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
    resume_mongo_id     VARCHAR(100),
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

CREATE TABLE IF NOT EXISTS job_matches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id              UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    candidate_id        UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    assigned_recruiter  UUID REFERENCES users(id) ON DELETE SET NULL,
    status              match_status NOT NULL DEFAULT 'pending',
    ai_score            FLOAT,
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

CREATE TABLE IF NOT EXISTS outreach_campaigns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    target_type     VARCHAR(50) NOT NULL,
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

CREATE TABLE IF NOT EXISTS outreach_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id     UUID NOT NULL REFERENCES outreach_campaigns(id) ON DELETE CASCADE,
    channel         channel NOT NULL,
    recipient_type  VARCHAR(50) NOT NULL,
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
    external_id     VARCHAR(255),
    thread_id       VARCHAR(255),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) UNIQUE NOT NULL,
    category        VARCHAR(100) NOT NULL,
    channel         channel NOT NULL DEFAULT 'email',
    subject         VARCHAR(500),
    body_html       TEXT,
    body_text       TEXT,
    variables       TEXT[],
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

CREATE TABLE IF NOT EXISTS placements (
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

CREATE TABLE IF NOT EXISTS commissions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    placement_id        UUID NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
    recruiter_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    employer_id         UUID NOT NULL REFERENCES employers(id),
    invoice_number      VARCHAR(100) UNIQUE,
    gross_amount        NUMERIC(14,2) NOT NULL,
    tax_amount          NUMERIC(14,2) DEFAULT 0,
    net_amount          NUMERIC(14,2) NOT NULL,
    currency            VARCHAR(10) DEFAULT 'INR',
    payment_terms       VARCHAR(50),
    due_date            DATE,
    paid_date           DATE,
    payment_status      VARCHAR(50) DEFAULT 'pending',
    payment_reference   VARCHAR(255),
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_deals (
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

CREATE TABLE IF NOT EXISTS crm_activities (
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

CREATE TABLE IF NOT EXISTS job_board_configs (
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
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_employers_name ON employers USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_employers_industry ON employers(industry);
CREATE INDEX IF NOT EXISTS idx_employers_status ON employers(status);
CREATE INDEX IF NOT EXISTS idx_employers_score ON employers(score DESC);
CREATE INDEX IF NOT EXISTS idx_employers_tech_stack ON employers USING gin(tech_stack);
CREATE INDEX IF NOT EXISTS idx_hiring_contacts_employer ON hiring_contacts(employer_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_employer ON job_postings(employer_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(status);
CREATE INDEX IF NOT EXISTS idx_job_postings_required_skills ON job_postings USING gin(required_skills);
CREATE INDEX IF NOT EXISTS idx_candidates_skills ON candidates USING gin(skills);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_job_matches_job ON job_matches(job_id);
CREATE INDEX IF NOT EXISTS idx_job_matches_candidate ON job_matches(candidate_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON outreach_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_placements_status ON placements(status);
CREATE INDEX IF NOT EXISTS idx_crm_deals_stage ON crm_deals(stage);

-- =============================================================================
-- TRIGGERS
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users','employers','hiring_contacts','recruiter_contacts',
        'job_postings','candidates','job_matches','outreach_campaigns',
        'outreach_messages','email_templates','placements','commissions',
        'crm_deals','crm_activities'
    ] LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s;
            CREATE TRIGGER trg_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;

-- =============================================================================
-- Record migration
-- =============================================================================
INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Initial schema — all tables, indexes, triggers, and seed data')
ON CONFLICT (version) DO NOTHING;

COMMIT;
