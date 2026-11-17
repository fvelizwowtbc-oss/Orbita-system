import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   BLOQUEANDO ACCESO DE SCANNER A OTRAS RUTAS")
    print("==================================================\n")

    p = Path('app/__init__.py')
    if not p.exists():
        print("❌ No se encontró app/__init__.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_scanner_block')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Verificar si ya está el bloque
    if 'current_user.es_scanner' in c and 'bloquear_scanner' in c:
        print("✅ El bloqueo de rutas para Scanner ya existe.")
        return

    # Inyectar el bloque antes del 'return app' en create_app
    bloque_scanner = """
    # ============================================================
    # ✅ BLOQUEO DE RUTAS PARA USUARIOS TIPO SCANNER
    # ============================================================
    from flask import request, redirect, url_for
    from flask_login import current_user
    from flask import flash

    @app.before_request
    def bloquear_scanner():
        if not current_user.is_authenticated:
            return None
            
        if not getattr(current_user, 'es_scanner', False):
            return None
            
        # Lista de rutas permitidas para scanner
        allowed_endpoints = [
            'scanner.pantalla',
            'scanner.buscar',
            'auth.logout',
            'static',
        ]
        
        if request.endpoint not in allowed_endpoints:
            flash('No tienes acceso a esta sección.', 'warning')
            return redirect(url_for('scanner.pantalla'))
            
        return None
"""

    # Buscar el lugar donde está el 'return app' al final de create_app
    if 'return app' in c:
        # Buscar la última aparición de 'return app' (la que cierra create_app)
        # Usualmente está antes de la definición de otras funciones como _setup_logging
        idx = c.rfind('    return app')
        if idx != -1:
            c = c[:idx] + bloque_scanner + '\n' + c[idx:]
            p.write_text(c, encoding='utf-8')
            print("✅ app/__init__.py: Bloqueo de rutas para Scanner instalado.")
        else:
            print("⚠️ No se encontró 'return app' con indentación. Buscando 'return app' simple...")
            idx = c.rfind('return app')
            if idx != -1:
                c = c[:idx] + bloque_scanner + '\n' + c[idx:]
                p.write_text(c, encoding='utf-8')
                print("✅ app/__init__.py: Bloqueo instalado (método alternativo).")
            else:
                print("❌ No se encontró 'return app' en el archivo.")
    else:
        print("❌ No se encontró 'return app' en el archivo.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) e intenta entrar a /user/dashboard como scanner.")
    print("Debería redirigirte a la pantalla del scanner.")

if __name__ == '__main__':
    main()