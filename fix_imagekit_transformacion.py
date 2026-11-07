from pathlib import Path
import shutil

def main():
    p = Path('app/services/imagekit_service.py')
    if not p.exists():
        print("❌ No se encontró imagekit_service.py")
        return
        
    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_transform')
    if not bak.exists():
        shutil.copy2(p, bak)

    new_code = """from imagekitio import ImageKit
from flask import current_app
from io import BytesIO

class ImageKitService:
    @staticmethod
    def subir_imagen(file):
        try:
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY')
            if not private_key:
                return None

            imagekit = ImageKit(private_key=private_key)
            
            file_bytes = file.read()
            file_stream = BytesIO(file_bytes)
            
            # ✅ Agregamos compresión y redimensionado para no gastar espacio
            upload_result = imagekit.files.upload(
                file=file_stream,
                file_name=file.filename,
                options={
                    "is_private_file": False,
                    "use_unique_file_name": True,
                    "transformation": {
                        "pre": "w-500,h-500,c-maintain_ratio,q-80,f-webp"
                    }
                }
            )
            
            if hasattr(upload_result, 'url'):
                return upload_result.url
            return None
            
        except Exception as e:
            print(f"Error subiendo a ImageKit: {e}")
            return None
"""
    p.write_text(new_code, encoding='utf-8')
    print("✅ ¡Servicio de ImageKit actualizado con redimensionado y compresión!")

if __name__ == '__main__':
    main()