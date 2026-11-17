from pathlib import Path
import shutil

def main():
    print("\n==================================================")
    print("   CORRIGIENDO DESCUENTO DE VARIANTE (DEFINITIVO)")
    print("==================================================\n")

    p = Path('app/services/ventas.py')
    if not p.exists():
        print("❌ No se encontró ventas.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_variante_def')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar el bloque exacto de descuento de stock (el que vimos en el archivo)
    old_block = """                # Descontar stock
                
                from decimal import Decimal
                if producto.categoria in ('Carniceria', 'Charcuteria'):
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - Decimal(str(cant))
                else:
                    producto.stock_actual = int(producto.stock_actual or 0) - int(cant)"""

    new_block = """                # Descontar stock del producto
                from decimal import Decimal
                es_peso = producto.categoria in ('Carniceria', 'Charcuteria')
                
                if es_peso:
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - Decimal(str(cant))
                else:
                    producto.stock_actual = int(producto.stock_actual or 0) - int(cant)

                # ✅ Descontar stock de la variante si aplica
                variante_id_venta = item.get('variante_id')
                if variante_id_venta:
                    from ..models.producto import ProductoVariante
                    variante = ProductoVariante.query.filter_by(id=variante_id_venta, producto_id=pid).first()
                    if variante:
                        if es_peso:
                            variante.stock_actual = Decimal(str(variante.stock_actual or 0)) - Decimal(str(cant))
                        else:
                            variante.stock_actual = int(variante.stock_actual or 0) - int(cant)"""

    if old_block in c:
        c = c.replace(old_block, new_block)
        p.write_text(c, encoding='utf-8')
        print("✅ ventas.py: Descuento de variante agregado correctamente.")
    else:
        print("⚠️ No se encontró el bloque exacto. Buscando variante...")
        
        # Intentar con otra variante (sin el salto de línea extra)
        old_block2 = """                # Descontar stock
                
                from decimal import Decimal
                if producto.categoria in ('Carniceria', 'Charcuteria'):
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - Decimal(str(cant))
                else:
                    producto.stock_actual = int(producto.stock_actual or 0) - int(cant)"""
        
        if old_block2 in c:
            c = c.replace(old_block2, new_block)
            p.write_text(c, encoding='utf-8')
            print("✅ ventas.py: Descuento de variante agregado (método alternativo).")
        else:
            # Si aún falla, buscar la línea exacta y reemplazarla
            print("⚠️ No se encontró el bloque exacto. Buscando la línea de descuento...")
            
            # Buscar la línea donde se descuenta el stock
            lines = c.split('\n')
            found = False
            for i, line in enumerate(lines):
                if 'producto.stock_actual' in line and '-=' in line:
                    print(f"  Encontrada línea: {line.strip()}")
                    # Obtener la indentación
                    indent = line[:len(line) - len(line.lstrip())]
                    
                    # Construir el bloque de variante
                    variante_code = f"""{line}
{indent}# ✅ Descontar stock de la variante si aplica
{indent}variante_id_venta = item.get('variante_id')
{indent}if variante_id_venta:
{indent}    from ..models.producto import ProductoVariante
{indent}    variante = ProductoVariante.query.filter_by(id=variante_id_venta, producto_id=pid).first()
{indent}    if variante:
{indent}        if es_peso:
{indent}            variante.stock_actual = Decimal(str(variante.stock_actual or 0)) - Decimal(str(cant))
{indent}        else:
{indent}            variante.stock_actual = int(variante.stock_actual or 0) - int(cant)"""
                    
                    lines[i] = variante_code
                    found = True
                    break
            
            if found:
                c = '\n'.join(lines)
                p.write_text(c, encoding='utf-8')
                print("✅ ventas.py: Descuento de variante agregado (método manual).")
            else:
                print("❌ No se encontró ninguna línea de descuento de stock.")

    # Verificar que el bloque está en el archivo
    c = p.read_text(encoding='utf-8')
    if 'Descontar stock de la variante' in c:
        print("✅ Verificación exitosa: El bloque de descuento de variante está en el archivo.")
    else:
        print("⚠️ Advertencia: No se pudo verificar el bloque.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py).")
    print("Prueba vendiendo un producto con variantes y verifica que el stock de la variante también baje.")

if __name__ == '__main__':
    main()