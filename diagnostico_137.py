import pandas as pd
import warnings
warnings.filterwarnings('ignore')

URL_137 = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/f86728ed-d4b9-479e-b939-a9841fd6d8d3/download/actas-detalle-137-2.0.csv"
df = pd.read_csv(URL_137, nrows=3)
print(df.columns.tolist())
print(df.head(3))