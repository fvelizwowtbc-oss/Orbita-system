# app/services/vendedores.py
"""
Servicio para gestion de vendedores.
Un usuario VIP (o cualquier user) puede crear hasta 7 vendedores.
"""
from datetime import datetime, date
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models.usuario import Usuario, VendedorConfig
from ..utils.validators import validar_email, validar_password


class VendedorService:

    @staticmethod
    def listar(padre_id):
        """Lista todos los vendedores de un padre."""
        configs = VendedorConfig.query.filter_by(usuario_padre_id=padre_id) \
            .order_by(VendedorConfig.creado_en.desc()).all()
        return configs

    @staticmethod
    def puede_crear_mas(padre_id):
        """Verifica si el padre puede crear mas vendedores (debe ser VIP)."""
        if not VendedorService.es_vip(padre_id):
            return False
        return VendedorConfig.puede_crear_mas(padre_id)

    @staticmethod
    def contar(padre_id):
        """Cuenta vendedores activos."""
        return VendedorConfig.contar_vendedores(padre_id)

    @staticmethod
    def es_vip(padre_id):
        """Verifica si el usuario tiene suscripcion VIP activa."""
        padre = Usuario.query.get(padre_id)
        if not padre:
            return False
        return padre.suscripcion_vigente

    @staticmethod
    def crear(padre_id, data):
        """
        Crea un nuevo vendedor.
        data: {
            nombre, email, password, telefono (opcional),
            notas (opcional),
            puede_editar_inventario, puede_ver_clientes, puede_ver_facturas,
            puede_ver_reportes_completos, puede_cancelar_ventas, puede_ver_costos
        }
        """
        # 0. ✅ VALIDAR SUSCRIPCION VIP
        padre = Usuario.query.get(padre_id)
        if not padre:
            return None, 'Usuario no encontrado'
        
        if not padre.suscripcion_vigente:
            return None, 'Solo usuarios con suscripcion VIP activa pueden crear vendedores. Adquiere tu plan VIP para habilitar esta funcion.'
        
        # 1. Verificar limite
        if not VendedorConfig.puede_crear_mas(padre_id):
            return None, f'Limite alcanzado. Maximo {VendedorConfig.MAX_VENDEDORES} vendedores por cuenta.'

        # 2. Validar datos
        nombre = data.get('nombre', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not nombre:
            return None, 'El nombre es obligatorio'
        if not email:
            return None, 'El email es obligatorio'

        ok, msg = validar_email(email)
        if not ok:
            return None, f'Email invalido: {msg}'

        ok, msg = validar_password(password)
        if not ok:
            return None, msg

        # 3. Verificar que el email no exista
        existente = Usuario.query.filter_by(email=email).first()
        if existente:
            return None, 'El email ya esta registrado'

        # 4. Crear usuario
        vendedor = Usuario(
            nombre=nombre,
            email=email,
            telefono=data.get('telefono', '').strip(),
            es_vendedor=True,
            usuario_padre_id=padre_id,
            activo=True,
        )
        vendedor.set_password(password)

        # 5. Aplicar permisos
        vendedor.puede_editar_inventario = data.get('puede_editar_inventario') == '1'
        vendedor.puede_ver_clientes = data.get('puede_ver_clientes') == '1'
        vendedor.puede_ver_facturas = data.get('puede_ver_facturas') == '1'
        vendedor.puede_ver_reportes_completos = data.get('puede_ver_reportes_completos') == '1'
        vendedor.puede_cancelar_ventas = data.get('puede_cancelar_ventas') == '1'
        vendedor.puede_ver_costos = data.get('puede_ver_costos') == '1'

        try:
            db.session.add(vendedor)
            db.session.flush()

            # 6. Crear config
            config = VendedorConfig(
                usuario_padre_id=padre_id,
                vendedor_id=vendedor.id,
                activo=True,
                notas=data.get('notas', '').strip(),
                puede_editar_inventario=vendedor.puede_editar_inventario,
                puede_ver_clientes=vendedor.puede_ver_clientes,
                puede_ver_facturas=vendedor.puede_ver_facturas,
                puede_ver_reportes_completos=vendedor.puede_ver_reportes_completos,
                puede_cancelar_ventas=vendedor.puede_cancelar_ventas,
                puede_ver_costos=vendedor.puede_ver_costos,
            )
            db.session.add(config)
            db.session.commit()
            return vendedor, None
        except Exception as e:
            db.session.rollback()
            return None, f'Error al crear vendedor: {str(e)}'

    @staticmethod
    def actualizar(vendedor_id, padre_id, data):
        """Actualiza los permisos de un vendedor."""
        vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=padre_id).first()
        if not vendedor:
            return False, 'Vendedor no encontrado'

        config = VendedorConfig.query.filter_by(vendedor_id=vendedor_id).first()
        if not config:
            return False, 'Configuracion no encontrada'

        # Actualizar datos basicos
        vendedor.nombre = data.get('nombre', vendedor.nombre).strip()
        vendedor.telefono = data.get('telefono', vendedor.telefono or '').strip()

        # Actualizar permisos
        permisos = ['puede_editar_inventario', 'puede_ver_clientes', 'puede_ver_facturas',
                    'puede_ver_reportes_completos', 'puede_cancelar_ventas', 'puede_ver_costos']
        for p in permisos:
            valor = data.get(p) == '1'
            setattr(vendedor, p, valor)
            setattr(config, p, valor)

        # Actualizar config
        config.notas = data.get('notas', config.notas or '').strip()

        # Actualizar password si se envio
        password = data.get('password', '').strip()
        if password:
            ok, msg = validar_password(password)
            if not ok:
                return False, msg
            vendedor.set_password(password)

        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def desactivar(vendedor_id, padre_id):
        """Desactiva un vendedor."""
        vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=padre_id).first()
        if not vendedor:
            return False, 'Vendedor no encontrado'

        vendedor.activo = False
        config = VendedorConfig.query.filter_by(vendedor_id=vendedor_id).first()
        if config:
            config.activo = False

        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def reactivar(vendedor_id, padre_id):
        """Reactiva un vendedor."""
        # Validar VIP
        if not VendedorService.es_vip(padre_id):
            return False, 'Solo usuarios VIP pueden gestionar vendedores.'
        
        if not VendedorConfig.puede_crear_mas(padre_id):
            return False, f'Limite alcanzado. Maximo {VendedorConfig.MAX_VENDEDORES} vendedores.'

        vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=padre_id).first()
        if not vendedor:
            return False, 'Vendedor no encontrado'

        vendedor.activo = True
        config = VendedorConfig.query.filter_by(vendedor_id=vendedor_id).first()
        if config:
            config.activo = True

        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def eliminar(vendedor_id, padre_id):
        """Elimina un vendedor permanentemente."""
        vendedor = Usuario.query.filter_by(id=vendedor_id, usuario_padre_id=padre_id).first()
        if not vendedor:
            return False, 'Vendedor no encontrado'

        try:
            db.session.delete(vendedor)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def stats_vendedor(vendedor_id):
        """Devuelve estadisticas de un vendedor."""
        from ..models.venta import Venta
        from sqlalchemy import func

        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        stats = {
            'ventas_hoy': Venta.query.filter(
                Venta.vendedor_id == vendedor_id,
                func.date(Venta.creado_en) == hoy,
            ).count(),
            'total_hoy_usd': float(
                db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
                .filter(Venta.vendedor_id == vendedor_id, func.date(Venta.creado_en) == hoy)
                .scalar() or 0
            ),
            'ventas_mes': Venta.query.filter(
                Venta.vendedor_id == vendedor_id,
                func.date(Venta.creado_en) >= inicio_mes,
            ).count(),
            'total_mes_usd': float(
                db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
                .filter(Venta.vendedor_id == vendedor_id, func.date(Venta.creado_en) >= inicio_mes)
                .scalar() or 0
            ),
        }
        return stats

    @staticmethod
    def ventas_recientes(vendedor_id, limite=10):
        """Devuelve las ventas recientes de un vendedor."""
        from ..models.venta import Venta
        return Venta.query.filter_by(vendedor_id=vendedor_id) \
            .order_by(Venta.creado_en.desc()).limit(limite).all()
