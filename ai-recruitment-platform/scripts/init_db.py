#!/usr/bin/env python3
"""Initialize the database with schema and seed data."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db(database_url: str) -> None:
    engine = create_async_engine(database_url, echo=False)

    logger.info("Running database initialization...")
    async with engine.begin() as conn:
        with open("database/postgres/init.sql") as f:
            sql = f.read()
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    await conn.execute(text(stmt))
                except Exception as e:
                    logger.debug(f"Statement skipped: {e}")

    # Seed skills taxonomy
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSession() as session:
        await seed_skills(session)
        await seed_email_templates(session)
        await seed_admin_user(session)
        await session.commit()

    await engine.dispose()
    logger.info("✅ Database initialized successfully!")


async def seed_skills(session) -> None:
    skills = [
        ("Java", "Backend", ["J2EE", "Core Java"], ["Spring Boot", "Hibernate", "Maven"]),
        ("Spring Boot", "Backend", ["Spring Framework"], ["Java", "Microservices", "REST API"]),
        ("Python", "Backend/AI", ["Python3"], ["FastAPI", "Django", "Flask", "ML"]),
        ("JavaScript", "Frontend/Backend", ["JS", "ES6+"], ["React", "Node.js", "TypeScript"]),
        ("TypeScript", "Frontend/Backend", ["TS"], ["React", "Node.js", "Angular"]),
        ("React", "Frontend", ["ReactJS", "React.js"], ["TypeScript", "Redux", "Next.js"]),
        ("AWS", "Cloud", ["Amazon Web Services"], ["EC2", "S3", "Lambda", "EKS"]),
        ("Azure", "Cloud", ["Microsoft Azure"], ["AKS", "Azure Functions"]),
        ("GCP", "Cloud", ["Google Cloud Platform"], ["GKE", "BigQuery", "Cloud Run"]),
        ("Docker", "DevOps", ["Containerization"], ["Kubernetes", "Docker Compose"]),
        ("Kubernetes", "DevOps", ["K8s"], ["Docker", "Helm", "EKS", "GKE"]),
        ("DevOps", "Platform", [], ["CI/CD", "Jenkins", "GitHub Actions", "Terraform"]),
        ("SQL", "Database", ["MySQL", "PostgreSQL", "MSSQL"], ["Database Design", "Stored Procedures"]),
        ("MongoDB", "Database", ["NoSQL"], ["Mongoose", "Atlas"]),
        ("Kafka", "Messaging", ["Apache Kafka"], ["Event Streaming", "Confluent"]),
        ("Machine Learning", "AI/ML", ["ML", "Deep Learning"], ["Python", "TensorFlow", "PyTorch"]),
        ("LangChain", "AI/ML", ["LangGraph"], ["Python", "OpenAI", "RAG", "LLM"]),
        ("SAP", "ERP", ["SAP HANA", "SAP S/4"], ["ABAP", "SAP Fiori"]),
        ("Salesforce", "CRM", ["SFDC"], ["Apex", "Lightning", "Visualforce"]),
        ("Cybersecurity", "Security", ["InfoSec", "AppSec"], ["SIEM", "Penetration Testing"]),
    ]
    for skill_name, category, aliases, related in skills:
        try:
            await session.execute(text("""
                INSERT INTO skills_taxonomy (id, skill_name, category, aliases, related_skills, demand_level)
                VALUES (:id, :name, :cat, :aliases, :related, 'high')
                ON CONFLICT (skill_name) DO NOTHING
            """), {
                "id": str(uuid.uuid4()), "name": skill_name, "cat": category,
                "aliases": json.dumps(aliases), "related": json.dumps(related),
            })
        except Exception:
            pass
    logger.info(f"✅ Seeded {len(skills)} skills")


async def seed_email_templates(session) -> None:
    with open("data/email_templates.json") as f:
        templates_data = json.load(f)

    for tmpl in templates_data.get("templates", []):
        try:
            await session.execute(text("""
                INSERT INTO email_templates (id, name, category, channel, subject, body, variables, performance_score, usage_count, created_at)
                VALUES (:id, :name, :cat, :chan, :subj, :body, :vars, 0.0, 0, :now)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": tmpl["id"], "name": tmpl["name"], "cat": tmpl["category"],
                "chan": tmpl["channel"], "subj": tmpl.get("subject", ""),
                "body": tmpl["body"], "vars": json.dumps(tmpl.get("variables", [])),
                "now": datetime.now(timezone.utc),
            })
        except Exception:
            pass
    logger.info(f"✅ Seeded {len(templates_data.get('templates', []))} email templates")


async def seed_admin_user(session) -> None:
    from common.security import hash_password
    try:
        await session.execute(text("""
            INSERT INTO users (id, email, hashed_password, role, full_name, created_at, is_active)
            VALUES (:id, :email, :pwd, 'admin', 'Admin User', :now, true)
            ON CONFLICT (email) DO NOTHING
        """), {
            "id": str(uuid.uuid4()),
            "email": "admin@recruitai.io",
            "pwd": hash_password("Admin@123"),
            "now": datetime.now(timezone.utc),
        })
        logger.info("✅ Admin user created: admin@recruitai.io / Admin@123")
    except Exception as e:
        logger.warning(f"Admin user not created: {e}")


if __name__ == "__main__":
    import os
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://recruitment:recruitment@localhost:5432/recruitment")
    asyncio.run(init_db(db_url))
