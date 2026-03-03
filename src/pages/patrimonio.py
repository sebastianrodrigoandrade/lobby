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
            WHERE patrimonio_neto IS NOT NULL
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
            WHERE patrimonio_neto IS NOT NULL
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
            WHERE d.patrimonio_neto IS NOT NULL AND l.bloque = :bloque
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
            WHERE l.bloque IS NOT NULL
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
        where = ["patrimonio_neto IS NOT NULL"]
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
        df['bloque'] = None  # No tenemos bloque sin el vinculo
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
            WHERE cuit = :cuit
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
        where = ["patrimonio_neto IS NOT NULL"]
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
            # Tomar el ultimo año de cada legislador usando subquery
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
    
    # Merge con indicadores
    df = df_evol.copy()
    df = df.merge(df_indicadores.reset_index(), on='anio', how='inner')
    
    if len(df) < 2:
        return None
    
    anio_inicial = df['anio'].min()
    anio_final = df['anio'].max()
    
    pat_inicial = df[df['anio'] == anio_inicial]['patrimonio_promedio'].values[0]
    pat_final = df[df['anio'] == anio_final]['patrimonio_promedio'].values[0]
    
    dolar_inicial = df[df['anio'] == anio_inicial]['dolar'].values[0]
    dolar_final = df[df['anio'] == anio_final]['dolar'].values[0]
    
    ipc_inicial = df[df['anio'] == anio_inicial]['ipc'].values[0]
    ipc_final = df[df['anio'] == anio_final]['ipc'].values[0]
    
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
        'gano_inflacion': var_real > 0
    }

def grafico_evolucion_comparativa(df_evol, df_indicadores, titulo="Evolucion Patrimonial"):
    """Genera grafico de lineas comparativo."""
    if df_evol.empty:
        return None
    
    df = df_evol.merge(df_indicadores.reset_index(), on='anio', how='inner')
    
    if df.empty:
        return None
    
    # Calcular indices base 100
    base = df.iloc[0]
    df['pat_idx'] = (df['patrimonio_promedio'] / base['patrimonio_promedio']) * 100
    df['ipc_idx'] = (df['ipc'] / base['ipc']) * 100
    df['dolar_idx'] = (df['dolar'] / base['dolar']) * 100
    df['pat_usd'] = df['patrimonio_promedio'] / df['dolar']
    
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
    df['pat_usd'] = df['patrimonio_promedio'] / df['dolar']
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['anio'],
        y=df['pat_usd'],
        marker_color='#2563EB',
        text=[f"USD {v:,.0f}" for v in df['pat_usd']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="Patrimonio Promedio (USD)",
        template="plotly_white",
        height=350
    )
    
    return fig

def mostrar_metricas(metricas):
    """Muestra metricas de evolucion."""
    if not metricas:
        st.info("No hay datos suficientes para calcular metricas.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"Var. Nominal ({metricas['anio_inicial']}-{metricas['anio_final']})",
            f"{metricas['var_nominal']:+,.1f}%"
        )
    
    with col2:
        st.metric("Inflacion Acumulada", f"{metricas['inflacion_acum']:,.1f}%")
    
    with col3:
        st.metric(
            "Variacion Real",
            f"{metricas['var_real']:+,.1f}%",
            delta="Gano vs inflacion" if metricas['gano_inflacion'] else "Perdio vs inflacion",
            delta_color="normal" if metricas['gano_inflacion'] else "inverse"
        )
    
    with col4:
        st.metric("Var. en USD", f"{metricas['var_usd']:+,.1f}%")

# ============================================
# PAGINA PRINCIPAL
# ============================================

def render():
    """Renderiza la pagina de patrimonio."""
    
    st.title("Patrimonio de Legisladores")
    st.markdown("Declaraciones juradas y evolucion patrimonial · Fuente: Oficina Anticorrupcion")
    
    # Cargar indicadores una vez
    df_indicadores = cargar_indicadores()
    
    # ========================================
    # NIVEL 1: VISION GENERAL
    # ========================================
    
    st.markdown("---")
    st.markdown("## Vision General")
    
    df_general = cargar_evolucion_general()
    
    if df_general.empty:
        st.warning("No hay datos de DDJJ disponibles.")
        return
    
    # Metricas generales del ultimo año
    ultimo_anio = df_general['anio'].max()
    datos_ultimo = df_general[df_general['anio'] == ultimo_anio].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Legisladores con DDJJ", f"{int(datos_ultimo['legisladores']):,}")
    col2.metric("Patrimonio Promedio", fmt_pesos(datos_ultimo['patrimonio_promedio']))
    col3.metric("Mediana", fmt_pesos(datos_ultimo['mediana']))
    col4.metric("Año", int(ultimo_anio))
    
    # Evolucion general
    st.markdown("### Evolucion del Patrimonio Promedio")
    
    metricas = calcular_metricas_evolucion(df_general, df_indicadores)
    mostrar_metricas(metricas)
    
    tab1, tab2 = st.tabs(["Comparativa con Inflacion", "Patrimonio en USD"])
    
    with tab1:
        fig = grafico_evolucion_comparativa(df_general, df_indicadores, "Patrimonio vs Inflacion vs Dolar (Base 100)")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Si la linea azul (patrimonio) esta por encima de la roja (inflacion), los legisladores ganaron poder adquisitivo.")
    
    with tab2:
        fig = grafico_patrimonio_usd(df_general, df_indicadores)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    
    # ========================================
    # NIVEL 2: POR CAMARA
    # ========================================
    
    st.markdown("---")
    st.markdown("## Por Camara")
    
    df_camara = cargar_evolucion_por_camara()
    
    if not df_camara.empty:
        camaras = df_camara['camara'].unique().tolist()
        
        cols = st.columns(len(camaras))
        
        for i, camara in enumerate(camaras):
            df_cam = df_camara[df_camara['camara'] == camara]
            
            with cols[i]:
                st.markdown(f"### {camara}")
                
                ultimo = df_cam[df_cam['anio'] == df_cam['anio'].max()].iloc[0]
                st.metric("Patrimonio Promedio", fmt_pesos(ultimo['patrimonio_promedio']))
                st.metric("Legisladores", int(ultimo['legisladores']))
                
                # Mini grafico
                metricas_cam = calcular_metricas_evolucion(
                    df_cam.rename(columns={'patrimonio_promedio': 'patrimonio_promedio'}),
                    df_indicadores
                )
                if metricas_cam:
                    color = "green" if metricas_cam['gano_inflacion'] else "red"
                    st.markdown(f"**Var. Real:** <span style='color:{color}'>{metricas_cam['var_real']:+.1f}%</span>", unsafe_allow_html=True)
    
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
            
            if not df_bloque.empty:
                st.markdown(f"### {bloque_sel}")
                
                metricas_bloque = calcular_metricas_evolucion(df_bloque, df_indicadores)
                mostrar_metricas(metricas_bloque)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = grafico_evolucion_comparativa(df_bloque, df_indicadores, f"Evolucion - {bloque_sel}")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = grafico_patrimonio_usd(df_bloque, df_indicadores, f"Patrimonio USD - {bloque_sel}")
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
        anios_disponibles = df_general['anio'].tolist()
        anio_rank = st.selectbox("Año", ["Ultimo disponible"] + anios_disponibles, key="rank_anio")
    with col2:
        camara_rank = st.selectbox("Camara", ["Todas", "Diputados", "Senadores"], key="rank_camara")
    with col3:
        top_n = st.slider("Top", 10, 50, 20, key="rank_n")
    
    anio_param = None if anio_rank == "Ultimo disponible" else anio_rank
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