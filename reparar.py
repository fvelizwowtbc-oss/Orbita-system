# reparar.py - Reparador POS Flask v2 (patrones exactos)
import sys, re, shutil
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv

class C:
    OK='\033[92m'; WARN='\033[93m'; ERR='\033[91m'
    INFO='\033[96m'; DIM='\033[90m'; RESET='\033[0m'; BOLD='\033[1m'

def log(m,c=C.RESET): print(f"{c}{m}{C.RESET}")
def ok(m): log(f"  [OK] {m}", C.OK)
def warn(m): log(f"  [!!] {m}", C.WARN)
def err(m): log(f"  [XX] {m}", C.ERR)
def info(m): log(f"  [..] {m}", C.INFO)
def dim(m): log(f"       {m}", C.DIM)

def backup(p):
    if DRY_RUN or not p.exists(): return
    bak = p.with_suffix(p.suffix + '.bak')
    if not bak.exists():
        shutil.copy2(p, bak); dim(f"backup -> {bak.name}")

def readf(p): return p.read_text(encoding='utf-8')
def writef(p, c):
    if DRY_RUN: dim(f"(dry-run) escribir {p.name}"); return
    p.write_text(c, encoding='utf-8')

def find(root, name, subdir=None):
    for p in root.rglob(name):
        parts = p.parts
        if any(x in parts for x in ('.bak','__pycache__','venv','.venv','node_modules')): continue
        if p.suffix == '.bak': continue
        if subdir and subdir not in parts: continue
        return p
    return None

results = {'ok':0,'skip':0,'fail':0}
def mark(s):
    if s=='ok': results['ok']+=1
    elif s=='skip': results['skip']+=1
    else: results['fail']+=1

# ============================================================
# FIX 1: vendedor.py - NameError (lineas 999-1003)
# ============================================================
def fix1(root):
    log("\n[FIX 1] vendedor.py -> NameError: factura", C.BOLD)
    p = find(root, 'vendedor.py', 'routes')
    if not p: err("vendedor.py no encontrado"); return mark('fail')
    c = readf(p); orig = c
    
    # Buscar la funcion cashea_pagar_cuota y dentro de ella el bug
    # El bloque exacto segun lineas 999-1003:
    old = """    # ✅ Verificar que la venta fue hecha por este vendedor
    venta = Venta.query.filter_by(
        nro_factura=factura.nro_factura,
        vendedor_id=vid,
    ).first()"""
    
    # Verificar cuantas veces aparece (debe ser 1, en cashea_pagar_cuota)
    if c.count(old) == 0:
        # Intentar con variante: puede tener otra indentacion
        patron = re.compile(
            r"(\s*# ✅ Verificar que la venta fue hecha por este vendedor\s*\n"
            r"\s*venta = Venta\.query\.filter_by\(\s*\n"
            r"\s*nro_factura=factura\.nro_factura,\s*\n"
            r"\s*vendedor_id=vid,\s*\n"
            r"\s*\)\.first\(\))"
        )
        m = patron.search(c)
        if not m:
            warn("Patron no encontrado"); return mark('skip')
        # Reemplazar con la version corregida (preservando indentacion)
        block = m.group(1)
        indent = re.match(r'(\s*)', block).group(1)
        new_block = (
            f"{indent}# ✅ Obtener la factura de la cuota (fix: `factura` no estaba definida)\n"
            f"{indent}factura = cuota.factura\n"
            f"{indent}if not factura:\n"
            f"{indent}    return jsonify({{'success': False, 'error': 'Cuota sin factura asociada'}}), 400\n"
            f"\n"
            f"{indent}# ✅ Verificar que la venta fue hecha por este vendedor\n"
            f"{indent}venta = Venta.query.filter_by(\n"
            f"{indent}    nro_factura=factura.nro_factura,\n"
            f"{indent}    vendedor_id=vid,\n"
            f"{indent}    usuario_id=padre_id,\n"
            f"{indent}).first()"
        )
        c = c.replace(block, new_block, 1)
        ok("NameError corregido (regex)")
    else:
        new = """    # ✅ Obtener la factura de la cuota (fix: `factura` no estaba definida)
    factura = cuota.factura
    if not factura:
        return jsonify({'success': False, 'error': 'Cuota sin factura asociada'}), 400

    # ✅ Verificar que la venta fue hecha por este vendedor
    venta = Venta.query.filter_by(
        nro_factura=factura.nro_factura,
        vendedor_id=vid,
        usuario_id=padre_id,
    ).first()"""
        c = c.replace(old, new, 1)
        ok("NameError corregido")
    
    if c != orig:
        backup(p); writef(p, c); ok(f"Actualizado: {p.name}"); return mark('ok')
    mark('skip')

# ============================================================
# FIX 2: vendedor.py - tipo_venta='credito' en Cashea (linea 308)
# ============================================================
def fix2(root):
    log("\n[FIX 2] vendedor.py -> tipo_venta Cashea", C.BOLD)
    p = find(root, 'vendedor.py', 'routes')
    if not p: err("vendedor.py no encontrado"); return mark('fail')
    c = readf(p); orig = c
    
    # Buscar la linea 308: tipo_venta='credito' dentro de la creacion de FacturaCobrar
    # en el bloque Cashea (despues de "if es_cashea and cashea_data:")
    # Estrategia: buscar "if es_cashea and cashea_data:" y luego el primer tipo_venta='credito'
    idx = c.find('if es_cashea and cashea_data:')
    if idx == -1:
        warn("Bloque 'if es_cashea and cashea_data:' no encontrado"); return mark('skip')
    
    # Buscar tipo_venta='credito' despues de idx
    target = "tipo_venta='credito'"
    idx2 = c.find(target, idx)
    if idx2 == -1:
        warn("tipo_venta='credito' no encontrado despues de Cashea"); return mark('skip')
    
    # Asegurar que no sea muy lejos (dentro del bloque Cashea, antes del proximo return)
    return_idx = c.find('return jsonify', idx2)
    if return_idx != -1 and idx2 > return_idx:
        warn("tipo_venta='credito' fuera del bloque Cashea"); return mark('skip')
    
    c = c[:idx2] + "tipo_venta='cashea'" + c[idx2 + len(target):]
    ok("tipo_venta cambiado a 'cashea' (linea 308)")
    
    if c != orig:
        backup(p); writef(p, c); ok(f"Actualizado: {p.name}"); return mark('ok')
    mark('skip')

# ============================================================
# FIX 3: auth.py - duplicados sesion_previa_activa (lineas 56-80)
# ============================================================
def fix3(root):
    log("\n[FIX 3] auth.py -> duplicados", C.BOLD)
    p = find(root, 'auth.py', 'routes')
    if not p: err("auth.py no encontrado"); return mark('fail')
    c = readf(p); orig = c
    
    # Segun la salida: 
    # linea 56:                        # ✅ Detectar si ya habia una sesion activa  (24 espacios)
    # linea 57:        sesion_previa_activa = bool(user.session_token)              (8 espacios)
    # linea 58: (blank)
    # linea 59:                # ✅ Detectar si ya habia una sesion activa          (16 espacios)
    # linea 60:        sesion_previa_activa = bool(user.session_token)              (8 espacios)
    # ... 
    # linea 74:        # Si habia una sesion previa...
    # linea 75:        if sesion_previa_activa:
    # linea 76:            flash(...)
    # linea 78:        # Si habia una sesion previa...
    # linea 79:        if sesion_previa_activa:
    # linea 80:            flash(...)
    
    # Patron: eliminar desde linea 59 (segundo comentario Detectar) hasta linea 60
    # Regex: capturar el primer bloque, eliminar el segundo
    patron_var = re.compile(
        r"(\s*# ✅ Detectar si ya habia una sesion activa\s*\n"
        r"\s*sesion_previa_activa = bool\(user\.session_token\))\s*\n\s*\n"
        r"\s*# ✅ Detectar si ya habia una sesion activa\s*\n"
        r"\s*sesion_previa_activa = bool\(user\.session_token\)"
    )
    if patron_var.search(c):
        c = patron_var.sub(r"\1", c, count=1)
        ok("Duplicado sesion_previa_activa eliminado")
    else:
        warn("Patron de sesion_previa_activa no encontrado")
    
    # Patron flash: eliminar segundo bloque if/flash
    patron_flash = re.compile(
        r"(\s*# Si habia una sesion previa, mostramos un mensaje de advertencia\s*\n"
        r"\s*if sesion_previa_activa:\s*\n"
        r"\s*flash\([^\n]+\))\s*\n\s*\n"
        r"\s*# Si habia una sesion previa, mostramos un mensaje de advertencia\s*\n"
        r"\s*if sesion_previa_activa:\s*\n"
        r"\s*flash\([^\n]+\)"
    )
    if patron_flash.search(c):
        c = patron_flash.sub(r"\1", c, count=1)
        ok("Duplicado flash eliminado")
    else:
        warn("Patron flash no encontrado")
    
    if c != orig:
        backup(p); writef(p, c); ok(f"Actualizado: {p.name}"); return mark('ok')
    mark('skip')

# ============================================================
# FIX 5: inventario.html - modal duplicado (lineas 1098-1340)
# ============================================================
def fix5(root):
    log("\n[FIX 5] inventario.html -> modal duplicado", C.BOLD)
    p = find(root, 'inventario.html', 'templates')
    if not p: err("inventario.html no encontrado"); return mark('fail')
    c = readf(p); orig = c
    
    # El marcador real es "MODAL: Importar inventario desde Excel" (sin <!-- al inicio)
    # Hay 2 ocurrencias. La primera (linea 867) es la buena.
    # La segunda (linea 1098) debe eliminarse hasta "MODAL: Escaner"
    marker = 'MODAL: Importar inventario desde Excel'
    positions = []
    s = 0
    while True:
        i = c.find(marker, s)
        if i == -1: break
        positions.append(i)
        s = i + 1
    
    info(f"Encontradas {len(positions)} ocurrencias del marcador")
    
    if len(positions) < 2:
        warn(f"Solo {len(positions)} ocurrencia(s). Nada que eliminar.")
        return mark('skip')
    
    # El segundo bloque empieza en positions[1]
    # Retroceder hasta el "<!--" que lo precede
    start_second = positions[1]
    # Buscar el "<!--" mas cercano antes
    comment_start = c.rfind('<!--', 0, start_second)
    if comment_start != -1 and comment_start > positions[0] + 100:
        start_second = comment_start
    
    # El fin: buscar "MODAL: Escaner de codigos de barras"
    escaner_marker = 'MODAL: Escaner de codigos de barras'
    escaner_idx = c.find(escaner_marker, start_second)
    if escaner_idx == -1:
        warn("Marcador de escaner no encontrado. Usando fin de archivo.")
        escaner_idx = len(c)
    else:
        # Retroceder hasta el "<!--" del escaner
        comment_escaner = c.rfind('<!--', start_second, escaner_idx)
        if comment_escaner != -1:
            escaner_idx = comment_escaner
    
    info(f"Eliminando desde pos {start_second} hasta {escaner_idx} ({escaner_idx - start_second} chars)")
    
    # Verificar que el bloque a eliminar contiene el modal duplicado
    block_to_remove = c[start_second:escaner_idx]
    if 'modalImportar' not in block_to_remove or 'inputExcel' not in block_to_remove:
        warn("El bloque no parece ser el modal. Saltando.")
        return mark('skip')
    
    c = c[:start_second] + c[escaner_idx:]
    ok(f"Modal duplicado eliminado ({len(block_to_remove)} chars)")
    
    if c != orig:
        backup(p); writef(p, c); ok(f"Actualizado: {p.name}"); return mark('ok')
    mark('skip')

# ============================================================
# MAIN
# ============================================================
def main():
    root_arg = '.'
    for a in sys.argv[1:]:
        if not a.startswith('--'): root_arg = a
    root = Path(root_arg).resolve()
    if not root.exists():
        print(f"ERROR: {root} no existe"); sys.exit(1)
    
    log(f"\n{'='*50}", C.INFO)
    log("REPARADOR POS FLASK v2", C.BOLD)
    log(f"{'='*50}", C.INFO)
    log(f"Proyecto: {root}", C.DIM)
    if DRY_RUN: log("MODO: DRY-RUN", C.WARN)
    else: log("MODO: REAL (backups .bak)", C.OK)
    
    fix1(root)
    fix2(root)
    fix3(root)
    fix5(root)
    
    log(f"\n{'='*50}", C.INFO)
    log(f"RESULTADO: {results['ok']} OK | {results['skip']} SKIP | {results['fail']} FAIL", C.BOLD)
    log(f"{'='*50}\n", C.INFO)

if __name__ == '__main__':
    main()