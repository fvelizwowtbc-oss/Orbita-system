# app/services/inventario_excel.py
# Servicio para exportar/importar inventario completo a Excel.
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter


# ============================================================
# COLUMNAS
# ============================================================
COLUMNAS_PRODUCTOS = [
    ('codigo', 'CODIGO', 18),
    ('nombre', 'NOMBRE', 35),
    ('modelo', 'MODELO', 18),
    ('marca', 'MARCA', 15),
    ('referencia', 'REFERENCIA', 15),
    ('categoria', 'CATEGORIA', 18),
    ('subcategoria', 'SUBCATEGORIA', 18),
    ('color', 'COLOR', 12),
    ('descripcion', 'DESCRIPCION', 30),
    ('stock_actual', 'STOCK', 10),
    ('stock_minimo', 'STOCK_MINIMO', 12),
    ('precio_costo_usd', 'COSTO_USD', 12),
    ('precio_venta_usd', 'VENTA_USD', 12),
    ('margen_ganancia', 'MARGEN', 10),
    ('impuesto', 'IMPUESTO', 10),
    ('medida_unidad', 'MEDIDA', 12),
    ('medida_cantidad', 'CANT_MEDIDA', 12),
    ('ubicacion', 'UBICACION', 15),
    ('fecha_expiracion', 'FECHA_EXP', 12),
    ('proveedor_nombre', 'PROVEEDOR', 20),
    ('proveedor_contacto', 'CONTACTO', 15),
    ('pagado_contado', 'PAGADO', 10),
    ('dias_credito', 'DIAS_CRED', 10),
    ('observaciones', 'OBSERVACIONES', 25),
    ('imagen_principal', 'IMAGEN', 25),
    ('activo', 'ACTIVO', 8),
]

COLUMNAS_VARIANTES = [
    ('codigo_padre', 'CODIGO_PRODUCTO', 18),
    ('nombre', 'NOMBRE', 25),
    ('codigo', 'CODIGO_VARIANTE', 18),
    ('stock_actual', 'STOCK', 10),
    ('stock_minimo', 'STOCK_MINIMO', 12),
    ('precio_costo_usd', 'COSTO_USD', 12),
    ('precio_venta_usd', 'VENTA_USD', 12),
    ('activo', 'ACTIVO', 8),
]


# ============================================================
# ESTILOS
# ============================================================
def _header_style():
    return {
        'font': Font(bold=True, color='FFFFFF', size=11),
        'fill': PatternFill(start_color='1e3a5f', end_color='1e3a5f', fill_type='solid'),
        'alignment': Alignment(horizontal='center', vertical='center'),
        'border': Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC'),
        ),
    }


def _cell_border():
    return Border(
        left=Side(style='thin', color='EEEEEE'),
        right=Side(style='thin', color='EEEEEE'),
        top=Side(style='thin', color='EEEEEE'),
        bottom=Side(style='thin', color='EEEEEE'),
    )


# ============================================================
# SERVICIO
# ============================================================
class InventarioExcelService:

    @staticmethod
    def _valor_str(v, default=''):
        if v is None:
            return default
        return str(v)

    @staticmethod
    def _valor_float(v, default=0.0):
        if v is None or v == '':
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _valor_int(v, default=0):
        if v is None or v == '':
            return default
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _valor_bool(v, default=True):
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ('1', 'si', 'sí', 's', 'true', 'yes', 'y', 'activo'):
            return True
        if s in ('0', 'no', 'n', 'false', 'inactivo'):
            return False
        return default

    # ========================================================
    # EXPORTAR
    # ========================================================
    @staticmethod
    def exportar(productos):
        """Genera un Excel con todos los productos y sus variantes.

        Args:
            productos: lista de objetos Producto (con sus variantes cargadas)

        Returns:
            BytesIO con el archivo .xlsx
        """
        wb = Workbook()

        # ============ HOJA 1: PRODUCTOS ============
        ws = wb.active
        ws.title = 'Productos'
        estilo = _header_style()

        # Encabezados
        for col, (_, titulo, ancho) in enumerate(COLUMNAS_PRODUCTOS, 1):
            c = ws.cell(row=1, column=col, value=titulo)
            c.font = estilo['font']
            c.fill = estilo['fill']
            c.alignment = estilo['alignment']
            c.border = estilo['border']
            ws.column_dimensions[get_column_letter(col)].width = ancho

        # Congelar primera fila
        ws.freeze_panes = 'A2'

        # Filas
        for row_idx, p in enumerate(productos, start=2):
            for col_idx, (campo, _, _) in enumerate(COLUMNAS_PRODUCTOS, 1):
                val = getattr(p, campo, None)

                # Convertir tipos
                if campo in ('precio_costo_usd', 'precio_venta_usd', 'margen_ganancia',
                             'impuesto', 'medida_cantidad'):
                    val = float(val) if val is not None else 0.0
                elif campo in ('stock_actual', 'stock_minimo', 'dias_credito'):
                    val = int(val) if val is not None else 0
                elif campo in ('pagado_contado', 'activo'):
                    val = 'SI' if val else 'NO'
                elif campo == 'fecha_expiracion':
                    val = val.strftime('%Y-%m-%d') if val else ''
                elif val is None:
                    val = ''

                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.border = _cell_border()

        # ============ HOJA 2: VARIANTES ============
        ws2 = wb.create_sheet('Variantes')

        for col, (_, titulo, ancho) in enumerate(COLUMNAS_VARIANTES, 1):
            c = ws2.cell(row=1, column=col, value=titulo)
            c.font = estilo['font']
            c.fill = estilo['fill']
            c.alignment = estilo['alignment']
            c.border = estilo['border']
            ws2.column_dimensions[get_column_letter(col)].width = ancho

        ws2.freeze_panes = 'A2'

        row_var = 2
        for p in productos:
            for v in p.variantes.all():
                valores = {
                    'codigo_padre': p.codigo,
                    'nombre': v.nombre or '',
                    'codigo': v.codigo or '',
                    'stock_actual': v.stock_actual or 0,
                    'stock_minimo': v.stock_minimo or 0,
                    'precio_costo_usd': float(v.precio_costo_usd or 0),
                    'precio_venta_usd': float(v.precio_venta_usd or 0),
                    'activo': 'SI' if v.activo else 'NO',
                }
                for col_idx, (campo, _, _) in enumerate(COLUMNAS_VARIANTES, 1):
                    c = ws2.cell(row=row_var, column=col_idx, value=valores.get(campo, ''))
                    c.border = _cell_border()
                row_var += 1

        # Guardar
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    # ========================================================
    # PLANTILLA VACIA
    # ========================================================
    @staticmethod
    def plantilla():
        """Genera un Excel vacio con las columnas correctas + ejemplo."""
        wb = Workbook()
        ws = wb.active
        ws.title = 'Productos'
        estilo = _header_style()

        for col, (_, titulo, ancho) in enumerate(COLUMNAS_PRODUCTOS, 1):
            c = ws.cell(row=1, column=col, value=titulo)
            c.font = estilo['font']
            c.fill = estilo['fill']
            c.alignment = estilo['alignment']
            c.border = estilo['border']
            ws.column_dimensions[get_column_letter(col)].width = ancho

        ws.freeze_panes = 'A2'

        # Fila de ejemplo
        ejemplo = {
            'codigo': 'EJEMPLO001',
            'nombre': 'Producto de ejemplo',
            'categoria': 'Otros',
            'stock_actual': 10,
            'stock_minimo': 2,
            'precio_costo_usd': 5.00,
            'precio_venta_usd': 6.50,
            'impuesto': 16,
            'medida_unidad': 'Unidad',
            'medida_cantidad': 1,
            'pagado_contado': 'SI',
            'activo': 'SI',
        }
        for col_idx, (campo, _, _) in enumerate(COLUMNAS_PRODUCTOS, 1):
            c = ws.cell(row=2, column=col_idx, value=ejemplo.get(campo, ''))
            c.border = _cell_border()
            c.font = Font(italic=True, color='888888')

        # Hoja 2
        ws2 = wb.create_sheet('Variantes')
        for col, (_, titulo, ancho) in enumerate(COLUMNAS_VARIANTES, 1):
            c = ws2.cell(row=1, column=col, value=titulo)
            c.font = estilo['font']
            c.fill = estilo['fill']
            c.alignment = estilo['alignment']
            c.border = estilo['border']
            ws2.column_dimensions[get_column_letter(col)].width = ancho

        ws2.freeze_panes = 'A2'

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    # ========================================================
    # IMPORTAR
    # ========================================================
    @staticmethod
    def _mapear_columnas(headers):
        """Mapea las columnas del Excel a los campos del modelo."""
        def find_col(keywords):
            for i, h in enumerate(headers):
                for kw in keywords:
                    if kw in h:
                        return i
            return None

        # Mapa de campo -> indices
        mapa = {}
        for campo, titulo, _ in COLUMNAS_PRODUCTOS:
            # Buscar por el titulo en mayusculas O por el nombre del campo
            idx = find_col([titulo.lower(), campo.lower()])
            if idx is not None:
                mapa[campo] = idx

        return mapa

    @staticmethod
    def _mapear_columnas_variantes(headers):
        def find_col(keywords):
            for i, h in enumerate(headers):
                for kw in keywords:
                    if kw in h:
                        return i
            return None

        mapa = {}
        for campo, titulo, _ in COLUMNAS_VARIANTES:
            idx = find_col([titulo.lower(), campo.lower()])
            if idx is not None:
                mapa[campo] = idx
        return mapa

    @staticmethod
    def importar(file, usuario_id, modo='actualizar'):
        """Importa productos desde un Excel.

        Args:
            file: archivo Excel subido
            usuario_id: ID del usuario dueno
            modo: 'actualizar' (actualiza existentes) o 'agregar' (solo nuevos)

        Returns:
            dict con: agregados, actualizados, omitidos, errores (lista), variantes
        """
        from ..extensions import db
        from ..models.producto import Producto, ProductoVariante

        resultado = {
            'agregados': 0,
            'actualizados': 0,
            'omitidos': 0,
            'errores': [],
            'variantes_agregadas': 0,
            'variantes_actualizadas': 0,
        }

        try:
            wb = load_workbook(file, data_only=True)
        except Exception as e:
            resultado['errores'].append(f'No se pudo abrir el Excel: {e}')
            return resultado

        # ============ HOJA 1: PRODUCTOS ============
        ws = wb['Productos'] if 'Productos' in wb.sheetnames else wb.active
        headers = [str(c.value).lower().strip() if c.value else '' for c in ws[1]]
        mapa = InventarioExcelService._mapear_columnas(headers)

        if 'codigo' not in mapa and 'nombre' not in mapa:
            resultado['errores'].append('Faltan columnas CODIGO y NOMBRE')
            return resultado

        productos_por_codigo = {}

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                def gv(campo, default=''):
                    idx = mapa.get(campo)
                    if idx is not None and idx < len(row) and row[idx] is not None:
                        return str(row[idx]).strip()
                    return default

                codigo = gv('codigo')
                nombre = gv('nombre')

                if not codigo and not nombre:
                    continue
                if not codigo:
                    codigo = f'AUTO-{row_idx}'
                if not nombre:
                    nombre = codigo

                # Buscar si ya existe
                existente = Producto.query.filter_by(
                    usuario_id=usuario_id, codigo=codigo
                ).first()

                # Datos del producto
                datos = {
                    'nombre': nombre,
                    'codigo': codigo,
                    'modelo': gv('modelo'),
                    'marca': gv('marca'),
                    'referencia': gv('referencia'),
                    'categoria': gv('categoria'),
                    'subcategoria': gv('subcategoria'),
                    'color': gv('color'),
                    'descripcion': gv('descripcion'),
                    'stock_actual': InventarioExcelService._valor_int(gv('stock_actual', 0), 0),
                    'stock_minimo': InventarioExcelService._valor_int(gv('stock_minimo', 5), 5),
                    'precio_costo_usd': InventarioExcelService._valor_float(gv('precio_costo_usd', 0), 0),
                    'precio_venta_usd': InventarioExcelService._valor_float(gv('precio_venta_usd', 0), 0),
                    'margen_ganancia': InventarioExcelService._valor_float(gv('margen_ganancia', 0), 0),
                    'impuesto': InventarioExcelService._valor_float(gv('impuesto', 16), 16),
                    'medida_unidad': gv('medida_unidad', 'Unidad') or 'Unidad',
                    'medida_cantidad': InventarioExcelService._valor_float(gv('medida_cantidad', 1), 1),
                    'ubicacion': gv('ubicacion'),
                    'proveedor_nombre': gv('proveedor_nombre'),
                    'proveedor_contacto': gv('proveedor_contacto'),
                    'pagado_contado': InventarioExcelService._valor_bool(gv('pagado_contado', 'SI'), True),
                    'dias_credito': InventarioExcelService._valor_int(gv('dias_credito', 0), 0),
                    'observaciones': gv('observaciones'),
                    'imagen_principal': gv('imagen_principal'),
                    'activo': InventarioExcelService._valor_bool(gv('activo', 'SI'), True),
                }

                # Fecha expiracion
                fecha_exp_str = gv('fecha_expiracion')
                if fecha_exp_str:
                    try:
                        datos['fecha_expiracion'] = datetime.strptime(fecha_exp_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass

                if existente:
                    if modo == 'actualizar':
                        for k, v in datos.items():
                            if k != 'codigo':  # no cambiar el codigo
                                setattr(existente, k, v)
                        resultado['actualizados'] += 1
                        productos_por_codigo[codigo] = existente
                    else:
                        resultado['omitidos'] += 1
                        productos_por_codigo[codigo] = existente
                else:
                    # Verificar limite
                    from .suscripciones import SuscripcionesService
                    limites = SuscripcionesService.verificar_limites(usuario_id)
                    total_actual = Producto.query.filter_by(usuario_id=usuario_id).count()
                    if limites['limite_productos'] > 0 and total_actual >= limites['limite_productos']:
                        resultado['errores'].append(
                            f'Fila {row_idx}: Limite de productos alcanzado'
                        )
                        continue

                    p = Producto(usuario_id=usuario_id, **datos)
                    db.session.add(p)
                    db.session.flush()  # para obtener el ID
                    resultado['agregados'] += 1
                    productos_por_codigo[codigo] = p

            except Exception as e:
                resultado['errores'].append(f'Fila {row_idx}: {e}')

        # ============ HOJA 2: VARIANTES ============
        if 'Variantes' in wb.sheetnames:
            ws2 = wb['Variantes']
            headers2 = [str(c.value).lower().strip() if c.value else '' for c in ws2[1]]
            mapa2 = InventarioExcelService._mapear_columnas_variantes(headers2)

            for row_idx, row in enumerate(ws2.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    def gv2(campo, default=''):
                        idx = mapa2.get(campo)
                        if idx is not None and idx < len(row) and row[idx] is not None:
                            return str(row[idx]).strip()
                        return default

                    cod_padre = gv2('codigo_padre')
                    if not cod_padre:
                        continue

                    padre = productos_por_codigo.get(cod_padre)
                    if not padre:
                        # Buscar en BD
                        padre = Producto.query.filter_by(
                            usuario_id=usuario_id, codigo=cod_padre
                        ).first()
                    if not padre:
                        resultado['errores'].append(
                            f'Variante fila {row_idx}: producto padre {cod_padre} no existe'
                        )
                        continue

                    nombre_v = gv2('nombre')
                    if not nombre_v:
                        continue

                    # Buscar variante existente
                    variante = ProductoVariante.query.filter_by(
                        producto_id=padre.id, nombre=nombre_v
                    ).first()

                    datos_v = {
                        'nombre': nombre_v,
                        'codigo': gv2('codigo'),
                        'stock_actual': InventarioExcelService._valor_int(gv2('stock_actual', 0), 0),
                        'stock_minimo': InventarioExcelService._valor_int(gv2('stock_minimo', 0), 0),
                        'precio_costo_usd': InventarioExcelService._valor_float(gv2('precio_costo_usd', 0), 0),
                        'precio_venta_usd': InventarioExcelService._valor_float(gv2('precio_venta_usd', 0), 0),
                        'activo': InventarioExcelService._valor_bool(gv2('activo', 'SI'), True),
                    }

                    if variante:
                        if modo == 'actualizar':
                            for k, v in datos_v.items():
                                setattr(variante, k, v)
                            resultado['variantes_actualizadas'] += 1
                    else:
                        v = ProductoVariante(producto_id=padre.id, **datos_v)
                        db.session.add(v)
                        resultado['variantes_agregadas'] += 1

                except Exception as e:
                    resultado['errores'].append(f'Variante fila {row_idx}: {e}')

        db.session.commit()
        return resultado
