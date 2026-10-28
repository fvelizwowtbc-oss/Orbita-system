# app/models/config.py
from datetime import datetime
from ..extensions import db


class ConfigEmpresa(db.Model):
    __tablename__ = 'config_empresa'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           unique=True, nullable=False)
    nombre = db.Column(db.String(300), default='Mi Empresa')
    rif = db.Column(db.String(50), default='J-00000000-0')
    direccion = db.Column(db.String(500), default='Venezuela')
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(200))
    logo = db.Column(db.Text)
    mensaje_factura = db.Column(db.String(500), default='¡Gracias por su compra!')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ConfigEmpresa {self.nombre}>'


class ConfigTasa(db.Model):
    __tablename__ = 'config_tasa'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    tasa_oficial = db.Column(db.Numeric(10, 2), default=36)
    tasa_manual1 = db.Column(db.Numeric(10, 2), default=38)
    tasa_manual2 = db.Column(db.Numeric(10, 2), default=40)
    tasa_activa = db.Column(db.String(20), default='oficial')
    fuente_oficial = db.Column(db.String(100), default='BCV')
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    actualizado_por = db.Column(db.Integer)

    tasa_manual_valor = db.Column(db.Numeric(10, 2), default=0)
    modo_tasa = db.Column(db.String(20), default='auto')

    def __repr__(self):
        return f'<ConfigTasa user={self.usuario_id}>'