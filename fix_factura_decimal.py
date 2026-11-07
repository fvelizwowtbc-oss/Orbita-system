from pathlib import Path
import shutil

def main():
    p = Path('app/templates/user/factura_template.html')
    if not p.exists():
        print("❌ No se encontró factura_template.html")
        return
        
    c = p.read_text(encoding='utf-8')
    
    # Hacer backup
    bak = p.with_suffix('.html.bak_decimal')
    if not bak.exists():
        shutil.copy2(p, bak)

    # 1. Arreglar el cálculo en la tabla de productos (sumando |float)
    c = c.replace(
        '<td class="tr">Bs. {{ "%.2f"|format(v.total_usd * tasa_activa) }}</td>',
        '<td class="tr">Bs. {{ "%.2f"|format((v.total_usd|float) * tasa_activa) }}</td>'
    )
    
    # 2. Arreglar el cálculo en el total de abajo (por si acaso)
    c = c.replace(
        '<td class="tr tf">Bs. {{ "%.2f"|format(factura.total_ves) }}</td>',
        '<td class="tr tf">Bs. {{ "%.2f"|format(factura.total_ves|float) }}</td>'
    )

    p.write_text(c, encoding='utf-8')
    print("✅ ¡Error de Decimal corregido! Ahora la factura multiplicará correctamente.")
    print("Recarga el navegador y vuelve a darle al ojito de la factura.")

if __name__ == '__main__':
    main()