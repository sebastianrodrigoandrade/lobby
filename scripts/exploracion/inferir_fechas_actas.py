import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import warnings
warnings.filterwarnings('ignore')

URL_DETALLES = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/262cc543-3186-401b-b35e-dcdb2635976d/download/detalle-actas-datos-generales-2.4.csv"

def main():
    logger.info("=== INFIRIENDO FECHAS DE ACTAS ===")
    session = SessionLocal()

    try:
        # Cargar detalles
        logger.info("Descargando CSV de detalles...")
        df = pd.read_csv(URL_DETALLES, encoding='utf-8', usecols=['acta_id'])
        acta_ids_unicos = sorted(df['acta_id'].dropna().unique().astype(int).tolist())
        logger.info(f"acta_ids unicos en detalles: {len(acta_ids_unicos)}")

        # Cargar cabecera existente con fechas
        result = session.execute(text("""
            SELECT acta_id, fecha, titulo, resultado,
                   votos_afirmativos, votos_negativos, abstenciones, ausentes
            FROM actas_cabecera
            WHERE fecha IS NOT NULL
            ORDER BY acta_id
        """))
        df_cab = pd.DataFrame(result.fetchall(), columns=result.keys())
        logger.info(f"Actas con fecha en DB: {len(df_cab)}")

        # Ver qué acta_ids faltan
        ids_con_fecha = set(df_cab['acta_id'].tolist())
        ids_sin_fecha = [i for i in acta_ids_unicos if i not in ids_con_fecha]
        logger.info(f"acta_ids sin fecha: {len(ids_sin_fecha)}")

        if not ids_sin_fecha:
            logger.info("No hay IDs sin fecha. Nada que hacer.")
            return

        # Interpolación: para cada ID sin fecha, buscar el más cercano con fecha
        df_cab_sorted = df_cab.sort_values('acta_id').reset_index(drop=True)
        ids_conocidos = df_cab_sorted['acta_id'].values
        fechas_conocidas = df_cab_sorted['fecha'].values

        logger.info("Insertando actas inferidas...")
        nuevos = 0

        for acta_id in ids_sin_fecha:
            # Buscar el acta_id conocido más cercano
            diff = abs(ids_conocidos - acta_id)
            idx_mas_cercano = diff.argmin()
            fecha_inferida = fechas_conocidas[idx_mas_cercano]
            acta_ref = int(ids_conocidos[idx_mas_cercano])

            # Solo insertar si la diferencia no es enorme (max 200 IDs de distancia)
            if diff[idx_mas_cercano] > 200:
                continue

            session.execute(text("""
                INSERT INTO actas_cabecera (acta_id, fecha, titulo, resultado)
                VALUES (:acta_id, :fecha, :titulo, :resultado)
                ON CONFLICT (acta_id) DO NOTHING
            """), {
                'acta_id': acta_id,
                'fecha': fecha_inferida,
                'titulo': f'(Inferido desde acta {acta_ref})',
                'resultado': ''
            })
            nuevos += 1

            if nuevos % 200 == 0:
                session.commit()
                logger.info(f"  {nuevos} actas inferidas insertadas...")

        session.commit()
        logger.info(f"Total actas inferidas: {nuevos}")

        # Verificar cobertura final
        result2 = session.execute(text("""
            SELECT COUNT(DISTINCT v.acta_id) as votos_con_fecha
            FROM votos v
            JOIN actas_cabecera a ON a.acta_id = v.acta_id
            WHERE a.fecha IS NOT NULL
        """))
        cobertura = result2.fetchone()[0]
        logger.info(f"Votos con fecha despues de inferencia: {cobertura}")

    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    main()