# app/routes/vendedor.py
from datetime import date, datetime
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..models.producto import Producto, ProductoVariante
from ..models.venta import Venta
from ..models.cliente import Cliente
from ..models.gasto import Gasto, CATEGORIAS_GASTOS, METODOS_PAGO
from ..models.usuario import VendedorConfig
from ..services.tasas import TasasService
from ..services.ventas import VentasService, VentaError
from ..services.facturas import FacturasService
from ..utils.decorators import vendedor_required


from app.utils_tz import rango_dia_caracas, hoy_caracas, a_caracas

vendedor_bp = Blueprint('vendedor', __name__)


@vendedor_bp.before_request
@login_required
@vendedor_required
def before_request():
    # ✅ Verificar que el padre (VIP) tenga suscripcion vigente
    if current_user.is_authenticated and getattr(current_user, 'es_vendedor', False):
        padre = current_user.padre
        if not padre or not padre.suscripcion_vigente:
            from flask_login import logout_user
            logout_user()
            flash('Tu cuenta esta desactivada. El negocio no tiene suscripcion activa.', 'warning')
            return redirect(url_for('auth.login'))


def _tiene_permiso(permiso):
    """Verifica si el vendedor actual tiene un permiso."""
    return getattr(current_user, permiso, False)


@vendedor_bp.context_processor
def inject_permisos():
    """Inyecta los permisos del vendedor en todos los templates."""
    return {
        'vendedor_puede_editar_inventario': _tiene_permiso('puede_editar_inventario'),
        'vendedor_puede_ver_clientes': _tiene_permiso('puede_ver_clientes'),
        'vendedor_puede_ver_facturas': _tiene_permiso('puede_ver_facturas'),
        'vendedor_puede_ver_reportes_completos': _tiene_permiso('puede_ver_reportes_completos'),
        'vendedor_puede_cancelar_ventas': _tiene_permiso('puede_cancelar_ventas'),
        'vendedor_puede_ver_costos': _tiene_permiso('puede_ver_costos'),
    }


# ============================================================
# DASHBOARD DEL VENDEDOR
# ============================================================
@vendedor_bp.route('/dashboard')
def dashboard():
    vid = current_user.id
    padre_id = current_user.usuario_padre_id
    hoy = hoy_caracas()
    inicio_mes = hoy.replace(day=1)
    
    # ============ RANGOS UTC (hora Caracas) ============
    rango_hoy_inicio_utc, rango_hoy_fin_utc = rango_dia_caracas(hoy)

    # Stats del vendedor (SOLO DEL DIA)
    ventas_hoy_q = Venta.query.filter(
        Venta.vendedor_id == vid,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_hoy_inicio_utc,
        Venta.creado_en <= rango_hoy_fin_utc,
    )
    num_ventas_hoy = ventas_hoy_q.count()

    total_hoy_usd = float(
        db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
        .filter(
            Venta.vendedor_id == vid,
            Venta.estado != 'cancelada',
            Venta.creado_en >= rango_hoy_inicio_utc,
            Venta.creado_en <= rango_hoy_fin_utc,
        )
        .scalar() or 0
    )

    unidades_hoy = int(
        db.session.query(func.coalesce(func.sum(Venta.cantidad), 0))
        .filter(
            Venta.vendedor_id == vid,
            Venta.estado != 'cancelada',
            Venta.creado_en >= rango_hoy_inicio_utc,
            Venta.creado_en <= rango_hoy_fin_utc,
        )
        .scalar() or 0
    )

    ticket_promedio_hoy = round(total_hoy_usd / num_ventas_hoy, 2) if num_ventas_hoy > 0 else 0.0

    stats = {
        'ventas_hoy': num_ventas_hoy,
        'total_hoy_usd': total_hoy_usd,
        'unidades_hoy': unidades_hoy,
        'ticket_promedio_hoy': ticket_promedio_hoy,
    }
    
    # Ventas recientes
    ventas_recientes = Venta.query.filter_by(vendedor_id=vid) \
        .filter(Venta.estado != 'cancelada') \
        .order_by(Venta.creado_en.desc()).limit(8).all()
    
    # ✅ Cuotas Cashea pagadas HOY (del padre)
    from ..models.factura import FacturaCobrar
    from ..models.cuota_cashea import CuotaCashea
    cuotas_cashea_hoy_vend_dash = CuotaCashea.query.filter(
        CuotaCashea.estado == 'pagada',
        CuotaCashea.fecha_pago == hoy,
    ).join(
        FacturaCobrar, CuotaCashea.factura_id == FacturaCobrar.id
    ).filter(
        FacturaCobrar.usuario_id == padre_id,
    ).all()

    total_cuotas_cashea_hoy_vend = sum(float(cu.monto_usd or 0) for cu in cuotas_cashea_hoy_vend_dash)

    # Info del negocio del padre
    from ..models.config import ConfigEmpresa
    config = ConfigEmpresa.query.filter_by(usuario_id=padre_id).first()
    empresa = {
        'nombre': config.nombre if config else 'Mi Negocio',
        'rif': config.rif if config else '',
    }
    
    # Tasa
    tasas = TasasService.obtener_tasas(padre_id)
    
    return render_template(
        'vendedor/dashboard.html',
        stats=stats,
        ventas_recientes=ventas_recientes,
        empresa=empresa,
        tasas=tasas,
        total_cuotas_cashea_hoy=total_cuotas_cashea_hoy_vend,
    )


# ============================================================
# VENTAS (Punto de Venta)
# ============================================================
@vendedor_bp.route('/ventas')
def ventas():
    vid = current_user.id
    padre_id = current_user.usuario_padre_id
    hoy = hoy_caracas()
    inicio_mes = hoy.replace(day=1)

    productos = Producto.query.filter(
        Producto.usuario_id == padre_id,
        Producto.stock_actual > 0,
        Producto.activo.is_(True),
    ).order_by(Producto.nombre).all()

    ventas_recientes = Venta.query.filter_by(vendedor_id=vid) \
        .filter(Venta.estado != 'cancelada') \
        .order_by(Venta.creado_en.desc()).limit(10).all()

    stats = {
        'total_ventas': Venta.query.filter_by(vendedor_id=vid).filter(Venta.estado != 'cancelada').count(),
        'ingresos_usd': float(
            db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
            .filter(Venta.vendedor_id == vid, Venta.estado != 'cancelada').scalar() or 0
        ),
    }

    clientes = Cliente.query.filter_by(usuario_id=padre_id).order_by(Cliente.nombre).all()
    tasas = TasasService.obtener_tasas(padre_id)

    return render_template(
        'vendedor/ventas.html',
        productos=productos,
        ventas_recientes=ventas_recientes,
        stats=stats,

        clientes=clientes,
        tasas=tasas,
    )


@vendedor_bp.route('/ventas/procesar', methods=['POST'])
def procesar_venta():
    padre_id = current_user.usuario_padre_id
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'success': False, 'error': 'Datos invalidos'}), 400

    # ✅ Verificar limites del negocio (padre)
    try:
        from ..services.suscripciones import SuscripcionesService
        limites = SuscripcionesService.verificar_limites(padre_id)
        ventas_mes = SuscripcionesService.ventas_mes_actual(padre_id)
        if limites['limite_ventas'] > 0 and ventas_mes >= limites['limite_ventas']:
            return jsonify({
                'success': False,
                'error': f'El negocio alcanzo el limite de {limites["limite_ventas"]} ventas mensuales (plan Free).'
            }), 403
    except Exception:
        current_app.logger.exception('Error validando limites del padre')

    # ✅ Detectar si es Cashea
    es_cashea = data.get('tipo_venta') == 'cashea' or data.get('metodo_pago') == 'cashea' or data.get('tipo_venta') == 'cashea'
    cashea_data = None

    if es_cashea:
        cashea_data = {
            'porcentaje_inicial': int(data.get('cashea_porcentaje_inicial', 0)),
            'num_cuotas': int(data.get('cashea_num_cuotas', 3)),
            'nombre_comprador': data.get('cashea_nombre_comprador', '').strip(),
            'cedula': data.get('cashea_cedula', '').strip(),
            'telefono': data.get('cashea_telefono', '').strip(),
            'tipo': data.get('cashea_tipo', 'normal'),
        }

        if not cashea_data['nombre_comprador'] or not cashea_data['cedula'] or not cashea_data['telefono']:
            return jsonify({
                'success': False,
                'error': 'Cashea requiere nombre, cedula y telefono del comprador'
            }), 400

    try:
        data['vendedor_id'] = current_user.id
        resultado = VentasService.procesar(padre_id, data, vendedor_id=current_user.id)

        tasas = TasasService.obtener_tasas(padre_id)
        config = FacturasService.obtener_config_empresa(padre_id)
        resultado['cliente_nombre'] = data.get('cliente_nombre', 'Consumidor Final')
        resultado['metodo_pago'] = data.get('metodo_pago', 'efectivo')
        resultado['observaciones'] = data.get('observaciones', '')

        filename = FacturasService.generar_html(
            resultado, tasas, padre_id, current_user.nombre, config
        )

        venta_id = resultado.get('primera_venta_id') or resultado.get('factura_id')
        if not venta_id and resultado.get('ventas'):
            venta_id = resultado['ventas'][0].get('venta_id')

        # ✅ Si es Cashea, guardar datos y crear cuotas
        if es_cashea and cashea_data:
            from ..models.factura import FacturaCobrar
            from ..models.cliente import Cliente
            from ..services.cashea import CasheaService

            # Buscar o crear cliente
            cliente_cashea = None
            if cashea_data['cedula']:
                cliente_cashea = Cliente.query.filter_by(
                    usuario_id=padre_id,
                    documento=cashea_data['cedula'],
                ).first()

            if not cliente_cashea:
                cliente_cashea = Cliente(
                    usuario_id=padre_id,
                    nombre=cashea_data['nombre_comprador'],
                    documento=cashea_data['cedula'],
                    telefono=cashea_data['telefono'],
                )
                db.session.add(cliente_cashea)
                db.session.flush()

            resumen_cashea = CasheaService.calcular_resumen_cashea(
                float(resultado['total_usd']),
                cashea_data['porcentaje_inicial'],
                cashea_data['num_cuotas'],
            )

            ventas_factura = Venta.query.filter_by(
                nro_factura=resultado['nro_factura'],
                usuario_id=padre_id,
                vendedor_id=current_user.id,
            ).all()

            for v in ventas_factura:
                v.cliente_id = cliente_cashea.id
                v.cliente_nombre = cashea_data['nombre_comprador']
                v.cashea_porcentaje_inicial = cashea_data['porcentaje_inicial']
                v.cashea_num_cuotas = cashea_data['num_cuotas']
                v.cashea_nombre_comprador = cashea_data['nombre_comprador']
                v.cashea_cedula = cashea_data['cedula']
                v.cashea_telefono = cashea_data['telefono']
                v.cashea_monto_inicial = resumen_cashea['monto_inicial']
                v.cashea_monto_cuota = resumen_cashea['monto_cuota']
                v.cashea_tipo = cashea_data['tipo']

            factura_cobrar = FacturaCobrar.query.filter_by(
                nro_factura=resultado['nro_factura'],
                usuario_id=padre_id,
            ).first()

            if not factura_cobrar:
                factura_cobrar = FacturaCobrar(
                    usuario_id=padre_id,
                    venta_id=ventas_factura[0].id if ventas_factura else None,
                    cliente_id=cliente_cashea.id,
                    cliente_nombre=cashea_data['nombre_comprador'],
                    tipo_venta='cashea',
                    total_usd=float(resultado['total_usd']),
                    total_ves=float(resultado['total_ves']),
                    saldo_usd=resumen_cashea['saldo'],
                    saldo_ves=resumen_cashea['saldo'] * float(tasas.oficial or 0),
                    estado='pendiente',
                    nro_factura=resultado['nro_factura'],
                )
                db.session.add(factura_cobrar)
                db.session.flush()
            else:
                factura_cobrar.saldo_usd = resumen_cashea['saldo']
                factura_cobrar.estado = 'pendiente'
                if cliente_cashea and not factura_cobrar.cliente_id:
                    factura_cobrar.cliente_id = cliente_cashea.id

            factura_cobrar.cashea_porcentaje_inicial = cashea_data['porcentaje_inicial']
            factura_cobrar.cashea_num_cuotas = cashea_data['num_cuotas']
            factura_cobrar.cashea_nombre_comprador = cashea_data['nombre_comprador']
            factura_cobrar.cashea_cedula = cashea_data['cedula']
            factura_cobrar.cashea_telefono = cashea_data['telefono']
            factura_cobrar.cashea_monto_inicial = resumen_cashea['monto_inicial']
            factura_cobrar.cashea_monto_cuota = resumen_cashea['monto_cuota']
            factura_cobrar.cashea_tipo = cashea_data['tipo']

            CasheaService.crear_cuotas(
                factura_cobrar,
                cashea_data['num_cuotas'],
                resumen_cashea['saldo'],
            )

            db.session.commit()

        return jsonify({
            'success': True,
            'venta_id': venta_id,
            'ventas': resultado['ventas'],
            'total_usd': resultado['total_usd'],
            'total_ves': resultado['total_ves'],
            'nro_factura': resultado['nro_factura'],
            'factura_url': f'/user/factura/ver/{filename}',
            'tipo_venta': resultado['tipo_venta'],
        })
    except VentaError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception:
        current_app.logger.exception('Error vendedor procesar_venta')
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# ============================================================
# INVENTARIO (solo lectura, o editar si tiene permiso)
# ============================================================
@vendedor_bp.route('/inventario')
def inventario():
    padre_id = current_user.usuario_padre_id
    search = request.args.get('search', '').strip()
    categoria = request.args.get('categoria', '').strip()
    
    query = Producto.query.filter(
        Producto.usuario_id == padre_id,
        Producto.activo.is_(True),
    )
    
    if search:
        like = f'%{search}%'
        query = query.filter(db.or_(
            Producto.nombre.ilike(like),
            Producto.codigo.ilike(like),
        ))
    
    if categoria:
        query = query.filter_by(categoria=categoria)
    
    productos = query.order_by(Producto.nombre).all()
    
    categorias = [r[0] for r in db.session.query(Producto.categoria).filter(
        Producto.usuario_id == padre_id,
        Producto.categoria.isnot(None),
        Producto.categoria != '',
    ).distinct().order_by(Producto.categoria).all()]
    
    stats = {
        'total': len(productos),
        'stock_total': sum(p.stock_actual or 0 for p in productos),
        'bajo_stock': sum(1 for p in productos if p.stock_bajo),
    }
    
    return render_template(
        'vendedor/inventario.html',
        productos=productos,
        categorias=categorias,
        search=search,
        categoria=categoria,
        stats=stats,
    )


# ============================================================
# REPORTES (solo sus ventas, o completos si tiene permiso)
# ============================================================
@vendedor_bp.route('/reportes')
def reportes():
    """Reporte del vendedor: SOLO sus ventas de HOY.

    El vendedor NO ve ganancia, ni gastos, ni ventas por dia.
    Solo ve el total vendido hoy y el top de productos.
    """
    vid = current_user.id
    padre_id = current_user.usuario_padre_id
    hoy = hoy_caracas()

    # ✅ SOLO HOY (sin filtros de fecha)
    fecha_desde = hoy
    fecha_hasta = hoy

    # ✅ Si tiene permiso de ver reportes completos, ve los del negocio
    # Pero SIEMPRE solo del dia de hoy
    if _tiene_permiso('puede_ver_reportes_completos'):
        filtro_vendedor = Venta.usuario_id == padre_id
        titulo = 'Ventas del Dia (Negocio)'
    else:
        filtro_vendedor = Venta.vendedor_id == vid
        titulo = 'Mis Ventas del Dia'

    # Rango UTC para hoy (hora Caracas)
    rango_inicio_utc, rango_fin_utc = rango_dia_caracas(hoy)

    # ✅ Ventas de HOY
    ventas_hoy = Venta.query.filter(
        filtro_vendedor,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).order_by(Venta.creado_en.desc()).all()

    # ✅ Resumen del dia
    total_usd = sum(float(v.total_usd or 0) for v in ventas_hoy)
    total_unidades = sum(int(v.cantidad or 0) for v in ventas_hoy)
    num_ventas = len(ventas_hoy)

    try:
        tasa_bcv = float(TasasService.obtener_tasa_bcv())
    except Exception:
        tasa_bcv = 50.0

    resumen = {
        'fecha': hoy.strftime('%d/%m/%Y'),
        'dia_semana': ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'][hoy.weekday()],
        'num_ventas': num_ventas,
        'total_unidades': total_unidades,
        'total_usd': round(total_usd, 2),
        'total_bs': round(total_usd * tasa_bcv, 2),
        'tasa_bcv': round(tasa_bcv, 2),
        'ticket_promedio_usd': round(total_usd / num_ventas, 2) if num_ventas > 0 else 0,
    }

    # ✅ Lista de ventas de HOY
    ventas = []
    for v in ventas_hoy:
        ventas.append({
            'id': v.id,
            'hora': a_caracas(v.creado_en).strftime('%H:%M') if v.creado_en else '',
            'producto': v.producto.nombre if v.producto else 'Producto',
            'codigo': v.producto.codigo if v.producto else '',
            'cantidad': v.cantidad,
            'precio_usd': float(v.precio_usd or 0),
            'total_usd': float(v.total_usd or 0),
            'total_bs': float(v.total_usd or 0) * tasa_bcv,
            'cliente': v.cliente_nombre,
            'nro_factura': v.nro_factura or '-',
        })

    # ✅ Top productos de HOY
    top_productos = db.session.query(
        Producto.nombre,
        Producto.codigo,
        func.coalesce(func.sum(Venta.cantidad), 0).label('total_vendido'),
        func.coalesce(func.sum(Venta.total_usd), 0).label('ingresos'),
    ).join(Venta, Venta.producto_id == Producto.id).filter(
        filtro_vendedor,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).group_by(Producto.id, Producto.nombre, Producto.codigo).order_by(
        func.sum(Venta.cantidad).desc()
    ).limit(10).all()

    top_productos = [dict(r._mapping) for r in top_productos]

    return render_template(
        'vendedor/reportes.html',
        resumen=resumen,
        ventas=ventas,
        top_productos=top_productos,
        titulo=titulo,
        puede_ver_completos=_tiene_permiso('puede_ver_reportes_completos'),
    )

@vendedor_bp.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if not _tiene_permiso('puede_ver_clientes'):
        flash('No tienes permiso para ver clientes.', 'warning')
        return redirect(url_for('vendedor.dashboard'))
    
    padre_id = current_user.usuario_padre_id
    
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre es obligatorio', 'danger')
        else:
            c = Cliente(
                usuario_id=padre_id,
                nombre=nombre,
                telefono=request.form.get('telefono', '').strip(),
                email=request.form.get('email', '').strip(),
                direccion=request.form.get('direccion', '').strip(),
                documento=request.form.get('documento', '').strip(),
            )
            db.session.add(c)
            db.session.commit()
            flash('Cliente agregado.', 'success')
        return redirect(url_for('vendedor.clientes'))
    
    clientes = Cliente.query.filter_by(usuario_id=padre_id).order_by(Cliente.nombre).all()
    return render_template('vendedor/clientes.html', clientes=clientes)


# ============================================================
# FACTURAS (solo si tiene permiso)
# ============================================================
@vendedor_bp.route('/facturas')
def facturas():
    if not _tiene_permiso('puede_ver_facturas'):
        flash('No tienes permiso para ver facturas.', 'warning')
        return redirect(url_for('vendedor.dashboard'))

    vid = current_user.id
    padre_id = current_user.usuario_padre_id

    from ..models.factura import FacturaCobrar

    # Si tiene permiso de ver reportes completos, ve las facturas del negocio
    if _tiene_permiso('puede_ver_reportes_completos'):
        filtro = FacturaCobrar.usuario_id == padre_id
    else:
        filtro = FacturaCobrar.venta.has(Venta.vendedor_id == vid)

    facturas = FacturaCobrar.query.filter(filtro) \
        .order_by(FacturaCobrar.id.desc()).limit(200).all()

    tasas = TasasService.obtener_tasas(padre_id)

    return render_template('vendedor/facturas.html',
                           facturas=facturas,
                           tasas=tasas)


@vendedor_bp.route('/producto/<int:producto_id>/datos')
def producto_datos(producto_id):
    padre_id = current_user.usuario_padre_id
    p = Producto.query.filter_by(id=producto_id, usuario_id=padre_id).first_or_404()
    
    variantes = []
    for v in ProductoVariante.query.filter_by(producto_id=p.id, activo=True).order_by(ProductoVariante.id).all():
        variantes.append({
            'id': v.id,
            'nombre': v.nombre,
            'codigo': v.codigo or '',
            'stock_actual': v.stock_actual or 0,
            'precio_venta_usd': v.precio_venta_efectivo,
        })
    
    return jsonify({
        'id': p.id,
        'nombre': p.nombre,
        'codigo': p.codigo,
        'precio_venta_usd': float(p.precio_venta_usd or 0),
        'stock_actual': p.stock_actual,
        'variantes': variantes,
        'tiene_variantes': len(variantes) > 0,
    })

# ============================================================
# VER FACTURA (modal para el vendedor)
# ============================================================
@vendedor_bp.route('/factura/<int:factura_id>/ver-modal')
def ver_factura_modal(factura_id):
    """Devuelve el HTML de la factura para mostrar en un iframe."""
    from ..models.factura import FacturaCobrar
    import os
    import glob

    padre_id = current_user.usuario_padre_id
    vid = current_user.id

    # Si tiene permiso de ver reportes completos, puede ver cualquier factura del negocio
    if _tiene_permiso('puede_ver_reportes_completos'):
        factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=padre_id).first()
    else:
        # Sino, solo las facturas de sus propias ventas
        factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=padre_id) \
            .filter(FacturaCobrar.venta.has(Venta.vendedor_id == vid)).first()

    if not factura:
        return '<div style="padding:2rem;color:#dc2626;font-family:sans-serif;text-align:center;"><h2>Factura no encontrada</h2><p>No tienes acceso a esta factura.</p></div>', 404

    if not factura.nro_factura:
        return '<div style="padding:2rem;color:#dc2626;font-family:sans-serif;text-align:center;"><h2>Factura sin numero</h2></div>', 404

    filename = f"factura_{factura.nro_factura.replace('/', '-')}_{padre_id}.html"
    facturas_dir = current_app.config.get("FACTURAS_DIR", "facturas")
    filepath = os.path.join(facturas_dir, filename)

    if not os.path.exists(filepath):
        patron = os.path.join(facturas_dir, f"*{factura.nro_factura.replace('/', '-')}*.html")
        matches = glob.glob(patron)
        if matches:
            filepath = matches[0]
        else:
            return f'<div style="padding:2rem;color:#dc2626;font-family:sans-serif;text-align:center;"><h2>Archivo no encontrado</h2><p>{filename}</p></div>', 404

    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

# ============================================================
# ABONAR FACTURA (para vendedores con permiso)
# ============================================================
@vendedor_bp.route('/factura/<int:factura_id>/abonar', methods=['POST'])
def abonar_factura(factura_id):
    """Registra un abono a una factura."""
    from ..models.factura import FacturaCobrar
    
    padre_id = current_user.usuario_padre_id
    vid = current_user.id
    
    # Verificar permiso
    if not _tiene_permiso('puede_ver_facturas'):
        flash('No tienes permiso para abonar facturas.', 'warning')
        return redirect(url_for('vendedor.facturas'))
    
    # Buscar la factura
    if _tiene_permiso('puede_ver_reportes_completos'):
        # Puede abonar cualquier factura del negocio
        factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=padre_id).first()
    else:
        # Solo facturas de sus ventas
        factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=padre_id) \
            .filter(FacturaCobrar.venta.has(Venta.vendedor_id == vid)).first()
    
    if not factura:
        flash('Factura no encontrada o sin permiso.', 'danger')
        return redirect(url_for('vendedor.facturas'))
    
    # Obtener datos del formulario
    try:
        monto_usd = float(request.form.get('monto_usd', 0) or 0)
        monto_ves = float(request.form.get('monto_ves', 0) or 0)
        tasa_usada = float(request.form.get('tasa_usada', 50) or 50)
    except ValueError:
        flash('Montos invalidos', 'danger')
        return redirect(url_for('vendedor.facturas'))
    
    if monto_usd <= 0:
        flash('El monto en USD debe ser mayor a 0', 'danger')
        return redirect(url_for('vendedor.facturas'))
    
    # Registrar abono
    ok, err = VentasService.agregar_abono(
        factura_id, monto_usd, monto_ves, tasa_usada,
        request.form.get('metodo_pago', 'efectivo'),
        request.form.get('notas', ''),
    )
    
    if ok:
        flash(f'Abono de ${monto_usd:.2f} registrado correctamente.', 'success')
    else:
        flash(err or 'Error al registrar abono', 'danger')
    
    return redirect(url_for('vendedor.facturas'))

# ============================================================
# IMPRIMIR TICKET (POS-58) - Vendedor
# ============================================================
@vendedor_bp.route('/ventas/<int:venta_id>/imprimir-ticket', methods=['POST'])
@login_required
def imprimir_ticket_venta(venta_id):
    """Imprime el ticket de una venta en la POS-58 (vendedor).

    Busca TODAS las ventas que comparten el mismo nro_factura
    del padre del vendedor.
    """
    from ..services.tickets import TicketsService
    from ..services.facturas import FacturasService

    vid = current_user.id
    padre_id = current_user.usuario_padre_id

    # 1. Buscar la venta del vendedor
    venta_ref = Venta.query.filter_by(
        id=venta_id,
        usuario_id=padre_id,
        vendedor_id=vid,
    ).first()
    if not venta_ref:
        return jsonify({'success': False, 'error': 'Venta no encontrada'}), 404

    # 2. Traer TODAS las ventas con el mismo nro_factura
    ventas_factura = Venta.query.filter_by(
        nro_factura=venta_ref.nro_factura,
        usuario_id=padre_id,
        vendedor_id=vid,
    ).order_by(Venta.id).all()

    # 3. Config empresa
    try:
        config = FacturasService.obtener_config_empresa(padre_id) or {}
    except Exception:
        config = {}

    empresa = {
        'nombre': config.get('nombre') or 'Mi Negocio',
        'rif': config.get('rif') or '',
        'direccion': config.get('direccion') or '',
        'telefono': config.get('telefono') or '',
    }

    # 4. Armar productos
    productos = []
    total_usd = 0.0
    for v in ventas_factura:
        productos.append({
            'nombre': v.producto.nombre if v.producto else 'Producto',
            'cantidad': v.cantidad,
            'precio_usd': float(v.precio_usd or 0),
        })
        total_usd += float(v.total_usd or 0)

    venta_data = {
        'nro_factura': venta_ref.nro_factura,
        'cliente_nombre': venta_ref.cliente_nombre,
        'metodo_pago': venta_ref.metodo_pago,
        'total_usd': total_usd,
        'tasa_bcv': float(venta_ref.tasa_oficial or 50),
        'productos': productos,
    }

    nombre_impresora = 'POS-58'
    if isinstance(config, dict):
        nombre_impresora = config.get('nombre_impresora') or 'POS-58'
    else:
        nombre_impresora = getattr(config, 'nombre_impresora', None) or 'POS-58'

    exito, error = TicketsService.imprimir_ticket(
        venta_data, empresa,
        nombre_impresora=nombre_impresora,
        vendedor_nombre=current_user.nombre
    )

    if exito:
        return jsonify({'success': True, 'message': 'Ticket impreso'})
    else:
        return jsonify({'success': False, 'error': error}), 500

# ============================================================
# CANCELAR FACTURA (vendedor - requiere PIN del VIP)
# ============================================================
@vendedor_bp.route('/facturas/<nro_factura>/cancelar', methods=['POST'])
@login_required
def cancelar_factura(nro_factura):
    """Cancela una factura. Requiere el PIN del VIP padre."""
    vid = current_user.id
    padre = current_user.padre

    if not padre:
        return jsonify({'success': False, 'error': 'No tienes un VIP padre configurado'}), 400

    data = request.get_json() or {}
    pin = data.get('pin', '').strip()
    motivo = data.get('motivo', '').strip()[:500]

    # Verificar PIN del padre
    if not padre.tiene_pin_cancelacion:
        return jsonify({'success': False, 'error': 'El VIP no ha configurado un PIN'}), 400

    if not padre.check_pin_cancelacion(pin):
        return jsonify({'success': False, 'error': 'PIN incorrecto'}), 401

    # Buscar las ventas de esa factura hechas por este vendedor
    ventas = Venta.query.filter_by(
        nro_factura=nro_factura,
        vendedor_id=vid,
    ).all()

    if not ventas:
        return jsonify({'success': False, 'error': 'Factura no encontrada'}), 404

    if all(v.estado == 'cancelada' for v in ventas):
        return jsonify({'success': False, 'error': 'Esta factura ya esta cancelada'}), 400

    # Verificar limite de 3 dias
    from datetime import datetime, timedelta
    ahora = datetime.utcnow()
    for v in ventas:
        if v.creado_en and (ahora - v.creado_en) > timedelta(days=3):
            return jsonify({
                'success': False,
                'error': 'Solo se pueden cancelar facturas de los ultimos 3 dias'
            }), 400

    # Cancelar y devolver stock
    for v in ventas:
        if v.producto:
            try:
                v.producto.stock_actual = (v.producto.stock_actual or 0) + int(v.cantidad or 0)
            except Exception:
                pass

        if v.variante:
            try:
                v.variante.stock_actual = (v.variante.stock_actual or 0) + int(v.cantidad or 0)
            except Exception:
                pass

        v.estado = 'cancelada'
        v.cancelado_en = ahora
        v.cancelado_por_id = vid
        v.motivo_cancelacion = motivo

    # Cancelar la FacturaCobrar asociada (del padre)
    try:
        from ..models.factura import FacturaCobrar
        padre_id = current_user.usuario_padre_id
        facturas_cobrar = FacturaCobrar.query.filter_by(
            nro_factura=nro_factura,
            usuario_id=padre_id,
        ).all()
        for fc in facturas_cobrar:
            fc.estado = 'cancelada'
            fc.saldo_usd = 0
            fc.saldo_ves = 0
    except Exception as e:
        current_app.logger.exception('Error cancelando FacturaCobrar')

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Factura cancelada ({len(ventas)} items)'
    })

# ============================================================
# CASHEA (vendedor - solo las suyas)
# ============================================================
from ..models.cuota_cashea import CuotaCashea
from ..services.cashea import CasheaService


@vendedor_bp.route('/cashea')
@login_required
def cashea_listado():
    """Listado de facturas Cashea del vendedor (solo las suyas)."""
    from ..models.factura import FacturaCobrar
    from ..models.cuota_cashea import CuotaCashea

    vid = current_user.id
    padre_id = current_user.usuario_padre_id

    filtro_estado = request.args.get('estado', 'todas').strip()
    filtro_buscar = request.args.get('buscar', '').strip()

    # Buscar facturas donde la venta fue hecha por este vendedor
    ventas_vendedor = Venta.query.filter_by(
        vendedor_id=vid,
        usuario_id=padre_id,
    ).filter(
        Venta.tipo_venta == 'cashea',
    ).all()

    # Obtener nros de factura
    nros_factura = list(set(v.nro_factura for v in ventas_vendedor if v.nro_factura))

    if not nros_factura:
        facturas = []
    else:
        query = FacturaCobrar.query.filter(
            FacturaCobrar.usuario_id == padre_id,
            FacturaCobrar.nro_factura.in_(nros_factura),
            FacturaCobrar.tipo_venta == 'cashea',
        )

        if filtro_estado == 'pendiente':
            query = query.filter_by(estado='pendiente')
        elif filtro_estado == 'pagado':
            query = query.filter_by(estado='pagado')

        facturas = query.order_by(FacturaCobrar.fecha_creacion.desc()).all()

    if filtro_buscar:
        bl = filtro_buscar.lower()
        facturas = [f for f in facturas
                    if bl in (f.cashea_nombre_comprador or '').lower()
                    or bl in (f.cashea_cedula or '').lower()
                    or bl in (f.nro_factura or '').lower()]

    # Armar datos
    facturas_data = []
    total_saldo = 0

    for f in facturas:
        cuotas = f.cuotas_cashea.order_by(CuotaCashea.numero).all()
        pagadas = [c for c in cuotas if c.estado == 'pagada']
        pendientes = [c for c in cuotas if c.estado == 'pendiente']
        vencidas = [c for c in cuotas if c.vencida]

        total_saldo += float(f.saldo_usd or 0)

        facturas_data.append({
            'factura': f,
            'cuotas': cuotas,
            'pagadas': len(pagadas),
            'pendientes': len(pendientes),
            'vencidas': len(vencidas),
            'total_cuotas': len(cuotas),
            'saldo': float(f.saldo_usd or 0),
        })

    # ✅ Calcular totales para las cards
    total_ventas_cashea = sum(
        float(item['factura'].total_usd or 0) for item in facturas_data
    )
    total_inicial = sum(
        float(item['factura'].cashea_monto_inicial or 0) for item in facturas_data
    )
    total_cuotas_pagadas = 0
    for item in facturas_data:
        for cu in item['cuotas']:
            if cu.estado == 'pagada':
                total_cuotas_pagadas += float(cu.monto_usd or 0)

    total_cobrado = total_inicial + total_cuotas_pagadas

    # Ganancia: (precio venta - costo) de los productos
    ganancia_cashea = 0
    for item in facturas_data:
        factura = item['factura']
        ventas_cashea = Venta.query.filter_by(
            nro_factura=factura.nro_factura,
            usuario_id=padre_id,
        ).all()
        for v in ventas_cashea:
            if v.producto:
                costo = float(v.producto.precio_costo_usd or 0)
                precio = float(v.precio_usd or 0)
                ganancia_cashea += (precio - costo) * int(v.cantidad or 0)

    return render_template(
        'vendedor/cashea.html',
        facturas_data=facturas_data,
        total_saldo=total_saldo,
        total_facturas=len(facturas_data),
        filtro_estado=filtro_estado,
        filtro_buscar=filtro_buscar,
        total_ventas_cashea=total_ventas_cashea,
        total_cobrado=total_cobrado,
        total_inicial=total_inicial,
        total_cuotas_pagadas=total_cuotas_pagadas,
        ganancia_cashea=ganancia_cashea,
    )


@vendedor_bp.route('/cashea/cuota/<int:cuota_id>/pagar', methods=['POST'])
@login_required
def cashea_pagar_cuota(cuota_id):
    """Marca una cuota Cashea como pagada (vendedor)."""
    from ..models.factura import FacturaCobrar
    from ..models.cuota_cashea import CuotaCashea
    from ..services.cashea import CasheaService
    vid = current_user.id
    padre_id = current_user.usuario_padre_id

    # Filtro directo: solo cuotas de facturas del padre
    cuota = CuotaCashea.query.join(FacturaCobrar).filter(
        CuotaCashea.id == cuota_id,
        FacturaCobrar.usuario_id == padre_id,
    ).first()

    if not cuota:
        return jsonify({'success': False, 'error': 'Cuota no encontrada'}), 404

    # ✅ Obtener la factura de la cuota (fix: `factura` no estaba definida)
    factura = cuota.factura
    if not factura:
        return jsonify({'success': False, 'error': 'Cuota sin factura asociada'}), 400

    # ✅ Verificar que la venta fue hecha por este vendedor
    venta = Venta.query.filter_by(
        nro_factura=factura.nro_factura,
        vendedor_id=vid,
        usuario_id=padre_id,
    ).first()

    if not venta:
        return jsonify({
            'success': False,
            'error': 'Esta factura no fue creada por ti'
        }), 403

    exito, error = CasheaService.marcar_cuota_pagada(cuota)
    if exito:
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': error}), 400

# ============================================================
# GASTOS (vendedor)
# ============================================================
@vendedor_bp.route('/gastos')
@login_required
def gastos_listado():
    """Listado de gastos del padre (VIP)."""
    from datetime import date, timedelta, datetime as _dt

    vid = current_user.id
    padre_id = current_user.usuario_padre_id
    hoy = date.today()

    filtro_desde_str = request.args.get('desde', '').strip()
    filtro_hasta_str = request.args.get('hasta', '').strip()
    filtro_categoria = request.args.get('categoria', '').strip()
    filtro_buscar = request.args.get('buscar', '').strip()
    filtro_rango = request.args.get('rango', '').strip()

    if filtro_rango:
        if filtro_rango == 'hoy':
            filtro_desde_str = hoy.strftime('%Y-%m-%d')
            filtro_hasta_str = hoy.strftime('%Y-%m-%d')
        elif filtro_rango == 'semana':
            filtro_desde_str = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
            filtro_hasta_str = hoy.strftime('%Y-%m-%d')
        elif filtro_rango == 'mes':
            filtro_desde_str = hoy.replace(day=1).strftime('%Y-%m-%d')
            filtro_hasta_str = hoy.strftime('%Y-%m-%d')
        elif filtro_rango == 'anio':
            filtro_desde_str = hoy.replace(month=1, day=1).strftime('%Y-%m-%d')
            filtro_hasta_str = hoy.strftime('%Y-%m-%d')
        elif filtro_rango == 'todo':
            filtro_desde_str = ''
            filtro_hasta_str = ''

    filtro_desde = None
    filtro_hasta = None

    if filtro_desde_str:
        try:
            filtro_desde = _dt.strptime(filtro_desde_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if filtro_hasta_str:
        try:
            filtro_hasta = _dt.strptime(filtro_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if not filtro_desde and not filtro_hasta and not filtro_rango:
        filtro_desde = hoy
        filtro_hasta = hoy
        filtro_rango = 'hoy'

    query = Gasto.query.filter_by(usuario_id=padre_id)
    if filtro_desde:
        query = query.filter(Gasto.fecha >= filtro_desde)
    if filtro_hasta:
        query = query.filter(Gasto.fecha <= filtro_hasta)
    if filtro_categoria:
        query = query.filter_by(categoria=filtro_categoria)

    gastos = query.order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()

    if filtro_buscar:
        bl = filtro_buscar.lower()
        gastos = [g for g in gastos
                  if bl in (g.descripcion or '').lower()
                  or bl in (g.proveedor_nombre or '').lower()]

    total_filtro = sum(float(g.monto_usd or 0) for g in gastos)

    inicio_mes = hoy.replace(day=1)
    gastos_mes = Gasto.query.filter(
        Gasto.usuario_id == padre_id,
        Gasto.fecha >= inicio_mes,
        Gasto.fecha <= hoy,
    ).all()
    total_mes = sum(float(g.monto_usd or 0) for g in gastos_mes)

    inicio_anio = hoy.replace(month=1, day=1)
    gastos_anio = Gasto.query.filter(
        Gasto.usuario_id == padre_id,
        Gasto.fecha >= inicio_anio,
    ).all()
    total_anio = sum(float(g.monto_usd or 0) for g in gastos_anio)

    return render_template(
        'vendedor/gastos.html',
        gastos=gastos,
        total_filtro=total_filtro,
        total_mes=total_mes,
        total_anio=total_anio,
        categorias=CATEGORIAS_GASTOS,
        metodos_pago=METODOS_PAGO,
        filtro_desde=filtro_desde_str,
        filtro_hasta=filtro_hasta_str,
        filtro_categoria=filtro_categoria,
        filtro_buscar=filtro_buscar,
        filtro_rango=filtro_rango,
    )


@vendedor_bp.route('/gastos/crear', methods=['POST'])
@login_required
def gastos_crear():
    """Crea un gasto a nombre del padre."""
    from datetime import date, datetime as _dt

    vid = current_user.id
    padre_id = current_user.usuario_padre_id

    categoria = request.form.get('categoria', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    monto_usd_str = request.form.get('monto_usd', '0').strip()
    monto_ves_str = request.form.get('monto_ves', '0').strip()
    fecha_str = request.form.get('fecha', '').strip()
    metodo_pago = request.form.get('metodo_pago', 'efectivo').strip()
    proveedor_nombre = request.form.get('proveedor_nombre', '').strip()
    notas = request.form.get('notas', '').strip()

    if not categoria or not descripcion or not monto_usd_str:
        flash('Categoria, descripcion y monto son obligatorios', 'danger')
        return redirect(url_for('vendedor.gastos_listado'))

    try:
        monto_usd = float(monto_usd_str)
        if monto_usd <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Monto invalido', 'danger')
        return redirect(url_for('vendedor.gastos_listado'))

    try:
        monto_ves = float(monto_ves_str) if monto_ves_str else 0
    except (ValueError, TypeError):
        monto_ves = 0

    if fecha_str:
        try:
            fecha = _dt.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = date.today()
    else:
        fecha = date.today()

    try:
        tasa = float(TasasService.obtener_tasa_bcv() or 0)
    except Exception:
        tasa = 0

    gasto = Gasto(
        usuario_id=padre_id,
        categoria=categoria,
        descripcion=descripcion,
        monto_usd=monto_usd,
        monto_ves=monto_ves or (monto_usd * tasa),
        tasa_bcv=tasa,
        fecha=fecha,
        metodo_pago=metodo_pago,
        proveedor_nombre=proveedor_nombre,
        notas=notas + f' [creado por {current_user.nombre}]',
    )

    db.session.add(gasto)
    db.session.commit()

    flash('Gasto registrado', 'success')
    return redirect(url_for('vendedor.gastos_listado'))


@vendedor_bp.route('/gastos/<int:gasto_id>/eliminar', methods=['POST'])
@login_required
def gastos_eliminar(gasto_id):
    """Elimina un gasto del padre. Requiere PIN del VIP."""
    padre = current_user.padre
    if not padre:
        return jsonify({'success': False, 'error': 'No tienes VIP padre'}), 400

    gasto = Gasto.query.filter_by(id=gasto_id, usuario_id=padre.id).first()
    if not gasto:
        return jsonify({'success': False, 'error': 'Gasto no encontrado'}), 404

    data = request.get_json() or {}
    pin = data.get('pin', '').strip()

    if not padre.tiene_pin_cancelacion:
        return jsonify({
            'success': False,
            'error': 'El VIP no ha configurado un PIN'
        }), 400

    if not padre.check_pin_cancelacion(pin):
        return jsonify({'success': False, 'error': 'PIN incorrecto'}), 401

    db.session.delete(gasto)
    db.session.commit()

    return jsonify({'success': True})
