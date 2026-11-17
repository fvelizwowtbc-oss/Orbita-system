import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   LIMITANDO DECIMALES DE STOCK A 2 (EJ: 9.50)")
    print("==================================================\n")

    # 1. ACTUALIZAR EL MODELO (app/models/producto.py)
    p_model = Path('app/models/producto.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        bak = p_model.with_suffix('.py.bak_2decimales')
        if not bak.exists(): shutil.copy2(p_model, bak)

        # Cambiar Numeric(10, 3) a Numeric(10, 2)
        c = c.replace("db.Numeric(10, 3)", "db.Numeric(10, 2)")
        
        p_model.write_text(c, encoding='utf-8')
        print("✅ producto.py: Columnas de stock cambiadas a Numeric(10, 2).")

    # 2. ACTUALIZAR EL MODELO DE VENTA (app/models/venta.py)
    p_venta = Path('app/models/venta.py')
    if p_venta.exists():
        c = p_venta.read_text(encoding='utf-8')
        bak = p_venta.with_suffix('.py.bak_2decimales')
        if not bak.exists(): shutil.copy2(p_venta, bak)

        c = c.replace("db.Numeric(10, 3)", "db.Numeric(10, 2)")
        
        p_venta.write_text(c, encoding='utf-8')
        print("✅ venta.py: Columna cantidad cambiada a Numeric(10, 2).")

    # 3. ACTUALIZAR EL HTML (inputs) para limitar a 2 decimales
    for html_file in ['app/templates/user/inventario.html', 'app/templates/vendedor/inventario.html']:
        p = Path(html_file)
        if p.exists():
            c = p.read_text(encoding='utf-8')
            c = c.replace('step="0.001"', 'step="0.01"')
            p.write_text(c, encoding='utf-8')
            print(f"✅ {html_file}: Inputs de stock limitados a 2 decimales.")

    # 4. CREAR SCRIPT PARA ACTUALIZAR LA BASE DE DATOS
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
        
        print("Ajustando stock_actual y stock_minimo en productos (a 2 decimales)...")
        cursor.execute("ALTER TABLE productos ALTER COLUMN stock_actual TYPE NUMERIC(10, 2) USING ROUND(stock_actual::numeric, 2);")
        cursor.execute("ALTER TABLE productos ALTER COLUMN stock_minimo TYPE NUMERIC(10, 2) USING ROUND(stock_minimo::numeric, 2);")
        
        print("Ajustando stock en producto_variantes (a 2 decimales)...")
        cursor.execute("ALTER TABLE producto_variantes ALTER COLUMN stock_actual TYPE NUMERIC(10, 2) USING ROUND(stock_actual::numeric, 2);")
        cursor.execute("ALTER TABLE producto_variantes ALTER COLUMN stock_minimo TYPE NUMERIC(10, 2) USING ROUND(stock_minimo::numeric, 2);")
        
        print("Ajustando cantidad en ventas (a 2 decimales)...")
        cursor.execute("ALTER TABLE ventas ALTER COLUMN cantidad TYPE NUMERIC(10, 2) USING ROUND(cantidad::numeric, 2);")
        
        print("✅ ¡Columnas actualizadas a 2 decimales exitosamente!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
"""
    Path('arreglar_db_2decimales.py').write_text(db_script, encoding='utf-8')
    print("✅ Script 'arreglar_db_2decimales.py' generado.")

    print("\n👉 Ejecuta el script de base de datos y luego reinicia Flask.")

if __name__ == '__main__':
    main()