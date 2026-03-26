# -*- coding: utf-8 -*-
"""
Lobby - Página de Votaciones
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES AUXILIARES
# ============================================

ENCODING = {
    '¾': 'ó', 'ß': 'á', '±': 'ñ', 'Ý': 'í', '┴': 'Á',
    '═': 'Í', 'Ë': 'Ó', 'Ð': 'Ñ', 'â': 'â',
}

def limpiar(texto):
    if not texto:
        return ''
    for mal, bien in ENCODING.items():
        texto = texto.replace(mal, bien)
    return texto

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_votaciones_hcdn(limit=50, offset=0):
    """Carga votaciones de HCDN con paginación."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                acta_id, 
                TO_DATE(fecha, 'DD/MM/YYYY') as fecha,
                asunto,
                resultado,
                afirmativos,
                negativos,
                abstenciones,
                ausentes
            FROM votaciones_hcdn
            WHERE asunto IS NOT NULL AND asunto != ''
            ORDER BY TO_DATE(fecha, 'DD/MM/YYYY') DESC, acta_id DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset})
        df = pd.DataFrame(result.fetchall(), columns=['acta_id', 'fecha', 'asunto', 'resultado', 'afirmativos', 'negativos', 'abstenciones', 'ausentes'])
        df['asunto'] = df['asunto'].apply(limpiar)
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def contar_votaciones():
    """Cuenta total de votaciones."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT COUNT(*) FROM votaciones_hcdn
            WHERE asunto IS NOT NULL AND asunto != ''
        """))
        return result.scalar()
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_votaciones_ajustadas(limit=10):
    """Votaciones con resultado ajustado (diferencia < 20 votos)."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                acta_id,
                TO_DATE(fecha, 'DD/MM/YYYY') as fecha,
                asunto,
                resultado,
                afirmativos,
                negativos,
                ABS(afirmativos - negativos) as diferencia
            FROM votaciones_hcdn
            WHERE asunto IS NOT NULL 
              AND asunto != ''
              AND afirmativos > 0 
              AND negativos > 0
              AND ABS(afirmativos - negativos) < 20
            ORDER BY diferencia ASC, TO_DATE(fecha, 'DD/MM/YYYY') DESC
            LIMIT :limit
        """), {"limit": limit})
        df = pd.DataFrame(result.fetchall(), columns=['acta_id', 'fecha', 'asunto', 'resultado', 'afirmativos', 'negativos', 'diferencia'])
        df['asunto'] = df['asunto'].apply(limpiar)
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_votos_votacion(acta_id):
    """Carga votos individuales de una votación."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                vh.legislador,
                vh.bloque,
                vh.voto,
                l.nombre_completo
            FROM votos_hcdn vh
            LEFT JOIN legisladores l ON vh.legislador_id = l.id
            WHERE vh.acta_id = :acta_id
            ORDER BY vh.bloque, vh.legislador
        """), {"acta_id": acta_id})
        return pd.DataFrame(result.fetchall(), columns=['legislador_raw', 'bloque', 'voto', 'nombre'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def buscar_votaciones(termino, limit=50):
    """Busca votaciones por término."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                acta_id,
                TO_DATE(fecha, 'DD/MM/YYYY') as fecha,
                asunto,
                resultado,
                afirmativos,
                negativos,
                abstenciones,
                ausentes
            FROM votaciones_hcdn
            WHERE asunto ILIKE :termino
            ORDER BY TO_DATE(fecha, 'DD/MM/YYYY') DESC
            LIMIT :limit
        """), {"termino": f"%{termino}%", "limit": limit})
        df = pd.DataFrame(result.fetchall(), columns=['acta_id', 'fecha', 'asunto', 'resultado', 'afirmativos', 'negativos', 'abstenciones', 'ausentes'])
        df['asunto'] = df['asunto'].apply(limpiar)
        return df
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Votaciones")
    st.markdown("<div class='page-subtitle'>Como voto cada legislador en la Camara de Diputados</div>", unsafe_allow_html=True)
    
    # Tabs principales
    tab1, tab2 = st.tabs(["Todas las votaciones", "Votaciones ajustadas"])
    
    # ========================================
    # TAB 1: TODAS LAS VOTACIONES
    # ========================================
    with tab1:
        # Controles
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            busqueda = st.text_input(
                "Buscar por tema", 
                placeholder="Ej: Presupuesto, Jubilaciones, Ley Bases...",
                key="vot_busq"
            )
        
        with col2:
            cant_mostrar = st.selectbox(
                "Mostrar",
                [10, 20, 50],
                index=0,
                key="vot_cant"
            )
        
        with col3:
            total_votaciones = contar_votaciones()
            st.metric("Total disponible", f"{total_votaciones:,}")
        
        # Paginación
        if 'pagina_votaciones' not in st.session_state:
            st.session_state['pagina_votaciones'] = 0
        
        # Cargar datos
        if busqueda:
            df = buscar_votaciones(busqueda, limit=100)
            st.caption(f"Resultados para '{busqueda}': {len(df)} votaciones")
        else:
            offset = st.session_state['pagina_votaciones'] * cant_mostrar
            df = cargar_votaciones_hcdn(limit=cant_mostrar, offset=offset)
        
        if df.empty:
            st.info("No se encontraron votaciones.")
        else:
            # Mostrar votaciones
            for _, row in df.iterrows():
                fecha_str = row['fecha'].strftime('%d/%m/%Y') if pd.notna(row['fecha']) else '-'
                
                # Determinar color según resultado
                if row['afirmativos'] > row['negativos']:
                    color_borde = "#059669"  # Verde
                    resultado_texto = "APROBADO"
                elif row['negativos'] > row['afirmativos']:
                    color_borde = "#DC2626"  # Rojo
                    resultado_texto = "RECHAZADO"
                else:
                    color_borde = "#6B7280"  # Gris
                    resultado_texto = row['resultado'] or '-'
                
                with st.container():
                    st.markdown(f"""
                    <div style="border-left: 4px solid {color_borde}; padding: 0.8rem 1rem; margin-bottom: 0.8rem; background: white; border-radius: 0 8px 8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                            <div style="flex: 1;">
                                <div style="font-weight: 600; color: #1F2937; margin-bottom: 0.3rem;">{row['asunto'][:200]}{'...' if len(row['asunto']) > 200 else ''}</div>
                                <div style="font-size: 0.85rem; color: #6B7280;">{fecha_str}</div>
                            </div>
                            <div style="text-align: right; min-width: 120px;">
                                <div style="font-size: 0.9rem;">
                                    <span style="color: #059669; font-weight: 600;">{row['afirmativos'] or 0} a favor</span>
                                    <span style="color: #6B7280;"> · </span>
                                    <span style="color: #DC2626; font-weight: 600;">{row['negativos'] or 0} en contra</span>
                                </div>
                                <div style="font-size: 0.8rem; color: #6B7280;">
                                    {row['abstenciones'] or 0} abst. · {row['ausentes'] or 0} aus.
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Expander para ver detalle de votos
                    with st.expander(f"Ver votos individuales"):
                        df_votos = cargar_votos_votacion(row['acta_id'])
                        
                        if not df_votos.empty:
                            col_a, col_b, col_c = st.columns(3)
                            
                            with col_a:
                                afavor = df_votos[df_votos['voto'] == 'AFIRMATIVO']
                                st.markdown(f"**A favor ({len(afavor)})**")
                                for bloque in afavor['bloque'].unique():
                                    n = len(afavor[afavor['bloque'] == bloque])
                                    st.caption(f"{bloque or 'Sin bloque'}: {n}")
                            
                            with col_b:
                                encontra = df_votos[df_votos['voto'] == 'NEGATIVO']
                                st.markdown(f"**En contra ({len(encontra)})**")
                                for bloque in encontra['bloque'].unique():
                                    n = len(encontra[encontra['bloque'] == bloque])
                                    st.caption(f"{bloque or 'Sin bloque'}: {n}")
                            
                            with col_c:
                                ausentes = df_votos[df_votos['voto'] == 'AUSENTE']
                                st.markdown(f"**Ausentes ({len(ausentes)})**")
                                for bloque in ausentes['bloque'].unique():
                                    n = len(ausentes[ausentes['bloque'] == bloque])
                                    st.caption(f"{bloque or 'Sin bloque'}: {n}")
                        else:
                            st.caption("No hay datos de votos individuales para esta votación.")
            
            # Controles de paginación (solo si no hay búsqueda)
            if not busqueda:
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    if st.session_state['pagina_votaciones'] > 0:
                        if st.button("← Anteriores"):
                            st.session_state['pagina_votaciones'] -= 1
                            st.rerun()
                
                with col2:
                    pagina_actual = st.session_state['pagina_votaciones'] + 1
                    total_paginas = (total_votaciones // cant_mostrar) + 1
                    st.markdown(f"<div style='text-align: center; color: #6B7280;'>Página {pagina_actual} de {total_paginas}</div>", unsafe_allow_html=True)
                
                with col3:
                    if (st.session_state['pagina_votaciones'] + 1) * cant_mostrar < total_votaciones:
                        if st.button("Siguientes →"):
                            st.session_state['pagina_votaciones'] += 1
                            st.rerun()
    
    # ========================================
    # TAB 2: VOTACIONES AJUSTADAS
    # ========================================
    with tab2:
        st.markdown("### Votaciones mas renidas")
        st.caption("Votaciones donde la diferencia entre a favor y en contra fue menor a 20 votos")
        
        df_ajustadas = cargar_votaciones_ajustadas(limit=20)
        
        if df_ajustadas.empty:
            st.info("No se encontraron votaciones ajustadas.")
        else:
            for _, row in df_ajustadas.iterrows():
                fecha_str = row['fecha'].strftime('%d/%m/%Y') if pd.notna(row['fecha']) else '-'
                
                st.markdown(f"""
                <div style="border-left: 4px solid #F59E0B; padding: 0.8rem 1rem; margin-bottom: 0.8rem; background: #FFFBEB; border-radius: 0 8px 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #1F2937;">{row['asunto'][:200]}{'...' if len(str(row['asunto'])) > 200 else ''}</div>
                            <div style="font-size: 0.85rem; color: #6B7280; margin-top: 0.3rem;">{fecha_str}</div>
                        </div>
                        <div style="text-align: right; min-width: 150px;">
                            <div style="background: #FEF3C7; padding: 0.3rem 0.6rem; border-radius: 4px; display: inline-block;">
                                <span style="font-weight: 700; color: #92400E;">Diferencia: {int(row['diferencia'])} votos</span>
                            </div>
                            <div style="font-size: 0.9rem; margin-top: 0.3rem;">
                                <span style="color: #059669;">{row['afirmativos']}</span> vs 
                                <span style="color: #DC2626;">{row['negativos']}</span>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)