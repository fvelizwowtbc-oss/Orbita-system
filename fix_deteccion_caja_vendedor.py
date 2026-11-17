import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO DETECCIÓN DE CAJA EN VENDEDOR")
    print("==================================================\n")

    # 1. ARREGLAR LA RUTA DE VENTAS (vendedor.py)
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_fix_caja')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        # Buscar donde se renderiza la plantilla de ventas
        old_render = """    return render_template(
        'vendedor/ventas.html',
        productos=productos,
        ventas_recientes=ventas_recientes,
        stats=stats,

        clientes=clientes,
        tasas=tasas,
    )"""
        
        new_render = """    from ..models.caja import CajaTurno
    # ✅ Buscar la caja abierta DEL VENDEDOR
    caja_abierta = CajaTurno.query.filter_by(vendedor_id=current_user.id, estado='abierta').first()

    return render_template(
        'vendedor/ventas.html',
        productos=productos,
        ventas_recientes=ventas_recientes,
        stats=stats,
        clientes=clientes,
        tasas=tasas,
        caja_abierta=caja_abierta,
    )"""
        
        if old_render in c:
            c = c.replace(old_render, new_render)
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ Ruta de ventas del vendedor actualizada para buscar SU caja abierta.")
        else:
            print("⚠️ No se encontró el bloque exacto en ventas(). Buscando variante...")
            # Intento alternativo buscando la función def ventas()
            import re
            patron = re.compile(r'(def ventas\(\):.*?return render_template\s*\(\s*\'vendedor/ventas\.html\'.*?\))', re.DOTALL)
            if patron.search(c):
                # Reemplazar solo el return
                c = c.replace(
                    "return render_template(\n        'vendedor/ventas.html',",
                    "from ..models.caja import CajaTurno\n    caja_abierta = CajaTurno.query.filter_by(vendedor_id=current_user.id, estado='abierta').first()\n    return render_template(\n        'vendedor/ventas.html',\n        caja_abierta=caja_abierta,"
                )
                p_vendedor.write_text(c, encoding='utf-8')
                print("✅ Ruta actualizada (método alternativo).")

    # 2. ARREGLAR LA LÓGICA DE SUMAR VENTAS A LA CAJA (services/ventas.py)
    p_ventas_service = Path('app/services/ventas.py')
    if p_ventas_service.exists():
        c = p_ventas_service.read_text(encoding='utf-8')
        bak = p_ventas_service.with_suffix('.py.bak_caja_vend')
        if not bak.exists(): shutil.copy2(p_ventas_service, bak)

        # La suma a la caja debe hacerse a la caja del vendedor si aplica
        old_suma = """            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo == 'efectivo':
                caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, estado='abierta').first()
                if caja_abierta:
                    caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))"""
        
        new_suma = """            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo == 'efectivo':
                # Intentar buscar la caja del vendedor primero
                vendedor_id = data.get('vendedor_id') or vendedor_id
                if vendedor_id:
                    caja_abierta = CajaTurno.query.filter_by(vendedor_id=vendedor_id, estado='abierta').first()
                else:
                    caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, vendedor_id=None, estado='abierta').first()
                
                if caja_abierta:
                    caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))"""
        
        if old_suma in c:
            c = c.replace(old_suma, new_suma)
            p_ventas_service.write_text(c, encoding='utf-8')
            print("✅ Servicio de ventas actualizado para sumar a la caja del vendedor.")
        else:
            print("⚠️ No se encontró el bloque de suma a caja en ventas.py (puede que ya esté bien).")

    print("\n👉 Reinicia Flask con Ctrl+C y run.py, y recarga la página del vendedor con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()