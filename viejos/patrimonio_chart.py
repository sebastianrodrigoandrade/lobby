# -*- coding: utf-8 -*-
"""
Componente de grafico comparativo: patrimonio vs indicadores economicos
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text

def get_evolucion_patrimonial(db, legislador_id=None, bloque=None, camara=None):
    """Obtiene evolucion patrimonial agregada por año."""
    
    where_clauses = []
    params = {}
    
    if legislador_id:
        where_clauses.append("d.legislador_id = :leg_id")
        params['leg_id'] = legislador_id
    if bloque:
        where_clauses.append("l.bloque = :bloque")
        params['bloque'] = bloque
    if camara:
        where_clauses.append("l.camara = :camara")
        params['camara'] = camara
    
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query = text(f"""
        SELECT 
            d.anio,
            AVG(d.patrimonio_neto) as patrimonio_promedio,
            SUM(d.patrimonio_neto) as patrimonio_total,
            COUNT(*) as cantidad
        FROM ddjj_legisladores d
        LEFT JOIN legisladores l ON d.legislador_id = l.id
        {where_sql}
        GROUP BY d.anio
        ORDER BY d.anio
    """)
    
    result = db.execute(query, params)
    df = pd.DataFrame(result.fetchall(), columns=['anio', 'patrimonio_promedio', 'patrimonio_total', 'cantidad'])
    return df

def get_indicadores_anuales(db):
    """Obtiene indicadores economicos anuales."""
    query = text("""
        SELECT anio, dolar_fin_anio, ipc_acumulado, inflacion_anual
        FROM indicadores_anuales
        ORDER BY anio
    """)
    result = db.execute(query)
    df = pd.DataFrame(result.fetchall(), columns=['anio', 'dolar', 'ipc', 'inflacion'])
    return df

def calcular_indices_base_100(df_patrimonio, df_indicadores, anio_base=None):
    """Calcula indices con base 100 para comparacion."""
    
    # Merge de datos
    df = pd.merge(df_patrimonio, df_indicadores, on='anio', how='inner')
    
    if df.empty:
        return df
    
    # Usar el primer año como base si no se especifica
    if anio_base is None:
        anio_base = df['anio'].min()
    
    base = df[df['anio'] == anio_base].iloc[0]
    
    # Calcular indices base 100
    df['patrimonio_idx'] = (df['patrimonio_promedio'] / base['patrimonio_promedio']) * 100
    df['dolar_idx'] = (df['dolar'] / base['dolar']) * 100
    df['ipc_idx'] = (df['ipc'] / base['ipc']) * 100
    
    # Patrimonio en USD
    df['patrimonio_usd'] = df['patrimonio_promedio'] / df['dolar']
    df['patrimonio_usd_idx'] = (df['patrimonio_usd'] / df['patrimonio_usd'].iloc[0]) * 100
    
    # Variacion real (patrimonio - inflacion)
    df['variacion_nominal'] = df['patrimonio_idx'].pct_change() * 100
    df['variacion_real'] = df['patrimonio_idx'] - df['ipc_idx']
    
    return df

def grafico_evolucion_comparativa(df, titulo="Evolucion Patrimonial vs Indicadores"):
    """Genera grafico de lineas comparativo con Plotly."""
    
    if df.empty:
        return None
    
    fig = go.Figure()
    
    # Patrimonio nominal (indice)
    fig.add_trace(go.Scatter(
        x=df['anio'],
        y=df['patrimonio_idx'],
        name='Patrimonio Nominal',
        line=dict(color='#2563EB', width=3),
        mode='lines+markers'
    ))
    
    # IPC (inflacion acumulada)
    fig.add_trace(go.Scatter(
        x=df['anio'],
        y=df['ipc_idx'],
        name='IPC (Inflacion)',
        line=dict(color='#DC2626', width=2, dash='dash'),
        mode='lines+markers'
    ))
    
    # Dolar
    fig.add_trace(go.Scatter(
        x=df['anio'],
        y=df['dolar_idx'],
        name='Dolar Oficial',
        line=dict(color='#059669', width=2, dash='dot'),
        mode='lines+markers'
    ))
    
    # Linea base 100
    fig.add_hline(y=100, line_dash="solid", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="Indice (Base 100)",
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template="plotly_white",
        height=450
    )
    
    return fig

def grafico_patrimonio_usd(df, titulo="Patrimonio en Dolares"):
    """Genera grafico de patrimonio medido en USD."""
    
    if df.empty:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['anio'],
        y=df['patrimonio_usd'],
        name='Patrimonio USD',
        marker_color='#2563EB',
        text=[f"USD {v:,.0f}" for v in df['patrimonio_usd']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=titulo,
        xaxis_title="Año",
        yaxis_title="Patrimonio Promedio (USD)",
        template="plotly_white",
        height=400
    )
    
    return fig

def tabla_variacion_real(df):
    """Genera tabla con variaciones reales."""
    
    if df.empty:
        return pd.DataFrame()
    
    tabla = df[['anio', 'patrimonio_promedio', 'patrimonio_usd', 'inflacion']].copy()
    tabla.columns = ['Año', 'Patrimonio $', 'Patrimonio USD', 'Inflacion %']
    
    # Calcular variacion interanual
    tabla['Var. Nominal %'] = tabla['Patrimonio $'].pct_change() * 100
    tabla['Var. Real %'] = tabla['Var. Nominal %'] - tabla['Inflacion %']
    
    # Formatear con manejo de None/NaN
    def fmt_pesos(x):
        if pd.isna(x) or x is None:
            return "-"
        return f"${x:,.0f}"
    
    def fmt_usd(x):
        if pd.isna(x) or x is None:
            return "-"
        return f"USD {x:,.0f}"
    
    def fmt_pct(x):
        if pd.isna(x) or x is None:
            return "-"
        return f"{x:+.1f}%"
    
    def fmt_pct_simple(x):
        if pd.isna(x) or x is None:
            return "-"
        return f"{x:.1f}%"
    
    tabla['Patrimonio $'] = tabla['Patrimonio $'].apply(fmt_pesos)
    tabla['Patrimonio USD'] = tabla['Patrimonio USD'].apply(fmt_usd)
    tabla['Inflacion %'] = tabla['Inflacion %'].apply(fmt_pct_simple)
    tabla['Var. Nominal %'] = tabla['Var. Nominal %'].apply(fmt_pct)
    tabla['Var. Real %'] = tabla['Var. Real %'].apply(fmt_pct)
    
    return tabla

def mostrar_analisis_patrimonial(db, legislador_id=None, bloque=None, camara=None):
    """Componente principal que muestra el analisis patrimonial comparativo."""
    
    # Obtener datos
    df_patrimonio = get_evolucion_patrimonial(db, legislador_id, bloque, camara)
    df_indicadores = get_indicadores_anuales(db)
    
    if df_patrimonio.empty:
        st.info("No hay datos de DDJJ para el filtro seleccionado.")
        return
    
    if df_indicadores.empty:
        st.warning("No hay indicadores economicos cargados. Ejecuta el script de ingesta.")
        return
    
    # Calcular indices
    df = calcular_indices_base_100(df_patrimonio, df_indicadores)
    
    if df.empty:
        st.warning("No hay datos suficientes para comparar.")
        return
    
    # Metricas resumen
    anio_inicial = df['anio'].min()
    anio_final = df['anio'].max()
    
    patrimonio_inicial = df[df['anio'] == anio_inicial]['patrimonio_promedio'].values[0]
    patrimonio_final = df[df['anio'] == anio_final]['patrimonio_promedio'].values[0]
    
    patrimonio_usd_inicial = df[df['anio'] == anio_inicial]['patrimonio_usd'].values[0]
    patrimonio_usd_final = df[df['anio'] == anio_final]['patrimonio_usd'].values[0]
    
    var_nominal = ((patrimonio_final / patrimonio_inicial) - 1) * 100
    var_usd = ((patrimonio_usd_final / patrimonio_usd_inicial) - 1) * 100
    
    inflacion_acum = df[df['anio'] == anio_final]['ipc_idx'].values[0] - 100
    var_real = var_nominal - inflacion_acum
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"Var. Nominal ({anio_inicial}-{anio_final})",
            f"{var_nominal:+,.1f}%",
            delta=None
        )
    
    with col2:
        st.metric(
            "Inflacion Acumulada",
            f"{inflacion_acum:,.1f}%",
            delta=None
        )
    
    with col3:
        delta_color = "normal" if var_real > 0 else "inverse"
        st.metric(
            "Variacion Real",
            f"{var_real:+,.1f}%",
            delta="Gano vs inflacion" if var_real > 0 else "Perdio vs inflacion",
            delta_color=delta_color
        )
    
    with col4:
        st.metric(
            "Var. en USD",
            f"{var_usd:+,.1f}%",
            delta=None
        )
    
    st.markdown("---")
    
    # Graficos
    tab1, tab2, tab3 = st.tabs(["Evolucion Comparativa", "Patrimonio en USD", "Tabla Detalle"])
    
    with tab1:
        fig = grafico_evolucion_comparativa(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Base 100 = primer año con datos. Si el patrimonio crece mas que la inflacion, la linea azul esta por encima de la roja.")
    
    with tab2:
        fig = grafico_patrimonio_usd(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Patrimonio promedio convertido a dolares oficiales de fin de año.")
    
    with tab3:
        tabla = tabla_variacion_real(df)
        if not tabla.empty:
            st.dataframe(tabla, use_container_width=True, hide_index=True)
            st.caption("Var. Real = Var. Nominal - Inflacion. Un valor positivo indica ganancia real de patrimonio.")