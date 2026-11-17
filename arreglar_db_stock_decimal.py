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
