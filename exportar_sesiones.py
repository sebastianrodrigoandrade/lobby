import requests
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

URL_SESIONES = "https://datos.hcdn.gob.ar:443/dataset/f744ea10-83b4-4493-8bef-6fc9fb9e41e9/resource/4ac70a51-a82d-428b-966a-0a203dd0a7e3/download/sesiones2.7.csv"
URL_PERIODOS = "https://datos.hcdn.gob.ar:443/dataset/b2081b7c-0fd5-4ea5-804d-daec6c97176e/resource/a3ccd8d8-800b-49bf-bcc5-564e3c51489d/download/periodosparlamentarios1.6.csv"
URL_CABECERA_GENERAL = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/28bdc184-d8e3-4d50-b5b5-e2151f902ac7/download/actas-datos-generales-2.4.csv"
URL_CABECERA_137 = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/59c05ba8-ad0a-4d55-803d-20e3fe464d0b/download/actas-cabecera-137-2.0.csv"

# =============================================================
# PASO 1: SESIONES
# =============================================================
df_sesiones = pd.read_csv(URL_SESIONES, encoding='utf-8')
df_periodos = pd.read_csv(URL_PERIODOS, encoding='utf-8')

# Fechas y columnas extra
df_sesiones['reunion_inicio'] = pd.to_datetime(df_sesiones['reunion_inicio'])
df_sesiones['reunion_fin'] = pd.to_datetime(df_sesiones['reunion_fin'])
df_sesiones['año'] = df_sesiones['reunion_inicio'].dt.year
df_sesiones['mes'] = df_sesiones['reunion_inicio'].dt.month
df_sesiones['mes_nombre'] = df_sesiones['reunion_inicio'].dt.strftime('%B')
df_sesiones['dia_semana'] = df_sesiones['reunion_inicio'].dt.strftime('%A')

duracion_total = df_sesiones['reunion_fin'] - df_sesiones['reunion_inicio']
df_sesiones['duracion_horas'] = duracion_total.dt.total_seconds() / 3600
df_sesiones['duracion_legible'] = duracion_total.apply(
    lambda x: f"{int(x.total_seconds()//3600)}h {int((x.total_seconds()%3600)//60)}min"
)
df_sesiones['hubo_quorum'] = df_sesiones['reunion_tipo'].apply(
    lambda x: 'No' if 'Minoría' in str(x) else 'Sí'
)

# Clasificar período por fecha
df_sesiones['nro_periodo'] = df_sesiones['periodo_id'].str.extract(r'HCDN(\d+)R')
df_periodos['nro_periodo'] = df_periodos['ID'].str.extract(r'HCDN(\d+)([OED])')[0]
df_periodos['tipo_periodo'] = df_periodos['ID'].str.extract(r'HCDN(\d+)([OED])')[1].map({
    'O': 'Ordinaria',
    'E': 'Extraordinaria',
    'D': 'Prórroga'
})
df_periodos['Inicio'] = pd.to_datetime(df_periodos['Inicio'])
df_periodos['Fin'] = pd.to_datetime(df_periodos['Fin'])

def clasificar_periodo(row):
    nro = row['nro_periodo']
    fecha = row['reunion_inicio']
    candidatos = df_periodos[df_periodos['nro_periodo'] == nro]
    for _, p in candidatos.iterrows():
        if p['Inicio'] <= fecha <= p['Fin']:
            return p['tipo_periodo']
    return 'Sin clasificar'

df_sesiones['tipo_periodo'] = df_sesiones.apply(clasificar_periodo, axis=1)

# Filtrar Diputados 2024-2025
df_export = df_sesiones[
    (df_sesiones['sesion_camara'] == 'DIPUTADOS') &
    (df_sesiones['año'].isin([2024, 2025]))
].copy()

print("=== RESUMEN SESIONES ===")
print(df_export.groupby(['año', 'tipo_periodo', 'hubo_quorum']).size().reset_index(name='cantidad').to_string(index=False))
print(f"\nTotal sesiones: {len(df_export)}")
print(f"Duración promedio: {df_export['duracion_horas'].mean():.1f} horas")

df_export.to_csv('sesiones_export.csv', index=False, encoding='utf-8-sig')
print("✅ Exportado: sesiones_export.csv")

# =============================================================
# PASO 2: VOTACIONES EN SESIONES EXTRAORDINARIAS
# =============================================================
# IDs de sesiones extraordinarias identificadas
ids_extraordinarias = df_export[df_export['tipo_periodo'] == 'Extraordinaria']['periodo_id'].unique().tolist()
print(f"\n=== SESIONES EXTRAORDINARIAS A BUSCAR ===")
print(ids_extraordinarias)

# Combinar ambos CSV de cabecera para tener cobertura completa
df_cab1 = pd.read_csv(URL_CABECERA_GENERAL, encoding='utf-8')
df_cab2 = pd.read_csv(URL_CABECERA_137, encoding='utf-8')
df_cabecera = pd.concat([df_cab1, df_cab2], ignore_index=True)

print(f"\nTotal registros cabecera combinada: {len(df_cabecera)}")

# Cruzar por sesion_id
df_extraordinarias = df_cabecera[df_cabecera['sesion_id'].isin(ids_extraordinarias)].copy()

print(f"\n=== VOTACIONES EN SESIONES EXTRAORDINARIAS 2024-2025 ===")
print(f"Total votaciones: {len(df_extraordinarias)}")

if len(df_extraordinarias) > 0:
    print()
    print(df_extraordinarias[['sesion_id', 'fecha', 'titulo', 'resultado',
                               'votos_afirmativos', 'votos_negativos', 'ausentes']]
          .to_string(index=False))
    df_extraordinarias.to_csv('extraordinarias_export.csv', index=False, encoding='utf-8-sig')
    print("\n✅ Exportado: extraordinarias_export.csv")
else:
    print("No se encontraron votaciones — los IDs no coinciden con la cabecera disponible.")
    print("\nVerificando qué sesion_id existen en cabecera con nroperiodo 141-142:")
    print(df_cabecera[df_cabecera['nroperiodo'].isin([141, 142])]['sesion_id'].unique())
    
    BASE_URL = "https://datos.hcdn.gob.ar/api/3/action"

print("\n=== BUSCANDO CABECERA PERÍODOS 141-142 ===")
for dataset in ["votacionesnominales", "votaciones_nominales"]:
    r = requests.get(f"{BASE_URL}/package_show", params={"id": dataset}, verify=False, timeout=30)
    data = r.json()
    if data.get("success"):
        for resource in data["result"].get("resources", []):
            nombre = resource['name'].lower()
            if 'cabecera' in nombre or 'general' in nombre or 'acta' in nombre:
                print(f"Dataset: {dataset}")
                print(f"  Nombre: {resource['name']}")
                print(f"  URL:    {resource.get('url', '')}")
                print()