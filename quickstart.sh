#!/bin/bash

# Quick Start Guide for SAP O2C Graph System
# This script sets up and launches the complete system

set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║  SAP O2C Graph System - Quick Start Setup          ║"
echo "║  Version: 1.0.0 | Date: March 2026               ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install from https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Install from https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker installed${NC}"
echo -e "${GREEN}✓ Docker Compose installed${NC}"

# Check if system is already running
echo ""
echo -e "${BLUE}Checking for running services...${NC}"

if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Backend already running on port 8000${NC}"
    read -p "Stop existing services? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down 2>/dev/null || true
        echo -e "${GREEN}✓ Stopped${NC}"
    else
        echo -e "${GREEN}✓ Using existing services${NC}"
        exit 0
    fi
fi

# Configuration
echo ""
echo -e "${BLUE}Configuration...${NC}"

if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}Creating .env from template...${NC}"
    cp backend/.env.example backend/.env
    echo -e "${GREEN}✓ .env created (using defaults)${NC}"
    echo ""
    echo "📝 NOTE: To enable full LLM features:"
    echo "   1. Get API key from https://ai.google.dev"
    echo "   2. Edit backend/.env and add:"
    echo "      GEMINI_API_KEY=your_key_here"
    echo "   3. Restart: docker-compose restart backend"
    echo ""
else
    echo -e "${GREEN}✓ .env found${NC}"
fi

# Build and start
echo ""
echo -e "${BLUE}Building and starting services...${NC}"

docker-compose down 2>/dev/null || true
docker-compose up -d --build

# Wait for services
echo ""
echo -e "${BLUE}Waiting for services to start...${NC}"

for i in {1..30}; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠ Backend startup timeout${NC}"
    fi
    echo -n "."
    sleep 1
done

for i in {1..30}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Frontend ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠ Frontend startup timeout${NC}"
    fi
    echo -n "."
    sleep 1
done

# Display info
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║  🎉 SAP O2C Graph System is Ready!               ║"
echo "╠════════════════════════════════════════════════════╣"
echo ""
echo -e "  ${GREEN}Frontend:${NC}  http://localhost:5173"
echo -e "  ${GREEN}Backend:${NC}   http://localhost:8000"
echo -e "  ${GREEN}API Docs:${NC}  http://localhost:8000/docs"
echo ""
echo "╠════════════════════════════════════════════════════╣"
echo ""
echo "📚 Documentation:"
echo "   - README.md          → Project overview"
echo "   - DEPLOYMENT.md      → API reference & deployment"
echo "   - INTEGRATION_TESTS.md → Testing guide"
echo "   - COMPLETION_SUMMARY.md → What's implemented"
echo ""
echo "🚀 Quick Start:"
echo "   1. Open browser: http://localhost:5173"
echo "   2. Click 'Refresh Graph' to load data"
echo "   3. Try a query: 'Which products have highest sales?'"
echo "   4. Click nodes to inspect properties"
echo "   5. Use filters and search to explore"
echo ""
echo "🛑 To Stop:"
echo "   docker-compose down"
echo ""
echo "📋 View Logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f frontend"
echo ""
echo "🧪 Run Tests:"
echo "   ./run_tests.sh"
echo ""
echo "╚════════════════════════════════════════════════════╝"
echo ""

echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "Opening browser... (or visit http://localhost:5173)"

# Try to open browser
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173 2>/dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:5173 2>/dev/null &
else
    echo "Please open http://localhost:5173 in your browser"
fi