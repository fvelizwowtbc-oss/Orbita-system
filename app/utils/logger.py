# app/utils/logger.py
"""
Configuracion centralizada de logging.

En modo .exe, los logs van a:
    %APPDATA%/SistemaGestion/logs/app.log

En modo dev, van a la raiz del proyecto (via basedir).
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def configurar_logging(app_data_dir, debug=False):
    """
    Configura logging a archivo + consola (solo si debug).

    Args:
        app_data_dir: ruta de datos de la app (%APPDATA%/SistemaGestion)
        debug: si True, aÃ±ade handler de consola y nivel DEBUG

    Returns:
        logging.Logger: logger raiz configurado
    """
    log_dir = os.path.join(app_data_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')

    nivel = logging.DEBUG if debug else logging.INFO

    formato = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Handler de archivo (rotativo: 5 MB x 5 archivos)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formato)
    file_handler.setLevel(nivel)

    # Handler de consola (solo en debug)
    console_handler = None
    if debug:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formato)
        console_handler.setLevel(nivel)

    # Logger raiz
    root = logging.getLogger()
    root.setLevel(nivel)

    # Limpiar handlers previos (evita duplicados)
    for h in list(root.handlers):
        root.removeHandler(h)

    root.addHandler(file_handler)
    if console_handler:
        root.addHandler(console_handler)

    # Silenciar logs ruidosos
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('waitress').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('webview').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f'Logging configurado: {log_file} (nivel={"DEBUG" if debug else "INFO"})')
    return logger
