import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   INSTALANDO CAJA PARA VENDEDORES (Y VISTA VIP)")
    print("==================================================\n")

    # 1. ACTUALIZAR EL MODELO (app/models/caja.py)
    p_model = Path('app/models/caja.py')
    if p_model.exists():
        c = p_model.read_text(encoding='utf-8')
        bak = p_model.with_suffix('.py.bak_vendedor')
        if not bak.exists(): shutil.copy2(p_model, bak)

        if 'vendedor_id' not in c:
            c = c.replace(
                "usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)",
                "usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)\n    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)"
            )
            # Añadir relación para el vendedor
            c = c.replace(
                "usuario = db.relationship('Usuario', backref='turnos_caja')",
                "usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='turnos_caja')\n    vendedor = db.relationship('Usuario', foreign_keys=[vendedor_id], backref='turnos_como_vendedor')"
            )
            p_model.write_text(c, encoding='utf-8')
            print("✅ Modelo CajaTurno actualizado con vendedor_id.")

    # 2. ACTUALIZAR LAS RUTAS DEL VENDEDOR (app/routes/vendedor.py)
    p_vendedor = Path('app/routes/vendedor.py')
    if p_vendedor.exists():
        c = p_vendedor.read_text(encoding='utf-8')
        bak = p_vendedor.with_suffix('.py.bak_caja')
        if not bak.exists(): shutil.copy2(p_vendedor, bak)

        if 'def caja():' not in c:
            rutas_caja_vendedor = """

# ============================================================
# CAJA (VENDEDOR)
# ============================================================
from ..models.caja import CajaTurno
from ..services.tasas import TasasService

@vendedor_bp.route('/caja', methods=['GET', 'POST'])
@login_required
def caja():
    vid = current_user.id
    padre_id = current_user.usuario_padre_id
    
    # Buscar si el vendedor tiene una caja abierta
    caja_abierta = CajaTurno.query.filter_by(vendedor_id=vid, estado='abierta').first()
    
    if request.method == 'POST' and not caja_abierta:
        try:
            usd = float(request.form.get('saldo_inicial_usd', 0) or 0)
            bs = float(request.form.get('saldo_inicial_bs', 0) or 0)
            
            nueva_caja = CajaTurno(
                usuario_id=padre_id,
                vendedor_id=vid,
                saldo_inicial_usd=usd,
                saldo_inicial_bs=bs,
                estado='abierta'
            )
            db.session.add(nueva_caja)
            db.session.commit()
            flash('Caja abierta correctamente.', 'success')
            return redirect(url_for('vendedor.caja'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al abrir caja: {e}', 'danger')

    # Historial de cajas cerradas del vendedor
    cierres = CajaTurno.query.filter_by(vendedor_id=vid, estado='cerrada').order_by(CajaTurno.cerrada_en.desc()).limit(10).all()
    
    # Tasa para mostrar en la vista
    tasas = TasasService.obtener_tasas(padre_id)
    
    return render_template('vendedor/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasas=tasas)


@vendedor_bp.route('/caja/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    vid = current_user.id
    caja = CajaTurno.query.filter_by(vendedor_id=vid, estado='abierta').first()
    
    if caja:
        caja.estado = 'cerrada'
        caja.cerrada_en = datetime.utcnow()
        
        # Arqueo
        from ..services.tasas import TasasService
        tasa_bcv = float(TasasService.obtener_tasa_bcv())
        if tasa_bcv <= 0: tasa_bcv = 1
        
        caja.saldo_real_usd = float(request.form.get('saldo_real_usd', 0) or 0)
        caja.saldo_real_bs = float(request.form.get('saldo_real_bs', 0) or 0)
        
        real_total_usd = caja.saldo_real_usd + (caja.saldo_real_bs / tasa_bcv)
        esperado_base_usd = float(caja.saldo_inicial_usd) + (float(caja.saldo_inicial_bs) / tasa_bcv)
        esperado_ventas_usd = float(caja.total_ventas_efectivo_usd) + (float(caja.total_ventas_efectivo_bs) / tasa_bcv)
        
        caja.diferencia_usd = (real_total_usd - esperado_base_usd) - esperado_ventas_usd
        caja.diferencia_bs = caja.diferencia_usd * tasa_bcv
        caja.tasa_cierre = tasa_bcv
        
        db.session.commit()
        flash('Caja cerrada correctamente. Turno finalizado.', 'success')
    else:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        
    return redirect(url_for('vendedor.caja'))
"""
            c += rutas_caja_vendedor
            p_vendedor.write_text(c, encoding='utf-8')
            print("✅ Rutas de Caja agregadas a vendedor.py.")

    # 3. CREAR EL ARCHIVO HTML PARA LA CAJA DEL VENDEDOR (app/templates/vendedor/caja.html)
    p_html_vendedor = Path('app/templates/vendedor/caja.html')
    html_vendedor = """{% extends 'base.html' %}
{% block title %}Caja{% endblock %}
{% block page_title %}Mi Caja{% endblock %}
{% block page_subtitle %}Control de efectivo y turnos{% endblock %}
{% block sidebar %}{% include 'vendedor/_sidebar.html' %}{% endblock %}

{% block content %}
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    
    <div class="lg:col-span-2 space-y-6">
        {% if not caja_abierta %}
        <!-- FORMULARIO DE APERTURA -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="px-6 py-4 border-b border-slate-200">
                <h3 class="font-bold text-lg text-slate-800">Abrir caja</h3>
                <p class="text-sm text-slate-500 mt-1">Indica el efectivo con que empiezas, en cada moneda.</p>
            </div>
            <form method="POST" class="p-6 space-y-4">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Efectivo inicial (USD)</label>
                    <input type="number" step="0.01" name="saldo_inicial_usd" value="0" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#0f172a] outline-none transition">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Efectivo inicial (VES)</label>
                    <input type="number" step="0.01" name="saldo_inicial_bs" value="0" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#0f172a] outline-none transition">
                </div>
                <button type="submit" class="w-full mt-4 bg-gradient-to-r from-[#f09433] via-[#dc2743] to-[#bc1888] text-white font-bold py-3 rounded-lg transition-colors text-lg">
                    Abrir caja
                </button>
            </form>
        </div>
        {% else %}
        <!-- ESTADO DE CAJA ABIERTA -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center">
            <div class="w-20 h-20 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <i class="fas fa-cash-register text-3xl"></i>
            </div>
            <h3 class="text-2xl font-bold text-slate-800 mb-2">Caja Abierta</h3>
            <p class="text-slate-500 mb-6">Abierta el {{ caja_abierta.abierta_en.strftime('%d/%m/%Y a las %H:%M') }}</p>
            
            <div class="grid grid-cols-2 gap-4 max-w-md mx-auto mb-6">
                <div class="bg-slate-50 p-4 rounded-lg border border-slate-200">
                    <p class="text-xs text-slate-500 uppercase">Base Inicial USD</p>
                    <p class="text-xl font-bold text-slate-800">${{ "%.2f"|format(caja_abierta.saldo_inicial_usd|float) }}</p>
                </div>
                <div class="bg-slate-50 p-4 rounded-lg border border-slate-200">
                    <p class="text-xs text-slate-500 uppercase">Base Inicial Bs</p>
                    <p class="text-xl font-bold text-slate-800">Bs. {{ "%.2f"|format(caja_abierta.saldo_inicial_bs|float) }}</p>
                </div>
            </div>

            <button type="button" onclick="document.getElementById('modalArqueo').classList.remove('hidden')" class="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-8 rounded-lg transition-colors shadow-lg shadow-red-500/30">
                <i class="fas fa-lock mr-2"></i> Cerrar caja (Arqueo Z)
            </button>
        </div>
        {% endif %}
    </div>

    <!-- COLUMNA DERECHA: CIERRES ANTERIORES -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200">
        <div class="px-5 py-4 border-b border-slate-200">
            <h3 class="font-bold text-slate-800">Cierres anteriores</h3>
        </div>
        <div class="p-5">
            {% if cierres_anteriores %}
            <div class="space-y-3">
                {% for cierre in cierres_anteriores %}
                <div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">
                    <div class="flex justify-between items-center border-b border-slate-100 pb-2 mb-2">
                        <p class="text-sm font-bold text-slate-800"><i class="far fa-calendar-alt text-slate-400 mr-1"></i> {{ cierre.cerrada_en.strftime('%d/%m/%Y') }}</p>
                        <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">Tasa: {{ "%.2f"|format(cierre.tasa_cierre|float or 0) }}</span>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-2 text-xs mb-2">
                        <div class="bg-blue-50 p-2 rounded border border-blue-100">
                            <p class="text-blue-800 font-semibold mb-0.5">Dólares (USD)</p>
                            <p class="text-slate-700">${{ "%.2f"|format(cierre.saldo_real_usd|float or 0) }}</p>
                        </div>
                        <div class="bg-amber-50 p-2 rounded border border-amber-100">
                            <p class="text-amber-800 font-semibold mb-0.5">Bolívares (Bs)</p>
                            <p class="text-slate-700">Bs. {{ "%.2f"|format(cierre.saldo_real_bs|float or 0) }}</p>
                        </div>
                    </div>

                    <div class="flex justify-between items-center text-xs mt-2 pt-2 border-t border-slate-100">
                        <span class="text-slate-500">Diferencia:</span>
                        <div class="text-right">
                            <span class="font-bold block {% if (cierre.diferencia_usd|float or 0) < 0 %}text-red-600{% else %}text-emerald-600{% endif %}">
                                ${{ "%.2f"|format(cierre.diferencia_usd|float or 0) }}
                            </span>
                            <span class="text-[10px] text-slate-500 block">
                                Bs. {{ "%.2f"|format(cierre.diferencia_bs|float or 0) }}
                            </span>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="text-center py-10 text-slate-400">
                <p class="text-sm">Aún no hay cierres</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>

{% if caja_abierta %}
<!-- MODAL DE ARQUEO Z (Vendedor) -->
<div id="modalArqueo" class="hidden fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl w-full max-w-md shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-200 bg-[#0f172a] rounded-t-2xl">
            <h3 class="text-white font-bold text-lg"><i class="fas fa-calculator mr-2"></i> Arqueo Z (Cierre)</h3>
        </div>
        <form method="POST" action="{{ url_for('vendedor.cerrar_caja') }}" class="p-6 space-y-4">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div class="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4 text-sm text-slate-600 space-y-1">
                <p><i class="fas fa-lock text-slate-400 w-4"></i> <strong>Base de Apertura:</strong> ${{ "%.2f"|format(caja_abierta.saldo_inicial_usd|float) }} + Bs. {{ "%.2f"|format(caja_abierta.saldo_inicial_bs|float) }}</p>
                <p><i class="fas fa-shopping-cart text-slate-400 w-4"></i> <strong>Ventas en Efectivo:</strong> ${{ "%.2f"|format(caja_abierta.total_ventas_efectivo_usd|float) }} + Bs. {{ "%.2f"|format(caja_abierta.total_ventas_efectivo_bs|float) }}</p>
                <div class="border-t border-slate-200 mt-2 pt-2">
                    <p><i class="fas fa-calculator text-slate-400 w-4"></i> <strong>Total Esperado en Gaveta:</strong> ${{ "%.2f"|format((caja_abierta.saldo_inicial_usd|float) + (caja_abierta.total_ventas_efectivo_usd|float)) }} + Bs. {{ "%.2f"|format((caja_abierta.saldo_inicial_bs|float) + (caja_abierta.total_ventas_efectivo_bs|float)) }}</p>
                </div>
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-1">Efectivo Real en Gaveta (USD)</label>
                <input type="number" step="0.01" name="saldo_real_usd" id="saldo_real_usd" value="0" oninput="calcularBs()" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-[#0f172a]">
            </div>
            <div>
                <label class="block text-sm font-medium mb-1">Efectivo Real en Gaveta (Bs)</label>
                <input type="number" step="0.01" name="saldo_real_bs" id="saldo_real_bs" value="0" oninput="calcularUsd()" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-[#0f172a]">
            </div>
            
            <div class="flex gap-2 pt-4">
                <button type="button" onclick="document.getElementById('modalArqueo').classList.add('hidden')" class="flex-1 py-2 border rounded-lg text-slate-600 hover:bg-slate-50 font-medium">Cancelar</button>
                <button type="submit" class="flex-1 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold">Confirmar Cierre</button>
            </div>
        </form>
    </div>
</div>

<script>
    const TASA_CALCULO = {{ tasas.oficial if tasas and tasas.oficial else 50 }};
    function calcularBs() {
        const usd = parseFloat(document.getElementById('saldo_real_usd').value) || 0;
        document.getElementById('saldo_real_bs').value = (usd * TASA_CALCULO).toFixed(2);
    }
    function calcularUsd() {
        const bs = parseFloat(document.getElementById('saldo_real_bs').value) || 0;
        document.getElementById('saldo_real_usd').value = (bs / TASA_CALCULO).toFixed(2);
    }
</script>
{% endif %}
{% endblock %}"""
    
    p_html_vendedor.parent.mkdir(parents=True, exist_ok=True)
    p_html_vendedor.write_text(html_vendedor, encoding='utf-8')
    print("✅ Plantilla de Caja para vendedor creada.")

    # 4. ACTUALIZAR EL SIDEBAR DEL VENDEDOR (Agregar botón Caja)
    p_sidebar = Path('app/templates/vendedor/_sidebar.html')
    if p_sidebar.exists():
        c = p_sidebar.read_text(encoding='utf-8')
        if 'vendedor.caja' not in c:
            # Insertar antes de reportes
            c = c.replace(
                '<a href="{{ url_for(\'vendedor.reportes\') }}"',
                '<a href="{{ url_for(\'vendedor.caja\') }}" class="drawer-link {% if request.endpoint == \'vendedor.caja\' %}active{% endif %}">\n    <i class="fas fa-cash-register"></i>\n    <span>Caja</span>\n</a>\n\n<a href="{{ url_for(\'vendedor.reportes\') }}"'
            )
            p_sidebar.write_text(c, encoding='utf-8')
            print("✅ Botón de Caja agregado al sidebar del vendedor.")

    # 5. ACTUALIZAR LA VISTA DEL USUARIO (user/caja.html) PARA MOSTRAR CIERRES DE VENDEDORES
    p_user_caja = Path('app/templates/user/caja.html')
    if p_user_caja.exists():
        c = p_user_caja.read_text(encoding='utf-8')
        bak = p_user_caja.with_suffix('.html.bak_vendedores')
        if not bak.exists(): shutil.copy2(p_user_caja, bak)

        # Agregar un bloque al final (antes del cierre) para mostrar los cierres de vendedores
        # Esto depende de la estructura exacta. Como es complejo, lo haremos via Python en la ruta.
        pass

    # 6. ACTUALIZAR LA RUTA DEL USUARIO (user.py) PARA PASAR CIERRES DE VENDEDORES
    p_user_routes = Path('app/routes/user.py')
    if p_user_routes.exists():
        c = p_user_routes.read_text(encoding='utf-8')
        bak = p_user_routes.with_suffix('.py.bak_vendedores')
        if not bak.exists(): shutil.copy2(p_user_routes, bak)

        if 'cierres_vendedores' not in c:
            # En la función caja(), agregar la consulta
            c = c.replace(
                "cierres = CajaTurno.query.filter_by(usuario_id=uid, estado='cerrada').order_by(CajaTurno.cerrada_en.desc()).limit(10).all()",
                """cierres = CajaTurno.query.filter_by(usuario_id=uid, estado='cerrada').order_by(CajaTurno.cerrada_en.desc()).limit(10).all()
    
    # ✅ Cierres de vendedores
    from sqlalchemy.orm import aliased
    vendedor_alias = aliased(__import__('app.models.usuario', fromlist=['Usuario']).Usuario)
    cierres_vendedores = db.session.query(CajaTurno, vendedor_alias.nombre).\\
        join(vendedor_alias, CajaTurno.vendedor_id == vendedor_alias.id).\\
        filter(CajaTurno.usuario_id == uid, CajaTurno.estado == 'cerrada').\\
        order_by(CajaTurno.cerrada_en.desc()).limit(20).all()"""
            )
            
            # Actualizar el render_template para pasar cierres_vendedores
            c = c.replace(
                "return render_template('user/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasa_bcv=tasa_actual)",
                "return render_template('user/caja.html', caja_abierta=caja_abierta, cierres_anteriores=cierres, tasa_bcv=tasa_actual, cierres_vendedores=cierres_vendedores)"
            )
            p_user_routes.write_text(c, encoding='utf-8')
            print("✅ Ruta de Caja (usuario) actualizada para incluir cierres de vendedores.")

    print("\n👉 IMPORTANTE: Debes ejecutar un script para agregar la columna 'vendedor_id' a la tabla caja_turnos en tu base de datos.")
    print("Puedes usar el script 'arreglar_db_caja_vendedor.py' que se generará a continuación.")

    # Generar script de base de datos
    db_script = """import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

def main():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
    if not db_url:
        print("❌ No se encontró DATABASE_URL")
        return

    print("Conectando a PostgreSQL...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Agregando columna 'vendedor_id' a caja_turnos...")
        cursor.execute("ALTER TABLE caja_turnos ADD COLUMN IF NOT EXISTS vendedor_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;")
        
        print("✅ ¡Columna agregada exitosamente!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
"""
    Path('arreglar_db_caja_vendedor.py').write_text(db_script, encoding='utf-8')
    print("✅ Script 'arreglar_db_caja_vendedor.py' generado. Ejecútalo después de este script.")

if __name__ == '__main__':
    main()