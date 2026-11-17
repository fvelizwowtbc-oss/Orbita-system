import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   AGREGANDO BOTÓN DE CERRAR SESIÓN AL SCANNER")
    print("==================================================\n")

    p = Path('app/templates/scanner/pantalla.html')
    if not p.exists():
        print("❌ No se encontró scanner/pantalla.html")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.html.bak_logout')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Insertar el botón flotante justo antes de cerrar el <body>
    boton_html = """
    <!-- ✅ BOTÓN FLOTANTE: CERRAR SESIÓN -->
    <a href="{{ url_for('auth.logout') }}" 
       class="fixed bottom-6 right-6 z-[999] flex items-center gap-2 px-4 py-2.5 bg-white/80 backdrop-blur-md border border-slate-200 text-slate-600 hover:text-red-600 hover:bg-white hover:border-red-200 rounded-xl shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 group"
       title="Cerrar Sesión">
        <i class="fas fa-sign-out-alt group-hover:text-red-500"></i>
        <span class="text-sm font-medium">Salir</span>
    </a>
    """

    if '</body>' in c:
        if 'CERRAR SESIÓN' not in c:
            c = c.replace('</body>', boton_html + '\n</body>')
            p.write_text(c, encoding='utf-8')
            print("✅ Botón de cerrar sesión agregado a la pantalla del scanner.")
        else:
            print("⚠️ El botón de cerrar sesión ya existe.")
    else:
        print("❌ No se encontró la etiqueta </body> en el archivo.")

    print("\n👉 Reinicia Flask y recarga la pantalla del scanner con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()