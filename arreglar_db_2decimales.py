import os
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
