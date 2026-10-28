# app/services/tasas.py
import os
import json
import time
import logging
import requests
from datetime import datetime, date

from flask import current_app
from ..extensions import db
from ..models.config import ConfigTasa


logger = logging.getLogger(__name__)


class TasasService:

    @staticmethod
    def obtener_tasa_bcv(force=False):
        """Obtiene la tasa oficial del BCV con cache de 1h."""
        ttl = current_app.config.get('TASA_CACHE_TTL', 3600)
        fallback = current_app.config.get('TASA_FALLBACK', 50.0)

        cache_file = current_app.config.get("TASA_CACHE_FILE", "tasa_cache.json")
        if not force and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    if (time.time() - cache.get('timestamp', 0)) < ttl:
                        return float(cache['tasa'])
            except Exception:
                pass

        tasa = TasasService._fetch_remoto() or fallback

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'tasa': tasa, 'timestamp': time.time()}, f)
        except Exception as e:
            logger.warning(f'No se pudo guardar cache de tasa: {e}')

        return tasa

    @staticmethod
    def _fetch_remoto():
        # Intento 1: exchangerate-api
        try:
            r = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=8)
            if r.status_code == 200:
                t = float(r.json().get('rates', {}).get('VES', 0))
                if 10 < t < 10000:
                    return t
        except Exception as e:
            logger.debug(f'exchangerate-api falló: {e}')

        # Intento 2: dolartoday
        try:
            r = requests.get(
                'https://s3.amazonaws.com/dolartoday/data.json',
                timeout=8,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if r.status_code == 200:
                data = r.json()
                t = float(data.get('USD', {}).get('sicad2')
                          or data.get('USD', {}).get('promedio') or 0)
                if 10 < t < 10000:
                    return t
        except Exception as e:
            logger.debug(f'dolartoday falló: {e}')

        return None

    @staticmethod
    def obtener_tasas(usuario_id):
        """Devuelve la tasa activa segun el modo elegido."""
        defaults = {
            'oficial': 50.0,
            'manual1': 52.0,
            'manual2': 54.0,
            'activa': 'oficial',
            'fuente_oficial': 'BCV',
            'actualizado_en': '',
            'modo_tasa': 'auto',
            'tasa_manual_valor': 0,
            'tasa_bcv': 50.0,
        }
        if not usuario_id:
            return defaults

        config = ConfigTasa.query.filter_by(usuario_id=usuario_id) \
            .order_by(ConfigTasa.id.desc()).first()

        if not config:
            tasa_actual = TasasService.obtener_tasa_bcv()
            config = ConfigTasa(
                usuario_id=usuario_id,
                tasa_oficial=tasa_actual,
                tasa_manual1=tasa_actual + 2,
                tasa_manual2=tasa_actual + 4,
                tasa_activa='oficial',
                fuente_oficial='BCV',
                modo_tasa='auto',
                tasa_manual_valor=0,
            )
            db.session.add(config)
            db.session.commit()

        modo = getattr(config, 'modo_tasa', 'auto') or 'auto'
        tasa_manual = float(getattr(config, 'tasa_manual_valor', 0) or 0)
        tasa_bcv = float(config.tasa_oficial or 50)

        if modo == 'manual' and tasa_manual > 0:
            tasa_activa = tasa_manual
            fuente = 'Manual'
        else:
            if 10 < tasa_bcv < 100000:
                tasa_activa = tasa_bcv
                fuente = 'BCV'
            elif tasa_manual > 0:
                tasa_activa = tasa_manual
                fuente = 'Manual (respaldo)'
            else:
                tasa_activa = 50.0
                fuente = 'Default'

        return {
            'oficial': tasa_activa,
            'manual1': tasa_activa * 1.02,
            'manual2': tasa_activa * 1.04,
            'activa': 'oficial',
            'fuente_oficial': fuente,
            'actualizado_en': config.actualizado_en.strftime('%d/%m/%Y %H:%M')
                if config.actualizado_en else '',
            'modo_tasa': modo,
            'tasa_manual_valor': tasa_manual,
            'tasa_bcv': tasa_bcv,
        }

    @staticmethod
    def cambiar_modo_tasa(usuario_id, modo, tasa_manual=None):
        """Cambia el modo de tasa (auto/manual)."""
        try:
            config = ConfigTasa.query.filter_by(usuario_id=usuario_id) \
                .order_by(ConfigTasa.id.desc()).first()
            
            if not config:
                return False, 'No hay configuracion de tasa'
            
            if modo not in ('auto', 'manual'):
                return False, 'Modo invalido'
            
            config.modo_tasa = modo
            
            if tasa_manual is not None:
                tasa_manual = float(tasa_manual)
                if tasa_manual <= 0:
                    return False, 'La tasa manual debe ser mayor a 0'
                config.tasa_manual_valor = tasa_manual
            
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def actualizar_tasa_oficial(usuario_id, force=False):
        tasa = TasasService.obtener_tasa_bcv(force=force)
        config = ConfigTasa.query.filter_by(usuario_id=usuario_id) \
            .order_by(ConfigTasa.id.desc()).first()
        if config:
            config.tasa_oficial = tasa
            config.fuente_oficial = 'BCV'
            config.tasa_activa = 'oficial'
            db.session.commit()
        return tasa

    @staticmethod
    def configurar_tasas(usuario_id, manual1, manual2, activa='oficial'):
        config = ConfigTasa.query.filter_by(usuario_id=usuario_id) \
            .order_by(ConfigTasa.id.desc()).first()
        if not config:
            return False
        config.tasa_manual1 = manual1
        config.tasa_manual2 = manual2
        config.tasa_activa = activa
        db.session.commit()
        return True

    @staticmethod
    def calcular_precios(precio_usd, tasas):
        """Calcula el precio en las 3 tasas."""
        p = float(precio_usd or 0)
        return {
            'usd': round(p, 2),
            'oficial': round(p * tasas.get('oficial', 50), 2),
            'manual1': round(p * tasas.get('manual1', 52), 2),
            'manual2': round(p * tasas.get('manual2', 54), 2),
        }