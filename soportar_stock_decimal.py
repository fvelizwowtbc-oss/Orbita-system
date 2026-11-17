import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   SOPORTE DE STOCK DECIMAL PARA CARNICERÍA")
    print("==================================================\n")

    # 1. ACTUALIZAR EL MODELO (app/models/producto.py)
    p_model = Path('app/models/producto.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        bak = p_model.with_suffix('.py.bak_decimal')
        if not bak.exists(): shutil.copy2(p_model, bak)

        # Cambiar stock_actual y stock_minimo a Float/Numeric
        c = c.replace(
            "stock_actual = db.Column(db.Integer, default=0)",
            "stock_actual = db.Column(db.Numeric(10, 3), default=0) # ✅ Permite decimales (ej: 9.500 kg)"
        )
        c = c.replace(
            "stock_minimo = db.Column(db.Integer, default=5)",
            "stock_minimo = db.Column(db.Numeric(10, 3), default=5)"
        )
        
        # Lo mismo para las variantes
        c = c.replace(
            "stock_actual = db.Column(db.Integer, default=0)\n    stock_minimo = db.Column(db.Integer, default=0)",
            "stock_actual = db.Column(db.Numeric(10, 3), default=0)\n    stock_minimo = db.Column(db.Numeric(10, 3), default=0)"
        )

        p_model.write_text(c, encoding='utf-8')
        print("✅ Modelo Producto actualizado para aceptar decimales en el stock.")

    # 2. ACTUALIZAR EL SERVICIO DE VENTAS (app/services/ventas.py)
    p_ventas = Path('app/services/ventas.py')
    if p_ventas.exists():
        c = p_ventas.read_text(encoding='utf-8')
        bak = p_ventas.with_suffix('.py.bak_decimal')
        if not bak.exists(): shutil.copy2(p_ventas, bak)

        # En la función procesar, al descontar el stock:
        # Actualmente hace: producto.stock_actual -= cant
        # Debemos asegurarnos de que 'cant' sea decimal si es carnicería.
        
        # Buscamos el bloque de descuento de stock
        old_stock = """                # Descontar stock del producto
                producto.stock_actual -= cant"""
        
        new_stock = """                # Descontar stock del producto
                # ✅ Si es carnicería, usar Decimal para soportar gramos
                from decimal import Decimal
                cantidad_a_descontar = Decimal(str(cant))
                if producto.categoria == 'Carniceria':
                    # 'cant' viene como kilos (ej: 0.500 para 500g)
                    producto.stock_actual = Decimal(str(producto.stock_actual or 0)) - cantidad_a_descontar
                else:
                    # Productos normales (unidades enteras)
                    producto.stock_actual = int(producto.stock_actual or 0) - int(cant)"""

        if old_stock in c:
            c = c.replace(old_stock, new_stock)
            p_ventas.write_text(c, encoding='utf-8')
            print("✅ services/ventas.py: Descuento de stock actualizado (soporta decimales).")

    # 3. ACTUALIZAR EL INVENTARIO HTML (app/templates/user/inventario.html)
    p_html = Path('app/templates/user/inventario.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_decimal')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # Permitir decimales en los inputs de stock (actual y mínimo) en el formulario
        c = c.replace(
            '<input type="number" name="stock_actual" id="f_stock_actual" value="0" class="w-full px-4 py-2 border rounded-lg">',
            '<input type="number" step="0.001" name="stock_actual" id="f_stock_actual" value="0" class="w-full px-4 py-2 border rounded-lg">'
        )
        c = c.replace(
            '<input type="number" name="stock_minimo" id="f_stock_minimo" value="5" class="w-full px-4 py-2 border rounded-lg">',
            '<input type="number" step="0.001" name="stock_minimo" id="f_stock_minimo" value="5" class="w-full px-4 py-2 border rounded-lg">'
        )

        p_html.write_text(c, encoding='utf-8')
        print("✅ inventario.html: Inputs de stock ahora aceptan decimales.")

    # 4. ACTUALIZAR EL MODAL DE CARNICERÍA (app/templates/user/ventas.html y vendedor/ventas.html)
    # para que al agregar al carrito envíe los gramos como fracción de kilo (ej: 500g -> 0.5)
    for ventas_file in ['app/templates/user/ventas.html', 'app/templates/vendedor/ventas.html']:
        p_v = Path(ventas_file)
        if p_v.exists():
            c = p_v.read_text(encoding='utf-8')
            bak = p_v.with_suffix('.html.bak_decimal')
            if not bak.exists(): shutil.copy2(p_v, bak)

            # En la función agregarAlCarritoDesdeModal, calculamos la cantidad en kilos
            old_agregar = """    var precioProporcional = (gramos / 1000) * precioKg;
    var nombreFinal = nombre + ' (' + gramos + 'g)';
    var existente = carrito.find(function (i) { return i.producto_id === id && i.es_carniceria && i.gramos === gramos; });

    if (existente) {
        existente.cantidad++;
    } else {
        carrito.push({ 
            producto_id: id, 
            variante_id: null, 
            nombre: nombreFinal, 
            precio_usd: precioProporcional, 
            cantidad: 1, 
            stock: 9999,
            es_carniceria: true,
            gramos: gramos
        });
    }"""
            
            new_agregar = """    var precioProporcional = (gramos / 1000) * precioKg;
    var cantidadEnKilos = gramos / 1000; // ✅ 500g = 0.5 kg
    var nombreFinal = nombre + ' (' + gramos + 'g)';
    var existente = carrito.find(function (i) { return i.producto_id === id && i.es_carniceria; });

    if (existente) {
        existente.cantidad += cantidadEnKilos;
    } else {
        carrito.push({ 
            producto_id: id, 
            variante_id: null, 
            nombre: nombreFinal, 
            precio_usd: precioKg, // ✅ Precio por kilo
            cantidad: cantidadEnKilos, 
            stock: 9999,
            es_carniceria: true,
            gramos: gramos
        });
    }"""
            
            if old_agregar in c:
                c = c.replace(old_agregar, new_agregar)
                p_v.write_text(c, encoding='utf-8')
                print(f"✅ {ventas_file}: Lógica de carnicería actualizada (cantidad en kilos).")

    # 5. CREAR SCRIPT PARA ACTUALIZAR LA BASE DE DATOS
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

    print("Conectando a PostgreSQL...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Cambiando tipo de columna stock_actual en productos...")
        cursor.execute("ALTER TABLE productos ALTER COLUMN stock_actual TYPE NUMERIC(10, 3) USING stock_actual::numeric;")
        
        print("Cambiando tipo de columna stock_minimo en productos...")
        cursor.execute("ALTER TABLE productos ALTER COLUMN stock_minimo TYPE NUMERIC(10, 3) USING stock_minimo::numeric;")
        
        print("Cambiando tipo de columna stock_actual en producto_variantes...")
        cursor.execute("ALTER TABLE producto_variantes ALTER COLUMN stock_actual TYPE NUMERIC(10, 3) USING stock_actual::numeric;")
        
        print("Cambiando tipo de columna stock_minimo en producto_variantes...")
        cursor.execute("ALTER TABLE producto_variantes ALTER COLUMN stock_minimo TYPE NUMERIC(10, 3) USING stock_minimo::numeric;")
        
        print("✅ ¡Columnas actualizadas exitosamente!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
"""
    Path('arreglar_db_stock_decimal.py').write_text(db_script, encoding='utf-8')
    print("✅ Script 'arreglar_db_stock_decimal.py' generado.")

    print("\n👉 Ejecuta el script de base de datos y luego reinicia Flask.")

if __name__ == '__main__':
    main()