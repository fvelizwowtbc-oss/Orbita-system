import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   MOSTRANDO PRECIO DE VARIANTES EN VENTAS")
    print("==================================================\n")

    # 1. ACTUALIZAR LA RUTA DEL USUARIO (user.py) para enviar el precio mínimo
    p_user_routes = Path('app/routes/user.py')
    if p_user_routes.exists():
        c = p_user_routes.read_text(encoding='utf-8')
        bak = p_user_routes.with_suffix('.py.bak_precio_var')
        if not bak.exists(): shutil.copy2(p_user_routes, bak)

        # En la función ventas(), después de obtener los productos, añadir lógica de precio
        # Pero es mejor hacerlo en el template con Jinja para no tocar el backend.
        pass

    # 2. ACTUALIZAR EL TEMPLATE DE VENTAS (user/ventas.html y vendedor/ventas.html)
    for ventas_file in ['app/templates/user/ventas.html', 'app/templates/vendedor/ventas.html']:
        p_v = Path(ventas_file)
        if p_v.exists():
            c = p_v.read_text(encoding='utf-8')
            bak = p_v.with_suffix('.html.bak_precio_var')
            if not bak.exists(): shutil.copy2(p_v, bak)

            # Buscar el bloque donde se muestra el precio del producto
            old_precio = """                        <span class="font-bold {% if tiene_variantes %}text-[#787FF6]{% else %}text-[#0f172a]{% endif %}">
                            ${{ "%.2f"|format(p.precio_venta_usd) }}
                        </span>"""
            
            new_precio = """                        <span class="font-bold {% if tiene_variantes %}text-[#787FF6]{% else %}text-[#0f172a]{% endif %}">
                            {% if tiene_variantes %}
                                {% set precios_variantes = p.variantes.all() | map(attribute='precio_venta_efectivo') | list %}
                                {% if precios_variantes %}
                                    {% set precio_min = precios_variantes | min %}
                                    ${{ "%.2f"|format(precio_min) }}
                                    <span class="text-[10px] font-normal opacity-70">(desde)</span>
                                {% else %}
                                    ${{ "%.2f"|format(p.precio_venta_usd) }}
                                {% endif %}
                            {% else %}
                                ${{ "%.2f"|format(p.precio_venta_usd) }}
                            {% endif %}
                        </span>"""
            
            if old_precio in c:
                c = c.replace(old_precio, new_precio)
                
                # También mostrar "Ver variantes" en lugar de "Click para elegir variante"
                c = c.replace(
                    '<i class="fas fa-mouse-pointer mr-1"></i>Click para elegir variante',
                    '<i class="fas fa-list-ul mr-1"></i>Ver variantes'
                )
                
                p_v.write_text(c, encoding='utf-8')
                print(f"✅ {ventas_file}: Precio de variantes mostrado (mínimo).")
            else:
                print(f"⚠️ No se encontró el bloque de precio en {ventas_file}.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página de Ventas con Ctrl + Shift + R.")
    print("Ahora los productos con variantes mostrarán el precio más bajo de sus variantes con la etiqueta '(desde)'.")

if __name__ == '__main__':
    main()