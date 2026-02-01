#!/bin/bash
# Monitor de logs en tiempo real para debug de hoteles

echo "🔍 MONITOR DE LOGS - HOTELES EN WHATSAPP"
echo "========================================"
echo ""
echo "📍 Proceso backend: $(ps aux | grep 'uvicorn app.main:app' | grep -v grep | awk '{print $2}')"
echo "📂 Directorio: $(pwd)"
echo ""
echo "Esperando requests de WhatsApp..."
echo "Envía un mensaje con 'Busca hoteles en [ciudad]'"
echo ""
echo "----------------------------------------"

# Crear archivo temporal para logs si no existe
touch /tmp/biajez_debug.log

# Monitorear tanto stdout como archivos de log
tail -f /tmp/biajez_debug.log backend.log nohup.out 2>/dev/null | grep --line-buffered -E "(hotel|google_hotels|WhatsApp from|Tool Call|DEBUG|ERROR|pending_hotels|HotelEngine)" &

PID=$!
echo "Monitor iniciado (PID: $PID)"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

# Mantener script corriendo
wait $PID
