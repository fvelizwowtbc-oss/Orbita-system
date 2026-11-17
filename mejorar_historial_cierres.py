import re
import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   MEJORANDO EL HISTORIAL DE CIERRES DE CAJA")
    print("==================================================\n")

    # 1. ACTUALIZAR EL HTML DEL VENDEDOR (vendedor/caja.html)
    p_vend = Path('app/templates/vendedor/caja.html')
    if p_vend.exists():
        c = p_vend.read_text(encoding='utf-8')
        bak = p_vend.with_suffix('.html.bak_historial')
        if not bak.exists(): shutil.copy2(p_vend, bak)

        # Buscar el bloque del historial de cierres
        patron = re.compile(
            r'<div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">.*?</div>\s*</div>\s*</div>',
            re.DOTALL
        )

        nuevo_bloque = """<div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">
                    <!-- Cabecera: Fecha y Tasa -->
                    <div class="flex justify-between items-center border-b border-slate-100 pb-2 mb-3">
                        <p class="text-sm font-bold text-slate-800"><i class="far fa-calendar-alt text-slate-400 mr-1"></i> {{ cierre.cerrada_en.strftime('%d/%m/%Y') }}</p>
                        <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">Tasa: {{ "%.2f"|format(cierre.tasa_cierre|float or 0) }}</span>
                    </div>
                    
                    <!-- Desglose de Montos -->
                    <div class="space-y-2 text-xs mb-3">
                        <!-- Base Inicial -->
                        <div class="flex justify-between items-center bg-slate-50 p-1.5 rounded border border-slate-100">
                            <span class="text-slate-500 font-medium"><i class="fas fa-lock text-slate-400 w-4"></i> Base Inicial:</span>
                            <span class="text-slate-700">${{ "%.2f"|format(cierre.saldo_inicial_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.saldo_inicial_bs|float or 0) }}</span>
                        </div>
                        <!-- Ventas en Efectivo -->
                        <div class="flex justify-between items-center bg-emerald-50 p-1.5 rounded border border-emerald-100">
                            <span class="text-emerald-700 font-medium"><i class="fas fa-shopping-cart text-emerald-500 w-4"></i> Ventas Efectivo:</span>
                            <span class="text-emerald-800">${{ "%.2f"|format(cierre.total_ventas_efectivo_usd|float or 0) }} + Bs. {{ "%.2f"|format(cierre.total_ventas_efectivo_bs|float or 0) }}</span>
                        </div>
                        <!-- Físico Contado -->
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
                </div>"""
        
        if patron.search(c):
            c = patron.sub(nuevo_bloque, c)
            p_vend.write_text(c, encoding='utf-8')
            print("✅ vendedor/caja.html: Historial de cierres actualizado con desglose completo.")
        else:
            print("⚠️ No se encontró el bloque exacto en vendedor/caja.html.")

    # 2. ACTUALIZAR EL HTML DEL USUARIO (user/caja.html)
    p_user = Path('app/templates/user/caja.html')
    if p_user.exists():
        c = p_user.read_text(encoding='utf-8')
        bak = p_user.with_suffix('.html.bak_historial')
        if not bak.exists(): shutil.copy2(p_user, bak)

        # Buscar el bloque del historial de cierres en el usuario
        # (Es el mismo diseño que el del vendedor)
        patron_user = re.compile(
            r'<div class="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm bg-white">.*?</div>\s*</div>\s*</div>',
            re.DOTALL
        )
        
        if patron_user.search(c):
            c = patron_user.sub(nuevo_bloque, c)
            p_user.write_text(c, encoding='utf-8')
            print("✅ user/caja.html: Historial de cierres actualizado con desglose completo.")
        else:
            print("⚠️ No se encontró el bloque exacto en user/caja.html.")

    print("\n👉 Reinicia Flask (Ctrl+C y run.py) y recarga la página con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()