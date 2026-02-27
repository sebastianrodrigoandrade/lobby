import pandas as pd
import warnings
warnings.filterwarnings('ignore')

URL = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/262cc543-3186-401b-b35e-dcdb2635976d/download/detalle-actas-datos-generales-2.4.csv"
df = pd.read_csv(URL, nrows=3)
print(df.columns.tolist())
print(df.head(3))