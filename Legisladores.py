import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles

st.set_page_config(page_title="Legisladores · Lobby", layout="wide")
apply_styles()

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size:0.75rem; color:rgba(255,255,255,0.5); padding-top:1rem;'>
Monitor Legislativo · Argentina<br>
Datos: HCDN · Actualización: 2024-2025
</div>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def cargar_legisladores(camara=None):
    db = SessionLocal()
    filtro = f"WHERE l.camara = '{camara}'" if camara else ""
    result = db.execute(text(f"""
        SELECT l.id, l.nombre_completo, l.camara,
               COALESCE(l.bloque, '—') as bloque,
               COALESCE(l.distrito, '—') as distrito,
               COUNT(v.id) as total_votos
        FROM legisladores l
        LEFT JOIN votos v ON v.legislador_id = l.id
        {filtro}
        GROUP BY l.id, l.nombre_completo, l.camara, l.bloque, l.distrito
        ORDER BY total_votos DESC
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_votos_legislador(legislador_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT v.voto_individual, v.acta_id, v.acta_detalle_id,
               a.fecha, a.titulo as titulo_acta, a.resultado as resultado_general
        FROM votos v
        LEFT JOIN actas_cabecera a ON a.acta_id = v.acta_id
        WHERE v.legislador_id = :id
        ORDER BY a.fecha DESC NULLS LAST
    """), {"id": legislador_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_proyectos_legislador(nombre):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT nro_expediente, titulo, fecha_ingreso, estado
        FROM proyectos
        WHERE autores ILIKE :nombre
        ORDER BY fecha_ingreso DESC NULLS LAST
        LIMIT 50
    """), {"nombre": f"%{nombre}%"})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.title("Monitor Legislativo")
st.sidebar.markdown("Congreso de la Nación · Argentina")

camara_sel = st.sidebar.radio("Cámara", ["Todos", "Diputados", "Senadores"])

camara_filtro = None
if camara_sel == "Diputados":
    camara_filtro = "Diputados"
elif camara_sel == "Senadores":
    camara_filtro = "Senadores"

df_leg = cargar_legisladores(camara_filtro)

if df_leg.empty:
    st.title("Lobby")
    st.warning(f"No hay datos de {camara_sel} disponibles aún.")
    st.stop()

# ---------------------------------------------------------
# FILTROS
# ---------------------------------------------------------
bloques = ["Todos"] + sorted([b for b in df_leg['bloque'].unique() if b != '—'])
bloque_sel = st.sidebar.selectbox("Filtrar por bloque", bloques)

distritos = ["Todos"] + sorted([d for d in df_leg['distrito'].unique() if d != '—'])
distrito_sel = st.sidebar.selectbox("Filtrar por distrito", distritos)

df_filtrado = df_leg.copy()
if bloque_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['bloque'] == bloque_sel]
if distrito_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['distrito'] == distrito_sel]

# ---------------------------------------------------------
# BUSCADOR
# ---------------------------------------------------------
st.title(f"Monitor Legislativo — {camara_sel}")

busqueda = st.text_input("Buscar por nombre", placeholder="Ej: Menem, Kirchner, Moreau...")
if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado['nombre_completo'].str.contains(busqueda, case=False, na=False)
    ]

st.markdown(f"**{len(df_filtrado)} legisladores encontrados**")

st.dataframe(
    df_filtrado[['nombre_completo', 'bloque', 'distrito', 'camara', 'total_votos']].rename(columns={
        'nombre_completo': 'Nombre',
        'bloque': 'Bloque',
        'distrito': 'Distrito',
        'camara': 'Cámara',
        'total_votos': 'Votos registrados'
    }),
    use_container_width=True,
    hide_index=True
)

# ---------------------------------------------------------
# PERFIL
# ---------------------------------------------------------
st.divider()
st.subheader("Perfil de legislador")

nombres = df_filtrado['nombre_completo'].tolist()
if not nombres:
    st.info("No hay legisladores que coincidan con los filtros.")
    st.stop()

seleccionado = st.selectbox("Seleccionar legislador", nombres)
row = df_filtrado[df_filtrado['nombre_completo'] == seleccionado].iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.markdown(f"**BLOQUE**\n\n{row['bloque']}")
col2.markdown(f"**DISTRITO**\n\n{row['distrito']}")
col3.markdown(f"**CÁMARA**\n\n{row['camara']}")
col4.markdown(f"**VOTOS REGISTRADOS**\n\n{int(row['total_votos'])}")

tabs = st.tabs(["Votaciones", "Proyectos presentados"])

with tabs[0]:
    df_votos = cargar_votos_legislador(int(row['id']))

    if df_votos.empty:
        st.info("No hay votos registrados.")
    else:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            dist = df_votos['voto_individual'].value_counts().reset_index()
            dist.columns = ['Tipo', 'Cantidad']
            st.markdown("#### Distribución")
            st.dataframe(dist, hide_index=True, use_container_width=True)
        with col_b:
            st.markdown("#### Evolución en el tiempo")
            df_fecha = df_votos.dropna(subset=['fecha']).copy()
            if not df_fecha.empty:
                df_fecha['fecha'] = pd.to_datetime(df_fecha['fecha'])
                df_fecha['año'] = df_fecha['fecha'].dt.year
                evolucion = df_fecha.groupby(['año', 'voto_individual']).size().unstack(fill_value=0)
                st.bar_chart(evolucion)
            else:
                st.info("Sin datos de fecha para graficar evolución.")

        st.markdown("#### Últimas votaciones")
        df_con_fecha = df_votos.dropna(subset=['fecha']).head(20)
        if not df_con_fecha.empty:
            st.dataframe(
                df_con_fecha[['fecha', 'voto_individual', 'titulo_acta', 'resultado_general']].rename(columns={
                    'fecha': 'Fecha',
                    'voto_individual': 'Voto',
                    'titulo_acta': 'Asunto',
                    'resultado_general': 'Resultado'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sin fechas disponibles.")

with tabs[1]:
    apellido = seleccionado.split()[0]
    df_proyectos = cargar_proyectos_legislador(apellido)

    if df_proyectos.empty:
        st.info("No se encontraron proyectos para este legislador.")
    else:
        st.markdown(f"#### {len(df_proyectos)} proyectos encontrados")
        st.dataframe(
            df_proyectos.rename(columns={
                'nro_expediente': 'Expediente',
                'titulo': 'Título',
                'fecha_ingreso': 'Fecha',
                'estado': 'Tipo'
            }),
            use_container_width=True,
            hide_index=True
        )