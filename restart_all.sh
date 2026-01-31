#!/bin/bash

echo "🔄 REINICIANDO TODO EL SISTEMA"
echo "================================"

# Kill everything
echo "1. Matando procesos..."
pkill -9 -f vite 2>/dev/null
pkill -9 -f uvicorn 2>/dev/null
pkill -9 -f node 2>/dev/null
sleep 2

# Clean cache
echo "2. Limpiando cache..."
cd /Users/end/Downloads/Biajez/frontend
rm -rf node_modules/.vite
rm -rf dist
rm -rf .vite

# Start backend
echo "3. Iniciando backend..."
cd /Users/end/Downloads/Biajez
python3 -m uvicorn app.main:app --port 8000 --reload &
BACKEND_PID=$!
sleep 3

# Start frontend
echo "4. Iniciando frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
sleep 5

echo ""
echo "================================"
echo "✅ SISTEMA REINICIADO"
echo "================================"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "URLs:"
echo "  Frontend: http://localhost:5173 o http://localhost:5174"
echo "  Backend:  http://localhost:8000"
echo ""
echo "Para ver logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
