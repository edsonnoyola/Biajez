#!/usr/bin/env python3

# Leer FlightCard.tsx
with open('/Users/end/Desktop/Biajez/frontend/src/components/FlightCard.tsx', 'r') as f:
    lines = f.readlines()

# Buscar las líneas de origin y destination
new_lines = []
skip_next = False

for i, line in enumerate(lines):
    if skip_next:
        skip_next = False
        continue
        
    # Si encontramos la línea de origin, reemplazar origin y destination juntas
    if 'const origin = flight.slices[0].segments[0].origin' in line:
        # Agregar el código corregido
        indent = len(line) - len(line.lstrip())
        new_lines.append(' ' * indent + '// Fix: Mostrar solo el primer slice (vuelo de ida)\n')
        new_lines.append(' ' * indent + 'const firstSlice = flight.slices[0];\n')
        new_lines.append(' ' * indent + 'const origin = firstSlice.segments[0].origin.iata_code;\n')
        new_lines.append(' ' * indent + 'const destination = firstSlice.segments[firstSlice.segments.length - 1].destination.iata_code;\n')
        
        # Saltar la siguiente línea si es la de destination
        if i + 1 < len(lines) and 'const destination' in lines[i + 1]:
            skip_next = True
    elif 'const destination' in line and 'flight.slices' in line:
        # Si encontramos destination sola, saltarla (ya la agregamos arriba)
        continue
    else:
        new_lines.append(line)

# Guardar
with open('/Users/end/Desktop/Biajez/frontend/src/components/FlightCard.tsx', 'w') as f:
    f.writelines(new_lines)

print("✅ Fix aplicado!")
print("🔄 El servidor debería recargar automáticamente")
print("🧪 Recarga http://localhost:5173 y busca vuelos de nuevo")
