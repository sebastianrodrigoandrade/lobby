import pandas as pd
from src.database import SessionLocal
from src.models import Sesion
from src.utils import logger

# Necesitamos agregar un modelo TemarioItem - por ahora guardamos en la tabla sesiones
# como campo de texto JSON, o creamos tabla nueva.
# Opción simple: tabla temario_items

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base, engine

class TemarioItem(Base):
    __tablename__ = 'temario_items'
    
    id = Column(Integer, primary_key=True, index=True)
    sesion_id = Column(Integer, ForeignKey('sesiones.id'))
    item_nro = Column(Integer)
    descripcion = Column(Text)

Base.metadata.create_all(bind=engine)

def main():
    logger.info("=== INGESTA DE TEMARIO ===")
    session = SessionLocal()
    
    try:
        df = pd.read_csv('temario_extraordinarias.csv', encoding='utf-8-sig')
        logger.info(f"CSV cargado: {len(df)} items")

        # Cache de sesiones por periodo_id
        sesiones = {s.periodo_id: s.id for s in session.query(Sesion).all()}
        logger.info(f"Sesiones en DB: {len(sesiones)}")

        # Cache de items ya existentes
        existentes = {
            (t.sesion_id, t.item_nro)
            for t in session.query(TemarioItem.sesion_id, TemarioItem.item_nro).all()
        }

        nuevos = 0
        sin_sesion = 0

        for _, row in df.iterrows():
            periodo_id = row.get('periodo_id')
            sesion_id = sesiones.get(periodo_id)
            
            if not sesion_id:
                sin_sesion += 1
                continue

            key = (sesion_id, int(row['item_nro']))
            if key in existentes:
                continue

            session.add(TemarioItem(
                sesion_id=sesion_id,
                item_nro=int(row['item_nro']),
                descripcion=row.get('descripcion')
            ))
            existentes.add(key)
            nuevos += 1

        session.commit()
        logger.info(f"Items insertados: {nuevos}")
        if sin_sesion:
            logger.warning(f"Items sin sesion matching: {sin_sesion}")

    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    main()