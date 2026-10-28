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
    return db.session.get(Usuario, int(user_id))