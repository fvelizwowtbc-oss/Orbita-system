# app/utils/images.py
import os
import uuid
import glob
from datetime import datetime

from PIL import Image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generar_nombre_archivo(filename, user_id, producto_id=None):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    rs = uuid.uuid4().hex[:8]
    base = f'user_{user_id}_prod_{producto_id}_{ts}_{rs}' if producto_id \
        else f'user_{user_id}_{ts}_{rs}'
    return f'{base}.{ext}'


def guardar_imagen_producto(file, user_id, producto_id, upload_folder):
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    filename = generar_nombre_archivo(file.filename, user_id, producto_id)
    user_dir = os.path.join(upload_folder, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, filename)

    try:
        file.save(filepath)
        # Thumbnail
        with Image.open(filepath) as img:
            img.thumbnail((400, 400))
            thumb_path = os.path.join(user_dir, f'thumb_{filename}')
            img.save(thumb_path, quality=85, optimize=True)
        return filename
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        return None


def eliminar_imagenes_producto(user_id, producto_id, upload_folder):
    patron = os.path.join(upload_folder, str(user_id),
                          f'*user_{user_id}_prod_{producto_id}_*')
    for fp in glob.glob(patron):
        try:
            os.remove(fp)
        except OSError:
            pass


def obtener_imagen_producto(user_id, producto_id, upload_folder):
    patron = os.path.join(upload_folder, str(user_id),
                          f'*user_{user_id}_prod_{producto_id}_*')
    archivos = [f for f in glob.glob(patron) if 'thumb_' not in os.path.basename(f)]
    return os.path.basename(archivos[0]) if archivos else None