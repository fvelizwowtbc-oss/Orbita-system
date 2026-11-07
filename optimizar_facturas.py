import re
import shutil
from pathlib import Path

def log(msg, color='\033[0m'):
    print(f"{color}{msg}\033[0m")

def main():
    log("\n==================================================", '\033[96m')
    log("   OPTIMIZACIÓN: FACTURAS SIN CONSUMIR DISCO", '\033[96m')
    log("==================================================\n", '\033[96m')

    # 1. CREAR EL TEMPLATE HTML
    log("1. Creando plantilla de factura (factura_template.html)...")
    template_path = Path('app/templates/user/factura_template.html')
    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Factura {{ factura.nro_factura }}</title>
    <style>
        @page { size: A4; margin: 1cm; }
        * { box-sizing: border-box; }
        body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #1e293b; margin: 0; padding: 24px; background: #fff; }
        .header { text-align: center; border-bottom: 3px solid #1e3a5f; padding-bottom: 16px; margin-bottom: 20px; }
        .header h1 { margin: 0 0 6px; font-size: 24px; color: #1e3a5f; text-transform: uppercase; letter-spacing: 1px; }
        .header .rif { font-size: 13px; color: #475569; font-weight: 600; }
        .header .dir, .header .contacto { font-size: 11px; color: #64748b; margin-top: 4px; }
        .badge { display: inline-block; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
        .badge-contado { background: #d1fae5; color: #065f46; }
        .badge-credito { background: #fef3c7; color: #92400e; }
        .badge-cashea { background: #f3e8ff; color: #7e22ce; border: 1px solid #d8b4fe; }
        .info { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 20px; font-size: 11px; background: #f8fafc; padding: 14px 18px; border-radius: 8px; border: 1px solid #e2e8f0; }
        .info strong { color: #1e3a5f; display: inline-block; min-width: 70px; }
        table.items { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 11px; }
        table.items thead th { background: #1e3a5f; color: white; padding: 10px 12px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
        table.items tbody td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }
        table.items tbody tr:hover { background: #f8fafc; }
        .tr { text-align: right; }
        .tc { text-align: center; }
        .totales { width: 100%; max-width: 340px; margin-left: auto; margin-top: 12px; }
        .totales table { width: 100%; font-size: 12px; }
        .totales td { padding: 8px 12px; }
        .totales .tf { font-size: 18px; font-weight: 700; color: #1e3a5f; border-top: 2px solid #1e3a5f; }
        .tasa-info { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 10px 16px; margin: 16px 0; font-size: 11px; border-radius: 4px; }
        .footer { text-align: center; border-top: 2px solid #1e3a5f; padding-top: 14px; margin-top: 24px; font-size: 10px; color: #64748b; }
        @media print { body { padding: 0; } .no-print { display: none; } }
    </style>
</head>
<body>
<div class="header">
    <h1>{{ config.nombre }}</h1>
    <div class="rif">RIF: {{ config.rif }}</div>
    <div class="dir">{{ config.direccion }}</div>
    <div class="contacto">Tel: {{ config.telefono }} | Email: {{ config.email }}</div>
</div>

<div style="text-align:center; margin-bottom:16px;">
    <span class="badge badge-{{ factura.tipo_venta }}">
        {{ 'CASHEA' if factura.tipo_venta == 'cashea' else ('CONTADO' if factura.tipo_venta == 'contado' else 'CRÉDITO') }}
    </span>
</div>

<div class="info">
    <div>
        <div><strong>Factura:</strong> {{ factura.nro_factura }}</div>
        <div><strong>Fecha:</strong> {{ factura.fecha_creacion.strftime('%d/%m/%Y %H:%M') if factura.fecha_creacion else '' }}</div>
        <div><strong>Vendedor:</strong> {{ vendedor_nombre }}</div>
    </div>
    <div>
        <div><strong>Cliente:</strong> {{ factura.cliente_nombre }}</div>
        <div><strong>Pago:</strong> {{ factura.venta.metodo_pago|upper if factura.venta else 'EFECTIVO' }}</div>
        <div><strong>Tasa:</strong> {{ tasas.activa|upper }}</div>
    </div>
</div>

<table class="items">
    <thead>
        <tr>
            <th class="tc">Cant</th>
            <th>Producto</th>
            <th class="tr">P. Unit (USD)</th>
            <th class="tr">Total (USD)</th>
            <th class="tr">Total (VES)</th>
        </tr>
    </thead>
    <tbody>
        {% for v in ventas %}
        <tr>
            <td class="tc">{{ v.cantidad }}</td>
            <td>{{ v.producto.nombre if v.producto else 'Producto' }}</td>
            <td class="tr">${{ "%.2f"|format(v.precio_usd) }}</td>
            <td class="tr">${{ "%.2f"|format(v.total_usd) }}</td>
            <td class="tr">Bs. {{ "%.2f"|format(v.total_usd * tasa_activa) }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<div class="totales">
    <table>
        <tr><td><strong>Total USD:</strong></td><td class="tr">${{ "%.2f"|format(factura.total_usd) }}</td></tr>
        <tr><td><strong>Total VES:</strong></td><td class="tr tf">Bs. {{ "%.2f"|format(factura.total_ves) }}</td></tr>
    </table>
</div>

<div class="tasa-info">
    <strong>Tasa aplicada:</strong> {{ tasas.activa|upper }} — Bs. {{ "%.2f"|format(tasa_activa) }} / USD
</div>

<div class="footer">
    <div style="font-size: 12px; color: #1e3a5f; font-weight: 600; margin-bottom: 6px;">{{ config.mensaje_factura }}</div>
    <p>Documento generado electrónicamente</p>
</div>
</body>
</html>"""
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(html_template, encoding='utf-8')
    log("  [OK] factura_template.html creado.", '\033[92m')

    # 2. MODIFICAR EL SERVICIO (facturas.py)
    log("2. Modificando app/services/facturas.py...")
    p_serv = Path('app/services/facturas.py')
    if p_serv.exists():
        c = p_serv.read_text(encoding='utf-8')
        # Buscar todo el bloque donde escribe en el disco
        patron = re.compile(r"        facturas_dir = current_app.*?return filename", re.DOTALL)
        if patron.search(c):
            c = patron.sub("        return nro.replace('/', '-')", c)
            shutil.copy2(p_serv, p_serv.with_suffix('.py.bak_pro'))
            p_serv.write_text(c, encoding='utf-8')
            log("  [OK] Servicio ya no guarda archivos HTML.", '\033[92m')

    # 3. ACTUALIZAR RUTAS DE VISUALIZACIÓN
    log("3. Actualizando rutas de visualización...")
    
    # 3.1 USER.PY
    p_user = Path('app/routes/user.py')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        patron_user = re.compile(r"@user_bp\.route\('/factura/<int:factura_id>/ver-modal'\).*?(?=@user_bp\.route|def _)", re.DOTALL)
        nueva_ruta_user = """@user_bp.route('/factura/<int:factura_id>/ver-modal')
def ver_factura_modal(factura_id):
    from ..models.factura import FacturaCobrar
    from ..models.venta import Venta
    from ..services.facturas import FacturasService
    from ..services.tasas import TasasService
    
    factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=current_user.id).first_or_404()
    ventas = Venta.query.filter_by(nro_factura=factura.nro_factura, usuario_id=current_user.id).all()
    
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
        if patron_user.search(c):
            c = patron_user.sub(nueva_ruta_user, c)
            shutil.copy2(p_user, p_user.with_suffix('.py.bak_pro'))
            p_user.write_text(c, encoding='utf-8')
            log("  [OK] user.py actualizado (renderiza al vuelo).", '\033[92m')

    # 3.2 VENDEDOR.PY
    p_vend = Path('app/routes/vendedor.py')
    if p_vend.exists():
        c = p_vend.read_text(encoding='utf-8')
        patron_vend = re.compile(r"@vendedor_bp\.route\('/factura/<int:factura_id>/ver-modal'\).*?(?=@vendedor_bp\.route|def _)", re.DOTALL)
        nueva_ruta_vend = """@vendedor_bp.route('/factura/<int:factura_id>/ver-modal')
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
        if patron_vend.search(c):
            c = patron_vend.sub(nueva_ruta_vend, c)
            shutil.copy2(p_vend, p_vend.with_suffix('.py.bak_pro'))
            p_vend.write_text(c, encoding='utf-8')
            log("  [OK] vendedor.py actualizado (renderiza al vuelo).", '\033[92m')

    log("\n==================================================", '\033[92m')
    log(" ¡OPTIMIZACIÓN COMPLETADA!", '\033[92m')
    log("==================================================\n", '\033[92m')
    log("Ya puedes subir esto a GitHub. Tus facturas se generarán en memoria", '\033[93m')
    log("sin gastar ni un megabyte de almacenamiento en Render o tu VPS.", '\033[93m')

if __name__ == '__main__':
    main()