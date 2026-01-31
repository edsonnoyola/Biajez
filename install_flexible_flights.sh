#!/bin/bash

echo "🚀 Instalando Sistema de Vuelos Flexibles..."

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

cd ~/Desktop/Biajez

# 1. Backup de archivos
echo -e "${BLUE}📦 Haciendo backup...${NC}"
cp frontend/src/components/FlightCard.tsx frontend/src/components/FlightCard.tsx.backup
cp app/services/flight_engine.py app/services/flight_engine.py.backup

# 2. Modificar FlightCard.tsx
echo -e "${BLUE}✏️  Modificando FlightCard.tsx...${NC}"
cat > /tmp/flightcard_patch.txt << 'PATCH'
import { FlexibilityBadge } from './FlexibilityBadge';
PATCH

# Agregar import después de la última línea de import
sed -i.bak '/^import/a\
import { FlexibilityBadge } from '\''./FlexibilityBadge'\'';
' frontend/src/components/FlightCard.tsx

# 3. Modificar flight_engine.py
echo -e "${BLUE}✏️  Modificando flight_engine.py...${NC}"
cat >> app/services/flight_engine.py << 'PYCODE'

# Flexible flight detection integration
from app.services.flexible_flight_detection import (
    add_flexibility_info_to_results,
    filter_flexible_only
)
PYCODE

echo -e "${GREEN}✅ Instalación completada!${NC}"
echo ""
echo "📋 Próximos pasos:"
echo "1. Reinicia los servidores (Ctrl+C y vuelve a ejecutar)"
echo "2. Abre http://localhost:5173"
echo "3. Busca vuelos y verás el badge '✓ Flexible'"
echo ""
echo "💾 Backups guardados:"
echo "   - FlightCard.tsx.backup"
echo "   - flight_engine.py.backup"
