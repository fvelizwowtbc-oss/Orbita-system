# app/utils/tokens.py
"""
Generacion y verificacion de tokens JWT para descargas seguras.

El token se pasa en la URL (?token=...) y NO requiere cookies,
ideal para pywebview (que no comparte cookies con requests).
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


# Tiempo de expiracion del token (segundos)
TOKEN_MAX_AGE = 300  # 5 minutos


def _get_serializer():
    """Crea el serializer con la SECRET_KEY de la app."""
    return URLSafeTimedSerializer(
        current_app.config['SECRET_KEY'],
        salt='descarga-archivo',
    )


def generar_token_descarga(recurso_id, tipo='factura'):
    """
    Genera un token firmado para descargar un recurso.

    Args:
        recurso_id: ID del recurso (ej: id de factura)
        tipo: tipo de recurso ('factura', 'reporte', etc.)

    Returns:
        str: token URL-safe
    """
    s = _get_serializer()
    payload = {
        'recurso_id': recurso_id,
        'tipo': tipo,
    }
    return s.dumps(payload)


def verificar_token_descarga(token, max_age=None):
    """
    Verifica un token de descarga.

    Args:
        token: string del token
        max_age: segundos de validez (default: TOKEN_MAX_AGE)

    Returns:
        dict con 'recurso_id' y 'tipo' si es valido, None si no.
    """
    if not token:
        return None

    if max_age is None:
        max_age = TOKEN_MAX_AGE

    try:
        s = _get_serializer()
        payload = s.loads(token, max_age=max_age)

        # Validar estructura
        if not isinstance(payload, dict):
            return None
        if 'recurso_id' not in payload or 'tipo' not in payload:
            return None

        return payload

    except SignatureExpired:
        return None
    except BadSignature:
        return None
    except Exception:
        return None
