import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles, show_logo

st.set_page_config(page_title="Votaciones — Lobby", layout="wide")
apply_styles()
show_logo()

@st.cache_data(ttl=3600)
def cargar_sesiones():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT s.id, s.fecha, s.tipo_periodo, s.tipo_reunion,
               s.duracion_horas, s.hubo_quorum, s.periodo_id,
               COUNT(v.id) as total_votos
        FROM sesiones s
        LEFT JOIN votos v ON v.sesion_id = s.id
        GROUP BY s.id, s.fecha, s.tipo_periodo, s.tipo_reunion,
                 s.duracion_horas, s.hubo_quorum, s.periodo_id
        ORDER BY s.fecha DESC NULLS LAST
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_temario_sesion(sesion_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT item_nro, descripcion
        FROM temario_items
        WHERE sesion_id = :id
        ORDER BY item_nro
    """), {"id": sesion_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

# ---------------------------------------------------------
st.title("Sesiones")
st.markdown("<div class='page-subtitle'>Cámara de Diputados · 2024-2025</div>", unsafe_allow_html=True)

df = cargar_sesiones()

if df.empty:
    st.warning("No hay sesiones cargadas.")
    st.stop()

df['fecha'] = pd.to_datetime(df['fecha'])
df['año'] = df['fecha'].dt.year
df['duracion_horas'] = pd.to_numeric(df['duracion_horas'], errors='coerce')

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total sesiones", len(df))
col2.metric("Con quórum", df[df['hubo_quorum'] == 'Sí'].shape[0])
col3.metric("Sin quórum", df[df['hubo_quorum'] == 'No'].shape[0])
col4.metric("Duración promedio", f"{df['duracion_horas'].mean():.1f}h")

st.divider()

col_f1, col_f2 = st.columns(2)
with col_f1:
    años = ["Todos"] + sorted(df['año'].dropna().unique().astype(int).tolist(), reverse=True)
    año_sel = st.selectbox("Año", años)
with col_f2:
    tipos = ["Todos"] + sorted(df['tipo_periodo'].dropna().unique().tolist())
    tipo_sel = st.selectbox("Tipo de período", tipos)

df_filtrado = df.copy()
if año_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['año'] == int(año_sel)]
if tipo_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['tipo_periodo'] == tipo_sel]

st.subheader("Duración por sesión")
if not df_filtrado.empty:
    chart_data = df_filtrado.set_index('fecha')[['duracion_horas']].sort_index()
    st.bar_chart(chart_data)

st.subheader(f"{len(df_filtrado)} sesiones")
st.dataframe(
    df_filtrado[['fecha', 'tipo_periodo', 'tipo_reunion', 'duracion_horas', 'hubo_quorum', 'periodo_id']].rename(columns={
        'fecha': 'Fecha',
        'tipo_periodo': 'Período',
        'tipo_reunion': 'Tipo',
        'duracion_horas': 'Duración (hs)',
        'hubo_quorum': 'Quórum',
        'periodo_id': 'ID'
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()
st.subheader("Temario de sesión")

opciones = df_filtrado['periodo_id'].dropna().tolist()
if opciones:
    sel = st.selectbox("Seleccionar sesión", opciones)
    row = df_filtrado[df_filtrado['periodo_id'] == sel].iloc[0]

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Fecha", str(row['fecha'].date()))
    col_b.metric("Tipo", row['tipo_periodo'])
    col_c.metric("Duración", f"{row['duracion_horas']:.1f}h" if pd.notna(row['duracion_horas']) else "—")

    df_temario = cargar_temario_sesion(int(row['id']))
    if not df_temario.empty:
        st.dataframe(
            df_temario.rename(columns={
                'item_nro': 'N°',
                'descripcion': 'Asunto'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay temario disponible para esta sesión.")