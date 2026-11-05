# app/services/ventas.py
from datetime import date
from decimal import Decimal
import logging

from ..extensions import db
from ..models.producto import Producto
from ..models.venta import Venta
from ..models.factura import FacturaCobrar, Abono
from ..models.caja import CajaTurno
from ..models.cliente import Cliente
from .tasas import TasasService
from ..utils.helpers import generar_numero_factura


logger = logging.getLogger(__name__)


class VentaError(Exception):
    pass


class VentasService:

    @staticmethod
    def procesar(usuario_id, data, vendedor_id=None):
        """
        Procesa una venta multi-item.
        data: {
            items: [{producto_id, cantidad, precio_usd, tasa_usada}],
            tipo_venta: 'contado'|'credito',
            cliente_id, cliente_nombre,
            metodo_pago, observaciones,
            monto_inicial_usd, monto_inicial_ves,
            vendedor_id
        }
        """
        items = data.get('items', [])
        if not items:
            raise VentaError('No hay items en la venta')

        tasas = TasasService.obtener_tasas(usuario_id)
        tipo_venta = data.get('tipo_venta', 'contado')
        cliente_id = data.get('cliente_id')
        cliente_nombre = data.get('cliente_nombre', 'Consumidor Final')
        monto_inicial_usd = float(data.get('monto_inicial_usd', 0) or 0)
        monto_inicial_ves = float(data.get('monto_inicial_ves', 0) or 0)

        ventas_creadas = []
        total_usd = 0.0
        primera_venta_id = None

        try:
            for item in items:
                pid = item['producto_id']
                cant = int(item['cantidad'])
                pu = float(item['precio_usd'])
                tasa_usada = item.get('tasa_usada', tasas['activa'])

                # Bloqueo pesimista: SELECT ... FOR UPDATE (SQLite no soporta, pero evitamos race con verificación)
                producto = Producto.query.filter_by(id=pid, usuario_id=usuario_id).first()
                if not producto:
                    raise VentaError(f'Producto {pid} no encontrado')
                if producto.stock_actual < cant:
                    raise VentaError(
                        f'Stock insuficiente de "{producto.nombre}". '
                        f'Disponible: {producto.stock_actual}'
                    )

                total_item = cant * pu
                total_usd += total_item

                # Descontar stock
                producto.stock_actual -= cant

                venta = Venta(
                    usuario_id=usuario_id,
                    producto_id=pid,
                    vendedor_id=data.get('vendedor_id') or vendedor_id,
                    cantidad=cant,
                    precio_usd=pu,
                    tasa_oficial=tasas['oficial'],
                    tasa_manual1=tasas['manual1'],
                    tasa_manual2=tasas['manual2'],
                    tasa_usada=tasa_usada,
                    total_usd=total_item,
                    total_oficial=total_item * tasas['oficial'],
                    total_manual1=total_item * tasas['manual1'],
                    total_manual2=total_item * tasas['manual2'],
                    metodo_pago=data.get('metodo_pago', 'efectivo'),
                    observaciones=data.get('observaciones', ''),
                    tipo_venta=tipo_venta,
                    cliente_id=cliente_id,
                    cliente_nombre=cliente_nombre,
                )
                db.session.add(venta)
                db.session.flush()  # para obtener ID

                if primera_venta_id is None:
                    primera_venta_id = venta.id

                ventas_creadas.append({
                    'venta_id': venta.id,
                    'producto': producto.nombre,
                    'cantidad': cant,
                    'precio_usd': pu,
                    'total_usd': total_item,
                    'nombre': producto.nombre,
                })

            # Generar número de factura
            nro_factura = generar_numero_factura(primera_venta_id)

            # Actualizar todas las ventas con el número de factura
            for v in ventas_creadas:
                venta = db.session.get(Venta, v['venta_id'])
                venta.nro_factura = nro_factura

            # Calcular totales en VES
            tasa_venta = tasas.get(tasas['activa'], 0)
            total_ves = total_usd * tasa_venta

            # Crear factura por cobrar
            if tipo_venta == 'contado':
                saldo_usd, saldo_ves, estado = 0, 0, 'pagado'
            else:
                saldo_usd = max(0, total_usd - monto_inicial_usd)
                saldo_ves = max(0, total_ves - monto_inicial_ves)
                estado = 'pagado' if saldo_usd <= 0.01 else 'pendiente'

            factura = FacturaCobrar(
                usuario_id=usuario_id,
                venta_id=primera_venta_id,
                cliente_id=cliente_id,
                cliente_nombre=cliente_nombre,
                tipo_venta=tipo_venta,
                total_usd=total_usd,
                total_ves=total_ves,
                saldo_usd=saldo_usd,
                saldo_ves=saldo_ves,
                estado=estado,
                nro_factura=nro_factura,
            )
            db.session.add(factura)
            db.session.flush()

            # Abono inicial
            if monto_inicial_usd > 0:
                abono = Abono(
                    factura_id=factura.id,
                    monto_usd=monto_inicial_usd,
                    monto_ves=monto_inicial_ves,
                    tasa_usada=tasa_venta or 36,
                    metodo_pago='efectivo',
                    notas='Pago inicial',
                )
                db.session.add(abono)

            # ✅ SUMAR A LA CAJA SI EL PAGO ES EN EFECTIVO
            from decimal import Decimal
            metodo = data.get('metodo_pago', 'efectivo')
            if metodo == 'efectivo':
                caja_abierta = CajaTurno.query.filter_by(usuario_id=usuario_id, estado='abierta').first()
                if caja_abierta:
                    caja_abierta.total_ventas_efectivo_usd = Decimal(str(caja_abierta.total_ventas_efectivo_usd or 0)) + Decimal(str(total_usd))
                    caja_abierta.total_ventas_efectivo_bs = Decimal(str(caja_abierta.total_ventas_efectivo_bs or 0)) + Decimal(str(total_ves))

            db.session.commit()

            return {
                'ventas': ventas_creadas,
                'total_usd': total_usd,
                'total_ves': total_ves,
                'nro_factura': nro_factura,
                'factura_id': factura.id,
                'tipo_venta': tipo_venta,
                'primera_venta_id': primera_venta_id,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error procesando venta: {e}')
            if isinstance(e, VentaError):
                raise
            raise VentaError(str(e))

    @staticmethod
    def agregar_abono(factura_id, monto_usd, monto_ves, tasa_usada, metodo='efectivo', notas=''):
        factura = db.session.get(FacturaCobrar, factura_id)
        if not factura:
            return False, 'Factura no encontrada'

        if monto_usd <= 0:
            return False, 'Monto debe ser mayor a 0'

        abono = Abono(
            factura_id=factura_id,
            monto_usd=round(float(monto_usd), 2),
            monto_ves=round(float(monto_ves), 2),
            tasa_usada=round(float(tasa_usada), 2),
            metodo_pago=metodo,
            notas=notas,
        )
        db.session.add(abono)

        factura.saldo_usd = round(max(0, float(factura.saldo_usd or 0) - float(monto_usd)), 2)
        factura.saldo_ves = round(max(0, float(factura.saldo_ves or 0) - float(monto_ves)), 2)

        if factura.saldo_usd < 0.01:
            factura.estado = 'pagado'
        else:
            factura.estado = 'pendiente'

        db.session.commit()
        return True, None