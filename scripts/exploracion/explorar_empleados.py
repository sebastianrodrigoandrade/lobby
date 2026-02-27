import requests
import pandas as pd
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

url = "https://datos.hcdn.gob.ar/dataset/af7136d5-84eb-49b2-af2e-aaf6319e4aae/resource/6e49506e-6757-44cd-94e9-0e75f3bd8c38/download/nomina-personal.csv"
r = requests.get(url, timeout=30, verify=False)
print(f"Status: {r.status_code} | Size: {len(r.content)} bytes")

df = pd.read_csv(StringIO(r.text), sep=None, engine='python', nrows=5)
print(f"\nColumnas: {df.columns.tolist()}")
print(f"Total filas: ...")
df2 = pd.read_csv(StringIO(r.text), sep=None, engine='python')
print(f"Total filas: {len(df2)}")
print(f"\nPrimeras filas:")
print(df2.head(5).to_string())