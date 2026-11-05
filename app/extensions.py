# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    from .models.usuario import Usuario
    from flask import session
    
    # Buscar el usuario por ID
    user = db.session.get(Usuario, int(user_id))
    
    # Si el usuario tiene un token de sesión, verificar que coincida con el de la sesión actual
    if user and user.session_token:
        token_en_sesion = session.get('session_token')
        if token_en_sesion != user.session_token:
            # El token no coincide: alguien más inició sesión desde otro lugar
            # Limpiamos la sesión actual pero guardamos una bandera para mostrar la alerta
            session['sesion_robada'] = True
            return None  # Forzar logout
    
    return user