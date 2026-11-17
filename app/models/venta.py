# app/models/venta.py
from datetime import datetime
from ..extensions import db


class Venta(db.Model):
    __tablename__ = 'ventas'

    # ============ CAMPOS ============
    id = db.Column(db.Integer, primary_key=True)

    # 🔑 FK al dueño del negocio (usuario principal)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # 🔑 FK al producto vendido
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )

    variante_id = db.Column(
        db.Integer,
        db.ForeignKey('producto_variantes.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    # 🔑 FK al vendedor (puede ser NULL si la venta la hizo el dueño)
    # ⚠️ Esta es la SEGUNDA FK a usuarios → causa la ambigüedad
    vendedor_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    # 🔑 FK al cliente (opcional)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('clientes.id', ondelete='SET NULL'),
        nullable=True,
    )

    # ============ DATOS DE LA VENTA ============
    cantidad = db.Column(db.Numeric(10, 2), nullable=False) # ✅ Soporta decimales
    precio_usd = db.Column(db.Numeric(10, 2), nullable=False)

    # Las 3 tasas al momento de la venta
    tasa_oficial = db.Column(db.Numeric(10, 2), default=36)
    tasa_manual1 = db.Column(db.Numeric(10, 2), default=38)
    tasa_manual2 = db.Column(db.Numeric(10, 2), default=40)
    tasa_usada = db.Column(db.String(20), default='oficial')

    # Totales calculados en cada tasa
    total_usd = db.Column(db.Numeric(10, 2), nullable=False)
    total_oficial = db.Column(db.Numeric(10, 2), nullable=False)
    total_manual1 = db.Column(db.Numeric(10, 2), nullable=False)
    total_manual2 = db.Column(db.Numeric(10, 2), nullable=False)

    # ============ METADATOS ============
    metodo_pago = db.Column(db.String(50), default='efectivo')
    observaciones = db.Column(db.Text)
    nro_factura = db.Column(db.String(100), index=True)
    tipo_venta = db.Column(db.String(20), default='contado')  # contado | credito
    cliente_nombre = db.Column(db.String(300), default='Consumidor Final')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # ============ CANCELACION ============
    estado = db.Column(db.String(20), default='activa', index=True)
    # 'activa' | 'cancelada'
    cancelado_en = db.Column(db.DateTime, nullable=True)
    cancelado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    motivo_cancelacion = db.Column(db.String(500), nullable=True)

    # ============ CASHEA ============
    cashea_porcentaje_inicial = db.Column(db.Integer, nullable=True)     # 0, 10, 20, ..., 60
    cashea_num_cuotas = db.Column(db.Integer, nullable=True)             # 3, 6, 9, 12
    cashea_nombre_comprador = db.Column(db.String(300), nullable=True)
    cashea_cedula = db.Column(db.String(50), nullable=True)
    cashea_telefono = db.Column(db.String(50), nullable=True)
    cashea_monto_inicial = db.Column(db.Numeric(10, 2), nullable=True)
    cashea_monto_cuota = db.Column(db.Numeric(10, 2), nullable=True)
    cashea_tipo = db.Column(db.String(20), nullable=True)  # 'cotidiana' | 'normal'

    # ============ RELACIONES ============
    #
    # ⚠️ IMPORTANTE sobre SQLAlchemy y FKs ambiguas:
    #
    # Hay DOS FKs de 'ventas' hacia 'usuarios':
    #   1. usuario_id  → dueño del negocio
    #   2. vendedor_id → vendedor que hizo la venta
    #
    # SQLAlchemy no sabe cuál usar si defines `Usuario.ventas` sin especificar.
    # Por eso aquí NO definimos las relaciones hacia Usuario.
    # Se definen en Usuario con `foreign_keys=` explícito.
    #
    # Relaciones que SÍ van aquí (porque no hay ambigüedad):
    #

    producto = db.relationship(
        'Producto',
        backref=db.backref('ventas', lazy='dynamic'),
        foreign_keys=[producto_id],
    )

    variante = db.relationship(
        'ProductoVariante',
        foreign_keys=[variante_id],
    )

    cliente = db.relationship(
        'Cliente',
        backref=db.backref('ventas', lazy='dynamic'),
        foreign_keys=[cliente_id],
    )

    # ❌ NO incluir:
    # usuario = db.relationship('Usuario', ...)
    # vendedor = db.relationship('Usuario', ...)
    #
    # Porque ya se definen en Usuario.ventas y Usuario.ventas_como_vendedor
    # con foreign_keys explícito. Tener ambos lados causa conflicto.

    # ============ PROPIEDADES ============
    @property
    def total_ves(self):
        """Total en VES según la tasa usada."""
        tasa = {
            'oficial': float(self.tasa_oficial or 0),
            'manual1': float(self.tasa_manual1 or 0),
            'manual2': float(self.tasa_manual2 or 0),
        }.get(self.tasa_usada, float(self.tasa_oficial or 0))
        return round(float(self.total_usd or 0) * tasa, 2)

    @property
    def es_credito(self):
        return self.tipo_venta == 'credito'

    @property
    def es_contado(self):
        return self.tipo_venta == 'contado'

    def to_dict(self):
        return {
            'id': self.id,
            'producto': self.producto.nombre if self.producto else '',
            'cantidad': self.cantidad,
            'precio_usd': float(self.precio_usd or 0),
            'total_usd': float(self.total_usd or 0),
            'total_ves': self.total_ves,
            'nro_factura': self.nro_factura,
            'tipo_venta': self.tipo_venta,
            'cliente': self.cliente_nombre,
            'creado_en': self.creado_en.strftime('%d/%m/%Y %H:%M') if self.creado_en else '',
        }

    def __repr__(self):
        return f'<Venta {self.id} - {self.nro_factura or "sin-factura"}>'