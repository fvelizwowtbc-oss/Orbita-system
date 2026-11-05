# app/routes/scanner.py
from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models.producto import Producto
from ..services.tasas import TasasService

scanner_bp = Blueprint('scanner', __name__)

@scanner_bp.before_request
@login_required
def before_request():
    if not current_user.es_scanner:
        return redirect(url_for('auth.index'))

@scanner_bp.route('/')
def pantalla():
    # Al iniciar sesión, el scanner va directo aquí
    return render_template('scanner/pantalla.html', tiempo_scanner=current_user.scanner_tiempo or 10)

@scanner_bp.route('/buscar', methods=['POST'])
def buscar():
    data = request.get_json() or {}
    codigo = data.get('codigo', '').strip()
    
    if not codigo:
        return jsonify({'success': False, 'error': 'Código vacío'})
        
    producto = Producto.query.filter(
        Producto.usuario_id == current_user.usuario_padre_id,
        Producto.activo.is_(True),
        db.or_(Producto.codigo.ilike(codigo), Producto.nombre.ilike(f'%{codigo}%'))
    ).first()
    
    if not producto:
        return jsonify({'success': False, 'error': 'Producto no encontrado'})
        
    tasas = TasasService.obtener_tasas(current_user.usuario_padre_id)
    tasa_actual = float(tasas['oficial'])
    
    return jsonify({
        'success': True,
        'nombre': producto.nombre,
        'codigo': producto.codigo,
        'precio_usd': float(producto.precio_venta_usd),
        'precio_bs': float(producto.precio_venta_usd) * tasa_actual,
        'tasa': tasa_actual
    })
