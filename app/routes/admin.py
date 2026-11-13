# app/routes/admin.py
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from ..extensions import db
from ..models.usuario import Usuario
from ..models.suscripcion import Suscripcion
from ..models.config import ConfigEmpresa
from ..services.suscripciones import SuscripcionesService
from ..utils.decorators import admin_required


admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
@login_required
@admin_required
def before_request():
    pass


@admin_bp.route('/dashboard')
def dashboard():
    from datetime import date
    
    # ✅ Solo usuarios principales (dueños de negocio, SIN vendedores)
    total_usuarios = Usuario.query.filter(
        Usuario.role == 'user',
        Usuario.es_vendedor.is_(False),
    ).count()
    
    # ✅ Total de vendedores en el sistema (solo para info)
    total_vendedores = Usuario.query.filter(
        Usuario.es_vendedor.is_(True),
        Usuario.activo.is_(True),
    ).count()
    
    suscripciones_activas = Suscripcion.query.filter(
        Suscripcion.estado == 'activa',
        Suscripcion.fecha_fin >= date.today(),
    ).count()

    # ✅ Usuarios recientes (SIN vendedores)
    usuarios_recientes = Usuario.query.filter(
        Usuario.role == 'user',
        Usuario.es_vendedor.is_(False),
    ).order_by(Usuario.fecha_registro.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_usuarios=total_usuarios,
        total_vendedores=total_vendedores,
        suscripciones_activas=suscripciones_activas,
        usuarios_recientes=usuarios_recientes,
    )


@admin_bp.route('/usuarios')
def usuarios():
    # ✅ Solo usuarios principales (dueños de negocio)
    # NO incluir vendedores (esos pertenecen al VIP)
    usuarios = Usuario.query.filter(
        Usuario.role == 'user',
        Usuario.es_vendedor.is_(False),
    ).order_by(Usuario.nombre).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


@admin_bp.route('/suscripciones')
def suscripciones():
    # JOIN entre Suscripcion y Usuario para traer nombre y email
    resultados = db.session.query(
        Suscripcion,
        Usuario.nombre.label('usuario_nombre'),
        Usuario.email.label('usuario_email'),
    ).join(
        Usuario, Suscripcion.usuario_id == Usuario.id
    ).filter(
        Usuario.role == 'user',
        Usuario.es_vendedor.is_(False),  # ✅ excluir vendedores
    ).order_by(
        Suscripcion.creado_en.desc()
    ).all()

    suscripciones = []
    for s, nombre, email in resultados:
        d = {
            'id': s.id,
            'usuario_id': s.usuario_id,
            'plan': s.plan,
            'dias': s.dias,
            'fecha_inicio': s.fecha_inicio.strftime('%d/%m/%Y') if s.fecha_inicio else '',
            'fecha_fin': s.fecha_fin.strftime('%d/%m/%Y') if s.fecha_fin else '',
            'estado': s.estado,
            'monto': float(s.monto) if s.monto else 0,
            'notas': s.notas or '',
            'creado_en': s.creado_en.strftime('%d/%m/%Y') if s.creado_en else '',
            'usuario_nombre': nombre or 'Sin nombre',
            'usuario_email': email or 'Sin email',
        }
        suscripciones.append(d)

    # Usuarios sin suscripcion activa
    subquery = db.session.query(Suscripcion.usuario_id).filter(
        Suscripcion.estado == 'activa',
        Suscripcion.fecha_fin >= date.today(),
    ).subquery()

    usuarios_sin = Usuario.query.filter(
        Usuario.activo.is_(True),
        Usuario.role == 'user',
        Usuario.es_vendedor.is_(False),  # ✅ excluir vendedores
        ~Usuario.id.in_(db.session.query(subquery.c.usuario_id)),
    ).order_by(Usuario.nombre).all()

    return render_template('admin/suscripciones.html',
                           suscripciones=suscripciones,
                           usuarios_sin_suscripcion=usuarios_sin)

@admin_bp.route('/suscripciones/crear', methods=['POST'])
def crear_suscripcion():
    uid = request.form.get('usuario_id', type=int)
    plan = request.form.get('plan', 'VIP')
    dias = request.form.get('dias', 30, type=int)

    if not uid or dias <= 0:
        flash('Datos inválidos', 'danger')
        return redirect(url_for('admin.suscripciones'))

    s, err = SuscripcionesService.crear(uid, plan, dias, current_user.id)
    if err:
        flash(err, 'warning')
    else:
        flash(f'Suscripción {plan} creada hasta {s.fecha_fin.strftime("%d/%m/%Y")}', 'success')
    return redirect(url_for('admin.suscripciones'))


@admin_bp.route('/suscripciones/<int:sid>/cancelar', methods=['POST'])
def cancelar_suscripcion(sid):
    ok, err = SuscripcionesService.cancelar(sid, current_user.id)
    flash('Suscripción cancelada.' if ok else err, 'success' if ok else 'danger')
    return redirect(url_for('admin.suscripciones'))


@admin_bp.route('/suscripciones/<int:sid>/extender', methods=['POST'])
def extender_suscripcion(sid):
    dias = request.form.get('dias_extra', 30, type=int)
    ok, err = SuscripcionesService.extender(sid, dias)
    flash(f'Suscripción extendida {dias} dÍ­as.' if ok else err,
          'success' if ok else 'danger')
    return redirect(url_for('admin.suscripciones'))


@admin_bp.route('/usuarios/<int:uid>/empresa', methods=['GET', 'POST'])
def configurar_empresa(uid):
    usuario = db.session.get(Usuario, uid)
    if not usuario:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.usuarios'))

    config = ConfigEmpresa.query.filter_by(usuario_id=uid).first()
    if not config:
        config = ConfigEmpresa(usuario_id=uid)
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.nombre = request.form.get('nombre', '').strip()
        config.rif = request.form.get('rif', '').strip()
        config.direccion = request.form.get('direccion', '').strip()
        config.telefono = request.form.get('telefono', '').strip()
        config.email = request.form.get('email', '').strip()
        config.mensaje_factura = request.form.get('mensaje_factura', '').strip()
        db.session.commit()
        flash('Configuración actualizada.', 'success')
        return redirect(url_for('admin.configurar_empresa', uid=uid))

    return render_template('admin/configurar_empresa.html',
                           usuario=usuario, config=config)

@admin_bp.route('/suscripciones/<int:sid>/eliminar', methods=['POST'])
def eliminar_suscripcion(sid):
    s = db.session.get(Suscripcion, sid)
    if not s:
        flash('Suscripción no encontrada', 'danger')
        return redirect(url_for('admin.suscripciones'))

    # Solo permitir eliminar las canceladas
    if s.estado != 'cancelada':
        flash('Solo se pueden eliminar suscripciones canceladas.', 'warning')
        return redirect(url_for('admin.suscripciones'))

    db.session.delete(s)
    db.session.commit()
    flash('Suscripción eliminada del historial.', 'success')
    return redirect(url_for('admin.suscripciones'))


@admin_bp.route('/usuarios/<int:uid>/activar', methods=['POST'])
def activar_usuario(uid):
    usuario = db.session.get(Usuario, uid)
    if not usuario:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.usuarios'))
        
    usuario.activo = True
    usuario.codigo_verificacion = None
    usuario.codigo_expira = None
    db.session.commit()
    
    flash(f'Usuario {usuario.nombre} activado manualmente con éxito.', 'success')
    return redirect(url_for('admin.usuarios'))
