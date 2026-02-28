import os
os.environ['DB_USER'] = 'neondb_owner'
os.environ['DB_PASS'] = 'npg_kASKs8f9jdHT'
os.environ['DB_HOST'] = 'ep-patient-shadow-aiqmylpa-pooler.c-4.us-east-1.aws.neon.tech'
os.environ['DB_NAME'] = 'neondb'
os.environ['DB_PORT'] = '5432'

from src.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Marcar registro basura con bloque especial para filtrarlo en UI
db.execute(text("UPDATE legisladores SET bloque = 'DATO INVALIDO' WHERE nombre_completo = 'xx BORRAR Manuel Isauro'"))

# Ver cuántos votos tiene UÑAC y cómo está en la DB
r = db.execute(text("""
    SELECT id, nombre_completo, bloque, distrito FROM legisladores 
    WHERE nombre_completo ILIKE '%A%AC%' AND camara = 'Diputados' AND bloque IS NULL
"""))
for row in r:
    print(row)

db.commit()
db.close()