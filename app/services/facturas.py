# app/services/facturas.py
import os
import logging
from datetime import datetime

from flask import current_app
from ..models.config import ConfigEmpresa
from ..utils.helpers import formatear_fecha


logger = logging.getLogger(__name__)


class FacturasService:

    @staticmethod
    def obtener_config_empresa(usuario_id):
        config = ConfigEmpresa.query.filter_by(usuario_id=usuario_id).first()
        if not config:
            return {
                'nombre': 'Mi Empresa',
                'rif': 'J-00000000-0',
                'direccion': 'Venezuela',
                'telefono': '',
                'email': '',
                'mensaje_factura': '¡Gracias por su compra!',
            }
        return {
            'nombre': config.nombre,
            'rif': config.rif,
            'direccion': config.direccion,
            'telefono': config.telefono or '',
            'email': config.email or '',
            'mensaje_factura': config.mensaje_factura or '',
        }

    @staticmethod
    def generar_html(venta_resultado, tasas, usuario_id, vendedor_nombre, config):
        """Genera el HTML de la factura y lo guarda en disco."""
        fecha = datetime.now()
        fs = fecha.strftime('%d/%m/%Y %H:%M:%S')
        nro = venta_resultado['nro_factura']
        items = venta_resultado['ventas']
        total_usd = venta_resultado['total_usd']
        total_ves = venta_resultado['total_ves']
        tipo_venta = venta_resultado['tipo_venta']
        
        # ✅ FIX: Indentación corregida y etiqueta para CASHEA
        tipo_label = 'CASHEA' if tipo_venta == 'cashea' else ('CONTADO' if tipo_venta == 'contado' else 'CRÉDITO')
        tasa_activa = tasas.get(tasas.get('activa', 'oficial'), 0)

        filas = ''
        for it in items:
            subtotal = it['cantidad'] * it['precio_usd']
            subtotal_ves = subtotal * tasa_activa
            filas += f'''
            <tr>
                <td class="tc">{it['cantidad']}</td>
                <td>{it['nombre']}</td>
                <td class="tr">${it['precio_usd']:.2f}</td>
                <td class="tr">${subtotal:.2f}</td>
                <td class="tr">Bs. {subtotal_ves:,.2f}</td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Factura {nro}</title>
<style>
@page {{ size: A4; margin: 1cm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #1e293b; margin: 0; padding: 24px; background: #fff; }}
.header {{ text-align: center; border-bottom: 3px solid #1e3a5f; padding-bottom: 16px; margin-bottom: 20px; }}
.header h1 {{ margin: 0 0 6px; font-size: 24px; color: #1e3a5f; text-transform: uppercase; letter-spacing: 1px; }}
.header .rif {{ font-size: 13px; color: #475569; font-weight: 600; }}
.header .dir, .header .contacto {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
.badge {{ display: inline-block; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
.badge-contado {{ background: #d1fae5; color: #065f46; }}
.badge-credito {{ background: #fef3c7; color: #92400e; }}
.badge-cashea {{ background: #f3e8ff; color: #7e22ce; border: 1px solid #d8b4fe; }}
.info {{ display: flex; justify-content: space-between; gap: 20px; margin-bottom: 20px; font-size: 11px; background: #f8fafc; padding: 14px 18px; border-radius: 8px; border: 1px solid #e2e8f0; }}
.info strong {{ color: #1e3a5f; display: inline-block; min-width: 70px; }}
table.items {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 11px; }}
table.items thead th {{ background: #1e3a5f; color: white; padding: 10px 12px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
table.items tbody td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }}
table.items tbody tr:hover {{ background: #f8fafc; }}
.tr {{ text-align: right; }}
.tc {{ text-align: center; }}
.totales {{ width: 100%; max-width: 340px; margin-left: auto; margin-top: 12px; }}
.totales table {{ width: 100%; font-size: 12px; }}
.totales td {{ padding: 8px 12px; }}
.totales .tf {{ font-size: 18px; font-weight: 700; color: #1e3a5f; border-top: 2px solid #1e3a5f; }}
.tasa-info {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 10px 16px; margin: 16px 0; font-size: 11px; border-radius: 4px; }}
.tasa-info strong {{ color: #92400e; }}
.obs {{ background: #f1f5f9; border-left: 4px solid #64748b; padding: 12px 16px; margin: 16px 0; font-size: 11px; border-radius: 4px; }}
.footer {{ text-align: center; border-top: 2px solid #1e3a5f; padding-top: 14px; margin-top: 24px; font-size: 10px; color: #64748b; }}
.footer .mensaje {{ font-size: 12px; color: #1e3a5f; font-weight: 600; margin-bottom: 6px; }}
@media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
</style>
</head>
<body>
<div class="header">
    <h1>{config['nombre']}</h1>
    <div class="rif">RIF: {config['rif']}</div>
    <div class="dir">{config['direccion']}</div>
    <div class="contacto">Tel: {config['telefono']} | Email: {config['email']}</div>
</div>

<div style="text-align:center; margin-bottom:16px;">
    <span class="badge badge-{tipo_venta}">{tipo_label}</span>
</div>

<div class="info">
    <div>
        <div><strong>Factura:</strong> {nro}</div>
        <div><strong>Fecha:</strong> {fs}</div>
        <div><strong>Vendedor:</strong> {vendedor_nombre}</div>
    </div>
    <div>
        <div><strong>Cliente:</strong> {venta_resultado.get('cliente_nombre', 'Consumidor Final')}</div>
        <div><strong>Pago:</strong> {venta_resultado.get('metodo_pago', 'Efectivo').upper()}</div>
        <div><strong>Tasa:</strong> {tasas.get('activa', 'Oficial').upper()}</div>
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
    <tbody>{filas}</tbody>
</table>

<div class="totales">
    <table>
        <tr><td><strong>Total USD:</strong></td><td class="tr">${total_usd:.2f}</td></tr>
        <tr><td><strong>Total VES:</strong></td><td class="tr tf">Bs. {total_ves:,.2f}</td></tr>
    </table>
</div>

<div class="tasa-info">
    <strong>Tasa aplicada:</strong> {tasas.get('activa', 'Oficial').upper()} — Bs. {tasa_activa:,.2f} / USD
</div>

{f'<div class="obs"><strong>Observaciones:</strong> {venta_resultado.get("observaciones", "")}</div>' if venta_resultado.get('observaciones') else ''}

<div class="footer">
    <div class="mensaje">{config.get('mensaje_factura', '¡Gracias por su compra!')}</div>
    <p>Documento generado el {fs}</p>
</div>
</body>
</html>'''

        facturas_dir = current_app.config.get("FACTURAS_DIR", "facturas")
        os.makedirs(facturas_dir, exist_ok=True)
        filename = f'factura_{nro.replace("/", "-")}_{usuario_id}.html'
        filepath = os.path.join(facturas_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        return filename