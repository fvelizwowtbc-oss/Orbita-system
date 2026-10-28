# run.py
# Servidor de produccion (waitress) para el Sistema de Gestion.
#
# Uso:
#     python run.py                 # Puerto 5000, accesible en la red
#     PORT=8080 python run.py       # Puerto custom
import os
from waitress import serve
from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))

    print('=' * 60)
    print(f'  Servidor iniciado en http://{host}:{port}')
    print('=' * 60)

    serve(
        app,
        host=host,
        port=port,
        threads=8,
        connection_limit=100,
        channel_timeout=300,
        cleanup_interval=30,
    )
