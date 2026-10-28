# app/utils_tz.py
# Zona horaria oficial: Caracas (UTC-4)
from datetime import datetime, timedelta, timezone, date, time

TZ_CARACAS = timezone(timedelta(hours=-4))


def ahora_caracas():
    """Devuelve datetime actual en hora de Caracas."""
    return datetime.now(TZ_CARACAS)


def hoy_caracas():
    """Devuelve date actual en hora de Caracas."""
    return ahora_caracas().date()


def a_caracas(dt):
    """Convierte un datetime (naive UTC o aware) a hora de Caracas."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # La BD guarda UTC naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_CARACAS)


def rango_dia_caracas(fecha):
    """Dado un date, devuelve (inicio_utc_naive, fin_utc_naive).

    Toma un dia en hora Caracas y devuelve los limites en UTC naive
    que corresponden a ese dia (para filtrar en SQLite).
    """
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    inicio_local = datetime.combine(fecha, time.min, tzinfo=TZ_CARACAS)
    fin_local = datetime.combine(fecha, time.max, tzinfo=TZ_CARACAS)
    inicio_utc = inicio_local.astimezone(timezone.utc).replace(tzinfo=None)
    fin_utc = fin_local.astimezone(timezone.utc).replace(tzinfo=None)
    return inicio_utc, fin_utc


def rango_entre_caracas(fecha_desde, fecha_hasta):
    """Rango completo entre dos fechas (inclusive), en UTC naive."""
    if isinstance(fecha_desde, datetime):
        fecha_desde = fecha_desde.date()
    if isinstance(fecha_hasta, datetime):
        fecha_hasta = fecha_hasta.date()
    inicio, _ = rango_dia_caracas(fecha_desde)
    _, fin = rango_dia_caracas(fecha_hasta)
    return inicio, fin


def fmt_fecha_caracas(dt, formato='%d/%m/%Y'):
    """Formatea un datetime en hora de Caracas."""
    if dt is None:
        return ''
    return a_caracas(dt).strftime(formato)


def fmt_hora_caracas(dt, formato='%H:%M'):
    """Formatea la hora de un datetime en hora de Caracas."""
    if dt is None:
        return ''
    return a_caracas(dt).strftime(formato)
