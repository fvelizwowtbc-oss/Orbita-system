import shutil
from pathlib import Path

def log(msg, color='\033[0m'):
    print(f"{color}{msg}\033[0m")

def main():
    log("\n==================================================", '\033[96m')
    log("   FIX DEFINITIVO PARA RENDER (POSTGRES + IMAGEKIT)", '\033[96m')
    log("==================================================\n", '\033[96m')

    # 1. ARREGLAR CONFIG.PY PARA QUE NO USE SQLITE EN RENDER
    log("1. Forzando PostgreSQL en producción...")
    p_config = Path('config.py')
    if p_config.exists():
        c = p_config.read_text(encoding='utf-8')
        
        # Buscamos la línea donde asigna SQLALCHEMY_DATABASE_URI
        old_db = "SQLALCHEMY_DATABASE_URI = _db_url or f\"sqlite:///{INSTANCE_DIR / 'sistema_gestion.db'}\""
        
        # Si estamos en producción, OBLIGAMOS a usar DATABASE_URL
        new_db = """SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{INSTANCE_DIR / 'sistema_gestion.db'}"
    
    # ✅ FIX: Si estamos en Render (produccion) y no hay DATABASE_URL, es un error fatal
    import os as _os
    if _os.environ.get('RENDER') and not _db_url:
        raise RuntimeError("FATAL: DATABASE_URL no está configurada en Render. La app no puede usar SQLite en producción.")"""
        
        if old_db in c and 'RENDER' not in c:
            c = c.replace(old_db, new_db)
            shutil.copy2(p_config, p_config.with_suffix('.py.bak_render'))
            p_config.write_text(c, encoding='utf-8')
            log("  [OK] config.py actualizado (forzando PostgreSQL).", '\033[92m')

    # 2. ARREGLAR IMAGEKIT PARA QUE LIMPIE LAS URLS VIEJAS
    log("2. Limpiando URLs viejas de ImageKit...")
    p_service = Path('app/services/imagekit_service.py')
    if p_service.exists():
        c = p_service.read_text(encoding='utf-8')
        
        new_code = """from imagekitio import ImageKit
from flask import current_app
from io import BytesIO

class ImageKitService:
    @staticmethod
    def subir_imagen(file):
        try:
            # ✅ Limpiamos espacios y comillas
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY', '').strip().strip('"').strip("'")
            
            if not private_key:
                print("❌ DEBUG: IMAGEKIT_PRIVATE_KEY vacía.")
                return None

            imagekit = ImageKit(private_key=private_key)
            
            file_bytes = file.read()
            file_stream = BytesIO(file_bytes)
            
            upload_result = imagekit.files.upload(
                file=file_stream,
                file_name=file.filename,
                is_private_file=False,
                transformation={
                    "pre": "w-500,h-500,c-maintain_ratio,q-80,f-webp"
                }
            )
            
            if hasattr(upload_result, 'url'):
                url = upload_result.url
                print(f"✅ DEBUG: Imagen subida: {url}")
                return url
            return None
            
        except Exception as e:
            print(f"❌ DEBUG Error subiendo a ImageKit: {e}")
            return None
"""
        shutil.copy2(p_service, p_service.with_suffix('.py.bak_render2'))
        p_service.write_text(new_code, encoding='utf-8')
        log("  [OK] imagekit_service.py actualizado.", '\033[92m')

    # 3. ARREGLAR EL MODELO PARA DETECTAR BIEN LAS URLs VIEJAS
    log("3. Arreglando detección de URLs en producto.py...")
    p_model = Path('app/models/producto.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        
        # Reemplazar la propiedad imagen_url completa
        import re
        patron = re.compile(r"    @property\n    def imagen_url\(self\):.*?return f'/uploads/\{self\.usuario_id\}/\{self\.imagen_principal\}'", re.DOTALL)
        
        nueva_prop = """    @property
    def imagen_url(self):
        if not self.imagen_principal:
            return None
        # Si ya es URL de internet, devolverla tal cual (limpia)
        if self.imagen_principal.startswith('http://') or self.imagen_principal.startswith('https://'):
            return self.imagen_principal
        # Si es un archivo local, agregar la ruta
        return f'/uploads/{self.usuario_id}/{self.imagen_principal}'"""

        if patron.search(c):
            c = patron.sub(nueva_prop, c)
            shutil.copy2(p_model, p_model.with_suffix('.py.bak_render2'))
            p_model.write_text(c, encoding='utf-8')
            log("  [OK] producto.py actualizado.", '\033[92m')

    log("\n==================================================", '\033[92m')
    log(" ¡CAMBIOS APLICADOS!", '\033[92m')
    log("==================================================\n", '\033[92m')
    log("SIGUIENTE PASO OBLIGATORIO:", '\033[93m')
    log("1. Sube los cambios a GitHub (git add . && git commit -m 'Fix Render' && git push)")
    log("2. En Render, ve a Environment y BORRA la variable DATABASE_URL actual.")
    log("3. Vuelve a copiar la Internal Database URL desde tu base de datos en Render y pégala de nuevo.")
    log("4. Haz clic en Save, rebuild and deploy.\n")

if __name__ == '__main__':
    main()