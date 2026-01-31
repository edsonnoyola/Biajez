#!/bin/bash
# Script automático para configurar Amadeus
# Uso: ./setup_amadeus.sh

echo "🔧 CONFIGURACIÓN AUTOMÁTICA DE AMADEUS"
echo "======================================"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f ".env" ]; then
    echo "❌ Error: No se encuentra .env"
    echo "   Ejecuta este script desde /Users/end/Downloads/Biajez"
    exit 1
fi

echo "📝 PASO 1: Registrarse en Amadeus"
echo "--------------------------------"
echo "1. Ve a: https://developers.amadeus.com/register"
echo "2. Completa el formulario:"
echo "   - Email: (tu email)"
echo "   - Nombre completo"
echo "   - Compañía: Biajez Travel"
echo "   - País: México"
echo "3. Verifica tu email"
echo "4. Inicia sesión"
echo ""
read -p "¿Ya completaste el registro? (y/n): " registered

if [ "$registered" != "y" ]; then
    echo "⏸️  Pausa - Completa el registro primero"
    exit 0
fi

echo ""
echo "📝 PASO 2: Crear App y Obtener Keys"
echo "-----------------------------------"
echo "1. En el dashboard, haz clic en 'Create New App'"
echo "2. Nombre: Biajez Travel Platform"
echo "3. Selecciona APIs:"
echo "   ✓ Flight Offers Search"
echo "   ✓ Flight Create Orders"
echo "   ✓ Hotel Search"
echo "   ✓ Hotel Booking"
echo "4. Haz clic en 'Create'"
echo "5. Ve a la pestaña 'App Keys'"
echo ""
echo "Verás dos conjuntos de keys:"
echo "  - Test keys (para desarrollo)"
echo "  - Production keys (para producción)"
echo ""
read -p "¿Ya creaste la app? (y/n): " app_created

if [ "$app_created" != "y" ]; then
    echo "⏸️  Pausa - Crea la app primero"
    exit 0
fi

echo ""
echo "📝 PASO 3: Copiar Keys"
echo "----------------------"
echo "Vamos a usar las PRODUCTION keys (más confiables)"
echo ""
read -p "Pega tu PRODUCTION API Key: " api_key
read -p "Pega tu PRODUCTION API Secret: " api_secret

# Validar que no estén vacías
if [ -z "$api_key" ] || [ -z "$api_secret" ]; then
    echo "❌ Error: Las keys no pueden estar vacías"
    exit 1
fi

echo ""
echo "🔧 PASO 4: Actualizando .env..."

# Backup del .env actual
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup creado: .env.backup.*"

# Actualizar .env
sed -i '' "s/^AMADEUS_CLIENT_ID=.*/AMADEUS_CLIENT_ID=$api_key/" .env
sed -i '' "s/^AMADEUS_CLIENT_SECRET=.*/AMADEUS_CLIENT_SECRET=$api_secret/" .env
sed -i '' "s/^AMADEUS_HOSTNAME=.*/AMADEUS_HOSTNAME=production/" .env

echo "✅ .env actualizado"

echo ""
echo "🧹 PASO 5: Limpiando cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo "✅ Cache limpiado"

echo ""
echo "🧪 PASO 6: Probando conexión..."
python3 << 'PYTHON'
import os
from dotenv import load_dotenv
from amadeus import Client, ResponseError

load_dotenv()

client = Client(
    client_id=os.getenv("AMADEUS_CLIENT_ID"),
    client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
    hostname=os.getenv("AMADEUS_HOSTNAME", "production")
)

print("\n🔍 Probando búsqueda de vuelos...")
try:
    response = client.shopping.flight_offers_search.get(
        originLocationCode='MEX',
        destinationLocationCode='CUN',
        departureDate='2026-01-20',
        adults=1,
        max=5
    )
    print(f"✅ ¡ÉXITO! Encontrados {len(response.data)} vuelos")
    for i, flight in enumerate(response.data[:3], 1):
        price = flight['price']['total']
        currency = flight['price']['currency']
        print(f"   {i}. ${price} {currency}")
    print("\n🎉 AMADEUS CONFIGURADO CORRECTAMENTE")
except ResponseError as error:
    print(f"❌ Error: {error}")
    print("\n⚠️  Las keys pueden tardar hasta 30 minutos en activarse")
    print("   Intenta de nuevo en unos minutos")
except Exception as e:
    print(f"❌ Error inesperado: {e}")
PYTHON

echo ""
echo "✅ CONFIGURACIÓN COMPLETA"
echo "========================"
echo ""
echo "Próximos pasos:"
echo "1. Si viste vuelos arriba, ¡ya está funcionando!"
echo "2. Si dio error, espera 30 minutos y ejecuta:"
echo "   python3 test_amadeus_direct.py"
echo ""
echo "Para reiniciar el servidor:"
echo "   ./restart_servers.sh"
