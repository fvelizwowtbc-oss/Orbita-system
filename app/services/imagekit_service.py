from imagekitio import ImageKit
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
