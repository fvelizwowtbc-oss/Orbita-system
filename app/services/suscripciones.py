# app/services/suscripciones.py
from datetime import date, timedelta

from ..extensions import db
from ..models.usuario import Usuario
from ..models.suscripcion import Suscripcion
from ..models.producto import Producto
from ..models.venta import Venta


LIMITES = {
    'free': {'productos': 5, 'ventas': 20},
    'vip': {'productos': 999999, 'ventas': 999999},
}


class SuscripcionesService:

    @staticmethod
    def verificar_limites(usuario_id):
        u = db.session.get(Usuario, usuario_id)
        if not u:
            return {'suscripcion_activa': False, 'limite_productos': 50,
                    'limite_ventas': 20, 'plan': 'Free'}

        activa = u.suscripcion_vigente
        return {
            'suscripcion_activa': activa,
            'limite_productos': u.limite_productos or 50,
            'limite_ventas': u.limite_ventas_mensuales or 20,
            'plan': 'VIP' if activa else 'Free',
        }

    @staticmethod
    def obtener_activa(usuario_id):
        return Suscripcion.query.filter(
            Suscripcion.usuario_id == usuario_id,
            Suscripcion.estado == 'activa',
            Suscripcion.fecha_fin >= date.today(),
        ).order_by(Suscripcion.fecha_fin.desc()).first()

    @staticmethod
    def cantidad_productos(usuario_id):
        return Producto.query.filter_by(usuario_id=usuario_id).count()

    @staticmethod
    def ventas_mes_actual(usuario_id):
        from ..utils_tz import rango_entre_caracas, hoy_caracas
        hoy = hoy_caracas()
        inicio = hoy.replace(day=1)
        inicio_utc, fin_utc = rango_entre_caracas(inicio, hoy)
        return Venta.query.filter(
            Venta.usuario_id == usuario_id,
            Venta.creado_en >= inicio_utc,
            Venta.creado_en <= fin_utc,
        ).count()

    @staticmethod
    def crear(usuario_id, plan, dias, admin_id, monto=0, notas=''):
        u = db.session.get(Usuario, usuario_id)
        if not u:
            return None, 'Usuario no encontrado'

        activa = SuscripcionesService.obtener_activa(usuario_id)
        if activa:
            return None, 'El usuario ya tiene una suscripción activa'

        fi = date.today()
        ff = fi + timedelta(days=dias)
        plan_key = plan.lower()

        s = Suscripcion(
            usuario_id=usuario_id,
            plan=plan,
            dias=dias,
            fecha_inicio=fi,
            fecha_fin=ff,
            monto=monto,
            metodo_pago='admin',
            notas=notas,
            creado_por=admin_id,
            estado='activa',
        )
        db.session.add(s)

        u.suscripcion_activa = True
        u.fecha_fin_suscripcion = ff
        u.limite_productos = LIMITES.get(plan_key, LIMITES['free'])['productos']
        u.limite_ventas_mensuales = LIMITES.get(plan_key, LIMITES['free'])['ventas']

        db.session.commit()
        return s, None

    @staticmethod
    def cancelar(suscripcion_id, admin_id):
        s = db.session.get(Suscripcion, suscripcion_id)
        if not s:
            return False, 'Suscripción no encontrada'

        s.estado = 'cancelada'
        s.cancelado_en = date.today()
        s.cancelado_por = admin_id

        u = db.session.get(Usuario, s.usuario_id)
        if u:
            u.suscripcion_activa = False
            u.limite_productos = LIMITES['free']['productos']
            u.limite_ventas_mensuales = LIMITES['free']['ventas']

        db.session.commit()
        return True, None

    @staticmethod
    def extender(suscripcion_id, dias_extra):
        s = db.session.get(Suscripcion, suscripcion_id)
        if not s:
            return False, 'Suscripción no encontrada'

        nueva_fecha = s.fecha_fin + timedelta(days=dias_extra)
        s.fecha_fin = nueva_fecha
        s.dias += dias_extra

        u = db.session.get(Usuario, s.usuario_id)
        if u:
            u.fecha_fin_suscripcion = nueva_fecha

        db.session.commit()
        return True, None