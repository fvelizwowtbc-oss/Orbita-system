import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   IGUALANDO VENDEDOR AL USUARIO (COPIA EXACTA)")
    print("==================================================\n")

    # 1. RUTAS DE LOS ARCHIVOS
    p_user_ventas = Path('app/templates/user/ventas.html')
    p_vend_ventas = Path('app/templates/vendedor/ventas.html')
    p_user_sidebar = Path('app/templates/user/_sidebar.html')
    p_vend_sidebar = Path('app/templates/vendedor/_sidebar.html')

    # 2. COPIAR EL SIDEBAR DEL USUARIO AL VENDEDOR (con pequeñas adaptaciones)
    if p_user_sidebar.exists() and p_vend_sidebar.exists():
        c = p_user_sidebar.read_text(encoding='utf-8')
        # Cambiar las rutas de user a vendedor
        c = c.replace("url_for('user.", "url_for('vendedor.")
        
        # Filtrar opciones que el vendedor no debe ver (Caja, Scanners, Mis Vendedores)
        lineas = c.split('\n')
        nuevas_lineas = []
        omitir = False
        for linea in lineas:
            if 'user.caja' in linea or 'vip.scanners_lista' in linea or 'vip.lista' in linea or 'Mis Vendedores' in linea or 'Scanners Pasillo' in linea or 'Caja' in linea:
                omitir = True
                continue
            if omitir and '</a>' in linea:
                omitir = False
                continue
            if not omitir:
                nuevas_lineas.append(linea)
        
        # Guardar
        p_vend_sidebar.write_text('\n'.join(nuevas_lineas), encoding='utf-8')
        print("✅ vendedor/_sidebar.html actualizado con el diseño del usuario.")

    # 3. COPIAR EL ARCHIVO ventas.html DEL USUARIO AL VENDEDOR
    if p_user_ventas.exists() and p_vend_ventas.exists():
        c = p_user_ventas.read_text(encoding='utf-8')
        
        # A. Cambiar el título y subtítulo para que sea el de vendedor
        c = c.replace('{% block title %}Ventas{% endblock %}', '{% block title %}Ventas - Vendedor{% endblock %}')
        c = c.replace('{% block page_title %}Punto de Venta{% endblock %}', '{% block page_title %}Punto de Venta{% endblock %}')
        
        # B. Cambiar las rutas del backend (fetch, url_for, etc.)
        c = c.replace("url_for('user.", "url_for('vendedor.")
        c = c.replace("'/user/ventas/procesar'", "'/vendedor/ventas/procesar'")
        c = c.replace("'/user/ventas/", "'/vendedor/ventas/")
        c = c.replace("'/user/producto/", "'/vendedor/producto/")
        c = c.replace("'/user/factura/", "'/vendedor/factura/")
        c = c.replace("'/user/facturas/", "'/vendedor/facturas/")
        
        # C. Reemplazar variables específicas si es necesario
        # (El vendedor usa las mismas variables que el usuario en ventas, así que no hace falta cambiar)
        
        # D. Guardar el archivo
        p_vend_ventas.write_text(c, encoding='utf-8')
        print("✅ vendedor/ventas.html copiado exactamente del usuario.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")
    print("Si sigues viendo lo mismo, abre una ventana de incógnito y entra como vendedor.")

if __name__ == '__main__':
    main()