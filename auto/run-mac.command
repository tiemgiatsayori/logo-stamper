#!/bin/bash
echo ""
echo "  ========================================"
echo "   Ohara Flower — Logo Stamper"
echo "  ========================================"
echo ""
echo "  Starting... (first run may take a few minutes to download)"
echo ""

docker compose up -d --build 2>/dev/null || docker-compose up -d --build

echo ""
echo "  App is ready! Opening browser..."
echo "  If it doesn't open, go to: http://localhost:7860"
echo ""

sleep 3
open http://localhost:7860 2>/dev/null || xdg-open http://localhost:7860 2>/dev/null
