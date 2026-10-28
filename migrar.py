# migrar.py
import os
import sys
import traceback
from sqlalchemy import create_engine, MetaData, text

# ============================================================
# CONFIGURACION (NO PEGAR EN EL CHAT)
# ============================================================
DATABASE_URL = "postgresql://db_orbita_xf88_user:ZaqIPlpqV5YcSlOcnIh4JlYTEetpDKHd@dpg-dbgfpgks728c739lv8eg-a.ohio-postgres.render.com/db_orbita_xf88"
SQLITE_PATH = r"C:\Orbita\data\instance\sistema_gestion.db"
# ============================================================

def migrar():
    print("=" * 60)
    print("  MIGRACION DEFINITIVA (SIN FK) SQLITE -> POSTGRESQL")
    print("=" * 60)

    if not os.path.exists(SQLITE_PATH):
        print(f"[ERR] No se encuentra SQLite: {SQLITE_PATH}")
        return

    # 1. Conectar
    print("\n[1/6] Conectando a PostgreSQL...")
    try:
        engine_pg = create_engine(DATABASE_URL, pool_pre_ping=True)
        print("  [OK] Conectado")
    except Exception as e:
        print(f"  [ERR] Error conectando: {e}")
        return

    # 2. Limpieza total
    print("\n[2/6] Limpiando PostgreSQL...")
    try:
        with engine_pg.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
        print("  [OK] Esquema limpiado")
    except Exception as e:
        print(f"  [ERR] Error limpiando: {e}")
        return

    # 3. Crear tablas
    print("\n[3/6] Creando tablas con modelos de Flask...")
    try:
        os.environ["DATABASE_URL"] = DATABASE_URL
        from app import create_app
        from app.extensions import db
        import app.models
        
        app = create_app("production")
        
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'].lower():
            print(f"  [ERR] App sigue usando SQLite")
            return
        
        print(f"  [OK] Usando: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1]}")
        
        with app.app_context():
            db.create_all()
            print("  [OK] Tablas creadas")
            
            # Eliminar el admin que _seed_data() insertó
            from app.models.usuario import Usuario
            usuario = Usuario.query.filter_by(email='admin@sistema.com').first()
            if usuario:
                db.session.delete(usuario)
                db.session.commit()
                print("  [OK] Admin por defecto eliminado")
                
    except Exception as e:
        print(f"  [ERR] Error creando tablas: {e}")
        traceback.print_exc()
        return

    # 4. RESETEAR SECUENCIAS A 1 (CRUCIAL)
    print("\n[4/6] Reseteando secuencias a 1...")
    try:
        with engine_pg.begin() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE';
            """))
            tablas = [row[0] for row in result]
            
            for tabla in tablas:
                result_col = conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{tabla}' AND column_name = 'id';
                """))
                if result_col.fetchone():
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), 1, false);"))
                    print(f"  [OK] {tabla}: secuencia reseteada a 1")
        print("  [OK] Secuencias reseteadas")
    except Exception as e:
        print(f"  [ERR] Error reseteando secuencias: {e}")

    # 5. Copiar datos
    print("\n[5/6] Copiando datos...")
    try:
        engine_sqlite = create_engine(f"sqlite:///{SQLITE_PATH}")
        metadata_sqlite = MetaData()
        metadata_sqlite.reflect(bind=engine_sqlite)
        
        metadata_pg = MetaData()
        metadata_pg.reflect(bind=engine_pg)

        total_filas = 0

        for table in metadata_sqlite.sorted_tables:
            if table.name not in metadata_pg.tables:
                print(f"  [SKIP] {table.name} (no existe en PostgreSQL)")
                continue

            with engine_sqlite.connect() as conn_sqlite:
                rows = conn_sqlite.execute(table.select()).fetchall()

            if not rows:
                print(f"  - {table.name}: 0 filas")
                continue

            data = [dict(row._mapping) for row in rows]
            columns = list(data[0].keys())
            placeholders = ", ".join([f":{c}" for c in columns])
            cols_str = ", ".join(columns)

            if 'id' in columns:
                sql = text(f"INSERT INTO {table.name} ({cols_str}) OVERRIDING SYSTEM VALUE VALUES ({placeholders})")
            else:
                sql = text(f"INSERT INTO {table.name} ({cols_str}) VALUES ({placeholders})")

            with engine_pg.begin() as conn_pg:
                try:
                    conn_pg.execute(sql, data)
                    total_filas += len(data)
                    print(f"  + {table.name}: {len(data)} filas")
                except Exception as e:
                    print(f"  [ERR] {table.name}: {e}")

        print(f"\n[OK] Datos copiados. Total: {total_filas} filas")

    except Exception as e:
        print(f"[ERR] Error copiando datos: {e}")
        traceback.print_exc()
        return

    # 6. Actualizar secuencias al MAX(id)
    print("\n[6/6] Actualizando secuencias al MAX(id)...")
    try:
        with engine_pg.begin() as conn:
            for table in metadata_pg.sorted_tables:
                if 'id' in [c.name for c in table.columns]:
                    try:
                        result = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table.name};"))
                        max_id = result.scalar()
                        if max_id > 0:
                            conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), {max_id});"))
                            print(f"  [OK] {table.name}: secuencia actualizada a {max_id}")
                    except Exception:
                        pass
        print("  [OK] Secuencias actualizadas")
    except Exception as e:
        print(f"  [ERR] Error actualizando secuencias: {e}")

    print("\n" + "=" * 60)
    print("  PROCESO COMPLETADO")
    print("=" * 60)

if __name__ == "__main__":
    try:
        migrar()
    except Exception:
        traceback.print_exc()
    input("\nPresiona Enter para cerrar...")