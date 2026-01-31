#!/bin/bash
# Reinicia todos los servidores

echo "🔄 Reiniciando servidores..."

# Matar procesos existentes
echo "🛑 Deteniendo procesos..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null

sleep 2

# Limpiar cache
echo "🧹 Limpiando cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Iniciar backend
echo "🚀 Iniciando backend..."
python3 -m uvicorn app.main:app --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

sleep 3

# Verificar backend
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "✅ Backend corriendo en http://localhost:8000"
else
    echo "❌ Error iniciando backend"
    cat backend.log
    exit 1
fi

# Iniciar frontend
echo "🚀 Iniciando frontend..."
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Iniciar ngrok
echo "🚀 Iniciando ngrok..."
ngrok http 8000 > ngrok.log 2>&1 &

sleep 5

echo ""
echo "✅ SERVIDORES INICIADOS"
echo "======================"
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5174"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "Para detener:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
