/* ============================================================
   autofocus_scanner.js
   Auto-foco en #buscadorProductos + deteccion de escaner fisico.
   Compatible con user/ventas.html y vendedor/ventas.html.

   Flujo:
     Escaner escribe codigo -> filtrarProductos() se dispara en oninput
     -> al terminar (100ms sin teclas), buscamos por data-codigo
     -> click en el producto (agregarDesdeElemento) -> carrito
     -> limpiamos input -> foco vuelve al buscador
   ============================================================ */
(function () {
    'use strict';

    // ⚠️ NO ejecutar en móvil (el auto-foco cierra el teclado)
    if (/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)) {
        console.log('[autofocus] Desactivado en móvil');
        return;
    }

    // ---------- Config ----------
    const INPUT_ID = 'buscadorProductos';
    const UMBRAL_ESCANER_MS = 50;      // teclas mas rapidas que esto = escaner
    const PAUSA_POST_ESCANER_MS = 100; // ms sin teclas = fin de escaneo

    // Inputs donde SI se permite escribir sin que el auto-foco robe
    const INPUTS_PERMITIDOS = [
        'select',
        'option',
        'textarea',
        'input[type="number"]',
        'input[type="checkbox"]',
        'input[type="radio"]',
        'input[type="date"]',
        'input[type="tel"]',
        'input[name="cliente_nombre"]',
        'input[name="telefono"]',
        'input[name="documento"]',
        'input[name="cantidad"]',
        'input[name="precio_usd"]',
        'input[name="monto"]',
        'input[name="notas"]',
        'input[type="number"]',
        'input[name="cliente_nombre"]',
        'input[name="telefono"]',
        'input[name="documento"]',
        'input[name="cantidad"]',
        'input[name="precio_usd"]',
        'input[name="monto"]',
        'input[name="notas"]',
        'textarea',
        '.cantidad-input',
    ];

    let inputBusqueda = null;
    let bufferEscaner = '';
    let timerEscaner = null;
    let ultimaTecla = 0;

    // ---------- Helpers ----------
    function esInputPermitido(el) {
        if (!el) return false;
        if (el === inputBusqueda) return false;
        for (const sel of INPUTS_PERMITIDOS) {
            if (el.matches(sel)) return true;
        }
        return false;
    }

    function hayModalAbierto() {
        return !!(
            document.querySelector('[data-modal-open="1"]') ||
            document.querySelector('.modal-overlay:not(.hidden)') ||
            document.querySelector('#modalPago:not(.hidden)') ||
            document.querySelector('#modalElegirVariante:not(.hidden)') ||
            document.querySelector('#modalEscanerVentas:not(.hidden)') ||
            document.querySelector('.swal2-container')
        );
    }

    function enfocarBuscador() {
        // No robar foco si hay un select abierto
        if (document.activeElement && document.activeElement.tagName === 'SELECT') return;
        if (document.activeElement && document.activeElement.tagName === 'OPTION') return;
        
        if (!inputBusqueda) return;
        if (document.activeElement === inputBusqueda) return;
        if (esInputPermitido(document.activeElement)) return;
        if (hayModalAbierto()) return;
        try {
            inputBusqueda.focus({ preventScroll: true });
        } catch (e) {
            inputBusqueda.focus();
        }
    }

    // ---------- Buscar producto por codigo ----------
    function buscarProductoPorCodigo(codigo) {
        const productos = document.querySelectorAll('.producto-item');
        const codigoNorm = normalizar(codigo);
        for (const p of productos) {
            if (normalizar(p.dataset.codigo || '') === codigoNorm) {
                return p;
            }
        }
        return null;
    }

    function normalizar(s) {
        if (!s) return '';
        return String(s).toLowerCase().trim();
    }

    // ---------- Procesar escaneo completo ----------
    function procesarEscaneo(codigo) {
        const valor = (codigo || '').trim();
        if (!valor) return;

        // 1. Filtrar productos (por si oninput no lo hizo)
        if (typeof window.filtrarProductos === 'function') {
            try { window.filtrarProductos(); } catch (e) {}
        }

        // 2. Buscar el producto por data-codigo exacto
        const producto = buscarProductoPorCodigo(valor);

        if (producto) {
            console.log('[scanner] Codigo encontrado:', valor, '->', producto.dataset.nombre);
            // 3. Click en el producto (dispara agregarDesdeElemento)
            producto.click();
        } else {
            // 4. Fallback: si no hay match exacto, buscar el primer visible (filtro parcial)
            const visibles = Array.from(document.querySelectorAll('.producto-item'))
                .filter(el => el.style.display !== 'none' && el.offsetParent !== null);

            if (visibles.length === 1) {
                console.log('[scanner] Un solo resultado visible, agregando:', visibles[0].dataset.nombre);
                visibles[0].click();
            } else if (visibles.length > 1) {
                console.warn('[scanner] Multiples resultados para "' + valor + '". Usa el mouse o escanea codigo exacto.');
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Multiples productos',
                        text: 'Se encontraron varios productos. Escanea el codigo exacto o haz click en uno.',
                        timer: 2000,
                        showConfirmButton: false,
                    });
                }
            } else {
                console.warn('[scanner] Producto no encontrado:', valor);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No encontrado',
                        text: 'Codigo: ' + valor,
                        timer: 1500,
                        showConfirmButton: false,
                    });
                }
            }
        }

        // 5. Limpiar input y re-disparar filtro
        if (inputBusqueda) {
            inputBusqueda.value = '';
            if (typeof window.filtrarProductos === 'function') {
                try { window.filtrarProductos(); } catch (e) {}
            }
        }

        // 6. Volver a enfocar
        setTimeout(enfocarBuscador, 100);
    }

    // ---------- Detectar teclas del escaner ----------
    function alTeclear(e) {
        if (!inputBusqueda) return;
        if (document.activeElement !== inputBusqueda) return;

        const ahora = Date.now();
        const delta = ahora - ultimaTecla;
        const esRafaga = delta < UMBRAL_ESCANER_MS;

        // Enter: procesar inmediatamente
        if (e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation();
            clearTimeout(timerEscaner);
            const valor = inputBusqueda.value.trim();
            bufferEscaner = '';
            if (valor) {
                procesarEscaneo(valor);
            }
            return;
        }

        // Tecla normal: acumular en buffer si es rafaga
        if (e.key.length === 1) {
            if (esRafaga) {
                bufferEscaner += e.key;
            } else {
                // No es rafaga (tecleo humano), resetear buffer
                bufferEscaner = e.key;
            }
            ultimaTecla = ahora;

            // Programar procesamiento despues de pausa
            clearTimeout(timerEscaner);
            timerEscaner = setTimeout(() => {
                // Si el buffer tiene >= 4 caracteres y no hay Enter,
                // probablemente fue escaner sin Enter
                const valor = inputBusqueda.value.trim();
                if (valor.length >= 4 && bufferEscaner.length >= 4) {
                    // Solo auto-procesar si hubo rafaga
                    // (si el usuario tecleo normal, no procesamos, espera Enter)
                    const fueRafaga = bufferEscaner.length >= 4 && 
                        (ultimaTecla - (ultimaTecla - UMBRAL_ESCANER_MS)) < UMBRAL_ESCANER_MS;
                    // Heuristica: si escribio 4+ caracteres en rafaga, procesar
                    if (valor.length >= 6) {
                        console.log('[scanner] Escaneo sin Enter detectado, procesando:', valor);
                        bufferEscaner = '';
                        procesarEscaneo(valor);
                    }
                }
                bufferEscaner = '';
            }, PAUSA_POST_ESCANER_MS);
        }
    }

    // ---------- Click fuera -> volver al buscador ----------
    function alClick(e) {
        if (e.target.closest('button, a, input, textarea, select, [role="button"], .swal2-container, .modal-overlay')) {
            return;
        }
        setTimeout(enfocarBuscador, 50);
    }

    // ---------- Inicializar ----------
    function init() {
        inputBusqueda = document.getElementById(INPUT_ID);

        if (!inputBusqueda) {
            // Fallback: buscar por placeholder
            inputBusqueda = document.querySelector('input[placeholder*="scanner" i], input[placeholder*="escanear" i], input[placeholder*="buscar producto" i]');
        }

        if (!inputBusqueda) {
            console.warn('[autofocus] No se encontro input de busqueda');
            return;
        }

        console.log('[autofocus] Input encontrado:', inputBusqueda);

        inputBusqueda.setAttribute('autocomplete', 'off');
        inputBusqueda.setAttribute('autocorrect', 'off');
        inputBusqueda.setAttribute('autocapitalize', 'off');
        inputBusqueda.setAttribute('spellcheck', 'false');
        inputBusqueda.setAttribute('data-scanner', '1');

        // Enfocar al cargar
        setTimeout(enfocarBuscador, 300);

        // Re-enfocar al perder foco
        inputBusqueda.addEventListener('blur', () => {
            setTimeout(() => {
                if (document.activeElement === document.body && !hayModalAbierto()) {
                    enfocarBuscador();
                }
            }, 100);
        });

        // Detector de teclas del escaner
        inputBusqueda.addEventListener('keydown', alTeclear);

        // Cualquier tecla en el documento
        document.addEventListener('keydown', (e) => {
        // No interferir si el usuario está en un select
        if (document.activeElement && document.activeElement.tagName === 'SELECT') return;
        if (e.target && (e.target.tagName === 'SELECT' || e.target.tagName === 'OPTION')) return;
        
            if (esInputPermitido(document.activeElement)) return;
            if (document.activeElement === inputBusqueda) return;
            if (hayModalAbierto()) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            if (e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete') {
                enfocarBuscador();
            }
        });

        // Click fuera
        document.addEventListener('click', alClick);

        // Re-enfocar despues de cerrar modal
        const observer = new MutationObserver(() => {
            if (!hayModalAbierto()) {
                setTimeout(enfocarBuscador, 100);
            }
        });
        observer.observe(document.body, {
            attributes: true,
            childList: true,
            subtree: true,
            attributeFilter: ['class', 'data-modal-open'],
        });

        // Exponer funcion global
        window.enfocarBuscador = enfocarBuscador;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
