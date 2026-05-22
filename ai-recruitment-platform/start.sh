#!/bin/bash
set -e

# ── Colours ───────────────────────────────────────────────────────────────────
G='\033[0;32m'; B='\033[0;34m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
ok()  { echo -e "${G}✓${N} $1"; }
log() { echo -e "${B}•${N} $1"; }
warn(){ echo -e "${Y}!${N} $1"; }
die() { echo -e "${R}✗${N} $1"; exit 1; }

echo -e "\n${B}━━━ AI Recruitment Platform ━━━${N}\n"

# ── 1. Check Docker ───────────────────────────────────────────────────────────
command -v docker &>/dev/null     || die "Docker not installed → https://docker.com"
docker info &>/dev/null 2>&1      || die "Docker not running. Start Docker Desktop first."
ok "Docker running"

# ── 2. Write .env (every run overwrites with safe defaults) ───────────────────
cat > .env <<'ENVEOF'
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Add your key here for AI features (matching, email generation)
OPENAI_API_KEY=sk-placeholder
ANTHROPIC_API_KEY=

DATABASE_URL=postgresql+asyncpg://recruitment:recruitment@postgresql:5432/recruitment
MONGODB_URL=mongodb://mongodb:27017
REDIS_URL=redis://redis:6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ELASTICSEARCH_URL=http://elasticsearch:9200

PINECONE_API_KEY=
PINECONE_ENVIRONMENT=us-east-1-aws
APOLLO_API_KEY=
HUNTER_API_KEY=
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

JWT_SECRET_KEY=recruitment-platform-super-secret-jwt-key-32chars
JWT_ALGORITHM=HS256

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET_RESUMES=recruitment-resumes-dev

SENTRY_DSN=
ENABLE_WHATSAPP_OUTREACH=false
ENABLE_LINKEDIN_AUTOMATION=false
ENABLE_AUTO_FOLLOWUP=true
ENABLE_MARKET_INTELLIGENCE=true
ENVEOF
ok ".env written"

# ── 3. Start infra first (DB, Redis, Kafka) ───────────────────────────────────
log "Starting infrastructure services..."
docker compose up -d postgresql mongodb redis zookeeper kafka elasticsearch 2>&1 | tail -3
ok "Infrastructure containers started"

# ── 4. Wait for PostgreSQL ────────────────────────────────────────────────────
log "Waiting for PostgreSQL..."
for i in $(seq 1 40); do
  docker compose exec -T postgresql pg_isready -U recruitment -q 2>/dev/null && break
  [ "$i" -eq 40 ] && die "PostgreSQL failed to start after 80s"
  sleep 2
done
ok "PostgreSQL ready"

# ── 5. Init DB schema + seed via temp container ───────────────────────────────
log "Initialising database schema..."
docker run --rm \
  --network "$(basename $(pwd))_data-net" \
  -v "$(pwd)/database:/app/database" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/common:/app/common" \
  -v "$(pwd)/scripts:/app/scripts" \
  -e DATABASE_URL="postgresql+asyncpg://recruitment:recruitment@postgresql:5432/recruitment" \
  -e PYTHONPATH=/app \
  -w /app \
  python:3.11-slim \
  bash -c "pip install -q sqlalchemy asyncpg 'passlib[bcrypt]' 'python-jose[cryptography]' aiofiles 2>/dev/null && python scripts/init_db.py" \
  2>/dev/null && ok "Schema + admin user created" || warn "DB init skipped (already initialised)"

log "Seeding demo employers and candidates..."
docker run --rm \
  --network "$(basename $(pwd))_data-net" \
  -v "$(pwd)/scripts:/app/scripts" \
  -e DATABASE_URL="postgresql+asyncpg://recruitment:recruitment@postgresql:5432/recruitment" \
  -e PYTHONPATH=/app \
  -w /app \
  python:3.11-slim \
  bash -c "pip install -q sqlalchemy asyncpg 2>/dev/null && python scripts/seed_data.py" \
  2>/dev/null && ok "Demo data seeded" || warn "Seed skipped (data already exists)"

# ── 6. Start all app services + frontend ─────────────────────────────────────
log "Starting application services and frontend..."
docker compose up -d --build 2>&1 | grep -E "(Building|Started|Running|Error|error)" | head -20 || true
ok "All containers started"

# ── 7. Wait for frontend ──────────────────────────────────────────────────────
log "Waiting for frontend on port 3000..."
for i in $(seq 1 60); do
  curl -sf http://localhost:3000 &>/dev/null && break
  [ "$i" -eq 60 ] && { warn "Frontend slow — open http://localhost:3000 manually once ready"; break; }
  sleep 3
done
ok "Frontend ready"

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${G}  Platform is live!${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  App      → http://localhost:3000"
echo -e "  API docs → http://localhost:8000/docs"
echo -e "  Login    → admin@recruitai.io / Admin@123"
echo ""
echo -e "  ${Y}Add OPENAI_API_KEY to .env for AI features${N}"
echo -e "  Stop → docker compose down"
echo ""

# Auto-open browser
command -v xdg-open &>/dev/null && xdg-open http://localhost:3000 &>/dev/null &
command -v open     &>/dev/null && open     http://localhost:3000 &>/dev/null &
true
