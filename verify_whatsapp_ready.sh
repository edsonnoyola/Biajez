#!/bin/bash

echo "🔍 VERIFICACIÓN RÁPIDA DEL SISTEMA"
echo "=================================="
echo ""

# Backend
echo "1️⃣  Backend Status:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Backend corriendo en http://localhost:8000"
else
    echo "   ❌ Backend NO responde"
fi
echo ""

# Ngrok
echo "2️⃣  Ngrok Tunnel:"
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
if [ -n "$NGROK_URL" ]; then
    echo "   ✅ Túnel activo: $NGROK_URL"
else
    echo "   ❌ Ngrok NO está corriendo"
fi
echo ""

# WhatsApp Token
echo "3️⃣  WhatsApp Token:"
if grep -q "WHATSAPP_ACCESS_TOKEN" .env 2>/dev/null; then
    echo "   ✅ Token configurado en .env"
else
    echo "   ⚠️  Token no encontrado"
fi
echo ""

echo "=================================="
echo "✅ Sistema listo para probar"
echo ""
echo "📱 PRUEBA RÁPIDA:"
echo "1. Abre WhatsApp"
echo "2. Envía: 'ayuda'"
echo "3. Debe responder con el menú completo"
echo ""
echo "📋 Guía completa: whatsapp_testing_guide.md"
