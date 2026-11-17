import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   HACIENDO INDEPENDIENTES LOS CAMPOS DEL ARQUEO")
    print("==================================================\n")

    # 1. ACTUALIZAR EL HTML DEL VENDEDOR (vendedor/caja.html)
    p_vend = Path('app/templates/vendedor/caja.html')
    if p_vend.exists():
        c = p_vend.read_text(encoding='utf-8')
        bak = p_vend.with_suffix('.html.bak_arqueo_indep')
        if not bak.exists(): shutil.copy2(p_vend, bak)

        # Quitar el oninput que hace la conversión
        c = c.replace('oninput="calcularBs()"', '')
        c = c.replace('oninput="calcularUsd()"', '')
        
        # Eliminar las funciones de conversión del script
        c = re.sub(r'function calcularBs\(\).*?\}\n', '', c, flags=re.DOTALL)
        c = re.sub(r'function calcularUsd\(\).*?\}\n', '', c, flags=re.DOTALL)
        
        # Eliminar la tasa de cálculo si queda suelta
        c = c.replace('const TASA_CALCULO = {{ tasas.oficial if tasas and tasas.oficial else 50 }};', '')

        p_vend.write_text(c, encoding='utf-8')
        print("✅ vendedor/caja.html: Campos de USD y Bs ahora son independientes.")

    # 2. ACTUALIZAR EL HTML DEL USUARIO (user/caja.html)
    p_user = Path('app/templates/user/caja.html')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        bak = p_user.with_suffix('.html.bak_arqueo_indep')
        if not bak.exists(): shutil.copy2(p_user, bak)

        # Quitar el oninput
        c = c.replace('oninput="calcularBs()"', '')
        c = c.replace('oninput="calcularUsd()"', '')
        
        # Eliminar funciones
        c = re.sub(r'function calcularBs\(\).*?\}\n', '', c, flags=re.DOTALL)
        c = re.sub(r'function calcularUsd\(\).*?\}\n', '', c, flags=re.DOTALL)
        
        c = c.replace('const TASA_CALCULO = {{ tasas.oficial if tasas and tasas.oficial else 50 }};', '')

        p_user.write_text(c, encoding='utf-8')
        print("✅ user/caja.html: Campos de USD y Bs ahora son independientes.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()