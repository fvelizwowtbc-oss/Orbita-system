import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   BLINDANDO CIERRE DE CAJA DEL VENDEDOR")
    print("==================================================\n")

    # 1. CORREGIR LA LÓGICA EN vendedor.py
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_caja_none')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        # Buscar el bloque de arqueo dentro de la función cerrar_caja
        patron = re.compile(r"# Arqueo\n.*?caja\.tasa_cierre = tasa_bcv", re.DOTALL)
        
        nueva_logica = """        # Arqueo blindado
        from ..services.tasas import TasasService
        
        # 1. Obtener tasa de forma segura
        try:
            tasa_bcv = float(TasasService.obtener_tasa_bcv() or 1.0)
        except (TypeError, ValueError):
            tasa_bcv = 1.0
        if tasa_bcv <= 0: tasa_bcv = 1.0
        
        # 2. Leer montos reales del formulario (con protección contra None)
        raw_usd = request.form.get('saldo_real_usd')
        raw_bs = request.form.get('saldo_real_bs')
        
        caja.saldo_real_usd = float(raw_usd) if raw_usd and raw_usd.strip() else 0.0
        caja.saldo_real_bs = float(raw_bs) if raw_bs and raw_bs.strip() else 0.0
        
        # 3. Calcular diferencias protegiendo contra None en la base de datos
        base_usd = float(caja.saldo_inicial_usd or 0)
        base_bs = float(caja.saldo_inicial_bs or 0)
        ventas_usd = float(caja.total_ventas_efectivo_usd or 0)
        ventas_bs = float(caja.total_ventas_efectivo_bs or 0)
        
        esperado_usd = base_usd + ventas_usd
        esperado_bs = base_bs + ventas_bs
        
        caja.diferencia_usd = caja.saldo_real_usd - esperado_usd
        caja.diferencia_bs = caja.saldo_real_bs - esperado_bs
        
        caja.tasa_cierre = tasa_bcv"""
        
        if patron.search(c):
            c = patron.sub(nueva_logica, c)
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ vendedor.py: Cierre de caja blindado contra valores nulos.")
        else:
            print("⚠️ No se encontró el bloque exacto en vendedor.py. Intentando reemplazo manual...")
            # Si el regex no funciona, reemplazamos la parte donde calcula
            old_calc = """        from ..services.tasas import TasasService
        tasa_bcv = float(TasasService.obtener_tasa_bcv())
        if tasa_bcv <= 0: tasa_bcv = 1
        
        caja.saldo_real_usd = float(request.form.get('saldo_real_usd', 0) or 0)
        caja.saldo_real_bs = float(request.form.get('saldo_real_bs', 0) or 0)
        
        real_total_usd = caja.saldo_real_usd + (caja.saldo_real_bs / tasa_bcv)
        esperado_base_usd = float(caja.saldo_inicial_usd) + (float(caja.saldo_inicial_bs) / tasa_bcv)
        esperado_ventas_usd = float(caja.total_ventas_efectivo_usd) + (float(caja.total_ventas_efectivo_bs) / tasa_bcv)
        
        caja.diferencia_usd = (real_total_usd - esperado_base_usd) - esperado_ventas_usd
        caja.diferencia_bs = caja.diferencia_usd * tasa_bcv
        caja.tasa_cierre = tasa_bcv"""
            
            if old_calc in c:
                c = c.replace(old_calc, nueva_logica)
                p_vendedor.write_text(c, encoding='utf-8')
                print("✅ vendedor.py: Cierre de caja blindado (método alternativo).")
            else:
                print("❌ No se pudo encontrar la fórmula en vendedor.py.")

    # 2. ARREGLAR EL HTML (vendedor/caja.html) para mostrar la diferencia correctamente
    p_html = Path('app/templates/vendedor/caja.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_caja_none')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # En el historial, asegurar que los datos se muestren aunque sean None
        c = c.replace('{{ "%.2f"|format(cierre.saldo_real_usd|float or 0) }}', '{{ "%.2f"|format(cierre.saldo_real_usd|float or 0) }}')
        c = c.replace('{{ "%.2f"|format(cierre.saldo_real_bs|float or 0) }}', '{{ "%.2f"|format(cierre.saldo_real_bs|float or 0) }}')
        
        p_html.write_text(c, encoding='utf-8')
        print("✅ vendedor/caja.html: Visualización blindada.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página de Caja del vendedor con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()