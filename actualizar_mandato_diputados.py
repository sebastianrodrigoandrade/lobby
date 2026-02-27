import requests
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from rapidfuzz import process, fuzz
import warnings
warnings.filterwarnings('ignore')

url = "https://www.diputados.gov.ar/diputados/"
r = requests.get(url, timeout=30, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
tabla = soup.find('table')
filas = tabla.find_all('tr')[1:]

diputados = []
for fila in filas:
    celdas = fila.find_all('td')
    if len(celdas) >= 7:
        nombre_raw = celdas[1].get_text(strip=True)
        partes = nombre_raw.split(',', 1)
        nombre_invertido = f"{partes[1].strip()} {partes[0].strip()}" if len(partes) == 2 else nombre_raw
        diputados.append({
            'nombre_completo': nombre_invertido.strip(),
            'distrito': celdas[2].get_text(strip=True).title(),
            'bloque': celdas[3].get_text(strip=True),
            'fin': celdas[6].get_text(strip=True),
        })

df = pd.DataFrame(diputados)
df['fin_date'] = pd.to_datetime(df['fin'], format='%d/%m/%Y', errors='coerce').dt.date

db = SessionLocal()
result = db.execute(text("SELECT id, nombre_completo FROM legisladores WHERE camara = 'Diputados'"))
db_diputados = [(row[0], row[1]) for row in result.fetchall()]
nombres_db = [d[1] for d in db_diputados]

actualizados = 0
insertados = 0

for _, row in df.iterrows():
    nombre = row['nombre_completo']
    fin = row['fin_date']

    match = process.extractOne(nombre.upper(), [n.upper() for n in nombres_db],
                               scorer=fuzz.token_sort_ratio, score_cutoff=82)
    if match:
        _, score, idx = match
        leg_id = db_diputados[idx][0]
        db.execute(text("""
            UPDATE legisladores 
            SET mandato_hasta = :m, bloque = :b, distrito = :d
            WHERE id = :id
        """), {'m': fin, 'b': row['bloque'], 'd': row['distrito'], 'id': leg_id})
        actualizados += 1
    else:
        # Insertar nuevo
        res = db.execute(text("""
            INSERT INTO legisladores (nombre_completo, camara, bloque, distrito, mandato_hasta)
            VALUES (:nombre, 'Diputados', :bloque, :distrito, :mandato)
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {'nombre': nombre, 'bloque': row['bloque'],
               'distrito': row['distrito'], 'mandato': fin})
        if res.fetchone():
            insertados += 1
            nombres_db.append(nombre)
            # Actualizar cache local
            result2 = db.execute(text("SELECT id FROM legisladores WHERE nombre_completo = :n"), {'n': nombre})
            new_row = result2.fetchone()
            if new_row:
                db_diputados.append((new_row[0], nombre))

db.commit()
db.close()

print(f"Actualizados: {actualizados}")
print(f"Insertados nuevos: {insertados}")
print(f"Total: {actualizados + insertados} / {len(df)}")