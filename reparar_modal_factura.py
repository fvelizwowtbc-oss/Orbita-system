import re
import shutil
from pathlib import Path

def log(msg, color='\033[0m'):
    print(f"{color}{msg}\033[0m")

def main():
    log("\n==================================================", '\033[96m')
    log("   REPARANDO MODAL DE FACTURA (HTTP 500)", '\033[96m')
    log("==================================================\n", '\033[96m')

    # 1. REPARAR USER.PY
    p_user = Path('app/routes/user.py')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        
        # Buscar la función actual desde el decorador hasta la siguiente ruta
        patron = re.compile(r"@user_bp\.route\('/factura/<int:factura_id>/ver-modal'\).*?(?=@user_bp\.route|def )", re.DOTALL)
        
        nueva_funcion = """@user_bp.route('/factura/<int:factura_id>/ver-modal')
def ver_factura_modal(factura_id):
    from ..models.factura import FacturaCobrar
    from ..models.venta import Venta
    from ..services.facturas import FacturasService
    from ..services.tasas import TasasService
    
    factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=current_user.id).first_or_404()
    
    # Traer todas las ventas de esa factura
    ventas = Venta.query.filter_by(nro_factura=factura.nro_factura, usuario_id=current_user.id).all()
    
    # Traer configuración y tasas
    config = FacturasService.obtener_config_empresa(current_user.id)
    tasas = TasasService.obtener_tasas(current_user.id)
    tasa_activa = float(tasas.get(tasas.get('activa', 'oficial'), 0))
    
    return render_template('user/factura_template.html',
        factura=factura,
        ventas=ventas,
        config=config,
        tasas=tasas,
        tasa_activa=tasa_activa,
        vendedor_nombre=current_user.nombre
    )

"""
        if patron.search(c):
            c = patron.sub(nueva_funcion, c)
            bak = p_user.with_suffix('.py.bak_modal')
            if not bak.exists(): shutil.copy2(p_user, bak)
            p_user.write_text(c, encoding='utf-8')
            log("  [OK] user.py reparado.", '\033[92m')
        else:
            log("  [!!] No se encontró la función en user.py", '\033[93m')

    # 2. REPARAR VENDEDOR.PY
    p_vend = Path('app/routes/vendedor.py')
    if p_vend.exists():
        c = p_vend.read_text(encoding='utf-8')
        
        patron = re.compile(r"@vendedor_bp\.route\('/factura/<int:factura_id>/ver-modal'\).*?(?=@vendedor_bp\.route|def )", re.DOTALL)
        
        nueva_funcion_vend = """@vendedor_bp.route('/factura/<int:factura_id>/ver-modal')
def ver_factura_modal(factura_id):
    from ..models.factura import FacturaCobrar
    from ..models.venta import Venta
    from ..services.facturas import FacturasService
    from ..services.tasas import TasasService
    
    padre_id = current_user.usuario_padre_id
    factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=padre_id).first_or_404()
    
    ventas = Venta.query.filter_by(nro_factura=factura.nro_factura, usuario_id=padre_id).all()
    
    config = FacturasService.obtener_config_empresa(padre_id)
    tasas = TasasService.obtener_tasas(padre_id)
    tasa_activa = float(tasas.get(tasas.get('activa', 'oficial'), 0))
    
    return render_template('user/factura_template.html',
        factura=factura,
        ventas=ventas,
        config=config,
        tasas=tasas,
        tasa_activa=tasa_activa,
        vendedor_nombre=current_user.nombre
    )

"""
        if patron.search(c):
            c = patron.sub(nueva_funcion_vend, c)
            bak = p_vend.with_suffix('.py.bak_modal')
            if not bak.exists(): shutil.copy2(p_vend, bak)
            p_vend.write_text(c, encoding='utf-8')
            log("  [OK] vendedor.py reparado.", '\033[92m')
        else:
            log("  [!!] No se encontró la función en vendedor.py", '\033[93m')

    # 3. VERIFICAR EL SERVICIO (facturas.py)
    p_serv = Path('app/services/facturas.py')
    if p_serv.exists():
        c = p_serv.read_text(encoding='utf-8')
        if 'def obtener_config_empresa' not in c:
            log("  [!!] Falta obtener_config_empresa en facturas.py", '\033[91m')
        else:
            log("  [OK] facturas.py tiene la función de configuración.", '\033[92m')

    log("\n==================================================", '\033[92m')
    log(" ¡REPARACIÓN COMPLETADA!", '\033[92m')
    log("==================================================\n", '\033[92m')
    log("Reinicia Flask y vuelve a probar el botón del ojo.", '\033[93m')

if __name__ == '__main__':
    main()