import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   GUARDANDO Y MOSTRANDO VENTAS EN EL CIERRE")
    print("==================================================\n")

    # 1. ACTUALIZAR EL MODELO (app/models/caja.py)
    p_model = Path('app/models/caja.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        bak = p_model.with_suffix('.py.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_model, bak)

        if 'ventas_totales_usd' not in c:
            c = c.replace(
                "tasa_cierre = db.Column(db.Numeric(10, 2), nullable=True)",
                """tasa_cierre = db.Column(db.Numeric(10, 2), nullable=True)
    # ✅ Montos totales de ventas al momento del cierre (para el historial)
    ventas_totales_usd = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    ventas_totales_bs = db.Column(db.Numeric(10, 2), nullable=True, default=0)"""
            )
            p_model.write_text(c, encoding='utf-8')
            print("✅ Modelo CajaTurno actualizado con campos de ventas totales.")

    # 2. ACTUALIZAR LA RUTA DEL VENDEDOR (app/routes/vendedor.py)
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        # Agregar el guardado de ventas totales antes de cerrar la caja
        old_cierre = """        caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        
        caja.tasa_cierre = tasa_bcv"""
        
        new_cierre = """        caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        
        # ✅ Guardar el total de ventas en ese turno para el historial
        caja.ventas_totales_usd = ventas_usd
        caja.ventas_totales_bs = ventas_bs
        
        caja.tasa_cierre = tasa_bcv"""
        
        if old_cierre in c:
            c = c.replace(old_cierre, new_cierre)
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ vendedor.py: Ahora guarda el total de ventas al cerrar.")

    # 3. ACTUALIZAR LA VISTA DEL VENDEDOR (app/templates/vendedor/caja.html)
    p_vend_html = Path('app/templates/vendedor/caja.html')
    if p_vend_html.exists():
        c = p_vend_html.read_text(encoding='utf-8')
        bak = p_vend_html.with_suffix('.html.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_vend_html, bak)

        # Buscar la sección de "Ventas Efectivo" y cambiarla para que muestre el total guardado
        old_ventas = """                        <!-- Ventas en Efectivo -->
                        <div class="flex justify-between items-center bg-emerald-50 p-1.5 rounded border border-emerald-100">
                            <span class="text-emerald-700 font-medium"><i class="fas fa-shopping-cart text-emerald-500 w-4"></i> Ventas Efectivo:</span>
                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}</span>
                        </div>"""
        
        new_ventas = """                        <!-- Ventas en Efectivo -->
                        <div class="flex justify-between items-center bg-emerald-50 p-1.5 rounded border border-emerald-100">
                            <span class="text-emerald-700 font-medium"><i class="fas fa-shopping-cart text-emerald-500 w-4"></i> Ventas del Turno:</span>
                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.ventas_totales_usd|float or cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.ventas_totales_bs|float or cierre.total_ventas_efectivo_bs|float or 0) }}</span>
                        </div>"""
        
        if old_ventas in c:
            c = c.replace(old_ventas, new_ventas)
            p_vend_html.write_text(c, encoding='utf-8')
            print("✅ vendedor/caja.html: Muestra el total de ventas del turno.")
        else:
            print("⚠️ No se encontró el bloque de ventas en vendedor/caja.html. Aplicando reemplazo simple...")
            c = c.replace('Ventas Efectivo:', 'Ventas del Turno:')
            c = c.replace(
                '${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}',
                '${{ "%.2f"|format(cierre.ventas_totales_usd|float or cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.ventas_totales_bs|float or cierre.total_ventas_efectivo_bs|float or 0) }}'
            )
            p_vend_html.write_text(c, encoding='utf-8')
            print("✅ vendedor/caja.html: Actualizado (método directo).")

    # 4. ACTUALIZAR LA VISTA DEL USUARIO (app/templates/user/caja.html)
    # Para que el dueño también vea las ventas de los turnos de sus vendedores
    p_user_html = Path('app/templates/user/caja.html')
    if p_user_html.exists():
        c = p_user_html.read_text(encoding='utf-8')
        bak = p_user_html.with_suffix('.html.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_user_html, bak)

        c = c.replace('Ventas Efectivo:', 'Ventas del Turno:')
        c = c.replace(
            '${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}',
            '${{ "%.2f"|format(cierre.ventas_totales_usd|float or cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.ventas_totales_bs|float or cierre.total_ventas_efectivo_bs|float or 0) }}'
        )
        p_user_html.write_text(c, encoding='utf-8')
        print("✅ user/caja.html: Muestra el total de ventas del turno.")

    # 5. GENERAR SCRIPT PARA AGREGAR COLUMNAS A LA BASE DE DATOS
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
"""
    Path('add_columnas_ventas_cierre.py').write_text(db_script, encoding='utf-8')
    print("✅ Script 'add_columnas_ventas_cierre.py' generado.")

    print("\n👉 Ejecuta el script de base de datos y luego reinicia Flask.")

if __name__ == '__main__':
    main()