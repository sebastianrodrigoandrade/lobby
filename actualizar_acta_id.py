import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import warnings
warnings.filterwarnings('ignore')

URL = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/262cc543-3186-401b-b35e-dcdb2635976d/download/detalle-actas-datos-generales-2.4.csv"

def main():
    logger.info("=== ACTUALIZANDO acta_id EN VOTOS ===")
    
    df = pd.read_csv(URL, encoding='utf-8', usecols=['acta_id', 'acta_detalle_id'])
    df = df.dropna()
    df['acta_id'] = df['acta_id'].astype(int)
    df['acta_detalle_id'] = df['acta_detalle_id'].astype(int)
    logger.info(f"CSV cargado: {len(df)} registros")

    session = SessionLocal()
    try:
        actualizados = 0
        batch_size = 5000

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            # Construir VALUES para UPDATE masivo
            values = ', '.join(
                f"({row['acta_detalle_id']}, {row['acta_id']})"
                for _, row in batch.iterrows()
            )
            
            result = session.execute(text(f"""
                UPDATE votos v
                SET acta_id = c.acta_id
                FROM (VALUES {values}) AS c(acta_detalle_id, acta_id)
                WHERE v.acta_detalle_id = c.acta_detalle_id
                AND v.acta_id IS NULL
            """))
            
            actualizados += result.rowcount
            session.commit()
            logger.info(f"  Procesados {min(i+batch_size, len(df))}/{len(df)} — actualizados: {actualizados}")

        logger.info(f"Total votos actualizados: {actualizados}")

    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    main()
    