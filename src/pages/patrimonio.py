# -*- coding: utf-8 -*-
"""
Lobby - Pagina de Patrimonio
Flujo: General -> Camara -> Bloque -> Legislador
Solo legisladores con patrimonio > 0
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
    if pd.isna(valor) or valor is None or valor == 0:
        return "-"
    return f"${valor:,.0f}".replace(",", ".")

def fmt_usd(valor):
    if pd.isna(valor) or valor is None or valor == 0:
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
        # Convertir a float
        for col in ['dolar', 'ipc', 'inflacion']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.set_index('anio')
    except:
        return pd.DataFrame()
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_anios_disponibles():
    """Retorna los años con DDJJ disponibles."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT DISTINCT anio FROM ddjj_legisladores
            WHERE patrimonio_neto > 0
            ORDER BY anio
        """))
        return [row[0] for row in result.fetchall()]
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_evolucion_general(solo_vigentes=False):
    """Carga evolucion patrimonial general."""
    db = SessionLocal()
    try:
        if solo_vigentes:
            query = """
                SELECT
                    d.anio,
                    COUNT(*) as legisladores,
                    AVG(d.patrimonio_neto) as patrimonio_promedio,
                    SUM(d.patrimonio_neto) as patrimonio_total,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.patrimonio_neto) as mediana
                FROM ddjj_legisladores d
                JOIN legisladores l ON d.legislador_id = l.id
                WHERE d.patrimonio_neto > 0
                  AND l.mandato_hasta >= CURRENT_DATE
                GROUP BY d.anio
                ORDER BY d.anio
            """
        else:
            query = """
                SELECT
                    anio,
                    COUNT(*) as legisladores,
                    AVG(patrimonio_neto) as patrimonio_promedio,
                    SUM(patrimonio_neto) as patrimonio_total,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
                FROM ddjj_legisladores
                WHERE patrimonio_neto > 0
                GROUP BY anio
                ORDER BY anio
            """
        result = db.execute(text(query))
        df = pd.DataFrame(result.fetchall(), columns=['anio', 'legisladores', 'patrimonio_promedio', 'patrimonio_total', 'mediana'])
        # Convertir a float
        for col in ['patrimonio_promedio', 'patrimonio_total', 'mediana']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_evolucion_por_camara(solo_vigentes=False):
    """Carga evolucion patrimonial por camara."""
    db = SessionLocal()
    try:
        if solo_vigentes:
            query = """
                SELECT
                    d.anio,
                    CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    COUNT(*) as legisladores,
                    AVG(d.patrimonio_neto) as patrimonio_promedio,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.patrimonio_neto) as mediana
                FROM ddjj_legisladores d
                JOIN legisladores l ON d.legislador_id = l.id
                WHERE d.patrimonio_neto > 0 AND l.mandato_hasta >= CURRENT_DATE
                GROUP BY d.anio, camara
                ORDER BY d.anio, camara
            """
        else:
            query = """
                SELECT
                    anio,
                    CASE WHEN organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    COUNT(*) as legisladores,
                    AVG(patrimonio_neto) as patrimonio_promedio,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
                FROM ddjj_legisladores
                WHERE patrimonio_neto > 0
                GROUP BY anio, camara
                ORDER BY anio, camara
            """
        result = db.execute(text(query))
        df = pd.DataFrame(result.fetchall(), columns=['anio', 'camara', 'legisladores', 'patrimonio_promedio', 'mediana'])
        df['patrimonio_promedio'] = pd.to_numeric(df['patrimonio_promedio'], errors='coerce')
        df['mediana'] = pd.to_numeric(df['mediana'], errors='coerce')
        return df
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
            WHERE d.patrimonio_neto > 0 AND l.bloque = :bloque
            GROUP BY d.anio
            ORDER BY d.anio
        """), {'bloque': bloque})
        df = pd.DataFrame(result.fetchall(), columns=['anio', 'legisladores', 'patrimonio_promedio'])
        df['patrimonio_promedio'] = pd.to_numeric(df['patrimonio_promedio'], errors='coerce')
        return df
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
def cargar_legisladores_con_ddjj(camara=None):
    """Lista de legisladores con DDJJ."""
    db = SessionLocal()
    try:
        where = ["d.patrimonio_neto > 0", "d.legislador_id IS NOT NULL"]
        if camara and camara != "Todas":
            if camara == "Diputados":
                where.append("d.organismo ILIKE '%DIPUTADOS%'")
            else:
                where.append("d.organismo ILIKE '%SENADO%'")
        
        where_sql = " AND ".join(where)
        
        result = db.execute(text(f"""
            SELECT
                d.cuit,
                d.funcionario_apellido_nombre as nombre,
                CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                l.bloque,
                COUNT(DISTINCT d.anio) as anios_ddjj,
                MAX(d.patrimonio_neto) as ultimo_patrimonio,
                d.legislador_id
            FROM ddjj_legisladores d
            LEFT JOIN legisladores l ON d.legislador_id = l.id
            WHERE {where_sql}
            GROUP BY d.cuit, d.funcionario_apellido_nombre, d.organismo, l.bloque, d.legislador_id
            ORDER BY ultimo_patrimonio DESC
        """))
        df = pd.DataFrame(result.fetchall(), columns=['cuit', 'nombre', 'camara', 'bloque', 'anios_ddjj', 'ultimo_patrimonio', 'legislador_id'])
        df['ultimo_patrimonio'] = pd.to_numeric(df['ultimo_patrimonio'], errors='coerce')
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
            WHERE cuit = :cuit AND patrimonio_neto > 0
            ORDER BY anio
        """), {'cuit': cuit})
        df = pd.DataFrame(result.fetchall(), columns=['anio', 'patrimonio_neto', 'total_bienes', 'total_deudas', 'tipo_declaracion'])
        for col in ['patrimonio_neto', 'total_bienes', 'total_deudas']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_ranking_patrimonio(anio=None, camara=None, limit=20):
    """Ranking de legisladores por patrimonio."""
    db = SessionLocal()
    try:
        where = ["patrimonio_neto > 0"]
        params = {'limit': limit}
        
        if anio:
            where.append("anio = :anio")
            params['anio'] = int(anio)
        if camara and camara != "Todas":
            if camara == "Diputados":
                where.append("organismo ILIKE '%DIPUTADOS%'")
            else:
                where.append("organismo ILIKE '%SENADO%'")
        
        where_sql = " AND ".join(where)
        
        if anio:
            query = f"""
                SELECT 
                    funcionario_apellido_nombre as nombre,
                    CASE WHEN organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    patrimonio_neto,
                    anio
                FROM ddjj_legisladores
                WHERE {where_sql}
                ORDER BY patrimonio_neto DESC
                LIMIT :limit
            """
        else:
            query = f"""
                SELECT nombre, camara, patrimonio_neto, anio FROM (
                    SELECT DISTINCT ON (cuit)
                        funcionario_apellido_nombre as nombre,
                        CASE WHEN organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                        patrimonio_neto,
                        anio
                    FROM ddjj_legisladores
                    WHERE {where_sql}
                    ORDER BY cuit, anio DESC
                ) sub
                ORDER BY patrimonio_neto DESC
                LIMIT :limit
            """
        
        result = db.execute(text(query), params)
        df = pd.DataFrame(result.fetchall(), columns=['nombre', 'camara', 'patrimonio_neto', 'anio'])
        df['patrimonio_neto'] = pd.to_numeric(df['patrimonio_neto'], errors='coerce')
        return df
    finally:
        db.close()

# ============================================
# FUNCIONES DE VISUALIZACION
# ============================================

def calcular_metricas_evolucion(df_evol, df_indicadores, anio_inicial=None, anio_final=None):
    """Calcula metricas de evolucion patrimonial vs indicadores."""
    if df_evol.empty or df_indicadores.empty:
        return None

    df = df_evol.copy()
    df = df.merge(df_indicadores.reset_index(), on='anio', how='inner')

    if len(df) < 2:
        return None

    # Usar años especificados o los extremos disponibles
    if anio_inicial is None:
        anio_inicial = int(df['anio'].min())
    if anio_final is None:
        anio_final = int(df['anio'].max())
    
    df_inicial = df[df['anio'] == anio_inicial]
    df_final = df[df['anio'] == anio_final]
    
    if df_inicial.empty or df_final.empty:
        return None

    pat_inicial = float(df_inicial['patrimonio_promedio'].values[0])
    pat_final = float(df_final['patrimonio_promedio'].values[0])
    dolar_inicial = float(df_inicial['dolar'].values[0])
    dolar_final = float(df_final['dolar'].values[0])
    ipc_inicial = float(df_inicial['ipc'].values[0])
    ipc_final = float(df_final['ipc'].values[0])

    # Calcular variaciones como ratios
    ratio_patrimonio = pat_final / pat_inicial if pat_inicial else 1
    ratio_inflacion = ipc_final / ipc_inicial if ipc_inicial else 1
    ratio_dolar = dolar_final / dolar_inicial if dolar_inicial else 1

    # Variación nominal (en porcentaje)
    var_nominal = (ratio_patrimonio - 1) * 100

    # Inflación acumulada del período (en porcentaje)
    inflacion_acum = (ratio_inflacion - 1) * 100

    # Variación REAL: cuánto ganó/perdió en términos de poder adquisitivo
    # Fórmula: (1 + rendimiento) / (1 + inflación) - 1
    var_real = ((ratio_patrimonio / ratio_inflacion) - 1) * 100

    pat_usd_inicial = pat_inicial / dolar_inicial if dolar_inicial else 0
    pat_usd_final = pat_final / dolar_final if dolar_final else 0
    var_usd = ((pat_usd_final / pat_usd_inicial) - 1) * 100 if pat_usd_inicial else 0

    return {
        'anio_inicial': anio_inicial,
        'anio_final': anio_final,
        'pat_inicial': pat_inicial,
        'pat_final': pat_final,
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

    # Convertir a float
    df['patrimonio_promedio'] = pd.to_numeric(df['patrimonio_promedio'], errors='coerce')
    df['ipc'] = pd.to_numeric(df['ipc'], errors='coerce')
    df['dolar'] = pd.to_numeric(df['dolar'], errors='coerce')

    # Calcular indices base 100
    base = df.iloc[0]
    df['pat_idx'] = (df['patrimonio_promedio'] / float(base['patrimonio_promedio'])) * 100
    df['ipc_idx'] = (df['ipc'] / float(base['ipc'])) * 100
    df['dolar_idx'] = (df['dolar'] / float(base['dolar'])) * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['pat_idx'],
        name='Patrimonio',
        line=dict(color='#2563EB', width=3),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['ipc_idx'],
        name='Inflación (IPC)',
        line=dict(color='#DC2626', width=2, dash='dash'),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=df['anio'], y=df['dolar_idx'],
        name='Dólar',
        line=dict(color='#059669', width=2, dash='dot'),
        mode='lines+markers'
    ))
    
    fig.add_hline(y=100, line_dash="solid", line_color="gray", opacity=0.3)

    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="Índice (Base 100 = primer año)",
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

    df['patrimonio_promedio'] = pd.to_numeric(df['patrimonio_promedio'], errors='coerce')
    df['dolar'] = pd.to_numeric(df['dolar'], errors='coerce')
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
    """Muestra metricas de evolucion patrimonial."""
    if not metricas:
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            f"Var. nominal ({metricas['anio_inicial']}-{metricas['anio_final']})",
            fmt_pct(metricas['var_nominal']),
            help="Cambio porcentual del patrimonio promedio en pesos argentinos entre los años seleccionados"
        )

    with col2:
        st.metric(
            "Var. real (descontando inflación)",
            fmt_pct(metricas['var_real']),
            delta="Ganó poder adquisitivo" if metricas['gano_inflacion'] else "Perdió poder adquisitivo",
            delta_color="normal" if metricas['gano_inflacion'] else "inverse",
            help=f"Patrimonio ajustado por inflación. El patrimonio creció {metricas['var_nominal']:+.1f}% y la inflación fue {metricas['inflacion_acum']:+.1f}%. En términos reales: {metricas['var_real']:+.1f}%"
        )

    with col3:
        st.metric(
            "Var. en dólares",
            fmt_pct(metricas['var_usd']),
            help="Cambio porcentual del patrimonio medido en dólares estadounidenses"
        )

# ============================================
# RENDER PRINCIPAL
# ============================================

def render():
    """Renderiza la pagina de patrimonio."""

    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Patrimonio de Legisladores")
    st.markdown("<div class='page-subtitle'>Evolución patrimonial basada en declaraciones juradas de la Oficina Anticorrupción</div>", unsafe_allow_html=True)

    # Cargar datos base
    df_indicadores = cargar_indicadores()
    anios_disponibles = cargar_anios_disponibles()
    
    if not anios_disponibles:
        st.warning("No hay datos de declaraciones juradas disponibles.")
        return

    # ========================================
    # FILTROS GLOBALES
    # ========================================
    
    st.markdown("### Configuración del análisis")
    
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    
    with col_f1:
        anio_desde = st.selectbox(
            "Año inicial", 
            anios_disponibles, 
            index=0,
            help="Año base para calcular variaciones"
        )
    
    with col_f2:
        anios_hasta = [a for a in anios_disponibles if a >= anio_desde]
        anio_hasta = st.selectbox(
            "Año final", 
            anios_hasta, 
            index=len(anios_hasta)-1,
            help="Año final para calcular variaciones"
        )

    # Info sobre los datos
    with st.expander("ℹ️ ¿Qué significan estas métricas?"):
        st.markdown("""
        **Patrimonio declarado**: Bienes menos deudas según la Declaración Jurada Patrimonial Integral.
        
        **Variación nominal**: Cambio porcentual en pesos argentinos. No considera inflación.
        
        **Variación real**: Variación nominal menos inflación acumulada del período. 
        - Si es **positiva** → el patrimonio creció más que la inflación (ganó poder adquisitivo)
        - Si es **negativa** → el patrimonio creció menos que la inflación (perdió poder adquisitivo)
        
        **Variación en USD**: Cambio porcentual medido en dólares (usando cotización oficial de fin de año).
        
        **Mediana**: El valor del medio cuando ordenás todos los patrimonios de menor a mayor. 
        Es menos sensible a valores extremos que el promedio.
        
        **Nota**: Solo se incluyen declaraciones con patrimonio mayor a $0.
        """)

    st.markdown("---")

    # Cargar datos filtrados
    df_general = cargar_evolucion_general()
    df_general_filtrado = df_general[(df_general['anio'] >= anio_desde) & (df_general['anio'] <= anio_hasta)]
    df_indicadores_filtrado = df_indicadores[(df_indicadores.index >= anio_desde) & (df_indicadores.index <= anio_hasta)]

    if df_general_filtrado.empty:
        st.warning("No hay datos para el período seleccionado.")
        return

    # ========================================
    # NIVEL 1: VISTA GENERAL
    # ========================================

    st.markdown("## Vista General")
    st.caption(f"Todas las declaraciones juradas con patrimonio > $0 ({anio_desde}-{anio_hasta})")

    # Métricas del último año
    ultimo_anio = int(df_general_filtrado['anio'].max())
    datos_ultimo = df_general_filtrado[df_general_filtrado['anio'] == ultimo_anio].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        f"Legisladores con DDJJ ({ultimo_anio})", 
        int(datos_ultimo['legisladores']),
        help="Cantidad de legisladores con declaración jurada y patrimonio > $0"
    )
    col2.metric(
        "Patrimonio promedio", 
        fmt_pesos(datos_ultimo['patrimonio_promedio']),
        help="Promedio aritmético de todos los patrimonios declarados"
    )
    col3.metric(
        "Mediana", 
        fmt_pesos(datos_ultimo['mediana']),
        help="Valor del medio: 50% declara menos y 50% declara más que este valor"
    )
    col4.metric(
        "Patrimonio total", 
        fmt_pesos(datos_ultimo['patrimonio_total']),
        help="Suma de todos los patrimonios declarados"
    )

    # Métricas de variación
    metricas_gen = calcular_metricas_evolucion(df_general_filtrado, df_indicadores_filtrado, anio_desde, anio_hasta)
    if metricas_gen:
        mostrar_metricas(metricas_gen)

    # Gráficos
    col1, col2 = st.columns(2)

    with col1:
        fig = grafico_evolucion_comparativa(df_general_filtrado, df_indicadores_filtrado, "Patrimonio vs Inflación vs Dólar")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 años de datos para mostrar el gráfico")

    with col2:
        fig = grafico_patrimonio_usd(df_general_filtrado, df_indicadores_filtrado, "Patrimonio Promedio en USD")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 años de datos para mostrar el gráfico")

# ========================================
# NIVEL 2: POR CAMARA
# ========================================

    st.markdown("---")
    st.markdown("## Por Cámara")
    st.caption("Se muestra la **mediana** (valor del medio) que es más representativa que el promedio cuando hay patrimonios muy altos que distorsionan.")

    df_camara = cargar_evolucion_por_camara()
    df_camara_filtrado = df_camara[(df_camara['anio'] >= anio_desde) & (df_camara['anio'] <= anio_hasta)]

    if not df_camara_filtrado.empty:
        ultimo_anio_cam = int(df_camara_filtrado['anio'].max())
        primer_anio_cam = int(df_camara_filtrado['anio'].min())
        df_ultimo_cam = df_camara_filtrado[df_camara_filtrado['anio'] == ultimo_anio_cam]
        df_primer_cam = df_camara_filtrado[df_camara_filtrado['anio'] == primer_anio_cam]

        col1, col2 = st.columns(2)

        for idx, camara in enumerate(['Diputados', 'Senadores']):
            datos_ultimo = df_ultimo_cam[df_ultimo_cam['camara'] == camara]
            datos_primer = df_primer_cam[df_primer_cam['camara'] == camara]

            with [col1, col2][idx]:
                if not datos_ultimo.empty and not datos_primer.empty:
                    mediana_final = float(datos_ultimo['mediana'].values[0])
                    mediana_inicial = float(datos_primer['mediana'].values[0])
                    legisladores = int(datos_ultimo['legisladores'].values[0])
                    
                    # Calcular variación real de la mediana
                    ipc_inicial = float(df_indicadores.loc[primer_anio_cam, 'ipc']) if primer_anio_cam in df_indicadores.index else None
                    ipc_final = float(df_indicadores.loc[ultimo_anio_cam, 'ipc']) if ultimo_anio_cam in df_indicadores.index else None
                    
                    if ipc_inicial and ipc_final and mediana_inicial > 0:
                        ratio_mediana = mediana_final / mediana_inicial
                        ratio_inflacion = ipc_final / ipc_inicial
                        var_real_mediana = ((ratio_mediana / ratio_inflacion) - 1) * 100
                        gano = var_real_mediana > 0
                    else:
                        var_real_mediana = None
                        gano = None
                    st.markdown(f"### {camara}")
                    st.metric(
                        f"Mediana patrimonial ({ultimo_anio_cam})", 
                        fmt_pesos(mediana_final),
                        help="Valor del medio: 50% declara menos y 50% declara más"
                    )
                    st.caption(f"{legisladores} legisladores con DDJJ")

                    if var_real_mediana is not None:
                        color = "#059669" if gano else "#DC2626"
                        texto = "Ganó" if gano else "Perdió"
                        st.markdown(f"""
                        <div style="padding: 0.5rem; background: {'#ECFDF5' if gano else '#FEF2F2'}; border-radius: 8px; margin-top: 0.5rem;">
                            <span style="color: {color}; font-weight: 600;">{texto} vs inflación: {var_real_mediana:+.1f}%</span>
                            <br><span style="font-size: 0.8rem; color: #6B7280;">Mediana {primer_anio_cam}: {fmt_pesos(mediana_inicial)} → {ultimo_anio_cam}: {fmt_pesos(mediana_final)}</span>
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

                metricas_bloque = calcular_metricas_evolucion(df_bloque_filtrado, df_indicadores_filtrado, anio_desde, anio_hasta)
                if metricas_bloque:
                    mostrar_metricas(metricas_bloque)

                col1, col2 = st.columns(2)

                with col1:
                    fig = grafico_evolucion_comparativa(df_bloque_filtrado, df_indicadores_filtrado, f"Evolución - {bloque_sel}")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = grafico_patrimonio_usd(df_bloque_filtrado, df_indicadores_filtrado, f"En USD - {bloque_sel}")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos para este bloque en el período seleccionado.")
    else:
        st.info("No hay bloques con DDJJ vinculadas.")

    # ========================================
    # NIVEL 4: POR LEGISLADOR
    # ========================================

    st.markdown("---")
    st.markdown("## Por Legislador")

    col1, col2 = st.columns(2)
    with col1:
        camara_filtro = st.selectbox("Filtrar por cámara", ["Todas", "Diputados", "Senadores"], key="leg_camara")
    with col2:
        busqueda = st.text_input("Buscar por nombre", placeholder="Ej: Kirchner...", key="leg_busq")

    df_legisladores = cargar_legisladores_con_ddjj(camara=camara_filtro)

    if busqueda:
        df_legisladores = df_legisladores[
            df_legisladores['nombre'].str.contains(busqueda, case=False, na=False)
        ]

    if not df_legisladores.empty:
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
            col2.markdown(f"**Cámara:** {leg_data['camara'] or '-'}")
            col3.markdown(f"**DDJJ disponibles:** {int(leg_data['anios_ddjj'])}")

            df_serie = cargar_serie_legislador(cuit)

            if not df_serie.empty and not df_indicadores.empty:
                df_serie = df_serie.merge(df_indicadores.reset_index()[['anio', 'dolar']], on='anio', how='left')
                df_serie['dolar'] = pd.to_numeric(df_serie['dolar'], errors='coerce').fillna(1)
                df_serie['patrimonio_usd'] = df_serie['patrimonio_neto'] / df_serie['dolar']

                # Gráfico
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
                    title="Evolución Patrimonial en USD",
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
            else:
                st.info("No hay datos de patrimonio para este legislador.")
    else:
        st.info("No se encontraron legisladores con esos criterios.")

    # ========================================
    # RANKING
    # ========================================

    st.markdown("---")
    st.markdown("## Ranking de Patrimonio")

    col1, col2, col3 = st.columns(3)
    with col1:
        anios_rank = sorted([int(x) for x in anios_disponibles], reverse=True)
        anio_rank = st.selectbox("Año", ["Último disponible"] + anios_rank, key="rank_anio")
    with col2:
        camara_rank = st.selectbox("Cámara", ["Todas", "Diputados", "Senadores"], key="rank_camara")
    with col3:
        top_n = st.slider("Top", 10, 50, 20, key="rank_n")

    anio_param = None if anio_rank == "Último disponible" else int(anio_rank)
    
    df_ranking = cargar_ranking_patrimonio(anio=anio_param, camara=camara_rank, limit=top_n)
    
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
    else:
        st.info("No hay datos de ranking disponibles.")
    
    # ========================================
    # INFO ADICIONAL
    # ========================================

    st.markdown("---")
    with st.expander("🔗 Consultar declaración original"):
        st.markdown(f"""
        **Buscador de la Oficina Anticorrupción:**
        [Consultar DDJJ]({URL_BUSCADOR})

        Podés buscar por CUIT del legislador para ver la declaración completa.
        """)