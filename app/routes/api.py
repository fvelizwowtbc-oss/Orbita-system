# app/routes/api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from ..services.tasas import TasasService


api_bp = Blueprint('api', __name__)


@api_bp.route('/tasa-bcv')
def tasa_bcv():
    try:
        return jsonify({'success': True, 'tasa': TasasService.obtener_tasa_bcv()})
    except Exception:
        return jsonify({'success': False, 'tasa': 50.0})


@api_bp.route('/tasa/actualizar', methods=['POST'])
@login_required
def actualizar_tasa():
    try:
        tasa = TasasService.obtener_tasa_bcv(force=True)
        if not current_user.es_vendedor:
            TasasService.actualizar_tasa_oficial(current_user.id, force=True)
        return jsonify({'success': True, 'tasa': tasa})
    except Exception:
        return jsonify({'success': False}), 500


@api_bp.route('/tasas/configurar', methods=['POST'])
@login_required
def configurar_tasas():
    data = request.get_json() or {}
    try:
        m1 = float(data.get('tasa_manual1', 0))
        m2 = float(data.get('tasa_manual2', 0))
        activa = data.get('tasa_activa', 'oficial')
        if m1 <= 0 or m2 <= 0:
            return jsonify({'success': False, 'error': 'Tasas inválidas'}), 400
        ok = TasasService.configurar_tasas(current_user.id, m1, m2, activa)
        return jsonify({'success': ok})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400


@api_bp.route('/subcategorias')
def subcategorias():
    cat = request.args.get('categoria', '')
    mapa = {
        'Carniceria': ['Res', 'Cerdo', 'Pollo', 'Pescado', 'Chorizo', 'Queso', 'Otros'],
        'Repuestos Moto': ['Motor', 'Transmisión', 'Frenos', 'Suspensión',
                           'Electricidad', 'Chasis', 'Accesorios',
                           'Llantas y Neumáticos', 'Carrocería', 'Escape',
                           'Combustible', 'Refrigeración', 'Lubricación',
                           'Faros y Luces', 'Asientos', 'Manillares', 'Otros'],
        'Electrónica': ['Teléfonos', 'Computadoras', 'Tablets', 'Audio',
                        'Video', 'Cámaras', 'Accesorios'],
        'Automotriz': ['Repuestos Auto', 'Accesorios Auto', 'Lubricantes',
                       'Llantas', 'Baterías'],
        'Herramientas': ['Eléctricas', 'Manuales', 'Medición', 'Jardinería'],
    }
    return jsonify({'success': True, 'subcategorias': mapa.get(cat, [])})

@api_bp.route('/marcas-por-categoria')
def marcas_por_categoria():
    from flask import request, jsonify
    from ..routes.user import _marcas_por_categoria
    categoria = request.args.get('categoria', '')
    return jsonify({
        'success': True,
        'marcas': _marcas_por_categoria(categoria),
    })


@api_bp.route('/unidades-medida')
def unidades_medida():
    from flask import jsonify
    from ..routes.user import _unidades_medida
    return jsonify({'success': True, 'unidades': _unidades_medida()})
