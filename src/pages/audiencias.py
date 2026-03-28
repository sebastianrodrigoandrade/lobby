# -*- coding: utf-8 -*-
"""
Lobby - Página de Audiencias
Audiencias del Poder Ejecutivo Nacional
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_estadisticas_audiencias():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT sujeto_obligado_nombre) as funcionarios,
                COUNT(DISTINCT solicitante_nombre) as solicitantes,
                MIN(anio) as desde,
                MAX(anio) as hasta
            FROM audiencias_ejecutivo
        """))
        return dict(zip(result.keys(), result.fetchone()))
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_audiencias(filtros, limit=50, offset=0):
    db = SessionLocal()
    try:
        where = ["1=1"]
        params = {"limit": limit, "offset": offset}
        
        if filtros.get('anio'):
            where.append("anio = :anio")
            params['anio'] = filtros['anio']
        
        if filtros.get('funcionario'):
            where.append("sujeto_obligado_nombre ILIKE :func")
            params['func'] = f"%{filtros['funcionario']}%"
        
        if filtros.get('solicitante'):
            where.append("solicitante_nombre ILIKE :sol")
            params['sol'] = f"%{filtros['solicitante']}%"
        
        if filtros.get('dependencia'):
            where.append("sujeto_obligado_dependencia ILIKE :dep")
            params['dep'] = f"%{filtros['dependencia']}%"
        
        if filtros.get('motivo'):
            where.append("(motivo ILIKE :mot OR sintesis ILIKE :mot)")
            params['mot'] = f"%{filtros['motivo']}%"
        
        where_clause = " AND ".join(where)
        
        # Contar total
        count_result = db.execute(text(f"""
            SELECT COUNT(*) FROM audiencias_ejecutivo WHERE {where_clause}
        """), params)
        total = count_result.scalar()
        
        # Obtener datos
        result = db.execute(text(f"""
            SELECT fecha, sujeto_obligado_nombre, sujeto_obligado_cargo,
                   sujeto_obligado_dependencia, solicitante_nombre, 
                   solicitante_ocupacion, motivo, lugar
            FROM audiencias_ejecutivo
            WHERE {where_clause}
            ORDER BY fecha DESC
            LIMIT :limit OFFSET :offset
        """), params)
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'fecha', 'funcionario', 'cargo', 'dependencia', 
            'solicitante', 'ocupacion', 'motivo', 'lugar'
        ])
        
        return df, total
    finally:
        db.close()

@st.cache_data(ttl=3600)
def top_funcionarios(limit=20):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT sujeto_obligado_nombre, sujeto_obligado_cargo, 
                   sujeto_obligado_dependencia, COUNT(*) as audiencias
            FROM audiencias_ejecutivo
            GROUP BY sujeto_obligado_nombre, sujeto_obligado_cargo, sujeto_obligado_dependencia
            ORDER BY audiencias DESC
            LIMIT :limit
        """), {"limit": limit})
        return pd.DataFrame(result.fetchall(), columns=['nombre', 'cargo', 'dependencia', 'audiencias'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def top_solicitantes(limit=20):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT solicitante_nombre, solicitante_ocupacion, COUNT(*) as audiencias
            FROM audiencias_ejecutivo
            WHERE solicitante_nombre IS NOT NULL AND solicitante_nombre != ''
            GROUP BY solicitante_nombre, solicitante_ocupacion
            ORDER BY audiencias DESC
            LIMIT :limit
        """), {"limit": limit})
        return pd.DataFrame(result.fetchall(), columns=['nombre', 'ocupacion', 'audiencias'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def audiencias_por_anio():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT anio, COUNT(*) as audiencias
            FROM audiencias_ejecutivo
            GROUP BY anio
            ORDER BY anio
        """))
        return pd.DataFrame(result.fetchall(), columns=['anio', 'audiencias'])
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Audiencias")
    st.markdown("<div class='page-subtitle'>Audiencias del Poder Ejecutivo Nacional (datos.gob.ar)</div>", unsafe_allow_html=True)
    
    # Estadísticas
    stats = cargar_estadisticas_audiencias()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total audiencias", f"{stats['total']:,}")
    col2.metric("Funcionarios", f"{stats['funcionarios']:,}")
    col3.metric("Solicitantes", f"{stats['solicitantes']:,}")
    col4.metric("Periodo", f"{stats['desde']}-{stats['hasta']}")
    
    st.markdown("---")
    
    # Tabs
    tabs = st.tabs(["Buscar", "Top Funcionarios", "Top Solicitantes", "Por Año"])
    
    # ========================================
    # TAB BUSCAR
    # ========================================
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            filtro_func = st.text_input("Funcionario", placeholder="Nombre del funcionario...")
            filtro_dep = st.text_input("Dependencia", placeholder="Ministerio, Secretaría...")
        with col2:
            filtro_sol = st.text_input("Solicitante", placeholder="Quien pidió la audiencia...")
            filtro_motivo = st.text_input("Motivo/Tema", placeholder="Buscar en motivo...")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            filtro_anio = st.selectbox("Año", [None] + list(range(2025, 2016, -1)), format_func=lambda x: "Todos" if x is None else str(x))
        
        # Paginación
        if 'aud_page' not in st.session_state:
            st.session_state['aud_page'] = 0
        
        page_size = 25
        
        filtros = {
            'funcionario': filtro_func,
            'solicitante': filtro_sol,
            'dependencia': filtro_dep,
            'motivo': filtro_motivo,
            'anio': filtro_anio
        }
        
        df, total = cargar_audiencias(filtros, limit=page_size, offset=st.session_state['aud_page'] * page_size)
        
        st.markdown(f"**{total:,} audiencias encontradas**")
        
        if not df.empty:
            for _, row in df.iterrows():
                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                        <div>
                            <span style="font-weight: 600; color: #1E3A5F;">{row['funcionario']}</span>
                            <span style="color: #6B7280; font-size: 0.9rem;"> - {row['cargo'] or ''}</span>
                        </div>
                        <span style="color: #6B7280; font-size: 0.85rem;">{row['fecha'] or ''}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #6B7280; margin: 0.3rem 0;">{row['dependencia'] or ''}</div>
                    <div style="margin: 0.5rem 0;">
                        <span style="font-size: 0.85rem;">Solicitante: </span>
                        <span style="font-weight: 500;">{row['solicitante'] or 'No especificado'}</span>
                        <span style="color: #6B7280; font-size: 0.85rem;"> ({row['ocupacion'] or ''})</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #374151; background: #F9FAFB; padding: 0.5rem; border-radius: 4px;">
                        {row['motivo'][:200] if row['motivo'] else ''}{'...' if row['motivo'] and len(row['motivo']) > 200 else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Controles de paginación
            total_pages = (total // page_size) + (1 if total % page_size > 0 else 0)
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("← Anterior", disabled=st.session_state['aud_page'] == 0):
                    st.session_state['aud_page'] -= 1
                    st.rerun()
            with col2:
                st.markdown(f"<div style='text-align: center;'>Página {st.session_state['aud_page'] + 1} de {total_pages}</div>", unsafe_allow_html=True)
            with col3:
                if st.button("Siguiente →", disabled=st.session_state['aud_page'] >= total_pages - 1):
                    st.session_state['aud_page'] += 1
                    st.rerun()
    
    # ========================================
    # TAB TOP FUNCIONARIOS
    # ========================================
    with tabs[1]:
        st.markdown("### Funcionarios con más audiencias")
        df_top = top_funcionarios(30)
        
        for i, (_, row) in enumerate(df_top.iterrows()):
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid #F3F4F6;">
                <span style="font-weight: 700; color: #6B7280; width: 30px;">#{i+1}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600;">{row['nombre']}</div>
                    <div style="font-size: 0.85rem; color: #6B7280;">{row['cargo'] or ''} - {row['dependencia'] or ''}</div>
                </div>
                <span style="font-weight: 700; color: #2563EB;">{row['audiencias']:,}</span>
            </div>
            """, unsafe_allow_html=True)
    
    # ========================================
    # TAB TOP SOLICITANTES
    # ========================================
    with tabs[2]:
        st.markdown("### Solicitantes con más audiencias")
        df_sol = top_solicitantes(30)
        
        for i, (_, row) in enumerate(df_sol.iterrows()):
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid #F3F4F6;">
                <span style="font-weight: 700; color: #6B7280; width: 30px;">#{i+1}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600;">{row['nombre']}</div>
                    <div style="font-size: 0.85rem; color: #6B7280;">{row['ocupacion'] or ''}</div>
                </div>
                <span style="font-weight: 700; color: #059669;">{row['audiencias']:,}</span>
            </div>
            """, unsafe_allow_html=True)
    
    # ========================================
    # TAB POR AÑO
    # ========================================
    with tabs[3]:
        st.markdown("### Audiencias por año")
        df_anio = audiencias_por_anio()
        
        st.bar_chart(df_anio.set_index('anio'))
        
        st.markdown("---")
        st.dataframe(
            df_anio.rename(columns={'anio': 'Año', 'audiencias': 'Audiencias'}),
            use_container_width=True,
            hide_index=True
        )
