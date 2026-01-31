#!/bin/bash

echo "🚀 Preparando para Producción - Paso 3"
echo "======================================"
echo ""

# Create .env.production
echo "📝 Creando .env.production..."
cp .env .env.production

echo "✅ Archivo .env.production creado"
echo ""

echo "📋 SIGUIENTE PASO:"
echo ""
echo "1. Edita .env.production cuando tengas production keys:"
echo "   nano .env.production"
echo ""
echo "2. Cambia esta línea:"
echo "   DUFFEL_ACCESS_TOKEN=duffel_live_XXXXXXXXXX"
echo ""
echo "3. Mientras tanto, solicita production access en:"
echo "   https://duffel.com/dashboard"
echo ""
echo "======================================"
