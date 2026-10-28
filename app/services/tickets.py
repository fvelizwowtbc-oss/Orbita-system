# app/services/tickets.py
# Servicio de impresion de tickets para POS-58 (58mm termico)
from datetime import datetime
from decimal import Decimal


# ============================================================
# CONFIGURACION DEL TICKET
# ============================================================
ANCHO_TICKET = 32       # 32 caracteres para 58mm
SEPARADOR = "=" * ANCHO_TICKET
LINEA = "-" * ANCHO_TICKET


class TicketsService:

    @staticmethod
    def _formato_moneda(valor, simbolo="$"):
        """Formatea un monto con simbolo."""
        try:
            v = float(valor or 0)
            return f"{simbolo}{v:,.2f}"
        except Exception:
            return f"{simbolo}0.00"

    @staticmethod
    def _linea_izq_der(izq, der, ancho=ANCHO_TICKET):
        """Genera una linea con texto a la izquierda y a la derecha."""
        izq = str(izq)
        der = str(der)
        espacios = ancho - len(izq) - len(der)
        if espacios < 1:
            espacios = 1
        return izq + (" " * espacios) + der

    @staticmethod
    def calcular_desglose_iva(total_con_iva, tasa_iva=16.00):
        """Calcula base e IVA a partir de un total que YA incluye IVA.

        Args:
            total_con_iva: total final con IVA incluido
            tasa_iva: porcentaje de IVA (16% por defecto)

        Returns:
            dict con: base, iva, total, tasa, exento
        """
        total = Decimal(str(total_con_iva or 0))
        tasa = Decimal(str(tasa_iva or 16))

        if tasa <= 0:
            return {
                "base": float(total),
                "iva": 0.0,
                "total": float(total),
                "tasa": 0.0,
                "exento": True,
            }

        divisor = Decimal("1") + (tasa / Decimal("100"))
        base = (total / divisor).quantize(Decimal("0.01"))
        iva = (total - base).quantize(Decimal("0.01"))

        return {
            "base": float(base),
            "iva": float(iva),
            "total": float(total),
            "tasa": float(tasa),
            "exento": False,
        }

    @staticmethod
    def generar_texto_ticket(venta, empresa, vendedor_nombre=""):
        """Genera el texto plano del ticket (para debug o preview)."""
        lineas = []

        # ============ ENCABEZADO ============
        lineas.append(SEPARADOR)
        lineas.append(empresa.get("nombre", "MI NEGOCIO").center(ANCHO_TICKET))
        if empresa.get("rif"):
            lineas.append(f"RIF: {empresa['rif']}".center(ANCHO_TICKET))
        if empresa.get("direccion"):
            lineas.append(empresa["direccion"][:ANCHO_TICKET].center(ANCHO_TICKET))
        if empresa.get("telefono"):
            lineas.append(f"Tel: {empresa['telefono']}".center(ANCHO_TICKET))
        lineas.append(SEPARADOR)

        # ============ DATOS DE FACTURA ============
        nro = venta.get("nro_factura", "S/N")
        lineas.append(f"FACTURA: {nro}")
        lineas.append(f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        if vendedor_nombre:
            lineas.append(f"CAJERO: {vendedor_nombre[:20]}")
        cliente = venta.get("cliente_nombre", "Consumidor Final")
        lineas.append(f"CLIENTE: {cliente[:20]}")
        metodo = venta.get("metodo_pago", "efectivo").upper()
        lineas.append(f"PAGO: {metodo}")
        lineas.append(LINEA)

        # ============ PRODUCTOS ============
        lineas.append("CANT  DESCRIPCION          TOTAL")
        lineas.append(LINEA)

        for item in venta.get("productos", []):
            cant = item.get("cantidad", 0)
            nombre = item.get("nombre", "Producto")[:18]
            precio = float(item.get("precio_usd", 0))
            subtotal = cant * precio

            linea_prod = f"{cant:>4}  {nombre:<18} {TicketsService._formato_moneda(subtotal)}"
            lineas.append(linea_prod[:ANCHO_TICKET])

            if cant > 1:
                lineas.append(f"      {TicketsService._formato_moneda(precio)} c/u")

        lineas.append(LINEA)

        # ============ TOTALES CON IVA ============
        total_usd = float(venta.get("total_usd", 0))
        tasa_bcv = float(venta.get("tasa_bcv", 0))
        desglose = TicketsService.calcular_desglose_iva(total_usd, 16.00)

        lineas.append(TicketsService._linea_izq_der("SUBTOTAL (BASE):", TicketsService._formato_moneda(desglose["base"])))
        lineas.append(TicketsService._linea_izq_der(f"IVA ({desglose['tasa']:.0f}%):", TicketsService._formato_moneda(desglose["iva"])))
        lineas.append(TicketsService._linea_izq_der("TOTAL USD:", TicketsService._formato_moneda(desglose["total"])))
        lineas.append(LINEA)

        total_bs = total_usd * tasa_bcv
        lineas.append(TicketsService._linea_izq_der("TASA BCV:", f"Bs. {tasa_bcv:,.2f}"))
        lineas.append(TicketsService._linea_izq_der("TOTAL Bs:", f"Bs. {total_bs:,.2f}"))

        # ============ PIE ============
        lineas.append(SEPARADOR)
        lineas.append("GRACIAS POR SU COMPRA".center(ANCHO_TICKET))
        lineas.append(SEPARADOR)

        return "\n".join(lineas)

    @staticmethod
    def imprimir_ticket(venta, empresa, nombre_impresora="POS-58", vendedor_nombre=""):
        """Imprime el ticket en la POS-58.

        Returns:
            (success: bool, error: str or None)
        """
        try:
            from escpos.printer import Win32Raw
        except ImportError:
            return False, "python-escpos no instalado. Ejecuta: pip install python-escpos pywin32"

        try:
            p = Win32Raw(printer_name=nombre_impresora)

            # ============ ENCABEZADO ============
            p.set(align="center", bold=True, width=2, height=2)
            p.text(empresa.get("nombre", "MI NEGOCIO") + "\n")
            p.set(align="center", bold=False, width=1, height=1)
            if empresa.get("rif"):
                p.text(f"RIF: {empresa['rif']}\n")
            if empresa.get("direccion"):
                p.text(empresa["direccion"][:ANCHO_TICKET] + "\n")
            if empresa.get("telefono"):
                p.text(f"Tel: {empresa['telefono']}\n")
            p.text("=" * ANCHO_TICKET + "\n")

            # ============ DATOS FACTURA ============
            p.set(align="left")
            nro = venta.get("nro_factura", "S/N")
            p.text(f"FACTURA: {nro}\n")
            p.text(f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            if vendedor_nombre:
                p.text(f"CAJERO: {vendedor_nombre[:20]}\n")
            p.text(f"CLIENTE: {venta.get('cliente_nombre', 'Consumidor Final')[:20]}\n")
            p.text(f"PAGO: {venta.get('metodo_pago', 'efectivo').upper()}\n")
            p.text("-" * ANCHO_TICKET + "\n")

            # ============ PRODUCTOS ============
            p.set(bold=True)
            p.text("CANT  DESCRIPCION          TOTAL\n")
            p.set(bold=False)
            p.text("-" * ANCHO_TICKET + "\n")

            for item in venta.get("productos", []):
                cant = item.get("cantidad", 0)
                nombre = item.get("nombre", "Producto")[:18]
                precio = float(item.get("precio_usd", 0))
                subtotal = cant * precio

                p.text(f"{cant:>4}  {nombre:<18} ${subtotal:>7.2f}\n")
                if cant > 1:
                    p.text(f"      ${precio:>6.2f} c/u\n")

            p.text("-" * ANCHO_TICKET + "\n")

            # ============ TOTALES CON IVA ============
            total_usd = float(venta.get("total_usd", 0))
            tasa_bcv = float(venta.get("tasa_bcv", 0))
            desglose = TicketsService.calcular_desglose_iva(total_usd, 16.00)

            p.text(TicketsService._linea_izq_der("SUBTOTAL (BASE):", f"${desglose['base']:.2f}") + "\n")
            p.text(TicketsService._linea_izq_der(f"IVA ({desglose['tasa']:.0f}%):", f"${desglose['iva']:.2f}") + "\n")
            p.set(bold=True)
            p.text(TicketsService._linea_izq_der("TOTAL USD:", f"${desglose['total']:.2f}") + "\n")
            p.set(bold=False)
            p.text("-" * ANCHO_TICKET + "\n")

            total_bs = total_usd * tasa_bcv
            p.text(TicketsService._linea_izq_der("TASA BCV:", f"Bs. {tasa_bcv:,.2f}") + "\n")
            p.set(bold=True, height=2)
            p.text(TicketsService._linea_izq_der("TOTAL Bs:", f"Bs. {total_bs:,.2f}") + "\n")
            p.set(bold=False, height=1)

            # ============ PIE ============
            p.text("=" * ANCHO_TICKET + "\n")
            p.set(align="center")
            p.text("GRACIAS POR SU COMPRA\n")
            p.text("=" * ANCHO_TICKET + "\n")

            # ✅ Sin lineas en blanco — el corte se hace directo
            # Si la impresora avanza mucho papel, revisar opcion de cut()
            try:
                p.cut(feed=False)   # Sin feed extra antes del corte
            except TypeError:
                # Versiones viejas no aceptan feed=False
                p.cut()
            p.close()

            return True, None

        except Exception as e:
            return False, str(e)
