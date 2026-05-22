#!/bin/bash
set -e

# ── Create .env ───────────────────────────────────────────────────────────────
cat > .env << 'EOF'
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=

DATABASE_URL=postgresql+asyncpg://recruitment:recruitment@postgresql:5432/recruitment
MONGODB_URL=mongodb://mongodb:27017
REDIS_URL=redis://redis:6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ELASTICSEARCH_URL=http://elasticsearch:9200

PINECONE_API_KEY=
PINECONE_ENVIRONMENT=us-east-1-aws

APOLLO_API_KEY=
HUNTER_API_KEY=
CLEARBIT_API_KEY=
ROCKETREACH_API_KEY=

LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
FROM_EMAIL=noreply@recruitai.io
FROM_NAME=RecruitAI

WHATSAPP_API_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

JWT_SECRET_KEY=recruitment-platform-super-secret-jwt-key-change-in-prod
JWT_ALGORITHM=HS256

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET_RESUMES=recruitment-resumes-dev

SENTRY_DSN=
DATADOG_API_KEY=

ENABLE_WHATSAPP_OUTREACH=false
ENABLE_LINKEDIN_AUTOMATION=false
ENABLE_AUTO_FOLLOWUP=true
ENABLE_MARKET_INTELLIGENCE=true
EOF

echo "⚠️  Add your OPENAI_API_KEY to .env for AI features (optional — platform runs without it)"

# ── Start all services ────────────────────────────────────────────────────────
echo "🚀 Starting platform..."
docker compose up -d --build

# ── Wait for PostgreSQL ───────────────────────────────────────────────────────
echo "⏳ Waiting for PostgreSQL..."
until docker compose exec -T postgresql pg_isready -U recruitment &>/dev/null; do sleep 2; done

# ── Init DB + seed ────────────────────────────────────────────────────────────
echo "🗄️  Initialising database..."
docker compose exec -T api-gateway python scripts/init_db.py 2>/dev/null || true

echo "🌱 Seeding demo data..."
docker compose exec -T api-gateway python scripts/seed_data.py 2>/dev/null || true

# ── Wait for frontend ─────────────────────────────────────────────────────────
echo "⏳ Waiting for frontend..."
until curl -sf http://localhost:3000 &>/dev/null; do sleep 3; done

echo ""
echo "✅ Platform is live!"
echo "   → http://localhost:3000"
echo "   → Login: admin@recruitai.io / Admin@123"
echo ""
echo "   Stop: docker compose down"
