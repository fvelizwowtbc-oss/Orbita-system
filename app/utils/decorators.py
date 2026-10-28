# app/utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def vendedor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_vendedor:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.es_vendedor:
            return redirect(url_for('vendedor.ventas'))
        if current_user.es_admin:
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


def check_limite_productos(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from ..services.suscripciones import SuscripcionesService
        from ..models.producto import Producto
        limites = SuscripcionesService.verificar_limites(current_user.id)
        total = Producto.query.filter_by(usuario_id=current_user.id).count()
        if total >= limites['limite_productos']:
            flash(f'Límite de {limites["limite_productos"]} productos alcanzado. '
                  'Adquiere el plan VIP para ilimitado.', 'warning')
            return redirect(url_for('user.inventario'))
        return f(*args, **kwargs)
    return decorated