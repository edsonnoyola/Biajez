#!/usr/bin/env python3

# Leer el archivo original
with open('/Users/end/Desktop/Biajez/frontend/src/components/FlightCard.tsx', 'r') as f:
    lines = f.readlines()

# Encontrar la última línea de import
last_import_line = 0
for i, line in enumerate(lines):
    if line.strip().startswith('import'):
        last_import_line = i

# Insertar el import de FlexibilityBadge después del último import
if last_import_line > 0:
    lines.insert(last_import_line + 1, "import { FlexibilityBadge } from './FlexibilityBadge';\n")

# Guardar
with open('/Users/end/Desktop/Biajez/frontend/src/components/FlightCard.tsx', 'w') as f:
    f.writelines(lines)

print("✅ Import agregado correctamente")
print("⚠️  Nota: Solo agregué el import. El badge visual lo agregarás manualmente.")
