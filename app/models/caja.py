# app/models/caja.py
from datetime import datetime
from ..extensions import db

class CajaTurno(db.Model):
    __tablename__ = 'caja_turnos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    
    saldo_inicial_usd = db.Column(db.Numeric(10, 2), default=0)
    saldo_inicial_bs = db.Column(db.Numeric(10, 2), default=0)
    
    estado = db.Column(db.String(20), default='abierta')
    total_ventas_efectivo_usd = db.Column(db.Numeric(10, 2), default=0)
    total_ventas_efectivo_bs = db.Column(db.Numeric(10, 2), default=0)
    saldo_real_usd = db.Column(db.Numeric(10, 2), nullable=True)
    saldo_real_bs = db.Column(db.Numeric(10, 2), nullable=True)
    diferencia_usd = db.Column(db.Numeric(10, 2), nullable=True)
    diferencia_bs = db.Column(db.Numeric(10, 2), nullable=True)
    tasa_cierre = db.Column(db.Numeric(10, 2), nullable=True) # ✅ Tasa usada al cerrar # 'abierta' | 'cerrada'
    
    abierta_en = db.Column(db.DateTime, default=datetime.utcnow)
    cerrada_en = db.Column(db.DateTime, nullable=True)

    usuario = db.relationship('Usuario', backref='turnos_caja')
