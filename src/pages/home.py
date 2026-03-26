# -*- coding: utf-8 -*-
"""
Lobby - Página de Inicio
Dashboard para periodistas
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=1800)
def cargar_metricas():
    db = SessionLocal()
    try:
        stats = {}
        stats['legisladores'] = db.execute(text(
            "SELECT COUNT(*) FROM legisladores WHERE mandato_hasta >= CURRENT_DATE"
        )).scalar() or 0
        
        stats['votaciones'] = db.execute(text(
            "SELECT COUNT(*) FROM votaciones_hcdn"
        )).scalar() or 0
        
        stats['ddjj'] = db.execute(text(
            "SELECT COUNT(DISTINCT cuit) FROM ddjj_legisladores WHERE patrimonio_neto > 0"
        )).scalar() or 0
        
        return stats
    finally:
        db.close()

@st.cache_data(ttl=1800)
def buscar_legisladores(termino):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, nombre_completo, camara, bloque
            FROM legisladores
            WHERE mandato_hasta >= CURRENT_DATE
              AND nombre_completo ILIKE :termino
            ORDER BY nombre_completo
            LIMIT 10
        """), {"termino": f"%{termino}%"})
        return pd.DataFrame(result.fetchall(), columns=['id', 'nombre', 'camara', 'bloque'])
    finally:
        db.close()

@st.cache_data(ttl=1800)
def cargar_alertas_destacadas():
    """Carga las alertas más importantes para mostrar en el dashboard."""
    db = SessionLocal()
    try:
        # Top 3 crecimiento patrimonial inusual
        result = db.execute(text("""
            WITH datos AS (
                SELECT 
                    d.funcionario_apellido_nombre as nombre,
                    CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    MAX(CASE WHEN d.anio = 2022 THEN d.patrimonio_neto END) as pat_2022,
                    MAX(CASE WHEN d.anio = 2024 THEN d.patrimonio_neto END) as pat_2024
                FROM ddjj_legisladores d
                WHERE d.patrimonio_neto > 0 AND d.anio IN (2022, 2024)
                GROUP BY d.funcionario_apellido_nombre, d.organismo
                HAVING COUNT(DISTINCT d.anio) = 2
            ),
            inflacion AS (
                SELECT 
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2024) /
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2022) as ratio_ipc
            )
            SELECT 
                d.nombre, d.camara,
                d.pat_2022, d.pat_2024,
                d.pat_2024 / d.pat_2022 as multiplicador,
                (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 as var_real
            FROM datos d, inflacion i
            WHERE d.pat_2022 > 0
              AND (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 > 100
            ORDER BY var_real DESC
            LIMIT 3
        """))
        return pd.DataFrame(result.fetchall(), columns=['nombre', 'camara', 'pat_2022', 'pat_2024', 'multiplicador', 'var_real'])
    finally:
        db.close()

@st.cache_data(ttl=1800)
def cargar_ultimas_votaciones(limit=5):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                acta_id,
                TO_DATE(fecha, 'DD/MM/YYYY') as fecha,
                asunto,
                afirmativos,
                negativos
            FROM votaciones_hcdn
            WHERE asunto IS NOT NULL AND asunto != ''
            ORDER BY TO_DATE(fecha, 'DD/MM/YYYY') DESC
            LIMIT :limit
        """), {"limit": limit})
        df = pd.DataFrame(result.fetchall(), columns=['acta_id', 'fecha', 'asunto', 'afirmativos', 'negativos'])
        return df
    finally:
        db.close()

@st.cache_data(ttl=1800)
def cargar_votacion_mas_ajustada():
    """La votación más reñida reciente."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                asunto,
                TO_DATE(fecha, 'DD/MM/YYYY') as fecha,
                afirmativos,
                negativos,
                ABS(afirmativos - negativos) as diferencia
            FROM votaciones_hcdn
            WHERE asunto IS NOT NULL 
              AND asunto != ''
              AND afirmativos > 0 
              AND negativos > 0
            ORDER BY diferencia ASC
            LIMIT 1
        """))
        row = result.fetchone()
        if row:
            return {
                'asunto': row[0],
                'fecha': row[1],
                'afirmativos': row[2],
                'negativos': row[3],
                'diferencia': row[4]
            }
        return None
    finally:
        db.close()

# ============================================
# FUNCIONES DE FORMATO
# ============================================

def fmt_pesos(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    if valor >= 1_000_000_000:
        return f"${valor/1_000_000_000:,.1f}B"
    if valor >= 1_000_000:
        return f"${valor/1_000_000:,.0f}M"
    return f"${valor:,.0f}"

# ============================================
# RENDER
# ============================================

def render():
    # Header
    st.markdown("""
    <div style="margin-bottom: 1.5rem;">
        <h1 style="margin-bottom: 0.3rem;">Inteligencia Publica</h1>
        <p style="color: #6B7280; font-size: 1.1rem; margin: 0;">
            Datos del Congreso argentino para periodistas e investigadores
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ========================================
    # BUSCADOR DE LEGISLADORES
    # ========================================
    
    st.markdown("### Buscar legislador")
    
    busqueda = st.text_input(
        "Buscar",
        placeholder="Escribi el nombre o apellido...",
        key="busq_home",
        label_visibility="collapsed"
    )
    
    if busqueda and len(busqueda) >= 2:
        resultados = buscar_legisladores(busqueda)
        if not resultados.empty:
            for _, row in resultados.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"""
                    <div style="padding: 0.5rem 0; border-bottom: 1px solid #E5E7EB;">
                        <span style="font-weight: 600;">{row['nombre']}</span>
                        <span style="color: #6B7280; font-size: 0.9rem;"> · {row['camara']} · {row['bloque'] or 'Sin bloque'}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    if st.button("Ver perfil", key=f"ver_{row['id']}"):
                        st.session_state['legislador_seleccionado'] = row['id']
                        st.session_state['menu_selection'] = 'Legisladores'
                        st.rerun()
        else:
            st.caption("No se encontraron legisladores con ese nombre.")
    
    st.markdown("---")
    
    # ========================================
    # DOS COLUMNAS: ALERTAS + VOTACIONES
    # ========================================
    
    col_izq, col_der = st.columns([1, 1])
    
    # -------- COLUMNA IZQUIERDA: ALERTAS --------
    with col_izq:
        st.markdown("### Alertas patrimoniales")
        st.caption("Crecimiento inusual entre 2022-2024")
        
        df_alertas = cargar_alertas_destacadas()
        
        if not df_alertas.empty:
            for _, row in df_alertas.iterrows():
                st.markdown(f"""
                <div style="background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 0.8rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0;">
                    <div style="font-weight: 600; color: #1F2937;">{row['nombre']}</div>
                    <div style="font-size: 0.85rem; color: #6B7280;">{row['camara']}</div>
                    <div style="margin-top: 0.4rem;">
                        <span style="color: #059669; font-weight: 600;">x{row['multiplicador']:.1f}</span>
                        <span style="color: #6B7280; font-size: 0.9rem;"> en 2 anios ({fmt_pesos(row['pat_2022'])} → {fmt_pesos(row['pat_2024'])})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("Ver todas las alertas →", key="btn_alertas"):
                st.session_state['menu_selection'] = 'Alertas'
                st.rerun()
        else:
            st.info("No hay alertas para mostrar.")
    
    # -------- COLUMNA DERECHA: VOTACIONES --------
    with col_der:
        st.markdown("### Ultimas votaciones")
        
        df_votaciones = cargar_ultimas_votaciones(5)
        
        if not df_votaciones.empty:
            for _, row in df_votaciones.iterrows():
                fecha_str = row['fecha'].strftime('%d/%m') if pd.notna(row['fecha']) else '-'
                asunto_corto = row['asunto'][:60] + '...' if len(str(row['asunto'])) > 60 else row['asunto']
                
                st.markdown(f"""
                <div style="padding: 0.6rem 0; border-bottom: 1px solid #E5E7EB;">
                    <div style="font-size: 0.9rem; color: #1F2937;">{asunto_corto}</div>
                    <div style="font-size: 0.8rem; color: #6B7280; margin-top: 0.2rem;">
                        {fecha_str} · 
                        <span style="color: #059669;">{row['afirmativos'] or 0}✓</span> 
                        <span style="color: #DC2626;">{row['negativos'] or 0}✗</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("Ver todas las votaciones →", key="btn_votaciones"):
                st.session_state['menu_selection'] = 'Votaciones'
                st.rerun()
        else:
            st.info("No hay votaciones recientes.")
    
    st.markdown("---")
    
    # ========================================
    # VOTACION MAS AJUSTADA
    # ========================================
    
    votacion_ajustada = cargar_votacion_mas_ajustada()
    
    if votacion_ajustada:
        st.markdown("### La votacion mas renida")
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); padding: 1.2rem; border-radius: 12px; border-left: 4px solid #F59E0B;">
            <div style="font-weight: 600; font-size: 1rem; color: #1F2937; margin-bottom: 0.5rem;">
                {votacion_ajustada['asunto'][:150]}{'...' if len(str(votacion_ajustada['asunto'])) > 150 else ''}
            </div>
            <div style="display: flex; gap: 1.5rem; align-items: center;">
                <div>
                    <span style="font-size: 1.5rem; font-weight: 700; color: #059669;">{votacion_ajustada['afirmativos']}</span>
                    <span style="color: #6B7280;"> a favor</span>
                </div>
                <div style="font-size: 1.2rem; color: #6B7280;">vs</div>
                <div>
                    <span style="font-size: 1.5rem; font-weight: 700; color: #DC2626;">{votacion_ajustada['negativos']}</span>
                    <span style="color: #6B7280;"> en contra</span>
                </div>
                <div style="background: white; padding: 0.4rem 0.8rem; border-radius: 8px;">
                    <span style="font-weight: 700; color: #92400E;">Diferencia: {votacion_ajustada['diferencia']} votos</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ========================================
    # METRICAS Y FOOTER
    # ========================================
    
    metricas = cargar_metricas()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Legisladores vigentes", f"{metricas['legisladores']:,}")
    col2.metric("Votaciones HCDN", f"{metricas['votaciones']:,}")
    col3.metric("Legisladores con DDJJ", f"{metricas['ddjj']:,}")
    
    st.markdown("""
    <div style="text-align: center; color: #9CA3AF; font-size: 0.85rem; margin-top: 2rem;">
        Datos de fuentes publicas: HCDN, Oficina Anticorrupcion, INDEC<br>
        <a href="mailto:lobby.matufia@gmail.com" style="color: #6B7280;">lobby.matufia@gmail.com</a>
    </div>
    """, unsafe_allow_html=True)