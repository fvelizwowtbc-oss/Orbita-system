import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   MEJORANDO VISTA DE VARIANTES EN EL INVENTARIO")
    print("==================================================\n")

    # 1. ACTUALIZAR EL HTML DEL INVENTARIO DEL USUARIO
    p_html = Path('app/templates/user/inventario.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_variantes_visual')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # Buscar el bloque donde se muestran las variantes
        patron = re.compile(
            r'<div class="mt-2 flex flex-wrap gap-1 variantes-lista">.*?</div>\s*{% endif %}',
            re.DOTALL
        )

        nuevo_bloque = """<div class="mt-3 flex flex-wrap gap-1.5 variantes-lista">
                                    {% for v in variantes_producto %}
                                    {% set color_stock = 'bg-red-100 text-red-700 border-red-200' if v.stock_actual == 0 else ('bg-amber-100 text-amber-700 border-amber-200' if v.stock_actual <= v.stock_minimo else 'bg-emerald-100 text-emerald-700 border-emerald-200') %}
                                    <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border {{ color_stock }} shadow-sm" 
                                         title="Variante: {{ v.nombre }}&#10;Codigo: {{ v.codigo or 'N/A' }}&#10;Stock: {{ v.stock_actual }}&#10;Precio: ${{ '%.2f'|format(v.precio_venta_efectivo) }}">
                                        <i class="fas fa-tag opacity-70"></i>
                                        <span class="truncate max-w-[100px]">{{ v.nombre }}</span>
                                        <span class="font-bold ml-1">{{ v.stock_actual }}</span>
                                        <span class="opacity-75 text-[10px] ml-0.5">(${{ '%.2f'|format(v.precio_venta_efectivo) }})</span>
                                    </div>
                                    {% endfor %}
                                </div>
                                {% endif %}"""

        if patron.search(c):
            c = patron.sub(nuevo_bloque, c)
            p_html.write_text(c, encoding='utf-8')
            print("✅ user/inventario.html: Vista de variantes mejorada (colores por stock).")
        else:
            print("⚠️ No se encontró el bloque exacto en user/inventario.html.")

    # 2. ACTUALIZAR EL HTML DEL INVENTARIO DEL VENDEDOR (por si acaso)
    p_vend_html = Path('app/templates/vendedor/inventario.html')
    if p_vend_html.exists():
        c = p_vend_html.read_text(encoding='utf-8')
        bak = p_vend_html.with_suffix('.html.bak_variantes_visual')
        if not bak.exists(): shutil.copy2(p_vend_html, bak)

        patron_vend = re.compile(
            r'<div class="mt-2 flex flex-wrap gap-1 variantes-lista">.*?</div>\s*{% endif %}',
            re.DOTALL
        )

        if patron_vend.search(c):
            c = patron_vend.sub(nuevo_bloque, c)
            p_vend_html.write_text(c, encoding='utf-8')
            print("✅ vendedor/inventario.html: Vista de variantes mejorada.")
        else:
            print("⚠️ No se encontró el bloque exacto en vendedor/inventario.html.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga el Inventario con Ctrl + Shift + R.")
    print("Ahora las variantes mostrarán colores según su stock y será más fácil diferenciar cuál está agotada o por agotarse.")

if __name__ == '__main__':
    main()