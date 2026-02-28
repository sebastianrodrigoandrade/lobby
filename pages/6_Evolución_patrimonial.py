import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles, show_logo

st.set_page_config(page_title="Evolución Patrimonial · Lobby", layout="wide")
apply_styles()
show_logo()
st.sidebar.title("Monitor Legislativo")


def fmt_pesos(val):
    if not val or val == 0:
        return "—"
    millones = val / 1_000_000
    if millones >= 1000:
        return f"${millones/1000:,.1f}B"
    return f"${millones:,.1f}M"


@st.cache_data(ttl=3600)
def cargar_legisladores_con_historia():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            h.cuit,
            h.funcionario_apellido_nombre,
            COUNT(DISTINCT h.anio) as años_disponibles,
            MIN(h.anio) as primer_anio,
            MAX(h.anio) as ultimo_anio,
            l.nombre_completo, l.bloque, l.distrito, l.camara
        FROM ddjj_historico h
        LEFT JOIN legisladores l ON l.id = h.legislador_id
        GROUP BY h.cuit, h.funcionario_apellido_nombre, l.nombre_completo, l.bloque, l.distrito, l.camara
        HAVING COUNT(DISTINCT h.anio) >= 2
        ORDER BY años_disponibles DESC, h.funcionario_apellido_nombre
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_serie(cuit):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT anio, patrimonio_neto, total_bienes, total_deudas, ingresos_neto_gastos,
               tipo_declaracion, cargo
        FROM ddjj_historico
        WHERE cuit = :cuit
        ORDER BY anio
    """), {"cuit": cuit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    for col in ['patrimonio_neto', 'total_bienes', 'total_deudas', 'ingresos_neto_gastos']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


@st.cache_data(ttl=3600)
def cargar_ranking_variacion():
    db = SessionLocal()
    result = db.execute(text("""
        WITH primer_ultimo AS (
            SELECT 
                cuit,
                funcionario_apellido_nombre,
                MIN(anio) as anio_inicio,
                MAX(anio) as anio_fin
            FROM ddjj_historico
            GROUP BY cuit, funcionario_apellido_nombre
            HAVING COUNT(DISTINCT anio) >= 3
        ),
        valores AS (
            SELECT 
                pu.cuit,
                pu.funcionario_apellido_nombre,
                pu.anio_inicio,
                pu.anio_fin,
                h_ini.patrimonio_neto as pat_inicio,
                h_fin.patrimonio_neto as pat_fin
            FROM primer_ultimo pu
            JOIN ddjj_historico h_ini ON h_ini.cuit = pu.cuit AND h_ini.anio = pu.anio_inicio
            JOIN ddjj_historico h_fin ON h_fin.cuit = pu.cuit AND h_fin.anio = pu.anio_fin
        )
        SELECT 
            v.*,
            (v.pat_fin - v.pat_inicio) as variacion_absoluta,
            CASE WHEN v.pat_inicio > 0 
                 THEN ROUND((v.pat_fin - v.pat_inicio) * 100.0 / v.pat_inicio, 1)
                 ELSE NULL END as variacion_pct,
            l.bloque, l.camara
        FROM valores v
        LEFT JOIN legisladores l ON l.id = (
            SELECT legislador_id FROM ddjj_historico 
            WHERE cuit = v.cuit AND legislador_id IS NOT NULL LIMIT 1
        )
        ORDER BY variacion_absoluta DESC
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    for col in ['pat_inicio', 'pat_fin', 'variacion_absoluta']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


# ---------------------------------------------------------
st.title("Evolución Patrimonial")
st.markdown("<div class='page-subtitle'>Serie histórica 2012–2023 · Fuente: Oficina Anticorrupción</div>",
            unsafe_allow_html=True)

df_leg = cargar_legisladores_con_historia()

tab1, tab2, tab3 = st.tabs(["📈 Serie individual", "🏆 Ranking de variación", "📊 Evolución por bloque"])

# ---------------------------------------------------------
with tab1:
    st.markdown("#### Seguí el patrimonio de un legislador año a año")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar legislador", placeholder="Ej: Cobos, Kirchner, Lousteau...")
    with col_f2:
        min_años = st.slider("Mínimo de años con datos", 2, 12, 3)

    df_filtrado = df_leg[df_leg['años_disponibles'] >= min_años]
    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado['funcionario_apellido_nombre'].str.contains(busqueda, case=False, na=False)
        ]

    if df_filtrado.empty:
        st.info("No se encontraron legisladores con esos criterios.")
        st.stop()

    nombres = df_filtrado['funcionario_apellido_nombre'].tolist()
    seleccionado = st.selectbox("Seleccionar legislador", nombres)
    row = df_filtrado[df_filtrado['funcionario_apellido_nombre'] == seleccionado].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bloque", row['bloque'] or '—')
    col2.metric("Cámara", row['camara'] or '—')
    col3.metric("Años con datos", int(row['años_disponibles']))
    col4.metric("Período", f"{int(row['primer_anio'])}–{int(row['ultimo_anio'])}")

    df_serie = cargar_serie(row['cuit'])

    if df_serie.empty:
        st.info("Sin datos de serie histórica.")
    else:
        # Gráfico principal — patrimonio neto
        st.markdown("#### Patrimonio neto")
        st.line_chart(df_serie.set_index('anio')[['patrimonio_neto']])

        # Gráfico bienes vs deudas
        st.markdown("#### Bienes vs Deudas")
        st.line_chart(df_serie.set_index('anio')[['total_bienes', 'total_deudas']])

        # Tabla detalle
        st.markdown("#### Detalle año a año")
        tabla = df_serie.copy()
        tabla['Patrimonio neto'] = tabla['patrimonio_neto'].apply(fmt_pesos)
        tabla['Bienes'] = tabla['total_bienes'].apply(fmt_pesos)
        tabla['Deudas'] = tabla['total_deudas'].apply(fmt_pesos)
        tabla['Ingresos'] = tabla['ingresos_neto_gastos'].apply(fmt_pesos)

        # Variación interanual
        tabla['Δ vs año anterior'] = tabla['patrimonio_neto'].diff().apply(
            lambda x: f"+{fmt_pesos(x)}" if x > 0 else (fmt_pesos(x) if x != 0 else '—')
        )

        st.dataframe(
            tabla[['anio', 'Patrimonio neto', 'Bienes', 'Deudas', 'Ingresos', 'Δ vs año anterior', 'tipo_declaracion']].rename(columns={
                'anio': 'Año',
                'tipo_declaracion': 'Tipo'
            }),
            use_container_width=True,
            hide_index=True
        )

# ---------------------------------------------------------
with tab2:
    st.markdown("#### ¿Quién más aumentó su patrimonio entre su primera y última declaración?")

    df_rank = cargar_ranking_variacion()

    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        orden = st.radio("Ordenar", ["Mayor aumento", "Mayor caída"], horizontal=True)
    with col_r2:
        top_n = st.slider("Mostrar top", 10, 50, 20)

    if orden == "Mayor aumento":
        df_rank_show = df_rank.nlargest(top_n, 'variacion_absoluta')
    else:
        df_rank_show = df_rank.nsmallest(top_n, 'variacion_absoluta')

    for i, (_, r) in enumerate(df_rank_show.iterrows(), 1):
        color = "#1a7a3f" if r['variacion_absoluta'] > 0 else "#b91c1c"
        signo = "+" if r['variacion_absoluta'] > 0 else ""
        st.markdown(f"""
        <div style='background:white; border-left:4px solid {color}; padding:0.7rem 1rem; 
                    margin-bottom:0.4rem; border-radius:4px;'>
            <div style='font-size:0.7rem; color:#999; font-weight:600'>#{i}</div>
            <div style='font-weight:600; color:#1a1a1a'>{r['funcionario_apellido_nombre']}</div>
            <div style='font-size:0.8rem; color:#666'>{r['bloque'] or '—'} · {r['anio_inicio']}→{r['anio_fin']}</div>
            <div style='display:flex; gap:1.5rem; margin-top:0.3rem;'>
                <span style='font-size:1.1rem; font-weight:700; color:{color}'>{signo}{fmt_pesos(r['variacion_absoluta'])}</span>
                <span style='font-size:0.85rem; color:#666'>{fmt_pesos(r['pat_inicio'])} → {fmt_pesos(r['pat_fin'])}</span>
                {f'<span style="font-size:0.85rem; color:{color}">{signo}{r["variacion_pct"]}%</span>' if pd.notna(r['variacion_pct']) else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------
with tab3:
    st.markdown("#### Evolución del patrimonio promedio por bloque")

    db = SessionLocal()
    result = db.execute(text("""
        SELECT h.anio, l.bloque, 
               ROUND(AVG(h.patrimonio_neto)) as patrimonio_promedio,
               COUNT(DISTINCT h.cuit) as legisladores
        FROM ddjj_historico h
        JOIN legisladores l ON l.id = h.legislador_id
        WHERE l.bloque IS NOT NULL
        GROUP BY h.anio, l.bloque
        ORDER BY h.anio, patrimonio_promedio DESC
    """))
    df_bloques = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()

    if df_bloques.empty:
        st.info("Sin datos.")
    else:
        # Filtrar bloques con al menos 3 años de datos
        bloques_disponibles = df_bloques.groupby('bloque')['anio'].nunique()
        bloques_validos = bloques_disponibles[bloques_disponibles >= 3].index.tolist()

        bloques_sel = st.multiselect(
            "Bloques a comparar",
            sorted(bloques_validos),
            default=sorted(bloques_validos)[:4]
        )

        if bloques_sel:
            df_pivot = df_bloques[df_bloques['bloque'].isin(bloques_sel)].pivot_table(
                index='anio', columns='bloque', values='patrimonio_promedio'
            )
            st.line_chart(df_pivot)

            st.markdown("#### Tabla de datos")
            st.dataframe(
                df_bloques[df_bloques['bloque'].isin(bloques_sel)].rename(columns={
                    'anio': 'Año', 'bloque': 'Bloque',
                    'patrimonio_promedio': 'Patrimonio promedio',
                    'legisladores': 'Legisladores'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Patrimonio promedio': st.column_config.NumberColumn(format="$ %d")
                }
            )