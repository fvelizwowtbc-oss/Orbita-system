/* ============================================================
   animaciones.js - Control de animaciones de Orbita System
   ============================================================ */
(function () {
    'use strict';

    const STORAGE_KEY = 'orbita_anim_off';

    function marcarAnimReady() {
        document.documentElement.classList.add('anim-ready');
    }

    function aplicarStagger() {
        document.querySelectorAll('[data-anim-stagger]').forEach((container) => {
            Array.from(container.children).forEach((child, i) => {
                if (!child.hasAttribute('style') || !child.style.animationDelay) {
                    child.style.animationDelay = `${Math.min(i * 40, 400)}ms`;
                }
                if (!child.classList.contains('anim-slide-up')) {
                    child.classList.add('anim-slide-up');
                }
            });
        });
    }

    function activarScrollAnimations() {
        const els = document.querySelectorAll('[data-anim-scroll]');
        if (!els.length) return;

        if (!('IntersectionObserver' in window)) {
            els.forEach((el) => el.classList.add('anim-fade-in'));
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const tipo = entry.target.dataset.animScroll || 'fade-in';
                        entry.target.classList.add(`anim-${tipo}`);
                        entry.target.style.opacity = '';
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
        );

        els.forEach((el) => {
            el.style.opacity = '0';
            observer.observe(el);
        });
    }

    function activarShakeEnErrores() {
        document.querySelectorAll('[data-shake-on-error]').forEach((el) => {
            el.classList.add('anim-shake');
            setTimeout(() => el.classList.remove('anim-shake'), 500);
        });
    }

    function activarRipple() {
        document.querySelectorAll('[data-ripple]').forEach((btn) => {
            if (btn.dataset.rippleReady) return;

            // NO aplicar ripple si el boton contiene elementos complejos
            const tieneElementoComplejo = btn.querySelector(
                'video, canvas, input, textarea, select, iframe, svg, img, ' +
                '[class*="absolute"], [class*="fixed"], [data-no-ripple]'
            );
            if (tieneElementoComplejo) {
                btn.removeAttribute('data-ripple');
                return;
            }

            // NO aplicar ripple si el boton ya es absolute/fixed
            const pos = getComputedStyle(btn).position;
            if (pos === 'absolute' || pos === 'fixed' || pos === 'sticky') {
                btn.removeAttribute('data-ripple');
                return;
            }

            // NO aplicar ripple si el boton tiene overflow hidden propio
            if (getComputedStyle(btn).overflow === 'hidden') {
                btn.removeAttribute('data-ripple');
                return;
            }

            btn.dataset.rippleReady = '1';
            btn.style.position = 'relative';
            btn.style.overflow = 'hidden';

            btn.addEventListener('click', (e) => {
                const rect = btn.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const ripple = document.createElement('span');

                ripple.style.cssText = `
                    position: absolute;
                    left: ${e.clientX - rect.left - size / 2}px;
                    top: ${e.clientY - rect.top - size / 2}px;
                    width: ${size}px;
                    height: ${size}px;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.4);
                    transform: scale(0);
                    opacity: 1;
                    pointer-events: none;
                    animation: ripple 600ms ease-out;
                    z-index: 1;
                `;

                btn.appendChild(ripple);
                setTimeout(() => ripple.remove(), 600);
            });
        });
    }

    function inyectarRippleKeyframe() {
        if (document.getElementById('anim-ripple-kf')) return;
        const style = document.createElement('style');
        style.id = 'anim-ripple-kf';
        style.textContent = `
            @keyframes ripple {
                to { transform: scale(2.5); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    function activarContadores() {
        document.querySelectorAll('[data-count-to]').forEach((el) => {
            if (el.dataset.counted) return;
            el.dataset.counted = '1';

            const target = parseFloat(el.dataset.countTo);
            const duration = parseInt(el.dataset.countDuration || '800', 10);
            const decimals = parseInt(el.dataset.countDecimals || '0', 10);
            const start = performance.now();
            const initial = 0;

            function tick(now) {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const value = initial + (target - initial) * eased;
                el.textContent = value.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                if (progress < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }

    function aplicarPreferencia() {
        const off = localStorage.getItem(STORAGE_KEY) === '1';
        document.body.classList.toggle('anim-off', off);
    }

    window.animToggle = function () {
        const off = document.body.classList.toggle('anim-off');
        localStorage.setItem(STORAGE_KEY, off ? '1' : '0');
        return !off;
    };

    function init() {
        aplicarPreferencia();
        inyectarRippleKeyframe();
        marcarAnimReady();
        aplicarStagger();
        activarScrollAnimations();
        activarRipple();
        activarContadores();

        requestAnimationFrame(activarShakeEnErrores);

        if ('MutationObserver' in window) {
            const obs = new MutationObserver((mutations) => {
                let needsRipple = false;
                let needsStagger = false;
                let needsCount = false;

                mutations.forEach((m) => {
                    m.addedNodes.forEach((node) => {
                        if (node.nodeType !== 1) return;
                        if (node.matches?.('[data-ripple], [data-ripple] *')) needsRipple = true;
                        if (node.matches?.('[data-anim-stagger], [data-anim-stagger] *')) needsStagger = true;
                        if (node.matches?.('[data-count-to]')) needsCount = true;
                    });
                });

                if (needsRipple) activarRipple();
                if (needsStagger) aplicarStagger();
                if (needsCount) activarContadores();
            });
            obs.observe(document.body, { childList: true, subtree: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
