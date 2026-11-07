from pathlib import Path
import shutil

def main():
    p = Path('app/__init__.py')
    if not p.exists():
        print("❌ No se encontró app/__init__.py")
        return
        
    c = p.read_text(encoding='utf-8')
    
    bak = p.with_suffix('.py.bak_csp')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar la línea de img-src en el CSP y agregar el dominio de ImageKit
    old_csp = "img-src 'self' data: blob:; "
    new_csp = "img-src 'self' data: blob: https://ik.imagekit.io; "

    if old_csp in c:
        c = c.replace(old_csp, new_csp)
        p.write_text(c, encoding='utf-8')
        print("✅ ¡CSP actualizado! Ahora permite imágenes de ImageKit.")
    else:
        print("⚠️ No se encontró la línea exacta de img-src. Buscando variantes...")
        if "img-src" in c:
            # Intento con otras variantes de espacios
            c = c.replace("img-src 'self' data: blob:", "img-src 'self' data: blob: https://ik.imagekit.io")
            p.write_text(c, encoding='utf-8')
            print("✅ CSP actualizado por método alternativo.")
        else:
            print("❌ No se encontró la regla CSP. Revisa el archivo manualmente.")

if __name__ == '__main__':
    main()