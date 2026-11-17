from pathlib import Path
import shutil

def main():
    print("\n==================================================")
    print("   LIMPIANDO SIDEBAR DEL VENDEDOR (RUTAS VÁLIDAS)")
    print("==================================================\n")

    p = Path('app/templates/vendedor/_sidebar.html')
    if not p.exists():
        print("❌ No se encontró vendedor/_sidebar.html")
        return

    bak = p.with_suffix('.html.bak_limpiar')
    if not bak.exists():
        shutil.copy2(p, bak)

    nuevo_sidebar = """<a href="{{ url_for('vendedor.dashboard') }}" class="drawer-link {% if request.endpoint == 'vendedor.dashboard' %}active{% endif %}">
    <i class="fas fa-chart-pie"></i>
    <span>Dashboard</span>
</a>

<a href="{{ url_for('vendedor.ventas') }}" class="drawer-link {% if request.endpoint == 'vendedor.ventas' %}active{% endif %}">
    <i class="fas fa-shopping-bag"></i>
    <span>Ventas</span>
</a>

<a href="{{ url_for('vendedor.inventario') }}" class="drawer-link {% if request.endpoint == 'vendedor.inventario' %}active{% endif %}">
    <i class="fas fa-box"></i>
    <span>Inventario</span>
</a>

<a href="{{ url_for('vendedor.gastos_listado') }}" class="drawer-link {% if request.endpoint == 'vendedor.gastos_listado' %}active{% endif %}">
    <i class="fas fa-wallet"></i>
    <span>Gastos</span>
</a>

<a href="{{ url_for('vendedor.cashea_listado') }}" class="drawer-link {% if request.endpoint == 'vendedor.cashea_listado' %}active{% endif %}">
    <i class="fas fa-hand-holding-usd"></i>
    <span>Cashea</span>
</a>

{% if vendedor_puede_ver_clientes %}
<a href="{{ url_for('vendedor.clientes') }}" class="drawer-link {% if request.endpoint == 'vendedor.clientes' %}active{% endif %}">
    <i class="fas fa-users"></i>
    <span>Clientes</span>
</a>
{% endif %}

{% if vendedor_puede_ver_facturas %}
<a href="{{ url_for('vendedor.facturas') }}" class="drawer-link {% if request.endpoint == 'vendedor.facturas' %}active{% endif %}">
    <i class="fas fa-file-invoice"></i>
    <span>Facturas</span>
</a>
{% endif %}

<a href="{{ url_for('vendedor.reportes') }}" class="drawer-link {% if request.endpoint == 'vendedor.reportes' %}active{% endif %}">
    <i class="fas fa-chart-line"></i>
    <span>Reportes</span>
</a>"""

    p.write_text(nuevo_sidebar, encoding='utf-8')
    print("✅ Sidebar del vendedor limpiado. Solo contiene rutas válidas de vendedor.")

if __name__ == '__main__':
    main()