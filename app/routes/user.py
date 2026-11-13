# app/routes/user.py
import os
from datetime import date, timedelta, datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, current_app)
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..models.producto import Producto
from ..models.venta import Venta
from ..models.cliente import Cliente
from ..models.factura import FacturaCobrar
from ..models.config import ConfigEmpresa
from ..models.caja import CajaTurno
from ..services.tasas import TasasService
from ..services.cashea import CasheaService
from ..services.suscripciones import SuscripcionesService
from ..services.ventas import VentasService, VentaError
from ..services.inventario import InventarioService
from ..services.facturas import FacturasService
from ..utils.decorators import user_required, check_limite_productos
from ..utils.helpers import to_float, rango_meses_ultimos

from ..models.gasto import Gasto, CATEGORIAS_GASTOS, METODOS_PAGO
from ..models.factura_proveedor import FacturaProveedor
from ..models.cuota_cashea import CuotaCashea
from app.utils_tz import (
    rango_dia_caracas,
    rango_entre_caracas,
    hoy_caracas,
    a_caracas,
    fmt_fecha_caracas,
    fmt_hora_caracas,
)

user_bp = Blueprint('user', __name__)


@user_bp.before_request
def before_request():
    # ✅ Permitir descarga con token (no requiere login)
    if request.endpoint == 'user.descargar_con_token':
        return

    # Para todas las demas rutas, exigir login + rol user
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.path))

    # Verificar que sea un "user" (no vendedor) y este activo
    if not getattr(current_user, 'is_active', True):
        return redirect(url_for('auth.login'))

    # Si es vendedor, redirigir a su panel
    if getattr(current_user, 'es_vendedor', False):
        return redirect(url_for('vendedor.dashboard'))


@user_bp.route('/dashboard')
def dashboard():
    uid = current_user.id
    TasasService.obtener_tasas(uid)
    
    # Stats básicas
    inicio_mes = date.today().replace(day=1)
    stats = {
        'total_productos': Producto.query.filter_by(usuario_id=uid, activo=True).count(),
        'productos_bajo_stock': Producto.query.filter(
            Producto.usuario_id == uid,
            Producto.activo.is_(True),
            Producto.stock_actual <= Producto.stock_minimo,
            Producto.stock_actual >= 0,
        ).count(),
        'ventas_mes': Venta.query.filter(
            Venta.usuario_id == uid,
            Venta.estado != 'cancelada',
            func.date(Venta.creado_en) >= inicio_mes,
        ).count(),
        'ingresos_mes_usd': float(
            db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
            .filter(Venta.usuario_id == uid, Venta.estado != 'cancelada', func.date(Venta.creado_en) >= inicio_mes)
            .scalar() or 0
        ),
    }
    
    # ✅ Cuotas Cashea pagadas HOY
    from datetime import timedelta as _td
    from ..models.cuota_cashea import CuotaCashea
    hoy_dash = date.today()
    cuotas_cashea_hoy_dash = CuotaCashea.query.filter(
        CuotaCashea.estado == 'pagada',
        CuotaCashea.fecha_pago == hoy_dash,
    ).join(
        FacturaCobrar, CuotaCashea.factura_id == FacturaCobrar.id
    ).filter(
        FacturaCobrar.usuario_id == uid,
    ).all()

    total_cuotas_cashea_hoy = sum(float(cu.monto_usd or 0) for cu in cuotas_cashea_hoy_dash)

    # Alertas de bajo stock (hasta 6 productos)
    alertas_stock = Producto.query.filter(
        Producto.usuario_id == uid,
        Producto.activo.is_(True),
        Producto.stock_actual <= Producto.stock_minimo,
        Producto.stock_actual >= 0,
    ).order_by(Producto.stock_actual.asc()).limit(6).all()
    
    # ✅ TOP 5 CLIENTES MAS FRECUENTES (por monto gastado)
    top_clientes_query = db.session.query(
        Cliente.id,
        Cliente.nombre,
        Cliente.telefono,
        func.count(Venta.id).label('total_compras'),
        func.coalesce(func.sum(Venta.total_usd), 0).label('total_gastado'),
    ).join(
        Venta, Venta.cliente_id == Cliente.id
    ).filter(
        Cliente.usuario_id == uid,
        Venta.usuario_id == uid,
    ).group_by(
        Cliente.id, Cliente.nombre, Cliente.telefono
    ).order_by(
        func.sum(Venta.total_usd).desc()
    ).limit(5).all()
    
    top_clientes = []
    for row in top_clientes_query:
        top_clientes.append({
            'id': row.id,
            'nombre': row.nombre,
            'telefono': row.telefono or '',
            'compras': row.total_compras,
            'total': float(row.total_gastado or 0),
        })
    
    # Si no hay clientes con facturas, buscar "Consumidor Final" tambien
    if len(top_clientes) < 5:
        consumidor_final = db.session.query(
            func.count(Venta.id).label('total_compras'),
            func.coalesce(func.sum(Venta.total_usd), 0).label('total_gastado'),
        ).filter(
            Venta.usuario_id == uid,
            Venta.cliente_id.is_(None),
        ).first()
        
        if consumidor_final and consumidor_final.total_compras > 0:
            top_clientes.append({
                'id': None,
                'nombre': 'Consumidor Final',
                'telefono': '',
                'compras': consumidor_final.total_compras,
                'total': float(consumidor_final.total_gastado or 0),
            })
            top_clientes.sort(key=lambda x: x['total'], reverse=True)
            top_clientes = top_clientes[:5]
    
    # ============ ALERTAS DE FACTURAS DE PROVEEDORES ============
    from datetime import timedelta as _td
    hoy = date.today()
    limite_alerta = hoy + _td(days=3)

    facturas_por_vencer_dash = FacturaProveedor.query.filter(
        FacturaProveedor.usuario_id == uid,
        FacturaProveedor.estado == 'pendiente',
        FacturaProveedor.fecha_vencimiento.isnot(None),
        FacturaProveedor.fecha_vencimiento >= hoy,
        FacturaProveedor.fecha_vencimiento <= limite_alerta,
    ).order_by(FacturaProveedor.fecha_vencimiento.asc()).all()

    facturas_vencidas_dash = FacturaProveedor.query.filter(
        FacturaProveedor.usuario_id == uid,
        FacturaProveedor.estado == 'pendiente',
        FacturaProveedor.fecha_vencimiento.isnot(None),
        FacturaProveedor.fecha_vencimiento < hoy,
    ).order_by(FacturaProveedor.fecha_vencimiento.asc()).all()

    inicio_mes_dash = hoy.replace(day=1)
    gastos_mes_dash = Gasto.query.filter(
        Gasto.usuario_id == uid,
        Gasto.fecha >= inicio_mes_dash,
        Gasto.fecha <= hoy,
    ).all()

    total_gastos_mes_dash = sum(float(g.monto_usd or 0) for g in gastos_mes_dash)

    facturas_pendientes_dash = FacturaProveedor.query.filter(
        FacturaProveedor.usuario_id == uid,
        FacturaProveedor.estado == 'pendiente',
    ).all()

    total_facturas_pendientes_dash = sum(float(f.monto_usd or 0) for f in facturas_pendientes_dash)

    return render_template(
        'user/dashboard.html',
        stats=stats,
        alertas_stock=alertas_stock,
        top_clientes=top_clientes,
        limites=SuscripcionesService.verificar_limites(uid),
        suscripcion=SuscripcionesService.obtener_activa(uid),
        tasa_bcv=TasasService.obtener_tasa_bcv(),
        facturas_por_vencer_dash=facturas_por_vencer_dash,
        facturas_vencidas_dash=facturas_vencidas_dash,
        total_por_vencer_dash=sum(float(f.monto_usd or 0) for f in facturas_por_vencer_dash),
        total_vencidas_dash=sum(float(f.monto_usd or 0) for f in facturas_vencidas_dash),
        total_gastos_mes_dash=total_gastos_mes_dash,
        num_gastos_mes_dash=len(gastos_mes_dash),
        total_facturas_pendientes_dash=total_facturas_pendientes_dash,
        num_facturas_pendientes_dash=len(facturas_pendientes_dash),
    )


@user_bp.route('/inventario')
def inventario():
    uid = current_user.id
    search = request.args.get('search', '').strip()
    categoria = request.args.get('categoria', '').strip()
    subcategoria = request.args.get('subcategoria', '').strip()
    marca = request.args.get('marca', '').strip()
    stock_bajo = request.args.get('stock_bajo', '')

    query = Producto.query.filter_by(usuario_id=uid, activo=True)
    if search:
        like = f'%{search}%'
        query = query.filter(db.or_(
            Producto.nombre.ilike(like),
            Producto.codigo.ilike(like),
            Producto.referencia.ilike(like),
        ))
    if categoria:
        query = query.filter_by(categoria=categoria)
    if subcategoria:
        query = query.filter_by(subcategoria=subcategoria)
    if marca:
        query = query.filter_by(marca=marca)
    if stock_bajo == '1':
        query = query.filter(Producto.stock_actual <= Producto.stock_minimo,
                             Producto.stock_actual >= 0)

    productos = query.order_by(Producto.nombre).all()

    categorias_db = [r[0] for r in db.session.query(Producto.categoria).filter(
        Producto.usuario_id == uid,
        Producto.categoria.isnot(None),
        Producto.categoria != '',
    ).distinct().order_by(Producto.categoria).all()]

    subcategorias_db = []
    if categoria:
        subcategorias_db = [r[0] for r in db.session.query(Producto.subcategoria).filter(
            Producto.usuario_id == uid,
            Producto.categoria == categoria,
            Producto.subcategoria.isnot(None),
            Producto.subcategoria != '',
        ).distinct().order_by(Producto.subcategoria).all()]

    stats = {
        'total': len(productos),
        'stock_total': sum(p.stock_actual or 0 for p in productos),
        'valor_total': sum(p.valor_inventario_usd for p in productos),
        'stock_bajo': sum(1 for p in productos if p.stock_bajo),
    }

    return render_template(
        'user/inventario.html',
        productos=productos,
        categorias_db=categorias_db,
        subcategorias_db=subcategorias_db,
        marcas_moto=_marcas_moto(),
        categorias_predefinidas=_categorias_predefinidas(),
        search=search, categoria=categoria, subcategoria=subcategoria,
        marca=marca, stock_bajo=stock_bajo,
        stats=stats,
    )


@user_bp.route('/producto/crear', methods=['POST'])
@check_limite_productos
def crear_producto():
    try:
        InventarioService.crear(
            current_user.id, request.form, request.files,
            current_app.config['UPLOAD_FOLDER']
        )
        flash('Producto agregado correctamente.', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creando producto: {e}')
        flash(f'Error al agregar producto: {e}', 'danger')
    return redirect(url_for('user.inventario'))


@user_bp.route('/producto/<int:producto_id>/editar', methods=['POST'])
def editar_producto(producto_id):
    producto = Producto.query.filter_by(id=producto_id, usuario_id=current_user.id).first_or_404()
    try:
        InventarioService.actualizar(
            producto, request.form, request.files,
            current_app.config['UPLOAD_FOLDER']
        )
        flash('Producto actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error editando producto: {e}')
        flash(f'Error al actualizar: {e}', 'danger')
    return redirect(url_for('user.inventario'))


@user_bp.route('/producto/<int:producto_id>/eliminar', methods=['POST'])
def eliminar_producto(producto_id):
    producto = Producto.query.filter_by(id=producto_id, usuario_id=current_user.id).first_or_404()
    
    if producto.ventas.count() > 0:
        producto.activo = False
        producto.stock_actual = 0
        db.session.commit()
        flash(f'Producto "{producto.nombre}" desactivado (tiene ventas asociadas). '
              'Ya no aparecera en el inventario ni en ventas.', 'info')
    else:
        from ..utils.images import eliminar_imagenes_producto
        eliminar_imagenes_producto(current_user.id, producto.id, current_app.config['UPLOAD_FOLDER'])
        db.session.delete(producto)
        db.session.commit()
        flash('Producto eliminado permanentemente.', 'success')
    
    return redirect(url_for('user.inventario'))


@user_bp.route('/producto/<int:producto_id>/reactivar', methods=['POST'])
def reactivar_producto(producto_id):
    producto = Producto.query.filter_by(id=producto_id, usuario_id=current_user.id).first_or_404()
    producto.activo = True
    db.session.commit()
    flash(f'Producto "{producto.nombre}" reactivado.', 'success')
    return redirect(url_for('user.inventario'))


@user_bp.route('/producto/<int:producto_id>/ajustar-stock', methods=['POST'])
def ajustar_stock(producto_id):
    producto = Producto.query.filter_by(id=producto_id, usuario_id=current_user.id).first_or_404()
    try:
        tipo = request.form.get('tipo_ajuste', '').strip()
        cantidad = int(request.form.get('cantidad', 0))
        if cantidad <= 0:
            flash('La cantidad debe ser mayor a 0.', 'danger')
            return redirect(url_for('user.inventario'))
        ok, resultado = InventarioService.ajustar_stock(producto, tipo, cantidad)
        if ok:
            flash(f'Stock ajustado. Nuevo stock: {resultado}', 'success')
        else:
            flash(resultado, 'danger')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('user.inventario'))


@user_bp.route('/ventas')
def ventas():
    uid = current_user.id
    productos = Producto.query.filter(
        Producto.usuario_id == uid,
        Producto.stock_actual > 0,
        Producto.activo.is_(True),
    ).order_by(Producto.nombre).all()

    ventas_recientes = Venta.query.filter_by(usuario_id=uid) \
        .filter(Venta.estado != 'cancelada') \
        .order_by(Venta.creado_en.desc()).limit(10).all()

    stats = {
        'total_ventas': Venta.query.filter_by(usuario_id=uid).filter(Venta.estado != 'cancelada').count(),
        'ingresos_usd': float(
            db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
            .filter(Venta.usuario_id == uid, Venta.estado != 'cancelada').scalar() or 0
        ),
    }

    inicio_mes = date.today().replace(day=1)
    stats_mes = {
        'ventas': Venta.query.filter(
            Venta.usuario_id == uid,
            Venta.estado != 'cancelada',
            func.date(Venta.creado_en) >= inicio_mes
        ).count(),
        'ingresos_usd': float(
            db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
            .filter(Venta.usuario_id == uid, Venta.estado != 'cancelada', func.date(Venta.creado_en) >= inicio_mes)
            .scalar() or 0
        ),
    }

    clientes = Cliente.query.filter_by(usuario_id=uid).order_by(Cliente.nombre).all()

    vendedores = []
    if not current_user.es_vendedor:
        from ..models.usuario import Usuario
        vendedores = Usuario.query.filter_by(
            usuario_padre_id=uid, es_vendedor=True, activo=True
        ).order_by(Usuario.nombre).all()

    caja_abierta = CajaTurno.query.filter_by(usuario_id=uid, estado='abierta').first()
    return render_template(
        'user/ventas.html',
        caja_abierta=caja_abierta,
        productos=productos,
        ventas_recientes=ventas_recientes,
        stats=stats, stats_mes=stats_mes,
        clientes=clientes, vendedores=vendedores,
        tasa_bcv=TasasService.obtener_tasa_bcv(),
        tasas=TasasService.obtener_tasas(uid),
    )


@user_bp.route('/ventas/procesar', methods=['POST'])
def procesar_venta():
    uid = current_user.id
    limites = SuscripcionesService.verificar_limites(uid)
    ventas_mes = SuscripcionesService.ventas_mes_actual(uid)

    if limites['limite_ventas'] > 0 and ventas_mes >= limites['limite_ventas']:
        return jsonify({
            'success': False,
            'error': f'Lí­mite de {limites["limite_ventas"]} ventas mensuales alcanzado. '
                     'Adquiere el plan VIP.'
        }), 403

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400

    try:
        es_cashea = data.get('tipo_venta') == 'cashea' or data.get('metodo_pago') == 'cashea'
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

        resultado = VentasService.procesar(uid, data)

        tasas = TasasService.obtener_tasas(uid)
        config = FacturasService.obtener_config_empresa(uid)
        resultado['cliente_nombre'] = data.get('cliente_nombre', 'Consumidor Final')
        resultado['metodo_pago'] = data.get('metodo_pago', 'efectivo')
        resultado['observaciones'] = data.get('observaciones', '')

        filename = FacturasService.generar_html(
            resultado, tasas, uid, current_user.nombre, config
        )

        venta_id = resultado.get('primera_venta_id') or resultado.get('factura_id')
        if not venta_id and resultado.get('ventas'):
            venta_id = resultado['ventas'][0].get('venta_id')

        if es_cashea and cashea_data:
            from ..models.factura import FacturaCobrar
            from ..models.cliente import Cliente

            cliente_cashea = None
            if cashea_data['cedula']:
                cliente_cashea = Cliente.query.filter_by(
                    usuario_id=uid,
                    documento=cashea_data['cedula'],
                ).first()

            if not cliente_cashea:
                cliente_cashea = Cliente(
                    usuario_id=uid,
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
                usuario_id=uid,
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

            resultado['cliente_nombre'] = cashea_data['nombre_comprador']

            factura_cobrar = FacturaCobrar.query.filter_by(
                nro_factura=resultado['nro_factura'],
                usuario_id=uid,
            ).first()

            if not factura_cobrar:
                factura_cobrar = FacturaCobrar(
                    usuario_id=uid,
                    venta_id=ventas_factura[0].id if ventas_factura else None,
                    cliente_id=cliente_cashea.id,
                    cliente_nombre=cashea_data['nombre_comprador'],
                    tipo_venta='cashea', # ✅ AQUÍ ESTÁ LA CORRECCIÓN
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
            factura_cobrar.tipo_venta = 'cashea'

            CasheaService.crear_cuotas(
                factura_cobrar,
                cashea_data['num_cuotas'],
                resumen_cashea['saldo'],
            )

            db.session.commit()

        return jsonify({
            'success': True,
            'venta_id': venta_id,
            'message': 'Venta procesada correctamente',
            'ventas': resultado['ventas'],
            'total_usd': resultado['total_usd'],
            'total_ves': resultado['total_ves'],
            'nro_factura': resultado['nro_factura'],
            'factura_url': url_for('user.ver_factura', filename=filename),
            'tipo_venta': resultado['tipo_venta'],
        })
    except VentaError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.exception('Error en procesar_venta')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


@user_bp.route('/facturas')
def facturas():
    uid = current_user.id
    filtro = request.args.get('filtro', 'todas')
    buscar = request.args.get('buscar', '').strip()

    query = FacturaCobrar.query.filter_by(usuario_id=uid)

    # ✅ Excluir facturas Cashea del listado normal
    query = query.filter(FacturaCobrar.tipo_venta != 'cashea')
    if filtro == 'contado':
        query = query.filter_by(tipo_venta='contado')
    elif filtro == 'credito':
        query = query.filter_by(tipo_venta='credito')
    elif filtro == 'pendiente':
        query = query.filter_by(estado='pendiente')
    elif filtro == 'pagado':
        query = query.filter_by(estado='pagado')

    facturas = query.order_by(FacturaCobrar.id.desc()).limit(200).all()

    if buscar:
        bl = buscar.lower()
        facturas = [f for f in facturas
                    if bl in (f.nro_factura or '').lower()
                    or bl in (f.cliente_nombre or '').lower()]

    return render_template('user/facturas.html', facturas=facturas,
                           filtro=filtro, buscar=buscar, uid=uid,
                           tasas=TasasService.obtener_tasas(uid))


@user_bp.route('/factura/<int:factura_id>/abonar', methods=['POST'])
def abonar_factura(factura_id):
    factura = FacturaCobrar.query.filter_by(id=factura_id, usuario_id=current_user.id).first_or_404()
    filtro = request.args.get('filtro', 'todas')

    try:
        monto_usd = float(request.form.get('monto_usd', 0) or 0)
        monto_ves = float(request.form.get('monto_ves', 0) or 0)
        tasa_usada = float(request.form.get('tasa_usada', 36) or 36)
    except ValueError:
        flash('Montos inválidos', 'danger')
        return redirect(url_for('user.facturas', filtro=filtro))

    if monto_usd <= 0:
        flash('El monto en USD debe ser mayor a 0', 'danger')
        return redirect(url_for('user.facturas', filtro=filtro))

    ok, err = VentasService.agregar_abono(
        factura_id, monto_usd, monto_ves, tasa_usada,
        request.form.get('metodo_pago', 'efectivo'),
        request.form.get('notas', ''),
    )
    flash('Pago registrado correctamente.' if ok else err, 'success' if ok else 'danger')
    
    # ✅ Redirigir de vuelta a la vista correcta
    if filtro == 'cashea':
        return redirect(url_for('user.cashea_listado'))
    return redirect(url_for('user.facturas', filtro=filtro))


@user_bp.route('/factura/ver/<path:filename>')
def ver_factura(filename):
    facturas_dir = current_app.config.get("FACTURAS_DIR", "facturas")
    return send_from_directory(facturas_dir, filename)


@user_bp.route('/clientes', methods=['GET', 'POST'])
def clientes():
    uid = current_user.id
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre es obligatorio', 'danger')
        else:
            c = Cliente(
                usuario_id=uid,
                nombre=nombre,
                telefono=request.form.get('telefono', '').strip(),
                email=request.form.get('email', '').strip(),
                direccion=request.form.get('direccion', '').strip(),
                documento=request.form.get('documento', '').strip(),
            )
            db.session.add(c)
            db.session.commit()
            flash('Cliente agregado.', 'success')
        return redirect(url_for('user.clientes'))

    clientes = Cliente.query.filter_by(usuario_id=uid).order_by(Cliente.nombre).all()
    return render_template('user/clientes.html', clientes=clientes)


@user_bp.route('/clientes/<int:cliente_id>/editar', methods=['POST'])
def editar_cliente(cliente_id):
    c = Cliente.query.filter_by(id=cliente_id, usuario_id=current_user.id).first_or_404()
    c.nombre = request.form.get('nombre', '').strip()
    c.telefono = request.form.get('telefono', '').strip()
    c.email = request.form.get('email', '').strip()
    c.direccion = request.form.get('direccion', '').strip()
    c.documento = request.form.get('documento', '').strip()
    db.session.commit()
    flash('Cliente actualizado.', 'success')
    return redirect(url_for('user.clientes'))


@user_bp.route('/clientes/<int:cliente_id>/eliminar', methods=['POST'])
def eliminar_cliente(cliente_id):
    c = Cliente.query.filter_by(id=cliente_id, usuario_id=current_user.id).first_or_404()
    if c.facturas.count() > 0:
        flash('No se puede eliminar: tiene facturas asociadas.', 'danger')
    else:
        db.session.delete(c)
        db.session.commit()
        flash('Cliente eliminado.', 'success')
    return redirect(url_for('user.clientes'))


@user_bp.route('/reportes')
def reportes():
    uid = current_user.id
    
    fecha_desde_str = request.args.get('fecha_desde', '')
    fecha_hasta_str = request.args.get('fecha_hasta', '')
    
    hoy = date.today()
    if not fecha_desde_str:
        fecha_desde = hoy
    else:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_desde = hoy
    
    if not fecha_hasta_str:
        fecha_hasta = hoy
    else:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_hasta = hoy
    
    rango_inicio_utc, rango_fin_utc = rango_entre_caracas(fecha_desde, fecha_hasta)

    try:
        tasa_bcv = float(TasasService.obtener_tasa_bcv())
    except Exception:
        tasa_bcv = 50.0
    
    ventas_rango = Venta.query.filter(
        Venta.usuario_id == uid,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).order_by(Venta.creado_en.desc()).all()
    
    total_usd = sum(float(v.total_usd or 0) for v in ventas_rango)
    total_unidades = sum(int(v.cantidad or 0) for v in ventas_rango)
    num_ventas = len(ventas_rango)
    
    ganancia_usd = 0
    for v in ventas_rango:
        if v.producto:
            costo = float(v.producto.precio_costo_usd or 0)
            precio = float(v.precio_usd or 0)
            ganancia_usd += (precio - costo) * int(v.cantidad or 0)
    
    total_bs = total_usd * tasa_bcv
    ganancia_bs = ganancia_usd * tasa_bcv
    
    try:
        from ..models.cuota_cashea import CuotaCashea as _CC_Rep
        from ..models.factura import FacturaCobrar as _FC_Rep

        _cashea_rango = _CC_Rep.query.filter(
            _CC_Rep.estado == 'pagada',
            _CC_Rep.fecha_pago >= fecha_desde,
            _CC_Rep.fecha_pago <= fecha_hasta,
        ).join(
            _FC_Rep, _CC_Rep.factura_id == _FC_Rep.id
        ).filter(
            _FC_Rep.usuario_id == uid,
        ).all()

        total_cuotas_cashea_hoy = sum(float(c.monto_usd or 0) for c in _cashea_rango)
        num_cuotas_cashea = len(_cashea_rango)
    except Exception as _e_cashea:
        total_cuotas_cashea_hoy = 0
        num_cuotas_cashea = 0
    
    resumen = {
        'fecha_desde': fecha_desde.strftime('%d/%m/%Y'),
        'fecha_hasta': fecha_hasta.strftime('%d/%m/%Y'),
        'num_ventas': num_ventas,
        'total_unidades': total_unidades,
        'total_usd': round(total_usd, 2),
        'total_bs': round(total_bs, 2),
        'ganancia_usd': round(ganancia_usd, 2),
        'ganancia_bs': round(ganancia_bs, 2),
        'tasa_bcv': round(tasa_bcv, 2),
        'ticket_promedio_usd': round(total_usd / num_ventas, 2) if num_ventas > 0 else 0,
        'cuotas_cashea_usd': round(total_cuotas_cashea_hoy, 2),
        'cuotas_cashea_bs': round(total_cuotas_cashea_hoy * tasa_bcv, 2),
        'num_cuotas_cashea': num_cuotas_cashea,
    }
    
    ventas_por_dia_query = db.session.query(
        db.func.date(Venta.creado_en).label('dia'),
        db.func.count().label('cantidad_ventas'),
        db.func.coalesce(db.func.sum(Venta.cantidad), 0).label('unidades'),
        db.func.coalesce(db.func.sum(Venta.total_usd), 0).label('total_usd'),
    ).filter(
        Venta.usuario_id == uid,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).group_by('dia').order_by('dia').all()
    
    ventas_por_dia = []
    total_ganancia_neta_rango = 0
    total_gastos_rango_dias = 0

    for row in ventas_por_dia_query:
        dia = row.dia
        ventas_dia = [v for v in ventas_rango if str(v.creado_en.date()) == str(dia)]
        ganancia_dia = 0
        for v in ventas_dia:
            if v.producto:
                costo = float(v.producto.precio_costo_usd or 0)
                precio = float(v.precio_usd or 0)
                ganancia_dia += (precio - costo) * int(v.cantidad or 0)

        gastos_dia = Gasto.query.filter(
            Gasto.usuario_id == uid,
            Gasto.fecha == dia,
        ).all()
        total_gastos_dia = sum(float(g.monto_usd or 0) for g in gastos_dia)

        ganancia_neta_dia = ganancia_dia - total_gastos_dia

        total_ganancia_neta_rango += ganancia_neta_dia
        total_gastos_rango_dias += total_gastos_dia

        ventas_por_dia.append({
            'dia': dia,
            'dia_fmt': dia.strftime('%d/%m') if hasattr(dia, 'strftime') else str(dia),
            'cantidad_ventas': row.cantidad_ventas,
            'unidades': int(row.unidades),
            'total_usd': round(float(row.total_usd), 2),
            'total_bs': round(float(row.total_usd) * tasa_bcv, 2),
            'ganancia_usd': round(ganancia_dia, 2),
            'ganancia_bs': round(ganancia_dia * tasa_bcv, 2),
            'gastos_usd': round(total_gastos_dia, 2),
            'gastos_bs': round(total_gastos_dia * tasa_bcv, 2),
            'ganancia_neta_usd': round(ganancia_neta_dia, 2),
            'ganancia_neta_bs': round(ganancia_neta_dia * tasa_bcv, 2),
        })
    
    top_productos = db.session.query(
        Producto.nombre,
        Producto.codigo,
        db.func.coalesce(db.func.sum(Venta.cantidad), 0).label('total_vendido'),
        db.func.coalesce(db.func.sum(Venta.total_usd), 0).label('ingresos'),
    ).join(Venta, Venta.producto_id == Producto.id).filter(
        Venta.usuario_id == uid,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).group_by(Producto.id, Producto.nombre, Producto.codigo).order_by(
        db.func.sum(Venta.cantidad).desc()
    ).limit(10).all()
    
    top_productos = [dict(r._mapping) for r in top_productos]
    
    ventas_categoria = db.session.query(
        Producto.categoria,
        db.func.count().label('cantidad'),
        db.func.coalesce(db.func.sum(Venta.total_usd), 0).label('total_usd'),
    ).join(Venta, Venta.producto_id == Producto.id).filter(
        Venta.usuario_id == uid,
        Venta.estado != 'cancelada',
        Venta.creado_en >= rango_inicio_utc,
        Venta.creado_en <= rango_fin_utc,
    ).group_by(Producto.categoria).order_by(db.func.count().desc()).all()
    
    ventas_categoria = [dict(r._mapping) for r in ventas_categoria]
    
    gastos_rango = Gasto.query.filter(
        Gasto.usuario_id == uid,
        Gasto.fecha >= fecha_desde,
        Gasto.fecha <= fecha_hasta,
    ).order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()

    total_gastos_rango = sum(float(g.monto_usd or 0) for g in gastos_rango)
    num_gastos_rango = len(gastos_rango)

    gastos_por_categoria = {}
    for g in gastos_rango:
        cat = g.categoria or 'otros'
        if cat not in gastos_por_categoria:
            gastos_por_categoria[cat] = {'total': 0, 'count': 0}
        gastos_por_categoria[cat]['total'] += float(g.monto_usd or 0)
        gastos_por_categoria[cat]['count'] += 1

    facturas_prov_rango = FacturaProveedor.query.filter(
        FacturaProveedor.usuario_id == uid,
        FacturaProveedor.estado == 'pagada',
        FacturaProveedor.fecha_pago >= fecha_desde,
        FacturaProveedor.fecha_pago <= fecha_hasta,
    ).order_by(FacturaProveedor.fecha_pago.desc()).all()

    total_facturas_prov_rango = sum(float(f.monto_usd or 0) for f in facturas_prov_rango)
    num_facturas_prov_rango = len(facturas_prov_rango)

    from datetime import timedelta as _td
    facturas_por_vencer = FacturaProveedor.query.filter(
        FacturaProveedor.usuario_id == uid,
        FacturaProveedor.estado == 'pendiente',
        FacturaProveedor.fecha_vencimiento.isnot(None),
        FacturaProveedor.fecha_vencimiento >= fecha_desde,
        FacturaProveedor.fecha_vencimiento <= fecha_hasta,
    ).order_by(FacturaProveedor.fecha_vencimiento.asc()).all()

    total_por_vencer = sum(float(f.monto_usd or 0) for f in facturas_por_vencer)

    ventas_por_mes = db.session.query(
        db.func.to_char(Venta.creado_en, 'YYYY-MM').label('mes'),
        db.func.count().label('cantidad'),
        db.func.coalesce(db.func.sum(Venta.total_usd), 0).label('total_usd'),
    ).filter(Venta.usuario_id == uid, Venta.estado != 'cancelada').group_by('mes').order_by(
        db.func.to_char(Venta.creado_en, 'YYYY-MM').desc()
    ).limit(12).all()
    
    ventas_por_mes = [dict(r._mapping) for r in ventas_por_mes]
    
    stats = {
        'total_productos': Producto.query.filter_by(usuario_id=uid, activo=True).count(),
        'stock_total': db.session.query(db.func.coalesce(db.func.sum(Producto.stock_actual), 0))
            .filter_by(usuario_id=uid, activo=True).scalar(),
        'total_ventas': Venta.query.filter_by(usuario_id=uid).filter(Venta.estado != 'cancelada').count(),
        'ingresos_totales': float(
            db.session.query(db.func.coalesce(db.func.sum(Venta.total_usd), 0))
            .filter(Venta.usuario_id == uid, Venta.estado != 'cancelada').scalar() or 0
        ),
    }
    
    resumen['ganancia_neta_usd'] = round(total_ganancia_neta_rango, 2)
    resumen['ganancia_neta_bs'] = round(total_ganancia_neta_rango * tasa_bcv, 2)
    resumen['gastos_rango_dias_usd'] = round(total_gastos_rango_dias, 2)
    resumen['gastos_rango_dias_bs'] = round(total_gastos_rango_dias * tasa_bcv, 2)

    return render_template(
        'user/reportes.html',
        resumen=resumen,
        ventas_por_dia=ventas_por_dia,
        ventas_por_mes=ventas_por_mes,
        top_productos=top_productos,
        ventas_categoria=ventas_categoria,
        stats=stats,
        gastos_rango=gastos_rango,
        total_gastos_rango=total_gastos_rango,
        num_gastos_rango=num_gastos_rango,
        gastos_por_categoria=gastos_por_categoria,
        categorias_gastos=CATEGORIAS_GASTOS,
        facturas_prov_rango=facturas_prov_rango,
        total_facturas_prov_rango=total_facturas_prov_rango,
        num_facturas_prov_rango=num_facturas_prov_rango,
        facturas_por_vencer=facturas_por_vencer,
        total_por_vencer=total_por_vencer,
        fecha_desde=fecha_desde.strftime('%Y-%m-%d'),
        fecha_hasta=fecha_hasta.strftime('%Y-%m-%d'),
    )


# ============ EXCEL ============
@user_bp.route('/inventario/exportar-excel')
@login_required
def exportar_excel():
    from ..services.inventario_excel import InventarioExcelService
    from flask import send_file

    uid = current_user.id
    productos = Producto.query.filter_by(usuario_id=uid).order_by(Producto.nombre).all()

    output = InventarioExcelService.exportar(productos)

    filename = f'inventario_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

# ============================================================
# DESCARGA CON TOKEN (para pywebview)
# ============================================================
import secrets
from datetime import timedelta

_tokens_excel_descarga = {}

@user_bp.route('/inventario/generar-token-excel', methods=['POST'])
@login_required
def generar_token_excel():
    token = secrets.token_urlsafe(32)
    _tokens_excel_descarga[token] = {
        'usuario_id': current_user.id,
        'tipo': 'inventario',
        'expira': datetime.utcnow() + timedelta(minutes=10),
    }
    return jsonify({'success': True, 'token': token})


@user_bp.route('/inventario/generar-token-plantilla', methods=['POST'])
@login_required
def generar_token_plantilla():
    token = secrets.token_urlsafe(32)
    _tokens_excel_descarga[token] = {
        'usuario_id': current_user.id,
        'tipo': 'plantilla',
        'expira': datetime.utcnow() + timedelta(minutes=10),
    }
    return jsonify({'success': True, 'token': token})


@user_bp.route('/inventario/descargar-con-token/<token>')
def descargar_con_token(token):
    from ..services.inventario_excel import InventarioExcelService
    from flask import send_file

    data = _tokens_excel_descarga.pop(token, None)
    if not data:
        return 'Token invalido o ya usado', 403

    if datetime.utcnow() > data['expira']:
        return 'Token expirado', 403

    uid = data['usuario_id']
    tipo = data.get('tipo', 'inventario')

    if tipo == 'plantilla':
        output = InventarioExcelService.plantilla()
        filename = 'plantilla_inventario.xlsx'
    else:
        productos = Producto.query.filter_by(usuario_id=uid).order_by(Producto.nombre).all()
        output = InventarioExcelService.exportar(productos)
        filename = f'inventario_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@user_bp.route('/inventario/plantilla-excel')
@login_required
def plantilla_excel():
    from ..services.inventario_excel import InventarioExcelService
    from flask import send_file

    output = InventarioExcelService.plantilla()

    return send_file(
        output,
        as_attachment=True,
        download_name='plantilla_inventario.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@user_bp.route('/inventario/importar-excel', methods=['POST'])
@login_required
def importar_excel():
    from ..services.inventario_excel import InventarioExcelService

    file = request.files.get('archivo_excel')
    modo = request.form.get('modo', 'actualizar')

    if not file or not file.filename:
        flash('Selecciona un archivo Excel.', 'danger')
        return redirect(url_for('user.inventario'))

    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        flash('Solo se permiten archivos .xlsx o .xls', 'danger')
        return redirect(url_for('user.inventario'))

    try:
        resultado = InventarioExcelService.importar(file, current_user.id, modo=modo)
        msg = (
            f'✅ {resultado["agregados"]} agregados · '
            f'{resultado["actualizados"]} actualizados · '
            f'{resultado["omitidos"]} omitidos'
        )
        if resultado['variantes_agregadas'] or resultado['variantes_actualizadas']:
            msg += f' | Variantes: {resultado["variantes_agregadas"]} nuevas, {resultado["variantes_actualizadas"]} actualizadas'
        if resultado['errores']:
            msg += f' | ⚠️ {len(resultado["errores"])} errores'
            for err_msg in resultado['errores'][:5]:
                flash(err_msg, 'warning')
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Error importando Excel')
        flash(f'Error al importar: {e}', 'danger')

    return redirect(url_for('user.inventario'))


def _categorias_predefinidas():
    return ['Carniceria', 'Repuestos Moto', 'Electrónica', 'Hogar', 'Ropa', 'Herramientas',
            'Automotriz', 'Oficina', 'Alimentos', 'Bebidas', 'Juguetes',
            'Deportes', 'Salud y Belleza', 'Libros', 'Construcción',
            'Farmacia', 'Otros']


def _marcas_moto():
    return sorted(['Bera', 'Empire Keeway', 'Honda', 'Kawasaki', 'Suzuki',
                   'TVS', 'Yamaha', 'Hero', 'Otra Marca'])


def _marcas_por_categoria(categoria):
    marcas = {
        'Repuestos Moto': ['Bera', 'Empire Keeway', 'Hero', 'Honda', 'Kawasaki',
                           'Suzuki', 'TVS', 'Yamaha', 'AKT', 'Bajaj', 'Motocar'],
        'Electrónica': ['Samsung', 'LG', 'Sony', 'Apple', 'Xiaomi', 'Huawei',
                        'Panasonic', 'Philips', 'HP', 'Dell', 'Lenovo', 'Asus',
                        'Acer', 'JBL', 'Logitech'],
        'Hogar': ['Oster', 'Hamilton Beach', 'Black+Decker', 'Philips',
                  'Mabe', 'Whirlpool', 'LG', 'Samsung', 'Imusa'],
        'Ropa': ['Nike', 'Adidas', 'Puma', 'Reebok', 'Under Armour', "Levi's",
                 'Zara', 'H&M', 'Tommy Hilfiger'],
        'Herramientas': ['Stanley', 'DeWalt', 'Bosch', 'Makita', 'Black+Decker',
                         'Truper', 'Klein Tools', 'Milwaukee', 'Craftsman', 'Einhell'],
        'Automotriz': ['Toyota', 'Chevrolet', 'Ford', 'Hyundai', 'Kia', 'Honda',
                       'Nissan', 'Mazda', 'Volkswagen', 'Fiat', 'Renault',
                       'Mitsubishi', 'Jeep'],
        'Oficina': ['Faber-Castell', 'Bic', 'Pilot', 'Paper Mate', 'Maped',
                    'Artesco', 'HP', 'Epson', 'Canon', 'Brother'],
        'Alimentos': ['Nestlé', 'Polar', 'Kraft', 'Heinz', "Kellogg's",
                      'Quaker', 'Del Monte', 'Mary', 'Plumrose', 'Parmalat', 'Danone'],
        'Bebidas': ['Coca-Cola', 'Pepsi', 'Polar', 'Sprite', 'Fanta',
                    'Red Bull', 'Monster', 'Gatorade', 'Malta', 'Brahma', 'Zulia'],
        'Juguetes': ['Lego', 'Hasbro', 'Mattel', 'Fisher-Price', 'Playmobil',
                     'Nerf', 'Barbie', 'Hot Wheels', 'Funko'],
        'Deportes': ['Nike', 'Adidas', 'Puma', 'Under Armour', 'Wilson',
                     'Spalding', 'Coleman', 'Everlast', 'Speedo', 'Reebok'],
        'Salud y Belleza': ['Nivea', "L'Oreal", 'Dove', 'Pantene', 'Head & Shoulders',
                            'Colgate', 'Oral-B', 'Gillette', 'Vaseline', 'Eucerin',
                            'Neutrogena'],
        'Libros': ['Planeta', 'Penguin Random House', 'Santillana', 'Anaya',
                   'Alfaguara', 'Norma'],
        'Construcción': ['Truper', 'Stanley', 'DeWalt', 'Bosch', 'Makita',
                         'Pretul', 'Sika', 'Cemex', 'Holcim', 'Pegatex'],
        'Farmacia': ['Bayer', 'Pfizer', 'Roche', 'Novartis', 'Sanofi',
                     'Genomma Lab', 'MK', 'Beacon', 'Genfar'],
        'Otros': [],
    }
    return sorted(marcas.get(categoria, []))


def _unidades_medida():
    return ['Unidad', 'Caja', 'Paquete', 'Docena', 'Metro', 'Centímetro',
            'Kilogramo', 'Gramo', 'Litro', 'Mililitro', 'Galón', 'Rollo',
            'Par', 'Juego', 'Kit']
                   
@user_bp.route('/producto/<int:producto_id>/datos')
def producto_datos(producto_id):
    from flask import jsonify
    from ..models.producto import ProductoVariante
    
    p = Producto.query.filter_by(id=producto_id, usuario_id=current_user.id).first_or_404()
    
    variantes = []
    for v in ProductoVariante.query.filter_by(producto_id=p.id, activo=True).order_by(ProductoVariante.id).all():
        variantes.append({
            'id': v.id,
            'nombre': v.nombre,
            'codigo': v.codigo or '',
            'stock_actual': v.stock_actual or 0,
            'stock_minimo': v.stock_minimo or 0,
            'precio_costo_usd': float(v.precio_costo_usd or 0),
            'precio_venta_usd': float(v.precio_venta_usd or 0),
        })
    
    return jsonify({
        'id': p.id,
        'nombre': p.nombre,
        'codigo': p.codigo,
        'categoria': p.categoria,
        'subcategoria': p.subcategoria,
        'marca': p.marca,
        'modelo': p.modelo,
        'referencia': p.referencia,
        'color': p.color,
        'descripcion': p.descripcion,
        'precio_costo_usd': float(p.precio_costo_usd or 0),
        'precio_venta_usd': float(p.precio_venta_usd or 0),
        'margen_ganancia': float(p.margen_ganancia or 0),
        'stock_actual': p.stock_actual,
        'stock_minimo': p.stock_minimo,
        'ubicacion': p.ubicacion,
        'impuesto': float(p.impuesto or 16),
        'observaciones': p.observaciones,
        'medida_unidad': p.medida_unidad,
        'medida_cantidad': float(p.medida_cantidad or 1),
        'variantes': variantes,
        'tiene_variantes': len(variantes) > 0,
    })


@user_bp.route('/factura/<int:factura_id>/ver-modal')
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

@user_bp.route('/cambiar-modo-tasa', methods=['POST'])
def cambiar_modo_tasa_route():
    try:
        data = request.get_json() or {}
        modo = data.get('modo', 'auto')
        tasa_manual = data.get('tasa_manual')
        
        if tasa_manual is not None:
            try:
                tasa_manual = float(tasa_manual)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Tasa invalida'})
        
        ok, err = TasasService.cambiar_modo_tasa(current_user.id, modo, tasa_manual)
        
        if ok:
            tasas = TasasService.obtener_tasas(current_user.id)
            return jsonify({
                'success': True,
                'modo': modo,
                'tasa_activa': tasas['oficial'],
                'fuente': tasas['fuente_oficial'],
            })
        else:
            return jsonify({'success': False, 'error': err})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# IMPRIMIR TICKET (POS-58)
# ============================================================
@user_bp.route('/ventas/<int:venta_id>/imprimir-ticket', methods=['POST'])
@login_required
def imprimir_ticket_venta(venta_id):
    from ..services.tickets import TicketsService
    from ..services.facturas import FacturasService

    uid = current_user.id

    venta_ref = Venta.query.filter_by(id=venta_id, usuario_id=uid).first()
    if not venta_ref:
        return jsonify({'success': False, 'error': 'Venta no encontrada'}), 404

    ventas_factura = Venta.query.filter_by(
        nro_factura=venta_ref.nro_factura,
        usuario_id=uid,
    ).order_by(Venta.id).all()

    try:
        config = FacturasService.obtener_config_empresa(uid) or {}
    except Exception:
        config = {}

    empresa = {
        'nombre': config.get('nombre') or 'Mi Negocio',
        'rif': config.get('rif') or '',
        'direccion': config.get('direccion') or '',
        'telefono': config.get('telefono') or '',
    }

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


@user_bp.route('/ventas/<int:venta_id>/ticket-preview', methods=['GET'])
@login_required
def ticket_preview(venta_id):
    from ..services.tickets import TicketsService
    from ..services.facturas import FacturasService

    uid = current_user.id
    venta = Venta.query.filter_by(id=venta_id, usuario_id=uid).first()
    if not venta:
        return jsonify({'success': False, 'error': 'Venta no encontrada'}), 404

    try:
        config = FacturasService.obtener_config_empresa(uid) or {}
    except Exception:
        config = {}

    empresa = {
        'nombre': config.get('nombre') or 'Mi Negocio',
        'rif': config.get('rif') or '',
        'direccion': config.get('direccion') or '',
        'telefono': config.get('telefono') or '',
    }

    venta_data = {
        'nro_factura': venta.nro_factura,
        'cliente_nombre': venta.cliente_nombre,
        'metodo_pago': venta.metodo_pago,
        'total_usd': float(venta.total_usd or 0),
        'tasa_bcv': float(venta.tasa_oficial or 50),
        'productos': [{
            'nombre': venta.producto.nombre if venta.producto else 'Producto',
            'cantidad': venta.cantidad,
            'precio_usd': float(venta.precio_usd or 0),
        }],
    }

    texto = TicketsService.generar_texto_ticket(venta_data, empresa, vendedor_nombre=current_user.nombre)
    return jsonify({'success': True, 'ticket': texto})

# ============================================================
# CONFIGURAR PIN DE CANCELACION (solo VIP)
# ============================================================
@user_bp.route('/perfil/pin', methods=['POST'])
@login_required
def configurar_pin_cancelacion():
    if current_user.es_vendedor:
        return jsonify({'success': False, 'error': 'Solo el VIP puede configurar el PIN'}), 403

    data = request.get_json() or {}
    pin = data.get('pin', '').strip()
    pin_confirm = data.get('pin_confirm', '').strip()

    if not pin.isdigit() or len(pin) != 6:
        return jsonify({'success': False, 'error': 'El PIN debe tener exactamente 6 digitos'}), 400

    if pin != pin_confirm:
        return jsonify({'success': False, 'error': 'Los PINes no coinciden'}), 400

    try:
        current_user.set_pin_cancelacion(pin)
        db.session.commit()
        return jsonify({'success': True, 'message': 'PIN configurado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# CANCELAR FACTURA (VIP)
# ============================================================
@user_bp.route('/facturas/<nro_factura>/cancelar', methods=['POST'])
@login_required
def cancelar_factura(nro_factura):
    if current_user.es_vendedor:
        return jsonify({'success': False, 'error': 'Los vendedores deben usar la ruta de vendedor'}), 403

    data = request.get_json() or {}
    pin = data.get('pin', '').strip()
    motivo = data.get('motivo', '').strip()[:500]

    if not current_user.tiene_pin_cancelacion:
        return jsonify({'success': False, 'error': 'No has configurado un PIN de cancelacion'}), 400

    if not current_user.check_pin_cancelacion(pin):
        return jsonify({'success': False, 'error': 'PIN incorrecto'}), 401

    ventas = Venta.query.filter_by(
        nro_factura=nro_factura,
        usuario_id=current_user.id,
    ).all()

    if not ventas:
        return jsonify({'success': False, 'error': 'Factura no encontrada'}), 404

    if all(v.estado == 'cancelada' for v in ventas):
        return jsonify({'success': False, 'error': 'Esta factura ya esta cancelada'}), 400

    from datetime import datetime, timedelta
    ahora = datetime.utcnow()
    for v in ventas:
        if v.creado_en and (ahora - v.creado_en) > timedelta(days=3):
            return jsonify({
                'success': False,
                'error': 'Solo se pueden cancelar facturas de los ultimos 3 dias'
            }), 400

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
        v.cancelado_por_id = current_user.id
        v.motivo_cancelacion = motivo

    try:
        from ..models.factura import FacturaCobrar
        facturas_cobrar = FacturaCobrar.query.filter_by(
            nro_factura=nro_factura,
            usuario_id=current_user.id,
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
# GASTOS
# ============================================================
from ..models.gasto import Gasto, CATEGORIAS_GASTOS, METODOS_PAGO
from ..models.factura_proveedor import FacturaProveedor
from ..models.cuota_cashea import CuotaCashea


@user_bp.route('/gastos')
@login_required
def gastos_listado():
    from datetime import date, timedelta

    uid = current_user.id
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
            filtro_desde = datetime.strptime(filtro_desde_str, '%Y-%m-%d').date()
        except ValueError:
            filtro_desde = None

    if filtro_hasta_str:
        try:
            filtro_hasta = datetime.strptime(filtro_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            filtro_hasta = None

    if not filtro_desde and not filtro_hasta and not filtro_rango:
        filtro_desde = hoy
        filtro_hasta = hoy
        filtro_rango = 'hoy'

    query = Gasto.query.filter_by(usuario_id=uid)
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

    totales_categoria = {}
    for g in gastos:
        cat = g.categoria or 'otros'
        totales_categoria[cat] = totales_categoria.get(cat, 0) + float(g.monto_usd or 0)

    inicio_mes = hoy.replace(day=1)
    gastos_mes = Gasto.query.filter(
        Gasto.usuario_id == uid,
        Gasto.fecha >= inicio_mes,
        Gasto.fecha <= hoy,
    ).all()
    total_mes = sum(float(g.monto_usd or 0) for g in gastos_mes)

    inicio_anio = hoy.replace(month=1, day=1)
    gastos_anio = Gasto.query.filter(
        Gasto.usuario_id == uid,
        Gasto.fecha >= inicio_anio,
    ).all()
    total_anio = sum(float(g.monto_usd or 0) for g in gastos_anio)

    return render_template(
        'user/gastos.html',
        gastos=gastos,
        total_filtro=total_filtro,
        total_mes=total_mes,
        total_anio=total_anio,
        totales_categoria=totales_categoria,
        categorias=CATEGORIAS_GASTOS,
        metodos_pago=METODOS_PAGO,
        filtro_desde=filtro_desde_str,
        filtro_hasta=filtro_hasta_str,
        filtro_categoria=filtro_categoria,
        filtro_buscar=filtro_buscar,
        filtro_rango=filtro_rango,
    )


@user_bp.route('/gastos/crear', methods=['POST'])
@login_required
def gastos_crear():
    from datetime import date, datetime as _dt

    uid = current_user.id

    categoria = request.form.get('categoria', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    monto_usd = request.form.get('monto_usd', '0').strip()
    monto_ves = request.form.get('monto_ves', '0').strip()
    fecha_str = request.form.get('fecha', '').strip()
    metodo_pago = request.form.get('metodo_pago', 'efectivo').strip()
    proveedor_nombre = request.form.get('proveedor_nombre', '').strip()
    notas = request.form.get('notas', '').strip()

    if not categoria or not descripcion or not monto_usd:
        flash('Categoria, descripcion y monto son obligatorios', 'danger')
        return redirect(url_for('user.gastos_listado'))

    try:
        monto_usd = float(monto_usd)
        if monto_usd <= 0:
            raise ValueError('Monto debe ser mayor a 0')
    except (ValueError, TypeError):
        flash('Monto invalido', 'danger')
        return redirect(url_for('user.gastos_listado'))

    try:
        monto_ves = float(monto_ves) if monto_ves else 0
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
        from ..services.tasas import TasasService
        tasa = TasasService.obtener_tasa_bcv()
        tasa = float(tasa) if tasa else 0
    except Exception:
        tasa = 0

    gasto = Gasto(
        usuario_id=uid,
        categoria=categoria,
        descripcion=descripcion,
        monto_usd=monto_usd,
        monto_ves=monto_ves or (monto_usd * tasa),
        tasa_bcv=tasa,
        fecha=fecha,
        metodo_pago=metodo_pago,
        proveedor_nombre=proveedor_nombre,
        notas=notas,
    )

    db.session.add(gasto)
    db.session.commit()

    flash('Gasto registrado', 'success')
    return redirect(url_for('user.gastos_listado'))


@user_bp.route('/gastos/<int:gasto_id>/editar', methods=['POST'])
@login_required
def gastos_editar(gasto_id):
    from datetime import date, datetime as _dt

    uid = current_user.id
    gasto = Gasto.query.filter_by(id=gasto_id, usuario_id=uid).first()
    if not gasto:
        flash('Gasto no encontrado', 'danger')
        return redirect(url_for('user.gastos_listado'))

    gasto.categoria = request.form.get('categoria', gasto.categoria).strip()
    gasto.descripcion = request.form.get('descripcion', gasto.descripcion).strip()
    try:
        gasto.monto_usd = float(request.form.get('monto_usd', gasto.monto_usd))
    except (ValueError, TypeError):
        pass
    gasto.metodo_pago = request.form.get('metodo_pago', gasto.metodo_pago).strip()
    gasto.proveedor_nombre = request.form.get('proveedor_nombre', gasto.proveedor_nombre or '').strip()
    gasto.notas = request.form.get('notas', gasto.notas or '').strip()

    fecha_str = request.form.get('fecha', '')
    if fecha_str:
        try:
            gasto.fecha = _dt.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    db.session.commit()
    flash('Gasto actualizado', 'success')
    return redirect(url_for('user.gastos_listado'))


@user_bp.route('/gastos/<int:gasto_id>/eliminar', methods=['POST'])
@login_required
def gastos_eliminar(gasto_id):
    uid = current_user.id
    gasto = Gasto.query.filter_by(id=gasto_id, usuario_id=uid).first()
    if not gasto:
        return jsonify({'success': False, 'error': 'Gasto no encontrado'}), 404

    db.session.delete(gasto)
    db.session.commit()

    return jsonify({'success': True})


# ============================================================
# FACTURAS DE PROVEEDORES
# ============================================================
@user_bp.route('/proveedores/facturas')
@login_required
def proveedores_facturas():
    from datetime import date

    uid = current_user.id
    hoy = date.today()

    filtro_estado = request.args.get('estado', 'todas').strip()
    filtro_tipo = request.args.get('tipo', 'todos').strip()
    filtro_buscar = request.args.get('buscar', '').strip()

    query = FacturaProveedor.query.filter_by(usuario_id=uid)

    if filtro_estado == 'pendiente':
        query = query.filter_by(estado='pendiente')
    elif filtro_estado == 'pagada':
        query = query.filter_by(estado='pagada')
    elif filtro_estado == 'vencida':
        query = query.filter(FacturaProveedor.estado == 'pendiente', FacturaProveedor.fecha_vencimiento < hoy)
    elif filtro_estado == 'por_vencer':
        query = query.filter(
            FacturaProveedor.estado == 'pendiente',
            FacturaProveedor.fecha_vencimiento >= hoy,
            FacturaProveedor.fecha_vencimiento <= hoy + timedelta(days=3),
        )

    if filtro_tipo == 'contado':
        query = query.filter_by(tipo='contado')
    elif filtro_tipo == 'credito':
        query = query.filter_by(tipo='credito')

    facturas = query.order_by(
        FacturaProveedor.estado.asc(),
        FacturaProveedor.fecha_vencimiento.asc(),
        FacturaProveedor.id.desc(),
    ).all()

    if filtro_buscar:
        bl = filtro_buscar.lower()
        facturas = [f for f in facturas
                    if bl in (f.proveedor_nombre or '').lower()
                    or bl in (f.nro_factura or '').lower()]

    total_pendiente = sum(float(f.monto_usd or 0) for f in facturas if f.estado == 'pendiente')
    total_pagado = sum(float(f.monto_usd or 0) for f in facturas if f.estado == 'pagada')
    total_vencidas = sum(float(f.monto_usd or 0) for f in facturas if f.estado == 'pendiente' and f.vencida)
    total_por_vencer = sum(float(f.monto_usd or 0) for f in facturas if f.estado == 'pendiente' and f.por_vencer)

    return render_template(
        'user/facturas_proveedores.html',
        facturas=facturas,
        total_pendiente=total_pendiente,
        total_pagado=total_pagado,
        total_vencidas=total_vencidas,
        total_por_vencer=total_por_vencer,
        filtro_estado=filtro_estado,
        filtro_tipo=filtro_tipo,
        filtro_buscar=filtro_buscar,
        metodos_pago=METODOS_PAGO,
    )


@user_bp.route('/proveedores/facturas/crear', methods=['POST'])
@login_required
def proveedores_crear():
    from datetime import date, datetime as _dt

    uid = current_user.id

    proveedor_nombre = request.form.get('proveedor_nombre', '').strip()
    proveedor_rif = request.form.get('proveedor_rif', '').strip()
    proveedor_telefono = request.form.get('proveedor_telefono', '').strip()
    nro_factura = request.form.get('nro_factura', '').strip()
    monto_usd = request.form.get('monto_usd', '0').strip()
    tipo = request.form.get('tipo', 'contado').strip()
    fecha_emision_str = request.form.get('fecha_emision', '').strip()
    fecha_vencimiento_str = request.form.get('fecha_vencimiento', '').strip()
    notas = request.form.get('notas', '').strip()
    metodo_pago = request.form.get('metodo_pago', 'efectivo').strip()

    if not proveedor_nombre or not monto_usd:
        flash('Proveedor y monto son obligatorios', 'danger')
        return redirect(url_for('user.proveedores_facturas'))

    try:
        monto_usd = float(monto_usd)
        if monto_usd <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Monto invalido', 'danger')
        return redirect(url_for('user.proveedores_facturas'))

    if fecha_emision_str:
        try:
            fecha_emision = _dt.strptime(fecha_emision_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_emision = date.today()
    else:
        fecha_emision = date.today()

    fecha_vencimiento = None
    if tipo == 'credito' and fecha_vencimiento_str:
        try:
            fecha_vencimiento = _dt.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    try:
        from ..services.tasas import TasasService
        tasa = float(TasasService.obtener_tasa_bcv() or 0)
    except Exception:
        tasa = 0

    if tipo == 'contado':
        estado = 'pagada'
    else:
        estado = 'pendiente'

    factura = FacturaProveedor(
        usuario_id=uid,
        proveedor_nombre=proveedor_nombre,
        proveedor_rif=proveedor_rif,
        proveedor_telefono=proveedor_telefono,
        nro_factura=nro_factura,
        monto_usd=monto_usd,
        monto_ves=monto_usd * tasa,
        tasa_bcv=tasa,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        tipo=tipo,
        estado=estado,
        metodo_pago=metodo_pago if tipo == 'contado' else None,
        fecha_pago=date.today() if tipo == 'contado' else None,
        monto_pagado_usd=monto_usd if tipo == 'contado' else 0,
        notas=notas,
    )
    db.session.add(factura)
    db.session.flush()

    db.session.commit()
    flash('Factura de proveedor registrada', 'success')
    return redirect(url_for('user.proveedores_facturas'))


@user_bp.route('/proveedores/facturas/<int:factura_id>/pagar', methods=['POST'])
@login_required
def proveedores_pagar(factura_id):
    from datetime import date

    uid = current_user.id
    factura = FacturaProveedor.query.filter_by(id=factura_id, usuario_id=uid).first()
    if not factura:
        return jsonify({'success': False, 'error': 'Factura no encontrada'}), 404

    if factura.estado == 'pagada':
        return jsonify({'success': False, 'error': 'Ya esta pagada'}), 400

    data = request.get_json() or {}
    metodo_pago = data.get('metodo_pago', 'efectivo').strip() or 'efectivo'

    factura.estado = 'pagada'
    factura.fecha_pago = date.today()
    factura.monto_pagado_usd = factura.monto_usd
    factura.metodo_pago = metodo_pago

    db.session.commit()

    return jsonify({'success': True})


@user_bp.route('/proveedores/facturas/<int:factura_id>/eliminar', methods=['POST'])
@login_required
def proveedores_eliminar(factura_id):
    uid = current_user.id
    factura = FacturaProveedor.query.filter_by(id=factura_id, usuario_id=uid).first()
    if not factura:
        return jsonify({'success': False, 'error': 'Factura no encontrada'}), 404

    if factura.gasto:
        db.session.delete(factura.gasto)

    db.session.delete(factura)
    db.session.commit()

    return jsonify({'success': True})

# ============================================================
# CASHEA (VIP)
# ============================================================
@user_bp.route('/cashea')
@login_required
def cashea_listado():
    """Listado de facturas Cashea con resumen."""
    uid = current_user.id

    filtro_estado = request.args.get('estado', 'todas').strip()
    filtro_buscar = request.args.get('buscar', '').strip()

    # 1. Obtener las facturas filtradas para la tabla
    query = FacturaCobrar.query.filter(
        FacturaCobrar.usuario_id == uid,
        FacturaCobrar.tipo_venta == 'cashea',
    )

    if filtro_estado == 'pendiente':
        query = query.filter_by(estado='pendiente')
    elif filtro_estado == 'pagado':
        query = query.filter_by(estado='pagado')

    facturas = query.order_by(FacturaCobrar.id.desc()).all()

    if filtro_buscar:
        bl = filtro_buscar.lower()
        facturas = [f for f in facturas
                    if bl in (f.cashea_nombre_comprador or '').lower()
                    or bl in (f.cashea_cedula or '').lower()
                    or bl in (f.nro_factura or '').lower()]

    # 2. Calcular los totales globales para las tarjetas de resumen
    todas_facturas_cashea = FacturaCobrar.query.filter(
        FacturaCobrar.usuario_id == uid,
        FacturaCobrar.tipo_venta == 'cashea',
    ).all()

    total_ventas_cashea = 0
    total_inicial = 0
    total_cuotas_pagadas = 0
    ganancia_cashea = 0

    for f in todas_facturas_cashea:
        total_ventas_cashea += float(f.total_usd or 0)
        total_inicial += float(f.cashea_monto_inicial or 0)
        
        # Sumar cuotas pagadas
        for c in f.cuotas_cashea:
            if c.estado == 'pagada':
                total_cuotas_pagadas += float(c.monto_usd or 0)
                
        # Calcular ganancia de esta factura
        ventas = Venta.query.filter_by(nro_factura=f.nro_factura, usuario_id=uid).all()
        for v in ventas:
            if v.producto:
                costo = float(v.producto.precio_costo_usd or 0)
                precio = float(v.precio_usd or 0)
                ganancia_cashea += (precio - costo) * int(v.cantidad or 0)

    total_cobrado = total_inicial + total_cuotas_pagadas

    from ..services.tasas import TasasService
    tasas = TasasService.obtener_tasas(uid)

    return render_template(
        'user/cashea.html',
        facturas=facturas,
        filtro_estado=filtro_estado,
        filtro_buscar=filtro_buscar,
        tasas=tasas,
        # Variables para las tarjetas de resumen
        total_ventas_cashea=total_ventas_cashea,
        total_cobrado=total_cobrado,
        total_inicial=total_inicial,
        total_cuotas_pagadas=total_cuotas_pagadas,
        ganancia_cashea=ganancia_cashea,
        total_facturas=len(todas_facturas_cashea)
    )


@user_bp.route('/cashea/cuota/<int:cuota_id>/pagar', methods=['POST'])
@login_required
def cashea_pagar_cuota(cuota_id):
    """Marca una cuota Cashea como pagada."""
    uid = current_user.id
    # Filtro directo: solo cuotas de facturas del usuario actual
    cuota = CuotaCashea.query.join(FacturaCobrar).filter(
        CuotaCashea.id == cuota_id,
        FacturaCobrar.usuario_id == uid,
    ).first()

    if not cuota:
        return jsonify({'success': False, 'error': 'Cuota no encontrada'}), 404

    exito, error = CasheaService.marcar_cuota_pagada(cuota)
    if exito:
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': error}), 400

# ============================================================
# CAJA (APERTURA Y CIERRE)
# ============================================================
@user_bp.route('/caja', methods=['GET', 'POST'])
@login_required
def caja():
    uid = current_user.id
    caja_abierta = CajaTurno.query.filter_by(usuario_id=uid, estado='abierta').first()
    
    if request.method == 'POST' and not caja_abierta:
        try:
            usd = float(request.form.get('saldo_inicial_usd', 0) or 0)
            bs = float(request.form.get('saldo_inicial_bs', 0) or 0)
            
            nueva_caja = CajaTurno(
                usuario_id=uid,
                saldo_inicial_usd=usd,
                saldo_inicial_bs=bs,
                estado='abierta'
            )
            db.session.add(nueva_caja)
            db.session.commit()
            flash('Caja abierta correctamente.', 'success')
            return redirect(url_for('user.caja'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al abrir caja: {e}', 'danger')

    cierres = CajaTurno.query.filter_by(usuario_id=uid, estado='cerrada').order_by(CajaTurno.cerrada_en.desc()).limit(10).all()
    
    from ..services.tasas import TasasService
    tasa_actual = TasasService.obtener_tasa_bcv()
    return render_template('user/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasa_bcv=tasa_actual)

@user_bp.route('/caja/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    uid = current_user.id
    caja = CajaTurno.query.filter_by(usuario_id=uid, estado='abierta').first()
    
    if caja:
        caja.estado = 'cerrada'
        caja.cerrada_en = datetime.utcnow()
        
        # Arqueo Z (Cálculo de faltantes/sobrantes)
        caja.saldo_real_usd = float(request.form.get('saldo_real_usd', 0) or 0)
        caja.saldo_real_bs = float(request.form.get('saldo_real_bs', 0) or 0)
        
        esperado_usd = float(caja.saldo_inicial_usd) + float(caja.total_ventas_efectivo_usd)
        esperado_bs = float(caja.saldo_inicial_bs) + float(caja.total_ventas_efectivo_bs)
        
        caja.diferencia_usd = caja.saldo_real_usd - esperado_usd
        caja.diferencia_bs = caja.saldo_real_bs - esperado_bs
        
        db.session.commit()
        flash('Caja cerrada correctamente. Turno finalizado.', 'success')
    else:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        
    return redirect(url_for('user.caja'))


# ============================================================
# SCANNER DE PRECIOS (MODO PASILLO)
# ============================================================
@user_bp.route('/scanner')
@login_required
def scanner():
    return render_template('user/scanner.html', tiempo_scanner=current_user.scanner_tiempo or 10)

@user_bp.route('/scanner/configurar', methods=['POST'])
@login_required
def configurar_scanner():
    try:
        tiempo = int(request.form.get('tiempo', 10))
        current_user.scanner_tiempo = tiempo
        db.session.commit()
        flash('Tiempo de pantalla actualizado a ' + str(tiempo) + ' segundos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al configurar el tiempo.', 'danger')
    return redirect(url_for('user.scanner'))

@user_bp.route('/scanner/buscar', methods=['POST'])
@login_required
def scanner_buscar():
    data = request.get_json() or {}
    codigo = data.get('codigo', '').strip()
    
    if not codigo:
        return jsonify({'success': False, 'error': 'Código vacío'})
        
    # Buscar producto (por código exacto o nombre)
    from ..models.producto import Producto, ProductoVariante
    from ..services.tasas import TasasService
    
    producto = Producto.query.filter(
        Producto.usuario_id == current_user.id,
        Producto.activo.is_(True),
        db.or_(Producto.codigo.ilike(codigo), Producto.nombre.ilike(f'%{codigo}%'))
    ).first()
    
    if not producto:
        return jsonify({'success': False, 'error': 'Producto no encontrado'})
        
    tasas = TasasService.obtener_tasas(current_user.id)
    tasa_actual = float(tasas['oficial'])
    
    # Formatear precios
    precio_usd = float(producto.precio_venta_usd)
    precio_bs = precio_usd * tasa_actual
    
    return jsonify({
        'success': True,
        'nombre': producto.nombre,
        'codigo': producto.codigo,
        'precio_usd': precio_usd,
        'precio_bs': precio_bs,
        'tasa': tasa_actual
    })
