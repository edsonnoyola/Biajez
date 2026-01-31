#!/bin/bash

echo "🔄 Reiniciando Biajez..."

# 1. Kill backend if running
echo "1. Deteniendo backend..."
pkill -f "uvicorn app.main:app" || echo "  (no estaba corriendo)"

# 2. Kill frontend if running
echo "2. Deteniendo frontend..."
pkill -f "vite" || echo "  (no estaba corriendo)"

# 3. Start backend in background
echo "3. Iniciando backend..."
cd /Users/end/Downloads/Biajez
source .venv/bin/activate 2>/dev/null || echo "  (usando Python global)"
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# 4. Rebuild frontend
echo "4. Reconstruyendo frontend..."
cd frontend
npm run build
echo "  Build completo"

# 5. Start frontend in background
echo "5. Iniciando frontend..."
nohup npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wait for frontend to start
sleep 3

echo ""
echo "✅ Servicios iniciados:"
echo "  - Backend: http://localhost:8000 (PID: $BACKEND_PID)"
echo "  - Frontend: http://localhost:5173 (PID: $FRONTEND_PID)"
echo ""
echo "📋 Para ver logs:"
echo "  - Backend: tail -f /Users/end/Downloads/Biajez/backend.log"
echo "  - Frontend: tail -f /Users/end/Downloads/Biajez/frontend.log"
echo ""
echo "🧪 Ejecutando prueba de MEX-CUN..."
cd /Users/end/Downloads/Biajez
python3 test_duffel_mex_cun.py

echo ""
echo "🎯 Ahora abre http://localhost:5173 y prueba: 'Vuelo de México a Cancún'"
