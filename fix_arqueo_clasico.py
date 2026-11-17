import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO ARQUEO CLÁSICO (POR MONEDA)")
    print("==================================================\n")

    # 1. CORREGIR LA LÓGICA EN user.py (Dueño)
    p_user = Path('app/routes/user.py')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        bak = p_user.with_suffix('.py.bak_arqueo_clasico')
        if not bak.exists(): shutil.copy2(p_user, bak)

        # Buscar el bloque de cálculo actual
        patron = re.compile(r"# ✅ Cálculo por MONEDA \(sin conversiones\).*?caja\.tasa_cierre = tasa_bcv", re.DOTALL)
        
        nueva_logica = """        # ✅ ARQUEO CLÁSICO POR MONEDA
        
        # 1. Diferencia en Dólares
        # (Físico USD) - (Base Inicial USD + Ventas USD)
        real_usd = float(caja.saldo_real_usd)
        esperado_usd = float(caja.saldo_inicial_usd) + float(caja.total_ventas_efectivo_usd)
        caja.diferencia_usd = real_usd - esperado_usd
        
        # 2. Diferencia en Bolívares
        # (Físico Bs) - (Base Inicial Bs + Ventas Bs)
        real_bs = float(caja.saldo_real_bs)
        esperado_bs = float(caja.saldo_inicial_bs) + float(caja.total_ventas_efectivo_bs)
        caja.diferencia_bs = real_bs - esperado_bs
        
        caja.tasa_cierre = tasa_bcv"""
        
        if patron.search(c):
            c = patron.sub(nueva_logica, c)
            p_user.write_text(c, encoding='utf-8')
            print("✅ user.py: Fórmula de arqueo corregida (por moneda).")
        else:
            # Buscar la fórmula anterior si el regex falla
            old_calc = re.compile(r"# 1\. Calcular todo en USD para unificar.*?caja\.tasa_cierre = tasa_bcv", re.DOTALL)
            if old_calc.search(c):
                c = old_calc.sub(nueva_logica, c)
                p_user.write_text(c, encoding='utf-8')
                print("✅ user.py: Fórmula corregida (método alternativo).")

    # 2. CORREGIR LA LÓGICA EN vendedor.py (Vendedor)
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_arqueo_clasico')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        # Buscar el bloque de cálculo actual en vendedor.py
        patron_vend = re.compile(r"# Arqueo\n.*?caja\.tasa_cierre = tasa_bcv", re.DOTALL)
        
        if patron_vend.search(c):
            c = patron_vend.sub(nueva_logica, c)
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ vendedor.py: Fórmula de arqueo corregida (por moneda).")
        else:
            # Intentar buscar la fórmula vieja
            old_calc_vend = re.compile(r"# 1\. Convertir TODO a USD para una comparación justa.*?caja\.tasa_cierre = tasa_bcv", re.DOTALL)
            if old_calc_vend.search(c):
                c = old_calc_vend.sub(nueva_logica, c)
                p_vendedor.write_text(c, encoding='utf-8')
                print("✅ vendedor.py: Fórmula corregida (método alternativo).")

    # 3. ACTUALIZAR EL MODAL DE ARQUEO EN EL HTML (user/caja.html)
    p_html = Path('app/templates/user/caja.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_clasico')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # Actualizar el resumen del modal para que sea claro
        old_resumen = """            <div class="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4 text-sm text-slate-600 space-y-1">
                <p><i class="fas fa-lock text-slate-400 w-4"></i> <strong>Base de Apertura:</strong> ${{ "%.2f"|format(caja_abierta.saldo_inicial_usd|float) }} + Bs. {{ "%.2f"|format(caja_abierta.saldo_inicial_bs|float) }}</p>
                <p><i class="fas fa-shopping-cart text-slate-400 w-4"></i> <strong>Ventas en Efectivo:</strong> ${{ "%.2f"|format(caja_abierta.total_ventas_efectivo_usd|float) }} + Bs. {{ "%.2f"|format(caja_abierta.total_ventas_efectivo_bs|float) }}</p>
                <div class="border-t border-slate-200 mt-2 pt-2">
                    <p><i class="fas fa-calculator text-slate-400 w-4"></i> <strong>Total Esperado en Gaveta:</strong> ${{ "%.2f"|format((caja_abierta.saldo_inicial_usd|float) + (caja_abierta.total_ventas_efectivo_usd|float)) }} + Bs. {{ "%.2f"|format((caja_abierta.saldo_inicial_bs|float) + (caja_abierta.total_ventas_efectivo_bs|float)) }}</p>
                </div>
            </div>"""
        
        new_resumen = """            <div class="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4 text-sm text-slate-600 space-y-2">
                <div class="bg-blue-50 p-2 rounded border border-blue-100">
                    <p class="text-blue-800 font-semibold mb-1">Dólares (USD)</p>
                    <p><i class="fas fa-lock text-blue-400 w-4"></i> Base: ${{ "%.2f"|format(caja_abierta.saldo_inicial_usd|float) }}</p>
                    <p><i class="fas fa-shopping-cart text-blue-400 w-4"></i> Ventas: ${{ "%.2f"|format(caja_abierta.total_ventas_efectivo_usd|float) }}</p>
                    <p class="border-t border-blue-200 mt-1 pt-1 font-bold"><i class="fas fa-calculator text-blue-400 w-4"></i> Esperado: ${{ "%.2f"|format((caja_abierta.saldo_inicial_usd|float) + (caja_abierta.total_ventas_efectivo_usd|float)) }}</p>
                </div>
                <div class="bg-amber-50 p-2 rounded border border-amber-100">
                    <p class="text-amber-800 font-semibold mb-1">Bolívares (Bs)</p>
                    <p><i class="fas fa-lock text-amber-400 w-4"></i> Base: Bs. {{ "%.2f"|format(caja_abierta.saldo_inicial_bs|float) }}</p>
                    <p><i class="fas fa-shopping-cart text-amber-400 w-4"></i> Ventas: Bs. {{ "%.2f"|format(caja_abierta.total_ventas_efectivo_bs|float) }}</p>
                    <p class="border-t border-amber-200 mt-1 pt-1 font-bold"><i class="fas fa-calculator text-amber-400 w-4"></i> Esperado: Bs. {{ "%.2f"|format((caja_abierta.saldo_inicial_bs|float) + (caja_abierta.total_ventas_efectivo_bs|float)) }}</p>
                </div>
            </div>"""
        
        if old_resumen in c:
            c = c.replace(old_resumen, new_resumen)
            p_html.write_text(c, encoding='utf-8')
            print("✅ user/caja.html: Modal de cierre actualizado (desglose por moneda).")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")
    print("Ahora el sistema calcula la diferencia restando (Base + Ventas) del efectivo físico contado.")

if __name__ == '__main__':
    main()