from pathlib import Path
import shutil

def main():
    print("\n==================================================")
    print("   CORRIGIENDO LÍNEA ESPECÍFICA DE CAJA (VENDEDOR)")
    print("==================================================\n")

    p = Path('app/routes/vendedor.py')
    if not p.exists():
        print("❌ No se encontró vendedor.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_linea')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Reemplazar la línea exacta que está fallando
    # La línea original es:
    # real_usd = float(caja.saldo_real_usd)
    # Y debe ser:
    # real_usd = float(caja.saldo_real_usd or 0)

    # Pero además, todas las líneas siguientes que hagan cálculos deben estar protegidas.
    # Vamos a reemplazar el bloque completo de cálculo desde "real_usd = ..." hasta "caja.tasa_cierre = tasa_bcv"

    import re
    patron = re.compile(
        r"(real_usd = float\(caja\.saldo_real_usd\).*?caja\.tasa_cierre = tasa_bcv)",
        re.DOTALL
    )
    
    match = patron.search(c)
    if match:
        bloque_viejo = match.group(1)
        
        # Construir el nuevo bloque blindado
        nuevo_bloque = """real_usd = float(caja.saldo_real_usd or 0)
        real_bs = float(caja.saldo_real_bs or 0)
        
        esperado_usd = float(caja.saldo_inicial_usd or 0) + float(caja.total_ventas_efectivo_usd or 0)
        esperado_bs = float(caja.saldo_inicial_bs or 0) + float(caja.total_ventas_efectivo_bs or 0)
        
        caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        caja.tasa_cierre = tasa_bcv"""
        
        c = c.replace(bloque_viejo, nuevo_bloque)
        p.write_text(c, encoding='utf-8')
        print("✅ vendedor.py: Bloque de cálculo de cierre de caja blindado (línea corregida).")
    else:
        # Si no encuentra el bloque exacto, intentamos un reemplazo más simple
        print("⚠️ No se encontró el bloque exacto. Intentando reemplazo línea por línea...")
        
        lineas = c.split('\n')
        nuevas_lineas = []
        for linea in lineas:
            if 'real_usd = float(caja.saldo_real_usd)' in linea:
                nuevas_lineas.append('        real_usd = float(caja.saldo_real_usd or 0)')
            elif 'real_bs = float(caja.saldo_real_bs)' in linea:
                nuevas_lineas.append('        real_bs = float(caja.saldo_real_bs or 0)')
            elif 'esperado_usd = float(caja.saldo_inicial_usd)' in linea:
                nuevas_lineas.append('        esperado_usd = float(caja.saldo_inicial_usd or 0) + float(caja.total_ventas_efectivo_usd or 0)')
            elif 'esperado_bs = float(caja.saldo_inicial_bs)' in linea:
                nuevas_lineas.append('        esperado_bs = float(caja.saldo_inicial_bs or 0) + float(caja.total_ventas_efectivo_bs or 0)')
            elif 'caja.diferencia_usd = real_usd - esperado_usd' in linea:
                nuevas_lineas.append('        caja.diferencia_usd = real_usd - esperado_usd')
            elif 'caja.diferencia_bs = real_bs - esperado_bs' in linea:
                nuevas_lineas.append('        caja.diferencia_bs = real_bs - esperado_bs')
            else:
                nuevas_lineas.append(linea)
        
        c = '\n'.join(nuevas_lineas)
        p.write_text(c, encoding='utf-8')
        print("✅ vendedor.py: Líneas de cálculo blindadas manualmente.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página de Caja del vendedor con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()