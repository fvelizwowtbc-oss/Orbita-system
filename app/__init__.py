# app/__init__.py
import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from config import config
from .extensions import db, login_manager, csrf
from flask_mail import Mail


def create_app(config_name='default'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])

    # Asegurar carpetas
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    _log_dir = app.config.get('LOG_DIR', 'logs')
    _fac_dir = app.config.get('FACTURAS_DIR', 'facturas')
    os.makedirs(_log_dir, exist_ok=True)
    os.makedirs(_fac_dir, exist_ok=True)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail = Mail(app)

    # Configurar logging
    _setup_logging(app)

    # Registrar blueprints
    _register_blueprints(app)

    # Handlers de error
    _register_error_handlers(app)

    # Context processors
    _register_context_processors(app)

    # CLI commands
    _register_cli(app)

    # Crear tablas si no existen
    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()
        _seed_data()


    # ============================================================
    # SERVIR IMAGENES DE PRODUCTOS (compatible con .exe)
    # ============================================================
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Sirve las imagenes desde UPLOAD_FOLDER.

        Funciona tanto en modo script como en modo .exe.
        En .exe, UPLOAD_FOLDER = %APPDATA%/SistemaGestion/uploads/
        """
        from flask import send_from_directory
        upload_folder = app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            return 'No configurado', 404
        return send_from_directory(upload_folder, filename)

    # ============================================================
    # HEADERS DE SEGURIDAD
    # ============================================================
    @app.after_request
    def add_security_headers(response):
        # Clickjacking: no permitir iframes de otros dominios
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        # XSS / MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions policy (deshabilita features que no usas)
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(self), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )

        # CSP: solo permitir scripts/estilos de tu dominio + CDNs usados
        # NOTA: CSP puede romper funcionalidad. Si algo se rompe,
        # comenta esta linea y reporta el error.
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob: https://ik.imagekit.io; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp

        return response

    app.mail = mail
    return app

def _setup_logging(app):
    if app.debug:
        return
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "sistema_gestion.log")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=10240, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    ))
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)
    file_handler.setLevel(level)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(level)


def _register_blueprints(app):
    from .routes.auth import auth_bp
    from .routes.user import user_bp
    from .routes.admin import admin_bp
    from .routes.vendedor import vendedor_bp
    from .routes.vip import vip_bp
    from .routes.scanner import scanner_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendedor_bp, url_prefix='/vendedor')
    app.register_blueprint(vip_bp, url_prefix='/vip')
    app.register_blueprint(scanner_bp, url_prefix='/scanner')
    app.register_blueprint(api_bp, url_prefix='/api')




# ============================================================
# SERVIR IMAGENES DE PRODUCTOS (compatible con .exe)
# ============================================================
def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/error.html', error='Página no encontrada', codigo=404), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/error.html', error='Acceso denegado', codigo=403), 403

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        app.logger.error(f'Error 500: {e}')
        return render_template('errors/error.html', error='Error interno del servidor', codigo=500), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        db.session.rollback()
        app.logger.exception('Excepción no controlada')
        return render_template('errors/error.html', error=str(e), codigo=500), 500


def _register_context_processors(app):
    from .utils_red import obtener_ip_local_servidor

    @app.context_processor
    def inject_ip_local():
        """Expone la IP local del servidor a todos los templates."""
        try:
            puerto = int(os.environ.get('PORT', 5000))
        except Exception:
            puerto = 5000
        return {
            'ip_local': obtener_ip_local_servidor(),
            'puerto_local': puerto,
            'modo_escritorio': os.environ.get('MODO_ESCRITORIO') == '1',
        }


    from .services.tasas import TasasService
    from flask_login import current_user

    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'Orbita System',
            'current_user': current_user,
            'tasas': TasasService.obtener_tasas(current_user.id) if current_user.is_authenticated else None,
        }


def _register_cli(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Inicializa la base de datos."""
        db.create_all()
        _seed_data()
        print('âœ… Base de datos inicializada.')


def _seed_data():
    """Crea el admin y demo por defecto si no existen.

    Verifica CADA UNO por separado para que se puedan recuperar
    usuarios individuales si fueron borrados.
    """
    from .models.usuario import Usuario
    from .models.config import ConfigTasa
    from .services.tasas import TasasService

    creados = 0

    # ---- Admin ----
    if not Usuario.query.filter_by(email='admin@sistema.com').first():
        admin = Usuario(
            nombre='Administrador',
            email='admin@sistema.com',
            role='admin',
            activo=True,
        )
        admin.set_password('Admin123!')
        db.session.add(admin)
        db.session.flush()
        creados += 1

    # ---- Demo (VIP) ----
    if not Usuario.query.filter_by(email='demo@demo.com').first():
        demo = Usuario(
            nombre='Usuario Demo',
            email='demo@demo.com',
            telefono='04141234567',
            activo=True,
        )
        demo.set_password('User123!')
        db.session.add(demo)
        db.session.flush()

        # Crear config de tasas para el demo
        try:
            tasa_actual = TasasService.obtener_tasa_bcv()
            config = ConfigTasa(
                usuario_id=demo.id,
                tasa_oficial=tasa_actual,
                tasa_manual1=tasa_actual + 2,
                tasa_manual2=tasa_actual + 4,
            )
            db.session.add(config)
        except Exception:
            pass

        creados += 1

    if creados > 0:
        db.session.commit()
