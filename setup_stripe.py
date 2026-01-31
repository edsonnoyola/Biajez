#!/usr/bin/env python3
"""
Interactive Stripe Configuration Script
Helps you set up Stripe keys for the application
"""
import os
import re

def print_header():
    print("\n" + "="*60)
    print("  🎨 STRIPE CONFIGURATION WIZARD")
    print("="*60 + "\n")

def print_section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}\n")

def get_stripe_keys():
    """Guide user to get Stripe keys"""
    print_section("📋 Paso 1: Obtener Stripe Keys")
    
    print("Para obtener tus Stripe keys:")
    print("1. Ve a: https://dashboard.stripe.com/login")
    print("2. Inicia sesión (o crea cuenta si no tienes)")
    print("3. Ve a: Developers → API keys")
    print("4. Asegúrate de estar en modo 'Test' (toggle arriba)")
    print("5. Copia las keys:\n")
    
    print("   📌 Publishable key (empieza con pk_test_...)")
    print("   📌 Secret key (click 'Reveal test key', empieza con sk_test_...)\n")
    
    input("Presiona ENTER cuando tengas las keys listas...")

def configure_backend():
    """Configure backend .env file"""
    print_section("🔧 Paso 2: Configurar Backend")
    
    print("Ingresa tu Stripe SECRET KEY (sk_test_...):")
    secret_key = input("Secret Key: ").strip()
    
    print("\nIngresa tu Stripe PUBLISHABLE KEY (pk_test_...):")
    publishable_key = input("Publishable Key: ").strip()
    
    # Validate keys
    if not secret_key.startswith('sk_test_') and not secret_key.startswith('sk_live_'):
        print("⚠️  Advertencia: La secret key no parece válida")
        if input("¿Continuar de todos modos? (y/n): ").lower() != 'y':
            return False
    
    if not publishable_key.startswith('pk_test_') and not publishable_key.startswith('pk_live_'):
        print("⚠️  Advertencia: La publishable key no parece válida")
        if input("¿Continuar de todos modos? (y/n): ").lower() != 'y':
            return False
    
    # Read current .env
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    else:
        env_content = ""
    
    # Update or add Stripe keys
    if 'STRIPE_SECRET_KEY=' in env_content:
        env_content = re.sub(
            r'STRIPE_SECRET_KEY=.*',
            f'STRIPE_SECRET_KEY={secret_key}',
            env_content
        )
    else:
        env_content += f'\nSTRIPE_SECRET_KEY={secret_key}\n'
    
    if 'STRIPE_PUBLISHABLE_KEY=' in env_content:
        env_content = re.sub(
            r'STRIPE_PUBLISHABLE_KEY=.*',
            f'STRIPE_PUBLISHABLE_KEY={publishable_key}',
            env_content
        )
    else:
        env_content += f'STRIPE_PUBLISHABLE_KEY={publishable_key}\n'
    
    # Write back
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f"\n✅ Backend .env actualizado")
    
    return publishable_key

def configure_frontend(publishable_key):
    """Configure frontend .env file"""
    print_section("🎨 Paso 3: Configurar Frontend")
    
    frontend_env_path = 'frontend/.env'
    
    # Create or update frontend .env
    env_content = f'VITE_STRIPE_PUBLISHABLE_KEY={publishable_key}\n'
    
    with open(frontend_env_path, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Frontend .env creado/actualizado")

def update_app_tsx(publishable_key):
    """Update App.tsx to use environment variable"""
    print_section("📝 Paso 4: Actualizar App.tsx")
    
    app_tsx_path = 'frontend/src/App.tsx'
    
    if not os.path.exists(app_tsx_path):
        print("⚠️  App.tsx no encontrado, saltando...")
        return
    
    with open(app_tsx_path, 'r') as f:
        content = f.read()
    
    # Replace hardcoded key with environment variable
    updated_content = re.sub(
        r"loadStripe\('pk_test_[^']+'\)",
        f"loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || '{publishable_key}')",
        content
    )
    
    # Also update the TODO comment
    updated_content = re.sub(
        r'// TODO: Replace with your actual Stripe publishable key.*\n',
        '// Stripe publishable key from environment variable\n',
        updated_content
    )
    
    with open(app_tsx_path, 'w') as f:
        f.write(updated_content)
    
    print("✅ App.tsx actualizado para usar variable de entorno")

def restart_instructions():
    """Show restart instructions"""
    print_section("🔄 Paso 5: Reiniciar Servidores")
    
    print("Para aplicar los cambios, reinicia ambos servidores:\n")
    print("Backend:")
    print("  1. Presiona Ctrl+C en la terminal del backend")
    print("  2. Ejecuta: python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n")
    print("Frontend:")
    print("  1. Presiona Ctrl+C en la terminal del frontend")
    print("  2. Ejecuta: cd frontend && npm run dev\n")

def test_instructions():
    """Show testing instructions"""
    print_section("🧪 Paso 6: Probar Pagos")
    
    print("Tarjeta de prueba para pagos exitosos:\n")
    print("  Número: 4242 4242 4242 4242")
    print("  Fecha: 12/34 (cualquier fecha futura)")
    print("  CVC: 123 (cualquier 3 dígitos)")
    print("  ZIP: 12345 (cualquier código)\n")
    print("Más tarjetas de prueba: https://stripe.com/docs/testing\n")

def main():
    print_header()
    
    print("Este script te ayudará a configurar Stripe en tu aplicación.\n")
    print("Necesitarás:")
    print("  • Cuenta de Stripe (gratis)")
    print("  • Test API keys de Stripe\n")
    
    if input("¿Continuar? (y/n): ").lower() != 'y':
        print("\n❌ Configuración cancelada")
        return
    
    # Step 1: Guide to get keys
    get_stripe_keys()
    
    # Step 2: Configure backend
    publishable_key = configure_backend()
    if not publishable_key:
        print("\n❌ Configuración cancelada")
        return
    
    # Step 3: Configure frontend
    configure_frontend(publishable_key)
    
    # Step 4: Update App.tsx
    update_app_tsx(publishable_key)
    
    # Step 5: Restart instructions
    restart_instructions()
    
    # Step 6: Testing instructions
    test_instructions()
    
    print_section("✅ CONFIGURACIÓN COMPLETA")
    print("Stripe está configurado correctamente!")
    print("Reinicia los servidores y prueba hacer un pago.\n")
    print("📖 Para más información, consulta: STRIPE_SETUP.md\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuración cancelada por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
