#!/bin/bash

echo "🔧 CONFIGURAR AMADEUS PRODUCTION KEYS"
echo "======================================"
echo ""

# Ask for keys
read -p "Production Client ID: " CLIENT_ID
read -p "Production Secret: " CLIENT_SECRET

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Error: Debes proporcionar ambas keys"
    exit 1
fi

# Backup
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup creado"

# Update .env
sed -i '' "s/AMADEUS_CLIENT_ID=.*/AMADEUS_CLIENT_ID=$CLIENT_ID/" .env
sed -i '' "s/AMADEUS_CLIENT_SECRET=.*/AMADEUS_CLIENT_SECRET=$CLIENT_SECRET/" .env
sed -i '' "s/AMADEUS_HOSTNAME=.*/AMADEUS_HOSTNAME=production/" .env

echo "✅ Keys actualizadas en .env"
echo ""

# Verify
echo "📋 Verificando configuración..."
grep "AMADEUS_CLIENT_ID" .env
grep "AMADEUS_HOSTNAME" .env

echo ""
echo "🔄 Reiniciando backend..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 2
python3 -m uvicorn app.main:app --port 8000 &

echo ""
echo "✅ CONFIGURACIÓN COMPLETA"
echo ""
echo "📝 Próximos pasos:"
echo "1. Espera 5 segundos"
echo "2. Ejecuta: python3 test_amadeus_production.py"
echo "3. Verifica que funcione"
echo ""
