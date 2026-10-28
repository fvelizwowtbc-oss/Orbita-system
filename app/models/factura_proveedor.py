# app/models/factura_proveedor.py
from datetime import datetime, date
from ..extensions import db


class FacturaProveedor(db.Model):
    __tablename__ = 'facturas_proveedores'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)

    # Datos del proveedor
    proveedor_nombre = db.Column(db.String(300), nullable=False, index=True)
    proveedor_rif = db.Column(db.String(50))
    proveedor_telefono = db.Column(db.String(50))

    # Datos de la factura
    nro_factura = db.Column(db.String(100), index=True)
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_ves = db.Column(db.Numeric(10, 2), default=0)
    tasa_bcv = db.Column(db.Numeric(10, 2), default=0)

    # Fechas
    fecha_emision = db.Column(db.Date, default=date.today, index=True)
    fecha_vencimiento = db.Column(db.Date, nullable=True, index=True)

    # Tipo y estado
    tipo = db.Column(db.String(20), default='contado', index=True)  # contado | credito
    estado = db.Column(db.String(20), default='pendiente', index=True)  # pendiente | pagada | cancelada

    # Pago
    fecha_pago = db.Column(db.Date, nullable=True)
    monto_pagado_usd = db.Column(db.Numeric(10, 2), default=0)
    metodo_pago = db.Column(db.String(50))

    # Extras
    notas = db.Column(db.Text)
    comprobante = db.Column(db.String(300))

    # Meta
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacion con gasto (si se pago)
    gasto = db.relationship('Gasto', backref='factura_proveedor', uselist=False,
                            foreign_keys='Gasto.factura_proveedor_id')

    @property
    def comprobante_url(self):
        if self.comprobante:
            return f'/uploads/proveedores/{self.usuario_id}/{self.comprobante}'
        return None

    @property
    def dias_para_vencer(self):
        """Dias que faltan para el vencimiento. Negativo si ya vencio."""
        if not self.fecha_vencimiento:
            return None
        return (self.fecha_vencimiento - date.today()).days

    @property
    def vencida(self):
        """True si esta pendiente y ya paso la fecha de vencimiento."""
        if self.estado != 'pendiente' or not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento < date.today()

    @property
    def por_vencer(self):
        """True si esta pendiente y vence en los proximos 3 dias."""
        if self.estado != 'pendiente' or not self.fecha_vencimiento:
            return False
        dias = self.dias_para_vencer
        return 0 <= dias <= 3

    @property
    def estado_visual(self):
        """Devuelve el estado para mostrar con color."""
        if self.estado == 'pagada':
            return 'pagada'
        if self.estado == 'cancelada':
            return 'cancelada'
        # Pendiente
        dias = self.dias_para_vencer
        if dias is None:
            return 'pendiente'
        if dias < 0:
            return 'vencida'
        if dias <= 3:
            return 'por_vencer'
        return 'pendiente'

    def to_dict(self):
        return {
            'id': self.id,
            'proveedor': self.proveedor_nombre,
            'nro_factura': self.nro_factura,
            'monto_usd': float(self.monto_usd or 0),
            'fecha_emision': self.fecha_emision.strftime('%d/%m/%Y') if self.fecha_emision else '',
            'fecha_vencimiento': self.fecha_vencimiento.strftime('%d/%m/%Y') if self.fecha_vencimiento else '',
            'tipo': self.tipo,
            'estado': self.estado,
            'estado_visual': self.estado_visual,
            'dias_para_vencer': self.dias_para_vencer,
        }

    def __repr__(self):
        return f'<FacturaProveedor {self.proveedor_nombre} ${self.monto_usd}>'
