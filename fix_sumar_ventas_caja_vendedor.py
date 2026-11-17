import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO SUMA DE VENTAS A LA CAJA DEL VENDEDOR")
    print("==================================================\n")

    p = Path('app/services/ventas.py')
    if not p.exists():
        print("❌ No se encontró services/ventas.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_suma_ventas')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar el bloque donde se suma a la caja
    patron = re.compile(
        r"(\s*# ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO.*?caja_abierta\.total_ventas_efectivo_bs = .*?\n)",
        re.DOTALL
    )

    nuevo_bloque = """
            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo == 'efectivo':
                from decimal import Decimal
                
                # Identificar si la venta la hizo un vendedor
                vendedor_actual_id = data.get('vendedor_id') or vendedor_id
                
                if vendedor_actual_id:
                    # Es vendedor: buscar SU caja abierta
                    caja_abierta = CajaTurno.query.filter_by(vendedor_id=vendedor_actual_id, estado='abierta').first()
                else:
                    # Es dueño: buscar SU caja abierta (sin vendedor)
                    caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, vendedor_id=None, estado='abierta').first()

                if caja_abierta:
                    # Sumar montos (usando Decimal para evitar errores de precisión)
                    caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))
            
            db.session.commit()
"""

    if patron.search(c):
        c = patron.sub(nuevo_bloque, c)
        p.write_text(c, encoding='utf-8')
        print("✅ services/ventas.py: Lógica de suma a la caja corregida (detecta vendedor).")
    else:
        print("⚠️ No se encontró el bloque exacto. Intentando método alternativo...")
        
        # Buscar el bloque viejo (el que teníamos antes)
        old_block = """            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo == 'efectivo':
                caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, estado='abierta').first()
                if caja_abierta:
                    caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))"""
        
        if old_block in c:
            c = c.replace(old_block, nuevo_bloque)
            p.write_text(c, encoding='utf-8')
            print("✅ services/ventas.py: Lógica corregida (método alternativo).")
        else:
            print("❌ No se encontró el bloque. Revisa el archivo manualmente.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py).")
    print("Abre una caja como vendedor, haz una venta en efectivo, y luego cierra la caja.")
    print("El historial debería mostrar las ventas de ese turno.")

if __name__ == '__main__':
    main()