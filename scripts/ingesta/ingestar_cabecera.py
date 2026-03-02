import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.models import ActaCabecera
from src.utils import logger
import warnings
warnings.filterwarnings('ignore')

URLS_CABECERA = [
    "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/28bdc184-d8e3-4d50-b5b5-e2151f902ac7/download/actas-datos-generales-2.4.csv",
    "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/59c05ba8-ad0a-4d55-803d-20e3fe464d0b/download/actas-cabecera-137-2.0.csv",
    "https://datos.hcdn.gob.ar:443/dataset/59fff38a-0a79-405b-a11b-29bc8722891b/resource/4a1f2093-c77a-4205-b53d-c5a0a8458e2c/download/actas-datos-generales-135.csv",
    "https://datos.hcdn.gob.ar:443/dataset/59fff38a-0a79-405b-a11b-29bc8722891b/resource/c3c30d22-5b4f-4f4c-8873-cf298cb1ea53/download/votaciones-nominales-periodos-129-a-135-cabecera.csv",
]

def main():
    logger.info("=== INGESTA CABECERA VOTACIONES ===")
    session = SessionLocal()

    try:
        # Cargar y combinar todos los CSVs
        dfs = []
        for url in URLS_CABECERA:
            try:
                logger.info(f"Descargando: {url.split('/')[-1]}")
                df_temp = pd.read_csv(url, encoding='utf-8')
                df_temp.columns = df_temp.columns.str.lower().str.strip()
                dfs.append(df_temp)
                logger.info(f"  {len(df_temp)} registros")
            except Exception as e:
                logger.warning(f"No se pudo descargar {url}: {e}")

        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=['acta_id'])
        logger.info(f"Total registros cabecera combinados: {len(df)}")

        # Cache de acta_ids ya existentes
        existentes = {
            row[0] for row in session.execute(text("SELECT acta_id FROM actas_cabecera")).fetchall()
        }
        logger.info(f"Ya en DB: {len(existentes)}")

        nuevos = 0
        for _, row in df.iterrows():
            acta_id = row.get('acta_id')
            if pd.isna(acta_id) or int(acta_id) in existentes:
                continue

            fecha = None
            try:
                fecha = pd.to_datetime(row.get('fecha')).date()
            except:
                pass

            session.add(ActaCabecera(
                acta_id=int(acta_id),
                sesion_id=str(row.get('sesion_id', '')),
                nroperiodo=int(row['nroperiodo']) if not pd.isna(row.get('nroperiodo')) else None,
                tipo_periodo=str(row.get('tipo_periodo', '')),
                reunion=int(row['reunion']) if not pd.isna(row.get('reunion')) else None,
                fecha=fecha,
                hora=str(row.get('hora', '')),
                titulo=str(row.get('titulo', '')),
                resultado=str(row.get('resultado', '')),
                votos_afirmativos=int(row['votos_afirmativos']) if not pd.isna(row.get('votos_afirmativos')) else None,
                votos_negativos=int(row['votos_negativos']) if not pd.isna(row.get('votos_negativos')) else None,
                abstenciones=int(row['abstenciones']) if not pd.isna(row.get('abstenciones')) else None,
                ausentes=int(row['ausentes']) if not pd.isna(row.get('ausentes')) else None,
            ))
            existentes.add(int(acta_id))
            nuevos += 1

            if nuevos % 500 == 0:
                session.commit()
                logger.info(f"  {nuevos} actas insertadas...")

        session.commit()
        logger.info(f"Actas insertadas: {nuevos}")

    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    main()