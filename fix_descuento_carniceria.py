import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   FORZANDO DESCUENTO DECIMAL EN CARNICERÍA")
    print("==================================================\n")

    p = Path('app/services/ventas.py')
    if not p.exists():
        print("❌ No se encontró services/ventas.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_descuento_carn')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Buscar el bloque donde se procesan los items (el for)
    # Y asegurarnos de que 'cant' se maneje como decimal si es carnicería.

    # El código actual suele hacer: cant = int(item['cantidad'])
    old_cant = "cant = int(item['cantidad'])"
    
    # Queremos: si el producto es de carnicería, cant = float(item['cantidad'])
    # Pero como no sabemos si es carnicería hasta buscar el producto, 
    # primero dejamos cant como float y luego redondeamos según el producto.
    
    # Estrategia: 
    # 1. Cambiar cant = int(...) por cant = float(...)
    # 2. Al descontar el stock, si NO es carnicería, convertir a int.
    
    new_cant = "cant = float(item['cantidad'])" # Ahora es float

    if old_cant in c:
        c = c.replace(old_cant, new_cant)
        print("✅ Cantidad ahora se lee como float (para soportar gramos).")
    else:
        print("⚠️ No se encontró 'cant = int(item['cantidad'])'. Buscando variante...")
        if "cant = item.get('cantidad')" in c:
            c = c.replace("cant = item.get('cantidad')", "cant = float(item.get('cantidad'))")

    # 2. Arreglar la lógica de descuento de stock
    # Buscamos el bloque donde descuenta
    patron_descuento = re.compile(
        r"(\s*# Descontar stock del producto\s*\n.*?)(\n\s*# Descontar stock de la variante|\n\s*venta = Venta\()",
        re.DOTALL
    )

    nuevo_descuento = """
                # Descontar stock del producto
                from decimal import Decimal
                
                # Si es carnicería, descontar decimales. Si no, convertir a entero.
                if producto.categoria == 'Carniceria':
                    cantidad_a_descontar = Decimal(str(cant))
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - cantidad_a_descontar
                else:
                    cantidad_a_descontar = int(cant)
                    producto.stock_actual = int(producto.stock_actual or 0) - cantidad_a_descontar
"""

    if patron_descuento.search(c):
        c = patron_descuento.sub(nuevo_descuento, c, count=1)
        p.write_text(c, encoding='utf-8')
        print("✅ services/ventas.py: Lógica de descuento actualizada (Carnicería usa Decimal).")
    else:
        print("⚠️ No se encontró el bloque de descuento exacto. Intentando reemplazo de línea...")
        
        # Si no encuentra el bloque, forzamos la línea de descuento
        old_line = "producto.stock_actual -= cant"
        new_line = """
                from decimal import Decimal
                if producto.categoria == 'Carniceria':
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - Decimal(str(cant))
                else:
                    producto.stock_actual = int(producto.stock_actual or 0) - int(cant)"""
        
        if old_line in c:
            c = c.replace(old_line, new_line)
            p.write_text(c, encoding='utf-8')
            print("✅ services/ventas.py: Descuento de stock corregido (método alternativo).")
        else:
            print("❌ No se pudo encontrar la línea de descuento de stock.")

    # 3. Arreglar el registro de la Venta (por si intenta guardar cant como int)
    # Buscar: cantidad=cant
    c = c.replace("cantidad=cant,", "cantidad=cant,") # No hacemos nada aquí, SQLAlchemy lo maneja si el campo es Integer o Numeric.
    
    # Asegurarnos de que el modelo Venta acepte decimales en cantidad
    p_model_venta = Path('app/models/venta.py')
    if p_model_venta.exists():
        c_v = p_model_venta.read_text(encoding='utf-8')
        if 'cantidad = db.Column(db.Integer' in c_v:
            c_v = c_v.replace(
                "cantidad = db.Column(db.Integer, nullable=False)",
                "cantidad = db.Column(db.Numeric(10, 3), nullable=False) # ✅ Soporta decimales"
            )
            p_model_venta.write_text(c_v, encoding='utf-8')
            print("✅ models/venta.py: Campo 'cantidad' ahora acepta decimales.")
            
            # Generar script para base de datos
            db_script = """import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

def main():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
    if not db_url:
        print("❌ No se encontró DATABASE_URL")
        return

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Cambiando tipo de columna cantidad en ventas...")
        cursor.execute("ALTER TABLE ventas ALTER COLUMN cantidad TYPE NUMERIC(10, 3) USING cantidad::numeric;")
        
        print("✅ ¡Columna 'cantidad' actualizada exitosamente!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
"""
            Path('arreglar_db_cantidad_decimal.py').write_text(db_script, encoding='utf-8')
            print("✅ Script 'arreglar_db_cantidad_decimal.py' generado.")

    print("\n👉 Reinicia Flask y prueba vender 500g de carnicería. El stock debería bajar a 9.5.")

if __name__ == '__main__':
    main()