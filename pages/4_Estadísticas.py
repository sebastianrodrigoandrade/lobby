import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles
apply_styles()

st.set_page_config(page_title="Estadísticas — Lobby", layout="wide")

@st.cache_data(ttl=3600)
def cargar_leyes_por_año():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            EXTRACT(YEAR FROM fecha_ingreso)::int as año,
            estado,
            COUNT(*) as total
        FROM proyectos
        WHERE fecha_ingreso IS NOT NULL
          AND estado IN ('LEY', 'RESOLUCION', 'DECLARACION', 'MENSAJE')
        GROUP BY año, estado
        ORDER BY año DESC, total DESC
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_dnus():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            EXTRACT(YEAR FROM fecha_ingreso)::int as año,
            COUNT(*) as total,
            STRING_AGG(nro_expediente || ': ' || LEFT(titulo, 80), ' | ' ORDER BY fecha_ingreso DESC) as detalle
        FROM proyectos
        WHERE nro_expediente ILIKE '%-JGM-%'
          AND titulo ILIKE '%DECRETO DE NECESIDAD Y URGENCIA%'
        GROUP BY año
        ORDER BY año DESC
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_dnus_detalle():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            nro_expediente,
            titulo,
            fecha_ingreso,
            estado
        FROM proyectos
        WHERE nro_expediente ILIKE '%-JGM-%'
          AND titulo ILIKE '%DECRETO DE NECESIDAD Y URGENCIA%'
        ORDER BY fecha_ingreso DESC
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_proyectos_por_bloque():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            COALESCE(l.bloque, 'Sin bloque') as bloque,
            COUNT(DISTINCT p.id) as proyectos
        FROM proyectos p
        JOIN legisladores l ON p.autores ILIKE '%' || SPLIT_PART(l.nombre_completo, ',', 1) || '%'
        WHERE p.fecha_ingreso >= '2023-01-01'
          AND l.camara = 'Diputados'
        GROUP BY l.bloque
        ORDER BY proyectos DESC
        LIMIT 15
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

# ---------------------------------------------------------
st.title("Estadísticas")
st.markdown("<div class='page-subtitle'>Actividad legislativa · Congreso de la Nación</div>", unsafe_allow_html=True)

tabs = st.tabs(["Leyes y proyectos", "DNUs"])

# ---------------------------------------------------------
with tabs[0]:
    df_leyes = cargar_leyes_por_año()

    if df_leyes.empty:
        st.info("Sin datos.")
    else:
        # Métricas generales
        total_leyes = int(df_leyes[df_leyes['estado'] == 'LEY']['total'].sum())
        total_res = int(df_leyes[df_leyes['estado'] == 'RESOLUCION']['total'].sum())
        total_decl = int(df_leyes[df_leyes['estado'] == 'DECLARACION']['total'].sum())

        col1, col2, col3 = st.columns(3)
        col1.metric("Total leyes (histórico)", f"{total_leyes:,}")
        col2.metric("Resoluciones", f"{total_res:,}")
        col3.metric("Declaraciones", f"{total_decl:,}")

        st.divider()

        # Gráfico leyes por año
        st.subheader("Leyes sancionadas por año")
        df_pivot = df_leyes.pivot_table(
            index='año', columns='estado', values='total', fill_value=0
        ).reset_index()
        df_pivot = df_pivot[df_pivot['año'] >= 2008].sort_values('año')

        if 'LEY' in df_pivot.columns:
            st.bar_chart(df_pivot.set_index('año')[['LEY']])

        st.divider()

        # Tabla completa
        st.subheader("Actividad por año")
        df_tabla = df_leyes[df_leyes['año'] >= 2008].pivot_table(
            index='año', columns='estado', values='total', fill_value=0
        ).reset_index().sort_values('año', ascending=False)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
with tabs[1]:
    df_dnus = cargar_dnus()
    df_dnus_det = cargar_dnus_detalle()

    total_dnus = int(df_dnus['total'].sum()) if not df_dnus.empty else 0
    año_max = int(df_dnus['año'].max()) if not df_dnus.empty else '—'
    dnus_max = int(df_dnus.loc[df_dnus['total'].idxmax(), 'total']) if not df_dnus.empty else 0
    año_mas_dnus = int(df_dnus.loc[df_dnus['total'].idxmax(), 'año']) if not df_dnus.empty else '—'

    col1, col2, col3 = st.columns(3)
    col1.metric("Total DNUs registrados", total_dnus)
    col2.metric("Último año con datos", año_max)
    col3.metric("Año con más DNUs", f"{año_mas_dnus} ({dnus_max})")

    st.caption("Datos disponibles: 2008–2023. Los DNUs del período 2024-2025 no están publicados en el portal de datos abiertos de HCDN.")

    st.divider()

    st.subheader("DNUs por año")
    if not df_dnus.empty:
        st.bar_chart(df_dnus.set_index('año')[['total']].sort_index())

    st.divider()

    st.subheader("Listado de DNUs")
    busqueda_dnu = st.text_input("Buscar DNU", placeholder="Ej: jubilaciones, emergencia, exportaciones...")
    df_mostrar = df_dnus_det.copy()
    if busqueda_dnu:
        df_mostrar = df_mostrar[df_mostrar['titulo'].str.contains(busqueda_dnu, case=False, na=False)]

    st.dataframe(
        df_mostrar[['fecha_ingreso', 'nro_expediente', 'titulo']].rename(columns={
            'fecha_ingreso': 'Fecha',
            'nro_expediente': 'Expediente',
            'titulo': 'Descripción',
        }),
        use_container_width=True,
        hide_index=True
    )