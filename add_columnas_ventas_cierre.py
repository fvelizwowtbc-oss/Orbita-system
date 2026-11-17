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
        
        print("Agregando columnas 'ventas_totales_usd' y 'ventas_totales_bs'...")
        cursor.execute("ALTER TABLE caja_turnos ADD COLUMN IF NOT EXISTS ventas_totales_usd NUMERIC(10, 2) DEFAULT 0;")
        cursor.execute("ALTER TABLE caja_turnos ADD COLUMN IF NOT EXISTS ventas_totales_bs NUMERIC(10, 2) DEFAULT 0;")
        
        print("✅ ¡Columnas agregadas exitosamente!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
