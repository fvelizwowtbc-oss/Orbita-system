import shutil
from pathlib import Path

def log(msg, color='\033[0m'):
    print(f"{color}{msg}\033[0m")

def main():
    log("\n==================================================", '\033[96m')
    log("   INTEGRACIÓN DE IMAGEKIT (ALTERNATIVA A CLOUDINARY)", '\033[96m')
    log("==================================================\n", '\033[96m')

    # 1. Config.py
    log("1. Actualizando config.py...")
    p_config = Path('config.py')
    if p_config.exists():
        c = p_config.read_text(encoding='utf-8')
        if 'IMAGEKIT_PRIVATE_KEY' not in c:
            c = c.replace(
                "    # ============ BASE DE DATOS ============",
                """    # ============ IMAGEKIT (IMAGENES) ============
    IMAGEKIT_PUBLIC_KEY = os.environ.get("IMAGEKIT_PUBLIC_KEY")
    IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY")
    IMAGEKIT_URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT")

    # ============ BASE DE DATOS ============"""
            )
            shutil.copy2(p_config, p_config.with_suffix('.py.bak_ik'))
            p_config.write_text(c, encoding='utf-8')
            log("  [OK] Variables de ImageKit agregadas.", '\033[92m')

    # 2. Modelo Producto (misma lógica, detecta URLs http)
    log("2. Asegurando modelo de Producto...")
    p_model = Path('app/models/producto.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        if 'startswith(\'http\')' not in c:
            old_prop = """    @property
    def imagen_url(self):
        if self.imagen_principal:
            return f'/uploads/{self.usuario_id}/{self.imagen_principal}'
        return None"""
            new_prop = """    @property
    def imagen_url(self):
        if not self.imagen_principal:
            return None
        if self.imagen_principal.startswith('http'):
            return self.imagen_principal
        return f'/uploads/{self.usuario_id}/{self.imagen_principal}'"""
            c = c.replace(old_prop, new_prop)
            shutil.copy2(p_model, p_model.with_suffix('.py.bak_ik'))
            p_model.write_text(c, encoding='utf-8')
            log("  [OK] Modelo actualizado.", '\033[92m')

    # 3. Servicio de ImageKit
    log("3. Creando servicio de subida a ImageKit...")
    p_service = Path('app/services/imagekit_service.py')
    service_code = """from imagekitio import ImageKit
from flask import current_app

class ImageKitService:
    @staticmethod
    def subir_imagen(file):
        \"\"\"Sube una imagen a ImageKit y devuelve la URL.\"\"\"
        try:
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY')
            url_endpoint = current_app.config.get('IMAGEKIT_URL_ENDPOINT')
            
            if not private_key or not url_endpoint:
                return None # No configurado

            imagekit = ImageKit(
                private_key=private_key,
                public_key=current_app.config.get('IMAGEKIT_PUBLIC_KEY'),
                url_endpoint=url_endpoint
            )
            
            # Subimos el archivo
            upload_result = imagekit.upload_file(
                file=file,
                file_name=file.filename,
                options={
                    "folder": "/orbita_productos",
                    "is_private_file": False,
                }
            )
            return upload_result.response_metadata.url
        except Exception as e:
            print(f"Error subiendo a ImageKit: {e}")
            return None
"""
    p_service.parent.mkdir(parents=True, exist_ok=True)
    p_service.write_text(service_code, encoding='utf-8')
    log("  [OK] imagekit_service.py creado.", '\033[92m')

    # 4. Inventario.py
    log("4. Modificando app/services/inventario.py...")
    p_inv = Path('app/services/inventario.py')
    if p_inv.exists():
        c = p_inv.read_text(encoding='utf-8')
        
        # Reemplazar lógica en crear
        old_create = """                    nombre_img = guardar_imagen_producto(img, usuario_id, producto.id, upload_folder)
                    if nombre_img:
                        producto.imagen_principal = nombre_img"""
        new_create = """                    from .imagekit_service import ImageKitService
                    url_nube = ImageKitService.subir_imagen(img)
                    if url_nube:
                        producto.imagen_principal = url_nube
                    else:
                        nombre_img = guardar_imagen_producto(img, usuario_id, producto.id, upload_folder)
                        if nombre_img:
                            producto.imagen_principal = nombre_img"""
        c = c.replace(old_create, new_create)

        # Reemplazar lógica en editar
        old_edit = """                eliminar_imagenes_producto(producto.usuario_id, producto.id, upload_folder)
                nombre = guardar_imagen_producto(img, producto.usuario_id, producto.id, upload_folder)
                if nombre:
                    producto.imagen_principal = nombre"""
        new_edit = """                from .imagekit_service import ImageKitService
                url_nube = ImageKitService.subir_imagen(img)
                if url_nube:
                    producto.imagen_principal = url_nube
                else:
                    eliminar_imagenes_producto(producto.usuario_id, producto.id, upload_folder)
                    nombre = guardar_imagen_producto(img, producto.usuario_id, producto.id, upload_folder)
                    if nombre:
                        producto.imagen_principal = nombre"""
        c = c.replace(old_edit, new_edit)

        shutil.copy2(p_inv, p_inv.with_suffix('.py.bak_ik'))
        p_inv.write_text(c, encoding='utf-8')
        log("  [OK] inventario.py actualizado para ImageKit.", '\033[92m')

    log("\n==================================================", '\033[92m')
    log(" ¡INTEGRACIÓN CON IMAGEKIT COMPLETADA!", '\033[92m')
    log("==================================================\n", '\033[92m')
    log("SIGUIENTES PASOS:", '\033[93m')
    log("1. Regístrate gratis en ImageKit.io")
    log("2. Copia tus 3 credenciales al archivo .env")
    log("3. Instala: .\\venv\\Scripts\\pip install imagekitio")
    log("4. Reinicia Flask.\n")

if __name__ == '__main__':
    main()