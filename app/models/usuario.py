# app/models/usuario.py
from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(500), nullable=False)
    telefono = db.Column(db.String(50))
    foto_perfil = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default='user')
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    es_vendedor = db.Column(db.Boolean, default=False)
    usuario_padre_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    
    # Permisos de vendedor
    puede_editar_inventario = db.Column(db.Boolean, default=False)
    puede_ver_clientes = db.Column(db.Boolean, default=False)
    puede_ver_facturas = db.Column(db.Boolean, default=False)
    puede_ver_reportes_completos = db.Column(db.Boolean, default=False)
    puede_cancelar_ventas = db.Column(db.Boolean, default=False)
    puede_ver_costos = db.Column(db.Boolean, default=False)
    
    limite_productos = db.Column(db.Integer, default=50)
    limite_ventas_mensuales = db.Column(db.Integer, default=20)
    tasa_activa = db.Column(db.String(20), default='oficial')
    suscripcion_activa = db.Column(db.Boolean, default=False)
    fecha_fin_suscripcion = db.Column(db.Date)

    # ✅ PIN de cancelacion (solo el VIP puede configurarlo)
    pin_cancelacion_hash = db.Column(db.String(500), nullable=True)

    # ✅ Relación auto-referencial con foreign_keys explícito
    vendedores = db.relationship(
        'Usuario',
        backref=db.backref('padre', remote_side=[id]),
        foreign_keys=[usuario_padre_id],
    )

    productos = db.relationship(
        'Producto', backref='usuario', lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Producto.usuario_id',
    )

    clientes = db.relationship(
        'Cliente', backref='usuario', lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Cliente.usuario_id',
    )

    # ✅ VENTAS: especificar foreign_keys para evitar ambigüedad
    ventas = db.relationship(
        'Venta',
        backref='usuario',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Venta.usuario_id',  # 👈 CLAVE
    )

    ventas_como_vendedor = db.relationship(
        'Venta',
        backref='vendedor',
        lazy='dynamic',
        foreign_keys='Venta.vendedor_id',  # 👈 CLAVE
    )

    suscripciones = db.relationship(
        'Suscripcion', backref='usuario', lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Suscripcion.usuario_id',
    )

    config_empresa = db.relationship(
        'ConfigEmpresa', backref='usuario', uselist=False,
        cascade='all, delete-orphan',
        foreign_keys='ConfigEmpresa.usuario_id',
    )

    config_tasa = db.relationship(
        'ConfigTasa', backref='usuario', uselist=False,
        cascade='all, delete-orphan',
        foreign_keys='ConfigTasa.usuario_id',
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.role == 'admin'

    @property
    def es_vendedor_activo(self):
        return self.es_vendedor and self.usuario_padre_id is not None

    @property
    def suscripcion_vigente(self):
        if not self.suscripcion_activa or not self.fecha_fin_suscripcion:
            return False
        return self.fecha_fin_suscripcion >= date.today()

    @property
    def plan(self):
        return 'VIP' if self.suscripcion_vigente else 'Free'





    # ============ PIN DE CANCELACION ============
    def set_pin_cancelacion(self, pin):
        """Hashea y guarda el PIN de cancelacion (6 digitos)."""
        from werkzeug.security import generate_password_hash
        if not pin or not pin.isdigit() or len(pin) != 6:
            raise ValueError('El PIN debe tener exactamente 6 digitos')
        self.pin_cancelacion_hash = generate_password_hash(pin)

    def check_pin_cancelacion(self, pin):
        """Verifica el PIN de cancelacion."""
        from werkzeug.security import check_password_hash
        if not self.pin_cancelacion_hash:
            return False
        if not pin:
            return False
        return check_password_hash(self.pin_cancelacion_hash, pin)

    @property
    def tiene_pin_cancelacion(self):
        return bool(self.pin_cancelacion_hash)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'email': self.email,
            'role': self.role,
            'activo': self.activo,
        }

    def __repr__(self):
        return f'<Usuario {self.email}>'

class VendedorConfig(db.Model):
    """Configuracion y permisos de un vendedor bajo un usuario padre (VIP).
    Limite: MAX 7 vendedores por VIP.
    """
    __tablename__ = 'vendedores_config'
    
    MAX_VENDEDORES = 7

    id = db.Column(db.Integer, primary_key=True)
    usuario_padre_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                                  nullable=False, index=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'),
                            nullable=False, unique=True, index=True)
    activo = db.Column(db.Boolean, default=True)
    notas = db.Column(db.Text, default='')
    limite_ventas_dia = db.Column(db.Integer, default=0)
    
    puede_editar_inventario = db.Column(db.Boolean, default=False)
    puede_ver_clientes = db.Column(db.Boolean, default=False)
    puede_ver_facturas = db.Column(db.Boolean, default=False)
    puede_ver_reportes_completos = db.Column(db.Boolean, default=False)
    puede_cancelar_ventas = db.Column(db.Boolean, default=False)
    puede_ver_costos = db.Column(db.Boolean, default=False)
    
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    
    padre = db.relationship('Usuario', foreign_keys=[usuario_padre_id],
                            backref=db.backref('vendedores_config', lazy='dynamic',
                                              cascade='all, delete-orphan'))
    vendedor = db.relationship('Usuario', foreign_keys=[vendedor_id],
                               backref=db.backref('config_vendedor', uselist=False,
                                                 cascade='all, delete-orphan'))
    
    @staticmethod
    def contar_vendedores(padre_id):
        return VendedorConfig.query.filter_by(usuario_padre_id=padre_id, activo=True).count()
    
    @staticmethod
    def puede_crear_mas(padre_id):
        return VendedorConfig.contar_vendedores(padre_id) < VendedorConfig.MAX_VENDEDORES
    
    def __repr__(self):
        return f'<VendedorConfig padre={self.usuario_padre_id} vendedor={self.vendedor_id}>'
