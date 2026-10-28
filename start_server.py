# start_server.py
# Entrypoint de produccion web para Orbita System (Windows / Waitress).
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from app import create_app
from waitress import serve


def main():
    app = create_app("production")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))

    print("=" * 60)
    print("  Orbita System - Servidor de produccion")
    print("=" * 60)
    print(f"  Escuchando: http://{host}:{port}")
    print(f"  Datos:      {os.environ.get('DATA_DIR', 'N/A')}")
    print("=" * 60)

    serve(
        app,
        host=host,
        port=port,
        threads=8,
        connection_limit=100,
        channel_timeout=300,
        cleanup_interval=30,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
        sys.exit(0)
