import shutil
from pathlib import Path

def main():
    print("\n==================================================")
    print("   CORRIGIENDO VALOR INVENTARIO (FLOAT * DECIMAL)")
    print("==================================================\n")

    p = Path('app/models/producto.py')
    if not p.exists():
        print("❌ No se encontró producto.py")
        return

    c = p.read_text(encoding='utf-8')
    bak = p.with_suffix('.py.bak_valor_inv')
    if not bak.exists():
        shutil.copy2(p, bak)

    # Buscar la propiedad valor_inventario_usd
    old_prop = """    @property
    def valor_inventario_usd(self):
        # Si tiene variantes, calculamos el valor sumando (precio_variante * stock_variante)
        variantes = self.variantes.all()
        if variantes:
            total = 0
            for v in variantes:
                # Si la variante no tiene precio propio, hereda el del padre (o usa 0)
                precio = float(v.precio_venta_usd) if v.precio_venta_usd else float(self.precio_venta_usd or 0)
                total += precio * v.stock_actual
            return total
        # Si no tiene variantes, usa el cálculo normal
        return float(self.precio_venta_usd or 0) * self.stock_actual"""

    new_prop = """    @property
    def valor_inventario_usd(self):
        # ✅ Convertir todo a float para evitar mezclar float y Decimal
        variantes = self.variantes.all()
        if variantes:
            total = 0.0
            for v in variantes:
                precio = float(v.precio_venta_usd) if v.precio_venta_usd else float(self.precio_venta_usd or 0)
                stock = float(v.stock_actual or 0)
                total += precio * stock
            return total
        # Si no tiene variantes, usa el cálculo normal
        return float(self.precio_venta_usd or 0) * float(self.stock_actual or 0)"""

    if old_prop in c:
        c = c.replace(old_prop, new_prop)
        p.write_text(c, encoding='utf-8')
        print("✅ producto.py: Propiedad valor_inventario_usd corregida (conversión a float).")
    else:
        print("⚠️ No se encontró el bloque exacto. Intentando reemplazo simple...")
        # Buscar cualquier variante de la propiedad
        if 'valor_inventario_usd' in c:
            # Forzar la conversión a float en la línea de multiplicación
            c = c.replace(
                "total += precio * v.stock_actual",
                "total += float(precio) * float(v.stock_actual or 0)"
            )
            c = c.replace(
                "return float(self.precio_venta_usd or 0) * self.stock_actual",
                "return float(self.precio_venta_usd or 0) * float(self.stock_actual or 0)"
            )
            p.write_text(c, encoding='utf-8')
            print("✅ producto.py: Conversión a float aplicada en las multiplicaciones.")
        else:
            print("❌ No se encontró la propiedad valor_inventario_usd.")

    print("\n👉 Recarga la página de inventario con Ctrl + Shift + R.")

if __name__ == '__main__':
    main()