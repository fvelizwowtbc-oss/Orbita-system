# app/services/cashea.py
# Servicio para manejar la logica de Cashea (cuotas y vencimientos)
from datetime import date, timedelta
from decimal import Decimal

from ..extensions import db
from ..models.cuota_cashea import CuotaCashea
from ..models.factura import FacturaCobrar


# Cada cuantos dias vence una cuota
DIAS_ENTRE_CUOTAS = 14


PORCENTAJES_INICIALES = [0, 10, 20, 30, 40, 50, 60]
NUMEROS_CUOTAS = [3, 6, 9, 12]


class CasheaService:

    @staticmethod
    def crear_cuotas(factura, num_cuotas, saldo_usd, fecha_inicio=None):
        """Crea las cuotas de una factura Cashea.

        Args:
            factura: instancia de FacturaCobrar
            num_cuotas: numero de cuotas (3, 6, 9, 12)
            saldo_usd: monto total a pagar en cuotas (despues del inicial)
            fecha_inicio: fecha desde la cual contar (default: hoy)

        Returns:
            lista de CuotaCashea creadas
        """
        if fecha_inicio is None:
            fecha_inicio = date.today()

        saldo = Decimal(str(saldo_usd))
        monto_por_cuota = (saldo / num_cuotas).quantize(Decimal("0.01"))

        # Ajustar la ultima cuota para que sumen exactamente el saldo
        cuotas = []
        acumulado = Decimal("0")

        for i in range(1, num_cuotas + 1):
            if i == num_cuotas:
                monto = saldo - acumulado  # ajustar
            else:
                monto = monto_por_cuota
                acumulado += monto

            fecha_venc = fecha_inicio + timedelta(days=DIAS_ENTRE_CUOTAS * i)

            cuota = CuotaCashea(
                factura_id=factura.id,
                numero=i,
                monto_usd=float(monto),
                fecha_vencimiento=fecha_venc,
                estado='pendiente',
            )
            db.session.add(cuota)
            cuotas.append(cuota)

        return cuotas

    @staticmethod
    def calcular_resumen_cashea(total_usd, porcentaje_inicial, num_cuotas):
        """Calcula el resumen de Cashea.

        Returns:
            dict con: monto_inicial, saldo, monto_cuota, total
        """
        total = Decimal(str(total_usd))
        porcentaje = Decimal(str(porcentaje_inicial))

        monto_inicial = (total * porcentaje / Decimal("100")).quantize(Decimal("0.01"))
        saldo = total - monto_inicial
        monto_cuota = (saldo / num_cuotas).quantize(Decimal("0.01")) if num_cuotas > 0 else Decimal("0")

        return {
            "monto_inicial": float(monto_inicial),
            "saldo": float(saldo),
            "monto_cuota": float(monto_cuota),
            "total": float(total),
            "porcentaje_inicial": int(porcentaje_inicial),
            "num_cuotas": num_cuotas,
        }

    @staticmethod
    def marcar_cuota_pagada(cuota, fecha_pago=None):
        """Marca una cuota como pagada y actualiza el saldo de la factura.

        Tambien registra el ingreso del dia en los reportes.
        """
        if cuota.estado == 'pagada':
            return False, 'Ya esta pagada'

        if fecha_pago is None:
            fecha_pago = date.today()

        cuota.estado = 'pagada'
        cuota.fecha_pago = fecha_pago

        # Actualizar saldo de la factura
        factura = cuota.factura
        if factura:
            # Restar del saldo
            nuevo_saldo = float(factura.saldo_usd or 0) - float(cuota.monto_usd or 0)
            if nuevo_saldo < 0:
                nuevo_saldo = 0
            factura.saldo_usd = nuevo_saldo

            # Si todas las cuotas estan pagadas, marcar factura como pagada
            total_cuotas = factura.cuotas_cashea.count()
            cuotas_pagadas = factura.cuotas_cashea.filter_by(estado='pagada').count()

            if cuotas_pagadas >= total_cuotas:
                factura.estado = 'pagado'
            else:
                factura.estado = 'pendiente'

            # ✅ Registrar el ingreso del dia para reportes
            try:
                from ..models.cuota_cashea import CuotaCashea
                # Marcar la cuota como ingreso del dia
                cuota.monto_usd = float(cuota.monto_usd or 0)
                # El ingreso se calcula en reportes sumando las cuotas pagadas por fecha
                # (No necesitamos agregar un campo, ya tenemos fecha_pago)
            except Exception:
                pass

        return True, None
