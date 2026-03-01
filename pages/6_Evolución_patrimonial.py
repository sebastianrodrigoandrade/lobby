import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
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


def fmt_usd(val):
    if not val or val == 0:
        return "—"
    miles = val / 1_000
    if miles >= 1000:
        return f"USD {miles/1000:,.1f}M"
    return f"USD {miles:,.0f}K"


@st.cache_data(ttl=86400)
def cargar_indices():
    """Carga IPC, RIPTE y dólar desde API de datos.gob.ar"""
    # IPC Congreso 2012-2016 (estimación alternativa durante intervención INDEC)
    ipc_congreso = {2012: 25.6, 2013: 26.6, 2014: 38.5, 2015: 26.9, 2016: 36.3}

    try:
        url_ipc = "https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2017-01-01&end_date=2023-12-31"
        ipc_oficial = {int(r[0][:4]): r[1] for r in requests.get(url_ipc, timeout=15).json()['data']}
        ipc_items = sorted(ipc_oficial.items())
        ipc_variacion = {}
        for i, (anio, idx) in enumerate(ipc_items):
            if i == 0:
                ipc_variacion[anio] = ((idx / 100) - 1) * 100
            else:
                ipc_variacion[anio] = ((idx / ipc_items[i-1][1]) - 1) * 100
        ipc_variacion.update(ipc_congreso)
    except Exception:
        # Fallback hardcodeado si la API falla
        ipc_variacion = {2012:25.6, 2013:26.6, 2014:38.5, 2015:26.9, 2016:36.3,
                         2017:24.8, 2018:47.6, 2019:53.8, 2020:36.1, 2021:50.9,
                         2022:94.8, 2023:211.4}

    try:
        url_ripte = "https://apis.datos.gob.ar/series/api/series/?ids=158.1_REPTE_0_0_5&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2012-01-01&end_date=2023-12-31"
        ripte_vals = {int(r[0][:4]): r[1] for r in requests.get(url_ripte, timeout=15).json()['data']}
    except Exception:
        ripte_vals = {2012:6985, 2013:8743, 2014:11953, 2015:15800, 2016:20690,
                      2017:26301, 2018:34339, 2019:49574, 2020:66869, 2021:102589,
                      2022:194175, 2023:484298}

    try:
        url_dolar = "https://apis.datos.gob.ar/series/api/series/?ids=92.2_TIPO_CAMBIION_0_0_21_24&collapse=year&collapse_aggregation=end_of_period&format=json&start_date=2012-01-01&end_date=2023-12-31"
        dolar_vals = {int(r[0][:4]): r[1] for r in requests.get(url_dolar, timeout=15).json()['data']}
    except Exception:
        dolar_vals = {2012:4.92, 2013:6.52, 2014:8.55, 2015:13.0, 2016:15.85,
                      2017:18.77, 2018:37.81, 2019:59.9, 2020:84.15, 2021:102.75,
                      2022:177.13, 2023:808.48}

    años = list(range(2012, 2024))
    df = pd.DataFrame({'anio': años})
    df['ipc_var'] = df['anio'].map(ipc_variacion)
    df['ripte'] = df['anio'].map(ripte_vals)
    df['dolar'] = df['anio'].map(dolar_vals)

    # Acumulados base 2012 = 100
    df['ipc_acum'] = 100.0
    df['ripte_acum'] = 100.0
    df['dolar_acum'] = 100.0
    for i in range(1, len(df)):
        df.loc[i, 'ipc_acum'] = df.loc[i-1, 'ipc_acum'] * (1 + df.loc[i, 'ipc_var'] / 100)
        if pd.notna(df.loc[i, 'ripte']) and pd.notna(df.loc[i-1, 'ripte']) and df.loc[i-1, 'ripte'] > 0:
            df.loc[i, 'ripte_acum'] = df.loc[i-1, 'ripte_acum'] * (df.loc[i, 'ripte'] / df.loc[i-1, 'ripte'])
        if pd.notna(df.loc[i, 'dolar']) and pd.notna(df.loc[i-1, 'dolar']) and df.loc[i-1, 'dolar'] > 0:
            df.loc[i, 'dolar_acum'] = df.loc[i-1, 'dolar_acum'] * (df.loc[i, 'dolar'] / df.loc[i-1, 'dolar'])

    return df.set_index('anio')


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
            SELECT cuit, funcionario_apellido_nombre,
                   MIN(anio) as anio_inicio, MAX(anio) as anio_fin
            FROM ddjj_historico
            GROUP BY cuit, funcionario_apellido_nombre
            HAVING COUNT(DISTINCT anio) >= 3
        ),
        valores AS (
            SELECT pu.cuit, pu.funcionario_apellido_nombre,
                   pu.anio_inicio, pu.anio_fin,
                   h_ini.patrimonio_neto as pat_inicio,
                   h_fin.patrimonio_neto as pat_fin
            FROM primer_ultimo pu
            JOIN ddjj_historico h_ini ON h_ini.cuit = pu.cuit AND h_ini.anio = pu.anio_inicio
            JOIN ddjj_historico h_fin ON h_fin.cuit = pu.cuit AND h_fin.anio = pu.anio_fin
        )
        SELECT v.*,
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
st.markdown("<div class='page-subtitle'>Serie histórica 2012–2023 · Fuente: Oficina Anticorrupción · Índices: INDEC / datos.gob.ar</div>",
            unsafe_allow_html=True)

df_indices = cargar_indices()
df_leg = cargar_legisladores_con_historia()

tab1, tab2, tab3 = st.tabs(["📈 Serie individual", "🏆 Ranking de variación", "📊 Por bloque"])

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
        # Cruzar con índices solo para los años disponibles
        años_serie = df_serie['anio'].tolist()
        año_base = años_serie[0]
        idx_base = df_indices.loc[año_base] if año_base in df_indices.index else None

        # ---- GRÁFICO 1: Ingresos vs IPC y RIPTE ----
        st.markdown("#### Ingresos vs Inflación y Salarios formales")
        st.caption("Eje izquierdo: ingresos en $ nominales · Eje derecho: variación acumulada desde el primer año con datos (base = 100)")

        fig1 = go.Figure()

        # Ingresos nominales (eje izquierdo)
        ingresos = df_serie[df_serie['ingresos_neto_gastos'] != 0]
        if not ingresos.empty:
            fig1.add_trace(go.Scatter(
                x=ingresos['anio'], y=ingresos['ingresos_neto_gastos'],
                name="Ingresos ($ nominales)",
                line=dict(color="#0F2240", width=3),
                yaxis="y1"
            ))

        # IPC y RIPTE acumulados desde año base (eje derecho)
        idx_disponibles = [a for a in años_serie if a in df_indices.index]
        if idx_disponibles and idx_base is not None:
            ipc_base = df_indices.loc[año_base, 'ipc_acum']
            ripte_base = df_indices.loc[año_base, 'ripte_acum']

            ipc_rel = [(df_indices.loc[a, 'ipc_acum'] / ipc_base) * 100 for a in idx_disponibles]
            ripte_rel = [(df_indices.loc[a, 'ripte_acum'] / ripte_base) * 100 for a in idx_disponibles]

            fig1.add_trace(go.Scatter(
                x=idx_disponibles, y=ipc_rel,
                name="IPC acumulado",
                line=dict(color="#e63946", width=2, dash="dash"),
                yaxis="y2"
            ))
            fig1.add_trace(go.Scatter(
                x=idx_disponibles, y=ripte_rel,
                name="RIPTE acumulado",
                line=dict(color="#2a9d8f", width=2, dash="dot"),
                yaxis="y2"
            ))

        fig1.update_layout(
            yaxis=dict(title="Ingresos ($)", tickformat="$,.0f"),
            yaxis2=dict(title="Índice acumulado (base=100)", overlaying="y", side="right",
                       tickformat=".0f"),
            xaxis=dict(tickmode="array", tickvals=años_serie),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400, margin=dict(t=40, b=40)
        )
        st.plotly_chart(fig1, use_container_width=True)

        # ---- GRÁFICO 2: Patrimonio en USD ----
        st.markdown("#### Patrimonio en dólares oficiales")
        st.caption("Eje izquierdo: patrimonio convertido a USD al tipo de cambio oficial de fin de año · Eje derecho: devaluación acumulada (base=100)")

        fig2 = go.Figure()

        # Patrimonio en USD
        pat_usd = []
        for _, r in df_serie.iterrows():
            anio = int(r['anio'])
            if anio in df_indices.index and df_indices.loc[anio, 'dolar'] > 0:
                usd = r['patrimonio_neto'] / df_indices.loc[anio, 'dolar']
            else:
                usd = None
            pat_usd.append(usd)

        df_serie['pat_usd'] = pat_usd
        df_usd = df_serie.dropna(subset=['pat_usd'])

        fig2.add_trace(go.Scatter(
            x=df_usd['anio'], y=df_usd['pat_usd'],
            name="Patrimonio (USD oficiales)",
            line=dict(color="#0F2240", width=3),
            yaxis="y1"
        ))

        # Devaluación acumulada (eje derecho)
        if idx_disponibles and idx_base is not None:
            dolar_base = df_indices.loc[año_base, 'dolar_acum']
            dolar_rel = [(df_indices.loc[a, 'dolar_acum'] / dolar_base) * 100 for a in idx_disponibles]

            fig2.add_trace(go.Scatter(
                x=idx_disponibles, y=dolar_rel,
                name="Devaluación acumulada",
                line=dict(color="#f4a261", width=2, dash="dash"),
                yaxis="y2"
            ))

        fig2.update_layout(
            yaxis=dict(title="Patrimonio (USD)", tickformat="$,.0f"),
            yaxis2=dict(title="Devaluación acumulada (base=100)", overlaying="y", side="right",
                       tickformat=".0f"),
            xaxis=dict(tickmode="array", tickvals=años_serie),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400, margin=dict(t=40, b=40)
        )
        st.plotly_chart(fig2, use_container_width=True)

        # ---- TABLA DETALLE ----
        st.markdown("#### Detalle año a año")
        tabla = df_serie.copy()
        tabla['Patrimonio neto'] = tabla['patrimonio_neto'].apply(fmt_pesos)
        tabla['En USD'] = tabla['pat_usd'].apply(lambda x: fmt_usd(x) if x else '—')
        tabla['Bienes'] = tabla['total_bienes'].apply(fmt_pesos)
        tabla['Deudas'] = tabla['total_deudas'].apply(fmt_pesos)
        tabla['Ingresos'] = tabla['ingresos_neto_gastos'].apply(fmt_pesos)
        tabla['Δ patrimonio'] = tabla['patrimonio_neto'].diff().apply(
            lambda x: (f"+{fmt_pesos(x)}" if x > 0 else fmt_pesos(x)) if x != 0 and pd.notna(x) else '—'
        )
        # IPC del año
        tabla['IPC año'] = tabla['anio'].apply(
            lambda a: f"{df_indices.loc[a, 'ipc_var']:.1f}%" if a in df_indices.index else '—'
        )

        st.dataframe(
            tabla[['anio', 'Patrimonio neto', 'En USD', 'Δ patrimonio', 'Ingresos', 'IPC año', 'tipo_declaracion']].rename(columns={
                'anio': 'Año', 'tipo_declaracion': 'Tipo'
            }),
            use_container_width=True, hide_index=True
        )

        st.caption("⚠️ IPC 2012–2016: estimación IPC Congreso (el INDEC no publicó datos confiables durante ese período). Desde 2017: IPC oficial INDEC.")

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

        # IPC acumulado en ese período
        a_ini, a_fin = int(r['anio_inicio']), int(r['anio_fin'])
        if a_ini in df_indices.index and a_fin in df_indices.index:
            ipc_periodo = ((df_indices.loc[a_fin, 'ipc_acum'] / df_indices.loc[a_ini, 'ipc_acum']) - 1) * 100
            ipc_txt = f"· IPC período: +{ipc_periodo:.0f}%"
        else:
            ipc_txt = ""

        st.markdown(f"""
        <div style='background:white; border-left:4px solid {color}; padding:0.7rem 1rem;
                    margin-bottom:0.4rem; border-radius:4px;'>
            <div style='font-size:0.7rem; color:#999; font-weight:600'>#{i}</div>
            <div style='font-weight:600; color:#1a1a1a'>{r['funcionario_apellido_nombre']}</div>
            <div style='font-size:0.8rem; color:#666'>{r['bloque'] or '—'} · {a_ini}→{a_fin} {ipc_txt}</div>
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

    if not df_bloques.empty:
        bloques_validos = df_bloques.groupby('bloque')['anio'].nunique()
        bloques_validos = bloques_validos[bloques_validos >= 3].index.tolist()

        bloques_sel = st.multiselect("Bloques a comparar", sorted(bloques_validos),
                                     default=sorted(bloques_validos)[:4])

        if bloques_sel:
            df_pivot = df_bloques[df_bloques['bloque'].isin(bloques_sel)].pivot_table(
                index='anio', columns='bloque', values='patrimonio_promedio'
            )
            st.line_chart(df_pivot)

            st.dataframe(
                df_bloques[df_bloques['bloque'].isin(bloques_sel)].rename(columns={
                    'anio': 'Año', 'bloque': 'Bloque',
                    'patrimonio_promedio': 'Patrimonio promedio',
                    'legisladores': 'Legisladores'
                }),
                use_container_width=True, hide_index=True,
                column_config={'Patrimonio promedio': st.column_config.NumberColumn(format="$ %d")}
            )