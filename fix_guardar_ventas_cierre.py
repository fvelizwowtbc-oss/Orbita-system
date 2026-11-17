import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO GUARDADO DE VENTAS EN EL CIERRE")
    print("==================================================\n")

    # 1. CORREGIR vendedor.py (Cierre de caja del vendedor)
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        # Buscar el bloque donde se cierra la caja
        patron = re.compile(
            r"(caja\.diferencia_usd = real_usd - esperado_usd\s*\n\s*caja\.diferencia_bs = real_bs - esperado_bs\s*\n\s*caja\.tasa_cierre = tasa_bcv)",
            re.DOTALL
        )
        
        nuevo_bloque = """caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        
        # ✅ Guardar las ventas totales del turno para el historial
        caja.ventas_totales_usd = float(caja.total_ventas_efectivo_usd or 0)
        caja.ventas_totales_bs = float(caja.total_ventas_efectivo_bs or 0)
        
        caja.tasa_cierre = tasa_bcv"""
        
        if patron.search(c):
            c = patron.sub(nuevo_bloque, c)
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ vendedor.py: Se guardan las ventas en el cierre.")
        else:
            print("⚠️ No se encontró el bloque exacto en vendedor.py. Buscando variante...")
            # Intentar con la fórmula anterior
            old_block = """caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        
        caja.tasa_cierre = tasa_bcv"""
            if old_block in c:
                c = c.replace(old_block, nuevo_bloque)
                p_vendedor.write_text(c, encoding='utf-8')
                print("✅ vendedor.py: Se guardan las ventas en el cierre (método alternativo).")
            else:
                print("❌ No se encontró el bloque en vendedor.py.")

    # 2. CORREGIR user.py (Cierre de caja del dueño)
    p_user = Path('app/routes/user.py')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        bak = p_user.with_suffix('.py.bak_ventas_cierre')
        if not bak.exists(): shutil.copy2(p_user, bak)

        # Buscar el bloque donde se cierra la caja en user.py
        patron_user = re.compile(
            r"(caja\.diferencia_usd = .*?\n\s*caja\.diferencia_bs = .*?\n\s*caja\.tasa_cierre = tasa_bcv)",
            re.DOTALL
        )
        
        nuevo_bloque_user = """caja.diferencia_usd = float(caja.saldo_real_usd or 0) - (float(caja.saldo_inicial_usd or 0) + float(caja.total_ventas_efectivo_usd or 0))
        caja.diferencia_bs = float(caja.saldo_real_bs or 0) - (float(caja.saldo_inicial_bs or 0) + float(caja.total_ventas_efectivo_bs or 0))
        
        # ✅ Guardar las ventas totales del turno para el historial
        caja.ventas_totales_usd = float(caja.total_ventas_efectivo_usd or 0)
        caja.ventas_totales_bs = float(caja.total_ventas_efectivo_bs or 0)
        
        caja.tasa_cierre = tasa_bcv"""
        
        if patron_user.search(c):
            c = patron_user.sub(nuevo_bloque_user, c)
            p_user.write_text(c, encoding='utf-8')
            print("✅ user.py: Se guardan las ventas en el cierre.")
        else:
            # Intentar con el bloque que ya teníamos
            old_user = """caja.diferencia_usd = float(caja.saldo_real_usd or 0) - (float(caja.saldo_inicial_usd or 0) + float(caja.total_ventas_efectivo_usd or 0))
        caja.diferencia_bs = float(caja.saldo_real_bs or 0) - (float(caja.saldo_inicial_bs or 0) + float(caja.total_ventas_efectivo_bs or 0))"""
            if old_user in c:
                c = c.replace(old_user, nuevo_bloque_user)
                p_user.write_text(c, encoding='utf-8')
                print("✅ user.py: Se guardan las ventas en el cierre (método alternativo).")
            else:
                print("⚠️ La fórmula en user.py ya estaba actualizada o tiene otro formato.")

    # 3. ACTUALIZAR LA VISTA (vendedor/caja.html) para usar los nuevos campos
    p_vend_html = Path('app/templates/vendedor/caja.html')
    if p_vend_html.exists():
        c = p_vend_html.read_text(encoding='utf-8')
        bak = p_vend_html.with_suffix('.html.bak_ventas')
        if not bak.exists(): shutil.copy2(p_vend_html, bak)

        old_html = """                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.ventas_totales_usd|float or cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.ventas_totales_bs|float or cierre.total_ventas_efectivo_bs|float or 0) }}</span>"""
        
        new_html = """                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}</span>"""
        
        if old_html in c:
            c = c.replace(old_html, new_html)
            p_vend_html.write_text(c, encoding='utf-8')
            print("✅ vendedor/caja.html: Ahora usa los campos originales de ventas.")

    # 4. ACTUALIZAR LA VISTA (user/caja.html) para usar los nuevos campos
    p_user_html = Path('app/templates/user/caja.html')
    if p_user_html.exists():
        c = p_user_html.read_text(encoding='utf-8')
        bak = p_user_html.with_suffix('.html.bak_ventas')
        if not bak.exists(): shutil.copy2(p_user_html, bak)

        old_html_user = """                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.ventas_totales_usd|float or cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.ventas_totales_bs|float or cierre.total_ventas_efectivo_bs|float or 0) }}</span>"""
        
        new_html_user = """                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}</span>"""
        
        if old_html_user in c:
            c = c.replace(old_html_user, new_html_user)
            p_user_html.write_text(c, encoding='utf-8')
            print("✅ user/caja.html: Ahora usa los campos originales de ventas.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")
    print("Los NUEVOS cierres de caja guardarán y mostrarán las ventas correctamente.")

if __name__ == '__main__':
    main()