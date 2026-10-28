# app/models/cliente.py
from datetime import datetime
from ..extensions import db


class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    nombre = db.Column(db.String(300), nullable=False)
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(200))
    direccion = db.Column(db.String(500))
    documento = db.Column(db.String(50))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    facturas = db.relationship('FacturaCobrar', backref='cliente', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'telefono': self.telefono,
            'documento': self.documento,
            'email': self.email,
        }

    def __repr__(self):
        return f'<Cliente {self.nombre}>'