# app/models/gasto.py
from datetime import datetime
from ..extensions import db


class Gasto(db.Model):
    __tablename__ = 'gastos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)

    # Datos del gasto
    categoria = db.Column(db.String(50), nullable=False, index=True)
    descripcion = db.Column(db.String(500), nullable=False)
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_ves = db.Column(db.Numeric(10, 2), default=0)
    tasa_bcv = db.Column(db.Numeric(10, 2), default=0)

    # Info
    fecha = db.Column(db.Date, default=datetime.utcnow, index=True)
    metodo_pago = db.Column(db.String(50), default='efectivo')
    proveedor_nombre = db.Column(db.String(300))
    notas = db.Column(db.Text)
    comprobante = db.Column(db.String(300))  # nombre del archivo

    # Relacion con factura proveedor (si aplica)
    factura_proveedor_id = db.Column(db.Integer, db.ForeignKey('facturas_proveedores.id', ondelete='SET NULL'),
                                     nullable=True)

    # Meta
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def comprobante_url(self):
        if self.comprobante:
            return f'/uploads/gastos/{self.usuario_id}/{self.comprobante}'
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'categoria': self.categoria,
            'descripcion': self.descripcion,
            'monto_usd': float(self.monto_usd or 0),
            'fecha': self.fecha.strftime('%d/%m/%Y') if self.fecha else '',
            'metodo_pago': self.metodo_pago,
        }

    def __repr__(self):
        return f'<Gasto {self.categoria} ${self.monto_usd}>'


# ============================================================
# CATEGORIAS PREDEFINIDAS
# ============================================================
CATEGORIAS_GASTOS = [
    ('alquiler', 'Alquiler', 'fa-home'),
    ('servicios', 'Servicios (Luz, Agua, Internet)', 'fa-bolt'),
    ('salarios', 'Salarios', 'fa-users'),
    ('impuestos', 'Impuestos', 'fa-file-invoice'),
    ('mercancia', 'Mercancia', 'fa-boxes'),
    ('transporte', 'Transporte', 'fa-truck'),
    ('comida', 'Comida', 'fa-utensils'),
    ('mantenimiento', 'Mantenimiento', 'fa-tools'),
    ('publicidad', 'Publicidad', 'fa-bullhorn'),
    ('otros', 'Otros', 'fa-ellipsis-h'),
]


METODOS_PAGO = [
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('pago_movil', 'Pago Movil'),
    ('punto', 'Punto de Venta'),
    ('zelle', 'Zelle'),
    ('binance', 'Binance'),
    ('otro', 'Otro'),
]
