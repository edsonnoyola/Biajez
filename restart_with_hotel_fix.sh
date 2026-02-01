#!/bin/bash
# Script para reiniciar solo el backend después de fix de hoteles

echo "🔄 Reiniciando backend con fix de hoteles..."

# Matar proceso existente
pkill -f "uvicorn app.main:app"

# Esperar un momento
sleep 2

# Iniciar backend
echo "🚀 Iniciando backend..."
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &

echo "✅ Backend reiniciado con soporte de hoteles en WhatsApp"
echo ""
echo "Para probar, envía a WhatsApp:"
echo '  "Busca hoteles en Cancún del 15 al 18 de febrero"'
echo ""
