#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[•]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AI Recruitment Platform — Startup    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Check Docker ──────────────────────────────────────────────────────────
log "Checking Docker..."
command -v docker &>/dev/null || fail "Docker not found. Install from https://docker.com"
docker info &>/dev/null       || fail "Docker daemon not running. Start Docker Desktop."
ok "Docker is running"

# ── 2. Set up .env ───────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  log "Creating .env from .env.example..."
  cp .env.example .env
  warn ".env created. Add your OPENAI_API_KEY to .env for AI features."
  warn "Edit .env now? (Press Enter to skip, Ctrl+C to edit first)"
  read -r
fi

# Warn if OPENAI_API_KEY is missing or placeholder
if grep -qE "^OPENAI_API_KEY=(sk-\.\.\.|)$" .env 2>/dev/null; then
  warn "OPENAI_API_KEY not set — AI features (matching, outreach generation) will be disabled."
fi
ok ".env ready"

# ── 3. Pull & start all services ─────────────────────────────────────────────
log "Starting all services (first run pulls Docker images — may take 5 min)..."
docker compose up -d --build 2>&1 | grep -E "(Pulling|Building|Started|Running|Error)" || true
ok "Containers started"

# ── 4. Wait for PostgreSQL ────────────────────────────────────────────────────
log "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
  if docker compose exec -T postgresql pg_isready -U recruitment &>/dev/null; then
    ok "PostgreSQL ready"
    break
  fi
  [ "$i" -eq 30 ] && fail "PostgreSQL did not become ready in time"
  sleep 2
done

# ── 5. Wait for API Gateway ───────────────────────────────────────────────────
log "Waiting for API Gateway (port 8000)..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "API Gateway ready"
    break
  fi
  [ "$i" -eq 30 ] && { warn "API Gateway slow to start — skipping health check"; break; }
  sleep 3
done

# ── 6. Init DB + seed data ────────────────────────────────────────────────────
log "Initialising database schema..."
docker compose exec -T api-gateway python /app/scripts/init_db.py 2>/dev/null \
  || docker run --rm --network ai-recruitment-platform_data-net \
       -e DATABASE_URL=postgresql+asyncpg://recruitment:recruitment@postgresql:5432/recruitment \
       -v "$(pwd)/scripts:/scripts" \
       -v "$(pwd)/database:/database" \
       -v "$(pwd)/data:/data" \
       -v "$(pwd)/common:/common" \
       python:3.11-slim bash -c "pip install -q sqlalchemy asyncpg aiofiles bcrypt passlib python-jose 2>/dev/null; python /scripts/init_db.py" 2>/dev/null \
  || warn "DB init skipped (may already be initialised)"
ok "Database schema ready"

log "Seeding demo data (20 employers, 10 candidates)..."
docker compose exec -T api-gateway python /app/scripts/seed_data.py 2>/dev/null \
  || warn "Seed skipped (data may already exist)"
ok "Demo data loaded"

# ── 7. Wait for frontend ──────────────────────────────────────────────────────
log "Waiting for frontend (port 3000)..."
for i in $(seq 1 40); do
  if curl -sf http://localhost:3000 &>/dev/null; then
    ok "Frontend ready"
    break
  fi
  [ "$i" -eq 40 ] && { warn "Frontend still starting — open http://localhost:3000 manually"; break; }
  sleep 3
done

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Platform is LIVE! 🚀           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Dashboard:${NC}  http://localhost:3000"
echo -e "  ${BLUE}API:${NC}        http://localhost:8000/docs"
echo -e "  ${BLUE}Login:${NC}      admin@recruitai.io / Admin@123"
echo ""
echo -e "  ${YELLOW}Stop:${NC}  docker compose down"
echo -e "  ${YELLOW}Logs:${NC}  docker compose logs -f"
echo ""

# Open browser automatically
if command -v xdg-open &>/dev/null; then
  xdg-open http://localhost:3000 &
elif command -v open &>/dev/null; then
  open http://localhost:3000 &
fi
