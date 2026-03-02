import requests
import pandas as pd
from io import StringIO
from src.database import SessionLocal
from src.models import Sesion
from src.utils import logger
import warnings
warnings.filterwarnings('ignore')

URL = "https://datos.hcdn.gob.ar/dataset/f744ea10-83b4-4493-8bef-6fc9fb9e41e9/resource/4ac70a51-a82d-4290-8a73-d7f8ec38d5a0/download/sesiones.csv"

def main():
    logger.info("=== INGESTA DE SESIONES ===")
    session = SessionLocal()
    try:
        logger.info("Descargando CSV de sesiones...")
        r = requests.get(URL, timeout=30, verify=False)
        df = pd.read_csv(StringIO(r.text), encoding='utf-8-sig', on_bad_lines='skip')
        logger.info(f"CSV cargado: {len(df)} sesiones")

        existentes = {
            s.periodo_id
            for s in session.query(Sesion.periodo_id).all()
            if s.periodo_id
        }
        logger.info(f"Sesiones ya en DB: {len(existentes)}")

        nuevas = 0
        for _, row in df.iterrows():
            periodo_id = row.get('periodo_id')
            if not periodo_id or periodo_id in existentes:
                continue
            session.add(Sesion(
                fecha=pd.to_datetime(row.get('reunion_inicio')).date() if pd.notna(row.get('reunion_inicio')) else None,
                tipo_periodo=row.get('tipo_periodo'),
                tipo_reunion=row.get('reunion_tipo'),
                duracion_horas=str(round(row.get('duracion_horas', 0), 2)),
                hubo_quorum=row.get('hubo_quorum'),
                periodo_id=periodo_id,
            ))
            existentes.add(periodo_id)
            nuevas += 1

        session.commit()
        logger.info(f"Sesiones insertadas: {nuevas}")
    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
