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
        
        # No hay cambios en la base de datos, pero lo dejamos por si acaso.
        print("✅ Base de datos lista (no se requieren cambios).")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
