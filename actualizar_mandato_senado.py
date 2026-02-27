import requests
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from rapidfuzz import process, fuzz
import warnings
warnings.filterwarnings('ignore')

# Bajar JSON oficial
url = "https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoSenadores/json"
r = requests.get(url, timeout=30, verify=False)
rows = r.json()['table']['rows']
df_senado = pd.DataFrame(rows)
df_senado['nombre_completo'] = (df_senado['APELLIDO'] + ' ' + df_senado['NOMBRE']).str.strip().str.upper()
df_senado['mandato_hasta'] = pd.to_datetime(df_senado['C_LEGAL'], errors='coerce').dt.date
print(f"Senadores oficiales: {len(df_senado)}")

# Cargar senadores de nuestra DB
db = SessionLocal()
result = db.execute(text("SELECT id, nombre_completo FROM legisladores WHERE camara = 'Senadores'"))
db_senadores = [(row[0], row[1]) for row in result.fetchall()]
nombres_db = [s[1] for s in db_senadores]

# Matching fuzzy
actualizados = 0
no_encontrados = []

for _, row in df_senado.iterrows():
    nombre_oficial = row['nombre_completo']
    mandato = row['mandato_hasta']
    if not mandato:
        continue

    match = process.extractOne(nombre_oficial, nombres_db, scorer=fuzz.token_sort_ratio, score_cutoff=75)
    if match:
        nombre_match, score, idx = match
        leg_id = db_senadores[idx][0]
        db.execute(text("UPDATE legisladores SET mandato_hasta = :m WHERE id = :id"),
                   {'m': mandato, 'id': leg_id})
        actualizados += 1
    else:
        no_encontrados.append(nombre_oficial)

db.commit()
db.close()

print(f"\nActualizados: {actualizados}")
print(f"No encontrados ({len(no_encontrados)}):")
for n in no_encontrados:
    print(f"  - {n}")