#!/bin/bash
# Reinicia SOLO el backend (sin ngrok ni frontend)

echo "🔄 Reiniciando SOLO backend..."

# Matar proceso backend en puerto 8000
echo "🛑 Deteniendo backend..."
lsof -ti:8000 | xargs kill -9 2>/dev/null

sleep 2

# Limpiar cache
echo "🧹 Limpiando cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Iniciar backend
echo "🚀 Iniciando backend con nuevo token..."
python3 -m uvicorn app.main:app --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

sleep 3

# Verificar backend
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "✅ Backend corriendo en http://localhost:8000"
    echo "✅ Nuevo token cargado correctamente"
    echo ""
    echo "📱 PRUEBA AHORA:"
    echo "   Envía 'Hola' al bot por WhatsApp"
else
    echo "❌ Error iniciando backend"
    cat backend.log
    exit 1
fi
