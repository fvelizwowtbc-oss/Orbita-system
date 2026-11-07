import shutil
from pathlib import Path

def log(msg, color='\033[0m'):
    print(f"{color}{msg}\033[0m")

def main():
    log("\n==================================================", '\033[96m')
    log("   INTEGRACIÓN DE CLOUDINARY (ALMACENAMIENTO EN LA NUBE)", '\033[96m')
    log("==================================================\n", '\033[96m')

    # 1. Modificar el archivo config.py para agregar las variables
    log("1. Actualizando config.py...")
    p_config = Path('config.py')
    if p_config.exists():
        c = p_config.read_text(encoding='utf-8')
        if 'CLOUDINARY_CLOUD_NAME' not in c:
            c = c.replace(
                "    # ============ BASE DE DATOS ============",
                """    # ============ CLOUDINARY (IMAGENES) ============
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

    # ============ BASE DE DATOS ============"""
            )
            shutil.copy2(p_config, p_config.with_suffix('.py.bak_cloud'))
            p_config.write_text(c, encoding='utf-8')
            log("  [OK] Variables de Cloudinary agregadas a config.py.", '\033[92m')

    # 2. Modificar el archivo models/producto.py
    log("2. Actualizando modelo de Producto para guardar la URL...")
    p_model = Path('app/models/producto.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        # Cambiamos la propiedad imagen_url para que detecte si es una URL de Cloudinary
        old_prop = """    @property
    def imagen_url(self):
        if self.imagen_principal:
            return f'/uploads/{self.usuario_id}/{self.imagen_principal}'
        return None"""
        new_prop = """    @property
    def imagen_url(self):
        if not self.imagen_principal:
            return None
        # Si la imagen ya viene de Cloudinary (empieza con http), la devolvemos tal cual
        if self.imagen_principal.startswith('http'):
            return self.imagen_principal
        return f'/uploads/{self.usuario_id}/{self.imagen_principal}'"""
        
        if old_prop in c:
            c = c.replace(old_prop, new_prop)
            shutil.copy2(p_model, p_model.with_suffix('.py.bak_cloud'))
            p_model.write_text(c, encoding='utf-8')
            log("  [OK] Modelo de producto actualizado.", '\033[92m')

    # 3. Crear el servicio de Cloudinary
    log("3. Creando servicio de subida a la nube...")
    p_service = Path('app/services/cloudinary_service.py')
    service_code = """import cloudinary
import cloudinary.uploader
from flask import current_app
from io import BytesIO

class CloudinaryService:
    @staticmethod
    def inicializar():
        cloudinary.config(
            cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
            api_key=current_app.config.get('CLOUDINARY_API_KEY'),
            api_secret=current_app.config.get('CLOUDINARY_API_SECRET')
        )

    @staticmethod
    def subir_imagen(file):
        \"\"\"Sube una imagen a Cloudinary y devuelve la URL segura.\"\"\"
        try:
            CloudinaryService.inicializar()
            if not current_app.config.get('CLOUDINARY_CLOUD_NAME'):
                return None  # No configurado, usar fallback local

            # Subimos el archivo directamente desde el stream de memoria
            resultado = cloudinary.uploader.upload(
                file,
                folder="orbita_productos",
                transformation=[{"width": 500, "height": 500, "crop": "limit"}] # Optimiza la imagen
            )
            return resultado.get('secure_url')
        except Exception as e:
            print(f"Error subiendo a Cloudinary: {e}")
            return None
"""
    p_service.parent.mkdir(parents=True, exist_ok=True)
    p_service.write_text(service_code, encoding='utf-8')
    log("  [OK] cloudinary_service.py creado.", '\033[92m')

    # 4. Modificar inventario.py para usar Cloudinary
    log("4. Modificando app/services/inventario.py...")
    p_inv = Path('app/services/inventario.py')
    if p_inv.exists():
        c = p_inv.read_text(encoding='utf-8')
        
        # Reemplazar la lógica de guardado local por Cloudinary
        old_img_logic = """            # Guardar imagen
            if 'imagen_producto' in files:
                img = files['imagen_producto']
                if img and img.filename:
                    nombre_img = guardar_imagen_producto(img, usuario_id, producto.id, upload_folder)
                    if nombre_img:
                        producto.imagen_principal = nombre_img"""
        new_img_logic = """            # Guardar imagen (Cloudinary o Local)
            if 'imagen_producto' in files:
                img = files['imagen_producto']
                if img and img.filename:
                    from .cloudinary_service import CloudinaryService
                    url_nube = CloudinaryService.subir_imagen(img)
                    if url_nube:
                        producto.imagen_principal = url_nube
                    else:
                        # Fallback: Guardar local si Cloudinary falla o no está configurado
                        nombre_img = guardar_imagen_producto(img, usuario_id, producto.id, upload_folder)
                        if nombre_img:
                            producto.imagen_principal = nombre_img"""
                            
        if old_img_logic in c:
            c = c.replace(old_img_logic, new_img_logic)
            
            # Hacer lo mismo en la función de editar
            old_edit_img = """        if 'imagen_producto' in files:
            img = files['imagen_producto']
            if img and img.filename:
                eliminar_imagenes_producto(producto.usuario_id, producto.id, upload_folder)
                nombre = guardar_imagen_producto(img, producto.usuario_id, producto.id, upload_folder)
                if nombre:
                    producto.imagen_principal = nombre"""
            new_edit_img = """        if 'imagen_producto' in files:
            img = files['imagen_producto']
            if img and img.filename:
                from .cloudinary_service import CloudinaryService
                url_nube = CloudinaryService.subir_imagen(img)
                if url_nube:
                    producto.imagen_principal = url_nube
                else:
                    eliminar_imagenes_producto(producto.usuario_id, producto.id, upload_folder)
                    nombre = guardar_imagen_producto(img, producto.usuario_id, producto.id, upload_folder)
                    if nombre:
                        producto.imagen_principal = nombre"""
            c = c.replace(old_edit_img, new_edit_img)
            
            shutil.copy2(p_inv, p_inv.with_suffix('.py.bak_cloud'))
            p_inv.write_text(c, encoding='utf-8')
            log("  [OK] inventario.py actualizado para usar Cloudinary.", '\033[92m')

    log("\n==================================================", '\033[92m')
    log(" ¡INTEGRACIÓN BASE COMPLETADA!", '\033[92m')
    log("==================================================\n", '\033[92m')
    log("SIGUIENTES PASOS:", '\033[93m')
    log("1. Regístrate gratis en Cloudinary.com")
    log("2. Agrega las credenciales a tu archivo .env")
    log("3. Instala la librería: .\\venv\\Scripts\\pip install cloudinary")
    log("4. Reinicia Flask.\n")

if __name__ == '__main__':
    main()