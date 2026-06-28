#!/usr/bin/env bash
# start.sh — AutoMark AI local development launcher
# Starts the shared PostgreSQL database then prints the commands to run each app.
#
# Usage (from the AutoMarkAi/ root):
#   bash start.sh           — start DB and show instructions
#   bash start.sh --docker  — start EVERYTHING in Docker (db + crm + analytics)
#   bash start.sh --down    — stop all containers

set -e
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# ── Flags ─────────────────────────────────────────────────────────────────────
if [ "$1" = "--down" ]; then
  echo -e "${YELLOW}Stopping all containers...${NC}"
  docker-compose down
  echo -e "${GREEN}Done.${NC}"
  exit 0
fi

if [ "$1" = "--docker" ]; then
  echo -e "${CYAN}Starting full stack in Docker...${NC}"
  docker-compose up --build
  exit 0
fi

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   AutoMark AI — Dev Startup          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Check Docker ───────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "${RED}ERROR: Docker not found.${NC}"
  echo "  Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info &>/dev/null 2>&1; then
  echo -e "${RED}ERROR: Docker daemon is not running.${NC}"
  echo "  Start Docker Desktop, then re-run this script."
  exit 1
fi

# ── 2. Start the database ─────────────────────────────────────────────────────
echo -e "${YELLOW}[1/3]${NC} Starting PostgreSQL + pgvector..."
docker-compose up -d db

echo -e "${YELLOW}[2/3]${NC} Waiting for PostgreSQL to be ready..."
TRIES=0
MAX=30
until docker-compose exec -T db pg_isready -U postgres -q 2>/dev/null; do
  TRIES=$((TRIES+1))
  if [ "$TRIES" -ge "$MAX" ]; then
    echo -e "${RED}ERROR: PostgreSQL did not become ready.${NC}"
    docker-compose logs db | tail -20
    exit 1
  fi
  printf "."
  sleep 1
done
echo -e " ${GREEN}ready${NC}"

# ── 3. Check .env ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}[!] .env not found — copying from .env.example${NC}"
  cp .env.example .env
  echo -e "    ${RED}Open .env and fill in GEMINI_API_KEY before starting the apps.${NC}"
fi

# ── 4. Print startup instructions ────────────────────────────────────────────
echo ""
echo -e "${GREEN}[3/3] Database is up and ready!${NC}"
echo ""
echo -e "  ┌─ ${CYAN}CRM Agent${NC} ─────────────────────────────────────"
echo    "  │  Open a new terminal, then run:"
echo    "  │"
echo    "  │    cd CRM"
echo    "  │    set PYTHONPATH=..      (Windows CMD)"
echo    "  │    python -m uvicorn main:app --port 8000"
echo    "  │"
echo -e "  │  API Docs: ${CYAN}http://localhost:8000/docs${NC}"
echo    "  │  Health:   http://localhost:8000/health"
echo    "  │  DB API:   http://localhost:8000/admin/db/stats"
echo    ""
echo -e "  ┌─ ${CYAN}Analytics Assistant${NC} ─────────────────────────────"
echo    "  │  Open another terminal, then run:"
echo    "  │"
echo    "  │    streamlit run data-analytics-assistant/app/ui/streamlit_app.py"
echo    "  │"
echo -e "  │  UI: ${CYAN}http://localhost:8501${NC}"
echo    ""
echo -e "  ┌─ ${YELLOW}Other commands${NC} ──────────────────────────────────"
echo    "  │  Stop DB:         bash start.sh --down"
echo    "  │  Full Docker:     bash start.sh --docker"
echo    "  │  Re-embed RAG:    cd CRM && python -m app.rag.ingest --source ./knowledge_base"
echo    "  │  DB admin UI:     http://localhost:8000/admin/db/stats (CRM must be running)"
echo    ""
