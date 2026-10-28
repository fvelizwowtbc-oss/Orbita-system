# app/utils/validators.py
import re
from email_validator import validate_email, EmailNotValidError


def validar_email(email):
    try:
        valid = validate_email(email)
        return True, valid.email
    except EmailNotValidError as e:
        return False, str(e)


def validar_password(password, minimo=6):
    if not password:
        return False, 'La contraseña es obligatoria'
    if len(password) < minimo:
        return False, f'La contraseña debe tener al menos {minimo} caracteres'
    return True, ''


def validar_rif(rif):
    patron = r'^[JGVEPjgvep]-\d{8,9}-\d$'
    if not re.match(patron, rif or ''):
        return False, 'Formato de RIF inválido (Ej: J-12345678-9)'
    return True, ''


def validar_telefono_ve(telefono):
    if not telefono:
        return True, ''
    patron = r'^(0(412|414|416|424|426|212|241|etc)\d{7})$'
    # Validación simple: solo dígitos y +
    if not re.match(r'^[\d+\-\s()]{7,20}$', telefono):
        return False, 'Teléfono inválido'
    return True, ''


def validar_precio(valor):
    try:
        v = float(valor)
        if v < 0:
            return False, 'El precio no puede ser negativo'
        return True, v
    except (ValueError, TypeError):
        return False, 'Precio inválido'


def validar_cantidad(valor):
    try:
        v = int(valor)
        if v < 0:
            return False, 'La cantidad no puede ser negativa'
        return True, v
    except (ValueError, TypeError):
        return False, 'Cantidad inválida'