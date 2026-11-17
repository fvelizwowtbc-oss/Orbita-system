import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   SEPARANDO VENTAS POR MONEDA (BS vs USD)")
    print("==================================================\n")

    p = Path('app/services/ventas.py')
    if not p.exists():
        print("❌ No se encontró services/ventas.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_separar_moneda')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar el bloque donde se suma a la caja
    patron = re.compile(
        r"(\s*# ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO.*?caja_abierta\.total_ventas_efectivo_bs = .*?\n)",
        re.DOTALL
    )

    nuevo_bloque = """
            # ✅ SUMAR A LA CAJA SOLO A LA MONEDA CORRESPONDIENTE
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo in ('efectivo', 'divisa'):
                from decimal import Decimal
                
                # Identificar si la venta la hizo un vendedor
                vendedor_actual_id = data.get('vendedor_id') or vendedor_id
                
                if vendedor_actual_id:
                    caja_abierta = CajaTurno.query.filter_by(vendedor_id=vendedor_actual_id, estado='abierta').first()
                else:
                    caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, vendedor_id=None, estado='abierta').first()

                if caja_abierta:
                    # Si paga en Bs (efectivo), sumar SOLO a la caja en Bs
                    if metodo == 'efectivo':
                        caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))
                    # Si paga en Divisas ($), sumar SOLO a la caja en Dólares
                    elif metodo == 'divisa':
                        caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
"""

    if patron.search(c):
        c = patron.sub(nuevo_bloque, c)
        p.write_text(c, encoding='utf-8')
        print("✅ services/ventas.py: Lógica separada. Ahora suma solo a la moneda pagada.")
    else:
        print("⚠️ No se encontró el bloque exacto. Intentando método alternativo...")
        
        # Buscar el bloque viejo (el de la versión anterior)
        old_block = """            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
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
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))"""
        
        if old_block in c:
            c = c.replace(old_block, nuevo_bloque)
            p.write_text(c, encoding='utf-8')
            print("✅ services/ventas.py: Lógica corregida (método alternativo).")
        else:
            print("❌ No se encontró el bloque. Revisa el archivo manualmente.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py).")
    print("Prueba haciendo una venta pagada en Bs y otra en Divisas.")
    print("Verás que en la caja se suman por separado a la moneda correcta.")

if __name__ == '__main__':
    main()