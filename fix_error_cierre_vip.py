import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO ERROR DE CIERRES EN VISTA VIP")
    print("==================================================\n")

    p = Path('app/routes/user.py')
    if not p.exists():
        print("❌ No se encontró user.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_error_cierre')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Buscar el bloque donde se hace la consulta de cierres_vendedores
    patron = re.compile(
        r"cierres_vendedores_query = db\.session\.query\(CajaTurno,.*?cierres_vendedores\.append\(\{.*?'vendedor_nombre': vendedor_nombre.*?\}\)",
        re.DOTALL
    )

    nueva_logica = """cierres_vendedores_query = db.session.query(CajaTurno, vendedor_alias.nombre.label('vendedor_nombre')).\\
        join(vendedor_alias, CajaTurno.vendedor_id == vendedor_alias.id).\\
        filter(CajaTurno.usuario_id == uid, CajaTurno.estado == 'cerrada').\\
        order_by(CajaTurno.cerrada_en.desc()).limit(20).all()
    
    # Formatear los datos para el template (Diccionario)
    cierres_vendedores = []
    for row in cierres_vendedores_query:
        cierre_obj = row[0] # El objeto CajaTurno
        vendedor_nombre = row[1] # El nombre del vendedor
        
        cierres_vendedores.append({
            'cierre': cierre_obj,
            'vendedor_nombre': vendedor_nombre
        })"""

    if patron.search(c):
        c = patron.sub(nueva_logica, c)
        p.write_text(c, encoding='utf-8')
        print("✅ user.py: Consulta de cierres corregida (devuelve diccionario).")
    else:
        print("⚠️ No se encontró el bloque exacto. Buscando variante...")
        # Si falla, buscar el bloque de la versión anterior
        old_query = """cierres_vendedores_query = db.session.query(CajaTurno, vendedor_alias.nombre.label('vendedor_nombre')).\\
        join(vendedor_alias, CajaTurno.vendedor_id == vendedor_alias.id).\\
        filter(CajaTurno.usuario_id == uid, CajaTurno.estado == 'cerrada').\\
        order_by(CajaTurno.cerrada_en.desc()).limit(20).all()
    
    # Formatear los datos para el template
    cierres_vendedores = []
    for cierre, vendedor_nombre in cierres_vendedores_query:
        cierres_vendedores.append({
            'cierre': cierre,
            'vendedor_nombre': vendedor_nombre
        })"""
        
        if old_query in c:
            c = c.replace(old_query, nueva_logica)
            p.write_text(c, encoding='utf-8')
            print("✅ user.py: Consulta corregida (método alternativo).")
        else:
            print("❌ No se encontró el bloque de consulta.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página de Caja como VIP con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()