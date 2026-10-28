# app/models/cuota_cashea.py
from datetime import datetime, date
from ..extensions import db


class CuotaCashea(db.Model):
    """Cuota individual de una venta con metodo de pago Cashea."""
    __tablename__ = 'cuotas_cashea'

    id = db.Column(db.Integer, primary_key=True)

    # FK a la factura de cobrar
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas_cobrar.id', ondelete='CASCADE'),
                           nullable=False, index=True)

    # Datos de la cuota
    numero = db.Column(db.Integer, nullable=False)               # 1, 2, 3...
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_ves = db.Column(db.Numeric(10, 2), default=0)

    # Fechas
    fecha_vencimiento = db.Column(db.Date, nullable=False, index=True)
    fecha_pago = db.Column(db.Date, nullable=True)

    # Estado
    estado = db.Column(db.String(20), default='pendiente', index=True)  # pendiente | pagada

    # Meta
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def vencida(self):
        """True si esta pendiente y ya paso la fecha."""
        if self.estado != 'pendiente' or not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento < date.today()

    @property
    def dias_para_vencer(self):
        """Dias que faltan para el vencimiento. Negativo si ya vencio."""
        if not self.fecha_vencimiento:
            return None
        return (self.fecha_vencimiento - date.today()).days

    @property
    def por_vencer(self):
        """True si esta pendiente y vence en los proximos 3 dias."""
        if self.estado != 'pendiente' or not self.fecha_vencimiento:
            return False
        dias = self.dias_para_vencer
        return 0 <= dias <= 3

    @property
    def estado_visual(self):
        if self.estado == 'pagada':
            return 'pagada'
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
            'numero': self.numero,
            'monto_usd': float(self.monto_usd or 0),
            'fecha_vencimiento': self.fecha_vencimiento.strftime('%d/%m/%Y') if self.fecha_vencimiento else '',
            'fecha_pago': self.fecha_pago.strftime('%d/%m/%Y') if self.fecha_pago else '',
            'estado': self.estado,
            'estado_visual': self.estado_visual,
        }

    def __repr__(self):
        return f'<CuotaCashea #{self.numero} ${self.monto_usd} {self.estado}>'
