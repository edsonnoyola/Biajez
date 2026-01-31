#!/bin/bash

echo "🚀 CHECKLIST DE PRODUCCIÓN - Biajez"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Duffel Token
echo "1. Verificando Duffel Token..."
if grep -q "duffel_live_" .env 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Duffel production token configurado"
else
    echo -e "${RED}✗${NC} Duffel en modo TEST"
    echo "   Acción: Obtener production token de https://duffel.com/dashboard"
fi

# Check Amadeus
echo ""
echo "2. Verificando Amadeus..."
if grep -q "AMADEUS_HOSTNAME=production" .env 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Amadeus en modo producción"
else
    echo -e "${YELLOW}⚠${NC} Amadeus en modo test (opcional)"
fi

# Check Database
echo ""
echo "3. Verificando Base de Datos..."
if grep -q "postgresql://" .env 2>/dev/null; then
    echo -e "${GREEN}✓${NC} PostgreSQL configurado"
elif grep -q "sqlite" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} SQLite (cambiar a PostgreSQL para producción)"
else
    echo -e "${RED}✗${NC} Base de datos no configurada"
fi

# Check SSL
echo ""
echo "4. SSL/HTTPS..."
echo -e "${YELLOW}?${NC} Verificar manualmente en tu hosting"

# Check Environment
echo ""
echo "5. Variables de Entorno..."
required_vars=("DUFFEL_ACCESS_TOKEN" "OPENAI_API_KEY" "DATABASE_URL")
for var in "${required_vars[@]}"; do
    if grep -q "$var=" .env 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $var configurado"
    else
        echo -e "${RED}✗${NC} $var faltante"
    fi
done

echo ""
echo "===================================="
echo "📋 PRÓXIMOS PASOS:"
echo ""
echo "1. Obtener Duffel production keys:"
echo "   https://duffel.com/dashboard"
echo ""
echo "2. Configurar método de pago en Duffel"
echo ""
echo "3. Deploy a Render/Railway:"
echo "   - Render: https://render.com"
echo "   - Railway: https://railway.app"
echo ""
echo "4. Hacer reserva de prueba con $50-100"
echo ""
echo "5. Verificar PNR y confirmación"
echo ""
echo "===================================="
