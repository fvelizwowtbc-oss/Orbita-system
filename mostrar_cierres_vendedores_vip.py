import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   MOSTRANDO CIERRES DE VENDEDORES AL USUARIO VIP")
    print("==================================================\n")

    # 1. ACTUALIZAR LA RUTA DEL USUARIO (user.py)
    p_user = Path('app/routes/user.py')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        bak = p_user.with_suffix('.py.bak_cierres_vip')
        if not bak.exists(): shutil.copy2(p_user, bak)

        # Buscar la función caja() y agregar la consulta de cierres de vendedores
        old_caja = """    cierres = CajaTurno.query.filter_by(usuario_id=uid, estado='cerrada').order_by(CajaTurno.cerrada_en.desc()).limit(10).all()
    
    return render_template('user/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasa_bcv=tasa_actual)"""
        
        new_caja = """    # Cierres propios del usuario (VIP)
    cierres = CajaTurno.query.filter_by(usuario_id=uid, estado='cerrada', vendedor_id=None).order_by(CajaTurno.cerrada_en.desc()).limit(10).all()
    
    # ✅ Cierres de los vendedores (turnos cerrados)
    from sqlalchemy.orm import aliased
    from ..models.usuario import Usuario as _Usuario
    vendedor_alias = aliased(_Usuario)
    
    cierres_vendedores_query = db.session.query(CajaTurno, vendedor_alias.nombre.label('vendedor_nombre')).\\
        join(vendedor_alias, CajaTurno.vendedor_id == vendedor_alias.id).\\
        filter(CajaTurno.usuario_id == uid, CajaTurno.estado == 'cerrada').\\
        order_by(CajaTurno.cerrada_en.desc()).limit(20).all()
    
    # Formatear los datos para el template
    cierres_vendedores = []
    for cierre, vendedor_nombre in cierres_vendedores_query:
        cierres_vendedores.append({
            'cierre': cierre,
            'vendedor_nombre': vendedor_nombre
        })
    
    return render_template('user/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasa_bcv=tasa_actual, cierres_vendedores=cierres_vendedores)"""
        
        if old_caja in c:
            c = c.replace(old_caja, new_caja)
            p_user.write_text(c, encoding='utf-8')
            print("✅ user.py: Ahora consulta los cierres de los vendedores.")
        else:
            print("⚠️ No se encontró el bloque exacto en la función caja(). Revisa manualmente.")

    # 2. ACTUALIZAR EL HTML DEL USUARIO (user/caja.html)
    p_html = Path('app/templates/user/caja.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_cierres_vip')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # Agregar una nueva sección debajo de "Cierres anteriores"
        # Buscamos el cierre del bloque de la columna derecha (donde está el historial del usuario)
        old_columna = """        <div class="p-5">
            {% if cierres_anteriores %}
            <div class="space-y-3">
                {% for cierre in cierres_anteriores %}
                <div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">"""
        
        new_columna = """        <div class="p-5 space-y-6">
            <!-- Cierres del usuario (VIP) -->
            <div>
                <h4 class="text-sm font-bold text-slate-700 mb-3 border-b pb-2">Mis Cierres</h4>
                {% if cierres_anteriores %}
                <div class="space-y-3">
                    {% for cierre in cierres_anteriores %}
                    <div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">"""
        
        # Necesitamos cerrar correctamente los bloques (esto es complejo de hacer con replace simple)
        # Mejor inyectamos la nueva sección de vendedores al final de la tarjeta de cierres
        # Buscamos el final de la tarjeta de "Cierres anteriores" del usuario
        
        # Para evitar romper el HTML, vamos a agregar una nueva columna o tarjeta al final del grid.
        # Buscamos el cierre del grid principal (después de la columna derecha)
        
        # Una forma más segura es agregar una nueva columna completa al final.
        marker_fin_grid = "</div>\n</div>\n\n{% if caja_abierta %}"
        
        nueva_columna_html = """
    <!-- ✅ NUEVA COLUMNA: Cierres de Vendedores -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 mt-6">
        <div class="px-5 py-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
            <h3 class="font-bold text-slate-800 flex items-center gap-2">
                <i class="fas fa-users text-[#dc2743]"></i> Cierres de Vendedores
            </h3>
        </div>
        <div class="p-5">
            {% if cierres_vendedores %}
            <div class="space-y-3 max-h-[500px] overflow-y-auto">
                {% for item in cierres_vendedores %}
                {% set cierre = item.cierre %}
                <div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">
                    <!-- Cabecera -->
                    <div class="flex justify-between items-center border-b border-slate-100 pb-2 mb-3">
                        <p class="text-sm font-bold text-slate-800 flex items-center gap-2">
                            <i class="fas fa-user-tie text-slate-400"></i> {{ item.vendedor_nombre }}
                        </p>
                        <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                            {{ cierre.cerrada_en.strftime('%d/%m/%Y') }} - Tasa: {{ "%.2f"|format(cierre.tasa_cierre|float or 0) }}
                        </span>
                    </div>
                    
                    <!-- Desglose -->
                    <div class="space-y-2 text-xs mb-3">
                        <div class="flex justify-between items-center bg-slate-50 p-1.5 rounded border border-slate-100">
                            <span class="text-slate-500 font-medium"><i class="fas fa-lock text-slate-400 w-4"></i> Base Inicial:</span>
                            <span class="text-slate-700">${{ "%.2f"|format(cierre.saldo_inicial_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.saldo_inicial_bs|float or 0) }}</span>
                        </div>
                        <div class="flex justify-between items-center bg-emerald-50 p-1.5 rounded border border-emerald-100">
                            <span class="text-emerald-700 font-medium"><i class="fas fa-shopping-cart text-emerald-500 w-4"></i> Ventas del Turno:</span>
                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}</span>
                        </div>
                        <div class="flex justify-between items-center bg-blue-50 p-1.5 rounded border border-blue-100">
                            <span class="text-blue-700 font-medium"><i class="fas fa-hand-holding-usd text-blue-500 w-4"></i> Físico Contado:</span>
                            <span class="text-blue-800">${{ "%.2f"|format(cierre.saldo_real_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.saldo_real_bs|float or 0) }}</span>
                        </div>
                    </div>
                    
                    <!-- Diferencia -->
                    <div class="flex justify-between items-center text-xs pt-2 border-t border-slate-200">
                        <span class="text-slate-600 font-bold">Diferencia:</span>
                        <div class="text-right">
                            <span class="font-bold block {% if (cierre.diferencia_usd|float or 0) < 0 %}text-red-600{% else %}text-emerald-600{% endif %}">
                                ${{ "%.2f"|format(cierre.diferencia_usd|float or 0) }}
                            </span>
                            <span class="font-bold block {% if (cierre.diferencia_bs|float or 0) < 0 %}text-red-600{% else %}text-emerald-600{% endif %}">
                                Bs. {{ "%.2f"|format(cierre.diferencia_bs|float or 0) }}
                            </span>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="text-center py-8 text-slate-400">
                <i class="fas fa-users-slash text-4xl mb-2 opacity-50"></i>
                <p class="text-sm">Aún no hay cierres de vendedores</p>
            </div>
            {% endif %}
        </div>
    </div>
"""
        
        if marker_fin_grid in c:
            c = c.replace(marker_fin_grid, marker_fin_grid + nueva_columna_html)
            p_html.write_text(c, encoding='utf-8')
            print("✅ user/caja.html: Sección de cierres de vendedores agregada.")
        else:
            print("⚠️ No se encontró el marcador de cierre del grid. Revisa el HTML manualmente.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()