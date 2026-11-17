import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   REPARANDO CIERRE DE CAJA (VENDEDOR) DEFINITIVO")
    print("==================================================\n")

    p = Path('app/routes/vendedor.py')
    if not p.exists():
        print("❌ No se encontró vendedor.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_definitivo')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Buscar la función cerrar_caja completa y reescribirla
    # Buscamos desde "@vendedor_bp.route('/caja/cerrar'" hasta el siguiente decorador o def
    patron = re.compile(
        r"@vendedor_bp\.route\('/caja/cerrar'.*?(?=\n@vendedor_bp|\n# ============================================================|\Z)",
        re.DOTALL
    )

    match = patron.search(c)
    if not match:
        print("❌ No se encontró la función cerrar_caja en vendedor.py")
        return

    nueva_funcion = """@vendedor_bp.route('/caja/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    vid = current_user.id
    caja = CajaTurno.query.filter_by(vendedor_id=vid, estado='abierta').first()
    
    if caja:
        caja.estado = 'cerrada'
        caja.cerrada_en = datetime.utcnow()
        
        # Obtener tasa de forma segura
        from ..services.tasas import TasasService
        try:
            tasa_bcv = float(TasasService.obtener_tasa_bcv() or 1.0)
        except (TypeError, ValueError):
            tasa_bcv = 1.0
        if tasa_bcv <= 0:
            tasa_bcv = 1.0
        
        # Leer montos reales del formulario
        raw_usd = request.form.get('saldo_real_usd')
        raw_bs = request.form.get('saldo_real_bs')
        
        real_usd = float(raw_usd) if raw_usd and raw_usd.strip() else 0.0
        real_bs = float(raw_bs) if raw_bs and raw_bs.strip() else 0.0
        
        caja.saldo_real_usd = real_usd
        caja.saldo_real_bs = real_bs
        
        # Calcular esperado
        base_usd = float(caja.saldo_inicial_usd or 0)
        base_bs = float(caja.saldo_inicial_bs or 0)
        ventas_usd = float(caja.total_ventas_efectivo_usd or 0)
        ventas_bs = float(caja.total_ventas_efectivo_bs or 0)
        
        esperado_usd = base_usd + ventas_usd
        esperado_bs = base_bs + ventas_bs
        
        # Diferencia
        caja.diferencia_usd = real_usd - esperado_usd
        caja.diferencia_bs = real_bs - esperado_bs
        
        caja.tasa_cierre = tasa_bcv
        
        db.session.commit()
        flash('Caja cerrada correctamente. Turno finalizado.', 'success')
    else:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        
    return redirect(url_for('vendedor.caja'))"""

    c = patron.sub(nueva_funcion, c)
    p.write_text(c, encoding='utf-8')
    print("✅ vendedor.py: Función cerrar_caja reescrita y blindada.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página de Caja del vendedor con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()