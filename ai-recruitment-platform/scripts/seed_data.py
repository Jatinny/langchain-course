#!/usr/bin/env python3
"""Seed realistic demo data for the platform."""
import asyncio
import json
import uuid
import random
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMPLOYERS = [
    {"name": "Tata Consultancy Services", "industry": "IT Services", "region": "India", "country": "India", "size": "5001+", "website": "tcs.com", "score": 75, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 500},
    {"name": "Infosys", "industry": "IT Services", "region": "India", "country": "India", "size": "5001+", "website": "infosys.com", "score": 72, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 400},
    {"name": "Wipro Technologies", "industry": "IT Services", "region": "India", "country": "India", "size": "5001+", "website": "wipro.com", "score": 70, "vendor_friendly": True, "contract": True, "c2h": False, "volume": 350},
    {"name": "HCL Technologies", "industry": "IT Services", "region": "India", "country": "India", "size": "5001+", "website": "hcltech.com", "score": 73, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 300},
    {"name": "Razorpay", "industry": "FinTech", "region": "India", "country": "India", "size": "201-1000", "website": "razorpay.com", "score": 88, "vendor_friendly": True, "contract": False, "c2h": True, "volume": 40},
    {"name": "PhonePe", "industry": "FinTech", "region": "India", "country": "India", "size": "1001-5000", "website": "phonepe.com", "score": 85, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 60},
    {"name": "Swiggy", "industry": "E-commerce", "region": "India", "country": "India", "size": "1001-5000", "website": "swiggy.in", "score": 82, "vendor_friendly": True, "contract": False, "c2h": False, "volume": 80},
    {"name": "Zomato", "industry": "E-commerce", "region": "India", "country": "India", "size": "1001-5000", "website": "zomato.com", "score": 80, "vendor_friendly": True, "contract": False, "c2h": True, "volume": 70},
    {"name": "HDFC Bank Technology", "industry": "BFSI", "region": "India", "country": "India", "size": "5001+", "website": "hdfcbank.com", "score": 78, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 100},
    {"name": "ICICI Prudential Tech", "industry": "BFSI", "region": "India", "country": "India", "size": "1001-5000", "website": "iciciprulife.com", "score": 74, "vendor_friendly": True, "contract": True, "c2h": False, "volume": 50},
    {"name": "Google GCC Hyderabad", "industry": "GCC", "region": "India", "country": "India", "size": "1001-5000", "website": "careers.google.com", "score": 95, "vendor_friendly": False, "contract": False, "c2h": False, "volume": 150},
    {"name": "Microsoft India R&D", "industry": "GCC", "region": "India", "country": "India", "size": "1001-5000", "website": "microsoft.com/india", "score": 93, "vendor_friendly": False, "contract": True, "c2h": False, "volume": 120},
    {"name": "Amazon Development Center", "industry": "GCC", "region": "India", "country": "India", "size": "5001+", "website": "amazon.jobs", "score": 92, "vendor_friendly": False, "contract": False, "c2h": False, "volume": 200},
    {"name": "Barclays GCC India", "industry": "GCC", "region": "India", "country": "India", "size": "1001-5000", "website": "barclays.in", "score": 84, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 80},
    {"name": "BYJU's", "industry": "EdTech", "region": "India", "country": "India", "size": "1001-5000", "website": "byjus.com", "score": 65, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 30},
    {"name": "Freshworks", "industry": "Product", "region": "India", "country": "India", "size": "1001-5000", "website": "freshworks.com", "score": 87, "vendor_friendly": False, "contract": False, "c2h": False, "volume": 60},
    {"name": "Zoho Corporation", "industry": "Product", "region": "India", "country": "India", "size": "1001-5000", "website": "zoho.com", "score": 85, "vendor_friendly": False, "contract": False, "c2h": False, "volume": 100},
    {"name": "Mphasis Limited", "industry": "IT Services", "region": "India", "country": "India", "size": "1001-5000", "website": "mphasis.com", "score": 76, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 80},
    {"name": "Hexaware Technologies", "industry": "IT Services", "region": "India", "country": "India", "size": "1001-5000", "website": "hexaware.com", "score": 74, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 70},
    {"name": "Persistent Systems", "industry": "IT Services", "region": "India", "country": "India", "size": "1001-5000", "website": "persistent.com", "score": 77, "vendor_friendly": True, "contract": True, "c2h": True, "volume": 60},
]

CANDIDATES = [
    ("Rahul Sharma", "Senior Java Developer", "Bangalore", 6, ["Java", "Spring Boot", "Microservices", "AWS", "Docker"], 1500000, 2200000),
    ("Priya Nair", "AI Engineer", "Hyderabad", 4, ["Python", "TensorFlow", "LangChain", "AWS", "SQL"], 1800000, 2800000),
    ("Arjun Mehta", "Cloud Engineer", "Pune", 5, ["AWS", "Terraform", "Kubernetes", "Docker", "CI/CD"], 1600000, 2400000),
    ("Sneha Patel", "Full Stack Developer", "Mumbai", 3, ["React", "Node.js", "TypeScript", "MongoDB", "AWS"], 1000000, 1600000),
    ("Vikram Singh", "DevOps Engineer", "Bangalore", 7, ["Kubernetes", "Docker", "Jenkins", "Terraform", "AWS", "Prometheus"], 2000000, 3000000),
    ("Ananya Krishnan", "Data Engineer", "Chennai", 5, ["Python", "Apache Spark", "Kafka", "SQL", "AWS Glue"], 1700000, 2500000),
    ("Rohan Gupta", "SAP Consultant", "Delhi NCR", 8, ["SAP S/4HANA", "ABAP", "SAP Fiori", "SAP BTP"], 2200000, 3500000),
    ("Meera Iyer", "QA Automation Engineer", "Hyderabad", 4, ["Selenium", "Cypress", "Python", "API Testing", "Postman"], 900000, 1500000),
    ("Kartik Joshi", "Salesforce Developer", "Pune", 5, ["Apex", "Salesforce Lightning", "Visualforce", "SOQL"], 1400000, 2200000),
    ("Divya Reddy", "Cybersecurity Engineer", "Bangalore", 6, ["Penetration Testing", "SIEM", "Python", "Network Security"], 1800000, 2800000),
]


async def seed(database_url: str) -> None:
    engine = create_async_engine(database_url, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSession() as session:
        # Seed employers
        employer_ids = []
        for e in EMPLOYERS:
            eid = str(uuid.uuid4())
            employer_ids.append(eid)
            try:
                await session.execute(text("""
                    INSERT INTO employers (id, name, industry, size, country, region, website, score,
                        is_vendor_friendly, accepts_contract, accepts_c2h, hiring_volume, status, created_at)
                    VALUES (:id, :name, :ind, :size, :country, :region, :website, :score,
                        :vf, :contract, :c2h, :vol, 'active', :now)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": eid, "name": e["name"], "ind": e["industry"], "size": e["size"],
                    "country": e["country"], "region": e["region"], "website": e["website"],
                    "score": e["score"], "vf": e["vendor_friendly"], "contract": e["contract"],
                    "c2h": e["c2h"], "vol": e["volume"], "now": datetime.now(timezone.utc),
                })
            except Exception as ex:
                logger.debug(f"Employer insert skipped: {ex}")

        logger.info(f"✅ Seeded {len(EMPLOYERS)} employers")

        # Seed candidates
        for name, title, location, yoe, skills, sal_min, sal_max in CANDIDATES:
            cid = str(uuid.uuid4())
            try:
                await session.execute(text("""
                    INSERT INTO candidates (id, name, location, current_title, years_experience, skills,
                        availability, salary_expectation_min, salary_expectation_max, preferred_work_type, status, created_at)
                    VALUES (:id, :name, :loc, :title, :yoe, :skills, 'immediate', :smin, :smax, 'hybrid', 'active', :now)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": cid, "name": name, "loc": location, "title": title, "yoe": yoe,
                    "skills": json.dumps(skills), "smin": sal_min, "smax": sal_max,
                    "now": datetime.now(timezone.utc),
                })
            except Exception as ex:
                logger.debug(f"Candidate insert skipped: {ex}")

        logger.info(f"✅ Seeded {len(CANDIDATES)} candidates")

        await session.commit()
    await engine.dispose()
    logger.info("✅ Demo data seeded successfully!")


if __name__ == "__main__":
    import os
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://recruitment:recruitment@localhost:5432/recruitment")
    asyncio.run(seed(db_url))
