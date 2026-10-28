# app/models/factura.py
from datetime import datetime
from ..extensions import db


class FacturaCobrar(db.Model):
    __tablename__ = 'facturas_cobrar'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id', ondelete='CASCADE'),
                         nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id', ondelete='SET NULL'))
    cliente_nombre = db.Column(db.String(300), default='Consumidor Final')
    tipo_venta = db.Column(db.String(20), default='contado')
    total_usd = db.Column(db.Numeric(10, 2), nullable=False)
    total_ves = db.Column(db.Numeric(10, 2), nullable=False)
    saldo_usd = db.Column(db.Numeric(10, 2), default=0)
    saldo_ves = db.Column(db.Numeric(10, 2), default=0)
    estado = db.Column(db.String(20), default='pagado', index=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    nro_factura = db.Column(db.String(100))

    # ============ CASHEA ============
    cashea_porcentaje_inicial = db.Column(db.Integer, nullable=True)
    cashea_num_cuotas = db.Column(db.Integer, nullable=True)
    cashea_nombre_comprador = db.Column(db.String(300), nullable=True)
    cashea_cedula = db.Column(db.String(50), nullable=True)
    cashea_telefono = db.Column(db.String(50), nullable=True)
    cashea_monto_inicial = db.Column(db.Numeric(10, 2), nullable=True)
    cashea_monto_cuota = db.Column(db.Numeric(10, 2), nullable=True)
    cashea_tipo = db.Column(db.String(20), nullable=True)  # 'cotidiana' | 'normal'

    venta = db.relationship('Venta', backref='factura_cobrar')
    cuotas_cashea = db.relationship('CuotaCashea', backref='factura', lazy='dynamic',
                                     cascade='all, delete-orphan',
                                     foreign_keys='CuotaCashea.factura_id')

    abonos = db.relationship('Abono', backref='factura', lazy='dynamic',
                             cascade='all, delete-orphan')

    @property
    def total_cuotas_pagadas(self):
        return self.cuotas_cashea.filter_by(estado='pagada').count()

    @property
    def total_cuotas(self):
        return self.cuotas_cashea.count()

    @property
    def es_cashea(self):
        return self.cashea_num_cuotas is not None and self.cashea_num_cuotas > 0

    @property
    def total_abonado_usd(self):
        return sum(float(a.monto_usd) for a in self.abonos)

    @property
    def porcentaje_pagado(self):
        if not self.total_usd or float(self.total_usd) == 0:
            return 100
        pagado = float(self.total_usd) - float(self.saldo_usd or 0)
        return round((pagado / float(self.total_usd)) * 100, 1)

    def __repr__(self):
        return f'<Factura {self.nro_factura} - {self.estado}>'


class Abono(db.Model):
    __tablename__ = 'abonos'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas_cobrar.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_ves = db.Column(db.Numeric(10, 2), nullable=False)
    tasa_usada = db.Column(db.Numeric(10, 2))
    metodo_pago = db.Column(db.String(50), default='efectivo')
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Abono {self.id} - ${self.monto_usd}>'