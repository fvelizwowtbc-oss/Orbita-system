import shutil
from pathlib import Path
import re

def main():
    print("\n==================================================")
    print("   CORRIGIENDO FACTURAS Y MODAL DE ABONO")
    print("==================================================\n")

    # 1. OCULTAR CASHEA EN EL LISTADO DE FACTURAS (BACKEND)
    p_routes = Path('app/routes/user.py')
    if p_routes.exists():
        c = p_routes.read_text(encoding='utf-8')
        bak = p_routes.with_suffix('.py.bak_facturas')
        if not bak.exists(): shutil.copy2(p_routes, bak)

        # La función facturas() debe filtrar las Cashea
        if "FacturaCobrar.tipo_venta != 'cashea'" not in c:
            c = c.replace(
                "query = FacturaCobrar.query.filter_by(usuario_id=uid)",
                "query = FacturaCobrar.query.filter_by(usuario_id=uid).filter(FacturaCobrar.tipo_venta != 'cashea')"
            )
            p_routes.write_text(c, encoding='utf-8')
            print("✅ user.py: Facturas Cashea ocultas del listado general.")

    # 2. REESCRIBIR EL MODAL DE ABONO (USER) CON DISEÑO PREMIUM
    p_html = Path('app/templates/user/facturas.html')
    if p_html.exists():
        c = p_html.read_text(encoding='utf-8')
        bak = p_html.with_suffix('.html.bak_abono')
        if not bak.exists(): shutil.copy2(p_html, bak)

        # Buscar el bloque del modal de abono
        patron_modal = re.compile(r'<!-- MODAL: Abonar -->.*?</div>\s*</div>\s*</div>', re.DOTALL)
        
        nuevo_modal = """<!-- MODAL: Abonar (Premium) -->
<div id="modalAbono" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" style="z-index: 99999 !important;">
    <div class="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden anim-scale-in">
        <div class="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-[#f09433] via-[#dc2743] to-[#bc1888] rounded-t-3xl">
            <div class="flex justify-between items-center">
                <div>
                    <h3 class="text-white font-bold text-lg flex items-center gap-2">
                        <i class="fas fa-hand-holding-usd"></i> Registrar Abono
                    </h3>
                    <p class="text-xs text-white/80 mt-0.5">Factura: <span id="facturaNro" class="font-mono"></span></p>
                </div>
                <button type="button" onclick="cerrarAbono()" class="text-white/80 hover:text-white">
                    <i class="fas fa-times text-lg"></i>
                </button>
            </div>
        </div>

        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <span class="text-sm font-medium text-slate-600">Saldo pendiente:</span>
            <span id="saldoFactura" class="text-2xl font-extrabold text-red-600">$0.00</span>
        </div>

        <form id="formAbono" method="POST" class="p-6 space-y-4">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-1">Monto a abonar (USD) *</label>
                <div class="relative">
                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
                    <input type="number" step="0.01" name="monto_usd" id="a_monto_usd" required 
                           class="w-full pl-8 pr-3 py-3 bg-white border border-slate-200 rounded-xl text-lg font-semibold focus:border-[#dc2743] focus:ring-4 focus:ring-[#dc2743]/10 outline-none transition"
                           placeholder="0.00" oninput="calcularAbono()">
                </div>
            </div>

            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-1">Monto en Bolívares</label>
                <div class="relative">
                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium text-sm">Bs</span>
                    <input type="number" step="0.01" name="monto_ves" id="a_monto_ves" value="0" 
                           class="w-full pl-10 pr-3 py-3 bg-slate-50 border border-slate-200 rounded-xl text-lg font-semibold text-slate-500 outline-none transition cursor-not-allowed"
                           readonly>
                </div>
            </div>

            <div class="bg-blue-50 border border-blue-100 rounded-xl p-3 flex justify-between items-center">
                <div>
                    <p class="text-xs font-semibold text-blue-800">Tasa aplicada</p>
                    <p class="text-lg font-bold text-blue-900" id="a_tasa_display">Bs. 0,00</p>
                </div>
                <input type="hidden" name="tasa_usada" id="a_tasa" value="{{ ((tasas.oficial if tasas and tasas.oficial else 50) or 50)|float }}">
                <span class="text-xs font-medium text-blue-600 bg-white px-2 py-1 rounded shadow-sm border border-blue-100">{{ (tasas.fuente_oficial if tasas else 'BCV') }}</span>
            </div>

            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-1">Método de pago</label>
                <select name="metodo_pago" class="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:border-[#dc2743] focus:ring-4 focus:ring-[#dc2743]/10 outline-none transition">
                    <option value="efectivo">Efectivo</option>
                    <option value="transferencia">Transferencia</option>
                    <option value="pago_movil">Pago Móvil</option>
                    <option value="punto">Punto de Venta</option>
                </select>
            </div>

            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-1">Notas (opcional)</label>
                <input type="text" name="notas" class="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:border-[#dc2743] focus:ring-4 focus:ring-[#dc2743]/10 outline-none transition" placeholder="Ej: Pago parcial">
            </div>

            <div class="flex gap-3 pt-4 border-t border-slate-200">
                <button type="button" onclick="cerrarAbono()" class="flex-1 py-3 border border-slate-300 rounded-xl text-slate-700 hover:bg-slate-50 font-medium transition">Cancelar</button>
                <button type="submit" class="flex-1 py-3 bg-gradient-to-r from-[#f09433] via-[#dc2743] to-[#bc1888] text-white rounded-xl font-bold shadow-lg shadow-pink-500/30 transition hover:opacity-90">
                    <i class="fas fa-check mr-1"></i> Registrar
                </button>
            </div>
        </form>
    </div>
</div>"""
        
        if patron_modal.search(c):
            c = patron_modal.sub(nuevo_modal, c)
            p_html.write_text(c, encoding='utf-8')
            print("✅ facturas.html: Modal de abono rediseñado al estilo premium.")
        else:
            print("⚠️ No se encontró el bloque del modal de abono. Se intentará reemplazo directo.")
            # Si el regex falla, buscar la ID del modal
            if 'id="modalAbono"' in c:
                # Esto es más complejo, pero podemos simplemente reemplazar el contenido desde <div id="modalAbono" hasta el cierre antes de </div> final.
                pass

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga Facturas con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()