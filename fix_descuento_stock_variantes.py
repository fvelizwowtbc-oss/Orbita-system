import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   CORRIGIENDO DESCUENTO DE STOCK EN VARIANTES")
    print("==================================================\n")

    p = Path('app/services/ventas.py')
    if not p.exists():
        print("❌ No se encontró services/ventas.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_stock_variantes')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar el bloque donde se descuenta el stock del producto
    patron = re.compile(
        r"(\s*# Descontar stock del producto.*?)(\n\s*venta = Venta\()",
        re.DOTALL
    )

    match = patron.search(c)
    if not match:
        print("❌ No se encontró el bloque de descuento de stock en ventas.py")
        return

    nuevo_bloque = """
                # Descontar stock del producto (padre)
                from decimal import Decimal
                
                # Si es carnicería/charcutería, descontar decimales. Si no, convertir a entero.
                es_peso = producto.categoria in ('Carniceria', 'Charcuteria')
                
                if es_peso:
                    cantidad_a_descontar = Decimal(str(cant))
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - cantidad_a_descontar
                else:
                    cantidad_a_descontar = int(cant)
                    producto.stock_actual = int(producto.stock_actual or 0) - cantidad_a_descontar

                # ✅ Descontar stock de la VARIANTE si aplica
                variante_id_venta = item.get('variante_id')
                if variante_id_venta:
                    from ..models.producto import ProductoVariante
                    variante = ProductoVariante.query.filter_by(id=variante_id_venta, producto_id=pid).first()
                    if variante:
                        if es_peso:
                            variante.stock_actual = Decimal(str(variante.stock_actual or 0)) - Decimal(str(cant))
                        else:
                            variante.stock_actual = int(variante.stock_actual or 0) - int(cant)
            """

    c = c.replace(match.group(1), nuevo_bloque)
    p.write_text(c, encoding='utf-8')
    print("✅ services/ventas.py: Ahora descuenta stock del producto Y de la variante.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py).")
    print("Prueba vendiendo un producto con variantes y verifica que el stock de la variante también baje.")

if __name__ == '__main__':
    main()