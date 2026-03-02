"""
Lobby - Página de Patrimonio
DDJJ, Evolución patrimonial, Rankings
"""
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import fmt_pesos, fmt_usd

URL_BUSCADOR = "https://www2.jus.gov.ar/consultaddjj/Home/Busqueda"


@st.cache_data(ttl=3600)
def cargar_ddjj(solo_vigentes=True):
    db = SessionLocal()
    filtro_mandato = "AND l.mandato_hasta >= CURRENT_DATE" if solo_vigentes else ""
    result = db.execute(text(f"""
        SELECT
            d.id, d.anio, d.cuit, d.funcionario_apellido_nombre,
            d.organismo, d.cargo,
            d.total_bienes, d.total_deudas, d.patrimonio_neto,
            d.ingresos_neto_gastos, d.proveedor_contratista,
            d.tipo_declaracion, d.legislador_id,
            l.nombre_completo, l.bloque, l.distrito, l.camara,
            l.mandato_hasta
        FROM ddjj_legisladores d
        LEFT JOIN legisladores l ON l.id = d.legislador_id
        WHERE l.nombre_completo != 'xx BORRAR Manuel Isauro'
          AND COALESCE(l.bloque, '') != 'DATO INVALIDO'
          {filtro_mandato}
        ORDER BY d.patrimonio_neto DESC NULLS LAST
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    for col in ['total_bienes', 'total_deudas', 'patrimonio_neto', 'ingresos_neto_gastos']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


@st.cache_data(ttl=86400)
def cargar_indices():
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
        ipc_variacion = {2012:25.6, 2013:26.6, 2014:38.5, 2015:26.9, 2016:36.3,
                         2017:24.8, 2018:47.6, 2019:53.8, 2020:36.1, 2021:50.9,
                         2022:94.8, 2023:211.4}

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
    df['dolar'] = df['anio'].map(dolar_vals)

    df['ipc_acum'] = 100.0
    df['dolar_acum'] = 100.0
    for i in range(1, len(df)):
        df.loc[i, 'ipc_acum'] = df.loc[i-1, 'ipc_acum'] * (1 + df.loc[i, 'ipc_var'] / 100)
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


def render():
    """Renderiza la página de patrimonio"""
    
    st.title("Patrimonio de Legisladores")
    st.markdown("<div class='page-subtitle'>Declaraciones juradas y evolución patrimonial · Fuente: Oficina Anticorrupción</div>", unsafe_allow_html=True)

    tabs = st.tabs(["💰 Declaraciones Juradas", "📈 Evolución", "🏆 Rankings"])

    # ========== TAB DDJJ ==========
    with tabs[0]:
        solo_vigentes = st.toggle("Solo mandatos vigentes", value=True, key="ddjj_vig")
        
        df = cargar_ddjj(solo_vigentes)

        if df.empty:
            st.warning("Sin datos.")
            return

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Legisladores con DDJJ", len(df))
        col2.metric("Patrimonio promedio", fmt_pesos(float(df['patrimonio_neto'].mean())))
        col3.metric("Mayor patrimonio", fmt_pesos(float(df['patrimonio_neto'].max())))
        col4.metric("Proveedores del Estado", int((df['proveedor_contratista'] == 'SI').sum()))

        st.markdown("---")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            busqueda = st.text_input("🔍 Buscar legislador", placeholder="Ej: Kirchner...", key="ddjj_busq")
        with col_f2:
            camara_opts = ["Todas"] + sorted(df['camara'].dropna().unique().tolist())
            camara_sel = st.selectbox("Cámara", camara_opts, key="ddjj_cam")
        with col_f3:
            orden = st.selectbox("Ordenar", ["Mayor patrimonio", "Menor patrimonio", "Apellido"], key="ddjj_ord")

        df_filtrado = df.copy()
        if busqueda:
            df_filtrado = df_filtrado[
                df_filtrado['funcionario_apellido_nombre'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['nombre_completo'].str.contains(busqueda, case=False, na=False)
            ]
        if camara_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado['camara'] == camara_sel]

        if orden == "Mayor patrimonio":
            df_filtrado = df_filtrado.sort_values('patrimonio_neto', ascending=False)
        elif orden == "Menor patrimonio":
            df_filtrado = df_filtrado.sort_values('patrimonio_neto', ascending=True)
        else:
            df_filtrado = df_filtrado.sort_values('funcionario_apellido_nombre')

        st.markdown(f"### {len(df_filtrado)} declaraciones")

        tabla = df_filtrado[[
            'funcionario_apellido_nombre', 'bloque', 'camara',
            'patrimonio_neto', 'total_bienes', 'total_deudas',
            'proveedor_contratista', 'cuit'
        ]].copy().rename(columns={
            'funcionario_apellido_nombre': 'Legislador',
            'bloque': 'Bloque', 'camara': 'Cámara',
            'patrimonio_neto': 'Patrimonio', 'total_bienes': 'Bienes',
            'total_deudas': 'Deudas', 'proveedor_contratista': 'Proveedor',
            'cuit': 'CUIT',
        })

        st.dataframe(
            tabla,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Patrimonio': st.column_config.NumberColumn(format="$ %d"),
                'Bienes': st.column_config.NumberColumn(format="$ %d"),
                'Deudas': st.column_config.NumberColumn(format="$ %d"),
            }
        )

        with st.expander("📋 ¿Cómo consultar la declaración original?"):
            st.markdown(f"""
            **Buscador de la Oficina Anticorrupción:**  
            👉 [{URL_BUSCADOR}]({URL_BUSCADOR})
            
            El **CUIT** está disponible en la tabla de arriba.
            """)

        st.markdown("---")

        st.markdown("### Patrimonio promedio por bloque")
        df_bloque = df[df['bloque'].notna()].groupby('bloque').agg(
            legisladores=('id', 'count'),
            patrimonio_promedio=('patrimonio_neto', 'mean')
        ).reset_index().sort_values('patrimonio_promedio', ascending=False)

        st.dataframe(
            df_bloque.rename(columns={
                'bloque': 'Bloque', 'legisladores': 'Legisladores',
                'patrimonio_promedio': 'Patrimonio promedio',
            }),
            use_container_width=True, hide_index=True,
            column_config={'Patrimonio promedio': st.column_config.NumberColumn(format="$ %d")}
        )

    # ========== TAB EVOLUCIÓN ==========
    with tabs[1]:
        st.markdown("### Serie histórica 2012–2023")
        
        df_indices = cargar_indices()
        df_leg = cargar_legisladores_con_historia()
        
        if df_leg.empty:
            st.warning("No hay datos históricos disponibles.")
        else:
            busqueda_evol = st.text_input("🔍 Buscar legislador", placeholder="Ej: Kirchner...", key="evol_busq")
            
            nombres_evol = df_leg['funcionario_apellido_nombre'].tolist()
            if busqueda_evol:
                nombres_evol = [n for n in nombres_evol if busqueda_evol.lower() in n.lower()]
            
            if not nombres_evol:
                st.info("No se encontró el legislador.")
            else:
                seleccionado = st.selectbox("Seleccionar", nombres_evol, key="evol_sel")
                row = df_leg[df_leg['funcionario_apellido_nombre'] == seleccionado].iloc[0]
                
                col_e1, col_e2, col_e3 = st.columns(3)
                col_e1.markdown(f"**Bloque:** {row['bloque'] or '—'}")
                col_e2.markdown(f"**DDJJ:** {int(row['años_disponibles'])} ({int(row['primer_anio'])}–{int(row['ultimo_anio'])})")
                col_e3.markdown(f"**Cámara:** {row['camara'] or '—'}")
                
                df_serie = cargar_serie(row['cuit'])
                
                if df_serie.empty:
                    st.warning("No hay datos.")
                else:
                    años_serie = df_serie['anio'].tolist()
                    
                    st.markdown("---")
                    st.markdown("#### Patrimonio en USD")
                    
                    fig = go.Figure()
                    
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
                    
                    fig.add_trace(go.Scatter(
                        x=df_usd['anio'], y=df_usd['pat_usd'],
                        name="Patrimonio (USD)",
                        line=dict(color="#0F2240", width=3),
                        fill='tozeroy',
                        fillcolor='rgba(15,34,64,0.1)'
                    ))
                    
                    fig.update_layout(
                        yaxis=dict(title="USD", tickformat="$,.0f"),
                        xaxis=dict(tickmode="array", tickvals=años_serie),
                        height=350, margin=dict(t=20, b=40)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("#### Detalle año a año")
                    tabla = df_serie.copy()
                    tabla['Patrimonio'] = tabla['patrimonio_neto'].apply(fmt_pesos)
                    tabla['En USD'] = tabla['pat_usd'].apply(lambda x: fmt_usd(x) if x else '—')
                    tabla['IPC año'] = tabla['anio'].apply(
                        lambda a: f"{df_indices.loc[a, 'ipc_var']:.1f}%" if a in df_indices.index else '—'
                    )

                    st.dataframe(
                        tabla[['anio', 'Patrimonio', 'En USD', 'IPC año', 'tipo_declaracion']].rename(columns={
                            'anio': 'Año', 'tipo_declaracion': 'Tipo'
                        }),
                        use_container_width=True, hide_index=True
                    )

    # ========== TAB RANKINGS ==========
    with tabs[2]:
        st.markdown("### ¿Quién más aumentó su patrimonio?")
        
        df_rank = cargar_ranking_variacion()
        
        if df_rank.empty:
            st.warning("No hay datos suficientes.")
        else:
            df_indices = cargar_indices()
            
            col_r1, col_r2 = st.columns([1, 1])
            with col_r1:
                orden = st.radio("Ordenar", ["Mayor aumento", "Mayor caída"], horizontal=True, key="rank_ord")
            with col_r2:
                top_n = st.slider("Mostrar top", 10, 50, 20, key="rank_n")

            if orden == "Mayor aumento":
                df_rank_show = df_rank.nlargest(top_n, 'variacion_absoluta')
            else:
                df_rank_show = df_rank.nsmallest(top_n, 'variacion_absoluta')

            for i, (_, r) in enumerate(df_rank_show.iterrows(), 1):
                color = "#059669" if r['variacion_absoluta'] > 0 else "#DC2626"
                signo = "+" if r['variacion_absoluta'] > 0 else ""
                
                a_ini, a_fin = int(r['anio_inicio']), int(r['anio_fin'])
                if a_ini in df_indices.index and a_fin in df_indices.index:
                    ipc_periodo = ((df_indices.loc[a_fin, 'ipc_acum'] / df_indices.loc[a_ini, 'ipc_acum']) - 1) * 100
                    ipc_txt = f"· IPC: +{ipc_periodo:.0f}%"
                else:
                    ipc_txt = ""

                st.markdown(f"""
                <div style='background: white; border-left: 4px solid {color}; padding: 0.8rem 1rem;
                            margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; display: flex; align-items: center; gap: 1rem;'>
                    <div style='font-size: 1.3rem; font-weight: 700; color: #9CA3AF; min-width: 2rem;'>#{i}</div>
                    <div style='flex: 1;'>
                        <div style='font-weight: 600; color: #1F2937;'>{r['funcionario_apellido_nombre']}</div>
                        <div style='font-size: 0.8rem; color: #6B7280;'>{r['bloque'] or '—'} · {a_ini}→{a_fin} {ipc_txt}</div>
                    </div>
                    <div style='text-align: right;'>
                        <div style='font-size: 1.1rem; font-weight: 700; color: {color};'>{signo}{fmt_pesos(r['variacion_absoluta'])}</div>
                        <div style='font-size: 0.8rem; color: #6B7280;'>{fmt_pesos(r['pat_inicio'])} → {fmt_pesos(r['pat_fin'])}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
