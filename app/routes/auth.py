# app/routes/auth.py
from werkzeug.utils import secure_filename
import secrets
from flask import Blueprint, session, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models.usuario import Usuario
from ..models.config import ConfigTasa
from ..services.tasas import TasasService
from ..utils.validators import validar_email, validar_password


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.es_admin:
            return redirect(url_for('admin.dashboard'))
        if current_user.es_vendedor:
            return redirect(url_for('vendedor.ventas'))
        return redirect(url_for('user.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email y contraseña son obligatorios', 'danger')
            return render_template('auth/login.html')

        user = Usuario.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Credenciales inválidas', 'danger')
            return render_template('auth/login.html')

        if not user.activo:
            flash('Usuario inactivo. Contacta al administrador.', 'danger')
            return render_template('auth/login.html')

        # ✅ Bloqueo: vendedores cuyo padre no tiene suscripcion vigente
        if getattr(user, 'es_vendedor', False) and user.padre:
            if not user.padre.suscripcion_vigente:
                flash('Tu cuenta esta desactivada. El negocio no tiene suscripcion activa.', 'danger')
                return render_template('auth/login.html')

                        # ✅ Detectar si ya habia una sesion activa
        sesion_previa_activa = bool(user.session_token)

                # ✅ Detectar si ya habia una sesion activa
        sesion_previa_activa = bool(user.session_token)

        # ✅ Generar un token único para esta sesión y guardarlo en la BD
        # Esto invalida cualquier sesión anterior del mismo usuario
        nuevo_token = secrets.token_urlsafe(32)
        user.session_token = nuevo_token
        db.session.commit()
        
        # Guardar el token en la sesión de Flask
        session['session_token'] = nuevo_token
        
        # Iniciar sesión
        login_user(user, remember=False)
        
        # Si habia una sesion previa, mostramos un mensaje de advertencia
        if sesion_previa_activa:
            flash('Se ha cerrado la sesión anterior que estaba activa en otro dispositivo.', 'warning')
        
        # Si habia una sesion previa, mostramos un mensaje de advertencia
        if sesion_previa_activa:
            flash('Se ha cerrado la sesión anterior que estaba activa en otro dispositivo.', 'warning')

        if getattr(user, 'es_scanner', False):
            return redirect(url_for('scanner.pantalla'))

        if not user.es_vendedor:
            TasasService.obtener_tasas(user.id)

        flash(f'¡Bienvenido, {user.nombre}!', 'success')
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('auth.index'))

    return render_template('auth/login.html')



@auth_bp.route('/limpiar-sesion-robada')
def limpiar_sesion_robada():
    from flask import session
    session.pop('sesion_robada', None)
    return 'OK'


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        telefono = request.form.get('telefono', '').strip()

        if not nombre or not email or not password:
            flash('Todos los campos obligatorios deben estar completos', 'danger')
            return render_template('auth/register.html')

        ok, msg = validar_email(email)
        if not ok:
            flash(f'Email inválido: {msg}', 'danger')
            return render_template('auth/register.html')

        ok, msg = validar_password(password)
        if not ok:
            flash(msg, 'danger')
            return render_template('auth/register.html')

        if Usuario.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'danger')
            return render_template('auth/register.html')

        try:
            user = Usuario(nombre=nombre, email=email, telefono=telefono)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # Inicializar tasas
            tasa_actual = TasasService.obtener_tasa_bcv()
            config = ConfigTasa(
                usuario_id=user.id,
                tasa_oficial=tasa_actual,
                tasa_manual1=tasa_actual + 2,
                tasa_manual2=tasa_actual + 4,
            )
            db.session.add(config)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Detectar duplicado a nivel de BD (por si acaso)
            if 'UNIQUE constraint failed' in str(e).lower() and 'email' in str(e).lower():
                flash('El email ya está registrado', 'danger')
            else:
                flash(f'Error al registrar: {e}', 'danger')
            return render_template('auth/register.html')

        flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    # Limpiar el token de la sesión y de la BD
    current_user.session_token = None
    db.session.commit()
    session.pop('session_token', None)
    
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))

# ============================================================
# FOTO DE PERFIL
# ============================================================
import os
import uuid
from flask import current_app

ALLOWED_PERFIL_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_PERFIL_SIZE = 2 * 1024 * 1024  # 2 MB


def _carpeta_perfiles():
    """Devuelve la carpeta donde se guardan las fotos de perfil."""
    base = current_app.config.get('UPLOAD_FOLDER')
    if not base:
        base = os.path.join(current_app.root_path, 'static', 'uploads')
    carpeta = os.path.join(base, 'perfiles')
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _extension_permitida(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_PERFIL_EXT


@auth_bp.route('/perfil/foto', methods=['POST'])
@login_required
def subir_foto_perfil():
    """Sube o reemplaza la foto de perfil del usuario actual."""
    from flask import jsonify

    file = request.files.get('foto')
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No se selecciono archivo'}), 400

    if not _extension_permitida(file.filename):
        return jsonify({'success': False, 'error': 'Formato no permitido. Usa JPG, PNG, GIF o WEBP'}), 400

    # Verificar tamaño (leer el archivo en memoria)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_PERFIL_SIZE:
        return jsonify({'success': False, 'error': f'La imagen pesa {size/1024/1024:.1f}MB. Maximo 2MB'}), 400

    # Nombre unico
    ext = file.filename.rsplit('.', 1)[1].lower()
    nombre = f'user_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
    carpeta = _carpeta_perfiles()
    ruta_completa = os.path.join(carpeta, nombre)

    # Borrar la foto anterior si existe
    if current_user.foto_perfil:
        anterior = os.path.join(carpeta, current_user.foto_perfil)
        if os.path.exists(anterior):
            try:
                os.remove(anterior)
            except Exception:
                pass

    # Guardar nueva
    file.save(ruta_completa)

    # Actualizar BD
    current_user.foto_perfil = nombre
    db.session.commit()

    return jsonify({
        'success': True,
        'foto': nombre,
        'url': url_for('static', filename=f'uploads/perfiles/{nombre}'),
    })


@auth_bp.route('/perfil/foto/eliminar', methods=['POST'])
@login_required
def eliminar_foto_perfil():
    """Elimina la foto de perfil del usuario actual."""
    from flask import jsonify

    if current_user.foto_perfil:
        carpeta = _carpeta_perfiles()
        ruta = os.path.join(carpeta, current_user.foto_perfil)
        if os.path.exists(ruta):
            try:
                os.remove(ruta)
            except Exception:
                pass
        current_user.foto_perfil = None
        db.session.commit()

    return jsonify({'success': True})


@auth_bp.route('/perfil/foto/actual', methods=['GET'])
@login_required
def foto_actual():
    """Devuelve la URL de la foto actual."""
    from flask import jsonify
    if current_user.foto_perfil:
        return jsonify({
            'success': True,
            'foto': current_user.foto_perfil,
            'url': url_for('static', filename=f'uploads/perfiles/{current_user.foto_perfil}'),
        })
    return jsonify({'success': True, 'foto': None, 'url': None})
