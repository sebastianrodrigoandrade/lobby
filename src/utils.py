import logging
import sys
import re
from thefuzz import fuzz, process

# Configuración del Logger
def setup_logger():
    logger = logging.getLogger("CongresoIngestor")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Handler Consola
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        
        # Handler Archivo
        fh = logging.FileHandler("ingesta.log")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

logger = setup_logger()

class IdentityResolver:
    @staticmethod
    def clean_cuit_dni(value: str) -> str:
        """Limpia strings para dejar solo números."""
        if not value:
            return None
        return re.sub(r'\D', '', str(value))

    @staticmethod
    def resolve_legislator(session, nombre, dni_cuit, camara, bloque, distrito):
        from src.models import Legislador
        
        # ✅ FIX: si el nombre no es string válido, no podemos procesar
        if not nombre or not isinstance(nombre, str):
            return None
        
        clean_id = IdentityResolver.clean_cuit_dni(dni_cuit) or None
        legislador = None

        # 2. Intento A: Buscar por DNI/CUIT (Identificación Fuerte)
        if clean_id:
            legislador = session.query(Legislador).filter_by(dni_cuit=clean_id).first()
            if legislador:
                # Opcional: Actualizar datos si faltan
                return legislador

        # 3. Intento B: Buscar por Nombre Parecido (Fuzzy Matching)
        # Solo si no tenemos DNI o no encontramos nada por DNI
        if not legislador:
            legislador = IdentityResolver.fuzzy_match_legislator(session, Legislador, nombre)

        # 4. Intento C: Crear nuevo (Si todo lo anterior falló)
        if not legislador:
            logger.debug(f"Nuevo legislador detectado: {nombre} (DNI: {clean_id})")
            legislador = Legislador(
                nombre_completo=nombre,
                dni_cuit=clean_id, # Puede ser None
                camara=camara,
                bloque=bloque,
                distrito=distrito
            )
            session.add(legislador)
            session.commit() # Guardamos para que tenga ID inmediato
            
        return legislador

    @staticmethod
    def fuzzy_match_legislator(session, model_legislador, name_dirty, threshold=90):
        # ✅ FIX: validar que el nombre sea un string válido
        if not name_dirty or not isinstance(name_dirty, str):
            return None
            
        existing = session.query(model_legislador.id, model_legislador.nombre_completo).all()
        candidates = {leg.nombre_completo: leg.id for leg in existing if leg.nombre_completo}
        
        if not candidates:
            return None
        
        best_match, score = process.extractOne(name_dirty, candidates.keys(), scorer=fuzz.token_sort_ratio)
        
        if score >= threshold:
            legislador_id = candidates[best_match]
            logger.debug(f"[MATCH] '{name_dirty}' identificado como '{best_match}' (Confianza: {score}%)")
            return session.get(model_legislador, legislador_id)
        
        return None