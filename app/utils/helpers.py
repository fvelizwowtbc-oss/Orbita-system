# app/utils/helpers.py
from datetime import datetime, date
from decimal import Decimal


def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def to_decimal(value, default=Decimal('0.00')):
    if value is None:
        return default
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except Exception:
        return default


def formatear_moneda(valor, simbolo='$'):
    return f'{simbolo}{to_float(valor):,.2f}'


def formatear_fecha(fecha, formato='%d/%m/%Y'):
    if not fecha:
        return ''
    if isinstance(fecha, str):
        return fecha
    return fecha.strftime(formato)


def rango_fechas_mes_actual():
    hoy = date.today()
    inicio = hoy.replace(day=1)
    return inicio, hoy


def fecha_hoy():
    return date.today()


def rango_meses_ultimos(n=6):
    """Devuelve lista de 'YYYY-MM' de los últimos n meses."""
    hoy = date.today()
    meses = []
    for i in range(n):
        mes = hoy.month - i
        año = hoy.year
        while mes <= 0:
            mes += 12
            año -= 1
        meses.append(f'{año:04d}-{mes:02d}')
    return list(reversed(meses))


def generar_numero_factura(venta_id):
    return f"F-{datetime.now().strftime('%Y%m%d%H%M%S')}-{venta_id}"


def truncar(texto, largo=50):
    if not texto:
        return ''
    return texto if len(texto) <= largo else texto[:largo] + '...'


def limpiar_string(valor):
    return (valor or '').strip()