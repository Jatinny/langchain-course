"""Centralized configuration management for all microservices."""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # App
    app_name: str = "AI Recruitment Platform"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # AI / LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openai_model: str = "gpt-4o"
    claude_model: str = "claude-opus-4-7"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Databases
    database_url: str = "postgresql+asyncpg://recruitment:recruitment@localhost:5432/recruitment"
    database_pool_size: int = 20
    database_max_overflow: int = 40
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "recruitment"
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_max_connections: int = 100

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group_id: str = "recruitment-platform"
    kafka_auto_offset_reset: str = "earliest"
    kafka_max_poll_records: int = 100

    # Kafka Topics
    topic_employer_discovered: str = "employer.discovered"
    topic_employer_qualified: str = "employer.qualified"
    topic_recruiter_found: str = "recruiter.found"
    topic_outreach_sent: str = "outreach.sent"
    topic_outreach_replied: str = "outreach.replied"
    topic_candidate_matched: str = "candidate.matched"
    topic_candidate_submitted: str = "candidate.submitted"
    topic_placement_confirmed: str = "placement.confirmed"
    topic_commission_earned: str = "commission.earned"
    topic_analytics_event: str = "analytics.event"

    # Search
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "recruitment"
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1-aws"
    pinecone_index_name: str = "recruitment-embeddings"
    weaviate_url: str = "http://localhost:8080"

    # External Integrations
    apollo_api_key: str = ""
    apollo_base_url: str = "https://api.apollo.io/v1"
    hunter_api_key: str = ""
    hunter_base_url: str = "https://api.hunter.io/v2"
    clearbit_api_key: str = ""
    clearbit_base_url: str = "https://person.clearbit.com/v2"
    rocketreach_api_key: str = ""
    rocketreach_base_url: str = "https://api.rocketreach.co/v2"

    # LinkedIn
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:3000/auth/linkedin/callback"

    # Gmail / Email
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:3000/auth/gmail/callback"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@recruitai.io"
    from_name: str = "RecruitAI Platform"

    # WhatsApp
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Auth / Security
    jwt_secret_key: str = "change-me-in-production-use-rs256-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    password_min_length: int = 8
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    allowed_hosts: List[str] = ["*"]

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 3000
    apollo_rate_limit_per_minute: int = 10
    hunter_rate_limit_per_minute: int = 30
    linkedin_rate_limit_per_minute: int = 5

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_resumes: str = "recruitment-resumes"
    s3_bucket_backups: str = "recruitment-backups"

    # Observability
    sentry_dsn: str = ""
    datadog_api_key: str = ""
    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    # Service URLs (internal)
    employer_discovery_url: str = "http://employer-discovery:8001"
    recruiter_intelligence_url: str = "http://recruiter-intelligence:8002"
    outreach_engine_url: str = "http://outreach-engine:8003"
    candidate_matching_url: str = "http://candidate-matching:8004"
    crm_service_url: str = "http://crm-service:8005"
    analytics_service_url: str = "http://analytics-service:8006"

    # Feature Flags
    enable_whatsapp_outreach: bool = False
    enable_linkedin_automation: bool = False
    enable_ai_voice_assistant: bool = False
    enable_auto_followup: bool = True
    enable_market_intelligence: bool = True
    enable_salary_intelligence: bool = True

    # Scraping
    scraper_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    scraper_request_delay_seconds: float = 2.0
    scraper_max_retries: int = 3
    proxy_list: List[str] = []

    # India-specific
    default_regions: List[str] = ["India", "USA", "Canada", "UK", "Europe", "Singapore", "Australia", "UAE"]
    india_job_boards: List[str] = [
        "naukri", "foundit", "shine", "cutshort", "instahyre",
        "hirist", "linkedin_india", "timesjobs", "freshersworld", "apna",
        "wellfound", "iimjobs"
    ]
    default_target_roles: List[str] = [
        "Java Developer", "Spring Boot Developer", "AI Engineer", "Cloud Engineer",
        "DevOps Engineer", "Data Engineer", "Full Stack Developer", "QA Automation Engineer",
        "SAP Consultant", "Salesforce Developer", "Cybersecurity Engineer",
        "Python Developer", "ML Engineer", "React Developer", "Angular Developer"
    ]
    default_target_industries: List[str] = [
        "IT Services", "BFSI", "Product", "Startup", "GCC",
        "Healthcare IT", "EdTech", "FinTech", "E-commerce", "Telecom", "AI/ML"
    ]

    # Commission defaults
    default_permanent_commission_pct: float = 8.33
    default_contract_margin_pct: float = 15.0
    default_c2h_contract_fee_months: int = 3

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def kafka_topics(self) -> List[str]:
        return [
            self.topic_employer_discovered,
            self.topic_employer_qualified,
            self.topic_recruiter_found,
            self.topic_outreach_sent,
            self.topic_outreach_replied,
            self.topic_candidate_matched,
            self.topic_candidate_submitted,
            self.topic_placement_confirmed,
            self.topic_commission_earned,
            self.topic_analytics_event,
        ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
