# app/utils_red.py
# Utilidades para detectar la IP local del servidor.
import socket


def obtener_ip_local_servidor():
    """Devuelve la IP local de la PC en la red WiFi/LAN.

    Truco: abre un socket UDP y "conecta" a una IP publica (8.8.8.8).
    No envia datos, solo sirve para saber cual es la IP local que el
    sistema operativo usaria para salir a internet. Eso nos da la IP
    real de la PC en la red local.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            # Fallback: usar el hostname
            try:
                ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                ip = None
        finally:
            s.close()
        return ip
    except Exception:
        return None


def obtener_url_acceso(puerto=5000):
    """Devuelve la URL completa para acceder desde otro dispositivo."""
    ip = obtener_ip_local_servidor()
    if ip:
        return f"http://{ip}:{puerto}"
    return None
