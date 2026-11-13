# app/models/producto.py
from datetime import datetime
from ..extensions import db


class Producto(db.Model):
    __tablename__ = 'productos'
    __table_args__ = (
        db.UniqueConstraint('usuario_id', 'codigo', name='uq_usuario_codigo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    nombre = db.Column(db.String(300), nullable=False)
    modelo = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    referencia = db.Column(db.String(100))
    categoria = db.Column(db.String(100))
    subcategoria = db.Column(db.String(100))
    codigo = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(50))
    descripcion = db.Column(db.Text)
    fecha_expiracion = db.Column(db.Date)
    ubicacion = db.Column(db.String(200))
    stock_actual = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    precio_costo_usd = db.Column(db.Numeric(10, 2), default=0)
    precio_venta_usd = db.Column(db.Numeric(10, 2), nullable=False)
    margen_ganancia = db.Column(db.Numeric(10, 2), default=0)
    impuesto = db.Column(db.Numeric(10, 2), default=16)
    proveedor_nombre = db.Column(db.String(300))
    proveedor_contacto = db.Column(db.String(100))
    proveedor_notas = db.Column(db.Text)
    pagado_contado = db.Column(db.Boolean, default=True)
    dias_credito = db.Column(db.Integer, default=0)
    observaciones = db.Column(db.Text)
    imagen_principal = db.Column(db.String(300))
    medida_unidad = db.Column(db.String(50), default='Unidad')
    medida_cantidad = db.Column(db.Numeric(10, 2), default=1)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def stock_bajo(self):
        return 0 <= self.stock_actual <= self.stock_minimo

    @property
    def valor_inventario_usd(self):
        # Si tiene variantes, calculamos el valor sumando (precio_variante * stock_variante)
        variantes = self.variantes.all()
        if variantes:
            total = 0
            for v in variantes:
                # Si la variante no tiene precio propio, hereda el del padre (o usa 0)
                precio = float(v.precio_venta_usd) if v.precio_venta_usd else float(self.precio_venta_usd or 0)
                total += precio * v.stock_actual
            return total
        # Si no tiene variantes, usa el cálculo normal
        return float(self.precio_venta_usd or 0) * self.stock_actual

    @property
    def imagen_url(self):
        if not self.imagen_principal:
            return None
        # Si ya es URL de internet, devolverla tal cual (limpia)
        if self.imagen_principal.startswith('http://') or self.imagen_principal.startswith('https://'):
            return self.imagen_principal
        # Si es un archivo local, agregar la ruta
        return f'/uploads/{self.usuario_id}/{self.imagen_principal}'
        return None

    @property
    def imagen_thumb_url(self):
        """Devuelve la URL del thumbnail si existe."""
        if not self.imagen_principal:
            return None
        # Si el archivo empieza con 'user_', el thumb es 'thumb_' + archivo
        if self.imagen_principal.startswith('user_'):
            thumb = 'thumb_' + self.imagen_principal
            return f'/uploads/{self.usuario_id}/{thumb}'
        return self.imagen_url

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'codigo': self.codigo,
            'marca': self.marca,
            'categoria': self.categoria,
            'stock_actual': self.stock_actual,
            'stock_minimo': self.stock_minimo,
            'precio_venta_usd': float(self.precio_venta_usd or 0),
            'imagen_url': self.imagen_url,
        }

    # Relacion con variantes (todas las opciones de este producto)
    variantes = db.relationship(
        'ProductoVariante',
        backref=db.backref('producto', lazy='select'),
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='ProductoVariante.producto_id',
    )

    def __repr__(self):
        return f'<Producto {self.codigo} - {self.nombre}>'


class ProductoVariante(db.Model):
    """Variante de un producto (color, talla, modelo, presentacion, etc.)"""
    __tablename__ = 'producto_variantes'
    __table_args__ = (
        db.UniqueConstraint('producto_id', 'nombre', name='uq_producto_variante_nombre'),
    )

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    codigo = db.Column(db.String(100))
    stock_actual = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=0)
    precio_costo_usd = db.Column(db.Numeric(10, 2), default=0)
    precio_venta_usd = db.Column(db.Numeric(10, 2), default=0)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def stock_bajo(self):
        return 0 <= self.stock_actual <= self.stock_minimo

    @property
    def precio_venta_efectivo(self):
        if self.precio_venta_usd and float(self.precio_venta_usd) > 0:
            return float(self.precio_venta_usd)
        return float(self.producto.precio_venta_usd or 0) if self.producto else 0

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'codigo': self.codigo or '',
            'stock_actual': self.stock_actual,
            'precio_venta_usd': self.precio_venta_efectivo,
        }

    def __repr__(self):
        return f'<ProductoVariante {self.nombre} - {self.producto_id}>'
