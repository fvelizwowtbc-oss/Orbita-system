from pathlib import Path
import shutil

def main():
    p = Path('app/services/imagekit_service.py')
    if not p.exists():
        print("❌ No se encontró imagekit_service.py")
        return
        
    c = p.read_text(encoding='utf-8')
    
    bak = p.with_suffix('.py.bak_v5')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Código adaptado a la nueva SDK (v5+)
    new_code = """from imagekitio import ImageKit
from flask import current_app

class ImageKitService:
    @staticmethod
    def subir_imagen(file):
        \"\"\"Sube una imagen a ImageKit (SDK v5+) y devuelve la URL.\"\"\"
        try:
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY')
            
            if not private_key:
                return None # No configurado

            # ✅ La nueva SDK SOLO acepta private_key en el constructor
            imagekit = ImageKit(private_key=private_key)
            
            # ✅ La subida se hace a través de imagekit.files.upload
            upload_result = imagekit.files.upload(
                file=file,
                file_name=file.filename
            )
            
            # La respuesta trae la URL directamente
            if hasattr(upload_result, 'url'):
                return upload_result.url
            
            return None
            
        except Exception as e:
            print(f"Error subiendo a ImageKit: {e}")
            return None
"""
    p.write_text(new_code, encoding='utf-8')
    print("✅ ¡Servicio de ImageKit actualizado para la SDK v5+!")

if __name__ == '__main__':
    main()