# app/routes/vip.py
"""
Blueprint para gestion de vendedores por parte del usuario VIP.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models.usuario import Usuario, VendedorConfig
from ..services.vendedores import VendedorService
from ..utils.decorators import vendedor_required, admin_required
from ..services.suscripciones import SuscripcionesService


vip_bp = Blueprint('vip', __name__)


def _check_acceso():
    """Verifica que el usuario pueda gestionar vendedores (debe ser VIP)."""
    # No vendedores
    if current_user.es_vendedor:
        flash('Acceso denegado', 'danger')
        return False
    
    # ✅ Debe ser VIP (suscripcion activa)
    if not current_user.suscripcion_vigente:
        flash('Solo usuarios VIP pueden crear y gestionar vendedores. Adquiere tu plan VIP.', 'warning')
        return False
    
    return True


@vip_bp.route('/vendedores')
@login_required
def lista():
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    vendedores = VendedorService.listar(current_user.id)
    total = VendedorService.contar(current_user.id)
    
    # Stats de cada vendedor
    for v in vendedores:
        v._stats = VendedorService.stats_vendedor(v.vendedor_id)
    
    limites = {
        'total': total,
        'max': VendedorConfig.MAX_VENDEDORES,
        'puede_crear': VendedorService.puede_crear_mas(current_user.id),
    }
    
    return render_template('vip/vendedores.html',
                           vendedores=vendedores,
                           limites=limites)


@vip_bp.route('/vendedores/crear', methods=['GET', 'POST'])
@login_required
def crear():
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    # Validar VIP
    if not VendedorService.es_vip(current_user.id):
        flash('Solo usuarios VIP pueden crear vendedores.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    if not VendedorService.puede_crear_mas(current_user.id):
        flash(f'Limite alcanzado. Maximo {VendedorConfig.MAX_VENDEDORES} vendedores.', 'warning')
        return redirect(url_for('vip.lista'))
    
    if request.method == 'POST':
        vendedor, err = VendedorService.crear(current_user.id, request.form)
        if err:
            flash(err, 'danger')
        else:
            flash(f'Vendedor "{vendedor.nombre}" creado correctamente.', 'success')
            return redirect(url_for('vip.lista'))
    
    return render_template('vip/crear_vendedor.html')


@vip_bp.route('/vendedores/<int:vendedor_id>')
@login_required
def detalle(vendedor_id):
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=current_user.id).first_or_404()
    config = VendedorConfig.query.filter_by(vendedor_id=vendedor_id).first()
    
    stats = VendedorService.stats_vendedor(vendedor_id)
    ventas = VendedorService.ventas_recientes(vendedor_id, 20)
    
    return render_template('vip/detalle_vendedor.html',
                           vendedor=vendedor,
                           config=config,
                           stats=stats,
                           ventas=ventas)


@vip_bp.route('/vendedores/<int:vendedor_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(vendedor_id):
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=current_user.id).first_or_404()
    config = VendedorConfig.query.filter_by(vendedor_id=vendedor_id).first()
    
    if request.method == 'POST':
        ok, err = VendedorService.actualizar(vendedor_id, current_user.id, request.form)
        if ok:
            flash('Vendedor actualizado.', 'success')
            return redirect(url_for('vip.detalle', vendedor_id=vendedor_id))
        else:
            flash(err, 'danger')
    
    return render_template('vip/editar_vendedor.html',
                           vendedor=vendedor,
                           config=config)


@vip_bp.route('/vendedores/<int:vendedor_id>/desactivar', methods=['POST'])
@login_required
def desactivar(vendedor_id):
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    ok, err = VendedorService.desactivar(vendedor_id, current_user.id)
    if ok:
        flash('Vendedor desactivado.', 'success')
    else:
        flash(err, 'danger')
    return redirect(url_for('vip.lista'))


@vip_bp.route('/vendedores/<int:vendedor_id>/reactivar', methods=['POST'])
@login_required
def reactivar(vendedor_id):
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    ok, err = VendedorService.reactivar(vendedor_id, current_user.id)
    if ok:
        flash('Vendedor reactivado.', 'success')
    else:
        flash(err, 'danger')
    return redirect(url_for('vip.lista'))


@vip_bp.route('/vendedores/<int:vendedor_id>/eliminar', methods=['POST'])
@login_required
def eliminar(vendedor_id):
    if not _check_acceso():
        return redirect(url_for('user.dashboard'))
    
    ok, err = VendedorService.eliminar(vendedor_id, current_user.id)
    if ok:
        flash('Vendedor eliminado.', 'success')
    else:
        flash(err, 'danger')
    return redirect(url_for('vip.lista'))
