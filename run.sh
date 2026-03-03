#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${GREEN}Personal AI Assistant${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 is required. Please install it first.${NC}"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

# Install deps
echo -e "${BLUE}Installing dependencies...${NC}"
pip install -q -r requirements.txt

# Check for .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}No .env file found. Copying from .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env and add your API keys!${NC}"
    echo ""
fi

# Create data dir
mkdir -p data

# Start server
echo -e "${GREEN}Starting JARVIS on http://localhost:${PORT:-8000}${NC}"
echo -e "${BLUE}Open your browser and go to the URL above.${NC}"
echo ""

python3 -m uvicorn backend.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
