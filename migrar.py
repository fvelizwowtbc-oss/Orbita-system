# migrar.py
import os
import sys
import traceback
import io
from sqlalchemy import create_engine, MetaData, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_PATH = r"C:\Orbita\data\instance\sistema_gestion.db"

def migrar():
    print("=" * 60)
    print("  MIGRACION SQLITE -> POSTGRESQL")
    print("=" * 60)

    if not DATABASE_URL:
        print("[ERR] DATABASE_URL no está en .env")
        return

    if not os.path.exists(SQLITE_PATH):
        print(f"[ERR] No se encuentra SQLite: {SQLITE_PATH}")
        return

    url_mostrar = DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else DATABASE_URL
    print(f"\n  Origen:  {SQLITE_PATH}")
    print(f"  Destino: {url_mostrar}")

    # 1. Configurar Flask
    print("\n[1/5] Configurando Flask...")
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
    except Exception as e:
        print(f"  [ERR] Error configurando Flask: {e}")
        traceback.print_exc()
        return

    # 2. Limpiar PostgreSQL
    print("\n[2/5] Limpiando PostgreSQL...")
    with app.app_context():
        try:
            with db.engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
            print("  [OK] Esquema limpiado")
        except Exception as e:
            print(f"  [ERR] Error limpiando: {e}")
            return
        finally:
            db.session.remove()

    # 3. Crear tablas
    print("\n[3/5] Creando tablas...")
    with app.app_context():
        try:
            db.create_all()
            print("  [OK] Tablas creadas")

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
        finally:
            db.session.remove()

    # 3.5. Resetear secuencias y eliminar FKs
    print("\n[3.5/5] Reseteando secuencias y eliminando FKs...")
    with app.app_context():
        try:
            with db.engine.begin() as conn:
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
                        conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), 1000000, false);"))
                        print(f"  [OK] {tabla}: secuencia reseteada a 1,000,000")
            print("  [OK] Secuencias reseteadas")

            with db.engine.begin() as conn:
                result = conn.execute(text("""
                    SELECT
                        tc.table_name,
                        tc.constraint_name
                    FROM
                        information_schema.table_constraints AS tc
                    WHERE
                        tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = 'public';
                """))
                fks = result.fetchall()
                for table, constraint in fks:
                    conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT "{constraint}";'))
            print(f"  [OK] {len(fks)} restricciones FK eliminadas temporalmente")

        except Exception as e:
            print(f"  [ERR] Error en paso 3.5: {e}")
            traceback.print_exc()
            return
        finally:
            db.session.remove()

    # 4. Copiar datos
    print("\n[4/5] Copiando datos con COPY...")
    with app.app_context():
        try:
            engine_sqlite = create_engine(f"sqlite:///{SQLITE_PATH}")
            metadata_sqlite = MetaData()
            metadata_sqlite.reflect(bind=engine_sqlite)

            metadata_pg = MetaData()
            metadata_pg.reflect(bind=db.engine)

            total_filas = 0

            for table in metadata_sqlite.sorted_tables:
                if table.name not in metadata_pg.tables:
                    print(f"  [SKIP] {table.name}")
                    continue

                with engine_sqlite.connect() as conn_sqlite:
                    rows = conn_sqlite.execute(table.select()).fetchall()

                if not rows:
                    print(f"  - {table.name}: 0 filas")
                    continue

                columns = [c.name for c in table.columns]

                output = io.StringIO()
                for row in rows:
                    vals = []
                    for v in row:
                        if v is None:
                            vals.append('\\N')
                        else:
                            s = str(v)
                            s = s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')
                            vals.append(s)
                    output.write('\t'.join(vals) + '\n')
                output.seek(0)

                try:
                    raw_conn = db.engine.raw_connection()
                    cursor = raw_conn.cursor()
                    cursor.copy_from(
                        output,
                        table.name,
                        sep='\t',
                        null='\\N',
                        columns=columns
                    )
                    raw_conn.commit()
                    cursor.close()
                    raw_conn.close()
                    total_filas += len(rows)
                    print(f"  + {table.name}: {len(rows)} filas")
                except Exception as e:
                    print(f"  [ERR] {table.name}: {e}")

            print(f"\n[OK] Datos copiados. Total: {total_filas} filas")

        except Exception as e:
            print(f"[ERR] Error copiando datos: {e}")
            traceback.print_exc()
            return
        finally:
            db.session.remove()

    # 5. Actualizar secuencias y recrear FKs
    print("\n[5/5] Actualizando secuencias y recreando FKs...")
    with app.app_context():
        try:
            with db.engine.begin() as conn:
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

            print("  Recreando restricciones FK...")
            fks_a_crear = [
                ('clientes', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('config_empresa', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('config_tasa', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('facturas_cobrar', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('facturas_cobrar', 'venta_id', 'ventas', 'id', 'CASCADE'),
                ('facturas_cobrar', 'cliente_id', 'clientes', 'id', 'SET NULL'),
                ('gastos', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('gastos', 'factura_proveedor_id', 'facturas_proveedores', 'id', 'SET NULL'),
                ('producto_variantes', 'producto_id', 'productos', 'id', 'CASCADE'),
                ('productos', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('suscripciones', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('suscripciones', 'creado_por', 'usuarios', 'id', 'SET NULL'),
                ('vendedores_config', 'usuario_padre_id', 'usuarios', 'id', 'CASCADE'),
                ('vendedores_config', 'vendedor_id', 'usuarios', 'id', 'CASCADE'),
                ('ventas', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('ventas', 'producto_id', 'productos', 'id', 'RESTRICT'),
                ('ventas', 'variante_id', 'producto_variantes', 'id', 'SET NULL'),
                ('ventas', 'vendedor_id', 'usuarios', 'id', 'SET NULL'),
                ('ventas', 'cliente_id', 'clientes', 'id', 'SET NULL'),
                ('abonos', 'factura_id', 'facturas_cobrar', 'id', 'CASCADE'),
                ('cuotas_cashea', 'factura_id', 'facturas_cobrar', 'id', 'CASCADE'),
                ('facturas_proveedores', 'usuario_id', 'usuarios', 'id', 'CASCADE'),
                ('usuarios', 'usuario_padre_id', 'usuarios', 'id', 'SET NULL'),
            ]

            for tabla_hija, col_hija, tabla_padre, col_padre, on_delete in fks_a_crear:
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text(f"""
                            ALTER TABLE "{tabla_hija}"
                            ADD CONSTRAINT "fk_{tabla_hija}_{col_hija}"
                            FOREIGN KEY ("{col_hija}") REFERENCES "{tabla_padre}"("{col_padre}")
                            ON DELETE {on_delete};
                        """))
                    print(f"  [OK] FK {tabla_hija}.{col_hija}")
                except Exception as e:
                    print(f"  [WARN] No se pudo crear FK {tabla_hija}.{col_hija}: {e}")

        except Exception as e:
            print(f"  [ERR] Error en paso final: {e}")
        finally:
            db.session.remove()

    print("\n" + "=" * 60)
    print("  PROCESO COMPLETADO")
    print("=" * 60)

if __name__ == "__main__":
    try:
        migrar()
    except Exception:
        traceback.print_exc()
    input("\nPresiona Enter para cerrar...")