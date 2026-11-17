import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   AGREGANDO CATEGORÍA 'CHARCUTERIA' (VENTA POR PESO)")
    print("==================================================\n")

    # 1. ACTUALIZAR EL BACKEND (app/routes/user.py)
    p_routes = Path('app/routes/user.py')
    if p_routes.exists():
        c = p_routes.read_text(encoding='utf-8')
        bak = p_routes.with_suffix('.py.bak_charcuteria')
        if not bak.exists(): shutil.copy2(p_routes, bak)

        # Agregar 'Charcuteria' a la lista de categorías
        if "'Charcuteria'" not in c:
            c = c.replace(
                "return ['Carniceria', 'Repuestos Moto', 'Electrónica'",
                "return ['Carniceria', 'Charcuteria', 'Repuestos Moto', 'Electrónica'"
            )
            # Agregar subcategorías de Charcutería
            c = c.replace(
                "'Carniceria': ['Res', 'Cerdo', 'Pollo', 'Pescado', 'Chorizo', 'Queso', 'Otros'],",
                "'Carniceria': ['Res', 'Cerdo', 'Pollo', 'Pescado', 'Chorizo', 'Queso', 'Otros'],\n        'Charcuteria': ['Jamon', 'Queso', 'Salchichon', 'Mortadela', 'Chorizo', 'Otros'],"
            )
            # Agregar marcas
            c = c.replace(
                "'Carniceria': ['Propia', 'Otra Marca'],",
                "'Carniceria': ['Propia', 'Otra Marca'],\n        'Charcuteria': ['Propia', 'Otra Marca'],"
            )
            p_routes.write_text(c, encoding='utf-8')
            print("✅ user.py: Categoría 'Charcuteria' agregada.")

    # 2. ACTUALIZAR EL API (app/routes/api.py)
    p_api = Path('app/routes/api.py')
    if p_api.exists():
        c = p_api.read_text(encoding='utf-8')
        bak = p_api.with_suffix('.py.bak_charcuteria')
        if not bak.exists(): shutil.copy2(p_api, bak)

        if "'Charcuteria':" not in c:
            c = c.replace(
                "'Carniceria': ['Res', 'Cerdo', 'Pollo', 'Pescado', 'Chorizo', 'Queso', 'Otros'],",
                "'Carniceria': ['Res', 'Cerdo', 'Pollo', 'Pescado', 'Chorizo', 'Queso', 'Otros'],\n        'Charcuteria': ['Jamon', 'Queso', 'Salchichon', 'Mortadela', 'Chorizo', 'Otros'],"
            )
            p_api.write_text(c, encoding='utf-8')
            print("✅ api.py: Subcategorías de Charcuteria agregadas.")

    # 3. ACTUALIZAR EL JAVASCRIPT (app/templates/user/inventario.html)
    p_html = Path('app/templates/user/inventario.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_charcuteria')
        if not bak.exists(): shutil.copy2(p_html, bak)

        if "'Charcuteria': [" not in c:
            c = c.replace(
                "'Carniceria': ['Propia', 'Otra Marca'],",
                "'Carniceria': ['Propia', 'Otra Marca'],\n    'Charcuteria': ['Propia', 'Otra Marca'],"
            )
            p_html.write_text(c, encoding='utf-8')
            print("✅ inventario.html: Marca de Charcuteria agregada al JS.")

    # 4. ACTUALIZAR LA LÓGICA DE VENTAS (user/ventas.html y vendedor/ventas.html)
    for ventas_file in ['app/templates/user/ventas.html', 'app/templates/vendedor/ventas.html']:
        p_v = Path(ventas_file)
        if p_v.exists():
            c = p_v.read_text(encoding='utf-8')
            bak = p_v.with_suffix('.html.bak_charcuteria')
            if not bak.exists(): shutil.copy2(p_v, bak)

            # Modificar la función agregarDesdeElemento para detectar Charcuteria
            old_cat = """    if (categoria === 'carniceria') {
        abrirModalCarniceria(id, nombre, precio);
    } else if (tieneVariantes) {"""
            
            new_cat = """    // ✅ Detectar tanto Carniceria como Charcuteria
    if (categoria === 'carniceria' || categoria === 'charcuteria') {
        abrirModalCarniceria(id, nombre, precio);
    } else if (tieneVariantes) {"""
            
            if old_cat in c:
                c = c.replace(old_cat, new_cat)
                
                # También actualizar el título del modal para que diga "Carniceria / Charcuteria"
                c = c.replace(
                    '<h3 class="text-white font-bold text-lg flex items-center gap-2"><i class="fas fa-weight"></i> Venta por Peso</h3>',
                    '<h3 class="text-white font-bold text-lg flex items-center gap-2"><i class="fas fa-weight"></i> Venta por Peso (Carniceria / Charcuteria)</h3>'
                )
                
                p_v.write_text(c, encoding='utf-8')
                print(f"✅ {ventas_file}: Lógica de Charcuteria agregada.")

    # 5. ACTUALIZAR EL SERVICIO DE VENTAS (app/services/ventas.py)
    p_ventas_service = Path('app/services/ventas.py')
    if p_ventas_service.exists():
        c = p_ventas_service.read_text(encoding='utf-8')
        bak = p_ventas_service.with_suffix('.py.bak_charcuteria')
        if not bak.exists(): shutil.copy2(p_ventas_service, bak)

        # La condición para usar Decimal debe incluir Charcuteria
        old_cond = "if producto.categoria == 'Carniceria':"
        new_cond = "if producto.categoria in ('Carniceria', 'Charcuteria'):"
        
        if old_cond in c:
            c = c.replace(old_cond, new_cond)
            p_ventas_service.write_text(c, encoding='utf-8')
            print("✅ services/ventas.py: Condición de decimales actualizada (Carniceria y Charcuteria).")

    # 6. CREAR SCRIPT PARA ACTUALIZAR LA BASE DE DATOS (por si acaso)
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
        
        # No hay cambios en la base de datos, pero lo dejamos por si acaso.
        print("✅ Base de datos lista (no se requieren cambios).")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
"""
    Path('arreglar_db_charcuteria.py').write_text(db_script, encoding='utf-8')
    print("✅ Script 'arreglar_db_charcuteria.py' generado (no hace cambios en la DB).")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga el inventario con Ctrl + Shift + R.")
    print("Ahora podrás crear productos con categoría 'Charcuteria' y venderlos por peso.")

if __name__ == '__main__':
    main()