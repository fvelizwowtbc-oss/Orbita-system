# app/models/suscripcion.py
from datetime import datetime
from ..extensions import db


class Suscripcion(db.Model):
    __tablename__ = 'suscripciones'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    plan = db.Column(db.String(50), nullable=False)
    dias = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    monto = db.Column(db.Numeric(10, 2), default=0)
    estado = db.Column(db.String(20), default='activa', index=True)
    metodo_pago = db.Column(db.String(50))
    transaccion_id = db.Column(db.String(200))
    notas = db.Column(db.Text)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    cancelado_en = db.Column(db.Date)
    cancelado_por = db.Column(db.Integer)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    creador = db.relationship('Usuario', foreign_keys=[creado_por])

    def __repr__(self):
        return f'<Suscripcion {self.plan} - {self.estado}>'