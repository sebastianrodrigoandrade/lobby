import requests, pandas as pd

# IPC Congreso 2012-2016 (estimación alternativa usada durante intervención INDEC)
ipc_congreso = {2012: 25.6, 2013: 26.6, 2014: 38.5, 2015: 26.9, 2016: 36.3}

# IPC oficial INDEC base dic 2016 (valores del índice, no variación)
url_ipc = "https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2017-01-01&end_date=2023-12-31"
ipc_oficial = {int(r[0][:4]): r[1] for r in requests.get(url_ipc, timeout=15).json()['data']}

# Construir serie IPC variación anual completa
# Convertir índice a variación: (idx_año / idx_año_anterior - 1) * 100
ipc_variacion = {}
ipc_items = sorted(ipc_oficial.items())
for i, (anio, idx) in enumerate(ipc_items):
    if i == 0:
        # 2017: variación sobre dic 2016 (base=100)
        ipc_variacion[anio] = ((idx / 100) - 1) * 100
    else:
        prev_idx = ipc_items[i-1][1]
        ipc_variacion[anio] = ((idx / prev_idx) - 1) * 100

ipc_variacion.update(ipc_congreso)  # agregar 2012-2016

# RIPTE
url_ripte = "https://apis.datos.gob.ar/series/api/series/?ids=158.1_REPTE_0_0_5&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2012-01-01&end_date=2023-12-31"
ripte_vals = {int(r[0][:4]): r[1] for r in requests.get(url_ripte, timeout=15).json()['data']}

# Dólar oficial
url_dolar = "https://apis.datos.gob.ar/series/api/series/?ids=92.2_TIPO_CAMBIION_0_0_21_24&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2012-01-01&end_date=2023-12-31"
dolar_vals = {int(r[0][:4]): r[1] for r in requests.get(url_dolar, timeout=15).json()['data']}

# Construir DataFrame de índices
años = list(range(2012, 2024))
df_indices = pd.DataFrame({'anio': años})
df_indices['ipc_variacion'] = df_indices['anio'].map(ipc_variacion)
df_indices['ripte'] = df_indices['anio'].map(ripte_vals)
df_indices['dolar'] = df_indices['anio'].map(dolar_vals)

# Calcular variación acumulada base 2012=100 para IPC y RIPTE
df_indices['ipc_acum'] = 100.0
df_indices['ripte_acum'] = 100.0
df_indices['dolar_acum'] = 100.0

for i in range(1, len(df_indices)):
    df_indices.loc[i, 'ipc_acum'] = df_indices.loc[i-1, 'ipc_acum'] * (1 + df_indices.loc[i, 'ipc_variacion'] / 100)
    df_indices.loc[i, 'ripte_acum'] = df_indices.loc[i-1, 'ripte_acum'] * (df_indices.loc[i, 'ripte'] / df_indices.loc[i-1, 'ripte'])
    df_indices.loc[i, 'dolar_acum'] = df_indices.loc[i-1, 'dolar_acum'] * (df_indices.loc[i, 'dolar'] / df_indices.loc[i-1, 'dolar'])

print(df_indices[['anio', 'ipc_variacion', 'ipc_acum', 'ripte_acum', 'dolar_acum']].to_string(index=False))