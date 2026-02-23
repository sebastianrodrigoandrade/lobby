import sys
import requests
from datetime import datetime

from src.database import engine, Base, SessionLocal
from src.utils import logger, IdentityResolver
from src.models import Legislador, Proyecto, Voto
from src.extractors.api_client import ArgentinaDatosClient, OpenDataPortalClient

def main():
    logger.info("=== INICIANDO PIPELINE DE INGESTA CONGRESO ===")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        api_client = ArgentinaDatosClient()
        portal_client = OpenDataPortalClient()

        # PASO 1: INGESTA DE PROYECTOS (con paginación completa)
        logger.info("--- Iniciando Ingesta de Proyectos ---")
        df_proyectos = portal_client.extract_hcdn_bills()

        nuevos_proyectos_count = 0
        if not df_proyectos.empty:
            # ✅ Cache en memoria de expedientes ya existentes
            expedientes_existentes = {
                p.nro_expediente
                for p in session.query(Proyecto.nro_expediente).all()
            }
            logger.info(f"Proyectos ya en DB: {len(expedientes_existentes)}")

            for _, row in df_proyectos.iterrows():
                expediente = row.get('nro_expediente')
                if not expediente:
                    continue

                # ✅ Chequeo en memoria, no query por cada fila
                if expediente in expedientes_existentes:
                    continue

                session.add(Proyecto(
                    nro_expediente=expediente,
                    titulo=row.get('titulo'),
                    fecha_ingreso=row.get('fecha_ingreso'),
                    estado=row.get('estado'),
                    autores=row.get('autores')
                ))
                expedientes_existentes.add(expediente)  # evitar duplicados dentro del mismo batch
                nuevos_proyectos_count += 1

                if nuevos_proyectos_count % 2000 == 0:
                    session.commit()
                    logger.info(f"  {nuevos_proyectos_count} proyectos insertados...")

            session.commit()
            logger.info(f"Se insertaron {nuevos_proyectos_count} proyectos nuevos.")

        # ---------------------------------------------------------
        # PASO 2: VOTACIONES Y RESOLUCIÓN DE IDENTIDADES
        # ---------------------------------------------------------
        logger.info("--- Iniciando Ingesta de Votos e Identidades ---")
        votos_data = api_client.get_votes_history("diputados")

        # Resolver legisladores únicos
        nombres_unicos = {
            r.get('diputado_nombre') for r in votos_data
            if r.get('diputado_nombre') and isinstance(r.get('diputado_nombre'), str)
        }
        logger.info(f"Procesando {len(nombres_unicos)} legisladores únicos...")

        for nombre in nombres_unicos:
            IdentityResolver.resolve_legislator(
                session, nombre=nombre, dni_cuit=None,
                camara='Diputados', bloque=None, distrito=None
            )
        session.commit()

        # ✅ Cache en memoria: evita query a DB por cada voto
        cache_legisladores = {
            leg.nombre_completo: leg.id
            for leg in session.query(Legislador).all()
        }
        logger.info(f"Cache cargado: {len(cache_legisladores)} legisladores.")

        # ✅ Deduplicación: traer acta_detalle_ids ya insertados
        from src.models import Voto as VotoModel
        ids_existentes = {
            v.acta_detalle_id
            for v in session.query(VotoModel.acta_detalle_id).all()
            if v.acta_detalle_id is not None
        }
        logger.info(f"Votos ya existentes en DB: {len(ids_existentes)}")

        logger.info("Insertando votos...")
        nuevos_votos = 0
        saltados = 0

        for registro in votos_data:
            nombre = registro.get('diputado_nombre')
            if not nombre or not isinstance(nombre, str):
                continue

            # ✅ Deduplicación por acta_detalle_id
            acta_detalle_id = registro.get('acta_detalle_id')
            if acta_detalle_id and acta_detalle_id in ids_existentes:
                saltados += 1
                continue

            legislador_id = cache_legisladores.get(nombre)
            if not legislador_id:
                continue

            session.add(Voto(
                legislador_id=legislador_id,
                acta_detalle_id=acta_detalle_id,
                acta_id=registro.get('acta_id'),
                voto_individual=registro.get('voto'),
            ))
            nuevos_votos += 1

            if nuevos_votos % 5000 == 0:
                session.commit()
                logger.info(f"  {nuevos_votos} votos insertados...")

        session.commit()
        logger.info(f"Pipeline finalizado. Nuevos: {nuevos_votos} | Saltados (ya existían): {saltados}")

    except Exception as e:
        logger.error(f"ERROR FATAL EN PIPELINE: {e}")
        session.rollback()
        raise e

    finally:
        session.close()
        logger.info("Sesión de base de datos cerrada.")

if __name__ == "__main__":
    main()