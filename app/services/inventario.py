# app/services/inventario.py
import logging
from ..extensions import db
from ..models.producto import Producto


logger = logging.getLogger(__name__)


class InventarioService:

    @staticmethod
    def crear(usuario_id, form, files, upload_folder):
        from ..utils.images import guardar_imagen_producto
        from sqlalchemy.exc import IntegrityError

        precio_costo = float(form.get('precio_costo_usd', 0) or 0)
        precio_venta = float(form.get('precio_venta_usd', 0) or 0)
        margen = float(form.get('margen_ganancia', 0) or 0)
        if margen == 0 and precio_costo > 0:
            margen = ((precio_venta - precio_costo) / precio_costo * 100)

        nombre = form.get('nombre', '').strip()
        codigo = form.get('codigo', '').strip()

        if not nombre:
            raise ValueError('El nombre del producto es obligatorio')
        if not codigo:
            raise ValueError('El codigo del producto es obligatorio')

        existente = Producto.query.filter_by(usuario_id=usuario_id, codigo=codigo).first()
        if existente:
            raise ValueError(f'El codigo "{codigo}" ya esta en uso por el producto "{existente.nombre}". Usa otro codigo.')

        # Verificar si el producto tiene variantes
        tiene_variantes = form.get('tiene_variantes') == '1'

        producto = Producto(
            usuario_id=usuario_id,
            nombre=nombre,
            codigo=codigo,
            categoria=form.get('categoria', '').strip(),
            subcategoria=form.get('subcategoria', '').strip(),
            marca=form.get('marca', '').strip(),
            modelo=form.get('modelo', '').strip(),
            referencia=form.get('referencia', '').strip(),
            color=form.get('color', '').strip(),
            descripcion=form.get('descripcion', '').strip(),
            precio_costo_usd=precio_costo,
            precio_venta_usd=precio_venta,
            margen_ganancia=margen,
            stock_actual=int(form.get('stock_actual', 0) or 0) if not tiene_variantes else 0,
            stock_minimo=int(form.get('stock_minimo', 5) or 5),
            ubicacion=form.get('ubicacion', '').strip(),
            fecha_expiracion=form.get('fecha_expiracion') or None,
            impuesto=float(form.get('impuesto', 16) or 16),
            proveedor_nombre=form.get('proveedor_nombre', '').strip(),
            proveedor_contacto=form.get('proveedor_contacto', '').strip(),
            proveedor_notas=form.get('proveedor_notas', '').strip(),
            pagado_contado=form.get('pagado_contado') == '1',
            dias_credito=int(form.get('dias_credito', 0) or 0),
            observaciones=form.get('observaciones', '').strip(),
            medida_unidad=form.get('medida_unidad', 'Unidad').strip(),
            medida_cantidad=float(form.get('medida_cantidad', 1) or 1),
        )

        try:
            db.session.add(producto)
            db.session.flush()

            # Guardar imagen
            if 'imagen_producto' in files:
                img = files['imagen_producto']
                if img and img.filename:
                    from .imagekit_service import ImageKitService
                    url_nube = ImageKitService.subir_imagen(img)
                    if url_nube:
                        producto.imagen_principal = url_nube
                    else:
                        nombre_img = guardar_imagen_producto(img, usuario_id, producto.id, upload_folder)
                        if nombre_img:
                            producto.imagen_principal = nombre_img

            # Guardar variantes si tiene
            if tiene_variantes:
                variantes_guardadas = InventarioService._procesar_variantes(producto, form)
                # Actualizar stock total del producto = suma de variantes
                producto.stock_actual = sum(v.stock_actual for v in variantes_guardadas)

            db.session.commit()
            return producto
        except IntegrityError as e:
            db.session.rollback()
            if 'UNIQUE' in str(e) and 'codigo' in str(e):
                raise ValueError(f'El codigo "{codigo}" ya existe. Usa otro.')
            raise ValueError(f'Error al guardar: {str(e)}')
        except Exception as e:
            db.session.rollback()
            raise

    @staticmethod
    def _procesar_variantes(producto, form):
        """Procesa las variantes del formulario y las guarda en la BD."""
        from ..models.producto import ProductoVariante

        # Extraer variantes del form
        # Formato: variantes[0][nombre], variantes[0][codigo], etc.
        variantes_data = {}
        for key in form.keys():
            if key.startswith('variantes['):
                # Extraer índice y campo: "variantes[0][nombre]" -> (0, "nombre")
                import re as _re
                m = _re.match(r"variantes\[(\d+)\]\[([^\]]+)\]", key)
                if m:
                    idx = int(m.group(1))
                    campo = m.group(2)
                    if idx not in variantes_data:
                        variantes_data[idx] = {}
                    variantes_data[idx][campo] = form.get(key, "").strip()

        # Crear las variantes
        variantes = []
        for idx in sorted(variantes_data.keys()):
            data = variantes_data[idx]
            nombre_var = data.get('nombre', '').strip()
            if not nombre_var:
                continue  # Ignorar variantes sin nombre

            # Verificar si ya existe una variante con ese nombre
            existente = ProductoVariante.query.filter_by(
                producto_id=producto.id,
                nombre=nombre_var
            ).first()

            if existente:
                # Actualizar
                existente.codigo = data.get('codigo', '').strip()
                existente.stock_actual = int(data.get('stock_actual', 0) or 0)
                existente.stock_minimo = int(data.get('stock_minimo', 0) or 0)
                existente.precio_costo_usd = float(data.get('precio_costo_usd', 0) or 0)
                existente.precio_venta_usd = float(data.get('precio_venta_usd', 0) or 0)
                variantes.append(existente)
            else:
                # Crear nueva
                nueva = ProductoVariante(
                    producto_id=producto.id,
                    nombre=nombre_var,
                    codigo=data.get('codigo', '').strip(),
                    stock_actual=int(data.get('stock_actual', 0) or 0),
                    stock_minimo=int(data.get('stock_minimo', 0) or 0),
                    precio_costo_usd=float(data.get('precio_costo_usd', 0) or 0),
                    precio_venta_usd=float(data.get('precio_venta_usd', 0) or 0),
                )
                db.session.add(nueva)
                variantes.append(nueva)

        return variantes

    @staticmethod
    def actualizar(producto, form, files, upload_folder):
        from ..utils.images import guardar_imagen_producto, eliminar_imagenes_producto
        from ..models.producto import ProductoVariante

        precio_costo = float(form.get('precio_costo_usd', 0) or 0)
        precio_venta = float(form.get('precio_venta_usd', 0) or 0)

        tiene_variantes = form.get('tiene_variantes') == '1'

        producto.nombre = form.get('nombre', '').strip()
        producto.categoria = form.get('categoria', '').strip()
        producto.subcategoria = form.get('subcategoria', '').strip()
        producto.marca = form.get('marca', '').strip()
        producto.modelo = form.get('modelo', '').strip()
        producto.referencia = form.get('referencia', '').strip()
        producto.color = form.get('color', '').strip()
        producto.descripcion = form.get('descripcion', '').strip()
        producto.precio_costo_usd = precio_costo
        producto.precio_venta_usd = precio_venta
        producto.margen_ganancia = ((precio_venta - precio_costo) / precio_costo * 100) if precio_costo > 0 else 0
        producto.stock_minimo = int(form.get('stock_minimo', 5) or 5)
        producto.ubicacion = form.get('ubicacion', '').strip()
        producto.fecha_expiracion = form.get('fecha_expiracion') or None
        producto.impuesto = float(form.get('impuesto', 16) or 16)
        producto.observaciones = form.get('observaciones', '').strip()
        producto.medida_unidad = form.get('medida_unidad', 'Unidad').strip()
        producto.medida_cantidad = float(form.get('medida_cantidad', 1) or 1)

        # Stock: si tiene variantes, se calcula sumando. Si no, se lee del form.
        if not tiene_variantes:
            producto.stock_actual = int(form.get('stock_actual', 0) or 0)

        if 'imagen_producto' in files:
            img = files['imagen_producto']
            if img and img.filename:
                from .imagekit_service import ImageKitService
                url_nube = ImageKitService.subir_imagen(img)
                if url_nube:
                    producto.imagen_principal = url_nube
                else:
                    eliminar_imagenes_producto(producto.usuario_id, producto.id, upload_folder)
                    nombre = guardar_imagen_producto(img, producto.usuario_id, producto.id, upload_folder)
                    if nombre:
                        producto.imagen_principal = nombre

        # Procesar variantes
        if tiene_variantes:
            variantes_form = InventarioService._procesar_variantes(producto, form)
            # Actualizar stock del producto = suma de variantes
            producto.stock_actual = sum(v.stock_actual for v in variantes_form)
            
            # Eliminar variantes que ya no están en el form
            nombres_form = set()
            for key in form.keys():
                if key.startswith('variantes[') and key.endswith('[nombre]'):
                    nombre_var = form.get(key, '').strip()
                    if nombre_var:
                        nombres_form.add(nombre_var)
            
            # Buscar variantes huérfanas
            variantes_actuales = ProductoVariante.query.filter_by(producto_id=producto.id).all()
            for v in variantes_actuales:
                if v.nombre not in nombres_form:
                    db.session.delete(v)
        else:
            # Si ya no tiene variantes, eliminar todas las existentes
            ProductoVariante.query.filter_by(producto_id=producto.id).delete()

        db.session.commit()
        return producto

    @staticmethod
    def ajustar_stock(producto, tipo, cantidad):
        if tipo == 'entrada':
            producto.stock_actual += cantidad
        elif tipo == 'salida':
            if producto.stock_actual < cantidad:
                return False, f'Stock insuficiente. Disponible: {producto.stock_actual}'
            producto.stock_actual -= cantidad
        else:
            return False, 'Tipo de ajuste inválido'
        db.session.commit()
        return True, producto.stock_actual

    @staticmethod
    def puede_eliminar(producto):
        return producto.ventas.count() == 0