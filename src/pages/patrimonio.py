# -*- coding: utf-8 -*-
"""
Lobby - Pagina de Patrimonio
Flujo: General -> Camara -> Bloque -> Legislador
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text
from src.database import SessionLocal

# URL del buscador de DDJJ
URL_BUSCADOR = "https://djci.oac.uncoma.edu.ar/consulta.php"

# ============================================
# FUNCIONES DE FORMATO
# ============================================

def fmt_pesos(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    return f"${valor:,.0f}".replace(",", ".")

def fmt_usd(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    return f"USD {valor:,.0f}".replace(",", ".")

def fmt_pct(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    return f"{valor:+.1f}%"

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_indicadores():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT anio, dolar_fin_anio as dolar, ipc_acumulado as ipc, inflacion_anual
            FROM indicadores_anuales ORDER BY anio
        """))
        df = pd.DataFrame(result.fetchall(), columns=['anio', 'dolar', 'ipc', 'inflacion'])
        return df.set_index('anio')
    except:
        return pd.DataFrame()
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_evolucion_general():
    """Carga evolucion patrimonial general (todos los legisladores)."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                anio,
                COUNT(*) as legisladores,
                AVG(patrimonio_neto) as patrimonio_promedio,
                SUM(patrimonio_neto) as patrimonio_total,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
            FROM ddjj_legisladores
            WHERE patrimonio_neto IS NOT NULL AND patrimonio_neto > 0
            GROUP BY anio
            ORDER BY anio
        """))
        return pd.DataFrame(result.fetchall(), columns=['anio', 'legisladores', 'patrimonio_promedio', 'patrimonio_total', 'mediana'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_evolucion_por_camara():
    """Carga evolucion patrimonial por camara."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                anio,
                CASE
                    WHEN organismo ILIKE '%SENADO%' THEN 'Senadores'
                    ELSE 'Diputados'
                END as camara,
                COUNT(*) as legisladores,
                AVG(patrimonio_neto) as patrimonio_promedio
            FROM ddjj_legisladores
            WHERE patrimonio_neto IS NOT NULL AND patrimonio_neto > 0
            GROUP BY anio, camara
            ORDER BY anio, camara
        """))
        return pd.DataFrame(result.fetchall(), columns=['anio', 'camara', 'legisladores', 'patrimonio_promedio'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_evolucion_por_bloque(bloque):
    """Carga evolucion patrimonial de un bloque especifico."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                d.anio,
                COUNT(*) as legisladores,
                AVG(d.patrimonio_neto) as patrimonio_promedio
            FROM ddjj_legisladores d
            JOIN legisladores l ON d.legislador_id = l.id
            WHERE d.patrimonio_neto IS NOT NULL AND d.patrimonio_neto > 0 AND l.bloque = :bloque
            GROUP BY d.anio
            ORDER BY d.anio
        """), {'bloque': bloque})
        return pd.DataFrame(result.fetchall(), columns=['anio', 'legisladores', 'patrimonio_promedio'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_bloques_con_ddjj():
    """Lista de bloques que tienen DDJJ."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT DISTINCT l.bloque, COUNT(*) as total
            FROM ddjj_legisladores d
            JOIN legisladores l ON d.legislador_id = l.id
            WHERE l.bloque IS NOT NULL AND d.patrimonio_neto > 0
            GROUP BY l.bloque
            ORDER BY total DESC
        """))
        return [r[0] for r in result.fetchall()]
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_legisladores_con_ddjj(bloque=None, camara=None):
    """Lista de legisladores con DDJJ, opcionalmente filtrados."""
    db = SessionLocal()
    try:
        where = ["patrimonio_neto IS NOT NULL", "patrimonio_neto > 0"]
        params = {}

        if camara:
            if camara == "Diputados":
                where.append("organismo ILIKE '%DIPUTADOS%'")
            elif camara == "Senadores":
                where.append("organismo ILIKE '%SENADO%'")

        where_sql = " AND ".join(where)

        result = db.execute(text(f"""
            SELECT
                cuit,
                funcionario_apellido_nombre as nombre,
                CASE
                    WHEN organismo ILIKE '%SENADO%' THEN 'Senadores'
                    ELSE 'Diputados'
                END as camara,
                COUNT(DISTINCT anio) as anios_ddjj,
                MAX(patrimonio_neto) as ultimo_patrimonio
            FROM ddjj_legisladores
            WHERE {where_sql}
            GROUP BY cuit, funcionario_apellido_nombre, organismo
            ORDER BY ultimo_patrimonio DESC
        """), params)
        df = pd.DataFrame(result.fetchall(), columns=['cuit', 'nombre', 'camara', 'anios_ddjj', 'ultimo_patrimonio'])
        df['bloque'] = None
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_serie_legislador(cuit):
    """Carga serie historica de un legislador."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT anio, patrimonio_neto, total_bienes, total_deudas, tipo_declaracion
            FROM ddjj_legisladores
            WHERE cuit = :cuit AND patrimonio_neto IS NOT NULL
            ORDER BY anio
        """), {'cuit': cuit})
        return pd.DataFrame(result.fetchall(), columns=['anio', 'patrimonio_neto', 'total_bienes', 'total_deudas', 'tipo_declaracion'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_ranking_patrimonio(anio=None, camara=None, limit=20):
    """Ranking de legisladores por patrimonio."""
    db = SessionLocal()
    try:
        where = ["patrimonio_neto IS NOT NULL", "patrimonio_neto > 0"]
        params = {}

        if anio:
            where.append("anio = :anio")
            params['anio'] = anio
        if camara:
            if camara == "Diputados":
                where.append("organismo ILIKE '%DIPUTADOS%'")
            elif camara == "Senadores":
                where.append("organismo ILIKE '%SENADO%'")
        
        where_sql = " AND ".join(where)
        
        if anio:
            result = db.execute(text(f"""
                SELECT 
                    funcionario_apellido_nombre as nombre,
                    CASE 
                        WHEN organismo ILIKE '%SENADO%' THEN 'Senadores'
                        ELSE 'Diputados'
                    END as camara,
                    patrimonio_neto,
                    anio
                FROM ddjj_legisladores
                WHERE {where_sql}
                ORDER BY patrimonio_neto DESC
            """), params)
        else:
            result = db.execute(text(f"""
                SELECT nombre, camara, patrimonio_neto, anio FROM (
                    SELECT DISTINCT ON (cuit)
                        funcionario_apellido_nombre as nombre,
                        CASE 
                            WHEN organismo ILIKE '%SENADO%' THEN 'Senadores'
                            ELSE 'Diputados'
                        END as camara,
                        patrimonio_neto,
                        anio
                    FROM ddjj_legisladores
                    WHERE {where_sql}
                    ORDER BY cuit, anio DESC
                ) sub
                ORDER BY patrimonio_neto DESC
            """), params)

        df = pd.DataFrame(result.fetchall(), columns=['nombre', 'camara', 'patrimonio_neto', 'anio'])
        if not df.empty:
            df['patrimonio_neto'] = pd.to_numeric(df['patrimonio_neto'], errors='coerce')
            df = df.dropna(subset=['patrimonio_neto'])
            df = df.nlargest(limit, 'patrimonio_neto')
        return df
    finally:
        db.close()

# ============================================
# FUNCIONES DE VISUALIZACION
# ============================================

def calcular_metricas_evolucion(df_evol, df_indicadores):
    """Calcula metricas de evolucion patrimonial vs indicadores."""
    if df_evol.empty or df_indicadores.empty:
        return None

    df = df_evol.copy()
    df = df.merge(df_indicadores.reset_index(), on='anio', how='inner')

    if len(df) < 2:
        return None

    anio_inicial = df['anio'].min()
    anio_final = df['anio'].max()

    pat_inicial = float(df[df['anio'] == anio_inicial]['patrimonio_promedio'].values[0])
    pat_final = float(df[df['anio'] == anio_final]['patrimonio_promedio'].values[0])

    dolar_inicial = float(df[df['anio'] == anio_inicial]['dolar'].values[0])
    dolar_final = float(df[df['anio'] == anio_final]['dolar'].values[0])

    ipc_inicial = float(df[df['anio'] == anio_inicial]['ipc'].values[0])
    ipc_final = float(df[df['anio'] == anio_final]['ipc'].values[0])

    var_nominal = ((pat_final / pat_inicial) - 1) * 100 if pat_inicial else 0
    var_dolar = ((dolar_final / dolar_inicial) - 1) * 100 if dolar_inicial else 0
    inflacion_acum = ((ipc_final / ipc_inicial) - 1) * 100 if ipc_inicial else 0
    var_real = var_nominal - inflacion_acum

    pat_usd_inicial = pat_inicial / dolar_inicial if dolar_inicial else 0
    pat_usd_final = pat_final / dolar_final if dolar_final else 0
    var_usd = ((pat_usd_final / pat_usd_inicial) - 1) * 100 if pat_usd_inicial else 0
    
    return {
        'anio_inicial': anio_inicial,
        'anio_final': anio_final,
        'var_nominal': var_nominal,
        'inflacion_acum': inflacion_acum,
        'var_real': var_real,
        'var_usd': var_usd,
        'pat_usd_final': pat_usd_final,
        'gano_inflacion': var_real > 0
    }

def grafico_evolucion_comparativa(df_evol, df_indicadores, titulo="Evolucion Patrimonial"):
    """Genera grafico de lineas comparativo."""
    if df_evol.empty:
        return None

    df = df_evol.merge(df_indicadores.reset_index(), on='anio', how='inner')

    if df.empty or len(df) < 2:
        return None

    # Convertir a float para evitar errores con Decimal
    df['patrimonio_promedio'] = df['patrimonio_promedio'].astype(float)
    df['ipc'] = df['ipc'].astype(float)
    df['dolar'] = df['dolar'].astype(float)

    # Calcular indices base 100
    base = df.iloc[0]
    base = df.iloc[0]
    df['pat_idx'] = (df['patrimonio_promedio'] / base['patrimonio_promedio']) * 100
    df['ipc_idx'] = (df['ipc'] / base['ipc']) * 100
    df['dolar_idx'] = (df['dolar'] / base['dolar']) * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['pat_idx'],
        name='Patrimonio',
        line=dict(color='#2563EB', width=3),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['ipc_idx'],
        name='Inflacion (IPC)',
        line=dict(color='#DC2626', width=2, dash='dash'),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['dolar_idx'],
        name='Dolar',
        line=dict(color='#059669', width=2, dash='dot'),
        mode='lines+markers'
    ))
    
    fig.add_hline(y=100, line_dash="solid", line_color="gray", opacity=0.3)

    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="Indice (Base 100 = primer año)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=400
    )

    return fig

def grafico_patrimonio_usd(df_evol, df_indicadores, titulo="Patrimonio en USD"):
    """Grafico de patrimonio en dolares."""
    if df_evol.empty:
        return None

    df = df_evol.merge(df_indicadores.reset_index(), on='anio', how='inner')

    if df.empty or len(df) < 2:
        return None

    df['patrimonio_promedio'] = df['patrimonio_promedio'].astype(float)
    df['dolar'] = df['dolar'].astype(float)
    df['patrimonio_usd'] = df['patrimonio_promedio'] / df['dolar']
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['patrimonio_usd'],
        name='Patrimonio USD',
        line=dict(color='#059669', width=3),
        fill='tozeroy',
        fillcolor='rgba(5, 150, 105, 0.1)',
        mode='lines+markers'
    ))

    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="USD",
        yaxis_tickformat="$,.0f",
        template="plotly_white",
        height=400
    )

    return fig

def mostrar_metricas(metricas):
    """Muestra metricas de evolucion patrimonial con explicacion clara."""
    if not metricas:
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            f"Variacion nominal ({metricas['anio_inicial']}-{metricas['anio_final']})",
            fmt_pct(metricas['var_nominal']),
            help="Cambio porcentual del patrimonio en pesos"
        )

    with col2:
        color = "green" if metricas['gano_inflacion'] else "red"
        st.metric(
            "Variacion real (vs inflacion)",
            fmt_pct(metricas['var_real']),
            delta=f"{'Gano' if metricas['gano_inflacion'] else 'Perdio'} contra inflacion",
            delta_color="normal" if metricas['gano_inflacion'] else "inverse",
            help="Variacion nominal menos inflacion acumulada. Positivo = gano poder adquisitivo"
        )

    with col3:
        st.metric(
            "Variacion en USD",
            fmt_pct(metricas['var_usd']),
            help="Cambio porcentual del patrimonio medido en dolares"
        )

# ============================================
# RENDER PRINCIPAL
# ============================================

def render():
    """Renderiza la pagina de patrimonio."""

    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Patrimonio de Legisladores")
    st.markdown("<div class='page-subtitle'>Evolucion patrimonial basada en declaraciones juradas</div>", unsafe_allow_html=True)

    # Cargar datos base
    df_indicadores = cargar_indicadores()
    df_general = cargar_evolucion_general()

    if df_general.empty:
        st.warning("No hay datos de declaraciones juradas disponibles.")
        return

    # ========================================
    # FILTRO GLOBAL DE PERIODO
    # ========================================
    
    anios_disponibles = sorted(df_general['anio'].unique())
    
    col_filtro1, col_filtro2, _ = st.columns([1, 1, 2])
    with col_filtro1:
        anio_desde = st.selectbox("Desde", anios_disponibles, index=0, key="filtro_desde")
    with col_filtro2:
        anios_hasta = [a for a in anios_disponibles if a >= anio_desde]
        anio_hasta = st.selectbox("Hasta", anios_hasta, index=len(anios_hasta)-1, key="filtro_hasta")
    
    # Filtrar datos por periodo seleccionado
    df_general_filtrado = df_general[(df_general['anio'] >= anio_desde) & (df_general['anio'] <= anio_hasta)]
    df_indicadores_filtrado = df_indicadores[(df_indicadores.index >= anio_desde) & (df_indicadores.index <= anio_hasta)]

    st.markdown("---")

    # ========================================
    # NIVEL 1: VISTA GENERAL
    # ========================================

    st.markdown("## Vista General")

    # Metricas principales
    metricas_gen = calcular_metricas_evolucion(df_general_filtrado, df_indicadores_filtrado)
    mostrar_metricas(metricas_gen)

    # Graficos
    col1, col2 = st.columns(2)

    with col1:
        fig = grafico_evolucion_comparativa(df_general_filtrado, df_indicadores_filtrado, "Patrimonio vs Inflacion vs Dolar")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 años de datos para mostrar el grafico")

    with col2:
        fig = grafico_patrimonio_usd(df_general_filtrado, df_indicadores_filtrado, "Patrimonio Promedio en USD")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 años de datos para mostrar el grafico")

    # ========================================
    # NIVEL 2: POR CAMARA
    # ========================================

    st.markdown("---")
    st.markdown("## Por Camara")

    df_camara = cargar_evolucion_por_camara()
    df_camara_filtrado = df_camara[(df_camara['anio'] >= anio_desde) & (df_camara['anio'] <= anio_hasta)]

    if not df_camara_filtrado.empty:
        # Obtener ultimo año filtrado
        ultimo_anio = df_camara_filtrado['anio'].max()
        df_ultimo = df_camara_filtrado[df_camara_filtrado['anio'] == ultimo_anio]

        col1, col2 = st.columns(2)

        for idx, camara in enumerate(['Diputados', 'Senadores']):
            df_cam = df_camara_filtrado[df_camara_filtrado['camara'] == camara]
            datos_ultimo = df_ultimo[df_ultimo['camara'] == camara]

            with [col1, col2][idx]:
                if not datos_ultimo.empty:
                    patrimonio_prom = datos_ultimo['patrimonio_promedio'].values[0]
                    legisladores = int(datos_ultimo['legisladores'].values[0])

                    st.markdown(f"""
                    <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1.5rem; text-align: center;">
                        <div style="font-size: 1.1rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">{camara}</div>
                        <div style="font-size: 0.85rem; color: #6B7280;">Patrimonio Promedio ({ultimo_anio})</div>
                        <div style="font-size: 1.8rem; font-weight: 700; color: #2563EB; margin: 0.5rem 0;">{fmt_pesos(patrimonio_prom)}</div>
                        <div style="font-size: 0.85rem; color: #6B7280;">{legisladores} legisladores con DDJJ</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Calcular variacion real si hay suficientes datos
                    metricas_cam = calcular_metricas_evolucion(
                        df_cam.rename(columns={'patrimonio_promedio': 'patrimonio_promedio'}),
                        df_indicadores_filtrado
                    )
                    if metricas_cam:
                        color = "#059669" if metricas_cam['gano_inflacion'] else "#DC2626"
                        texto = "Gano" if metricas_cam['gano_inflacion'] else "Perdio"
                        st.markdown(f"""
                        <div style="text-align: center; margin-top: 0.5rem; padding: 0.5rem; background: {'#ECFDF5' if metricas_cam['gano_inflacion'] else '#FEF2F2'}; border-radius: 8px;">
                            <span style="color: {color}; font-weight: 600;">{texto} contra inflacion: {metricas_cam['var_real']:+.1f}%</span>
                        </div>
                        """, unsafe_allow_html=True)
    
    # ========================================
    # NIVEL 3: POR BLOQUE
    # ========================================

    st.markdown("---")
    st.markdown("## Por Bloque")

    bloques = cargar_bloques_con_ddjj()

    if bloques:
        bloque_sel = st.selectbox("Seleccionar bloque", [""] + bloques, key="bloque_sel")

        if bloque_sel:
            df_bloque = cargar_evolucion_por_bloque(bloque_sel)
            df_bloque_filtrado = df_bloque[(df_bloque['anio'] >= anio_desde) & (df_bloque['anio'] <= anio_hasta)]

            if not df_bloque_filtrado.empty:
                st.markdown(f"### {bloque_sel}")

                metricas_bloque = calcular_metricas_evolucion(df_bloque_filtrado, df_indicadores_filtrado)
                mostrar_metricas(metricas_bloque)

                col1, col2 = st.columns(2)

                with col1:
                    fig = grafico_evolucion_comparativa(df_bloque_filtrado, df_indicadores_filtrado, f"Evolucion - {bloque_sel}")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = grafico_patrimonio_usd(df_bloque_filtrado, df_indicadores_filtrado, f"Patrimonio USD - {bloque_sel}")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                # Legisladores del bloque
                st.markdown("#### Legisladores del bloque")
                df_legs = cargar_legisladores_con_ddjj(bloque=bloque_sel)

                if not df_legs.empty:
                    st.dataframe(
                        df_legs[['nombre', 'camara', 'anios_ddjj', 'ultimo_patrimonio']].rename(columns={
                            'nombre': 'Legislador',
                            'camara': 'Camara',
                            'anios_ddjj': 'DDJJ',
                            'ultimo_patrimonio': 'Ultimo Patrimonio'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Ultimo Patrimonio': st.column_config.NumberColumn(format="$ %d")
                        }
                    )

    # ========================================
    # NIVEL 4: POR LEGISLADOR
    # ========================================

    st.markdown("---")
    st.markdown("## Por Legislador")

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        camara_filtro = st.selectbox("Filtrar por camara", ["Todas", "Diputados", "Senadores"], key="leg_camara")
    with col2:
        busqueda = st.text_input("Buscar por nombre", placeholder="Ej: Kirchner...", key="leg_busq")

    df_legisladores = cargar_legisladores_con_ddjj(
        camara=camara_filtro if camara_filtro != "Todas" else None
    )

    if busqueda:
        df_legisladores = df_legisladores[
            df_legisladores['nombre'].str.contains(busqueda, case=False, na=False)
        ]

    if not df_legisladores.empty:
        # Selector de legislador
        opciones = df_legisladores['nombre'].tolist()

        legislador_sel = st.selectbox(
            f"Seleccionar legislador ({len(opciones)} disponibles)",
            [""] + opciones,
            key="leg_sel"
        )

        if legislador_sel:
            leg_data = df_legisladores[df_legisladores['nombre'] == legislador_sel].iloc[0]
            cuit = leg_data['cuit']

            st.markdown(f"### {legislador_sel}")

            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Bloque:** {leg_data['bloque'] or '-'}")
            col2.markdown(f"**Camara:** {leg_data['camara'] or '-'}")
            col3.markdown(f"**DDJJ disponibles:** {int(leg_data['anios_ddjj'])}")

            # Serie historica
            df_serie = cargar_serie_legislador(cuit)

            if not df_serie.empty and not df_indicadores.empty:
                # Calcular patrimonio en USD
                df_serie = df_serie.merge(df_indicadores.reset_index()[['anio', 'dolar']], on='anio', how='left')
                df_serie['patrimonio_neto'] = df_serie['patrimonio_neto'].astype(float)
                df_serie['dolar'] = df_serie['dolar'].astype(float)
                df_serie['patrimonio_usd'] = df_serie['patrimonio_neto'] / df_serie['dolar']

                # Grafico
                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=df_serie['anio'],
                    y=df_serie['patrimonio_usd'],
                    name="Patrimonio USD",
                    line=dict(color="#2563EB", width=3),
                    fill='tozeroy',
                    fillcolor='rgba(37, 99, 235, 0.1)',
                    mode='lines+markers'
                ))

                fig.update_layout(
                    title="Evolucion Patrimonial en USD",
                    xaxis_title="Año",
                    yaxis_title="USD",
                    yaxis_tickformat="$,.0f",
                    template="plotly_white",
                    height=350
                )

                st.plotly_chart(fig, use_container_width=True)

                # Tabla detalle
                st.markdown("#### Detalle por año")

                tabla = df_serie[['anio', 'patrimonio_neto', 'patrimonio_usd', 'total_bienes', 'total_deudas']].copy()
                tabla.columns = ['Año', 'Patrimonio $', 'Patrimonio USD', 'Bienes', 'Deudas']

                st.dataframe(
                    tabla,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Patrimonio $': st.column_config.NumberColumn(format="$ %d"),
                        'Patrimonio USD': st.column_config.NumberColumn(format="USD %d"),
                        'Bienes': st.column_config.NumberColumn(format="$ %d"),
                        'Deudas': st.column_config.NumberColumn(format="$ %d"),
                    }
                )

    # ========================================
    # RANKING
    # ========================================

    st.markdown("---")
    st.markdown("## Ranking de Patrimonio")

    col1, col2, col3 = st.columns(3)
    with col1:
        anios_rank = sorted([int(x) for x in df_general['anio'].unique()], reverse=True)
        anio_rank = st.selectbox("Año", ["Ultimo disponible"] + list(anios_rank), key="rank_anio")
    with col2:
        camara_rank = st.selectbox("Camara", ["Todas", "Diputados", "Senadores"], key="rank_camara")
    with col3:
        top_n = st.slider("Top", 10, 50, 20, key="rank_n")

    anio_param = None if anio_rank == "Ultimo disponible" else int(anio_rank)
    camara_param = None if camara_rank == "Todas" else camara_rank

    df_ranking = cargar_ranking_patrimonio(anio=anio_param, camara=camara_param, limit=top_n)
    
    if not df_ranking.empty:
        for i, (_, row) in enumerate(df_ranking.iterrows(), 1):
            st.markdown(f"""
            <div style='background: white; border-left: 4px solid #2563EB; padding: 0.8rem 1rem;
                        margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; display: flex; align-items: center; gap: 1rem;'>
                <div style='font-size: 1.3rem; font-weight: 700; color: #9CA3AF; min-width: 2rem;'>#{i}</div>
                <div style='flex: 1;'>
                    <div style='font-weight: 600; color: #1F2937;'>{row['nombre']}</div>
                    <div style='font-size: 0.8rem; color: #6B7280;'>{row['camara'] or '-'}</div>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 1.1rem; font-weight: 700; color: #2563EB;'>{fmt_pesos(row['patrimonio_neto'])}</div>
                    <div style='font-size: 0.8rem; color: #6B7280;'>DDJJ {int(row['anio'])}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # ========================================
    # INFO ADICIONAL
    # ========================================

    st.markdown("---")
    with st.expander("¿Como consultar la declaracion original?"):
        st.markdown(f"""
        **Buscador de la Oficina Anticorrupcion:**
        [Consultar DDJJ]({URL_BUSCADOR})

        Podes buscar por CUIT del legislador.
        """)
    
    with st.expander("¿Que significa cada metrica?"):
        st.markdown("""
        - **Variacion nominal**: Cambio porcentual del patrimonio en pesos argentinos.
        - **Variacion real (vs inflacion)**: Variacion nominal menos la inflacion acumulada del periodo. Si es positiva, el patrimonio gano poder adquisitivo. Si es negativa, perdio.
        - **Variacion en USD**: Cambio porcentual del patrimonio medido en dolares estadounidenses.
        
        Los graficos muestran indices base 100, donde el primer año del periodo seleccionado equivale a 100. Esto permite comparar facilmente como evoluciono el patrimonio respecto a la inflacion y el dolar.
        """)