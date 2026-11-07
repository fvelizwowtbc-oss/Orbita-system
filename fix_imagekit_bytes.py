from pathlib import Path
import shutil

def main():
    p = Path('app/services/imagekit_service.py')
    if not p.exists():
        print("❌ No se encontró imagekit_service.py")
        return
        
    c = p.read_text(encoding='utf-8')
    
    bak = p.with_suffix('.py.bak_bytes')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Código final adaptado para enviar BytesIO al SDK v5+
    new_code = """from imagekitio import ImageKit
from flask import current_app
from io import BytesIO

class ImageKitService:
    @staticmethod
    def subir_imagen(file):
        \"\"\"Sube una imagen a ImageKit convirtiendo FileStorage a BytesIO.\"\"\"
        try:
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY')
            
            if not private_key:
                return None # No configurado

            imagekit = ImageKit(private_key=private_key)
            
            # ✅ Convertimos el FileStorage de Flask a BytesIO para que el SDK lo acepte
            file_bytes = file.read()
            file_stream = BytesIO(file_bytes)
            
            # ✅ Pasamos el stream y el nombre del archivo
            upload_result = imagekit.files.upload(
                file=file_stream,
                file_name=file.filename
            )
            
            if hasattr(upload_result, 'url'):
                return upload_result.url
            
            return None
            
        except Exception as e:
            print(f"Error subiendo a ImageKit: {e}")
            return None
"""
    p.write_text(new_code, encoding='utf-8')
    print("✅ ¡Servicio de ImageKit actualizado para enviar BytesIO!")

if __name__ == '__main__':
    main()