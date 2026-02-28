import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles, show_logo

st.set_page_config(page_title="Legisladores · Lobby", layout="wide")
apply_styles()
show_logo()
st.sidebar.title("Monitor Legislativo")
st.sidebar.markdown("Congreso de la Nación · Argentina")

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


@st.cache_data(ttl=3600)
def cargar_ranking_proyectos(camara=None, top_n=20):
    db = SessionLocal()
    filtro = f"AND l.camara = '{camara}'" if camara else ""
    result = db.execute(text(f"""
        SELECT l.nombre_completo, COALESCE(l.bloque, '—') as bloque,
               COALESCE(l.distrito, '—') as distrito, l.camara,
               COUNT(DISTINCT p.id) as proyectos
        FROM legisladores l
        JOIN proyectos p ON p.autores ILIKE '%' || SPLIT_PART(l.nombre_completo, ' ', 1) || '%'
        WHERE l.nombre_completo IS NOT NULL {filtro}
        GROUP BY l.nombre_completo, l.bloque, l.distrito, l.camara
        HAVING COUNT(DISTINCT p.id) > 0
        ORDER BY proyectos DESC
        LIMIT :top_n
    """), {"top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_adeptos(camara=None, top_n=20):
    db = SessionLocal()
    filtro = f"AND l.camara = '{camara}'" if camara else ""
    result = db.execute(text(f"""
        SELECT l.nombre_completo, COALESCE(l.bloque, '—') as bloque,
               l.camara, COUNT(*) as total_votos,
               SUM(CASE WHEN v.voto_individual = 'AFIRMATIVO' THEN 1 ELSE 0 END) as afirmativos,
               ROUND(SUM(CASE WHEN v.voto_individual = 'AFIRMATIVO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct_afirmativo
        FROM legisladores l
        JOIN votos v ON v.legislador_id = l.id
        WHERE 1=1 {filtro}
        GROUP BY l.nombre_completo, l.bloque, l.camara
        HAVING COUNT(*) >= 50
        ORDER BY pct_afirmativo DESC
        LIMIT :top_n
    """), {"top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_rebeldes(camara=None, top_n=20):
    db = SessionLocal()
    filtro = f"AND l.camara = '{camara}'" if camara else ""
    result = db.execute(text(f"""
        WITH voto_bloque AS (
            SELECT v.acta_id,
                   l.bloque,
                   MODE() WITHIN GROUP (ORDER BY v.voto_individual) as voto_mayoritario
            FROM votos v
            JOIN legisladores l ON l.id = v.legislador_id
            WHERE l.bloque IS NOT NULL AND v.acta_id IS NOT NULL
            GROUP BY v.acta_id, l.bloque
        ),
        divergencias AS (
            SELECT l.id, l.nombre_completo, COALESCE(l.bloque,'—') as bloque, l.camara,
                   COUNT(*) as votaciones,
                   SUM(CASE WHEN v.voto_individual != vb.voto_mayoritario THEN 1 ELSE 0 END) as votos_distintos
            FROM votos v
            JOIN legisladores l ON l.id = v.legislador_id
            JOIN voto_bloque vb ON vb.acta_id = v.acta_id AND vb.bloque = l.bloque
            WHERE v.acta_id IS NOT NULL {filtro}
            GROUP BY l.id, l.nombre_completo, l.bloque, l.camara
            HAVING COUNT(*) >= 50
        )
        SELECT nombre_completo, bloque, camara, votaciones, votos_distintos,
               ROUND(votos_distintos * 100.0 / votaciones, 1) as pct_rebelde
        FROM divergencias
        ORDER BY pct_rebelde DESC
        LIMIT :top_n
    """), {"top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


# ---------------------------------------------------------
# SIDEBAR FILTROS
# ---------------------------------------------------------
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

bloques = ["Todos"] + sorted([b for b in df_leg['bloque'].unique() if b != '—'])
bloque_sel = st.sidebar.selectbox("Bloque", bloques)

distritos = ["Todos"] + sorted([d for d in df_leg['distrito'].unique() if d != '—'])
distrito_sel = st.sidebar.selectbox("Distrito", distritos)

df_filtrado = df_leg.copy()
if bloque_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['bloque'] == bloque_sel]
if distrito_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['distrito'] == distrito_sel]

# ---------------------------------------------------------
# TABS PRINCIPALES
# ---------------------------------------------------------
st.title("Legisladores")
st.markdown("<div class='page-subtitle'>Perfil · Votaciones · Proyectos · Rankings</div>", unsafe_allow_html=True)

tab_perfil, tab_proyectos_ranking, tab_adeptos, tab_rebeldes = st.tabs([
    "Perfil individual",
    "Quién presenta más proyectos",
    "Más adeptos",
    "Votan distinto al bloque",
])

# ── TAB 1: PERFIL ──────────────────────────────────────────
with tab_perfil:
    busqueda = st.text_input("Buscar por nombre", placeholder="Ej: Menem, Kirchner, Moreau...")
    df_busq = df_filtrado.copy()
    if busqueda:
        df_busq = df_busq[df_busq['nombre_completo'].str.contains(busqueda, case=False, na=False)]

    st.markdown(f"**{len(df_busq)} legisladores encontrados**")
    st.dataframe(
        df_busq[['nombre_completo', 'bloque', 'distrito', 'camara', 'total_votos']].rename(columns={
            'nombre_completo': 'Nombre', 'bloque': 'Bloque',
            'distrito': 'Distrito', 'camara': 'Cámara', 'total_votos': 'Votos registrados'
        }),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader("Perfil detallado")
    nombres = df_busq['nombre_completo'].tolist()
    if not nombres:
        st.info("No hay legisladores que coincidan con los filtros.")
        st.stop()

    seleccionado = st.selectbox("Seleccionar legislador", nombres)
    row = df_busq[df_busq['nombre_completo'] == seleccionado].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"**BLOQUE**\n\n{row['bloque']}")
    col2.markdown(f"**DISTRITO**\n\n{row['distrito']}")
    col3.markdown(f"**CÁMARA**\n\n{row['camara']}")
    col4.markdown(f"**VOTOS REGISTRADOS**\n\n{int(row['total_votos'])}")

    subtabs = st.tabs(["Votaciones", "Proyectos presentados"])

    with subtabs[0]:
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
                    st.info("Sin datos de fecha.")

            st.markdown("#### Últimas votaciones")
            df_con_fecha = df_votos.dropna(subset=['fecha']).head(20)
            if not df_con_fecha.empty:
                st.dataframe(
                    df_con_fecha[['fecha', 'voto_individual', 'titulo_acta', 'resultado_general']].rename(columns={
                        'fecha': 'Fecha', 'voto_individual': 'Voto',
                        'titulo_acta': 'Asunto', 'resultado_general': 'Resultado'
                    }),
                    use_container_width=True, hide_index=True
                )

    with subtabs[1]:
        apellido = seleccionado.split()[0]
        df_proy = cargar_proyectos_legislador(apellido)
        if df_proy.empty:
            st.info("No se encontraron proyectos.")
        else:
            st.markdown(f"#### {len(df_proy)} proyectos encontrados")
            st.dataframe(
                df_proy.rename(columns={
                    'nro_expediente': 'Expediente', 'titulo': 'Título',
                    'fecha_ingreso': 'Fecha', 'estado': 'Tipo'
                }),
                use_container_width=True, hide_index=True
            )

# ── TAB 2: RANKING PROYECTOS ────────────────────────────────
with tab_proyectos_ranking:
    st.subheader("Quién presenta más proyectos")
    top_n = st.slider("Mostrar top", 10, 50, 20, key="slider_proyectos")
    df_rank = cargar_ranking_proyectos(camara_filtro, top_n)
    if df_rank.empty:
        st.info("Sin datos.")
    else:
        st.bar_chart(df_rank.set_index('nombre_completo')['proyectos'])
        st.dataframe(
            df_rank.rename(columns={
                'nombre_completo': 'Legislador', 'bloque': 'Bloque',
                'distrito': 'Distrito', 'camara': 'Cámara', 'proyectos': 'Proyectos'
            }),
            use_container_width=True, hide_index=True
        )

# ── TAB 3: MÁS ADEPTOS ─────────────────────────────────────
with tab_adeptos:
    st.subheader("Mayor % de voto afirmativo")
    st.caption("Legisladores que más votan 'sí'. Mínimo 50 votaciones registradas.")
    df_ad = cargar_adeptos(camara_filtro)
    if df_ad.empty:
        st.info("Sin datos suficientes.")
    else:
        st.bar_chart(df_ad.set_index('nombre_completo')['pct_afirmativo'])
        st.dataframe(
            df_ad.rename(columns={
                'nombre_completo': 'Legislador', 'bloque': 'Bloque',
                'camara': 'Cámara', 'total_votos': 'Votaciones',
                'afirmativos': 'Afirmativos', 'pct_afirmativo': '% Afirmativo'
            }),
            use_container_width=True, hide_index=True
        )

# ── TAB 4: REBELDES ─────────────────────────────────────────
with tab_rebeldes:
    st.subheader("Votan distinto a la mayoría de su bloque")
    st.caption("Mínimo 50 votaciones registradas.")
    df_reb = cargar_rebeldes(camara_filtro)
    if df_reb.empty:
        st.info("Sin datos suficientes.")
    else:
        st.bar_chart(df_reb.set_index('nombre_completo')['pct_rebelde'])
        st.dataframe(
            df_reb.rename(columns={
                'nombre_completo': 'Legislador', 'bloque': 'Bloque',
                'camara': 'Cámara', 'votaciones': 'Votaciones',
                'votos_distintos': 'Votos distintos al bloque', 'pct_rebelde': '% Rebelde'
            }),
            use_container_width=True, hide_index=True
        )