import os
os.environ['DB_USER'] = 'neondb_owner'
os.environ['DB_PASS'] = 'npg_kASKs8f9jdHT'
os.environ['DB_HOST'] = 'ep-patient-shadow-aiqmylpa-pooler.c-4.us-east-1.aws.neon.tech'
os.environ['DB_NAME'] = 'neondb'
os.environ['DB_PORT'] = '5432'

from src.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()

# Ver cobertura por año y cuántos legisladores tienen serie completa
r = db.execute(text("""
    SELECT anio, COUNT(DISTINCT cuit) as legisladores, COUNT(*) as registros
    FROM ddjj_historico
    GROUP BY anio ORDER BY anio
"""))
print("Año | Legisladores | Registros")
for row in r:
    print(f"  {row[0]} | {row[1]:12d} | {row[2]}")

# Ver un legislador con serie larga como ejemplo
r2 = db.execute(text("""
    SELECT funcionario_apellido_nombre, COUNT(DISTINCT anio) as años
    FROM ddjj_historico
    WHERE legislador_id IS NOT NULL
    GROUP BY funcionario_apellido_nombre
    ORDER BY años DESC
    LIMIT 5
"""))
print("\nLegisladores con más años de datos:")
for row in r2:
    print(f"  {row[0]} — {row[1]} años")

db.close()