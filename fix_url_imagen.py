from pathlib import Path
import shutil

def main():
    p = Path('app/models/producto.py')
    if not p.exists():
        print("❌ No se encontró producto.py")
        return
        
    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_url')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar la propiedad imagen_url y reemplazarla por una versión segura
    import re
    patron = re.compile(r"    @property\n    def imagen_url\(self\):.*?return f'/uploads/\{self\.usuario_id\}/\{self\.imagen_principal\}'", re.DOTALL)
    
    nueva_prop = """    @property
    def imagen_url(self):
        if not self.imagen_principal:
            return None
        # ✅ Si ya es una URL de internet (ImageKit), la devolvemos tal cual
        if self.imagen_principal.startswith('http://') or self.imagen_principal.startswith('https://'):
            return self.imagen_principal
        # Si es un archivo local, le agregamos la ruta
        return f'/uploads/{self.usuario_id}/{self.imagen_principal}'"""

    if patron.search(c):
        c = patron.sub(nueva_prop, c)
        p.write_text(c, encoding='utf-8')
        print("✅ ¡Propiedad imagen_url corregida! Ahora detecta URLs de ImageKit.")
    else:
        # Intento alternativo si el regex falla por indentación
        old = """    @property
    def imagen_url(self):
        if self.imagen_principal:
            return f'/uploads/{self.usuario_id}/{self.imagen_principal}'
        return None"""
        if old in c:
            c = c.replace(old, nueva_prop)
            p.write_text(c, encoding='utf-8')
            print("✅ ¡Propiedad imagen_url corregida (método alternativo)!")
        else:
            print("⚠️ No se encontró la propiedad imagen_url. Revisa el archivo manualmente.")

if __name__ == '__main__':
    main()